"""Testkjører for API-atlaset — sjekker at alle kildene fortsatt lever.

Kjøring (fra repo-roten, krever bare Python 3.11+ og nett):

    python3 api-atlas/test_atlas.py

Hvert script i eksempler/ har en smoke()-funksjon som gjør ett lite,
ekte kall mot kilden og returnerer én kontrollinje. Kjøreren samler
resultatene i en tabell:

    ✓  kilden svarer og dataene ser riktige ut
    –  hoppet over (API-nøkkel mangler, f.eks. FROST_CLIENT_ID)
    ?  kilden ble aldri nådd (nede nett, brannmur eller proxy) — sier
       ingenting om atlaset, og DOK-lenken hjelper deg ikke
    ✗  kilden feiler — åpne scriptets DOK-lenke og se hva som er endret

Skillet mellom ? og ✗ er hele poenget: en blokkert utgående forbindelse
ser ellers nøyaktig ut som at alle sytten API-ene endret seg samtidig, og
da sender tabellen deg til dokumentasjonen for kilder som står stille.

Exit-kode: antall ✗. Er alt grønt, 0. Nådde vi ikke kildene i det hele
tatt, 1 — kjøringen er ikke konklusiv, og det skal ikke leses som grønt.
Kjør gjerne månedlig — API-er endrer seg sjelden, men aldri når det passer.
"""

from __future__ import annotations

import importlib.util
import socket
import ssl
import sys
import time
import urllib.error
from pathlib import Path

# Konsollen på Windows er cp1252 og kveler ✓/✗ med UnicodeEncodeError etter
# at kallene er gjort. Atlaset er bevisst frittstående, så vi arver ikke
# pipeline/kontrakt.py — vi gjentar de to linjene i stedet. No-op på Unix.
for _strom in (sys.stdout, sys.stderr):
    if hasattr(_strom, "reconfigure"):
        _strom.reconfigure(encoding="utf-8")

EKSEMPLER = Path(__file__).parent / "eksempler"

# HTTPError er med vilje utelatt: da svarte serveren, og et 404 på et
# endepunkt som pleide å finnes er nettopp det testen skal fange. Lista er
# smal med vilje — bare OSError ville dratt inn fil- og rettighetsfeil også.
NETTVERKSFEIL = (
    urllib.error.URLError,
    ConnectionError,
    TimeoutError,
    socket.gaierror,
    ssl.SSLError,
)


def nettverksaarsak(e: BaseException) -> BaseException | None:
    """Returner transportfeilen i årsakskjeden, eller None om kilden svarte.

    Scriptene pakker gjerne feilen sin i en ValueError med en lesbar melding;
    `raise ... from e` beholder årsaken, og her graver vi den fram igjen.
    """
    sett: set[int] = set()
    while e is not None and id(e) not in sett:
        sett.add(id(e))
        if isinstance(e, urllib.error.HTTPError):
            return None
        if isinstance(e, NETTVERKSFEIL):
            return e
        e = e.__cause__ or e.__context__
    return None


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
    uten_nett = 0
    hoppet = 0
    svarer = 0
    bredde = max(len(f.stem) for f in filer) + 2

    for fil in filer:
        start = time.time()
        modul = None
        try:
            modul = last_modul(fil)
            status, melding = "✓", modul.smoke()
            svarer += 1
        except Exception as e:
            aarsak = nettverksaarsak(e)
            if type(e).__name__ == "ManglerNokkel":
                status, melding = "–", f"hoppet over: {e}"
                hoppet += 1
            elif aarsak is not None:
                status, melding = "?", f"nådde ikke kilden: {aarsak}"
                uten_nett += 1
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
    if uten_nett:
        print(f"{uten_nett} av {len(filer)} kilder ble ikke nådd. Det er "
              "forbindelsen herfra, ikke kilden: sjekk nett, brannmur eller "
              "proxy, og kjør på nytt. Disse er hverken bekreftet eller "
              "avkreftet.")
    # Sluttlinjen skal ikke påstå mer enn kjøringen viste. En hoppet over
    # kilde er hverken bekreftet eller avkreftet, og «alle» dekker den ikke.
    if not feil and not uten_nett:
        if hoppet:
            print(f"{svarer} av {len(filer)} kilder svarer, {hoppet} hoppet over "
                  "uten API-nøkkel. Atlaset er ferskt så langt det er testet.")
        else:
            print(f"Alle {len(filer)} kilder svarer. Atlaset er ferskt.")
    elif not feil:
        print("Ingen kilder er bekreftet endret, men kjøringen er ikke konklusiv.")
    return feil or (1 if uten_nett else 0)


if __name__ == "__main__":
    sys.exit(main())
