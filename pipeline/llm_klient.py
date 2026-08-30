"""Tynn LLM-klient for berikingssteg i pipelinen.

Brukes av hentescripts som trenger en språkmodell til å strukturere eller normalisere
rotete kildedata. Modellen kalles **kun ved bygging** — snapshotene som sjekkes inn er
statiske, og nettsiden gjør aldri et API-kall. Se CLAUDE.md.

Kun standardbibliotek (urllib), i tråd med husregelen om minst mulig avhengigheter.

Standardveien er OpenRouter. API-nøkkelen leses i denne rekkefølgen:
  1. miljøvariabelen OPENROUTER_API_KEY
  2. fila OPENROUTER_ENV_FIL peker på
  3. ../openrouter/.env (der nøkkelen ligger på utviklingsmaskinen)

Andre leverandører nås med prefiks i modellnavnet, f.eks.
`nvidia:openai/gpt-oss-120b` for NVIDIAs eget endepunkt (build.nvidia.com).
Se LEVERANDORER. Nøkkelen deres leses fra sin egen miljøvariabel eller fra
`.env` på nivået over repoet — aldri fra en fil inne i repoet, som serveres
statisk av Vercel.

Merk at kostnadsrapporteringen bare virker for OpenRouter, som oppgir faktisk
pris i `usage.cost`. Kjører du mot en leverandør som ikke gjør det, sier
`forbruk_oppsummert()` «pris ikke oppgitt» framfor å vise null.
"""

from __future__ import annotations

import http.client
import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# Andre leverandører enn OpenRouter. Modellnavn med prefiks «nvidia:» går direkte
# til NVIDIAs eget endepunkt (build.nvidia.com), som er OpenAI-kompatibelt.
# Kolon er valgt som skilletegn nettopp fordi OpenRouter selv har modeller som
# heter «nvidia/...» — «nvidia:openai/gpt-oss-120b» kan ikke forveksles med dem.
#
# MERK: NVIDIA rapporterer ikke pris i svaret. forbruk_oppsummert() sier derfor
# «pris ikke oppgitt» framfor «$0,0000», som ville lest som gratis.
LEVERANDORER = {
    "nvidia": {
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "nokkel": "NVIDIA_API_KEY",
        "hjelp": "Hent nøkkel på https://build.nvidia.com/ (starter med «nvapi-»)",
        "oppgir_pris": False,
    },
}


# Lesetidsavbrudd per kall. En resonnerende modell i en delt pulje kan bruke
# lang tid på å komme i gang, og et for kort avbrudd kaster bort generering som
# var underveis: forsøket telles som mislykket, og neste forsøk starter på null.
# Settes av kalleren (kategoriser_evalueringer.py --tidsavbrudd) framfor å
# tres gjennom fem funksjoner.
STANDARD_TIDSAVBRUDD = 120


def _del_modell(modell: str) -> tuple[str, str, dict | None]:
    """«nvidia:openai/gpt-oss-120b» -> (url, modellnavn, leverandørkonfig)."""
    if ":" in modell:
        prefiks, resten = modell.split(":", 1)
        if prefiks in LEVERANDORER:
            k = LEVERANDORER[prefiks]
            return k["url"], resten, k
    return BASE_URL, modell, None

# Standardmodell for bulk-beriking, valgt på målte tall (ICNPO-fasittest, n=300, og
# faktisk pris per 1000 tekster fra usage.cost — se DATANOTAT for historien):
#
#   gemini-3.1-flash-lite   68,7 %   $0,066    ← valgt
#   claude-haiku-4.5        65,7 %   $0,182
#   claude-sonnet-5         71,0 %   $0,981
#   gemini-2.5-flash-lite   51,7 %   $0,022    for svak
#   gemini-3.7-flash          n/a    $0,388    resonnerer, se under
#
# LISTEPRIS ER IKKE PRIS. Resonnerende modeller fakturerer tenketokens som output:
# gemini-3.7-flash har lavere listepris enn Haiku, men brukte 415 av 458 output-tokens på
# resonnering vi ikke bruker, og ble dobbelt så dyr. Mål alltid med usage.cost før du
# bytter — sammenlign aldri modeller på prislisten alene.
STANDARDMODELL = "google/gemini-3.1-flash-lite"

# Reserve når kreditten tar slutt.
#
# ADVARSEL: gratismodeller er testet grundig og duger ikke til bulk. Målt:
#
#   gemma-4-31b:free        429 på åtte forsøk over 248 s — puljen er mettet
#   nemotron-super-120b     60,0 % treff, 24 min for 300 tekster (37 t for 28 000)
#   nemotron-nano-omni      formatfeil; brant 28 501 resonneringstokens på én bunt
#   nemotron-ultra-550b     78 s på seks tekster; døde på oppstrømsfeil
#   nemotron-content-safety moderasjonsklassifikator, svarer «User Safety: safe»
#
# NVIDIAs pulje har en hard grense på 16 samtidige forespørsler DELT MED ALLE ANDRE
# OpenRouter-brukere, ikke bare deg — den treffes selv når du kjører én jobb alene.
# Gratis er mulig, ikke gunstig: super-120b er 8,7 prosentpoeng svakere enn
# standardmodellen og bruker timer der den bruker minutter, for å spare et par dollar.
#
# En røyktest på seks tekster avslører ingenting av dette: alle fire nemotron-modellene
# svarte 6/6 der. Formatsammenbruddet i nano-omni kom først på 300 rader.
#
# Vil du ha reell gratiskapasitet, må egen leverandørnøkkel kobles på under
# openrouter.ai/settings/integrations.
#
# Bytte skjer bare med --reserve, skjer høylytt, og registreres per cache-oppføring: en
# historie der deler av grunnlaget er kategorisert av en annen modell må opplyse om det.
RESERVEMODELL = "google/gemma-4-31b-it:free"

STATUS_SOM_PROVES_IGJEN = {408, 409, 429, 500, 502, 503, 504, 529}


class TomForKreditt(Exception):
    """HTTP 402. Egen type så kallende kode kan bytte til RESERVEMODELL i stedet for å
    stoppe — men bare hvis den velger det bevisst, og registrerer byttet."""

# Forbruket akkumuleres på tvers av kall så scriptene kan skrive ut hva en kjøring kostet.
# OpenRouter oppgir faktisk pris per kall i usage.cost — vi anslår ikke.
forbruk = {"kall": 0, "kostnad": 0.0, "inn": 0, "ut": 0, "resonnering": 0,
           "pris_ukjent": False}
_forbrukslas = threading.Lock()


def nullstill_forbruk() -> None:
    with _forbrukslas:
        for k in forbruk:
            forbruk[k] = {"kostnad": 0.0, "pris_ukjent": False}.get(k, 0)


def forbruk_oppsummert() -> str:
    pris = ("pris ikke oppgitt av leverandøren" if forbruk["pris_ukjent"]
            else f"${forbruk['kostnad']:.4f}")
    return (
        f"{forbruk['kall']} kall, {pris} — "
        f"{forbruk['inn']:,} tokens inn, {forbruk['ut']:,} ut "
        f"(hvorav {forbruk['resonnering']:,} resonnering)"
    )


def hent_leverandornokkel(konfig: dict) -> str:
    """Nøkkel for en annen leverandør enn OpenRouter, fra miljøvariabel eller .env.

    Samme regel som ellers: nøkler bor utenfor repoet. .env-filer er sperret i
    .gitignore, fordi alt i repoet serveres statisk av Vercel.
    """
    navn = konfig["nokkel"]
    if os.environ.get(navn, "").strip():
        return os.environ[navn].strip()
    for sti in (Path(os.environ["OPENROUTER_ENV_FIL"]) if os.environ.get("OPENROUTER_ENV_FIL")
                else None,
                Path(__file__).resolve().parents[2] / ".env"):
        if sti and sti.exists():
            for linje in sti.read_text(encoding="utf-8").splitlines():
                if linje.strip().startswith(navn):
                    return linje.split("=", 1)[1].strip().strip('"').strip("'")
    envsti = Path(__file__).resolve().parents[2] / ".env"
    raise SystemExit(
        f"Fant ingen {navn}.\n"
        f"  {konfig['hjelp']}\n"
        f"  Sett miljøvariabelen, eller legg linja {navn}=... i\n"
        f"  {envsti} (utenfor repoet)."
    )


def hent_api_nokkel() -> str:
    nokkel = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if nokkel:
        return nokkel

    kandidater = []
    if os.environ.get("OPENROUTER_ENV_FIL"):
        kandidater.append(Path(os.environ["OPENROUTER_ENV_FIL"]))
    kandidater.append(Path(__file__).resolve().parent.parent.parent / "openrouter" / ".env")

    for sti in kandidater:
        if not sti.exists():
            continue
        for linje in sti.read_text(encoding="utf-8").splitlines():
            linje = linje.strip()
            if linje.startswith("OPENROUTER_API_KEY"):
                return linje.split("=", 1)[1].strip().strip('"').strip("'")

    raise SystemExit(
        "Fant ingen OPENROUTER_API_KEY.\n"
        "  Sett miljøvariabelen, eller pek OPENROUTER_ENV_FIL på en .env-fil.\n"
        f"  Lette etter: {', '.join(str(s) for s in kandidater)}"
    )


def kall_modell(
    meldinger: list[dict],
    modell: str = STANDARDMODELL,
    temperatur: float = 0.0,
    maks_tokens: int = 4000,
    resonnering: str | None = None,
    forsok: int | None = None,
    tidsavbrudd: int | None = None,
    _doblinger: int = 0,
) -> str:
    """Returnerer modellens svartekst. Feiler hardt framfor å returnere noe tvilsomt."""
    if tidsavbrudd is None:
        tidsavbrudd = STANDARD_TIDSAVBRUDD
    # Gratismodellene ligger i en delt pulje og rate-limites oppstrøms. De trenger flere
    # og lengre forsøk enn en betalt modell — ellers gir de opp før puljen frigjøres.
    # OpenRouters gratismodeller heter «...:free». NVIDIAs gratislag gjør ikke
    # det, men rate-limites like fullt, så leverandøren regnes med her.
    gratis = modell.endswith(":free") or modell.startswith("nvidia:")
    if forsok is None:
        forsok = 8 if gratis else 5

    url, modellnavn, leverandor = _del_modell(modell)
    payload = json.dumps(
        {
            "model": modellnavn,
            "messages": meldinger,
            "temperature": temperatur,
            "max_tokens": maks_tokens,
            # gpt-oss og andre resonnerende modeller tenker som standard, og
            # tenketokens faktureres og telles som output. På en klassifisering
            # med fast kategoriliste er det bortkastet: valget er ett ord, ikke
            # et resonnement. «low» kutter forbruket kraftig uten å endre svaret
            # nevneverdig — men mål det med --fasittest før du stoler på det.
            **({"reasoning_effort": resonnering} if resonnering else {}),
        }
    ).encode("utf-8")

    nokkel = (hent_leverandornokkel(leverandor) if leverandor
              else hent_api_nokkel())
    hodefelt = {
        "Authorization": f"Bearer {nokkel}",
        "Content-Type": "application/json",
        "X-Title": "Impromptu Analytics",
    }

    siste_feil = ""
    for n in range(forsok):
        req = urllib.request.Request(url, data=payload, headers=hodefelt, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=tidsavbrudd) as svar:
                data = json.loads(svar.read())
            # OpenRouter leverer også oppstrømsfeil som HTTP 200 med en error-kropp.
            # Uten dette ser en forbigående «Service temporarily overloaded» ut som et
            # permanent formatavvik, og kjøringen dør på noe som ville gått over.
            feil = data.get("error") if isinstance(data, dict) else None
            if feil:
                kode = int(feil.get("code") or 0)
                if kode == 402:
                    raise TomForKreditt(f"OpenRouter avviste kallet: {feil.get('message')}")
                siste_feil = f"kropp-feil {kode}: {str(feil.get('message'))[:200]}"
                if kode not in STATUS_SOM_PROVES_IGJEN or n == forsok - 1:
                    raise SystemExit(f"OpenRouter svarte {siste_feil}")
                ventetid = min(2 ** n * (4 if gratis else 1), 60)
                print(f"    …{siste_feil[:120]} — forsøk {n + 2}/{forsok} "
                      f"om {ventetid}s")
                time.sleep(ventetid)
                continue
            break
        except urllib.error.HTTPError as e:
            kropp = e.read().decode("utf-8", "replace")
            if e.code == 402:
                # Ta med kroppen: 402 dekker både «tom konto» og «in-flight-budsjettet
                # sprengt», og de krever helt ulike tiltak. Uten teksten er de umulige
                # å skille fra hverandre.
                raise TomForKreditt(
                    "OpenRouter avviste kallet med HTTP 402:\n"
                    f"  {kropp[:600]}\n"
                    "  Saldo og forbruk: https://openrouter.ai/settings/credits\n"
                    "  Kjøringen kan startes igjen — cachen gjør at alt som allerede er\n"
                    "  kategorisert ikke koster noe på nytt."
                )
            siste_feil = f"HTTP {e.code}: {kropp[:400]}"
            if e.code not in STATUS_SOM_PROVES_IGJEN or n == forsok - 1:
                raise SystemExit(f"OpenRouter svarte {siste_feil}")
        except (
            urllib.error.URLError,
            http.client.HTTPException,  # bl.a. IncompleteRead: svaret brytes midtveis
            ConnectionError,
            TimeoutError,
            json.JSONDecodeError,  # halvlest kropp gir ugyldig JSON
        ) as e:
            siste_feil = f"{type(e).__name__}: {e}"
            if n == forsok - 1:
                raise SystemExit(f"OpenRouter utilgjengelig etter {forsok} forsøk ({siste_feil})")
        ventetid = min(2 ** n * (4 if gratis else 1), 60)
        # Forsøksnummeret er ikke pynt: uten det ser tre og syv forsøk likt ut,
        # og man vet ikke om kjøringen er i ferd med å gi opp eller så vidt har
        # begynt å prøve.
        print(f"    …{siste_feil[:120]} — forsøk {n + 2}/{forsok} om {ventetid}s")
        time.sleep(ventetid)

    if "choices" not in data or not data["choices"]:
        raise SystemExit(f"Uventet responsformat fra OpenRouter: {json.dumps(data)[:400]}")

    bruk = data.get("usage") or {}
    with _forbrukslas:
        forbruk["kall"] += 1
        # Oppgir ikke leverandøren pris, skal det ikke leses som null. Uten dette
        # ville en NVIDIA-kjøring rapportert «$0,0000» og sett gratis ut.
        if leverandor and not leverandor.get("oppgir_pris", True):
            forbruk["pris_ukjent"] = True
        forbruk["kostnad"] += float(bruk.get("cost") or 0)
        forbruk["inn"] += int(bruk.get("prompt_tokens") or 0)
        forbruk["ut"] += int(bruk.get("completion_tokens") or 0)
        forbruk["resonnering"] += int(
            (bruk.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
        )

    valg = data["choices"][0]
    # Et avkuttet svar er ubrukelig — halvferdig JSON eller en setning som stopper midt i.
    # Uten denne sjekken feiler det først lenger nede, med en melding som peker på
    # symptomet i stedet for årsaken.
    if valg.get("finish_reason") == "length":
        res = (bruk.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
        # Resonnerende modeller bruker vidt forskjellig mye tenketokens, og de trekkes fra
        # samme budsjett som svaret. Et fast tak som passer én modell sulter en annen, så
        # vi dobler og prøver igjen framfor å kreve at kalleren gjetter riktig på forhånd.
        # Taket på to doblinger hindrer at en modell som aldri stopper får løpe fritt.
        if _doblinger < 2:
            print(
                f"    avkuttet på {maks_tokens} tokens ({res} på resonnering) — "
                f"dobler til {maks_tokens * 2}"
            )
            return kall_modell(
                meldinger, modell, temperatur, maks_tokens * 2, resonnering,
                forsok, tidsavbrudd,
                _doblinger + 1,
            )
        raise SystemExit(
            f"Modellen ble avkuttet selv med {maks_tokens} tokens; den rakk "
            f"{bruk.get('completion_tokens')}, hvorav {res} på resonnering. "
            "Be om færre elementer per kall."
        )
    return valg["message"]["content"]


def hent_json_liste(tekst: str) -> list:
    """Plukker ut den første JSON-lista i et modellsvar.

    Modeller pakker gjerne svaret i ```json-blokker eller legger på en innledende setning.
    Vi leter derfor etter ytterste [ ... ] framfor å kreve rent JSON.
    """
    start = tekst.find("[")
    slutt = tekst.rfind("]")
    if start == -1 or slutt <= start:
        raise ValueError(f"fant ingen JSON-liste i svaret: {tekst[:200]!r}")
    return json.loads(tekst[start : slutt + 1])
