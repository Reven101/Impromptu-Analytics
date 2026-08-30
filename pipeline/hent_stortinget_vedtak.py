"""Utvider trakten i akt 2 fra to trinn til fire: navngitt → behandlet → vedtatt.

Kjøring (krever nett mot data.stortinget.no):

    python pipeline/hent_stortinget_vedtak.py --sonder    # finn koblingsnøkkelen
    python pipeline/hent_stortinget_vedtak.py             # hent vedtakene

`koble_evalueringer_stortinget.py` teller at et stortingsdokument NAVNGIR en
evaluering. Det er trinn to. Trinn tre og fire — at saken faktisk ble behandlet,
og at det ble fattet et vedtak — krever en kobling fra publikasjon til sak, og
derfra til votering.

**Hvorfor scriptet leter etter koblingsnøkkelen i stedet for å kjenne den.**
Dokumentasjonen på data.stortinget.no lister endepunktene, men ikke hvilket felt
i et saksobjekt som bærer referansen til publikasjonen. Å gjette feltnavnet gir
enten en tom kobling (som ser ut som «ingen evalueringer ble behandlet») eller en
tilfeldig treffende én. Begge er verre enn ingen tall. `--sonder` henter derfor
saksobjektene og leter rekursivt etter publikasjons-ID-ene vi allerede vet
finnes, og skriver ut hvilken sti de lå på. Nøkkelen lagres, så hentingen etterpå
er billig.

**Bare de dokumentene som ga treff slås opp.** Trinn tre og fire angår per
definisjon bare evalueringer som allerede er navngitt, og det er noen hundre
dokumenter, ikke ni tusen. Hele denne hentingen er derfor minutter, ikke timer —
i motsetning til fulltekstene den bygger på.

**Referater kan ikke telles med.** Et referat dekker en hel møtedag og mange
saker; at en evaluering nevnes der beviser ikke at DEN saken ble behandlet.
Referattreff blir stående på trinn to, og antallet rapporteres for seg framfor å
forsvinne stille.

Rådata skrives UTENFOR repoet (jf. SIKKERHET.md): sett STORTINGET_DIR, ellers
../impromptu_raadata/stortinget/.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import time
from datetime import date
from pathlib import Path

import nett
import kontrakt  # noqa: F401  -- setter utf-8 på stdout/stderr (se CLAUDE.md)
from hent_stortinget_publikasjoner import normaliser

API = "https://data.stortinget.no/eksport"
KILDE = "Stortinget (åpne data)"
KILDE_URL = "https://data.stortinget.no/dokumentasjon-og-hjelp/"
BRUKERAGENT = "Impromptu-Analytics/1.0 (kontakt@impromptu.no)"
PAUSE = 0.3

# Dokumenttyper som hører til én sak, og derfor kan følges til et vedtak.
# Referat og innberetning gjør ikke det — se docstringen.
SAKSBUNDNE_TYPER = ("innstilling", "dok8", "lovvedtak", "dok12")

# Hvor mange saker sonderingen ser på før den gir opp å finne nøkkelen. Ligger
# referansen ikke i de første hundre, ligger den neppe i felt vi kan stole på.
SONDER_SAKER = 100

STORTINGET_DIR = Path(
    os.environ.get("STORTINGET_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "stortinget"
)
TREFFIL = STORTINGET_DIR / "navngitte_evalueringer.json"
NOKKELFIL = STORTINGET_DIR / "koblingsnokkel.json"
UTFIL = STORTINGET_DIR / "vedtak.json"


# ---------------------------------------------------------------- kilde

def hent_json(sti: str, **params) -> dict:
    import urllib.parse
    url = f"{API}/{sti}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return nett.hent_json(url, BRUKERAGENT, timeout=60)


def forste_liste(data) -> list:
    """Stortinget pakker svarene i ulikt navngitte lister (`saker_liste`,
    `voteringer_liste`). Vi tar den første lista i objektet framfor å hardkode
    navnet — det har endret seg mellom endepunktene før."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for verdi in data.values():
            if isinstance(verdi, list):
                return verdi
    return []


# ---------------------------------------------------------------- sondering

def _stier(objekt, sti: str = "", dybde: int = 0):
    """Alle (sti, streng) i et nøstet objekt. Brukes til å finne hvor en kjent
    ID ligger, uten å vite hva feltet heter."""
    if dybde > 6:
        return
    if isinstance(objekt, str):
        yield sti, objekt
    elif isinstance(objekt, dict):
        for k, v in objekt.items():
            yield from _stier(v, f"{sti}.{k}" if sti else k, dybde + 1)
    elif isinstance(objekt, list):
        for v in objekt:
            yield from _stier(v, f"{sti}[]", dybde + 1)


def _inneholder(tekst: str, nål: str) -> bool:
    """Substring, men bare på ordgrense.

    Uten grensesjekken ville «innst. 10 s» truffet inne i «innst. 101 s», og
    trakten fått treff på feil sak. Grensen er billig og fjerner hele klassen.
    """
    start = 0
    while True:
        i = tekst.find(nål, start)
        if i < 0:
            return False
        før = tekst[i - 1] if i else " "
        etter = tekst[i + len(nål)] if i + len(nål) < len(tekst) else " "
        if not før.isalnum() and not etter.isalnum():
            return True
        start = i + 1


def nokler_i(verdi: str, form: str, kjente: dict[str, str] | set) -> list[str]:
    """Hvilke kjente publikasjonsnøkler denne feltverdien peker på.

    Samme funksjon brukes i sonderingen og i den etterfølgende hentingen, så
    kartet bygges nøyaktig slik nøkkelen ble funnet. Skilles de to, får man en
    sondering som lykkes og en kobling som stille finner null.
    """
    if form == "id":
        return [verdi] if verdi in kjente else []
    if form == "tittel":
        n = normaliser(verdi)
        return [n] if n and n in kjente else []
    if form == "id_delstreng":
        return [k for k in kjente if _inneholder(verdi, k)]
    if form == "tittel_delstreng":
        n = normaliser(verdi)
        return [k for k in kjente if k and _inneholder(n, k)] if n else []
    raise ValueError(f"ukjent koblingsform: {form}")


def finn_koblingsnokkel(sesjon: str, publikasjoner: list[dict]) -> dict | None:
    """Leter etter en publikasjons-ID eller -tittel i saksobjektene.

    Returnerer {"nivaa": "sak"|"saker", "sti": "...", "form": ...} eller None.
    `nivaa` sier om referansen fantes i lista fra `saker` (billig) eller først i
    detaljene fra `sak` (ett kall per sak). `form` sier om feltet ER ID-en eller
    tittelen, eller bare INNEHOLDER den — «Innst. 101 S (2025-2026), jf. Prop. 1
    S» er den formen kilden faktisk bruker i henvisningsfelt, og en kobling som
    bare godtok eksakt likhet ville gått glipp av hele trakten.
    """
    kjente_ider = {str(p["id"]) for p in publikasjoner if p.get("id")}
    kjente_titler = {normaliser(str(p.get("tittel") or "")): str(p["id"])
                     for p in publikasjoner if p.get("tittel") and p.get("id")}
    kjente_titler.pop("", None)
    print(f"  leter etter {len(kjente_ider)} ID-er og {len(kjente_titler)} "
          f"titler fra sesjon {sesjon}", flush=True)

    saker = forste_liste(hent_json("saker", sesjonid=sesjon, format="json"))
    print(f"  {len(saker)} saker i sesjonen", flush=True)
    if not saker:
        return None
    print(f"  nøkler i et saksobjekt: {sorted(saker[0])}", flush=True)

    def let(objekter: list[dict], nivaa: str) -> dict | None:
        # Eksakt likhet prøves først og alene: treffer den, er den tryggere enn
        # en delstreng, og delstrengsøket koster titusener av substring-kall.
        for former in (("id", "tittel"), ("id_delstreng", "tittel_delstreng")):
            traff: collections.Counter = collections.Counter()
            for sak in objekter:
                for sti, verdi in _stier(sak):
                    for form in former:
                        kjente = kjente_ider if form.startswith("id") else kjente_titler
                        if nokler_i(verdi, form, kjente):
                            traff[(sti, form)] += 1
            if traff:
                break
        if not traff:
            return None
        (sti, form), antall = traff.most_common(1)[0]
        print(f"  ✓ fant referansen på «{sti}» ({form}) i {antall} av "
              f"{len(objekter)} saker, nivå «{nivaa}»", flush=True)
        for (s, f), n in traff.most_common(5)[1:]:
            print(f"    (også: {s} som {f}, {n} treff)", flush=True)
        return {"nivaa": nivaa, "sti": sti, "form": form, "sesjon": sesjon}

    funn = let(saker, "saker")
    if funn:
        return funn

    print(f"  ingenting i sakslista — henter detaljene for de "
          f"{min(SONDER_SAKER, len(saker))} første sakene", flush=True)
    detaljer = []
    for i, sak in enumerate(saker[:SONDER_SAKER], 1):
        if not sak.get("id"):
            continue
        time.sleep(PAUSE)
        try:
            detaljer.append(hent_json("sak", sakid=sak["id"], format="json"))
        except (nett.NettFeil, nett.HttpFeil) as e:
            print(f"    ✗ sak {sak['id']}: {e}", flush=True)
        if i % 25 == 0:
            print(f"    {i} saker …", flush=True)
    if detaljer:
        print(f"  nøkler i et saksdetaljobjekt: {sorted(detaljer[0])}", flush=True)
    return let(detaljer, "sak")


# ---------------------------------------------------------------- henting

def les_treff() -> dict:
    if not TREFFIL.exists():
        raise SystemExit(
            f"FEIL: fant ikke {TREFFIL}.\n"
            "Kjør først: python pipeline/koble_evalueringer_stortinget.py"
        )
    return json.loads(TREFFIL.read_text(encoding="utf-8"))


def treffdokumenter(data: dict) -> list[dict]:
    """De distinkte publikasjonene som navngir minst én evaluering."""
    sett: dict[str, dict] = {}
    for dokumenter in (data.get("treff") or {}).values():
        for d in dokumenter:
            if d.get("id"):
                sett.setdefault(str(d["id"]), d)
    return list(sett.values())


def _hent_sti(objekt, sti: str) -> list[str]:
    """Plukker verdiene på en sti som `_stier` fant. Tåler lister underveis."""
    biter = sti.split(".")
    nivå = [objekt]
    for bit in biter:
        liste = bit.endswith("[]")
        navn = bit[:-2] if liste else bit
        neste = []
        for o in nivå:
            if not isinstance(o, dict):
                continue
            v = o.get(navn)
            if liste and isinstance(v, list):
                neste.extend(v)
            elif not liste and v is not None:
                neste.append(v)
        nivå = neste
    return [v for v in nivå if isinstance(v, str)]


def bygg_sakskart(nokkel: dict, sesjoner: list[str],
                  kjente: set[str]) -> dict[str, dict]:
    """publikasjons-ID (eller normalisert tittel) → saksobjekt."""
    kart: dict[str, dict] = {}
    for sesjon in sesjoner:
        time.sleep(PAUSE)
        try:
            saker = forste_liste(hent_json("saker", sesjonid=sesjon, format="json"))
        except (nett.NettFeil, nett.HttpFeil) as e:
            # En sesjon vi ikke får saksregisteret for er et hull i trinn tre
            # og fire, ikke i trinn to. Vi teller den som udekket framfor å
            # la dens dokumenter framstå som «ikke behandlet».
            print(f"  ✗ sesjon {sesjon}: {e} — trinn 3–4 dekker den ikke",
                  flush=True)
            continue
        print(f"  {sesjon}: {len(saker)} saker", flush=True)
        objekter = saker
        if nokkel["nivaa"] == "sak":
            objekter = []
            for i, sak in enumerate(saker, 1):
                if not sak.get("id"):
                    continue
                time.sleep(PAUSE)
                try:
                    objekter.append(hent_json("sak", sakid=sak["id"], format="json"))
                except (nett.NettFeil, nett.HttpFeil):
                    continue
                if i % 100 == 0:
                    print(f"    {i}/{len(saker)} saksdetaljer …", flush=True)
        for sak in objekter:
            for verdi in _hent_sti(sak, nokkel["sti"]):
                for n in nokler_i(verdi, nokkel["form"], kjente):
                    kart[n] = sak
    return kart


def hent_voteringer(sakid) -> list[dict]:
    try:
        return forste_liste(hent_json("voteringer", sakid=sakid, format="json"))
    except (nett.NettFeil, nett.HttpFeil) as e:
        print(f"    ✗ voteringer for sak {sakid}: {e}", flush=True)
        return []


def er_vedtatt(voteringer: list[dict]) -> bool:
    """Sant hvis minst én votering på saken gikk gjennom.

    Feltet leses defensivt: API-et har levert `vedtatt` både som bool og som
    strengen «true», og en streng er sann i Python uansett innhold — «false»
    ville da telt som et vedtak.
    """
    for v in voteringer:
        verdi = v.get("vedtatt")
        if verdi is True or (isinstance(verdi, str) and verdi.strip().lower() == "true"):
            return True
    return False


# ---------------------------------------------------------------- rapport

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sonder", action="store_true",
                    help="finn koblingsnøkkelen og skriv den ut (ingen henting)")
    ap.add_argument("--frisk", action="store_true",
                    help="ignorer lagret koblingsnøkkel")
    args = ap.parse_args()

    print(f"{KILDE} — {KILDE_URL}")
    data = les_treff()
    dokumenter = treffdokumenter(data)
    if not dokumenter:
        raise SystemExit(
            "FEIL: ingen treff i navngitte_evalueringer.json.\n"
            "  Uten treff er det ingenting å følge til vedtak. Sjekk at\n"
            "  fulltekstene er hentet og at koblingen fant noe."
        )
    sesjoner = sorted({str(d.get("sesjon")) for d in dokumenter if d.get("sesjon")})
    print(f"{len(dokumenter)} dokumenter navngir minst én evaluering, "
          f"fordelt på {len(sesjoner)} sesjoner")

    saksbundne = [d for d in dokumenter if d.get("type") in SAKSBUNDNE_TYPER]
    løse = len(dokumenter) - len(saksbundne)
    print(f"  {len(saksbundne)} er saksbundne ({', '.join(SAKSBUNDNE_TYPER)})")
    print(f"  {løse} er referater eller innberetninger — de dekker mange saker "
          f"og blir stående på trinn to")

    nokkel = None
    if NOKKELFIL.exists() and not args.frisk:
        nokkel = json.loads(NOKKELFIL.read_text(encoding="utf-8"))
        print(f"  bruker lagret koblingsnøkkel: {nokkel['sti']} "
              f"({nokkel['form']}, nivå {nokkel['nivaa']})")
    else:
        print("\nSonderer koblingen publikasjon → sak …")
        nyeste = sesjoner[-1]
        i_sesjonen = [d for d in saksbundne if str(d.get("sesjon")) == nyeste]
        nokkel = finn_koblingsnokkel(nyeste, i_sesjonen or saksbundne)
        if not nokkel:
            raise SystemExit(
                "FEIL: fant ingen referanse til publikasjonene i saksobjektene.\n"
                "  Verken sakslista eller saksdetaljene inneholder ID-ene eller\n"
                "  titlene til dokumentene som ga treff. Da kan trinn tre og\n"
                "  fire ikke bygges på denne koblingen, og trakten skal stå med\n"
                "  to trinn framfor å fylles med et tall vi ikke kan forsvare.\n"
                "  Lim utskriften over inn i samtalen — nøklene den lister er\n"
                "  det som finnes å koble på."
            )
        STORTINGET_DIR.mkdir(parents=True, exist_ok=True)
        NOKKELFIL.write_text(json.dumps(nokkel, ensure_ascii=False, indent=1),
                             encoding="utf-8")
        print(f"  Skrev {NOKKELFIL}")

    if args.sonder:
        print("\nSonderingen er ferdig. Kjør uten --sonder for å hente vedtakene.")
        return 0

    # Kartet bygges bare for de dokumentene som faktisk ga treff. Det gjør
    # delstrengsøket billig, og det hindrer at en sak knyttes til et dokument
    # vi ikke leter etter.
    if nokkel["form"].startswith("id"):
        kjente = {str(d["id"]) for d in saksbundne if d.get("id")}
    else:
        kjente = {normaliser(str(d.get("tittel") or "")) for d in saksbundne}
        kjente.discard("")

    print(f"\nBygger sakskart for {len(sesjoner)} sesjoner …")
    kart = bygg_sakskart(nokkel, sesjoner, kjente)
    print(f"  {len(kart)} publikasjonsreferanser i kartet")

    # Fra dokument til sak til votering. Sakene slås opp én gang hver, ikke én
    # gang per dokument — flere innstillinger kan høre til samme sak.
    dok_til_sak: dict[str, dict] = {}
    for d in saksbundne:
        nøkkel = (str(d["id"]) if nokkel["form"].startswith("id")
                  else normaliser(str(d.get("tittel") or "")))
        sak = kart.get(nøkkel)
        if sak:
            dok_til_sak[str(d["id"])] = sak

    print(f"  {len(dok_til_sak)} av {len(saksbundne)} saksbundne dokumenter "
          f"lot seg knytte til en sak")

    sakider = sorted({str(s.get("id")) for s in dok_til_sak.values() if s.get("id")})
    print(f"\nHenter voteringer for {len(sakider)} saker …")
    vedtatt_sak: dict[str, bool] = {}
    for i, sakid in enumerate(sakider, 1):
        time.sleep(PAUSE)
        vedtatt_sak[sakid] = er_vedtatt(hent_voteringer(sakid))
        if i % 25 == 0 or i == len(sakider):
            print(f"  {i}/{len(sakider)}", flush=True)

    # Trakten telles på evalueringer, ikke på dokumenter: spørsmålet er hvor
    # mange evalueringer som fikk konsekvenser, ikke hvor mange dokumenter som
    # nevnte dem.
    behandlet: set[str] = set()
    vedtatt: set[str] = set()
    for uuid, dokliste in (data.get("treff") or {}).items():
        for d in dokliste:
            sak = dok_til_sak.get(str(d.get("id")))
            if not sak:
                continue
            behandlet.add(uuid)
            if vedtatt_sak.get(str(sak.get("id"))):
                vedtatt.add(uuid)

    navngitt = data.get("navngitt")
    nevner = data.get("nevner")
    print("\nTrakten:")
    print(f"  publisert i dekningsvinduet   {nevner}")
    print(f"  navngitt i et dokument        {navngitt}")
    print(f"  knyttet til en sak            {len(behandlet)}")
    print(f"  saken fikk et vedtak          {len(vedtatt)}")
    if not (isinstance(navngitt, int) and len(behandlet) <= navngitt
            and len(vedtatt) <= len(behandlet)):
        raise SystemExit(
            "FEIL: trakten er ikke monotont synkende. Et trinn kan ikke være\n"
            "  bredere enn trinnet over — sjekk koblingen før dette publiseres."
        )

    STORTINGET_DIR.mkdir(parents=True, exist_ok=True)
    UTFIL.write_text(json.dumps({
        "dato": date.today().isoformat(),
        "koblingsnokkel": nokkel,
        "forbehold": ("Trinn 3 og 4 gjelder bare saksbundne dokumenttyper "
                      f"({', '.join(SAKSBUNDNE_TYPER)}). Et referat dekker mange "
                      "saker, så en evaluering nevnt der kan ikke knyttes til ett "
                      "vedtak, og blir stående på trinn 2. «Vedtatt» betyr at "
                      "saken fikk et vedtak — ikke at vedtaket fulgte "
                      "evalueringens anbefaling."),
        "dokumenter_med_treff": len(dokumenter),
        "saksbundne": len(saksbundne),
        "uten_sakstilknytning": løse,
        "dokumenter_koblet": len(dok_til_sak),
        "saker": len(sakider),
        "trakt": {"publisert": nevner, "navngitt": navngitt,
                  "behandlet": len(behandlet), "vedtatt": len(vedtatt)},
        "behandlet_uuid": sorted(behandlet),
        "vedtatt_uuid": sorted(vedtatt),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nSkrev {UTFIL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
