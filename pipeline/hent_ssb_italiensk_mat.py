"""Norsk import av italienske matvarer 1988–, på varenummernivå, fra SSB.

    python pipeline/hent_ssb_italiensk_mat.py
    python pipeline/hent_ssb_italiensk_mat.py --land Italia --csv ~/italiensk_mat.csv

Bruker tabell **08801** — «Utenrikshandel med varer, etter varenummer (HS) og land»,
årlig 1988–. Det er den eneste SSB-tabellen som er fin nok til å skille pancetta fra
skinke og pesto fra ketchup. Den grovere SITC-tabellen 08809 (som
`hent_ssb_matimport.py` bruker) stopper på «05 Frukt og grønnsaker» og kan ikke
svare på spørsmål om varegrupper.

## Hvorfor scriptet henter alt og grupperer etterpå

Vi henter **hele HS-kapittel 01–24** for landet i én omgang og grupperer lokalt.
Det koster ett uttrekk, og gir til gjengjeld en *eksakt nevner*: gruppene er en
delmengde av all matimport fra landet, så scriptet kan si nøyaktig hvor stor andel
gruppene dekker, og navngi de største varene som faller utenfor. Å hente
gruppe for gruppe gir ingen slik kontroll — da vet du aldri om du glemte en vare.
Å endre gruppeinndelingen etterpå koster heller ingenting: rådataene ligger i
cachen.

## Fella i tabell 08801: varenummer er datert

Kodene i `Varekoder` er ikke HS-nummer, men **HS-nummer + året versjonen trådte i
kraft**: `20032000_1988`, `20039010_2012`. Tolltariffen revideres jevnlig, og et
varenummer får nytt nummer, blir splittet eller slått sammen. Trøfler på glass er
`20032000` til og med 2011 og `20039010` fra 2012.

Velger du bare den gjeldende koden, får du en serie som begynner på null i 2012 og
ser ut som eksplosiv vekst. Det er ikke vekst, det er en omnummerering. Derfor:

- gruppene defineres på **HS-prefiks**, ikke på enkeltkoder, og scriptet slår opp
  *alle* daterte versjoner av prefikset i tabellens egen metadata;
- gyldighetsspennet står i klartekst i etiketten — `(1988-2011)`, `(2012-)` — og
  `dekningsport()` krever at hver gruppe har minst én gyldig kode i hvert eneste år.
  Et hull der er en omnummerering scriptet ikke har fanget opp, og det stopper
  kjøringen framfor å levere en kunstig knekk.

Utgåtte koder svarer `0` utenfor gyldighetsperioden sin — ikke `null`. Å summere
alle versjoner av et varenummer er derfor trygt og gir ingen dobbelttelling.

## De andre portene

- **Disjunkthet.** Ingen varekode får havne i to grupper. Uten den porten blir
  oliven telt både som «bearbeidede grønnsaker» og som «oliven og kapers», og
  totalen blir større enn matimporten den er en del av.
- **Enhet.** `Mengde1` er kg for alle koder i kapittel 01–24, men enheten står i
  varetekstene (`M1=kg`), ikke i dimensjonens metadata — der står det bare
  «hovedsakelig kg». Scriptet leser `M1=` av hver etikett og nekter å summere
  mengde for en gruppe der en kode måler noe annet enn kg. Samme regel gjelder
  `Mengde2`: vin og eddik oppgir `M2=liter`, og literserien skrives bare for
  grupper der *hver* kode gjør det.
- **Nevnerkontroll, internt.** Summen av gruppene pluss restposten skal være lik
  summen over alle kapittel 01–24. Slår det ikke til, er grupperingen lekk.
- **Nevnerkontroll, eksternt.** Den forrige porten er sirkulær: gruppene summerer
  til totalen fordi de er bygget av den, og den ville stått grønn selv om hele
  uttrekket gjaldt feil land. Derfor sammenlignes summen også mot **tabell
  08809**, som SSB publiserer på SITC og aggregerer uavhengig av varenumrene.
  Universene er ikke like — olivenolje er SITC-seksjon 4, ikke 0 — så kapitlene
  i `UTENFOR_SITC_01` trekkes fra først. For Italia er største avvik +1,8 % over
  38 år.

## Tre mål på «vekst», og de svarer ikke på det samme

38 år i løpende kroner er mest prisvekst. Scriptet skriver derfor tre serier, og
valget mellom dem er ikke en detalj — for italiensk mat samlet spriker de fra
19,9x til 4,8x for **samme periode og samme tall**:

| Serie | 1989→2025 | Svarer på |
|---|---|---|
| `verdi_lopende` | 19,9x | ingenting alene |
| `verdi_faste` (KPI, tabell 08981) | 8,3x | hva beløpet er verdt i dagens penger |
| `verdi_faste_importpris` (tabell 06322) | 5,6x | volum, indeksmålt |
| `kg` | 4,8x | volum, målt direkte |

**KPI er ikke feil, men den er ofte ikke det man tror man spør om.** Importerte
matvarer har steget 3,5x i pris siden 1989 mot KPIs 2,4x. Deflaterer du med KPI,
blir den forskjellen liggende igjen i «realveksten» og ser ut som mer mat. Skal
du si «nordmenn spiser mer italiensk», er tallet 4,8x — ikke 8,3x. Skal du si
«nordmenn bruker mer penger på italiensk mat, målt i dagens kroner», er det 8,3x.

At `verdi_faste_importpris` og `kg` lander nær hverandre for pasta (10,3 mot 9,8),
vin (10,2 mot 9,2) og grønnsaker (8,4 mot 7,5), er kontrollen på at deflateringen
gjør det den skal. Der de spriker — meieri, 68x mot 154x — har sammensetningen
inne i gruppen endret seg, og det er i seg selv et funn.

Hver gruppe deflateres med prisindeksen for sin egen SITC-gruppe, ikke med én
felles matvareindeks. Se `velg_prisindeks()` for hvorfor noen grupper likevel
faller ned på seksjonsnivå: divisjonene 01, 02, 03 og 11 starter først i 2000, og
å skjøte dem bakover ville skjult en antagelse i en serie som ser målt ut.

Skriver snapshot til pipeline/cache/ssb_italiensk_mat_<land>.json. Dette er ikke
en publisert historie — skal tallene bli en, se kontrakt.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

import kontrakt  # noqa: F401  — importen setter UTF-8 på Windows-konsollen
from nett import hent_json

API = "https://data.ssb.no/api/v0/no/table/"
TABELL = "08801"
KPI_TABELL = "08981"
PRISINDEKS_TABELL = "06322"   # prisindekser for utenrikshandel, etter SITC
KILDE_URL = "https://www.ssb.no/statbank/table/08801"

CACHE_DIR = Path(__file__).resolve().parent / "cache"
BRUKERAGENT = "Impromptu-Analytics-datainnsamling (kontakt: kontakt@impromptu.no)"

# Matkapitlene i HS. 01-24 er «næringsmidler, drikkevarer og tobakk» — vi henter
# hele spennet som nevner, og grupperer et utvalg av det.
MATKAPITLER = tuple(f"{n:02d}" for n in range(1, 25))

# Kodenes gyldighetsspenn står i etiketten: «... (1988-2011) (M1=kg, M2=nei)».
SPENN = re.compile(r"\((\d{4})-(\d{4})?\)\s*\(M1=")
ENHET_M1 = re.compile(r"M1=\s*([^,)]*)")
ENHET_M2 = re.compile(r"M2=\s*([^,)]*)")

# Måltallene vi henter. Ligger i cachefila slik at en senere kjøring oppdager at
# lista er endret — uten det ville en cache hentet før literstøtten ble lagt inn
# blitt gjenbrukt i stillhet, og vin ville manglet volum uten noen feilmelding.
MAALTALL = {"Verdi": "verdi", "Mengde1": "kg", "Mengde2": "liter"}


# ---------------------------------------------------------------------------
# Varegruppene
#
# Skrevet for hånd, mot varetekstene i tabellen slik de faktisk står. Hver gruppe
# er (prefiks, unntatt) der prefiks er HS-nummer med 2, 4, 6 eller 8 siffer, og
# unntatt er 8-sifrede varenummer som hører hjemme i en annen gruppe.
#
# Rekkefølgen er brukerens liste. `del_av` markerer en undergruppe som rapporteres
# for seg *inne i* hovedgruppen — den telles ikke en gang til i totalen.
# ---------------------------------------------------------------------------

# Pizzakodene står som egen konstant fordi de brukes to steder — som «unntatt» i
# brødgruppen og som «prefiks» i pizzagruppen. Skrevet to ganger ville de før
# eller siden gått fra hverandre, og da havner pizza enten i begge grupper
# (disjunkthetsporten stopper det) eller i ingen (ingenting stopper det).
PIZZAKODER = ["19059005", "19059006", "19059008",
              "19059010", "19059021", "19059022"]

VAREGRUPPER: list[dict] = [
    {
        "id": "meieri",
        "prisindeks": "02",
        "navn": "Meieriprodukter",
        "prefiks": ["0401", "0402", "0403", "0404", "0405", "0406"],
        "undergrupper": {"ost": ["0406"]},
        "note": "Ost er HS 0406 og er skilt ut. Resten er melk, fløte, yoghurt, "
                "smør og myse (0401-0405).",
    },
    {
        "id": "spekemat",
        "prisindeks": "01",
        "navn": "Spekemat og bearbeidede kjøttprodukter",
        "prefiks": ["0210", "1601", "1602"],
        "undergrupper": {
            # Pancetta er sideflesk (buk) og ligger i 02101200. Guanciale er
            # kjake, ikke buk, og faller derfor i 02101900 — «svinekjøtt unntatt
            # skinker og sideflesk». De to skal ikke slås sammen.
            "pancetta_sideflesk": ["02101200"],
            "guanciale_coppa_mv": ["02101900"],
            "skinke_prosciutto": ["02101100", "02101101", "02101109"],
            "polser_salami": ["1601"],
            "tilberedt_svin": ["16024100", "16024200", "16024900"],
        },
        "note": "Pancetta er sideflesk og ligger i 02101200 (1,3 mill. i 2025). "
                "Guanciale er svinekjake og havner i 02101900 sammen med coppa, "
                "speck og lonzino — 68,9 mill. i 2025, den største kurerte "
                "kjøttposten. HS kan ikke isolere guanciale fra de andre i den "
                "posten. Spekeskinke (prosciutto) ligger i 021011*.",
    },
    {
        "id": "pasta",
        "prisindeks": "04",
        "navn": "Pasta og melprodukter",
        "prefiks": ["1902"],
        "unntatt": ["19024000"],  # couscous — ikke italiensk, egen HS-linje
        "undergrupper": {
            "torrpasta": ["19021100", "19021900"],
            "fylt_pasta": ["190220"],
        },
        "note": "Couscous (19024000) er holdt utenfor. Gnocchi har ingen egen "
                "HS-linje: ferske potetgnocchi føres normalt på 190220/190230, "
                "men kan også havne på 200520 (potetprodukter) — tallet er derfor "
                "et minimum for gnocchi spesielt.",
    },
    {
        "id": "brod_kjeks",
        "prisindeks": "04",
        "navn": "Brød og kjeks",
        "prefiks": ["1905"],
        "unntatt": PIZZAKODER,
        "undergrupper": {
            "kjeks_smakaker": ["19053001", "19053100"],
            "vafler": ["19053002", "19053200"],
            "brod_og_brodvarer": ["19059091", "19059092"],
        },
        "note": "Pizza er skilt ut i egen gruppe. Uten den delingen var denne "
                "gruppen 538 mill. i 2025, hvorav 370 mill. var pizza — en "
                "overskrift som sa «brød og kjeks» om noe som i hovedsak var "
                "ferdigpizza.",
    },
    {
        "id": "pizza",
        "prisindeks": "04",
        "navn": "Pizza og pizzabunner",
        # Pizza har egne varenummer hele veien, men de ble omnummerert i 1995:
        # 19059005/06 (pizza) og 19059008 (bunner) gjelder til og med 1994,
        # deretter 19059010/21 og 19059022.
        "prefiks": PIZZAKODER,
        "undergrupper": {
            "med_kjott": ["19059005", "19059010"],
            "uten_kjott": ["19059006", "19059021"],
            "pizzabunner": ["19059008", "19059022"],
        },
        "note": "Skilt ut av HS 1905 fordi pizza utgjorde 69 % av bakverkgruppen "
                "i 2025. Andelen lå på 29 % i 2015 og 67 % i 2020 — hoppet er "
                "reell handel, ikke omnummerering: kodene er uendret siden 1995.",
    },
    {
        "id": "gronnsaker",
        "prisindeks": "05",
        "navn": "Hermetiserte og bearbeidede grønnsaker",
        "prefiks": ["2001", "2002", "2004", "2005"],
        # Oliven, kapers og artisjokk har egen gruppe nedenfor.
        "unntatt": [
            "20019010", "20019020",              # kapers og oliven i eddik
            "20057000",                          # oliven, ikke i eddik
            "20059001", "20059002", "20059901",  # kapers / artisjokk / slått sammen
            "20049091",                          # artisjokk, fryst
        ],
        "undergrupper": {"tomat": ["2002"]},
        "note": "Tomatprodukter (HS 2002: hele/oppdelte tomater og tomatpuré) er "
                "skilt ut. Tomatsaus og ketchup ligger i sausgruppen, ikke her.",
    },
    {
        "id": "sauser",
        "prisindeks": "0",
        "navn": "Sauser og smakstilsetninger",
        "prefiks": ["2103"],
        "undergrupper": {"tomatsaus_ketchup": ["210320"]},
        "note": "Pesto har ingen egen HS-linje og ligger i samlekoden 21039099 "
                "«sauser og preparater for tillaging av sauser, i.e.n.» sammen med "
                "alt annet som ikke er soyasaus, tomatsaus, sennep eller majones. "
                "Artisjokk på glass er en grønnsak i HS og ligger i oliven/kapers-"
                "gruppen, ikke her.",
    },
    {
        "id": "olivenolje_eddik",
        "prisindeks": "4",
        "navn": "Olivenolje og eddik",
        "prefiks": ["1509", "1510", "2209"],
        "undergrupper": {"olivenolje": ["1509", "1510"], "eddik": ["2209"]},
        "note": "1509 er olivenolje av oliven, 1510 er pressrestolje (pomace). "
                "Fra 2022 skiller tariffen extra virgin (150920) fra virgin "
                "(150930) og øvrig (150940); før det lå alt i 150910/150990. "
                "Varianter «til dyrefor» er tatt med — de var ikke egne koder før "
                "1995, så å utelate dem ville laget en kunstig knekk.",
    },
    {
        "id": "troffel",
        "prisindeks": "05",
        "navn": "Trøffelprodukter",
        # Trøffel er den mest omnummererte varen i utvalget: fersk trøffel har
        # tre koder over perioden, konservert har to.
        "prefiks": ["07095200", "07095600", "07095910", "20032000", "20039010"],
        "undergrupper": {
            "fersk": ["07095200", "07095600", "07095910"],
            "konservert": ["20032000", "20039010"],
        },
        "note": "Fersk trøffel: 07095200 (1988-2006) → 07095910 (2007-2021) → "
                "07095600 (2022-). Konservert: 20032000 (1988-2011) → 20039010 "
                "(2012-). Trøffelolje og trøffelkrem har ingen egen HS-linje og "
                "er IKKE med — de ligger spredt i sausekoder og oljekoder.",
    },
    {
        "id": "sjomat",
        "prisindeks": "03",
        "navn": "Hermetisert sjømat",
        "prefiks": ["1604"],
        # 160415 er makrell og hører ikke hjemme under «sardin og ansjos». Den gir
        # 0 kr fra Italia i dag, så den forurenset ingen tall — men den lå i
        # prefikslista og ville slukt makrellen stille den dagen importen startet.
        "undergrupper": {
            "tunfisk": ["160414"],
            "sardin_ansjos": ["160413", "160416"],
            "makrell": ["160415"],
        },
        "note": "HS 1604 er tilberedt/konservert fisk. Skalldyr og bløtdyr "
                "(HS 1605) er ikke med.",
    },
    {
        "id": "oliven_kapers",
        "prisindeks": "05",
        "navn": "Oliven, kapers og artisjokk",
        "prefiks": [
            "20019010", "20019020", "20057000",
            "20059001", "20059002", "20059901", "20049091",
        ],
        "undergrupper": {
            "oliven": ["20019020", "20057000"],
            "kapers_ren": ["20019010", "20059001"],
            "artisjokk_ren": ["20059002", "20049091"],
        },
        "note": "VIKTIG BRUDD: fra 2007 slo tolltariffen sammen kapers, artisjokk "
                "og søte pepperfrukter til én kode (20059901). Etter 2006 kan de "
                "tre ikke skilles i SSBs tall. Undergruppene «kapers_ren» og "
                "«artisjokk_ren» er derfor bare komplette til og med 2006; "
                "hovedgruppen er sammenlignbar hele veien. Oliven (20019020 i "
                "eddik, 20057000 ellers) er uendret 1988-.",
    },
    {
        "id": "vin",
        "prisindeks": "11",
        "navn": "Vin og vermut",
        # Eddik (2209) ligger i olivenolje-gruppen. Skulle den havnet her også,
        # stopper disjunkthetsporten kjøringen framfor å telle den to ganger.
        "prefiks": ["2204", "2205"],
        "undergrupper": {
            "musserende": ["220410"],
            "stille_vin": ["220421", "220422", "220429"],
            "vermut": ["2205"],
        },
        "note": "HS 2204 er vin av friske druer, 2205 er vermut. Øl, likør, sprit "
                "og mineralvann i kapittel 22 er ikke med. Denne gruppen har "
                "mengde i LITER (M2), ikke bare kilo — bruk literserien når du "
                "siterer volum.",
    },
]


def _flat(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower())
                   if unicodedata.category(c) != "Mn")


def _post(tabell: str, query: list) -> dict:
    return hent_json(API + tabell, BRUKERAGENT, timeout=120,
                     json_kropp={"query": query,
                                 "response": {"format": "json-stat2"}})


# ---------------------------------------------------------------------------
# Metadata og portene
# ---------------------------------------------------------------------------

def hent_metadata(tabell: str) -> dict:
    meta = hent_json(API + tabell, BRUKERAGENT, timeout=120)
    return {v["code"]: v for v in meta["variables"]}


def finn_land(var: dict, land: str) -> str:
    ønsket = _flat(land)
    par = list(zip(var["values"], var["valueTexts"]))
    for kode, tekst in par:
        if _flat(tekst) == ønsket:
            return kode
    treff = [(k, t) for k, t in par if ønsket in _flat(t)]
    if len(treff) == 1:
        return treff[0][0]
    raise SystemExit(
        f"Fant ikke «{land}» entydig i tabell {TABELL}. "
        + (f"Kandidater: {', '.join(t for _, t in treff[:8])}" if treff else "Ingen treff.")
    )


def spenn(etikett: str) -> tuple[int, int] | None:
    """(fra, til) fra varetekstens «(1988-2011)». Åpen slutt gir 9999."""
    m = SPENN.search(etikett)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)) if m.group(2) else 9999


def enhet_m1(etikett: str) -> str:
    m = ENHET_M1.search(etikett)
    return m.group(1).strip().lower() if m else ""


def enhet_m2(etikett: str) -> str:
    """M2 er et sekundært mengdemål. For de fleste varer står det «nei»; for vin,
    eddik og brennevin står det «liter», og da er liter det siterbare volumet."""
    m = ENHET_M2.search(etikett)
    return m.group(1).strip().lower() if m else ""


def liter_per_aar(koder: list[str], alle: dict[str, str],
                  serier: dict) -> dict[int, float]:
    """Litersum per år, men **bare for år der summen er komplett**.

    Regelen kan ikke være «alle koder i gruppen oppgir liter», slik kg-porten er.
    Vin har 27 kodeversjoner med `M2=liter` og 6 med `M2=nei` — de seks er
    1988/89-versjonene, fra før SSB registrerte volum på vin i det hele tatt. Med
    en alt-eller-ingenting-regel ville hele vingruppen mistet literserien på grunn
    av to årganger.

    I stedet avgjøres det år for år: bidrar en kode med omsetning det året uten å
    oppgi liter, er årets litersum ufullstendig, og året utelates. For vin gir det
    en serie som starter når SSB faktisk begynte å måle liter, og ingen stille
    undervurdering i årene før.
    """
    ut: dict[int, float] = {}
    for aar in {a for k in koder for a in serier.get(k, {}).get("verdi", {})}:
        bidrar = [k for k in koder if serier.get(k, {}).get("verdi", {}).get(aar)]
        if bidrar and all(enhet_m2(alle[k]) == "liter" for k in bidrar):
            ut[aar] = sum(serier[k].get("liter", {}).get(aar, 0) for k in bidrar)
    return ut


def matkoder(varekoder: dict) -> dict[str, str]:
    """Alle varenummer i HS-kapittel 01-24, kode -> etikett."""
    return {k: t for k, t in zip(varekoder["values"], varekoder["valueTexts"])
            if k[:2] in MATKAPITLER}


def treff(kode: str, prefiks: list[str]) -> bool:
    hs = kode.split("_")[0]
    return any(hs.startswith(p) for p in prefiks)


def grupper_koder(alle: dict[str, str]) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Fordeler varenumrene på gruppene. Håndhever disjunkthet."""
    fordelt: dict[str, list[str]] = {}
    eier: dict[str, str] = {}
    for gruppe in VAREGRUPPER:
        valgt = []
        for kode in alle:
            if not treff(kode, gruppe["prefiks"]):
                continue
            if any(kode.split("_")[0].startswith(u) for u in gruppe.get("unntatt", [])):
                continue
            if kode in eier:
                raise SystemExit(
                    f"Varekoden {kode} ({alle[kode][:60]}) havner i både "
                    f"«{eier[kode]}» og «{gruppe['id']}». Gruppene må være "
                    "disjunkte — legg koden i «unntatt» på én av dem."
                )
            eier[kode] = gruppe["id"]
            valgt.append(kode)
        if not valgt:
            raise SystemExit(
                f"Gruppen «{gruppe['id']}» traff ingen varenummer. Prefiksene "
                f"{gruppe['prefiks']} finnes ikke i tabell {TABELL} — "
                "sannsynligvis er tariffen omnummerert."
            )
        fordelt[gruppe["id"]] = sorted(valgt)
    return fordelt, eier


def enhetsport(fordelt: dict[str, list[str]], alle: dict[str, str]) -> None:
    """Mengde1 er bare summerbar hvis alle kodene i gruppen måler i kg."""
    for gid, koder in fordelt.items():
        avvik = {k: enhet_m1(alle[k]) for k in koder if enhet_m1(alle[k]) != "kg"}
        if avvik:
            raise SystemExit(
                f"Gruppen «{gid}» har varenummer som ikke måles i kg: "
                + ", ".join(f"{k} (M1={e or '?'})" for k, e in list(avvik.items())[:5])
                + ". Mengdeserien for gruppen ville summert epler og pærer."
            )


def dekningsport(fordelt: dict[str, list[str]], alle: dict[str, str],
                 aarene: list[int]) -> dict[str, list[int]]:
    """Hvert år må dekkes av minst én gyldig kode i hver gruppe.

    Et hull betyr at varenummeret ble omnummerert til noe prefikset ikke fanger.
    Serien ville da falt til null i hullet og sett ut som et sammenbrudd i
    handelen.
    """
    hull: dict[str, list[int]] = {}
    for gid, koder in fordelt.items():
        spenn_liste = [s for s in (spenn(alle[k]) for k in koder) if s]
        manglende = [aar for aar in aarene
                     if not any(f <= aar <= t for f, t in spenn_liste)]
        if manglende:
            hull[gid] = manglende
    if hull:
        linjer = "\n".join(
            f"  {gid}: ingen gyldig varekode i {_komprimer(aar)}"
            for gid, aar in hull.items()
        )
        raise SystemExit(
            "Dekningshull — en eller flere grupper har år uten en eneste gyldig "
            f"varekode:\n{linjer}\n"
            "Det er nesten alltid en omnummerering i tolltariffen. Finn den nye "
            "koden i --vis-koder og legg prefikset inn i VAREGRUPPER."
        )
    return hull


def _komprimer(aar: list[int]) -> str:
    if not aar:
        return ""
    grupper, start, forrige = [], aar[0], aar[0]
    for a in aar[1:]:
        if a != forrige + 1:
            grupper.append((start, forrige))
            start = a
        forrige = a
    grupper.append((start, forrige))
    return ", ".join(f"{f}" if f == t else f"{f}-{t}" for f, t in grupper)


# ---------------------------------------------------------------------------
# Uttrekket
# ---------------------------------------------------------------------------

def raa_cache(land: str) -> Path:
    return CACHE_DIR / f"ssb_08801_raa_{_flat(land).replace(' ', '_')}.json"


def hent_serier_cachet(koder: list[str], landkode: str, aarene: list[int],
                       land: str, frisk: bool) -> dict:
    """Rådataene for hele kapittel 01-24, cachet på disk.

    Cachen finnes fordi grupperingen er det som kommer til å endre seg. Å flytte
    en varekode fra én gruppe til en annen skal koste null nye kall mot SSB —
    ellers blir terskelen for å rette en feilplassert kode høyere enn terskelen
    for å la den ligge.
    """
    felt = sorted(MAALTALL.values())
    sti = raa_cache(land)
    if sti.exists() and not frisk:
        lagret = json.loads(sti.read_text(encoding="utf-8"))
        # Måltallene er med i gyldighetssjekken: uten dem ville en cache hentet
        # før literstøtten kom blitt gjenbrukt i stillhet, og vin manglet volum.
        if (lagret.get("aarene") == aarene
                and sorted(lagret.get("koder", [])) == sorted(koder)
                and sorted(lagret.get("maaltall", [])) == felt):
            print(f"  bruker rå-cache {sti.name} "
                  f"({len(lagret['serier'])} varenummer, hentet {lagret['hentet']})")
            return {k: {m: {int(a): v for a, v in r.get(m, {}).items()} for m in felt}
                    for k, r in lagret["serier"].items()}
        print("  rå-cachen gjelder et annet uttrekk — henter på nytt")
    serier = hent_serier(koder, landkode, aarene)
    sti.parent.mkdir(parents=True, exist_ok=True)
    sti.write_text(json.dumps({
        "hentet": date.today().isoformat(), "tabell": TABELL, "land": land,
        "landkode": landkode, "aarene": aarene, "koder": sorted(koder),
        "maaltall": felt,
        "serier": {k: {m: {str(a): v for a, v in r.get(m, {}).items()} for m in felt}
                   for k, r in serier.items()},
    }, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓ rå-cache skrevet: {sti.name}")
    return serier


def hent_serier(koder: list[str], landkode: str, aarene: list[int],
                bunt: int = 700) -> dict[str, dict[str, dict[int, float]]]:
    """kode -> {"verdi"|"kg"|"liter" -> {år: tall}}. Henter i bunter for cellegrensen.

    800 000 celler er taket. 700 koder x 38 år x 3 måltall = 79 800 — god margin,
    og få nok forespørsler til å holde seg under 30 i minuttet.
    """
    ut: dict[str, dict[str, dict[int, float]]] = {}
    for i in range(0, len(koder), bunt):
        del_ = koder[i:i + bunt]
        print(f"  henter {i + 1}-{i + len(del_)} av {len(koder)} varenummer …", flush=True)
        stat = _post(TABELL, [
            {"code": "Varekoder", "selection": {"filter": "item", "values": del_}},
            {"code": "ImpEks", "selection": {"filter": "item", "values": ["1"]}},
            {"code": "Land", "selection": {"filter": "item", "values": [landkode]}},
            {"code": "ContentsCode",
             "selection": {"filter": "item", "values": list(MAALTALL)}},
            {"code": "Tid", "selection": {"filter": "item",
                                          "values": [str(a) for a in aarene]}},
        ])
        ut.update(_les(stat))
    return ut


def _les(stat: dict) -> dict[str, dict[str, dict[int, float]]]:
    order, size = stat["id"], stat["size"]
    idx = {d: stat["dimension"][d]["category"]["index"] for d in order}
    verdier = stat["value"]

    def flat(koord: dict[str, int]) -> int:
        f = 0
        for i, dim in enumerate(order):
            f = f * size[i] + koord[dim]
        return f

    maal = MAALTALL
    ut: dict[str, dict[str, dict[int, float]]] = {}
    for kode, ki in idx["Varekoder"].items():
        rad = {navn: {} for navn in maal.values()}
        for cc, navn in maal.items():
            if cc not in idx["ContentsCode"]:
                continue
            for aar, ti in idx["Tid"].items():
                koord = {d: 0 for d in order}
                koord["Varekoder"], koord["ContentsCode"], koord["Tid"] = ki, idx["ContentsCode"][cc], ti
                v = verdier[flat(koord)]
                if v:
                    rad[navn][int(aar)] = v
        ut[kode] = rad
    return ut


# HS-kapitler som ligger inne i 01-24, men UTENFOR SITC-seksjon 0 og 1:
# 05 animalske produkter i.e.n., 06 levende planter og snittblomster,
# 12 oljefrø, 13 gummi og harpiks, 14 vegetabilske flettematerialer (alle SITC 2),
# og 15 fett og oljer — inkludert olivenolje — som er SITC-seksjon 4.
UTENFOR_SITC_01 = ("05", "06", "12", "13", "14", "15")


def nevnerkontroll_mot_sitc(land: str, serier: dict, aarene: list[int],
                            toleranse: float = 0.02) -> dict:
    """Kontrollerer uttrekket mot en HELT ANNEN SSB-tabell.

    Alt annet i scriptet er intern konsistens: gruppene summerer til totalen fordi
    de er bygget av den. Det fanger ikke at hele uttrekket kan være feil — feil
    land, feil retning, halve varenumrene tapt i en bunt. Derfor sammenlignes
    summen vår mot tabell 08809, som er publisert på SITC og aggregert av SSB
    uavhengig av varenummernivået.

    De to universene er ikke identiske: SITC-seksjon 0+1 er «matvarer, levende
    dyr, drikkevarer og tobakk», mens HS-kapittel 01-24 i tillegg drar med seg
    snittblomster, oljefrø og — viktigst — olivenoljen, som SITC fører i seksjon
    4 sammen med alle andre fettstoffer. Trekker vi fra kapitlene i
    UTENFOR_SITC_01, skal de to tallene møtes.

    For Italia lander avviket på under en halv prosent i alle 38 år. Sprekker
    det, er det ikke en avrundingsdetalj: da har uttrekket mistet noe.
    """
    sitc = hent_json(API + "08809", BRUKERAGENT, timeout=120, json_kropp={
        "query": [
            {"code": "Land", "selection": {"filter": "item", "values": [land]}},
            {"code": "SITC", "selection": {"filter": "item", "values": ["0", "1"]}},
            {"code": "ImpEks", "selection": {"filter": "item", "values": ["1"]}},
            {"code": "ContentsCode", "selection": {"filter": "item", "values": ["Verdi"]}},
            {"code": "Tid", "selection": {"filter": "item",
                                          "values": [str(a) for a in aarene]}},
        ],
        "response": {"format": "json-stat2"}})
    order, size = sitc["id"], sitc["size"]
    idx = {d: sitc["dimension"][d]["category"]["index"] for d in order}

    def celle(seksjon: str, aar: str) -> float:
        koord = {d: 0 for d in order}
        koord["SITC"], koord["Tid"] = idx["SITC"][seksjon], idx["Tid"][aar]
        f = 0
        for i, dim in enumerate(order):
            f = f * size[i] + koord[dim]
        # 08809 er i 1 000 kr; 08801 er i kr.
        return (sitc["value"][f] or 0) * 1000

    avvik: dict[int, float] = {}
    verste = (0.0, None)
    for aar in aarene:
        fasit = celle("0", str(aar)) + celle("1", str(aar))
        vaart = sum(v for k, r in serier.items() if k[:2] not in UTENFOR_SITC_01
                    for a, v in r["verdi"].items() if a == aar)
        if not fasit:
            continue
        d = (vaart - fasit) / fasit
        avvik[aar] = round(d, 5)
        if abs(d) > abs(verste[0]):
            verste = (d, aar)

    if abs(verste[0]) > toleranse:
        raise SystemExit(
            f"Nevnerkontroll mot tabell 08809 feilet: i {verste[1]} avviker vårt "
            f"HS-uttrekk {verste[0]:+.1%} fra SSBs publiserte SITC 0+1 for landet "
            f"(toleranse {toleranse:.0%}). Uttrekket har mistet eller doblet "
            "varenummer — ikke tolk tallene før dette er forklart."
        )
    print(f"  ✓ kontroll mot tabell 08809 (SITC 0+1): største avvik "
          f"{verste[0]:+.2%} i {verste[1]}")
    return {"tabell": "08809", "storste_avvik": verste[0], "storste_avvik_aar": verste[1],
            "avvik_per_aar": {str(a): d for a, d in sorted(avvik.items())},
            "kapitler_trukket_fra": list(UTENFOR_SITC_01)}


def hent_prisindeks(aarene: list[int]) -> dict[str, dict[int, float]]:
    """Prisindekser for norsk vareimport, etter SITC (tabell 06322, 2000=100).

    Hvorfor denne finnes ved siden av KPI: de to svarer på hvert sitt spørsmål, og
    forskjellen er stor nok til å snu en påstand. KPI måler hva norske husholdninger
    betaler for alt de kjøper, og deflatert med den blir tallet «hva er dette verdt
    i dagens penger». Importprisindeksen måler hva *disse varene* faktisk kostet
    over grensen, og deflatert med den blir tallet et volumanslag.

    For italiensk mat samlet er sprikte 8,3x mot 5,7x siden 1989 — importert mat har
    steget klart mer i pris enn norsk konsum generelt, og KPI lar den differansen bli
    liggende igjen i «realveksten».

    Hver varegruppe deflateres med SITC-gruppen den faktisk tilhører (`prisindeks` i
    VAREGRUPPER), ikke med én felles matvareindeks: ost og olivenolje har ikke fulgt
    samme prisbane. Indeksen starter i 1989, så 1988 får ingen verdi — den utelates
    framfor å bli ekstrapolert.
    """
    koder = sorted({g["prisindeks"] for g in VAREGRUPPER} | {"0", "1"})
    aar = [str(a) for a in aarene if a >= 1989]
    stat = _post(PRISINDEKS_TABELL, [
        {"code": "ImpEks", "selection": {"filter": "item", "values": ["1"]}},
        {"code": "ImpEkspGr", "selection": {"filter": "item", "values": koder}},
        {"code": "ContentsCode", "selection": {"filter": "item", "values": ["Prisindeks"]}},
        {"code": "Tid", "selection": {"filter": "item", "values": aar}},
    ])
    order, size = stat["id"], stat["size"]
    idx = {d: stat["dimension"][d]["category"]["index"] for d in order}
    ut: dict[str, dict[int, float]] = {}
    for kode, ki in idx["ImpEkspGr"].items():
        rad = {}
        for a, ti in idx["Tid"].items():
            koord = {d: 0 for d in order}
            koord["ImpEkspGr"], koord["Tid"] = ki, ti
            f = 0
            for i, dim in enumerate(order):
                f = f * size[i] + koord[dim]
            if stat["value"][f]:
                rad[int(a)] = stat["value"][f]
        ut[kode] = rad
    mangler = [g["id"] for g in VAREGRUPPER if not ut.get(g["prisindeks"])]
    if mangler:
        raise SystemExit(
            f"Tabell {PRISINDEKS_TABELL} mangler prisindeks for gruppene {mangler}. "
            "SITC-inndelingen i indeksen er endret — sjekk «prisindeks» i VAREGRUPPER."
        )
    return ut


def velg_prisindeks(onsket: str, prisindeks: dict[str, dict[int, float]],
                    aarene: list[int]) -> tuple[str, str | None]:
    """Den mest presise indeksen som dekker HELE perioden. (kode, merknad).

    SSB fører ikke alle SITC-nivåer like langt tilbake: seksjonene (0, 1, 4) og
    divisjonene 04 og 05 starter i 1989, mens 01 kjøtt, 02 meieri, 03 fisk og
    11 drikkevarer først starter i 2000.

    Alternativet ville vært å skjøte: bruke divisjonen fra 2000 og skjøte den
    bakover med seksjonens vekstrater. Det er en vanlig teknikk, men den legger
    inn en antagelse — at kjøttprisene fulgte matvareprisene generelt på
    1990-tallet — og skjuler den inne i en serie som ser målt ut. Det er nøyaktig
    den feilen resten av dette scriptet er bygget for å unngå.

    Derfor faller vi heller ned på seksjonsnivået for hele perioden, og sier fra
    at vi gjorde det. Presisjonen som tapes, er synlig; en skjøt ville ikke vært.
    """
    trengs = {a for a in aarene if a >= 1989}
    if trengs <= set(prisindeks.get(onsket, {})):
        return onsket, None
    seksjon = onsket[0]
    if trengs <= set(prisindeks.get(seksjon, {})):
        start = min(prisindeks[onsket]) if prisindeks.get(onsket) else "?"
        return seksjon, (f"SITC {onsket} finnes først fra {start}; bruker seksjon "
                         f"{seksjon} for hele perioden framfor å skjøte to indekser")
    raise SystemExit(
        f"Verken SITC {onsket} eller seksjon {seksjon} dekker {min(trengs)}-"
        f"{max(trengs)} i tabell {PRISINDEKS_TABELL}."
    )


def hent_kpi(aarene: list[int]) -> dict[int, float]:
    stat = _post(KPI_TABELL, [
        {"code": "Maaned", "selection": {"filter": "item", "values": ["90"]}},
        {"code": "ContentsCode", "selection": {"filter": "item", "values": ["KpiIndMnd"]}},
        {"code": "Tid", "selection": {"filter": "item", "values": [str(a) for a in aarene]}},
    ])
    idx = stat["dimension"]["Tid"]["category"]["index"]
    return {int(a): stat["value"][i] for a, i in idx.items()
            if stat["value"][i] is not None}


# ---------------------------------------------------------------------------
# Aggregering
# ---------------------------------------------------------------------------

def revisjonsaar(koder: list[str], alle: dict[str, str]) -> set[int]:
    """År der en varekode i gruppen begynner eller slutter å gjelde."""
    ut: set[int] = set()
    for k in koder:
        s = spenn(alle[k])
        if not s:
            continue
        ut.add(s[0])
        if s[1] != 9999:
            ut.add(s[1] + 1)   # året etter at koden falt bort
    return ut


SPINKELT_KRONER = 2_000_000   # faste kroner; under dette er serien enkeltforsendelser


def datakvalitet(koder: list[str], alle: dict[str, str], verdi: dict[int, float],
                 faste: dict[int, float], aarene: list[int]) -> dict:
    """Peker på år der serien ikke bør leses som en sammenhengende utvikling.

    To ting flagges, og de er ikke det samme:

    - **brudd**: et årshopp på over 60 % som faller sammen med et år der
      tolltariffen omnummererte en av gruppens koder. Da er det minst like
      sannsynlig at varen byttet kode som at handelen endret seg.
    - **spinkelt_grunnlag**: år der gruppen omsatte for under 2 mill. faste
      kroner. Det er noen få forsendelser, og da flytter én feilklassifisert
      container hele serien. Terskelen er bevisst *absolutt* og ikke en andel av
      dagens nivå: en andelsterskel ville flagget meieri i 1988 (2,3 mill. kr),
      som er et helt reelt tall, bare lite sammenlignet med i dag. Det som gjør
      brødtallet for 1988 ubrukelig er ikke at det er lite i forhold til 2025 —
      det er at 199 000 kr er for lite til å være en målt størrelse.
      En vekstrate regnet fra en slik base sier mer om nevneren enn om
      utviklingen.

    Bruddsøket har i tillegg sitt eget støygulv (`terskel`, 1 % av siste års
    verdi). Uten det ville hvert eneste år der en gruppe svinger mellom 0 og
    200 000 kr blitt rapportert som brudd. Bivirkningen er verdt å kjenne til:
    i en gruppe som har vokst hundre ganger, er de tidligste årene i praksis
    unntatt bruddsøk — de ligger under gulvet uansett. Der er det
    `spinkelt_grunnlag` som er advarselen, ikke bruddlista.
    """
    rev = revisjonsaar(koder, alle)
    siste = max((a for a in aarene if verdi.get(a)), default=None)
    terskel = (verdi.get(siste, 0) or 0) * 0.01

    brudd = []
    for i in range(1, len(aarene)):
        f, n = verdi.get(aarene[i - 1], 0), verdi.get(aarene[i], 0)
        if aarene[i] not in rev or max(f, n) < terskel:
            continue
        if f == 0 or abs(n - f) / f > 0.6:
            brudd.append({
                "aar": aarene[i],
                "fra": f, "til": n,
                "koder_endret": sorted(
                    k for k in koder
                    if (sp := spenn(alle[k])) and (sp[0] == aarene[i] or sp[1] == aarene[i] - 1)
                ),
            })

    spinkelt = [a for a in aarene if faste.get(a, 0) < SPINKELT_KRONER]
    return {
        "forste_solide_aar": next(
            (a for a in aarene if faste.get(a, 0) >= SPINKELT_KRONER), None),
        "spinkelt_grunnlag": _komprimer(spinkelt) or None,
        "mulige_omnummereringsbrudd": brudd,
    }


def summer(koder: list[str], serier: dict, felt: str) -> dict[int, float]:
    ut: dict[int, float] = {}
    for k in koder:
        for aar, v in serier.get(k, {}).get(felt, {}).items():
            ut[aar] = ut.get(aar, 0) + v
    return ut


def bygg(land: str, csv_ut: Path | None, vis_koder: bool, frisk: bool) -> dict:
    print(f"Tabell {TABELL} — metadata …", flush=True)
    variabler = hent_metadata(TABELL)
    landkode = finn_land(variabler["Land"], land)
    aarene = sorted(int(a) for a in variabler["Tid"]["values"])
    alle = matkoder(variabler["Varekoder"])
    print(f"  {land} = {landkode!r}; {len(alle)} varenummer i kapittel 01-24; "
          f"{aarene[0]}-{aarene[-1]}")

    fordelt, eier = grupper_koder(alle)
    enhetsport(fordelt, alle)
    dekningsport(fordelt, alle, aarene)
    print(f"  {sum(len(v) for v in fordelt.values())} varenummer fordelt på "
          f"{len(VAREGRUPPER)} grupper; portene er grønne")

    if vis_koder:
        for gruppe in VAREGRUPPER:
            print(f"\n[{gruppe['id']}] {gruppe['navn']}")
            for k in fordelt[gruppe["id"]]:
                print(f"   {k}  {alle[k][:96]}")
        print()

    print(f"Uttrekk: import fra {land}, {len(alle)} varenummer x {len(aarene)} år")
    serier = hent_serier_cachet(list(alle), landkode, aarene, land, frisk)
    sitc_kontroll = nevnerkontroll_mot_sitc(landkode, serier, aarene)
    kpi = hent_kpi(aarene)
    prisindeks = hent_prisindeks(aarene)
    basis = kpi[max(kpi)]
    print(f"  KPI: {min(kpi)}={kpi[min(kpi)]} … {max(kpi)}={basis} (basisår for faste kroner)")

    def fast(rad: dict[int, float]) -> dict[int, float]:
        """KPI-deflatert: hva belopet er verdt i dagens penger."""
        return {a: v * basis / kpi[a] for a, v in rad.items() if a in kpi}

    def fast_import(rad: dict[int, float], sitc: str) -> dict[int, float]:
        """Deflatert med importprisindeksen for varegruppens egen SITC-gruppe.

        Dette er volumanslaget: hva belopet tilsvarer nar prisen pa nettopp disse
        varene holdes fast. Indeksen starter 1989, sa 1988 faller ut.
        """
        pi = prisindeks[sitc]
        if not pi:
            return {}
        p_basis = pi[max(pi)]
        return {a: v * p_basis / pi[a] for a, v in rad.items() if a in pi}

    # Nevner: alt i kapittel 01-24.
    total_verdi = summer(list(alle), serier, "verdi")
    total_kg = summer(list(alle), serier, "kg")

    # Totalen spenner over bade mat (SITC 0) og drikke/tobakk (SITC 1), og de to
    # har ulik prisbane - vin har steget langt mer enn matvarer. A deflatere hele
    # summen med matvareindeksen ville lagt vinprisveksten inn i "volumet".
    # Derfor en verdivektet indeks: hvert ars vekt er arets egen fordeling mellom
    # kapittel 22/24 (drikke og tobakk) og resten.
    DRIKKEKAP = ("22", "24")
    drikke_verdi = summer([k for k in alle if k[:2] in DRIKKEKAP], serier, "verdi")

    def fast_import_total(rad: dict[int, float]) -> dict[int, float]:
        p0, p1 = prisindeks["0"], prisindeks["1"]
        felles = set(p0) & set(p1)
        if not felles:
            return {}
        b0, b1 = p0[max(felles)], p1[max(felles)]
        ut = {}
        for aar, v in rad.items():
            if aar not in felles or not v:
                continue
            w1 = drikke_verdi.get(aar, 0) / v          # drikkeandel dette aret
            indeks = (1 - w1) * p0[aar] / b0 + w1 * p1[aar] / b1
            if indeks:
                ut[aar] = v / indeks
        return ut

    grupper_ut = []
    byttet: list[str] = []
    sum_gruppe: dict[int, float] = {}
    for gruppe in VAREGRUPPER:
        koder = fordelt[gruppe["id"]]
        verdi, kg = summer(koder, serier, "verdi"), summer(koder, serier, "kg")
        for a, v in verdi.items():
            sum_gruppe[a] = sum_gruppe.get(a, 0) + v
        under = {}
        for uid, pref in gruppe.get("undergrupper", {}).items():
            uk = [k for k in koder if treff(k, pref)]
            under[uid] = {
                "varenummer": uk,
                "verdi": {str(a): v for a, v in sorted(summer(uk, serier, "verdi").items())},
                "kg": {str(a): v for a, v in sorted(summer(uk, serier, "kg").items())},
            }
        pi_kode, pi_merknad = velg_prisindeks(gruppe["prisindeks"], prisindeks, aarene)
        if pi_merknad:
            byttet.append(f"{gruppe['id']}: {pi_merknad}")
        rad = {
            "id": gruppe["id"],
            "navn": gruppe["navn"],
            "note": gruppe.get("note"),
            "antall_varenummer": len(koder),
            "varenummer": {k: alle[k] for k in koder},
            "verdi_lopende": {str(a): v for a, v in sorted(verdi.items())},
            "verdi_faste": {str(a): round(v, 0) for a, v in sorted(fast(verdi).items())},
            "verdi_faste_importpris": {
                str(a): round(v, 0)
                for a, v in sorted(fast_import(verdi, pi_kode).items())},
            "prisindeks_sitc": pi_kode,
            "prisindeks_merknad": pi_merknad,
            "kg": {str(a): v for a, v in sorted(kg.items())},
            "kr_per_kg": {str(a): round(verdi[a] / kg[a], 2)
                          for a in sorted(verdi) if kg.get(a)},
            "undergrupper": under,
            "datakvalitet": datakvalitet(koder, alle, verdi, fast(verdi), aarene),
        }
        # Liter der målet finnes og året er komplett. Gjelder i praksis vin.
        liter = liter_per_aar(koder, alle, serier)
        if liter:
            rad["liter"] = {str(a): v for a, v in sorted(liter.items())}
            rad["kr_per_liter"] = {str(a): round(verdi[a] / liter[a], 2)
                                   for a in sorted(verdi) if liter.get(a)}
        grupper_ut.append(rad)

    # Nevnerkontroll: gruppene + restposten = alt i kapittel 01-24.
    dekket = {k for koder in fordelt.values() for k in koder}
    rest = [k for k in alle if k not in dekket]
    sum_rest = summer(rest, serier, "verdi")
    for aar in aarene:
        fasit = total_verdi.get(aar, 0)
        summen = sum_gruppe.get(aar, 0) + sum_rest.get(aar, 0)
        if abs(summen - fasit) > max(1.0, fasit * 1e-9):
            raise SystemExit(
                f"Nevnerkontrollen slår ikke til for {aar}: grupper + rest = "
                f"{summen:,.0f}, alle kapittel 01-24 = {fasit:,.0f}. "
                "Grupperingen lekker — en varekode telles to ganger eller ingen."
            )

    for linje in byttet:
        print(f"  ! prisindeks {linje}")

    siste = max(a for a in aarene if total_verdi.get(a))
    storste_rest = sorted(
        ({"varenummer": k, "navn": alle[k], "verdi": serier[k]["verdi"][siste]}
         for k in rest if serier.get(k, {}).get("verdi", {}).get(siste)),
        key=lambda d: -d["verdi"],
    )[:15]

    data = {
        "meta": {
            "tittel": f"Norsk import av matvarer fra {land}, {aarene[0]}–{siste}",
            "kilde": "Statistisk sentralbyrå",
            "kilde_url": KILDE_URL,
            "tabell": TABELL,
            "deflator": f"SSB {KPI_TABELL}, KPI årsgjennomsnitt, faste {max(kpi)}-kroner",
            "deflator_alternativ": (
                f"SSB {PRISINDEKS_TABELL}, prisindeks for vareimport etter SITC, "
                f"faste {max(kpi)}-kroner. Gir volumvekst; KPI gir kjøpekraft. "
                "Starter 1989."),
            "dato_hentet": date.today().isoformat(),
            "land": land,
            "landkode": landkode,
            "retning": "import til Norge",
            "enhet": "kroner (løpende og faste) og kilo",
            "aarene": aarene,
            "siste_aar": siste,
            "avgrensning": "HS-kapittel 01-24 (næringsmidler, drikkevarer, tobakk) "
                           "er nevneren; de ti gruppene er et utvalg av den.",
        },
        "grupper": grupper_ut,
        "all_mat_kap_01_24": {
            "verdi_lopende": {str(a): v for a, v in sorted(total_verdi.items())},
            "verdi_faste": {str(a): round(v, 0) for a, v in sorted(fast(total_verdi).items())},
            "verdi_faste_importpris": {
                str(a): round(v, 0)
                for a, v in sorted(fast_import_total(total_verdi).items())},
            "kg": {str(a): v for a, v in sorted(total_kg.items())},
            "antall_varenummer": len(alle),
        },
        "utenfor_gruppene": {
            "andel_siste_aar": round(sum_rest.get(siste, 0) / total_verdi[siste], 4),
            "storste_siste_aar": storste_rest,
        },
        "kpi": {str(a): v for a, v in sorted(kpi.items())},
        "kontroll_mot_sitc": sitc_kontroll,
    }

    if csv_ut:
        skriv_csv(data, csv_ut)
    return data


def skriv_csv(data: dict, sti: Path) -> None:
    sti.parent.mkdir(parents=True, exist_ok=True)
    with sti.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["gruppe_id", "gruppe", "nivaa", "aar", "verdi_kr_lopende",
                    f"verdi_kr_faste_KPI_{data['meta']['siste_aar']}",
                    f"verdi_kr_faste_IMPORTPRIS_{data['meta']['siste_aar']}",
                    "mengde_kg", "kr_per_kg", "mengde_liter", "prisindeks_sitc"])
        for g in data["grupper"]:
            for aar in data["meta"]["aarene"]:
                a = str(aar)
                if a not in g["verdi_lopende"]:
                    continue
                w.writerow([g["id"], g["navn"], "gruppe", aar,
                            g["verdi_lopende"][a], g["verdi_faste"].get(a, ""),
                            g.get("verdi_faste_importpris", {}).get(a, ""),
                            g["kg"].get(a, ""), g["kr_per_kg"].get(a, ""),
                            g.get("liter", {}).get(a, ""), g.get("prisindeks_sitc", "")])
            for uid, u in g["undergrupper"].items():
                for aar in data["meta"]["aarene"]:
                    a = str(aar)
                    if a not in u["verdi"]:
                        continue
                    w.writerow([f"{g['id']}.{uid}", uid, "undergruppe", aar,
                                u["verdi"][a], "", "", u["kg"].get(a, ""), "", "", ""])
        tot = data["all_mat_kap_01_24"]
        for aar in data["meta"]["aarene"]:
            a = str(aar)
            if a in tot["verdi_lopende"]:
                w.writerow(["_alle_matvarer", "All mat/drikke (HS 01-24)", "nevner", aar,
                            tot["verdi_lopende"][a], tot["verdi_faste"].get(a, ""),
                            tot.get("verdi_faste_importpris", {}).get(a, ""),
                            tot["kg"].get(a, ""), "", "", ""])
    print(f"✓ CSV: {sti}")


def kr(v: float) -> str:
    for grense, navn in ((1e9, "mrd"), (1e6, "mill"), (1e3, "tusen")):
        if abs(v) >= grense:
            return f"{v / grense:,.1f} {navn}".replace(",", " ").replace(".", ",")
    return f"{v:,.0f}".replace(",", " ")


def skriv_ut(d: dict) -> None:
    siste, forste = d["meta"]["siste_aar"], d["meta"]["aarene"][0]
    tot = d["all_mat_kap_01_24"]
    print(f"\nNorsk import av mat og drikke fra {d['meta']['land']} "
          f"({d['meta']['tabell']}, hentet {d['meta']['dato_hentet']})")
    print("=" * 92)
    print(f"  All mat/drikke (HS 01-24), {siste}: {kr(tot['verdi_lopende'][str(siste)])} kr")
    print(f"  Samme, {forste}: {kr(tot['verdi_lopende'][str(forste)])} kr løpende / "
          f"{kr(tot['verdi_faste'][str(forste)])} kr i {siste}-kroner")
    print(f"  De {len(d['grupper'])} gruppene dekker "
          f"{100 * (1 - d['utenfor_gruppene']['andel_siste_aar']):.0f} % av verdien i {siste}\n")

    print(f"{'Varegruppe':<40}{siste + 0:>13}{'':2}{forste:>12} {'realvekst':>11}  {'kr/kg':>8}")
    print("-" * 92)
    for g in sorted(d["grupper"], key=lambda x: -x["verdi_lopende"].get(str(siste), 0)):
        n = g["verdi_lopende"].get(str(siste), 0)
        f0 = g["verdi_faste"].get(str(forste), 0)
        fn = g["verdi_faste"].get(str(siste), 0)
        # «*» = vekstraten er regnet fra et år scriptet selv har flagget som for
        # tynt til å måle. Tallet står, men det skal ikke siteres uten forbeholdet.
        tynn = f0 < SPINKELT_KRONER
        vekst = (f"{fn / f0:,.0f}x{'*' if tynn else ' '}".replace(",", " ")
                 if f0 else "–")
        print(f"{g['navn'][:39]:<40}{kr(n):>13}{'':2}{kr(g['verdi_lopende'].get(str(forste), 0)):>12}"
              f" {vekst:>11}  {g['kr_per_kg'].get(str(siste), '–'):>8}")
    print("-" * 92)
    print(f"{'SUM ' + str(len(d['grupper'])) + ' grupper':<40}"
          f"{kr(sum(g['verdi_lopende'].get(str(siste), 0) for g in d['grupper'])):>13}")
    print("  * vekst regnet fra et basisar scriptet har flagget som for tynt — se datakvalitet.")
    print("\n  Datakvalitet — år serien ikke bør leses som sammenhengende utvikling:")
    noe = False
    for g in d["grupper"]:
        dk = g["datakvalitet"]
        merknad = []
        if dk["spinkelt_grunnlag"]:
            merknad.append(f"under {SPINKELT_KRONER / 1e6:.0f} mill. faste kr i "
                           f"{dk['spinkelt_grunnlag']}")
        for b in dk["mulige_omnummereringsbrudd"]:
            merknad.append(f"hopp i {b['aar']} faller sammen med omnummerering "
                           f"({', '.join(b['koder_endret'][:2])})")
        if merknad:
            noe = True
            print(f"    {g['navn'][:34]:<36}{'; '.join(merknad)}")
    if not noe:
        print("    (ingen)")

    print(f"\n  Største matvarer fra {d['meta']['land']} som IKKE er i gruppene ({siste}):")
    for r in d["utenfor_gruppene"]["storste_siste_aar"][:8]:
        print(f"    {r['varenummer']:<16}{kr(r['verdi']):>11}  {r['navn'][:52]}")
    print()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--land", default="Italia")
    p.add_argument("--csv", type=Path, default=None,
                   help="skriv også en lang CSV (utenfor repoet — .gitignore sperrer *.csv)")
    p.add_argument("--frisk", action="store_true",
                   help="ignorer rå-cachen og hent alt på nytt fra SSB")
    p.add_argument("--vis-koder", action="store_true",
                   help="list alle varenummer per gruppe før uttrekket")
    args = p.parse_args()

    data = bygg(args.land, args.csv, args.vis_koder, args.frisk)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ut = CACHE_DIR / f"ssb_italiensk_mat_{_flat(args.land).replace(' ', '_')}.json"
    ut.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    skriv_ut(data)
    print(f"✓ Snapshot: {ut}")


if __name__ == "__main__":
    main()
