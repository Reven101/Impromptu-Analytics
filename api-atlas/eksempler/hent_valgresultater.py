"""Valgdirektoratet — valgresultater (valgresultat.no).

Offisielle resultater for stortings-, kommune- og fylkestingsvalg, ned
til kommune- og kretsnivå. Samme API som valgresultat.no selv bruker.

Kjøring:  python3 api-atlas/eksempler/hent_valgresultater.py
Nøkkel:   ingen
Lisens:   åpne data — oppgi «Kilde: Valgdirektoratet»
Dok:      https://www.valgdirektoratet.no/om-valg/valgdata/
          (API-et er lite formelt dokumentert — strukturen under er
          observert praksis og kan endres foran hvert valg)

Endepunkt-mønster:
  GET https://valgresultat.no/api/<år>/<valgtype>
      valgtype: st (storting), ko (kommune), fy (fylke)
  GET https://valgresultat.no/api/<år>/st/<fylke>          drill-down
  Svaret er JSON med partiliste, oppslutning og mandater, pluss lenker
  («_links») videre ned i geografien.

Gull å grave i:
  - Kulturpolitikkens valgvind: partienes oppslutning der kulturtilbudet
    er tettest/tynnest (koblet mot tilskudds- og KOSTRA-data per kommune)
  - Fremmøte over tid per kommune — demokratihelse som datahistorie
"""

from __future__ import annotations

import json
import sys
import urllib.request

KILDE = "Valgdirektoratet (valgresultat.no)"
DOK = "https://www.valgdirektoratet.no/om-valg/valgdata/"
API = "https://valgresultat.no/api"
BRUKERAGENT = "Impromptu-API-atlas/1.0 (kontakt@impromptu.no)"


def hent_json(url: str, timeout: int = 60):
    req = urllib.request.Request(
        url, headers={"User-Agent": BRUKERAGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as svar:
        return json.loads(svar.read().decode("utf-8"))


def hent_valg(aar: int, valgtype: str) -> dict:
    return hent_json(f"{API}/{aar}/{valgtype}")


def smoke() -> str:
    feil = []
    for aar, valgtype in ((2025, "st"), (2023, "ko"), (2021, "st")):
        try:
            data = hent_valg(aar, valgtype)
        except Exception as e:
            feil.append(f"{aar}/{valgtype}: {e}")
            continue
        partier = data.get("partier") or []
        if partier:
            storste = max(
                partier,
                key=lambda p: (p.get("stemmer", {}).get("resultat", {}).get("prosent") or 0),
            )
            navn = storste.get("id", {}).get("navn", "?")
            prosent = storste.get("stemmer", {}).get("resultat", {}).get("prosent")
            return f"{aar}/{valgtype}: {len(partier)} partier; størst: {navn} ({prosent} %)"
        return f"{aar}/{valgtype}: svar mottatt med nøklene {sorted(data)[:6]}"
    raise ValueError("ingen av valgene svarte — sjekk API-mønsteret: " + "; ".join(feil))


def main() -> int:
    print(f"{KILDE} — {DOK}")
    print("Henter nasjonalt resultat (prøver 2025/st, så eldre valg) …")
    print(f"✓ {smoke()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
