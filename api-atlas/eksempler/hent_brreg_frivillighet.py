"""Brønnøysundregistrene — Frivillighetsregisteret.

Alle registrerte frivillige organisasjoner, med ICNPO-kategorier
(aktivitetsområder som «kunst og kultur», «idrett» osv.). Perfekt makker
til tilskuddsdataene: hvem av mottakerne er registrert frivillig, og i
hvilken kategori?

Kjøring:  python3 api-atlas/eksempler/hent_brreg_frivillighet.py
Nøkkel:   ingen
Lisens:   NLOD — oppgi «Kilde: Brønnøysundregistrene»
Dok:      https://data.brreg.no/frivillighetsregisteret/api/docs
          (Swagger: samme URL — sjekk her hvis endepunktene har flyttet seg)

Endepunkter:
  GET /frivillighetsregisteret/api/frivillige-organisasjoner?size=<n>
      søk/utlisting. NB: bruker «searchAfter»-paginering, ikke sidetall —
      sett searchAfter til høyeste org.nr fra forrige side for neste side.
  GET /frivillighetsregisteret/api/frivillige-organisasjoner/<orgnr>
      enkeltoppslag

Gull å grave i:
  - Andel tilskuddsmottakere som står i Frivillighetsregisteret
  - Kulturfrivillighetens geografi: ICNPO «kunst og kultur» per kommune
  - Vekst/frafall i frivillige organisasjoner over tid
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

KILDE = "Brreg Frivillighetsregisteret"
DOK = "https://data.brreg.no/frivillighetsregisteret/api/docs"
API = "https://data.brreg.no/frivillighetsregisteret/api/frivillige-organisasjoner"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"


def hent_json(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": BRUKERAGENT})
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def hent_side(antall: int = 5, search_after: str | None = None) -> list[dict]:
    params: dict = {"size": antall}
    if search_after:
        params["searchAfter"] = search_after
    data = hent_json(f"{API}?{urllib.parse.urlencode(params)}")
    # HAL-format: lista kan ligge under _embedded eller rett på rota
    embedded = data.get("_embedded") or {}
    for verdi in embedded.values():
        if isinstance(verdi, list):
            return verdi
    return data if isinstance(data, list) else []


def smoke() -> str:
    orgs = hent_side(3)
    if not orgs:
        raise ValueError("fikk ingen organisasjoner — sjekk endepunktet i Swagger-dok")
    forste = orgs[0]
    orgnr = forste.get("organisasjonsnummer", "?")
    navn = (forste.get("navn") or forste.get("organisasjonsnavn") or "?")
    return f"{len(orgs)} organisasjoner hentet; første: {navn} ({orgnr})"


def main() -> int:
    print(f"{KILDE} — {DOK}")
    for o in hent_side(5):
        print(f"  {o.get('organisasjonsnummer', '?')}  {o.get('navn') or o.get('organisasjonsnavn', '?')}")
    print(f"✓ {smoke()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
