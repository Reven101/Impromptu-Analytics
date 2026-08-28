"""Kobler IbsenStage-scener til koordinater via GeoNames.

Kjøring (krever hent_ibsenstage_detaljer.py først):

    python pipeline/berik_geodata.py

Scenestrengen i IbsenStage er halvstrukturert: «Estudios San Miguel, Buenos Aires,
Argentina», eller med gateadresse: «Palmer's Theatre, Broadway At 30Th St, New York,
United States Of America». Siste ledd er land, nest siste er by. Det holder i
praksis for alle scener med minst tre ledd — 10 113 av 10 304.

Vi geokoder mot GeoNames' `cities500` (235 536 steder med minst 500 innbyggere),
lastet ned én gang og lest lokalt. Alternativet — en geokodings-API som Nominatim —
er begrenset til ett kall i sekundet, altså tre timer, og gir et svar vi ikke kan
etterprøve. GeoNames gir oss dessuten folketall og administrativ enhet på kjøpet,
og fila er den samme hver gang, så resultatet er reproduserbart.

To ting krever håndarbeid, og begge er ført opp eksplisitt framfor å gjettes:

- **Landnavn.** 10 av våre 115 navn heter noe annet hos GeoNames. «England»,
  «Scotland», «Wales» og «Northern Ireland» finnes ikke som land der i det hele
  tatt — de er administrative enheter under GB. Vi beholder vår egen inndeling og
  slår opp mot GB.
- **Bynavn på flere språk.** «Vienna» heter «Wien», «Prague» heter «Praha».
  GeoNames' `alternatenames`-kolonne dekker det, og brukes i oppslaget.

FOLKETALLET ER DAGENS, IKKE DATIDENS. GeoNames fører nålevende befolkning, og
kolonnen heter derfor `folketall_idag`. Kristiania i 1850 hadde omtrent 30 000
innbyggere; GeoNames sier 1 082 575, som er Oslo nå. Feltet duger til å skille en
storby fra en bygd, ikke til noe som helst om byens størrelse på oppsetningstiden.

Der flere steder deler navn innenfor samme land, velges det med størst folketall.
Det er en regel, ikke en sannhet: en oppsetning i et lite Springfield havner i det
store. Feilen er systematisk og kjent, og scener uten treff rapporteres framfor å
tvinges inn på en koordinat.
"""

from __future__ import annotations

import collections
import json
import os
import unicodedata
import zipfile
from datetime import date
from pathlib import Path

import kontrakt  # noqa: F401

RAADATA_DIR = Path(
    os.environ.get("IBSENSTAGE_DIR")
    or Path(__file__).resolve().parents[2] / "impromptu_raadata" / "ibsenstage"
)

# Våre landnavn som GeoNames ikke kjenner. Kartlagt for hånd; de fire britiske
# er administrative enheter, ikke land, og slås opp mot GB.
LAND_KODE = {
    "United States of America": "US",
    "England": "GB", "Scotland": "GB", "Wales": "GB", "Northern Ireland": "GB",
    "Netherlands": "NL", "Czech Republic": "CZ", "Slovak Republic": "SK",
    "Macedonia": "MK", "Palestinian Territories": "PS",
}


def normaliser(s: str) -> str:
    ren = unicodedata.normalize("NFKD", s)
    ren = "".join(c for c in ren if not unicodedata.combining(c))
    ren = "".join(c if c.isalnum() or c.isspace() else " " for c in ren)
    return " ".join(ren.lower().split())


def les_landkoder(sti: Path) -> dict[str, str]:
    koder = dict(LAND_KODE)
    for linje in sti.read_text(encoding="utf-8").splitlines():
        if linje.startswith("#") or not linje.strip():
            continue
        d = linje.split("\t")
        if len(d) > 4:
            koder.setdefault(d[4], d[0])
    return koder


def _les_zip(zipsti: Path, steder: dict[tuple[str, str], dict], bare_p: bool) -> None:
    with zipfile.ZipFile(zipsti) as z:
        navnefil = next(n for n in z.namelist() if n.endswith(".txt")
                        and not n.startswith("readme"))
        with z.open(navnefil) as f:
            for rå in f:
                d = rå.decode("utf-8").rstrip("\n").split("\t")
                if len(d) < 15:
                    continue
                # Landfilene har alt: fjell, elver, gårdsbruk. Bare «P» er bebodde
                # steder — uten filteret ville «Nøtterøy» kunne treffe en holme.
                if bare_p and d[6] != "P":
                    continue
                post = {
                    "geonavn": d[1], "lat": float(d[4]), "lon": float(d[5]),
                    "landkode": d[8], "folketall_idag": int(d[14] or 0), "admin1": d[10],
                }
                # Både offisielt navn, ascii-navn og alle alternative navn indekseres,
                # ellers finner vi ikke Wien når kilden sier Vienna.
                navn = {d[1], d[2]} | set(filter(None, d[3].split(",")))
                for n in navn:
                    nk = (normaliser(n), d[8])
                    if not nk[0]:
                        continue
                    forrige = steder.get(nk)
                    if forrige is None or post["folketall_idag"] > forrige["folketall_idag"]:
                        steder[nk] = post


def les_steder(zipsti: Path, landmappe: Path) -> dict[tuple[str, str], dict]:
    """(normalisert stedsnavn, landkode) -> største sted med det navnet.

    `cities500` dekker steder med minst 500 innbyggere. Det er for grovt her:
    Riksteatret turnerer til Gålå og Nøtterøy, og norske spillesteder er små.
    Finnes det landfiler i `geonames_land/`, leses de i tillegg — de inneholder
    alle bebodde steder i landet, uansett størrelse.
    """
    steder: dict[tuple[str, str], dict] = {}
    _les_zip(zipsti, steder, bare_p=False)
    for fil in sorted(landmappe.glob("*.zip")) if landmappe.exists() else []:
        _les_zip(fil, steder, bare_p=True)
        print(f"  + {fil.stem}: {len(steder)} navneoppslag totalt", flush=True)
    return steder


def _varianter(felt: str) -> list[str]:
    """Skrivemåtene ett adresseledd kan gjemme.

    Kilden fører historiske og tospråklige stedsnavn som «Kristiania (Oslo)» og
    «Turku (Åbo)». Begge navnene er ekte, og hvilket av dem GeoNames kjenner
    varierer, så vi prøver hele strengen og hvert navn for seg.
    """
    ut = [felt]
    if "(" in felt and ")" in felt:
        ut.append(felt[:felt.index("(")].strip())
        ut.append(felt[felt.index("(") + 1:felt.rindex(")")].strip())
    return [v for v in ut if v]


def _finn_sted(d: list[str], kode: str | None, steder: dict, koder: dict):
    """Leter etter byen bakfra i adressen.

    Nest siste ledd er byen i de fleste postene, men ikke alle: «People's Theatre,
    Stephenson Rd, Newcastle Upon Tyne, Tyne And Wear, England» har fylket der. Vi
    prøver derfor de tre siste leddene før landet, nærmest landet først.

    Ledd som er identiske med et landnavn hoppes over. Kilden har poster som
    «Germany, Germany, Germany», der byen er ukjent og feltet bare gjentar landet;
    å slå dem opp ville gitt en tilfeldig by som tilfeldigvis het det samme.
    """
    if not kode or len(d) < 3:
        return (d[-2] if len(d) >= 3 else None), None
    for felt in d[-2:-5:-1]:
        for variant in _varianter(felt):
            if variant in koder:
                continue
            sted = steder.get((normaliser(variant), kode))
            if sted:
                return variant, sted
    return d[-2], None


def main() -> None:
    zipsti = RAADATA_DIR / "cities500.zip"
    landsti = RAADATA_DIR / "countryInfo.txt"
    for sti in (zipsti, landsti):
        if not sti.exists():
            raise SystemExit(
                f"mangler {sti}\n"
                "  curl -o cities500.zip https://download.geonames.org/export/dump/cities500.zip\n"
                "  curl -o countryInfo.txt https://download.geonames.org/export/dump/countryInfo.txt"
            )

    koder = les_landkoder(landsti)
    steder = les_steder(zipsti, RAADATA_DIR / "geonames_land")
    print(f"{len(steder)} navneoppslag fra GeoNames, {len(koder)} landnavn")

    browse = {r["hendelse_id"]: r for r in json.loads(
        (RAADATA_DIR / "ibsenstage_hendelser.json").read_text(encoding="utf-8"))["hendelser"]}
    scener: dict[int, dict] = {}
    with (RAADATA_DIR / "ibsenstage_detaljer.jsonl").open(encoding="utf-8") as f:
        for linje in f:
            x = json.loads(linje)
            if not x.get("scene_id") or not x.get("scene"):
                continue
            s = scener.setdefault(x["scene_id"], {
                "scene_id": x["scene_id"], "streng": x["scene"],
                "land": (browse.get(x["hendelse_id"]) or {}).get("land"),
                "oppsetninger": 0,
            })
            s["oppsetninger"] += 1

    ut, uten = [], []
    for s in scener.values():
        d = [x.strip() for x in s["streng"].split(",")]
        kode = koder.get(s["land"] or "") or koder.get(d[-1] if d else "")
        by, sted = _finn_sted(d, kode, steder, koder)
        post = {**s, "by": by, "landkode": kode}
        if sted:
            post.update({"lat": sted["lat"], "lon": sted["lon"],
                         "folketall_idag": sted["folketall_idag"], "geonavn": sted["geonavn"]})
            ut.append(post)
        else:
            uten.append(post)

    fil = RAADATA_DIR / "ibsenstage_geodata.json"
    fil.write_text(json.dumps({
        "hentet": date.today().isoformat(),
        "kilde": "GeoNames cities500",
        "scener": len(scener), "med_koordinat": len(ut),
        "steder": ut + uten,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    n_opp = sum(s["oppsetninger"] for s in scener.values())
    dekket = sum(s["oppsetninger"] for s in ut)
    print(f"\n{len(scener)} scener, {n_opp} oppsetninger")
    print(f"  med koordinat: {len(ut)} scener ({len(ut) / len(scener) * 100:.1f}%), "
          f"{dekket} oppsetninger ({dekket / n_opp * 100:.1f}%)")
    print(f"  uten:          {len(uten)} scener")

    print("\nStørste scener uten treff:")
    for s in sorted(uten, key=lambda s: -s["oppsetninger"])[:10]:
        print(f"  {s['oppsetninger']:4d}  by={str(s['by'])[:22]:24s} {s['streng'][:52]}")

    per_land = collections.Counter(s["land"] for s in uten)
    print("\nLand med flest uløste scener:")
    for land, n in per_land.most_common(6):
        tot = sum(1 for s in scener.values() if s["land"] == land)
        print(f"  {land or '?':26s} {n:4d} av {tot:4d}")
    print(f"\n  {fil}")


if __name__ == "__main__":
    main()
