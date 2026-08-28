"""Henter hele IbsenStage-basen (ibsenstage.hf.uio.no) til rådata utenfor repoet.

Kjøring (krever nett mot ibsenstage.hf.uio.no):

    python pipeline/hent_ibsenstage.py            # alle kategorier
    python pipeline/hent_ibsenstage.py --kategori 1

Datakilde: UiOs IbsenStage, «browse by event category». Basen har ingen API og
ingen eksport, bare en paginert HTML-tabell. Tre ting gjør den likevel grei å hente:

1. `?per_page=N` er en fri parameter. Standardvisningen er 100 per side (245 sider
   for kategori 1); 1000 fungerer, 2500 gir HTTP 500. Vi bruker 1000, og henter
   dermed hele basen i ~30 forespørsler i stedet for 260.
2. Hver kategoriside oppgir sin egen fasit i overskriften — «Count 24489». Den
   leses ut og sammenlignes med antall parsede rader. Stemmer det ikke, stopper
   scriptet: en halv tabell er verre enn ingen tabell, fordi den ser komplett ut.
3. Tabellen har skjulte sorteringskolonner. Datoen finnes både som «04 April 2024»
   og som `20240404`, og sistnevnte er den vi tar vare på — den er entydig og
   sier samtidig hvor presis datoen er (`20240000` = bare år kjent).

Rådata skrives UTENFOR repoet (jf. SIKKERHET.md / .gitignore): sett IBSENSTAGE_DIR,
ellers brukes ../impromptu_raadata/ibsenstage/ ved siden av repoet. Rå HTML mellomlagres per
side, så en avbrutt kjøring fortsetter der den slapp og koster ingenting.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import kontrakt  # noqa: F401  -- setter utf-8 på stdout/stderr (Windows-konsollen er cp1252)

BASIS = "https://ibsenstage.hf.uio.no"
# Sidestørrelsene vi faller ned gjennom når en blokk ikke lar seg hente. Tjeneren
# regner offset som (side - 1) * per_page, så én blokk på 1000 er nøyaktig de ti
# blokkene på 100 som følger — se _blokk().
TRAPP = (1000, 100, 10, 1)
PAUSE = 1.0                # sekunder mellom forespørsler mot en universitetstjener
KATEGORIER = range(1, 16)  # 9 finnes ikke, 10-13/15 er tomme — begge deler håndteres

RAADATA_DIR = Path(
    os.environ.get("IBSENSTAGE_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ibsenstage"
)

# <title> begynner også med «Category:», så mønsteret må holde seg innenfor én
# tekstnode — ellers slukes hele dokumentet mellom tittelen og tellingen.
RE_TELLING = re.compile(r"Category:\s*([^<>]*?)\s*-\s*Count\s*(\d+)")
RE_RAD = re.compile(r'<tr style="line-height: 1;"[^>]*>(.*?)</tr>', re.S)
RE_CELLE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
RE_LENKE = re.compile(r'href="/pages/(\w+)/(\d+)"')


def _tekst(celle: str) -> str:
    """Cellens synlige tekst: strip tagger, avkod entiteter, normaliser luft."""
    ren = re.sub(r"<[^>]+>", "", celle)
    ren = html.unescape(ren).replace("\xa0", " ").replace("&nbsp", " ")
    return " ".join(ren.split())


def _id(celle: str, forventet: str) -> int | None:
    m = RE_LENKE.search(celle)
    return int(m.group(2)) if m and m.group(1) == forventet else None


# ------------------------------------------------------------ henting ----

class SideFeil(Exception):
    """Tjeneren nekter å rendre denne blokka. Del den opp i stedet for å gi opp."""


def _hent(url: str, forsok: int = 4) -> str:
    """GET med retry.

    HTTP 500 og nettverksfeil behandles ulikt med vilje. Nettverksfeil er
    forbigående og fortjener flere forsøk med økende pause. HTTP 500 fra denne
    tjeneren er derimot deterministisk — den kommer på nøyaktig samme rad hver
    gang, på under to sekunder — så etter ett kontrollforsøk sier vi fra at
    blokka må deles, i stedet for å bruke tid på å be om det samme igjen.
    """
    for n in range(1, forsok + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "impromptu.no datainnhenting (kontakt: impromptu.no)"},
            )
            with urllib.request.urlopen(req, timeout=180) as svar:
                return svar.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code >= 500:
                if n >= 2:
                    raise SideFeil(f"HTTP {e.code}")
                time.sleep(2)
                continue
            raise SystemExit(f"{url}: HTTP {e.code}")
        except (urllib.error.URLError, OSError) as e:
            if n == forsok:
                raise SystemExit(f"ga opp {url} etter {forsok} forsøk: {e}")
            ventetid = 3 * n
            print(f"  ! {e} - nytt forsøk om {ventetid}s ({n}/{forsok - 1})")
            time.sleep(ventetid)
    raise SideFeil("HTTP 500")


def _side(kategori: int, per_side: int, sidenr: int, cache: Path) -> str:
    """Én blokk rå HTML, mellomlagret på disk.

    Både treff og avvisning lagres. En avvist blokk skyldes en rad tjeneren ikke
    klarer å rendre, og det svaret er like stabilt som innholdet — lagrer vi det
    ikke, betaler hver ny kjøring de samme forgjeves forespørslene om igjen.
    """
    stamme = cache / f"kat{kategori:02d}_pp{per_side:04d}_s{sidenr:05d}"
    html_fil, feil_fil = stamme.with_suffix(".html"), stamme.with_suffix(".feil")
    if feil_fil.exists():
        raise SideFeil(feil_fil.read_text(encoding="utf-8"))
    if html_fil.exists() and html_fil.stat().st_size > 5000:
        return html_fil.read_text(encoding="utf-8")

    sti = f"/pages/browse/eventcategory/primary/{kategori}"
    if sidenr > 1:
        sti += f"/page/{sidenr}"
    cache.mkdir(parents=True, exist_ok=True)
    try:
        tekst = _hent(f"{BASIS}{sti}?per_page={per_side}")
    except SideFeil as e:
        feil_fil.write_text(str(e), encoding="utf-8")
        raise
    finally:
        time.sleep(PAUSE)
    html_fil.write_text(tekst, encoding="utf-8")
    return tekst


def _blokk(kategori: int, navn: str, trinn: int, sidenr: int,
           cache: Path, hull: list[int]) -> list[dict]:
    """Radene i én blokk, med nedtrapping rundt rader tjeneren ikke tåler.

    Én rad i kategori 1 (alfabetisk nr. 2323, mellom «Doll's House» og «Doll's
    House (Act 3), A») gir HTTP 500 uansett sidestørrelse — også i nettstedets
    egen visning på 100 per side. Én slik rad skal ikke koste 24 000 andre, så
    en avvist blokk deles i ti mindre og forsøkes på nytt. Når nedtrappingen er
    nede på én rad og den fortsatt avvises, noteres den som hull og telles med
    i sluttsummen, slik at fasitkontrollen fortsatt betyr noe.
    """
    per_side = TRAPP[trinn]
    try:
        return _parse_rader(_side(kategori, per_side, sidenr, cache), kategori, navn)
    except SideFeil:
        if per_side == 1:
            hull.append(sidenr)
            print(f"  ! rad {sidenr} avvises av tjeneren - hoppes over")
            return []
        faktor = per_side // TRAPP[trinn + 1]
        print(f"  ! blokk {sidenr} a {per_side} avvist - deler i {faktor}")
        rader: list[dict] = []
        for i in range(faktor):
            rader += _blokk(kategori, navn, trinn + 1,
                            (sidenr - 1) * faktor + i + 1, cache, hull)
        return rader


# ------------------------------------------------------------ parsing ----

def _parse_rader(sidehtml: str, kategori: int, kategorinavn: str) -> list[dict]:
    rader = []
    for rad in RE_RAD.findall(sidehtml):
        c = RE_CELLE.findall(rad)
        if len(c) < 10:
            continue
        # Kolonner: 0 sorteringstittel, 1 tittel, 2 verk, 3 sjangermerker,
        #           4 dato som YYYYMMDD, 5 dato som tekst, 6 sorteringsscene,
        #           7 scene, 8 land, 9 antall ressurser
        datokode = _tekst(c[4])
        ressurs = _tekst(c[9])
        rader.append({
            "hendelse_id": _id(c[1], "event"),
            "tittel": _tekst(c[1]),
            "verk": _tekst(c[2]),
            "verk_id": _id(c[2], "work"),
            "merker": [m.strip() for m in _tekst(c[3]).split(",") if m.strip()],
            "dato": datokode if datokode.isdigit() else None,
            "aar": int(datokode[:4]) if datokode[:4].isdigit() else None,
            "dato_tekst": _tekst(c[5]),
            "scene": _tekst(c[7]),
            "scene_id": _id(c[7], "venue"),
            "land": _tekst(c[8]),
            "ressurser": int(ressurs) if ressurs.isdigit() else 0,
            "kategori_id": kategori,
            "kategori": kategorinavn,
        })
    return rader


def hent_kategori(kategori: int, cache: Path) -> tuple[list[dict], int]:
    try:
        forste = _side(kategori, TRAPP[0], 1, cache)
    except SideFeil as e:
        raise SystemExit(f"kategori {kategori}: første side avvist ({e})")
    m = RE_TELLING.search(forste)
    if not m:
        print(f"kategori {kategori}: ingen tellelinje - hoppes over")
        return [], 0
    navn, fasit = m.group(1), int(m.group(2))
    if fasit == 0:
        print(f"kategori {kategori}: {navn} - tom")
        return [], 0

    sider = -(-fasit // TRAPP[0])
    print(f"kategori {kategori}: {navn} - {fasit} hendelser over {sider} blokk(er)")
    hull: list[int] = []
    rader = _parse_rader(forste, kategori, navn)
    for sidenr in range(2, sider + 1):
        rader += _blokk(kategori, navn, 0, sidenr, cache, hull)
        print(f"  blokk {sidenr}/{sider}: {len(rader)} rader")

    # Fasiten står i sidens egen overskrift. Avviker den, er henting eller parsing
    # feil, og en delvis tabell ser komplett ut i alt som kommer etterpå. Rader
    # tjeneren selv nekter å levere telles med her — de er kjente og talte hull,
    # ikke rader vi mistet uten å merke det.
    if len(rader) + len(hull) != fasit:
        raise SystemExit(
            f"kategori {kategori}: parset {len(rader)} rader + {len(hull)} hull, "
            f"siden oppgir {fasit}"
        )
    return rader, len(hull)


# --------------------------------------------------------------- skriv ----

FELT = ["hendelse_id", "tittel", "verk", "verk_id", "merker", "dato", "aar",
        "dato_tekst", "scene", "scene_id", "land", "ressurser",
        "kategori_id", "kategori"]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kategori", type=int, action="append",
                   help="hent bare denne kategorien (kan gjentas)")
    p.add_argument("--ut", type=Path, default=RAADATA_DIR)
    args = p.parse_args()

    utdir = args.ut
    cache = utdir / "html"
    utdir.mkdir(parents=True, exist_ok=True)
    print(f"rådata: {utdir}")

    alle: list[dict] = []
    hull = 0
    for kategori in (args.kategori or KATEGORIER):
        rader, kat_hull = hent_kategori(kategori, cache)
        alle += rader
        hull += kat_hull

    alle.sort(key=lambda r: (r["dato"] or "00000000", r["hendelse_id"] or 0))

    (utdir / "ibsenstage_hendelser.json").write_text(
        json.dumps({
            "hentet": date.today().isoformat(),
            "kilde": f"{BASIS}/pages/browse/eventcategory/primary/",
            "antall": len(alle),
            "utelatt": hull,  # rader tjeneren returnerer HTTP 500 på, se _blokk()
            "hendelser": alle,
        }, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    with (utdir / "ibsenstage_hendelser.csv").open("w", newline="", encoding="utf-8") as f:
        skriver = csv.DictWriter(f, fieldnames=FELT)
        skriver.writeheader()
        for r in alle:
            skriver.writerow({**r, "merker": "; ".join(r["merker"])})

    aar = [r["aar"] for r in alle if r["aar"]]
    print(f"\nOK {len(alle)} hendelser, {min(aar)}-{max(aar)}, "
          f"{len({r['land'] for r in alle})} land, {len({r['verk'] for r in alle})} verk")
    if hull:
        print(f"  {hull} rad(er) utelatt: tjeneren svarer HTTP 500 på dem")
    print(f"  {utdir / 'ibsenstage_hendelser.json'}")
    print(f"  {utdir / 'ibsenstage_hendelser.csv'}")


if __name__ == "__main__":
    main()
