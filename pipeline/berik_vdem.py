"""Kobler IbsenStage-oppsetninger til V-Dems land-år-indikatorer.

Kjøring (krever at V-Dem-CY-FullOthers-v16_csv.zip ligger i rådatamappa):

    python pipeline/berik_vdem.py

V-Dem er et forskningsdatasett over politiske institusjoner, land for land og år
for år, tilbake til 1789. Det gjør det til den ene eksterne kilden som faktisk
dekker Ibsen-materialets tidsspenn. Vi henter elleve av 4 618 kolonner:

    v2mecenefm        statlig sensur av medier
    v2clacfree        frihet for kunstnerisk og akademisk ytring
    v2x_freexp_altinf ytringsfrihet og alternative informasjonskilder
    v2x_polyarchy     valgdemokrati-indeks
    v2x_libdem        liberalt demokrati-indeks

Spørsmålet dette skal tjene er konkret: ble Ibsen spilt annerledes der og da
ytringsfriheten var mindre? «Gengangere» ble nektet oppført flere steder, så
sensur er ikke en påklistret variabel her — den er en del av stykkenes historie.

**Den store fallgruven er historiske grenser.** IbsenStage fører moderne land:
en oppsetning i Arad i 1879 står som «Romania», men Arad lå i Østerrike-Ungarn.
Kilden vet det selv — merknadsfeltet sier det rett ut — men landkolonnen sier
Romania. Kobler vi blindt, tilskriver vi Romania-1879 en forestilling som fant
sted i en helt annen stat.

Vi løser det ikke, vi gjør det synlig. V-Dem fører hver polity fra det året den
fantes, så oppslaget returnerer ingenting for land-år som ikke eksisterte. De
oppsetningene får `null` og telles i rapporten framfor å bli koblet til feil stat.
"""

from __future__ import annotations

import collections
import csv
import io
import json
import os
import sys
import zipfile
from datetime import date
from pathlib import Path

import kontrakt  # noqa: F401

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

RAADATA_DIR = Path(
    os.environ.get("IBSENSTAGE_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ibsenstage"
)
VDEM_ZIP = RAADATA_DIR / "V-Dem-CY-FullOthers-v16_csv.zip"
SLANK = RAADATA_DIR / "vdem_slank.json"

KOLONNER = ["country_name", "country_text_id", "country_id", "year", "histname",
            "v2mecenefm", "v2clacfree", "v2x_freexp_altinf", "v2x_polyarchy",
            "v2x_libdem", "e_regiongeo"]

# Våre landnavn som V-Dem kaller noe annet. Håndskrevet: en navnelikhetsregel ville
# gjettet «Georgia» på «Georgia» og blandet delstat med land.
LAND_NAVN = {
    "United States of America": "United States of America",
    "England": "United Kingdom", "Scotland": "United Kingdom",
    "Wales": "United Kingdom", "Northern Ireland": "United Kingdom",
    "Czech Republic": "Czechia", "Slovak Republic": "Slovakia",
    "Macedonia": "North Macedonia", "Palestinian Territories": "Palestine/West Bank",
    "Serbia and Montenegro": "Serbia", "Ivory Coast": "Ivory Coast",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina", "Korea, South": "South Korea",
    "Russia": "Russia", "Vietnam": "Vietnam",
}


def slank_ut() -> list[dict]:
    """Leser V-Dem-CSV-en strømmende og beholder de elleve kolonnene vi bruker.

    Fila er 406 MB med 4 618 kolonner. Å lese den inn i en DataFrame ville krevd
    pandas og flere gigabyte minne for data vi kaster 99,8 % av; her holder det
    med csv-modulen og en indeksliste.
    """
    if SLANK.exists():
        return json.loads(SLANK.read_text(encoding="utf-8"))["rader"]

    with zipfile.ZipFile(VDEM_ZIP) as z:
        navn = next(n for n in z.namelist() if n.endswith(".csv"))
        with z.open(navn) as rå:
            leser = csv.reader(io.TextIOWrapper(rå, encoding="utf-8"))
            hode = next(leser)
            idx = {k: hode.index(k) for k in KOLONNER if k in hode}
            rader = []
            for n, r in enumerate(leser):
                if n % 5000 == 0:
                    print(f"  {n} rader", flush=True)
                post = {}
                for k, i in idx.items():
                    v = r[i] if i < len(r) else ""
                    if k in ("year", "country_id"):
                        post[k] = int(v) if v else None
                    elif k.startswith("v2") or k == "e_regiongeo":
                        post[k] = float(v) if v else None
                    else:
                        post[k] = v
                rader.append(post)
    SLANK.write_text(json.dumps({"kilde": VDEM_ZIP.name, "antall": len(rader),
                                 "kolonner": KOLONNER, "rader": rader},
                                ensure_ascii=False), encoding="utf-8")
    return rader


def main() -> None:
    if not VDEM_ZIP.exists():
        raise SystemExit(f"mangler {VDEM_ZIP}")

    rader = slank_ut()
    aar = [r["year"] for r in rader if r["year"]]
    vdem_navn = {r["country_name"] for r in rader}
    print(f"V-Dem: {len(rader)} land-år, {min(aar)}-{max(aar)}, "
          f"{len(vdem_navn)} polities\n")

    oppslag = {(r["country_name"], r["year"]): r for r in rader}

    browse = json.loads((RAADATA_DIR / "ibsenstage_hendelser.json")
                        .read_text(encoding="utf-8"))["hendelser"]
    # Én rad per hendelse; kompilasjoner har én rad per verk i kilden.
    hendelser = {r["hendelse_id"]: r for r in browse if r["hendelse_id"]}

    vaare = collections.Counter(r["land"] for r in hendelser.values() if r["land"])
    ukjente = [(k, v) for k, v in vaare.most_common()
               if LAND_NAVN.get(k, k) not in vdem_navn]
    if ukjente:
        print(f"landnavn uten motstykke i V-Dem: {len(ukjente)}")
        for k, v in ukjente[:12]:
            print(f"  {v:5d}  {k}")
        print()

    ut, uten_land, uten_aar = [], 0, 0
    for h in hendelser.values():
        navn = LAND_NAVN.get(h["land"] or "", h["land"])
        if navn not in vdem_navn:
            uten_land += 1
            continue
        if not h["aar"]:
            uten_aar += 1
            continue
        v = oppslag.get((navn, h["aar"]))
        ut.append({
            "hendelse_id": h["hendelse_id"], "aar": h["aar"], "land": h["land"],
            "vdem_land": navn, "funnet": v is not None,
            **({k: v[k] for k in KOLONNER if k.startswith("v2")} if v else {}),
        })

    fil = RAADATA_DIR / "ibsenstage_vdem.json"
    truffet = [r for r in ut if r["funnet"]]
    fil.write_text(json.dumps({
        "hentet": date.today().isoformat(), "kilde": VDEM_ZIP.name,
        "antall": len(ut), "med_vdem": len(truffet), "hendelser": ut,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    n = len(hendelser)
    print(f"{n} hendelser")
    print(f"  koblet til V-Dem:     {len(truffet):6d}  ({len(truffet) / n * 100:.1f}%)")
    print(f"  land-år finnes ikke:  {len(ut) - len(truffet):6d}")
    print(f"  landnavn uten V-Dem:  {uten_land:6d}")
    print(f"  uten årstall:         {uten_aar:6d}")

    print("\nDekning per tiår — der den faller, fantes ikke staten:")
    per = collections.defaultdict(lambda: [0, 0])
    for r in ut:
        p = per[r["aar"] // 10 * 10]
        p[0] += 1
        p[1] += 1 if r["funnet"] else 0
    for tiar in sorted(per):
        tot, ok = per[tiar]
        print(f"  {tiar}-tallet {ok:5d}/{tot:5d} = {ok / tot * 100:5.1f}%")

    mangler = collections.Counter((r["land"], r["aar"] // 10 * 10)
                                  for r in ut if not r["funnet"])
    print("\nStørste hull (land, tiår):")
    for (land, tiar), c in mangler.most_common(8):
        print(f"  {c:4d}  {land} {tiar}-tallet")
    print(f"\n  {fil}")


if __name__ == "__main__":
    main()
