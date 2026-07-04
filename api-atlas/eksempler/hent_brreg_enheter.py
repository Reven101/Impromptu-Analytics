"""Brønnøysundregistrene — Enhetsregisteret.

Alle norske organisasjoner: navn, org.nr, adresse, kommune, sektor,
organisasjonsform, næringskode. Nøkkelen til å berike ALT annet som har
et organisasjonsnummer (tilskudd, anskaffelser, regnskap).

Kjøring:  python3 api-atlas/eksempler/hent_brreg_enheter.py
Nøkkel:   ingen
Lisens:   NLOD — oppgi «Kilde: Brønnøysundregistrene»
Dok:      https://data.brreg.no/enhetsregisteret/api/dokumentasjon

Endepunkter:
  GET /enhetsregisteret/api/enheter?navn=<søk>            navnesøk
  GET /enhetsregisteret/api/enheter?organisasjonsnummer=nr1,nr2,...
      batch-oppslag (opptil ~300 per kall — se tilskuddskompasset/
      tilskudd_data/hent_brreg_lookup.py for produksjonsbruk med cache)
  GET /enhetsregisteret/api/enheter/<orgnr>               enkeltoppslag
  GET /enhetsregisteret/api/underenheter?...              underenheter
  Hele registeret som gzip-JSON: /enhetsregisteret/api/enheter/lastned

Gull å grave i:
  - Berik tilskuddsdata med kommune/sektor (gjøres alt i Tilskuddskompasset)
  - Kart over kulturorganisasjoner per kommune (næringskode 90–91)
  - Alder på organisasjoner: når ble kulturlivet i en kommune stiftet?
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

KILDE = "Brreg Enhetsregisteret"
DOK = "https://data.brreg.no/enhetsregisteret/api/dokumentasjon"
API = "https://data.brreg.no/enhetsregisteret/api"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"


def hent_json(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": BRUKERAGENT})
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def sok_enheter(navn: str, antall: int = 5) -> list[dict]:
    url = f"{API}/enheter?{urllib.parse.urlencode({'navn': navn, 'size': antall})}"
    return hent_json(url).get("_embedded", {}).get("enheter", [])


def hent_enhet(orgnr: str) -> dict:
    return hent_json(f"{API}/enheter/{orgnr}")


def smoke() -> str:
    treff = sok_enheter("Kulturdirektoratet", 1)
    if not treff:
        raise ValueError("navnesøket ga ingen treff — har API-et endret seg?")
    enhet = hent_enhet(treff[0]["organisasjonsnummer"])
    kommune = (enhet.get("forretningsadresse") or {}).get("kommune", "?")
    return f"{enhet['navn']} ({enhet['organisasjonsnummer']}), {kommune}"


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Søker etter «Kulturdirektoratet» …")
    for e in sok_enheter("Kulturdirektoratet", 3):
        print(f"  {e['organisasjonsnummer']}  {e['navn']}")
    print(f"✓ {smoke()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
