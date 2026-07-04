"""SSB — Statistisk sentralbyrå (PxWebApi v2).

Norges største statistikkilde: befolkning, økonomi, kultur, KOSTRA
(kommunedata) og tusenvis av andre tabeller. Alt uten nøkkel.

Kjøring:  python3 api-atlas/eksempler/hent_ssb_statistikk.py
Nøkkel:   ingen
Lisens:   NLOD 2.0 / CC BY 4.0 — oppgi «Kilde: SSB»
Dok:      https://data.ssb.no/api/pxwebapi/v2/doc/

API-et har tre innganger:
  1. PxWebApi v2 (nyest, brukes her):
       GET  .../v2/tables?query=<søkeord>        søk i tabellkatalogen
       GET  .../v2/tables/<id>/metadata?lang=no  variabler og koder
       GET  .../v2/tables/<id>/data?...          data som json-stat2
  2. PxWeb v0 (eldre, POST-basert) — se pipeline/hent_ssb_navn.py i dette
     repoet for et komplett eksempel med v2→v0-fallback.
  3. Ferdige datasett: https://data.ssb.no/api/v0/dataset/ — populære
     tabeller som rene JSON/CSV-filer, null spørringsbygging.

KOSTRA-tips: kommunenes kulturutgifter ligger i KOSTRA-tabellene og
hentes gjennom akkurat samme API — søk «kostra kultur» i tabellkatalogen.

Gull å grave i:
  - Kommunenes kulturutgifter per innbygger over tid (KOSTRA)
  - Kulturskoledeltakelse mot befolkningsutvikling per kommune
  - Sysselsatte i kultursektoren per fylke
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

KILDE = "SSB PxWebApi v2"
DOK = "https://data.ssb.no/api/pxwebapi/v2/doc/"
API = "https://data.ssb.no/api/pxwebapi/v2"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"


def hent_json(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": BRUKERAGENT})
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def sok_tabeller(sokeord: str, antall: int = 5) -> list[dict]:
    """Søker i SSBs tabellkatalog og returnerer [{id, label}, ...]."""
    url = f"{API}/tables?{urllib.parse.urlencode({'query': sokeord, 'pageSize': antall, 'lang': 'no'})}"
    return hent_json(url).get("tables", [])


def hent_metadata(tabell_id: str) -> dict:
    """Variabler og gyldige koder for en tabell — trengs før datauttrekk."""
    return hent_json(f"{API}/tables/{tabell_id}/metadata?lang=no")


def smoke() -> str:
    treff = sok_tabeller("kulturskole", 3)
    if not treff:
        raise ValueError("tabellsøket ga ingen treff — har API-et endret seg?")
    meta = hent_metadata("06913")  # befolkning per kommune — brukes i pipeline/
    variabler = meta.get("variables") or list(meta.get("dimension") or [])
    if not variabler:
        raise ValueError("tabell 06913 mangler variabler i metadataene")
    return f"{len(treff)} tabelltreff på «kulturskole»; tabell 06913 har {len(variabler)} variabler"


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Søker etter «kulturskole» i tabellkatalogen …")
    for t in sok_tabeller("kulturskole", 5):
        print(f"  {t.get('id')}: {t.get('label')}")
    print("Henter metadata for tabell 06913 (befolkning per kommune) …")
    meta = hent_metadata("06913")
    for v in meta.get("variables", []):
        print(f"  variabel: {v.get('id') or v.get('code')} — {v.get('label')}")
    print("✓ SSB svarer. Se pipeline/hent_ssb_*.py for fullt datauttrekk med validering.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
