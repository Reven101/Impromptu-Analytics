"""Genererer verdensgeometri.js — landomriss som ferdige SVG-baner, nøklet på ISO2.

Kjøring (krever nett første gang; geojson-fila mellomlagres i rådatamappa):

    python pipeline/lag_verdensgeometri.py

Motoren skal ikke drive med kartprojeksjon i nettleseren. Den skal få `d`-strenger
den kan male. All matematikk skjer her, én gang, og resultatet sjekkes inn — samme
prinsipp som ellers i pipelinen: nettsiden gjør ingen beregninger den kan slippe.

**Projeksjonen er Robinson, ikke ekvirektangulær.** Ekvirektangulær er én linje kode
(`x = lon`), men den strekker høye breddegrader ubrukelig: Norge, Sverige og Finland
blir dobbelt så brede som de skal være, og Grønland sluker Nord-Atlanteren. Når
Norden er selve utgangspunktet for historien, er det ikke en detalj. Robinson er et
kompromiss uten matematisk renhet — den er verken arealriktig eller vinkelriktig — og
nettopp derfor ser verden riktig ut i den.

**ISO_A2_EH, ikke ISO_A2.** Natural Earth fører «-99» i `ISO_A2` for fem land, og to
av dem er Norge og Frankrike. Det ville vært en stille feil: kartet ville rendret,
Norge ville bare vært hvitt.

Antarktis droppes. Ingen har satt opp Ibsen der, og kontinentet ville tatt en femdel
av kartflaten.
"""

from __future__ import annotations

import json
import math
import os
import urllib.request
from pathlib import Path

import kontrakt  # noqa: F401

KILDE = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
         "master/geojson/ne_110m_admin_0_countries.geojson")

RAADATA_DIR = Path(
    os.environ.get("IBSENSTAGE_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ibsenstage"
)
UTFIL = Path(__file__).resolve().parent.parent / "historier" / "motor" / "verdensgeometri.js"

BREDDE = 1000.0        # viewBox-bredde; høyden regnes ut av projeksjonen
TOLERANSE = 0.35       # Douglas-Peucker, i viewBox-enheter
DESIMALER = 1

# Robinson-tabellen: lengdefaktor (A) og høyde (B) for hver 5. breddegrad.
ROBINSON_A = [1.0000, 0.9986, 0.9954, 0.9900, 0.9822, 0.9730, 0.9600, 0.9427,
              0.9216, 0.8962, 0.8679, 0.8350, 0.7986, 0.7597, 0.7186, 0.6732,
              0.6213, 0.5722, 0.5322]
ROBINSON_B = [0.0000, 0.0620, 0.1240, 0.1860, 0.2480, 0.3100, 0.3720, 0.4340,
              0.4958, 0.5571, 0.6176, 0.6769, 0.7346, 0.7903, 0.8435, 0.8936,
              0.9394, 0.9761, 1.0000]


def robinson(lon: float, lat: float) -> tuple[float, float]:
    """Grader inn, projiserte enheter ut. Lineær interpolasjon i 5°-tabellen."""
    a = min(abs(lat), 90.0) / 5.0
    i = min(int(a), len(ROBINSON_A) - 2)
    t = a - i
    faktor = ROBINSON_A[i] + (ROBINSON_A[i + 1] - ROBINSON_A[i]) * t
    hoyde = ROBINSON_B[i] + (ROBINSON_B[i + 1] - ROBINSON_B[i]) * t
    x = 0.8487 * faktor * math.radians(lon)
    y = 1.3523 * hoyde * (1 if lat >= 0 else -1)
    return x, y


def _forenkle(punkter: list[tuple[float, float]], toleranse: float) -> list:
    """Douglas-Peucker. Uten den blir fila unødig stor for detaljer ingen ser."""
    if len(punkter) < 3:
        return punkter
    start, slutt = punkter[0], punkter[-1]
    dx, dy = slutt[0] - start[0], slutt[1] - start[1]
    lengde = math.hypot(dx, dy)
    verst, indeks = -1.0, 0
    for n in range(1, len(punkter) - 1):
        px, py = punkter[n]
        if lengde == 0:
            d = math.hypot(px - start[0], py - start[1])
        else:
            d = abs(dy * px - dx * py + slutt[0] * start[1] - slutt[1] * start[0]) / lengde
        if d > verst:
            verst, indeks = d, n
    if verst <= toleranse:
        return [start, slutt]
    return (_forenkle(punkter[:indeks + 1], toleranse)[:-1]
            + _forenkle(punkter[indeks:], toleranse))


def main() -> None:
    RAADATA_DIR.mkdir(parents=True, exist_ok=True)
    lokal = RAADATA_DIR / "ne_110m_admin_0_countries.geojson"
    if not lokal.exists():
        print(f"laster {KILDE}")
        req = urllib.request.Request(
            KILDE, headers={"User-Agent": "impromptu.no research (kontakt: impromptu.no)"})
        with urllib.request.urlopen(req, timeout=180) as svar:
            lokal.write_bytes(svar.read())
    d = json.loads(lokal.read_text(encoding="utf-8"))

    # Projiser alt først, så vi kjenner utstrekningen før vi skalerer til viewBox.
    projisert: dict[str, list[list[tuple[float, float]]]] = {}
    for f in d["features"]:
        p = f["properties"]
        kode = p.get("ISO_A2_EH") or p.get("ISO_A2") or ""
        if kode in ("", "-99", "AQ"):
            continue
        g = f["geometry"]
        polygoner = (g["coordinates"] if g["type"] == "MultiPolygon"
                     else [g["coordinates"]])
        ringer = []
        for poly in polygoner:
            for ring in poly:
                ringer.append([robinson(lon, lat) for lon, lat in ring])
        if ringer:
            projisert.setdefault(kode, []).extend(ringer)

    alle = [pt for ringer in projisert.values() for r in ringer for pt in r]
    minx = min(p[0] for p in alle); maksx = max(p[0] for p in alle)
    miny = min(p[1] for p in alle); maksy = max(p[1] for p in alle)
    skala = BREDDE / (maksx - minx)
    hoyde = round((maksy - miny) * skala, 1)

    def til_viewbox(pt):
        # y snus: SVG vokser nedover, breddegrad oppover.
        return ((pt[0] - minx) * skala, (maksy - pt[1]) * skala)

    baner: dict[str, str] = {}
    for kode, ringer in projisert.items():
        deler = []
        for ring in ringer:
            pts = _forenkle([til_viewbox(p) for p in ring], TOLERANSE)
            if len(pts) < 3:
                continue  # en øy som forsvant i forenklingen
            d_ = " ".join(
                f"{'M' if n == 0 else 'L'}{x:.{DESIMALER}f} {y:.{DESIMALER}f}"
                for n, (x, y) in enumerate(pts))
            deler.append(d_ + "Z")
        if deler:
            baner[kode] = "".join(deler)

    linjer = [
        "/* GENERERT AV pipeline/lag_verdensgeometri.py — IKKE REDIGER FOR HÅND.",
        f"   Kilde: Natural Earth 110m. Projeksjon: Robinson. Nøkkel: ISO2 (ISO_A2_EH).",
        f"   {len(baner)} land. Kjør scriptet på nytt for å oppdatere. */",
        "",
        f"export const VERDEN_VIEWBOX = \"0 0 {BREDDE:.0f} {hoyde:.0f}\";",
        "",
        "export const VERDEN = {",
    ]
    for kode in sorted(baner):
        linjer.append(f'  "{kode}": "{baner[kode]}",')
    linjer.append("};")
    UTFIL.write_text("\n".join(linjer) + "\n", encoding="utf-8")

    punkter = sum(b.count("L") + b.count("M") for b in baner.values())
    print(f"{len(baner)} land, {punkter} punkter etter forenkling")
    print(f"  viewBox 0 0 {BREDDE:.0f} {hoyde:.0f}")
    print(f"  {UTFIL.stat().st_size / 1024:.0f} kB -> {UTFIL}")
    for k in ("NO", "DE", "US", "CN", "FR", "BD"):
        print(f"    {k}: {'ja' if k in baner else 'MANGLER'}")


if __name__ == "__main__":
    main()
