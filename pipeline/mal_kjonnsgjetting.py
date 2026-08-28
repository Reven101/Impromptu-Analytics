"""Måler hvor godt en språkmodell gjetter kjønn fra fornavn, mot Wikidata som fasit.

Kjøring (krever hent_ibsenstage.py, hent_ibsenstage_detaljer.py og
hent_wikidata_regissorer.py først):

    python pipeline/mal_kjonnsgjetting.py
    python pipeline/mal_kjonnsgjetting.py --modell openai/gpt-oss-120b

IbsenStage registrerer ikke kjønn. Skal vi si noe om hvem som regisserer Ibsen,
må kjønn utledes fra fornavn — og da må vi kunne svare på hvor ofte utledningen
treffer. Ett samletall duger ikke: feilraten er nesten sikkert ulik i Norge og
Ungarn, og i 1890 og 2010, og det er nettopp de aksene en historie om utviklingen
ville hvile på. Derfor rapporteres treffraten per land og per tiår.

Tre valg som avgjør om målingen betyr noe:

- **Modellen får bare fornavn og land** — nøyaktig det den ville fått i drift.
  Ga vi den fullt navn her, ville vi målt noe annet enn det vi skal bruke.
- **Navn som treffer flere Wikidata-personer med ULIKT kjønn forkastes.** Treffer
  de flere med samme kjønn, beholdes de: da spiller det ingen rolle hvem av dem
  det er.
- **Fasitens egen skjevhet rapporteres.** Wikidata kjenner Max Reinhardt, men
  neppe en ungarsk regissør fra 1930-tallet. Der fasiten er tynn, sier målingen
  lite — og det skal stå i utskriften, ikke i en fotnote.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from pathlib import Path

import kontrakt  # noqa: F401
import llm_klient
# Prompt, promptversjon og oppslagsfunksjon hentes fra produksjonsscriptet.
# Målingen skal gjelde nøyaktig det som kjøres — en kopi her ville kommet i utakt
# første gang prompten endres, og da måler vi noe annet enn vi bruker.
from berik_kjonn import PROMPTVERSJON, SYSTEM, gjett  # noqa: F401
from hent_wikidata_regissorer import normaliser

BUNT = 50

RAADATA_DIR = Path(
    os.environ.get("IBSENSTAGE_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ibsenstage"
)





# ---------------------------------------------------------------- data ----

def les_regissorer() -> list[dict]:
    """Regissører fra IbsenStage, med land og år fra browse-tabellen."""
    browse = {r["hendelse_id"]: r for r in json.loads(
        (RAADATA_DIR / "ibsenstage_hendelser.json").read_text(encoding="utf-8"))["hendelser"]}
    ut = []
    with (RAADATA_DIR / "ibsenstage_detaljer.jsonl").open(encoding="utf-8") as f:
        for linje in f:
            try:
                x = json.loads(linje)
            except json.JSONDecodeError:
                continue
            b_rad = browse.get(x["hendelse_id"]) or {}
            for b in x["bidragsytere"]:
                if b["funksjon"] == "Director" and b["navn"] and b["navn"].split():
                    ut.append({
                        "navn": b["navn"],
                        "fornavn": b["navn"].split()[0],
                        "land": b_rad.get("land") or x.get("produksjonsnasjonalitet") or "?",
                        "aar": b_rad.get("aar"),
                    })
    return ut


def bygg_fasit(regissorer: list[dict]) -> tuple[list[dict], dict]:
    kilde = json.loads((RAADATA_DIR / "wikidata_regissorer.json").read_text(encoding="utf-8"))
    etter_navn: dict[str, set[str]] = collections.defaultdict(set)
    for p in kilde["personer"]:
        for n in p["navn"]:
            etter_navn[normaliser(n)].add(p["kjonn"])

    fasit, sett = [], set()
    tvetydige = 0
    for r in regissorer:
        n = normaliser(r["navn"])
        kjonn = etter_navn.get(n)
        if not kjonn:
            continue
        if len(kjonn) > 1:
            # Samme navn, ulike personer, ulikt kjønn — ingen fasit å hente.
            tvetydige += 1
            continue
        nokkel = (r["fornavn"], r["land"], r["aar"])
        if nokkel in sett:
            continue
        sett.add(nokkel)
        # hent_wikidata_regissorer.py har allerede oversatt kjønns-QID-ene til
        # «mann»/«kvinne»/«annet». Verdien brukes som den er.
        fasit.append({**r, "fasit": next(iter(kjonn))})
    # «annet» dekker ikke-binære registreringer. De har ingen kategori i denne
    # målingen og holdes utenfor fasiten framfor å presses inn i en av to bokser.
    fasit = [f for f in fasit if f["fasit"] in ("mann", "kvinne")]
    return fasit, {"wikidata": kilde["antall"], "tvetydige": tvetydige}


# -------------------------------------------------------------- modell ----



# -------------------------------------------------------------- måling ----

def _rad(navn: str, poster: list[dict]) -> str:
    n = len(poster)
    svart = [p for p in poster if p["gjett"] != "vet ikke"]
    rett = sum(1 for p in svart if p["gjett"] == p["fasit"])
    dekning = len(svart) / n * 100
    treff = rett / len(svart) * 100 if svart else 0.0
    samlet = rett / n * 100
    merke = "  <- for tynt" if n < 30 else ""
    return (f"{navn:26s} {n:5d} {dekning:8.0f}% {treff:9.1f}% {samlet:8.1f}%{merke}")


def rapport(poster: list[dict], meta: dict, modell: str, kostnad: float) -> None:
    print(f"\n{'':26s} {'n':>5} {'dekning':>8} {'av svarte':>9} {'samlet':>8}")
    print("-" * 62)
    print(_rad("ALLE", poster))

    print("\nPer land (de ti største):")
    per_land = collections.defaultdict(list)
    for p in poster:
        per_land[p["land"]].append(p)
    for land, rader in sorted(per_land.items(), key=lambda kv: -len(kv[1]))[:10]:
        print(_rad(land, rader))

    print("\nPer tiår:")
    per_tiar = collections.defaultdict(list)
    for p in poster:
        if p["aar"]:
            per_tiar[p["aar"] // 10 * 10].append(p)
    for tiar in sorted(per_tiar):
        print(_rad(f"{tiar}-tallet", per_tiar[tiar]))

    kvinner = sum(1 for p in poster if p["fasit"] == "kvinne")
    print(f"\nFasit: {len(poster)} regissører matchet mot Wikidata "
          f"({meta['wikidata']} i referansesettet, {meta['tvetydige']} forkastet som tvetydige)")
    print(f"  kvinneandel i fasiten: {kvinner / len(poster) * 100:.1f}%")
    print(f"  modell: {modell}, ${kostnad:.4f} denne kjøringen")
    print("\nMerk: fasiten er de regissørene Wikidata kjenner. De er systematisk mer")
    print("kjente og mer vesteuropeiske enn resten. Rader merket «for tynt» sier")
    print("ingenting om treffraten - de sier at fasiten mangler der.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--modell", default=llm_klient.STANDARDMODELL)
    args = p.parse_args()

    for fil in ("ibsenstage_hendelser.json", "ibsenstage_detaljer.jsonl",
                "wikidata_regissorer.json"):
        if not (RAADATA_DIR / fil).exists():
            raise SystemExit(f"mangler {RAADATA_DIR / fil}")

    regissorer = les_regissorer()
    fasit, meta = bygg_fasit(regissorer)
    print(f"{len(regissorer)} regissørkrediteringer -> {len(fasit)} med fasit fra Wikidata")
    if len(fasit) < 100:
        raise SystemExit("for få fasitpunkter til at målingen betyr noe")

    llm_klient.nullstill_forbruk()
    t0 = time.time()
    svar = gjett([(f["fornavn"], f["land"]) for f in fasit], args.modell)
    for f in fasit:
        f["gjett"] = svar[(f["fornavn"], f["land"])]
    print(f"  {time.time() - t0:.0f} s, {llm_klient.forbruk_oppsummert()}")

    rapport(fasit, meta, args.modell, llm_klient.forbruk["kostnad"])


if __name__ == "__main__":
    main()
