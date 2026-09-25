"""Adresse, koordinater og bydel for ungdomsskolene i Oslo.

Kjøring (etter hent_udir_ungdomsskole_oslo.py):

    python pipeline/hent_skolested_oslo.py

Leser skolelista fra impromptu_raadata/udir/ungdomsskole_oslo_karakterer.csv og
skriver impromptu_raadata/udir/ungdomsskoler_sted.csv:

    orgnr, navn, adresse, postnummer, lat, lon, bydel, bydel_metode, omraade

Adressen er beliggenhetsadressen i Enhetsregisteret (skolene er underenheter).
Koordinatene er Kartverkets adressepunkt. Brreg skriver noen adresser slik
Kartverket ikke finner dem («Kabelgata 10-12», «Inngang G …», «St. Olavsgate»);
da prøves en forenklet variant mot hele Oslo kommune.

Nedlagte skoler har ingen adresse og får ingen bydel. Det er riktig.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import kontrakt  # noqa: F401  (UTF-8 på Windows-konsollen)
from hent_udir_vgs_oslo import RAADATA_DIR
from oslo_bydel import OMRAADE, bydel

UA = {"User-Agent": "Impromptu-Analytics/1.0 (kontakt@impromptu.no)"}


def hent(url: str):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as s:
            return json.loads(s.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return None
        raise


def forenkle(gate: str) -> str:
    g = re.sub(r"^Inngang \w+ ", "", gate)
    g = re.sub(r"(\d+)\s*[-–]\s*\d+", r"\1", g)
    return re.sub(r"(\w)sgate\b", r"\1s gate", g)


def koordinater(gate: str, postnummer: str):
    for sok, filt, verdi in ((gate, "postnummer", postnummer), (forenkle(gate), "kommunenummer", "0301")):
        q = urllib.parse.urlencode({"sok": sok, filt: verdi, "treffPerSide": 1})
        treff = (hent(f"https://ws.geonorge.no/adresser/v1/sok?{q}") or {}).get("adresser", [])
        if treff:
            p = treff[0]["representasjonspunkt"]
            return p["lat"], p["lon"]
    return None, None


def main() -> int:
    with open(RAADATA_DIR / "ungdomsskole_oslo_karakterer.csv", encoding="utf-8") as f:
        skoler = {}
        for r in csv.DictReader(f):
            if r["nivaa"] == "skole":
                skoler[r["orgnr"]] = r["navn"]
    ut = []
    for orgnr, navn in sorted(skoler.items(), key=lambda x: x[1]):
        enhet = hent(f"https://data.brreg.no/enhetsregisteret/api/underenheter/{orgnr}") \
            or hent(f"https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}") or {}
        adr = enhet.get("beliggenhetsadresse") or enhet.get("forretningsadresse") or {}
        gate = " ".join(adr.get("adresse") or [])
        lat, lon = koordinater(gate, adr.get("postnummer", "")) if gate else (None, None)
        b, metode = bydel(lon, lat) if lat else (None, None)
        ut.append({"orgnr": orgnr, "navn": navn, "adresse": gate, "postnummer": adr.get("postnummer"),
                   "lat": lat, "lon": lon, "bydel": b, "bydel_metode": metode, "omraade": OMRAADE.get(b)})
        time.sleep(0.1)
    uten = [r["navn"] for r in ut if not r["bydel"]]
    naermeste = [f"{r['navn']} → {r['bydel']}" for r in ut if r["bydel_metode"] == "nærmeste"]
    if len(uten) > len(ut) * 0.2:
        raise SystemExit(f"{len(uten)} av {len(ut)} skoler uten bydel — har Brreg eller Kartverket endret seg?")
    with open(RAADATA_DIR / "ungdomsskoler_sted.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(ut[0]))
        w.writeheader()
        w.writerows(ut)
    print(f"✓ {len(ut)} skoler, {len(ut) - len(uten)} med bydel.")
    print("  Uten bydel (nedlagt/ukjent adresse):", ", ".join(uten) or "–")
    print("  Bydel valgt etter nærmeste grense — sjekk for hånd:", "; ".join(naermeste) or "–")
    return 0


if __name__ == "__main__":
    sys.exit(main())
