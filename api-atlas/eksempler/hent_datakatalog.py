"""data.norge.no — Felles datakatalog (Digdir).

Norges offisielle katalog over åpne datasett og API-er fra offentlig
sektor. Ikke en datakilde i seg selv, men *kartet* over alle de andre —
førstevalget når du lurer på «finnes det data om X?».

Kjøring:  python3 api-atlas/eksempler/hent_datakatalog.py
Nøkkel:   ingen
Lisens:   katalogen er åpen; hvert datasett har egen lisens (som regel NLOD)
Dok:      https://data.norge.no/nb/technical/api/search

Endepunkter:
  POST https://search.api.fellesdatakatalog.digdir.no/search
       fritekstsøk på tvers av alle ressurstyper
  POST https://search.api.fellesdatakatalog.digdir.no/search/datasets
       bare datasett
  Body: {"query": "<søkeord>", "pagination": {"page": 0, "size": 5}}
  Det finnes også SPARQL- og KI-søk-API — se dokumentasjonen.

Gull å grave i:
  - Systematisk kartlegging: hvilke kulturdata finnes egentlig der ute?
  - Overvåk nye datasett innen et tema (kjør søket månedlig, sammenlign)
"""

from __future__ import annotations

import json
import sys
import urllib.request

KILDE = "Felles datakatalog (data.norge.no)"
DOK = "https://data.norge.no/nb/technical/api/search"
API = "https://search.api.fellesdatakatalog.digdir.no"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"


def post_json(url: str, body: dict, timeout: int = 60):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "User-Agent": BRUKERAGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def sok(sokeord: str, antall: int = 5) -> list[dict]:
    body = {"query": sokeord, "pagination": {"page": 0, "size": antall}}
    svarte = False
    siste_feil: Exception | None = None
    for endepunkt in (f"{API}/search", f"{API}/search/datasets"):
        try:
            data = post_json(endepunkt, body)
        except Exception as e:
            siste_feil = e
            continue
        svarte = True
        treff = data.get("hits") or data.get("searchHits") or []
        if treff:
            return treff
    # Skill «kilden svarte feil» fra «vi nådde aldri kilden»: uten dette blir en
    # blokkert proxy eller nede nett rapportert som en API-endring, og du leter i
    # dokumentasjonen etter noe som aldri har flyttet seg.
    if not svarte:
        raise ValueError(f"nådde ikke søkeendepunktene på {API}: {siste_feil}") from siste_feil
    raise ValueError("ingen av søkeendepunktene ga treff — sjekk API-dokumentasjonen")


def tittel(hit: dict) -> str:
    t = hit.get("title") or {}
    if isinstance(t, dict):
        return t.get("nb") or t.get("no") or t.get("en") or next(iter(t.values()), "?")
    return str(t)


def smoke() -> str:
    treff = sok("kultur", 3)
    return f"{len(treff)} katalogtreff på «kultur»; første: {tittel(treff[0])}"


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Søker etter «kultur» i katalogen …")
    for hit in sok("kultur", 5):
        print(f"  {tittel(hit)}")
    print(f"✓ {smoke()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
