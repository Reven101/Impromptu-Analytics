"""Bygger historien om mattekarakteren — «NYC school scores», matte-delen, på Oslo-vis.

Kjøring (etter hentescriptene):

    python pipeline/hent_udir_ungdomsskole_oslo.py
    python pipeline/hent_udir_matte.py
    python pipeline/bygg_historie_matte.py

Leser impromptu_raadata/udir og skriver historier/innhold/matte/data.json.
tekst.md skrives for hånd; scriptet stopper hvis tallene i den ikke stemmer.

Historien følger elevene fra 9. trinn til vg3:
nasjonale prøver i regning → matteeksamen på 10. trinn → valget mellom 1T og
1P → R1 og R2. Kjønn brukes bare på Oslo- og landsnivå: per skole er gutte- og
jentetallene prikket ulikt i 1P og 1T, og andelene blir skjeve.

Kontrollene som stopper bygget:
- 1T nasjonalt skal ha 8–30 000 elever hvert år (summert over fagkoder).
- Nasjonale prøver i regning, 9. trinn, skal ligge rundt 50–56 nasjonalt.
- Andelen som tar 1T skal ligge mellom 20 og 80 % for begge kjønn.
"""

from __future__ import annotations

import csv
import json
import os
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

import kontrakt
from kontrakt import INNHOLD_DIR

RAADATA = Path(os.environ.get("UDIR_DIR")
               or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "udir")
SLUG = "matte"
SISTE = "2024-25"                      # siste år med endelige tall på vgs
SKOLEAAR_1T = ["2023-24", "2024-25"]   # skolesammenligningen
MIN_ELEVER = 100


def les(navn: str) -> list[dict]:
    with open(RAADATA / navn, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def tall(s):
    return float(s) if s not in ("", None) else None


def komma(v: float, des: int = 1) -> str:
    return f"{v:.{des}f}".replace(".", ",").replace("-", "−")


def vaar(skoleaar: str) -> int:
    return int(skoleaar[:4]) + 1


# ----------------------------------------------------- 10. trinn

def eksamen_10(rader: list[dict]) -> dict:
    """(navn, kjonn, karaktertype, år) → snitt i matematikk. I overgangsår finnes
    begge fagkodene; den med flest elever er kullet."""
    beste: dict = {}
    for r in rader:
        if (r["fag_kode"] not in ("MAT0010", "MAT0015") or r["eierform"] != "Alle eierformer"
                or r["nivaa"] == "skole" or not r["snitt"] or r["forelopig"] == "True"):
            continue
        n = (r["navn"], r["kjonn"], r["karaktertype"], r["skoleaar"])
        if n not in beste or tall(r["antall"] or 0) > beste[n][1]:
            beste[n] = (tall(r["snitt"]), tall(r["antall"] or 0))
    return {n: v[0] for n, v in beste.items()}


# ------------------------------------------------ nasjonale prøver

def np_gap(rader: list[dict]) -> dict:
    """(navn, prøve) → snitt av (gutt − jente) i skalapoeng, 9. trinn, alle år."""
    v: dict = defaultdict(dict)
    for r in rader:
        if r["nivaa"] == "skole" or r["trinn"] != "9. årstrinn" or not r["skalapoeng"]:
            continue
        v[(r["navn"], r["prove"], r["skoleaar"])][r["kjonn"]] = tall(r["skalapoeng"])
    ut: dict = defaultdict(list)
    for (navn, prove, _), d in v.items():
        if "Gutt" in d and "Jente" in d:
            ut[(navn, prove)].append(d["Gutt"] - d["Jente"])
    niva = {(n, p): statistics.fmean(x["Alle kjønn"] for (n2, p2, _), x in v.items()
                                     if n2 == n and p2 == p and "Alle kjønn" in x)
            for (n, p) in ut}
    return {k: statistics.fmean(x) for k, x in ut.items()}, niva


# ----------------------------------------------------------- vgs

def kursantall(rader: list[dict]) -> dict:
    """(nivaa, orgnr/navn, år, kurs, kjønn) → elever i standpunkt, summert over fagkoder."""
    ut: dict = defaultdict(float)
    for r in rader:
        if r["karaktertype"] != "Standpunkt" or r["forelopig"] == "True" or not r["antall"]:
            continue
        hvem = r["orgnr"] if r["nivaa"] == "skole" else r["navn"]
        ut[(r["nivaa"], hvem, r["skoleaar"], r["kurs"], r["kjonn"])] += tall(r["antall"])
    return ut


def main() -> None:
    e10 = eksamen_10(les("ungdomsskole_oslo_karakterer.csv"))
    np_rader = les("matte_oslo_np.csv")
    gap_np, niva_np = np_gap(np_rader)
    vgs_rader = les("matte_oslo_vgs_matte.csv")
    k = kursantall(vgs_rader)
    navn_skole = {r["orgnr"]: r["navn"] for r in vgs_rader if r["nivaa"] == "skole"}

    # --- kontroller
    land_1t = {a: v for (niv, hvem, a, kurs, kj), v in k.items()
               if niv == "land" and kurs == "1T" and kj == "Alle kjønn"}
    if not all(8000 <= v <= 30000 for v in land_1t.values()):
        raise SystemExit(f"1T nasjonalt utenfor 8–30 000: {land_1t}")
    reg_land = niva_np[("Hele landet", "Regning")]
    if not 50 <= reg_land <= 56:
        raise SystemExit(f"Nasjonale prøver regning 9. trinn nasjonalt = {reg_land:.1f} — feil rad?")

    def andel_1t(niv, hvem, aar, kj):
        t, p = k.get((niv, hvem, aar, "1T", kj)), k.get((niv, hvem, aar, "1P", kj))
        return None if not t or not p else 100 * t / (t + p)

    aar_1t = sorted({a for (niv, _, a, kurs, _) in k if niv == "land" and kurs == "1T" and a >= "2013-14"})
    andeler = {(n, kj): [[vaar(a), round(andel_1t("land" if n == "Hele landet" else "fylke", n, a, kj), 1)]
                         for a in aar_1t if andel_1t("land" if n == "Hele landet" else "fylke", n, a, kj)]
               for n in ("Hele landet", "Oslo") for kj in ("Gutt", "Jente")}
    for (n, kj), s in andeler.items():
        if not all(20 <= y <= 80 for _, y in s):
            raise SystemExit(f"Andel 1T {n} {kj} utenfor 20–80 %: {s}")
    a1 = {(n, kj): dict(map(tuple, s))[vaar(SISTE)] for (n, kj), s in andeler.items()}
    a0 = {(n, kj): s[0][1] for (n, kj), s in andeler.items()}

    # --- jenteandel gjennom løpet, siste år
    def jenteandel(kurs, navn="Hele landet"):
        niv = "land" if navn == "Hele landet" else "fylke"
        j, g = k[(niv, navn, SISTE, kurs, "Jente")], k[(niv, navn, SISTE, kurs, "Gutt")]
        return 100 * j / (j + g)
    lop = {kurs: jenteandel(kurs) for kurs in ("1T", "R1", "R2")}
    s1_topp = max(k[("land", "Hele landet", a, "S1", "Alle kjønn")] for a in ("2019-20", "2020-21"))
    s1_na = k[("land", "Hele landet", SISTE, "S1", "Alle kjønn")]
    r1_na = k[("land", "Hele landet", SISTE, "R1", "Alle kjønn")]

    # --- 1T-andel per Oslo-skole
    skoler = []
    for o in {h for (niv, h, *_r) in k if niv == "skole"}:
        t = sum(k.get(("skole", o, a, "1T", "Alle kjønn"), 0) for a in SKOLEAAR_1T)
        p = sum(k.get(("skole", o, a, "1P", "Alle kjønn"), 0) for a in SKOLEAAR_1T)
        if t + p >= MIN_ELEVER:
            navn = (navn_skole[o].replace(" videregående Skole/ Wang Toppidrett", "")
                    .replace(" videregående skole", "").replace(" AS", ""))
            skoler.append({"navn": navn,
                           "verdi": round(100 * t / (t + p), 1), "detalj": f"{int(t)} av {int(t + p)} elever"})
    skoler.sort(key=lambda s: -s["verdi"])

    # --- 10. trinn
    ek = {n: [[vaar(a), v] for (nn, kj, kt, a), v in sorted(e10.items(), key=lambda x: x[0][3])
              if nn == n and kj == "Alle kjønn" and kt == "Skriftlig eksamen"] for n in ("Hele landet", "Oslo")}
    e_oslo_g = e10[("Oslo", "Gutt", "Skriftlig eksamen", SISTE)]
    e_oslo_j = e10[("Oslo", "Jente", "Skriftlig eksamen", SISTE)]
    s_oslo_g = e10[("Oslo", "Gutt", "Standpunkt", SISTE)]
    s_oslo_j = e10[("Oslo", "Jente", "Standpunkt", SISTE)]
    oslo_forsprang = e10[("Oslo", "Alle kjønn", "Skriftlig eksamen", SISTE)] - \
        e10[("Hele landet", "Alle kjønn", "Skriftlig eksamen", SISTE)]

    tall_i_teksten = {
        "a_jente_land": f"{komma(a1[('Hele landet', 'Jente')])} prosent av jentene",
        "a_gutt_land": f"{komma(a1[('Hele landet', 'Gutt')])} prosent av guttene",
        "a_jente_oslo": f"{komma(a1[('Oslo', 'Jente')])} prosent",
        "a_gutt_oslo": f"{komma(a1[('Oslo', 'Gutt')])} prosent",
        "a0_jente": f"{komma(a0[('Hele landet', 'Jente')])} prosent",
        "np_reg_oslo": f"{komma(gap_np[('Oslo', 'Regning')])} skalapoeng",
        "np_les_oslo": f"{komma(-gap_np[('Oslo', 'Lesing')])} skalapoeng",
        "e_oslo": f"{komma(e_oslo_j)} mot {komma(e_oslo_g)}",
        "forsprang": f"{komma(oslo_forsprang)} karakterpoeng",
        "lop": f"{komma(lop['1T'])}, {komma(lop['R1'])} og {komma(lop['R2'])} prosent",
        "s1": f"fra {int(s1_topp):,} til {int(s1_na):,}".replace(",", " "),
    }

    data = {
        "meta": {
            "tittel": "Like gode i matte, ulike valg",
            "kilde": "Utdanningsdirektoratet, Statistikkbanken",
            "kilde_url": "https://www.udir.no/tall-og-forskning/statistikk/",
            "dato_hentet": date.today().isoformat(),
            "geografi": "Oslo og hele landet",
            "enhet": "prosent",
            "oppdateringsfrekvens": "årlig",
            "beskrivelse": (f"Jentene og guttene i Oslo får samme karakter på matteeksamen i 10. klasse. Året etter "
                            f"velger {komma(a1[('Oslo', 'Jente')])} prosent av jentene teoretisk matte, mot "
                            f"{komma(a1[('Oslo', 'Gutt')])} prosent av guttene."),
            "utkast": True,
        },
        "visninger": {
            "hero": {
                "type": "hero",
                "eyebrow": "Matematikk i Oslo",
                "sporsmal": "Hvem velger teoretisk matte — når alle er like gode?",
                "rader": [
                    {"etikett": "jenter og gutter, matteeksamen 10. trinn", "verdi": f"{komma(e_oslo_j)} / {komma(e_oslo_g)}",
                     "detalj": f"Oslo {SISTE}, snittkarakter"},
                    {"etikett": "av jentene velger teoretisk matte", "verdi": f"{komma(a1[('Oslo', 'Jente')])} %",
                     "detalj": f"Oslo {SISTE}, 1T av 1T + 1P"},
                    {"etikett": "av guttene", "verdi": f"{komma(a1[('Oslo', 'Gutt')])} %",
                     "detalj": "samme år, samme byen"},
                ],
                "fotnote": "Studieforberedende utdanningsprogram, vg1.",
            },
            "eksamen_10": {
                "type": "tidslinje",
                "tittel": f"Oslo ligger {komma(oslo_forsprang)} karakterpoeng over landet i matte",
                "undertekst": ("Skriftlig eksamen i matematikk, 10. trinn, snittkarakter. Eksamen avlyst 2020–2022; "
                               "linjene trekkes over hullet."),
                "enhet": "karakter",
                "x_navn": "Skoleår (vår)",
                "serier": [{"navn": n, "punkter": p} for n, p in ek.items()],
            },
            "tre_malinger": {
                "type": "kortgalleri",
                "tittel": "Tre målinger, tre svar",
                "undertekst": "Gutter og jenter i Oslo, matematikk",
                "kort": [
                    {"overtittel": "Nasjonale prøver i regning, 9. trinn",
                     "verdi": f"Gutter +{komma(gap_np[('Oslo', 'Regning')])}",
                     "detalj": f"skalapoeng, snitt 2022–26 (lesing: jenter +{komma(-gap_np[('Oslo', 'Lesing')])})"},
                    {"overtittel": "Skriftlig eksamen, 10. trinn",
                     "verdi": f"{komma(e_oslo_j)} / {komma(e_oslo_g)}", "detalj": f"jenter / gutter, {SISTE}"},
                    {"overtittel": "Standpunkt, 10. trinn",
                     "verdi": f"{komma(s_oslo_j)} / {komma(s_oslo_g)}", "detalj": f"jenter / gutter, {SISTE}"},
                ],
            },
            "valget": {
                "type": "tidslinje",
                "tittel": "Jentene velger bort teoretisk matte",
                "undertekst": "Andel som tar 1T av alle som tar 1T eller 1P, studieforberedende vg1",
                "enhet": "prosent",
                "x_navn": "Skoleår (vår)",
                "serier": [{"navn": f"{ {'Gutt': 'Gutter', 'Jente': 'Jenter'}[kj]}, {'landet' if n == 'Hele landet' else n}",
                            "punkter": s}
                           for (n, kj), s in andeler.items()],
            },
            "skolene": {
                "type": "rangering",
                "tittel": "Fra 4 til 75 prosent: skolene i Oslo",
                "undertekst": f"Andel som tar 1T av 1T + 1P, skoleårene {SKOLEAAR_1T[0][:4]}–{vaar(SKOLEAAR_1T[-1])}, skoler med minst {MIN_ELEVER} elever",
                "enhet": "prosent",
                "rader": skoler,
            },
            "lekkasjen": {
                "type": "rangering",
                "tittel": "Jentene forsvinner på veien",
                "undertekst": f"Jentenes andel av elevene i hvert mattekurs, hele landet {SISTE}",
                "enhet": "prosent",
                "sorter": False,
                "rader": [{"navn": "1T (vg1)", "verdi": round(lop["1T"], 1)},
                          {"navn": "R1 (vg2)", "verdi": round(lop["R1"], 1)},
                          {"navn": "R2 (vg3)", "verdi": round(lop["R2"], 1)}],
            },
        },
    }
    # Tittelen på skolefiguren må følge dataene
    lav, hoy = skoler[-1]["verdi"], skoler[0]["verdi"]
    data["visninger"]["skolene"]["tittel"] = f"Fra {round(lav)} til {round(hoy)} prosent: skolene i Oslo"

    feil = kontrakt.valider_snapshot(data, SLUG)
    if feil:
        raise SystemExit("\n".join(feil))
    tekstfil = INNHOLD_DIR / SLUG / "tekst.md"
    if tekstfil.exists():
        tekst = tekstfil.read_text(encoding="utf-8").replace("\xa0", " ")
        mangler = {n: v for n, v in tall_i_teksten.items() if v not in tekst}
        if mangler:
            raise SystemExit("tekst.md stemmer ikke med tallene. Finner ikke:\n  "
                             + "\n  ".join(f"{n}: «{v}»" for n, v in mangler.items()))
    ut = INNHOLD_DIR / SLUG
    ut.mkdir(parents=True, exist_ok=True)
    (ut / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Tall teksten må inneholde:", *[f"  {n}: {v}" for n, v in tall_i_teksten.items()], sep="\n")
    print(f"Skoler: {len(skoler)}, fra {lav} til {hoy} %")
    print(f"✓ Skrev {ut / 'data.json'}. Husk: python pipeline/bygg_manifest.py")


if __name__ == "__main__":
    main()
