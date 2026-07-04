"""data.norge.no — systematisk kartlegging av Felles datakatalog.

Utvider hent_datakatalog.py: der originalen gjør ett søk for å vise at
API-et virker, søker denne på tvers av flere emneord og aggregerer
svarene til en oversikt over hvilke datasett som faktisk finnes — per
emne, utgiver (etat/kommune/fylke) og filformat. Dette er selve
«Systematisk kartlegging»-idéen fra hent_datakatalog.py sin docstring.

Kjøring:  python3 api-atlas/eksempler/analyser_datakatalog.py
          python3 api-atlas/eksempler/analyser_datakatalog.py bibliotek museum idrett
Nøkkel:   ingen
Lisens:   katalogen er åpen; hvert datasett har egen lisens (som regel NLOD)
Dok:      https://data.norge.no/nb/technical/api/search

NB om feltnavn: dette scriptet er skrevet og committet uten nettilgang
(miljøets egress-policy blokkerte search.api.fellesdatakatalog.digdir.no
i denne økten — se api-atlas/test_atlas.py, som feiler på alle 15
kildene med samme årsak). Ekstraksjonen av utgiver/format/totalt-antall
er derfor basert på det vanlige DCAT-AP-NO-mønsteret og er defensiv
(mange fallback-nøkler), men IKKE verifisert mot et ekte svar. Kjør
scriptet et sted med nettilgang og se PARSE_NOTE nedenfor hvis
aggregeringen ser tom eller feil ut.

Gull å grave i:
  - Kartlegg kulturfeltet: hvilke etater/kommuner publiserer data om
    kultur, frivillighet, idrett, bibliotek, museum — og hvem mangler?
  - Kjør månedlig og diff rapportfilen mot forrige kjøring: hvilke
    datasett er nye siden sist, hvilke er borte?
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from collections import Counter
from datetime import date, timezone, datetime
from pathlib import Path

KILDE = "Felles datakatalog (data.norge.no)"
DOK = "https://data.norge.no/nb/technical/api/search"
API = "https://search.api.fellesdatakatalog.digdir.no"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"

# Standardemner: matcher impromptu.no sitt fokus på kultur- og
# frivillighetsdata (se README.md "Idéer på tvers av kildene"). Overstyr
# med kommandolinjeargumenter, f.eks.:
#   python3 analyser_datakatalog.py kultur bibliotek museum
STANDARD_TEMAER = ["kultur", "bibliotek", "museum", "idrett", "frivillighet", "kunst"]

RAPPORT_STI = Path(__file__).resolve().parent.parent / "analyser" / "datakatalog_oversikt.json"


def post_json(url: str, body: dict, timeout: int = 60):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "User-Agent": BRUKERAGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def sok(sokeord: str, antall: int = 20) -> tuple[list[dict], int | None]:
    """Returnerer (treff-liste, totalt antall treff i katalogen for søket).

    PARSE_NOTE: «totalt antall» ligger typisk i et pagination/hits-objekt
    i søkesvaret (f.eks. totalHits/totalElements/total). Vi prøver flere
    kjente nøkler og faller tilbake til None (ukjent) hvis ingen finnes —
    juster get_totalt() under når du har sett et ekte svar.
    """
    body = {"query": sokeord, "pagination": {"page": 0, "size": antall}}
    for endepunkt in (f"{API}/search", f"{API}/search/datasets"):
        try:
            data = post_json(endepunkt, body)
        except Exception:
            continue
        treff = data.get("hits") or data.get("searchHits") or []
        if treff:
            return treff, get_totalt(data)
    raise ValueError("ingen av søkeendepunktene ga treff — sjekk API-dokumentasjonen")


def get_totalt(data: dict) -> int | None:
    for nokkel in ("totalHits", "total", "totalResults", "numberOfHits"):
        if isinstance(data.get(nokkel), int):
            return data[nokkel]
    pagination = data.get("pagination")
    if isinstance(pagination, dict):
        for nokkel in ("totalElements", "total", "totalHits"):
            if isinstance(pagination.get(nokkel), int):
                return pagination[nokkel]
    return None


def _sprakfelt(verdi) -> str | None:
    if isinstance(verdi, dict):
        return verdi.get("nb") or verdi.get("no") or verdi.get("en") or next(iter(verdi.values()), None)
    return verdi


def tittel(hit: dict) -> str:
    return _sprakfelt(hit.get("title") or {}) or "(uten tittel)"


def utgivernavn(hit: dict) -> str:
    utgiver = hit.get("publisher") or hit.get("organization") or {}
    if isinstance(utgiver, dict):
        navn = _sprakfelt(utgiver.get("name") or utgiver.get("prefLabel") or utgiver.get("id"))
        return navn or "(ukjent utgiver)"
    return str(utgiver) if utgiver else "(ukjent utgiver)"


def formater(hit: dict) -> list[str]:
    fmt = hit.get("format")
    if isinstance(fmt, list) and fmt:
        return [str(f) for f in fmt]
    distribusjoner = hit.get("distribution") or []
    ut = []
    for d in distribusjoner:
        if isinstance(d, dict) and d.get("format"):
            ut.append(str(d["format"]))
    return ut


def kartlegg(temaer: list[str], antall_per_tema: int = 20) -> dict:
    rapport = {
        "kilde": KILDE,
        "dok": DOK,
        "generert": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "temaer": {},
    }
    for i, tema in enumerate(temaer):
        if i:
            time.sleep(0.3)  # pause mellom kall — vi er gjester hos forvaltningen
        try:
            treff, totalt = sok(tema, antall_per_tema)
        except Exception as e:
            rapport["temaer"][tema] = {"feil": str(e)}
            continue
        utgivere = Counter(utgivernavn(h) for h in treff)
        alle_formater = Counter(f for h in treff for f in formater(h))
        rapport["temaer"][tema] = {
            "antall_hentet": len(treff),
            "antall_totalt": totalt,
            "topp_utgivere": utgivere.most_common(5),
            "formater": alle_formater.most_common(10),
            "eksempler": [tittel(h) for h in treff[:5]],
        }
    return rapport


def skriv_rapport(rapport: dict, sti: Path = RAPPORT_STI) -> None:
    sti.parent.mkdir(parents=True, exist_ok=True)
    sti.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")


def print_rapport(rapport: dict) -> None:
    print(f"{KILDE} — kartlegging {rapport['generert']}\n")
    for tema, funn in rapport["temaer"].items():
        if "feil" in funn:
            print(f"✗ {tema}: {funn['feil']}")
            continue
        totalt = funn["antall_totalt"]
        totalt_tekst = f"{totalt} treff totalt" if totalt is not None else f"{funn['antall_hentet']}+ treff (totalt ukjent)"
        print(f"● {tema}: {totalt_tekst}")
        if funn["topp_utgivere"]:
            topp = ", ".join(f"{navn} ({n})" for navn, n in funn["topp_utgivere"])
            print(f"    utgivere: {topp}")
        if funn["formater"]:
            fmt = ", ".join(f"{f} ({n})" for f, n in funn["formater"])
            print(f"    formater: {fmt}")
        for eksempel in funn["eksempler"]:
            print(f"    - {eksempel}")
        print()


def main() -> int:
    temaer = sys.argv[1:] or STANDARD_TEMAER
    rapport = kartlegg(temaer)
    print_rapport(rapport)
    skriv_rapport(rapport)
    print(f"✓ rapport skrevet til {RAPPORT_STI.relative_to(Path(__file__).resolve().parent.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
