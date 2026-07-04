"""Entur — kollektivtrafikk for hele Norge.

All rutedata for buss, tog, trikk, T-bane og ferge i Norge, pluss
sanntid og geokoding av holdeplasser. Krever ingen nøkkel, men en
identifiserende ET-Client-Name-header er obligatorisk.

Kjøring:  python3 api-atlas/eksempler/hent_entur_reiser.py
Nøkkel:   ingen (men ET-Client-Name-header kreves: «firma-app»)
Lisens:   NLOD — oppgi «Kilde: Entur»
Dok:      https://developer.entur.org/

Endepunkter:
  GET  https://api.entur.io/geocoder/v1/autocomplete?text=<søk>&size=<n>
       holdeplass-/stedssøk (brukes her — enkel REST)
  POST https://api.entur.io/journey-planner/v3/graphql
       reisesøk (GraphQL). Eksempelspørring:
         { trip(from: {place: "NSR:StopPlace:59872"},
                to:   {place: "NSR:StopPlace:58366"}) {
             tripPatterns { duration legs { mode line { publicCode } } } } }

Gull å grave i:
  - Kollektivtilgjengelighet til kulturarenaer: hvor mange når
    Kanonhallen på under 30 minutter?
  - Rutetetthet by mot bygd — kart over avganger per time
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

KILDE = "Entur (kollektivdata)"
DOK = "https://developer.entur.org/"
API = "https://api.entur.io/geocoder/v1/autocomplete"
KLIENTNAVN = "impromptu-apiatlas"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"


def hent_json(url: str, timeout: int = 60):
    req = urllib.request.Request(
        url, headers={"User-Agent": BRUKERAGENT, "ET-Client-Name": KLIENTNAVN}
    )
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def sok_holdeplass(tekst: str, antall: int = 5) -> list[dict]:
    url = f"{API}?{urllib.parse.urlencode({'text': tekst, 'size': antall, 'lang': 'no'})}"
    return hent_json(url).get("features", [])


def smoke() -> str:
    treff = sok_holdeplass("Oslo S", 1)
    if not treff:
        raise ValueError("holdeplass-søket ga ingen treff — har API-et endret seg?")
    e = treff[0].get("properties", {})
    return f"{e.get('label', '?')} (id: {e.get('id', '?')})"


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Søker etter «Oslo S» i geocoderen …")
    for f in sok_holdeplass("Oslo S", 3):
        p = f.get("properties", {})
        print(f"  {p.get('label', '?')}  [{p.get('id', '?')}]")
    print(f"✓ {smoke()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
