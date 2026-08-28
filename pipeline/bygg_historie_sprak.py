"""Bygger historien «Ibsen reiste ikke på norsk» — språket han ble spilt på.

Kjøring:

    python pipeline/bygg_analysetabell.py
    python pipeline/bygg_historie_sprak.py

Forestillingsspråk er oppgitt på 25 339 av 25 342 oppsetninger — den mest komplette
kolonnen i hele materialet, og registrert av arkivarene, ikke utledet av oss.

Historien hviler på én kontroll. Et språk kan være mye brukt av to grunner: fordi
landet det snakkes i spiller mye Ibsen, eller fordi andre land bruker det. De to
er ikke det samme, og forskjellen er hele poenget:

- **Norsk følger Norge nesten perfekt.** 34,1 % norskspråklig mot 32,4 % norske
  oppsetninger på 1950-tallet; 17,1 mot 17,5 på 2010-tallet. Norskspråklig Ibsen
  er Ibsen i Norge. Språket reiser ikke.
- **Tysk overgår Tyskland i hele perioden.** 45,0 % tyskspråklig mot 33,2 % tyske
  oppsetninger på 1910-tallet, med 187 tyskspråklige oppsetninger utenfor
  Tyskland. Tysk var språket andre land tok Ibsen på.

Uten den kontrollen ville grafen bare vist at Ibsen spilles mye i Norge og
Tyskland, og det er ikke en observasjon om noe som helst.
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
SLUG = "ibsen-reiste-ikke-pa-norsk"

SPRAK_NORSK = {
    "Norwegian": "norsk", "German": "tysk", "English": "engelsk", "Italian": "italiensk",
    "Hungarian": "ungarsk", "Swedish": "svensk", "French": "fransk", "Dutch": "nederlandsk",
    "Danish": "dansk", "Spanish": "spansk", "Polish": "polsk", "Czech": "tsjekkisk",
    "Russian": "russisk", "Finnish": "finsk", "Japanese": "japansk", "Greek": "gresk",
    "Portuguese": "portugisisk", "Romanian": "rumensk", "Chinese": "kinesisk",
}


def main() -> None:
    rader = json.loads((RAADATA_DIR / "ibsenstage_analyse.json")
                       .read_text(encoding="utf-8"))["oppsetninger"]

    # Samlet: antall oppsetninger og antall land per språk.
    ant = collections.Counter()
    land: dict[str, set] = collections.defaultdict(set)
    for r in rader:
        for s in r["sprak"]:
            ant[s] += 1
            if r["land"]:
                land[s].add(r["land"])

    # Per tiår: andel av oppsetningene på hvert språk, og andel i hvert land.
    # Paret er poenget — språkkurven alene sier ikke om språket reiser.
    def andel(velg, fra=1870, til=2020):
        ut = []
        for t in range(fra, til + 1, 10):
            n = [r for r in rader if r["aar"] and t <= r["aar"] < t + 10]
            if len(n) < 40:
                continue
            ut.append([t, round(sum(1 for r in n if velg(r)) / len(n) * 100, 1)])
        return ut

    serier_sprak = [
        {"navn": "Tysk", "punkter": andel(lambda r: "German" in r["sprak"])},
        {"navn": "Engelsk", "punkter": andel(lambda r: "English" in r["sprak"])},
        {"navn": "Norsk", "punkter": andel(lambda r: "Norwegian" in r["sprak"])},
    ]
    serier_kontroll = [
        {"navn": "Tysk språk", "punkter": andel(lambda r: "German" in r["sprak"])},
        {"navn": "Tyskland", "punkter": andel(lambda r: r["land"] == "Germany")},
        {"navn": "Norsk språk", "punkter": andel(lambda r: "Norwegian" in r["sprak"])},
        {"navn": "Norge", "punkter": andel(lambda r: r["land"] == "Norway")},
    ]

    kort = [
        {"overtittel": SPRAK_NORSK.get(s, s).capitalize(),
         "verdi": f"{len(land[s])} land", "detalj": f"{ant[s]} oppsetninger"}
        for s, _ in ant.most_common(6)
    ]
    kort.sort(key=lambda k: -int(k["verdi"].split()[0]))

    data = {
        "meta": {
            "tittel": "Ibsen reiste ikke på norsk",
            "kilde": "IbsenStage, Universitetet i Oslo",
            "kilde_url": "https://ibsenstage.hf.uio.no/",
            "dato_hentet": "2026-08-28",
            "geografi": "115 land",
            "enhet": "andel av oppsetningene",
            "oppdateringsfrekvens": "Løpende",
            "beskrivelse": (
                f"Ibsen er spilt {ant['German']} ganger på tysk og {ant['Norwegian']} "
                "ganger på norsk — men norskspråklige oppsetninger er nesten utelukkende "
                "i Norge, mens tysk ble språket andre land tok ham på."
            ),
            "utkast": True,
        },
        "visninger": {
            "hero": {
                "type": "hero",
                "eyebrow": f"25 339 oppsetninger med oppgitt språk, {len(ant)} språk",
                "rader": [
                    {"etikett": "Tysk", "verdi": f"{ant['German']}",
                     "detalj": f"i {len(land['German'])} land"},
                    {"etikett": "Norsk", "verdi": f"{ant['Norwegian']}",
                     "detalj": f"i {len(land['Norwegian'])} land"},
                    {"etikett": "Engelsk", "verdi": f"{ant['English']}",
                     "detalj": f"i {len(land['English'])} land"},
                ],
                "fotnote": (
                    "Språk er registrert av arkivarene, ikke utledet. Oppsetninger på "
                    "flere språk teller for hvert av dem, så summen overstiger 100 %."
                ),
            },
            "sprak": {
                "type": "tidslinje",
                "tittel": "Tre språk, tre epoker",
                "undertekst": "Andel av oppsetningene i tiåret",
                "enhet": "%",
                "x_navn": "Tiår",
                "serier": serier_sprak,
            },
            "kontroll": {
                "type": "tidslinje",
                "tittel": "Norsk følger Norge. Tysk gjør ikke det",
                "undertekst": "Andel av oppsetningene: språket mot landet",
                "enhet": "%",
                "x_navn": "Tiår",
                "serier": serier_kontroll,
            },
            "rekkevidde": {
                "type": "kortgalleri",
                "tittel": "Hvor langt hvert språk rakk",
                "undertekst": "Antall land Ibsen er spilt på språket i",
                "kort": kort,
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
    print(f"{SLUG}: {len(ant)} språk")
    for s in ("German", "Norwegian", "English"):
        print(f"  {SPRAK_NORSK[s]:10s} {ant[s]:5d} oppsetninger i {len(land[s]):3d} land")
    print(f"  validering: {'OK' if not feil else feil}")


if __name__ == "__main__":
    main()
