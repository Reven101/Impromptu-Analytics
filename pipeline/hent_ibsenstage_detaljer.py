"""Henter detaljsidene for hver hendelse i IbsenStage og parser dem til JSONL.

Kjøring (krever at hent_ibsenstage.py har kjørt først):

    python pipeline/hent_ibsenstage.py
    python pipeline/hent_ibsenstage_detaljer.py

Tabellen i browse-visningen gir tittel, verk, dato, scene og land. Detaljsiden
(`/pages/event/<id>`) gir resten, og det er der folkene ligger: medvirkende med
funksjon (regissør, oversetter, skuespiller), produksjonsselskap, sluttdato,
premieredato, status (profesjonell/amatør/student), forestillingsspråk og
produksjonsnasjonalitet.

Tre valg som er verdt å kjenne til:

- **Rå HTML mellomlagres gzippet, sharded på id.** 25 000 sider er sju timer av
  en universitetstjeners tid. Den regningen skal betales én gang, ikke på nytt
  hver gang parseren endrer seg. Gzip tar sidene fra ~35 kB til ~6 kB, og
  `--reparse` bygger JSONL-en på nytt fra disk uten et eneste nettverkskall.
- **Fire tråder, ikke tjue.** Kilden er et forskningsarkiv ved UiO uten API og
  uten rate limit-header — altså ingen som har sagt hva som er greit. Fire
  samtidige med pause lander på ~4 forespørsler i sekundet og bruker ~1,5 time.
- **Sider som feiler noteres, de stopper ikke jobben.** Åtte rader i basen gir
  HTTP 500 i browse-visningen (se hent_ibsenstage.py); enkeltsider kan gjøre det
  samme. De havner i `detaljer_feilet.json` og telles i sluttrapporten.

Rådata skrives utenfor repoet, samme sted som browse-hentingen (IBSENSTAGE_DIR).
"""

from __future__ import annotations

import argparse
import gzip
import html as htmlmod
import http.client
import json
import os
import re
import threading
import time
import traceback
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import kontrakt  # noqa: F401  -- setter utf-8 på stdout/stderr (Windows-konsollen er cp1252)

BASIS = "https://ibsenstage.hf.uio.no"
TRAADER = 4
PAUSE = 1.0  # sekunder per tråd mellom forespørsler

RAADATA_DIR = Path(
    os.environ.get("IBSENSTAGE_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ibsenstage"
)

# Tittelraden har et ikon foran etiketten, med linjeskift rundt — derfor \s* på
# begge sider av det valgfrie <img>-leddet. Uten det faller «Event» ut, og siden
# alle andre felt matcher, blir den eneste følgen at tittelen stille blir null.
RE_FELT = re.compile(
    r'<th class="record-label[^"]*">\s*(?:<img[^>]*>)?\s*([^<]+?)\s*</th>\s*'
    r'<td class="record-value[^"]*"[^>]*>(.*?)</td>',
    re.S,
)
RE_BIDRAG_TABELL = re.compile(r'<table[^>]*id="stupidTable"[^>]*>(.*?)</table>', re.S)
RE_RAD = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
RE_CELLE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
RE_LI = re.compile(r"<li[^>]*>(.*?)</li>", re.S)
RE_LENKE = re.compile(r'href=["\']/pages/(\w+)/(\d+)["\']')

# Feltene vi tar vare på, med navnet de får i JSON. Alt annet på siden ignoreres
# bevisst — resten er visningslogikk (Print, Add information, Event Identifier).
ENKLE_FELT = {
    "Description": "beskrivelse",
    "First Date": "forste_dato",
    "Last Date": "siste_dato",
    "Opening Night": "premiere",
    "Status": "status",
    "Primary Genre": "sjanger_primar",
    "Secondary Genre": "sjanger_sekundar",
    "Production Nationality": "produksjonsnasjonalitet",
    "Performance language": "sprak",
    "Date Estimated": "dato_anslatt",
    "Further Information": "tilleggsinfo",
}


def _tekst(bit: str) -> str:
    ren = re.sub(r"<[^>]+>", " ", bit)
    ren = htmlmod.unescape(ren).replace("\xa0", " ")
    return " ".join(ren.split())


def _avsnitt(bit: str) -> str:
    """Som _tekst, men beholder avsnittsskift — beskrivelsene er flere avsnitt."""
    ren = re.sub(r"<[^>]+>", " ", bit)
    ren = htmlmod.unescape(ren).replace("\xa0", " ")
    return "\n\n".join(" ".join(a.split()) for a in ren.split("\n\n") if a.strip())


# ------------------------------------------------------------ parsing ----

def _lenkeliste(bit: str, entitet: str) -> list[dict]:
    """<li>-lista som «navn (id), rolle» — brukes for verk og organisasjoner."""
    ut = []
    for li in RE_LI.findall(bit) or [bit]:
        if not _tekst(li):
            continue
        m = RE_LENKE.search(li)
        if m and m.group(1) != entitet:
            continue
        navn = _tekst(re.search(r"<a[^>]*>(.*?)</a>", li, re.S).group(1)) if m else _tekst(li)
        etter = _tekst(li[li.find("</a>") + 4:]).lstrip(", ") if m else ""
        ut.append({"navn": navn, "id": int(m.group(2)) if m else None, "rolle": etter or None})
    return ut


def _bidragsytere(sidehtml: str) -> list[dict]:
    m = RE_BIDRAG_TABELL.search(sidehtml)
    if not m:
        return []
    ut = []
    for rad in RE_RAD.findall(m.group(1)):
        c = RE_CELLE.findall(rad)
        if len(c) < 7:
            continue
        # Kolonner: 0 person-id, 1 sorteringsnavn, 2 navn, 3 funksjons-id,
        #           4 funksjon, 5 rollefigur, 6 merknad
        ut.append({
            "person_id": int(_tekst(c[0])) if _tekst(c[0]).isdigit() else None,
            "navn": _tekst(c[2]),
            "sortnavn": _tekst(c[1]),
            "funksjon_id": int(_tekst(c[3])) if _tekst(c[3]).isdigit() else None,
            "funksjon": _tekst(c[4]),
            "rollefigur": _tekst(c[5]) or None,
            "merknad": _tekst(c[6]) or None,
        })
    return ut


def parse(sidehtml: str, hendelse_id: int) -> dict:
    felt = {etikett: verdi for etikett, verdi in RE_FELT.findall(sidehtml)}
    post: dict = {"hendelse_id": hendelse_id}

    tittel = felt.get("Event")
    post["tittel"] = _tekst(tittel) if tittel else None

    for etikett, navn in ENKLE_FELT.items():
        if etikett in felt:
            verdi = (_avsnitt if navn == "beskrivelse" else _tekst)(felt[etikett])
            if verdi:
                post[navn] = verdi

    if "Venue" in felt:
        post["scene"] = _tekst(felt["Venue"])
        m = RE_LENKE.search(felt["Venue"])
        post["scene_id"] = int(m.group(2)) if m and m.group(1) == "venue" else None

    post["verk"] = _lenkeliste(felt.get("Works", ""), "work")
    post["organisasjoner"] = _lenkeliste(felt.get("Organisations", ""), "organisation")
    post["kilder"] = [_tekst(li) for li in RE_LI.findall(felt.get("Source", "")) if _tekst(li)]
    post["bidragsytere"] = _bidragsytere(sidehtml)
    return post


# ------------------------------------------------------------ henting ----

_skriveløs = threading.Lock()


def _cachefil(cache: Path, hendelse_id: int) -> Path:
    return cache / f"{hendelse_id // 1000:03d}" / f"{hendelse_id}.html.gz"


def _hent_side(hendelse_id: int, cache: Path) -> str | None:
    """Rå HTML, fra disk om den finnes. None betyr at tjeneren avviste sida."""
    fil = _cachefil(cache, hendelse_id)
    if fil.exists():
        with gzip.open(fil, "rt", encoding="utf-8") as f:
            return f.read()

    url = f"{BASIS}/pages/event/{hendelse_id}"
    for forsok in range(1, 4):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "impromptu.no datainnhenting (kontakt: impromptu.no)"},
            )
            with urllib.request.urlopen(req, timeout=120) as svar:
                tekst = svar.read().decode("utf-8", "replace")
            # Svaret sendes chunked. Blir det brutt underveis, kommer det ikke
            # alltid som unntak — det kan også komme som en kort, gyldig streng.
            # Da mangler avslutningen, og en halv side som mellomlagres ser
            # komplett ut for alltid etterpå.
            if "</html>" not in tekst[-2000:]:
                time.sleep(2 * forsok)
                continue
            fil.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(fil, "wt", encoding="utf-8") as f:
                f.write(tekst)
            time.sleep(PAUSE)
            return tekst
        except urllib.error.HTTPError as e:
            # 500 er deterministisk på denne tjeneren, 404 like så: ikke prøv igjen.
            if e.code in (404, 500):
                time.sleep(PAUSE)
                return None
            time.sleep(2 * forsok)
        except (urllib.error.URLError, http.client.HTTPException, OSError):
            # IncompleteRead er en HTTPException, ikke en OSError. Uten den greina
            # river et enkelt avbrutt svar med seg hele puljen.
            time.sleep(3 * forsok)
    return None


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ut", type=Path, default=RAADATA_DIR)
    p.add_argument("--grense", type=int, help="hent bare de N første (for test)")
    p.add_argument("--reparse", action="store_true",
                   help="bygg JSONL på nytt fra mellomlagret HTML, uten nettverk")
    args = p.parse_args()

    utdir = args.ut
    cache = utdir / "html_hendelser"
    kilde = utdir / "ibsenstage_hendelser.json"
    if not kilde.exists():
        raise SystemExit(f"mangler {kilde} - kjør hent_ibsenstage.py først")

    ider = sorted({r["hendelse_id"] for r in json.loads(kilde.read_text(encoding="utf-8"))
                   ["hendelser"] if r["hendelse_id"]})
    if args.grense:
        ider = ider[:args.grense]

    jsonl = utdir / "ibsenstage_detaljer.jsonl"
    ferdig: set[int] = set()
    if jsonl.exists() and not args.reparse:
        with jsonl.open(encoding="utf-8") as f:
            for linje in f:
                try:
                    ferdig.add(json.loads(linje)["hendelse_id"])
                except (json.JSONDecodeError, KeyError):
                    pass
    if args.reparse:
        jsonl.unlink(missing_ok=True)

    igjen = [i for i in ider if i not in ferdig]
    print(f"{len(ider)} hendelser, {len(ferdig)} allerede hentet, {len(igjen)} igjen")
    if args.reparse:
        print("reparse: leser bare mellomlagret HTML")

    feilet: list[int] = []
    teller = {"n": 0}
    start = time.time()
    utfil = jsonl.open("a", encoding="utf-8")

    def arbeid(hendelse_id: int) -> None:
        # En uventet feil i én tråd skal koste én side, ikke resten av kjøringen:
        # pool.map lar unntaket boble opp og avbryter alt som ikke er ferdig.
        try:
            sidehtml = (
                _hent_side(hendelse_id, cache) if not args.reparse
                else (gzip.open(_cachefil(cache, hendelse_id), "rt", encoding="utf-8").read()
                      if _cachefil(cache, hendelse_id).exists() else None)
            )
        except Exception:  # noqa: BLE001 - loggføres og telles, se detaljer_feilet.json
            print(f"  ! {hendelse_id}: {traceback.format_exc(limit=1).strip()}")
            sidehtml = None
        with _skriveløs:
            teller["n"] += 1
            if sidehtml is None:
                feilet.append(hendelse_id)
            else:
                utfil.write(json.dumps(parse(sidehtml, hendelse_id), ensure_ascii=False) + "\n")
            n = teller["n"]
            if n % 250 == 0 or n == len(igjen):
                gatt = time.time() - start
                fart = n / gatt if gatt else 0
                igjen_sek = (len(igjen) - n) / fart if fart else 0
                print(f"  {n}/{len(igjen)}  {fart:.1f}/s  "
                      f"~{igjen_sek / 60:.0f} min igjen  {len(feilet)} feilet",
                      flush=True)  # stdout er blokkbufret når det ikke er en terminal:
                utfil.flush()      # uten flush kommer hele loggen først ved avslutning

    with ThreadPoolExecutor(max_workers=1 if args.reparse else TRAADER) as pool:
        list(pool.map(arbeid, igjen))
    utfil.close()

    if feilet:
        (utdir / "detaljer_feilet.json").write_text(
            json.dumps({"hentet": date.today().isoformat(), "hendelse_id": sorted(feilet)},
                       indent=1),
            encoding="utf-8")

    print(f"\nOK {len(igjen) - len(feilet)} sider parset, {len(feilet)} avvist")
    print(f"  {jsonl}")


if __name__ == "__main__":
    main()
