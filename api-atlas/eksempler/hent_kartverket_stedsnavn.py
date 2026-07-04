"""Kartverket — Stedsnavn-API (Sentralt stedsnavnregister, SSR).

Over en million norske stedsnavn med koordinater, navnetype (fjell, vik,
gård, bruk …) og språk (norsk, samisk, kvensk). En kulturskatt i seg
selv — stedsnavnene bærer historie.

Kjøring:  python3 api-atlas/eksempler/hent_kartverket_stedsnavn.py
Nøkkel:   ingen
Lisens:   CC BY 4.0 — oppgi «Kilde: Kartverket»
Dok:      https://ws.geonorge.no/stedsnavn/v1/ (Swagger)

Endepunkter:
  GET .../navn?sok=<søk>&treffPerSide=<n>&side=1   navnesøk (* som joker)
  GET .../punkt?nord=..&ost=..&radius=..&koordsys=..  navn rundt et punkt
  GET .../sted?stedsnummer=..                       enkeltoppslag

Gull å grave i:
  - Navnehistorier: hvor i landet finnes «-heim», «-set», «-vin»-navn?
    (bosettingshistorie fra jernalderen, lesbar i kartet)
  - Samiske og kvenske stedsnavn — utbredelse og tetthet
  - Kombiner med SSB-navnestatistikken: steder som deler navn med folk
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

KILDE = "Kartverket Stedsnavn-API"
DOK = "https://ws.geonorge.no/stedsnavn/v1/"
API = "https://ws.geonorge.no/stedsnavn/v1/navn"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"


def hent_json(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": BRUKERAGENT})
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def sok_navn(sok: str, antall: int = 5) -> list[dict]:
    url = f"{API}?{urllib.parse.urlencode({'sok': sok, 'treffPerSide': antall, 'side': 1})}"
    return hent_json(url).get("navn", [])


def smoke() -> str:
    treff = sok_navn("Galdhøpiggen", 1)
    if not treff:
        raise ValueError("stedsnavnsøket ga ingen treff — har API-et endret seg?")
    n = treff[0]
    return f"{n.get('skrivemåte', '?')} ({n.get('navneobjekttype', '?')}), stedsnummer {n.get('stedsnummer', '?')}"


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Søker etter «Galdhøpiggen» …")
    for n in sok_navn("Galdhøpiggen", 3):
        print(f"  {n.get('skrivemåte', '?')} — {n.get('navneobjekttype', '?')}")
    print(f"✓ {smoke()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
