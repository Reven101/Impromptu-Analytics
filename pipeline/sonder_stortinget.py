"""Sonderer data.stortinget.no: hvilket koblingsnivå er faktisk tilgjengelig?

Kjøring (krever nett mot data.stortinget.no):

    python pipeline/sonder_stortinget.py
    python pipeline/sonder_stortinget.py --sesjon 2023-2024

Scriptet henter ingenting til fil og analyserer ingenting. Det har én oppgave:
fastslå, mot den levende kilden, hvilket av tre nivåer vi kan koble evalueringer
til stortingsbehandling på — og skrive svaret ut så et menneske kan lese det.

    Nivå 1  SAKSMETADATA    tittel, korttittel, emner, type, status per sak.
                            Nok til en temamatch — som vi ikke vil ha, fordi den
                            treffer nesten alltid og gjør gapet mindre enn det er.
    Nivå 2  FULLTEKST       teksten i innstillinger og referater. Dette er nivået
                            hele akt 2 står og faller på: bare med fulltekst kan vi
                            telle at et stortingsdokument faktisk NAVNGIR en
                            bestemt evaluering. Basisraten for en verbatim
                            tittelmatch er nær null, så treffet betyr noe.
    Nivå 3  VEDTAK          voteringer og voteringsresultat, så «behandlet» kan
                            skilles fra «vedtatt» i trakten.

Hvorfor sondering framfor å bare skrive koblingsscriptet: dokumentasjonen på
data.stortinget.no lister endepunktene, men ikke hvilke av dem som gir tekstkropp
og ikke bare metadata. Gjetter vi feil, får vi et koblingsscript som stille
degraderer til en svakere match enn den vi har lovet i teksten. Det er verre enn
å ikke ha tallet.

Alle endepunkter prøves i JSON (`format=json`); svarer de bare XML, rapporteres det,
for da må koblingsscriptet parse XML i stedet.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import kontrakt  # noqa: F401  -- setter utf-8 på stdout/stderr (Windows-konsollen er cp1252)

API = "https://data.stortinget.no/eksport"
KILDE = "Stortinget (åpne data)"
DOK = "https://data.stortinget.no/dokumentasjon-og-hjelp/"
BRUKERAGENT = "Impromptu-Analytics/1.0 (kontakt@impromptu.no)"
PAUSE = 0.3

# Terskel for hva som teller som «fulltekst». Et metadatasvar om en innstilling er
# gjerne et par tusen tegn; selve innstillingen er titusener. Vi setter listen lavt
# nok til å fange korte referater, høyt nok til at et rent metadataobjekt ikke
# feilaktig blir godkjent som tekstkropp.
FULLTEKST_TERSKEL = 4_000


def hent(sti: str, **params) -> tuple[int, str, str]:
    """Returnerer (http-status, content-type, kropp). Feil er data her, ikke unntak —
    poenget med sonderingen er å rapportere hva som ikke virker."""
    url = f"{API}/{sti}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": BRUKERAGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as svar:
            return (svar.status,
                    svar.headers.get("Content-Type", "?"),
                    svar.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "?"), e.read().decode("utf-8", errors="replace")[:400]
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, "-", f"{type(e).__name__}: {e}"


def som_json(kropp: str):
    try:
        return json.loads(kropp)
    except json.JSONDecodeError:
        return None


def vis(etikett: str, sti: str, **params) -> tuple[str, object]:
    """Prøver ett endepunkt og skriver ut hva det ga. Returnerer (form, data)."""
    time.sleep(PAUSE)
    status, ctype, kropp = hent(sti, **params)
    url = f"{API}/{sti}" + ("?" + urllib.parse.urlencode(params) if params else "")
    print(f"\n  {etikett}")
    print(f"    {url}")
    if status != 200:
        print(f"    ✗ HTTP {status} — {kropp[:200]}")
        return "feil", None

    data = som_json(kropp)
    if data is None:
        er_xml = kropp.lstrip().startswith("<")
        print(f"    ~ HTTP 200, {len(kropp)} tegn, men ikke JSON "
              f"({'XML' if er_xml else ctype}) — koblingsscriptet må parse dette som XML")
        return ("xml" if er_xml else "ukjent"), kropp

    if isinstance(data, dict):
        print(f"    ✓ HTTP 200, JSON-objekt, {len(kropp)} tegn")
        print(f"      toppnøkler: {', '.join(sorted(data)[:14])}")
        for nokkel, verdi in data.items():
            if isinstance(verdi, list) and verdi:
                print(f"      {nokkel}: liste med {len(verdi)} elementer")
                if isinstance(verdi[0], dict):
                    print(f"        nøkler i element 0: {', '.join(sorted(verdi[0])[:18])}")
    else:
        print(f"    ✓ HTTP 200, JSON-{type(data).__name__}, {len(kropp)} tegn")
    return "json", data


def forste_liste(data) -> list:
    """Stortinget pakker lister i «*_liste»-nøkler. Finn den første som har innhold."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for nokkel, verdi in data.items():
        if nokkel.endswith("_liste") and isinstance(verdi, list) and verdi:
            return verdi
    for verdi in data.values():
        if isinstance(verdi, list) and verdi:
            return verdi
    return []


def tekstmengde(objekt) -> int:
    """Antall tegn i alle strengverdier — hvor mye tekstkropp svaret faktisk bærer."""
    if isinstance(objekt, str):
        return len(objekt)
    if isinstance(objekt, dict):
        return sum(tekstmengde(v) for v in objekt.values())
    if isinstance(objekt, list):
        return sum(tekstmengde(v) for v in objekt)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sesjon", help="sesjons-id å sondere, f.eks. 2023-2024 "
                                     "(standard: nyeste sesjon API-et oppgir)")
    args = ap.parse_args()

    print(f"{KILDE} — {DOK}")
    print("=" * 72)
    funn: dict[str, bool] = {}

    # ---------------------------------------------------------- nivå 1
    print("\nNIVÅ 1 — SAKSMETADATA")
    _, sesjoner = vis("Sesjonsregisteret", "sesjoner", format="json")
    sesjonsliste = forste_liste(sesjoner)
    if not sesjonsliste:
        raise SystemExit(
            "FEIL: fikk ingen sesjoner. Uten sesjons-id-ene kommer vi ikke videre — "
            f"sjekk {DOK} for om eksport-API-et er flyttet."
        )
    ider = [s.get("id") for s in sesjonsliste if isinstance(s, dict) and s.get("id")]
    print(f"    {len(ider)} sesjoner, nyeste: {ider[:3]}")

    sesjon = args.sesjon or ider[0]
    _, saker = vis(f"Saker i sesjon {sesjon}", "saker", sesjonid=sesjon, format="json")
    saksliste = forste_liste(saker)
    funn["saksmetadata"] = bool(saksliste)
    if not saksliste:
        print("    ✗ ingen saker — nivå 1 er ikke tilgjengelig, og da faller alt")
        return 1

    felt = sorted({k for s in saksliste[:50] if isinstance(s, dict) for k in s})
    print(f"    {len(saksliste)} saker. Felt på radnivå: {', '.join(felt)}")
    for ventet in ("id", "tittel", "korttittel", "emne_liste", "type", "status",
                   "dokumentgruppe", "behandlet_sesjon_id"):
        print(f"      {'✓' if ventet in felt else '·'} {ventet}")

    sak = next((s for s in saksliste if isinstance(s, dict) and s.get("id")), None)
    sakid = sak.get("id")
    print(f"    Sonderer videre på sak {sakid}: {str(sak.get('tittel'))[:70]}")
    vis("Saksdetaljer", "sak", sakid=sakid, format="json")

    # ---------------------------------------------------------- nivå 2
    print("\n" + "=" * 72)
    print("NIVÅ 2 — FULLTEKST  (dette avgjør akt 2)")
    form, publikasjoner = vis("Publikasjoner for saken", "publikasjoner",
                              sakid=sakid, format="json")
    publiste = forste_liste(publikasjoner) if form == "json" else []
    funn["fulltekst"] = False

    if not publiste:
        print("    ✗ ingen publikasjonsliste for denne saken — prøver referatene i stedet")
    else:
        pfelt = sorted({k for p in publiste[:20] if isinstance(p, dict) for k in p})
        print(f"    {len(publiste)} publikasjoner. Felt: {', '.join(pfelt)}")
        pid = next((p.get("id") for p in publiste
                    if isinstance(p, dict) and p.get("id")), None)
        if pid:
            form, publikasjon = vis(f"Publikasjonen {pid} — har den tekstkropp?",
                                    "publikasjon", publikasjonid=pid, format="json")
            if form == "json":
                tegn = tekstmengde(publikasjon)
                print(f"    tekstmengde i svaret: {tegn} tegn "
                      f"(terskel for «fulltekst»: {FULLTEKST_TERSKEL})")
                funn["fulltekst"] = tegn >= FULLTEKST_TERSKEL
            elif form == "xml":
                # XML-svaret er kroppen selv; strip tagger for et grovt tegnestimat.
                _, _, kropp = hent("publikasjon", publikasjonid=pid)
                bar = re.sub(r"<[^>]+>", " ", kropp)
                print(f"    XML, ca. {len(bar.split())} ord tekst utenfor taggene")
                funn["fulltekst"] = len(bar) >= FULLTEKST_TERSKEL

    if not funn["fulltekst"]:
        vis("Referatoversikt (alternativ tekstkilde)", "publikasjoner",
            sesjonid=sesjon, format="json")

    # ---------------------------------------------------------- nivå 3
    print("\n" + "=" * 72)
    print("NIVÅ 3 — VEDTAK")
    form, voteringer = vis("Voteringer for saken", "voteringer", sakid=sakid, format="json")
    vliste = forste_liste(voteringer) if form == "json" else []
    funn["vedtak"] = bool(vliste)
    if vliste:
        vfelt = sorted({k for v in vliste[:10] if isinstance(v, dict) for k in v})
        print(f"    {len(vliste)} voteringer. Felt: {', '.join(vfelt)}")
        vid = next((v.get("votering_id") or v.get("id") for v in vliste
                    if isinstance(v, dict)), None)
        if vid:
            vis(f"Voteringsresultat {vid}", "voteringsresultat", voteringid=vid, format="json")
    else:
        print("    · ingen voteringer på denne saken (den kan være under behandling) —")
        print("      prøv --sesjon med en avsluttet sesjon før du konkluderer")

    # ---------------------------------------------------------- konklusjon
    print("\n" + "=" * 72)
    print("KONKLUSJON — lim denne utskriften inn i samtalen")
    print("=" * 72)
    for nivå, etikett in (("saksmetadata", "Nivå 1  saksmetadata"),
                          ("fulltekst", "Nivå 2  fulltekst"),
                          ("vedtak", "Nivå 3  vedtak")):
        print(f"  {'✓' if funn.get(nivå) else '✗'} {etikett}")

    if funn.get("fulltekst"):
        print("\n  Akt 2 kan bygges som planlagt: verbatim navngiving av rapporttitler")
        print("  i stortingsdokumenter, rapportert som en NEDRE grense.")
    else:
        print("\n  Fulltekst ble ikke bekreftet. Da kan akt 2 IKKE telle navngiving,")
        print("  og alternativene er:")
        print("    a) søke i sakstitler og korttitler alene — mye lavere rekkevidde,")
        print("       som i så fall må oppgis eksplisitt i teksten")
        print("    b) hente innstillingstekstene fra stortinget.no utenfor eksport-API-et")
        print("    c) skrive akt 2 om til «dette lar seg ikke måle med åpne data»,")
        print("       som også er et funn")
        print("  Ikke velg for meg — lim utskriften inn, så tar vi det sammen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
