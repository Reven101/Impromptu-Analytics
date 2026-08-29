"""Henter hele evalueringskorpuset fra Kudos (DFØ) til rådata utenfor repoet.

Kjøring (krever nett mot kudos.dfo.no):

    python pipeline/hent_kudos_evalueringer.py
    python pipeline/hent_kudos_evalueringer.py --kartlegg   # bare feltkartlegging, 1 side

Kudos er DFØs base over kunnskapsdokumenter i offentlig sektor — evalueringer,
utredninger, årsrapporter, tildelingsbrev. Vi henter én type: `Evaluering`.
API-et er Laravel-paginert (`meta.current_page` / `last_page` / `total`) og har
ingen fritekstsøk i v0, bare strukturerte filtre. Se api-atlas/eksempler/hent_kudos.py
for filterlista — den kom fra API-ets egen 422-feilmelding.

Rådata skrives UTENFOR repoet (jf. SIKKERHET.md / .gitignore): sett KUDOS_DIR,
ellers brukes ../impromptu_raadata/kudos/ ved siden av repoet. Alt i dette repoet
serveres statisk av Vercel, så en innsjekket kopi av basen blir offentlig nedlastbar.

To ting scriptet gjør med vilje:

- **Det teller mot API-ets egen fasit.** `meta.total` sier hvor mange dokumenter som
  finnes. Får vi færre rader enn det, stopper vi. En halv base er verre enn ingen
  base, fordi den ser komplett ut — og alle andeler regnet på den blir feil.
- **Det skriver ut en feltkartlegging framfor å anta.** Hvilke felt Kudos faktisk
  leverer per dokument avgjør hvordan resten av pipelinen kan bygges: har basen et
  eget temafelt, trengs ingen LLM-klassifisering; ligger oppdragsgiveren som en
  aktørliste med roller, må rollen velges eksplisitt; og dekningen på
  organisasjonsnummer avgjør om koblingen mot statsregnskapet i det hele tatt bærer.
  Kartleggingen er utskrift, ikke gjetning — den skal leses av et menneske.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import kontrakt  # noqa: F401  -- setter utf-8 på stdout/stderr (Windows-konsollen er cp1252)

API = "https://kudos.dfo.no/api/v0/documents"
KILDE = "Kudos (DFØ)"
KILDE_URL = "https://kudos.dfo.no/apne-data"
BRUKERAGENT = "Impromptu-Analytics/1.0 (kontakt@impromptu.no)"
DOKUMENTTYPE = "Evaluering"

PER_SIDE = 50           # API-ets tak, oppgitt av dets egen 422: «The per page may not
                        # be greater than 50.» Gir ~143 sider på evalueringskorpuset.
PAUSE = 0.3             # samme høflighetspause som atlaset bruker
FORSOK = 4              # med eksponentiell backoff: 2, 4, 8 sekunder

# Rimelighetsgrenser. Atlaset målte ~7 000 evalueringer i juli 2026 og smoke-testen
# der krever minst 1 000. Vi er strengere: faller totalen under 5 000 eller stiger
# over 15 000, har enten API-et endret betydning av `type`, eller vi spør feil.
MIN_RIMELIG = 5_000
MAKS_RIMELIG = 15_000

RAADATA_DIR = Path(
    os.environ.get("KUDOS_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "kudos"
)
UTFIL = RAADATA_DIR / "evalueringer.json"


# ---------------------------------------------------------------- henting

def hent_json(url: str, timeout: int = 60) -> dict:
    """GET med retry. Nettverksfeil og 5xx prøves igjen; 4xx er vår feil og bobler opp."""
    siste = None
    for forsok in range(FORSOK):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": BRUKERAGENT})
            with urllib.request.urlopen(req, timeout=timeout) as svar:
                return json.loads(svar.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # 422 røper gyldige parametre i kroppen — vis den, ikke bare koden.
            if e.code < 500:
                kropp = e.read().decode("utf-8", errors="replace")[:800]
                raise SystemExit(
                    f"FEIL: Kudos svarte HTTP {e.code} på\n  {url}\n{kropp}\n"
                    "Har filternavnene endret seg? API-ets 422 lister de gyldige."
                ) from e
            siste = e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            siste = e
        if forsok < FORSOK - 1:
            time.sleep(2 ** (forsok + 1))
    raise SystemExit(f"FEIL: ga opp {url} etter {FORSOK} forsøk — siste feil: {siste}")


def hent_side(side: int, **filtre) -> dict:
    params = {"page": side, "per_page": PER_SIDE, **filtre}
    return hent_json(f"{API}?{urllib.parse.urlencode(params)}")


def hent_alle() -> tuple[list[dict], dict]:
    """Alle dokumenter av typen Evaluering, med API-ets egen meta fra første side."""
    forste = hent_side(1, type=DOKUMENTTYPE)
    meta = forste.get("meta") or {}
    total = meta.get("total")
    sider = meta.get("last_page")
    if not isinstance(total, int) or not isinstance(sider, int):
        raise SystemExit(
            "FEIL: svaret mangler meta.total / meta.last_page. Kudos v0 var "
            f"Laravel-paginert — har formatet endret seg?\n{json.dumps(meta)[:400]}"
        )
    if not MIN_RIMELIG <= total <= MAKS_RIMELIG:
        raise SystemExit(
            f"FEIL: Kudos oppgir {total} dokumenter av typen «{DOKUMENTTYPE}». "
            f"Vi ventet mellom {MIN_RIMELIG} og {MAKS_RIMELIG}.\n"
            "Enten har type-filteret byttet betydning, eller basen er endret. "
            f"Sjekk {KILDE_URL} før du justerer grensene."
        )

    print(f"  {total} evalueringer fordelt på {sider} sider à {PER_SIDE}")
    dokumenter = list(forste.get("data") or [])
    for side in range(2, sider + 1):
        time.sleep(PAUSE)
        dokumenter += hent_side(side, type=DOKUMENTTYPE).get("data") or []
        if side % 10 == 0 or side == sider:
            print(f"  side {side}/{sider} — {len(dokumenter)} dokumenter")

    # Fasitsjekk mot API-ets eget tall. Duplikater over sidegrenser er en kjent
    # paginerings-felle når basen endres under kjøring, så vi teller unike uuid-er.
    unike = {d.get("uuid") for d in dokumenter if d.get("uuid")}
    if len(unike) < total:
        raise SystemExit(
            f"FEIL: hentet {len(unike)} unike dokumenter, men API-et oppgir {total}. "
            "En ufullstendig base ser komplett ut, og alle andeler regnet på den "
            "blir feil. Kjør på nytt."
        )
    mangler_felt = [d for d in dokumenter if not d.get("uuid") or not d.get("title")]
    if mangler_felt:
        raise SystemExit(
            f"FEIL: {len(mangler_felt)} dokumenter mangler uuid eller title. "
            f"Første: {json.dumps(mangler_felt[0], ensure_ascii=False)[:300]}"
        )
    return dokumenter, meta


# ---------------------------------------------------------------- kartlegging

# Nøkler vi *håper* finnes. Ingenting i scriptet krever dem — de brukes bare til å
# gjøre utskriften lesbar, slik at et menneske ser hva som faktisk er der.
TEMA_HINT = ("theme", "topic", "subject", "category", "tag", "emne", "tema")
AKTOR_HINT = ("actor", "org", "publisher", "owner", "virksomhet")
AAR_HINT = ("year", "date", "published", "aar", "dato")


def _flat_verdier(verdi) -> list:
    """Pakker ut lister og objekter én gang, så vi kan telle dekning på nøstede felt."""
    if isinstance(verdi, list):
        return verdi
    return [verdi]


def kartlegg(dokumenter: list[dict]) -> None:
    """Skriver ut hva basen faktisk inneholder. Dette er scriptets viktigste utskrift."""
    n = len(dokumenter)
    nokler = collections.Counter()
    for d in dokumenter:
        nokler.update(d.keys())

    print("\n" + "=" * 72)
    print("FELTKARTLEGGING — lim denne utskriften inn i samtalen")
    print("=" * 72)

    print(f"\nAntall dokumenter: {n}")
    print(f"Nøkler i datasettet ({len(nokler)}), med dekning:")
    for nokkel, antall in sorted(nokler.items(), key=lambda kv: (-kv[1], kv[0])):
        ikke_tom = sum(
            1 for d in dokumenter
            if d.get(nokkel) not in (None, "", [], {})
        )
        print(f"  {nokkel:<28} {ikke_tom:>6}/{n}  ({100 * ikke_tom / n:.1f} %)")

    print("\nFørste dokument, i sin helhet:")
    print(json.dumps(dokumenter[0], ensure_ascii=False, indent=2)[:2500])

    def gruppe(overskrift: str, hint: tuple[str, ...]) -> None:
        traff = [k for k in nokler if any(h in k.lower() for h in hint)]
        print(f"\n{overskrift}")
        if not traff:
            print("  (ingen felt med disse ordene i navnet)")
            return
        for k in sorted(traff):
            # Ligger feltet som en liste av objekter (aktørlista er den sannsynlige
            # formen), er «<objekt: name, role>» ubrukelig som svar. Vi pakker derfor
            # ut ett nivå og teller hver undernøkkel for seg — det er rolleverdiene
            # og organisasjonsnumrene vi faktisk trenger å se.
            verdier: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
            for d in dokumenter:
                for v in _flat_verdier(d.get(k)):
                    if isinstance(v, dict):
                        for undernokkel, underverdi in v.items():
                            if underverdi not in (None, "", [], {}):
                                verdier[f"{k}.{undernokkel}"][str(underverdi)[:60]] += 1
                    elif v not in (None, ""):
                        verdier[k][str(v)[:60]] += 1
            for felt, teller in sorted(verdier.items()):
                print(f"  {felt} — {len(teller)} unike verdier. De 12 vanligste:")
                for verdi, antall in teller.most_common(12):
                    print(f"      {antall:>6}  {verdi}")

    gruppe("TEMA — finnes det et emnefelt? (avgjør om LLM-klassifisering trengs)", TEMA_HINT)
    gruppe("AKTØR — hvor ligger oppdragsgiveren, og hvilken rolle betyr «bestilte denne»?", AKTOR_HINT)
    gruppe("ÅR — finnes publiseringsår på radnivå?", AAR_HINT)

    print("\n" + "=" * 72)
    print("Fire spørsmål utskriften over skal svare på:")
    print("  1. Har Kudos et eget temafelt?  (nei → pipeline/kategoriser_evalueringer.py)")
    print("  2. Hvordan ligger oppdragsgiveren, og hvilken rolleverdi gjelder?")
    print("  3. Hvor mange prosent har organisasjonsnummer?  (bærer koblingen mot")
    print("     statsregnskapet — lav dekning krymper akt 3 tilsvarende)")
    print("  4. Finnes publiseringsår per dokument?")
    print("=" * 72)


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kartlegg", action="store_true",
                    help="hent bare første side og kartlegg feltene (ingen skriving)")
    args = ap.parse_args()

    print(f"{KILDE} — {KILDE_URL}")

    if args.kartlegg:
        print(f"Henter én side à {PER_SIDE} for feltkartlegging …")
        svar = hent_side(1, type=DOKUMENTTYPE)
        print(f"  meta: {json.dumps(svar.get('meta') or {}, ensure_ascii=False)}")
        kartlegg(list(svar.get("data") or []))
        return 0

    print(f"Henter alle dokumenter av typen «{DOKUMENTTYPE}» …")
    dokumenter, meta = hent_alle()

    RAADATA_DIR.mkdir(parents=True, exist_ok=True)
    UTFIL.write_text(json.dumps({
        "kilde": KILDE,
        "kilde_url": KILDE_URL,
        "dato_hentet": date.today().isoformat(),
        "hentet_tidspunkt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "filter": {"type": DOKUMENTTYPE},
        "api_meta": meta,
        "dokumenter": dokumenter,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n✓ Skrev {len(dokumenter)} dokumenter til {UTFIL}")
    print("  (utenfor repoet — rådata skal ikke sjekkes inn, jf. SIKKERHET.md)")

    kartlegg(dokumenter)

    print("\nNeste steg: lim feltkartleggingen inn i samtalen, så skrives")
    print("bygg_historie_evalueringer.py mot det basen faktisk inneholder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
