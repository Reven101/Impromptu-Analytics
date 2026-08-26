"""Lar en språkmodell opptre som dataredaktør og forsøke å motsi en historie.

Kjøres FØR publisering, som siste ledd etter kontrakt.py. Der kontrakten sjekker at
snapshotet har riktig form, spør denne om påstandene faktisk bæres av tallene.

Utskriften er RÅD TIL FORFATTEREN, ikke en dom. Den lagres som
historier/innhold/<slug>/REDAKTORSJEKK.md og skal leses av et menneske. Ingenting
publiseres eller stoppes automatisk på grunnlag av den — en modell som gjetter på
innvendinger vil produsere både treffende og tåpelige, og bare et menneske kan skille.

    python pipeline/redaktorsjekk.py kulturgap
    python pipeline/redaktorsjekk.py --alle

Motsatt jobb av kategoriser_formaal.py: ett kall per historie, der kvaliteten på
innvendingene er hele verdien. Her er en dyr modell riktig — se REDAKTORMODELL.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kontrakt import INNHOLD_DIR, er_utkast, valider_historie
from llm_klient import forbruk_oppsummert, kall_modell

# Bevisst en sterk modell. Kategoriseringen er bulk og skal være billig; dette er ett kall
# per historie der en svak modell bare gir generiske innvendinger som koster lesetid.
REDAKTORMODELL = "anthropic/claude-sonnet-5"

SYSTEMPROMPT = (
    "Du er dataredaktør i en redaksjon som publiserer datajournalistikk om norske "
    "offentlige data. Jobben din er å finne svakheter før publisering, ikke å rose. "
    "Du er konkret og nøktern, og du skiller mellom det du kan lese ut av materialet "
    "og det du antar. Du svarer på norsk."
)

OPPGAVE = """Under følger en datahistorie som er klar til publisering: metadata,
visualiseringene med tallene bak, og brødteksten.

Gå gjennom den som redaktør og svar på fire spørsmål. Vær konkret — pek på setninger og
tall, ikke på generelle prinsipper.

1. PÅSTANDER UTEN DEKNING. Hvilke påstander i teksten bæres ikke av tallene som faktisk
   vises? Sitér setningen og forklar hva som mangler.

2. MANGLENDE NORMALISERING. Er noe sammenlignet som ikke er sammenlignbart — absolutte tall
   der andeler trengs, nominelle kroner over tid, geografi uten befolkning, ulike
   tidsperioder? Si hvilken normalisering som mangler og hvorfor den ville endret bildet.

3. ALTERNATIVE FORKLARINGER. Hvilke andre forklaringer enn den teksten gir, kan produsere
   det samme mønsteret? Nevn særlig endringer i måling, rapportering eller definisjoner.

4. HVA VILLE AVKREFTET DETTE. Hvilket konkret, offentlig tilgjengelig datasett ville
   styrket eller knekt hovedpåstanden? Vær presis nok til at det kan hentes.

Er noe av dette allerede håndtert i teksten eller fotnotene, si det kort og gå videre.
Finner du ingen reell svakhet under et punkt, skriv «ingen innvending» framfor å finne på
en. Ikke foreslå omskrivinger av språket — vi er ute etter faktafeil og metodefeil.
"""


def les_historie(mappe: Path) -> str:
    data = json.loads((mappe / "data.json").read_text(encoding="utf-8"))
    tekst = (mappe / "tekst.md").read_text(encoding="utf-8")
    return (
        f"SLUG: {mappe.name}\n\n"
        f"METADATA OG VISNINGER (data.json):\n{json.dumps(data, ensure_ascii=False, indent=1)}\n\n"
        f"BRØDTEKST (tekst.md):\n{tekst}"
    )


def sjekk(mappe: Path, modell: str) -> str:
    feil = valider_historie(mappe)
    if feil:
        raise SystemExit(
            f"{mappe.name} bryter kontrakten — rett det før redaktørsjekk:\n  "
            + "\n  ".join(feil)
        )

    svar = kall_modell(
        [
            {"role": "system", "content": SYSTEMPROMPT},
            {"role": "user", "content": OPPGAVE + "\n\n---\n\n" + les_historie(mappe)},
        ],
        modell=modell,
        # Romslig: redaktørmodellen er resonnerende, og tenketokens trekkes fra samme
        # budsjett som prosaen. Ett kall per historie, så taket koster ingenting her.
        maks_tokens=16000,
    )

    fil = mappe / "REDAKTORSJEKK.md"
    fil.write_text(
        f"# Redaktørsjekk: {mappe.name}\n\n"
        f"Maskinelt generert av {modell}, {date.today().isoformat()}.\n\n"
        "**Dette er råd, ikke fasit.** Punktene under er en modells forsøk på å motsi\n"
        "historien. Noen treffer, noen bommer. De skal vurderes av et menneske, og\n"
        "ingenting stoppes eller publiseres automatisk på grunnlag av dem.\n\n"
        "---\n\n" + svar.strip() + "\n",
        encoding="utf-8",
    )
    return svar


def main() -> int:
    ap = argparse.ArgumentParser(description="Redaktørsjekk av en datahistorie.")
    ap.add_argument("slug", nargs="*", help="historier å sjekke")
    ap.add_argument("--alle", action="store_true", help="alle historier i innhold/")
    ap.add_argument("--utkast", action="store_true", help="ta med utkast (utelates ellers)")
    ap.add_argument("--modell", default=REDAKTORMODELL)
    args = ap.parse_args()

    if args.alle:
        mapper = sorted(p for p in INNHOLD_DIR.iterdir() if p.is_dir())
    elif args.slug:
        mapper = [INNHOLD_DIR / s for s in args.slug]
    else:
        ap.error("oppgi minst én slug, eller --alle")

    for mappe in mapper:
        if not mappe.is_dir():
            raise SystemExit(f"Fant ikke historien {mappe.name} i {INNHOLD_DIR}")
        data = json.loads((mappe / "data.json").read_text(encoding="utf-8"))
        if er_utkast(data) and not args.utkast and args.alle:
            print(f"— {mappe.name} hoppet over (utkast; bruk --utkast)")
            continue

        print(f"\n{'=' * 70}\n{mappe.name}\n{'=' * 70}")
        print(sjekk(mappe, args.modell))
        print(f"\n→ skrevet til {mappe / 'REDAKTORSJEKK.md'}")

    print(f"\nForbruk: {forbruk_oppsummert()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
