"""Felles datalag for historien om korps, kor og resten av kulturfrivilligheten.

Fire kilder, alle åpne og uten nøkkel:

  Enhetsregisteret         hele registeret som gzip-JSON (~210 MB). Gir navn,
                           stiftelsesdato, næringskode og kommunenummer.
  Frivillighetsregisteret  ICNPO-kategori og grasrotandel per organisasjon.
                           Sideblar med searchAfter, maks 100 per side.
  SSB tabell 07459         folkemengde per kommune og alder, via PxWeb.
  SSB KLASS 131            kommuneendringer, til å gjøre 2010 og 2026 sammenlignbare.

Rådata havner i en cache UTENFOR repoet (IMPROMPTU_CACHE, som standard
~/.impromptu-cache/brreg). Registerfila er 210 MB, og alt i dette repoet
serveres statisk av Vercel — den skal ikke inn her.

Personopplysninger: styredataene fra /roller inneholder navn og fødselsdato.
Denne modulen plukker ut fødselsåret og kaster resten før noe skrives til disk.
Snapshotet inneholder bare aggregater (median, andeler).
"""

from __future__ import annotations

import concurrent.futures as cf
import gzip
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import kontrakt  # noqa: F401  — setter UTF-8 på stdout/stderr (se CLAUDE.md)

BRUKERAGENT = "Impromptu-datamotor/1.0 (kontakt@impromptu.no)"
HODER = {"User-Agent": BRUKERAGENT, "Accept": "application/json"}

CACHE = Path(os.environ.get("IMPROMPTU_CACHE") or (Path.home() / ".impromptu-cache" / "brreg"))

ENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/lastned"
ROLLER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/{}/roller"
FRIVILLIG_URL = "https://data.brreg.no/frivillighetsregisteret/api/frivillige-organisasjoner"
SSB_TABELL = "07459"
SSB_URL = "https://data.ssb.no/api/v0/no/table/" + SSB_TABELL
KLASS_URL = ("https://data.ssb.no/api/klass/v1/classifications/131/changes"
             "?from={fra}-01-01&to={til}-01-01&language=nb")

# Fylkesnummer etter 2024-inndelingen — kartkomponenten forstår disse.
FYLKER = ["03", "11", "15", "18", "31", "32", "33", "34",
          "39", "40", "42", "46", "50", "55", "56"]

KATEGORINAVN = {
    "skolekorps": "Skolekorps",
    "voksenkorps": "Voksenkorps",
    "kor": "Kor og songlag",
    "teater": "Teater og revy",
    "tradisjon": "Folkemusikk og tradisjon",
}


# ---------------------------------------------------------------- nett

def _hent(url: str, body: dict | None = None, timeout: int = 180, forsok: int = 4):
    """GET/POST med retry. Gir opp med SystemExit — det skal stoppe kjøringen."""
    data = json.dumps(body).encode() if body else None
    hoder = dict(HODER)
    if body:
        hoder["Content-Type"] = "application/json"
    siste = None
    for n in range(forsok):
        try:
            req = urllib.request.Request(url, data=data, headers=hoder)
            with urllib.request.urlopen(req, timeout=timeout) as svar:
                return json.loads(svar.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                raise
            siste = e
        except Exception as e:  # noqa: BLE001 — tidsavbrudd, DNS, tilbakestilt kobling
            siste = e
        if n < forsok - 1:
            time.sleep(2 * (n + 1))
    raise SystemExit(f"Ga opp mot {url}: {siste}")


def last_ned_registeret(tving: bool = False) -> Path:
    """Laster ned hele Enhetsregisteret hvis cachen mangler eller er eldre enn et døgn."""
    CACHE.mkdir(parents=True, exist_ok=True)
    fil = CACHE / "enheter_alle.json.gz"
    if fil.exists() and not tving and time.time() - fil.stat().st_mtime < 86400:
        print(f"  bruker cachet register ({fil.stat().st_size // 1_000_000} MB)")
        return fil
    print("  laster ned Enhetsregisteret (~210 MB) …")
    midlertidig = fil.with_suffix(".delvis")
    req = urllib.request.Request(ENHETER_URL, headers={"User-Agent": BRUKERAGENT})
    with urllib.request.urlopen(req, timeout=900) as svar, open(midlertidig, "wb") as ut:
        while True:
            blokk = svar.read(1 << 20)
            if not blokk:
                break
            ut.write(blokk)
    midlertidig.replace(fil)
    print(f"  lastet ned {fil.stat().st_size // 1_000_000} MB")
    return fil


# ------------------------------------------------------- klassifisering

def _tokens(navn: str) -> list[str]:
    return re.findall(r"[A-ZÆØÅ]+", (navn or "").upper())


# Organisasjonsformer et lokallag faktisk kan ha. Uten dette filteret drar
# navnereglene under med seg ELKOR AS, FALKOR HOLDING ASA og KORPSBUTIKKEN AS.
FORENINGSFORMER = {"FLI", "FORB", "SA", "STI", "ANNA", "KIRK", "BA"}

# Ord som avslører at «-kor»/«korps» i navnet ikke er musikk: et hjelpekorps
# er beredskap, et skyttarlag er skyting, og DEKOR er dekor når det står
# sammen med juletrær — men et kor når det står alene (koret DEKOR finnes).
IKKE_KULTUR = ("HJELPEKORPS", "RØDEKORS", "RØDE KORS", "SANITETSKORPS",
               "SKYTTARLAG", "SKYTTERLAG", "JULETRE")


def kategoriser(navn: str) -> str | None:
    """Sorterer en organisasjon etter navnet sitt. None = ikke en av våre.

    Navnet, ikke næringskoden, er det som skiller et skolekorps fra et kor:
    begge står som regel på 90.201 «Utøvende kunstnerisk virksomhet ...
    innenfor musikk», som også rommer platestudioer og enkeltpersonforetak.
    Til gjengjeld er navnene i dette landskapet påfallende konsekvente —
    et skolekorps heter «skolekorps», et songlag heter «songlag».
    """
    stor = (navn or "").upper()
    if any(o in stor for o in IKKE_KULTUR):
        return None
    t = _tokens(navn)
    s = set(t)

    def delvis(*ord: str) -> bool:
        return any(any(o in x for o in ord) for x in t)

    if delvis("KORPS"):
        # «SKOLES MUSIKKORPS», «KNØTTEKORPS», «JUNIORKORPS» — alle rekrutterer barn
        if delvis("SKOLEKORPS", "SKULEKORPS", "SKOLEMUSIKK", "SKULEMUSIKK",
                  "JUNIORKORPS", "KNØTTEKORPS", "ASPIRANTKORPS", "BARNEKORPS",
                  "UNGDOMSKORPS") or (s & {"SKOLE", "SKULE", "SKOLES", "SKULES",
                                           "BARNE", "JUNIOR"}):
            return "skolekorps"
        return "voksenkorps"

    # «-KOR» som ordslutt fanger MANNSKOR, KAMMERKOR, GOSPELKOR, BARNEKOR ...
    if any(x.endswith("KOR") for x in t) or (s & {"SONGLAG", "SANGLAG", "SONGKOR"}) \
            or delvis("SANGFOREN", "SONGFOREN", "VOKALENSEMBLE", "KORFOREN"):
        return "kor"

    if delvis("TEATER", "TEATRET", "TEATRE", "REVY"):
        return "teater"

    if delvis("SPELEMANNSLAG", "SPELMANNSLAG", "SPELLEMANNSLAG", "LEIKARRING",
              "FOLKEDANS", "FOLKEMUSIKK", "HUSFLIDSLAG", "BYGDEKVINNELAG",
              "MÅLLAG", "HISTORIELAG"):
        return "tradisjon"

    return None


def les_foreninger(fil: Path) -> list[dict]:
    """Leser registerfila og returnerer bare organisasjonene vi er ute etter."""
    with gzip.open(fil, "rt", encoding="utf-8") as f:
        alle = json.load(f)
    ut = []
    forkastet = 0
    for e in alle:
        kat = kategoriser(e.get("navn"))
        if not kat:
            continue
        form = (e.get("organisasjonsform") or {}).get("kode")
        if form not in FORENINGSFORMER:
            forkastet += 1
            continue
        adr = e.get("forretningsadresse") or e.get("postadresse") or {}
        ut.append({
            "orgnr": e["organisasjonsnummer"],
            "navn": e.get("navn", ""),
            "kat": kat,
            "form": form,
            "nace": (e.get("naeringskode1") or {}).get("kode") or "",
            "stiftet": e.get("stiftelsesdato"),
            "registrert": e.get("registreringsdatoEnhetsregisteret"),
            "knr": adr.get("kommunenummer"),
            "frivillig": bool(e.get("registrertIFrivillighetsregisteret")),
        })
    print(f"  {len(alle)} enheter lest, {len(ut)} klassifisert "
          f"({forkastet} navnetreff forkastet på organisasjonsform)")
    return ut


# ------------------------------------------------------------ styrer

def hent_styrer(orgnrs: list[str], traader: int = 8) -> dict[str, dict]:
    """Fødselsår for sittende styremedlemmer, per organisasjon.

    /roller gir navn og full fødselsdato. Vi beholder årstallet og kaster
    resten før noe treffer disk — cachen skal ikke være et personregister.
    """
    fil = CACHE / "styrer.json"
    ut = json.loads(fil.read_text(encoding="utf-8")) if fil.exists() else {}
    mangler = [o for o in orgnrs if o not in ut]
    if not mangler:
        print(f"  {len(ut)} styrer fra cache")
        return ut
    print(f"  {len(ut)} i cache, henter {len(mangler)} styrer ...")

    def en(orgnr: str) -> tuple[str, dict]:
        try:
            d = _hent(ROLLER_URL.format(orgnr), timeout=60)
        except urllib.error.HTTPError:
            return orgnr, {"aar": [], "leder": None}
        aar, leder = [], None
        for gruppe in d.get("rollegrupper", []):
            if (gruppe.get("type") or {}).get("kode") != "STYR":
                continue
            for rolle in gruppe.get("roller", []):
                if rolle.get("avregistrert"):
                    continue
                fdato = (rolle.get("person") or {}).get("fodselsdato")
                if not fdato:
                    continue
                aar.append(int(fdato[:4]))
                if (rolle.get("type") or {}).get("kode") == "LEDE":
                    leder = int(fdato[:4])
        return orgnr, {"aar": aar, "leder": leder}

    laas = threading.Lock()
    teller = [0]
    with cf.ThreadPoolExecutor(traader) as ex:
        for orgnr, res in ex.map(en, mangler):
            with laas:
                ut[orgnr] = res
                teller[0] += 1
                if teller[0] % 1000 == 0:
                    print(f"    {teller[0]}/{len(mangler)}")
    fil.write_text(json.dumps(ut, ensure_ascii=False), encoding="utf-8")
    return ut


# -------------------------------------------------- frivillighetsregisteret

def hent_frivillighetsregisteret(maks_alder_timer: int = 24) -> dict[str, dict]:
    """Hele Frivillighetsregisteret, sideblad med searchAfter (maks 100 per side)."""
    fil = CACHE / "frivillighetsregisteret.json"
    if fil.exists() and time.time() - fil.stat().st_mtime < maks_alder_timer * 3600:
        d = json.loads(fil.read_text(encoding="utf-8"))
        print(f"  {len(d)} frivillige organisasjoner fra cache")
        return d
    print("  blar gjennom Frivillighetsregisteret ...")
    ut: dict[str, dict] = {}
    etter = None
    while True:
        params: dict = {"size": 100}
        if etter:
            params["searchAfter"] = etter
        d = _hent(f"{FRIVILLIG_URL}?{urllib.parse.urlencode(params)}", timeout=90)
        orgs = d.get("_embedded", {}).get("frivilligeOrganisasjoner", [])
        if not orgs:
            break
        for o in orgs:
            ut[o["organisasjonsnummer"]] = {
                "innfoert": o.get("innfoertDato"),
                "icnpo": [k.get("icnpoNummer") for k in (o.get("icnpoKategorier") or [])],
                "grasrot": bool((o.get("grasrotandel") or {}).get("deltarI")),
            }
        etter = orgs[-1]["organisasjonsnummer"]
        if not (d.get("_links") or {}).get("next"):
            break
    fil.write_text(json.dumps(ut, ensure_ascii=False), encoding="utf-8")
    print(f"  {len(ut)} frivillige organisasjoner hentet")
    return ut


# ------------------------------------------------------------- ssb

def _jsonstat(d: dict) -> tuple[dict, list[str]]:
    rekkefolge, storrelser = d["id"], d["size"]
    indekser = [d["dimension"][k]["category"]["index"] for k in rekkefolge]
    omvendt = [{v: k for k, v in i.items()} for i in indekser]
    ut = {}
    for flat, verdi in enumerate(d["value"]):
        if verdi is None:
            continue
        koord, rest = [], flat
        for s in reversed(storrelser):
            koord.append(rest % s)
            rest //= s
        koord.reverse()
        ut[tuple(omvendt[i][k] for i, k in enumerate(koord))] = verdi
    return ut, rekkefolge


def kommunekoder() -> list[str]:
    meta = _hent(SSB_URL, timeout=90)
    region = next(v for v in meta["variables"] if v["code"] == "Region")
    return [k for k in region["values"] if len(k) == 4 and k.isdigit()]


def sammenlignbare_enheter(fra: int, til: int):
    """Union-find over alle kommuneendringer i perioden.

    Kommunenummer endres ved hver reform, og både sammenslåinger og delinger
    ødelegger en naiv join: Halden er 0101 i 2010 og 3101 i 2026, og Ålesund
    ble delt i to i 2024. En ren gammel-til-ny-oppslagstabell takler ikke
    delingene — den mister den ene halvparten stille. Ved å slå alle koder som
    henger sammen gjennom en endring inn i én gruppe, blir folketall og
    organisasjoner summerbare i begge ender av perioden uansett reform.
    Prisen er at noen grupper dekker flere av dagens kommuner.
    """
    far: dict[str, str] = {}

    def finn(x: str) -> str:
        far.setdefault(x, x)
        while far[x] != x:
            far[x] = far[far[x]]
            x = far[x]
        return x

    def slaa(a: str, b: str) -> None:
        ra, rb = finn(a), finn(b)
        if ra != rb:
            far[ra] = rb

    for c in _hent(KLASS_URL.format(fra=fra, til=til), timeout=90)["codeChanges"]:
        slaa(c["oldCode"], c["newCode"])
    return finn


def ssb_folketall(regioner: list[str], aar: list[str], aldre: list[str] | None = None):
    """{år: {region: antall}} fra tabell 07459."""
    sporring = [{"code": "Region", "selection": {"filter": "item", "values": regioner}}]
    if aldre:
        sporring.append({"code": "Alder", "selection": {"filter": "item", "values": aldre}})
    sporring += [
        {"code": "ContentsCode", "selection": {"filter": "item", "values": ["Personer1"]}},
        {"code": "Tid", "selection": {"filter": "item", "values": aar}},
    ]
    d = _hent(SSB_URL, {"query": sporring, "response": {"format": "json-stat2"}})
    verdier, rekkefolge = _jsonstat(d)
    ireg, itid = rekkefolge.index("Region"), rekkefolge.index("Tid")
    ut: dict[str, dict[str, int]] = {a: {} for a in aar}
    for nokkel, verdi in verdier.items():
        if not verdi:
            continue
        ut[nokkel[itid]][nokkel[ireg]] = ut[nokkel[itid]].get(nokkel[ireg], 0) + int(verdi)
    return ut


def grupper_folketall(aar: list[str], aldre: list[str] | None = None):
    """Som ssb_folketall, men aggregert til reform-uavhengige kommunegrupper."""
    finn = sammenlignbare_enheter(int(min(aar)), int(max(aar)))
    raa = ssb_folketall(kommunekoder(), aar, aldre)
    ut: dict[str, dict[str, int]] = {a: {} for a in aar}
    for a, per_region in raa.items():
        for reg, verdi in per_region.items():
            g = finn(reg)
            ut[a][g] = ut[a].get(g, 0) + verdi
    return ut, finn
