"""Bygger historien «Standpunktet som følger skolen» — standpunkt mot eksamen i Oslo.

Kjøring (etter hentescriptene):

    python pipeline/hent_udir_ungdomsskole_oslo.py
    python pipeline/hent_udir_vgs_oslo.py
    python pipeline/bygg_historie_standpunkt.py

Leser rådata fra impromptu_raadata/udir (eller UDIR_DIR) og skriver
historier/innhold/standpunkt/data.json. tekst.md skrives for hånd; scriptet
sjekker at tallene i den stemmer med det som regnes ut her, og stopper ellers.

Målet er **relativ slakkhet**: skolens gap mellom standpunkt og skriftlig eksamen,
minus landets gap i samme fag og år. Positivt = skolen setter høyere standpunkt
enn eksamen tilsier, sammenlignet med resten av landet.

Tre ting historien hviler på, og som scriptet derfor feiler hardt på:

1. **Forskjellene mellom skolene er større enn trekkstøyen.** Skriftlig eksamen på
   10. trinn er trekk — om lag en tredel av elevene per fag — så eksamenssnittet
   har tilfeldig variasjon. Reliabiliteten (andel av variansen som ikke er støy)
   må være over 0,5, ellers er det ingen skoleforskjell å skrive om.
2. **Slakkhet er stabil over tid.** Samme skole i LK06 (2015-19) og LK20 (2022-25)
   må korrelere positivt.
3. **Nevneren stemmer med et kjent tall.** Oslos grunnskolepoeng skal ligge rundt 44.

Justering for elevgrunnlag: svakere elever får gjerne litt mer i standpunkt
uansett skole. Slakkheten i LK20 justeres derfor for skolens eksamensnivå i LK06.
Nivået hentes fra en ANNEN periode med vilje: eksamenssnittet står i både gapet og
nivået, og tilfeldig svak eksamen ville ellers gitt en mekanisk sammenheng.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

import kontrakt
from kontrakt import INNHOLD_DIR

RAADATA = Path(os.environ.get("UDIR_DIR")
               or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "udir")
SLUG = "standpunkt"
LK06 = ["2015-16", "2016-17", "2017-18", "2018-19"]
LK20 = ["2022-23", "2023-24", "2024-25"]
MIN_EKSAMEN = 60          # eksamensbesvarelser per skole i perioden
SD_EKSAMEN = 1.1          # omtrentlig sd for eksamenskarakterer (støyanslag)
ANTALL_NAVNGITT = 8


# ------------------------------------------------------------ hjelpere

def les(navn: str) -> list[dict]:
    with open(RAADATA / navn, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def tall(s: str) -> float | None:
    return float(s) if s not in ("", None) else None


def komma(v: float, des: int = 1) -> str:
    return f"{v:.{des}f}".replace(".", ",").replace("-", "−")


def pearson(x: list[float], y: list[float]) -> float:
    mx, my = statistics.fmean(x), statistics.fmean(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return sxy / math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))


def ols(y: list[float], xs: list[list[float]], w: list[float] | None = None) -> list[float]:
    """Vektet minste kvadrater med konstantledd. Returnerer [konstant, b1, b2, ...]."""
    w = w or [1.0] * len(y)
    X = [[1.0, *rad] for rad in zip(*xs)]
    k = len(X[0])
    A = [[sum(wi * xi[a] * xi[b] for wi, xi in zip(w, X)) for b in range(k)] for a in range(k)]
    v = [sum(wi * xi[a] * yi for wi, xi, yi in zip(w, X, y)) for a in range(k)]
    for i in range(k):                      # Gauss-eliminasjon, små systemer
        p = A[i][i]
        for j in range(i + 1, k):
            f = A[j][i] / p
            A[j] = [aj - f * ai for aj, ai in zip(A[j], A[i])]
            v[j] -= f * v[i]
    b = [0.0] * k
    for i in reversed(range(k)):
        b[i] = (v[i] - sum(A[i][j] * b[j] for j in range(i + 1, k))) / A[i][i]
    return b


# ------------------------------------------------------ ungdomsskolen

def gap_rader(rader: list[dict]) -> dict:
    """(nivaa, orgnr, år, fag) → {stp, eks, n_eks, navn} for alle eierformer og kjønn."""
    ut: dict = defaultdict(dict)
    for r in rader:
        if r["eierform"] != "Alle eierformer" or r["kjonn"] != "Alle kjønn" or r["forelopig"] == "True":
            continue
        n = (r["nivaa"], r["orgnr"], r["skoleaar"], r["fag_kode"])
        d = ut[n]
        d["navn"] = r["navn"]
        if r["karaktertype"] == "Standpunkt":
            d["stp"] = tall(r["snitt"])
        elif r["karaktertype"] == "Skriftlig eksamen":
            d["eks"], d["n_eks"] = tall(r["snitt"]), tall(r["antall"])
    return {n: d for n, d in ut.items() if d.get("stp") is not None and d.get("eks") is not None and d.get("n_eks")}


def per_skole(g: dict, aar: list[str]) -> dict[str, dict]:
    land = {(a, f): d for (niv, _, a, f), d in g.items() if niv == "land"}
    sum_w: dict = defaultdict(lambda: {"n": 0.0, "gap": 0.0, "eks": 0.0, "navn": ""})
    for (niv, orgnr, a, f), d in g.items():
        if niv != "skole" or a not in aar or (a, f) not in land:
            continue
        L = land[(a, f)]
        rel_gap = (d["stp"] - d["eks"]) - (L["stp"] - L["eks"])
        s = sum_w[orgnr]
        s["n"] += d["n_eks"]
        s["gap"] += rel_gap * d["n_eks"]
        s["eks"] += (d["eks"] - L["eks"]) * d["n_eks"]
        s["navn"] = d["navn"]
    return {o: {"navn": s["navn"], "n": s["n"], "rel_gap": s["gap"] / s["n"], "rel_eks": s["eks"] / s["n"],
                "se": SD_EKSAMEN / math.sqrt(s["n"])}
            for o, s in sum_w.items() if s["n"] >= MIN_EKSAMEN}


def oslo_mot_landet(g: dict) -> dict[str, list]:
    """Gap standpunkt − eksamen per år, snitt av de tre fagene, for Oslo og landet."""
    per: dict = defaultdict(list)
    for (niv, _, a, f), d in g.items():
        if niv in ("land", "kommune"):
            per[(niv, a)].append(d["stp"] - d["eks"])
    serier = {}
    for niv, navn in (("land", "Hele landet"), ("kommune", "Oslo")):
        serier[navn] = sorted([int(a[:4]) + 1, round(statistics.fmean(v), 2)]
                              for (n_, a), v in per.items() if n_ == niv and len(v) == 3)
    return serier


def grunnskolepoeng() -> tuple[dict[str, float], dict[str, float]]:
    """Relativt grunnskolepoeng (skole − landet) per skole, snitt over LK20; og Oslo per år."""
    rader = [r for r in les("ungdomsskole_oslo_grunnskolepoeng.csv")
             if r["eierform"] == "Alle eierformer" and r["kjonn"] == "Alle kjønn"]
    land = {r["skoleaar"]: tall(r["poeng"]) for r in rader if r["nivaa"] == "land"}
    oslo = {r["skoleaar"]: tall(r["poeng"]) for r in rader if r["nivaa"] == "kommune"}
    rel: dict = defaultdict(list)
    for r in rader:
        if r["nivaa"] == "skole" and r["skoleaar"] in LK20 and r["poeng"]:
            rel[r["orgnr"]].append(tall(r["poeng"]) - land[r["skoleaar"]])
    return {o: statistics.fmean(v) for o, v in rel.items()}, oslo


# ----------------------------------------------------------- vgs

def vgs_norsk() -> dict:
    """Norsk hovedmål vg3 (obligatorisk eksamen): gap per skole, og stabilitet over tid."""
    g: dict = defaultdict(dict)
    for r in les("vgs_oslo_karakterer.csv"):
        if (r["eierform"] != "Alle eierformer" or r["kjonn"] != "Alle kjønn" or r["forelopig"] == "True"
                or r["fag_kode"] not in ("NOR1211", "NOR1267") or r["skoleaar"] in ("2019-20", "2022-23")):
            continue
        d = g[(r["nivaa"], r["orgnr"], r["skoleaar"])]
        d["navn"] = r["navn"]
        if r["karaktertype"] == "Standpunkt":
            d["stp"] = tall(r["snitt"])
        elif r["karaktertype"] == "Skriftlig eksamen":
            d["eks"], d["n"] = tall(r["snitt"]), tall(r["antall"])
    g = {k: d for k, d in g.items() if d.get("stp") and d.get("eks") and (d.get("n") or 0) >= 10}
    land = {a: d["stp"] - d["eks"] for (niv, _, a), d in g.items() if niv == "land"}
    oslo = {a: d["stp"] - d["eks"] for (niv, _, a), d in g.items() if niv == "fylke"}

    def periode(aar):
        s: dict = defaultdict(lambda: [0.0, 0.0])
        for (niv, o, a), d in g.items():
            if niv == "skole" and a in aar and a in land:
                s[o][0] += ((d["stp"] - d["eks"]) - land[a]) * d["n"]
                s[o][1] += d["n"]
        return {o: v / n for o, (v, n) in s.items() if n >= 100}
    A = periode(["2013-14", "2014-15", "2015-16", "2016-17", "2017-18", "2018-19"])
    B = periode(["2023-24", "2024-25"])
    felles = sorted(set(A) & set(B))
    return {"r": pearson([A[o] for o in felles], [B[o] for o in felles]), "n": len(felles),
            "sd": statistics.stdev(B.values()), "skoler": len(B),
            "gap_oslo": statistics.fmean(oslo[a] for a in ("2023-24", "2024-25")),
            "gap_land": statistics.fmean(land[a] for a in ("2023-24", "2024-25"))}


# ---------------------------------------------------------- bygg

def main() -> None:
    g = gap_rader(les("ungdomsskole_oslo_karakterer.csv"))
    A, B = per_skole(g, LK06), per_skole(g, LK20)

    # Port 1: reelle skoleforskjeller
    rel = [s["rel_gap"] for s in B.values()]
    var = statistics.variance(rel)
    reliabilitet = (var - statistics.fmean(s["se"] ** 2 for s in B.values())) / var
    if reliabilitet < 0.5:
        raise SystemExit(f"Reliabilitet {reliabilitet:.2f} < 0,5 — skoleforskjellene er mest støy. "
                         "Historien har ikke grunnlag; ikke publiser.")

    # Port 2: stabilitet over tid
    felles = sorted(set(A) & set(B))
    r_stab = pearson([A[o]["rel_gap"] for o in felles], [B[o]["rel_gap"] for o in felles])
    if r_stab <= 0:
        raise SystemExit(f"Slakkhet LK06→LK20 korrelerer {r_stab:.2f} — ikke en egenskap ved skolen.")

    # Port 3: kjent nevner
    rel_gsp, oslo_gsp = grunnskolepoeng()
    if not 43 <= oslo_gsp["2024-25"] <= 46:
        raise SystemExit(f"Oslos grunnskolepoeng 2024-25 = {oslo_gsp['2024-25']} — ventet ~44. Feil rad?")

    # Justering for elevgrunnlag: rel_gap(LK20) ~ rel_eks(LK06)
    k0, k1 = ols([B[o]["rel_gap"] for o in felles], [[A[o]["rel_eks"] for o in felles]])
    for o in felles:
        B[o]["justert"] = B[o]["rel_gap"] - (k0 + k1 * A[o]["rel_eks"])
    just = [B[o]["justert"] for o in felles]
    desiler = statistics.quantiles(just, n=10, method="inclusive")
    spenn = desiler[8] - desiler[0]

    # Slår slakkheten ut i grunnskolepoeng? rel_gsp ~ rel_eks + rel_gap (LK20, vektet)
    m = [o for o in B if o in rel_gsp]
    _, b_eks, b_gap = ols([rel_gsp[o] for o in m], [[B[o]["rel_eks"] for o in m], [B[o]["rel_gap"] for o in m]],
                          [B[o]["n"] for o in m])
    spenn_gsp = b_gap * spenn
    oslo_rel = statistics.fmean(
        (g[("kommune", "", a, f)]["stp"] - g[("kommune", "", a, f)]["eks"])
        - (g[("land", "", a, f)]["stp"] - g[("land", "", a, f)]["eks"])
        for a in LK20 for f in ("NOR0218", "MAT0015", "ENG0030"))
    vgs = vgs_norsk()

    # Hvem navngis: endene, og bare der 95 %-usikkerheten fra trekket ikke krysser null
    rangert = sorted(felles, key=lambda o: B[o]["justert"])
    snill = [o for o in reversed(rangert) if B[o]["justert"] - 1.96 * B[o]["se"] > 0][:ANTALL_NAVNGITT]
    streng = [o for o in rangert if B[o]["justert"] + 1.96 * B[o]["se"] < 0][:ANTALL_NAVNGITT]

    # Vises i grunnskolepoeng (slakkhet × effekten på grunnskolepoeng): det er poengene
    # elevene konkurrerer med, og rangering tegner uansett ikke skalaer under 1.
    def rad(o, fortegn):
        return {"navn": B[o]["navn"].replace(" skole", ""),
                "verdi": round(fortegn * B[o]["justert"] * b_gap, 1),
                "detalj": f"{komma(fortegn * B[o]['justert'], 2)} karakterpoeng; "
                          f"{int(B[o]['n'])} eksamensbesvarelser 2022–25"}

    serier = oslo_mot_landet(g)
    oslo_s, land_s = dict(map(tuple, serier["Oslo"])), dict(map(tuple, serier["Hele landet"]))
    aar_felles = sorted(set(oslo_s) & set(land_s))
    strengere = sum(oslo_s[a] < land_s[a] for a in aar_felles)
    ORD = {6: "seks", 7: "sju", 8: "åtte", 9: "ni", 10: "ti", 11: "elleve", 12: "tolv"}
    if strengere == len(aar_felles):
        aar_setning = f"alle de {ORD.get(strengere, strengere)} eksamensårene siden {aar_felles[0]}"
    else:
        aar_setning = f"{strengere} av {len(aar_felles)} eksamensår siden {aar_felles[0]}"
    tall_i_teksten = {
        "aar": aar_setning,
        "spenn_gsp": f"{komma(spenn_gsp)} grunnskolepoeng",
        "spenn": f"{komma(spenn)} karakterpoeng",
        "oslo_rel": f"{komma(abs(oslo_rel), 2)} karakterpoeng",
        "skoler": f"{len(B)} ungdomsskoler",
        "reliabilitet": f"{round(reliabilitet * 100)} prosent",
        "b_gap": f"{komma(b_gap / 10, 2)} grunnskolepoeng",
        "r_stab": f"{komma(r_stab, 2)}",
        "vgs_r": f"{komma(vgs['r'], 2)}",
    }

    data = {
        "meta": {
            "tittel": "Standpunktet som følger skolen",
            "kilde": "Utdanningsdirektoratet, Statistikkbanken",
            "kilde_url": "https://www.udir.no/tall-og-forskning/statistikk/statistikk-grunnskole/",
            "dato_hentet": date.today().isoformat(),
            "geografi": "Oslo, ungdomsskoler og videregående skoler",
            "enhet": "karakterpoeng",
            "oppdateringsfrekvens": "årlig",
            "beskrivelse": (f"Samme eksamen, ulikt standpunkt. Mellom en snill og en streng ungdomsskole i Oslo "
                            f"ligger om lag {komma(spenn_gsp)} grunnskolepoeng — og det er de poengene "
                            f"elevene konkurrerer med om plass på videregående."),
            "utkast": True,
        },
        "visninger": {
            "hero": {
                "type": "hero",
                # Ett tall, sagt som en setning. Den første versjonen hadde tre tall
                # med fagord (persentil, karakterpoeng, eksamensbesvarelser) og
                # skremte bort lesere før de kom til teksten som forklarer dem.
                "eyebrow": "Ungdomsskolene i Oslo",
                "sporsmal": "To elever gjør det like godt på eksamen. Får de samme standpunkt?",
                "rader": [
                    {"etikett": "grunnskolepoeng kan skille dem",
                     "verdi": f"Nesten {round(spenn_gsp)}",
                     "detalj": "bare fordi de går på hver sin ungdomsskole"},
                ],
                "fotnote": (f"Forskjellen mellom en romslig og en streng skole blant {len(B)} ungdomsskoler "
                            "i Oslo, 2022–25. Grunnskolepoengene avgjør hvem som kommer inn hvor på videregående."),
            },
            "oslo_landet": {
                "type": "tidslinje",
                "tittel": f"Oslo har mindre gap enn landet i {aar_setning}",
                "undertekst": ("Standpunkt minus skriftlig eksamen, 10. trinn, snitt av norsk, matematikk og "
                               "engelsk. Eksamen ble avlyst 2020–2022; linjene trekkes over hullet."),
                "enhet": "karakterpoeng",
                "x_navn": "Skoleår (vår)",
                "serier": [{"navn": n, "punkter": p} for n, p in serier.items()],
            },
            "snillest": {
                "type": "rangering",
                "tittel": "Snillest: standpunkt høyere enn eksamen tilsier",
                "undertekst": ("Omtrentlige grunnskolepoeng over det elevgrunnlaget tilsier, sammenlignet med en typisk "
                               "Oslo-skole. Bare skoler der usikkerheten ikke krysser null."),
                "enhet": "grunnskolepoeng",
                "rader": [rad(o, 1) for o in snill],
            },
            "strengest": {
                "type": "rangering",
                "tittel": "Strengest: standpunkt lavere enn eksamen tilsier",
                "undertekst": ("Omtrentlige grunnskolepoeng under det elevgrunnlaget tilsier, sammenlignet med en typisk "
                               "Oslo-skole. Bare skoler der usikkerheten ikke krysser null."),
                "enhet": "grunnskolepoeng",
                "rader": [rad(o, -1) for o in streng],
            },
            "vgs": {
                "type": "kortgalleri",
                "tittel": "På videregående flytter det seg",
                "undertekst": "Norsk hovedmål vg3, skriftlig eksamen (obligatorisk for alle) mot standpunkt",
                "kort": [
                    {"overtittel": "Gap i Oslo 2023–25", "verdi": komma(vgs["gap_oslo"], 2),
                     "detalj": f"landet: {komma(vgs['gap_land'], 2)} karakterpoeng"},
                    {"overtittel": "Spredning mellom skolene", "verdi": komma(vgs["sd"], 2),
                     "detalj": f"standardavvik, {vgs['skoler']} skoler"},
                    {"overtittel": "Stabilitet 2013–19 → 2023–25", "verdi": komma(vgs["r"], 2),
                     "detalj": f"korrelasjon mellom periodene, {vgs['n']} skoler"},
                ],
            },
            "metode": {
                "type": "kortgalleri",
                "tittel": "Hvor sikkert er dette?",
                "undertekst": "Kontrollene historien må bestå for å bygges",
                "kort": [
                    {"overtittel": "Ikke støy", "verdi": f"{round(reliabilitet * 100)} %",
                     "detalj": "av skoleforskjellene er større enn eksamenstrekket forklarer"},
                    {"overtittel": "Stabilt over tid", "verdi": komma(r_stab, 2),
                     "detalj": f"korrelasjon LK06 → LK20, {len(felles)} skoler"},
                    {"overtittel": "Per 0,1 i slakkhet", "verdi": f"+{komma(b_gap / 10, 2)}",
                     "detalj": "grunnskolepoeng, ved likt eksamensnivå"},
                ],
            },
        },
    }

    feil = kontrakt.valider_snapshot(data, SLUG)
    if feil:
        raise SystemExit("\n".join(feil))

    # Brødteksten skal ikke drifte fra tallene (se CLAUDE.md).
    tekstfil = INNHOLD_DIR / SLUG / "tekst.md"
    if tekstfil.exists():
        tekst = tekstfil.read_text(encoding="utf-8").replace(" ", " ").replace("\xa0", " ")
        mangler = {k: v for k, v in tall_i_teksten.items() if v not in tekst}
        if mangler:
            raise SystemExit("tekst.md stemmer ikke med tallene. Finner ikke:\n  "
                             + "\n  ".join(f"{k}: «{v}»" for k, v in mangler.items()))

    ut = INNHOLD_DIR / SLUG
    ut.mkdir(parents=True, exist_ok=True)
    (ut / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"Reliabilitet {reliabilitet:.2f} | stabilitet r={r_stab:.2f} (n={len(felles)}) | "
          f"justering b={k1:+.2f} | spenn {spenn:.2f} kp ≈ {spenn_gsp:.1f} gsp (b_gap={b_gap:.2f}, b_eks={b_eks:.2f})")
    print(f"Oslo relativ slakkhet {oslo_rel:+.3f} | vgs: r={vgs['r']:.2f} sd={vgs['sd']:.2f}")
    print(f"Snillest: {[B[o]['navn'] for o in snill]}")
    print(f"Strengest: {[B[o]['navn'] for o in streng]}")
    print("Tall teksten må inneholde:", *[f"  {v}" for v in tall_i_teksten.values()], sep="\n")
    print(f"✓ Skrev {ut / 'data.json'}. Husk: python pipeline/bygg_manifest.py")


if __name__ == "__main__":
    main()
