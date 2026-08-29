"""Kudos — kunnskapsdokumenter i offentlig sektor (DFØ).

Evalueringer, utredninger, årsrapporter, tildelingsbrev, NOU-er og
proposisjoner fra hele forvaltningen, samlet av DFØ og Nasjonalbiblioteket.
For alle som analyserer offentlig sektor er dette selve gullkammeret:
~44 000 dokumenter (juli 2026), derav ~7 000 evalueringer, med
strukturert metadata.

Kjøring:  python3 api-atlas/eksempler/hent_kudos.py
Nøkkel:   ingen
Lisens:   åpne data — oppgi «Kilde: Kudos (DFØ)»
Dok:      https://kudos.dfo.no/apne-data (API-roten /api oppgir versjon)

Endepunkt (verifisert med live-test 2026-07-04):
  GET https://kudos.dfo.no/api/v0/documents
      Laravel-paginert: {"meta": {current_page, last_page, per_page,
      total}, "data": [{uuid, type, title, ...}]}.

  Ingen fritekst-søk i v0, men strukturerte filtre (listen kom fra
  API-ets egen 422-feilmelding — send en ugyldig parameter, så røper
  «allowed_parameters» fasiten):
      type                    f.eks. Evaluering, Årsrapport, Tildelingsbrev
      actor_name              virksomhetsnavn
      actor_org_number        org.nr — kobler rett mot Brreg/tilskudd.no!
      actor_role              virksomhetens rolle i dokumentet
      published_year_from/to  publiseringsår
      concerned_year_from/to  året dokumentet gjelder
      sort, page, per_page    per_page har tak på 50 (verifisert 2026-08-29)

Gull å grave i:
  - Alle evalueringer på kulturfeltet: type=Evaluering + actor_org_number
    fra Brreg-oppslag av kultursektorens virksomheter
  - Tildelingsbrevene som tidsserie: styringssignalene til kultur-
    virksomhetene, år for år
  - Kryss med tilskuddsdata: får virksomheter som evalueres oftere,
    mer eller mindre penger etterpå?
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


def hent_side(side: int = 1, **filtre) -> dict:
    """Én side dokumenter. Filtre: type, actor_name, actor_org_number,
    actor_role, published_year_from/to, concerned_year_from/to, sort,
    per_page. Ukjente parametre gir 422 med gyldig-liste i feilkroppen."""
    params = {"page": side, **filtre}
    return hent_json(f"{API}?{urllib.parse.urlencode(params)}")


def hent_alle(maks_sider: int | None = None, **filtre):
    """Generator over alle dokumenter som treffer filtrene, med pause.

    Uten filtre er basen ~880 sider — snapshot resultatet til fil og
    analyser lokalt i stedet for å spørre API-et på nytt.
    """
    side = 1
    while True:
        svar = hent_side(side, **filtre)
        yield from svar.get("data", [])
        meta = svar.get("meta", {})
        if side >= meta.get("last_page", side) or (maks_sider and side >= maks_sider):
            return
        side += 1
        time.sleep(PAUSE)


def smoke() -> str:
    alt = hent_side(1).get("meta", {}).get("total", 0)
    evalueringer = hent_side(1, type="Evaluering").get("meta", {}).get("total", 0)
    if alt < 10_000 or evalueringer < 1_000:
        raise ValueError(
            f"{alt} dokumenter / {evalueringer} evalueringer — har API-et endret seg?"
        )
    return (f"{alt:,} dokumenter, {evalueringer:,} evalueringer".replace(",", " ")
            + " — type-filteret virker")


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print(f"✓ {smoke()}")
    print("Ferskeste evalueringer:")
    svar = hent_side(1, type="Evaluering", per_page=5,
                     published_year_from=2024)
    for d in svar.get("data", [])[:5]:
        print(f"  {str(d.get('title', '?'))[:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
