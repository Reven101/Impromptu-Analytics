"""Stortinget — åpne data (data.stortinget.no).

Alt fra nasjonalforsamlingen: saker, voteringer, spørsmål, referater og
representanter tilbake til 1945. For en kulturanalytiker: hele det
politiske ordskiftet om kulturfeltet, strukturert.

Kjøring:  python3 api-atlas/eksempler/hent_stortinget.py
Nøkkel:   ingen
Lisens:   NLOD — oppgi «Kilde: Stortinget»
Dok:      https://data.stortinget.no/dokumentasjon-og-hjelp/

Endepunkter (XML som standard, legg på format=json for JSON):
  GET https://data.stortinget.no/eksport/allepartier?format=json
  GET https://data.stortinget.no/eksport/sesjoner?format=json
  GET https://data.stortinget.no/eksport/saker?sesjonid=<id>&format=json
  GET https://data.stortinget.no/eksport/voteringer?sakid=<id>&format=json
  ... og mange flere — se dokumentasjonen.

Gull å grave i:
  - Hvor ofte nevnes «kultur» i saker per sesjon — politisk oppmerksomhet
    over tid
  - Voteringsmønstre i kultursaker: hvem stemmer sammen?
  - Spørretimen som datasett: hvilke tema masete representanter mest om?
"""

from __future__ import annotations

import json
import sys
import urllib.request

KILDE = "Stortinget (åpne data)"
DOK = "https://data.stortinget.no/dokumentasjon-og-hjelp/"
API = "https://data.stortinget.no/eksport"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"


def hent_json(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": BRUKERAGENT})
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def hent_partier() -> list[dict]:
    data = hent_json(f"{API}/allepartier?format=json")
    return data.get("partier_liste", [])


def smoke() -> str:
    partier = hent_partier()
    if len(partier) < 5:
        raise ValueError(f"bare {len(partier)} partier — har API-et endret seg?")
    navn = [p.get("navn", "?") for p in partier[:3]]
    return f"{len(partier)} partier i registeret; blant dem {', '.join(navn)}"


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Henter partiregisteret …")
    print(f"✓ {smoke()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
