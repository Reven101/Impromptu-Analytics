"""Bygger historien «1 941 kvinner, én dør» — alle som har spilt Nora.

Kjøring:

    python pipeline/berik_kjonn.py
    python pipeline/rett_kjonn_rollefigur.py
    python pipeline/bygg_historie_nora.py

IbsenStage fører rollefigur på 187 064 krediteringer. «Nora» er den hyppigste av
425 rollenavn, med 4 832 krediteringer fordelt på 1 941 skuespillere i 90 land
fra 1879 til i dag. Det er den eneste av Ibsen-historiene våre som handler om
mennesker og ikke om strukturer.

Tre valg:

- **Kartet viser årstall, ikke antall.** Samme regel som i spredningshistorien:
  et koroplettkart vekter etter areal, og «hvor mange Noraer» ville gjort Russland
  til hovedpersonen. «Året Nora først gikk ut» er derimot et tidspunkt, der
  arealet ikke lyver.
- **Rollefiguren er ført konsekvent.** Vi matcher strengt på «Nora» i tilfelle
  kilden også bruker varianter som «Nora Helmer». Den gjør ikke det: samtlige
  4 832 krediteringer står som nøyaktig «Nora». En løsere match ville plukket
  opp figurer som heter Nora i andre stykker; sjekk på nytt hvis arkivet endrer praksis.
- **Kjønnet er korrigert mot rollefigur først.** Før korreksjonen sto 59 av
  Nora-spillerne som menn, fordi fornavn som «Tore» normalt er mannsnavn på norsk.
  Etterpå står to igjen — og begge er ekte: Andrus Vaarik spilte også Osvald
  Alving, Burton W. James også Peer Gynt.
"""

from __future__ import annotations

import collections
import json
import os
from pathlib import Path

import kontrakt
from kontrakt import INNHOLD_DIR

RAADATA_DIR = Path(
    os.environ.get("IBSENSTAGE_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ibsenstage"
)
SLUG = "nora"
ROLLE = "Nora"

NORSK_LAND = {
    "Norway": "Norge", "Sweden": "Sverige", "Denmark": "Danmark", "Finland": "Finland",
    "Germany": "Tyskland", "Austria": "Østerrike", "Switzerland": "Sveits",
    "Netherlands": "Nederland", "Belgium": "Belgia", "France": "Frankrike",
    "Italy": "Italia", "Spain": "Spania", "Portugal": "Portugal", "England": "England",
    "Scotland": "Skottland", "Wales": "Wales", "Northern Ireland": "Nord-Irland",
    "Ireland": "Irland", "United States of America": "USA", "Canada": "Canada",
    "Mexico": "Mexico", "Brazil": "Brasil", "Argentina": "Argentina", "Chile": "Chile",
    "Peru": "Peru", "Uruguay": "Uruguay", "Cuba": "Cuba", "Poland": "Polen",
    "Czech Republic": "Tsjekkia", "Slovak Republic": "Slovakia", "Hungary": "Ungarn",
    "Romania": "Romania", "Bulgaria": "Bulgaria", "Greece": "Hellas", "Turkey": "Tyrkia",
    "Russia": "Russland", "Ukraine": "Ukraina", "Estonia": "Estland", "Latvia": "Latvia",
    "Lithuania": "Litauen", "Croatia": "Kroatia", "Serbia": "Serbia",
    "Slovenia": "Slovenia", "Iceland": "Island", "Japan": "Japan", "China": "Kina",
    "South Korea": "Sør-Korea", "India": "India", "Bangladesh": "Bangladesh",
    "Iran": "Iran", "Egypt": "Egypt", "South Africa": "Sør-Afrika",
    "Australia": "Australia", "New Zealand": "New Zealand", "Sri Lanka": "Sri Lanka",
    "Israel": "Israel", "Indonesia": "Indonesia", "Vietnam": "Vietnam",
}


def main() -> None:
    browse = {r["hendelse_id"]: r for r in json.loads(
        (RAADATA_DIR / "ibsenstage_hendelser.json").read_text(encoding="utf-8"))["hendelser"]}
    kjonn = {p["person_id"]: p for p in json.loads(
        (RAADATA_DIR / "ibsenstage_kjonn.json").read_text(encoding="utf-8"))["personer"]}
    kode = {r["land"]: r["landkode"] for r in browse.values()
            if r["land"] and r.get("landkode")}
    if not kode:
        analyse = json.loads((RAADATA_DIR / "ibsenstage_analyse.json")
                             .read_text(encoding="utf-8"))["oppsetninger"]
        kode = {r["land"]: r["landkode"] for r in analyse if r["land"] and r["landkode"]}

    noraer = []
    with (RAADATA_DIR / "ibsenstage_detaljer.jsonl").open(encoding="utf-8") as f:
        for linje in f:
            x = json.loads(linje)
            b_rad = browse.get(x["hendelse_id"]) or {}
            for b in x["bidragsytere"]:
                if (b.get("rollefigur") or "").strip() == ROLLE and b["person_id"]:
                    noraer.append({
                        "aar": b_rad.get("aar"), "land": b_rad.get("land"),
                        "navn": b["navn"], "pid": b["person_id"],
                        "kjonn": kjonn.get(b["person_id"], {}).get("kjonn"),
                    })

    aar = [n["aar"] for n in noraer if n["aar"]]
    personer = collections.Counter(n["pid"] for n in noraer)
    navn_av_pid = {n["pid"]: n["navn"] for n in noraer}

    # Per tiår: antall krediteringer.
    per_tiar = collections.Counter(n["aar"] // 10 * 10 for n in noraer if n["aar"])
    # 2020-tallet stoppes: vi er i 2026, så tiåret er ikke halvveis ferdig. En kort
    # søyle ved siden av fulle tiår leser som et fall, ikke som et ufullstendig tiår.
    # Samme grep som i bygda-savner-barn, av samme grunn.
    tiar_punkter = [[t, per_tiar[t]] for t in sorted(per_tiar) if 1880 <= t <= 2010]

    # Andel av ALL Ibsen. Uten denne kontrollen leser den absolutte kurven som en
    # gjenoppblomstring, men Ibsen som helhet vokser like mye: 2 505 oppsetninger på
    # 1900-tallet mot 4 723 på 2000-tallet. Nora-kurven ER Dukkehjem-kurven, og
    # spørsmålet er om stykket tar mer eller mindre plass — ikke om tallet er større.
    analyse = json.loads((RAADATA_DIR / "ibsenstage_analyse.json")
                         .read_text(encoding="utf-8"))["oppsetninger"]
    alle_tiar = collections.Counter(r["aar"] // 10 * 10 for r in analyse if r["aar"])
    andel_punkter = [[t, round(per_tiar[t] / alle_tiar[t] * 100, 1)]
                     for t in sorted(per_tiar) if 1880 <= t <= 2010 and alle_tiar[t]]

    # Hero: velg tiår, få vite hvor mange, hvor mange kvinner, og hvem som spilte mest.
    oppslag = {}
    for t in sorted(per_tiar):
        if t < 1880:
            continue
        i = [n for n in noraer if n["aar"] and n["aar"] // 10 * 10 == t]
        flest = collections.Counter(n["pid"] for n in i).most_common(1)[0]
        land = collections.Counter(n["land"] for n in i if n["land"]).most_common(1)[0]
        oppslag[f"{t}-tallet"] = {"rader": [
            {"etikett": "Ganger spilt", "verdi": str(len(i)),
             "detalj": f"av {len({n['pid'] for n in i})} ulike skuespillere"},
            {"etikett": "Flest ganger", "verdi": navn_av_pid[flest[0]],
             "detalj": f"{flest[1]} ganger"},
            {"etikett": "Flest oppsetninger", "verdi": NORSK_LAND.get(land[0], land[0]),
             "detalj": f"{land[1]} av {len(i)}"},
        ]}

    # Kart: året Nora først ble spilt i landet. Tidspunkt, ikke volum.
    forste: dict[str, int] = {}
    antall_land: collections.Counter = collections.Counter()
    for n in sorted(noraer, key=lambda n: n["aar"] or 9999):
        k = kode.get(n["land"] or "")
        if not k or not n["aar"]:
            continue
        forste.setdefault(k, n["aar"])
        antall_land[k] += 1
    navn_land = {}
    for land, k in kode.items():
        if k in forste:
            navn_land.setdefault(k, {"GB": "Storbritannia"}.get(
                k, NORSK_LAND.get(land, land)))

    # Kort: de som spilte rollen flest ganger.
    kort = []
    for pid, antall in personer.most_common(4):
        i = [n for n in noraer if n["pid"] == pid]
        aa = [n["aar"] for n in i if n["aar"]]
        # Antall land, ikke det hyppigste landet. Monna Tandberg har 51 av sine 69
        # krediteringer i Norge og resten på turné i sju land; «Norge» alene ville
        # lest som om alle var der — og kollidert med at Norge har 51 i tiåret.
        n_land = len({n["land"] for n in i if n["land"]})
        spenn = f"{min(aa)}" if min(aa) == max(aa) else f"{min(aa)}–{max(aa)}"
        detalj = f"{spenn}, {n_land} land" if n_land > 1 else f"{spenn}, ett land"
        kort.append({"overtittel": navn_av_pid[pid], "verdi": f"{antall} ganger",
                     "detalj": detalj})

    en_gang = sum(1 for v in personer.values() if v == 1)
    kvinner = sum(1 for pid in personer
                  if kjonn.get(pid, {}).get("kjonn") == "kvinne")
    # Hardt mellomrom som tusenskille, slik huset skriver store tall. Formateres
    # for seg: en replace(",") på hele tittelen tok også kommaet i «kvinner, én dør».
    kvinner_tekst = f"{kvinner:,}".replace(",", " ")

    data = {
        "meta": {
            # Tittelen teller KVINNER, ikke skuespillere: av de 1 941 som har
            # spilt rollen er to menn (ekte rollebytte) og to ubestemte.
            "tittel": f"{kvinner_tekst} kvinner, én dør",
            "kilde": "IbsenStage, Universitetet i Oslo",
            "kilde_url": "https://ibsenstage.hf.uio.no/",
            "dato_hentet": "2026-08-28",
            "geografi": "90 land",
            "enhet": "krediteringer",
            "oppdateringsfrekvens": "Løpende",
            "beskrivelse": (
                f"{len(personer)} skuespillere har spilt Nora i {len({n['land'] for n in noraer if n['land']})} "
                f"land siden 1879 — og {round(en_gang / len(personer) * 100)} prosent av dem "
                "gjorde det bare én gang."
            ),
        },
        "visninger": {
            "hero": {
                "type": "hero",
                "eyebrow": f"{len(noraer)} ganger, {min(aar)}–{max(aar)}",
                "kontroll": {"etikett": "Velg tiår", "standard": "2000-tallet"},
                "oppslag": oppslag,
                "fotnote": (
                    "Rollefiguren er ført av arkivarene ved Senter for Ibsen-studier. "
                    "Skuespillernes kjønn er utledet av fornavn og korrigert mot "
                    "rollefigur; se datanotatet."
                ),
            },
            "kart": {
                "type": "verdenskart",
                "tittel": "Året Nora først gikk ut",
                "undertekst": "Første registrerte oppsetning med rollen i landet",
                "enhet": "",
                "verdier": forste,
                "navn": navn_land,
                "antall": dict(antall_land),
                "antall_navn": "Ganger spilt",
                "tom_etikett": "ingen registrert Nora",
                "skala": "kvantil",
            },
            "tiar": {
                "type": "tidslinje",
                "stil": "søyle",
                "tittel": "To topper, hundre år fra hverandre",
                "undertekst": "Krediteringer i rollen som Nora, hele tiår",
                "enhet": "ganger",
                "x_navn": "Tiår",
                "serier": [{"navn": "Nora", "punkter": tiar_punkter}],
            },
            "andel": {
                "type": "tidslinje",
                "tittel": "Men andelen var størst da stykket var nytt",
                "undertekst": "Nora-krediteringer som andel av alle Ibsen-oppsetninger",
                "enhet": "%",
                "x_navn": "Tiår",
                "serier": [{"navn": "Nora", "punkter": andel_punkter}],
            },
            "flest": {
                "type": "kortgalleri",
                "tittel": "De som gikk ut igjen og igjen",
                "undertekst": "Flest krediteringer i rollen",
                "kort": kort,
            },
        },
    }

    data, notater = kontrakt.flett_redaksjon(data, SLUG)
    mappe = INNHOLD_DIR / SLUG
    mappe.mkdir(parents=True, exist_ok=True)
    (mappe / "data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if notater:
        print(f"  redaksjon.json overstyrer {len(notater)} felt")

    feil = kontrakt.valider_snapshot(data, SLUG)
    print(f"{SLUG}: {len(noraer)} krediteringer, {len(personer)} skuespillere, "
          f"{len(forste)} land på kartet")
    print(f"  {en_gang} spilte rollen én gang ({en_gang / len(personer) * 100:.0f} %)")
    print(f"  kjønn: {dict(collections.Counter(n['kjonn'] for n in noraer))}")
    print(f"  validering: {'OK' if not feil else feil}")


if __name__ == "__main__":
    main()
