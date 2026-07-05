"""statsregnskapet.no — DFØ.

Hele statens kontantregnskap, måned for måned siden 2014: utgifter og
inntekter per departement, kapittel, post og virksomhet. Virksomhet_id
er organisasjonsnummer — direkte koblingsnøkkel mot Brreg, Kudos og
tilskudd.no.

Kjøring:  python3 api-atlas/eksempler/hent_statsregnskapet.py
Nøkkel:   ingen
Lisens:   NLOD — oppgi «Kilde: statsregnskapet.no (DFØ)»
Dok:      https://statsregnskapet.dfo.no/last-ned (ingen formell API-dok —
          nedlastings-URL-ene under er stabile og oppdateres månedlig,
          første virkedag etter rapporteringsfristen)

Endepunkter (alle under https://statsregnskapet.dfo.no/nedlasting/):
  statsregnskapet_aar_<år>.zip        kontantregnskapet per år, 2014–
  statsregnskapet_SRS_aar_<år>.zip    periodisert regnskap (SRS), 2016–
  statsregnskapet_siste_maaned.zip    nyeste måned alene
  statsregnskapet_hittil_i_aar.zip    inneværende år så langt
  statsregnskapet_full_historikk.zip  alt siden 2014
  bevilgninger_full_historikk.zip     bevilgningene (budsjettsiden)
  statsregnskapet_beskrivelse_av_kolonner.csv   kolonnedokumentasjon
  bevilgninger_beskrivelse_av_kolonner.csv

Hver zip inneholder én CSV: semikolonseparert, cp1252-kodet, norsk
desimalkomma i Beløp. 28 kolonner, bl.a. År, Periode (ÅÅÅÅMM),
Fagdepartement, Kapittel_id/Kapittel, Post_id/Post, Kontoklasse,
Artskonto, Virksomhet_id (orgnr!) og Beløp.

Gull å grave i:
  - Kulturbudsjettet kapittel for kapittel over tid (KUD-kapitlene) —
    bevilgning mot faktisk regnskap, år for år
  - Virksomhetenes pengestrøm koblet mot Kudos-dokumenter og
    tilskudd.no via orgnr: styring, evaluering og kroner i én graf
  - Departementenes utgiftsvekst siden 2014 — hvem eser, hvem krymper?
"""

from __future__ import annotations

import csv
import io
import sys
import urllib.request

KILDE = "statsregnskapet.no (DFØ)"
DOK = "https://statsregnskapet.dfo.no/last-ned"
NEDLASTING = "https://statsregnskapet.dfo.no/nedlasting"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"


def hent_bytes(sti: str, maks: int | None = None) -> bytes:
    req = urllib.request.Request(
        f"{NEDLASTING}/{sti}", headers={"User-Agent": BRUKERAGENT}
    )
    with urllib.request.urlopen(req, timeout=120) as svar:
        return svar.read(maks) if maks else svar.read()


def hent_kolonner() -> list[str]:
    """Leser kolonnedokumentasjonen (liten CSV) og returnerer kolonnenavnene."""
    tekst = hent_bytes("statsregnskapet_beskrivelse_av_kolonner.csv").decode("cp1252")
    rader = list(csv.reader(io.StringIO(tekst), delimiter=";"))
    return [rad[0] for rad in rader[1:] if rad]


def sjekk_zip(sti: str) -> None:
    """Leser bare starten av en zip og sjekker PK-magibytene."""
    start = hent_bytes(sti, maks=4)
    if not start.startswith(b"PK"):
        raise ValueError(
            f"{sti} er ikke en zip-fil (starter med {start!r}) — "
            "har nedlastingssiden endret seg?"
        )


def smoke() -> str:
    kolonner = hent_kolonner()
    for felt in ("Kapittel", "Virksomhet_id", "Beløp"):
        if felt not in kolonner:
            raise ValueError(f"kolonnen «{felt}» mangler i beskrivelsen: {kolonner}")
    sjekk_zip("statsregnskapet_siste_maaned.zip")
    return (
        f"kolonnebeskrivelsen lister {len(kolonner)} kolonner "
        "(bl.a. Kapittel, Virksomhet_id=orgnr, Beløp); siste måned er gyldig zip"
    )


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Sjekker kolonnedokumentasjonen og at månedsfilen svarer …")
    print(f"✓ {smoke()}")
    print(f"Årsfiler: {NEDLASTING}/statsregnskapet_aar_<år>.zip (2014–)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
