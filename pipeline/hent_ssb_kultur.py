"""Henter Norsk kulturbarometer og skriver snapshot til innhold/kultur/data.json.

Kjøring (krever nett mot data.ssb.no):

    python3 pipeline/hent_ssb_kultur.py
    python3 pipeline/bygg_manifest.py

Bruker SSB-tabell 13503 («Bruk av ulike kulturtilbud, etter kjønn og alder»)
via det åpne PxWeb-API-et: andelen av befolkningen som har brukt hvert
kulturtilbud siste 12 måneder, som tidsserie fra 1991. Undersøkelsen går
omtrent hvert fjerde år, så seriene har hull mellom målingene — det er
riktig, ikke en feil. Faller tabellen bort, søk på «kulturbarometer» på
data.ssb.no og oppdater TABELL_ID.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import date

from kontrakt import INNHOLD_DIR, valider_snapshot

API = "https://data.ssb.no/api/v0/no/table/"
TABELL_ID = "13503"
PANDEMIAAR = 2021

UTFIL = INNHOLD_DIR / "kultur" / "data.json"

# Visningsnavn for tilbudene — SSBs kategoritekster er lange og varierer
# mellom bokmål og nynorsk, så vi gjenkjenner dem på nøkkelord.
KORTNAVN = [
    ("kino", "Kino"),
    ("idrett", "Idrettsarrangement"),
    ("konsert", "Konsert"),
    ("bibliotek", "Folkebibliotek"),
    ("museum", "Museum"),
    ("teater", "Teater og revy"),
    ("kunstutst", "Kunstutstilling"),
    ("tros", "Tros-/livssynsmøte"),
    ("livssyn", "Tros-/livssynsmøte"),
    ("livsyn", "Tros-/livssynsmøte"),
    ("gudstjenest", "Tros-/livssynsmøte"),
    ("ballett", "Ballett og dans"),
    ("dans", "Ballett og dans"),
    ("opera", "Opera"),
    ("festival", "Kulturfestival"),
]

# Serier per graf — de fem store og de fem lange linjene.
STORE = ["Kino", "Idrettsarrangement", "Konsert", "Folkebibliotek", "Museum"]
LANGE = ["Teater og revy", "Kunstutstilling", "Tros-/livssynsmøte",
         "Ballett og dans", "Opera"]


def _hent_json(url: str, body: dict | None = None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"} if body else {}
    )
    with urllib.request.urlopen(req, timeout=120) as svar:
        return json.loads(svar.read().decode("utf-8"))


def kortnavn(tekst: str) -> str | None:
    """Mapper SSBs kategoritekst til visningsnavn — None = utelates.

    Digitale tilbud og «i alt»-aggregater hoppes over: de digitale seriene
    starter først i 2021 og ville gjort tidslinjene misvisende.
    """
    t = tekst.lower()
    if any(o in t for o in ("digital", "internett", "strøym", "strømm", "i alt")):
        return None
    for nokkel, navn in KORTNAVN:
        if nokkel in t:
            return navn
    return tekst  # ukjent tilbud — vis SSBs egen tekst


def velg_andel_maal(koder: list[str], tekster: list[str]) -> str:
    """Velger andels-målet (prosent som har brukt tilbudet) — aldri
    gjennomsnittlig antall besøk, som også ligger i tabellen."""
    def poeng(tekst: str) -> int:
        t = tekst.lower()
        if any(o in t for o in ("besøk", "gonger", "ganger", "gjennomsnitt", "tal på")):
            return -1
        if any(o in t for o in ("andel", "prosent", "del av")):
            return 2
        return 0

    beste = max(zip(koder, tekster), key=lambda kt: poeng(kt[1]))
    if poeng(beste[1]) <= 0:
        raise SystemExit(
            f"Fant ikke andels-målet i tabell {TABELL_ID}. "
            f"Tilgjengelige mål: {tekster}"
        )
    return beste[0]


def hent_kulturbruk() -> dict[str, dict[int, int]]:
    """Returnerer {tilbud: {år: prosent}} for alle analoge kulturtilbud."""
    meta = _hent_json(API + TABELL_ID)
    variabler = {v["code"]: v for v in meta["variables"]}
    innhold = variabler.get("ContentsCode")
    if not innhold or "Tid" not in variabler:
        raise SystemExit(
            f"Tabell {TABELL_ID} ser annerledes ut enn ventet — sjekk den på data.ssb.no."
        )

    tilbud_kode = next(
        (k for k, v in variabler.items()
         if k not in ("ContentsCode", "Tid") and "kultur" in v.get("text", "").lower()),
        None,
    )
    if not tilbud_kode:
        raise SystemExit(
            f"Fant ikke kulturtilbud-variabelen i tabell {TABELL_ID}. "
            f"Variabler: {[(k, v.get('text')) for k, v in variabler.items()]}"
        )

    maal = velg_andel_maal(innhold["values"], innhold["valueTexts"])

    query = [
        {"code": tilbud_kode, "selection": {"filter": "all", "values": ["*"]}},
        {"code": "ContentsCode", "selection": {"filter": "item", "values": [maal]}},
        {"code": "Tid", "selection": {"filter": "all", "values": ["*"]}},
    ]
    # Kjønn/alder og andre bakgrunnsvariabler: utelat dem der API-et kan
    # aggregere selv, ellers velg totalkategorien («begge kjønn», «alle»).
    for kode, var in variabler.items():
        if kode in (tilbud_kode, "ContentsCode", "Tid"):
            continue
        if var.get("elimination"):
            continue
        total = next(
            (v for v, t in zip(var["values"], var["valueTexts"])
             if any(o in t.lower() for o in ("alle", "begge", "i alt", "total"))),
            var["values"][0],
        )
        query.append({"code": kode, "selection": {"filter": "item", "values": [total]}})

    stat = _hent_json(API + TABELL_ID, {
        "query": query, "response": {"format": "json-stat2"},
    })

    dims, rekkefolge, størrelser = stat["dimension"], stat["id"], stat["size"]
    tilbud_indeks = dims[tilbud_kode]["category"]["index"]
    tilbud_tekst = dims[tilbud_kode]["category"]["label"]
    tid_indeks = dims["Tid"]["category"]["index"]
    posisjon = {d: i for i, d in enumerate(rekkefolge)}

    def verdi(tilbud_id: str, aar_id: str):
        koord = [0] * len(rekkefolge)
        koord[posisjon[tilbud_kode]] = tilbud_indeks[tilbud_id]
        koord[posisjon["Tid"]] = tid_indeks[aar_id]
        flat = 0
        for dim_i, k in enumerate(koord):
            flat = flat * størrelser[dim_i] + k
        return stat["value"][flat]

    serier: dict[str, dict[int, int]] = {}
    for tilbud_id in tilbud_indeks:
        navn = kortnavn(tilbud_tekst.get(tilbud_id, tilbud_id))
        if not navn:
            continue
        serie = {}
        for aar_id in tid_indeks:
            v = verdi(tilbud_id, aar_id)
            if v is None:
                continue
            if not 0 <= v <= 100:
                raise SystemExit(
                    f"«{navn}» {aar_id}: {v} er ikke en prosentandel — feil "
                    "måltall er valgt; sjekk statistikkvariablene på data.ssb.no."
                )
            serie[int(aar_id)] = round(v)
        if serie:
            serier.setdefault(navn, {}).update(serie)

    for krav in ("Kino", "Konsert"):
        serie = serier.get(krav)
        if not serie or len(serie) < 5 or max(serie.values()) < 40:
            raise SystemExit(
                f"{krav}-serien mangler eller ser urimelig ut — det er ikke "
                f"kulturbruksandeler. Fant serier: {sorted(serier)}"
            )
    return serier


def bygg_snapshot(serier: dict[str, dict[int, int]]) -> dict:
    konsert = serier["Konsert"]
    siste_aar = max(max(s) for s in serier.values())
    siste, forste = max(konsert), min(konsert)
    retning = "opp fra" if konsert[forste] < konsert[siste] else "ned fra"

    def punkter(navn: str):
        return [[a, v] for a, v in sorted(serier[navn].items())]

    def tidslinje(navn_liste: list[str], tittel: str) -> dict:
        return {
            "type": "tidslinje",
            "tittel": tittel,
            "undertekst": "andel som har brukt tilbudet siste 12 måneder",
            "enhet": "%",
            "serier": [{"navn": n, "punkter": punkter(n)}
                       for n in navn_liste if n in serier],
        }

    kort = []
    for navn, serie in sorted(serier.items(), key=lambda ns: -ns[1].get(siste_aar, -1)):
        if siste_aar not in serie:
            continue
        forste = min(serie)
        kort.append({"overtittel": navn,
                     "verdi": f"{serie[siste_aar]} %",
                     "detalj": f"mot {serie[forste]} % i {forste}"})

    return {
        "meta": {
            "tittel": "Konserten tar innpå",
            "kilde": "Statistisk sentralbyrå",
            "kilde_url": "https://www.ssb.no/kultur-og-fritid/tid-og-mediebruk/statistikk/norsk-kulturbarometer",
            "dato_hentet": date.today().isoformat(),
            "geografi": "Norge",
            "enhet": "prosent av befolkningen 9–79 år",
            "oppdateringsfrekvens": "hvert andre til fjerde år (kulturbruksundersøkelsen)",
            "beskrivelse": ("Seks av ti hører livemusikk i året nå — bare kinoen "
                            "samler flere. Tretti år med norske kulturvaner, fra "
                            "bibliotekets stille år til konsertens lange opptur."),
        },
        "visninger": {
            "hero": {
                "type": "hero",
                "eyebrow": "Kulturbruken",
                "rader": [{"etikett": f"Var på konsert i løpet av {siste}",
                           "verdi": f"{konsert[siste]} %",
                           "detalj": f"{retning} {konsert[forste]} % i {forste}"}],
                "fotnote": ("Andel av befolkningen 9–79 år som har brukt tilbudet "
                            "siste 12 måneder. Kilde: Norsk kulturbarometer (SSB)."),
            },
            "storefem": tidslinje(STORE, "De store kulturvanene siden 1991"),
            "lange": tidslinje(LANGE, "De lange linjene"),
            "status": {
                "type": "kortgalleri",
                "tittel": f"Kulturåret {siste_aar}",
                "undertekst": "andel som brukte tilbudet siste 12 måneder",
                "kort": kort,
            },
        },
    }


def main() -> int:
    print(f"Henter kulturbruk fra SSB-tabell {TABELL_ID} …")
    serier = hent_kulturbruk()
    siste = max(serier["Kino"])
    print(f"  {len(serier)} kulturtilbud, kino {siste}: {serier['Kino'][siste]} % "
          "(kontrolltall — rimelig?)")

    snapshot = bygg_snapshot(serier)
    feil = valider_snapshot(snapshot, "kultur")
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
