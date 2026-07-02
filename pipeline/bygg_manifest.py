"""Bygger historier/innhold/manifest.json fra innholdsmappen.

Forsiden (historier/index.html) leser manifestet og genererer galleriet
automatisk. Kjør dette scriptet etter at du har lagt til eller endret en
historie:

    python3 pipeline/bygg_manifest.py

Scriptet validerer samtidig at alle historier følger metadata-kontrakten
(se kontrakt.py) — bryter en historie kontrakten, bygges ikke manifestet.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from kontrakt import INNHOLD_DIR, valider_historie

MANIFEST_FIL = INNHOLD_DIR / "manifest.json"


def main() -> int:
    historier = []
    feil = []

    for mappe in sorted(p for p in INNHOLD_DIR.iterdir() if p.is_dir()):
        feil += valider_historie(mappe)
        datafil = mappe / "data.json"
        if not datafil.exists():
            continue
        meta = json.loads(datafil.read_text(encoding="utf-8")).get("meta", {})
        historier.append({
            "id": mappe.name,
            "tittel": meta.get("tittel"),
            "kilde": meta.get("kilde"),
            "dato_hentet": meta.get("dato_hentet"),
            "geografi": meta.get("geografi"),
            "beskrivelse": meta.get("beskrivelse"),
            "demo": bool(meta.get("demo")),
        })

    if feil:
        print("Manifest IKKE bygget — rett kontraktsbruddene først:")
        for f in feil:
            print(f"  ✗ {f}")
        return 1

    historier.sort(key=lambda h: h["dato_hentet"] or "", reverse=True)
    manifest = {"generert": date.today().isoformat(), "historier": historier}
    MANIFEST_FIL.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"✓ manifest.json bygget med {len(historier)} historier")
    return 0


if __name__ == "__main__":
    sys.exit(main())
