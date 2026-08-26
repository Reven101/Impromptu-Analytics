"""Kategoriserer fritekstbeskrivelsene i tilskudd.no-dataene etter FORMÅL.

Bakgrunn: tilskudd.no oppgir `icnpo_kategori`, men den beskriver mottakerorganisasjonens
*sektor* — ikke hva pengene skal brukes til. Fritekstfeltene `tiltak` og
`kort_beskrivelse_av_tiltak` beskriver tiltaket. Dette scriptet leser fritekstene og
plasserer hver av dem i én av kategoriene i KATEGORIER under.

Modellen kalles kun her, ved bygging. Resultatet er et datert, innsjekket snapshot
(pipeline/cache/formaal_cache.json) som resten av pipelinen leser. Nettsiden gjør
aldri et API-kall.

Kjøring:
    python pipeline/kategoriser_formaal.py --fasittest 300   # mål treffsikkerhet mot ICNPO
    python pipeline/kategoriser_formaal.py --grense 500      # liten prøvekjøring
    python pipeline/kategoriser_formaal.py --alle            # hele settet

Datasettet ligger utenfor dette repoet (det er tilskuddskompasset sitt rådata). Sett
TILDELINGER_CSV for å peke et annet sted.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import kontrakt  # noqa: F401  — setter UTF-8 på stdout (se CLAUDE.md)
from llm_klient import (
    RESERVEMODELL,
    STANDARDMODELL,
    TomForKreditt,
    forbruk_oppsummert,
    hent_json_liste,
    kall_modell,
)

# Bumpes når KATEGORIER eller prompten endres. Versjonen inngår i cache-nøkkelen, så en
# endring gjør automatisk gamle svar ugyldige framfor å blande to taksonomier i samme fil.
PROMPTVERSJON = "formaal-v2"
CACHE_FIL = Path(__file__).resolve().parent / "cache" / "formaal_cache.json"
STANDARD_CSV = (
    Path(__file__).resolve().parent.parent.parent
    / "tilskuddskompasset"
    / "tilskudd_data"
    / "tildelinger_samlet_2021_2026.csv"
)

# Formålskategoriene er skrevet for hånd. Modellen VELGER blant dem — den finner dem ikke
# på. Andelen «annet» er et kvalitetsmål: blir den stor, er listen feil, ikke dataene.
KATEGORIER = {
    "arrangement": "Gjennomføre et arrangement: festival, konsert, forestilling, utstilling, cup, stevne, marked, feiring.",
    "drift_og_administrasjon": "Ordinær drift av virksomheten: husleie, lønn, administrasjon, medlemstilbud, løpende aktivitet uten eget prosjekt.",
    "anlegg_og_utstyr": "Fysiske investeringer: bygge, rehabilitere eller utbedre anlegg og lokaler, kjøpe utstyr, instrumenter, kjøretøy eller IT.",
    "produksjon_og_utgivelse": "Lage et verk eller produkt: film, plate, bok, forestilling, spill, utstillingsproduksjon, komposisjon.",
    "opplaering_og_kompetanse": "Kurs, opplæring, instruktør- og trenerutdanning, kompetanseheving, studieturer med læringsformål.",
    "inkludering_og_deltakelse": "Senke terskler og få flere med: integrering, rekruttering av underrepresenterte grupper, lavterskeltilbud, tiltak mot utenforskap.",
    "helse_og_omsorg": "Helse, behandling, rehabilitering, pårørendearbeid, folkehelse, rus- og psykisk helsearbeid.",
    "beredskap_og_redning": "Redningstjeneste, beredskap, søk, førstehjelp, brann- og ulykkesforebygging.",
    "forskning_og_utredning": "Forskning, kartlegging, evaluering, utredning, dokumentasjon av kunnskap.",
    "informasjon_og_formidling": "Formidle til et publikum: kampanje, nettsted, tidsskrift, podkast, informasjonsarbeid, holdningsskapende tiltak.",
    "internasjonalt_samarbeid": "Samarbeid, utveksling eller bistand over landegrensene.",
    "bevaring_og_vedlikehold": "Ta vare på noe eksisterende: kulturminne, samling, arkiv, fartøy, restaurering, naturforvaltning, artsvern.",
    "annet": "Beskrivelsen er tydelig, men formålet passer ingen av kategoriene over.",
    "uklar_beskrivelse": "Teksten er bare en tittel, et navn eller en forkortelse, og sier ikke hva pengene skal brukes til — for eksempel «Bofellesskap», «Peak Performance 2» eller et verksnavn.",
}

SYSTEMPROMPT = (
    "Du klassifiserer norske tilskuddsbeskrivelser etter hva pengene skal brukes til. "
    "Du svarer kun med JSON."
)

# Formelstyrte ordninger: beløpet følger av en regel (omsetning, medlemstall, spillerandel,
# stemmetall), ikke av en søknad om et bestemt tiltak. De har ingen prosjektbeskrivelse å
# kategorisere — 83,6 % av radene og 42,8 % av kronene i datasettet er slike. Å sende dem
# til modellen er både bortkastede penger og en feilkilde: «GRASROTANDELEN» ville blitt
# tvunget inn i en formålskategori den ikke hører hjemme i.
#
# Matches på nøkkelord fordi ordningsnavnene veksler mellom bokmål og nynorsk.
FORMELSTYRTE_ORDNINGER = re.compile(
    r"momskompensasjon|merverdiavgiftskompensasjon|grasrotandel|"
    r"tr[ou]s- og livssynssamfunn|politiske partier|politiske parti|"
    r"samfunnsnyttige og humanit|samfunnsnyttige og humanit",
    re.I,
)

# Tekster uten innhold: kvartalsetiketter og enkeltord som «Driftsmidler». De sier hvilken
# periode eller post pengene hører til, ikke hva de skal brukes til.
INNHOLDSLOSE_TEKSTER = re.compile(
    r"^(grasrotandelen|driftsmidler|driftstilskudd|tilskudd|tilskot)\b[\s\d]*$|"
    r"^(januar|februar|mars|april|mai|juni|juli|august|september|oktober|november|desember)"
    r"[\s,–—-]",
    re.I,
)


def er_formelstyrt(rad: dict, tekst: str) -> bool:
    if FORMELSTYRTE_ORDNINGER.search(rad.get("tilskuddsordning") or ""):
        return True
    return bool(INNHOLDSLOSE_TEKSTER.match(tekst))

class BuntFeil(Exception):
    """Svaret hadde feil form — feil antall elementer eller en ukjent kategori.

    Egen type fordi den håndteres ved å dele bunten opp og prøve igjen. Feil fra
    llm_klient (tom kreditt, avkuttet svar, nettverk) er SystemExit og skal IKKE fanges
    her: å dele opp hjelper ikke mot dem, det bare ganger opp antallet mislykkede kall.
    """


_las = threading.Lock()


# ---------------------------------------------------------------- innlesing


def csv_sti() -> Path:
    sti = Path(os.environ.get("TILDELINGER_CSV", STANDARD_CSV))
    if not sti.exists():
        raise SystemExit(
            f"Fant ikke tildelingsfila: {sti}\n"
            "  Sett TILDELINGER_CSV hvis rådataene ligger et annet sted."
        )
    return sti


def normaliser(tekst: str) -> str:
    return re.sub(r"\s+", " ", tekst).strip()


def fritekst(rad: dict) -> str:
    biter = [rad.get("tiltak") or "", rad.get("kort_beskrivelse_av_tiltak") or ""]
    return normaliser(" — ".join(b.strip() for b in biter if b.strip()))


def les_rader():
    # utf-8-sig, ikke utf-8: fila har BOM, og uten dette heter første kolonne
    # "﻿tilskuddsforvalter". Den leses da som tom uten at noe feiler.
    with csv_sti().open(encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f, delimiter=";")


def belop(rad: dict) -> float:
    try:
        return float(rad.get("tildelt_belop") or 0)
    except ValueError:
        return 0.0


def samle_unike_tekster() -> tuple[dict[str, dict], dict[str, float]]:
    """Unik fritekst → antall rader og samlet beløp, pluss totaler for hele datasettet.

    Vi kategoriserer unike tekster, ikke rader: 695 000 rader inneholder under 60 000
    forskjellige beskrivelser, så det er drøyt ti ganger billigere. Formelstyrte
    tildelinger holdes utenfor, men telles — andelen deres er selve poenget i historien.
    """
    unike: dict[str, dict] = {}
    sum_: dict[str, float] = dict.fromkeys(
        ("rader", "belop", "formel_rader", "formel_belop"), 0.0
    )

    for rad in les_rader():
        tekst = fritekst(rad)
        kr = belop(rad)
        sum_["rader"] += 1
        sum_["belop"] += kr

        if len(tekst) < 12 or er_formelstyrt(rad, tekst):
            sum_["formel_rader"] += 1
            sum_["formel_belop"] += kr
            continue

        post = unike.setdefault(tekst, {"antall": 0, "belop": 0.0})
        post["antall"] += 1
        post["belop"] += kr

    return unike, sum_


# ---------------------------------------------------------------- cache


def nokkel(tekst: str) -> str:
    """Cache-nøkkel. Modellnavnet inngår bevisst IKKE.

    Det gjorde det før, men da ble halve cachen usynlig for oppslag så snart en kjøring
    byttet modell underveis. Modellen ligger nå på hver enkelt oppføring i stedet, slik at
    et blandet grunnlag kan oppdages og opplyses om framfor å forsvinne.
    """
    return hashlib.sha256(f"{PROMPTVERSJON}|{tekst.lower()}".encode("utf-8")).hexdigest()[:16]


def les_cache() -> dict:
    if not CACHE_FIL.exists():
        return {"metode": {}, "kategorier": {}}
    cache = json.loads(CACHE_FIL.read_text(encoding="utf-8"))

    gamle = cache.get("kategorier") or {}
    if gamle and "modell" not in next(iter(gamle.values())):
        cache["kategorier"] = migrer(gamle, cache.get("metode") or {})
    return cache


def migrer(gamle: dict, metode: dict) -> dict:
    """Migrerer fra da cache-nøkkelen inneholdt modellnavnet.

    Modellen kan utledes eksakt: den gamle nøkkelen var sha256(promptversjon|modell|tekst),
    og teksten ligger lagret på oppføringen. Vi prøver kandidatene mot nøkkelen framfor å
    stemple alt med metode.modell — cachen inneholder også tekster fra testkjøringer med
    andre modeller, og de skal ikke få feil merkelapp.

    Kolliderer to modeller på samme tekst, beholdes standardmodellens svar: det er den
    grunnlaget ellers er kategorisert med.
    """

    def gammel_nokkel(tekst: str, versjon: str, modell: str) -> str:
        raa = f"{versjon}|{modell}|{tekst.lower()}"
        return hashlib.sha256(raa.encode("utf-8")).hexdigest()[:16]

    modeller = [STANDARDMODELL, RESERVEMODELL, "anthropic/claude-sonnet-5"]
    if metode.get("modell"):
        modeller.append(metode["modell"])
    # Tidligere promptversjoner tas med for å kunne KJENNE IGJEN dem, ikke for å beholde
    # dem: de brukte en annen kategoriliste, og skal forkastes.
    versjoner = [PROMPTVERSJON, "formaal-v1"]

    ny: dict[str, dict] = {}
    funnet: Counter = Counter()
    forkastet: Counter = Counter()
    ukjent = 0

    for gnok, post in gamle.items():
        traff = next(
            (
                (v, m)
                for v in versjoner
                for m in modeller
                if gammel_nokkel(post["tekst"], v, m) == gnok
            ),
            None,
        )
        if traff is None:
            ukjent += 1
            continue
        versjon, modell = traff
        if versjon != PROMPTVERSJON:
            forkastet[versjon] += 1
            continue
        funnet[modell] += 1
        k = nokkel(post["tekst"])
        if k in ny and ny[k]["modell"] == STANDARDMODELL:
            continue  # standardmodellens svar vinner ved kollisjon
        ny[k] = {**post, "modell": modell}

    print(f"  cache migrert: {len(gamle):,} oppføringer → {len(ny):,} unike tekster")
    for m, n in funnet.most_common():
        print(f"    {n:6,}  {m}")
    for v, n in forkastet.most_common():
        print(f"    {n:6,}  forkastet — promptversjon {v}, annen kategoriliste")
    if ukjent:
        raise SystemExit(
            f"{ukjent} oppføringer kunne ikke tilskrives en promptversjon og modell. "
            "Utvid listene i migrer() framfor å gjette."
        )
    return ny


def modellfordeling(cache: dict) -> Counter:
    return Counter(p.get("modell", "ukjent") for p in cache["kategorier"].values())


def skriv_cache(cache: dict, modell: str) -> None:
    fordeling = modellfordeling(cache)
    cache["metode"] = {
        "modell": modell,
        "modeller": dict(fordeling),
        "promptversjon": PROMPTVERSJON,
        "dato_kjort": date.today().isoformat(),
        "antall_tekster": len(cache["kategorier"]),
        "kategorier": sorted(KATEGORIER),
        "kilde": csv_sti().name,
    }
    CACHE_FIL.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FIL.write_text(
        json.dumps(cache, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------- modellkall


def bygg_prompt(tekster: list[str]) -> str:
    liste = "\n".join(f"{k}: {v}" for k, v in KATEGORIER.items())
    nummererte = "\n".join(f"{i + 1}. {t[:600]}" for i, t in enumerate(tekster))
    return (
        "Kategorier:\n"
        f"{liste}\n\n"
        "Plasser hver beskrivelse under i nøyaktig én kategori. Velg kategorien som best "
        "beskriver hva pengene skal brukes til — ikke hva slags organisasjon som søker. "
        "Beskriver teksten et formål du kjenner igjen, skal du bruke den kategorien selv "
        "om ordlyden er kortfattet. «uklar_beskrivelse» er kun for tekster som ikke sier "
        "noe om formålet i det hele tatt.\n\n"
        f"Beskrivelser:\n{nummererte}\n\n"
        f"Svar med en JSON-liste med {len(tekster)} objekter, i samme rekkefølge: "
        '[{"nr": 1, "kategori": "..."}, ...]. Ingen annen tekst.'
    )


def kategoriser_bunt(tekster: list[str], modell: str, dybde: int = 0) -> list[str]:
    """Kategoriserer én bunt. Kommer svaret skjevt tilbake, halveres bunten og forsøkes
    på nytt — over 400 kall skjer det før eller siden, og da skal ikke hele kjøringen dø.
    Feiler det fortsatt på én enkelt tekst, er det en ekte feil og vi stopper."""
    try:
        return _kategoriser_bunt(tekster, modell)
    except BuntFeil as e:
        if len(tekster) == 1 or dybde >= 4:
            raise SystemExit(f"Bunt på {len(tekster)} feilet gjentatte ganger: {e}")
        midt = len(tekster) // 2
        print(f"    bunt på {len(tekster)}: {e} — deler i to og prøver igjen")
        return kategoriser_bunt(tekster[:midt], modell, dybde + 1) + kategoriser_bunt(
            tekster[midt:], modell, dybde + 1
        )


def _kategoriser_bunt(tekster: list[str], modell: str) -> list[str]:
    svar = kall_modell(
        [
            {"role": "system", "content": SYSTEMPROMPT},
            {"role": "user", "content": bygg_prompt(tekster)},
        ],
        modell=modell,
        # Målt forbruk er ~20 tokens per tekst; 40 gir dobbel margin. Ikke sett dette
        # høyere «for sikkerhets skyld»: OpenRouter reserverer kreditt mot maks_tokens
        # for hver forespørsel i luften, så et oppblåst tak sprenger in-flight-budsjettet
        # lenge før kontoen er tom.
        maks_tokens=40 * len(tekster) + 400,
    )
    try:
        rader = hent_json_liste(svar)
    except ValueError as e:
        raise BuntFeil(str(e)) from e

    if len(rader) != len(tekster):
        raise BuntFeil(f"{len(rader)} kategorier på {len(tekster)} tekster")

    ut = []
    for post in rader:
        kat = str(post.get("kategori", "")).strip().lower()
        if kat not in KATEGORIER:
            raise BuntFeil(f"ukjent kategori {kat!r}")
        ut.append(kat)
    return ut


def kjor(
    tekster: list[str],
    modell: str,
    buntstorrelse: int,
    arbeidere: int,
    reserve: bool = False,
) -> dict:
    cache = les_cache()
    mangler = [t for t in tekster if nokkel(t) not in cache["kategorier"]]
    print(f"  {len(tekster) - len(mangler)} av {len(tekster)} tekster lå i cachen")
    if not mangler:
        return cache

    bunter = [mangler[i : i + buntstorrelse] for i in range(0, len(mangler), buntstorrelse)]
    print(f"  {len(mangler)} tekster igjen → {len(bunter)} kall med {arbeidere} tråder")
    ferdig = 0

    def behandle(bunt: list[str]) -> None:
        nonlocal ferdig
        kategorier = kategoriser_bunt(bunt, modell)
        with _las:
            for tekst, kat in zip(bunt, kategorier):
                cache["kategorier"][nokkel(tekst)] = {
                    "tekst": tekst,
                    "kategori": kat,
                    "modell": modell,
                }
            ferdig += 1
            if ferdig % 25 == 0 or ferdig == len(bunter):
                print(f"    {ferdig}/{len(bunter)} bunter")
                skriv_cache(cache, modell)

    try:
        with ThreadPoolExecutor(max_workers=arbeidere) as pool:
            list(pool.map(behandle, bunter))
    except TomForKreditt as e:
        skriv_cache(cache, modell)
        if not reserve or modell == RESERVEMODELL:
            raise SystemExit(str(e))
        print(
            f"\n!! Kreditten er brukt opp. Bytter til reservemodellen {RESERVEMODELL}.\n"
            f"   {len(cache['kategorier']):,} tekster er allerede kategorisert med {modell}\n"
            "   og røres ikke. Resten får en annen modell, og det registreres per\n"
            "   oppføring — grunnlaget blir blandet, og må opplyses om i historien.\n"
        )
        return kjor(tekster, RESERVEMODELL, buntstorrelse, arbeidere, reserve=True)

    skriv_cache(cache, modell)
    return cache


# ---------------------------------------------------------------- fasittest


def fasittest(antall: int, modell: str, buntstorrelse: int) -> int:
    """Måler om modellen forstår norske tilskuddstekster i det hele tatt.

    Den får mottakernavn + fritekst og skal gjette ICNPO-kategorien, som finnes som fasit
    på 98,6 % av radene. Testen er streng: ICNPO beskriver organisasjonens sektor, ikke
    tiltaket, så selv en perfekt leser bommer på noen. Poenget er en nedre grense, ikke
    en fasit for formålskategoriene.
    """
    icnpo = sorted(
        {
            (r.get("icnpo_kategori") or "").strip()
            for r in les_rader()
            if (r.get("icnpo_kategori") or "").strip()
        }
    )
    kandidater = [
        (f"{(r.get('mottakernavn') or '').strip()} — {fritekst(r)}", r["icnpo_kategori"].strip())
        for r in les_rader()
        if (r.get("icnpo_kategori") or "").strip() and len(fritekst(r)) >= 12
    ]
    random.seed(42)
    utvalg = random.sample(kandidater, min(antall, len(kandidater)))
    print(f"Fasittest: {len(utvalg)} tilfeldige rader (seed 42), {len(icnpo)} ICNPO-kategorier")

    liste = "\n".join(f"- {k}" for k in icnpo)
    treff = 0
    formatfeil = 0
    per_kategori: Counter = Counter()
    per_kategori_treff: Counter = Counter()
    forvekslinger: Counter = Counter()
    ugyldige: Counter = Counter()

    for i in range(0, len(utvalg), buntstorrelse):
        bunt = utvalg[i : i + buntstorrelse]
        nummererte = "\n".join(f"{n + 1}. {t[:600]}" for n, (t, _) in enumerate(bunt))
        svar = kall_modell(
            [
                {"role": "system", "content": SYSTEMPROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Gyldige kategorier:\n{liste}\n\n"
                        "Under står mottakernavn og beskrivelse for norske offentlige "
                        "tilskudd. Gjett hvilken kategori mottakeren er registrert under. "
                        "Bruk nøyaktig skrivemåten over.\n\n"
                        f"{nummererte}\n\n"
                        f"Svar med en JSON-liste med {len(bunt)} objekter i samme "
                        'rekkefølge: [{"nr": 1, "kategori": "..."}, ...]. Ingen annen tekst.'
                    ),
                },
            ],
            modell=modell,
            # ICNPO-navnene er lange («Rekreasjon og sosiale foreninger»), og noen
            # modeller pakker svaret i en ```json-blokk. Romsligere enn formålskodene.
            maks_tokens=100 * len(bunt) + 400,
        )
        # Formatbrudd er en egenskap ved modellen vi vil MÅLE, ikke en grunn til å avbryte.
        # Svake modeller skriver resonneringen sin som svartekst i stedet for JSON; da skal
        # testen rapportere hvor ofte det skjer framfor å dø på første tilfelle.
        try:
            rader = hent_json_liste(svar)
        except ValueError:
            formatfeil += len(bunt)
            print(f"  {min(i + buntstorrelse, len(utvalg))}/{len(utvalg)} — formatfeil, hoppet over")
            continue
        if len(rader) != len(bunt):
            formatfeil += len(bunt)
            print(f"  {min(i + buntstorrelse, len(utvalg))}/{len(utvalg)} — "
                  f"{len(rader)} svar på {len(bunt)} rader, hoppet over")
            continue
        for (_, fasit), post in zip(bunt, rader):
            gjett = str(post.get("kategori", "")).strip()
            per_kategori[fasit] += 1
            if gjett == fasit:
                treff += 1
                per_kategori_treff[fasit] += 1
            elif gjett not in icnpo:
                ugyldige[gjett] += 1
            else:
                forvekslinger[(fasit, gjett)] += 1
        print(f"  {min(i + buntstorrelse, len(utvalg))}/{len(utvalg)} — {treff} treff så langt")

    besvart = len(utvalg) - formatfeil
    if not besvart:
        raise SystemExit(
            f"Modellen ga ugyldig format på alle {len(utvalg)} radene — den kan ikke "
            "brukes til strukturert klassifisering."
        )
    andel = treff / besvart * 100
    print(f"\nForbruk: {forbruk_oppsummert()}")
    if formatfeil:
        print(
            f"\nFormatfeil: {formatfeil} av {len(utvalg)} rader "
            f"({formatfeil / len(utvalg) * 100:.0f} %) — modellen svarte ikke med gyldig "
            "JSON, og de er utelatt fra treffprosenten under"
        )
    print(f"\nTreffsikkerhet: {treff}/{besvart} = {andel:.1f} %")
    print("\nPer kategori (kun kategorier med minst 5 rader i utvalget):")
    for kat, n in per_kategori.most_common():
        if n >= 5:
            andel_kat = per_kategori_treff[kat] / n * 100
            print(f"  {andel_kat:5.1f} %  ({per_kategori_treff[kat]}/{n})  {kat}")

    if ugyldige:
        print(f"\nSvar utenfor kategorilisten ({sum(ugyldige.values())} stk):")
        for gjett, n in ugyldige.most_common(10):
            print(f"  {n:4d}  {gjett!r}")

    print("\nVanligste forvekslinger (fasit → gjett):")
    for (fasit, gjett), n in forvekslinger.most_common(12):
        print(f"  {n:4d}  {fasit}  →  {gjett}")

    if andel < 70:
        print(
            "\n✗ Under 70 %. Se forvekslingene over før du konkluderer: går de mellom "
            "kategorier som overlapper i ICNPO selv (rekreasjon/interesse/lokalsamfunn), "
            "måler testen ICNPO-uklarhet, ikke modellens lesing."
        )
        return 1
    print("\n✓ Over terskelen på 70 %.")
    return 0


# ---------------------------------------------------------------- kontrolltall


def kontrolltall(
    cache: dict, unike: dict[str, dict], sum_: dict, modell: str, streng: bool
) -> None:
    fordeling: Counter = Counter()
    kroner: Counter = Counter()
    dekket = 0
    for tekst, post in unike.items():
        treff = cache["kategorier"].get(nokkel(tekst))
        if not treff:
            continue
        dekket += 1
        fordeling[treff["kategori"]] += post["antall"]
        kroner[treff["kategori"]] += post["belop"]

    rader = sum(fordeling.values())
    if not rader:
        raise SystemExit("Ingen tekster er kategorisert — noe er galt med cachen.")
    kr_sum = sum(kroner.values())

    print(f"\nFormelstyrt (holdt utenfor): {sum_['formel_rader']:>9,.0f} rader  "
          f"{sum_['formel_belop'] / 1e9:6.1f} mrd kr  "
          f"({sum_['formel_belop'] / sum_['belop'] * 100:.1f} % av alle kroner)")
    print(f"Kategorisert:                {rader:>9,} rader  {kr_sum / 1e9:6.1f} mrd kr  "
          f"({dekket:,} av {len(unike):,} unike tekster)")

    print(f"\n{'kategori':28s} {'rader':>9s} {'mrd kr':>8s} {'andel kr':>9s}")
    for kat, n in kroner.most_common():
        print(f"{kat:28s} {fordeling[kat]:9d} {n / 1e9:8.2f} {n / kr_sum * 100:8.1f}%")

    # «annet» = kategorilisten treffer ikke. «uklar_beskrivelse» = kilden sier ikke hva
    # pengene skal brukes til. Bare den første er en feil ved vårt arbeid; den andre er et
    # funn om datasettet, og hører hjemme i historien framfor å skjules.
    annet_kr = kroner["annet"] / kr_sum * 100
    annet_rader = fordeling["annet"] / rader * 100
    uklar_kr = kroner["uklar_beskrivelse"] / kr_sum * 100
    print(f"\n«annet»              {annet_rader:5.1f} % av rader, {annet_kr:5.1f} % av kroner")
    print(f"«uklar_beskrivelse»  {fordeling['uklar_beskrivelse'] / rader * 100:5.1f} % av rader, "
          f"{uklar_kr:5.1f} % av kroner")

    if annet_kr <= 25:
        print(f"\n✓ «annet» er under grensen på 25 % av kronene")
    elif not streng:
        print(
            f"\n! «annet» er {annet_kr:.1f} % av kronene. På et utvalg er kroneandelen "
            "ustabil — én stor tildeling flytter den flere prosentpoeng. Vurderes for "
            "alvor først ved --alle."
        )
    else:
        raise SystemExit(
            f"\n✗ {annet_kr:.1f} % av kronene havnet i «annet». Over 25 % betyr at "
            "kategorilisten ikke passer dataene — utvid KATEGORIER framfor å publisere."
        )


# ---------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser(description="Kategoriserer tilskuddsfritekster etter formål.")
    ap.add_argument("--alle", action="store_true", help="kategoriser alle unike tekster")
    ap.add_argument("--grense", type=int, help="kategoriser kun de N vanligste tekstene")
    ap.add_argument(
        "--kroner",
        type=int,
        metavar="N",
        help="kategoriser de N tekstene som har flest kroner bak seg (best dekning per krone)",
    )
    ap.add_argument(
        "--utvalg",
        type=int,
        metavar="N",
        help="tilfeldig utvalg på N tekster (seed 42) — for kvalitetssjekk, ikke publisering",
    )
    ap.add_argument("--fasittest", type=int, metavar="N", help="mål treffsikkerhet mot ICNPO")
    ap.add_argument("--modell", default=STANDARDMODELL)
    ap.add_argument("--bunt", type=int, default=20, help="tekster per modellkall")
    ap.add_argument("--arbeidere", type=int, default=8, help="parallelle kall")
    ap.add_argument(
        "--reserve",
        action="store_true",
        help=f"bytt til gratismodellen ({RESERVEMODELL}) hvis kreditten tar slutt",
    )
    args = ap.parse_args()

    if args.fasittest:
        return fasittest(args.fasittest, args.modell, args.bunt)

    if not (args.alle or args.grense or args.utvalg or args.kroner):
        ap.error(
            "velg --alle, --kroner N, --grense N, --utvalg N eller --fasittest N "
            "(koster penger — ingen default)"
        )

    print(f"Leser {csv_sti().name} …")
    unike, sum_ = samle_unike_tekster()
    print(
        f"  {sum_['rader']:,.0f} rader, {sum_['belop'] / 1e9:.1f} mrd kr\n"
        f"  {sum_['formel_rader']:,.0f} formelstyrte rader holdt utenfor "
        f"({sum_['formel_belop'] / 1e9:.1f} mrd kr)\n"
        f"  {len(unike):,} unike beskrivelser å kategorisere"
    )

    tekster = sorted(unike, key=lambda t: -unike[t]["antall"])
    if args.kroner:
        tekster = sorted(unike, key=lambda t: -unike[t]["belop"])[: args.kroner]
        dekning = sum(unike[t]["belop"] for t in tekster)
        print(
            f"  de {len(tekster):,} største tekstene i kroner "
            f"({dekning / sum(p['belop'] for p in unike.values()) * 100:.1f} % av kronene)"
        )
    elif args.utvalg:
        random.seed(42)
        tekster = random.sample(tekster, min(args.utvalg, len(tekster)))
        print(f"  tilfeldig utvalg på {len(tekster)} tekster (seed 42)")
    elif args.grense:
        tekster = tekster[: args.grense]
        print(f"  begrenset til de {len(tekster)} vanligste")

    cache = kjor(tekster, args.modell, args.bunt, args.arbeidere, reserve=args.reserve)
    print(f"\nForbruk: {forbruk_oppsummert()}")
    kontrolltall(cache, unike, sum_, args.modell, streng=bool(args.alle))
    print(f"\nSkrevet: {CACHE_FIL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
