"""Plasserer hver Kudos-evaluering i ett politikkområde.

Kudos har ingen emnefelt — feltkartleggingen viste 15 nøkler, og ikke ett av dem
er et tema. Til gjengjeld har hvert dokument et `abstract` med 100 % dekning, og
det er et langt bedre grunnlag enn tittelen alene.

Kjøring:

    python pipeline/kategoriser_evalueringer.py --grense 300      # måling først
    python pipeline/kategoriser_evalueringer.py --sammenlign 200  # to modeller mot hverandre
    python pipeline/kategoriser_evalueringer.py --alle

Modellen kalles KUN her, ved bygging. Resultatet er et datert, innsjekket snapshot
(pipeline/cache/kudostema_cache.json) som resten av pipelinen leser. Nettsiden gjør
aldri et API-kall.

Husreglene dette scriptet arver fra kategoriser_formaal.py, uendret:

- **Kategoriene er skrevet for hånd.** Modellen VELGER blant dem; den finner dem
  ikke på. Finner den på en, stopper scriptet framfor å opprette kategorien i
  etterkant. Andelen «annet» og «uklar» er et kvalitetsmål på lista, ikke på dataene.
- **PROMPTVERSJON inngår i cache-nøkkelen.** Endrer du prompten eller kategoriene,
  bump versjonen — da blir gamle svar ugyldige i stedet for å blandes med nye.
- **Modellnavnet inngår IKKE i nøkkelen**, men ligger på hver oppføring. Bytter en
  kjøring modell underveis, blir grunnlaget blandet — og da skal det kunne oppdages
  og opplyses om, ikke forsvinne.
- **Cachen sjekkes inn.** Den er både sporingslogg og kostnadssparer.
- **`maks_tokens` skal være realistisk.** Kreditt reserveres mot taket for hver
  forespørsel i luften; et oppblåst tak ganget med antall tråder gir HTTP 402 med
  god saldo på konto.
- **BuntFeil deles, SystemExit bobler opp.** Å dele opp mot en kredittfeil ganger
  bare opp antall mislykkede kall, på hver tråd.

Kudos står eksplisitt på godkjentlisten i SIKKERHET.md, så titler og sammendrag
kan sendes. Ingenting annet fra dokumentene forlater maskinen.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import random
import sys
import time
import urllib.parse
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import kontrakt  # noqa: F401  -- setter utf-8 på stdout (se CLAUDE.md)
import llm_klient
from llm_klient import (
    LEVERANDORER,
    STANDARDMODELL,
    TomForKreditt,
    forbruk_oppsummert,
    hent_api_nokkel,
    hent_json_liste,
    hent_leverandornokkel,
    kall_modell,
)

# Bumpes når KATEGORIER eller prompten endres.
PROMPTVERSJON = "kudostema-v2"
CACHE_FIL = Path(__file__).resolve().parent / "cache" / "kudostema_cache.json"

RAADATA_DIR = Path(
    os.environ.get("KUDOS_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "kudos"
)
KILDEFIL = RAADATA_DIR / "evalueringer.json"

# Sammendragene er lange nok til å koste mye og korte nok til å bære temaet i
# åpningen. 600 tegn er målt til å romme formålssetningen i de aller fleste.
ABSTRACT_TEGN = 600

# Politikkområdene er skrevet for hånd, etter departementsstrukturen — ikke etter
# hva som finnes i dataene. Det er poenget: en kategori ingen evaluering havner i,
# er en opplysning om forvaltningen, ikke en feil i lista.
#
# v2: «barn_og_familie» kom til etter en tomodellskjøring på 200 tekster. De to
# modellene var enige om 80 %, men uenighetene var ikke tilfeldig spredt — de
# klumpet seg der lista manglet et hjem. «Følgeevaluering av kompetansesatsingen
# for det kommunale barnevernet» ble arbeid_og_velferd hos den ene og
# kommunal_og_distrikt hos den andre; barnevern hørte ingen av stedene.
#
# Det er verre enn en høy annet-andel, som er synlig: her ble dokumentene presset
# inn i bokser som nesten passet, og andelen annet/uklar holdt seg på 2 % mens
# feilen vokste i det stille. Uenighet mellom to modeller er derfor et bedre
# instrument for å måle kategorilista enn annet-andelen alene.
#
# Likestilling er lagt til kultur_og_frivillighet, som følger departementsnavnet
# (Kultur- og likestillingsdepartementet).
KATEGORIER = {
    "helse_og_omsorg": "Helsetjenester, sykehus, folkehelse, eldreomsorg, rus og psykisk helse, legemidler.",
    "utdanning_og_forskning": "Barnehage, skole, høyere utdanning, fagopplæring, forskningspolitikk og forskningsfinansiering.",
    "arbeid_og_velferd": "Arbeidsmarked, NAV, trygd, pensjon, sykefravær, inkludering i arbeidslivet, fattigdom.",
    "barn_og_familie": "Barnevern, familiepolitikk, foreldrestøtte, adopsjon, oppvekstvilkår, vold i nære relasjoner. (Barnehage hører til utdanning og forskning.)",
    "samferdsel": "Vei, jernbane, kollektivtransport, luftfart, havner, post, elektronisk kommunikasjon.",
    "justis_og_beredskap": "Politi, domstoler, kriminalomsorg, sivil beredskap, redningstjeneste, samfunnssikkerhet.",
    "forsvar": "Forsvarssektoren, militære anskaffelser, langtidsplaner, alliert samarbeid.",
    "klima_miljo_og_energi": "Klimapolitikk, naturforvaltning, forurensning, kraft, petroleum, fornybar energi.",
    "naering_og_fiskeri": "Næringspolitikk, konkurranse, reiseliv, fiskeri, havbruk, virkemiddelapparatet.",
    "landbruk_og_mat": "Jordbruk, skogbruk, matproduksjon, mattrygghet, dyrevelferd, reindrift.",
    "kommunal_og_distrikt": "Kommuneøkonomi, kommunereform, regional utvikling, distriktspolitikk, bolig, plan og bygg.",
    "kultur_og_frivillighet": "Kultur, kunst, medier, idrett, frivillighet, likestilling og diskriminering, tros- og livssynssamfunn, kulturarv.",
    "innvandring_og_integrering": "Asyl, innvandring, integrering, bosetting, statsborgerskap.",
    "finans_og_skatt": "Skatt, avgift, statsbudsjett, finansmarked, økonomistyring i staten.",
    "utenriks_og_bistand": "Utenrikspolitikk, utviklingssamarbeid, bistand, internasjonale avtaler, EØS.",
    "digitalisering_og_forvaltning": "Digitalisering, IT-systemer, forvaltningspolitikk, statlig organisering, styring og tilsyn.",
    "annet": "Teksten er tydelig, men temaet passer ingen av kategoriene over.",
    "uklar": "Teksten sier ikke hva evalueringen handler om — bare et navn, et nummer eller en forkortelse.",
}

SYSTEMPROMPT = (
    "Du klassifiserer norske evalueringer og utredninger fra offentlig sektor "
    "etter hvilket politikkområde de handler om. Du svarer kun med JSON."
)

# Frist for preflighten. Kort med vilje: den skal svare på om tjenesten lever,
# ikke vente ut en treg modell. Kan heves med --tidsavbrudd når en stor modell
# ligger kaldt i en kø.
PREFLIGHT_TIDSAVBRUDD = 30

# Hvor ofte cachen skrives til disk under en kjøring. Ti bunter er 200 tekster:
# nok til at skrivingen ikke merkes, lite nok til at et avbrudd ikke koster mye.
LAGRE_HVER = 10

_las = threading.Lock()


def sjekk_nokler(modeller: list[str]) -> None:
    """Verifiserer at nøklene finnes FØR første kall.

    Uten dette oppdages en manglende nøkkel av fire tråder samtidig, midt i en
    kjøring som allerede har lest korpuset — fire like feilmeldinger og ingen
    anelse om hvilken modell som manglet hva.
    """
    for modell in dict.fromkeys(modeller):
        prefiks = modell.split(":", 1)[0] if ":" in modell else None
        try:
            if prefiks in LEVERANDORER:
                hent_leverandornokkel(LEVERANDORER[prefiks])
            else:
                hent_api_nokkel()
        except SystemExit as e:
            raise SystemExit(f"Modellen «{modell}» mangler nøkkel.\n{e}") from e
        print(f"  ✓ nøkkel funnet for {modell}")


def sjekk_tilkobling(modeller: list[str],
                     tidsavbrudd: int = PREFLIGHT_TIDSAVBRUDD) -> int:
    """Ett minimalt kall per modell, med kort tidsavbrudd, før den store jobben.

    En nøkkel som finnes betyr ikke at endepunktet svarer. Uten denne prøven ser
    «leverandøren er blokkert fra denne maskinen» nøyaktig ut som «modellen
    tenker lenge»: begge ender i TimeoutError etter åtte forsøk. Forskjellen er
    tjue minutter per kall og helt ulike tiltak.

    Kallet ber om ett token og aksepterer et avkuttet svar — vi tester at
    tjenesten svarer, ikke hva den svarer.
    """
    feilet = 0
    for modell in dict.fromkeys(modeller):
        url, _, leverandor = llm_klient._del_modell(modell)
        vert = urllib.parse.urlsplit(url).netloc
        start = time.monotonic()
        try:
            kall_modell([{"role": "user", "content": "Svar med tallet 1."}],
                        modell=modell, maks_tokens=16, forsok=1,
                        tidsavbrudd=tidsavbrudd)
            print(f"  ✓ {modell} svarte på {time.monotonic() - start:.1f} s "
                  f"({vert})")
        except SystemExit as e:
            # Et avkuttet svar er et svar: tjenesten er i live, og det er alt
            # denne prøven skal fastslå.
            if "avkuttet" in str(e):
                print(f"  ✓ {modell} svarte på {time.monotonic() - start:.1f} s "
                      f"({vert}, avkuttet — som forventet på 16 tokens)")
                continue
            feilet += 1
            print(f"  ✗ {modell} etter {time.monotonic() - start:.1f} s: {e}")
        except TomForKreditt as e:
            feilet += 1
            print(f"  ✗ {modell}: {e}")
    return feilet


# ---------------------------------------------------------------- kilde

def les_evalueringer() -> list[dict]:
    if not KILDEFIL.exists():
        raise SystemExit(
            f"FEIL: {KILDEFIL} mangler.\n"
            "Hent korpuset først: python pipeline/hent_kudos_evalueringer.py"
        )
    data = json.loads(KILDEFIL.read_text(encoding="utf-8"))
    dokumenter = data.get("dokumenter") or []
    if not dokumenter:
        raise SystemExit(f"FEIL: {KILDEFIL} inneholder ingen dokumenter.")
    return dokumenter


def tekst_for(dok: dict) -> str:
    """Det modellen faktisk får se: tittel, og starten av sammendraget.

    Tittelen alene er ofte nok («Evaluering av fastlegeordningen»), men langt fra
    alltid — «Områdegjennomgang av tilskudd» kan handle om hva som helst. Derfor
    tas sammendraget med, kuttet, siden temaet står i åpningen og resten er metode.
    """
    tittel = str(dok.get("title") or "").strip()
    sammendrag = " ".join(str(dok.get("abstract") or "").split())[:ABSTRACT_TEGN]
    return f"{tittel}\n{sammendrag}".strip()


def nokkel(tekst: str) -> str:
    """Cache-nøkkel. Modellnavnet inngår bevisst IKKE — det ligger på oppføringen,
    så et blandet grunnlag kan oppdages framfor å forsvinne."""
    return hashlib.sha256(
        f"{PROMPTVERSJON}|{tekst.lower()}".encode("utf-8")
    ).hexdigest()[:16]


# ---------------------------------------------------------------- cache

def les_cache() -> dict:
    if not CACHE_FIL.exists():
        return {"metode": {}, "temaer": {}}
    return json.loads(CACHE_FIL.read_text(encoding="utf-8"))


def skriv_cache(cache: dict, modell: str) -> None:
    CACHE_FIL.parent.mkdir(parents=True, exist_ok=True)
    cache["metode"] = {
        "promptversjon": PROMPTVERSJON,
        "sist_kjort": date.today().isoformat(),
        "sist_modell": modell,
        "kategorier": sorted(KATEGORIER),
        "abstract_tegn": ABSTRACT_TEGN,
    }
    CACHE_FIL.write_text(
        json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8"
    )


# ---------------------------------------------------------------- modellkall

class BuntFeil(Exception):
    """Svaret kom skjevt tilbake. Løses ved å dele bunten, ikke ved å gi opp."""


def bygg_prompt(tekster: list[str]) -> str:
    liste = "\n".join(
        f"{k}: {v}" for k, v in KATEGORIER.items()
    )
    nummerert = "\n\n".join(
        f"[{i + 1}]\n{t}" for i, t in enumerate(tekster)
    )
    return (
        "Kategorier:\n" + liste + "\n\n"
        f"Under følger {len(tekster)} evalueringer. Velg NØYAKTIG én kategori for "
        "hver, fra lista over. Ikke finn på nye kategorier.\n\n"
        + nummerert + "\n\n"
        f'Svar med en JSON-liste på {len(tekster)} objekter, i samme rekkefølge: '
        '[{"nr": 1, "kategori": "..."}, ...]. Ingen annen tekst.'
    )


def _kategoriser_bunt(tekster: list[str], modell: str, resonnering: str | None) -> list[str]:
    svar = kall_modell(
        [
            {"role": "system", "content": SYSTEMPROMPT},
            {"role": "user", "content": bygg_prompt(tekster)},
        ],
        modell=modell,
        # Svaret er ett kategorinavn per tekst: ~25 tokens med JSON-drakten.
        # 60 gir god margin uten å blåse opp in-flight-reservasjonen.
        maks_tokens=60 * len(tekster) + 400,
        resonnering=resonnering,
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


def kategoriser_bunt(tekster: list[str], modell: str,
                     resonnering: str | None, dybde: int = 0) -> list[str]:
    """Deler bunten og prøver igjen når svaret kommer skjevt tilbake.

    Over hundrevis av kall skjer det før eller siden, og da skal ikke hele
    kjøringen dø. Feiler det fortsatt på én enkelt tekst, er det en ekte feil.
    SystemExit og TomForKreditt fanges bevisst ikke: å dele opp mot dem ganger
    bare opp antall mislykkede kall, på hver tråd.
    """
    try:
        return _kategoriser_bunt(tekster, modell, resonnering)
    except BuntFeil as e:
        if len(tekster) == 1 or dybde >= 4:
            raise SystemExit(f"Bunt på {len(tekster)} feilet gjentatte ganger: {e}")
        midt = len(tekster) // 2
        print(f"    bunt på {len(tekster)}: {e} — deler i to og prøver igjen")
        return (kategoriser_bunt(tekster[:midt], modell, resonnering, dybde + 1)
                + kategoriser_bunt(tekster[midt:], modell, resonnering, dybde + 1))


def kjor(tekster: list[str], modell: str, buntstorrelse: int, arbeidere: int,
         resonnering: str | None) -> dict:
    cache = les_cache()
    cache.setdefault("temaer", {})
    mangler = [t for t in tekster if nokkel(t) not in cache["temaer"]]
    print(f"  {len(tekster) - len(mangler)} av {len(tekster)} lå i cachen")
    if not mangler:
        return cache

    bunter = [mangler[i:i + buntstorrelse] for i in range(0, len(mangler), buntstorrelse)]
    print(f"  {len(mangler)} igjen → {len(bunter)} kall med {arbeidere} tråder")
    ferdig = 0

    def behandle(bunt: list[str]) -> None:
        nonlocal ferdig
        kategorier = kategoriser_bunt(bunt, modell, resonnering)
        with _las:
            for tekst, kat in zip(bunt, kategorier):
                cache["temaer"][nokkel(tekst)] = {
                    "tekst": tekst[:200],
                    "kategori": kat,
                    "modell": modell,
                }
            ferdig += 1
            if ferdig % LAGRE_HVER == 0 or ferdig == len(bunter):
                print(f"    {ferdig}/{len(bunter)} bunter", flush=True)
                skriv_cache(cache, modell)

    try:
        with ThreadPoolExecutor(max_workers=arbeidere) as pool:
            list(pool.map(behandle, bunter))
    except TomForKreditt as e:
        skriv_cache(cache, modell)
        raise SystemExit(
            f"{e}\n{len(cache['temaer'])} tekster er allerede lagret og røres ikke."
        ) from e
    except BaseException:
        # Alt annet som avbryter kjøringen — nettverket som gir opp, tidsgrensa i
        # Actions, Ctrl-C — skal ikke koste de buntene som alt er klassifisert.
        # Uten dette skrives cachen bare hvert LAGRE_HVER kall og ved normal
        # slutt, og en drept kjøring kaster bort alt siden forrige lagring.
        skriv_cache(cache, modell)
        print(f"  Avbrutt — {len(cache['temaer'])} tekster er lagret i cachen.",
              flush=True)
        raise

    skriv_cache(cache, modell)
    return cache


# ---------------------------------------------------------------- sammenligning

def sammenlign(tekster: list[str], modell_a: str, modell_b: str,
               buntstorrelse: int, resonnering: str | None) -> int:
    """Kjører to modeller på samme utvalg og måler hvor enige de er.

    Det finnes ingen fasit for temaene — ingen har kategorisert Kudos før. Da er
    enighet mellom to uavhengige modeller det nærmeste vi kommer et kvalitetsmål,
    og uenighetene er der man skal se etter for hånd. Dette skriver IKKE til
    cachen: en måling skal ikke forurense grunnlaget den måler.
    """
    print(f"\nSammenligner på {len(tekster)} tekster")
    resultat = {}
    for navn in (modell_a, modell_b):
        print(f"  {navn} …", flush=True)
        svar = []
        for i in range(0, len(tekster), buntstorrelse):
            svar += kategoriser_bunt(tekster[i:i + buntstorrelse], navn, resonnering)
        resultat[navn] = svar
        print(f"    {forbruk_oppsummert()}")

    a, b = resultat[modell_a], resultat[modell_b]
    enige = sum(1 for x, y in zip(a, b) if x == y)
    print(f"\n  Enige om {enige}/{len(tekster)} ({100 * enige / len(tekster):.1f} %)")

    uenige = [(t, x, y) for t, x, y in zip(tekster, a, b) if x != y]
    if uenige:
        print(f"\n  De {min(15, len(uenige))} første uenighetene — les dem, "
              "og avgjør hvem som har rett:")
        for tekst, x, y in uenige[:15]:
            print(f"    {modell_a}={x}  |  {modell_b}={y}")
            print(f"      {tekst.splitlines()[0][:100]}")

    for navn, svar in resultat.items():
        fordeling = collections.Counter(svar)
        uklar = fordeling["uklar"] + fordeling["annet"]
        print(f"\n  {navn}: {len(fordeling)} kategorier i bruk, "
              f"{uklar} ({100 * uklar / len(svar):.0f} %) i annet/uklar")
        for kat, n in fordeling.most_common(5):
            print(f"    {n:>4}  {kat}")
    print("\n  Høy andel annet/uklar betyr at kategorilista er feil,")
    print("  ikke at dataene er det.")
    return 0


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--alle", action="store_true", help="kjør hele korpuset")
    ap.add_argument("--grense", type=int, help="kjør bare de N første (måling)")
    ap.add_argument("--sammenlign", type=int, metavar="N",
                    help="kjør to modeller på N tilfeldige tekster og mål enighet")
    ap.add_argument("--modell", default=STANDARDMODELL,
                    help=f"standard: {STANDARDMODELL} (OpenRouter). Kjør alt på "
                         "NVIDIA med nvidia:openai/gpt-oss-120b")
    ap.add_argument("--mot", default="nvidia:openai/gpt-oss-20b",
                    help="modell nummer to i --sammenlign. To modeller fra samme "
                         "leverandør er greit — poenget er at de er uavhengige, "
                         "ikke at de er fra hver sin tjeneste")
    ap.add_argument("--resonnering", choices=("low", "medium", "high"),
                    help="reasoning_effort; «low» for resonnerende modeller "
                         "som gpt-oss — svaret er ett ord, ikke et resonnement")
    ap.add_argument("--sjekk-tilkobling", action="store_true",
                    help="ett minimalt kall per modell og så stopp — svarer "
                         "leverandøren i det hele tatt? Tretti sekunder, mot "
                         "tjue minutter på å oppdage det samme midt i en jobb")
    ap.add_argument("--tidsavbrudd", type=int, default=None,
                    help="sekunder å vente på ett svar (standard "
                         f"{llm_klient.STANDARD_TIDSAVBRUDD}, {PREFLIGHT_TIDSAVBRUDD} "
                         "for --sjekk-tilkobling). Et 120b-kall i en delt pulje kan "
                         "bruke lengre tid på å komme i gang — og et avbrudd kaster "
                         "bort generering som var underveis")
    ap.add_argument("--bunt", type=int, default=20)
    ap.add_argument("--trader", type=int, default=4)
    args = ap.parse_args()
    if args.tidsavbrudd:
        llm_klient.STANDARD_TIDSAVBRUDD = args.tidsavbrudd

    if args.sjekk_tilkobling:
        modeller = [args.modell] + ([args.mot] if args.mot else [])
        sjekk_nokler(modeller)
        # Tretti sekunder er vår egen terskel for «i live», ikke leverandørens.
        # En stor modell som ligger kaldt i en kø kan bruke lengre tid på å
        # komme i gang uten å være nede, så terskelen skal kunne heves —
        # ellers avskriver prøven en modell den bare ikke ventet på.
        frist = args.tidsavbrudd or PREFLIGHT_TIDSAVBRUDD
        print(f"Prøvekaller hver modell med ett token (frist {frist} s) …")
        return 1 if sjekk_tilkobling(modeller, frist) else 0

    if not (args.alle or args.grense or args.sammenlign):
        ap.error("velg --grense N (måling først), --sammenlign N eller --alle")

    dokumenter = les_evalueringer()
    tekster = [tekst_for(d) for d in dokumenter]
    tekster = [t for t in tekster if t.strip()]
    print(f"{len(dokumenter)} evalueringer, {len(tekster)} med tekst")

    if args.sammenlign:
        sjekk_nokler([args.modell, args.mot])
        random.seed(42)  # samme utvalg hver gang, så to kjøringer kan sammenlignes
        utvalg = random.sample(tekster, min(args.sammenlign, len(tekster)))
        return sammenlign(utvalg, args.modell, args.mot, args.bunt, args.resonnering)

    sjekk_nokler([args.modell])
    valgte = tekster if args.alle else tekster[:args.grense]
    print(f"Kategoriserer {len(valgte)} med {args.modell}"
          + (f", reasoning_effort={args.resonnering}" if args.resonnering else ""))

    cache = kjor(valgte, args.modell, args.bunt, args.trader, args.resonnering)

    fordeling = collections.Counter(
        cache["temaer"][nokkel(t)]["kategori"] for t in valgte
        if nokkel(t) in cache["temaer"]
    )
    print(f"\n{forbruk_oppsummert()}")
    print(f"\nFordeling over {sum(fordeling.values())} evalueringer:")
    for kat, n in fordeling.most_common():
        print(f"  {n:>5}  {100 * n / sum(fordeling.values()):>5.1f} %  {kat}")

    uklar = fordeling["uklar"] + fordeling["annet"]
    andel = 100 * uklar / max(1, sum(fordeling.values()))
    print(f"\nannet/uklar: {uklar} ({andel:.1f} %)")
    if andel > 15:
        print("  ⚠ Over 15 % betyr at kategorilista ikke passer korpuset.")
        print("    Rett lista og bump PROMPTVERSJON — ikke godta tallet.")
    print(f"\nCache: {CACHE_FIL}")
    print("Husk: python pipeline/bygg_historie_evalueringer.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
