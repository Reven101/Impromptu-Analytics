"""Henter SSBs navnestatistikk og skriver snapshot til innhold/navn/data.json.

Kjøring (krever nett mot data.ssb.no):

    python3 pipeline/hent_ssb_navn.py
    python3 pipeline/bygg_manifest.py

Datakilde: SSB-tabell 10467, «Fødte, etter fornavn og år».
Primærkilde er PxWebApi v2 direkte mot tabell-ID-en:

    https://data.ssb.no/api/pxwebapi/v2/tables/10467/...

Faller v2 bort, prøves det eldre PxWeb-API-et (v0) mot samme tabell.

Kjønn er ikke egen variabel i tabellen: det ligger som sifferprefiks i
Fornavn-kodene («1ADA» = jentenavn, «2AKSEL» = guttenavn). Parseren leser
prefikset og VERIFISERER antakelsen 1=jenter/2=gutter mot kjente
ankernavn (Emma/Nora mot Jakob/Noah m.fl.) — er prefiksene motsatt,
byttes gruppene automatisk; er ankrene tvetydige, nektes skriving.
Snapshots er statiske filer — nettsiden spør aldri SSB direkte.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date

from kontrakt import INNHOLD_DIR, valider_snapshot

TABELL_ID = "10467"  # Fødte, etter fornavn og år
API_V2 = "https://data.ssb.no/api/pxwebapi/v2/tables/"
API_V0 = "https://data.ssb.no/api/v0/no/table/"
FRA_AAR = 1946          # nyere del av serien: komplett og relevant for fødselsår
ANTALL_SERIER = 4       # navn per tidslinje (maks 6 — validert palett)

UTFIL = INNHOLD_DIR / "navn" / "data.json"


def _hent_json(url: str, body: dict | None = None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"} if body else {}
    )
    with urllib.request.urlopen(req, timeout=300) as svar:
        return json.loads(svar.read().decode("utf-8"))


# ------------------------------------------------------------ henting ----

def _tidskoder_fra_metadata(meta: dict) -> list[str]:
    """Årskoder >= FRA_AAR fra v2-metadataene (tåler begge kjente former)."""
    variabler = meta.get("variables") or []
    for v in variabler:
        kode = (v.get("id") or v.get("code") or "").lower()
        if kode == "tid" or v.get("type") == "TimeVariable":
            verdier = v.get("values") or []
            koder = [w.get("code", w) if isinstance(w, dict) else w for w in verdier]
            return [k for k in koder if str(k).isdigit() and int(k) >= FRA_AAR]
    # json-stat2-formet metadata
    for kode, dim in (meta.get("dimension") or {}).items():
        if kode.lower() == "tid":
            return [k for k in dim["category"]["index"]
                    if str(k).isdigit() and int(k) >= FRA_AAR]
    raise ValueError("fant ingen tidsvariabel i metadataene")


def _variabelkoder_fra_metadata(meta: dict) -> list[str]:
    if meta.get("variables"):
        return [v.get("id") or v.get("code") for v in meta["variables"]]
    return list(meta.get("dimension") or [])


def hent_v2(tabell_id: str) -> dict:
    """PxWebApi v2: metadata for variabel- og årskodene, data som json-stat2."""
    meta = _hent_json(f"{API_V2}{tabell_id}/metadata?lang=no")
    aar = _tidskoder_fra_metadata(meta)
    params = {"lang": "no", "outputFormat": "json-stat2"}
    for kode in _variabelkoder_fra_metadata(meta):
        params[f"valueCodes[{kode}]"] = ",".join(aar) if kode.lower() == "tid" else "*"
    return _hent_json(f"{API_V2}{tabell_id}/data?{urllib.parse.urlencode(params)}")


def hent_v0(tabell_id: str) -> dict:
    """Eldre PxWeb-API (v0): alt i én POST, filtrerer år under parsing."""
    meta = _hent_json(API_V0 + tabell_id)
    sporring = {
        "query": [
            {"code": v["code"], "selection": {"filter": "all", "values": ["*"]}}
            for v in meta["variables"]
        ],
        "response": {"format": "json-stat2"},
    }
    return _hent_json(API_V0 + tabell_id, sporring)


# ------------------------------------------------------- json-stat2 ----

def _klassifiser_dimensjoner(stat: dict) -> tuple[str, str, str | None, dict]:
    """Finner (navn-dim, tid-dim, kjønn-dim, faste_valg) i et json-stat2-svar.

    Dimensjoner som verken er fornavn, tid eller kjønn (typisk ContentsCode)
    låses til én verdi i faste_valg — fortrinnsvis et antall/fødte-mål.
    """
    dims = stat["dimension"]
    navn_dim = tid_dim = kjonn_dim = None
    faste: dict[str, str] = {}

    for kode in stat["id"]:
        etikett = (dims[kode].get("label") or kode).lower()
        n = kode.lower()
        if "fornavn" in n or "fornavn" in etikett:
            navn_dim = kode
        elif n == "tid" or etikett in ("år", "aar", "year"):
            tid_dim = kode
        elif "kjønn" in etikett or "kjonn" in n or n == "kjonn" or n == "sex":
            kjonn_dim = kode

    for kode in stat["id"]:
        if kode in (navn_dim, tid_dim, kjonn_dim):
            continue
        kategori = dims[kode]["category"]
        etiketter = kategori.get("label", {})
        koder = list(kategori["index"])
        # skjuler kjønnsdelingen seg i et måltall-sett (f.eks. «Jenter, antall»)?
        if kjonn_dim is None and len(koder) > 1:
            tekster = " ".join(str(t).lower() for t in etiketter.values())
            if ("jent" in tekster or "kvinn" in tekster) and ("gutt" in tekster or "menn" in tekster):
                kjonn_dim = kode
                continue
        # ellers: lås til antalls-/fødte-målet, eller første verdi
        valgt = next((k for k in koder
                      if any(o in str(etiketter.get(k, "")).lower()
                             for o in ("fød", "antall", "person"))), koder[0])
        faste[kode] = valgt

    if not navn_dim or not tid_dim:
        raise ValueError(f"uventet tabellform — fant dimensjonene {stat['id']}")
    return navn_dim, tid_dim, kjonn_dim, faste


def _kjonn_gruppe(etikett: str) -> str | None:
    t = etikett.lower()
    if any(o in t for o in ("jent", "kvinn", "pike")):
        return "jenter"
    if any(o in t for o in ("gutt", "menn", "mann")):
        return "gutter"
    return None


# Antakelse for sifferprefikset i Fornavn-kodene — verifiseres mot ankernavnene.
PREFIKS_GRUPPE = {"1": "jenter", "2": "gutter"}
JENTE_ANKER = ("Emma", "Nora", "Anne", "Ida")
GUTTE_ANKER = ("Jakob", "Noah", "Jan", "Thomas")


def _verifiser_kjonnsdeling(ut: dict, kan_bytte: bool) -> dict:
    """Sjekker gruppene mot ankernavn alle kjenner kjønnet på.

    Hvert ankernavn skal ha klart størst totalsum i sin egen gruppe.
    Peker alle ankrene motsatt vei og delingen kom fra prefiks-antakelsen,
    byttes gruppene om. Tvetydige ankre stopper kjøringen — da skal ingen
    snapshot skrives.
    """
    def total(gruppe: str, navn: str) -> int:
        return sum(ut[gruppe].get(navn, {}).values())

    stemmer = mot = 0
    for navn, hjemme in [(n, "jenter") for n in JENTE_ANKER] + [(n, "gutter") for n in GUTTE_ANKER]:
        borte = "gutter" if hjemme == "jenter" else "jenter"
        t_hjemme, t_borte = total(hjemme, navn), total(borte, navn)
        if t_hjemme == t_borte == 0:
            continue  # ankeret finnes ikke i datasettet
        if t_hjemme > t_borte:
            stemmer += 1
        elif t_borte > t_hjemme:
            mot += 1

    if stemmer >= 2 and mot == 0:
        return ut
    if mot >= 2 and stemmer == 0 and kan_bytte:
        print("  NB: kjønnsprefiksene var motsatt av antatt — gruppene er byttet om")
        return {"jenter": ut["gutter"], "gutter": ut["jenter"]}
    raise SystemExit(
        f"Kjønnsdelingen lot seg ikke verifisere mot ankernavnene "
        f"({stemmer} stemmer, {mot} imot av {len(JENTE_ANKER) + len(GUTTE_ANKER)}). "
        "Sjekk Fornavn-kodene i tabellen på data.ssb.no — skriver ikke snapshot."
    )


def parse_navnedata(stat: dict) -> dict[str, dict[str, dict[int, int]]]:
    """json-stat2 → {"jenter"|"gutter": {navn: {år: antall}}}."""
    navn_dim, tid_dim, kjonn_dim, faste = _klassifiser_dimensjoner(stat)
    dims, rekkefolge, størrelser = stat["dimension"], stat["id"], stat["size"]

    def kategorier(kode):
        kat = dims[kode]["category"]
        koder = sorted(kat["index"], key=kat["index"].get)
        return koder, kat.get("label", {})

    navnekoder, navnetekst = kategorier(navn_dim)
    tidskoder, _ = kategorier(tid_dim)
    posisjon = {d: i for i, d in enumerate(rekkefolge)}

    faste_indekser = {d: dims[d]["category"]["index"][kode] for d, kode in faste.items()}

    def flat(koord: dict[str, int]) -> int:
        i = 0
        for dim_i, d in enumerate(rekkefolge):
            i = i * størrelser[dim_i] + koord.get(d, 0)
        return i

    def serie_for(navn_i: int, ekstra: dict[str, int]) -> dict[int, int]:
        serie = {}
        for ti, tid_id in enumerate(tidskoder):
            if not str(tid_id).isdigit() or int(tid_id) < FRA_AAR:
                continue
            v = stat["value"][flat({**faste_indekser, **ekstra,
                                    navn_dim: navn_i, tid_dim: ti})]
            if v:
                serie[int(tid_id)] = int(v)
        return serie

    ut: dict[str, dict[str, dict[int, int]]] = {"jenter": {}, "gutter": {}}

    if kjonn_dim:
        # egen kjønnsvariabel (eller kjønnsdelte måltall)
        kjonnkoder, kjonntekst = kategorier(kjonn_dim)
        grupper = [(g, {kjonn_dim: dims[kjonn_dim]["category"]["index"][k]})
                   for k in kjonnkoder
                   if (g := _kjonn_gruppe(str(kjonntekst.get(k, k))))]
        if {g for g, _ in grupper} != {"jenter", "gutter"}:
            raise ValueError("fant ikke både jenter og gutter i kjønnsvariabelen")
        for gruppe, kjonn_koord in grupper:
            for ni, navn_id in enumerate(navnekoder):
                navn = str(navnetekst.get(navn_id, navn_id)).strip().title()
                serie = serie_for(ni, kjonn_koord)
                if serie:
                    ut[gruppe][navn] = serie
        return _verifiser_kjonnsdeling(ut, kan_bytte=False)

    # ingen kjønnsdimensjon: kjønnet ligger som sifferprefiks i
    # Fornavn-kodene («1ADA» = jente, «2AKSEL» = gutt)
    treff = 0
    for ni, navn_id in enumerate(navnekoder):
        gruppe = PREFIKS_GRUPPE.get(str(navn_id)[:1])
        if not gruppe:
            continue
        treff += 1
        navn = str(navnetekst.get(navn_id, navn_id)).strip()
        if navn[:1] in PREFIKS_GRUPPE:
            navn = navn[1:]  # etiketten kan bære samme prefiks som koden
        navn = navn.strip().title()
        serie = serie_for(ni, {})
        if serie:
            ut[gruppe].setdefault(navn, {}).update(serie)

    if not navnekoder or treff / len(navnekoder) < 0.9:
        raise ValueError(
            "Fornavn-kodene har verken kjønnsvariabel eller ventet "
            f"sifferprefiks (1/2) — sjekk tabell {TABELL_ID} på data.ssb.no"
        )
    return _verifiser_kjonnsdeling(ut, kan_bytte=True)


# ------------------------------------------------------- snapshot ----

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
    print(f"Henter tabell {TABELL_ID} («Fødte, etter fornavn og år») fra SSB …")
    try:
        stat = hent_v2(TABELL_ID)
        print("  hentet via PxWebApi v2")
    except Exception as e:
        print(f"  PxWebApi v2 feilet ({e}) — prøver eldre API (v0) …")
        stat = hent_v0(TABELL_ID)
        print("  hentet via PxWeb-API v0")

    data = parse_navnedata(stat)
    print(f"  {len(data['jenter'])} jentenavn, {len(data['gutter'])} guttenavn")

    snapshot = bygg_snapshot(data["jenter"], data["gutter"])
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
