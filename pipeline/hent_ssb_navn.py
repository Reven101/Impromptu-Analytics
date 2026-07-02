"""Henter SSBs navnestatistikk og skriver snapshot til innhold/navn/data.json.

Kjøring (krever nett mot data.ssb.no):

    python3 pipeline/hent_ssb_navn.py
    python3 pipeline/bygg_manifest.py

Datakilde: SSBs åpne PxWeb-API (https://data.ssb.no/api/v0/no/).
Scriptet finner navnetabellene via API-søket (robust mot at tabell-id-er
endres), henter alle navn × alle år, og normaliserer til snapshot-formatet
definert i kontrakt.py. Snapshots er statiske filer — ingen live-spørringer
fra nettsiden, ingen jobber å vedlikeholde.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

from kontrakt import INNHOLD_DIR, valider_snapshot

API = "https://data.ssb.no/api/v0/no/table/"
FRA_AAR = 1946          # nyere del av serien: komplett og relevant for fødselsår
ANTALL_SERIER = 4       # navn per tidslinje (maks 6 — validert palett)

UTFIL = INNHOLD_DIR / "navn" / "data.json"


def _hent_json(url: str, body: dict | None = None) -> dict | list:
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"} if body else {}
    )
    with urllib.request.urlopen(req, timeout=120) as svar:
        return json.loads(svar.read().decode("utf-8"))


def finn_navnetabeller() -> dict[str, str]:
    """Finner tabell-id for jente- og guttenavn via API-søket."""
    resultat = _hent_json(API + "?query=fornavn")
    tabeller = resultat if isinstance(resultat, list) else resultat.get("tables", [])
    funnet = {}
    for t in tabeller:
        tittel = (t.get("title") or "").lower()
        if "fornavn" not in tittel:
            continue
        if "jente" in tittel and "jenter" not in funnet:
            funnet["jenter"] = t["id"]
        if "gutte" in tittel and "gutter" not in funnet:
            funnet["gutter"] = t["id"]
    if len(funnet) != 2:
        raise SystemExit(
            "Fant ikke navnetabellene via API-søket. Søk manuelt på "
            "https://data.ssb.no etter «fornavn» og oppdater dette scriptet."
        )
    return funnet


def hent_navnedata(tabell_id: str) -> dict[str, dict[int, int]]:
    """Returnerer {navn: {år: antall}} for alle navn i tabellen."""
    meta = _hent_json(API + tabell_id)
    koder = {v["code"].lower(): v["code"] for v in meta["variables"]}
    navn_kode = next((k for l, k in koder.items() if "fornavn" in l), None)
    if not navn_kode:
        raise SystemExit(f"Tabell {tabell_id} har ingen fornavn-variabel — sjekk tabellen.")

    sporring = {
        "query": [
            {"code": navn_kode, "selection": {"filter": "all", "values": ["*"]}},
            {"code": "Tid", "selection": {"filter": "all", "values": ["*"]}},
        ],
        "response": {"format": "json-stat2"},
    }
    stat = _hent_json(API + tabell_id, sporring)

    dims = stat["dimension"]
    rekkefolge = stat["id"]
    navn_dim = next(d for d in rekkefolge if "fornavn" in d.lower())
    navneliste = sorted(dims[navn_dim]["category"]["index"],
                        key=dims[navn_dim]["category"]["index"].get)
    navnetekst = dims[navn_dim]["category"]["label"]
    aarliste = sorted(dims["Tid"]["category"]["index"],
                      key=dims["Tid"]["category"]["index"].get)

    # json-stat2: flat verdi-liste i dimensjonsrekkefølgen fra "id"/"size"
    posisjon = {d: i for i, d in enumerate(rekkefolge)}
    størrelser = stat["size"]
    verdier = stat["value"]

    def indeks(navn_i: int, aar_i: int) -> int:
        koord = [0] * len(rekkefolge)
        koord[posisjon[navn_dim]] = navn_i
        koord[posisjon["Tid"]] = aar_i
        flat = 0
        for dim_i, k in enumerate(koord):
            flat = flat * størrelser[dim_i] + k
        return flat

    ut: dict[str, dict[int, int]] = {}
    for ni, navn_id in enumerate(navneliste):
        navn = navnetekst.get(navn_id, navn_id).strip().title()
        for ai, aar_id in enumerate(aarliste):
            aar = int(aar_id)
            if aar < FRA_AAR:
                continue
            v = verdier[indeks(ni, ai)]
            if v:
                ut.setdefault(navn, {})[aar] = int(v)
    return ut


def topp_per_aar(data: dict[str, dict[int, int]]) -> dict[int, tuple[str, int]]:
    per_aar: dict[int, tuple[str, int]] = {}
    for navn, serie in data.items():
        for aar, antall in serie.items():
            if aar not in per_aar or antall > per_aar[aar][1]:
                per_aar[aar] = (navn, antall)
    return dict(sorted(per_aar.items()))


def bygg_snapshot(jenter: dict, gutter: dict) -> dict:
    topp_j, topp_g = topp_per_aar(jenter), topp_per_aar(gutter)
    aar_felles = sorted(set(topp_j) & set(topp_g))

    oppslag = {
        str(aar): {"rader": [
            {"etikett": "Jenter", "verdi": topp_j[aar][0],
             "detalj": f"{topp_j[aar][1]:,} jenter fikk navnet".replace(",", " ")},
            {"etikett": "Gutter", "verdi": topp_g[aar][0],
             "detalj": f"{topp_g[aar][1]:,} gutter fikk navnet".replace(",", " ")},
        ]}
        for aar in aar_felles
    }

    def mestvinnende(topp: dict[int, tuple[str, int]]) -> list[str]:
        teller = Counter(navn for navn, _ in topp.values())
        return [navn for navn, _ in teller.most_common(ANTALL_SERIER)]

    def serier(data: dict, navneliste: list[str]) -> list[dict]:
        return [
            {"navn": navn,
             "punkter": [[aar, antall] for aar, antall in sorted(data[navn].items())]}
            for navn in navneliste if navn in data
        ]

    def tiarsvinnere() -> list[dict]:
        kort = []
        for tiar in range(1950, 2030, 10):
            aar_i_tiar = [a for a in aar_felles if tiar <= a < tiar + 10]
            if not aar_i_tiar:
                continue
            je = Counter(topp_j[a][0] for a in aar_i_tiar).most_common(1)[0]
            gu = Counter(topp_g[a][0] for a in aar_i_tiar).most_common(1)[0]
            kort.append({
                "overtittel": f"{tiar}-tallet",
                "verdi": f"{je[0]} & {gu[0]}",
                "detalj": f"på topp {je[1]} og {gu[1]} av {len(aar_i_tiar)} år",
            })
        return kort

    return {
        "meta": {
            "tittel": "Navnet alle fikk",
            "kilde": "Statistisk sentralbyrå",
            "kilde_url": "https://www.ssb.no/befolkning/navn/statistikk/navn",
            "dato_hentet": date.today().isoformat(),
            "geografi": "Norge",
            "enhet": "antall nyfødte",
            "oppdateringsfrekvens": "årlig (januar)",
            "beskrivelse": (
                "Hvilket navn var størst i ditt fødselsår? Åtti år med norske "
                "navnebølger, fra Anne og Jan til Nora og Jakob."
            ),
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
            "jentenavn": {
                "type": "tidslinje",
                "tittel": "Jentenavnene som har toppet listene",
                "enhet": "nyfødte per år",
                "serier": serier(jenter, mestvinnende(topp_j)),
            },
            "guttenavn": {
                "type": "tidslinje",
                "tittel": "Guttenavnene som har toppet listene",
                "enhet": "nyfødte per år",
                "serier": serier(gutter, mestvinnende(topp_g)),
            },
            "tiarsvinnere": {
                "type": "kortgalleri",
                "tittel": "Tiårenes vinnere",
                "undertekst": "jente- og guttenavnet som toppet flest år",
                "kort": tiarsvinnere(),
            },
        },
    }


def main() -> int:
    print("Søker etter navnetabeller hos SSB …")
    tabeller = finn_navnetabeller()
    print(f"  jenter: tabell {tabeller['jenter']}, gutter: tabell {tabeller['gutter']}")

    print("Henter jentenavn …")
    jenter = hent_navnedata(tabeller["jenter"])
    print(f"  {len(jenter)} navn")
    print("Henter guttenavn …")
    gutter = hent_navnedata(tabeller["gutter"])
    print(f"  {len(gutter)} navn")

    snapshot = bygg_snapshot(jenter, gutter)
    feil = valider_snapshot(snapshot, "navn")
    if feil:
        for f in feil:
            print(f"  ✗ {f}")
        return 1

    UTFIL.parent.mkdir(parents=True, exist_ok=True)
    UTFIL.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
    print(f"✓ skrev {UTFIL}")
    print("Husk: python3 pipeline/bygg_manifest.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
