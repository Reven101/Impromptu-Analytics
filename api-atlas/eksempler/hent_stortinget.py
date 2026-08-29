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
  GET https://data.stortinget.no/eksport/publikasjoner?publikasjontype=<type>&sesjonid=<id>
  GET https://data.stortinget.no/eksport/publikasjon?publikasjonid=<eksport_id>
  ... og mange flere — se dokumentasjonen.

Tre ting som kostet tid å finne ut (verifisert 2026-08-29):

  1. `publikasjoner` KREVER `publikasjontype`. Uten den: HTTP 400 med
     «manglende eller ugyldig parameter: 'PublikasjonType'». Feilmeldingen
     lister ikke de gyldige verdiene. Disse virker:
         referat, innstilling, dok8, dok12, lovvedtak, innberetning
     Disse gjør ikke: innstillinger, sporretime, alle.
     Volum i sesjon 2025-2026: 471 innstillinger, 325 dok8, 107 referater,
     96 lovvedtak, 4 innberetninger, 0 dok12.

  2. `publikasjon` svarer XML uansett `format=json`. Det er her fulltekstene
     ligger — et representantforslag ga 4 850 tegn tekst utenfor taggene.
     Alle andre endepunkter respekterer format=json.

  3. `sesjoner` lister sesjoner som ikke har begynt (2028-2029 finnes i
     august 2026, tom). Bruk `innevaerende_sesjon` — som er et OBJEKT med
     id inni, ikke en streng — og regn eldre sesjoner som det som ligger
     etter den i lista.

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
