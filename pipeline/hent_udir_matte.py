"""Henter mattetall for mattehistorien: matematikkvalg på vgs og nasjonale prøver.

Kjøring:

    python pipeline/hent_udir_matte.py        # ~1 minutt

Skriver til impromptu_raadata/udir/ (eller UDIR_DIR), utenfor repoet:

    matte_oslo.json, matte_oslo_<tabell>.csv

Tabeller, for hele landet, Oslo og hver Oslo-skole, splittet på kjønn:

    vgs_matte   standpunkt og skriftlig eksamen (snitt og antall elever) i
                matematikk på studieforberedende: 1P/1T (vg1) og R1, R2, S1, S2,
                alle læreplankoder, 2007-08 →
    np          nasjonale prøver 8. og 9. trinn i regning, lesing og engelsk:
                skalapoeng, usikkerhet og antall elever, 2022-23 →

Antall elever i STANDPUNKT er antall som tok faget. Det er grunnlaget for å
regne ut hvor mange som velger teoretisk matte (1T) framfor praktisk (1P).

Feller:
- Matematikk skifter kode ved hver læreplan: 1P/1T er MAT1002/MAT1007 (til
  2009), MAT1011/MAT1013 (LK06) og MAT1019/MAT1021 (LK20); R1/R2/S1/S2 er
  REA3022–3028 (LK06) og REA3056–3062 (LK20). Byggescriptet skjøter på kurs.
- Kjønnstall per skole er prikket der gruppene er små, og prikkingen treffer
  ulikt i 1P og 1T. Andel 1T per skole og kjønn blir da skjev — bruk kjønn
  bare på Oslo- og landsnivå. Kontrolltallene viser hvor mange celler som er prikket.
- Nasjonale prøver fikk ny skala i 2022 (snitt 50). Eldre år finnes ikke i
  denne rapporten og kan ikke sammenlignes.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import date
from pathlib import Path

import hent_udir_ungdomsskole_oslo as gsk
from hent_udir_vgs_oslo import (RAADATA_DIR, enhetsoppslag, rapport_pivot, rapportside, smelt)

KURS = {
    "1P": {"MAT1002", "MAT1011", "MAT1019"},
    "1T": {"MAT1007", "MAT1013", "MAT1021"},
    "R1": {"REA3022", "REA3056"}, "R2": {"REA3024", "REA3058"},
    "S1": {"REA3026", "REA3060"}, "S2": {"REA3028", "REA3062"},
}
KODE_TIL_KURS = {kode: kurs for kurs, koder in KURS.items() for kode in koder}
KJONN = [-10, 2, 1]


def hent_vgs_matte() -> list[dict]:
    side = rapportside("VGO_VGOkarakterer")
    fv = enhetsoppslag(side)
    enheter = {e["id"]: e for e in fv["EnhetID"]}
    fag = {f["id"]: f for f in fv["FagID"] if f["kode"] in KODE_TIL_KURS}
    mangler = set(KODE_TIL_KURS) - {f["kode"] for f in fag.values()}
    if mangler:
        raise SystemExit(f"Fant ikke fagkodene {sorted(mangler)} i filterVerdier — har Udir endret dem?")
    alle = []
    for tid in fv["TidID"]:
        filtre = {**side["filterDefaultVerdier"], "FagID": list(fag), "TidID": [tid["id"]],
                  "KaraktertypeID": [1, 3], "EierformID": [-10], "KjoennID": KJONN,
                  "UtdanningsprogramvariantID": [-10], "VisAntallPersoner": [1], "VisKarakterfordeling": [0]}
        hoder, rader = rapport_pivot(side, filtre, "**")
        biter = smelt(hoder, rader, enheter, {"Snittkarakter": "snitt", "Antall elever": "antall"},
                      fagprefiks=True, fag=fag)
        for b in biter:
            b["kurs"] = KODE_TIL_KURS.get(b["fag_kode"])
        alle += [b for b in biter if b["kurs"]]
        print(f"  vgs matte {tid['navn']}: {len(biter)} rader", flush=True)
    return alle


def hent_np() -> list[dict]:
    side = rapportside("GSK_NP_Geografisk")
    fv = enhetsoppslag(side)
    enheter = {e["id"]: e for e in fv["EnhetID"]}
    alle = []
    for aar in fv["SkoleAarID"]:
        filtre = {**side["filterDefaultVerdier"], "SkoleAarID": [aar["id"]], "TrinnID": [7, 8],
                  "KjoennID": KJONN, "EierformID": [-10], "ProevetypeID": [1, 2, 3],
                  "VisAntallRaderDeltatt": [1], "VisMestringsnivaafordeling": [0],
                  "VisDeltakelsestatusfordeling": [0], "VisMaaltall": [0]}
        hoder, rader = rapport_pivot(side, filtre, "**")
        # Prøvetype og trinn står i kolonnehodet; dimensjoner() i vgs-scriptet kjenner dem ikke.
        biter = gsk_smelt_np(hoder, rader, enheter)
        alle += biter
        print(f"  nasjonale prøver {aar['navn']}: {len(biter)} rader", flush=True)
    return alle


PROVER = {"Regning", "Lesing", "Engelsk"}
TRINN = {"8. årstrinn", "9. årstrinn"}


def gsk_smelt_np(hoder, rader, enheter) -> list[dict]:
    from hent_udir_vgs_oslo import skoleaar_navn, tall
    maal = {"Skalapoeng": "skalapoeng", "Usikkerhet": "usikkerhet", "Antall elever deltatt": "antall"}
    ut = []
    for r in rader:
        enhet = gsk.klassifiser(r["id"].split("."), enheter)
        if enhet is None:
            continue
        grupper: dict[tuple, dict] = {}
        for hode, verdi in zip(hoder, r["data"]):
            if hode[-1] not in maal:
                raise SystemExit(f"Ukjent mål {hode[-1]!r} i nasjonale prøver")
            g = tuple(hode[:-1])
            post = grupper.get(g)
            if post is None:
                post = {"skoleaar": skoleaar_navn(g[0]), **enhet, "navn": r["navn"].strip(), "prikket": False}
                for etikett in g[1:]:
                    if etikett in PROVER:
                        post["prove"] = etikett
                    elif etikett in TRINN:
                        post["trinn"] = etikett
                    elif etikett in ("Alle kjønn", "Gutt", "Jente"):
                        post["kjonn"] = etikett
                    elif etikett != "Alle eierformer":
                        raise SystemExit(f"Ukjent etikett {etikett!r} i nasjonale prøver")
                grupper[g] = post
            v, p = tall(verdi)
            post[maal[hode[-1]]] = v
            post["prikket"] = post["prikket"] or p
        ut += [p for p in grupper.values() if p["prikket"] or p.get("skalapoeng") is not None]
    return ut


def kontroller(vgs: list[dict], np_: list[dict]) -> None:
    feil = []
    # Summer over koder per år: i overgangsår ligger en rest på den gamle koden
    # (f.eks. 78 elever), og den alene er ikke et kull.
    land_1t: dict[str, float] = {}
    for r in vgs:
        if (r["nivaa"] == "land" and r["kurs"] == "1T" and r["kjonn"] == "Alle kjønn"
                and r["karaktertype"] == "Standpunkt" and r.get("antall")):
            land_1t[r["skoleaar"]] = land_1t.get(r["skoleaar"], 0) + r["antall"]
    if not land_1t or not all(8000 <= v <= 30000 for v in land_1t.values()):
        feil.append(f"elever i 1T nasjonalt utenfor 8–30 000: {land_1t}")
    reg = [r["skalapoeng"] for r in np_ if r["nivaa"] == "land" and r.get("prove") == "Regning"
           and r.get("kjonn") == "Alle kjønn" and r.get("skalapoeng")]
    if not reg or not all(45 <= v <= 55 for v in reg):
        feil.append(f"nasjonalt snitt regning {reg} — ny skala har snitt ~50")
    if feil:
        raise SystemExit("Snapshotet ble IKKE skrevet:\n  ✗ " + "\n  ✗ ".join(feil))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--ut", type=Path, default=RAADATA_DIR)
    args = p.parse_args()
    start = time.time()
    print("Matematikk på vgs (1P/1T, R1/R2, S1/S2) …")
    vgs = hent_vgs_matte()
    print("Nasjonale prøver 8. og 9. trinn …")
    np_ = hent_np()
    prikk = sum(1 for r in vgs if r["nivaa"] == "skole" and r["kjonn"] != "Alle kjønn" and r["prikket"])
    print(f"\nKontrolltall: vgs {len(vgs)} rader ({prikk} prikkede skole×kjønn-celler), np {len(np_)} rader")
    kontroller(vgs, np_)
    args.ut.mkdir(parents=True, exist_ok=True)
    tabeller = {"vgs_matte": vgs, "np": np_}
    pakke = {"meta": {"kilde": "Utdanningsdirektoratet, Statistikkbanken", "lisens": "NLOD 2.0",
                      "kilde_url": "https://www.udir.no/tall-og-forskning/statistikk/",
                      "dato_hentet": date.today().isoformat(), "script": "pipeline/hent_udir_matte.py"},
             "tabeller": tabeller}
    (args.ut / "matte_oslo.json").write_text(json.dumps(pakke, ensure_ascii=False, indent=1), encoding="utf-8")
    for navn, rader in tabeller.items():
        kolonner = list(dict.fromkeys(c for r in rader for c in r))
        with open(args.ut / f"matte_oslo_{navn}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=kolonner)
            w.writeheader()
            w.writerows(rader)
    print(f"✓ Skrev {args.ut / 'matte_oslo.json'} — {time.time() - start:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
