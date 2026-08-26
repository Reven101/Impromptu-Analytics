"""Tynn OpenRouter-klient for berikingssteg i pipelinen.

Brukes av hentescripts som trenger en språkmodell til å strukturere eller normalisere
rotete kildedata. Modellen kalles **kun ved bygging** — snapshotene som sjekkes inn er
statiske, og nettsiden gjør aldri et API-kall. Se CLAUDE.md.

Kun standardbibliotek (urllib), i tråd med husregelen om minst mulig avhengigheter.

API-nøkkelen leses i denne rekkefølgen:
  1. miljøvariabelen OPENROUTER_API_KEY
  2. fila OPENROUTER_ENV_FIL peker på
  3. ../openrouter/.env (der nøkkelen ligger på utviklingsmaskinen)
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
# ADVARSEL: gratisnivået ligger i en delt pulje hos leverandøren og er i praksis ikke
# tilgjengelig — åtte forsøk over 248 sekunder ga 429 hver gang, på en test med seks
# tekster. Regn ikke med den til bulkjobber. Vil du ha reell gratiskapasitet, må egen
# Google-nøkkel kobles på under openrouter.ai/settings/integrations.
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
forbruk = {"kall": 0, "kostnad": 0.0, "inn": 0, "ut": 0, "resonnering": 0}
_forbrukslas = threading.Lock()


def nullstill_forbruk() -> None:
    with _forbrukslas:
        for k in forbruk:
            forbruk[k] = 0 if k != "kostnad" else 0.0


def forbruk_oppsummert() -> str:
    return (
        f"{forbruk['kall']} kall, ${forbruk['kostnad']:.4f} — "
        f"{forbruk['inn']:,} tokens inn, {forbruk['ut']:,} ut "
        f"(hvorav {forbruk['resonnering']:,} resonnering)"
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
    forsok: int | None = None,
    tidsavbrudd: int = 120,
) -> str:
    """Returnerer modellens svartekst. Feiler hardt framfor å returnere noe tvilsomt."""
    # Gratismodellene ligger i en delt pulje og rate-limites oppstrøms. De trenger flere
    # og lengre forsøk enn en betalt modell — ellers gir de opp før puljen frigjøres.
    gratis = modell.endswith(":free")
    if forsok is None:
        forsok = 8 if gratis else 5
    payload = json.dumps(
        {
            "model": modell,
            "messages": meldinger,
            "temperature": temperatur,
            "max_tokens": maks_tokens,
        }
    ).encode("utf-8")

    hodefelt = {
        "Authorization": f"Bearer {hent_api_nokkel()}",
        "Content-Type": "application/json",
        "X-Title": "Impromptu Analytics",
    }

    siste_feil = ""
    for n in range(forsok):
        req = urllib.request.Request(BASE_URL, data=payload, headers=hodefelt, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=tidsavbrudd) as svar:
                data = json.loads(svar.read())
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
        print(f"    …{siste_feil[:120]} — nytt forsøk om {ventetid}s")
        time.sleep(ventetid)

    if "choices" not in data or not data["choices"]:
        raise SystemExit(f"Uventet responsformat fra OpenRouter: {json.dumps(data)[:400]}")

    bruk = data.get("usage") or {}
    with _forbrukslas:
        forbruk["kall"] += 1
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
        raise SystemExit(
            f"Modellen ble avkuttet av maks_tokens ({maks_tokens}); den rakk "
            f"{bruk.get('completion_tokens')} tokens, hvorav {res} på resonnering. "
            "Øk budsjettet, eller be om mindre per kall."
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
