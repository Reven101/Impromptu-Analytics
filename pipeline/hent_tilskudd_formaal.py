"""Bygger datahistorien om hva statlige tilskuddskroner faktisk skal brukes til.

Leser tilskudd.no-eksporten og formålskategoriene fra kategoriser_formaal.py, og skriver
historier/innhold/tilskudd-formaal/data.json etter metadata-kontrakten.

Kjør kategoriser_formaal.py først — dette scriptet kaller ingen modell, det bare leser
snapshotet den la igjen.

    python pipeline/kategoriser_formaal.py --kroner 40000
    python pipeline/hent_tilskudd_formaal.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kategoriser_formaal import (
    CACHE_FIL,
    KATEGORIER,
    belop,
    csv_sti,
    er_formelstyrt,
    fritekst,
    les_rader,
    nokkel,
)
from kontrakt import INNHOLD_DIR, valider_snapshot

SLUG = "tilskudd-formaal"
KILDE_URL = "https://tilskudd.no"

# 2026 er inneværende budsjettår og bare delvis rapportert; alt etter er ubehandlede
# søknader, ikke tildelinger. Begge deler ville laget et falskt fall i tidslinjen.
AR_FRA, AR_TIL = 2021, 2025

# Lesbare navn til visningene. Rekkefølgen i KATEGORIER er teknisk; denne er redaksjonell.
NAVN = {
    "arrangement": "Arrangement",
    "drift_og_administrasjon": "Drift",
    "anlegg_og_utstyr": "Anlegg og utstyr",
    "produksjon_og_utgivelse": "Produksjon og utgivelse",
    "opplaering_og_kompetanse": "Opplæring",
    "inkludering_og_deltakelse": "Inkludering",
    "helse_og_omsorg": "Helse og omsorg",
    "beredskap_og_redning": "Beredskap og redning",
    "forskning_og_utredning": "Forskning og utredning",
    "informasjon_og_formidling": "Informasjon og formidling",
    "internasjonalt_samarbeid": "Internasjonalt samarbeid",
    "bevaring_og_vedlikehold": "Bevaring og vedlikehold",
    "annet": "Annet",
    "uklar_beskrivelse": "Ingen oppgitt beskrivelse",
}


def mrd(kr: float) -> str:
    return f"{kr / 1e9:.1f}".replace(".", ",") + " mrd kr"


def prosent(del_: float, av: float) -> str:
    return f"{del_ / av * 100:.0f} %".replace(".", ",")


def samle() -> dict:
    cache = json.loads(CACHE_FIL.read_text(encoding="utf-8"))
    modell = cache["metode"]["modell"]
    oppslag = cache["kategorier"]

    tot = defaultdict(float)
    per_kategori: Counter = Counter()
    per_ar: dict[int, Counter] = defaultdict(Counter)
    ukjent_kr = 0.0

    for rad in les_rader():
        try:
            ar = int((rad.get("budsjettar") or "").strip())
        except ValueError:
            continue
        if not AR_FRA <= ar <= AR_TIL:
            continue

        kr = belop(rad)
        tekst = fritekst(rad)
        tot["alle"] += kr
        tot["rader"] += 1

        if len(tekst) < 12 or er_formelstyrt(rad, tekst):
            tot["formel"] += kr
            continue

        tot["beskrevet"] += kr
        treff = oppslag.get(nokkel(tekst, modell))
        if not treff:
            # Utenfor det som er kategorisert (den lange halen av småbeløp).
            ukjent_kr += kr
            continue

        per_kategori[treff["kategori"]] += kr
        per_ar[ar][treff["kategori"]] += kr

    return {
        "modell": modell,
        "dato_kjort": cache["metode"]["dato_kjort"],
        "tot": dict(tot),
        "ukjent_kr": ukjent_kr,
        "per_kategori": per_kategori,
        "per_ar": per_ar,
    }


def bygg_visninger(d: dict) -> dict:
    tot = d["tot"]
    per_kategori = d["per_kategori"]
    kategorisert_kr = sum(per_kategori.values())
    dekning = kategorisert_kr / tot["beskrevet"] * 100

    uten_formaal = tot["formel"] + per_kategori["uklar_beskrivelse"]
    andel_uten = uten_formaal / tot["alle"] * 100

    hero = {
        "type": "hero",
        "eyebrow": f"Statlige tilskudd {AR_FRA}–{AR_TIL}",
        "rader": [
            {
                "etikett": "Utbetalt i tilskudd",
                "verdi": mrd(tot["alle"]),
                "detalj": f"{tot['rader']:,.0f} tildelinger".replace(",", " "),
            },
            {
                "etikett": "Fordelt etter formel",
                "verdi": prosent(tot["formel"], tot["alle"]),
                "detalj": "momskompensasjon, grasrotandel, partistøtte, trossamfunn — ingen søknad om et bestemt tiltak",
            },
            {
                "etikett": "Uten oppgitt formål i det hele tatt",
                "verdi": f"minst {andel_uten:.0f} %",
                "detalj": "formelstyrt, eller beskrevet med bare en tittel",
            },
        ],
        "fotnote": (
            f"Tildelte beløp {AR_FRA}–{AR_TIL} fra tilskudd.no. Formålskategoriene er "
            f"maskinelt utledet fra fritekstfeltene med språkmodellen {d['modell']} "
            f"({d['dato_kjort']}); de dekker {dekning:.0f} % av kronene med beskrivelse."
        ),
    }

    # Kortgalleriet handler om tilskudd som FAKTISK beskriver et formål, så de uklare må
    # ut av både lista og nevneren. Blir de stående i nevneren, blir hver andel for lav.
    rangert = [(k, v) for k, v in per_kategori.most_common() if k != "uklar_beskrivelse"]
    med_formaal_kr = sum(v for _, v in rangert)
    kortgalleri = {
        "type": "kortgalleri",
        "tittel": "Hva pengene skal brukes til",
        "undertekst": (
            f"tildelte kroner {AR_FRA}–{AR_TIL}, blant tilskuddene som faktisk beskriver "
            "et formål"
        ),
        "kort": [
            {
                "overtittel": NAVN[k],
                "verdi": mrd(v),
                "detalj": prosent(v, med_formaal_kr) + " av kronene med oppgitt formål",
            }
            for k, v in rangert[:8]
        ],
    }

    topp = [k for k, _ in rangert[:5]]
    tidslinje = {
        "type": "tidslinje",
        "tittel": "De fem største formålene over tid",
        "undertekst": "tildelte kroner per budsjettår",
        "enhet": "mrd kr",
        "serier": [
            {
                "navn": NAVN[k],
                "punkter": [
                    [ar, round(d["per_ar"][ar][k] / 1e9, 3)]
                    for ar in range(AR_FRA, AR_TIL + 1)
                ],
            }
            for k in topp
        ],
    }

    return {"hero": hero, "formaal": kortgalleri, "utvikling": tidslinje}, {
        "dekning": dekning,
        "andel_uten": andel_uten,
        "kategorisert_kr": kategorisert_kr,
    }


def main() -> int:
    if not CACHE_FIL.exists():
        raise SystemExit(
            f"Fant ikke {CACHE_FIL.name}. Kjør kategoriser_formaal.py først."
        )

    print(f"Leser {csv_sti().name} …")
    d = samle()
    visninger, n = bygg_visninger(d)
    tot = d["tot"]

    print(f"\nKontrolltall {AR_FRA}–{AR_TIL}")
    print(f"  Alle tildelinger      {mrd(tot['alle']):>14s}  ({tot['rader']:,.0f} rader)")
    print(f"  Formelstyrt           {mrd(tot['formel']):>14s}  "
          f"({tot['formel'] / tot['alle'] * 100:.1f} %)")
    print(f"  Med beskrivelse       {mrd(tot['beskrevet']):>14s}")
    print(f"    – kategorisert      {mrd(n['kategorisert_kr']):>14s}  "
          f"({n['dekning']:.1f} % av de beskrevne)")
    print(f"    – utenfor kjøringen {mrd(d['ukjent_kr']):>14s}")
    print(f"\n  Uten oppgitt formål:  {n['andel_uten']:.1f} % av alle kroner")

    print(f"\n{'kategori':30s} {'mrd kr':>9s} {'andel':>7s}")
    for k, v in d["per_kategori"].most_common():
        print(f"{NAVN[k]:30s} {v / 1e9:9.2f} {v / n['kategorisert_kr'] * 100:6.1f}%")

    if n["dekning"] < 90:
        raise SystemExit(
            f"\n✗ Bare {n['dekning']:.1f} % av de beskrevne kronene er kategorisert. "
            "Kjør kategoriser_formaal.py med flere tekster før historien publiseres."
        )

    data = {
        "meta": {
            "tittel": "Pengene uten formål",
            "kilde": "tilskudd.no (Lotteri- og stiftelsestilsynet)",
            "kilde_url": KILDE_URL,
            "dato_hentet": date.today().isoformat(),
            "geografi": "Norge",
            "enhet": "tildelte kroner",
            "oppdateringsfrekvens": "årlig",
            "beskrivelse": (
                f"Staten delte ut {mrd(tot['alle'])} i tilskudd {AR_FRA}–{AR_TIL}. "
                f"For minst {n['andel_uten']:.0f} % av kronene står det ingen steder "
                "hva de skulle brukes til."
            ).replace(".0 %", " %"),
            "utkast": True,
        },
        "visninger": visninger,
    }

    feil = valider_snapshot(data, SLUG)
    if feil:
        raise SystemExit("Kontraktsbrudd:\n  " + "\n  ".join(feil))

    mappe = INNHOLD_DIR / SLUG
    mappe.mkdir(parents=True, exist_ok=True)
    (mappe / "data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n✓ Skrevet {mappe / 'data.json'}")
    print("  Merket som utkast — fjern meta.utkast når teksten er faktasjekket.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
