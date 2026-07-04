"""Norges Bank — valutakurser og renter.

Offisielle valutakurser (ca. 40 valutaer mot NOK) og styringsrenter,
daglig oppdatert, historikk langt tilbake. SDMX-standard REST-API uten
nøkkel. Kursene er de «riktige» tallene å bruke i alt fra fakturaer til
analyser.

Kjøring:  python3 api-atlas/eksempler/hent_norges_bank_valuta.py
Nøkkel:   ingen
Lisens:   åpne data — oppgi «Kilde: Norges Bank»
Dok:      https://www.norges-bank.no/tema/Statistikk/apne-data/

Endepunkt (SDMX REST):
  GET https://data.norges-bank.no/api/data/EXR/B.USD.NOK.SP
      ?format=sdmx-json&lastNObservations=5
  Nøkkelen «B.USD.NOK.SP» = daglig (B), USD mot NOK, spotkurs.
  Bytt USD mot EUR/SEK/GBP osv. format=csv gir CSV rett i pandas.
  Renter ligger i dataflyten IR i samme API.

Gull å grave i:
  - Kronekursens historie som datahistorie (hytte i Sverige-indeksen?)
  - Valutajusterte sammenligninger i alle internasjonale analyser
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

KILDE = "Norges Bank (valuta/renter)"
DOK = "https://www.norges-bank.no/tema/Statistikk/apne-data/"
API = "https://data.norges-bank.no/api/data"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"


def hent_json(url: str, timeout: int = 60):
    req = urllib.request.Request(
        url, headers={"User-Agent": BRUKERAGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def hent_kurs(valuta: str = "USD", antall: int = 5) -> list[tuple[str, float]]:
    """Siste observasjoner for én valuta mot NOK: [(dato, kurs), ...]."""
    params = {"format": "sdmx-json", "lastNObservations": antall}
    url = f"{API}/EXR/B.{valuta}.NOK.SP?{urllib.parse.urlencode(params)}"
    data = hent_json(url)

    datasett = data["data"]["dataSets"][0]
    serie = next(iter(datasett["series"].values()))
    # tidsaksen ligger i structure.dimensions.observation
    dims = data["data"]["structure"]["dimensions"]["observation"]
    tidsverdier = next(d["values"] for d in dims if d["id"] in ("TIME_PERIOD", "TIME"))

    ut = []
    for indeks, obs in sorted(serie["observations"].items(), key=lambda p: int(p[0])):
        dato = tidsverdier[int(indeks)]["id"]
        ut.append((dato, float(obs[0])))
    return ut


def smoke() -> str:
    kurser = hent_kurs("USD", 3)
    if not kurser:
        raise ValueError("ingen observasjoner — har API-et endret seg?")
    dato, kurs = kurser[-1]
    if not 3 < kurs < 30:
        raise ValueError(f"urealistisk USD/NOK-kurs: {kurs} — feil parsing?")
    return f"USD/NOK {dato}: {kurs}"


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Henter siste USD/NOK-kurser …")
    for dato, kurs in hent_kurs("USD", 5):
        print(f"  {dato}: {kurs}")
    print(f"✓ {smoke()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
