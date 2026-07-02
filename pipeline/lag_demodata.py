"""Genererer PLASSHOLDER-snapshots så motoren kan vises frem uten nett.

Tallene her er omtrentlige og skal IKKE publiseres som fakta — de er
merket med "demo": true i metadataene, som gir et synlig «Demodata»-merke
på sidene. Bytt til ekte tall med:

    python3 pipeline/hent_ssb_navn.py
    python3 pipeline/hent_ssb_befolkning.py
    python3 pipeline/bygg_manifest.py

Navnene som ligger inne (Anne, Jan, Nora, Jakob …) følger de godt kjente
hovedtrekkene i SSBs navnestatistikk, men årstall og antall er glattede
demoverdier — ikke sitérbare.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

from kontrakt import INNHOLD_DIR, valider_snapshot

AAR = list(range(1946, 2025))


def klokke(aar: int, topp_aar: int, topp: int, bredde: float, gulv: int = 12) -> int:
    """Glatt klokkekurve — tydelig demoform, ikke ekte årstall-variasjon."""
    return max(gulv, round(topp * math.exp(-((aar - topp_aar) ** 2) / (2 * bredde ** 2))))


# ---------------------------------------------------------------- navn ----

JENTESERIER = [("Anne", 1955, 1150, 11), ("Ida", 1995, 780, 9),
               ("Emma", 2006, 560, 9), ("Nora", 2016, 480, 8)]
GUTTESERIER = [("Jan", 1954, 1250, 10), ("Thomas", 1980, 900, 11),
               ("Markus", 2001, 640, 9), ("Jakob", 2017, 460, 8)]

JENTETOPP = [(1946, 1965, "Anne"), (1966, 1972, "Hilde"), (1973, 1979, "Monica"),
             (1980, 1986, "Silje"), (1987, 1992, "Camilla"), (1993, 1999, "Ida"),
             (2000, 2011, "Emma"), (2012, 2022, "Nora"), (2023, 2024, "Emma")]
GUTTETOPP = [(1946, 1964, "Jan"), (1965, 1971, "Geir"), (1972, 1988, "Thomas"),
             (1989, 1997, "Martin"), (1998, 2007, "Markus"), (2008, 2013, "Lucas"),
             (2014, 2021, "Jakob"), (2022, 2024, "Noah")]


def lag_navnedata() -> dict:
    def kurver(serier):
        return {navn: {aar: klokke(aar, t, v, b) for aar in AAR}
                for navn, t, v, b in serier}

    jenter, gutter = kurver(JENTESERIER), kurver(GUTTESERIER)

    def toppnavn(perioder, kurvesett):
        ut = {}
        for fra, til, navn in perioder:
            for aar in range(fra, til + 1):
                if navn in kurvesett:
                    antall = kurvesett[navn][aar]
                else:
                    antall = round(max(s[aar] for s in kurvesett.values()) * 1.08)
                ut[aar] = (navn, antall)
        return ut

    topp_j = toppnavn(JENTETOPP, jenter)
    topp_g = toppnavn(GUTTETOPP, gutter)

    fmt = lambda n: f"{n:,}".replace(",", " ")
    oppslag = {
        str(aar): {"rader": [
            {"etikett": "Jenter", "verdi": topp_j[aar][0],
             "detalj": f"{fmt(topp_j[aar][1])} jenter fikk navnet"},
            {"etikett": "Gutter", "verdi": topp_g[aar][0],
             "detalj": f"{fmt(topp_g[aar][1])} gutter fikk navnet"},
        ]} for aar in AAR
    }

    def tiarsvinnere():
        kort = []
        for tiar in range(1950, 2030, 10):
            aar_i = [a for a in AAR if tiar <= a < tiar + 10]
            if not aar_i:
                continue
            je = Counter(topp_j[a][0] for a in aar_i).most_common(1)[0]
            gu = Counter(topp_g[a][0] for a in aar_i).most_common(1)[0]
            kort.append({"overtittel": f"{tiar}-tallet",
                         "verdi": f"{je[0]} & {gu[0]}",
                         "detalj": f"på topp {je[1]} og {gu[1]} av {len(aar_i)} år"})
        return kort

    serieliste = lambda kurvesett: [
        {"navn": navn, "punkter": [[aar, kurvesett[navn][aar]] for aar in AAR]}
        for navn in kurvesett
    ]

    return {
        "meta": {
            "tittel": "Navnet alle fikk",
            "kilde": "Statistisk sentralbyrå",
            "kilde_url": "https://www.ssb.no/befolkning/navn/statistikk/navn",
            "dato_hentet": "2026-07-02",
            "geografi": "Norge",
            "enhet": "antall nyfødte",
            "oppdateringsfrekvens": "årlig (januar)",
            "beskrivelse": ("Hvilket navn var størst i ditt fødselsår? Åtti år med "
                            "norske navnebølger, fra Anne og Jan til Nora og Jakob."),
            "demo": True,
        },
        "visninger": {
            "hero": {
                "type": "hero",
                "eyebrow": "Slå opp",
                "sporsmal": "Hvilket navn var størst i ditt fødselsår?",
                "kontroll": {"etikett": "Velg fødselsår", "standard": "1990"},
                "oppslag": oppslag,
                "fotnote": ("Navn gitt til nyfødte i Norge det valgte året. "
                            "Kilde: SSBs navnestatistikk."),
            },
            "jentenavn": {"type": "tidslinje",
                          "tittel": "Jentenavnene som har toppet listene",
                          "enhet": "nyfødte per år", "serier": serieliste(jenter)},
            "guttenavn": {"type": "tidslinje",
                          "tittel": "Guttenavnene som har toppet listene",
                          "enhet": "nyfødte per år", "serier": serieliste(gutter)},
            "tiarsvinnere": {"type": "kortgalleri", "tittel": "Tiårenes vinnere",
                             "undertekst": "jente- og guttenavnet som toppet flest år",
                             "kort": tiarsvinnere()},
        },
    }


# ---------------------------------------------------------- befolkning ----

MILEPAELER = [(1946, 3_127_000), (1950, 3_278_000), (1960, 3_591_000),
              (1970, 3_876_000), (1980, 4_086_000), (1990, 4_249_000),
              (2000, 4_478_000), (2010, 4_858_000), (2020, 5_368_000),
              (2025, 5_551_000)]

FYLKESTALL_2025 = {
    "Oslo": 731_000, "Akershus": 748_000, "Østfold": 320_000,
    "Buskerud": 273_000, "Innlandet": 376_000, "Vestfold": 260_000,
    "Telemark": 178_000, "Agder": 322_000, "Rogaland": 504_000,
    "Vestland": 654_000, "Møre og Romsdal": 270_000, "Trøndelag": 487_000,
    "Nordland": 243_000, "Troms": 170_000, "Finnmark": 76_000,
}


def lag_befolkningsdata() -> dict:
    punkter = []
    for (a1, v1), (a2, v2) in zip(MILEPAELER, MILEPAELER[1:]):
        for aar in range(a1, a2):
            andel = (aar - a1) / (a2 - a1)
            punkter.append([aar, round(v1 + (v2 - v1) * andel)])
    punkter.append([MILEPAELER[-1][0], MILEPAELER[-1][1]])

    vekst = []
    serie = dict(punkter)
    for tiar in range(1950, 2020, 10):
        if tiar in serie and tiar + 10 in serie:
            vekst.append([tiar, serie[tiar + 10] - serie[tiar]])

    return {
        "meta": {
            "tittel": "Fem og en halv million",
            "kilde": "Statistisk sentralbyrå",
            "kilde_url": "https://www.ssb.no/befolkning/folketall/statistikk/befolkning",
            "dato_hentet": "2026-07-02",
            "geografi": "Norge, fylker",
            "enhet": "personer",
            "oppdateringsfrekvens": "kvartalsvis",
            "beskrivelse": ("Norges befolkning har vokst med nesten to og en halv "
                            "million siden krigen. Hvor bor vi nå — og hvor gikk veksten?"),
            "demo": True,
        },
        "visninger": {
            "hero": {
                "type": "hero",
                "eyebrow": "Folketallet",
                "rader": [{"etikett": "Bosatt i Norge 1. januar 2025",
                           "verdi": "5 551 000",
                           "detalj": "nesten 2,5 millioner flere enn i 1946"}],
                "fotnote": "Registrert bosatt befolkning. Kilde: SSBs befolkningsstatistikk.",
            },
            "utvikling": {"type": "tidslinje",
                          "tittel": "Befolkningen siden 1946",
                          "enhet": "personer",
                          "serier": [{"navn": "Befolkning", "punkter": punkter}]},
            "fylkeskart": {"type": "kart",
                           "tittel": "Hvor bor vi?",
                           "undertekst": "bosatte per fylke",
                           "enhet": "personer",
                           "verdier": FYLKESTALL_2025},
            "vekst": {"type": "tidslinje", "stil": "søyle",
                      "tittel": "Vekst per tiår",
                      "undertekst": "nye innbyggere per tiår",
                      "enhet": "personer",
                      "x_navn": "Tiår (fra år)",
                      "serier": [{"navn": "Vekst", "punkter": vekst}]},
        },
    }


def main() -> int:
    for slug, data in [("navn", lag_navnedata()), ("befolkning", lag_befolkningsdata())]:
        feil = valider_snapshot(data, slug)
        if feil:
            for f in feil:
                print(f"  ✗ {f}")
            return 1
        fil = INNHOLD_DIR / slug / "data.json"
        fil.parent.mkdir(parents=True, exist_ok=True)
        fil.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
        print(f"✓ skrev {fil} (demodata)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
