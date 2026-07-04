"""Kudos — kunnskapsdokumenter i offentlig sektor (DFØ).

Evalueringer, utredninger, årsrapporter, tildelingsbrev, NOU-er og
proposisjoner fra hele forvaltningen, samlet av DFØ og Nasjonalbiblioteket.
For alle som analyserer offentlig sektor er dette selve gullkammeret:
~44 000 dokumenter (juli 2026) med strukturert metadata.

Kjøring:  python3 api-atlas/eksempler/hent_kudos.py
Nøkkel:   ingen
Lisens:   åpne data — oppgi «Kilde: Kudos (DFØ)»
Dok:      https://kudos.dfo.no/apne-data (og API-roten /api svarer med
          versjon og dok-peker)

Endepunkt (verifisert med live-test 2026-07-04):
  GET https://kudos.dfo.no/api/v0/documents?page=<n>
      Laravel-paginert: {"meta": {current_page, last_page, per_page,
      total}, "data": [{uuid, type, title, ...}]}. 50 per side.
      NB: «query» som parameter gir 422 — søkesyntaksen er ikke
      kartlagt ennå; hent heller alt og filtrer lokalt (44k dokumenter
      = ~880 kall = en kaffekopp), eller sjekk /apne-data for
      bulk-nedlasting av hele basen.

Gull å grave i:
  - Alle evalueringer på kulturfeltet siden 2005 — hvem evalueres,
    av hvem, og hva skjer etterpå?
  - Tildelingsbrevene som tidsserie: hvordan endres styringssignalene
    til kulturvirksomhetene år for år?
  - Dokumentproduksjon per virksomhet — hvem skriver mest, om hva?
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

KILDE = "Kudos (DFØ)"
DOK = "https://kudos.dfo.no/apne-data"
API = "https://kudos.dfo.no/api/v0/documents"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"
PAUSE = 0.3


def hent_json(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": BRUKERAGENT})
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def hent_side(side: int = 1) -> dict:
    """Én side med dokumenter: {"meta": {...}, "data": [...]}."""
    return hent_json(f"{API}?{urllib.parse.urlencode({'page': side})}")


def hent_alle(maks_sider: int | None = None):
    """Generator over alle dokumenter, side for side, med høflig pause.

    Full høsting (~880 sider) tar noen minutter — snapshot resultatet
    til fil og filtrer lokalt i stedet for å spørre API-et på nytt.
    """
    side = 1
    while True:
        svar = hent_side(side)
        yield from svar.get("data", [])
        meta = svar.get("meta", {})
        if side >= meta.get("last_page", side) or (maks_sider and side >= maks_sider):
            return
        side += 1
        time.sleep(PAUSE)


def smoke() -> str:
    svar = hent_side(1)
    meta, dokumenter = svar.get("meta", {}), svar.get("data", [])
    total = meta.get("total", 0)
    if total < 10_000 or not dokumenter:
        raise ValueError(f"bare {total} dokumenter — har API-et endret seg?")
    d = dokumenter[0]
    return (f"{total:,} dokumenter i basen; første på side 1: "
            f"{d.get('type', '?')}: {str(d.get('title', '?'))[:60]}").replace(",", " ")


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Henter side 1 av dokumentbasen …")
    print(f"✓ {smoke()}")
    print("Dokumenttyper på første side:")
    for d in hent_side(1).get("data", [])[:8]:
        print(f"  {d.get('type', '?'):<25} {str(d.get('title', ''))[:55]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
