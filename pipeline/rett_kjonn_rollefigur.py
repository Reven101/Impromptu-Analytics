"""Korrigerer den navnebaserte kjønnskolonnen mot rollefigurene folk faktisk spiller.

Kjøring (krever berik_kjonn.py først):

    python pipeline/rett_kjonn_rollefigur.py
    python pipeline/bygg_analysetabell.py

`berik_kjonn.py` utleder kjønn av fornavn, og treffer 99,9 % av de gangene den
svarer. Men de gangene den bommer, bommer den på en måte som er verdt å rette:
**Tore Segelcke**, en av Norges mest kjente Nora-skuespillerinner, står som mann
fordi «Tore» normalt er et mannsnavn på norsk. 59 personer sto som menn i
Nora-rollen; nesten alle er slike bom.

Materialet har en uavhengig kilde til det samme: 187 064 krediteringer har
rollefigur, fordelt på 425 navn. Er du kreditert som Nora, Hedda eller Fru Alving,
er du nesten sikkert kvinne — uavhengig av hva fornavnet ditt heter.

Fire valg som avgjør om korreksjonen er til å stole på:

- **Rollelista er håndskrevet.** Den kunne vært utledet — «Mrs.» og «Miss» er
  sterke signaler — men da ville regelen bommet på «Mother Aase», «Solveig» og
  «Anitra», og trukket «Mr.» ut av intet. 55 roller dekker 104 572 av de 187 064
  krediteringene med rollefigur, altså 56 %; resten står som ukjent framfor å gjettes.
- **Vi måler før vi retter.** Uenigheten mellom navn og rolle er det beste
  estimatet vi har på hvor gal kolonnen egentlig er, og det tallet forsvinner i
  det øyeblikket vi overskriver. Det rapporteres derfor først.
- **Bare konsistente tilfeller rettes.** Kryssrollebesetning er reell og økende
  etter 2000. En person som spiller både Nora og Peer Gynt er ikke en feil å
  rette, men en konflikt å telle.
- **Kilden følger med.** Hver person får `kjonn_kilde` — `navn` eller
  `rollefigur` — så det er sporbart hva som er utledet av hva.
"""

from __future__ import annotations

import collections
import json
import os
from datetime import date
from pathlib import Path

import kontrakt  # noqa: F401

RAADATA_DIR = Path(
    os.environ.get("IBSENSTAGE_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ibsenstage"
)

# Rollefigur -> kjønn. HÅNDSKREVET. Bare roller der Ibsen selv er utvetydig; alt
# som kan spilles av hvem som helst står oppført som None og brukes ikke.
#
# Utelatt med vilje: «A Troll», «Wedding Guest», «The Helmers' child», «a citizen»,
# «A porter» — ubestemte statistroller der kjønnet verken er gitt i teksten eller
# fast i tradisjonen.
ROLLE_KJONN = {
    # Et dukkehjem
    "Nora": "kvinne", "Mrs. Kristine Linde": "kvinne", "Anne Marie": "kvinne",
    "Helene": "kvinne", "Torvald Helmer": "mann", "Dr. Rank": "mann",
    "Nils Krogstad": "mann",
    # Gengangere
    "Mrs. Helene Alving": "kvinne", "Regine Engstrand": "kvinne",
    "Osvald Alving": "mann", "Pastor Manders": "mann", "Jacob Engstrand": "mann",
    # Hedda Gabler
    "Mrs. Hedda Tesman": "kvinne", "Thea Elvsted": "kvinne",
    "Miss Juliane Tesman": "kvinne", "Berte": "kvinne",
    "Jörgen Tesman": "mann", "Judge Brack": "mann", "Ejlert Lövborg": "mann",
    # Peer Gynt
    "Solveig": "kvinne", "Mother Aase": "kvinne", "Ingrid": "kvinne",
    "Anitra": "kvinne", "Herd girl": "kvinne", "Woman in green": "kvinne",
    "Peer Gynt": "mann", "The Troll King": "mann", "A Buttonmoulder": "mann",
    "Mads Moen": "mann", "Aslak": "mann", "Begriffenfeldt": "mann",
    # En folkefiende
    "Mrs. Katherine Stockmann": "kvinne", "Petra": "kvinne",
    "Dr. Thomas Stockmann": "mann", "Peter Stockmann": "mann", "Hovstad": "mann",
    "Aslaksen": "mann", "Billing": "mann", "Morten Kiil": "mann",
    "Captain Horster": "mann",
    # Vildanden
    "Hedvig": "kvinne", "Gina Ekdal": "kvinne", "Mrs. Sörby": "kvinne",
    "Hjalmar Ekdal": "mann", "Gregers Werle": "mann", "Old Ekdal": "mann",
    "Haakon Werle": "mann", "Relling": "mann", "Molvik": "mann",
    # Bygmester Solness
    "Hilde Wangel": "kvinne", "Halvard Solness": "mann",
    # Ubestemte, men kjønnede statistroller
    "A girl": "kvinne", "A Woman": "kvinne", "A boy": "mann", "A man": "mann",
}


def main() -> None:
    kfil = RAADATA_DIR / "ibsenstage_kjonn.json"
    if not kfil.exists():
        raise SystemExit(f"mangler {kfil} — kjør berik_kjonn.py først")
    kilde = json.loads(kfil.read_text(encoding="utf-8"))
    personer = {p["person_id"]: p for p in kilde["personer"]}

    # Rollebasert kjønn per person.
    roller: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    with (RAADATA_DIR / "ibsenstage_detaljer.jsonl").open(encoding="utf-8") as f:
        for linje in f:
            for b in json.loads(linje)["bidragsytere"]:
                k = ROLLE_KJONN.get((b.get("rollefigur") or "").strip())
                if k and b["person_id"]:
                    roller[b["person_id"]][k] += 1

    # --- måling FØR retting -------------------------------------------------
    enig = uenig = konflikt = 0
    bom_kvinne = bom_mann = 0
    for pid, teller in roller.items():
        p = personer.get(pid)
        if not p:
            continue
        if len(teller) > 1:
            konflikt += 1
            continue
        rolle = next(iter(teller))
        if p["kjonn"] == rolle:
            enig += 1
        elif p["kjonn"] in ("kvinne", "mann"):
            uenig += 1
            if rolle == "kvinne":
                bom_kvinne += 1
            else:
                bom_mann += 1

    målt = enig + uenig
    print(f"{len(roller)} personer har spilt minst én kjønnet rolle")
    print(f"  enige:    {enig:6d}")
    print(f"  uenige:   {uenig:6d}  = {uenig / målt * 100:.2f} % av {målt} sammenlignbare")
    print(f"    navnet sa mann, rollen sier kvinne:  {bom_kvinne}")
    print(f"    navnet sa kvinne, rollen sier mann:  {bom_mann}")
    print(f"  konflikt: {konflikt:6d}  (spiller roller av begge kjønn — rettes ikke)")

    # --- retting ------------------------------------------------------------
    rettet = 0
    for p in kilde["personer"]:
        p["kjonn_kilde"] = "navn"
        teller = roller.get(p["person_id"])
        # Bare entydige rolleprofiler brukes. Kryssrollebesetning er ekte teater,
        # ikke en registreringsfeil, og skal ikke overskrive noe.
        if not teller or len(teller) > 1:
            continue
        rolle = next(iter(teller))
        if p["kjonn"] != rolle:
            p["kjonn"] = rolle
            p["kjonn_kilde"] = "rollefigur"
            rettet += 1

    kilde["rettet_mot_rollefigur"] = {
        "dato": date.today().isoformat(),
        "roller_i_lista": len(ROLLE_KJONN),
        "personer_med_rolle": len(roller),
        "uenige": uenig, "konflikter": konflikt, "rettet": rettet,
    }
    kfil.write_text(json.dumps(kilde, ensure_ascii=False, indent=1), encoding="utf-8")

    fordeling = collections.Counter(p["kjonn"] for p in kilde["personer"])
    print(f"\n{rettet} personer rettet")
    for k in ("kvinne", "mann", "vet ikke"):
        print(f"  {k:10s} {fordeling[k]:7d}")
    print(f"  {kfil}")


if __name__ == "__main__":
    main()
