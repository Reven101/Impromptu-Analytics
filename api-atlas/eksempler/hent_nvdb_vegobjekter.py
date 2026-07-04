"""Statens vegvesen — Nasjonal vegdatabank (NVDB).

Hele det norske vegnettet med hundretusenvis av «vegobjekter»:
fartsgrenser, bomstasjoner, rasteplasser, tunneler, trafikkmengde (ÅDT).
Et av de rikeste geodata-API-ene i landet.

Kjøring:  python3 api-atlas/eksempler/hent_nvdb_vegobjekter.py
Nøkkel:   ingen (identifiserende X-Client-header er god skikk)
Lisens:   NLOD — oppgi «Kilde: Statens vegvesen»
Dok:      https://nvdb-docs.atlas.vegvesen.no/ (v4)
          https://api.vegdata.no/ (oversikt)

Endepunkter:
  v4:  GET https://nvdbapiles.atlas.vegvesen.no/vegobjekter/api/v4/
           vegobjekter/<typeid>?antall=<n>
  v3:  GET https://nvdbapiles-v3.atlas.vegvesen.no/vegobjekter/<typeid>
           ?antall=<n>  (eldre, fases ut — scriptet prøver v4 først)
  Objekttype 105 = fartsgrense, 45 = bomstasjon, 540 = trafikkmengde.
  Full typeliste: .../vegobjekttyper i samme API.

Gull å grave i:
  - Trafikkmengde forbi kulturarenaer — synlighet/tilgjengelighet
  - Fartsgrense-Norge: hvor mange meter 110-sone finnes egentlig?
  - Bomstasjonskart mot valgresultater (bompengepartiets geografi!)
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

KILDE = "Statens vegvesen NVDB"
DOK = "https://nvdb-docs.atlas.vegvesen.no/"
API_V4 = "https://nvdbapiles.atlas.vegvesen.no/vegobjekter/api/v4/vegobjekter"
API_V3 = "https://nvdbapiles-v3.atlas.vegvesen.no/vegobjekter"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"

FARTSGRENSE = 105  # vegobjekttype


def hent_json(url: str, ekstra_headers: dict | None = None, timeout: int = 60):
    headers = {"User-Agent": BRUKERAGENT, "X-Client": "impromptu-apiatlas",
               "Accept": "application/json"}
    headers.update(ekstra_headers or {})
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def hent_vegobjekter(typeid: int, antall: int = 3) -> tuple[str, list[dict]]:
    """Prøver v4 først, faller tilbake til v3. Returnerer (versjon, objekter)."""
    params = urllib.parse.urlencode({"antall": antall})
    try:
        data = hent_json(f"{API_V4}/{typeid}?{params}")
        return "v4", data.get("objekter", [])
    except Exception:
        data = hent_json(
            f"{API_V3}/{typeid}?{params}",
            {"Accept": "application/vnd.vegvesen.nvdb-v3-rev1+json"},
        )
        return "v3", data.get("objekter", [])


def smoke() -> str:
    versjon, objekter = hent_vegobjekter(FARTSGRENSE, 3)
    if not objekter:
        raise ValueError("ingen vegobjekter returnert — sjekk dok for endret API")
    return f"{len(objekter)} fartsgrense-objekter hentet via {versjon}; første id: {objekter[0].get('id')}"


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Henter noen fartsgrense-objekter (type 105) …")
    print(f"✓ {smoke()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
