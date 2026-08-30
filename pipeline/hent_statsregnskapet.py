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

# Kolonnene vi faktisk bruker. Alt annet i filene ignoreres — regnskapsfila har 28
# kolonner, mer enn analysen trenger, og en smal nøkkel gjør aggregatet lite nok
# til å sjekkes med øyet.
#
# DE TO DATASETTENE HAR ULIK FORM, og det er ikke en tilfeldighet man kan
# normalisere bort: bevilgningsfila har ingen virksomhetsdimensjon, fordi
# Stortinget bevilger til kapittel og post — ikke til etater. Beløpskolonnen
# heter dessuten «Bevilgning_beløp» der, ikke «Beløp».
#
# Konsekvensen for akt 3 er at koblingen orgnr → kapittel MÅ komme fra
# regnskapet, mens utfallet måles på bevilgningen. Begge settene trengs.
SETT = {
    "statsregnskapet": {
        "zip": "statsregnskapet_full_historikk.zip",
        "kolonnefil": "statsregnskapet_beskrivelse_av_kolonner.csv",
        "utfil": "statsregnskapet_aarlig.json",
        "hva": "kontantregnskapet — hva som faktisk ble brukt",
        # Kontoklasse er med i nøkkelen, ikke fordi analysen grupperer på den,
        # men fordi den MÅ kunne filtreres på. Summerer man utgifter og
        # inntekter i én bunke, netter de hverandre ut: hele kontantregnskapet
        # 2014–2026 kom ut på 10,1 mrd, som er tre størrelsesordener for lite
        # for én måned, langt mindre tretten år.
        "nokler": ["År", "Kapittel_id", "Kapittel", "Post_id", "Post",
                   "Kontoklasse", "Fagdepartement", "Virksomhet_id",
                   "Virksomhet"],
        "belop": "Beløp",
        # Kolonner vi vil se fordelingen av før vi velger filter. Uten dette
        # gjetter man på hvilken verdi som betyr «utgift».
        "fordel_paa": ["Kontoklasse"],
    },
    "bevilgninger": {
        "zip": "bevilgninger_full_historikk.zip",
        "kolonnefil": "bevilgninger_beskrivelse_av_kolonner.csv",
        "utfil": "bevilgninger_aarlig.json",
        "hva": "bevilgningene — hva Stortinget vedtok",
        # Ingen Virksomhet_id her. Verifisert mot kildens egen
        # kolonnebeskrivelse 2026-08-30: 18 kolonner, ingen av dem om
        # virksomhet.
        "nokler": ["År", "Kapittel_id", "Kapittel", "Post_id", "Post",
                   "Post_type", "Fagdepartement"],
        "belop": "Bevilgning_beløp",
        # Tildelings_periode og Bevilgning er med i diagnosen fordi de ser ut
        # til å skille mellom typer bevilgningsvedtak. Summen fordelt på dem
        # avgjør om fila inneholder nivåer, endringer, eller begge om
        # hverandre — og det er forskjellen på et brukbart og et ubrukelig
        # utfallsmål.
        "fordel_paa": ["Post_type", "Tildelings_periode", "Bevilgning"],
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


def dokumenterte_kolonner(kolonnefil: str) -> list[tuple[str, str]]:
    """Kolonnenavn OG beskrivelse, slik DFØ selv dokumenterer dem.

    Beskrivelsen ble lenge ignorert, og det var en feil: uten den gjettet vi på
    hva «Bevilgning_beløp» og «Post_type» betyr, og gjetningen ga et
    aggregat der overføringer kom ut som minus fire tusen milliarder. Kilden
    dokumenterer sine egne kolonner — da skal vi lese dokumentasjonen framfor å
    tolke tallene baklengs.
    """
    tekst = hent_tekst(kolonnefil)
    rader = list(csv.reader(io.StringIO(tekst), delimiter=";"))
    ut = []
    for rad in rader[1:]:
        if rad and rad[0].strip():
            ut.append((rad[0].strip(),
                       " ".join(c.strip() for c in rad[1:] if c.strip())))
    return ut


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


def aggreger(zipsti: Path, dokumentert: list[str], nokler: list[str],
             belopskolonne: str,
             fordel_paa: list[str] | None = None) -> tuple[list[dict], dict]:
    """Strømmer CSV-en i zipen og summerer beløpet per nøkkel.

    `fordel_paa` navngir kolonner vi i tillegg vil se summen fordelt på. Det er
    ikke pynt: et totaltall som er nettet ut mellom utgift og inntekt ser
    fullstendig troverdig ut helt til man bryter det ned.
    """
    fordel_paa = fordel_paa or []
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
                mangler = [k for k in nokler + [belopskolonne] if k not in kolonner]
                if mangler:
                    raise SystemExit(
                        f"FEIL: {kilde} mangler kolonnene {mangler}.\n"
                        f"  Fant: {kolonner}\n"
                        f"Har formatet endret seg? Se {KILDE_URL}"
                    )

            sum_per: dict[tuple, float] = collections.defaultdict(float)
            rader_lest = 0
            aar = collections.Counter()
            # Summen per verdi i klassekolonnene. Dette er diagnosen som
            # avslører at et totaltall er nettet ut — se merknaden i SETT.
            fordeling: dict[str, dict[str, list]] = {
                k: collections.defaultdict(lambda: [0, 0.0]) for k in fordel_paa
            }
            for rad in leser:
                rader_lest += 1
                nokkel = tuple((rad.get(k) or "").strip() for k in nokler)
                belop = tall(rad.get(belopskolonne, ""))
                sum_per[nokkel] += belop
                aar[nokkel[0]] += 1
                for kol in fordel_paa:
                    post = fordeling[kol][(rad.get(kol) or "").strip() or "(tom)"]
                    post[0] += 1
                    post[1] += belop

    if rader_lest == 0:
        raise SystemExit(f"FEIL: {zipsti.name} inneholdt ingen rader.")

    aggregat = [
        {**dict(zip(nokler, nokkel)), "belop": round(belop, 2)}
        for nokkel, belop in sorted(sum_per.items())
    ]
    return aggregat, {
        "rader_lest": rader_lest,
        "aar": dict(sorted(aar.items())),
        "fordeling": {kol: {v: {"rader": n, "sum": round(b, 2)}
                            for v, (n, b) in sorted(d.items())}
                      for kol, d in fordeling.items()},
    }


# ---------------------------------------------------------------- main

def kjor_sett(navn: str, behold_zip: bool) -> None:
    konf = SETT[navn]
    print(f"\n{navn} — {konf['hva']}")
    print(f"  Leser kolonnebeskrivelsen ({konf['kolonnefil']}) …")
    dokumentert_par = dokumenterte_kolonner(konf["kolonnefil"])
    dokumentert = [navn for navn, _ in dokumentert_par]
    print(f"    {len(dokumentert)} dokumenterte kolonner:")
    for navn, forklaring in dokumentert_par:
        merke = " ←" if navn in set(konf["nokler"]) | {konf["belop"]} else "  "
        print(f"     {merke} {navn:<28} {forklaring[:88]}")

    zipsti = RAADATA_DIR / konf["zip"]
    if zipsti.exists():
        print(f"  {zipsti.name} finnes allerede ({zipsti.stat().st_size / 1e6:.0f} MB) — gjenbruker")
    else:
        print(f"  Laster ned {konf['zip']} …")
        last_ned(konf["zip"], zipsti)

    print("  Aggregerer (strømmer CSV-en, holder ikke hele i minnet) …")
    aggregat, kontroll = aggreger(zipsti, dokumentert, konf["nokler"],
                                  konf["belop"], konf.get("fordel_paa"))

    utfil = RAADATA_DIR / konf["utfil"]
    utfil.write_text(json.dumps({
        "kilde": KILDE,
        "kilde_url": KILDE_URL,
        "dato_hentet": date.today().isoformat(),
        "datasett": navn,
        "aggregeringsnokkel": konf["nokler"],
        "belopskolonne": konf["belop"],
        "merknad": ("Summert per år, ikke per måned. Et budsjett beveger seg når "
                    "Stortinget vedtar det, ikke mellom månedene — «24 måneder etter» "
                    "er i praksis «de to budsjettårene etter»."),
        "kontroll": kontroll,
        "rader": aggregat,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"  ✓ {kontroll['rader_lest']} rader → {len(aggregat)} aggregerte linjer")
    print(f"    år i datasettet: {', '.join(sorted(k for k in kontroll['aar'] if k))}")
    print(f"    sum totalt: {sum(r['belop'] for r in aggregat) / 1e9:.1f} mrd kr")
    for kol, verdier in (kontroll.get("fordeling") or {}).items():
        print(f"    fordelt på {kol} — dette avgjør hva som må filtreres bort:")
        for verdi, tallene in sorted(verdier.items(),
                                     key=lambda kv: -abs(kv[1]["sum"])):
            print(f"      {verdi[:34]:<34} {tallene['sum'] / 1e9:>12.1f} mrd "
                  f"({tallene['rader']} rader)")
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
