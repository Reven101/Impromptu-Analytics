"""Bygger historien «Kostymene er kvinner, lyset er menn» — kjønn per rolle i Ibsen-teatret.

Kjøring:

    python pipeline/berik_kjonn.py
    python pipeline/rett_kjonn_rollefigur.py
    python pipeline/bygg_historie_hvem.py

Kjønn er ikke registrert i IbsenStage. Det er utledet av fornavn med en språkmodell
og korrigert mot rollefigur, med en målt feilrate på 1,50 %. Alt i denne historien
hviler på det, og det står i teksten.

To ting styrer hvordan tallene kan brukes:

- **Rollene registreres ulikt ofte, og det har endret seg.** Regissør er ført på
  95–99 % av oppsetningene siden 1950, men bare 39 % på 1900-tallet. Kostymedesigner
  er ført på 1 % i 1900 og 65 % i 2000. Tverrsnittet over hele perioden er derfor
  i praksis et moderne bilde: 79 % av kostymekrediteringene er fra 1980 eller senere.
- **Derfor starter tidsserien i 1950.** Der er dekningen for regissør og skuespiller
  stabil (91–99 %), og en kurve måler da noe annet enn hvor godt arkivet fører.
  Før 1950 ville den blandet «flere kvinner regisserer» med «flere regissører
  registreres» — 0 % kvinnelige regissører på 1880-tallet er ikke en observasjon,
  det er 46 % dekning.

Vi teller **krediteringer**, ikke personer: spørsmålet er hvem som gjør arbeidet,
ikke hvem som har gjort det minst én gang. Forskjellen er reell — blant skuespillere
er kvinneandelen 41,3 % målt i krediteringer og 44,2 % målt i personer, fordi menn i
snitt har flere oppsetninger hver.
"""

from __future__ import annotations

import collections
import json
import os
from pathlib import Path

import kontrakt
from kontrakt import INNHOLD_DIR

RAADATA_DIR = Path(
    os.environ.get("IBSENSTAGE_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ibsenstage"
)
SLUG = "kostymene-er-kvinner"

# Rollene vi viser, med norske navn. Håndskrevet utvalg: de tolv med nok
# krediteringer til at andelen betyr noe. «Playwright» er utelatt — den er
# Ibsen selv på 25 029 av 25 078 krediteringer.
ROLLER = {
    "Costume Designer": "Kostymedesigner", "Choreographer": "Koreograf",
    "Dramaturg": "Dramaturg", "Actor": "Skuespiller", "Producer": "Produsent",
    "Adapter": "Bearbeider", "Designer": "Scenograf", "Director": "Regissør",
    "Translator": "Oversetter", "Lighting Designer": "Lysdesigner",
    "Sound Designer": "Lyddesigner", "Composer": "Komponist",
}
TIDSSERIE = ["Actor", "Director", "Costume Designer"]
FRA_AAR = 1950


def main() -> None:
    kjonn = {p["person_id"]: p["kjonn"] for p in json.loads(
        (RAADATA_DIR / "ibsenstage_kjonn.json").read_text(encoding="utf-8"))["personer"]}
    browse = {r["hendelse_id"]: r for r in json.loads(
        (RAADATA_DIR / "ibsenstage_hendelser.json").read_text(encoding="utf-8"))["hendelser"]}

    oppsetninger = []
    with (RAADATA_DIR / "ibsenstage_detaljer.jsonl").open(encoding="utf-8") as f:
        for linje in f:
            x = json.loads(linje)
            x["_aar"] = (browse.get(x["hendelse_id"]) or {}).get("aar")
            oppsetninger.append(x)

    # Tverrsnitt: kvinneandel per rolle, hele perioden.
    per_rolle = collections.defaultdict(collections.Counter)
    for x in oppsetninger:
        for b in x["bidragsytere"]:
            if b["person_id"]:
                per_rolle[b["funksjon"]][kjonn.get(b["person_id"])] += 1

    def andel(c: collections.Counter) -> tuple[float, int]:
        base = c["kvinne"] + c["mann"]
        return (c["kvinne"] / base * 100 if base else 0.0), base

    tverrsnitt = []
    for f, navn in ROLLER.items():
        p, n = andel(per_rolle[f])
        tverrsnitt.append((navn, p, n, per_rolle[f]["vet ikke"]))
    tverrsnitt.sort(key=lambda t: -t[1])

    # Tidsserie fra 1950, der dekningen er stabil.
    serier = []
    dekning = {}
    for f in TIDSSERIE:
        punkter, dek = [], []
        for t in range(FRA_AAR, 2030, 10):
            n = [x for x in oppsetninger if x["_aar"] and t <= x["_aar"] < t + 10]
            if not n:
                continue
            c = collections.Counter(
                kjonn.get(b["person_id"]) for x in n for b in x["bidragsytere"]
                if b["funksjon"] == f and b["person_id"])
            p, base = andel(c)
            if base < 100:
                continue
            punkter.append([t, round(p, 1)])
            dek.append(round(sum(1 for x in n if any(b["funksjon"] == f
                                                     for b in x["bidragsytere"]))
                             / len(n) * 100))
        serier.append({"navn": ROLLER[f], "punkter": punkter})
        dekning[ROLLER[f]] = (min(dek), max(dek))

    def pst(f: str) -> str:
        return f"{andel(per_rolle[f])[0]:.0f} %"

    data = {
        "meta": {
            "tittel": "Kostymene er kvinner, lyset er menn",
            "kilde": "IbsenStage, Universitetet i Oslo",
            "kilde_url": "https://ibsenstage.hf.uio.no/",
            "dato_hentet": "2026-08-28",
            "geografi": "115 land",
            "enhet": "andel kvinner",
            "oppdateringsfrekvens": "Løpende",
            "beskrivelse": (
                "Sju av ti kostymedesignere i Ibsen-teatret er kvinner og én av ni "
                "komponister — og blant regissørene har andelen gått fra 14 til 34 "
                "prosent siden 1980, mens skuespillerne knapt har rikket seg."
            ),
            "utkast": True,
        },
        "visninger": {
            "hero": {
                "type": "hero",
                "eyebrow": "349 041 krediteringer, 96 415 personer",
                "rader": [
                    {"etikett": "Kostymedesigner", "verdi": pst("Costume Designer"),
                     "detalj": "er kvinner"},
                    {"etikett": "Regissør", "verdi": pst("Director"),
                     "detalj": "over hele perioden; 34 % på 2020-tallet"},
                    {"etikett": "Komponist", "verdi": pst("Composer"),
                     "detalj": "den laveste av tolv roller"},
                ],
                "fotnote": (
                    "Kjønn er ikke registrert i kilden. Det er utledet av fornavn med "
                    "gemini-3.1-flash-lite og korrigert mot rollefigur; målt feilrate "
                    "1,50 %. Se datanotatet."
                ),
            },
            "roller": {
                "type": "kortgalleri",
                "tittel": "Tolv roller, fra sju av ti til én av ni",
                "undertekst": "Andel kvinner blant krediteringene, hele perioden",
                "kort": [
                    {"overtittel": navn, "verdi": f"{p:.0f} %",
                     "detalj": f"av {n:,} krediteringer".replace(",", " ")}
                    for navn, p, n, _ in tverrsnitt
                ],
            },
            "utvikling": {
                "type": "tidslinje",
                "tittel": "Regissørene beveger seg. Skuespillerne gjør ikke det",
                "undertekst": "Andel kvinner, tiår med stabil registrering",
                "enhet": "%",
                "x_navn": "Tiår",
                "serier": serier,
            },
        },
    }

    data, notater = kontrakt.flett_redaksjon(data, SLUG)
    mappe = INNHOLD_DIR / SLUG
    mappe.mkdir(parents=True, exist_ok=True)
    (mappe / "data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if notater:
        print(f"  redaksjon.json overstyrer {len(notater)} felt")

    feil = kontrakt.valider_snapshot(data, SLUG)
    print(f"{SLUG}: {len(tverrsnitt)} roller")
    for navn, p, n, u in tverrsnitt:
        print(f"  {navn:18s} {p:5.1f} %  n={n:7d}, {u} ubestemt")
    print("  dekning i tidsserien:", {k: f"{a}–{b} %" for k, (a, b) in dekning.items()})
    print(f"  validering: {'OK' if not feil else feil}")


if __name__ == "__main__":
    main()
