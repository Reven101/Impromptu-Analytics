"""Henter skoletall for de videregående skolene i Oslo fra Udirs statistikkbank.

Kjøring:

    python pipeline/hent_udir_vgs_oslo.py            # alt, ~2 minutter
    python pipeline/hent_udir_vgs_oslo.py --ut <mappe>

Skriver rådata UTENFOR repoet, til impromptu_raadata/udir/ (eller UDIR_DIR):

    vgs_oslo.json        alle tabellene + metadata (kilde, dato, filtre)
    vgs_oslo_<tabell>.csv  samme tabeller, for pandas

Tallene er offentlig aggregatstatistikk, men dette er fortsatt rådata: det
byggescriptet for historien trekker ut, er det som sjekkes inn.

Hva som hentes, for hele landet, Oslo og hver Oslo-skole, splittet på eierform
(alle/offentlig/privat) og kjønn (alle/gutt/jente):

    karakterer   snitt per fellesfag, skriftlig eksamen og standpunkt, 2007-08 →
    fravaer      median fraværsdager/-timer, totalt og vitnemålsfravær, 2013-14 →
    sluttet      andel som sluttet i løpet av skoleåret, 2011-12 →
    euv          Elevundersøkelsen Vg1: indikatorer (trivsel, mestring …), 2021-22 →
    mobbing      Elevundersøkelsen Vg1: andel mobbet, 2021-22 →
    deltakelse   Elevundersøkelsen: andel elever som svarte (ikke kjønn), 2021-22 →
    skoler       utledet: én rad per Oslo-skole med eierform

Kildene er to forskjellige grensesnitt i samme system — se
api-atlas/eksempler/hent_udir_statistikkbank.py for hele kartleggingen:

- Karakterer, fravær og sluttet: rapport-endepunktene statistikkbankens
  nettsider selv kaller. Udokumentert, og Udir sier det endres uten varsel.
- Elevundersøkelsen: det åpne eksport-API-et (v2).

Feller scriptet håndterer, målt september 2026:

- Beskrivelsene av eksport 153 og 154 er byttet om i tabellista: 154 har
  mobbetallene (AndelMobbet), 153 har temaspørsmålene. Scriptet velger derfor
  på feltnavn, ikke på beskrivelse.
- Elevundersøkelsen for vgs har ikke «alle trinn». Vg1 brukes fordi det er
  trinnet der undersøkelsen er obligatorisk.
- Fagkodene skifter ved læreplanreformer (NOR1267 finnes bare fra
  fagfornyelsen). Scriptet lagrer fagkode OG fagnavn; skjøting av tidsserier
  er byggescriptets beslutning, ikke hentingens.
- "*" er skjermet (prikket), "" er ingen data. Begge blir None, men prikkingen
  lagres som eget flagg — en skole med prikket snitt er ikke en skole uten elever.
- Kjønn per SKOLE publiseres bare for karakterer (og der er mye prikket).
  Fravær og sluttet har kjønn for Oslo og landet, men tomme celler per skole.
  Det er Udirs publisering, ikke en feil her — kontrolltallene viser det.
- Med eierform × kjønn er de fleste cellene tomme (en offentlig skole har
  ingenting under «Privat eiet»). Tomme kombinasjoner droppes; prikkede beholdes.
- Vgs-hierarkiet er Nasjonalt.Fylke.Skole, uten kommunenivå. Skoleradene har
  EnhetID som siste ledd i rad-id-en; fylkes- og landsradene har det IKKE
  (Oslo-raden heter "1.3", mens Oslo har EnhetID -17).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import date
from pathlib import Path

import kontrakt  # noqa: F401  (setter UTF-8 på Windows-konsollen)
from nett import hent_json

BRUKERAGENT = "Impromptu-Analytics/1.0 (kontakt@impromptu.no)"
RAPPORT = "https://statistikkportalen.udir.no/api/rapportering/"
EKSPORT = "https://api.statistikkbanken.udir.no/api/rest/v2/Eksport/"
KILDE_URL = "https://www.udir.no/tall-og-forskning/statistikk/statistikk-videregaende-skole/"

RAADATA_DIR = Path(
    os.environ.get("UDIR_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "udir"
)

OSLO_FYLKE = -17        # EnhetID for Oslo (fylkesnivå) i vgs-hierarkiet
HELE_LANDET = -12
ALLE = -10
VG1 = 10
EIERFORMER = [ALLE, 8, 2]   # alle, offentlig skole, privat eiet
KJONN = [ALLE, 2, 1]        # alle, gutt, jente
FELLESFAG = -12         # FagID-gruppe: alle fellesfag

# Karaktertypene vi vil ha; muntlig eksamen er for tynt per skole til å si noe.
KARAKTERTYPER = {3: "Skriftlig eksamen", 1: "Standpunkt"}

# Eksport-tabellene for Elevundersøkelsen vgs. Beskrivelsene i tabellista er
# upålitelige (se over), så hver tabell valideres på feltene den skal ha.
EUV_INDIKATOR, EUV_MOBBING, EUV_DELTAKELSE = 152, 154, 243
EUV_FORVENTET_FELT = {
    EUV_INDIKATOR: "Score",
    EUV_MOBBING: "AndelMobbet",
    EUV_DELTAKELSE: "AndelDeltatt",
}


# ---------------------------------------------------------------- hjelpere

def hent(url: str) -> dict | list:
    return hent_json(url, BRUKERAGENT, timeout=300)


def tall(tekst) -> tuple[float | None, bool]:
    """'5 943' → 5943.0, '-  4,5' → -4.5. Returnerer (verdi, prikket)."""
    if tekst is None:
        return None, False
    t = str(tekst).strip()
    if t == "*":
        return None, True
    t = t.replace(" ", "").replace(" ", "").replace(",", ".")
    if t in ("", "-"):
        return None, False
    try:
        return float(t), False
    except ValueError:
        raise SystemExit(f"Uventet tallformat fra Udir: {tekst!r}. "
                         "Har formatet endret seg? Sjekk statistikkbanken.")


def filterstreng(filtre: dict[str, list[int]]) -> str:
    return "_".join(f"{k}({'_'.join(str(v) for v in verdier)})" for k, verdier in filtre.items())


def skoleaar_navn(tekst: str) -> str:
    """'Foreløpige tall 2025-26' → '2025-26'. Foreløpige tall merkes separat."""
    m = re.search(r"\d{4}-\d{2}", tekst)
    if not m:
        raise SystemExit(f"Fant ikke skoleår i kolonnehodet {tekst!r}")
    return m.group(0)


# ---------------------------------------------------------- rapport (vei B)

def rapportside(kode: str) -> dict:
    return hent(f"{RAPPORT}rest/v1/Rapportside/{kode}")["rappside"]


def rapport_pivot(side: dict, filtre: dict, radsti: str) -> tuple[list[list[str]], list[dict]]:
    """Returnerer (kolonnehoder, rader). Kolonnehodet er foldet ut til én liste
    med ledd per kolonne, øverste nivå først."""
    ep = side["rapportElementer"][0]["dataEndepunkt"]
    params = urllib.parse.urlencode({"filter": filterstreng(filtre), "radSti": radsti})
    svar = hent(f"{RAPPORT}{ep}?{params}")
    nivaaer = svar["metadata"]["columns"]
    utfoldet = [[c["name"] for c in nivaa for _ in range(c["columnCount"])] for nivaa in nivaaer]
    hoder = [list(ledd) for ledd in zip(*utfoldet)]
    for r in svar["rows"]:
        if len(r["data"]) != len(hoder):
            raise SystemExit(f"{side['kode']}: rad {r['id']} har {len(r['data'])} verdier, "
                             f"kolonnehodet {len(hoder)}. Pivotformatet har endret seg.")
    return hoder, svar["rows"]


def enhetsoppslag(side: dict) -> dict[int, dict]:
    ep = side["rapportElementer"][0]["dataEndepunkt"]
    fv = hent(RAPPORT + ep.replace("/data", "/filterVerdier"))
    return fv


def klassifiser_rad(sti: list[str], enheter: dict[int, dict]) -> dict | None:
    """sti = hierarkidelen av rad-id-en (uten fag-prefiks): ['1'], ['1','3'], ['1','3','6119'].

    Returnerer enhetsinfo, eller None for rader utenfor Oslo.
    """
    if sti[0] != "1":
        return None  # "2" er Utlandet — norske skoler i utlandet, egen gren
    if sti == ["1"]:
        return {"nivaa": "land", "enhet_id": HELE_LANDET, "orgnr": None}
    if len(sti) >= 2 and sti[1] != "3":
        return None
    if sti == ["1", "3"]:
        return {"nivaa": "fylke", "enhet_id": OSLO_FYLKE, "orgnr": None}
    if len(sti) == 3:
        eid = int(sti[2])
        e = enheter.get(eid)
        if e is None:
            raise SystemExit(f"Skole-ID {eid} i Oslo finnes ikke i filterVerdier. "
                             "Har rad-id-ene sluttet å være EnhetID?")
        return {"nivaa": "skole", "enhet_id": eid, "orgnr": e["kode"]}
    raise SystemExit(f"Uventet rad-sti {'.'.join(sti)} — har hierarkiet fått et nytt nivå?")


def smelt(hoder, rader, enheter, maal_felt: dict[str, str], fagprefiks: bool,
          fag: dict[int, dict] | None = None) -> list[dict]:
    """Pivot → lange rader, én per (rad, kolonnegruppe). maal_felt oversetter
    målnavnene i nederste hodenivå til kolonnenavn, f.eks. 'Snittkarakter' → 'snitt'."""
    ut: dict[tuple, dict] = {}
    fagnavn: dict[int, str] = {}   # fagradene kommer før skoleradene sine
    for r in rader:
        deler = r["id"].split(".")
        fag_id = int(deler[0]) if fagprefiks else None
        sti = deler[1:] if fagprefiks else deler
        if fagprefiks and not sti:
            fagnavn[fag_id] = r["navn"].strip()
            continue  # selve fagraden (summerer ikke til noe vi bruker)
        enhet = klassifiser_rad(sti, enheter)
        if enhet is None:
            continue
        for hode, verdi in zip(hoder, r["data"]):
            maal = hode[-1]
            if maal not in maal_felt:
                raise SystemExit(f"Ukjent mål {maal!r} i kolonnehodet {hode}. "
                                 f"Kjente: {sorted(maal_felt)}")
            gruppe = tuple(hode[:-1])
            nokkel = (r["id"], gruppe)
            post = ut.get(nokkel)
            if post is None:
                post = {
                    "skoleaar": skoleaar_navn(gruppe[0]),
                    "forelopig": gruppe[0].lower().startswith("foreløpig"),
                    **dimensjoner(gruppe[1:]),
                    **enhet,
                    "navn": r["navn"].strip(),
                }
                if fagprefiks:
                    # Utgåtte fag (f.eks. 32124) står i dataene, men ikke i
                    # filterVerdier. Da har vi navnet fra fagraden, men ikke koden.
                    f = fag.get(fag_id)
                    post |= {"fag_id": fag_id,
                             "fag_kode": f["kode"] if f else None,
                             "fag_navn": f["navn"].strip() if f else fagnavn.get(fag_id, "?")}
                ut[nokkel] = post
            v, prikket = tall(verdi)
            post[maal_felt[maal]] = v
            if prikket:
                post["prikket"] = True
    maal = set(maal_felt.values())
    beholdt = []
    for post in ut.values():
        post.setdefault("prikket", False)
        # Med eierform × kjønn i hodet er de fleste cellene tomme: en offentlig
        # skole har ingenting under «Privat eiet». Tomme kombinasjoner er ikke
        # data, prikkede er det (de forteller at tallet finnes, men er skjult).
        if post["prikket"] or any(post.get(m) is not None for m in maal):
            beholdt.append(post)
    return beholdt


# Etikettene i kolonnehodet, sortert på hvilken dimensjon de tilhører.
DIMENSJONER = {
    "eierform": {"Alle eierformer", "Offentlig skole", "Privat eiet"},
    "kjonn": {"Alle kjønn", "Gutt", "Jente"},
    "karaktertype": {"Skriftlig eksamen", "Muntlig eksamen", "Standpunkt"},
    "fravaerstype": {"Totalt fravær", "Vitnemålsfravær"},
}
# Etiketter som bare gjentar et filter vi har satt til «alle».
OVERFLODIGE = {"Alle trinn", "Alle utdanningsprogram"}


def dimensjoner(ledd: tuple[str, ...]) -> dict[str, str]:
    """('Skriftlig eksamen', 'Privat eiet', 'Gutt') → {karaktertype, eierform, kjonn}.

    Feiler på ukjente etiketter: da har rapporten fått en dimensjon vi ikke
    vet om, og den ville ellers blitt stille slått sammen med de andre."""
    ut = {}
    for etikett in ledd:
        dim = next((d for d, verdier in DIMENSJONER.items() if etikett in verdier), None)
        if dim:
            ut[dim] = etikett
        elif etikett not in OVERFLODIGE:
            raise SystemExit(f"Ukjent etikett {etikett!r} i kolonnehodet {ledd}.")
    return ut


def hent_karakterer() -> list[dict]:
    side = rapportside("VGO_VGOkarakterer")
    fv = enhetsoppslag(side)
    enheter = {e["id"]: e for e in fv["EnhetID"]}
    fag = {f["id"]: f for f in fv["FagID"]}
    aar = [t["id"] for t in fv["TidID"]]
    alle: list[dict] = []
    for tid in aar:
        filtre = {**side["filterDefaultVerdier"],
                  "FagID": [FELLESFAG], "TidID": [tid],
                  "KaraktertypeID": list(KARAKTERTYPER),
                  "EierformID": EIERFORMER, "KjoennID": KJONN,
                  "UtdanningsprogramvariantID": [ALLE],
                  "VisAntallPersoner": [1], "VisKarakterfordeling": [0]}
        hoder, rader = rapport_pivot(side, filtre, "**")
        biter = smelt(hoder, rader, enheter,
                      {"Snittkarakter": "snitt", "Antall elever": "antall"},
                      fagprefiks=True, fag=fag)
        alle += biter
        skoler = sum(1 for b in biter if b["nivaa"] == "skole")
        print(f"  karakterer {tid}: {len(biter):>5} rader ({skoler} skole×fag×type)", flush=True)
    return alle


def hent_enkel_rapport(kode: str, ekstra: dict, maal_felt: dict[str, str]) -> list[dict]:
    """Fravær og sluttet: hierarki Nasjonalt.Fylke.Skole, alle år i ett kall."""
    side = rapportside(kode)
    fv = enhetsoppslag(side)
    enheter = {e["id"]: e for e in fv["EnhetID"]}
    filtre = {**side["filterDefaultVerdier"], **ekstra,
              "TidID": [t["id"] for t in fv["TidID"]]}
    hoder, rader = rapport_pivot(side, filtre, "**")
    return smelt(hoder, rader, enheter, maal_felt, fagprefiks=False)


# --------------------------------------------------- Elevundersøkelsen (A)

def oslo_skoler_euv(tabell: int) -> tuple[list[int], dict]:
    fv = hent(f"{EKSPORT}{tabell}/filterVerdier")
    E = fv["EnhetID"]
    oslo = next(e for e in E if e["id"] == OSLO_FYLKE)
    return [E[i]["id"] for i in oslo.get("barn", [])], fv


def hent_euv(tabell: int, ekstra: dict[str, list[int]]) -> list[dict]:
    skoler, fv = oslo_skoler_euv(tabell)
    felt = EUV_FORVENTET_FELT[tabell]
    alle: list[dict] = []
    for tid in fv["TidID"]:
        filtre = {"TidID": [tid["id"]], "EnhetID": [HELE_LANDET, OSLO_FYLKE, *skoler], **ekstra}
        fs = filterstreng(filtre)
        info = hent(f"{EKSPORT}{tabell}/sideData?" + urllib.parse.urlencode({"filter": fs}))
        sider = info[0]["JSONSider"] if info else 0
        rader: list[dict] = []
        for s in range(1, sider + 1):
            rader += hent(f"{EKSPORT}{tabell}/data?" +
                          urllib.parse.urlencode({"filter": fs, "sideNummer": s}))
        if rader and felt not in rader[0]:
            raise SystemExit(f"Eksport {tabell} mangler feltet {felt!r} — har Udir byttet "
                             f"om tabellene igjen? Felt: {sorted(rader[0])}")
        for r in rader:
            nivaa = {0: "land", 1: "land", 2: "fylke", 3: "skole"}[r["EnhetNivaa"]]
            post = {
                "skoleaar": r["Skoleaarnavn"],
                "nivaa": nivaa,
                "orgnr": r["Organisasjonsnummer"] if nivaa == "skole" else None,
                "navn": r["EnhetNavn"].strip() if nivaa == "skole" else
                        ("Oslo" if nivaa == "fylke" else "Hele landet"),
                "trinn": r.get("Trinnnavn"),
                "eierform": r.get("EierformNavn"),
                "kjonn": r.get("Kjoenn", "Alle kjønn"),  # deltakelse har ikke kjønn
            }
            if tabell == EUV_INDIKATOR:
                post |= {"indikator": r["Indikator"], "sporsmal": r["Spoersmaalnavn"],
                         "sporsmal_nivaa": r["SpoersmaalNivaa"]}
                for kilde, navn in (("Score", "score"), ("AntallBesvart", "antall")):
                    post[navn], p = tall(r[kilde]); post["prikket"] = post.get("prikket") or p
            elif tabell == EUV_MOBBING:
                post |= {"indikator": r["Indikator"], "sporsmal": r["Spoersmaalnavn"]}
                for kilde, navn in (("AndelMobbet", "andel_mobbet"), ("AntallBesvart", "antall")):
                    post[navn], p = tall(r[kilde]); post["prikket"] = post.get("prikket") or p
            else:
                post["andel_deltatt"], post["prikket"] = tall(r["AndelDeltatt"])
            maal = [v for k, v in post.items() if k in ("score", "andel_mobbet", "andel_deltatt")]
            if post["prikket"] or any(v is not None for v in maal):
                alle.append(post)
        print(f"  eksport {tabell} {tid['navn']}: {len(rader)} rader", flush=True)
    return alle


# ------------------------------------------------------------- kontroller

def kontroller(tabeller: dict[str, list[dict]]) -> None:
    """Rimelighetssjekker. Feiler hardt: et snapshot med feil mål er verre enn intet."""
    feil = []
    k = tabeller["karakterer"]
    snitt = [r["snitt"] for r in k if r.get("snitt") is not None]
    if not snitt or min(snitt) < 1 or max(snitt) > 6:
        feil.append(f"karaktersnitt utenfor 1–6: {min(snitt, default=None)}–{max(snitt, default=None)}")
    oslo_skoler = {r["orgnr"] for r in k if r["nivaa"] == "skole"}
    if not 30 <= len(oslo_skoler) <= 90:
        feil.append(f"{len(oslo_skoler)} Oslo-skoler med karakterer — ventet 30–90")
    # Kanarifugl: nasjonalt snitt i skriftlig eksamen norsk hovedmål ligger rundt 3,5.
    kanari = [r["snitt"] for r in k if r["nivaa"] == "land" and r["fag_kode"] == "NOR1267"
              and r["karaktertype"] == "Skriftlig eksamen" and er_total(r) and r.get("snitt")]
    if kanari and not all(2.8 <= s <= 4.2 for s in kanari):
        feil.append(f"nasjonalt snitt NOR1267 skriftlig: {kanari} — feil mål eller kolonne?")

    for r in tabeller["sluttet"]:
        v = r.get("andel_sluttet")
        if v is not None and not 0 <= v <= 100:
            feil.append(f"andel sluttet {v} for {r['navn']} {r['skoleaar']}")
            break
    for r in tabeller["fravaer"]:
        v = r.get("median_dager")
        if v is not None and not 0 <= v <= 100:
            feil.append(f"median fraværsdager {v} for {r['navn']} {r['skoleaar']}")
            break
    for r in tabeller["euv"]:
        v = r.get("score")
        if v is not None and not 1 <= v <= 5:
            feil.append(f"EUV-score {v} utenfor 1–5 ({r['navn']}, {r['indikator']})")
            break
    for r in tabeller["mobbing"]:
        v = r.get("andel_mobbet")
        if v is not None and not 0 <= v <= 100:
            feil.append(f"andel mobbet {v} ({r['navn']})")
            break
    # Hver skole skal ha nøyaktig én eierform. To betyr at utledningen er gal
    # (eller at en skole har skiftet eier — da vil vi vite det).
    for s in tabeller["skoler"]:
        if len(s["eierformer_sett"]) != 1:
            print(f"  ! {s['navn']} ({s['orgnr']}) har eierform {s['eierformer_sett']}")
    if not any(s["eierform"] == "Privat eiet" for s in tabeller["skoler"]):
        feil.append("ingen private skoler i Oslo — eierformutledningen virker ikke")
    if feil:
        raise SystemExit("Snapshotet ble IKKE skrevet:\n  ✗ " + "\n  ✗ ".join(feil))


def kontrolltall(tabeller: dict[str, list[dict]]) -> None:
    print("\nKontrolltall (sjekk mot statistikkbanken før du stoler på dem):")
    for navn, rader in tabeller.items():
        if navn == "skoler":
            continue
        skoler = {r.get("orgnr") for r in rader if r["nivaa"] == "skole"}
        aar = sorted({r["skoleaar"] for r in rader})
        prikk = sum(1 for r in rader if r.get("prikket"))
        print(f"  {navn:<11} {len(rader):>6} rader  {len(skoler):>3} skoler  "
              f"{aar[0]}–{aar[-1]}  prikket: {prikk}")
        # Kjønn per skole: finnes det tall, eller bare prikker/ingenting?
        kjonn_skole = sum(1 for r in rader if r["nivaa"] == "skole"
                          and r.get("kjonn") in ("Gutt", "Jente") and not r.get("prikket"))
        print(f"  {'':<11} skolerader med tall for gutt/jente: {kjonn_skole}")
    sk = tabeller["skoler"]
    print(f"  skoler      {len(sk)} i alt: "
          f"{sum(s['eierform'] == 'Offentlig skole' for s in sk)} offentlige, "
          f"{sum(s['eierform'] == 'Privat eiet' for s in sk)} private")

    def vis(tabell, filt, felt, etikett):
        for r in sorted((r for r in tabeller[tabell] if filt(r)), key=lambda r: r["skoleaar"])[-3:]:
            print(f"    {etikett} {r['skoleaar']} {r['navn']:<12} {felt}={r.get(felt)}")

    vis("karakterer", lambda r: r["nivaa"] in ("land", "fylke") and r["fag_kode"] == "NOR1267"
        and r["karaktertype"] == "Skriftlig eksamen" and er_total(r), "snitt", "NOR1267 skriftlig")
    for kj in ("Gutt", "Jente"):
        vis("karakterer", lambda r, kj=kj: r["nivaa"] == "fylke" and r["fag_kode"] == "NOR1267"
            and r["karaktertype"] == "Skriftlig eksamen" and r["kjonn"] == kj
            and r["eierform"] == "Alle eierformer", "snitt", f"NOR1267 {kj.lower()}")
    vis("sluttet", lambda r: r["nivaa"] == "fylke" and er_total(r), "andel_sluttet", "sluttet")
    vis("mobbing", lambda r: r["nivaa"] == "fylke" and r["sporsmal"] == "Alle spørsmål"
        and er_total(r), "andel_mobbet", "mobbet")


def er_total(r: dict) -> bool:
    return (r.get("eierform", "Alle eierformer") == "Alle eierformer"
            and r.get("kjonn", "Alle kjønn") == "Alle kjønn")


def utled_skoler(tabeller: dict[str, list[dict]]) -> list[dict]:
    """Én rad per Oslo-skole med eierform.

    Udir har ikke eierform som egenskap ved skolen i disse rapportene, men hver
    skole får tall bare under sin egen eierform. Den som har tall under
    «Privat eiet», er privat. Alle tabellene og årene stemmer over.
    """
    sett: dict[str, dict] = {}
    for rader in tabeller.values():
        for r in rader:
            if r["nivaa"] != "skole" or r.get("eierform") in (None, "Alle eierformer"):
                continue
            s = sett.setdefault(r["orgnr"], {"orgnr": r["orgnr"], "navn": r["navn"],
                                             "eierformer_sett": set(), "siste_aar": ""})
            s["eierformer_sett"].add(r["eierform"])
            if r["skoleaar"] >= s["siste_aar"]:
                s["siste_aar"], s["navn"] = r["skoleaar"], r["navn"]
    ut = []
    for s in sorted(sett.values(), key=lambda s: s["navn"]):
        s["eierformer_sett"] = sorted(s["eierformer_sett"])
        s["eierform"] = s["eierformer_sett"][0] if len(s["eierformer_sett"]) == 1 else "uklar"
        s["nivaa"] = "skole"
        s["skoleaar"] = s.pop("siste_aar")
        ut.append(s)
    return ut


# ------------------------------------------------------------------- main

def skriv(tabeller: dict[str, list[dict]], ut: Path) -> None:
    ut.mkdir(parents=True, exist_ok=True)
    pakke = {
        "meta": {
            "kilde": "Utdanningsdirektoratet, Statistikkbanken",
            "kilde_url": KILDE_URL,
            "lisens": "NLOD 2.0",
            "dato_hentet": date.today().isoformat(),
            "geografi": "Oslo, videregående skoler (+ Oslo og hele landet til sammenligning)",
            "script": "pipeline/hent_udir_vgs_oslo.py",
        },
        "tabeller": tabeller,
    }
    (ut / "vgs_oslo.json").write_text(json.dumps(pakke, ensure_ascii=False, indent=1), encoding="utf-8")
    for navn, rader in tabeller.items():
        kolonner = list(dict.fromkeys(k for r in rader for k in r))
        with open(ut / f"vgs_oslo_{navn}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=kolonner)
            w.writeheader()
            w.writerows(rader)
    print(f"\n✓ Skrev {ut / 'vgs_oslo.json'} og {len(tabeller)} CSV-filer")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--ut", type=Path, default=RAADATA_DIR)
    args = p.parse_args()

    start = time.time()
    print("Karakterer (fellesfag, skriftlig eksamen og standpunkt) …")
    karakterer = hent_karakterer()
    print("Fravær …")
    fravaer = hent_enkel_rapport(
        "VGO_fravaer",
        {"TrinnID": [ALLE], "EierformID": EIERFORMER, "KjoennID": KJONN,
         "ProgramomraadeID": [ALLE], "FravaertypeID": [1, 2],
         "VisAntallPersoner": [1], "VisMaaltall": [0]},
        {"Median dager": "median_dager", "Median timer": "median_timer",
         "Antall elever": "antall"})
    print(f"  {len(fravaer)} rader")
    print("Sluttet i løpet av året …")
    sluttet = hent_enkel_rapport(
        "VGO_slutta",
        {"TrinnID": [ALLE], "EierformID": EIERFORMER, "KjoennID": KJONN,
         "ProgramomraadeID": [ALLE], "VisAntallPersoner": [1], "VisAntallPersonerSlutta": [1]},
        {"Andel sluttet": "andel_sluttet", "Antall elever": "antall",
         "Antall sluttet": "antall_sluttet"})
    print(f"  {len(sluttet)} rader")
    print("Elevundersøkelsen, Vg1 …")
    felles = {"TrinnID": [VG1], "KjoennID": KJONN, "EierformID": EIERFORMER, "ProgramomraadeID": [ALLE]}
    euv = hent_euv(EUV_INDIKATOR, felles)
    mobbing = hent_euv(EUV_MOBBING, felles)
    deltakelse = hent_euv(EUV_DELTAKELSE, {"TrinnID": [VG1], "EierformID": EIERFORMER})

    tabeller = {"karakterer": karakterer, "fravaer": fravaer, "sluttet": sluttet,
                "euv": euv, "mobbing": mobbing, "deltakelse": deltakelse}
    tabeller["skoler"] = utled_skoler(tabeller)
    kontrolltall(tabeller)
    kontroller(tabeller)
    skriv(tabeller, args.ut)
    print(f"Tid: {time.time() - start:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
