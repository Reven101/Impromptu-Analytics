"""Henter SSBs befolkningstall og skriver snapshot til innhold/befolkning/data.json.

Kjøring (krever nett mot data.ssb.no):

    python3 pipeline/hent_ssb_befolkning.py
    python3 pipeline/bygg_manifest.py

Bruker SSB-tabell 06913 («Folkemengde 1. januar og endringer i kalenderåret»)
via det åpne PxWeb-API-et: hele landet som tidsserie + dagens fylker for
kartet. Faller tabellen bort, søk på «folkemengde» på data.ssb.no og
oppdater TABELL_ID.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import date

from kontrakt import INNHOLD_DIR, valider_snapshot

API = "https://data.ssb.no/api/v0/no/table/"
TABELL_ID = "06913"
FRA_AAR = 1946
LANDET = "0"
# Fylkesnummer etter 2024-inndelingen — kartkomponenten forstår disse.
FYLKER = ["03", "11", "15", "18", "31", "32", "33", "34",
          "39", "40", "42", "46", "50", "55", "56"]

UTFIL = INNHOLD_DIR / "befolkning" / "data.json"


def _hent_json(url: str, body: dict | None = None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"} if body else {}
    )
    with urllib.request.urlopen(req, timeout=120) as svar:
        return json.loads(svar.read().decode("utf-8"))


def velg_folkemengde_maal(koder: list[str], tekster: list[str]) -> str:
    """Velger folkemengde-målet — og aldri tilvekst/endringer/fødte/døde.

    Tabell 06913 har flere måltall der flere inneholder «folke»
    (f.eks. «Folketilvekst»); et naivt tekstsøk kan derfor treffe feil
    mål og gi tall i titusener der folketallet skulle vært millioner.
    """
    def poeng(tekst: str) -> int:
        t = tekst.lower()
        if any(o in t for o in ("tilvekst", "vekst", "endring", "fød", "død", "flytt")):
            return -1
        if any(o in t for o in ("folkemengd", "folketal", "befolkning")):
            return 2
        return 1 if "person" in t else 0

    beste = max(zip(koder, tekster), key=lambda kt: poeng(kt[1]))
    if poeng(beste[1]) <= 0:
        raise SystemExit(
            f"Fant ikke folkemengde-målet i tabell {TABELL_ID}. "
            f"Tilgjengelige mål: {tekster}"
        )
    return beste[0]


def hent_folkemengde() -> tuple[dict[int, int], dict[str, int], int]:
    """Returnerer (landserie {år: folketall}, {fylkesnr: folketall}, siste år)."""
    meta = _hent_json(API + TABELL_ID)
    variabler = {v["code"]: v for v in meta["variables"]}
    region_kode = next((k for k in variabler if k.lower().startswith("region")), None)
    innhold = variabler.get("ContentsCode")
    if not region_kode or not innhold:
        raise SystemExit(f"Tabell {TABELL_ID} ser annerledes ut enn ventet — sjekk den på data.ssb.no.")

    maal = velg_folkemengde_maal(innhold["values"], innhold["valueTexts"])

    tilgjengelige = set(variabler[region_kode]["values"])
    regioner = [r for r in [LANDET, *FYLKER] if r in tilgjengelige]
    if LANDET not in regioner:
        raise SystemExit("Fant ikke «hele landet» i tabellen — sjekk regionkodene.")

    stat = _hent_json(API + TABELL_ID, {
        "query": [
            {"code": region_kode, "selection": {"filter": "item", "values": regioner}},
            {"code": "ContentsCode", "selection": {"filter": "item", "values": [maal]}},
            {"code": "Tid", "selection": {"filter": "all", "values": ["*"]}},
        ],
        "response": {"format": "json-stat2"},
    })

    dims, rekkefolge, størrelser = stat["dimension"], stat["id"], stat["size"]
    region_dim = next(d for d in rekkefolge if d.lower().startswith("region"))
    reg_indeks = dims[region_dim]["category"]["index"]
    tid_indeks = dims["Tid"]["category"]["index"]
    posisjon = {d: i for i, d in enumerate(rekkefolge)}

    def verdi(region: str, aar_id: str):
        koord = [0] * len(rekkefolge)
        koord[posisjon[region_dim]] = reg_indeks[region]
        koord[posisjon["Tid"]] = tid_indeks[aar_id]
        flat = 0
        for dim_i, k in enumerate(koord):
            flat = flat * størrelser[dim_i] + k
        return stat["value"][flat]

    landserie = {}
    for aar_id in tid_indeks:
        aar = int(aar_id)
        v = verdi(LANDET, aar_id)
        if aar >= FRA_AAR and v:
            landserie[aar] = int(v)

    siste_aar = max(landserie)
    if landserie[siste_aar] < 1_000_000:
        raise SystemExit(
            f"Landstallet for {siste_aar} er {landserie[siste_aar]:,} — det er "
            "ikke et folketall. Feil måltall er valgt; sjekk tabellens "
            "statistikkvariabler på data.ssb.no."
        )
    fylkestall = {}
    for f in FYLKER:
        if f in reg_indeks:
            v = verdi(f, str(siste_aar))
            if v:
                fylkestall[f] = int(v)

    return landserie, fylkestall, siste_aar


def bygg_snapshot(landserie: dict[int, int], fylkestall: dict[str, int], siste_aar: int) -> dict:
    fmt = lambda n: f"{n:,}".replace(",", " ")
    forste_aar = min(landserie)
    vekst_siden_start = landserie[siste_aar] - landserie[forste_aar]

    vekst_per_tiar = []
    for tiar in range(1950, siste_aar - 9, 10):
        if tiar in landserie and tiar + 10 in landserie:
            vekst_per_tiar.append([tiar, landserie[tiar + 10] - landserie[tiar]])

    return {
        "meta": {
            "tittel": "Fem og en halv million",
            "kilde": "Statistisk sentralbyrå",
            "kilde_url": "https://www.ssb.no/befolkning/folketall/statistikk/befolkning",
            "dato_hentet": date.today().isoformat(),
            "geografi": "Norge, fylker",
            "enhet": "personer",
            "oppdateringsfrekvens": "kvartalsvis",
            # Årstallet interpoleres fra serien. Sto tidligere som «siden krigen», mens
            # tallet gjelder fra seriens første år (1951) — SSBs kommunefordelte serie
            # starter der, ikke i 1945. Formuleringen undervurderte dermed veksten den
            # skulle illustrere, og ville drevet fra hverandre igjen hvis serien endret seg.
            "beskrivelse": (f"Norges befolkning har vokst med nesten to og en halv "
                            f"million siden {forste_aar}. Hvor bor vi nå — og hvor "
                            "gikk veksten?"),
        },
        "visninger": {
            "hero": {
                "type": "hero",
                "eyebrow": "Folketallet",
                "rader": [{"etikett": f"Bosatt i Norge 1. januar {siste_aar}",
                           "verdi": fmt(landserie[siste_aar]),
                           "detalj": f"{fmt(vekst_siden_start)} flere enn i {forste_aar}"}],
                "fotnote": "Registrert bosatt befolkning. Kilde: SSBs befolkningsstatistikk.",
            },
            "utvikling": {"type": "tidslinje",
                          "tittel": f"Befolkningen siden {forste_aar}",
                          "enhet": "personer",
                          "serier": [{"navn": "Befolkning",
                                      "punkter": [[a, v] for a, v in sorted(landserie.items())]}]},
            "fylkeskart": {"type": "kart",
                           "tittel": "Hvor bor vi?",
                           "undertekst": f"bosatte per fylke, {siste_aar}",
                           "enhet": "personer",
                           "verdier": fylkestall},
            "vekst": {"type": "tidslinje", "stil": "søyle",
                      "tittel": "Vekst per tiår",
                      "undertekst": "nye innbyggere per tiår",
                      "enhet": "personer",
                      "x_navn": "Tiår (fra år)",
                      "serier": [{"navn": "Vekst", "punkter": vekst_per_tiar}]},
        },
    }


def main() -> int:
    print(f"Henter folkemengde fra SSB-tabell {TABELL_ID} …")
    landserie, fylkestall, siste_aar = hent_folkemengde()
    print(f"  landserie {min(landserie)}–{siste_aar}, {len(fylkestall)} fylker")

    snapshot = bygg_snapshot(landserie, fylkestall, siste_aar)
    feil = valider_snapshot(snapshot, "befolkning")
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
