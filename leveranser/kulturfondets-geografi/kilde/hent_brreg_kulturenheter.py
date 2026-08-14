"""Henter kunst- og kulturorganisasjoner fra Enhetsregisteret og fordeler dem på fylke.

Kjøring (krever nett mot data.brreg.no):

    python3 hent_brreg_kulturenheter.py
    python3 hent_brreg_kulturenheter.py --naering 90 91 58.11 59 60   # bredere kulturnæring

Spørsmålet scriptet svarer på: hvor i landet holder organisasjonene som driver
med kunst og kultur til — og hvordan står tettheten av dem mot søkerbasen til
Norsk kulturfond? Tallene skrives til et datert snapshot og sammenstilles med
folketall og søkertall fra ../kilde/data.json (geografianalysen 2024–2026).

STATUS: IKKE VERIFISERT MOT LIVE API. Scriptet er skrevet uten nettilgang til
data.brreg.no. Feltnavn og parametere følger Enhetsregisterets dokumenterte
v1-API, men første kjøring må kontrolleres mot kanaritallene scriptet printer.
Oppdater denne linjen — og kildekortet i kultursektor-datakilder-skillen — når
det er gjort.

Kilde:    Brønnøysundregistrene, Enhetsregisteret
Lisens:   NLOD — oppgi «Kilde: Brønnøysundregistrene»
Dok:      https://data.brreg.no/enhetsregisteret/api/dokumentasjon

Hvorfor kommune-for-kommune og ikke ett stort søk: Enhetsregisterets søke-API
nekter å paginere forbi 10 000 treff. Ett landsdekkende søk på næringskode 90
sprenger den grensen. Ved å løkke over kommunene holder hvert delsøk seg godt
under taket, og vi slipper å laste ned hele registeret (~1 million enheter).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

API = "https://data.brreg.no/enhetsregisteret/api"
BRUKERAGENT = "Impromptu-datainnsamling (kontakt: kontakt@impromptu.no)"
PAUSE = 0.35
TIMEOUT = 30
SIDESTORRELSE = 500

HER = Path(__file__).resolve().parent
ANALYSE_DATA = HER / "data.json"          # fylkesdata fra geografianalysen
UTFIL = HER.parent / f"brreg-kulturenheter-{date.today().isoformat()}.json"

# 2024-inndelingen. Kommunenummerets to første siffer gir fylket.
FYLKE_AV_PREFIKS = {
    "03": "Oslo", "11": "Rogaland", "15": "Møre og Romsdal", "18": "Nordland",
    "31": "Østfold", "32": "Akershus", "33": "Buskerud", "34": "Innlandet",
    "39": "Vestfold", "40": "Telemark", "42": "Agder", "46": "Vestland",
    "50": "Trøndelag", "55": "Troms", "56": "Finnmark",
}

# Næring 90 = kunstnerisk virksomhet og underholdning, 91 = biblioteker, arkiver,
# museer og annen kulturvirksomhet. Prefiks, ikke fullstendige koder: scriptet
# grupperer på de underkodene registeret faktisk returnerer, slik at det ikke
# avhenger av at underkodelista er riktig gjengitt her.
STANDARD_NAERING = ["90", "91"]

# Organisasjonsformene sier hvem søkeren er. Grupperingen speiler skillet i
# geografianalysen mellom enkeltpersoner og organisasjoner.
FORM_GRUPPER = {
    "enkeltpersonforetak": {"ENK"},
    "frivillig og ideell": {"FLI", "STI", "SA", "BRL", "BBL"},
    "selskap": {"AS", "ASA", "ANS", "DA", "NUF", "KS", "SE"},
    "offentlig": {"KOMM", "FYLK", "STAT", "ORGL", "IKS", "KF", "FKF", "SF"},
}


def hent_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": BRUKERAGENT,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as svar:
            return json.loads(svar.read().decode("utf-8"))
    except urllib.error.HTTPError as feil:
        raise SystemExit(
            f"Enhetsregisteret svarte {feil.code} på\n  {url}\n"
            "Sjekk https://data.brreg.no/enhetsregisteret/api/dokumentasjon — "
            "endepunktet eller parameternavnene kan ha endret seg."
        ) from feil
    except urllib.error.URLError as feil:
        raise SystemExit(
            f"Fikk ikke kontakt med data.brreg.no ({feil.reason}). "
            "Kjører du bak en proxy som blokkerer verten?"
        ) from feil


def sjekk_at_naeringssoket_virker(prefiks: list[str]) -> None:
    """Prefikssøk på næringskode må gi treff — ellers er hele uttrekket tomt.

    Uten denne sjekken ville et API som slutter å godta delvise koder gi en
    pen, tom rapport i stedet for en feilmelding.
    """
    for kode in prefiks:
        url = f"{API}/enheter?{urllib.parse.urlencode({'naeringskode': kode, 'size': 1})}"
        treff = hent_json(url).get("page", {}).get("totalElements")
        if not treff:
            raise SystemExit(
                f"Søk på næringskode «{kode}» ga null treff. Enten godtar ikke API-et "
                "lenger delvise koder, eller feltnavnet er endret. Prøv med "
                "fullstendige koder (f.eks. 90.011 90.012 …) og oppdater STANDARD_NAERING."
            )
        print(f"  næringskode {kode}: {treff:,} enheter i registeret".replace(",", " "))


def hent_kommuner() -> list[dict]:
    data = hent_json(f"{API}/kommuner")
    kommuner = data.get("_embedded", {}).get("kommuner")
    if not kommuner:
        raise SystemExit(
            "Fant ingen kommuner på /api/kommuner — svarstrukturen er ikke som ventet. "
            f"Toppnøkler i svaret: {list(data)}"
        )
    return kommuner


def hent_enheter_i_kommune(kommunenummer: str, naering: str) -> list[dict]:
    enheter: list[dict] = []
    side = 0
    while True:
        url = f"{API}/enheter?" + urllib.parse.urlencode({
            "kommunenummer": kommunenummer,
            "naeringskode": naering,
            "size": SIDESTORRELSE,
            "page": side,
        })
        svar = hent_json(url)
        enheter.extend(svar.get("_embedded", {}).get("enheter", []))
        sider = svar.get("page", {}).get("totalPages", 0)
        side += 1
        if side >= sider:
            break
        if side * SIDESTORRELSE >= 10_000:
            raise SystemExit(
                f"Kommune {kommunenummer} har mer enn 10 000 treff på næring {naering}. "
                "Del søket videre (f.eks. per underkode) — API-et pagineres ikke lenger."
            )
        time.sleep(PAUSE)
    return enheter


def er_aktiv(enhet: dict) -> bool:
    return not (enhet.get("slettedato") or enhet.get("konkurs") or enhet.get("underAvvikling"))


def formgruppe(kode: str) -> str:
    for navn, koder in FORM_GRUPPER.items():
        if kode in koder:
            return navn
    return "annet"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--naering", nargs="+", default=STANDARD_NAERING,
                    help="næringskode-prefikser (standard: 90 91)")
    ap.add_argument("--ta-med-inaktive", action="store_true",
                    help="ta med konkurs, under avvikling og slettede enheter")
    args = ap.parse_args()

    print(f"Enhetsregisteret — kunst- og kulturenheter, næring {' '.join(args.naering)}")
    sjekk_at_naeringssoket_virker(args.naering)

    kommuner = hent_kommuner()
    print(f"  {len(kommuner)} kommuner å gå gjennom\n")

    per_fylke: dict[str, Counter] = defaultdict(Counter)
    per_kommune: Counter = Counter()
    underkoder: Counter = Counter()
    utenfor_fylkesinndelingen = 0
    sett: set[str] = set()

    for nr, kommune in enumerate(kommuner, 1):
        knr = str(kommune.get("nummer", "")).zfill(4)
        for naering in args.naering:
            for enhet in hent_enheter_i_kommune(knr, naering):
                orgnr = enhet.get("organisasjonsnummer")
                if not orgnr or orgnr in sett:
                    continue          # en enhet kan treffe flere næringsprefiks
                if not args.ta_med_inaktive and not er_aktiv(enhet):
                    continue
                sett.add(orgnr)

                fylke = FYLKE_AV_PREFIKS.get(knr[:2])
                if fylke is None:
                    utenfor_fylkesinndelingen += 1
                    continue

                form = (enhet.get("organisasjonsform") or {}).get("kode", "")
                per_fylke[fylke]["enheter"] += 1
                per_fylke[fylke][formgruppe(form)] += 1
                per_kommune[f"{kommune.get('navn', knr)} ({knr})"] += 1
                underkoder[(enhet.get("naeringskode1") or {}).get("kode", "ukjent")] += 1
            time.sleep(PAUSE)
        if nr % 50 == 0:
            print(f"  … {nr}/{len(kommuner)} kommuner, {len(sett):,} enheter".replace(",", " "))

    if not sett:
        raise SystemExit("Uttrekket ble tomt. Se kanaritallene over — noe er galt med søket.")

    # Kobling mot geografianalysen: folketall og søkerbase per fylke
    analyse = json.loads(ANALYSE_DATA.read_text(encoding="utf-8"))
    fylkesdata = {f["fylke"]: f for f in analyse["fylker"]}

    rader = []
    for fylke, tall in per_fylke.items():
        ref = fylkesdata.get(fylke, {})
        folketall = ref.get("folketall")
        rader.append({
            "fylke": fylke,
            "enheter": tall["enheter"],
            "enkeltpersonforetak": tall["enkeltpersonforetak"],
            "frivillig_og_ideell": tall["frivillig og ideell"],
            "selskap": tall["selskap"],
            "offentlig": tall["offentlig"],
            "annet": tall["annet"],
            "folketall": folketall,
            "enheter_per_10k": round(tall["enheter"] / folketall * 10_000, 1) if folketall else None,
            # Søkertallene kommer fra geografianalysen og gjelder Norsk kulturfond 2024–2026.
            # Bare organisasjonssøkerne sammenliknes med registeret; enkeltpersonene som
            # søker i eget navn har ikke noe organisasjonsnummer å finnes igjen på.
            "kulturfond_org_sokere": ref.get("unike_org"),
            "kulturfond_sokere_per_10k": ref.get("sokere_per_10k"),
            # Indikativt mål, ikke en andel: en søkerorganisasjon kan være registrert på
            # en helt annen næringskode enn 90/91 (mange festivaler ligger f.eks. under
            # 93.2), så telleren er ikke en delmengde av nevneren. Brukes til å rangere
            # fylker mot hverandre, ikke til å si «x prosent av kulturlivet søker».
            "org_sokere_per_100_enheter": (
                round(ref["unike_org"] / tall["enheter"] * 100, 1)
                if ref.get("unike_org") and tall["enheter"] else None
            ),
        })
    rader.sort(key=lambda r: -(r["enheter_per_10k"] or 0))

    snapshot = {
        "kilde": "Brønnøysundregistrene, Enhetsregisteret",
        "hentet": date.today().isoformat(),
        "naeringskoder": args.naering,
        "inkluderer_inaktive": args.ta_med_inaktive,
        "enheter_totalt": len(sett),
        "utenfor_fylkesinndelingen": utenfor_fylkesinndelingen,
        "underkoder": dict(underkoder.most_common()),
        "fylker": rader,
        "topp_kommuner": dict(per_kommune.most_common(25)),
        "forbehold": (
            "Forretningsadresse, ikke der aktiviteten foregår — samme begrensning som i "
            "geografianalysen. Enhetsregisteret sier heller ingenting om aktivitetsnivå: "
            "en sovende forening og et helårsdrevet hus teller likt."
        ),
    }
    UTFIL.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")

    # Kanaritall til manuell rimelighetssjekk
    print(f"\n{len(sett):,} aktive enheter".replace(",", " "))
    print(f"{utenfor_fylkesinndelingen} utenfor fylkesinndelingen (Svalbard, ukjent kommune)")
    print(f"{len(underkoder)} ulike næringsunderkoder, de fem største:")
    for kode, antall in underkoder.most_common(5):
        print(f"    {kode}: {antall:,}".replace(",", " "))
    print(f"\n{'Fylke':<18}{'Enheter':>9}{'Per 10 000':>12}{'Herav ENK':>11}{'Søkere/10k':>12}")
    for r in rader:
        print(f"{r['fylke']:<18}{r['enheter']:>9,}{r['enheter_per_10k'] or 0:>12.1f}"
              f"{r['enkeltpersonforetak']:>11,}{r['kulturfond_sokere_per_10k'] or 0:>12.1f}"
              .replace(",", " "))
    print(f"\nSkrevet: {UTFIL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
