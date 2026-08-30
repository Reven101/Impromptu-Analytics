"""Bygger historien «Hvor mange evalueringer fikk konsekvenser?».

Kjøring:

    python pipeline/bygg_historie_evalueringer.py
    python pipeline/kontrakt.py
    python pipeline/redaktorsjekk.py
    python pipeline/bygg_manifest.py

Setter sammen fire snapshots til én data.json. Scriptet henter ingenting selv —
det leser det de fire foregående skrev, og feiler forklarende hvis et av dem
mangler. Rekkefølgen står i kjøreoppskriften; hvert unntak her navngir
kommandoen som mangler.

Tre valg som avgjør hva historien påstår:

- **Overskriftstallet er API-ets `meta.total`, grunnlaget er det vi faktisk fikk
  servert.** Kudos teller flere dokumenter enn det serverer — nye publiseres mens
  pagineringen står på, og halen skyves forbi siste side. Differansen er liten
  (rundt en halv promille), men den er kjent, og da skal den stå i figuren
  framfor å rundes bort.

- **Akt 2 er en nedre grense, og nevneren er ikke hele korpuset.** Vi teller
  evalueringer som navngis ordrett i et stortingsdokument, i de sesjonene vi har
  fulltekst for. En evaluering kan bli lest uten å bli navngitt, og en evaluering
  fra 2008 kan ikke telles som «aldri nevnt» når vi ikke har lett i 2008. Begge
  deler står i teksten hver gang tallet nevnes.

- **Vekstkurven måler også registreringspraksis.** Kudos er bygget opp i
  etterkant, sammen med Nasjonalbiblioteket. At det ligger flere evalueringer fra
  2020 enn fra 2005 er delvis at det ble laget flere, delvis at de nyere er
  registrert. Uten den setningen er «industriell skala»-kurven et artefakt. Det er
  historiens viktigste enkeltforbehold, og derfor står det i brødteksten.
"""

from __future__ import annotations

import collections
import json
import os
import statistics
from datetime import date
from pathlib import Path

import kontrakt
from kontrakt import INNHOLD_DIR
# Nøkkelen og teksten hentes fra kategoriseringen selv, ikke skrevet av på nytt.
# Skriver man dem av, drifter de fra hverandre ved første lille endring — og en
# nøkkel som ikke stemmer gir null temaer, som ser ut som at ingen evaluering
# har tema.
from kategoriser_evalueringer import nokkel as temanokkel, tekst_for

SLUG = "evalueringene"

KUDOS_DIR = Path(
    os.environ.get("KUDOS_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "kudos"
)
STORTINGET_DIR = Path(
    os.environ.get("STORTINGET_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "stortinget"
)
STATSREGNSKAP_DIR = Path(
    os.environ.get("STATSREGNSKAP_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "statsregnskapet"
)
TEMACACHE = Path(__file__).resolve().parent / "cache" / "kudostema_cache.json"

# Toppliste-lengder. Femten rader er så mye en liggende søylefigur bærer før
# etikettene blir uleselige på mobil.
TOPP_BESTILLERE = 15
TOPP_LEST = 12

# Under dette blir «andel navngitt» ren støy: én av to er 50 %, og betyr ingenting.
MIN_FOR_ANDEL = 25

# Kategorinøkler fra kategoriser_evalueringer.py, til lesbare navn. Håndskrevet:
# nøklene er maskinvennlige, figuren skal være menneskevennlig.
TEMANAVN = {
    "helse_og_omsorg": "Helse og omsorg",
    "utdanning_og_forskning": "Utdanning og forskning",
    "arbeid_og_velferd": "Arbeid og velferd",
    "samferdsel": "Samferdsel",
    "justis_og_beredskap": "Justis og beredskap",
    "forsvar": "Forsvar",
    "klima_miljo_og_energi": "Klima, miljø og energi",
    "naering_og_fiskeri": "Næring og fiskeri",
    "landbruk_og_mat": "Landbruk og mat",
    "kommunal_og_distrikt": "Kommunal og distrikt",
    "kultur_og_frivillighet": "Kultur og frivillighet",
    "innvandring_og_integrering": "Innvandring og integrering",
    "finans_og_skatt": "Finans og skatt",
    "utenriks_og_bistand": "Utenriks og bistand",
    "digitalisering_og_forvaltning": "Digitalisering og forvaltning",
    "annet": "Annet",
    "uklar": "For lite tekst til å avgjøre",
}


# ---------------------------------------------------------------- innlesing

def les(fil: Path, kommando: str) -> dict:
    if not fil.exists():
        raise SystemExit(
            f"FEIL: {fil} mangler.\n"
            f"  Kjør først: {kommando}\n"
            "  Historien bygges ikke uten — en akt som stille faller ut ser ut\n"
            "  som et funn, og det er verre enn en feilmelding."
        )
    return json.loads(fil.read_text(encoding="utf-8"))


def oppdragsgivere(ev: dict) -> list[str]:
    """`owners` er oppdragsgiveren; `authoring_actors` skrev rapporten. Kilden
    skiller dem, så det gjør vi også — historien handler om hvem som BESTILLER."""
    ut = [a["name"] for a in (ev.get("owners") or [])
          if isinstance(a, dict) and a.get("name")]
    return ut or ["(ukjent oppdragsgiver)"]


# ---------------------------------------------------------------- main

def main() -> None:
    kudos = les(KUDOS_DIR / "evalueringer.json",
                "python pipeline/hent_kudos_evalueringer.py")
    kobling = les(STORTINGET_DIR / "navngitte_evalueringer.json",
                  "python pipeline/koble_evalueringer_stortinget.py")
    vedtak = les(STORTINGET_DIR / "vedtak.json",
                 "python pipeline/hent_stortinget_vedtak.py")
    spor = les(STATSREGNSKAP_DIR / "budsjettspor.json",
               "python pipeline/analyser_budsjettspor.py")
    temaer = les(TEMACACHE, "python pipeline/kategoriser_evalueringer.py --alle")

    dokumenter = kudos.get("dokumenter") or []
    api_meta = kudos.get("api_meta") or {}
    oppgitt = api_meta.get("total") or len(dokumenter)
    manko = api_meta.get("manko") or 0
    if len(dokumenter) < 5_000:
        raise SystemExit(
            f"FEIL: bare {len(dokumenter)} evalueringer i snapshotet. "
            "Historien påstår «industriell skala» — det tallet må være ekte."
        )

    # --- akt 1: skalaen
    per_aar = collections.Counter()
    uten_aar = 0
    for ev in dokumenter:
        aar = str(ev.get("publish_date") or "")[:4]
        if aar.isdigit():
            per_aar[int(aar)] += 1
        else:
            uten_aar += 1

    # Siste år er ufullstendig — vi står midt i det — og en halv årgang tegnet
    # som et fall er en løgn figuren forteller uten et ord.
    i_aar = date.today().year
    aarspunkter = sorted((a, n) for a, n in per_aar.items() if a < i_aar and a >= 1990)
    toppaar, topptall = max(aarspunkter, key=lambda p: p[1])

    per_giver = collections.Counter()
    for ev in dokumenter:
        for g in oppdragsgivere(ev):
            per_giver[g] += 1
    bestillere = per_giver.most_common(TOPP_BESTILLERE)

    # Snitt per uke, over de ti siste hele årene. Hele korpuset ville blandet inn
    # åtti- og nittitallet, da registeret knapt fylles.
    siste_ti = [n for a, n in aarspunkter if a >= i_aar - 10]
    per_uke = sum(siste_ti) / (len(siste_ti) * 52) if siste_ti else 0

    # --- temaene
    tema_oppslag = temaer.get("temaer") or {}
    per_tema = collections.Counter()
    uten_tema = 0
    for ev in dokumenter:
        post = tema_oppslag.get(temanokkel(tekst_for(ev)))
        if post and post.get("kategori"):
            per_tema[post["kategori"]] += 1
        else:
            uten_tema += 1
    if not per_tema:
        raise SystemExit(
            "FEIL: ingen av evalueringene fant sin kategori i temacachen.\n"
            "  Cachen er laget med promptversjon "
            f"{(temaer.get('metode') or {}).get('promptversjon', '?')!r}; koden\n"
            "  bruker en annen. Bumpes PROMPTVERSJON, må kategoriseringen kjøres\n"
            "  på nytt — en tom temafigur ville sett ut som at ingen evaluering\n"
            "  har tema."
        )

    # --- akt 2: trakten
    trakt = vedtak.get("trakt") or {}
    nevner = trakt.get("publisert") or kobling.get("nevner") or 0
    navngitt = trakt.get("navngitt") or kobling.get("navngitt") or 0
    behandlet = trakt.get("behandlet") or 0
    vedtatt = trakt.get("vedtatt") or 0
    dekning = kobling.get("dekning") or {}
    andel_navngitt = 100 * navngitt / nevner if nevner else 0

    per_giver_kobling = kobling.get("per_oppdragsgiver") or {}
    lest = [
        (navn, 100 * tall["navngitt"] / tall["totalt"], tall["totalt"], tall["navngitt"])
        for navn, tall in per_giver_kobling.items()
        if tall.get("totalt", 0) >= MIN_FOR_ANDEL
    ]
    lest.sort(key=lambda r: r[1], reverse=True)
    lest = lest[:TOPP_LEST]
    if not lest:
        raise SystemExit(
            f"FEIL: ingen oppdragsgiver har {MIN_FOR_ANDEL} evalueringer innenfor\n"
            "  dekningsvinduet. Da finnes ikke fordelingen figuren skal vise, og\n"
            "  akt 2 må skrives om til totalen alene."
        )

    # --- akt 3: budsjettsporet
    sporet = spor.get("spor") or {}
    forskyvninger = sporet.get("forskyvninger") or []
    if not (sporet.get("evaluert") and sporet.get("kontroll")):
        raise SystemExit(
            "FEIL: budsjettsporet mangler banene figuren tegner.\n"
            "  Kjør analyser_budsjettspor.py på nytt — den skriver «spor» med\n"
            "  én median per forskyvning for hver gruppe."
        )
    p_verdi = spor.get("p_verdi", 1.0)
    skiller_seg = p_verdi < 0.05

    data = {
        "meta": {
            "tittel": f"{oppgitt:,}".replace(",", " ") + " evalueringer — hvor mange fikk konsekvenser?",
            "kilde": "Kudos (DFØ), Stortinget, statsregnskapet.no (DFØ)",
            "kilde_url": "https://kudos.dfo.no/apne-data",
            "dato_hentet": kudos.get("dato_hentet") or date.today().isoformat(),
            "geografi": "Norge",
            "enhet": "evalueringer",
            "oppdateringsfrekvens": "løpende",
            "beskrivelse": (
                f"Forvaltningen har publisert {oppgitt:,}".replace(",", " ")
                + " evalueringer av seg selv. Vi talte hvor mange av dem som "
                  "navngis i et stortingsdokument, og hva som skjer med "
                  "bestillerens budsjett etterpå."
            ),
            # Står som utkast til de tre stikkprøvene i planen er gjort: tre
            # oppdragsgivere slått opp på kudos.dfo.no, og tre påståtte
            # stortingstreff åpnet og lest. Akt 2 kan ikke publiseres uten.
            "utkast": True,
        },
        "visninger": {
            "hero": {
                "type": "hero",
                "eyebrow": "Kunnskapsgrunnlaget",
                "sporsmal": "Hvor mye kunnskap produserer forvaltningen om seg selv — og hvor blir den av?",
                "rader": [
                    {"etikett": "Evalueringer i Kudos", "verdi": f"{oppgitt:,}".replace(",", " "),
                     "detalj": f"{len(dokumenter):,}".replace(",", " ") + " hentet"},
                    {"etikett": "Oppdragsgivere", "verdi": f"{len(per_giver):,}".replace(",", " "),
                     "detalj": f"{bestillere[0][0]} har flest"},
                    {"etikett": "Nye per uke", "verdi": f"{per_uke:.1f}".replace(".", ","),
                     "detalj": "snitt siste ti år"},
                    {"etikett": "Navngitt på Stortinget", "verdi": f"{andel_navngitt:.1f} %".replace(".", ","),
                     "detalj": f"{navngitt} av {nevner} i dekningsvinduet"},
                ],
                "fotnote": (
                    f"Kudos oppgir {oppgitt} dokumenter og serverte "
                    f"{len(dokumenter)}; de siste {manko} skyves forbi siste side "
                    "mens pagineringen står på. Andelen navngitt er en nedre "
                    "grense: den teller ordrett navngiving i "
                    f"{dekning.get('sesjoner', '?')} stortingssesjoner "
                    f"({dekning.get('fra_aar', '?')}–{dekning.get('til_aar', '?')})."
                ),
            },
            "tempo": {
                "type": "tidslinje",
                "tittel": f"Toppåret var {toppaar}, med {topptall} evalueringer",
                "undertekst": "Evalueringer i Kudos per publiseringsår",
                "enhet": "evalueringer",
                "stil": "søyle",
                "x_navn": "Publiseringsår",
                "serier": [{"navn": "Evalueringer",
                            "punkter": [[a, n] for a, n in aarspunkter]}],
            },
            "bestillerne": {
                "type": "rangering",
                "tittel": "Hvem bestiller kunnskapen",
                "undertekst": f"De {len(bestillere)} oppdragsgiverne med flest evalueringer i Kudos",
                "enhet": "evalueringer",
                "rader": [{"navn": navn, "verdi": n} for navn, n in bestillere],
            },
            "temaene": {
                "type": "rangering",
                "tittel": "Hva evalueres",
                "undertekst": "Evalueringer per politikkområde, klassifisert av en språkmodell",
                "enhet": "evalueringer",
                "rader": [{"navn": TEMANAVN.get(k, k), "verdi": n}
                          for k, n in per_tema.most_common()],
            },
            "trakten": {
                "type": "rangering",
                "tittel": "Fra publisert til vedtatt",
                "undertekst": "Evalueringer publisert i dekningsvinduet, og hvor langt de kom",
                "enhet": "evalueringer",
                "sorter": False,
                "rader": [
                    {"navn": "Publisert", "verdi": nevner,
                     "detalj": "i sesjonene vi har fulltekst for"},
                    {"navn": "Navngitt i et dokument", "verdi": navngitt,
                     "detalj": "ordrett tittelmatch"},
                    {"navn": "Knyttet til en sak", "verdi": behandlet,
                     "detalj": "saksbundne dokumenttyper"},
                    {"navn": "Saken fikk et vedtak", "verdi": vedtatt,
                     "detalj": "ikke nødvendigvis evalueringens anbefaling"},
                ],
            },
            "hvem_blir_lest": {
                "type": "rangering",
                "tittel": "Hvem får sin evaluering navngitt",
                "undertekst": (f"Andel navngitt på Stortinget, oppdragsgivere med "
                               f"minst {MIN_FOR_ANDEL} evalueringer i vinduet"),
                "enhet": "prosent",
                "rader": [{"navn": navn, "verdi": round(andel, 1),
                           "detalj": f"{treff} av {totalt}"}
                          for navn, andel, totalt, treff in lest],
            },
            "budsjettsporet": {
                "type": "tidslinje",
                "tittel": ("Budsjettet beveger seg ikke målbart etter en evaluering"
                           if not skiller_seg else
                           "Budsjettet beveger seg etter en evaluering — men ikke nødvendigvis av den"),
                "undertekst": ("Kapitlets andel av statsbudsjettet, indeksert til 100 "
                               "i evalueringsåret"),
                "enhet": "indeks",
                "x_navn": "År fra evalueringen",
                "serier": [
                    {"navn": f"Evaluert (n={sporet.get('n_evaluert', 0)})",
                     "punkter": [[x, y] for x, y in zip(forskyvninger, sporet["evaluert"])]},
                    {"navn": f"Kontroll (n={sporet.get('n_kontroll', 0)})",
                     "punkter": [[x, y] for x, y in zip(forskyvninger, sporet["kontroll"])]},
                ],
            },
            "forbeholdene": {
                "type": "kortgalleri",
                "tittel": "Hva som ikke er med",
                "undertekst": "Tall som ellers ville forsvunnet i metoden",
                "kort": [
                    {"overtittel": "Aldri servert", "verdi": str(manko),
                     "detalj": f"av {oppgitt} Kudos teller"},
                    {"overtittel": "Uten publiseringsår", "verdi": str(uten_aar),
                     "detalj": "faller ut av tempokurven"},
                    {"overtittel": "Uten tema", "verdi": str(uten_tema),
                     "detalj": "ikke klassifisert"},
                    {"overtittel": "Utenfor dekningsvinduet", "verdi": str(kobling.get("utenfor_dekning", 0)),
                     "detalj": "publisert før sesjonene vi søkte i"},
                    {"overtittel": "For generisk tittel", "verdi": str(kobling.get("utelatt_generisk", 0)),
                     "detalj": "et treff ville ikke bevist noe"},
                    {"overtittel": "Uten sakstilknytning", "verdi": str(vedtak.get("uten_sakstilknytning", 0)),
                     "detalj": "nevnt i referat, som dekker mange saker"},
                ],
            },
        },
    }

    data, notater = kontrakt.flett_redaksjon(data, SLUG)

    mappe = INNHOLD_DIR / SLUG
    mappe.mkdir(parents=True, exist_ok=True)
    (mappe / "data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if notater:
        print(f"  redaksjon.json overstyrer {len(notater)} felt:")
        for n in notater:
            print(f"    {n}")

    # Kontrolltall til konsollen. De skal leses, ikke bare produseres.
    print(f"{SLUG}:")
    print(f"  korpus:   {len(dokumenter)} hentet av {oppgitt} oppgitt "
          f"({manko} aldri servert)")
    print(f"  tempo:    {len(aarspunkter)} årganger, topp {toppaar} ({topptall}), "
          f"{uten_aar} uten år")
    print(f"  temaer:   {len(per_tema)} kategorier, sum {sum(per_tema.values())}, "
          f"{uten_tema} uten")
    print(f"  trakt:    {nevner} → {navngitt} → {behandlet} → {vedtatt}")
    print(f"  akt 3:    n={spor['behandling']['n']}/{spor['kontroll']['n']}, "
          f"p={p_verdi}, forskjell {100 * spor['forskjell_median']:+.2f} pp")

    if sum(per_tema.values()) + uten_tema != len(dokumenter):
        raise SystemExit("FEIL: temafordelingen summerer ikke til korpuset.")
    if not (nevner >= navngitt >= behandlet >= vedtatt):
        raise SystemExit("FEIL: trakten er ikke monotont synkende.")

    feil = kontrakt.valider_snapshot(data, SLUG)
    print(f"  validering: {'OK' if not feil else feil}")
    print(f"  {mappe / 'data.json'}")
    print("\n  Står som utkast. Fjern flagget først når stikkprøvene er gjort:")
    print("  tre oppdragsgivere slått opp på kudos.dfo.no, og tre påståtte")
    print("  stortingstreff åpnet og lest — er det rapporten som omtales?")


if __name__ == "__main__":
    main()
