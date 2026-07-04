"""Henter data til «Kulturordet» — historiens to kilder:

  1. Nasjonalbiblioteket (n-gram): hvor ofte ordet «kultur» står i norske
     aviser, år for år siden 1800-tallet. Relativ frekvens, så avisvekst
     ikke forveksles med ordvekst.
  2. Stortinget (åpne data): antall saker per sesjon med kultur i tittel
     eller emneliste — politikkens oppmerksomhet mot feltet.

Kjøring (krever nett mot api.nb.no og data.stortinget.no):

    python3 pipeline/hent_kulturordet.py           # ekte tall
    python3 pipeline/hent_kulturordet.py --demo    # merkede plassholderdata
    python3 pipeline/bygg_manifest.py

N-gram-API-et har flere generasjoner endepunkter; scriptet prøver dem i
rekkefølge og VERIFISERER svaret mot kjent virkelighet («kultur» brukes
vesentlig mer etter 1990 enn før 1900) før noe skrives. Feiler alle
kandidatene, skrives ingen snapshot — juster kandidatlisten mot
dokumentasjonen på https://api.nb.no/ og DH-laben.

Stortingets eksport går én sesjon om gangen med pause mellom kallene.
"""

from __future__ import annotations

import json
import math
import sys
import time
import urllib.parse
import urllib.request
from datetime import date

from kontrakt import INNHOLD_DIR, valider_snapshot

UTFIL = INNHOLD_DIR / "kulturordet" / "data.json"
BRUKERAGENT = "impromptu.no datahistorier (kontakt@impromptu.no)"

ORD = "kultur"
NGRAM_FRA, NGRAM_TIL = 1860, 2022
STORTING_FRA = 1998  # eldste sesjon vi teller saker for
PAUSE = 0.4


def _hent(url: str, body: dict | None = None, timeout: int = 120):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"User-Agent": BRUKERAGENT, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


# ------------------------------------------------- NB n-gram (aviser) ----

def _ngram_dhlab() -> dict[int, float]:
    """DH-labens n-gram-API — endepunktet dhlab-biblioteket selv bruker.

    Verifisert mot NationalLibraryOfNorway/DHLAB (dhlab/constants.py) og
    live-testet 2026-07-04:
    NGRAM_API = https://api.nb.no/dhlab/nb_ngram/ngram/query
    Årlige frekvenser fra 1800; «y» er PROSENT av korpuset, «f» råtall.
    NB: corpus=avis kombinert med lang=nob gir HTTP 500 (aviskorpuset er
    ikke språkdelt) — derfor sendes lang ikke med.
    """
    params = urllib.parse.urlencode({"terms": ORD, "corpus": "avis"})
    return _normaliser_ngram(_hent(f"https://api.nb.no/dhlab/nb_ngram/ngram/query?{params}"))


def _ngram_viewer() -> dict[int, float]:
    """Eldre viewer-API — beholdt som reserve."""
    params = urllib.parse.urlencode(
        {"terms": ORD, "corpus": "avis", "lang": "nob", "case_sens": 0, "freq": "rel"}
    )
    return _normaliser_ngram(_hent(f"https://api.nb.no/ngram/ngram?{params}"))


def _normaliser_ngram(svar) -> dict[int, float]:
    """Tåler de kjente svarformene og gir {år: relativ frekvens}.

    Kjente former:
      - [{"key"/"name": ord, "values": [{punkt}, ...]}, ...] der hvert
        punkt har år som "x"/"year" (evt. epoch-millisekunder) og verdi
        som "y"/"relfreq"/"f" — relativ frekvens foretrekkes over råtall
      - {"kultur": {"1975": 0.0012, ...}}  (ord → år → verdi)
      - {"1975": 0.0012, ...}
    """
    serie: dict[int, float] = {}

    def til_aar(x) -> int | None:
        try:
            tall = float(x)
        except (TypeError, ValueError):
            return None
        if 1800 <= tall <= 2030:
            return int(tall)
        # epoch-millisekunder (slik grafbiblioteker gjerne vil ha dem)
        if abs(tall) > 1e10:
            from datetime import datetime, timezone
            return datetime.fromtimestamp(tall / 1000, tz=timezone.utc).year
        return None

    def ta_med(aar, verdi):
        a = til_aar(aar)
        try:
            v = float(verdi)
        except (TypeError, ValueError):
            return
        if a is not None and v >= 0:
            serie[a] = v

    if isinstance(svar, list):
        for element in svar:
            for punkt in element.get("values", []):
                if not isinstance(punkt, dict):
                    continue
                aar = punkt.get("x", punkt.get("year"))
                verdi = punkt.get("y", punkt.get("relfreq", punkt.get("f")))
                ta_med(aar, verdi)
    elif isinstance(svar, dict):
        verdier = svar.get(ORD, svar)
        if isinstance(verdier, dict):
            for aar, verdi in verdier.items():
                ta_med(aar, verdi)

    return {a: v for a, v in sorted(serie.items()) if NGRAM_FRA <= a <= NGRAM_TIL}


def hent_ngram() -> dict[int, float]:
    kandidater = [("DH-lab-API (nb_ngram/ngram/query)", _ngram_dhlab),
                  ("eldre viewer-API (api.nb.no/ngram)", _ngram_viewer)]
    feil = []
    for navn, hent in kandidater:
        try:
            serie = hent()
        except Exception as e:
            feil.append(f"{navn}: {e}")
            continue
        try:
            kontroller_ngram(serie)
        except SystemExit as e:
            feil.append(f"{navn}: {e}")
            continue
        print(f"  n-gram hentet via {navn} ({len(serie)} år)")
        return serie
    raise SystemExit("Ingen n-gram-kandidat ga brukbart svar:\n  " + "\n  ".join(feil))


def kontroller_ngram(serie: dict[int, float]) -> None:
    """Nekt å bruke serier som ikke ligner virkeligheten."""
    if len(serie) < 80:
        raise SystemExit(f"bare {len(serie)} år i serien — ventet 80+")
    tidlig = [v for a, v in serie.items() if a < 1900]
    sent = [v for a, v in serie.items() if 1990 <= a <= 2015]
    if not tidlig or not sent:
        raise SystemExit("serien dekker ikke både 1800-tallet og 1990–2015")
    if not max(sent) > 0:
        raise SystemExit("nyere verdier er null — feil parsing?")
    snitt = lambda liste: sum(liste) / len(liste)
    if snitt(sent) <= snitt(tidlig) * 2:
        raise SystemExit(
            "«kultur» øker ikke klart fra 1800-tallet til 1990–2015 — "
            "dette stemmer ikke med kjent språkhistorie; sjekk parsingen"
        )


# ------------------------------------------------- Stortinget (saker) ----

def hent_stortinget() -> list[dict]:
    """[{sesjon, aar, kultursaker, alle_saker}] fra STORTING_FRA og fremover."""
    data = _hent("https://data.stortinget.no/eksport/sesjoner?format=json")
    sesjoner = [s.get("id") for s in data.get("sesjoner_liste", []) if s.get("id")]
    sesjoner = sorted(
        s for s in sesjoner
        if s[:4].isdigit() and int(s[:4]) >= STORTING_FRA
    )
    if len(sesjoner) < 15:
        raise SystemExit(f"bare {len(sesjoner)} sesjoner funnet fra {STORTING_FRA} — uventet")

    ut = []
    for sesjon in sesjoner:
        params = urllib.parse.urlencode({"sesjonid": sesjon, "format": "json"})
        saker = _hent(f"https://data.stortinget.no/eksport/saker?{params}").get(
            "saker_liste", []
        )
        kultursaker = sum(1 for sak in saker if _er_kultursak(sak))
        ut.append({"sesjon": sesjon, "aar": int(sesjon[:4]),
                   "kultursaker": kultursaker, "alle_saker": len(saker)})
        print(f"  {sesjon}: {kultursaker} kultursaker av {len(saker)}")
        time.sleep(PAUSE)

    if sum(r["alle_saker"] for r in ut) < 1000:
        raise SystemExit("mistenkelig få saker totalt — sjekk eksport-API-et")
    return ut


def _er_kultursak(sak: dict) -> bool:
    emner = sak.get("emne_liste") or []
    if any("kultur" in str(e.get("navn", "")).lower() for e in emner):
        return True
    return "kultur" in str(sak.get("tittel", "")).lower()


# ------------------------------------------------------- snapshot ----

# API-ets «y» er prosent; ganget med 10 000 blir det forekomster per
# million ord — tall i spennet ~5–80, som både grafmotor og leser trives
# med. Skalaen er verifisert empirisk 2026-07-04: implisert korpus
# (f delt på y som prosent) gir ~1,2 mrd. avisord for 2015, som stemmer.
FRA_PROSENT_TIL_PER_MILLION = 10_000


def bygg_snapshot(ngram: dict[int, float], storting: list[dict], demo: bool) -> dict:
    ngram = {a: round(v * FRA_PROSENT_TIL_PER_MILLION, 3) for a, v in ngram.items()}
    if not 0.5 <= max(ngram.values()) <= 5000:
        raise SystemExit(
            f"skalert maksverdi {max(ngram.values())} per million ord er utenfor "
            "rimelig bånd — har API-et endret enhet (prosent ↔ andel)?"
        )
    forste_tiaar = [v for a, v in ngram.items() if a < min(ngram) + 10]
    siste_tiaar = [v for a, v in ngram.items() if a > max(ngram) - 10]
    ganger = round((sum(siste_tiaar) / len(siste_tiaar))
                   / max(sum(forste_tiaar) / len(forste_tiaar), 1e-12))
    toppsesjon = max(storting, key=lambda r: r["kultursaker"])

    meta = {
        "tittel": "Ordet som erobret Norge",
        "kilde": "Nasjonalbiblioteket og Stortinget",
        "kilde_url": "https://www.nb.no/ngram/",
        "dato_hentet": date.today().isoformat(),
        "geografi": "Norge",
        "enhet": "relativ frekvens i aviser; antall saker i Stortinget",
        "oppdateringsfrekvens": "årlig",
        "beskrivelse": (
            "«Kultur» var et sjeldent ord i norske aviser. Så begynte det å "
            "vokse — og i Stortinget fulgte sakene etter. To kilder, én "
            "ordhistorie."
        ),
    }
    if demo:
        meta["demo"] = True

    return {
        "meta": meta,
        "visninger": {
            "hero": {
                "type": "hero",
                "eyebrow": "Ett ord, to arkiver",
                "sporsmal": "Hvor stort ble ordet «kultur»?",
                "rader": [
                    {"etikett": "I avisene", "verdi": f"~{ganger}× oftere",
                     "detalj": f"enn på {min(ngram)}-tallet, målt per million avisord"},
                    {"etikett": "På Stortinget", "verdi": f"{toppsesjon['kultursaker']} saker",
                     "detalj": f"i toppsesjonen {toppsesjon['sesjon']}"},
                ],
                "fotnote": ("Relativ frekvens i digitaliserte aviser (Nasjonalbiblioteket) "
                            "og saker med kultur i tittel/emne (data.stortinget.no)."),
            },
            "aviser": {
                "type": "tidslinje",
                "tittel": "«Kultur» i norske aviser",
                "enhet": "forekomster per million avisord",
                "serier": [{
                    "navn": "kultur",
                    "punkter": [[a, v] for a, v in sorted(ngram.items())],
                }],
            },
            "storting": {
                "type": "tidslinje",
                "stil": "søyle",
                "tittel": "Kultursaker i Stortinget per sesjon",
                "enhet": "saker med kultur i tittel eller emne",
                "serier": [{
                    "navn": "kultursaker",
                    "punkter": [[r["aar"], r["kultursaker"]] for r in storting],
                }],
            },
            "milepaeler": {
                "type": "kortgalleri",
                "tittel": "Ordets milepæler",
                "undertekst": "øyeblikk der kulturen rykket frem i offentligheten",
                "kort": [
                    {"overtittel": "1973–74", "verdi": "Første kulturmelding",
                     "detalj": "det «utvidede kulturbegrepet» gjør ordet til politikk"},
                    {"overtittel": "2005", "verdi": "Kulturløftet",
                     "detalj": "én prosent av statsbudsjettet blir politisk mål"},
                    {"overtittel": "2007", "verdi": "Kulturlova",
                     "detalj": "det offentlige kulturansvaret blir lovfestet"},
                    {"overtittel": "2020–21", "verdi": "Stengte scener",
                     "detalj": "pandemien gjør kulturpolitikk til krisepolitikk"},
                ],
            },
        },
    }


# ------------------------------------------------------- demodata ----

def demodata() -> tuple[dict[int, float], list[dict]]:
    """Glatte plassholderkurver med riktig form — merkes «demo» i meta."""
    ngram = {
        aar: round(7e-4 * (1 + 9 / (1 + math.exp(-(aar - 1960) / 18))), 7)
        for aar in range(NGRAM_FRA, NGRAM_TIL + 1)
    }
    storting = [
        {"sesjon": f"{aar}-{aar + 1}", "aar": aar,
         "kultursaker": 30 + round(12 * math.sin((aar - 1998) / 3)) + (aar - 1998) // 2,
         "alle_saker": 900}
        for aar in range(STORTING_FRA, 2026)
    ]
    return ngram, storting


def main() -> int:
    demo = "--demo" in sys.argv
    if demo:
        print("Genererer PLASSHOLDERDATA (merkes «Demodata» på siden) …")
        ngram, storting = demodata()
    else:
        print(f"Henter «{ORD}» fra Nasjonalbibliotekets n-gram …")
        ngram = hent_ngram()
        print("Henter saker fra data.stortinget.no (én sesjon om gangen) …")
        storting = hent_stortinget()

    snapshot = bygg_snapshot(ngram, storting, demo)
    feil = valider_snapshot(snapshot, "kulturordet")
    if feil:
        for f in feil:
            print(f"  ✗ {f}")
        return 1

    UTFIL.parent.mkdir(parents=True, exist_ok=True)
    UTFIL.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
    print(f"✓ skrev {UTFIL}")
    print("Husk: python3 pipeline/bygg_manifest.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
