"""tilskudd.no — Lotteri- og stiftelsestilsynet.

Alle statlige tildelinger til frivillige organisasjoner, samlet på ett
sted: hvem søkte, hvem fikk, hvor mye, fra hvilken ordning og hvilket
departement. Grunnfjellet under Tilskuddskompasset.

Kjøring:  python3 api-atlas/eksempler/hent_tilskudd_lottstift.py
Nøkkel:   ingen
Lisens:   åpne data — oppgi «Kilde: tilskudd.no (Lottstift)»
Dok:      https://tilskudd.lottstift.no (ingen formell API-dok — endepunktet
          under er det nettsiden selv bruker, og har vært stabilt siden 2021)

Endepunkt:
  GET /api/download/allocation-to-volunteers?year=<budsjettår>
      Excel-fil med alle tildelinger for ett budsjettår. Arkene heter
      «Tilskuddsordninger» og «Enkeltstående tilskudd».

Full pipeline med parsing, normalisering og statistikk finnes i
tilskuddskompasset/hent_bulk_tildelinger.py (krever requests + openpyxl).
Dette scriptet sjekker bare at endepunktet lever og leverer gyldig fil,
uten å laste ned alt.

Gull å grave i:
  - Innvilgelsesgrad per ordning over tid (gjøres alt i Tilskuddskompasset)
  - Geografisk skjevfordeling: tilskuddskroner per innbygger per fylke
    (koblet mot SSB-befolkning)
  - Organisasjoner som lever av én enkelt ordning — sårbarhetsanalyse
"""

from __future__ import annotations

import sys
import urllib.parse
import urllib.request

KILDE = "tilskudd.no (Lottstift)"
DOK = "https://tilskudd.lottstift.no"
API = "https://tilskudd.lottstift.no/api/download/allocation-to-volunteers"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"


def sjekk_aar(aar: int) -> tuple[str, int]:
    """Åpner nedlastingen for ett år og leser bare starten av filen.

    Returnerer (content-type, antall bytes lest). Excel-filer (xlsx) er
    zip-arkiver og starter alltid med magibytene «PK».
    """
    url = f"{API}?{urllib.parse.urlencode({'year': aar})}"
    req = urllib.request.Request(url, headers={"User-Agent": BRUKERAGENT})
    with urllib.request.urlopen(req, timeout=120) as svar:
        start = svar.read(4)
        ctype = svar.headers.get("Content-Type", "?")
    if not start.startswith(b"PK"):
        raise ValueError(
            f"svaret for {aar} er ikke en Excel-fil (starter med {start!r}) — "
            "har endepunktet endret format?"
        )
    return ctype, len(start)


def smoke() -> str:
    ctype, _ = sjekk_aar(2024)
    return f"budsjettår 2024 leverer gyldig Excel-fil ({ctype})"


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Sjekker at bulk-nedlastingen svarer (leser bare filstarten) …")
    print(f"✓ {smoke()}")
    print("Full nedlasting og parsing: tilskuddskompasset/hent_bulk_tildelinger.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
