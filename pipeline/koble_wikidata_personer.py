"""Kobler IbsenStage-personer i skapende roller til Wikidata-ID-er (Q-numre).

Kjøring (krever hent_ibsenstage_detaljer.py først):

    python pipeline/koble_wikidata_personer.py            # alle tre steg
    python pipeline/koble_wikidata_personer.py --bare-beslutning   # uten nettverk

Hvorfor ikke bare bruke den offisielle koblingen: Wikidata HAR en egenskap for
dette, `P11923 (IbsenStage ID)`. Den brukes av 604 elementer i hele Wikidata,
hvorav 547 er personer — mot 96 415 personer i IbsenStage. Det er 0,6 %, og
holder ikke til analyse. Men de 547 er kuratert av mennesker, så de brukes her
til to ting: de overstyrer navnematchingen der de finnes, og de er fasit når
presisjonen skal måles.

Hvorfor QLever og ikke Wikidatas eget API: unionen av de aktuelle yrkene er
448 464 personer med 8,3 millioner navneformer — for mye å laste ned for å finne
noen tusen treff. Motsatt vei, ett søk per navn mot Wikidatas API, ble målt til
under ett navn i sekundet, og TREGERE takt ga FLERE avvisninger. Det er ikke en
klientkvote man kan pace seg rundt, det er en global struping. QLever er et
uavhengig SPARQL-endepunkt over de samme dataene; der kan navnene sendes inn i
spørringen i bunter på 300, og hele jobben blir 77 kall i stedet for 23 055.

Kobling på navn alene duger ikke. «Eugen Apostol» er to forskjellige mennesker i
Wikidata, og det finnes mange «Anna Larsen». Derfor kreves det at kandidaten
BÅDE har eksakt navnetreff, ET yrke som hører hjemme i teater/film/musikk, OG en
levetid som er forenlig med årene personen er aktiv i IbsenStage. Overlever mer
enn én kandidat, kobles det ikke — en tom kobling er et hull vi kan telle, mens
en feil kobling forurenser alt som bygger på den.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import kontrakt  # noqa: F401
from hent_wikidata_regissorer import normaliser

API = "https://www.wikidata.org/w/api.php"
# QLever er et uavhengig SPARQL-endepunkt over de samme Wikidata-dataene. Vi bruker
# det fordi Wikidatas eget API strupte oss ned til under ett navn i sekundet — og
# tregere takt ga FLERE avvisninger, ikke færre, altså en global begrensning vi
# ikke kunne pacet oss rundt. QLever svarer på millisekunder og lar oss sende
# navnene inn i spørringen i bunter, i stedet for ett søk per navn.
QLEVER = "https://qlever.dev/api/wikidata"
BRUKERAGENT = "impromptu.no research (kontakt: impromptu.no)"
BUNT_NAVN = 300
PAUSE = 2.0

RAADATA_DIR = Path(
    os.environ.get("IBSENSTAGE_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ibsenstage"
)

# Rollene vi kobler. Skuespillere holdes utenfor med vilje: de er 72 343 personer,
# og Wikidatas skuespillerpopulasjon er i hundretusenklassen. Navnesammenfall
# vokser med begge sidene, og treffsikkerheten ville ikke holdt.
SKAPENDE = {"Director", "Translator", "Adapter", "Composer", "Choreographer",
            "Designer", "Costume Designer", "Lighting Designer", "Sound Designer",
            "Dramaturg", "Producer", "Playwright"}

# Roller som krever at personen levde da oppsetningen fant sted. De øvrige —
# dramatiker, komponist, oversetter, bearbeider — krediteres for et verk som
# brukes videre etter deres død. Henrik Ibsen står som dramatiker på oppsetninger
# fra 2026; han døde i 1906. Uten dette skillet avvises han som umulig.
MAA_LEVE = {"Director", "Choreographer", "Dramaturg", "Producer", "Designer",
            "Costume Designer", "Lighting Designer", "Sound Designer"}

# Yrker som gjør en Wikidata-person til en plausibel kandidat. Håndskrevet liste:
# den skal være vid nok til å slippe gjennom en scenograf som står oppført som
# «kunstner», og smal nok til å utelukke fotballspilleren med samme navn.
YRKER = {
    "Q3387717": "teaterregissør", "Q2526255": "filmregissør", "Q1734662": "dramaturg",
    "Q1281618": "scenograf", "Q1323191": "kostymedesigner", "Q2490358": "koreograf",
    "Q36834": "komponist", "Q333634": "oversetter", "Q214917": "dramatiker",
    "Q2259451": "sceneskuespiller", "Q10800557": "filmskuespiller", "Q33999": "skuespiller",
    "Q158852": "dirigent", "Q639669": "musiker", "Q1028181": "maler",
    "Q483501": "kunstner", "Q49757": "lyriker", "Q36180": "forfatter",
    "Q3455803": "regissør", "Q222344": "scenograf (annen)", "Q5716684": "danser",
}

_las = threading.Lock()


def _api(**p) -> dict:
    p.setdefault("format", "json")
    url = API + "?" + urllib.parse.urlencode(p)
    for n in range(1, 8):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": BRUKERAGENT})
            with urllib.request.urlopen(req, timeout=90) as svar:
                return json.loads(svar.read())
        except urllib.error.HTTPError as e:
            if n == 7:
                raise SystemExit(f"Wikidata-API-et svarte {e}")
            time.sleep(min(2 ** n, 30))
        except (urllib.error.URLError, OSError, TimeoutError):
            if n == 7:
                raise SystemExit("Wikidata-API-et er utilgjengelig")
            time.sleep(5 * n)
    return {}


# ------------------------------------------------------------- personer ----

def les_personer() -> dict[int, dict]:
    browse = {r["hendelse_id"]: r for r in json.loads(
        (RAADATA_DIR / "ibsenstage_hendelser.json").read_text(encoding="utf-8"))["hendelser"]}
    p: dict[int, dict] = {}
    with (RAADATA_DIR / "ibsenstage_detaljer.jsonl").open(encoding="utf-8") as f:
        for linje in f:
            x = json.loads(linje)
            b_rad = browse.get(x["hendelse_id"]) or {}
            for b in x["bidragsytere"]:
                if not b["person_id"] or b["funksjon"] not in SKAPENDE:
                    continue
                e = p.setdefault(b["person_id"], {
                    "person_id": b["person_id"], "navn": b["navn"],
                    "funksjoner": collections.Counter(), "land": collections.Counter(),
                    "aar": [],
                })
                e["funksjoner"][b["funksjon"]] += 1
                if b_rad.get("land"):
                    e["land"][b_rad["land"]] += 1
                if b_rad.get("aar"):
                    e["aar"].append(b_rad["aar"])
    # Navn med ett ledd kan ikke matches forsvarlig - «Shakespeare» treffer alt.
    return {k: v for k, v in p.items() if v["navn"] and len(v["navn"].split()) >= 2}


PREFIKS = """PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""


def _qlever(sporring: str, forsok: int = 8) -> list[dict]:
    data = urllib.parse.urlencode({"query": PREFIKS + sporring}).encode()
    for n in range(1, forsok + 1):
        try:
            req = urllib.request.Request(QLEVER, data=data, headers={
                "User-Agent": BRUKERAGENT,
                "Accept": "application/sparql-results+json",
                "Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=300) as svar:
                return json.loads(svar.read())["results"]["bindings"]
        except urllib.error.HTTPError as e:
            if n == forsok:
                raise SystemExit(f"QLever svarte {e}")
            ventetid = min(15 * n, 120) if e.code == 429 else 10 * n
            print(f"  ! HTTP {e.code} - venter {ventetid}s", flush=True)
            time.sleep(ventetid)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            if n == forsok:
                raise SystemExit(f"QLever utilgjengelig: {e}")
            time.sleep(10 * n)
    return []


# ---------------------------------------------------------- steg 1: søk ----

def sok_kandidater(personer: dict[int, dict], cachefil: Path) -> dict[str, list[dict]]:
    """Kandidater fra Wikidata for hvert navn, hentet i bunter fra QLever.

    Spørringen gjør tre ting på én gang som tidligere krevde to API-er: den
    begrenser til personer med et relevant yrke, den matcher mot både offisielt
    navn og aliaser, og den henter fødsels- og dødsår. `FILTER(STR(?l) = ?navn)`
    er nødvendig fordi Wikidata-etiketter er språktaggede — «Peter Stein»@de er
    ikke lik «Peter Stein», og uten STR() blir treffet null.
    """
    cache: dict[str, list[dict]] = {}
    if cachefil.exists():
        with cachefil.open(encoding="utf-8") as f:
            for linje in f:
                d = json.loads(linje)
                cache[d["navn"]] = d["kandidater"]

    navn = sorted({p["navn"] for p in personer.values()})
    mangler = [n for n in navn if n not in cache]
    print(f"steg 1: {len(navn)} navn, {len(cache)} fra cache, {len(mangler)} å slå opp")
    if not mangler:
        return cache

    yrker = " ".join(f"wd:{q}" for q in YRKER)
    utfil = cachefil.open("a", encoding="utf-8")
    start = time.time()
    for i in range(0, len(mangler), BUNT_NAVN):
        bunt = mangler[i:i + BUNT_NAVN]
        verdier = " ".join(json.dumps(n) for n in bunt)
        rader = _qlever(f"""SELECT ?p ?l ?fodt ?dod WHERE {{
  VALUES ?navn {{ {verdier} }}
  VALUES ?o {{ {yrker} }}
  ?p wdt:P106 ?o .
  {{ ?p rdfs:label ?l }} UNION {{ ?p skos:altLabel ?l }}
  FILTER(STR(?l) = ?navn)
  OPTIONAL {{ ?p wdt:P569 ?fodt }} OPTIONAL {{ ?p wdt:P570 ?dod }}
}}""")
        treff: dict[str, dict[str, dict]] = {n: {} for n in bunt}
        for r in rader:
            etikett = r["l"]["value"]
            if etikett not in treff:
                continue
            qid = r["p"]["value"].rsplit("/", 1)[-1]
            treff[etikett][qid] = {
                "qid": qid,
                "fodt": (r.get("fodt", {}).get("value") or "")[:4] or None,
                "dod": (r.get("dod", {}).get("value") or "")[:4] or None,
            }
        for n in bunt:
            cache[n] = list(treff[n].values())
            utfil.write(json.dumps({"navn": n, "kandidater": cache[n]},
                                   ensure_ascii=False) + "\n")
        utfil.flush()
        ferdig = min(i + BUNT_NAVN, len(mangler))
        gatt = time.time() - start
        print(f"  {ferdig}/{len(mangler)}  "
              f"~{(len(mangler) - ferdig) / (ferdig / gatt) / 60:.0f} min igjen", flush=True)
        time.sleep(PAUSE)
    utfil.close()
    return cache


# ------------------------------------------------- steg 2: kandidatdata ----

FELT = {"P106": "yrke", "P569": "fodt", "P570": "dod", "P27": "statsborger",
        "P21": "kjonn", "P11923": "ibsenstage"}


def hent_kandidater(qids: set[str], cachefil: Path) -> dict[str, dict]:
    cache: dict[str, dict] = {}
    if cachefil.exists():
        with cachefil.open(encoding="utf-8") as f:
            for linje in f:
                d = json.loads(linje)
                cache[d["qid"]] = d

    mangler = sorted(qids - set(cache))
    print(f"steg 2: {len(qids)} kandidater, {len(cache)} fra cache, {len(mangler)} å hente")
    if not mangler:
        return cache

    utfil = cachefil.open("a", encoding="utf-8")
    for i in range(0, len(mangler), 50):
        bunt = mangler[i:i + 50]
        d = _api(action="wbgetentities", ids="|".join(bunt),
                 props="labels|aliases|claims", languages="en|de|no|nb|nn|sv|da|fr|it|es|"
                                                          "hu|pl|cs|nl|fi|pt|ro|el|tr")
        for qid, e in (d.get("entities") or {}).items():
            navn = {v["value"] for v in (e.get("labels") or {}).values()}
            navn |= {a["value"] for al in (e.get("aliases") or {}).values() for a in al}
            post = {"qid": qid, "navn": sorted(navn)}
            for pid, felt in FELT.items():
                verdier = []
                for c in (e.get("claims") or {}).get(pid, []):
                    dv = (c.get("mainsnak") or {}).get("datavalue", {}).get("value")
                    if isinstance(dv, dict):
                        verdier.append(dv.get("id") or dv.get("time") or "")
                    elif dv:
                        verdier.append(dv)
                post[felt] = verdier
            cache[qid] = post
            utfil.write(json.dumps(post, ensure_ascii=False) + "\n")
        utfil.flush()
        if (i // 50) % 20 == 0:
            print(f"  {min(i + 50, len(mangler))}/{len(mangler)}", flush=True)
        time.sleep(0.4)
    utfil.close()
    return cache


# ------------------------------------------------- steg 3: beslutningen ----

def _aar(tid: str | None) -> int | None:
    """QLever gir «1912-04-03T00:00:00Z» eller «1912»; vi vil ha årstallet."""
    if not tid:
        return None
    try:
        return int(str(tid)[:4])
    except ValueError:
        return None


def vurder(person: dict, kandidat: dict) -> tuple[bool, str]:
    """Kan denne kandidaten være denne personen? (ja/nei, begrunnelse)

    Navnetreff og yrke er allerede avgjort i spørringen — QLever returnerer bare
    personer med eksakt navnetreff og et yrke fra YRKER. Her gjenstår levetiden.
    """
    fodt = _aar(kandidat.get("fodt"))
    dod = _aar(kandidat.get("dod"))
    aar = person["aar"]
    if aar and fodt:
        # Verket kan ikke være laget før opphavspersonen fantes. Ingen debuterer
        # før fylte 12; grensen er romslig med vilje og skal luke ut åpenbare
        # bomtreff, ikke avgjøre tvilstilfeller.
        if min(aar) < fodt + 12:
            return False, f"født {fodt}, aktiv fra {min(aar)}"
        # Dødsåret sier bare noe for roller som krever at personen var til stede.
        if dod and max(aar) > dod + 30 and set(person["funksjoner"]) <= MAA_LEVE:
            return False, f"død {dod}, aktiv til {max(aar)}"
    return True, "ok"


def beslutt(personer: dict[int, dict], sok: dict[str, list[dict]],
            fasit: dict[int, str]) -> list[dict]:
    ut = []
    for pid, p in personer.items():
        if pid in fasit:
            ut.append({**_slank(p), "qid": fasit[pid], "kilde": "P11923", "kandidater": 1})
            continue
        aktuelle = [k["qid"] for k in sok.get(p["navn"], []) if vurder(p, k)[0]]
        ut.append({**_slank(p),
                   "qid": aktuelle[0] if len(aktuelle) == 1 else None,
                   "kilde": "navn" if len(aktuelle) == 1 else
                            ("flertydig" if len(aktuelle) > 1 else "ingen"),
                   "kandidater": len(aktuelle)})
    return ut


def _slank(p: dict) -> dict:
    return {"person_id": p["person_id"], "navn": p["navn"],
            "funksjoner": sorted(p["funksjoner"]),
            "land": p["land"].most_common(1)[0][0] if p["land"] else None,
            "fra": min(p["aar"]) if p["aar"] else None,
            "til": max(p["aar"]) if p["aar"] else None}


def rapport(koblinger: list[dict], fasit: dict[int, str], personer: dict[int, dict]) -> None:
    etter = collections.Counter(k["kilde"] for k in koblinger)
    n = len(koblinger)
    koblet = etter["P11923"] + etter["navn"]
    print(f"\n{n} personer i skapende roller")
    print(f"  koblet:     {koblet:6d}  ({koblet / n * 100:.1f}%)")
    print(f"    kuratert P11923: {etter['P11923']}")
    print(f"    navnematch:      {etter['navn']}")
    print(f"  flertydige: {etter['flertydig']:6d}  (mer enn én kandidat overlevde)")
    print(f"  ingen:      {etter['ingen']:6d}")

    print("\nDekning per rolle:")
    per = collections.defaultdict(lambda: [0, 0])
    for k in koblinger:
        for f in k["funksjoner"]:
            per[f][0] += 1
            per[f][1] += 1 if k["qid"] else 0
    for f, (tot, ok) in sorted(per.items(), key=lambda kv: -kv[1][0]):
        print(f"  {f:20s} {ok:5d}/{tot:5d} = {ok / tot * 100:5.1f}%")

    # Presisjon: hva ville navnematchingen sagt om de kuraterte koblingene?
    tull = {"treff": 0, "bom": 0, "flertydig": 0, "ingen": 0}
    for pid, riktig in fasit.items():
        p = personer.get(pid)
        if not p:
            continue
        aktuelle = [k["qid"] for k in SOK_GLOBAL.get(p["navn"], []) if vurder(p, k)[0]]
        if len(aktuelle) == 1:
            tull["treff" if aktuelle[0] == riktig else "bom"] += 1
        elif len(aktuelle) > 1:
            tull["flertydig"] += 1
        else:
            tull["ingen"] += 1
    målt = tull["treff"] + tull["bom"]
    if målt:
        print(f"\nPresisjon målt mot de {len(fasit)} kuraterte koblingene:")
        print(f"  navnematchingen ga ett svar på {målt} av dem")
        print(f"  riktig {tull['treff']}, feil {tull['bom']} "
              f"= {tull['treff'] / målt * 100:.1f}% presisjon")
        print(f"  avvist som flertydig {tull['flertydig']}, ingen kandidat {tull['ingen']}")


SOK_GLOBAL: dict[str, list[str]] = {}
KAND_GLOBAL: dict[str, dict] = {}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bare-beslutning", action="store_true",
                    help="hopp over nettverkssteg, bruk det som ligger i cachen")
    args = ap.parse_args()

    personer = les_personer()
    print(f"{len(personer)} personer i skapende roller\n")

    sokcache = RAADATA_DIR / "wd_kandidater.jsonl"
    sok: dict[str, list[dict]] = {}
    if args.bare_beslutning:
        if sokcache.exists():
            with sokcache.open(encoding="utf-8") as f:
                for linje in f:
                    d = json.loads(linje)
                    sok[d["navn"]] = d["kandidater"]
    else:
        sok = sok_kandidater(personer, sokcache)

    # Kuraterte koblinger. Egenskapen brukes av så få at hele lista hentes i ett kall.
    fasit = {}
    for r in _qlever("SELECT ?p ?id WHERE { ?p wdt:P11923 ?id }"):
        verdi = r["id"]["value"]
        if verdi.startswith("contributor/"):
            try:
                fasit[int(verdi.split("/")[1])] = r["p"]["value"].rsplit("/", 1)[-1]
            except (ValueError, IndexError):
                pass
    fasit = {k: v for k, v in fasit.items() if k in personer}
    print(f"kuraterte koblinger (P11923) som gjelder våre personer: {len(fasit)}")

    SOK_GLOBAL.update(sok)

    koblinger = beslutt(personer, sok, fasit)
    fil = RAADATA_DIR / "ibsenstage_wikidata.json"
    fil.write_text(json.dumps({
        "hentet": date.today().isoformat(),
        "antall": len(koblinger),
        "koblet": sum(1 for k in koblinger if k["qid"]),
        "personer": koblinger,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    rapport(koblinger, fasit, personer)
    print(f"\n  {fil}")


if __name__ == "__main__":
    main()
