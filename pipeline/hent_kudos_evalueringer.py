"""Henter hele evalueringskorpuset fra Kudos (DFØ) til rådata utenfor repoet.

Kjøring (krever nett mot kudos.dfo.no):

    python pipeline/hent_kudos_evalueringer.py
    python pipeline/hent_kudos_evalueringer.py --kartlegg   # bare feltkartlegging, 1 side
    python pipeline/hent_kudos_evalueringer.py --frisk      # ignorer lagrede sider

Kudos er DFØs base over kunnskapsdokumenter i offentlig sektor — evalueringer,
utredninger, årsrapporter, tildelingsbrev. Vi henter én type: `Evaluering`.
API-et er Laravel-paginert (`meta.current_page` / `last_page` / `total`) og har
ingen fritekstsøk i v0, bare strukturerte filtre. Se api-atlas/eksempler/hent_kudos.py
for filterlista — den kom fra API-ets egen 422-feilmelding.

Rådata skrives UTENFOR repoet (jf. SIKKERHET.md / .gitignore): sett KUDOS_DIR,
ellers brukes ../impromptu_raadata/kudos/ ved siden av repoet. Alt i dette repoet
serveres statisk av Vercel, så en innsjekket kopi av basen blir offentlig nedlastbar.

Korpuset er 143 sider som må hentes sekvensielt, og kilden er merkbart tregere
under vedvarende paginering enn ved enkeltkall. Derfor lagres hver side til disk
etter hvert: blir kjøringen avbrutt — tidsgrense i Actions, et lukket lokk —
fortsetter neste kjøring der den slapp i stedet for å betale for alt på nytt.

Tre ting scriptet gjør med vilje:

- **Det teller mot API-ets egen fasit.** `meta.total` sier hvor mange dokumenter som
  finnes. Får vi færre rader enn det, stopper vi. En halv base er verre enn ingen
  base, fordi den ser komplett ut — og alle andeler regnet på den blir feil.
- **Det skriver ut en feltkartlegging framfor å anta.** Hvilke felt Kudos faktisk
  leverer per dokument avgjør hvordan resten av pipelinen kan bygges: har basen et
  eget temafelt, trengs ingen LLM-klassifisering; ligger oppdragsgiveren som en
  aktørliste med roller, må rollen velges eksplisitt; og dekningen på
  organisasjonsnummer avgjør om koblingen mot statsregnskapet i det hele tatt bærer.
  Kartleggingen er utskrift, ikke gjetning — den skal leses av et menneske.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import nett
import kontrakt  # noqa: F401  -- setter utf-8 på stdout/stderr (Windows-konsollen er cp1252)

API = "https://kudos.dfo.no/api/v0/documents"
KILDE = "Kudos (DFØ)"
KILDE_URL = "https://kudos.dfo.no/apne-data"
BRUKERAGENT = "Impromptu-Analytics/1.0 (kontakt@impromptu.no)"
DOKUMENTTYPE = "Evaluering"

PER_SIDE = 50           # API-ets tak, oppgitt av dets egen 422: «The per page may not
                        # be greater than 50.» Gir ~143 sider på evalueringskorpuset.
# Kudos slutter å svare etter en håndfull raske kall: en kjøring fikk sidene 1-4
# på sekunder, og så timet side 5 ut fire ganger på 30 sekunder hver. Det er ikke
# 429 — tjeneren tar imot forbindelsen og sender ingenting. Vi går derfor
# betydelig saktere fra start, og bremser ytterligere når det først skjer.
PAUSE = 2.0             # utgangspunkt; 143 sider ≈ 5 minutter i ren venting
PAUSE_TAK = 15.0        # aldri saktere enn dette
PAUSE_FAKTOR = 1.6      # ganges på ved hver feil
GJENVINN_ETTER = 15     # etter så mange sider på rad uten feil, øk farten litt

# Uten en eksplisitt sortering gir Laravel radene i den rekkefølgen databasen
# tilfeldigvis har dem. Over en kjøring på halvannen time forskyver den seg, og
# da havner samme dokument på to sider mens et annet aldri blir servert: en
# kjøring ga 6775 unike av 7138, altså 363 duplikater. Vi ber derfor om en
# stabil sortering. Hvilke felt som godtas står ikke i dokumentasjonen, så
# kandidatene prøves og API-ets eget svar avgjør.
SORTERINGSKANDIDATER = ("uuid", "id", "published_date", "publish_date",
                        "title", "created_at")

# Årsskivene starter her. Tomme år koster ett kall hver, så det er billig å
# begynne tidlig — og et dokument fra 1994 som faller utenfor ville vært et
# stille hull i basen.
FORSTE_AAR = 1990

# Feil som betyr «prøv igjen», ikke «gi opp». http.client.HTTPException er den
# viktige: en avkuttet chunked respons kommer som IncompleteRead, som arver fra
# HTTPException og ValueError — ikke fra URLError. Den gikk derfor rett forbi
# retry-løkka og drepte en kjøring på side 10 av 143.
# OSError dekker ConnectionReset og TimeoutError, som begge er OSError-subklasser.

# Rimelighetsgrenser. Atlaset målte ~7 000 evalueringer i juli 2026 og smoke-testen
# der krever minst 1 000. Vi er strengere: faller totalen under 5 000 eller stiger
# over 15 000, har enten API-et endret betydning av `type`, eller vi spør feil.
MIN_RIMELIG = 5_000
MAKS_RIMELIG = 15_000

RAADATA_DIR = Path(
    os.environ.get("KUDOS_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "kudos"
)
UTFIL = RAADATA_DIR / "evalueringer.json"


# ---------------------------------------------------------------- henting

class PerSideTak(Exception):
    """API-et avviste sidestørrelsen og oppga sitt eget tak i feilkroppen."""

    def __init__(self, tak: int):
        super().__init__(f"per_page-tak: {tak}")
        self.tak = tak


def les_per_side_tak(kropp: str) -> int | None:
    """Plukker per_page-taket ut av en 422-kropp, hvis den oppgir et.

    Kudos svarer f.eks.
        {"error": {"details": {"per_page": ["The per page may not be greater than 50."]}}}
    Vi leser tallet ut av meldingen framfor å hardkode det: taket er API-ets å
    bestemme, og det kan endres uten at vi får beskjed.
    """
    try:
        detaljer = (json.loads(kropp).get("error") or {}).get("details") or {}
    except (json.JSONDecodeError, AttributeError):
        return None
    for melding in detaljer.get("per_page") or []:
        funn = re.search(r"(\d+)", str(melding))
        if funn:
            return int(funn.group(1))
    return None


def hent_json(url: str, timeout: int = 30) -> dict:
    """Kudos-laget over nett.hent_json.

    Retry-reglene ligger i nett.py, delt med de andre hentescriptene. Det ene
    Kudos legger på: en 422 om per_page er ikke en feil, men en beskjed om
    sidestørrelsen — den oversettes til PerSideTak, som hent_side forhandler på.
    """
    try:
        return nett.hent_json(url, BRUKERAGENT, timeout)
    except nett.HttpFeil as e:
        tak = les_per_side_tak(e.kropp)
        if tak is not None:
            raise PerSideTak(tak) from e
        raise SystemExit(
            f"FEIL: Kudos svarte HTTP {e.kode} på\n  {url}\n{e.kropp}\n"
            "Har filternavnene endret seg? API-ets 422 lister de gyldige."
        ) from e


def finn_sortering() -> str | None:
    """Første sorteringsfelt API-et godtar, eller None hvis ingen gjør det.

    Prøves én gang ved oppstart. Koster noen få kall og sparer oss for en
    kjøring der pagineringen har flyttet på seg underveis.
    """
    forste_avvisning = None
    for kandidat in SORTERINGSKANDIDATER:
        params = {"page": 1, "per_page": 1, "type": DOKUMENTTYPE, "sort": kandidat}
        url = f"{API}?{urllib.parse.urlencode(params)}"
        try:
            nett.hent_json(url, BRUKERAGENT)
        except nett.HttpFeil as e:
            # Kroppen er fasiten, ikke støy. Kudos' 422 oppga per_page-taket, og
            # Stortingets 400 navnga parameteren som manglet — en avvisning som
            # bare noteres som «avvist» kaster nettopp den opplysningen vi
            # trenger for å finne den gyldige verdien.
            print(f"  · sort={kandidat}: HTTP {e.kode}", flush=True)
            if forste_avvisning is None:
                forste_avvisning = e.kropp
            continue
        except nett.NettFeil:
            print(f"  · sort={kandidat} svarte ikke — hopper over", flush=True)
            continue
        print(f"  ✓ sorterer på «{kandidat}» — stabil paginering", flush=True)
        return kandidat

    print("  ⚠ ingen av kandidatene ble godtatt.", flush=True)
    if forste_avvisning:
        print("    API-ets egen feilkropp — her står som regel de gyldige "
              "verdiene:", flush=True)
        print(f"    {forste_avvisning[:600]}", flush=True)
    print("    Uten stabil sortering kan pagineringen forskyve seg underveis.", flush=True)
    print("    Kjøringen fortsetter, og henter et sveip til for å tette hull.", flush=True)
    return None


def hent_side(side: int, **filtre) -> dict:
    """Én side. Retter seg etter API-ets per_page-tak hvis det avviser vårt.

    Sidestørrelsen påvirker bare pagineringen, ikke ett eneste tall vi henter ut,
    så her er det riktig å bøye seg framfor å stoppe. Men justeringen skrives ut:
    en stille tilpasning ville skjult at kilden har endret seg, og da ville neste
    person lurt på hvorfor kjøringen plutselig tar dobbelt så mange kall.
    """
    global PER_SIDE
    for _ in range(2):
        params = {"page": side, "per_page": PER_SIDE, **filtre}
        try:
            return hent_json(f"{API}?{urllib.parse.urlencode(params)}")
        except PerSideTak as e:
            if e.tak >= PER_SIDE or e.tak < 1:
                raise SystemExit(
                    f"FEIL: Kudos avviste per_page={PER_SIDE} og oppga taket "
                    f"{e.tak}, som ikke er lavere. Da har vi misforstått "
                    f"feilmeldingen — sjekk {KILDE_URL}."
                ) from e
            print(f"  ⚠ Kudos oppgir et per_page-tak på {e.tak} (vi ba om "
                  f"{PER_SIDE}). Justerer ned og fortsetter.")
            PER_SIDE = e.tak
    raise SystemExit("FEIL: Kudos avviste sidestørrelsen to ganger på rad.")


# Sjekkpunktene legges under sorteringen de ble hentet med. En side hentet uten
# stabil sortering er ikke den samme siden som en hentet med — den kan inneholde
# dokumenter som nå ligger på en annen side, og gjenbruk ville arvet nøyaktig det
# duplikatproblemet sorteringen er der for å fjerne. Skifter sorteringen, finnes
# de gamle sidene rett og slett ikke, og hentingen starter friskt av seg selv.
_merkelapp: str = "alt"


def sider_dir() -> Path:
    return RAADATA_DIR / f"sider_{_merkelapp}"


def _sidefil(side: int) -> Path:
    return sider_dir() / f"side_{side:04d}.json"


def les_lagret_side(side: int) -> list[dict] | None:
    """Én ferdighentet side fra disk, eller None hvis den mangler eller er ødelagt."""
    fil = _sidefil(side)
    if not fil.exists():
        return None
    try:
        data = json.loads(fil.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None  # halvskrevet eller uleselig: hentes på nytt
    return data if isinstance(data, list) else None


def skriv_side(side: int, data: list[dict]) -> None:
    """Lagrer én side atomisk: skriv til .tmp, så gi nytt navn.

    Uten rename-trikset kan en kjøring som blir drept midt i en skriving legge
    igjen en halv fil som ser gyldig ut på neste kjøring.
    """
    sider_dir().mkdir(parents=True, exist_ok=True)
    tmp = _sidefil(side).with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_sidefil(side))


def _sveip(filtre: dict, merkelapp: str, bruk_sjekkpunkt: bool,
           ved_side=None) -> tuple[list[dict], dict]:
    """Ett gjennomløp av pagineringen for én skive av korpuset.

    `filtre` går rett inn i spørringen — tomt for hele korpuset, eller
    published_year_from/to for ett år. `merkelapp` navngir sjekkpunktmappa, så
    to skiver aldri leser hverandres sider.

    `ved_side` kalles med hver ferdige side og kan returnere True for å stoppe.
    Det er der restsveipet henter sin verdi: leter vi etter 411 dokumenter som
    mangler årstall, er det ingen grunn til å hente de 6727 vi allerede har
    når de siste er funnet.

    Hver side lagres til disk etter hvert. En avbrutt kjøring — tidsgrense i
    Actions, et lukket lokk på Windows — fortsetter da der den slapp i stedet
    for å betale for de samme 143 kallene på nytt.

    Duplikater telles og rapporteres, men stopper ikke sveipet: et sveip med
    duplikater bidrar fortsatt med dokumenter, og kalleren slår sveipene sammen.
    """
    global _merkelapp
    _merkelapp = merkelapp
    ekstra = dict(filtre)
    forste = hent_side(1, type=DOKUMENTTYPE, **ekstra)
    meta = forste.get("meta") or {}
    total = meta.get("total")
    sider = meta.get("last_page")
    if not isinstance(total, int) or not isinstance(sider, int):
        raise SystemExit(
            "FEIL: svaret mangler meta.total / meta.last_page. Kudos v0 var "
            f"Laravel-paginert — har formatet endret seg?\n{json.dumps(meta)[:400]}"
        )
    # Rimelighetssjekken på korpusstørrelsen hører hjemme i hent_alle, ikke her:
    # en årsskive kan godt være tom, og skal da bare returnere ingenting.
    if total == 0:
        return [], meta

    print(f"  {merkelapp}: {total} dokumenter på {sider} sider", flush=True)

    # Sidene samles i en dict framfor å appendes underveis. Da blir resultatet
    # det samme enten en side ble hentet nå, gjenbrukt fra sjekkpunkt, eller
    # hentet i den andre runden — og rekkefølgen er alltid sidenes egen.
    sider_data: dict[int, list[dict]] = {1: list(forste.get("data") or [])}
    if bruk_sjekkpunkt:
        skriv_side(1, sider_data[1])
    # Side 1 hentes før løkka, så den må mates til ved_side her — ellers hopper
    # restsveipet over de første femti dokumentene og kommer nøyaktig én side
    # for kort.
    if ved_side and ved_side(sider_data[1]):
        print("  alt vi lette etter lå på første side", flush=True)
        return sider_data[1], meta
    gjenbrukt = 0
    feilede: list[int] = []
    start = time.monotonic()
    pause = PAUSE
    uten_feil = 0
    # Anslaget bør si hvor fort det går NÅ, ikke i snitt siden start. Et
    # kumulativt snitt henger etter: bruker kilden 40 sekunder de første femti
    # sidene og 10 de neste, står anslaget og lyver lenge om at det er langt
    # igjen. Vi holder derfor de siste ti sidetidene og regner på dem.
    siste_tider: collections.deque[float] = collections.deque(maxlen=10)
    # Duplikater telles og vises underveis, men avbryter ikke sveipet. Med
    # stabil sortering skal tallet være null; er det ikke det, forteller det oss
    # at rekkefølgen forskyver seg — og da er svaret å hente et sveip til og
    # slå dem sammen, ikke å kaste det vi allerede har betalt for.
    sett_uuid: set[str] = {d.get("uuid") for d in sider_data[1] if d.get("uuid")}
    dubletter = 0

    for side in range(2, sider + 1):
        lagret = les_lagret_side(side) if bruk_sjekkpunkt else None
        if lagret is not None:
            sider_data[side] = lagret
            gjenbrukt += 1
            if ved_side and ved_side(lagret):
                print(f"  alt vi lette etter er funnet — stopper på side {side}",
                      flush=True)
                break
            continue
        time.sleep(pause)
        side_start = time.monotonic()
        try:
            rader = hent_side(side, type=DOKUMENTTYPE, **ekstra).get("data") or []
        except nett.NettFeil as e:
            # Én gjenstridig side skal ikke koste alt det andre. Vi noterer den
            # og tar den i en ny runde til slutt, når kilden har fått puste.
            print(f"  ⚠ side {side} ga opp ({e}) — tas i ny runde til slutt",
                  flush=True)
            feilede.append(side)
            pause = min(pause * PAUSE_FAKTOR, PAUSE_TAK)
            uten_feil = 0
            print(f"    bremser til {pause:.1f} s mellom sidene", flush=True)
            continue
        siste_tider.append(time.monotonic() - side_start)
        for d in rader:
            u = d.get("uuid")
            if u in sett_uuid:
                dubletter += 1
            elif u:
                sett_uuid.add(u)
        sider_data[side] = rader
        if bruk_sjekkpunkt:
            skriv_side(side, rader)
        uten_feil += 1
        if ved_side and ved_side(rader):
            print(f"  alt vi lette etter er funnet — stopper på side {side} "
                  f"av {sider}", flush=True)
            break
        if uten_feil >= GJENVINN_ETTER and pause > PAUSE:
            pause = max(PAUSE, pause / PAUSE_FAKTOR)
            uten_feil = 0
            print(f"    går bra igjen — øker farten til {pause:.1f} s", flush=True)

        if side % 10 == 0 or side == sider:
            # Farten er selve diagnosen når en kjøring går på tidsgrensa. Uten
            # sekundene i utskriften kan vi ikke skille «kilden er treg» fra
            # «vi prøver på nytt hele tiden», og da gjetter vi på neste fiks.
            gått = time.monotonic() - start
            nylig = (sum(siste_tider) / len(siste_tider)) if siste_tider else 0.0
            igjen = (sider - side) * (nylig + pause)
            print(f"  side {side}/{sider} — {gått / 60:.0f} min brukt, "
                  f"{nylig:.0f} s/side siste ti, ~{igjen / 60:.0f} min igjen"
                  + (f", {dubletter} dubletter" if dubletter else ""),
                  flush=True)


    if gjenbrukt:
        print(f"  ({gjenbrukt} sider gjenbrukt fra sjekkpunkt — "
              f"de kostet ingen nye kall)", flush=True)

    # Ny runde på de gjenstridige, i rolig tempo. Kilden henger under press,
    # men kommer seg — den samme siden går ofte gjennom et minutt senere.
    if feilede:
        print(f"\n  Ny runde på {len(feilede)} sider som feilet, "
              f"med {PAUSE_TAK:.0f} s mellom hver", flush=True)
        fortsatt_feil = []
        for side in feilede:
            time.sleep(PAUSE_TAK)
            try:
                rader = hent_side(side, type=DOKUMENTTYPE, **ekstra).get("data") or []
            except nett.NettFeil as e:
                print(f"    ✗ side {side} feilet igjen: {e}", flush=True)
                fortsatt_feil.append(side)
                continue
            sider_data[side] = rader
            if bruk_sjekkpunkt:
                skriv_side(side, rader)
            print(f"    ✓ side {side} kom gjennom denne gangen", flush=True)
        feilede = fortsatt_feil

    if feilede:
        raise SystemExit(
            f"FEIL: {len(feilede)} sider lot seg ikke hente: {feilede}\n"
            "Sidene som gikk gjennom er lagret, så en ny kjøring fortsetter\n"
            "der denne slapp og henter bare det som mangler."
        )

    dokumenter = [d for side in sorted(sider_data) for d in sider_data[side]]

    # Fasitsjekk mot API-ets eget tall. Duplikater over sidegrenser er en kjent
    # paginerings-felle når basen endres under kjøring, så vi teller unike uuid-er.
    mangler_felt = [d for d in dokumenter if not d.get("uuid") or not d.get("title")]
    if mangler_felt:
        raise SystemExit(
            f"FEIL: {len(mangler_felt)} dokumenter mangler uuid eller title. "
            f"Første: {json.dumps(mangler_felt[0], ensure_ascii=False)[:300]}"
        )
    return dokumenter, meta


def hent_alle(bruk_sjekkpunkt: bool = True) -> tuple[list[dict], dict]:
    """Hele korpuset, hentet år for år og satt sammen.

    Hvorfor år for år, og ikke ett langt sveip: Kudos serverer nyeste først og
    godtar ingen sortering (alle seks kandidatene ga 422, og feilkroppen lister
    ikke gyldige verdier). Publiseres et dokument mens vi henter, skyves alt
    nedover — og et dokument på en sidegrense blir servert to ganger mens et
    annet aldri blir servert. Over halvannen time ga det 363 duplikater og like
    mange tapte dokumenter.

    En årsskive er ferdig på sekunder, og et nytt dokument i 2026 rører ikke
    2019. Driften følger tid, ikke sidetall, så korte spørringer fjerner den
    nesten helt. At summen av årene må møte API-ets egen `meta.total` er
    dessuten en strengere kontroll enn før: den fanger både hull i et enkelt år
    og dokumenter som mangler årstall.
    """
    fasit = hent_side(1, type=DOKUMENTTYPE).get("meta") or {}
    total = fasit.get("total")
    if not isinstance(total, int):
        raise SystemExit(f"FEIL: mangler meta.total.\n{json.dumps(fasit)[:300]}")
    if not MIN_RIMELIG <= total <= MAKS_RIMELIG:
        raise SystemExit(
            f"FEIL: Kudos oppgir {total} dokumenter av typen «{DOKUMENTTYPE}». "
            f"Vi ventet mellom {MIN_RIMELIG} og {MAKS_RIMELIG}.\n"
            f"Sjekk {KILDE_URL} før du justerer grensene."
        )
    print(f"\nFasit fra API-et: {total} evalueringer\n", flush=True)

    samlet: dict[str, dict] = {}
    per_aar: dict[str, int] = {}

    def hent_aar(aar: int) -> bool:
        """Én årsskive inn i `samlet`. False hvis kilden ikke svarte."""
        filtre = {"published_year_from": aar, "published_year_to": aar}
        try:
            dokumenter, _ = _sveip(filtre, f"aar_{aar}", bruk_sjekkpunkt)
        except nett.HttpFeil as e:
            raise SystemExit(
                f"FEIL: årsfilteret ble avvist for {aar}: HTTP {e.kode}\n"
                f"{e.kropp[:400]}\n"
                "Har filternavnene endret seg? API-ets 422 lister de gyldige."
            ) from e
        except nett.NettFeil as e:
            # Side 1 i en skive hentes utenfor løkkas retry, så en treg spørring
            # her ville ellers drept hele kjøringen. Ett år som ikke svarer er
            # ikke en grunn til å kaste de seksten andre — vi noterer det og
            # prøver igjen når kilden har fått puste.
            print(f"  ⚠ {aar} svarte ikke ({e}) — tas i ny runde til slutt",
                  flush=True)
            return False
        if not dokumenter:
            return True
        før = len(samlet)
        for d in dokumenter:
            if d.get("uuid"):
                samlet.setdefault(d["uuid"], d)
        per_aar[str(aar)] = len(dokumenter)
        print(f"  {aar}: {len(dokumenter)} dokumenter, {len(samlet) - før} nye "
              f"— {len(samlet)}/{total} totalt", flush=True)
        return True

    feilede_aar = [a for a in range(FORSTE_AAR, date.today().year + 1)
                   if not hent_aar(a)]

    if feilede_aar:
        print(f"\n  Ny runde på {len(feilede_aar)} år som ikke svarte: "
              f"{feilede_aar}", flush=True)
        fortsatt = []
        for aar in feilede_aar:
            time.sleep(PAUSE_TAK)
            if not hent_aar(aar):
                fortsatt.append(aar)
        if fortsatt:
            raise SystemExit(
                f"FEIL: årene {fortsatt} lot seg ikke hente.\n"
                "  Alt annet er lagret, så en ny kjøring henter bare det som\n"
                "  mangler — de ferdige årene koster ingen nye kall."
            )

    # Dokumenter uten publiseringsår fanges ikke av noen årsskive. Er summen
    # kortere enn fasiten, henter vi resten ufiltrert og slår sammen.
    if len(samlet) < total:
        mangler = total - len(samlet)
        print(f"\n  {mangler} dokumenter fanget ikke av årsskivene — de mangler")
        print("  trolig publiseringsår. Henter ufiltrert og slår sammen.", flush=True)
        # Sveipet mater rader inn i `samlet` etter hvert, og stopper i det
        # øyeblikket fasiten er nådd. Uten det ville vi hentet hele korpuset
        # på nytt for å finne en håndfull dokumenter uten årstall.
        def samle(rader: list[dict]) -> bool:
            for d in rader:
                if d.get("uuid"):
                    samlet.setdefault(d["uuid"], d)
            return len(samlet) >= total

        før = len(samlet)
        _sveip({}, "uten_aarsfilter", bruk_sjekkpunkt, ved_side=samle)
        print(f"  restsveipet ga {len(samlet) - før} nye "
              f"— {len(samlet)}/{total}", flush=True)

    if len(samlet) < total:
        raise SystemExit(
            f"FEIL: {len(samlet)} unike dokumenter, men API-et oppgir {total}.\n"
            f"  Per år: {per_aar}\n"
            f"  {total - len(samlet)} dokumenter ble aldri servert. Et snapshot\n"
            f"  som ser komplett ut og ikke er det, gir feil i alle andeler —\n"
            f"  og feilen er usynlig i ettertid. Si fra med denne meldingen."
        )

    print(f"\n✓ {len(samlet)} unike dokumenter, fordelt på "
          f"{len(per_aar)} årganger", flush=True)
    return list(samlet.values()), {**fasit, "per_aar": per_aar}


# ---------------------------------------------------------------- kartlegging

# Nøkler vi *håper* finnes. Ingenting i scriptet krever dem — de brukes bare til å
# gjøre utskriften lesbar, slik at et menneske ser hva som faktisk er der.
TEMA_HINT = ("theme", "topic", "subject", "category", "tag", "emne", "tema")
AKTOR_HINT = ("actor", "org", "publisher", "owner", "virksomhet")
AAR_HINT = ("year", "date", "published", "aar", "dato")


def _flat_verdier(verdi) -> list:
    """Pakker ut lister og objekter én gang, så vi kan telle dekning på nøstede felt."""
    if isinstance(verdi, list):
        return verdi
    return [verdi]


def kartlegg(dokumenter: list[dict]) -> None:
    """Skriver ut hva basen faktisk inneholder. Dette er scriptets viktigste utskrift."""
    n = len(dokumenter)
    nokler = collections.Counter()
    for d in dokumenter:
        nokler.update(d.keys())

    print("\n" + "=" * 72)
    print("FELTKARTLEGGING — lim denne utskriften inn i samtalen")
    print("=" * 72)

    print(f"\nAntall dokumenter: {n}")
    print(f"Nøkler i datasettet ({len(nokler)}), med dekning:")
    for nokkel, antall in sorted(nokler.items(), key=lambda kv: (-kv[1], kv[0])):
        ikke_tom = sum(
            1 for d in dokumenter
            if d.get(nokkel) not in (None, "", [], {})
        )
        print(f"  {nokkel:<28} {ikke_tom:>6}/{n}  ({100 * ikke_tom / n:.1f} %)")

    print("\nFørste dokument, i sin helhet:")
    print(json.dumps(dokumenter[0], ensure_ascii=False, indent=2)[:2500])

    def gruppe(overskrift: str, hint: tuple[str, ...]) -> None:
        traff = [k for k in nokler if any(h in k.lower() for h in hint)]
        print(f"\n{overskrift}")
        if not traff:
            print("  (ingen felt med disse ordene i navnet)")
            return
        for k in sorted(traff):
            # Ligger feltet som en liste av objekter (aktørlista gjør det), er
            # «<objekt: name, org_number>» ubrukelig som svar. Vi pakker derfor ut
            # ett nivå og teller hver undernøkkel for seg.
            #
            # Og vi teller to forskjellige ting, fordi de svarer på hvert sitt
            # spørsmål: hvor mange *dokumenter* som har feltet (dekning — det er
            # den som avgjør om en kobling bærer), og hvor mange *forekomster*
            # hver verdi har (fordeling). Et dokument kan ha flere aktører, så de
            # to tallene er ikke like, og det er nettopp forskjellen som er
            # interessant.
            verdier: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
            dekning: dict[str, set[int]] = collections.defaultdict(set)
            for i, d in enumerate(dokumenter):
                for v in _flat_verdier(d.get(k)):
                    if isinstance(v, dict):
                        for undernokkel, underverdi in v.items():
                            if underverdi not in (None, "", [], {}):
                                sti = f"{k}.{undernokkel}"
                                verdier[sti][str(underverdi)[:60]] += 1
                                dekning[sti].add(i)
                    elif v not in (None, ""):
                        verdier[k][str(v)[:60]] += 1
                        dekning[k].add(i)
            for felt, teller in sorted(verdier.items()):
                har = len(dekning[felt])
                print(f"  {felt} — {har}/{n} dokumenter ({100 * har / n:.1f} %), "
                      f"{len(teller)} unike verdier. De 12 vanligste:")
                for verdi, antall in teller.most_common(12):
                    print(f"      {antall:>6}  {verdi}")

    gruppe("TEMA — finnes det et emnefelt? (avgjør om LLM-klassifisering trengs)", TEMA_HINT)
    gruppe("AKTØR — hvor ligger oppdragsgiveren, og hvilken rolle betyr «bestilte denne»?", AKTOR_HINT)
    gruppe("ÅR — finnes publiseringsår på radnivå?", AAR_HINT)

    # Koblingen mot statsregnskapet går på organisasjonsnummer. Om den bærer,
    # er ikke noe man skal måtte slutte seg til fra en liste over unike verdier —
    # så vi regner det ut og sier det rett fram.
    print("\n" + "=" * 72)
    print("KOBLINGSGRUNNLAGET — organisasjonsnummer per dokument")
    for felt in ("owners", "authoring_actors"):
        # Finnes feltet i det hele tatt? Spørres bare dokument 0, forsvinner hele
        # avsnittet den dagen det første dokumentet tilfeldigvis mangler det.
        if not any(d.get(felt) for d in dokumenter):
            print(f"  {felt}: finnes ikke i dette uttrekket")
            continue
        med = [d for d in dokumenter
               if any(isinstance(a, dict) and a.get("org_number")
                      for a in _flat_verdier(d.get(felt)))]
        orgnr = {a.get("org_number") for d in dokumenter
                 for a in _flat_verdier(d.get(felt))
                 if isinstance(a, dict) and a.get("org_number")}
        print(f"  {felt}: {len(med)}/{n} dokumenter ({100 * len(med) / n:.1f} %) "
              f"har minst ett org.nr — {len(orgnr)} unike virksomheter")
        typer = {type(o).__name__ for o in orgnr}
        print(f"    datatype i JSON: {', '.join(sorted(typer))} "
              f"(statsregnskapets Virksomhet_id er tekst — må castes ved kobling)")

    print("\n" + "=" * 72)
    print("Fire spørsmål utskriften over skal svare på:")
    print("  1. Har Kudos et eget temafelt?  (nei → pipeline/kategoriser_evalueringer.py)")
    print("  2. Hvordan ligger oppdragsgiveren, og hvilken rolleverdi gjelder?")
    print("  3. Hvor mange prosent har organisasjonsnummer?  (bærer koblingen mot")
    print("     statsregnskapet — lav dekning krymper akt 3 tilsvarende)")
    print("  4. Finnes publiseringsår per dokument?")
    print("=" * 72)


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kartlegg", action="store_true",
                    help="hent bare første side og kartlegg feltene (ingen skriving)")
    ap.add_argument("--frisk", action="store_true",
                    help="ignorer lagrede sider og hent alt på nytt")
    ap.add_argument("--sorteringer", action="store_true",
                    help="prøv bare sorteringskandidatene og vis API-ets svar "
                         "(sekunder — bruk denne før du starter en lang henting)")
    args = ap.parse_args()

    print(f"{KILDE} — {KILDE_URL}")

    if args.sorteringer:
        print("Prøver sorteringskandidatene …")
        valgt = finn_sortering()
        print(f"\nResultat: {valgt or 'ingen sortering godtatt'}")
        if not valgt:
            print("Les feilkroppen over: står de gyldige verdiene der, legg dem")
            print("inn i SORTERINGSKANDIDATER. Gjør de ikke det, må hentingen")
            print("klare seg med flere sveip som slås sammen.")
        return 0

    if args.kartlegg:
        print(f"Henter én side à {PER_SIDE} for feltkartlegging …")
        svar = hent_side(1, type=DOKUMENTTYPE)
        print(f"  meta: {json.dumps(svar.get('meta') or {}, ensure_ascii=False)}")
        kartlegg(list(svar.get("data") or []))
        return 0

    print(f"Henter alle dokumenter av typen «{DOKUMENTTYPE}» …")
    dokumenter, meta = hent_alle(bruk_sjekkpunkt=not args.frisk)

    RAADATA_DIR.mkdir(parents=True, exist_ok=True)
    UTFIL.write_text(json.dumps({
        "kilde": KILDE,
        "kilde_url": KILDE_URL,
        "dato_hentet": date.today().isoformat(),
        "hentet_tidspunkt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "filter": {"type": DOKUMENTTYPE},
        "api_meta": meta,
        "dokumenter": dokumenter,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n✓ Skrev {len(dokumenter)} dokumenter til {UTFIL}")
    print("  (utenfor repoet — rådata skal ikke sjekkes inn, jf. SIKKERHET.md)")

    kartlegg(dokumenter)

    print("\nNeste steg: lim feltkartleggingen inn i samtalen, så skrives")
    print("bygg_historie_evalueringer.py mot det basen faktisk inneholder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
