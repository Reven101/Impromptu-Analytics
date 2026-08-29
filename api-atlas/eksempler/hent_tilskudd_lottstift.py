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
      Svarer (per juli 2026) med 307 til
      tilskudd-service.lottstift.no/file/download/<uuid>, som leverer
      Excel-filen for budsjettåret. Peker-URL-en ligger også som ren
      tekst i svarkroppen. Arkene heter «Tilskuddsordninger» og
      «Enkeltstående tilskudd». NB: filen har ødelagte dimensjoner —
      openpyxl i read_only-modus trenger ws.reset_dimensions().
      NB2: nedlastingen svarer med Content-Type «application/json», men
      kroppen er en xlsx. Stol på PK-signaturen, ikke på headeren.

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
    zip-arkiver og starter alltid med magibytene «PK». Endepunktet svarer
    med en peker (307 og/eller URL i kroppen) til selve filen; urllib
    følger redirecten selv, men en peker i kroppen følges her eksplisitt.
    """
    url = f"{API}?{urllib.parse.urlencode({'year': aar})}"
    for hopp in range(2):
        req = urllib.request.Request(url, headers={"User-Agent": BRUKERAGENT})
        with urllib.request.urlopen(req, timeout=120) as svar:
            start = svar.read(256)
            ctype = svar.headers.get("Content-Type", "?")
        if start.startswith(b"PK"):
            return ctype, len(start)
        peker = start.decode("utf-8", "replace").strip()
        if hopp == 0 and peker.startswith("https://tilskudd-service.lottstift.no/"):
            url = peker
            continue
        raise ValueError(
            f"svaret for {aar} er verken Excel-fil eller kjent peker "
            f"(starter med {start[:40]!r}) — har endepunktet endret format?"
        )
    raise AssertionError("uoppnåelig")


# Nyeste år først. Inneværende budsjettår finnes ikke før det er publisert,
# så testen faller bakover framfor å låse seg til ett år som blir stående og
# svare grønt lenge etter at de nye har sluttet å virke.
AAR_A_PROVE = (2026, 2025, 2024)


def smoke() -> str:
    feil = []
    siste_unntak: Exception | None = None
    for aar in AAR_A_PROVE:
        try:
            ctype, _ = sjekk_aar(aar)
        except Exception as e:
            feil.append(f"{aar}: {e}")
            siste_unntak = e
            continue
        # Serveren merker xlsx-fila som application/json. Det er dens feil,
        # ikke vår, og PK-signaturen er det som faktisk er verifisert — så
        # si det, framfor å vise fram en content-type som ser gal ut.
        riktig_merket = "spreadsheet" in ctype or "excel" in ctype
        merknad = "" if riktig_merket else f"; serveren merker den feil som {ctype}"
        return f"budsjettår {aar}: gyldig xlsx, PK-signatur bekreftet{merknad}"
    raise ValueError(
        "ingen av budsjettårene ga en gyldig fil: " + "; ".join(feil)
    ) from siste_unntak


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Sjekker at bulk-nedlastingen svarer (leser bare filstarten) …")
    print(f"✓ {smoke()}")
    print("Full nedlasting og parsing: tilskuddskompasset/hent_bulk_tildelinger.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
