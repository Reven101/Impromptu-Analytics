"""Utleder sannsynlig kjønn for medvirkende i IbsenStage, fra fornavn og land.

Kjøring:

    python pipeline/berik_kjonn.py                    # alle funksjoner
    python pipeline/berik_kjonn.py --rolle Director   # bare én rolle

IbsenStage registrerer ikke kjønn. Skal materialet si noe om hvem som lager
Ibsen-forestillinger, må det utledes — og da må feilraten være målt, ikke antatt.
`mal_kjonnsgjetting.py` importerer prompten og oppslagsfunksjonen herfra og måler
dem mot Wikidatas `P21` for de regissørene som har en oppføring der. Målt på
2 837 regissører:

    treff blant besvarte   99,9 %
    dekning (ikke «vet ikke»)  92 %
    skjevhet i kvinneandel     -0,2 prosentpoeng

Delingen er med vilje: målescriptet skal måle NØYAKTIG det som kjøres, ikke en
kopi av det som kan komme i utakt.

Tre ting som avgjør om tallene er brukbare:

- **Oppslaget er (fornavn, land), ikke person.** Det er det modellen så under
  målingen, og det gjør cachen liten: samme fornavn i samme land slås opp én gang
  uansett hvor mange det gjelder.
- **«vet ikke» er et gyldig svar og skal ikke presses ned.** 8 % havner der. De
  som ikke lar seg bestemme er lett overrepresentert blant kvinner (22,4 % mot
  19,5 %), men effekten på kvinneandelen er -0,2 prosentpoeng.
- **Landet er der forestillingen ble spilt, ikke personens opphav.** En ungarsk
  regissør på Nationaltheatret slås opp som norsk. Det er en kjent feilkilde som
  ikke lar seg rette uten opplysninger vi ikke har.

ADVARSEL OM TIDSSERIER: bare 79,6 % av oppsetningene har regissør oppført, og
andelen stiger fra 30 % på 1870-tallet til 98 % på 1970-tallet. En kurve over
kvinneandel gjennom tid blander derfor «flere kvinner regisserer» med «flere
regissører registreres». Tallene er brukbare innenfor et tiår, ikke som trend
uten at det skiftende utvalget håndteres eksplisitt.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import kontrakt  # noqa: F401
import llm_klient

PROMPTVERSJON = 1
BUNT = 50
TRAADER = 4
MAKS_TOKENS = 1500

RAADATA_DIR = Path(
    os.environ.get("IBSENSTAGE_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ibsenstage"
)
CACHE = Path(__file__).resolve().parent / "cache" / "kjonn_cache.json"

SYSTEM = """Du bestemmer sannsynlig kjønn ut fra et fornavn og landet oppsetningen fant sted i.

Svar for hvert navn med nøyaktig én av: "kvinne", "mann", "vet ikke".

"vet ikke" er et fullverdig svar og skal brukes når navnet er kjønnsnøytralt i den
aktuelle språkkulturen, når du ikke kjenner navnet, eller når landet ikke gir nok
holdepunkt. Ikke gjett for å unngå "vet ikke".

Merk at landet er der forestillingen ble spilt, ikke nødvendigvis personens opphav.

Svar med en JSON-liste med ett objekt per navn, i samme rekkefølge:
[{"nr": 0, "kjonn": "kvinne"}, {"nr": 1, "kjonn": "vet ikke"}]
Ingen forklaring."""

_las = threading.Lock()


def _nokkel(fornavn: str, land: str, modell: str) -> str:
    return f"{PROMPTVERSJON}|{modell}|{fornavn}|{land}"


def les_cache() -> dict:
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def _lagre(cache: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True),
                     encoding="utf-8")


def gjett(par: list[tuple[str, str]], modell: str,
          cache: dict | None = None) -> dict[tuple[str, str], str]:
    """(fornavn, land) -> «kvinne» | «mann» | «vet ikke». Cachen sjekkes inn."""
    cache = les_cache() if cache is None else cache
    mangler = [p for p in par if _nokkel(*p, modell) not in cache]
    print(f"  {len(par) - len(mangler)} fra cache, {len(mangler)} nye oppslag")

    if mangler:
        bunter = [mangler[i:i + BUNT] for i in range(0, len(mangler), BUNT)]
        teller = {"n": 0}
        start = time.time()

        def _svar(bunt: list[tuple[str, str]]) -> None:
            tekst = "\n".join(f"[{i}] {f} ({l})" for i, (f, l) in enumerate(bunt))
            ut = llm_klient.kall_modell(
                [{"role": "system", "content": SYSTEM},
                 {"role": "user", "content": tekst}],
                modell=modell, maks_tokens=MAKS_TOKENS)
            liste = llm_klient.hent_json_liste(ut)
            if len(liste) != len(bunt):
                # Buntfeil løses ved å dele; API-feil (SystemExit) skal boble opp.
                if len(bunt) == 1:
                    with _las:
                        cache[_nokkel(*bunt[0], modell)] = "vet ikke"
                    return
                midt = len(bunt) // 2
                _svar(bunt[:midt])
                _svar(bunt[midt:])
                return
            with _las:
                for (f, l), post in zip(bunt, liste):
                    v = str(post.get("kjonn") or "").strip().lower()
                    cache[_nokkel(f, l, modell)] = (
                        v if v in ("kvinne", "mann") else "vet ikke")

        def gjor(bunt) -> None:
            _svar(bunt)
            with _las:
                teller["n"] += 1
                if teller["n"] % 50 == 0 or teller["n"] == len(bunter):
                    gatt = time.time() - start
                    igjen = (len(bunter) - teller["n"]) / (teller["n"] / gatt) / 60
                    print(f"    bunt {teller['n']}/{len(bunter)}  ~{igjen:.0f} min igjen"
                          f"  ${llm_klient.forbruk['kostnad']:.4f}", flush=True)
                    _lagre(cache)

        with ThreadPoolExecutor(max_workers=TRAADER) as pool:
            list(pool.map(gjor, bunter))
        _lagre(cache)

    return {p: cache[_nokkel(*p, modell)] for p in par}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--modell", default=llm_klient.STANDARDMODELL)
    ap.add_argument("--rolle", action="append",
                    help="begrens til disse funksjonene (kan gjentas)")
    args = ap.parse_args()

    browse = {r["hendelse_id"]: r for r in json.loads(
        (RAADATA_DIR / "ibsenstage_hendelser.json")
        .read_text(encoding="utf-8"))["hendelser"]}

    # Én oppføring per (person, land) — samme person i to land slås opp to ganger,
    # fordi landet er en del av spørsmålet modellen fikk under målingen.
    personer: dict[int, dict] = {}
    par: set[tuple[str, str]] = set()
    with (RAADATA_DIR / "ibsenstage_detaljer.jsonl").open(encoding="utf-8") as f:
        for linje in f:
            x = json.loads(linje)
            land = ((browse.get(x["hendelse_id"]) or {}).get("land")
                    or x.get("produksjonsnasjonalitet") or "?")
            for b in x["bidragsytere"]:
                if args.rolle and b["funksjon"] not in args.rolle:
                    continue
                if not b["person_id"] or not b["navn"] or not b["navn"].split():
                    continue
                fornavn = b["navn"].split()[0]
                p = personer.setdefault(b["person_id"], {
                    "person_id": b["person_id"], "navn": b["navn"],
                    "fornavn": fornavn, "land": collections.Counter(),
                    "funksjoner": set()})
                p["land"][land] += 1
                p["funksjoner"].add(b["funksjon"])
                par.add((fornavn, land))

    print(f"{len(personer)} personer, {len(par)} unike (fornavn, land)")
    llm_klient.nullstill_forbruk()
    svar = gjett(sorted(par), args.modell)

    # Personens kjønn avgjøres i landet vi har flest krediteringer fra. Er svarene
    # uenige mellom land, veier det landet personen oftest er registrert i.
    ut = []
    for p in personer.values():
        land = p["land"].most_common(1)[0][0]
        ut.append({"person_id": p["person_id"], "navn": p["navn"],
                   "fornavn": p["fornavn"], "land": land,
                   "kjonn": svar.get((p["fornavn"], land), "vet ikke"),
                   "funksjoner": sorted(p["funksjoner"])})

    fil = RAADATA_DIR / "ibsenstage_kjonn.json"
    fil.write_text(json.dumps({
        "hentet": date.today().isoformat(), "modell": args.modell,
        "promptversjon": PROMPTVERSJON,
        "maalt_treff_blant_besvarte": 99.9, "maalt_dekning": 92.0,
        "maalt_mot": "Wikidata P21, 2837 regissører (mal_kjonnsgjetting.py)",
        "antall": len(ut), "personer": ut,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    fordeling = collections.Counter(p["kjonn"] for p in ut)
    print(f"\n{len(ut)} personer")
    for k in ("kvinne", "mann", "vet ikke"):
        print(f"  {k:10s} {fordeling[k]:7d}  {fordeling[k] / len(ut) * 100:5.1f}%")
    print(f"\n{llm_klient.forbruk_oppsummert()}")

    print("\nKvinneandel per rolle (blant de bestemte):")
    per = collections.defaultdict(collections.Counter)
    for p in ut:
        for f in p["funksjoner"]:
            per[f][p["kjonn"]] += 1
    for f, c in sorted(per.items(), key=lambda kv: -sum(kv[1].values()))[:10]:
        bestemt = c["kvinne"] + c["mann"]
        if not bestemt:
            continue
        print(f"  {f:20s} {c['kvinne'] / bestemt * 100:5.1f}%  "
              f"(n={bestemt}, {c['vet ikke']} ubestemt)")
    print(f"\n  {fil}")


if __name__ == "__main__":
    main()
