"""Nasjonalbiblioteket — katalog- og tekst-API.

Metadata for alt NB har digitalisert: bøker, aviser, bilder, kart, musikk
og radio tilbake til 1700-tallet. For kulturanalyse er dette en av
Norges mest undervurderte kilder — hele den norske offentligheten,
søkbar.

Kjøring:  python3 api-atlas/eksempler/hent_nasjonalbiblioteket.py
Nøkkel:   ingen for katalogsøk
Lisens:   metadata er åpne; selve verkene har egne rettigheter
Dok:      https://api.nb.no/ (Swagger)

Endepunkter:
  GET https://api.nb.no/catalog/v1/items?q=<søk>&size=<n>
      katalogsøk. Filtrer med f.eks. filter=mediatype:aviser
  N-gram (ordbruk over tid i bøker/aviser — «norsk Google Ngram»):
      https://api.nb.no/dhlab/ og https://www.nb.no/ngram/
      (DH-laben har eget Python-bibliotek: pip install dhlab)

Gull å grave i:
  - Ordet «kultur» i norske aviser 1900–2026 — begrepshistorie som graf
  - Når begynte avisene å skrive om din hjemkommune?
  - Slektshistorie: søk forfedres navn i digitaliserte aviser (slektstre!)
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

KILDE = "Nasjonalbiblioteket"
DOK = "https://api.nb.no/"
API = "https://api.nb.no/catalog/v1/items"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"


def hent_json(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": BRUKERAGENT})
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def sok_katalog(sok: str, antall: int = 5) -> list[dict]:
    url = f"{API}?{urllib.parse.urlencode({'q': sok, 'size': antall})}"
    data = hent_json(url)
    return data.get("_embedded", {}).get("items", [])


def smoke() -> str:
    treff = sok_katalog("Henrik Ibsen", 3)
    if not treff:
        raise ValueError("katalogsøket ga ingen treff — har API-et endret seg?")
    m = treff[0].get("metadata", {})
    return f"{len(treff)} treff på «Henrik Ibsen»; første: {m.get('title', '?')} ({m.get('mediaTypes', ['?'])[0]})"


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Søker etter «Henrik Ibsen» i katalogen …")
    for item in sok_katalog("Henrik Ibsen", 5):
        m = item.get("metadata", {})
        print(f"  {m.get('title', '?')}  [{', '.join(m.get('mediaTypes', []))}]")
    print(f"✓ {smoke()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
