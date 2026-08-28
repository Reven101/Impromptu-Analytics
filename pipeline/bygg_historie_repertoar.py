"""Bygger historien «Verden vil se folkefienden» — hvilke Ibsen-stykker som spilles nå.

Kjøring:

    python pipeline/bygg_historie_repertoar.py
    python pipeline/kontrakt.py
    python pipeline/bygg_manifest.py

Historien har to bevegelser, og de er ikke den samme:

1. **«En folkefiende» har tredoblet seg** som andel av oppsetningene, fra 6,8 % i
   2005–09 til 23,8 % i 2025. Stigningen er monoton over femårsbolker og begynner
   rundt 2010 — lenge før pandemien.
2. **Repertoaret smalnet fra 2017.** Alle ni år fra 2017 har topp tre over 57 % av
   oppsetningene; av de sytten årene før gjelder det bare seks.

To metodevalg som avgjør om tallene tåler vekt:

- **Femårsbolker i andelsgrafen, årstall i konsentrasjonsgrafen.** Årsandelene per
  verk er for støyende til å lese: «Et dukkehjem» går fra 11,7 % (2015) til 23,3 %
  (2016) uten at noe har skjedd. Konsentrasjonen er derimot stabil nok per år til
  at nivåskiftet i 2017 er synlig.
- **2026 utelates.** Arkivet har registreringer fram til oktober 2026, altså etter
  dagens dato: det er annonserte oppsetninger, ikke spilte. Å ta dem med ville
  blandet plan og historie.

Den nærliggende forklaringen — at ferske år er dårligere registrert, og at et
arkiv lettere fanger opp en stor «Et dukkehjem» enn et lite «Vildanden» — holder
ikke: 2025 har 347 oppsetninger i 47 land, mot 389 i 38 land i 2015. Samme mengde
teater, flere land, og likevel halvparten så mange ulike stykker.
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
SLUG = "verden-vil-se-folkefienden"
SISTE_AAR = 2025  # 2026 er annonserte oppsetninger, ikke spilte
FOLKEFIENDE = "An Enemy Of The People"

# Landnavn på norsk for kartet. Håndskrevet; land utenfor lista beholder kildens navn.
NORSK_LAND = {
    "Turkey": "Tyrkia", "Poland": "Polen", "Spain": "Spania", "Germany": "Tyskland",
    "Austria": "Østerrike", "United States of America": "USA", "Czech Republic": "Tsjekkia",
    "Switzerland": "Sveits", "Romania": "Romania", "Argentina": "Argentina",
    "England": "England", "Canada": "Canada", "France": "Frankrike", "Italy": "Italia",
    "Norway": "Norge", "Sweden": "Sverige", "Denmark": "Danmark", "Finland": "Finland",
    "Netherlands": "Nederland", "Hungary": "Ungarn", "Russia": "Russland",
    "Japan": "Japan", "China": "Kina", "India": "India", "Brazil": "Brasil",
    "Greece": "Hellas", "Belgium": "Belgia", "Ireland": "Irland", "Mexico": "Mexico",
    "Australia": "Australia", "South Korea": "Sør-Korea", "Portugal": "Portugal",
}

NORSK = {
    "A Doll's House": "Et dukkehjem", "An Enemy Of The People": "En folkefiende",
    "Peer Gynt": "Peer Gynt", "Hedda Gabler": "Hedda Gabler", "Ghosts": "Gengangere",
    "The Wild Duck": "Vildanden", "The Lady From The Sea": "Fruen fra havet",
    "The Master Builder": "Bygmester Solness", "Rosmersholm": "Rosmersholm",
    "John Gabriel Borkman": "John Gabriel Borkman", "Little Eyolf": "Lille Eyolf",
    "Pillars Of Society": "Samfundets støtter", "Brand": "Brand",
    "When We Dead Awaken": "Når vi døde vågner",
}


def _andeler(rader: list[dict], fra: int, til: int) -> tuple[collections.Counter, int, int]:
    """Verkstellinger i perioden, pluss antall oppsetninger og antall land.

    Et verk telles én gang per oppsetning — `set(r["verk"])` — ellers ville en
    kompilasjon som spiller samme stykke i to bearbeidelser telt dobbelt.
    """
    n = [r for r in rader if r["aar"] and fra <= r["aar"] <= til]
    c = collections.Counter(v for r in n for v in set(r["verk"]))
    return c, len(n), len({r["land"] for r in n if r["land"]})


def main() -> None:
    rader = json.loads((RAADATA_DIR / "ibsenstage_analyse.json")
                       .read_text(encoding="utf-8"))["oppsetninger"]

    # Andel per verk, femårsbolker. Punktet plasseres midt i bolken.
    serier = {v: [] for v in ("A Doll's House", "An Enemy Of The People", "Peer Gynt")}
    for start in range(1950, SISTE_AAR + 1, 5):
        slutt = min(start + 4, SISTE_AAR)
        c, n, _ = _andeler(rader, start, slutt)
        if n < 80:
            continue
        # Midtpunktet regnes av den FAKTISKE bolken, ikke av fem år. Siste bolk
        # er avkortet (2025 alene), og «start + 2» ville plassert den i 2027 —
        # et årstall som ikke finnes i materialet, på en akse leseren tror er tid.
        midt = (start + slutt) // 2
        tot = sum(c.values())
        for v in serier:
            serier[v].append([midt, round(c[v] / tot * 100, 1)])

    # Konsentrasjon per år.
    konsentrasjon = []
    for a in range(2000, SISTE_AAR + 1):
        c, n, _ = _andeler(rader, a, a)
        if n < 50:
            continue
        tot = sum(c.values())
        konsentrasjon.append([a, round(sum(k for _, k in c.most_common(3)) / tot * 100, 1)])

    # Vinnere og tapere: tiåret før mot årene etter pandemibunnen.
    for_c, for_n, for_land = _andeler(rader, 2010, 2019)
    ett_c, ett_n, ett_land = _andeler(rader, 2022, SISTE_AAR)
    for_t, ett_t = sum(for_c.values()), sum(ett_c.values())
    endring = sorted(
        ((v, for_c[v] / for_t * 100, ett_c[v] / ett_t * 100) for v in set(for_c) | set(ett_c)),
        key=lambda t: t[2] - t[1])
    kort = [endring[-1], endring[-2], endring[0], endring[1]]

    # Geografi: hvor stor del av hvert lands EGET Ibsen-repertoar «En folkefiende»
    # utgjør. Absolutte tall ville bare rangert store teaternasjoner på nytt —
    # USA og Tyskland spiller mest Ibsen og dermed mest av alt. Andelen sier noe
    # annet: i Tyrkia er dette ene stykket over halvparten av all Ibsen.
    #
    # Terskelen på 15 oppsetninger holder land med to-tre registreringer ute; en
    # median på «100 %» av én oppsetning er ikke en observasjon.
    kode = {r["land"]: r["landkode"] for r in rader if r["land"] and r["landkode"]}
    nylig = [r for r in rader if r["aar"] and 2015 <= r["aar"] <= SISTE_AAR]
    land_tot = collections.Counter(kode[r["land"]] for r in nylig if r["land"] in kode)
    land_fi = collections.Counter(kode[r["land"]] for r in nylig
                                  if FOLKEFIENDE in r["verk"] and r["land"] in kode)
    TERSKEL = 15
    andel_land = {k: round(land_fi[k] / land_tot[k] * 100)
                  for k in land_tot if land_tot[k] >= TERSKEL}
    navn_land = {}
    for land, k in kode.items():
        if k in andel_land:
            navn_land.setdefault(k, {"GB": "Storbritannia"}.get(k, NORSK_LAND.get(land, land)))

    def pst(verk: str) -> str:
        return f"{round(ett_c[verk] / ett_t * 100)} %"

    pst_dukkehjem = pst("A Doll's House")
    pst_folkefiende = pst("An Enemy Of The People")
    pst_peer = pst("Peer Gynt")

    _, n2015, land2015 = _andeler(rader, 2015, 2015)
    _, n2025, land2025 = _andeler(rader, 2025, 2025)
    c2015, _, _ = _andeler(rader, 2015, 2015)
    c2025, _, _ = _andeler(rader, 2025, 2025)

    data = {
        "meta": {
            "tittel": "Verden vil se folkefienden",
            "kilde": "IbsenStage, Universitetet i Oslo",
            "kilde_url": "https://ibsenstage.hf.uio.no/",
            "dato_hentet": "2026-08-28",
            "geografi": "115 land",
            "enhet": "andel av oppsetningene",
            "oppdateringsfrekvens": "Løpende",
            "beskrivelse": (
                "«En folkefiende» har tredoblet seg som andel av Ibsen-oppsetningene "
                "siden 2005 — og siden 2017 har de tre mest spilte stykkene "
                "tatt over 57 prosent av oppsetningene hvert eneste år."
            ),
        },
        "visninger": {
            "hero": {
                "type": "hero",
                "eyebrow": f"{ett_n} oppsetninger i {ett_land} land, 2022–{SISTE_AAR}",
                "rader": [
                    {"etikett": "Et dukkehjem", "verdi": pst_dukkehjem,
                     "detalj": "av alle Ibsen-oppsetninger i verden"},
                    {"etikett": "En folkefiende", "verdi": pst_folkefiende,
                     "detalj": "var 6,8 % i 2005–09"},
                    {"etikett": "Peer Gynt", "verdi": pst_peer,
                     "detalj": "var 17,9 % i samme periode"},
                ],
                "fotnote": (
                    "Andel av oppsetningene, ikke av forestillingene. Et verk telles "
                    "én gang per oppsetning. 2026 er utelatt: arkivet har annonserte "
                    "oppsetninger fram til oktober, og de er ikke spilt."
                ),
            },
            "andeler": {
                "type": "tidslinje",
                "tittel": "Tre stykker, tre baner",
                "undertekst": "Andel av oppsetningene, femårsbolker",
                "enhet": "%",
                "serier": [{"navn": NORSK[v], "punkter": p} for v, p in serier.items()],
            },
            "konsentrasjon": {
                "type": "tidslinje",
                "tittel": "Fra 2017 tar de tre største stadig mer",
                "undertekst": "Andel av oppsetningene som er ett av de tre mest spilte verkene",
                "enhet": "%",
                "serier": [{"navn": "Topp tre", "punkter": konsentrasjon}],
            },
            "geografi": {
                "type": "verdenskart",
                "tittel": "Hvor mye av landets Ibsen er «En folkefiende»?",
                "undertekst": "Andel av oppsetningene 2015–2025, land med minst 15 oppsetninger",
                "enhet": "%",
                "verdier": andel_land,
                "navn": navn_land,
                "antall": {k: land_tot[k] for k in andel_land},
                "antall_navn": "Ibsen-oppsetninger",
                "tom_etikett": "under 15 oppsetninger",
            },
            "endring": {
                "type": "kortgalleri",
                "tittel": "Hvem vokste, hvem falt",
                "undertekst": f"Andel 2010–2019 mot 2022–{SISTE_AAR}",
                "kort": [
                    {"overtittel": NORSK.get(v, v), "verdi": f"{b - a:+.1f} pp",
                     "detalj": f"fra {a:.1f} % til {b:.1f} %"}
                    for v, a, b in kort
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
    print(f"{SLUG}")
    print(f"  2015: {n2015} oppsetninger, {land2015} land, {len(c2015)} ulike verk")
    print(f"  2025: {n2025} oppsetninger, {land2025} land, {len(c2025)} ulike verk")
    print(f"  konsentrasjonsserie: {len(konsentrasjon)} år, "
          f"{len(serier['Peer Gynt'])} femårsbolker")
    print(f"  validering: {'OK' if not feil else feil}")


if __name__ == "__main__":
    main()
