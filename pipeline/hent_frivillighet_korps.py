"""Skriver snapshot til innhold/bygda-savner-barn/data.json.

Kjøring (krever nett mot data.brreg.no og data.ssb.no):

    python pipeline/hent_frivillighet_korps.py
    python pipeline/bygg_manifest.py

Første kjøring laster ned Enhetsregisteret (~210 MB) og henter 5 800 styrer og
hele Frivillighetsregisteret. Regn med et kvarter. Alt caches utenfor repoet,
så senere kjøringer tar under et minutt. `--tving-nedlasting` henter registeret
på nytt selv om cachen er fersk.

Datagrunnlaget og forbeholdene er dokumentert i
historier/innhold/bygda-savner-barn/DATANOTAT.md.
"""

from __future__ import annotations

import collections
import json
import statistics
import sys
from datetime import date

import kulturforeninger as kf
from kontrakt import INNHOLD_DIR, valider_snapshot

SLUG = "bygda-savner-barn"
UTFIL = INNHOLD_DIR / SLUG / "data.json"

# Serien starter i 2000. Før det er frafallet blant organisasjoner som ikke
# lenger finnes så stort at «stiftet per år» blir aldersprofil, ikke stiftelsestakt.
FRA_AAR = 2000
BARNEALDRE = [f"{a:03d}" for a in range(6, 16)]  # skolekorpsenes rekrutteringsgrunnlag
KATEGORIER = ["skolekorps", "voksenkorps", "kor", "teater", "tradisjon"]

FYLKESNAVN = {
    "03": "Oslo", "11": "Rogaland", "15": "Møre og Romsdal", "18": "Nordland",
    "31": "Østfold", "32": "Akershus", "33": "Buskerud", "34": "Innlandet",
    "39": "Vestfold", "40": "Telemark", "42": "Agder", "46": "Vestland",
    "50": "Trøndelag", "55": "Troms", "56": "Finnmark",
}


def stiftelsesaar(e: dict) -> int | None:
    """Stiftelsesåret, eller None hvis det ikke er til å stole på.

    Enhetsregisteret ble opprettet i 1995, og for organisasjoner som var
    stiftet lenge før, ble stiftelsesdatoen mange steder satt lik
    registreringsdatoen. Utslaget er dramatisk: 61 skolekorps står som
    «stiftet» i 1995, mot ett til fire i hvert av årene rundt. Å forkaste
    radene der de to datoene er identiske fjerner 54 av de 61 — og nesten
    ingenting utenfor 1995, siden en organisasjon sjelden rekker å bli
    registrert samme dag den stiftes.
    """
    if not e["stiftet"] or e["stiftet"] == e["registrert"]:
        return None
    return int(e["stiftet"][:4])


def bygg_snapshot(org: list[dict], styrer: dict, frivillig: dict,
                  folk: dict, barn: dict, finn, fylkesbarn: dict,
                  siste_aar: int) -> dict:
    fmt = lambda n: f"{n:,}".replace(",", " ")  # noqa: E731
    per_kat = lambda k: [e for e in org if e["kat"] == k]  # noqa: E731

    # ---- stiftet per år, per kategori
    stiftet: dict[str, collections.Counter] = {
        k: collections.Counter() for k in KATEGORIER}
    for e in org:
        a = stiftelsesaar(e)
        if a is not None:
            stiftet[e["kat"]][a] += 1

    aar = list(range(FRA_AAR, siste_aar + 1))
    serie = lambda k: [[a, stiftet[k].get(a, 0)] for a in aar]  # noqa: E731

    # ---- aldersprofil for dagens bestand
    profil = {}
    for k in KATEGORIER:
        aarene = sorted(a for a in (stiftelsesaar(e) for e in per_kat(k)) if a)
        profil[k] = {
            "antall": len(per_kat(k)),
            "median": int(statistics.median(aarene)),
            "for_1990": sum(1 for a in aarene if a < 1990) / len(aarene),
            "siste_ti": sum(1 for a in aarene if a > siste_aar - 10),
            "forrige_ti": sum(1 for a in aarene if siste_aar - 20 < a <= siste_aar - 10),
        }

    # ---- styrealder (fødselsår -> alder ved utgangen av siste hele år)
    styre = {}
    for k in KATEGORIER:
        aldre = sorted(siste_aar - y for e in per_kat(k)
                       for y in styrer.get(e["orgnr"], {}).get("aar", []))
        styre[k] = {
            "antall": len(aldre),
            "median": int(statistics.median(aldre)),
            "andel_60": sum(1 for a in aldre if a >= 60) / len(aldre),
            "andel_u40": sum(1 for a in aldre if a < 40) / len(aldre),
        }

    # ---- kommunetyper: vekst, stabil, nedgang 2010 -> i år
    fra, til = str(siste_aar - 16), str(siste_aar + 1)
    bøtter: dict[str, list[str]] = collections.defaultdict(list)
    for g, nå in folk[til].items():
        før = folk[fra].get(g)
        if not før:
            continue
        endring = nå / før - 1
        bøtter["vekst" if endring >= 0.05 else
               "nedgang" if endring <= -0.05 else "stabil"].append(g)

    per_gruppe: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    nye_gruppe: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for e in org:
        if not e["knr"]:
            continue
        g = finn(e["knr"])
        per_gruppe[g][e["kat"]] += 1
        a = stiftelsesaar(e)
        if a is not None and int(fra) <= a <= siste_aar:
            nye_gruppe[g][e["kat"]] += 1

    kommunetype = {}
    for navn, grupper in bøtter.items():
        sum_over = lambda d, k: sum(d[g][k] for g in grupper)  # noqa: E731
        f_nå = sum(folk[til][g] for g in grupper)
        f_før = sum(folk[fra][g] for g in grupper)
        b_nå = sum(barn[til].get(g, 0) for g in grupper)
        b_før = sum(barn[fra].get(g, 0) for g in grupper)
        kommunetype[navn] = {
            "kommuner": len(grupper),
            "folketall": f_nå,
            "folkevekst": f_nå / f_før - 1,
            "barnevekst": b_nå / b_før - 1,
            "skolekorps": sum_over(per_gruppe, "skolekorps"),
            "korps_per_1000_barn": sum_over(per_gruppe, "skolekorps") / b_nå * 1000,
            "kor_per_10000": sum_over(per_gruppe, "kor") / f_nå * 10000,
            "nye_skolekorps": sum_over(nye_gruppe, "skolekorps"),
            "nye_kor": sum_over(nye_gruppe, "kor"),
        }

    # ---- fylkeskart: skolekorps per 1000 barn 6-15
    per_fylke: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for e in org:
        if e["knr"]:
            per_fylke[e["knr"][:2]][e["kat"]] += 1
    kart = {f: round(per_fylke[f]["skolekorps"] / fylkesbarn[f] * 1000, 2)
            for f in kf.FYLKER if fylkesbarn.get(f)}
    topp = max(kart, key=kart.get)
    bunn = min(kart, key=kart.get)

    # ---- Frivillighetsregisteret: registerets egen koding som kontroll
    i_frivillig = [e for e in org if e["orgnr"] in frivillig]
    kunst_kultur = sum(1 for e in i_frivillig
                       if "1100" in frivillig[e["orgnr"]]["icnpo"])
    grasrot = sum(1 for e in i_frivillig if frivillig[e["orgnr"]]["grasrot"])

    n_sk = stiftet["skolekorps"].get(siste_aar, 0)
    n_kor = stiftet["kor"].get(siste_aar, 0)
    nedgang = kommunetype["nedgang"]
    # Formuleres om null faktisk er null — en ny kjøring kan gi 1, og da skal
    # ikke forsideteksten fortsatt påstå «ikke ett eneste».
    n_ny = nedgang["nye_skolekorps"]
    ingen = ("ikke stiftet ett eneste nytt skolekorps" if n_ny == 0
             else f"stiftet {n_ny} nye skolekorps")

    return {
        "meta": {
            "tittel": "Bygda savner barn, ikke korps",
            "kilde": "Brønnøysundregistrene og Statistisk sentralbyrå",
            "kilde_url": "https://data.brreg.no/enhetsregisteret/api/dokumentasjon",
            "dato_hentet": date.today().isoformat(),
            "geografi": "Norge, fylker",
            "enhet": "organisasjoner",
            "oppdateringsfrekvens": "daglig",
            "beskrivelse": (
                f"Skolekorpsene står tettest der folketallet faller — men i de "
                f"{nedgang['kommuner']} kommunene med befolkningsnedgang er det "
                f"{ingen} siden {fra}."),
        },
        "visninger": {
            "hero": {
                "type": "hero",
                "eyebrow": f"Stiftet i {siste_aar}",
                "rader": [
                    {"etikett": "Nye skolekorps",
                     "verdi": str(n_sk),
                     "detalj": f"av {fmt(profil['skolekorps']['antall'])} som finnes i dag"},
                    {"etikett": "Nye kor og songlag",
                     "verdi": str(n_kor),
                     "detalj": f"av {fmt(profil['kor']['antall'])} som finnes i dag"},
                    {"etikett": "Median stiftelsesår, skolekorps",
                     "verdi": str(profil["skolekorps"]["median"]),
                     "detalj": f"for kor er medianen {profil['kor']['median']}"},
                ],
                "fotnote": ("Foreninger i Enhetsregisteret sortert på navn. "
                            "Tellingen gjelder organisasjoner som står i registeret i dag."),
            },
            "nystiftet": {
                "type": "tidslinje",
                "tittel": f"Nystiftede foreninger per år, {FRA_AAR}–{siste_aar}",
                "undertekst": "organisasjoner som fortsatt står i registeret",
                "enhet": "nye foreninger",
                "serier": [
                    {"navn": "Teater og revy", "punkter": serie("teater")},
                    {"navn": "Kor og songlag", "punkter": serie("kor")},
                    {"navn": "Skolekorps", "punkter": serie("skolekorps")},
                ],
            },
            "bestand": {
                "type": "tidslinje",
                "stil": "søyle",
                "tittel": "Skolekorpsene vi har, etter stiftelsestiår",
                # Bare hele tiår: en halvferdig 2020-søyle ville lest som fall.
                # 75 av 829 faller derfor utenfor — 61 uten brukbar dato, 13 i
                # 2020-årene, ett før 1900.
                "undertekst": "dagens bestand fordelt på tiåret de ble stiftet, 1900–2019",
                "enhet": "skolekorps",
                "x_navn": "Tiår (fra år)",
                "serier": [{"navn": "Skolekorps", "punkter": [
                    [t, sum(v for a, v in stiftet["skolekorps"].items() if t <= a < t + 10)]
                    for t in range(1900, siste_aar - 8, 10)]}],
            },
            "fylkeskart": {
                "type": "kart",
                "tittel": "Hvor står korpsene tettest?",
                "undertekst": f"skolekorps per 1000 barn 6–15 år, {siste_aar + 1}",
                "enhet": "skolekorps per 1000 barn",
                "verdier": kart,
            },
            "kommunetype": {
                "type": "kortgalleri",
                "tittel": "Kulturlivet er tettest der folk blir færre",
                "undertekst": f"kommuner gruppert etter folketallsendring {fra}–{til}",
                "kort": [
                    {"overtittel": f"Vekst (+{kommunetype['vekst']['folkevekst']:.0%})",
                     "verdi": f"{kommunetype['vekst']['korps_per_1000_barn']:.2f}".replace(".", ","),
                     "detalj": (f"skolekorps per 1000 barn · "
                                f"{kommunetype['vekst']['kommuner']} kommuner · "
                                f"{kommunetype['vekst']['nye_skolekorps']} nye korps siden {fra}")},
                    {"overtittel": f"Stabil ({kommunetype['stabil']['folkevekst']:+.0%})",
                     "verdi": f"{kommunetype['stabil']['korps_per_1000_barn']:.2f}".replace(".", ","),
                     "detalj": (f"skolekorps per 1000 barn · "
                                f"{kommunetype['stabil']['kommuner']} kommuner · "
                                f"{kommunetype['stabil']['nye_skolekorps']} nye korps siden {fra}")},
                    {"overtittel": f"Nedgang ({nedgang['folkevekst']:.0%})",
                     "verdi": f"{nedgang['korps_per_1000_barn']:.2f}".replace(".", ","),
                     "detalj": (f"skolekorps per 1000 barn · "
                                f"{nedgang['kommuner']} kommuner · "
                                f"{nedgang['nye_skolekorps']} nye korps siden {fra}")},
                ],
            },
            "styret": {
                "type": "kortgalleri",
                "tittel": "Hvem sitter i styret?",
                "undertekst": f"medianalder blant sittende styremedlemmer, {siste_aar}",
                "kort": [
                    {"overtittel": kf.KATEGORINAVN[k],
                     "verdi": f"{styre[k]['median']} år",
                     "detalj": (f"{styre[k]['andel_60']:.0%} er 60 eller eldre · "
                                f"{fmt(styre[k]['antall'])} styremedlemmer")}
                    for k in ["skolekorps", "teater", "voksenkorps", "kor", "tradisjon"]
                ],
            },
        },
        # Tall teksten viser til, samlet så de ikke driver fra hverandre.
        "_noekkeltall": {
            "siste_aar": siste_aar,
            "totalt": len(org),
            "profil": profil,
            "styre": styre,
            "kommunetype": kommunetype,
            "fylke_topp": [FYLKESNAVN[topp], kart[topp]],
            "fylke_bunn": [FYLKESNAVN[bunn], kart[bunn]],
            "frivillighetsregisteret": {
                "av_vaare": len(i_frivillig),
                "andel_kunst_kultur": kunst_kultur / len(i_frivillig),
                "andel_grasrot": grasrot / len(i_frivillig),
            },
        },
    }


def main() -> int:
    tving = "--tving-nedlasting" in sys.argv
    siste_aar = date.today().year - 1  # siste hele kalenderår

    print("1/5  Enhetsregisteret")
    org = kf.les_foreninger(kf.last_ned_registeret(tving))

    print("2/5  Frivillighetsregisteret")
    frivillig = kf.hent_frivillighetsregisteret()

    print("3/5  styrer (Brreg /roller)")
    styrer = kf.hent_styrer([e["orgnr"] for e in org])

    print("4/5  SSB folketall")
    aar = [str(siste_aar - 16), str(siste_aar + 1)]
    folk, finn = kf.grupper_folketall(aar)
    barn, _ = kf.grupper_folketall(aar, BARNEALDRE)
    fylkesbarn = kf.ssb_folketall(kf.FYLKER, [str(siste_aar + 1)], BARNEALDRE)[str(siste_aar + 1)]
    print(f"  {len(folk[aar[0]])} sammenlignbare kommunegrupper, "
          f"{sum(folk[aar[1]].values())} innbyggere")

    print("5/5  bygger snapshot")
    snapshot = bygg_snapshot(org, styrer, frivillig, folk, barn, finn,
                             fylkesbarn, siste_aar)

    feil = valider_snapshot(snapshot, SLUG)
    if feil:
        for f in feil:
            print(f"  ✗ {f}")
        return 1

    UTFIL.parent.mkdir(parents=True, exist_ok=True)
    UTFIL.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
    print(f"✓ skrev {UTFIL}")
    print("Husk: python pipeline/bygg_manifest.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
