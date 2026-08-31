"""Felles HTTP-henting med retry for hentescriptene.

Hvorfor denne finnes: retry-logikken tok tre runder å få riktig mot Kudos.
IncompleteRead arver fra http.client.HTTPException og ikke fra URLError, så den
gikk forbi den første versjonen. 429 er en 4xx, men betyr «for fort», ikke «du
spurte feil», så den drepte den andre. Å ha den kunnskapen i ett script og
skrive den på nytt i det neste er en garanti for at neste feil må rettes to
ganger — og at den bare blir rettet ett sted.

Reglene, samlet:

- Nettverksfeil, avkuttede svar, 5xx og 408/425/429 prøves igjen med
  eksponentiell backoff. `Retry-After` respekteres når serveren setter den.
- Alle andre 4xx bobler opp som `HttpFeil` med kroppen intakt. De blir ikke
  bedre av flere forsøk, og kroppen er ofte fasiten: Kudos' 422 oppgir det
  gyldige per_page-taket, Stortingets 400 navngir parameteren som mangler.
- Hvert forsøk skrives ut med flush. En stille retry skjuler at kilden er i
  ferd med å bli dårligere, og over hundrevis av kall er raten selve diagnosen.
"""

from __future__ import annotations

import http.client
import json
import time
import urllib.error
import urllib.request

FORSOK = 4              # med eksponentiell backoff: 2, 4, 8 sekunder
STANDARD_TIMEOUT = 30

# 4xx som likevel betyr «prøv igjen»: 408 Request Timeout, 425 Too Early,
# 429 Too Many Requests.
PROV_IGJEN_STATUS = {408, 425, 429}

# Feil som betyr «prøv igjen», ikke «gi opp». http.client.HTTPException er den
# viktige: en avkuttet chunked respons kommer som IncompleteRead, som arver fra
# HTTPException og ValueError — ikke fra URLError. OSError dekker
# ConnectionReset og TimeoutError, som begge er OSError-subklasser.
FORBIGAENDE = (
    urllib.error.URLError,
    http.client.HTTPException,
    json.JSONDecodeError,
    OSError,
)


class NettFeil(Exception):
    """Alle forsøk brukt opp på én URL.

    Bevisst en vanlig exception og ikke SystemExit: kalleren skal kunne notere
    at akkurat denne enheten feilet, gå videre, og prøve den igjen når kilden
    har fått puste. Stopper vi hele kjøringen på første gjenstridige side,
    kaster vi bort alt arbeidet som allerede er gjort.
    """


class HttpFeil(Exception):
    """En 4xx som ikke blir bedre av flere forsøk. Bærer kroppen, som ofte
    inneholder svaret på hva som var galt."""

    def __init__(self, kode: int, url: str, kropp: str):
        super().__init__(f"HTTP {kode} på {url}")
        self.kode = kode
        self.url = url
        self.kropp = kropp


def hent_bytes(url: str, brukeragent: str, timeout: int = STANDARD_TIMEOUT,
               forsok_maks: int = FORSOK, json_kropp: dict | None = None) -> bytes:
    """GET — eller POST når `json_kropp` er satt — med retry. Kroppen som bytes.

    Kaster HttpFeil på 4xx som ikke skal prøves igjen, og NettFeil når alle
    forsøk er brukt opp — den siste feilen står i meldingen.

    `json_kropp` finnes fordi SSBs PxWeb-API krever POST for alt annet enn de
    aller minste uttrekkene: GET-URL-en tar bare ~2100 tegn, og en spørring med
    noen hundre varenummer er langt over. Uten dette har hvert SSB-script rullet
    sin egen urlopen uten retry — og mistet både backoff og Retry-After.
    """
    siste: Exception | None = None
    hoder = {"User-Agent": brukeragent}
    kropp = None
    if json_kropp is not None:
        kropp = json.dumps(json_kropp).encode("utf-8")
        hoder["Content-Type"] = "application/json"
    for forsok in range(forsok_maks):
        try:
            req = urllib.request.Request(url, data=kropp, headers=hoder)
            with urllib.request.urlopen(req, timeout=timeout) as svar:
                return svar.read()
        except urllib.error.HTTPError as e:
            if e.code in PROV_IGJEN_STATUS:
                vent = e.headers.get("Retry-After") if e.headers else None
                if vent and str(vent).strip().isdigit():
                    print(f"  ⚠ HTTP {e.code}, Retry-After {vent} s — venter", flush=True)
                    time.sleep(min(int(vent), 120))
            elif e.code < 500:
                raise HttpFeil(e.code, url,
                               e.read().decode("utf-8", errors="replace")[:800]) from e
            siste = e
        except FORBIGAENDE as e:
            siste = e
        if forsok < forsok_maks - 1:
            # «except ... as e» avbinder e når blokken går ut — her er det
            # siste som bærer feilen.
            vent = min(2 ** (forsok + 1), 60)
            print(f"  ⚠ {type(siste).__name__} på forsøk {forsok + 1}/{forsok_maks} "
                  f"({siste}) — prøver igjen om {vent} s", flush=True)
            time.sleep(vent)
    raise NettFeil(f"ga opp {url} etter {forsok_maks} forsøk. "
                   f"Siste feil: {type(siste).__name__}: {siste}")


def hent_json(url: str, brukeragent: str, timeout: int = STANDARD_TIMEOUT,
              forsok_maks: int = FORSOK, json_kropp: dict | None = None) -> dict:
    """Som hent_bytes, men tolker svaret som JSON."""
    return json.loads(
        hent_bytes(url, brukeragent, timeout, forsok_maks, json_kropp).decode("utf-8")
    )
