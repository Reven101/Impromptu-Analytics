"""Henter standpunkt, eksamen og grunnskolepoeng for ungdomsskolene i Oslo fra Udir.

Kjøring:

    python pipeline/hent_udir_ungdomsskole_oslo.py        # ~1–2 minutter

Skriver til impromptu_raadata/udir/ (eller UDIR_DIR), utenfor repoet:

    ungdomsskole_oslo.json          begge tabellene + metadata
    ungdomsskole_oslo_<tabell>.csv

Tabeller, for hele landet, Oslo og hver Oslo-skole, splittet på eierform og kjønn:

    karakterer        standpunkt og skriftlig eksamen i norsk hovedmål, matematikk
                      og engelsk, 10. trinn, 2012-13 →
    grunnskolepoeng   snitt og antall elever, 2011-12 →

Hvorfor akkurat disse fagene: skriftlig eksamen på 10. trinn er et TREKK — hver
elev kommer opp i ett av de tre. Eksamenssnittet per fag bygger derfor på om lag
en tredel av elevene, tilfeldig valgt, mens standpunkt gjelder alle. Differansen
standpunkt − eksamen er et mål på hvor «snill» skolens vurdering er, men med
støy; slå sammen fag og år før du sier noe om én skole.

Fagkodene byttes ved fagfornyelsen (LK20). Begge settene hentes:
    LK06: NOR0214, MAT0010, ENG0012     LK20: NOR0218, MAT0015, ENG0030

Samme rapport-endepunkter og feller som hent_udir_vgs_oslo.py (se den og
api-atlas/eksempler/hent_udir_statistikkbank.py). Forskjellen her: grunnskolen
har kommunenivå, så skoleradene ligger på Fag.1.<fylke>.<kommune>.<skole>, og
Oslo er både fylke (rad 3) og kommune (rad 42, EnhetID -76).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import date
from pathlib import Path

from hent_udir_vgs_oslo import (RAADATA_DIR, dimensjoner, enhetsoppslag, rapport_pivot,
                                rapportside, skoleaar_navn, tall)

KILDE_URL = "https://www.udir.no/tall-og-forskning/statistikk/statistikk-grunnskole/"
FAGKODER = {"NOR0214", "MAT0010", "ENG0012", "NOR0218", "MAT0015", "ENG0030"}
EIERFORMER = [-10, 8, 2]
KJONN = [-10, 2, 1]


def klassifiser(sti: list[str], enheter: dict[int, dict]) -> dict | None:
    """sti uten fag-prefiks: ['1'], ['1','3'], ['1','3','42'], ['1','3','42','<EnhetID>']."""
    if sti == ["1"]:
        return {"nivaa": "land", "orgnr": None}
    if len(sti) < 2 or sti[0] != "1" or sti[1] != "3":
        return None
    if len(sti) == 2:
        return None                      # Oslo fylke = Oslo kommune; kommuneraden brukes
    if len(sti) == 3:
        return {"nivaa": "kommune", "orgnr": None}
    if len(sti) == 4:
        e = enheter.get(int(sti[3]))
        if e is None:
            raise SystemExit(f"Skole-ID {sti[3]} finnes ikke i filterVerdier — har rad-id-ene endret seg?")
        return {"nivaa": "skole", "orgnr": e["kode"]}
    raise SystemExit(f"Uventet rad-sti {'.'.join(sti)}")


def smelt(hoder, rader, enheter, maal_felt, fag=None) -> list[dict]:
    ut = []
    for r in rader:
        deler = r["id"].split(".")
        if fag is not None:
            fag_id, sti = int(deler[0]), deler[1:]
            if not sti:
                continue
        else:
            fag_id, sti = None, deler
        enhet = klassifiser(sti, enheter)
        if enhet is None:
            continue
        grupper: dict[tuple, dict] = {}
        for hode, verdi in zip(hoder, r["data"]):
            maal = maal_felt.get(hode[-1])
            if maal is None:
                raise SystemExit(f"Ukjent mål {hode[-1]!r}")
            g = tuple(hode[:-1])
            post = grupper.setdefault(g, {
                "skoleaar": skoleaar_navn(g[0]), "forelopig": g[0].lower().startswith("foreløpig"),
                **dimensjoner(g[1:]), **enhet, "enhet_id": int(sti[-1]) if enhet["nivaa"] == "skole" else None,
                "navn": r["navn"].strip(), "prikket": False})
            if fag is not None:
                f = fag.get(fag_id, {})
                post |= {"fag_kode": f.get("kode"), "fag_navn": (f.get("navn") or "").strip()}
            v, p = tall(verdi)
            post[maal] = v
            post["prikket"] = post["prikket"] or p
        for post in grupper.values():
            if post["prikket"] or any(post.get(m) is not None for m in maal_felt.values()):
                ut.append(post)
    return ut


def hent_karakterer() -> list[dict]:
    side = rapportside("GSK_GSKarakterer")
    fv = enhetsoppslag(side)
    enheter = {e["id"]: e for e in fv["EnhetID"]}
    fag = {f["id"]: f for f in fv["FagID"] if f["kode"] in FAGKODER}
    if {f["kode"] for f in fag.values()} != FAGKODER:
        raise SystemExit(f"Fant ikke alle fagkodene: {FAGKODER - {f['kode'] for f in fag.values()}}")
    alle = []
    for tid in fv["TidID"]:
        filtre = {**side["filterDefaultVerdier"], "FagID": list(fag), "TidID": [tid["id"]],
                  "KaraktertypeID": [1, 3], "EierformID": EIERFORMER, "KjoennID": KJONN,
                  "VisAntallPersoner": [1], "VisKarakterfordeling": [0]}
        hoder, rader = rapport_pivot(side, filtre, "**")
        biter = smelt(hoder, rader, enheter, {"Snittkarakter": "snitt", "Antall elever": "antall"}, fag=fag)
        alle += biter
        print(f"  karakterer {tid['navn']}: {len(biter)} rader", flush=True)
    return alle


def hent_grunnskolepoeng() -> list[dict]:
    side = rapportside("GSK_GSPoeng")
    fv = enhetsoppslag(side)
    enheter = {e["id"]: e for e in fv["EnhetID"]}
    filtre = {**side["filterDefaultVerdier"], "TidID": [t["id"] for t in fv["TidID"]],
              "EierformID": EIERFORMER, "KjoennID": KJONN, "VisAntallPersoner": [1]}
    hoder, rader = rapport_pivot(side, filtre, "**")
    return smelt(hoder, rader, enheter, {"Grunnskolepoeng": "poeng", "Antall elever": "antall"})


def kontroller(k: list[dict], gp: list[dict]) -> None:
    feil = []
    snitt = [r["snitt"] for r in k if r.get("snitt") is not None]
    if min(snitt) < 1 or max(snitt) > 6:
        feil.append(f"karaktersnitt utenfor 1–6: {min(snitt)}–{max(snitt)}")
    # Skolenivå kan være ekstremt: spesialskoler (Lønnebakken) og Språksenteret for
    # nyankomne har 6–13 elever og grunnskolepoeng ned mot 3. Det er riktige tall;
    # de sorteres ut i analysen. Hard grense bare på skalaen.
    poeng = [r["poeng"] for r in gp if r.get("poeng") is not None]
    if min(poeng) < 0 or max(poeng) > 60:
        feil.append(f"grunnskolepoeng utenfor skalaen 0–60: {min(poeng)}–{max(poeng)}")
    skoler = {r["orgnr"] for r in k if r["nivaa"] == "skole"}
    if not 50 <= len(skoler) <= 130:
        feil.append(f"{len(skoler)} Oslo-skoler med karakterer — ventet 50–130")
    # Kanarifugl: Oslo-snittet i grunnskolepoeng har ligget rundt 42–44.
    oslo = [r["poeng"] for r in gp if r["nivaa"] == "kommune" and r.get("kjonn") == "Alle kjønn"
            and r.get("eierform") == "Alle eierformer" and r.get("poeng")]
    if not oslo or not all(38 <= p <= 48 for p in oslo):
        feil.append(f"Oslo-snitt grunnskolepoeng {oslo} — feil rad eller mål?")
    if feil:
        raise SystemExit("Snapshotet ble IKKE skrevet:\n  ✗ " + "\n  ✗ ".join(feil))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--ut", type=Path, default=RAADATA_DIR)
    args = p.parse_args()
    start = time.time()
    print("Karakterer 10. trinn (standpunkt og skriftlig eksamen) …")
    k = hent_karakterer()
    print("Grunnskolepoeng …")
    gp = hent_grunnskolepoeng()
    print(f"  {len(gp)} rader")

    def er_total(r):
        return r.get("eierform") == "Alle eierformer" and r.get("kjonn") == "Alle kjønn"
    print("\nKontrolltall:")
    for navn, rader in (("karakterer", k), ("grunnskolepoeng", gp)):
        sk = {r["orgnr"] for r in rader if r["nivaa"] == "skole"}
        print(f"  {navn:<16} {len(rader):>6} rader  {len(sk)} skoler")
    for r in sorted((r for r in gp if r["nivaa"] != "skole" and er_total(r)), key=lambda r: r["skoleaar"])[-4:]:
        print(f"    grunnskolepoeng {r['skoleaar']} {r['navn']:<12} {r.get('poeng')}")
    kontroller(k, gp)

    args.ut.mkdir(parents=True, exist_ok=True)
    tabeller = {"karakterer": k, "grunnskolepoeng": gp}
    pakke = {"meta": {"kilde": "Utdanningsdirektoratet, Statistikkbanken", "kilde_url": KILDE_URL,
                      "lisens": "NLOD 2.0", "dato_hentet": date.today().isoformat(),
                      "geografi": "Oslo, ungdomsskoler (+ Oslo og hele landet)",
                      "script": "pipeline/hent_udir_ungdomsskole_oslo.py"},
             "tabeller": tabeller}
    (args.ut / "ungdomsskole_oslo.json").write_text(json.dumps(pakke, ensure_ascii=False, indent=1), encoding="utf-8")
    for navn, rader in tabeller.items():
        kolonner = list(dict.fromkeys(c for r in rader for c in r))
        with open(args.ut / f"ungdomsskole_oslo_{navn}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=kolonner)
            w.writeheader()
            w.writerows(rader)
    print(f"\n✓ Skrev {args.ut / 'ungdomsskole_oslo.json'} — {time.time() - start:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
