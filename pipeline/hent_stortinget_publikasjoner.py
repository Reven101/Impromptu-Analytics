"""Henter fulltekstene til stortingsdokumenter for de siste sesjonene.

Kjøring (krever nett mot data.stortinget.no):

    python pipeline/hent_stortinget_publikasjoner.py                # 10 sesjoner
    python pipeline/hent_stortinget_publikasjoner.py --sesjoner 3    # prøvekjøring
    python pipeline/hent_stortinget_publikasjoner.py --frisk         # ignorer lagret

Dette er søkeflaten for akt 2: for å telle at et stortingsdokument NAVNGIR en
bestemt evaluering, må vi ha teksten i dokumentene. Sondering (sonder_stortinget.py)
fastslo hvordan det lar seg gjøre, og de tre funnene former dette scriptet:

- **`publikasjoner` krever `publikasjontype`.** Uten den: HTTP 400. De gyldige
  verdiene står i PUBLIKASJONSTYPER under; de ble funnet ved å prøve, ikke ved
  å lese dokumentasjonen, som ikke lister dem.
- **`publikasjon` svarer XML**, uansett `format=json`. Det er det eneste
  endepunktet som gjør det, og det er der fulltekstene ligger.
- **`innstillingstekst` på saksnivå er ofte tomt** — det finnes bare når saken
  har fått innstilling. Derfor henter vi dokumentene, ikke saksfeltene.

Dekning: de N nyeste sesjonene. Det er et bevisst valg med en konsekvens som
MÅ stå i historien: en evaluering fra 2008 kan ikke telles som «aldri nevnt»
når vi ikke har lett i 2008-sesjonen. Nevneren i akt 2 begrenses derfor til
evalueringer publisert i årene denne hentingen dekker.

Rådata skrives UTENFOR repoet (jf. SIKKERHET.md): sett STORTINGET_DIR, ellers
../impromptu_raadata/stortinget/. Én .jsonl per sesjon, som det appendes til
underveis — en avbrutt kjøring fortsetter der den slapp.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import time
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import nett
import kontrakt  # noqa: F401  -- setter utf-8 på stdout/stderr (Windows-konsollen er cp1252)

API = "https://data.stortinget.no/eksport"
KILDE = "Stortinget (åpne data)"
KILDE_URL = "https://data.stortinget.no/dokumentasjon-og-hjelp/"
BRUKERAGENT = "Impromptu-Analytics/1.0 (kontakt@impromptu.no)"
PAUSE = 0.3

# Verifisert ved å prøve — API-ets 400 lister dem ikke. «innstillinger»,
# «sporretime» og «alle» gir HTTP 400 og er derfor ikke med.
PUBLIKASJONSTYPER = ("innstilling", "dok8", "referat", "lovvedtak",
                     "innberetning", "dok12")

STANDARD_SESJONER = 10

RAADATA_DIR = Path(
    os.environ.get("STORTINGET_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "stortinget"
)


# ---------------------------------------------------------------- tekst

def normaliser(tekst: str) -> str:
    """Teksten slik vi vil søke i den senere.

    Normaliseringen gjøres HER, ikke ved søketidspunktet, av to grunner: den
    halverer lagringen, og den garanterer at dokumenttekst og rapporttittel
    normaliseres likt — en match som feiler fordi den ene siden har « og den
    andre ", er den vondeste feilen å oppdage.
    """
    t = unicodedata.normalize("NFKC", tekst)
    t = t.replace("­", "")                      # myk bindestrek
    for hermetegn in ("«", "»", "”", "“", "„", "’", "‘", "'"):
        t = t.replace(hermetegn, '"')
    t = re.sub(r"[‐-―]", "-", t)           # alle bindestrekvariantene
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


def tekst_fra_xml(kropp: bytes) -> str:
    """All tekst i XML-dokumentet, uten tagger.

    ElementTree først, fordi den håndterer entiteter og CDATA riktig. Feiler
    parsingen — et avkuttet svar, en tag som ikke lukkes — faller vi tilbake på
    å strippe taggene med regex. Halv tekst er bedre enn ingen tekst her: vi
    leter etter navngivinger, og et dokument vi ikke får parset er et dokument
    vi ellers ville telt som «nevnte den ikke».
    """
    try:
        rot = ET.fromstring(kropp.decode("utf-8", errors="replace"))
        return " ".join(rot.itertext())
    except ET.ParseError:
        rå = kropp.decode("utf-8", errors="replace")
        return html.unescape(re.sub(r"<[^>]+>", " ", rå))


# ---------------------------------------------------------------- API

def hent(sti: str, **params) -> bytes:
    url = f"{API}/{sti}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return nett.hent_bytes(url, BRUKERAGENT)


def hent_json(sti: str, **params) -> dict:
    return json.loads(hent(sti, **params).decode("utf-8"))


def forste_liste(data) -> list:
    """Stortinget pakker lister i «*_liste»-nøkler."""
    if not isinstance(data, dict):
        return []
    for nokkel, verdi in data.items():
        if nokkel.endswith("_liste") and isinstance(verdi, list):
            return verdi
    return []


def sesjoner(antall: int) -> list[str]:
    """De N nyeste sesjonene som faktisk har begynt.

    Registeret lister sesjoner fram i tid — i august 2026 står 2028-2029 der,
    tom. Vi tar derfor fra og med den inneværende og bakover.
    """
    try:
        data = hent_json("sesjoner", format="json")
    except (nett.NettFeil, nett.HttpFeil) as e:
        raise SystemExit(f"FEIL: fikk ikke sesjonsregisteret: {e}") from e
    liste = forste_liste(data)
    ider = [s.get("id") for s in liste if isinstance(s, dict) and s.get("id")]

    rå = data.get("innevaerende_sesjon")
    nå = rå.get("id") if isinstance(rå, dict) else rå if isinstance(rå, str) else None
    if nå in ider:
        ider = ider[ider.index(nå):]
    return ider[:antall]


# ---------------------------------------------------------------- lagring

def sesjonsfil(sesjon: str) -> Path:
    return RAADATA_DIR / f"publikasjoner_{sesjon}.jsonl"


def alt_hentet(sesjon: str) -> set[str]:
    """Id-ene som allerede ligger i sesjonsfila.

    Siste linje kan være halvskrevet hvis kjøringen ble drept midt i en append.
    Den hoppes over — dokumentet hentes da på nytt, som er riktig.
    """
    fil = sesjonsfil(sesjon)
    if not fil.exists():
        return set()
    hentet = set()
    with fil.open(encoding="utf-8") as f:
        for linje in f:
            linje = linje.strip()
            if not linje:
                continue
            try:
                hentet.add(json.loads(linje)["id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return hentet


def legg_til(sesjon: str, rad: dict) -> None:
    RAADATA_DIR.mkdir(parents=True, exist_ok=True)
    with sesjonsfil(sesjon).open("a", encoding="utf-8") as f:
        f.write(json.dumps(rad, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- henting

def hent_sesjon(sesjon: str, bruk_sjekkpunkt: bool) -> dict:
    """Alle publikasjoner i én sesjon, med fulltekst. Returnerer kontrolltall."""
    hentet = alt_hentet(sesjon) if bruk_sjekkpunkt else set()
    if hentet:
        print(f"  {len(hentet)} dokumenter ligger allerede lagret", flush=True)

    ønsket: list[tuple[str, str, str]] = []      # (id, type, tittel)
    for ptype in PUBLIKASJONSTYPER:
        time.sleep(PAUSE)
        try:
            data = hent_json("publikasjoner", publikasjontype=ptype,
                             sesjonid=sesjon, format="json")
        except nett.HttpFeil as e:
            print(f"    ✗ {ptype}: HTTP {e.kode} — {e.kropp[:120]}", flush=True)
            continue
        except nett.NettFeil as e:
            # Her er det verre: uten lista vet vi ikke hva som mangler, så
            # sesjonen blir ufullstendig uten at noen ser det. Stopp.
            raise SystemExit(
                f"FEIL: fikk ikke listet {ptype} for sesjon {sesjon}: {e}\n"
                "Uten lista vet vi ikke hvilke dokumenter som mangler."
            ) from e
        liste = forste_liste(data)
        print(f"    {ptype}: {len(liste)} publikasjoner", flush=True)
        for p in liste:
            if isinstance(p, dict) and p.get("id"):
                ønsket.append((p["id"], ptype, str(p.get("tittel") or "")))

    mangler = [x for x in ønsket if x[0] not in hentet]
    print(f"  {len(ønsket)} publikasjoner totalt, {len(mangler)} å hente", flush=True)

    start = time.monotonic()
    tomme = 0
    feilede: list[str] = []
    for i, (pid, ptype, tittel) in enumerate(mangler, 1):
        time.sleep(PAUSE)
        try:
            kropp = hent("publikasjon", publikasjonid=pid)
        except nett.HttpFeil as e:
            print(f"    ✗ {pid}: HTTP {e.kode}", flush=True)
            feilede.append(pid)
            continue
        except nett.NettFeil as e:
            # Ett dokument som ikke svarer er et hull i dekningen, ikke en
            # grunn til å kaste de andre. Men hullet telles: et dokument vi
            # ikke fikk lest kan ikke gi treff, og skal aldri forveksles med
            # et dokument som ikke nevnte noe.
            print(f"    ✗ {pid}: {e}", flush=True)
            feilede.append(pid)
            continue
        tekst = normaliser(tekst_fra_xml(kropp))
        if not tekst:
            tomme += 1
        legg_til(sesjon, {"id": pid, "type": ptype, "sesjon": sesjon,
                          "tittel": tittel, "tegn": len(tekst), "tekst": tekst})
        if i % 50 == 0 or i == len(mangler):
            gått = time.monotonic() - start
            print(f"    {i}/{len(mangler)} — {gått:.0f} s, "
                  f"{gått / i:.2f} s/dok, ~{(len(mangler) - i) * gått / i / 60:.0f} min igjen",
                  flush=True)

    if feilede:
        print(f"  ⚠ {len(feilede)} dokumenter lot seg ikke hente. En ny kjøring "
              f"prøver dem igjen — resten er lagret.", flush=True)
    return {"publikasjoner": len(ønsket), "hentet_nå": len(mangler),
            "tomme": tomme, "feilede": len(feilede)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sesjoner", type=int, default=STANDARD_SESJONER,
                    help=f"antall sesjoner bakover (standard {STANDARD_SESJONER})")
    ap.add_argument("--frisk", action="store_true",
                    help="ignorer lagrede dokumenter og hent alt på nytt")
    args = ap.parse_args()

    print(f"{KILDE} — {KILDE_URL}")
    valgte = sesjoner(args.sesjoner)
    if not valgte:
        raise SystemExit("FEIL: fikk ingen sesjoner fra registeret.")
    print(f"Henter fulltekst for {len(valgte)} sesjoner: {', '.join(valgte)}")

    RAADATA_DIR.mkdir(parents=True, exist_ok=True)
    fasit = {}
    for sesjon in valgte:
        print(f"\nSesjon {sesjon}", flush=True)
        fasit[sesjon] = hent_sesjon(sesjon, bruk_sjekkpunkt=not args.frisk)

    (RAADATA_DIR / "hentelogg.json").write_text(json.dumps({
        "kilde": KILDE, "kilde_url": KILDE_URL,
        "dato_hentet": date.today().isoformat(),
        "sesjoner": valgte,
        "publikasjonstyper": list(PUBLIKASJONSTYPER),
        "merknad": ("Dekningen begrenser nevneren i akt 2: en evaluering kan "
                    "ikke telles som «aldri nevnt» for år vi ikke har hentet."),
        "per_sesjon": fasit,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    totalt = sum(f["publikasjoner"] for f in fasit.values())
    tomme = sum(f["tomme"] for f in fasit.values())
    feilet = sum(f["feilede"] for f in fasit.values())
    print(f"\n✓ {totalt} publikasjoner over {len(valgte)} sesjoner")
    if feilet:
        print(f"  ⚠ {feilet} dokumenter mangler fortsatt — kjør igjen for å")
        print("    hente dem; resten gjenbrukes og koster ingen nye kall")
    if tomme:
        print(f"  ⚠ {tomme} dokumenter ga tom tekst — de kan ikke gi treff,")
        print("    og skal telles som manglende dekning, ikke som «nevnte ikke»")
    print(f"  skrev til {RAADATA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
