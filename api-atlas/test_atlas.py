"""Testkjører for API-atlaset — sjekker at alle kildene fortsatt lever.

Kjøring (fra repo-roten, krever bare Python 3.11+ og nett):

    python3 api-atlas/test_atlas.py

Hvert script i eksempler/ har en smoke()-funksjon som gjør ett lite,
ekte kall mot kilden og returnerer én kontrollinje. Kjøreren samler
resultatene i en tabell:

    ✓  kilden svarer og dataene ser riktige ut
    –  hoppet over (API-nøkkel mangler, f.eks. FROST_CLIENT_ID)
    ✗  kilden feiler — åpne scriptets DOK-lenke og se hva som er endret

Exit-kode 0 når alt er grønt, ellers antall feil. Kjør gjerne månedlig —
API-er endrer seg sjelden, men aldri når det passer.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

EKSEMPLER = Path(__file__).parent / "eksempler"


def last_modul(fil: Path):
    spec = importlib.util.spec_from_file_location(fil.stem, fil)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def main() -> int:
    filer = sorted(EKSEMPLER.glob("hent_*.py"))
    if not filer:
        print(f"Fant ingen hent_*.py i {EKSEMPLER}")
        return 1

    print(f"Tester {len(filer)} datakilder …\n")
    feil = 0
    bredde = max(len(f.stem) for f in filer) + 2

    for fil in filer:
        start = time.time()
        modul = None
        try:
            modul = last_modul(fil)
            status, melding = "✓", modul.smoke()
        except Exception as e:
            if type(e).__name__ == "ManglerNokkel":
                status, melding = "–", f"hoppet over: {e}"
            else:
                status, melding = "✗", f"{type(e).__name__}: {e}"
                feil += 1
        varighet = time.time() - start
        print(f"  {status}  {fil.stem:<{bredde}} {varighet:5.1f}s  {melding}")
        if status == "✗" and modul is not None and getattr(modul, "DOK", None):
            print(f"     {'':<{bredde}}        se dok: {modul.DOK}")

    print()
    if feil:
        print(f"{feil} av {len(filer)} kilder feiler. API-er endrer seg — "
              "åpne dok-lenken i det aktuelle scriptet og juster endepunktet.")
    else:
        print("Alle kilder svarer. Atlaset er ferskt.")
    return feil


if __name__ == "__main__":
    sys.exit(main())
