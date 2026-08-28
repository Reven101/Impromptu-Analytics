"""Setter sammen én analysetabell med én rad per Ibsen-oppsetning.

Kjøring (krever hent_ibsenstage.py, hent_ibsenstage_detaljer.py, berik_geodata.py
og berik_vdem.py):

    python pipeline/bygg_analysetabell.py

Grunnlaget ligger spredt på fem filer med tre ulike nøkler — `hendelse_id`,
`scene_id` og `person_id`. Uten ett felles utgangspunkt gjør hver analyse
sammenkoblingen på nytt, og to analyser gjør den snart ulikt. Denne tabellen er
det ene stedet koblingen skjer.

Tre ting den gjør som er lett å gjøre feil hver for seg:

- **Én rad per oppsetning, ikke per verk.** Browse-tabellen i kilden har én rad
  per verk, så kompilasjoner teller flere ganger: «Ibsen Kvinner — sett en ørn i
  bur» står seks steder. Her blir verkene en liste på én rad, og `antall_verk`
  sier hvor mange det var.
- **Duplikater merkes, ikke slettes.** 42 grupper deler tittel, scene og dato.
  Noen er utvetydige — samme oppsetning ført tre ganger med identisk kilde og
  rollebesetning. Andre er tvilstilfeller: samme Rosmersholm-dato registrert som
  både tysk og finsk kan være to turnéforestillinger. Tabellen flagger dem og
  sier om de er identiske; om de skal utelates er en analysebeslutning, og den
  skal være synlig i analysen framfor skjult her.
- **Datoens presisjon følger med.** 96,9 % har full dato, 1,4 % bare år. En
  månedsanalyse på et materiale der 366 oppsetninger bare har årstall må vite det.

ADVARSEL OM REGISSØRER: bare 79,6 % av oppsetningene har en regissør oppført, og
andelen er sterkt tidsavhengig — 30,5 % på 1870-tallet, 39,3 % på 1900-tallet,
98,1 % på 1970-tallet. Det er dels en registreringsmangel og dels et historisk
faktum: regissørrollen slik vi kjenner den vokste fram rundt forrige århundreskifte,
og eldre teater var skuespillerstyrt. Uansett årsak betyr det at enhver analyse av
regissører over tid har et utvalg som skifter karakter underveis. De 39 % vi ser fra
1900-tallet er neppe et tilfeldig utvalg av oppsetningene — de er trolig de mest
omtalte. Kjønnsfordeling, nasjonalitet og gjengangere blant regissører må leses med
det for øye, og aldri som en tidsserie uten forbehold.

Tabellen skrives som JSON (for pipelinen) og CSV (for utforsking), begge utenfor
repoet — jf. LES_MEG.md i rådatamappa.
"""

from __future__ import annotations

import collections
import csv
import json
import os
from datetime import date
from pathlib import Path

import kontrakt  # noqa: F401

RAADATA_DIR = Path(
    os.environ.get("IBSENSTAGE_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ibsenstage"
)

VDEM_FELT = ["v2mecenefm", "v2clacfree", "v2x_freexp_altinf",
             "v2x_polyarchy", "v2x_libdem"]

# Rollene vi teller opp per oppsetning. Resten summeres i `bidragsytere`.
TELLES = ["Director", "Actor", "Translator", "Adapter", "Composer",
          "Designer", "Costume Designer", "Choreographer", "Dramaturg"]

# Rollene vi bryter ned på kjønn. Ikke alle 25 — tabellen skal være lesbar, og
# disse tre er de spørsmålene materialet faktisk kan bære.
KJONN_ROLLER = ["Director", "Actor", "Translator"]

KOLONNENAVN = {
    "Director": "regissorer", "Actor": "skuespillere", "Translator": "oversettere",
    "Adapter": "bearbeidere", "Composer": "komponister", "Designer": "scenografer",
    "Costume Designer": "kostymedesignere", "Choreographer": "koreografer",
    "Dramaturg": "dramaturger",
}


def _eldste(verkliste: list[dict], verksaar: dict) -> int | None:
    """Utgivelsesåret for det eldste verket i oppsetningen.

    Kompilasjoner spenner over flere stykker; det eldste er det som har hatt
    lengst tid på seg til å nå fram, og er derfor riktig utgangspunkt for å måle
    spredning."""
    aar = [verksaar.get(v["tittel"]) for v in verkliste]
    kjente = [a for a in aar if a]
    return min(kjente) if kjente else None


def _presisjon(dato: str | None) -> str:
    return {8: "dag", 6: "maaned", 4: "aar"}.get(len(dato or ""), "ingen")


def main() -> None:
    for fil in ("ibsenstage_hendelser.json", "ibsenstage_detaljer.jsonl",
                "ibsenstage_geodata.json", "ibsenstage_vdem.json"):
        if not (RAADATA_DIR / fil).exists():
            raise SystemExit(f"mangler {RAADATA_DIR / fil}")

    browse = json.loads((RAADATA_DIR / "ibsenstage_hendelser.json")
                        .read_text(encoding="utf-8"))["hendelser"]
    detalj = {}
    with (RAADATA_DIR / "ibsenstage_detaljer.jsonl").open(encoding="utf-8") as f:
        for linje in f:
            x = json.loads(linje)
            detalj[x["hendelse_id"]] = x
    geo = {s["scene_id"]: s for s in json.loads(
        (RAADATA_DIR / "ibsenstage_geodata.json").read_text(encoding="utf-8"))["steder"]}
    vdem = {x["hendelse_id"]: x for x in json.loads(
        (RAADATA_DIR / "ibsenstage_vdem.json").read_text(encoding="utf-8"))["hendelser"]}
    # Forestillingstallet er valgfritt: tabellen skal kunne bygges før uttrekket
    # er kjørt, og da står kolonnen tom framfor at bygget feiler.
    # Utgivelsesår per verk. Uten det kan ikke spørsmålet «hvor lang tid tok
    # stykket hit» stilles i det hele tatt.
    verksaar = {}
    vfil = RAADATA_DIR / "ibsenstage_verk.json"
    if vfil.exists():
        verksaar = {v["verk"]: v["utgitt"]
                    for v in json.loads(vfil.read_text(encoding="utf-8"))["verk"]}

    # Kjønn per person. Utledet, ikke registrert — se berik_kjonn.py for målt
    # feilrate og for hvorfor tallene ikke tåler å leses som tidsserie.
    kjonn = {}
    kfil = RAADATA_DIR / "ibsenstage_kjonn.json"
    if kfil.exists():
        k_json = json.loads(kfil.read_text(encoding="utf-8"))
        kjonn = {p["person_id"]: p["kjonn"] for p in k_json["personer"]}
        print(f"kjønn fra {k_json['modell']} "
              f"({k_json['maalt_treff_blant_besvarte']}% treff blant besvarte, "
              f"{k_json['maalt_dekning']}% dekning)")

    forestillinger = {}
    ffil = RAADATA_DIR / "ibsenstage_forestillinger.json"
    if ffil.exists():
        f_json = json.loads(ffil.read_text(encoding="utf-8"))
        forestillinger = {x["hendelse_id"]: x["forestillinger"]
                          for x in f_json["oppsetninger"]}
        print(f"forestillingstall fra {f_json['modell']} "
              f"(promptversjon {f_json['promptversjon']}, "
              f"fasit {f_json['fasit_treff']}%)")

    # Browse-tabellen har én rad per verk. Vi folder verkene sammen per hendelse.
    grunn: dict[int, dict] = {}
    verk: dict[int, list] = collections.defaultdict(list)
    for r in browse:
        i = r["hendelse_id"]
        if not i:
            continue
        grunn.setdefault(i, r)
        if r["verk"] and r["verk"] not in [v["tittel"] for v in verk[i]]:
            verk[i].append({"tittel": r["verk"], "verk_id": r["verk_id"]})

    rader = []
    for i, b in grunn.items():
        d = detalj.get(i, {})
        g = geo.get(b.get("scene_id")) or {}
        v = vdem.get(i) or {}
        roller = collections.Counter(x["funksjon"] for x in d.get("bidragsytere", []))

        rad = {
            "hendelse_id": i,
            "tittel": d.get("tittel") or b.get("tittel"),
            "aar": b.get("aar"),
            "dato": b.get("dato"),
            "dato_presisjon": _presisjon(b.get("dato")),
            "siste_dato": d.get("siste_dato"),
            "verk": [v_["tittel"] for v_ in verk[i]],
            "antall_verk": len(verk[i]),
            "verk_utgitt": _eldste(verk[i], verksaar),
            "kategori": b.get("kategori"),
            "status": d.get("status"),
            "sprak": [s.strip() for s in (d.get("sprak") or "").split(",") if s.strip()],
            "produksjonsnasjonalitet": d.get("produksjonsnasjonalitet"),
            # Geografi
            "land": b.get("land"),
            "landkode": g.get("landkode"),
            "by": g.get("by"),
            "lat": g.get("lat"),
            "lon": g.get("lon"),
            "by_folketall_idag": g.get("folketall_idag"),
            "scene": b.get("scene"),
            "scene_id": b.get("scene_id"),
            # Medvirkende
            "bidragsytere": sum(roller.values()),
            "regissor_navn": [x["navn"] for x in d.get("bidragsytere", [])
                              if x["funksjon"] == "Director"],
            "organisasjoner": [o["navn"] for o in d.get("organisasjoner", [])],
            # Kilde og fritekst
            "kilder": len(d.get("kilder", [])),
            "har_tilleggsinfo": bool(d.get("tilleggsinfo")),
            "forestillinger": forestillinger.get(i),
            "har_beskrivelse": bool(d.get("beskrivelse")),
            "ressurser": b.get("ressurser", 0),
        }
        # Årene fra verket ble utgitt til det ble spilt her. Negative verdier er
        # ekte: noen stykker ble urframført før de kom på trykk.
        rad["aar_siden_utgivelse"] = (
            rad["aar"] - rad["verk_utgitt"]
            if rad["aar"] and rad["verk_utgitt"] else None)
        for f in TELLES:
            rad[KOLONNENAVN[f]] = roller.get(f, 0)
        # Kjønnsfordeling for de rollene et spørsmål faktisk kan handle om.
        # «ukjent» holdes som egen kolonne, ikke slått sammen med noen av delene:
        # forskjellen på «vi vet ikke» og «ingen» må være synlig i nevneren.
        for f in KJONN_ROLLER:
            fordelt = collections.Counter(
                kjonn.get(x["person_id"], "vet ikke")
                for x in d.get("bidragsytere", []) if x["funksjon"] == f)
            base = KOLONNENAVN[f]
            rad[f"{base}_kvinne"] = fordelt["kvinne"]
            rad[f"{base}_mann"] = fordelt["mann"]
            rad[f"{base}_ukjent"] = fordelt["vet ikke"]
        rad["regissor_kjonn"] = [kjonn.get(x["person_id"], "vet ikke")
                                 for x in d.get("bidragsytere", [])
                                 if x["funksjon"] == "Director"]
        for f in VDEM_FELT:
            rad[f] = v.get(f) if v.get("funnet") else None
        rad["har_vdem"] = bool(v.get("funnet"))
        rader.append(rad)

    _merk_duplikater(rader, detalj)

    rader.sort(key=lambda r: (r["dato"] or "00000000", r["hendelse_id"]))
    _skriv(rader)
    _rapport(rader)


def _merk_duplikater(rader: list[dict], detalj: dict) -> None:
    """Merker rader som deler tittel, scene og dato.

    `duplikat_identisk` skiller de utvetydige fra tvilstilfellene: er språk,
    førstedato og antall medvirkende like, er det samme oppsetning ført flere
    ganger. Skiller de seg, kan det være to forestillinger på samme turné, og da
    er det ikke vår sak å avgjøre det her.
    """
    grupper = collections.defaultdict(list)
    for r in rader:
        if r["dato"] and r["scene_id"]:
            grupper[(r["tittel"], r["scene_id"], r["dato"])].append(r)

    for n, (_, medlemmer) in enumerate(
            (k, v) for k, v in grupper.items() if len(v) > 1):
        avtrykk = {
            (tuple(sorted(m["sprak"])),
             (detalj.get(m["hendelse_id"]) or {}).get("forste_dato"),
             m["bidragsytere"])
            for m in medlemmer
        }
        identisk = len(avtrykk) == 1
        forste = min(m["hendelse_id"] for m in medlemmer)
        for m in medlemmer:
            m["duplikat_gruppe"] = n + 1
            m["duplikat_identisk"] = identisk
            m["duplikat_av"] = None if m["hendelse_id"] == forste else forste

    for r in rader:
        r.setdefault("duplikat_gruppe", None)
        r.setdefault("duplikat_identisk", None)
        r.setdefault("duplikat_av", None)


def _skriv(rader: list[dict]) -> None:
    jsonfil = RAADATA_DIR / "ibsenstage_analyse.json"
    jsonfil.write_text(json.dumps({
        "bygget": date.today().isoformat(),
        "antall": len(rader),
        "oppsetninger": rader,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    csvfil = RAADATA_DIR / "ibsenstage_analyse.csv"
    lister = {"verk", "sprak", "regissor_navn", "organisasjoner", "regissor_kjonn"}
    with csvfil.open("w", newline="", encoding="utf-8") as f:
        skriver = csv.DictWriter(f, fieldnames=list(rader[0]))
        skriver.writeheader()
        for r in rader:
            skriver.writerow({k: ("; ".join(map(str, v)) if k in lister else v)
                              for k, v in r.items()})
    print(f"  {jsonfil}\n  {csvfil}")


def _rapport(rader: list[dict]) -> None:
    n = len(rader)
    aar = [r["aar"] for r in rader if r["aar"]]
    print(f"\n{n} oppsetninger, {min(aar)}-{max(aar)}\n")

    def andel(navn: str, tell) -> None:
        k = sum(1 for r in rader if tell(r))
        print(f"  {navn:32s} {k:6d}  {k / n * 100:5.1f}%")

    print("Dekning:")
    andel("årstall", lambda r: r["aar"])
    andel("full dato (dag)", lambda r: r["dato_presisjon"] == "dag")
    andel("koordinat", lambda r: r["lat"] is not None)
    andel("V-Dem", lambda r: r["har_vdem"])
    andel("koordinat + V-Dem + år", lambda r: r["lat"] is not None and r["har_vdem"] and r["aar"])
    andel("minst én regissør", lambda r: r["regissorer"] > 0)
    andel("språk oppgitt", lambda r: r["sprak"])
    andel("tilleggsinfo", lambda r: r["har_tilleggsinfo"])
    andel("forestillingstall", lambda r: r["forestillinger"])
    andel("utgivelsesår for verket", lambda r: r["verk_utgitt"])
    andel("kjønn bestemt for minst én regissør",
          lambda r: r["regissorer_kvinne"] + r["regissorer_mann"] > 0)
    kjent = [r["forestillinger"] for r in rader if r["forestillinger"]]
    if kjent:
        sum_tekst = f"{sum(kjent):,}".replace(",", " ")
        print(f"\nForestillinger der tallet er kjent: {sum_tekst} "
              f"fordelt på {len(kjent)} oppsetninger")
        print(f"  median {sorted(kjent)[len(kjent) // 2]}, maks {max(kjent)}")

    dup = [r for r in rader if r["duplikat_gruppe"]]
    ident = [r for r in dup if r["duplikat_identisk"]]
    print(f"\nDuplikater: {len(dup)} rader i "
          f"{len({r['duplikat_gruppe'] for r in dup})} grupper")
    print(f"  identiske (samme språk, dato og antall medvirkende): {len(ident)}")
    print(f"  overtallige om man utelater dem: "
          f"{sum(1 for r in dup if r['duplikat_av'])}")

    print("\nKompilasjoner (flere verk i én oppsetning):")
    flere = collections.Counter(r["antall_verk"] for r in rader if r["antall_verk"] > 1)
    for k in sorted(flere):
        print(f"  {k} verk: {flere[k]} oppsetninger")


if __name__ == "__main__":
    main()
