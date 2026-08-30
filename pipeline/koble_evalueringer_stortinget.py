"""Teller hvor mange evalueringer som blir NAVNGITT i et stortingsdokument.

Kjøring:

    python pipeline/koble_evalueringer_stortinget.py
    python pipeline/koble_evalueringer_stortinget.py --vis-treff 40

Dette er akt 2. Måten den teller på er valgt bevisst, og valget er strengere
enn alternativet:

**Vi teller verbatim navngiving, ikke temalikhet.** En temamatch — «det kom en
stortingssak om samferdsel innen 24 måneder» — treffer nesten alltid, fordi
ethvert tema får en stortingssak før eller siden. Den ville gjort gapet mindre
enn det er. At et dokument gjengir rapportens tittel ordrett er derimot ingen
tilfeldighet: basisraten er nær null, så treffet betyr noe uten at vi trenger
en nullmodell.

**Prisen er at tallet er en NEDRE grense.** En evaluering kan bli lest, brukt
og fulgt opp uten å bli navngitt. Tallet sier «minst så mange ble lest» — aldri
«bare så mange ble lest». Det skal stå hver gang tallet nevnes.

**Nevneren er begrenset til årene vi har lett i.** Vi har fulltekst for de
sesjonene hent_stortinget_publikasjoner.py hentet. En evaluering fra 2008 kan
ikke telles som «aldri nevnt» når vi ikke har lest 2008-sesjonen. Bare
evalueringer publisert innenfor dekningen inngår.

**Normaliseringen er delt med hentescriptet.** `normaliser` importeres derfra
framfor å gjenskapes. En match som feiler fordi den ene siden har « og den
andre ", er den vondeste feilen å oppdage — og den oppstår i det øyeblikket to
kopier av samme funksjon begynner å drifte fra hverandre.

Kilder, begge utenfor repoet:
    impromptu_raadata/kudos/evalueringer.json
    impromptu_raadata/stortinget/publikasjoner_<sesjon>.jsonl
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import kontrakt  # noqa: F401  -- setter utf-8 på stdout (se CLAUDE.md)
from hent_stortinget_publikasjoner import normaliser

KUDOS_DIR = Path(
    os.environ.get("KUDOS_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "kudos"
)
STORTINGET_DIR = Path(
    os.environ.get("STORTINGET_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "stortinget"
)
UTFIL = STORTINGET_DIR / "navngitte_evalueringer.json"

# Ordvinduet vi indekserer på. Fem ord er langt nok til at en tilfeldig
# sammenfall er usannsynlig, og kort nok til at titler på seks-sju ord fortsatt
# får minst ett vindu.
VINDU = 5

# Titler kortere enn dette er for generiske til å bevise noe. «Evaluering av
# tilskuddsordningen» finnes i et titalls varianter, og et treff på den sier
# ingenting om hvilken rapport det gjelder. De telles for seg framfor å blåse
# opp treffraten.
MIN_TEGN = 30

# Titler som er generiske selv når de er lange nok. Håndskrevet, som
# kategorilistene ellers: en regel modellen ikke skal finne på selv.
GENERISKE = (
    "evaluering av tilskuddsordningen",
    "evaluering av ordningen",
    "arsrapport",
    "årsrapport",
    "statusrapport",
    "sluttrapport",
    "delrapport",
    "underveisevaluering",
)


# ---------------------------------------------------------------- innlesing

def les_evalueringer() -> list[dict]:
    fil = KUDOS_DIR / "evalueringer.json"
    if not fil.exists():
        raise SystemExit(
            f"FEIL: {fil} mangler.\n"
            "Hent korpuset først: python pipeline/hent_kudos_evalueringer.py"
        )
    return json.loads(fil.read_text(encoding="utf-8")).get("dokumenter") or []


def les_publikasjoner() -> list[dict]:
    filer = sorted(STORTINGET_DIR.glob("publikasjoner_*.jsonl"))
    if not filer:
        raise SystemExit(
            f"FEIL: fant ingen publikasjoner_*.jsonl i {STORTINGET_DIR}.\n"
            "Hent dem først: python pipeline/hent_stortinget_publikasjoner.py"
        )
    rader = []
    for fil in filer:
        with fil.open(encoding="utf-8") as f:
            for linje in f:
                linje = linje.strip()
                if not linje:
                    continue
                try:
                    rader.append(json.loads(linje))
                except json.JSONDecodeError:
                    continue  # halvskrevet siste linje
    return rader


def sesjonsaar(sesjon: str) -> tuple[int, int]:
    """«2024-2025» → (2024, 2025). Ugyldig form gir (0, 9999), som slipper alt
    gjennom framfor å stille filtrere bort en hel sesjon."""
    funn = re.findall(r"(\d{4})", sesjon or "")
    if len(funn) >= 2:
        return int(funn[0]), int(funn[1])
    return 0, 9999


# ---------------------------------------------------------------- matching

def er_brukbar(tittel: str) -> bool:
    """Er tittelen distinkt nok til at et treff beviser noe?"""
    if len(tittel) < MIN_TEGN:
        return False
    if any(tittel.startswith(g) or tittel == g for g in GENERISKE):
        return False
    return len(ordliste(tittel)) >= VINDU


# Tegnsetting henger fast i ordene når man deler på mellomrom: dokumentet
# skriver «Evaluering av …» og gir tokenet «"evaluering», som aldri matcher
# tittelens «evaluering». Vi plukker derfor ut ordene med et uttrykk i stedet,
# og gjør det likt på begge sider — det er hele poenget med å dele
# normaliseringen: de to sidene må behandles identisk.
ORD = re.compile(r"[0-9a-zæøåäöüéèç]+")


def ordliste(tekst: str) -> list[str]:
    return ORD.findall(tekst)


def vinduer(tokens: list[str], n: int = VINDU):
    for i in range(len(tokens) - n + 1):
        yield " ".join(tokens[i:i + n])


def bygg_indeks(evalueringer: list[dict]) -> tuple[dict, dict, list[dict]]:
    """Indekserer titlene på ordvinduer.

    Naivt søk ville vært 7138 titler × 9000 dokumenter — titalls millioner
    substring-søk i ren Python, altså timer. Indeksen snur det: vi går én gang
    gjennom hvert dokument og slår opp vinduene der.
    """
    indeks: dict[str, list[str]] = collections.defaultdict(list)
    brukbare: dict[str, dict] = {}
    forkastet = []
    for ev in evalueringer:
        uuid = ev.get("uuid")
        tittel = normaliser(str(ev.get("title") or ""))
        if not uuid or not tittel:
            continue
        if not er_brukbar(tittel):
            forkastet.append({"uuid": uuid, "tittel": tittel})
            continue
        tokens = ordliste(tittel)
        brukbare[uuid] = {**ev, "_tittel": tittel, "_nokkel": " ".join(tokens)}
        for vindu in vinduer(tokens):
            indeks[vindu].append(uuid)
    return indeks, brukbare, forkastet


def finn_treff(publikasjoner: list[dict], indeks: dict,
               brukbare: dict) -> dict[str, list[dict]]:
    """uuid → liste over dokumenter som navngir evalueringen.

    Vinduet er bare et forfilter. Et kandidattreff bekreftes ved å sjekke at
    HELE den normaliserte tittelen står i teksten — ellers ville fem
    sammenfallende ord vært nok, og det er det ikke.
    """
    forsteord = {v.split(" ", 1)[0] for v in indeks}
    treff: dict[str, list[dict]] = collections.defaultdict(list)

    for pub in publikasjoner:
        tekst = pub.get("tekst") or ""
        if not tekst:
            continue
        tokens = ordliste(tekst)
        # Sammenligningsflaten er ordene, ikke råteksten: da spiller det ingen
        # rolle om dokumentet setter tittelen i anførselstegn eller parentes.
        flate = " ".join(tokens)
        _, sesjon_slutt = sesjonsaar(pub.get("sesjon", ""))
        kandidater: set[str] = set()
        for i, ord_ in enumerate(tokens):
            # Bare vinduer som starter på et ord vi faktisk indekserte trenger
            # å bygges. Det kutter arbeidet med over nitti prosent.
            if ord_ not in forsteord:
                continue
            vindu = " ".join(tokens[i:i + VINDU])
            kandidater.update(indeks.get(vindu, ()))

        for uuid in kandidater:
            ev = brukbare[uuid]
            if ev["_nokkel"] not in flate:
                continue
            # Et dokument kan ikke ha lest en rapport som ikke fantes ennå.
            aar = str(ev.get("publish_date") or "")[:4]
            if aar.isdigit() and int(aar) > sesjon_slutt:
                continue
            treff[uuid].append({"id": pub.get("id"), "type": pub.get("type"),
                                "sesjon": pub.get("sesjon"),
                                "tittel": pub.get("tittel")})
    return treff


# ---------------------------------------------------------------- rapport

def oppdragsgivere(ev: dict) -> list[str]:
    """`owners` er oppdragsgiveren; `authoring_actors` er den som skrev.
    Feltkartleggingen viste at kilden skiller dem, så det gjør vi også."""
    ut = []
    for a in ev.get("owners") or []:
        if isinstance(a, dict) and a.get("name"):
            ut.append(a["name"])
    return ut or ["(ukjent oppdragsgiver)"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vis-treff", type=int, default=20,
                    help="hvor mange treff som skrives ut for stikkprøve")
    args = ap.parse_args()

    evalueringer = les_evalueringer()
    publikasjoner = les_publikasjoner()
    sesjoner = sorted({p.get("sesjon") for p in publikasjoner if p.get("sesjon")})
    print(f"{len(evalueringer)} evalueringer, {len(publikasjoner)} "
          f"stortingsdokumenter fra {len(sesjoner)} sesjoner")
    print(f"  dekning: {sesjoner[0]} til {sesjoner[-1]}")

    # Nevneren: bare evalueringer publisert innenfor dekningen. En evaluering
    # fra før den eldste sesjonen kan ikke telles som «aldri nevnt» når vi
    # ikke har lest årene den kunne blitt nevnt i.
    fra_aar = sesjonsaar(sesjoner[0])[0]
    til_aar = sesjonsaar(sesjoner[-1])[1]
    i_vinduet = [e for e in evalueringer
                 if str(e.get("publish_date") or "")[:4].isdigit()
                 and fra_aar <= int(str(e["publish_date"])[:4]) <= til_aar]
    uten_dato = [e for e in evalueringer if not str(e.get("publish_date") or "")[:4].isdigit()]
    print(f"  {len(i_vinduet)} evalueringer publisert {fra_aar}–{til_aar} "
          f"(nevneren)")
    print(f"  {len(uten_dato)} uten publiseringsdato — utenfor nevneren")

    indeks, brukbare, forkastet = bygg_indeks(i_vinduet)
    print(f"  {len(brukbare)} titler er distinkte nok til å søkes på, "
          f"{len(forkastet)} for generiske")

    print("\nSøker …", flush=True)
    treff = finn_treff(publikasjoner, indeks, brukbare)

    navngitt = len(treff)
    andel = 100 * navngitt / max(1, len(brukbare))
    print(f"\n{'=' * 72}")
    print(f"NAVNGITT I ET STORTINGSDOKUMENT: {navngitt} av {len(brukbare)} "
          f"({andel:.1f} %)")
    print(f"{'=' * 72}")
    print("Dette er en NEDRE grense. En evaluering kan bli lest og brukt uten")
    print("å bli navngitt; den kan ikke bli navngitt uten å ha blitt lest.")

    # Fordelingen er det interessante, ikke gjennomsnittet: briefen spør hvem
    # som får sin evaluering lest.
    per_giver_alle: collections.Counter = collections.Counter()
    per_giver_treff: collections.Counter = collections.Counter()
    for uuid, ev in brukbare.items():
        for giver in oppdragsgivere(ev):
            per_giver_alle[giver] += 1
            if uuid in treff:
                per_giver_treff[giver] += 1

    print(f"\nAndel navngitt, oppdragsgivere med minst 20 evalueringer:")
    rader = [(g, per_giver_treff[g], n, 100 * per_giver_treff[g] / n)
             for g, n in per_giver_alle.items() if n >= 20]
    for giver, t, n, pst in sorted(rader, key=lambda r: -r[3])[:15]:
        print(f"  {pst:>5.1f} %  {t:>4}/{n:<4}  {giver[:50]}")

    typer = collections.Counter(d["type"] for ds in treff.values() for d in ds)
    print(f"\nHvor de navngis:")
    for typ, n in typer.most_common():
        print(f"  {n:>5}  {typ}")

    if args.vis_treff:
        print(f"\nDe {args.vis_treff} første treffene — les dem, og sjekk at det")
        print("faktisk er rapporten som omtales og ikke en tittelkollisjon:")
        for uuid, dokumenter in list(treff.items())[:args.vis_treff]:
            print(f"  «{brukbare[uuid]['_tittel'][:70]}»")
            print(f"    → {dokumenter[0]['type']} {dokumenter[0]['sesjon']}: "
                  f"{str(dokumenter[0]['tittel'])[:60]}")

    STORTINGET_DIR.mkdir(parents=True, exist_ok=True)
    UTFIL.write_text(json.dumps({
        "dato": date.today().isoformat(),
        "metode": "verbatim navngiving av normalisert rapporttittel",
        "forbehold": ("Nedre grense. Nevneren er evalueringer publisert i de "
                      "sesjonene vi har fulltekst for; titler kortere enn "
                      f"{MIN_TEGN} tegn eller på generiskelisten er utelatt."),
        "dekning": {"sesjoner": sesjoner, "fra_aar": fra_aar, "til_aar": til_aar},
        "nevner": len(brukbare),
        "navngitt": navngitt,
        "utelatt_generisk": len(forkastet),
        "utenfor_dekning": len(evalueringer) - len(i_vinduet),
        "per_oppdragsgiver": {g: {"navngitt": per_giver_treff[g], "totalt": n}
                              for g, n in per_giver_alle.items()},
        "treff": {u: d for u, d in treff.items()},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nSkrev {UTFIL}")
    print("\nNESTE: «behandlet» og «vedtatt» krever koblingen dokument → sak →")
    print("votering. Den bygges av hent_stortinget_vedtak.py, som leser fila")
    print("over. Kjøres den ikke, har trakten to trinn og ikke fire — og det")
    print("skal stå i teksten framfor å antydes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
