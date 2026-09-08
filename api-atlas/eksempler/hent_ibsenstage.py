"""IbsenStage — UiOs base over Ibsen-oppsetninger i verden (ibsenstage.hf.uio.no).

Hver kjente oppsetning av et Ibsen-stykke siden 1850-tallet: tittel, verk, dato,
scene, land — og på detaljsiden de medvirkende med funksjon (regissør, oversetter,
skuespiller), produksjonsselskap, status og forestillingsspråk. Rundt 25 000
hendelser i over hundre land.

Kjøring:  python3 api-atlas/eksempler/hent_ibsenstage.py
Nøkkel:   ingen
Lisens:   CC BY-NC-SA 4.0 (oppgitt i sidefoten) — navngivelse, IKKE kommersiell
          bruk, del videre på samme vilkår. Strengere enn resten av atlaset:
          NLOD-kildene her tillater kommersiell bruk, denne gjør det ikke.
          Kontakt: contact-ibsenstage@ibsen.uio.no
Dok:      https://ibsenstage.hf.uio.no/  (ingen API-dokumentasjon finnes)

DETTE ER DEN ENESTE KILDEN I ATLASET UTEN API. Det finnes verken JSON-endepunkt,
eksport eller nedlastingsknapp — bare en paginert HTML-tabell som må parses.
Sjekk derfor alltid denne fila før du skriver ny henting: strukturen er observert,
ikke dokumentert, og den ER endret minst én gang (se «Kolonnene» under).

Endepunkt-mønster (HTML, ikke JSON):
  GET /pages/browse/eventcategory/primary/<kategori>?per_page=<n>
  GET /pages/browse/eventcategory/primary/<kategori>/page/<n>?per_page=<n>
  GET /pages/event/<id>     detaljside: medvirkende, språk, status, datoer
  GET /pages/work/<id>      verket
  GET /pages/venue/<id>     scenen
  Kategoriene er 1–15. 9 finnes ikke, flere er tomme.

Fire ting som gjør skrapingen overkommelig:

1. **`per_page` er en fri parameter.** Standard er 100 (245 sider for kategori 1);
   1000 fungerer, 2500 gir HTTP 500. Hele basen på ~30 forespørsler i stedet
   for 260.
2. **Sidens egen overskrift er fasiten**: «Category: … - Count 24498». Les den ut
   og sammenlign med antall parsede rader. Stemmer det ikke, stopp — en halv
   tabell er verre enn ingen tabell, fordi den ser komplett ut i alt som følger.
3. **Noen få rader gir HTTP 500 uansett sidestørrelse**, også i nettstedets egen
   visning. Del blokka i mindre biter, tell dem som kjente hull, og la ikke åtte
   rader koste 24 000 andre.
4. **Tjeneren er et forskningsarkiv ved UiO uten rate limit-header.** Ingen har
   sagt hva som er greit, så: identifiserende User-Agent, pause mellom kall,
   maks en håndfull samtidige. Mellomlagre rå HTML — 25 000 detaljsider er sju
   timer av noen andres tjener, og den regningen betales én gang.

Kolonnene (bekreftet 1. september 2026 — 9 celler per rad):
  0 Name_SORT  1 Title(+event-id)  2 Work(+work-id)  3 Labels  4 First Date
  5 Venue_SORT 6 Venue(+venue-id)  7 Country         8 Resources
Tidligere hadde tabellen 10 kolonner, med datoen også som sorterbar tallkode
(`20240404`, der `20240000` betydde «bare år kjent»). Den kolonnen er borte, og
«First Date» er nå bare tekst («04 April 2024», eller «2013» når bare året er
kjent) — presisjonen må leses av formen på strengen. `pipeline/hent_ibsenstage.py`
i dette repoet forventer fortsatt 10 kolonner og må rettes før den kjøres igjen.

Personvern: detaljsidene navngir levende personer (skuespillere, regissører,
oversettere). `impromptu/SIKKERHET.md` gjelder — hent bare det analysen trenger,
og legg aldri persondata i et repo som deployer til nettet.

Gull å grave i:
  - Ibsen som eksportvare: hvilke land spiller hva, og når snur repertoaret?
  - Oversettelseskjeder — hvilke språk får stykkene, hvor lenge etter premieren?
  - Kjønn og funksjon over tid: når begynner kvinner å regissere Ibsen?
  - Koblet mot V-Dem eller Verdensbanken: spilles «En folkefiende» oftere der
    demokratiet er under press?
"""

from __future__ import annotations

import html
import re
import sys
import time
import urllib.request

KILDE = "IbsenStage, Universitetet i Oslo"
DOK = "https://ibsenstage.hf.uio.no/"
BASIS = "https://ibsenstage.hf.uio.no"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"

# «Category:» står også i <title>, så mønsteret må holde seg innenfor én
# tekstnode — ellers slukes hele dokumentet mellom tittelen og tellingen.
RE_TELLING = re.compile(r"Category:\s*([^<>]*?)\s*-\s*Count\s*(\d+)")
RE_RAD = re.compile(r'<tr style="line-height: 1;"[^>]*>(.*?)</tr>', re.S)
RE_CELLE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
RE_LENKE = re.compile(r'href="/pages/(\w+)/(\d+)"')
RE_FELT = re.compile(
    r'<th class="record-label[^"]*">\s*(?:<img[^>]*>)?\s*([^<]+?)\s*</th>\s*'
    r'<td class="record-value[^"]*"[^>]*>(.*?)</td>',
    re.S,
)

KOLONNER = ["Name_SORT", "Title", "Work", "Labels", "First Date",
            "Venue_SORT", "Venue", "Country", "Resources"]


def hent_html(sti: str, timeout: int = 120) -> str:
    req = urllib.request.Request(f"{BASIS}{sti}", headers={"User-Agent": BRUKERAGENT})
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return svar.read().decode("utf-8", "replace")


def tekst(celle: str) -> str:
    """Cellens synlige tekst: strip tagger, avkod entiteter, normaliser luft."""
    ren = re.sub(r"<[^>]+>", "", celle)
    ren = html.unescape(ren).replace("\xa0", " ").replace("&nbsp", " ")
    return " ".join(ren.split())


def id_i(celle: str, forventet: str) -> int | None:
    """Radene bærer sine egne id-er i lenkene — den eneste stabile nøkkelen."""
    m = RE_LENKE.search(celle)
    return int(m.group(2)) if m and m.group(1) == forventet else None


def parse_rader(sidehtml: str) -> list[dict]:
    rader = []
    for rad in RE_RAD.findall(sidehtml):
        c = RE_CELLE.findall(rad)
        if len(c) < len(KOLONNER):
            continue
        dato = tekst(c[4])
        ressurs = tekst(c[8])
        rader.append({
            "hendelse_id": id_i(c[1], "event"),
            "tittel": tekst(c[1]),
            "verk": tekst(c[2]),
            "verk_id": id_i(c[2], "work"),
            "merker": [m.strip() for m in tekst(c[3]).split(",") if m.strip()],
            "dato_tekst": dato,
            # Bare året er sikkert: «04 April 2024» og «2013» er samme kolonne.
            "aar": int(m.group()) if (m := re.search(r"\b(1[5-9]|20)\d{2}\b", dato)) else None,
            "scene": tekst(c[6]),
            "scene_id": id_i(c[6], "venue"),
            "land": tekst(c[7]),
            "ressurser": int(ressurs) if ressurs.isdigit() else 0,
        })
    return rader


def parse_detaljer(sidehtml: str) -> dict[str, str]:
    """Detaljsidens felt-tabell: {«First Date»: «4th April 2024», …}.

    De medvirkende ligger i en egen tabell med id «stupidTable» — én rad per
    person med funksjon, rolle og notat. Den parses ikke her; se
    `pipeline/hent_ibsenstage_detaljer.py`.
    """
    return {k: tekst(v) for k, v in RE_FELT.findall(sidehtml)}


def smoke() -> str:
    # Kategori 2 er liten (under 200 hendelser) — nok til å bekrefte formen
    # uten å be en universitetstjener om hele basen.
    side = hent_html("/pages/browse/eventcategory/primary/2?per_page=3")

    m = RE_TELLING.search(side)
    if not m:
        raise ValueError("fant ikke «Category: … - Count N» — fasiten i overskriften "
                         "er borte, og da kan ingen henting kontrollere seg selv")
    kategori, fasit = m.group(1), int(m.group(2))

    overskrifter = [tekst(t) for t in re.findall(r"<th[^>]*>(.*?)</th>", side, re.S)]
    if overskrifter[:len(KOLONNER)] != KOLONNER:
        raise ValueError(f"tabellkolonnene er endret: {overskrifter[:10]} "
                         f"(ventet {KOLONNER})")

    rader = parse_rader(side)
    if not rader:
        raise ValueError("ingen rader parset — radmønsteret eller celletallet er endret")
    forste = rader[0]
    if not forste["hendelse_id"]:
        raise ValueError(f"ingen event-id i første rad: {forste['tittel']!r}")

    time.sleep(1.0)  # vi er gjester på en forskningstjener
    felt = parse_detaljer(hent_html(f"/pages/event/{forste['hendelse_id']}"))
    mangler = {"Event", "First Date", "Venue"} - set(felt)
    if mangler:
        raise ValueError(f"detaljsiden mangler felt: {sorted(mangler)}")

    return (f"{kategori}: {fasit} hendelser, {len(KOLONNER)} kolonner; "
            f"første: «{forste['tittel']}» ({forste['aar']}, {forste['land']}) — "
            f"detaljsiden gir {len(felt)} felt, bl.a. {felt.get('Performance language') or felt['Status']}")


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Ingen API: henter én browse-side og én detaljside som HTML …")
    print(f"✓ {smoke()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
