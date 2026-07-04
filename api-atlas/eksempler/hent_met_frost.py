"""MET — Frost (historiske værobservasjoner).

Observasjoner fra norske værstasjoner tilbake til 1800-tallet:
temperatur, nedbør, vind, snødybde. Der Locationforecast ser fremover,
ser Frost bakover — dette er kilden for «hvordan var været da».

Kjøring:  FROST_CLIENT_ID=<din-id> python3 api-atlas/eksempler/hent_met_frost.py
Nøkkel:   GRATIS client-id — registrer deg på https://frost.met.no/auth/requestCredentials.html
          (tar ett minutt, e-post holder). Legg den i miljøvariabelen
          FROST_CLIENT_ID. Scriptet hopper pent over hvis den mangler.
Lisens:   NLOD / CC BY 4.0 — oppgi «Kilde: MET Norway / Frost»
Dok:      https://frost.met.no/api.html

Endepunkter (client-id sendes som brukernavn i basic auth, tomt passord):
  GET https://frost.met.no/sources/v0.jsonld?...        værstasjoner
  GET https://frost.met.no/observations/v0.jsonld?sources=SN18700&
      referencetime=2026-01-01/2026-01-31&elements=mean(air_temperature P1D)
      (SN18700 = Blindern, Oslo)

Gull å grave i:
  - 17. mai-været i din by, hvert år siden 1900
  - Skisesongens lengde over tid (snødybde per stasjon)
  - Kobling mot arrangementsdata: værets makt over publikumstall
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.parse
import urllib.request

KILDE = "MET Frost (historisk vær)"
DOK = "https://frost.met.no/api.html"
API = "https://frost.met.no"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"


class ManglerNokkel(Exception):
    """API-nøkkel mangler — testkjøreren hopper over, uten å feile."""


def hent_json(sti: str, params: dict) -> dict:
    client_id = os.environ.get("FROST_CLIENT_ID", "").strip()
    if not client_id:
        raise ManglerNokkel(
            "sett FROST_CLIENT_ID — gratis registrering: "
            "https://frost.met.no/auth/requestCredentials.html"
        )
    url = f"{API}{sti}?{urllib.parse.urlencode(params)}"
    auth = base64.b64encode(f"{client_id}:".encode()).decode()
    req = urllib.request.Request(
        url, headers={"User-Agent": BRUKERAGENT, "Authorization": f"Basic {auth}"}
    )
    with urllib.request.urlopen(req, timeout=60) as svar:
        return json.loads(svar.read().decode("utf-8"))


def smoke() -> str:
    data = hent_json("/sources/v0.jsonld", {"ids": "SN18700"})
    stasjoner = data.get("data", [])
    if not stasjoner:
        raise ValueError("fant ikke stasjon SN18700 (Blindern) — har API-et endret seg?")
    s = stasjoner[0]
    return f"stasjon {s.get('id')}: {s.get('name')}, i drift siden {s.get('validFrom', '?')[:10]}"


def main() -> int:
    print(f"{KILDE} — {DOK}")
    try:
        print(f"✓ {smoke()}")
    except ManglerNokkel as e:
        print(f"– hoppet over: {e}")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
