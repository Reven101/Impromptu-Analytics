"""Nordic Statistics — sammenlignbar statistikk for alle åtte nordiske områder.

267 tabeller der Danmark, Færøyene, Grønland, Finland, Åland, Island, Norge og
Sverige er harmonisert til samme definisjoner, samlet av Nordregio på oppdrag
fra Nordisk ministerråd siden 1960-tallet. Poenget er nettopp sammenligningen:
å hente de samme tallene fra åtte nasjonale statistikkbanker og gjøre dem
kommensurable er ukers arbeid, og her er det gjort.

PxWeb-API v1 — samme motor som SSB kjørte før v2, så spørringene ser kjente ut.

Kjøring:  python3 api-atlas/eksempler/hent_nordisk_statistikk.py
Nøkkel:   ingen
Lisens:   egne vilkår — IKKE NLOD/CC. Se punkt 2 under; attribusjonsregelen er
          snudd på hodet i forhold til resten av atlaset.
Dok:      https://www.nordicstatistics.org/about/
API-rot:  https://pxweb.nordicstatistics.org/api/v1/en/Nordic%20Statistics/

Endepunkter:
  GET  <rot>/                      emnene (type "l" = mappe, "t" = tabell)
  GET  <rot>/<emne>/<undermappe>/  tabellene, med "updated"-tidsstempel
  GET  <rot>/<sti>/CULT20.px       metadata: variabler, koder, kodetekster
  POST <rot>/<sti>/CULT20.px       selve uttrekket, JSON-spørring i kroppen

  Spørringen er standard PxWeb: {"query": [{"code": ..., "selection":
  {"filter": "item", "values": [...]}}], "response": {"format": "json-stat2"}}
  Utelatt variabel = alle verdier. Content-Type må settes til application/json.

Rammer (fra <rot>?config): 100 kall per 10 sekunder, 1 000 000 celler per
uttrekk. Romslig, men hierarkiet har 267 tabeller — throttle når du traverserer.

FEM TING SOM KOSTER TID:

1. Landlista varierer fra tabell til tabell, og den inneholder ikke bare
   land. CULT01 har alle åtte områdene; CULT20 mangler Åland; POPU01 har
   Åland, men legger til EA (eurosonen) og EU som egne rader i *samme*
   dimensjon som landene. To følger: summerer du «alle reporting
   countries» får du Norden pluss hele EU i samme tall, og ber du om en
   kode tabellen ikke har, svarer API-et 400 — den blir ikke stille
   utelatt. Hent metadata først og snitt mot LAND, slik
   `nordiske_koder()` gjør.

   Rekkefølgen i svaret er heller ikke din: ber du om ["NO", "IS"], kommer
   Island først. Les alltid category.index for å vite hvilken verdi som er
   hvilken — aldri posisjonen i spørringen.

2. Attribusjonen er invertert. Vilkårene sier: gjengir du tallene som de er,
   skal du oppgi «Source: Nordic Statistics database» — men *«If you are
   processing statistics from Nordic Statistics, you may not state Nordic
   Statistics database as a source.»* Regner du om, indekserer eller slår
   sammen, skal du altså IKKE kreditere basen. Da krediterer du produsenten
   i stedet, og den står i json-stat2-svarets "source"-felt: Eurostat, OECD,
   Nomesco-Nososco eller det enkelte statistikkbyrået — ofte med ulike
   kilder for ulike land i samme tabell. Atlasets vanlige regel («oppgi
   alltid kilde») er feil her. Les "source" og videreformidle den.
   Feltet inneholder rå HTML-lenker og «#» som skille mellom produsenter,
   så det må vaskes før det kan vises fram.

3. Kodene i POPU01 lyver, kodetekstene er sanne. Variabelen `unit` har
   verdiene «Percent of total» og «Percent of age group» byttet om mot
   sine kodetekster. Målt: koden «Percent of total» gir 100 % for
   ettåringer og 51,08 % for guttene blant dem — det er andel av
   *aldersgruppen*. Koden «Percent of age group» gir 0,94 % og 0,48 %,
   som er andel av *totalen*. json-stat2 gjengir samme ombytting i
   category.label, og der er etiketten den som stemmer med tallene.
   Les alltid label, aldri koden, som beskrivelse av hva du hentet.
   `sjekk_kodetekster()` fanger klassen av feil; per september 2026 er
   POPU01 den eneste av de 267 tabellene den slår ut på (den ligger to
   steder i hierarkiet, under Demography og under Gender Equality).

4. Bare `en` virker. /da/, /no/, /sv/, /fi/ og /is/ gir HTTP 400 på API-et,
   selv om nettsidene finnes på flere språk. Alle kodetekster kommer på
   engelsk, og norske landnavn må du sette på selv — se LAND under.

5. "updated" i uttrekket er ikke tabellens dato. json-stat2-svaret for
   CULT20 melder 2018, mens tabellisten melder desember 2025 for samme
   tabell. Listenivået er det som stemmer — hent ferskhet derfra.

Gull å grave i:
  - Norge mot Norden i kulturbruk: CULT01/04/15/16 (bibliotek, kino, teater,
    museum) er den sammenligningen SSB alene ikke kan gi deg
  - CULT20: kulturutgifter som andel av BNP, åtte land, 1998→. Målt for 2022:
    Island 1,1 %, Danmark 0,6 %, Norge 0,5 %
  - Færøyene, Grønland og Åland er med som egne enheter — de tre finnes
    nesten aldri i internasjonale databaser, og er ofte den mest slående
    kontrasten i en nordisk figur
  - «Nordic Indicators for our Vision 2030» (44 tabeller) er et ferdig
    politisk målesett: hva lovet Norden seg selv, og hvor står det nå?
  - Kobling: nordisk nivå herfra + norsk kommunenivå fra `ssb-api`
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

# Konsollen på Windows er cp1252 og kveler ✓ og de nordiske navnene med
# UnicodeEncodeError etter at kallene er gjort. Atlaset er bevisst
# frittstående, så vi arver ikke pipeline/kontrakt.py — vi gjentar de to
# linjene i stedet, som test_atlas.py. No-op på macOS/Linux.
for _strom in (sys.stdout, sys.stderr):
    if hasattr(_strom, "reconfigure"):
        _strom.reconfigure(encoding="utf-8")

KILDE = "Nordic Statistics (Nordregio / Nordisk ministerråd)"
DOK = "https://www.nordicstatistics.org/about/"
API = "https://pxweb.nordicstatistics.org/api/v1/en/Nordic Statistics"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"

# Landkodene slik de er i basen, med norske navn (API-et er engelsk).
# AX = Åland, FO = Færøyene, GL = Grønland — de tre som pleier å mangle
# i internasjonale datasett, og som er halve poenget med denne kilden.
LAND = {
    "DK": "Danmark", "FO": "Færøyene", "GL": "Grønland", "FI": "Finland",
    "AX": "Åland", "IS": "Island", "NO": "Norge", "SE": "Sverige",
}


def _url(sti: str) -> str:
    """Bygg URL. Mappenivåer må ha etterslept skråstrek, tabeller ikke."""
    full = f"{API}/{sti}" if sti else API
    if not full.endswith(".px"):
        full += "/"
    return urllib.parse.quote(full, safe=":/")


def hent_json(url: str, kropp: dict | None = None, timeout: int = 60):
    data = json.dumps(kropp).encode("utf-8") if kropp is not None else None
    hoder = {"User-Agent": BRUKERAGENT, "Accept": "application/json"}
    if data is not None:
        # PxWeb svarer 415 på POST uten denne.
        hoder["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hoder)
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def list_niva(sti: str = "") -> list[dict]:
    """Innholdet i ett nivå. type "l" er mappe, "t" er tabell."""
    return hent_json(_url(sti))


def hent_metadata(tabell: str) -> dict:
    """Variabler og koder for én tabell, f.eks. "Culture/CULT20.px"."""
    return hent_json(_url(tabell))


def sjekk_kodetekster(meta: dict) -> list[str]:
    """Finn variabler der koder og kodetekster er omstokket mot hverandre.

    Se punkt 3 i toppdokumentasjonen. Slår bare ut når kodene selv er
    lesbar tekst, altså når de to listene inneholder de samme strengene i
    ulik rekkefølge — da er paringen per posisjon beviselig gal.
    """
    mistenkte = []
    for v in meta["variables"]:
        koder, tekster = v["values"], v.get("valueTexts", [])
        if len(koder) != len(tekster):
            mistenkte.append(f"{v['code']}: ulikt antall koder og kodetekster")
        elif set(koder) == set(tekster) and koder != tekster:
            mistenkte.append(f"{v['code']}: koder og kodetekster er omstokket")
    return mistenkte


def nordiske_koder(meta: dict, variabel: str = "reporting country") -> list[str]:
    """De nordiske landkodene tabellen faktisk har, i tabellens rekkefølge.

    Se punkt 1: utvalget varierer per tabell, og dimensjonen inneholder
    også EA og EU. Snittet mot LAND gjør begge deler ufarlig — vi ber
    aldri om en kode som gir 400, og får aldri EU med på lasset.
    """
    v = next((x for x in meta["variables"] if x["code"] == variabel), None)
    if v is None:
        raise ValueError(f"tabellen har ingen variabel «{variabel}»")
    return [k for k in v["values"] if k in LAND]


def hent_tabell(tabell: str, utvalg: dict[str, list[str]]) -> dict:
    """POST et uttrekk. Utelatt variabel betyr alle verdier."""
    sporring = {
        "query": [
            {"code": kode, "selection": {"filter": "item", "values": verdier}}
            for kode, verdier in utvalg.items()
        ],
        "response": {"format": "json-stat2"},
    }
    return hent_json(_url(tabell), kropp=sporring)


def tabell_til_rader(data: dict) -> list[dict]:
    """Brett json-stat2 ut til rader med kodetekster, ikke koder.

    Verdilista er radvis over "size": siste akse varierer raskest. Vi
    bruker category.label og ikke koden — se punkt 3 øverst.
    """
    akser = data["id"]
    etiketter = [
        [
            data["dimension"][a]["category"]["label"][kode]
            for kode in data["dimension"][a]["category"]["index"]
        ]
        for a in akser
    ]

    rader = []
    for i, verdi in enumerate(data["value"]):
        rest, rad = i, {}
        for a in reversed(range(len(akser))):
            rest, j = divmod(rest, len(etiketter[a]))
            rad[akser[a]] = etiketter[a][j]
        rader.append({**rad, "verdi": verdi})
    return rader


def kulturutgifter(aar: str = "2022") -> list[tuple[str, float | None]]:
    """Offentlige kulturutgifter som andel av BNP, per nordisk land."""
    # Metadata først: CULT20 mangler Åland og har EA/EU i landdimensjonen.
    koder = nordiske_koder(hent_metadata("Culture/CULT20.px"))
    data = hent_tabell(
        "Culture/CULT20.px",
        {
            "reporting country": koder,
            "sector": ["S13"],           # offentlig forvaltning samlet
            "expenditure": ["G0802"],    # kulturformål (COFOG 08.2)
            "unit": ["PCGDP"],
            "time": [aar],
        },
    )
    # Med alt annet enn land låst til én verdi er verdilista én per land,
    # i samme rekkefølge som category.index.
    verdier = data["value"]
    indeks = data["dimension"]["reporting country"]["category"]["index"]
    ut = [
        (LAND.get(kode, kode), verdier[i] if i < len(verdier) else None)
        for kode, i in indeks.items()
    ]
    return sorted(ut, key=lambda p: (p[1] is None, -(p[1] or 0)))


def smoke() -> str:
    emner = list_niva()
    if len(emner) < 10:
        raise ValueError(f"bare {len(emner)} emner — har hierarkiet endret seg?")

    norge = dict(kulturutgifter("2022")).get("Norge")
    if norge is None:
        raise ValueError("ingen verdi for Norge i CULT20 — endret landkodene seg?")
    # Nordiske kulturutgifter ligger i området 0,3–2 % av BNP. Utenfor det
    # har vi hentet feil enhet, ikke oppdaget en kulturpolitisk revolusjon.
    if not 0.1 < norge < 3.0:
        raise ValueError(f"urealistisk BNP-andel for Norge: {norge} — feil unit?")

    return f"{len(emner)} emner; kulturutgifter Norge 2022: {norge} % av BNP"


def main() -> int:
    print(f"{KILDE} — {DOK}")

    emner = list_niva()
    print(f"\n{len(emner)} emner i basen:")
    for e in emner[:6]:
        print(f"  {e['id']}")
    print(f"  … og {len(emner) - 6} til")

    print("\nKulturtabeller:")
    for t in list_niva("Culture"):
        oppdatert = (t.get("updated") or "?")[:10]
        print(f"  {t['id']:12s} oppdatert {oppdatert}  {t['text'][:56]}")

    print("\nOffentlige kulturutgifter, andel av BNP (2022):")
    for land, verdi in kulturutgifter("2022"):
        print(f"  {land:12s} {verdi if verdi is not None else '–'}")

    # Attribusjonen ligger i dataene, ikke i atlaset — se punkt 2 øverst.
    data = hent_tabell("Culture/CULT20.px", {"time": ["2022"], "unit": ["PCGDP"]})
    print(f"\nProdusent oppgitt av tabellen:\n  {data['source'][:150]} …")

    meta = hent_metadata("Demography/Population size/POPU01.px")
    print("\nKodesjekk POPU01 (den kjente fella):")
    for linje in sjekk_kodetekster(meta) or ["ingen avvik"]:
        print(f"  {linje}")

    print(f"\n✓ {smoke()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
