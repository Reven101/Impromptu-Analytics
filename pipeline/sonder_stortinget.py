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
import collections
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

    # Registeret lister også sesjoner som ikke har begynt ennå — i august 2026
    # står 2028-2029 der, tom. Å ta den nyeste id-en blindt gir null saker og
    # ser ut som at API-et er borte. Svaret oppgir «innevaerende_sesjon» selv,
    # så vi bruker den, og faller ellers bakover gjennom lista til vi finner en
    # sesjon som faktisk har saker.
    # «innevaerende_sesjon» er et objekt, ikke en streng — id-en ligger inni.
    # Sendt rått som sesjonid ga en URL-enkodet dict og HTTP 400.
    rå_inneværende = (sesjoner or {}).get("innevaerende_sesjon") if isinstance(sesjoner, dict) else None
    if isinstance(rå_inneværende, dict):
        inneværende = rå_inneværende.get("id")
    elif isinstance(rå_inneværende, str):
        inneværende = rå_inneværende
    else:
        inneværende = None
    if inneværende:
        print(f"    API-et oppgir inneværende sesjon: {inneværende}")

    if args.sesjon:
        kandidater = [args.sesjon]
    else:
        kandidater = ([inneværende] if inneværende else []) + [
            i for i in ider if i != inneværende
        ]

    saksliste: list = []
    sesjon = None
    for kandidat in kandidater[:8]:
        _, saker = vis(f"Saker i sesjon {kandidat}", "saker",
                       sesjonid=kandidat, format="json")
        saksliste = forste_liste(saker)
        if saksliste:
            sesjon = kandidat
            break
        print(f"    · {kandidat} har ingen saker — prøver forrige sesjon")

    funn["saksmetadata"] = bool(saksliste)
    if not saksliste:
        print(f"    ✗ ingen av de prøvde sesjonene har saker "
              f"({', '.join(str(k) for k in kandidater[:8])}).")
        print("      Sjekk sesjons-id-formatet mot dokumentasjonen, eller kjør")
        print("      med --sesjon <id> for en du vet er avsluttet.")
        return 1
    print(f"    → sonderer videre på sesjon {sesjon}")

    felt = sorted({k for s in saksliste[:50] if isinstance(s, dict) for k in s})
    print(f"    {len(saksliste)} saker. Felt på radnivå: {', '.join(felt)}")
    for ventet in ("id", "tittel", "korttittel", "emne_liste", "type", "status",
                   "dokumentgruppe", "behandlet_sesjon_id"):
        print(f"      {'✓' if ventet in felt else '·'} {ventet}")

    statuser = collections.Counter(str(s.get("status")) for s in saksliste
                                   if isinstance(s, dict))
    print(f"    status-verdier: {dict(statuser)}")

    # Nivå 2 og 3 måler feil ting på en sak som ikke er ferdig: en sak under
    # behandling har hverken vedtak eller innstilling ennå. Vi leter derfor
    # etter en ferdigbehandlet sak med publikasjonsreferanser, og bruker den.
    sak_detalj = None
    sakid = None
    print("\n    Leter etter en ferdigbehandlet sak med publikasjoner:")
    for kandidat in saksliste[:40]:
        if not (isinstance(kandidat, dict) and kandidat.get("id")):
            continue
        time.sleep(PAUSE)
        status, _, kropp = hent("sak", sakid=kandidat["id"], format="json")
        detalj = som_json(kropp) if status == 200 else None
        if not isinstance(detalj, dict):
            print(f"      {kandidat['id']}: HTTP {status}")
            continue
        ferdig = detalj.get("ferdigbehandlet")
        refs = detalj.get("publikasjon_referanse_liste") or []
        # Én linje per sak. Førti fulle detaljblokker gjør loggen uleselig,
        # og det er treffet vi er ute etter, ikke letingen.
        print(f"      {kandidat['id']}: ferdigbehandlet={ferdig}, "
              f"{len(refs)} publikasjonsreferanser")
        if ferdig in (True, "true") and refs:
            sak_detalj, sakid = detalj, kandidat["id"]
            print(f"    → bruker sak {sakid}: {str(kandidat.get('tittel'))[:60]}")
            vis(f"Saksdetaljer for {sakid}", "sak", sakid=sakid, format="json")
            break
    if sak_detalj is None:
        # Ingen ferdig sak blant de første — ta den første vi fikk detaljer på,
        # og si fra at nivå 3 da måler en sak som ikke er avgjort.
        forste = next((k for k in saksliste if isinstance(k, dict) and k.get("id")), None)
        sakid = forste["id"]
        _, sak_detalj = vis(f"Saksdetaljer for {sakid} (ingen ferdigbehandlet funnet)",
                            "sak", sakid=sakid, format="json")
        print("    ⚠ fant ingen ferdigbehandlet sak med publikasjoner — nivå 3")
        print("      måler da en sak som kanskje ikke er votert over ennå")

    # ---------------------------------------------------------- nivå 2
    print("\n" + "=" * 72)
    print("NIVÅ 2 — FULLTEKST  (dette avgjør akt 2)")
    funn["fulltekst"] = False

    # 1) Saksdetaljene bærer tekst selv. innstillingstekst og kortvedtak sto i
    #    toppnøklene på forrige kjøring — de måles her framfor å antas.
    print("\n  Tekst i saksdetaljene")
    for felt in ("innstillingstekst", "kortvedtak", "parentestekst", "henvisning"):
        verdi = (sak_detalj or {}).get(felt)
        if isinstance(verdi, str) and verdi.strip():
            ren = re.sub(r"<[^>]+>", " ", verdi)
            print(f"    {felt}: {len(ren)} tegn")
            print(f"      «{ren.strip()[:180]}…»")
            if len(ren) >= FULLTEKST_TERSKEL:
                funn["fulltekst"] = True
        else:
            print(f"    {felt}: tomt")

    # 2) publikasjon_referanse_liste gir eksport_id og lenke_url per publikasjon.
    #    Det er veien inn til selve dokumentet — ikke publikasjoner-endepunktet,
    #    som krever en PublikasjonType vi ikke hadde (derav HTTP 400 sist, som
    #    var vår feil og ikke et bevis på at fulltekst mangler).
    referanser = (sak_detalj or {}).get("publikasjon_referanse_liste") or []
    print(f"\n  Publikasjonsreferanser på saken: {len(referanser)}")
    for ref in referanser[:5]:
        if isinstance(ref, dict):
            print(f"    type={ref.get('type')}/{ref.get('undertype')} "
                  f"eksport_id={ref.get('eksport_id')}")
            print(f"      {ref.get('lenke_tekst')} → {ref.get('lenke_url')}")

    eksport_id = next((r.get("eksport_id") for r in referanser
                       if isinstance(r, dict) and r.get("eksport_id")), None)
    if eksport_id:
        form, publikasjon = vis(f"Publikasjonen {eksport_id} — har den tekstkropp?",
                                "publikasjon", publikasjonid=eksport_id, format="json")
        if form == "json":
            tegn = tekstmengde(publikasjon)
            print(f"    tekstmengde: {tegn} tegn (terskel: {FULLTEKST_TERSKEL})")
            funn["fulltekst"] = funn["fulltekst"] or tegn >= FULLTEKST_TERSKEL
        elif form in ("xml", "ukjent"):
            _, _, kropp = hent("publikasjon", publikasjonid=eksport_id)
            bar = re.sub(r"<[^>]+>", " ", kropp)
            print(f"    ikke JSON, men {len(bar)} tegn tekst utenfor taggene "
                  f"(terskel: {FULLTEKST_TERSKEL})")
            print(f"      «{' '.join(bar.split())[:200]}…»")
            funn["fulltekst"] = funn["fulltekst"] or len(bar) >= FULLTEKST_TERSKEL
    else:
        print("    · ingen eksport_id å slå opp")

    # 3) publikasjoner-endepunktet krever publikasjontype. Feilmeldingen lister
    #    ikke de gyldige verdiene, så vi prøver kandidatene og rapporterer hvilke
    #    som svarer — det er raskere enn å lete i dokumentasjonen, og svaret blir
    #    stående i loggen for neste gang.
    print("\n  Hvilke publikasjontype-verdier godtas?")
    for kandidat in ("referat", "innstilling", "innstillinger", "dok8", "dok12",
                     "lovvedtak", "innberetning", "sporretime", "alle"):
        time.sleep(PAUSE)
        status, _, kropp = hent("publikasjoner", publikasjontype=kandidat,
                                sesjonid=sesjon, format="json")
        if status == 200:
            data = som_json(kropp)
            antall = len(forste_liste(data)) if data else 0
            print(f"    ✓ {kandidat}: HTTP 200, {antall} publikasjoner")
        else:
            print(f"    · {kandidat}: HTTP {status}")

    # ---------------------------------------------------------- nivå 3
    print("\n" + "=" * 72)
    print("NIVÅ 3 — VEDTAK")
    funn["vedtak"] = False

    # En sak i en pågående sesjon KAN ikke ha vedtak ennå, så å lete der og
    # melde «✗ vedtak» måler kalenderen, ikke API-et. Vi går derfor gjennom
    # sesjonene bakover — en avsluttet sesjon har ferdigbehandlede saker —
    # og stopper på den første saken som faktisk har en votering.
    # ider er nyeste først, og lista inneholder sesjoner som ikke har begynt.
    # «Avsluttet» er derfor det som ligger ETTER den inneværende i lista —
    # tar man bare «alle andre», ender man i 2028-2029, som er tom.
    if args.sesjon or sesjon not in ider:
        eldre = []
    else:
        eldre = ider[ider.index(sesjon) + 1:]
    avsluttede = eldre
    for kilde_sesjon in [sesjon, *avsluttede][:4]:
        if funn["vedtak"]:
            break
        if kilde_sesjon == sesjon:
            saker_her = saksliste
        else:
            time.sleep(PAUSE)
            status, _, kropp = hent("saker", sesjonid=kilde_sesjon, format="json")
            saker_her = forste_liste(som_json(kropp)) if status == 200 else []
            print(f"\n  Prøver avsluttet sesjon {kilde_sesjon}: {len(saker_her)} saker")

        for kandidat in saker_her[:25]:
            if not (isinstance(kandidat, dict) and kandidat.get("id")):
                continue
            time.sleep(PAUSE)
            status, _, kropp = hent("voteringer", sakid=kandidat["id"], format="json")
            vliste = forste_liste(som_json(kropp)) if status == 200 else []
            if not vliste:
                continue

            print(f"\n  Sak {kandidat['id']} i {kilde_sesjon} har "
                  f"{len(vliste)} voteringer")
            print(f"    {str(kandidat.get('tittel'))[:70]}")
            vfelt = sorted({k for v in vliste[:10] if isinstance(v, dict) for k in v})
            print(f"    Felt: {', '.join(vfelt)}")
            funn["vedtak"] = True

            vid = next((v.get("votering_id") or v.get("id") for v in vliste
                        if isinstance(v, dict)), None)
            if vid:
                vis(f"Voteringsresultat {vid}", "voteringsresultat",
                    voteringid=vid, format="json")
            break

    if not funn["vedtak"]:
        print("\n  · fant ingen sak med voteringer i de prøvde sesjonene.")
        print("    Det er ikke det samme som at voteringer ikke finnes —")
        print("    kjør med --sesjon mot en du vet er avsluttet før du tror på det.")

    # ---------------------------------------------------------- konklusjon
    print("\n" + "=" * 72)
    print("KONKLUSJON — lim denne utskriften inn i samtalen")
    print("=" * 72)
    for nivå, etikett in (("saksmetadata", "Nivå 1  saksmetadata"),
                          ("fulltekst", "Nivå 2  fulltekst"),
                          ("vedtak", "Nivå 3  vedtak")):
        print(f"  {'✓' if funn.get(nivå) else '✗'} {etikett}")

    # Hvert funn får sin egen if/else. Da jeg klemte vedtaks-meldingen inn
    # mellom fulltekst-if-en og dens else, bandt else-en seg til FEIL if:
    # en kjøring med vedtak=True skrev ut «ingen tekst passerte terskelen»
    # rett under «✓ Nivå 2 fulltekst». En rapport som motsier seg selv er
    # verre enn ingen rapport — det er hele produktet til dette skriptet.
    if funn.get("fulltekst"):
        print("\n  Akt 2 kan bygges som planlagt: verbatim navngiving av rapporttitler")
        print("  i stortingsdokumenter, rapportert som en NEDRE grense.")
    else:
        print("\n  Ingen enkelttekst passerte terskelen på "
              f"{FULLTEKST_TERSKEL} tegn.")
        print("  Se på tallene over før du konkluderer: en innstillingstekst på")
        print("  1500 tegn er ikke fulltekst, men den kan godt være nok til å")
        print("  bære en rapporttittel — det er navngivingen vi teller, ikke")
        print("  lengden. Alternativene:")
        print("    a) bruke innstillingstekst + kortvedtak som søkeflate, med")
        print("       rekkevidden oppgitt eksplisitt i historien")
        print("    b) følge lenke_url fra publikasjonsreferansene ut til")
        print("       selve dokumentet, utenfor eksport-API-et")
        print("    c) skrive akt 2 om til «dette lar seg ikke måle med åpne")
        print("       data», som også er et funn")
        print("  Ikke velg for meg — lim utskriften inn, så tar vi det sammen.")

    if not funn.get("vedtak"):
        print("\n  Uten nivå 3 mister trakten sitt siste trinn: vi kan telle")
        print("  «navngitt» og «behandlet», men ikke «vedtatt». Trakten blir da")
        print("  tre trinn i stedet for fire — ikke umulig, bare kortere.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
