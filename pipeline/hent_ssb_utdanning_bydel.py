"""Utdanningsnivå per bydel i Oslo fra SSB (tabell 09434).

Kjøring:

    python pipeline/hent_ssb_utdanning_bydel.py

Skriver impromptu_raadata/ssb/utdanning_bydel.csv med én rad per bydel:
bydel, år, andel med universitets- og høgskoleutdanning (kort + lang), antall
personer 16 år og over.

Feller:
- Tabellen har både dagens 15 bydeler og de gamle fra 1988–2003 i samme
  Region-variabel. De gamle har «(1988-2003)» i navnet og bare nuller for nyere
  år; de utelates.
- «Oslo i alt» har bare totalen, ikke fordeling på nivå (nuller). Oslo-snittet
  regnes derfor ut fra bydelene, vektet med antall personer.
- Andelen gjelder alle voksne 16+, ikke foreldre. I indre by bor mange høyt
  utdannede uten barn i skolealder; bydelssnittet sier derfor mindre om
  elevgrunnlaget der enn i ytre bydeler.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import urllib.request
from pathlib import Path

import kontrakt  # noqa: F401

TABELL = "09434"
API = f"https://data.ssb.no/api/v0/no/table/{TABELL}"
UT = Path(os.environ.get("SSB_DIR") or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ssb")


def hent(url: str, sporring: dict | None = None):
    data = json.dumps(sporring).encode("utf-8") if sporring else None
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "Impromptu-Analytics/1.0",
                                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as s:
        return json.loads(s.read().decode("utf-8"))


def main() -> int:
    meta = hent(API)
    var = {v["code"]: v for v in meta["variables"]}
    try:
        region = var["Region"]
        nivaa = var["UtdNivaa"]
        tid = var["Tid"]
    except KeyError:
        raise SystemExit(f"Tabell {TABELL} ser annerledes ut enn ventet — sjekk den på data.ssb.no.")
    bydeler = [(k, t) for k, t in zip(region["values"], region["valueTexts"])
               if k.startswith("0301") and "(1988" not in t and "i alt" not in t and "Uoppgitt" not in t
               and "(2001" not in t]
    hoy = [k for k, t in zip(nivaa["values"], nivaa["valueTexts"]) if "Universitets- og høgskolenivå" in t]
    if len(hoy) != 2 or len(bydeler) < 15:
        raise SystemExit(f"Fant {len(hoy)} høyere nivåer og {len(bydeler)} bydeler — tabellen har endret seg.")
    siste = tid["values"][-1]
    svar = hent(API, {"query": [
        {"code": "Region", "selection": {"filter": "item", "values": [k for k, _ in bydeler]}},
        {"code": "Kjonn", "selection": {"filter": "item", "values": ["0"]}},
        {"code": "UtdNivaa", "selection": {"filter": "item", "values": ["00", *hoy]}},
        {"code": "ContentsCode", "selection": {"filter": "item", "values": ["Personer"]}},
        {"code": "Tid", "selection": {"filter": "item", "values": [siste]}},
    ], "response": {"format": "json-stat2"}})

    # json-stat2 er flat-indeksert i dimensjonsrekkefølgen fra svar["id"]
    ider, storr = svar["id"], svar["size"]
    indeks = {d: svar["dimension"][d]["category"]["index"] for d in ider}

    def verdi(**koord):
        flat = 0
        for d, n in zip(ider, storr):
            flat = flat * n + indeks[d][koord[d]]
        return svar["value"][flat]

    rader = []
    for kode, navn in bydeler:
        totalt = verdi(Region=kode, Kjonn="0", UtdNivaa="00", ContentsCode="Personer", Tid=siste)
        hoyere = sum(verdi(Region=kode, Kjonn="0", UtdNivaa=h, ContentsCode="Personer", Tid=siste) for h in hoy)
        if not totalt:
            continue
        rader.append({"bydel": navn, "aar": siste, "andel_hoyere_utdanning": round(100 * hoyere / totalt, 1),
                      "personer_16_pluss": int(totalt)})
    for r in rader:
        if not 15 <= r["andel_hoyere_utdanning"] <= 85:
            raise SystemExit(f"Urimelig andel høyere utdanning i {r['bydel']}: {r['andel_hoyere_utdanning']}")
    UT.mkdir(parents=True, exist_ok=True)
    with open(UT / "utdanning_bydel.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rader[0]))
        w.writeheader()
        w.writerows(rader)
    oslo = sum(r["andel_hoyere_utdanning"] * r["personer_16_pluss"] for r in rader) / sum(r["personer_16_pluss"] for r in rader)
    print(f"✓ {len(rader)} bydeler, {siste}. Oslo (vektet): {oslo:.1f} % med høyere utdanning.")
    for r in sorted(rader, key=lambda r: r["andel_hoyere_utdanning"]):
        print(f"  {r['bydel']:<18} {r['andel_hoyere_utdanning']:5.1f} %")
    return 0


if __name__ == "__main__":
    sys.exit(main())
