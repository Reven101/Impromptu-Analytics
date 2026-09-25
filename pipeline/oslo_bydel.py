"""Bydel for et punkt i Oslo, fra Oslo kommunes bydelsgrenser.

Kilde: Oslo kommune, via github.com/AnalyseABO/Kart-fylker-og-kommuner-json
(Bydeler_Oslo_m_marka.json, TopoJSON i WGS84, forenklet i Mapshaper).
Fila lastes ned én gang til impromptu_raadata/oslo/ og brukes derfra.

Forenklingen gjør at et punkt helt inntil en grense, eller i en fjordkant, kan
falle utenfor alle polygonene (målt: Bentsebrua skole og Norlights). Da velges
bydelen med nærmeste grensepunkt, og treffet merkes som «nærmeste» så det kan
sjekkes for hånd.
"""

from __future__ import annotations

import json
import math
import os
import urllib.request
from functools import lru_cache
from pathlib import Path

KILDE = ("https://raw.githubusercontent.com/AnalyseABO/Kart-fylker-og-kommuner-json/"
         "main/Bydeler_Oslo_m_marka.json")
FIL = (Path(os.environ.get("OSLO_GEO_DIR") or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "oslo")
       / "bydeler_oslo.topo.json")

# Grupperingen Oslo kommune selv bruker i statistikken.
OMRAADE = {
    "Gamle Oslo": "indre øst", "Grünerløkka": "indre øst", "Sagene": "indre øst",
    "Frogner": "indre vest", "St. Hanshaugen": "indre vest",
    "Ullern": "ytre vest", "Vestre Aker": "ytre vest", "Nordre Aker": "ytre vest",
    "Bjerke": "ytre øst", "Grorud": "ytre øst", "Stovner": "ytre øst", "Alna": "ytre øst",
    "Østensjø": "ytre øst",
    "Nordstrand": "sør", "Søndre Nordstrand": "sør",
    "Sentrum": "sentrum",
}


def _last_ned() -> None:
    FIL.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(KILDE, headers={"User-Agent": "Impromptu-Analytics/1.0"})
    with urllib.request.urlopen(req, timeout=60) as svar:
        FIL.write_bytes(svar.read())


@lru_cache
def _polygoner() -> list[tuple[str, list[list[tuple[float, float]]]]]:
    if not FIL.exists():
        _last_ned()
    topo = json.loads(FIL.read_text(encoding="utf-8"))
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    buer = []
    for bue in topo["arcs"]:                 # delta-kodede, kvantiserte koordinater
        x = y = 0
        punkter = []
        for dx, dy in bue:
            x += dx
            y += dy
            punkter.append((x * sx + tx, y * sy + ty))
        buer.append(punkter)

    def ring(indekser):
        pts: list = []
        for i in indekser:
            bue = buer[i] if i >= 0 else buer[~i][::-1]
            pts.extend(bue if not pts else bue[1:])
        return pts

    ut = []
    for g in topo["objects"]["Bydeler"]["geometries"]:
        navn = g["properties"]["BYDELSNAVN"]
        if navn.startswith("Marka"):
            navn = "Marka"
        for flate in (g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]):
            ut.append((navn, [ring(r) for r in flate]))
    return ut


def _inni(lon: float, lat: float, ring) -> bool:
    inne = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inne = not inne
    return inne


def bydel(lon: float, lat: float) -> tuple[str, str]:
    """Returnerer (bydel, metode) der metode er «innenfor» eller «nærmeste»."""
    for navn, ringer in _polygoner():
        if _inni(lon, lat, ringer[0]) and not any(_inni(lon, lat, h) for h in ringer[1:]):
            return navn, "innenfor"
    kos = math.cos(math.radians(lat))

    def avstand(ringer):
        return min(((x - lon) * kos) ** 2 + (y - lat) ** 2 for x, y in ringer[0])
    navn, _ = min(_polygoner(), key=lambda p: avstand(p[1]))
    return navn, "nærmeste"
