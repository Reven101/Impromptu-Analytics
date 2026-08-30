"""Henter norsk matimport fra ett land (standard Italia) fra SSBs PxWeb-API.

Kjøring (krever nett mot data.ssb.no):

    python pipeline/hent_ssb_matimport.py
    python pipeline/hent_ssb_matimport.py --land Italia --html

Bruker SSB-tabell 08809 («Utenrikshandel med varer, etter varegruppe (en- og
tosifret SITC) og land/handelsområde/verdensdel», årlig fra 1988). Scriptet
henter HELE varegruppedimensjonen for landet og klassifiserer først ved lesing,
fordi kodene i SITC-dimensjonen ikke er stabile nok til å hardkodes.

«Mat» = SITC-seksjon 0, *Matvarer og levende dyr*. Drikkevarer og tobakk er
SITC-seksjon 1 og rapporteres for seg — for Italia er vin en stor post, så
tallet endrer seg mye med hvilken definisjon du velger. Deklarer alltid hvilken
av de to du siterer.

Trenger du ferskere tall enn siste hele år: samme struktur finnes månedlig i
tabell 08806 (`--tabell 08806`). Faller tabellen bort, søk «utenrikshandel med
varer varegruppe SITC land» på data.ssb.no og oppdater TABELL_ID.

Skriver snapshot til pipeline/cache/ssb_matimport_<land>.json og — med --html —
en frittstående diagramside i samme mappe. Dette er ikke en publisert historie:
skal tallene bli en, kopier snapshotet inn i historier/innhold/<slug>/data.json
på kontraktsformen (se kontrakt.py) og skriv tekst.md.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
import urllib.request
from datetime import date
from pathlib import Path

import kontrakt  # noqa: F401  — importen setter UTF-8 på Windows-konsollen

API = "https://data.ssb.no/api/v0/no/table/"
TABELL_ID = "08809"
KILDE_URL = "https://www.ssb.no/statbank/table/08809"

CACHE_DIR = Path(__file__).resolve().parent / "cache"

# SITC-seksjonene vi bryr oss om, gjenkjent på nøkkelord i SSBs varegruppetekst.
SEKSJONER = {
    "0": ("mat", ("matvarer", "levende dyr")),
    "1": ("drikke_tobakk", ("drikkevarer", "tobakk")),
}

# Ledende SITC-kode i en varegruppetekst: «05 Frukt og grønnsaker» → «05».
LEDENDE_KODE = re.compile(r"^\s*(\d{1,2})\b")


def _hent_json(url: str, body: dict | None = None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Impromptu-Analytics-datainnsamling (kontakt: kontakt@impromptu.no)",
        } if body else {
            "User-Agent": "Impromptu-Analytics-datainnsamling (kontakt: kontakt@impromptu.no)",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as svar:
        return json.loads(svar.read().decode("utf-8"))


def _flat(tekst: str) -> str:
    """Små bokstaver uten diakritikk — «Elfenbenskysten»/«Cote d'Ivoire»-hjelp."""
    return "".join(
        c for c in unicodedata.normalize("NFD", tekst.lower())
        if unicodedata.category(c) != "Mn"
    )


def finn_variabel(variabler: dict, *nokkelord: str) -> str | None:
    for kode, var in variabler.items():
        tekst = _flat(var.get("text", "")) + " " + _flat(kode)
        if any(n in tekst for n in nokkelord):
            return kode
    return None


def velg_land(var: dict, land: str) -> str:
    """Finner landkoden. Eksakt treff først — «Italia» skal ikke bli «Italia unntatt …»."""
    ønsket = _flat(land)
    par = list(zip(var["values"], var["valueTexts"]))
    for verdi, tekst in par:
        if _flat(tekst) == ønsket:
            return verdi
    treff = [(v, t) for v, t in par if ønsket in _flat(t)]
    if len(treff) == 1:
        return treff[0][0]
    if treff:
        raise SystemExit(
            f"«{land}» er tvetydig i tabell {TABELL_ID}. Kandidater: "
            + ", ".join(f"{t} ({v})" for v, t in treff[:10])
        )
    raise SystemExit(
        f"Fant ikke «{land}» blant landene i tabell {TABELL_ID}. "
        "Kjør med --vis-metadata for å se listen."
    )


def velg_import(variabler: dict, brukt: set[str]) -> tuple[list[dict], str, str | None]:
    """Velger importsiden av handelen.

    Tabellene finnes i to former: enten er import og eksport egne måltall under
    ContentsCode, eller så ligger de som verdier i en egen imp/eks-variabel.
    Returnerer (query-ledd, valgt ContentsCode, valgt imp/eks-verdi).
    """
    innhold = variabler.get("ContentsCode")
    if not innhold:
        raise SystemExit(f"Tabell {TABELL_ID} mangler ContentsCode — sjekk den på data.ssb.no.")

    def er_import(tekst: str) -> bool:
        t = _flat(tekst)
        return ("import" in t or "innfor" in t) and "eksport" not in t

    # Form A: egen imp/eks-dimensjon.
    for kode, var in variabler.items():
        if kode in brukt or kode in ("ContentsCode", "Tid"):
            continue
        treff = [v for v, t in zip(var["values"], var["valueTexts"]) if er_import(t)]
        if treff and len(treff) < len(var["values"]):
            maal = velg_verdimaal(innhold)
            return ([{"code": kode, "selection": {"filter": "item", "values": [treff[0]]}}],
                    maal, treff[0])

    # Form B: import som eget måltall.
    treff = [v for v, t in zip(innhold["values"], innhold["valueTexts"]) if er_import(t)]
    if not treff:
        raise SystemExit(
            f"Fant ikke importsiden i tabell {TABELL_ID}. Måltall: {innhold['valueTexts']}"
        )
    return ([], treff[0], None)


def velg_verdimaal(innhold: dict) -> str:
    """Måltallet som bærer kroneverdien — ikke vekt/mengde."""
    def poeng(tekst: str) -> int:
        t = _flat(tekst)
        if any(o in t for o in ("kg", "vekt", "mengde", "kvantum", "tonn")):
            return -1
        return 2 if any(o in t for o in ("verdi", "kr", "kroner")) else 0

    beste = max(zip(innhold["values"], innhold["valueTexts"]), key=lambda kt: poeng(kt[1]))
    if poeng(beste[1]) < 0:
        raise SystemExit(
            f"Tabell {TABELL_ID} ser bare ut til å ha mengdemål, ikke verdi: "
            f"{innhold['valueTexts']}"
        )
    return beste[0]


def sitc_kode(kode: str, tekst: str) -> str | None:
    m = LEDENDE_KODE.match(kode) or LEDENDE_KODE.match(tekst)
    return m.group(1) if m else None


def hent(land: str, tabell: str, vis_metadata: bool) -> dict:
    meta = _hent_json(API + tabell)
    variabler = {v["code"]: v for v in meta["variables"]}

    if vis_metadata:
        print(f"Tabell {tabell}: {meta.get('title', '')}\n")
        for kode, var in variabler.items():
            print(f"  {kode} — {var.get('text', '')} ({len(var['values'])} verdier)"
                  + (" [elimination]" if var.get("elimination") else ""))
            for v, t in list(zip(var["values"], var["valueTexts"]))[:12]:
                print(f"      {v!r:>10} {t}")
            if len(var["values"]) > 12:
                print(f"      … {len(var['values']) - 12} til")
        print()

    land_kode = finn_variabel(variabler, "land", "handelsomrade")
    vare_kode = finn_variabel(variabler, "varegruppe", "sitc", "vare")
    if not land_kode or not vare_kode or "Tid" not in variabler:
        raise SystemExit(
            f"Tabell {tabell} ser annerledes ut enn ventet (fant ikke land-, vare- eller "
            f"tidsdimensjon). Variabler: {list(variabler)}. Kjør med --vis-metadata."
        )

    landverdi = velg_land(variabler[land_kode], land)
    brukt = {land_kode, vare_kode}
    imp_ledd, maal, _ = velg_import(variabler, brukt)

    query = [
        {"code": land_kode, "selection": {"filter": "item", "values": [landverdi]}},
        {"code": vare_kode, "selection": {"filter": "item",
                                          "values": variabler[vare_kode]["values"]}},
        *imp_ledd,
        {"code": "ContentsCode", "selection": {"filter": "item", "values": [maal]}},
        {"code": "Tid", "selection": {"filter": "all", "values": ["*"]}},
    ]
    valgt = {ledd["code"] for ledd in query}
    # Øvrige bakgrunnsvariabler: dropp der API-et kan aggregere, ellers totalkategorien.
    for kode, var in variabler.items():
        if kode in valgt or var.get("elimination"):
            continue
        total = next(
            (v for v, t in zip(var["values"], var["valueTexts"])
             if any(o in _flat(t) for o in ("alle", "begge", "i alt", "total"))),
            var["values"][0],
        )
        query.append({"code": kode, "selection": {"filter": "item", "values": [total]}})

    stat = _hent_json(API + tabell, {"query": query, "response": {"format": "json-stat2"}})
    return les(stat, vare_kode, land, tabell)


def les(stat: dict, vare_kode: str, land: str, tabell: str) -> dict:
    dims, rekkefolge, størrelser = stat["dimension"], stat["id"], stat["size"]
    posisjon = {d: i for i, d in enumerate(rekkefolge)}
    indeks = {d: dims[d]["category"]["index"] for d in rekkefolge}
    etikett = dims[vare_kode]["category"]["label"]

    enhet_info = list(dims["ContentsCode"]["category"].get("unit", {}).values())
    enhet = enhet_info[0].get("base", "kr") if enhet_info else "kr"

    def verdi(vare_id: str, aar_id: str):
        koord = [0] * len(rekkefolge)
        koord[posisjon[vare_kode]] = indeks[vare_kode][vare_id]
        koord[posisjon["Tid"]] = indeks["Tid"][aar_id]
        flat = 0
        for dim_i, k in enumerate(koord):
            flat = flat * størrelser[dim_i] + k
        return stat["value"][flat]

    aarene = sorted(int(a) for a in indeks["Tid"])
    serier: dict[str, dict[int, float]] = {navn: {} for navn, _ in SEKSJONER.values()}
    divisjoner: dict[str, dict[int, float]] = {}
    divisjonsnavn: dict[str, str] = {}
    totalt: dict[int, float] = {}

    for vare_id in indeks[vare_kode]:
        tekst = etikett.get(vare_id, vare_id)
        kode = sitc_kode(vare_id, tekst)
        rad = {int(a): verdi(vare_id, a) for a in indeks["Tid"]}
        rad = {a: v for a, v in rad.items() if v is not None}

        if kode is None:
            if any(o in _flat(tekst) for o in ("i alt", "alle varer", "total")):
                totalt = rad
            continue
        if len(kode) == 1:
            seksjon = SEKSJONER.get(kode)
            if seksjon and all(n in _flat(tekst) for n in seksjon[1]):
                serier[seksjon[0]] = rad
            elif seksjon:
                raise SystemExit(
                    f"SITC-seksjon {kode} heter «{tekst}» i tabell {tabell} — "
                    "ikke det ventede. Sjekk tabellen før du stoler på tallene."
                )
        elif len(kode) == 2 and kode[0] in SEKSJONER:
            divisjoner[kode] = rad
            divisjonsnavn[kode] = tekst

    for navn in ("mat", "drikke_tobakk"):
        if not serier.get(navn):
            raise SystemExit(
                f"Fant ingen tall for SITC-seksjonen «{navn}» for {land} i tabell {tabell}. "
                "Kjør med --vis-metadata og se på varegruppedimensjonen."
            )

    siste = max(serier["mat"])

    # Kanarifugl: divisjonene 0x skal summere seg til seksjon 0. Slår det ikke til,
    # er en av dem noe annet enn vi tror — da er hele tallet upålitelig.
    sum_0x = sum(r.get(siste, 0) for k, r in divisjoner.items() if k[0] == "0")
    fasit = serier["mat"][siste]
    if fasit and abs(sum_0x - fasit) / fasit > 0.02:
        raise SystemExit(
            f"Kontrollsummen slår ikke til for {siste}: divisjonene 0x summerer til "
            f"{sum_0x:,.0f}, seksjon 0 er {fasit:,.0f}. Varegruppedimensjonen ser "
            "annerledes ut enn scriptet antar — kjør med --vis-metadata."
        )

    return {
        "hentet": date.today().isoformat(),
        "tabell": tabell,
        "kilde": "Statistisk sentralbyrå",
        "kilde_url": KILDE_URL,
        "land": land,
        "retning": "import til Norge",
        "enhet": enhet,
        "definisjon": "mat = SITC-seksjon 0 (matvarer og levende dyr); "
                      "drikke_tobakk = SITC-seksjon 1, holdt utenfor mat-tallet",
        "aarene": aarene,
        "siste_aar": siste,
        "serier": {navn: {str(a): v for a, v in sorted(rad.items())}
                   for navn, rad in serier.items()},
        "all_import_fra_landet": {str(a): v for a, v in sorted(totalt.items())} or None,
        # Alle divisjoner tas med — men de er merket med seksjon, fordi 1x
        # (drikkevarer, tobakk) ikke skal blandes inn i mat-sammensetningen.
        "divisjoner_siste_aar": sorted(
            ({"kode": k, "seksjon": k[0], "navn": divisjonsnavn[k], "verdi": r[siste]}
             for k, r in divisjoner.items() if siste in r),
            key=lambda d: -d["verdi"],
        ),
    }


def kroner(v: float, enhet: str) -> str:
    kr = v * 1000 if "1 000" in enhet or "1000" in enhet else v
    for grense, navn in ((1e9, "mrd."), (1e6, "mill.")):
        if abs(kr) >= grense:
            return f"{kr / grense:,.1f} {navn} kr".replace(",", " ").replace(".", ",", 1)
    return f"{kr:,.0f} kr".replace(",", " ")


def skriv_ut(d: dict) -> None:
    siste, enhet = d["siste_aar"], d["enhet"]
    mat = d["serier"]["mat"][str(siste)]
    drikke = d["serier"]["drikke_tobakk"].get(str(siste))
    print(f"\nMatimport fra {d['land']}, {siste} (SSB tabell {d['tabell']}, enhet: {enhet})")
    print("─" * 62)
    print(f"  SITC 0  Matvarer og levende dyr   {kroner(mat, enhet):>22}")
    if drikke is not None:
        print(f"  SITC 1  Drikkevarer og tobakk    {kroner(drikke, enhet):>22}")
        print(f"  0 + 1   Mat og drikke            {kroner(mat + drikke, enhet):>22}")
    alt = (d.get("all_import_fra_landet") or {}).get(str(siste))
    if alt:
        print(f"\n  Andel av all vareimport fra {d['land']}: "
              f"{100 * mat / alt:.1f}".replace(".", ",") + f" % (av {kroner(alt, enhet)})")
    tidligst = min(int(a) for a in d["serier"]["mat"])
    forste = d["serier"]["mat"][str(tidligst)]
    if forste:
        print(f"  Vekst siden {tidligst}: {100 * (mat / forste - 1):+.0f} % (løpende kroner)")
    drikkerader = [r for r in d["divisjoner_siste_aar"] if r["seksjon"] == "1"]
    if drikkerader:
        print("\n  Drikkevarer og tobakk, til sammenligning:")
        for rad in drikkerader:
            print(f"    {rad['kode']}  {rad['navn'][:44]:<44} {kroner(rad['verdi'], enhet):>18}")
    print("\n  Hva maten er (tosifret SITC, seksjon 0):")
    for rad in [r for r in d["divisjoner_siste_aar"] if r["seksjon"] == "0"][:8]:
        andel = f"{100 * rad['verdi'] / mat:.1f}".replace(".", ",") if mat else "–"
        print(f"    {rad['kode']}  {rad['navn'][:44]:<44} {kroner(rad['verdi'], enhet):>18}"
              f"  {andel:>5} %")
    print()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--land", default="Italia")
    p.add_argument("--tabell", default=TABELL_ID)
    p.add_argument("--vis-metadata", action="store_true",
                   help="dump tabellens variabler og verdier før uttrekket")
    p.add_argument("--html", action="store_true",
                   help="skriv også en frittstående diagramside ved siden av snapshotet")
    args = p.parse_args()

    data = hent(args.land, args.tabell, args.vis_metadata)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    slug = _flat(args.land).replace(" ", "_")
    utfil = CACHE_DIR / f"ssb_matimport_{slug}.json"
    utfil.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    skriv_ut(data)
    print(f"✓ Snapshot: {utfil}")

    if args.html:
        from lag_matimport_side import skriv_side
        side = skriv_side(data, CACHE_DIR / f"ssb_matimport_{slug}.html")
        print(f"✓ Diagramside: {side}")


if __name__ == "__main__":
    main()
