"""Akt 3: beveger bevilgningene seg etter at en virksomhet blir evaluert?

Kjøring (ingen nett — leser snapshotene de to hentescriptene skrev):

    python pipeline/analyser_budsjettspor.py
    python pipeline/analyser_budsjettspor.py --vindu 3     # ±3 år i stedet for ±2

Testen er definert HER, i kode, og kjøres én gang. Den rapporteres som den
falt — også hvis svaret er null. «Bevilgningen økte etter evalueringen» er en
verdiløs opplysning uten å vite hva den gjorde uten evaluering: bevilgninger
vokser stort sett, av lønns- og prisjustering alene. Derfor:

**Utfallet måles som andel av statsbudsjettet, ikke i kroner.** Et kapittel som
vokser like mye som alt annet har ikke beveget seg. Andelen er robust mot både
pris- og lønnsjustering uten at vi trenger en deflator vi må forsvare.

**Kontrollgruppen er de samme kapitlene i vinduer uten evaluering**, pluss
kapitler som aldri ble evaluert i perioden. Et kontrollvindu som overlapper et
behandlingsvindu er ikke en kontroll, så de er utelatt — ellers ville de to
fordelingene delt data og forskjellen blitt kunstig liten.

**Signifikansen testes med permutasjon, ikke en t-test.** Fordelingen av
budsjettendringer er tung i halene og ikke normal, og vi har ingen scipy i denne
pipelinen. En permutasjonstest på forskjellen mellom medianene trenger ingen av
delene: den stokker etikettene og teller hvor ofte tilfeldigheten gir like stor
forskjell. Frøet er fast, så tallet er reproduserbart.

**Tre forbehold som skal stå i brødteksten, ikke i en fotnote:**

- Koblingen går Kudos `actor_org_number` → `Virksomhet_id` → kapitlene
  virksomheten fører utgifter på. Det er BESTILLERENS budsjett, ikke det
  evaluerte tiltakets. Planens største metodiske svakhet.
- Dette måler samvariasjon, ikke årsak. En evaluering bestilles ofte NETTOPP
  fordi noe er i endring — omorganisering, kutt, ny satsing. Da er evalueringen
  et symptom på bevegelsen, ikke en årsak til den.
- Kapitler flyttes og slås sammen mellom år. Kapitler med brudd i id eller navn
  droppes, og antallet rapporteres — leseren skal se hvor mye som falt ut.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import random
import statistics
from datetime import date
from pathlib import Path

import kontrakt  # noqa: F401  -- setter utf-8 på stdout/stderr (se CLAUDE.md)

KUDOS_DIR = Path(
    os.environ.get("KUDOS_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "kudos"
)
STATSREGNSKAP_DIR = Path(
    os.environ.get("STATSREGNSKAP_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "statsregnskapet"
)
UTFIL = STATSREGNSKAP_DIR / "budsjettspor.json"

# Vinduet på hver side av evalueringsåret. To år, fordi et budsjett beveger seg
# når Stortinget vedtar det: en evaluering publisert i mars 2019 kan tidligst
# påvirke budsjettet for 2020, og realistisk 2021.
VINDU = 2

# Under dette bærer ikke testen, og da skal den ikke publiseres som et tall.
MIN_N = 30

# Nedre grense for hva et årsbudsjett kan være, i kroner. Statsbudsjettet har
# ligget rundt 1 500–2 000 mrd i perioden, og ingen rimelig lesning av
# «bevilgninger til statens kapitler» havner under 300.
#
# Denne finnes fordi utfallet er en ANDEL: kapitlets beløp delt på årets sum.
# Er nevneren feil, er hver eneste andel feil — men testen kjører like fint og
# gir et pent p-tall. Første kjøring ga 22 mrd i året, fordi utgifter og
# inntekter ble summert i samme bunke og nettet hverandre ut. Resultatet så
# helt troverdig ut.
MIN_AARSSUM = 300e9

# Kontrollgruppa skal være en sammenlignbar rest, ikke en kuriositet. Er den
# mye mindre enn behandlingsgruppa, er det ikke lenger «de samme kapitlene i år
# uten evaluering» — det er de få kapitlene ingen evaluert virksomhet rører,
# og de er systematisk annerledes.
MIN_KONTROLLANDEL = 0.25

# Antall omstokkinger i permutasjonstesten. 10 000 gir p ned til 0,0001, som er
# finere enn noe vi kommer til å påstå.
PERMUTASJONER = 10_000
FRO = 20260830


# ---------------------------------------------------------------- innlesing

def les(fil: Path, hint: str) -> dict:
    if not fil.exists():
        raise SystemExit(f"FEIL: fant ikke {fil}.\n  Kjør først: {hint}")
    return json.loads(fil.read_text(encoding="utf-8"))


def _rens_orgnr(verdi) -> str:
    """Organisasjonsnummeret på én form, uansett hvilken side det kom fra.

    Kudos og statsregnskapet skriver det ulikt — «912 345 678» og «912345678»
    er samme virksomhet, men ikke samme streng. Renses bare den ene siden,
    finner koblingen null, og null ser ut som et funn.
    """
    return str(verdi).strip().replace(" ", "").replace("\u00a0", "")


def orgnummer(ev: dict) -> set[str]:
    """Organisasjonsnumrene til oppdragsgiverne i én evaluering.

    Feltnavnet inne i aktørobjektene er ikke dokumentert, og feltkartleggingen
    viser bare at det finnes. Vi leter derfor etter et felt som SER ut som et
    organisasjonsnummer — ni siffer — framfor å hardkode en nøkkel som kan hete
    noe annet. Finner vi ingen, teller dokumentet som ukoblet, og andelen
    rapporteres.
    """
    funn = set()
    for aktør in ev.get("owners") or []:
        if not isinstance(aktør, dict):
            continue
        for nøkkel, verdi in aktør.items():
            if not isinstance(verdi, (str, int)):
                continue
            tekst = _rens_orgnr(verdi)
            if tekst.isdigit() and len(tekst) == 9 and (
                    "org" in nøkkel.lower() or "nummer" in nøkkel.lower()
                    or "number" in nøkkel.lower()):
                funn.add(tekst)
    return funn


def publiseringsaar(ev: dict) -> int | None:
    tekst = str(ev.get("publish_date") or "")[:4]
    return int(tekst) if tekst.isdigit() else None


# ---------------------------------------------------------------- budsjettet

def bygg_bevilgninger(rader: list[dict]) -> tuple[dict, dict, dict]:
    """Bevilgningslinjene aggregert til (år, kapittel). Dette er UTFALLET.

    Returnerer (kapittelsum, aarssum, kapittelnavn).
    """
    kapittelsum: dict[tuple[int, str], float] = collections.defaultdict(float)
    aarssum: dict[int, float] = collections.defaultdict(float)
    navn: dict[tuple[int, str], set] = collections.defaultdict(set)

    for rad in rader:
        aar = str(rad.get("År") or "").strip()
        kap = str(rad.get("Kapittel_id") or "").strip()
        if not aar.isdigit() or not kap:
            continue
        aar = int(aar)
        kapittelsum[(aar, kap)] += float(rad.get("belop") or 0.0)
        aarssum[aar] += float(rad.get("belop") or 0.0)
        navn[(aar, kap)].add(str(rad.get("Kapittel") or "").strip().lower())
    return dict(kapittelsum), dict(aarssum), dict(navn)


def bygg_orgkart(rader: list[dict]) -> dict[str, set]:
    """Organisasjonsnummer → kapitlene virksomheten fører utgifter på.

    Denne MÅ komme fra regnskapet, ikke fra bevilgningene: bevilgningsfila har
    ingen virksomhetsdimensjon, fordi Stortinget bevilger til kapittel og post
    og ikke til etater. Koblingen Kudos → statsregnskapet går gjennom
    organisasjonsnummeret, og det finnes bare på regnskapssiden.

    Konsekvensen er verdt å merke seg: vi leser hvilke kapitler en virksomhet
    faktisk BRUKER penger på, og måler så hva Stortinget BEVILGET til de samme
    kapitlene. Det er to ulike ting om samme kapittel, og det er med vilje —
    men det gjør koblingen indirekte, og det hører hjemme i forbeholdene.
    """
    org_kap: dict[str, set] = collections.defaultdict(set)
    for rad in rader:
        kap = str(rad.get("Kapittel_id") or "").strip()
        org = _rens_orgnr(rad.get("Virksomhet_id") or "")
        if kap and org:
            org_kap[org].add(kap)
    return dict(org_kap)


def andel(kapittelsum: dict, aarssum: dict, aar: int, kap: str) -> float | None:
    """Kapitlets andel av alle bevilgninger det året."""
    total = aarssum.get(aar)
    belop = kapittelsum.get((aar, kap))
    if not total or belop is None or belop <= 0:
        return None
    return belop / total


def utfall(kapittelsum, aarssum, navn, kap: str, aar: int,
           vindu: int) -> tuple[float | None, str]:
    """Relativ endring i kapitlets budsjettandel fra aar-vindu til aar+vindu.

    Returnerer (verdi, grunn). Verdien er None når vinduet ikke lar seg måle,
    og grunnen sier hvorfor — de grunnene telles og rapporteres.
    """
    før_aar, etter_aar = aar - vindu, aar + vindu
    før = andel(kapittelsum, aarssum, før_aar, kap)
    etter = andel(kapittelsum, aarssum, etter_aar, kap)
    if før is None or etter is None:
        return None, "utenfor_dataperioden"
    # Kapittelnummer gjenbrukes når et kapittel legges ned. Byttet navnet seg,
    # er det ikke det samme kapitlet, og en «endring» ville vært en
    # sammenligning av to ulike ting.
    navn_før = navn.get((før_aar, kap), set())
    navn_etter = navn.get((etter_aar, kap), set())
    if navn_før and navn_etter and not (navn_før & navn_etter):
        return None, "kapitlet_byttet_navn"
    return etter / før - 1, "ok"


# ---------------------------------------------------------------- testen

def bane(kapittelsum, aarssum, kap: str, aar: int, vindu: int) -> list[float] | None:
    """Kapitlets budsjettandel år for år gjennom vinduet, indeksert til 100 i år 0.

    Dette er det figuren tegner. Poenget med å indeksere hver enhet for seg —
    framfor å summere kronene — er at et stort kapittel ellers ville bestemt
    kurven alene: medianen av 200 baner er en typisk bane, summen er Nav og
    Helsedirektoratet.
    """
    basis = andel(kapittelsum, aarssum, aar, kap)
    if not basis:
        return None
    ut = []
    for forskyvning in range(-vindu, vindu + 1):
        verdi = andel(kapittelsum, aarssum, aar + forskyvning, kap)
        if verdi is None:
            return None
        ut.append(100 * verdi / basis)
    return ut


def median_bane(baner: list[list[float]]) -> list[float]:
    """Medianen for hver forskyvning. Ikke en enkelt banes forløp — en typisk verdi
    per år, som er det en leser av figuren skal kunne lese av."""
    return [round(statistics.median(kolonne), 2) for kolonne in zip(*baner)]


def permutasjonstest(behandlet: list[float], kontroll: list[float],
                     runder: int = PERMUTASJONER) -> float:
    """Tosidig p-verdi for forskjellen mellom medianene.

    Nullhypotesen er at etikettene ikke betyr noe. Vi stokker dem og teller hvor
    ofte tilfeldigheten gir en forskjell minst like stor som den observerte.
    """
    observert = abs(statistics.median(behandlet) - statistics.median(kontroll))
    alle = behandlet + kontroll
    n = len(behandlet)
    rng = random.Random(FRO)
    minst_like_stor = 0
    for _ in range(runder):
        rng.shuffle(alle)
        forskjell = abs(statistics.median(alle[:n]) - statistics.median(alle[n:]))
        if forskjell >= observert:
            minst_like_stor += 1
    # +1 i teller og nevner: en p-verdi på nøyaktig 0 er en påstand testen ikke
    # kan bære — den sier bare at ingen av 10 000 omstokkinger nådde opp.
    return (minst_like_stor + 1) / (runder + 1)


def oppsummer(verdier: list[float]) -> dict:
    if not verdier:
        return {"n": 0}
    sortert = sorted(verdier)
    return {
        "n": len(sortert),
        "median": round(statistics.median(sortert), 4),
        "gjennomsnitt": round(statistics.fmean(sortert), 4),
        "kvartil_1": round(sortert[len(sortert) // 4], 4),
        "kvartil_3": round(sortert[3 * len(sortert) // 4], 4),
        "min": round(sortert[0], 4),
        "maks": round(sortert[-1], 4),
    }


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vindu", type=int, default=VINDU,
                    help=f"antall år på hver side av evalueringsåret (standard {VINDU})")
    ap.add_argument("--permutasjoner", type=int, default=PERMUTASJONER)
    args = ap.parse_args()

    kudos = les(KUDOS_DIR / "evalueringer.json",
                "python pipeline/hent_kudos_evalueringer.py")
    bevilgninger = les(STATSREGNSKAP_DIR / "bevilgninger_aarlig.json",
                       "python pipeline/hent_statsregnskapet.py --sett bevilgninger")
    # Begge settene trengs, og de har ulik form: bevilgningsfila mangler
    # virksomhetskolonnen, så orgnr-koblingen må hentes fra regnskapet.
    regnskap = les(STATSREGNSKAP_DIR / "statsregnskapet_aarlig.json",
                   "python pipeline/hent_statsregnskapet.py --sett statsregnskapet")

    evalueringer = kudos.get("dokumenter") or []
    kapittelsum, aarssum, navn = bygg_bevilgninger(bevilgninger.get("rader") or [])
    org_kap = bygg_orgkart(regnskap.get("rader") or [])
    aar_fra, aar_til = min(aarssum), max(aarssum)

    # Sanity på nevneren FØR noe regnes ut. En andel av feil total er feil, og
    # den feilen er usynlig i resultatet.
    typisk = statistics.median(aarssum.values())
    if typisk < MIN_AARSSUM:
        raise SystemExit(
            f"FEIL: samlet bevilgning er {typisk / 1e9:.1f} mrd i et typisk år.\n"
            f"  Statsbudsjettet er over {MIN_AARSSUM / 1e9:.0f} mrd. Da er ikke\n"
            "  dette hele budsjettet, og utfallet — kapitlets ANDEL av årets sum\n"
            "  — er regnet mot feil nevner.\n"
            "  Vanligste årsak: utgifter og inntekter er summert i samme bunke\n"
            "  og netter hverandre ut. Kjør hent_statsregnskapet.py og les\n"
            "  «fordelt på»-linjene: de viser hvilke verdier som må filtreres\n"
            "  bort før dette tallet betyr noe.\n"
            "  Et nullresultat fra en ødelagt måling er ikke et nullresultat."
        )
    print(f"Bevilgninger: {aar_fra}–{aar_til}, "
          f"{len({k for _, k in kapittelsum})} kapitler (utfallet)")
    print(f"Regnskapet:   {len(org_kap)} virksomheter med organisasjonsnummer "
          f"(koblingen)")
    # Fører virksomhetene utgifter på kapitler bevilgningsfila ikke kjenner,
    # er de to settene ikke om samme verden, og resten av analysen er tull.
    kjente = {k for _, k in kapittelsum}
    truffet = {k for kapitler in org_kap.values() for k in kapitler} & kjente
    print(f"  {len(truffet)} kapitler finnes i begge settene")
    if not truffet:
        raise SystemExit(
            "FEIL: ingen kapittel-id fra regnskapet finnes i bevilgningene.\n"
            "  De to filene er da ikke om samme verden — sjekk at Kapittel_id\n"
            "  har samme format i begge (nullpadding, lengde) før du tolker\n"
            "  noe som helst av dette."
        )
    print(f"Evalueringer: {len(evalueringer)}")

    # --- kobling Kudos → statsregnskapet
    med_org = 0
    koblet = 0
    hendelser: set[tuple[str, int]] = set()      # (kapittel, evalueringsår)
    berørte_org: set[str] = set()
    for ev in evalueringer:
        orgnr = orgnummer(ev)
        aar = publiseringsaar(ev)
        if not orgnr:
            continue
        med_org += 1
        if aar is None:
            continue
        kapitler = {k for o in orgnr for k in org_kap.get(o, ())}
        if not kapitler:
            continue
        koblet += 1
        berørte_org |= orgnr & set(org_kap)
        for kap in kapitler:
            hendelser.add((kap, aar))

    print(f"\nKobling:")
    print(f"  {med_org} av {len(evalueringer)} evalueringer har organisasjonsnummer "
          f"({100 * med_org / max(len(evalueringer), 1):.0f} %)")
    print(f"  {koblet} lot seg koble til et kapittel i statsregnskapet "
          f"({100 * koblet / max(len(evalueringer), 1):.0f} %)")
    print(f"  {len(berørte_org)} virksomheter, {len(hendelser)} "
          f"(kapittel, år)-hendelser")
    if not hendelser:
        # Prøver som viser hvorfor. Uten dem er «null treff» et mysterium man
        # må skrive et engangsskript for å løse, og null ser dessuten ut som
        # et funn — «ingen evalueringer påvirket budsjettet» — når det bare er
        # to formater som ikke møtes.
        fra_kudos = sorted({o for e in evalueringer[:500] for o in orgnummer(e)})[:5]
        fra_budsjett = sorted(org_kap)[:5]
        raise SystemExit(
            "FEIL: ingen evalueringer lot seg koble til et kapittel.\n"
            f"  organisasjonsnumre i Kudos:        {fra_kudos or '(fant ingen)'}\n"
            f"  Virksomhet_id i bevilgningene:     {fra_budsjett or '(fant ingen)'}\n"
            "  Ser de like ut, er feilen i koblingen; ser de ulike ut, er det\n"
            "  formatet. Null treff er uansett ikke et funn."
        )

    # --- behandlings- og kontrollvinduer
    # Et kontrollvindu må ikke overlappe et behandlingsvindu: da ville de to
    # fordelingene delt de samme budsjettårene, og forskjellen blitt kunstig
    # liten. Vi holder derfor hele ±vindu unna en hendelse.
    hendelsesaar: dict[str, set] = collections.defaultdict(set)
    for kap, aar in hendelser:
        hendelsesaar[kap].add(aar)

    alle_kapitler = sorted({k for _, k in kapittelsum})
    mulige_aar = range(aar_fra + args.vindu, aar_til - args.vindu + 1)

    behandlet: list[float] = []
    kontroll: list[float] = []
    bane_behandlet: list[list[float]] = []
    bane_kontroll: list[list[float]] = []
    forkastet: collections.Counter = collections.Counter()

    for kap in alle_kapitler:
        for aar in mulige_aar:
            er_hendelse = aar in hendelsesaar.get(kap, ())
            nær_hendelse = any(abs(aar - h) <= args.vindu
                               for h in hendelsesaar.get(kap, ()))
            if not er_hendelse and nær_hendelse:
                forkastet["kontroll_overlapper_hendelse"] += 1
                continue
            verdi, grunn = utfall(kapittelsum, aarssum, navn, kap, aar, args.vindu)
            if verdi is None:
                forkastet[grunn] += 1
                continue
            (behandlet if er_hendelse else kontroll).append(verdi)
            b = bane(kapittelsum, aarssum, kap, aar, args.vindu)
            if b is None:
                forkastet["bane_ufullstendig"] += 1
            else:
                (bane_behandlet if er_hendelse else bane_kontroll).append(b)

    print(f"\nVinduer (±{args.vindu} år):")
    print(f"  behandling: {len(behandlet)}")
    print(f"  kontroll:   {len(kontroll)}")
    for grunn, antall in forkastet.most_common():
        print(f"  forkastet — {grunn}: {antall}")

    andel_kontroll = len(kontroll) / max(1, len(behandlet) + len(kontroll))
    if andel_kontroll < MIN_KONTROLLANDEL:
        print(f"\n  ⚠ Kontrollgruppa er bare {100 * andel_kontroll:.0f} % av "
              f"vinduene.", flush=True)
        print("    Evalueringene dekker da nesten hele budsjettet, og "
              "«kapitler uten", flush=True)
        print("    evaluering» er ikke en sammenlignbar rest — det er de få "
              "kapitlene", flush=True)
        print("    ingen evaluert virksomhet fører utgifter på. Forskjellen "
              "mellom", flush=True)
        print("    gruppene måler da også dette, og det skal stå i teksten.",
              flush=True)

    if len(behandlet) < MIN_N or len(kontroll) < MIN_N:
        raise SystemExit(
            f"FEIL: {len(behandlet)} behandlings- og {len(kontroll)} "
            f"kontrollvinduer.\n"
            f"  Testen krever minst {MIN_N} i hver. Under det er spredningen så\n"
            f"  stor at et hvilket som helst resultat er forenlig med ingenting,\n"
            f"  og et tall vi ikke kan forsvare er verre enn ingen akt 3.\n"
            f"  Skriv akten om til «datagrunnlaget rekker ikke» — det er også\n"
            f"  et funn, og et ærligere ett."
        )

    b, k = oppsummer(behandlet), oppsummer(kontroll)
    p = permutasjonstest(behandlet, kontroll, args.permutasjoner)
    forskjell = b["median"] - k["median"]

    print(f"\nEndring i kapitlets andel av statsbudsjettet, "
          f"fra {args.vindu} år før til {args.vindu} år etter:")
    for merkelapp, s in (("evaluert", b), ("kontroll", k)):
        print(f"  {merkelapp:9} n={s['n']:5}  median {100 * s['median']:+6.2f} %  "
              f"kvartiler {100 * s['kvartil_1']:+.1f} … {100 * s['kvartil_3']:+.1f} %")
    print(f"\n  forskjell i median: {100 * forskjell:+.2f} prosentpoeng")
    print(f"  p (permutasjon, {args.permutasjoner} runder): {p:.4f}")
    if p >= 0.05:
        print("\n  De to fordelingene er ikke til å skille fra hverandre.")
        print("  Det er resultatet, og det skal skrives rett ut: en evaluering")
        print("  følges ikke av en målbar bevegelse i bestillerens budsjett.")
    else:
        print("\n  Forskjellen er større enn omstokkingen gir. Merk fortsatt at")
        print("  dette er samvariasjon: en evaluering bestilles ofte nettopp")
        print("  fordi noe er i endring.")

    STATSREGNSKAP_DIR.mkdir(parents=True, exist_ok=True)
    UTFIL.write_text(json.dumps({
        "dato": date.today().isoformat(),
        "metode": (f"Endring i kapitlets andel av samlede bevilgninger fra "
                   f"{args.vindu} år før til {args.vindu} år etter en "
                   f"evaluering av en virksomhet som fører utgifter på kapitlet, "
                   f"mot kontrollvinduer uten evaluering."),
        "forbehold": ("Måler bestillerens kapittel, ikke det evaluerte tiltakets. "
                      "Samvariasjon, ikke årsak — en evaluering bestilles ofte "
                      "nettopp fordi noe er i endring."),
        "dataperiode": [aar_fra, aar_til],
        "vindu_aar": args.vindu,
        "kilder": {"utfall": "bevilgninger_aarlig.json",
                   "orgnr_kobling": "statsregnskapet_aarlig.json"},
        "kobling": {"evalueringer": len(evalueringer), "med_orgnummer": med_org,
                    "koblet_til_kapittel": koblet,
                    "virksomheter": len(berørte_org),
                    "hendelser": len(hendelser)},
        "forkastet": dict(forkastet),
        "kontrollandel": round(andel_kontroll, 3),
        "aarssum_typisk": round(typisk, 2),
        "behandling": b,
        "kontroll": k,
        "spor": {
            "forskyvninger": list(range(-args.vindu, args.vindu + 1)),
            "merknad": ("Median av kapitlenes egen budsjettandel, indeksert til "
                        "100 i evalueringsåret. Hver enhet indekseres for seg, "
                        "så et stort kapittel ikke bestemmer kurven alene."),
            "evaluert": median_bane(bane_behandlet) if bane_behandlet else [],
            "kontroll": median_bane(bane_kontroll) if bane_kontroll else [],
            "n_evaluert": len(bane_behandlet),
            "n_kontroll": len(bane_kontroll),
        },
        "forskjell_median": round(forskjell, 4),
        "p_verdi": round(p, 4),
        "permutasjoner": args.permutasjoner,
        "fro": FRO,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nSkrev {UTFIL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
