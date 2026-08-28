"""Kobler Ibsens 30 verk til utgivelsesår og urpremiere fra Wikidata.

Kjøring:

    python pipeline/berik_verk.py

IbsenStage sier hvilket verk en oppsetning bygger på, men ikke når verket ble
skrevet. Uten det kan materialet ikke svare på sitt mest nærliggende spørsmål:
**hvor lang tid tok hvert stykke til hvert land?** «Et dukkehjem» (1879) og «Når
vi døde vågner» (1899) har tjue års forsprang på hverandre, og uten årstallet
ligger de i samme kolonne som om de var samtidige.

Verkssidene i IbsenStage har det ikke — de gir bare aggregater vi kan regne ut
selv. Wikidata har det, men en spørring på «verk av Henrik Ibsen» gir 192 treff:
oversettelser, enkeltutgaver, sceneadapsjoner og dikt om hverandre, mange uten
lesbar etikett. Derfor er koblingen HÅNDSKREVET — ett Q-nummer per verk, valgt ut
fra 192 kandidater — mens årstallene hentes fra Wikidata. Da er hvert tall
sporbart til en kilde i stedet for å hvile på hukommelse, og lista kan
etterprøves rad for rad.

To verk har ingen utgivelsesdato i Wikidata, og får `null` framfor et gjettet
årstall: «Mountain Bird» (Fjeldfuglen) er en ufullført libretto, og «Svanhild» er
et utkast som ble til «Kjærlighedens komedie».

Merk at `utgitt` er utgivelsesåret, ikke skriveåret. For «Lady Inger» skiller de
seg med tre år: skrevet 1854, urframført 1855, utgitt 1857. Vi bruker utgivelse
fordi det er den datoen Wikidata fører konsistent for alle verkene.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import kontrakt  # noqa: F401

SPARQL = "https://query.wikidata.org/sparql"
BRUKERAGENT = "impromptu.no research (kontakt: impromptu.no)"

RAADATA_DIR = Path(
    os.environ.get("IBSENSTAGE_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ibsenstage"
)

# Verkstittelen slik IbsenStage skriver den -> kanonisk Wikidata-Q-nummer.
# Håndplukket fra de 192 treffene på «verk av Henrik Ibsen»; utgavene og
# oversettelsene er utelatt med vilje. Endres denne, skal årstallene hentes på
# nytt — de er ikke skrevet inn her nettopp for at kilden skal være ett sted.
VERK_QID = {
    "The Burial Mound": "Q1774352",
    "Catiline": "Q1774375",
    "Norma": "Q3285327",
    "St. John's Night": "Q3285337",
    "The Feast at Solhaug": "Q1774368",
    "Lady Inger": "Q2008287",
    "Olaf Liljekrans": "Q3285322",
    "The Vikings at Helgeland": "Q3285405",
    "Mountain Bird": "Q2595792",       # ufullført libretto, ingen utgivelsesdato
    "Svanhild": "Q17195108",           # utkast, ingen utgivelsesdato
    "Terje Vigen": "Q1777844",
    "Love's Comedy": "Q3286220",
    "The Pretenders": "Q1774386",
    "Brand": "Q2660511",
    "Peer Gynt": "Q208094",
    "The League Of Youth": "Q1774382",
    "Poetry": "Q3701852",              # diktsamlingen «Digte»
    "Emperor and Galilean": "Q268276",
    "Pillars Of Society": "Q1774700",
    "A Doll's House": "Q669694",
    "Ghosts": "Q1434818",
    "An Enemy Of The People": "Q1305319",
    "The Wild Duck": "Q1217608",
    "Rosmersholm": "Q1432009",
    "The Lady From The Sea": "Q1212719",
    "Hedda Gabler": "Q176465",
    "The Master Builder": "Q641378",
    "Little Eyolf": "Q983970",
    "John Gabriel Borkman": "Q289117",
    "When We Dead Awaken": "Q1728632",
}


def _aar(verdi: str | None) -> int | None:
    """Årstallet ut av en Wikidata-dato.

    De to endepunktene formaterer ulikt: WDQS gir «1879-12-04T00:00:00Z», QLever
    gir «+1879-12-04T00:00:00Z». Et krav om ledende plusstegn gjør at WDQS-svar
    stille blir null — alle tretti verkene fikk ingen årstall på den måten.
    """
    if not verdi:
        return None
    try:
        return int(verdi.lstrip("+")[:4])
    except ValueError:
        return None


def main() -> None:
    verdier = " ".join(f"wd:{q}" for q in VERK_QID.values())
    sporring = f"""SELECT ?w ?utgitt ?urpremiere WHERE {{
  VALUES ?w {{ {verdier} }}
  OPTIONAL {{ ?w wdt:P577 ?utgitt }}
  OPTIONAL {{ ?w wdt:P1191 ?urpremiere }}
}}"""
    url = SPARQL + "?" + urllib.parse.urlencode({"query": sporring, "format": "json"})
    # WDQS strammer til «1 req / min» når tjenesten er under press. Dette er ett
    # enkelt kall som skal kjøres én gang i året, så det kan godt vente et minutt.
    rader = None
    for forsok in range(1, 9):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": BRUKERAGENT, "Accept": "application/sparql-results+json"})
            with urllib.request.urlopen(req, timeout=180) as svar:
                rader = json.loads(svar.read())["results"]["bindings"]
            break
        except urllib.error.HTTPError as e:
            if forsok == 8:
                raise SystemExit(f"WDQS svarte {e}")
            print(f"  ! HTTP {e.code} - venter 65s ({forsok}/7)", flush=True)
            time.sleep(65)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            if forsok == 8:
                raise SystemExit(f"WDQS utilgjengelig: {e}")
            print(f"  ! {e} - venter 30s", flush=True)
            time.sleep(30)

    # Et verk kan ha flere utgivelsesdatoer (nyutgaver). Vi tar den tidligste:
    # det er førsteutgaven som er relevant for når stykket kom til verden.
    tidligst: dict[str, dict] = {}
    for r in rader:
        qid = r["w"]["value"].rsplit("/", 1)[-1]
        post = tidligst.setdefault(qid, {"utgitt": None, "urpremiere": None})
        for felt, nokkel in (("utgitt", "utgitt"), ("urpremiere", "urpremiere")):
            a = _aar(r.get(felt, {}).get("value"))
            if a and (post[nokkel] is None or a < post[nokkel]):
                post[nokkel] = a

    verk = []
    for tittel, qid in VERK_QID.items():
        p = tidligst.get(qid, {})
        verk.append({"verk": tittel, "qid": qid,
                     "utgitt": p.get("utgitt"), "urpremiere": p.get("urpremiere")})
    verk.sort(key=lambda v: (v["utgitt"] or 9999, v["verk"]))

    fil = RAADATA_DIR / "ibsenstage_verk.json"
    fil.write_text(json.dumps({
        "hentet": date.today().isoformat(), "kilde": "Wikidata P577 / P1191",
        "antall": len(verk), "verk": verk,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    uten = [v["verk"] for v in verk if not v["utgitt"]]
    print(f"{len(verk)} verk, {len(verk) - len(uten)} med utgivelsesår")
    if uten:
        print(f"  uten årstall: {', '.join(uten)}")
    print()
    for v in verk:
        print(f"  {str(v['utgitt'] or '—'):>5}  {v['verk']:26s} "
              f"urpremiere {v['urpremiere'] or '—'}   {v['qid']}")
    print(f"\n  {fil}")


if __name__ == "__main__":
    main()
