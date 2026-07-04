"""Kartverket — Adresse-API (geokoding).

Slår opp offisielle norske adresser fra Matrikkelen og gir koordinater,
kommune, postnummer m.m. Broen fra «adresse i et regneark» til «punkt på
et kart». Oppdateres normalt daglig.

Kjøring:  python3 api-atlas/eksempler/hent_kartverket_adresser.py
Nøkkel:   ingen
Lisens:   CC BY 4.0 — oppgi «Kilde: Kartverket»
Dok:      https://ws.geonorge.no/adresser/v1/ (Swagger)

Endepunkt:
  GET https://ws.geonorge.no/adresser/v1/sok?sok=<fritekst>&treffPerSide=<n>
      Fritekstsøk med * og ? som jokertegn. Kan filtreres på
      kommunenummer, postnummer osv. — se Swagger.
  GET .../punktsok?lat=..&lon=..&radius=..   omvendt oppslag (punkt→adresse)

Gull å grave i:
  - Geokod tilskuddsmottakernes adresser (fra Brreg) → kulturkart
  - Avstandsanalyser: hvor langt har folk til nærmeste kulturtilbud?
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

KILDE = "Kartverket Adresse-API"
DOK = "https://ws.geonorge.no/adresser/v1/"
API = "https://ws.geonorge.no/adresser/v1/sok"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"


def hent_json(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": BRUKERAGENT})
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def sok_adresse(fritekst: str, antall: int = 3) -> list[dict]:
    url = f"{API}?{urllib.parse.urlencode({'sok': fritekst, 'treffPerSide': antall})}"
    return hent_json(url).get("adresser", [])


def smoke() -> str:
    treff = sok_adresse("Mølleparken 4, Oslo", 1)  # Kulturdirektoratets adresse
    if not treff:
        raise ValueError("adressesøket ga ingen treff — har API-et endret seg?")
    a = treff[0]
    punkt = a.get("representasjonspunkt") or {}
    return (f"{a.get('adressetekst', '?')}, {a.get('poststed', '?')} → "
            f"lat {punkt.get('lat'):.4f}, lon {punkt.get('lon'):.4f}")


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Geokoder «Mølleparken 4, Oslo» …")
    print(f"✓ {smoke()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
