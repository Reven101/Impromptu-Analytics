"""Henter kulturbruk etter utdanningsnivå → innhold/kulturgap/data.json.

Kjøring (krever nett mot data.ssb.no):

    python3 pipeline/hent_ssb_kulturgap.py
    python3 pipeline/bygg_manifest.py

Bruker SSB-tabell 13504 («Bruk av ulike kulturtilbud, etter kjønn og
utdanningsnivå») via det åpne PxWeb-API-et: andelen som har brukt hvert
kulturtilbud siste 12 måneder, fordelt på høyeste fullførte utdanning,
1991–2025. Kjønn aggregeres bort. Faller tabellen bort, søk på
«kulturbarometer» på data.ssb.no og oppdater TABELL_ID.
"""

from __future__ import annotations

import json
import sys
from datetime import date

from hent_ssb_kultur import _hent_json, kortnavn, velg_andel_maal
from kontrakt import INNHOLD_DIR, valider_snapshot

API = "https://data.ssb.no/api/v0/no/table/"
TABELL_ID = "13504"

UTFIL = INNHOLD_DIR / "kulturgap" / "data.json"

# Visningsnavn for utdanningsnivåene, gjenkjent på nøkkelord i SSBs tekster.
# «Alle utdanningsnivå» utelates — historien handler om forskjellene.
UTDNAVN = [
    ("grunnskole", "Grunnskole"),
    ("videregående", "Videregående"),
    ("kort", "Universitet/høgskole, kort"),
    ("lang", "Universitet/høgskole, lang"),
]
GRUNN = "Grunnskole"
LANG = "Universitet/høgskole, lang"
NIVAA_REKKEFOLGE = [navn for _, navn in UTDNAVN]

# Tilbudene som bærer hver sin tidslinje i historien.
FOLKELIG = "Kino"
DELT = "Kunstutstilling"


def utdnavn(tekst: str) -> str | None:
    t = tekst.lower()
    for nokkel, navn in UTDNAVN:
        if nokkel in t:
            return navn
    return None


def hent_kulturgap() -> dict[str, dict[str, dict[int, int]]]:
    """Returnerer {tilbud: {utdanningsnivå: {år: prosent}}}."""
    meta = _hent_json(API + TABELL_ID)
    variabler = {v["code"]: v for v in meta["variables"]}
    innhold = variabler.get("ContentsCode")
    tilbud_kode = next((k for k, v in variabler.items()
                        if "kulturtilbud" in v.get("text", "").lower()), None)
    utd_kode = next((k for k, v in variabler.items()
                     if "utdanning" in v.get("text", "").lower()), None)
    if not innhold or not tilbud_kode or not utd_kode or "Tid" not in variabler:
        raise SystemExit(
            f"Tabell {TABELL_ID} ser annerledes ut enn ventet — sjekk den på data.ssb.no."
        )

    maal = velg_andel_maal(innhold["values"], innhold["valueTexts"])

    utd_valg = {v: utdnavn(t) for v, t in
                zip(variabler[utd_kode]["values"], variabler[utd_kode]["valueTexts"])}
    utd_valg = {v: n for v, n in utd_valg.items() if n}
    if set(utd_valg.values()) != set(NIVAA_REKKEFOLGE):
        raise SystemExit(
            f"Fant ikke alle fire utdanningsnivåene i tabell {TABELL_ID}: "
            f"{variabler[utd_kode]['valueTexts']}"
        )

    query = [
        {"code": tilbud_kode, "selection": {"filter": "item",
                                            "values": variabler[tilbud_kode]["values"]}},
        {"code": utd_kode, "selection": {"filter": "item",
                                         "values": list(utd_valg)}},
        {"code": "ContentsCode", "selection": {"filter": "item", "values": [maal]}},
        {"code": "Tid", "selection": {"filter": "all", "values": ["*"]}},
    ]
    # Øvrige bakgrunnsvariabler (kjønn): utelates der API-et kan aggregere,
    # ellers velges totalkategorien.
    for kode, var in variabler.items():
        if kode in (tilbud_kode, utd_kode, "ContentsCode", "Tid") or var.get("elimination"):
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
    posisjon = {d: i for i, d in enumerate(rekkefolge)}
    indeks = {d: dims[d]["category"]["index"] for d in rekkefolge}
    tilbud_tekst = dims[tilbud_kode]["category"]["label"]

    def verdi(tilbud_id: str, utd_id: str, aar_id: str):
        koord = [0] * len(rekkefolge)
        koord[posisjon[tilbud_kode]] = indeks[tilbud_kode][tilbud_id]
        koord[posisjon[utd_kode]] = indeks[utd_kode][utd_id]
        koord[posisjon["Tid"]] = indeks["Tid"][aar_id]
        flat = 0
        for dim_i, k in enumerate(koord):
            flat = flat * størrelser[dim_i] + k
        return stat["value"][flat]

    serier: dict[str, dict[str, dict[int, int]]] = {}
    for tilbud_id in indeks[tilbud_kode]:
        navn = kortnavn(tilbud_tekst.get(tilbud_id, tilbud_id))
        if not navn:
            continue
        for utd_id, utd in utd_valg.items():
            if utd_id not in indeks[utd_kode]:
                continue
            for aar_id in indeks["Tid"]:
                v = verdi(tilbud_id, utd_id, aar_id)
                if v is None:
                    continue
                if not 0 <= v <= 100:
                    raise SystemExit(
                        f"«{navn}»/{utd} {aar_id}: {v} er ikke en prosentandel — "
                        "feil måltall er valgt; sjekk tabellen på data.ssb.no."
                    )
                serier.setdefault(navn, {}).setdefault(utd, {})[int(aar_id)] = round(v)

    for krav in (FOLKELIG, DELT):
        if len(serier.get(krav, {})) < len(NIVAA_REKKEFOLGE):
            raise SystemExit(
                f"Seriene for «{krav}» mangler utdanningsnivåer. "
                f"Fant tilbud: {sorted(serier)}"
            )
    if max(serier[FOLKELIG][LANG].values()) < 40:
        raise SystemExit(
            "Kino-serien for lang utdanning ser urimelig lav ut — det er "
            "neppe kulturbruksandeler. Sjekk måltallet på data.ssb.no."
        )
    return serier


def bygg_snapshot(serier: dict[str, dict[str, dict[int, int]]]) -> dict:
    siste = max(aar for nivaaer in serier.values()
                for s in nivaaer.values() for aar in s)
    kunst = serier[DELT]

    def tidslinje(tilbud: str, tittel: str) -> dict:
        return {
            "type": "tidslinje",
            "tittel": tittel,
            "undertekst": "andel som har brukt tilbudet siste 12 måneder",
            "enhet": "%",
            "serier": [{"navn": nivaa,
                        "punkter": [[a, v] for a, v in sorted(serier[tilbud][nivaa].items())]}
                       for nivaa in NIVAA_REKKEFOLGE if nivaa in serier[tilbud]],
        }

    kort = []
    for navn, nivaaer in serier.items():
        grunn, lang = nivaaer.get(GRUNN, {}), nivaaer.get(LANG, {})
        if siste not in grunn or siste not in lang:
            continue
        kort.append({"overtittel": navn,
                     "verdi": f"{lang[siste] - grunn[siste]:+d} pp",
                     "detalj": f"{lang[siste]} % mot {grunn[siste]} %"})
    kort.sort(key=lambda k: -int(k["verdi"].split()[0].replace("+", "")))

    return {
        "meta": {
            "tittel": "Kino for alle, opera for de få",
            "kilde": "Statistisk sentralbyrå",
            "kilde_url": "https://www.ssb.no/kultur-og-fritid/tid-og-mediebruk/statistikk/norsk-kulturbarometer",
            "dato_hentet": date.today().isoformat(),
            "geografi": "Norge",
            "enhet": "prosent, etter utdanningsnivå",
            "oppdateringsfrekvens": "hvert andre til fjerde år (kulturbruksundersøkelsen)",
            "beskrivelse": ("Jo lengre utdanning, desto mer kulturbruk — men gapet "
                            "varierer: størst i museet og galleriet, minst på tribunen. "
                            "Og kinoen har nesten klart å lukke det."),
        },
        "visninger": {
            "hero": {
                "type": "hero",
                "eyebrow": "Kulturgapet",
                "rader": [
                    {"etikett": "Med lang universitetsutdanning",
                     "verdi": f"{kunst[LANG][siste]} %",
                     "detalj": f"var på kunstutstilling i {siste}"},
                    {"etikett": "Med grunnskoleutdanning",
                     "verdi": f"{kunst[GRUNN][siste]} %",
                     "detalj": "samme spørsmål, samme år"},
                ],
                "fotnote": ("Andel som har brukt tilbudet siste 12 måneder, etter "
                            "høyeste fullførte utdanning. "
                            "Kilde: Norsk kulturbarometer (SSB)."),
            },
            "folkelig": tidslinje(FOLKELIG, "Kino: gapet som krymper"),
            "delt": tidslinje(DELT, "Kunstutstilling: gapet som består"),
            "gap": {
                "type": "kortgalleri",
                "tittel": f"Gapet, tilbud for tilbud ({siste})",
                "undertekst": ("forsprang i prosentpoeng: lang universitets-/høgskole"
                               "utdanning mot grunnskole"),
                "kort": kort,
            },
        },
    }


def main() -> int:
    print(f"Henter kulturbruk etter utdanning fra SSB-tabell {TABELL_ID} …")
    serier = hent_kulturgap()
    kunst = serier[DELT]
    siste = max(kunst[LANG])
    print(f"  {len(serier)} kulturtilbud × {len(NIVAA_REKKEFOLGE)} utdanningsnivå; "
          f"kunstutstilling {siste}: {kunst[LANG][siste]} % (lang) mot "
          f"{kunst[GRUNN][siste]} % (grunnskole) — rimelig?")

    snapshot = bygg_snapshot(serier)
    feil = valider_snapshot(snapshot, "kulturgap")
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
