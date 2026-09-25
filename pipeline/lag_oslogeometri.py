"""Genererer historier/motor/oslogeometri.js — Oslos bydeler som ferdige SVG-baner.

Kjøring (krever nett første gang; grensefila mellomlagres i rådatamappa):

    python pipeline/lag_oslogeometri.py

Samme prinsipp som lag_verdensgeometri.py: all projeksjon skjer her, én gang,
og nettsiden får `d`-strenger den bare maler. Resultatet sjekkes inn.

Kilde: Oslo kommunes bydelsgrenser via AnalyseABO (se oslo_bydel.py).

**Projeksjon:** lengdegrad skalert med cos(midtbreddegraden). Over et område på
størrelse med Oslo er feilen i målestokk under én prosent; en ekte projeksjon
ville ikke synes.

**Marka er utelatt.** Den er større enn resten av byen til sammen, har ingen
skoler, og ville presset bydelene sammen i et hjørne av figuren.

**Etikettpunktet** er ikke tyngdepunktet: for en uregelmessig bydel kan det
havne utenfor polygonet (eller i nabobydelen). Vi søker i stedet i et rutenett
etter punktet inni bydelen som ligger lengst fra grensen — samme idé som
«polylabel», uten biblioteket.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import kontrakt  # noqa: F401
from oslo_bydel import _inni, _polygoner

UT = Path(__file__).resolve().parents[1] / "historier" / "motor" / "oslogeometri.js"
BREDDE = 1000.0
TOLERANSE = 0.6            # Douglas-Peucker i viewBox-enheter
# Små bydeler i sentrum ligger så tett at etikettene kolliderer. Flytt for hånd
# (viewBox-enheter), og sjekk resultatet i nettleseren etter hver endring.
ETIKETT_FLYTT = {"St. Hanshaugen": (-18, 30), "Sagene": (4, -12)}


def _forenkle(pts: list, tol: float) -> list:
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    lengde = math.hypot(dx, dy)
    verst, idx = -1.0, 0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        d = (math.hypot(px - x1, py - y1) if lengde == 0
             else abs(dy * px - dx * py + x2 * y1 - y2 * x1) / lengde)
        if d > verst:
            verst, idx = d, i
    if verst <= tol:
        return [pts[0], pts[-1]]
    return _forenkle(pts[:idx + 1], tol)[:-1] + _forenkle(pts[idx:], tol)


def _avstand_til_kant(x: float, y: float, ring: list) -> float:
    best = float("inf")
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy or 1)))
        best = min(best, math.hypot(x - x1 - t * dx, y - y1 - t * dy))
    return best


def _etikettpunkt(ring: list) -> tuple[float, float]:
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    best, punkt = -1.0, (sum(xs) / len(xs), sum(ys) / len(ys))
    for i in range(1, 60):
        for j in range(1, 60):
            x = min(xs) + (max(xs) - min(xs)) * i / 60
            y = min(ys) + (max(ys) - min(ys)) * j / 60
            if _inni(x, y, ring):
                d = _avstand_til_kant(x, y, ring)
                if d > best:
                    best, punkt = d, (x, y)
    return punkt


def main() -> None:
    bydeler = [(n, r) for n, r in _polygoner() if n != "Marka"]
    alle = [pt for _, ringer in bydeler for ring in ringer for pt in ring]
    lat0 = math.radians(sum(p[1] for p in alle) / len(alle))
    proj = lambda lon, lat: (lon * math.cos(lat0), -lat)      # noqa: E731
    xs = [proj(*p)[0] for p in alle]
    ys = [proj(*p)[1] for p in alle]
    skala = BREDDE / (max(xs) - min(xs))
    hoyde = round((max(ys) - min(ys)) * skala, 1)

    def vb(lon, lat):
        x, y = proj(lon, lat)
        return ((x - min(xs)) * skala, (y - min(ys)) * skala)

    baner: dict[str, list[str]] = {}
    storste: dict[str, list] = {}
    for navn, ringer in bydeler:
        for ring in ringer:
            pts = _forenkle([vb(lon, lat) for lon, lat in ring], TOLERANSE)
            if len(pts) < 3:
                continue
            baner.setdefault(navn, []).append(
                "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z")
            areal = abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2
            if navn not in storste or areal > storste[navn][0]:
                storste[navn] = [areal, pts]
    etikett = {}
    for n, v in storste.items():
        x, y = _etikettpunkt(v[1])
        dx, dy = ETIKETT_FLYTT.get(n, (0, 0))
        etikett[n] = [round(x + dx, 1), round(y + dy, 1)]

    if len(baner) != 16:
        raise SystemExit(f"Ventet 15 bydeler + Sentrum, fikk {len(baner)}: {sorted(baner)}")
    UT.write_text(
        "/* GENERERT AV pipeline/lag_oslogeometri.py — IKKE REDIGER FOR HÅND.\n"
        "   Kilde: Oslo kommunes bydelsgrenser (via AnalyseABO). Marka utelatt.\n"
        f"   {len(baner)} bydeler. Kjør scriptet på nytt for å oppdatere. */\n\n"
        f'export const OSLO_VIEWBOX = "0 0 {int(BREDDE)} {hoyde}";\n\n'
        "export const OSLO = " + json.dumps({n: " ".join(d) for n, d in sorted(baner.items())},
                                            ensure_ascii=False, indent=1) + ";\n\n"
        "export const OSLO_ETIKETT = " + json.dumps(dict(sorted(etikett.items())), ensure_ascii=False) + ";\n",
        encoding="utf-8")
    print(f"✓ Skrev {UT} ({UT.stat().st_size // 1024} kB), viewBox 0 0 {int(BREDDE)} {hoyde}")


if __name__ == "__main__":
    main()
