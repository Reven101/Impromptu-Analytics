"""Henter statsregnskapet og bevilgningene (DFØ) og aggregerer dem til årstall per kapittel.

Kjøring (krever nett mot statsregnskapet.dfo.no):

    python pipeline/hent_statsregnskapet.py                 # begge datasettene
    python pipeline/hent_statsregnskapet.py --sett bevilgninger
    python pipeline/hent_statsregnskapet.py --behold-zip    # ikke slett nedlastingen

Datasettene er hele statens kontantregnskap (2014–) og bevilgningene som ligger bak.
De kobles mot Kudos gjennom `Virksomhet_id`, som er organisasjonsnummeret — samme
nøkkel Kudos oppgir som `actor_org_number`. Det er den koblingen akt 3 i historien
hviler på.

Fire ting scriptet gjør med vilje:

- **Det aggregerer mens det leser, og holder aldri hele CSV-en i minnet.** Filene er
  på hundrevis av megabyte, og vi trenger bare summen per (år, kapittel, post,
  virksomhet). Zipen slettes etterpå med mindre --behold-zip er satt.
- **Det verifiserer kolonnene to steder.** Først mot DFØs egen kolonnebeskrivelse,
  så mot den faktiske headeren i CSV-en. Stemmer ikke navnene, stopper vi og skriver
  ut headeren vi faktisk fikk — det er den eneste måten å oppdage at nedlastingen
  har byttet format.
- **Formatet er en felle i seg selv:** semikolonseparert, cp1252-kodet, og norsk
  desimalkomma i Beløp, med tusenskille som kan være vanlig mellomrom eller hardt
  mellomrom. Leses det som UTF-8 og punktum-desimal, blir hver eneste sum feil.
- **Årstall, ikke måneder.** Kildene har `Periode` som ÅÅÅÅMM, men et budsjett
  beveger seg ikke mellom månedene — det beveger seg når Stortinget vedtar det.
  «24 måneder etter» er derfor i praksis «de to budsjettårene etter», og
  aggregeringen sier det rett ut framfor å late som oppløsningen er finere.

Rådata skrives UTENFOR repoet (jf. SIKKERHET.md / .gitignore): sett STATSREGNSKAP_DIR,
ellers brukes ../impromptu_raadata/statsregnskapet/ ved siden av repoet.
"""

from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import os
import re
import urllib.error
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

import kontrakt  # noqa: F401  -- setter utf-8 på stdout/stderr (Windows-konsollen er cp1252)

KILDE = "statsregnskapet.no (DFØ)"
KILDE_URL = "https://statsregnskapet.dfo.no/last-ned"
NEDLASTING = "https://statsregnskapet.dfo.no/nedlasting"
BRUKERAGENT = "Impromptu-Analytics/1.0 (kontakt@impromptu.no)"

RAADATA_DIR = Path(
    os.environ.get("STATSREGNSKAP_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "statsregnskapet"
)

# Kolonnene vi faktisk bruker. Alt annet i filene ignoreres — 28 kolonner er mer enn
# analysen trenger, og en smal nøkkel gjør aggregatet lite nok til å sjekkes med øyet.
NOKKELKOLONNER = ["År", "Kapittel_id", "Kapittel", "Post_id", "Post",
                  "Fagdepartement", "Virksomhet_id", "Virksomhet"]
BELOPSKOLONNE = "Beløp"

SETT = {
    "statsregnskapet": {
        "zip": "statsregnskapet_full_historikk.zip",
        "kolonnefil": "statsregnskapet_beskrivelse_av_kolonner.csv",
        "utfil": "statsregnskapet_aarlig.json",
        "hva": "kontantregnskapet — hva som faktisk ble brukt",
    },
    "bevilgninger": {
        "zip": "bevilgninger_full_historikk.zip",
        "kolonnefil": "bevilgninger_beskrivelse_av_kolonner.csv",
        "utfil": "bevilgninger_aarlig.json",
        "hva": "bevilgningene — hva Stortinget vedtok",
    },
}


# ---------------------------------------------------------------- nedlasting

def last_ned(sti: str, mal: Path) -> Path:
    """Strømmer en fil til disk i biter. Returnerer stien."""
    url = f"{NEDLASTING}/{sti}"
    mal.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": BRUKERAGENT})
    try:
        with urllib.request.urlopen(req, timeout=600) as svar, mal.open("wb") as ut:
            lest = 0
            while True:
                bit = svar.read(1 << 20)
                if not bit:
                    break
                ut.write(bit)
                lest += len(bit)
                if lest % (32 << 20) < (1 << 20):
                    print(f"    … {lest / 1e6:.0f} MB")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SystemExit(
            f"FEIL: klarte ikke laste ned {url}\n  {type(e).__name__}: {e}\n"
            f"Sjekk at nedlastingssiden fortsatt tilbyr fila: {KILDE_URL}"
        ) from e
    print(f"    {mal.name}: {mal.stat().st_size / 1e6:.0f} MB")
    return mal


def hent_tekst(sti: str) -> str:
    req = urllib.request.Request(f"{NEDLASTING}/{sti}", headers={"User-Agent": BRUKERAGENT})
    with urllib.request.urlopen(req, timeout=120) as svar:
        return svar.read().decode("cp1252")


def dokumenterte_kolonner(kolonnefil: str) -> list[str]:
    """Kolonnenavnene slik DFØ selv dokumenterer dem."""
    tekst = hent_tekst(kolonnefil)
    rader = list(csv.reader(io.StringIO(tekst), delimiter=";"))
    return [rad[0].strip() for rad in rader[1:] if rad and rad[0].strip()]


# ---------------------------------------------------------------- parsing

def tall(rå: str) -> float:
    """Norsk tallformat → float. Tusenskille kan være vanlig eller hardt mellomrom,
    og desimalskillet er komma. «1 234,50» → 1234.5. Tom streng → 0."""
    t = (rå or "").strip()
    if not t:
        return 0.0
    # Tusenskillet er mellomrom, men *hvilket* mellomrom varierer: vanlig, hardt
    # (U+00A0), smalt hardt (U+202F) og smalt (U+2009) er alle observert i norske
    # eksporter. \s i Python er unicode-bevisst og tar dem alle — en håndskrevet
    # liste over tegn glipper på det femte.
    t = re.sub(r"[\s']", "", t)
    t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError as e:
        raise SystemExit(
            f"FEIL: klarte ikke lese «{rå}» som beløp. Har tallformatet i "
            f"statsregnskapet endret seg? Se {KILDE_URL}"
        ) from e


def aggreger(zipsti: Path, dokumentert: list[str]) -> tuple[list[dict], dict]:
    """Strømmer CSV-en i zipen og summerer Beløp per (år, kapittel, post, virksomhet)."""
    with zipfile.ZipFile(zipsti) as z:
        csv_navn = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if len(csv_navn) != 1:
            raise SystemExit(
                f"FEIL: ventet nøyaktig én CSV i {zipsti.name}, fant {csv_navn}. "
                "Har nedlastingen endret innhold?"
            )
        with z.open(csv_navn[0]) as rå:
            strom = io.TextIOWrapper(rå, encoding="cp1252", newline="")
            leser = csv.DictReader(strom, delimiter=";")
            header = [(f or "").strip() for f in (leser.fieldnames or [])]

            # To uavhengige kontroller: dokumentasjonen og den faktiske headeren.
            # Uten den siste oppdager vi ikke at fila har byttet format før tallene
            # allerede er summert feil.
            for kilde, kolonner in (("kolonnebeskrivelsen", dokumentert), ("CSV-headeren", header)):
                mangler = [k for k in NOKKELKOLONNER + [BELOPSKOLONNE] if k not in kolonner]
                if mangler:
                    raise SystemExit(
                        f"FEIL: {kilde} mangler kolonnene {mangler}.\n"
                        f"  Fant: {kolonner}\n"
                        f"Har formatet endret seg? Se {KILDE_URL}"
                    )

            sum_per: dict[tuple, float] = collections.defaultdict(float)
            rader_lest = 0
            aar = collections.Counter()
            for rad in leser:
                rader_lest += 1
                nokkel = tuple((rad.get(k) or "").strip() for k in NOKKELKOLONNER)
                sum_per[nokkel] += tall(rad.get(BELOPSKOLONNE, ""))
                aar[nokkel[0]] += 1

    if rader_lest == 0:
        raise SystemExit(f"FEIL: {zipsti.name} inneholdt ingen rader.")

    aggregat = [
        {**dict(zip(NOKKELKOLONNER, nokkel)), "belop": round(belop, 2)}
        for nokkel, belop in sorted(sum_per.items())
    ]
    return aggregat, {"rader_lest": rader_lest, "aar": dict(sorted(aar.items()))}


# ---------------------------------------------------------------- main

def kjor_sett(navn: str, behold_zip: bool) -> None:
    konf = SETT[navn]
    print(f"\n{navn} — {konf['hva']}")
    print(f"  Leser kolonnebeskrivelsen ({konf['kolonnefil']}) …")
    dokumentert = dokumenterte_kolonner(konf["kolonnefil"])
    print(f"    {len(dokumentert)} dokumenterte kolonner")

    zipsti = RAADATA_DIR / konf["zip"]
    if zipsti.exists():
        print(f"  {zipsti.name} finnes allerede ({zipsti.stat().st_size / 1e6:.0f} MB) — gjenbruker")
    else:
        print(f"  Laster ned {konf['zip']} …")
        last_ned(konf["zip"], zipsti)

    print("  Aggregerer (strømmer CSV-en, holder ikke hele i minnet) …")
    aggregat, kontroll = aggreger(zipsti, dokumentert)

    utfil = RAADATA_DIR / konf["utfil"]
    utfil.write_text(json.dumps({
        "kilde": KILDE,
        "kilde_url": KILDE_URL,
        "dato_hentet": date.today().isoformat(),
        "datasett": navn,
        "aggregeringsnokkel": NOKKELKOLONNER,
        "merknad": ("Summert per år, ikke per måned. Et budsjett beveger seg når "
                    "Stortinget vedtar det, ikke mellom månedene — «24 måneder etter» "
                    "er i praksis «de to budsjettårene etter»."),
        "kontroll": kontroll,
        "rader": aggregat,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"  ✓ {kontroll['rader_lest']} rader → {len(aggregat)} aggregerte linjer")
    print(f"    år i datasettet: {', '.join(sorted(k for k in kontroll['aar'] if k))}")
    print(f"    sum totalt: {sum(r['belop'] for r in aggregat) / 1e9:.1f} mrd kr")
    print(f"    skrev {utfil}")

    if not behold_zip:
        zipsti.unlink()
        print(f"    slettet {zipsti.name} (bruk --behold-zip for å la den ligge)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sett", choices=sorted(SETT), action="append",
                    help="hvilket datasett (kan gjentas; standard: begge)")
    ap.add_argument("--behold-zip", action="store_true",
                    help="ikke slett den nedlastede zipen etter aggregering")
    args = ap.parse_args()

    print(f"{KILDE} — {KILDE_URL}")
    RAADATA_DIR.mkdir(parents=True, exist_ok=True)
    for navn in (args.sett or sorted(SETT)):
        kjor_sett(navn, args.behold_zip)

    print("\nRådata ligger utenfor repoet — de skal ikke sjekkes inn (SIKKERHET.md).")
    print("Neste steg: python pipeline/analyser_budsjettspor.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
