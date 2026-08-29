"""Brønnøysundregistrene — Frivillighetsregisteret.

Alle registrerte frivillige organisasjoner, med ICNPO-kategorier
(aktivitetsområder som «kunst og kultur», «idrett» osv.). Perfekt makker
til tilskuddsdataene: hvem av mottakerne er registrert frivillig, og i
hvilken kategori?

Kjøring:  python3 api-atlas/eksempler/hent_brreg_frivillighet.py
Nøkkel:   ingen
Lisens:   NLOD — oppgi «Kilde: Brønnøysundregistrene»
Dok:      https://data.brreg.no/frivillighetsregisteret/api/docs
          (Swagger: samme URL — sjekk her hvis endepunktene har flyttet seg)

Endepunkter:
  GET /frivillighetsregisteret/api/frivillige-organisasjoner?size=<n>
      søk/utlisting. NB: bruker «searchAfter»-paginering, ikke sidetall —
      sett searchAfter til høyeste org.nr fra forrige side for neste side.
  GET /frivillighetsregisteret/api/frivillige-organisasjoner/<orgnr>
      enkeltoppslag

Registeret gir deg IKKE organisasjonsnavnet. En post har organisasjons-
nummer, status, kontonummer, ICNPO-kategorier og datoer — ingenting mer.
Navnet slår du opp på orgnr i Enhetsregisteret (hent_brreg_enheter.py);
det er den koblingen som gjør de to scriptene til et par.

Kategoriens «navn» er også null i listesvaret. Selve teksten ligger i
«kategori» som enum-streng («ICNPOKategori.kulturOgRekreasjon»), eller
bak /icnpo-kategorier?spraak=NOB om du vil ha den offisielle ordlyden.

Gull å grave i:
  - Andel tilskuddsmottakere som står i Frivillighetsregisteret
  - Kulturfrivillighetens geografi: ICNPO «kunst og kultur» per kommune
  - Vekst/frafall i frivillige organisasjoner over tid
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

KILDE = "Brreg Frivillighetsregisteret"
DOK = "https://data.brreg.no/frivillighetsregisteret/api/docs"
API = "https://data.brreg.no/frivillighetsregisteret/api/frivillige-organisasjoner"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"


def hent_json(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": BRUKERAGENT})
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def hent_side(antall: int = 5, search_after: str | None = None) -> list[dict]:
    params: dict = {"size": antall}
    if search_after:
        params["searchAfter"] = search_after
    data = hent_json(f"{API}?{urllib.parse.urlencode(params)}")
    # HAL-format: lista kan ligge under _embedded eller rett på rota
    embedded = data.get("_embedded") or {}
    for verdi in embedded.values():
        if isinstance(verdi, list):
            return verdi
    return data if isinstance(data, list) else []


def icnpo(org: dict) -> str:
    """Første ICNPO-kategori som lesbar tekst, uten et ekstra oppslag."""
    kategorier = org.get("icnpoKategorier") or []
    if not kategorier:
        return "uten kategori"
    k = kategorier[0]
    # «navn» er null her; enum-strengen bærer den samme opplysningen.
    tekst = (k.get("kategori") or "").rsplit(".", 1)[-1] or "?"
    return f"ICNPO {k.get('icnpoNummer', '?')} ({tekst})"


def smoke() -> str:
    orgs = hent_side(3)
    if not orgs:
        raise ValueError("fikk ingen organisasjoner — sjekk endepunktet i Swagger-dok")
    forste = orgs[0]
    orgnr = forste.get("organisasjonsnummer")
    if not orgnr:
        # Orgnr er hele koblingsnøkkelen mot de andre registrene. Faller den
        # bort, er svarformatet endret, og da skal testen si fra framfor å
        # skrive «?» og se grønn ut.
        raise ValueError(
            f"første post mangler organisasjonsnummer — nøklene er {sorted(forste)}"
        )
    return f"{len(orgs)} organisasjoner; første: {orgnr}, {icnpo(forste)}"


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Navn står ikke i dette registeret — slå opp orgnr i Enhetsregisteret.")
    for o in hent_side(5):
        print(f"  {o.get('organisasjonsnummer', '?')}  {icnpo(o)}")
    print(f"✓ {smoke()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
