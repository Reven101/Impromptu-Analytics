"""Bygger historien «Hundre år til Kina» — hvor lang tid Ibsen brukte til hvert land.

Kjøring:

    python pipeline/bygg_historie_spredningen.py
    python pipeline/kontrakt.py
    python pipeline/bygg_manifest.py

Målet er ett tall per land: median antall år fra et Ibsen-verk ble utgitt til det
ble spilt første gang der. Medianen er tatt over verkene, ikke over oppsetningene —
ellers ville et land som spiller «Et dukkehjem» femti ganger telt femti ganger.

Tre valg som avgjør hva tallet betyr:

- **«Første registrerte», ikke «første».** IbsenStage er et norskdrevet arkiv, og
  dekningen av tidlig ikke-europeisk teater er dårligere enn av europeisk. Skjevheten
  peker én vei: ankomsten ser senere ut enn den var. Det står i teksten.
- **Land med få verk gir støyende tall.** Qatar har ett verk og havner på 147 år —
  det betyr «ett stykke kom nylig», ikke «Ibsen brukte 147 år hit». Antall verk følger
  med i tabellen under kartet.
- **Kartet viser tidspunkt, ikke volum.** Et koroplettkart vekter etter areal.
  Russland ville dominert et bilde Norge egentlig eier med sine 4 743 oppsetninger.
  Volumet hører hjemme i teksten og i kortene.
"""

from __future__ import annotations

import collections
import json
import os
import statistics
from pathlib import Path

import kontrakt
from kontrakt import INNHOLD_DIR

RAADATA_DIR = Path(
    os.environ.get("IBSENSTAGE_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ibsenstage"
)
SLUG = "hundre-ar-til-kina"

# Landnavn på norsk. Håndskrevet: kilden er engelsk, og et norsk nettsted skal si
# «Tyskland». Land som ikke står her beholder kildens skrivemåte.
NORSK = {
    "Norway": "Norge", "Sweden": "Sverige", "Denmark": "Danmark", "Finland": "Finland",
    "Iceland": "Island", "Germany": "Tyskland", "Austria": "Østerrike",
    "Switzerland": "Sveits", "Netherlands": "Nederland", "Belgium": "Belgia",
    "France": "Frankrike", "Italy": "Italia", "Spain": "Spania", "Portugal": "Portugal",
    "England": "England", "Scotland": "Skottland", "Wales": "Wales",
    "Northern Ireland": "Nord-Irland", "Ireland": "Irland",
    "United States of America": "USA", "Canada": "Canada", "Mexico": "Mexico",
    "Brazil": "Brasil", "Argentina": "Argentina", "Chile": "Chile", "Peru": "Peru",
    "Uruguay": "Uruguay", "Colombia": "Colombia", "Venezuela": "Venezuela",
    "Cuba": "Cuba", "Poland": "Polen", "Czech Republic": "Tsjekkia",
    "Slovak Republic": "Slovakia", "Hungary": "Ungarn", "Romania": "Romania",
    "Bulgaria": "Bulgaria", "Greece": "Hellas", "Turkey": "Tyrkia", "Russia": "Russland",
    "Ukraine": "Ukraina", "Belarus": "Hviterussland", "Estonia": "Estland",
    "Latvia": "Latvia", "Lithuania": "Litauen", "Croatia": "Kroatia",
    "Serbia": "Serbia", "Slovenia": "Slovenia", "Bosnia-Herzegovina": "Bosnia-Hercegovina",
    "Macedonia": "Nord-Makedonia", "Montenegro": "Montenegro", "Albania": "Albania",
    "Japan": "Japan", "China": "Kina", "South Korea": "Sør-Korea",
    "Korea, South": "Sør-Korea", "India": "India", "Bangladesh": "Bangladesh",
    "Pakistan": "Pakistan", "Sri Lanka": "Sri Lanka", "Nepal": "Nepal",
    "Iran": "Iran", "Iraq": "Irak", "Israel": "Israel", "Egypt": "Egypt",
    "South Africa": "Sør-Afrika", "Australia": "Australia", "New Zealand": "New Zealand",
    "Indonesia": "Indonesia", "Vietnam": "Vietnam", "Thailand": "Thailand",
    "Philippines": "Filippinene", "Singapore": "Singapore", "Malaysia": "Malaysia",
    "Greenland": "Grønland", "Faroe Islands": "Færøyene", "Luxembourg": "Luxembourg",
    "Kazakhstan": "Kasakhstan", "Turkmenistan": "Turkmenistan", "Qatar": "Qatar",
    "Togo": "Togo", "Dominican Republic": "Den dominikanske republikk",
}


def _les() -> list[dict]:
    return json.loads((RAADATA_DIR / "ibsenstage_analyse.json")
                      .read_text(encoding="utf-8"))["oppsetninger"]


def _verksaar() -> dict[str, int]:
    """Utgivelsesår PER VERK, fra ibsenstage_verk.json.

    Analysetabellens `verk_utgitt` er det ELDSTE verket i oppsetningen — riktig
    for en rad per oppsetning, men feil å bruke per verk. En kompilasjon med både
    «Peer Gynt» og «Rosmersholm» ville gitt Rosmersholm utgivelsesåret 1867 i
    stedet for 1886, og dermed lagt nitten år til hvert eneste land som først så
    stykket i en slik kveld. Feilen er stille: tallet ser rimelig ut.
    """
    v = json.loads((RAADATA_DIR / "ibsenstage_verk.json").read_text(encoding="utf-8"))
    return {x["verk"]: x["utgitt"] for x in v["verk"] if x["utgitt"]}


def _aar_til_forste(rader: list[dict], kode: dict, aar: dict) -> tuple[dict, dict]:
    """Per ISO-kode: median år fra utgivelse til første oppsetning, og antall verk.

    Aggregeringen skjer på ISO-koden, ikke på landnavnet, og det er ikke en detalj:
    England, Skottland, Wales og Nord-Irland deler koden GB. Grupperer man etter
    navn og slår sammen etterpå, overskriver den ene den andre — Englands 18 år
    ville blitt Wales' 120, eller omvendt, avhengig av rekkefølgen i en dict. Kartet
    ville rendret pent og vist feil århundre.
    """
    forste: dict[tuple, int] = {}
    for r in sorted(rader, key=lambda r: r["aar"] or 9999):
        if not (r["aar"] and r["land"]):
            continue
        k = kode.get(r["land"])
        if not k:
            continue
        for v in r["verk"]:
            if v in aar:
                forste.setdefault((k, v), r["aar"] - aar[v])
    per = collections.defaultdict(list)
    for (k, _), n in forste.items():
        per[k].append(n)
    return ({k: round(statistics.median(v)) for k, v in per.items()},
            {k: len(v) for k, v in per.items()})


def main() -> None:
    rader = _les()
    kode = {r["land"]: r["landkode"] for r in rader if r["land"] and r["landkode"]}
    verksaar = _verksaar()
    median, antall_verk = _aar_til_forste(rader, kode, verksaar)

    # Navn per ISO-kode. Deler flere land koden (GB), navngis den samlet — kartet
    # viser én flate, og den skal ikke hete «England».
    SAMLENAVN = {"GB": "Storbritannia"}
    navn: dict[str, str] = {}
    for land, k in kode.items():
        if k in SAMLENAVN:
            navn[k] = SAMLENAVN[k]
        else:
            navn.setdefault(k, NORSK.get(land, land))
    verdier = median

    # Kumulativt antall land som har spilt Ibsen.
    forste_aar = {}
    for r in sorted(rader, key=lambda r: r["aar"] or 9999):
        if r["aar"] and r["land"]:
            forste_aar.setdefault(r["land"], r["aar"])
    kum, punkter = 0, []
    for aar in range(1850, 2027):
        kum += sum(1 for a in forste_aar.values() if a == aar)
        if aar % 5 == 0:
            punkter.append([aar, kum])

    # Ventetiden per verk, målt mot en FAST gruppe land.
    #
    # Å måle mot alle land ser ut som en rangering av stykkene, men er det ikke:
    # korrelasjonen mellom utgivelsesår og «reisetid» er da -0,60, og mekanismen
    # er triviell — et verk fra 1867 har hatt hundre år ekstra på seg til å nå
    # land som først fikk Ibsen i 1990, og de ventetidene drar medianen opp.
    #
    # Måler vi i stedet mot de landene som har satt opp minst 15 av verkene, er
    # grunnlaget likt for alle stykkene. Da blir korrelasjonen -0,88, og det som
    # står igjen er ikke en egenskap ved stykkene i det hele tatt: det er Ibsens
    # egen berømmelse. «Peer Gynt» ventet 46 år på de samme landene som tok imot
    # «Når vi døde vågner» på ett.
    forste_verk = {}
    for r in sorted(rader, key=lambda r: r["aar"] or 9999):
        if not (r["aar"] and r["land"]):
            continue
        for v in r["verk"]:
            if v in verksaar:
                forste_verk.setdefault((v, r["land"]),
                                       (r["aar"] - verksaar[v], verksaar[v]))
    land_per_verk = collections.Counter(l for (_, l) in forste_verk)
    kjerne = {l for l, n in land_per_verk.items() if n >= 15}
    per_verk = collections.defaultdict(list)
    utgitt = {}
    for (v, l), (n, u) in forste_verk.items():
        utgitt[v] = u
        if l in kjerne:
            per_verk[v].append(n)
    rangert = sorted(((v, statistics.median(n), len(n))
                      for v, n in per_verk.items() if len(n) >= 20),
                     key=lambda t: t[1])
    ventetid = sorted(([utgitt[v], round(statistics.median(n))]
                       for v, n in per_verk.items() if len(n) >= 20),
                      key=lambda p: p[0])

    VERK_NORSK = {
        "When We Dead Awaken": "Når vi døde vågner", "Pillars Of Society": "Samfundets støtter",
        "John Gabriel Borkman": "John Gabriel Borkman", "Rosmersholm": "Rosmersholm",
        "Little Eyolf": "Lille Eyolf", "The Master Builder": "Bygmester Solness",
        "The Lady From The Sea": "Fruen fra havet", "Hedda Gabler": "Hedda Gabler",
        "A Doll's House": "Et dukkehjem", "Ghosts": "Gengangere",
        "An Enemy Of The People": "En folkefiende", "The Wild Duck": "Vildanden",
        "Peer Gynt": "Peer Gynt", "Brand": "Brand",
        "The League Of Youth": "De unges forbund", "Love's Comedy": "Kjærlighedens komedie",
        "The Pretenders": "Kongs-emnerne", "The Vikings at Helgeland": "Hærmennene på Helgeland",
        "Lady Inger": "Fru Inger til Østeraad", "Emperor and Galilean": "Kejser og Galilæer",
    }

    data = {
        "meta": {
            "tittel": "Hundre år til Kina",
            "kilde": "IbsenStage, Universitetet i Oslo",
            "kilde_url": "https://ibsenstage.hf.uio.no/",
            "dato_hentet": "2026-08-28",
            "geografi": "115 land",
            "enhet": "år",
            "oppdateringsfrekvens": "Løpende",
            "beskrivelse": (
                "Norden spilte Ibsen året han utga — resten av verden brukte i "
                "median 116 år på det samme, og Kina ventet i 116."
            ),
        },
        "visninger": {
            "hero": {
                "type": "hero",
                "eyebrow": "25 343 oppsetninger, 1850–2026",
                "rader": [
                    {"etikett": "Norden", "verdi": "1 år",
                     "detalj": "fra utgivelse til første oppsetning"},
                    {"etikett": "Tyskland", "verdi": "5 år",
                     "detalj": "USA og Nederland brukte 6"},
                    {"etikett": "Kina", "verdi": "116 år",
                     "detalj": "Bangladesh 120, Sør-Korea 114"},
                ],
                "fotnote": (
                    "Median over de verkene landet har satt opp. Verkenes "
                    "utgivelsesår er hentet fra Wikidata; 28 av 30 har et."
                ),
            },
            "spredning": {
                "type": "verdenskart",
                "tittel": "År fra utgivelse til første kjente oppsetning",
                "undertekst": "Median over verkene i hvert land",
                "enhet": "år",
                "verdier": verdier,
                "navn": navn,
                "antall": antall_verk,
                "antall_navn": "Verk satt opp",
                "tom_etikett": "ingen registrert oppsetning",
            },
            "utbredelse": {
                "type": "tidslinje",
                "tittel": "Land som har spilt Ibsen",
                "undertekst": "Kumulativt, fra første registrerte oppsetning",
                "enhet": "land",
                "serier": [{"navn": "Land", "punkter": punkter}],
            },
            "ventetid": {
                "type": "tidslinje",
                "tittel": "Jo senere Ibsen skrev, jo kortere ventet verden",
                "undertekst": "Median år til oppsetning i de 27 landene som har spilt minst 15 av verkene",
                "enhet": "år",
                "x_navn": "Verkets utgivelsesår",
                "serier": [{"navn": "Ventetid", "punkter": ventetid}],
            },
            "verk": {
                "type": "kortgalleri",
                "tittel": "Samme land, helt ulik ventetid",
                "undertekst": "Median år til oppsetning blant de 27 landene som har spilt minst 15 verk",
                "kort": [
                    {"overtittel": VERK_NORSK.get(v, v), "verdi": f"{m:.0f} år",
                     "detalj": f"utgitt {utgitt[v]}"}
                    for v, m, n in rangert[:3] + rangert[-3:]
                ],
            },
        },
    }

    # Håndskrevet tekst legges oppå det vi nettopp regnet ut. Byggescriptet eier
    # tallene, redaksjon.json eier ordene — ellers forsvinner enhver redigering
    # av tittel eller figurtekst neste gang dette kjøres.
    data, notater = kontrakt.flett_redaksjon(data, SLUG)

    mappe = INNHOLD_DIR / SLUG
    mappe.mkdir(parents=True, exist_ok=True)
    (mappe / "data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if notater:
        print(f"  redaksjon.json overstyrer {len(notater)} felt:")
        for n in notater:
            print(f"    {n}")

    feil = kontrakt.valider_snapshot(data, SLUG)
    print(f"{SLUG}: {len(verdier)} land på kartet, "
          f"{len(punkter)} punkter i tidslinja, {len(rangert)} verk rangert")
    print(f"  validering: {'OK' if not feil else feil}")
    print(f"  {mappe / 'data.json'}")


if __name__ == "__main__":
    main()
