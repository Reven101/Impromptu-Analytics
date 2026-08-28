"""Trekker ut antall spilte forestillinger fra IbsenStage sitt merknadsfelt.

Kjøring:

    python pipeline/uttrekk_forestillinger.py            # fasittest, så full kjøring
    python pipeline/uttrekk_forestillinger.py --bare-fasit
    python pipeline/uttrekk_forestillinger.py --modell openai/gpt-oss-120b

Hvorfor dette er verdt et LLM-steg: IbsenStage teller **oppsetninger**, ikke
forestillinger. En produksjon som gikk 52 ganger teller likt med én som gikk én
gang. Antallet står ofte i merknadsfeltet, men som fritekst — og ordet
«performance» betyr to helt ulike ting der. «32 Performances at Hovedscenen» er
et tall; «made a guest performance as Nora» og «Monologue-performance» er det
ikke. En regel som leter etter tall foran ordet treffer 87,5 % på fasiten, men
bare 1 av 6 av tilfellene som krever at man summerer deltall eller forstår
setningen. Det er skillet en modell faktisk kan gjøre.

Målt på 120 håndmerkede tekster (`fasit_forestillinger.json`, som kjøres først
hver gang):

    regel (regex)            87,5 %   gratis
    gemini-3.1-flash-lite    95,0 %   $0,0045
    openai/gpt-oss-120b      98,3 %   $0,0032   men 8x tregere

Vi bruker flash-lite. gpt-oss-120b er både bedre og billigere per kall, men brukte
73 % av output-tokenene på resonnering og åtte ganger så lang tid; forskjellen på
3,3 prosentpoeng forsvarer ikke det her.

To fallgruver som er håndtert i koden:

- **Modellen svarer «0» der prompten ber om «null».** Det var hele forklaringen
  på at flash-lite først målte 40,8 % og ikke 95,0 %. Null forestillinger er
  aldri et gyldig svar, så 0 tolkes som «ikke oppgitt».
- **38 % av tekstene er gjengangere.** Riksteatret fører samme merknad på hver
  turnédato. Vi slår opp per unike tekst, ikke per oppsetning, og sparer 6 808
  kall på det.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import kontrakt  # noqa: F401
import llm_klient

PROMPTVERSJON = 2
BUNT = 20
TRAADER = 4
# Målt forbruk er ~250 tokens per bunt på 20. Taket er dobbel margin, ikke
# «romslig for sikkerhets skyld»: OpenRouter reserverer kreditt mot maks_tokens
# for hver forespørsel i luften, og et oppblåst tak ganget med antall tråder gir
# HTTP 402 med god saldo på konto. llm_klient dobler selv ved avkutting.
MAKS_TOKENS = 800

RAADATA_DIR = Path(
    os.environ.get("IBSENSTAGE_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ibsenstage"
)
HER = Path(__file__).resolve().parent
FASIT = HER / "fasit_forestillinger.json"
CACHE = HER / "cache" / "forestillinger_cache.json"

SYSTEM = """Du trekker ut antall forestillinger fra merknadsfeltet i en database over Ibsen-oppsetninger.

For hver tekst: oppgi hvor mange ganger oppsetningen ble spilt, som et helt tall.
Oppgi null når teksten ikke sier det.

Regler:
- Oppgis flere deltall for samme oppsetning (ulike perioder, scener eller turné), legg dem sammen.
- «Played 17 times» og «Number of performances: 19» er antall. Det er «22 times ... About 40 performances elsewhere» også (= 62).
- Oppramsede datoer er IKKE et antall. «Also performed 23th, 25th, 26th October» gir null, selv om man kunne telt dem.
- Ordet «performance» brukes ofte i andre betydninger. Disse gir null:
  «guest performance», «premiere performance», «jubilee performance», «monologue-performance»,
  «made a guest performance as Nora», «the performances in Oslo».
- Er et antall oppgitt sammen med slik bruk, tell bare antallet: «11 Performances / Johanne Dybwad guest performance» gir 11.
- Bruk null, ikke 0.
- «nt / 1001», «tr / 796», «PERF_FLAG nt / 635» er interne arkivkoder, ikke antall.
  Tallet etter «nt /» eller «tr /» skal ALLTID ignoreres. «nt / 709» gir null.
  Står det et ekte antall i tillegg, tell bare det: «tr / 458 / 9 Performances» gir 9.

Svar med en JSON-liste med ett objekt per tekst, i samme rekkefølge:
[{"nr": 0, "antall": 9}, {"nr": 1, "antall": null}]
Ingen forklaring, bare lista."""

RE_REGEL = re.compile(
    r"(?i)(?:(?:tour\s+)?total(?:t)?(?:\s+tour)?(?:\s+of)?[:\s-]+|"
    r"number\s+of\s+performances[:\s]+|^)(\d+)\s*(?:pe[rf]{1,3}orman\w*)"
)

_las = threading.Lock()


def regel(tekst: str) -> int | None:
    m = RE_REGEL.search(tekst)
    return int(m.group(1)) if m else None


def _nokkel(tekst: str, modell: str) -> str:
    h = hashlib.sha1(tekst.encode("utf-8")).hexdigest()[:16]
    return f"{PROMPTVERSJON}|{modell}|{h}"


def _tolk(verdi) -> int | None:
    """0 er ikke et gyldig antall forestillinger — modellen mener «ikke oppgitt»."""
    if isinstance(verdi, bool) or verdi is None:
        return None
    if isinstance(verdi, str):
        verdi = verdi.strip()
        if not verdi.lstrip("-").isdigit():
            return None
        verdi = int(verdi)
    if isinstance(verdi, (int, float)):
        n = int(verdi)
        return n if n > 0 else None
    return None


def kjor(tekster: list[str], modell: str, cache: dict) -> dict[str, int | None]:
    mangler = [t for t in tekster if _nokkel(t, modell) not in cache]
    print(f"  {len(tekster) - len(mangler)} fra cache, {len(mangler)} nye")
    if not mangler:
        return {t: cache[_nokkel(t, modell)] for t in tekster}

    bunter = [mangler[i:i + BUNT] for i in range(0, len(mangler), BUNT)]
    teller = {"n": 0}
    start = time.time()

    def _svar(bunt: list[str]) -> None:
        """Kaller modellen på én bunt. Feil antall svar løses ved å dele bunten.

        Skillet mot API-feil er med vilje: SystemExit (kreditt, avkutting, nett)
        bobler opp, for å dele opp mot dem ganger bare opp antall mislykkede kall
        på hver tråd. Bare feil som skyldes bunten selv løses ved oppdeling.
        """
        bruker = "\n".join(f"[{i}] {t}" for i, t in enumerate(bunt))
        svar = llm_klient.kall_modell(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": bruker}],
            modell=modell, maks_tokens=MAKS_TOKENS,
        )
        liste = llm_klient.hent_json_liste(svar)
        if len(liste) != len(bunt):
            if len(bunt) == 1:
                print(f"    ! ett svar manglet på én tekst - hoppes over", flush=True)
                with _las:
                    cache[_nokkel(bunt[0], modell)] = None
                return
            midt = len(bunt) // 2
            print(f"    ! {len(liste)} svar på {len(bunt)} tekster - deler bunten",
                  flush=True)
            _svar(bunt[:midt])
            _svar(bunt[midt:])
            return
        with _las:
            for t, post in zip(bunt, liste):
                cache[_nokkel(t, modell)] = _tolk(post.get("antall"))

    def gjor(bunt: list[str]) -> None:
        _svar(bunt)
        with _las:
            teller["n"] += 1
            if teller["n"] % 25 == 0 or teller["n"] == len(bunter):
                gatt = time.time() - start
                igjen = (len(bunter) - teller["n"]) / (teller["n"] / gatt) / 60
                print(f"    bunt {teller['n']}/{len(bunter)}  ~{igjen:.0f} min igjen  "
                      f"${llm_klient.forbruk['kostnad']:.4f}", flush=True)
                _lagre(cache)

    with ThreadPoolExecutor(max_workers=TRAADER) as pool:
        list(pool.map(gjor, bunter))
    _lagre(cache)
    return {t: cache[_nokkel(t, modell)] for t in tekster}


def _lagre(cache: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True),
                     encoding="utf-8")


def fasittest(modell: str, cache: dict) -> float:
    data = json.loads(FASIT.read_text(encoding="utf-8"))
    tekster = [d["tekst"] for d in data]
    svar = kjor(tekster, modell, cache)
    rett = sum(1 for d in data if svar[d["tekst"]] == d["fasit"])
    falsk = sum(1 for d in data if d["fasit"] is None and svar[d["tekst"]] is not None)
    feller = [d for d in data if d["felle"]]
    felle_ok = sum(1 for d in feller if svar[d["tekst"]] is None)
    r = sum(1 for d in data if regel(d["tekst"]) == d["fasit"]) / len(data) * 100
    print(f"  fasit: {rett}/{len(data)} = {rett / len(data) * 100:.1f}%  "
          f"(regel-grunnlinje {r:.1f}%)")
    print(f"  falske tall: {falsk}   feller klart: {felle_ok}/{len(feller)}")
    # Feilene skrives ut, ikke bare telles. Første kjøring meldte «falske tall: 5»
    # og 95,8 %, og de fem var alle samme systematiske feil — arkivkoder lest som
    # antall. Et sammendrag som ikke viser hva som er galt, blir ikke lest.
    feil = [(d, svar[d["tekst"]]) for d in data if svar[d["tekst"]] != d["fasit"]]
    for d, fikk in feil:
        print(f"    fasit {str(d['fasit']):>5} | svarte {str(fikk):>5} | {d['tekst'][:74]}")
    return rett / len(data) * 100


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--modell", default=llm_klient.STANDARDMODELL)
    ap.add_argument("--bare-fasit", action="store_true")
    ap.add_argument("--terskel", type=float, default=90.0,
                    help="minste treffrate på fasiten før full kjøring settes i gang")
    args = ap.parse_args()

    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    llm_klient.nullstill_forbruk()

    print(f"Fasittest ({args.modell}):")
    treff = fasittest(args.modell, cache)
    if treff < args.terskel:
        raise SystemExit(
            f"treffraten {treff:.1f}% er under terskelen {args.terskel}%. "
            "Uttrekket stoppes framfor å fylle 17 686 rader med tall vi ikke stoler på."
        )
    if args.bare_fasit:
        print(f"\n{llm_klient.forbruk_oppsummert()}")
        return

    poster = []
    with (RAADATA_DIR / "ibsenstage_detaljer.jsonl").open(encoding="utf-8") as f:
        for linje in f:
            x = json.loads(linje)
            if x.get("tilleggsinfo"):
                poster.append((x["hendelse_id"], " ".join(x["tilleggsinfo"].split())))
    unike = sorted({t for _, t in poster})
    print(f"\nFullt uttrekk: {len(poster)} merknadsfelt, {len(unike)} unike tekster")

    svar = kjor(unike, args.modell, cache)

    ut = [{"hendelse_id": i, "forestillinger": svar.get(t),
           "regel_sa": regel(t)} for i, t in poster]
    fil = RAADATA_DIR / "ibsenstage_forestillinger.json"
    fil.write_text(json.dumps({
        "hentet": date.today().isoformat(), "modell": args.modell,
        "promptversjon": PROMPTVERSJON, "fasit_treff": round(treff, 1),
        "antall": len(ut), "oppsetninger": ut,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    med = [r for r in ut if r["forestillinger"]]
    tall = sorted(r["forestillinger"] for r in med)
    print(f"\n{len(ut)} oppsetninger med merknadsfelt")
    print(f"  med forestillingstall: {len(med)} ({len(med) / len(ut) * 100:.1f}%)")
    print(f"  median {tall[len(tall) // 2]}, "
          f"p90 {tall[int(len(tall) * 0.9)]}, maks {tall[-1]}")
    print(f"  sum forestillinger: {sum(tall):,}".replace(",", " "))
    bare_modell = sum(1 for r in med if r["regel_sa"] is None)
    print(f"  herav funnet av modellen, ikke av regelen: {bare_modell} "
          f"({bare_modell / len(med) * 100:.0f}%)")
    print(f"\n{llm_klient.forbruk_oppsummert()}")
    print(f"  {fil}")


if __name__ == "__main__":
    main()
