"""Henter teaterregissører med registrert kjønn fra Wikidata, som fasit for kjønnsgjetting.

Kjøring:

    python pipeline/hent_wikidata_regissorer.py

Dette er ikke en datakilde for historien — det er en **målestokk**. IbsenStage har
ikke kjønn på medvirkende, og skal vi utlede det fra fornavn, må vi kunne si hvor
ofte utledningen treffer, og om den treffer like godt i Ungarn som i Norge og i
1890 som i 2010. Wikidatas `P21` er registrert av mennesker, ikke gjettet av en
modell, og egner seg derfor som fasit.

Framgangsmåten er å hente hele referansepopulasjonen én gang og matche lokalt,
ikke å slå opp navn for navn. To grunner:

- Ett oppslag per navn er 6 800 forespørsler mot en tjeneste med delt kapasitet.
- Oppslag på navn treffer flere personer med samme navn, og da må man velge. Med
  hele settet lokalt kan vi se kollisjonene og forkaste dem framfor å gjette.

Hentingen går i to steg mot to ulike API-er, fordi ett steg ikke fungerte:

1. **WDQS (SPARQL)** gir ID, kjønn og fødselsår. Uten navn tar spørringen tre
   sekunder for 5000 rader. MED navn og aliaser tok den så lang tid at tjeneren
   svarte 504 Gateway Timeout — labels ligger i alle språk og eksploderer i antall
   rader. WDQS er dessuten periodevis nede for vedlikehold og strammer da til
   én forespørsel i minuttet; koden retter seg etter den takten.
2. **MediaWiki-API-et** gir navn og aliaser, 50 ID-er per kall på et halvsekund.

Fasiten er skjev, og det skal den få lov til å være så lenge skjevheten måles:
Wikidata kjenner Max Reinhardt, men neppe en ungarsk regissør fra 1930-tallet.
Derfor rapporterer mal_kjonnsgjetting.py treffraten per land og per tiår, aldri
bare som ett tall.
"""

from __future__ import annotations

import json
import os
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import kontrakt  # noqa: F401  -- setter utf-8 på stdout/stderr

SPARQL = "https://query.wikidata.org/sparql"
API = "https://www.wikidata.org/w/api.php"
BRUKERAGENT = "impromptu.no research (kontakt: impromptu.no)"
YRKE = "wd:Q3387717"  # teaterregissør
SIDE = 5000
API_BUNT = 50
SPRAK = ("en|de|no|nb|nn|sv|da|fr|it|es|hu|pl|cs|nl|fi|pt|ro|el|tr|hr|sl|sk|lv|et|lt")

KJONN_QID = {"Q6581097": "mann", "Q6581072": "kvinne"}

RAADATA_DIR = Path(
    os.environ.get("IBSENSTAGE_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ibsenstage"
)


def _hent(url: str, forsok: int = 8, tidsavbrudd: int = 90) -> dict:
    """GET som retter seg etter takten tjenesten selv oppgir.

    WDQS svarer HTTP 429 med teksten «Aggressively rate-limiting to 1 req / min»
    når den er under press. Da er riktig svar å vente et minutt, ikke å prøve
    igjen om fem sekunder: raskere forsøk gjør bare presset verre, og grensen
    gjelder uansett.

    Tidsavbruddet er bevisst kort. En spørring som virker tar tre sekunder; en
    som henger i fem minutter kommer ikke til å svare, og med åtte forsøk blir
    det timer der scriptet står helt stille uten å si fra hva det venter på.
    """
    for n in range(1, forsok + 1):
        print(f"    -> forsøk {n}/{forsok}", flush=True)
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": BRUKERAGENT,
                "Accept": "application/sparql-results+json",
            })
            with urllib.request.urlopen(req, timeout=tidsavbrudd) as svar:
                return json.loads(svar.read())
        except urllib.error.HTTPError as e:
            if n == forsok:
                raise SystemExit(f"Wikidata svarte ikke etter {forsok} forsøk: {e}")
            # De to tjenestene ber om helt ulik takt, og å bruke WDQS-regelen på
            # begge er sløsing: MediaWiki-API-et vil ha noen sekunder, mens WDQS
            # under vedlikehold uttrykkelig sier én forespørsel i minuttet.
            if e.code == 429:
                ventetid = 65 if url.startswith(SPARQL) else min(2 ** n, 30)
            else:
                ventetid = 10 * n
            print(f"  ! HTTP {e.code} - venter {ventetid}s", flush=True)
            time.sleep(ventetid)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            if n == forsok:
                raise SystemExit(f"Wikidata svarte ikke etter {forsok} forsøk: {e}")
            print(f"  ! {e} - nytt forsøk om {10 * n}s", flush=True)
            time.sleep(10 * n)
    raise SystemExit("uoppnåelig")


def _sparql(sporring: str) -> list[dict]:
    url = SPARQL + "?" + urllib.parse.urlencode({"query": sporring, "format": "json"})
    return _hent(url)["results"]["bindings"]


def normaliser(navn: str) -> str:
    """Nøkkel for navnematching: uten aksenter, uten skilletegn, små bokstaver.

    «Ødegård» og «Odegard» skal treffe hverandre. Vi mister noen få reelle
    forskjeller på det, men det motsatte — å la Wikidatas skrivemåte avgjøre —
    ville systematisk favorisert engelskspråklige oppføringer.
    """
    ren = unicodedata.normalize("NFKD", navn)
    ren = "".join(c for c in ren if not unicodedata.combining(c))
    ren = "".join(c if c.isalnum() or c.isspace() else " " for c in ren)
    return " ".join(ren.lower().split())


def main() -> None:
    utdir = RAADATA_DIR
    utdir.mkdir(parents=True, exist_ok=True)

    # Steg 1: ID, kjønn, fødselsår. Vi teller ikke opp først — en egen COUNT-spørring
    # er ett WDQS-kall til på en tjeneste som er ustabil, og gir bare et framdriftstall.
    # Vi blar til siden kommer tom tilbake.
    personer: dict[str, dict] = {}
    for offset in range(0, 200_000, SIDE):
        rader = _sparql(
            f"SELECT ?p ?k ?fodt WHERE {{ ?p wdt:P106 {YRKE} ; wdt:P21 ?k . "
            f"OPTIONAL {{ ?p wdt:P569 ?fodt }} }} LIMIT {SIDE} OFFSET {offset}"
        )
        if not rader:
            break
        antall = offset + len(rader)
        for r in rader:
            qid = r["p"]["value"].rsplit("/", 1)[-1]
            personer.setdefault(qid, {
                "qid": qid,
                "kjonn": KJONN_QID.get(r["k"]["value"].rsplit("/", 1)[-1], "annet"),
                "fodt": (r.get("fodt", {}).get("value") or "")[:4] or None,
                "navn": [],
            })
        print(f"  kjønn: {len(personer)} personer (t.o.m. rad {antall})", flush=True)
        time.sleep(2)

    # Steg 2: navn og aliaser.
    qider = sorted(personer)
    for i in range(0, len(qider), API_BUNT):
        bunt = qider[i:i + API_BUNT]
        url = API + "?" + urllib.parse.urlencode({
            "action": "wbgetentities", "ids": "|".join(bunt),
            "props": "labels|aliases", "format": "json", "languages": SPRAK,
        })
        for qid, e in (_hent(url).get("entities") or {}).items():
            if qid not in personer:
                continue
            navn = {v["value"] for v in (e.get("labels") or {}).values()}
            navn |= {a["value"] for al in (e.get("aliases") or {}).values() for a in al}
            # Aliaslistene inneholder også kallenavn, etternavn alene og av og til
            # boktitler. Vi krever minst to ledd: ett enkelt ord som «Adorno» ville
            # ellers matchet alt som tilfeldigvis het det samme.
            personer[qid]["navn"] = sorted(n for n in navn if len(n.split()) >= 2)
        if (i // API_BUNT) % 20 == 0:
            print(f"  navn: {min(i + API_BUNT, len(qider))}/{len(qider)}", flush=True)
        time.sleep(0.5)  # 0,2 s ga HTTP 429 på hvert sjette kall — to i sekundet holder

    ut = [p for p in personer.values() if p["navn"]]
    fil = utdir / "wikidata_regissorer.json"
    fil.write_text(json.dumps(
        {"hentet": date.today().isoformat(), "yrke": YRKE, "antall": len(ut), "personer": ut},
        ensure_ascii=False, indent=1), encoding="utf-8")

    fordeling: dict[str, int] = {}
    for p in ut:
        fordeling[p["kjonn"]] = fordeling.get(p["kjonn"], 0) + 1
    print(f"\nOK {len(ut)} personer med brukbart navn "
          f"({len(personer) - len(ut)} uten), "
          f"{sum(len(p['navn']) for p in ut)} navneformer")
    print(f"  kjønnsfordeling: {fordeling}")
    print(f"  {fil}")


if __name__ == "__main__":
    main()
