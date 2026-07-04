"""MET — Locationforecast 2.0 (værvarsel).

Meteorologisk institutts værvarsel for et hvilket som helst punkt —
samme data som yr.no. Krever ingen nøkkel, men KREVER en identifiserende
User-Agent (anonyme kall blir blokkert). Maks 20 kall/sekund.

Kjøring:  python3 api-atlas/eksempler/hent_met_vaervarsel.py
Nøkkel:   ingen (men identifiserende User-Agent er obligatorisk)
Lisens:   NLOD / CC BY 4.0 — oppgi «Kilde: MET Norway»
Dok:      https://api.met.no/weatherapi/locationforecast/2.0/documentation

Endepunkt:
  GET https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=..&lon=..
      «compact» holder for det meste; «complete» gir alle detaljer.
      Respekter Expires-headeren — ikke hent oftere enn varselet oppdateres.

Historisk vær (observasjoner bakover i tid) ligger i søsterkilden Frost —
se hent_met_frost.py.

Gull å grave i:
  - Vær + utendørs kulturarrangement: regnet det bort publikum?
  - «Årets første 20-graders dag» per by over tid (via Frost)
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

KILDE = "MET Locationforecast 2.0"
DOK = "https://api.met.no/weatherapi/locationforecast/2.0/documentation"
API = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"


def hent_varsel(lat: float, lon: float) -> dict:
    url = f"{API}?{urllib.parse.urlencode({'lat': lat, 'lon': lon})}"
    req = urllib.request.Request(url, headers={"User-Agent": BRUKERAGENT})
    with urllib.request.urlopen(req, timeout=60) as svar:
        return json.loads(svar.read().decode("utf-8"))


def smoke() -> str:
    varsel = hent_varsel(59.9139, 10.7522)  # Oslo sentrum
    serie = varsel.get("properties", {}).get("timeseries", [])
    if not serie:
        raise ValueError("varselet mangler timeseries — har API-et endret seg?")
    naa = serie[0]
    detaljer = naa.get("data", {}).get("instant", {}).get("details", {})
    temp = detaljer.get("air_temperature")
    return f"Oslo nå ({naa.get('time')}): {temp} °C, {len(serie)} tidspunkter i varselet"


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Henter varsel for Oslo sentrum …")
    print(f"✓ {smoke()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
