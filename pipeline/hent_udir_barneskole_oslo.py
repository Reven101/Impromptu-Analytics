"""Nasjonale prøver på 5. trinn for barneskolene i Oslo.

Kjøring:

    python pipeline/hent_udir_barneskole_oslo.py
    python pipeline/hent_skolested_oslo.py --barneskole

Skriver impromptu_raadata/udir/barneskole_oslo_np.csv: skalapoeng og antall
elever i regning, lesing og engelsk, per skole og år (2022-23 →), for hele
landet, Oslo og hver Oslo-skole.

Eierform hentes ved å be om «Offentlig skole» og «Privat eiet» hver for seg:
hver skole har tall bare under sin egen eierform, så kolonnen den står i ER
eierformen. (Samme grep som for vgs, se hent_udir_vgs_oslo.py.)

Hvorfor: historien «gladmelding til vestkanten» sier at forskjellene mellom
ungdomsskolene er satt før 8. trinn. Prøvene i 5. trinn viser om de allerede
er der på barneskolen.
"""

from __future__ import annotations

import csv
import sys

import hent_udir_ungdomsskole_oslo as gsk
from hent_udir_vgs_oslo import (RAADATA_DIR, enhetsoppslag, rapport_pivot, rapportside,
                                skoleaar_navn, tall)

MAAL = {"Skalapoeng": "skalapoeng", "Usikkerhet": "usikkerhet", "Antall elever deltatt": "antall"}


def main() -> int:
    side = rapportside("GSK_NP_Geo_Trinn5")
    fv = enhetsoppslag(side)
    enheter = {e["id"]: e for e in fv["EnhetID"]}
    ut = []
    for aar in fv["SkoleAarID"]:
        for sti, eierformer in (("1", [-10]), ("1.3.42", [-10]), ("1.3.42.*", [8, 2])):
            filtre = {**side["filterDefaultVerdier"], "SkoleAarID": [aar["id"]], "KjoennID": [-10],
                      "EierformID": eierformer, "ProevetypeID": [1, 2, 3]}
            hoder, rader = rapport_pivot(side, filtre, sti)
            for r in rader:
                enhet = gsk.klassifiser(r["id"].split("."), enheter)
                if enhet is None or (sti == "1.3.42.*" and enhet["nivaa"] != "skole"):
                    continue
                grupper: dict = {}
                for hode, verdi in zip(hoder, r["data"]):
                    if hode[-1] not in MAAL:
                        raise SystemExit(f"Ukjent mål {hode[-1]!r} i nasjonale prøver 5. trinn")
                    post = grupper.setdefault(tuple(hode[:-1]), {
                        "skoleaar": skoleaar_navn(hode[0]), **enhet, "navn": r["navn"].strip(),
                        "prove": hode[1], "eierform": hode[3], "prikket": False})
                    v, p = tall(verdi)
                    post[MAAL[hode[-1]]] = v
                    post["prikket"] = post["prikket"] or p
                ut += [p for p in grupper.values() if p["prikket"] or p.get("skalapoeng") is not None]
        print(f"  5. trinn {aar['navn']}", flush=True)

    land = [r["skalapoeng"] for r in ut if r["nivaa"] == "land" and r.get("skalapoeng")]
    skoler = {r["orgnr"] for r in ut if r["nivaa"] == "skole"}
    if not land or not all(45 <= v <= 55 for v in land):
        raise SystemExit(f"Landssnitt 5. trinn {land} — skalaen har snitt 50.")
    if not 80 <= len(skoler) <= 200:
        raise SystemExit(f"{len(skoler)} barneskoler i Oslo — ventet 80–200.")
    kolonner = list(dict.fromkeys(c for r in ut for c in r))
    with open(RAADATA_DIR / "barneskole_oslo_np.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=kolonner)
        w.writeheader()
        w.writerows(ut)
    print(f"✓ {len(ut)} rader, {len(skoler)} barneskoler i Oslo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
