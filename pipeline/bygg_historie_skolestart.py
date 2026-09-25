"""Bygger historien «En gladmelding til foreldrene på vestkanten».

Kjøring (etter hentescriptene):

    python pipeline/hent_udir_matte.py              # nasjonale prøver per skole
    python pipeline/hent_udir_ungdomsskole_oslo.py  # eierform per skole
    python pipeline/hent_skolested_oslo.py          # bydel per skole
    python pipeline/hent_ssb_utdanning_bydel.py     # utdanningsnivå per bydel
    python pipeline/bygg_historie_skolestart.py

Historien: når elevene begynner i 8. klasse, er ungdomsskolene i ytre vest så
like at det knapt spiller noen rolle hvilken barnet går på. På østkanten skiller
det flere skoleår. Men ungdomsskolene løfter elevene like mye overalt:
forskjellene er satt før første skoledag, og de tettes ikke.

Valg som er gjort med vilje:
- **Bare offentlige nærskoler.** Privatskoler (Wang Ung, Akademiet realfagsskole,
  Kristelig gymnasium, internasjonale skoler) tar inn elever fra hele byen og
  sier ingenting om nabolaget de ligger i.
- **Nasjonale prøver i 8. trinn**, regning og lesing, snitt 2023-24 til 2025-26.
  Prøvene tas i september, så de måler hva elevene har med seg inn — ikke hva
  ungdomsskolen har gjort. Engelsk er utelatt fordi den ikke tas i 9. trinn, og
  samme mål skal brukes for nivå og løft.
- **Skoleår som enhet.** De samme elevene går fram om lag fire skalapoeng fra
  8. til 9. trinn nasjonalt. Forskjeller regnes om med den veksten.
- **Løftet** er skolens framgang fra 8. til 9. trinn for samme kull, utover
  landets framgang. Det er nærmere et mål på skolen enn nivået er.

Kontroller som stopper bygget:
- Oslo-snittet i høyere utdanning (SSB) skal ligge mellom 50 og 62 prosent.
- Veksten fra 8. til 9. trinn skal være positiv og under 8 skalapoeng.
- Spredningen i ytre vest skal være mindre enn i ytre øst — ellers er
  historien feil og må skrives om.
- Tallene i tekst.md skal stemme med det som regnes ut her.
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

RAA = Path(__file__).resolve().parents[2] / "impromptu_raadata"
UDIR = Path(os.environ.get("UDIR_DIR") or RAA / "udir")
SSB = Path(os.environ.get("SSB_DIR") or RAA / "ssb")
SLUG = "skolestart"
NIVAA_AAR = ["2023-24", "2024-25", "2025-26"]
KULL = [("2022-23", "2023-24"), ("2023-24", "2024-25"), ("2024-25", "2025-26")]   # 8. trinn → 9. trinn
PROVER = ("Regning", "Lesing")
MIN_ELEVER = 60
# Støygulvet: hvor mye skolesnittene ville variert om alle skolene var like.
# Regning og lesing korrelerer hos samme elev (antatt 0,7, typisk for slike prøver),
# og Udir runder hvert skolesnitt til hele poeng (varians 1/12 per tall).
KORR_PROVER = 0.7


def les(fil: Path) -> list[dict]:
    with open(fil, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def tall(s):
    return float(s) if s not in ("", None) else None


def komma(v: float, des: int = 1) -> str:
    return f"{v:.{des}f}".replace(".", ",").replace("-", "−")


def sd(x: list[float]) -> float:
    return statistics.stdev(x) if len(x) > 1 else 0.0


def pearson(x: list[float], y: list[float]) -> float:
    mx, my = statistics.fmean(x), statistics.fmean(y)
    return (sum((a - mx) * (b - my) for a, b in zip(x, y))
            / (sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y)) ** 0.5)


def barneskolene() -> list[dict]:
    """Nasjonale prøver 5. trinn, regning og lesing, offentlige barneskoler, alle år.

    Samme utvalgsregler som for ungdomsskolene. Skalaen på 5. trinn er en egen
    skala (snitt 50, sd 10), så sammenligningen med 8. trinn gjøres som avvik fra
    Oslo-snittet i skalapoeng, ikke i skoleår.
    """
    sted = {r["orgnr"]: r for r in les(UDIR / "barneskoler_sted.csv")}
    sw: dict = defaultdict(lambda: [0.0, 0.0])
    for r in les(UDIR / "barneskole_oslo_np.csv"):
        if (r["nivaa"] == "skole" and r["eierform"] == "Offentlig skole" and r["prove"] in PROVER
                and r["skalapoeng"] and r["antall"]):
            sw[r["orgnr"]][0] += tall(r["skalapoeng"]) * tall(r["antall"])
            sw[r["orgnr"]][1] += tall(r["antall"])
    skoler = []
    for o, (w, n) in sw.items():
        omr = (sted.get(o) or {}).get("omraade")
        if omr and omr != "sentrum" and n / len(PROVER) >= MIN_ELEVER:
            skoler.append({"np5": w / n, "omraade": omr, "bydel": sted[o]["bydel"]})
    return skoler


def grunnskolepoeng_over_tid(orgnr: set, omraade: dict) -> dict:
    """Spredning i grunnskolepoeng mellom de samme skolene, vest mot øst/sør, hvert år."""
    per: dict = defaultdict(lambda: defaultdict(list))
    skole_aar: dict = defaultdict(dict)
    for r in les(UDIR / "ungdomsskole_oslo_grunnskolepoeng.csv"):
        if (r["nivaa"] == "skole" and r["orgnr"] in orgnr and r["eierform"] == "Alle eierformer"
                and r["kjonn"] == "Alle kjønn" and r["poeng"]):
            side = "vest" if "vest" in omraade[r["orgnr"]] else "øst"
            per[r["skoleaar"]][side].append(tall(r["poeng"]))
            skole_aar[r["orgnr"]][r["skoleaar"]] = tall(r["poeng"])
    serier = {"vest": [], "øst": []}
    for aar in sorted(per):
        if len(per[aar]["vest"]) >= 5 and len(per[aar]["øst"]) >= 5:
            for side in serier:
                serier[side].append([int(aar[:4]) + 1, round(sd(per[aar][side]), 2)])
    tidlig = ["2011-12", "2012-13", "2013-14", "2014-15", "2015-16"]
    sent = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
    par = [(statistics.fmean(d[a] for a in tidlig if a in d), statistics.fmean(d[a] for a in sent if a in d))
           for d in skole_aar.values() if any(a in d for a in tidlig) and any(a in d for a in sent)]
    return {"serier": serier, "r_stabil": pearson([a for a, _ in par], [b for _, b in par]),
            "n_stabil": len(par),
            "aar_ost_mer": sum(o[1] > v[1] for v, o in zip(serier["vest"], serier["øst"])),
            "aar_totalt": len(serier["vest"])}


def main() -> None:
    np_rader = [r for r in les(UDIR / "matte_oslo_np.csv")
                if r["kjonn"] == "Alle kjønn" and r["prove"] in PROVER and r["skalapoeng"]]
    sted = {r["orgnr"]: r for r in les(UDIR / "ungdomsskoler_sted.csv")}
    eier: dict = defaultdict(set)
    for r in les(UDIR / "ungdomsskole_oslo_karakterer.csv"):
        if r["nivaa"] == "skole" and r["eierform"] in ("Offentlig skole", "Privat eiet"):
            eier[r["orgnr"]].add(r["eierform"])
    utd = {r["bydel"]: tall(r["andel_hoyere_utdanning"]) for r in les(SSB / "utdanning_bydel.csv")}
    utd_pers = {r["bydel"]: tall(r["personer_16_pluss"]) for r in les(SSB / "utdanning_bydel.csv")}
    utd_aar = les(SSB / "utdanning_bydel.csv")[0]["aar"]

    # --- Kontroll: kjent nevner
    oslo_utd = sum(utd[b] * utd_pers[b] for b in utd) / sum(utd_pers.values())
    if not 50 <= oslo_utd <= 62:
        raise SystemExit(f"Oslo-snitt høyere utdanning {oslo_utd:.1f} % — feil rad i SSB-tabellen?")

    # --- Vekst per skoleår nasjonalt: 9. trinn (t+1) minus 8. trinn (t), samme kull
    land = {(r["prove"], r["trinn"][:1], r["skoleaar"]): tall(r["skalapoeng"])
            for r in np_rader if r["nivaa"] == "land"}
    vekst = statistics.fmean(land[(p, "9", a9)] - land[(p, "8", a8)] for a8, a9 in KULL for p in PROVER)
    if not 0 < vekst < 8:
        raise SystemExit(f"Vekst fra 8. til 9. trinn = {vekst:.2f} skalapoeng — urimelig.")

    # --- Nivå ved inngangen, per offentlig nærskole
    skole = [r for r in np_rader if r["nivaa"] == "skole"]
    sum_w: dict = defaultdict(lambda: [0.0, 0.0])
    for r in skole:
        if r["trinn"].startswith("8") and r["skoleaar"] in NIVAA_AAR and r["antall"]:
            sum_w[r["orgnr"]][0] += tall(r["skalapoeng"]) * tall(r["antall"])
            sum_w[r["orgnr"]][1] += tall(r["antall"])
    skoler = {}
    for o, (w, n) in sum_w.items():
        s = sted.get(o, {})
        if eier.get(o) != {"Offentlig skole"} or not s.get("omraade") or n / len(PROVER) < MIN_ELEVER:
            continue
        skoler[o] = {"navn": s["navn"].replace(" skole", "").replace(" ungdomsskole", ""),
                     "bydel": s["bydel"], "omraade": s["omraade"], "np8": w / n, "elever": n / len(PROVER)}
    private = sorted({sted[o]["navn"] for o in sum_w if eier.get(o) == {"Privat eiet"} and o in sted})

    # --- Løft fra 8. til 9. trinn, utover landets
    v = {(r["orgnr"], r["prove"], r["trinn"][:1], r["skoleaar"]): (tall(r["skalapoeng"]), tall(r["antall"] or 0))
         for r in skole}
    for o in skoler:
        lw = ln = 0.0
        for a8, a9 in KULL:
            for p in PROVER:
                if (o, p, "8", a8) in v and (o, p, "9", a9) in v:
                    (s8, n8), (s9, n9) = v[(o, p, "8", a8)], v[(o, p, "9", a9)]
                    vekt = min(n8, n9)
                    lw += ((s9 - land[(p, "9", a9)]) - (s8 - land[(p, "8", a8)])) * vekt
                    ln += vekt
        skoler[o]["loft"] = lw / ln if ln else None
        skoler[o]["loft_n"] = ln

    # --- Spredning per område, og støygulvet (sd fra tilfeldighet alene)
    omr: dict = defaultdict(list)
    for s in skoler.values():
        omr[s["omraade"]].append(s)
    stat = {}
    for o, liste in omr.items():
        x = [s["np8"] for s in liste]
        stoy = statistics.fmean(100 * (1 + KORR_PROVER) / 2 / s["elever"]
                                + (1 / 12) / (len(NIVAA_AAR) * len(PROVER)) for s in liste) ** 0.5
        stat[o] = {"n": len(x), "snitt": statistics.fmean(x), "sd": statistics.stdev(x) if len(x) > 1 else 0,
                   "spenn_aar": (max(x) - min(x)) / vekst, "stoy": stoy}
    if not stat["ytre vest"]["sd"] < stat["ytre øst"]["sd"]:
        raise SystemExit("Ytre vest spriker ikke mindre enn ytre øst lenger — historien må skrives om.")

    vest = [s for s in skoler.values() if "vest" in s["omraade"]]
    ost = [s for s in skoler.values() if s["omraade"] in ("indre øst", "ytre øst", "sør")]
    loft = [s for s in skoler.values() if s["loft"] is not None]
    loft_vest = statistics.fmean(s["loft"] for s in loft if "vest" in s["omraade"])
    loft_ost = statistics.fmean(s["loft"] for s in loft if s["omraade"] in ("indre øst", "ytre øst", "sør"))
    var_loft = statistics.variance([s["loft"] for s in loft])
    stoy_loft = statistics.fmean((10 * 2 ** 0.5 / s["loft_n"] ** 0.5) ** 2 for s in loft)
    reell_loft = max(var_loft - stoy_loft, 0) / var_loft
    # Er forskjellen i løft mellom vest og øst større enn tilfeldig omfordeling gir?
    import random
    rng = random.Random(1)
    alle_l = [s["loft"] for s in loft]
    er_vest = ["vest" in s["omraade"] for s in loft]
    obs = abs(loft_vest - loft_ost)
    treff = 0
    for _ in range(10000):
        rng.shuffle(er_vest)
        a = [x for x, v in zip(alle_l, er_vest) if v]
        b = [x for x, v in zip(alle_l, er_vest) if not v]
        treff += abs(statistics.fmean(a) - statistics.fmean(b)) >= obs
    p_loft = treff / 10000

    # --- Bydelene: skolesnitt og utdanningsnivå
    byd: dict = defaultdict(list)
    for s in skoler.values():
        byd[s["bydel"]].append(s["np8"])
    bydsnitt = {b: statistics.fmean(x) for b, x in byd.items()}
    xs = [utd[b] for b in bydsnitt]
    ys = [bydsnitt[b] for b in bydsnitt]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    r_utd = (sum((a - mx) * (b - my) for a, b in zip(xs, ys))
             / (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** 0.5)
    lavest = min(bydsnitt, key=bydsnitt.get)

    # --- Barneskolene (5. trinn) og grunnskolepoeng over 15 år
    b5 = barneskolene()
    oslo5 = statistics.fmean(s_["np5"] for s_ in b5)
    oslo8 = statistics.fmean(s_["np8"] for s_ in skoler.values())
    avvik = {o: (statistics.fmean(s_["np5"] for s_ in b5 if s_["omraade"] == o) - oslo5,
                 statistics.fmean(s_["np8"] for s_ in skoler.values() if s_["omraade"] == o) - oslo8)
             for o in ("ytre vest", "indre vest", "indre øst", "sør", "ytre øst")}
    sd5_vest = sd([s_["np5"] for s_ in b5 if s_["omraade"] == "ytre vest"])
    sd5_ost = sd([s_["np5"] for s_ in b5 if s_["omraade"] == "ytre øst"])
    if not sd5_vest < sd5_ost:
        raise SystemExit("Barneskolene i ytre vest spriker ikke mindre enn i ytre øst — skriv om seksjonen.")
    b5_byd: dict = defaultdict(list)
    for s_ in b5:
        b5_byd[s_["bydel"]].append(s_["np5"])
    r_utd5 = pearson([utd[b] for b in b5_byd], [statistics.fmean(x) for x in b5_byd.values()])
    gsp = grunnskolepoeng_over_tid(set(skoler), {o: s_["omraade"] for o, s_ in skoler.items()})
    if gsp["aar_ost_mer"] < gsp["aar_totalt"] * 0.8:
        raise SystemExit(f"Øst spriker mer bare i {gsp['aar_ost_mer']} av {gsp['aar_totalt']} år — skriv om seksjonen.")

    ytre_vest, ytre_ost = stat["ytre vest"], stat["ytre øst"]
    tall_i_teksten = {
        "spenn_vest": f"{komma(ytre_vest['spenn_aar'])} skoleår",
        "spenn_ost": f"{komma(ytre_ost['spenn_aar'])} skoleår",
        "n_skoler": f"{len(skoler)} offentlige ungdomsskoler",
        "vekst": f"{komma(vekst)} skalapoeng",
        "sd_vest": f"{komma(ytre_vest['sd'])} poeng",
        "stoy_vest": f"{komma(ytre_vest['stoy'])} poeng",
        "r_utd": f"{komma(r_utd, 2)}",
        "utd_lav": f"{komma(utd[lavest])} prosent",
        "loft_vest": f"{komma(loft_vest, 2)}",
        "loft_ost": f"{komma(loft_ost, 2)}",
        "ganger": f"{round(ytre_ost['sd'] / ytre_ost['stoy'])} ganger",
        "n_barneskoler": f"{len(b5)} offentlige barneskoler",
        "sd5": f"{komma(sd5_vest)} poeng i ytre vest og {komma(sd5_ost)} i ytre øst",
        "avvik_vest": (f"{komma(avvik['ytre vest'][0])} skalapoeng over Oslo-snittet i femte klasse og "
                       f"{komma(avvik['ytre vest'][1])} i åttende"),
        "avvik_ost": f"{komma(-avvik['ytre øst'][0])} under i femte og {komma(-avvik['ytre øst'][1])} i åttende",
        "r_utd5": f"{komma(r_utd5, 2)}",
        "gsp_aar": f"{gsp['aar_ost_mer']} av {gsp['aar_totalt']} år",
        "gsp_r": f"{komma(gsp['r_stabil'], 2)}",
    }

    def aar_foran(x):   # skoleår foran den svakeste offentlige skolen i Oslo
        return round((x - min(s["np8"] for s in skoler.values())) / vekst, 2)

    data = {
        "meta": {
            "tittel": "En gladmelding til foreldrene på vestkanten",
            "kilde": "Utdanningsdirektoratet (nasjonale prøver); SSB (utdanningsnivå, tabell 09434)",
            "kilde_url": "https://www.udir.no/tall-og-forskning/statistikk/statistikk-grunnskole/",
            "dato_hentet": date.today().isoformat(),
            "geografi": "Oslo, offentlige ungdomsskoler og bydeler",
            "enhet": "skoleår",
            "oppdateringsfrekvens": "årlig",
            "beskrivelse": (f"I ytre vest skiller det {komma(ytre_vest['spenn_aar'])} skoleår mellom beste og svakeste "
                            f"ungdomsskole. I ytre øst skiller det {komma(ytre_ost['spenn_aar'])}. Forskjellen er der "
                            "før første skoledag — og ungdomsskolen tetter den ikke."),
            "utkast": True,
        },
        "visninger": {
            "hero": {
                "type": "hero",
                "eyebrow": "Ungdomsskolene i Oslo",
                "sporsmal": "Spiller det noen rolle hvilken ungdomsskole barnet går på?",
                "rader": [
                    {"etikett": "ytre vest", "verdi": f"{komma(ytre_vest['spenn_aar'])} skoleår",
                     "detalj": "mellom beste og svakeste skole"},
                    {"etikett": "ytre øst", "verdi": f"{komma(ytre_ost['spenn_aar'])} skoleår",
                     "detalj": "mellom beste og svakeste skole"},
                ],
                "fotnote": ("Nasjonale prøver i regning og lesing ved starten av 8. klasse, offentlige skoler, "
                            "2023–2026. Ett skoleår = det elevene går fram fra 8. til 9. klasse."),
            },
            "kart_skole": {
                "type": "bydelskart",
                "tittel": "Hvor langt foran er elevene når de begynner i åttende?",
                "undertekst": (f"Skoleår foran {lavest}, snitt av bydelens offentlige ungdomsskoler, "
                               "nasjonale prøver i regning og lesing 2023–2026"),
                "enhet": "skoleår",
                "desimaler": 1,
                "verdier": {b: round((x - bydsnitt[lavest]) / vekst, 2) for b, x in bydsnitt.items()},
                "detalj": {b: f"{len(byd[b])} skoler; {komma(utd[b])} % av de voksne har høyere utdanning"
                           for b in bydsnitt},
            },
            "spennet": {
                "type": "rangering",
                "tittel": "Hvor mye betyr skolen? Det kommer an på hvor du bor",
                "undertekst": "Skoleår mellom beste og svakeste offentlige ungdomsskole i hvert område",
                "enhet": "skoleår",
                "rader": [{"navn": o[0].upper() + o[1:], "verdi": round(s["spenn_aar"], 1),
                           "detalj": f"{s['n']} skoler"} for o, s in stat.items() if s["n"] >= 3],
            },
            "kart_utdanning": {
                "type": "bydelskart",
                "tittel": "Andel voksne med høyere utdanning",
                "undertekst": f"Personer 16 år og over, {utd_aar} (SSB, tabell 09434)",
                "enhet": "prosent",
                "desimaler": 0,
                "verdier": {b: v for b, v in utd.items() if b != "Marka"},
            },
            "femte": {
                "type": "kortgalleri",
                "tittel": "Forskjellen er der allerede i femte klasse",
                "undertekst": "Skalapoeng over eller under Oslo-snittet, offentlige skoler, regning og lesing",
                "kort": [
                    {"overtittel": "Ytre vest, 5. klasse", "verdi": f"+{komma(avvik['ytre vest'][0])}",
                     "detalj": f"{sum(s_['omraade'] == 'ytre vest' for s_ in b5)} barneskoler"},
                    {"overtittel": "Ytre vest, 8. klasse", "verdi": f"+{komma(avvik['ytre vest'][1])}",
                     "detalj": f"{ytre_vest['n']} ungdomsskoler"},
                    {"overtittel": "Ytre øst, 5. klasse", "verdi": komma(avvik["ytre øst"][0]),
                     "detalj": f"{sum(s_['omraade'] == 'ytre øst' for s_ in b5)} barneskoler"},
                    {"overtittel": "Ytre øst, 8. klasse", "verdi": komma(avvik["ytre øst"][1]),
                     "detalj": f"{ytre_ost['n']} ungdomsskoler"},
                ],
            },
            "femten_aar": {
                "type": "tidslinje",
                "tittel": f"Østkanten har sprikt mer enn vestkanten i {gsp['aar_ost_mer']} av {gsp['aar_totalt']} år",
                "undertekst": ("Spredning i grunnskolepoeng mellom de samme offentlige ungdomsskolene "
                               "(standardavvik, poeng). Vest = indre og ytre vest; øst = øst og sør."),
                "enhet": "poeng",
                "x_navn": "Skoleår (vår)",
                "serier": [{"navn": "Øst og sør", "punkter": gsp["serier"]["øst"]},
                           {"navn": "Vest", "punkter": gsp["serier"]["vest"]}],
            },
            "loftet": {
                "type": "kortgalleri",
                "tittel": "Ungdomsskolen løfter like mye overalt",
                "undertekst": "Framgang fra 8. til 9. klasse for de samme elevene, utover landets, i skalapoeng",
                "kort": [
                    {"overtittel": "Skolene på vestkanten", "verdi": f"+{komma(loft_vest, 2)}",
                     "detalj": "skalapoeng, snitt"},
                    {"overtittel": "Skolene på østkanten og i sør", "verdi": f"+{komma(loft_ost, 2)}",
                     "detalj": f"skalapoeng, snitt — forskjellen er innenfor tilfeldighetene (p = {komma(p_loft, 2)})"},
                    {"overtittel": "Forskjell mellom skolene", "verdi": "Ingen målbar",
                     "detalj": f"variasjonen er ikke større enn tilfeldigheter ({len(loft)} skoler, tre kull)"},
                ],
            },
        },
    }

    feil = kontrakt.valider_snapshot(data, SLUG)
    if feil:
        raise SystemExit("\n".join(feil))
    tekstfil = INNHOLD_DIR / SLUG / "tekst.md"
    if tekstfil.exists():
        tekst = tekstfil.read_text(encoding="utf-8").replace("\xa0", " ")
        mangler = {n: t for n, t in tall_i_teksten.items() if t not in tekst}
        if mangler:
            raise SystemExit("tekst.md stemmer ikke med tallene. Finner ikke:\n  "
                             + "\n  ".join(f"{n}: «{t}»" for n, t in mangler.items()))
    # Skolelista er bakgrunnsmateriale: den skal ikke publiseres (historien navngir
    # ikke enkeltskoler), og den skal ikke i repoet, som er offentlig på GitHub.
    liste = UDIR / "skolestart_skoleliste.csv"
    with open(liste, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["skole", "bydel", "omraade", "np8_regning_lesing", "skoleaar_foran_svakeste",
                    "elever_per_prove_2023_26", "loft_8_til_9", "orgnr"])
        laveste = min(s_["np8"] for s_ in skoler.values())
        for o, s_ in sorted(skoler.items(), key=lambda x: -x[1]["np8"]):
            w.writerow([s_["navn"], s_["bydel"], s_["omraade"], round(s_["np8"], 2),
                        round((s_["np8"] - laveste) / vekst, 2), int(s_["elever"]),
                        None if s_["loft"] is None else round(s_["loft"], 2), o])

    ut = INNHOLD_DIR / SLUG
    ut.mkdir(parents=True, exist_ok=True)
    (ut / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"5. trinn: {len(b5)} skoler, sd vest {sd5_vest:.2f} øst {sd5_ost:.2f}, r_utd {r_utd5:.2f}; avvik {avvik}")
    print(f"Grunnskolepoeng: øst mer i {gsp['aar_ost_mer']}/{gsp['aar_totalt']} år, "
          f"stabilitet r={gsp['r_stabil']:.2f} (n={gsp['n_stabil']})")
    print(f"Vekst per skoleår: {vekst:.2f} | Oslo høyere utdanning {oslo_utd:.1f} % | r(utdanning, skolesnitt) = {r_utd:.2f}")
    for o, s in sorted(stat.items(), key=lambda x: x[1]["snitt"]):
        print(f"  {o:<11} n={s['n']:>2} snitt {s['snitt']:.1f} sd {s['sd']:.2f} støy {s['stoy']:.2f} spenn {s['spenn_aar']:.2f} år")
    print(f"Løft: vest {loft_vest:+.2f}, øst/sør {loft_ost:+.2f} (permutasjon p={p_loft:.2f}); "
          f"reell variasjon {reell_loft:.2f} (n={len(loft)})")
    print(f"Privatskoler utelatt: {', '.join(private)}")
    print("Tall teksten må inneholde:", *[f"  {n}: {t}" for n, t in tall_i_teksten.items()], sep="\n")
    print(f"Bakgrunnsmateriale (ikke publisert): {liste}")
    print(f"✓ Skrev {ut / 'data.json'}. Husk: python pipeline/bygg_manifest.py")


if __name__ == "__main__":
    main()
