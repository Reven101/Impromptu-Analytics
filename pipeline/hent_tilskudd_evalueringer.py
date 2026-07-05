"""Kobler tilskuddskroner mot Kudos-evalueringer, og skriver snapshot til
innhold/tilskuddskontroll/data.json.

Kildedata: tilskudd_data/evalueringer_vs_tilskudd.csv i det lokale
tilskuddskompasset-repoet — bygget der av analyse/evalueringer_vs_tilskudd.py
(v2), som for hver forvalter i tilskudd.no-tildelingene spør Kudos'
aktørsøk (actor_name) direkte om antall evalueringer.

Kjøring (krever at tilskuddskompasset ligger som søsken-mappe under samme
github-katalog):

    python3 pipeline/hent_tilskudd_evalueringer.py
    python3 pipeline/bygg_manifest.py

Mangler kildefilen, regenerer den i tilskuddskompasset-repoet:

    python3 analyse/evalueringer_vs_tilskudd.py

VIKTIG METODENOTAT (arvet fra kildescriptet): dette er utforskende
statistikk, ikke kausalanalyse. Tildelingsdataene dekker bare 2021–2026 —
altfor kort vindu til å si at evalueringer *fører til* budsjettendringer.
Kudos' aktørsøk er dessuten tekstbasert — stikkprøv forvaltere du kjenner
på kudos.dfo.no før tall siteres videre. Tallene peker på mønstre verdt
å undersøke, ikke konklusjoner.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

from kontrakt import INNHOLD_DIR, valider_snapshot

KILDEFIL = (Path(__file__).resolve().parent.parent.parent
            / "tilskuddskompasset" / "tilskudd_data" / "evalueringer_vs_tilskudd.csv")
UTFIL = INNHOLD_DIR / "tilskuddskontroll" / "data.json"

ZERO_EVAL_GALLERI_N = 6
MOTSATT_GALLERI_N = 5
MOTSATT_SUM_TAK = 1_000_000_000  # ekskluder de store pengeforvalterne fra "motsatt"-galleriet


def les_rader() -> list[dict]:
    if not KILDEFIL.exists():
        raise SystemExit(
            f"FEIL: {KILDEFIL} mangler.\n"
            "Regenerer den i tilskuddskompasset-repoet: "
            "python3 analyse/evalueringer_vs_tilskudd.py"
        )
    with KILDEFIL.open("r", encoding="utf-8-sig") as f:
        rader = list(csv.DictReader(f, delimiter=";"))
    for r in rader:
        r["evalueringer_totalt"] = int(r["evalueringer_totalt"])
        r["evalueringer_2021_2026"] = int(r["evalueringer_2021_2026"])
        r["sum_tildelt_2021_2026"] = float(r["sum_tildelt_2021_2026"])
        r["antall_tildelinger"] = int(r["antall_tildelinger"])
    return rader


def fmt_kr(n: float) -> str:
    if abs(n) >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}".replace(".", ",") + " mrd kr"
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.1f}".replace(".", ",") + " mill. kr"
    return f"{n:,.0f}".replace(",", " ") + " kr"


def fmt_antall(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def bygg_snapshot(rader: list[dict]) -> dict:
    rader_sortert = sorted(rader, key=lambda r: -r["sum_tildelt_2021_2026"])
    storst = rader_sortert[0]
    total_sum = sum(r["sum_tildelt_2021_2026"] for r in rader)

    uten_eval = [r for r in rader if r["evalueringer_totalt"] == 0]
    uten_eval_sum = sum(r["sum_tildelt_2021_2026"] for r in uten_eval)
    uten_eval_andel = round(uten_eval_sum / total_sum * 100)
    uten_eval_topp = sorted(uten_eval, key=lambda r: -r["sum_tildelt_2021_2026"])[:ZERO_EVAL_GALLERI_N]

    smaa_men_evaluerte = sorted(
        (r for r in rader if r["sum_tildelt_2021_2026"] < MOTSATT_SUM_TAK),
        key=lambda r: -r["evalueringer_totalt"],
    )[:MOTSATT_GALLERI_N]

    def kort_storst(r: dict) -> dict:
        detalj = ("ingen evaluering registrert i Kudos" if r["evalueringer_totalt"] == 0
                   else f"{r['evalueringer_totalt']} evaluering"
                        f"{'er' if r['evalueringer_totalt'] != 1 else ''} i Kudos")
        return {"overtittel": r["forvalter"], "verdi": fmt_kr(r["sum_tildelt_2021_2026"]),
                "detalj": detalj}

    def kort_uten_eval(r: dict) -> dict:
        return {"overtittel": r["forvalter"], "verdi": fmt_kr(r["sum_tildelt_2021_2026"]),
                "detalj": f"{fmt_antall(r['antall_tildelinger'])} tildelinger, "
                          f"{r['forste_aar']}–{r['siste_aar']}"}

    def kort_motsatt(r: dict) -> dict:
        n = r["evalueringer_totalt"]
        return {"overtittel": r["forvalter"], "verdi": f"{fmt_antall(n)} evaluering{'er' if n != 1 else ''}",
                "detalj": f"{fmt_kr(r['sum_tildelt_2021_2026'])} tildelt, "
                          f"{r['forste_aar']}–{r['siste_aar']}"}

    return {
        "meta": {
            "tittel": (f"{round(storst['sum_tildelt_2021_2026'] / 1_000_000_000)} milliarder, "
                       f"{storst['evalueringer_totalt']} evalueringer"),
            "kilde": "Kudos (DFØ) og tilskudd.no (Lotteri- og stiftelsestilsynet)",
            "kilde_url": "https://kudos.dfo.no/",
            "dato_hentet": date.today().isoformat(),
            "geografi": "Norge",
            "enhet": "kroner tildelt 2021–2026; antall evalueringer i Kudos",
            "oppdateringsfrekvens": "årlig",
            "beskrivelse": (
                f"{storst['forvalter']} fordelte {fmt_kr(storst['sum_tildelt_2021_2026'])} i tilskudd "
                f"på fem år — og er evaluert {storst['evalueringer_totalt']} ganger noensinne. "
                f"{uten_eval_andel} % av alle tilskuddskroner går gjennom forvaltere som aldri "
                "har vært gjenstand for én eneste evaluering i Kudos."
            ),
        },
        "visninger": {
            "hero": {
                "type": "hero",
                "eyebrow": "Tilskudd og kontroll",
                "rader": [
                    {
                        "etikett": f"Tildelt av {storst['forvalter']}, 2021–2026",
                        "verdi": fmt_kr(storst["sum_tildelt_2021_2026"]),
                        "detalj": (f"landets største tilskuddsforvalter i kroner — men "
                                   f"{storst['evalueringer_totalt']} evalueringer i Kudos noensinne, "
                                   f"{storst['evalueringer_2021_2026']} de siste fem årene"),
                    },
                    {
                        "etikett": "Går gjennom forvaltere uten en eneste evaluering i Kudos",
                        "verdi": f"{uten_eval_andel} %",
                        "detalj": (f"{fmt_kr(uten_eval_sum)} av {fmt_kr(total_sum)} "
                                   "tildelt 2021–2026"),
                    },
                ],
                "fotnote": ("Sum tildelt 2021–2026 fra tilskudd.no koblet mot antall "
                            "evalueringer i Kudos (DFØ), hentet via Kudos' eget "
                            f"tekstbaserte aktørsøk per forvalter. {len(rader)} forvaltere "
                            "med tildelinger i perioden."),
            },
            "storst": {
                "type": "kortgalleri",
                "tittel": "De ti største i kroner — og hvor ofte de evalueres",
                "undertekst": "sum tildelt 2021–2026, mot antall Kudos-evalueringer noensinne",
                "kort": [kort_storst(r) for r in rader_sortert[:10]],
            },
            "uten_kontroll": {
                "type": "kortgalleri",
                "tittel": "Størst blant dem uten en eneste evaluering",
                "undertekst": (f"{len(uten_eval)} av {len(rader)} forvaltere har aldri vært "
                                "evaluert i Kudos — her er de som forvalter mest"),
                "kort": [kort_uten_eval(r) for r in uten_eval_topp],
            },
            "motsatt": {
                "type": "kortgalleri",
                "tittel": "Mange evalueringer, lite penger",
                "undertekst": "forvalterne med desidert flest Kudos-evalueringer blant dem med under 1 mrd kr i tildelinger",
                "kort": [kort_motsatt(r) for r in smaa_men_evaluerte],
            },
        },
    }


def main() -> int:
    print(f"Leser {KILDEFIL} …")
    rader = les_rader()
    print(f"  {len(rader)} forvaltere")

    snapshot = bygg_snapshot(rader)
    feil = valider_snapshot(snapshot, "tilskuddskontroll")
    if feil:
        for f in feil:
            print(f"  ✗ {f}")
        return 1

    UTFIL.parent.mkdir(parents=True, exist_ok=True)
    UTFIL.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"✓ skrev {UTFIL}")
    print("Husk: python3 pipeline/bygg_manifest.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
