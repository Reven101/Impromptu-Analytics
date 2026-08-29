"""Felles metadata-kontrakt for alle datahistorier på impromptu.no.

Enhver snapshot-fil (innhold/<slug>/data.json) skal ha denne formen:

    {
      "meta": {
        "tittel": str,                  # historiens tittel
        "kilde": str,                   # f.eks. "Statistisk sentralbyrå"
        "kilde_url": str,               # lenke til kildens side for datasettet
        "dato_hentet": str,             # ISO-dato, f.eks. "2026-07-02"
        "geografi": str,                # f.eks. "Norge" eller "Norge, fylker"
        "enhet": str,                   # f.eks. "antall personer"
        "oppdateringsfrekvens": str,    # f.eks. "årlig"
        "beskrivelse": str,             # 1-2 setninger, vises i galleriet
        "demo": bool,                   # valgfri: true = plassholderdata,
                                        # kjør hentescriptet for ekte tall
        "utkast": bool                  # valgfri: true = holdes utenfor manifestet
                                        # (upublisert/til faktasjekk)
      },
      "visninger": {
        "<viz-id>": {"type": "hero" | "tidslinje" | "kart" | "kortgalleri"
                     | "verdenskart" | "rangering", ...}
      }
    }

Tekstfilen (innhold/<slug>/tekst.md) er vanlig markdown der linjen
``[[viz:<viz-id>]]`` setter inn visualiseringen med den id-en fra data.json.
Første visning i teksten rendres som hero.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Windows-konsollen bruker cp1252 og kaster UnicodeEncodeError på ✓/✗-tegnene
# scriptene skriver ut. No-op på macOS/Linux, som allerede er UTF-8.
for _strom in (sys.stdout, sys.stderr):
    if hasattr(_strom, "reconfigure"):
        _strom.reconfigure(encoding="utf-8", errors="replace")

PAKREVDE_METAFELT = [
    "tittel",
    "kilde",
    "kilde_url",
    "dato_hentet",
    "geografi",
    "enhet",
    "oppdateringsfrekvens",
    "beskrivelse",
]

GYLDIGE_VISNINGSTYPER = {"hero", "tidslinje", "kart", "verdenskart", "kortgalleri",
                         "rangering"}

INNHOLD_DIR = Path(__file__).resolve().parent.parent / "historier" / "innhold"


def valider_snapshot(data: dict, slug: str = "?") -> list[str]:
    """Returnerer en liste med feilmeldinger. Tom liste = gyldig snapshot."""
    feil = []
    meta = data.get("meta")
    if not isinstance(meta, dict):
        return [f"{slug}: mangler 'meta'-objekt"]

    for felt in PAKREVDE_METAFELT:
        verdi = meta.get(felt)
        if not isinstance(verdi, str) or not verdi.strip():
            feil.append(f"{slug}: meta.{felt} mangler eller er tom")

    for flagg in ("demo", "utkast"):
        if flagg in meta and not isinstance(meta[flagg], bool):
            feil.append(f"{slug}: meta.{flagg} må være true/false, fikk {meta[flagg]!r}")

    visninger = data.get("visninger")
    if not isinstance(visninger, dict) or not visninger:
        feil.append(f"{slug}: mangler 'visninger' med minst én visualisering")
    else:
        for viz_id, viz in visninger.items():
            if not isinstance(viz, dict):
                feil.append(f"{slug}: visninger.{viz_id} er ikke et objekt")
            elif viz.get("type") not in GYLDIGE_VISNINGSTYPER:
                feil.append(
                    f"{slug}: visninger.{viz_id}.type må være en av "
                    f"{sorted(GYLDIGE_VISNINGSTYPER)}, fikk {viz.get('type')!r}"
                )
    return feil


def flett_redaksjon(data: dict, slug: str) -> tuple[dict, list[str]]:
    """Legger håndskrevet tekst fra `redaksjon.json` oppå det byggescriptet regnet ut.

    Problemet den løser: `data.json` er generert, men inneholder både tall og tekst
    — tittel, ingressbeskrivelsen som står på forsiden, figurtitler, hero-etiketter.
    Redigerer man den direkte, forsvinner endringen neste gang scriptet kjøres, uten
    et ord. `tekst.md` har aldri hatt det problemet; byggescriptene rører den ikke.

    Med denne er arbeidsdelingen: **byggescriptet eier tallene, `redaksjon.json` eier
    ordene.** Fila er valgfri, og speiler strukturen i data.json:

        {
          "meta": {"tittel": "Min tittel", "beskrivelse": "..."},
          "visninger": {"hero": {"fotnote": "..."}}
        }

    To ting den gjør med vilje:

    - **Ukjente nøkler er en feil, ikke en no-op.** Overstyrer du `visninger.spredning`
      etter at figuren har byttet navn, skal du få vite det. Ellers redigerer du en
      tekst som ikke vises noe sted, og tror den virker.
    - **Divergens rapporteres.** Endrer tallene seg slik at den genererte teksten blir
      en annen enn den håndskrevne, skrives begge ut. Den håndskrevne vinner — men
      «median 114 år» som er blitt 116 skal ikke få stå upåaktet.
    """
    fil = INNHOLD_DIR / slug / "redaksjon.json"
    if not fil.exists():
        return data, []
    overstyring = json.loads(fil.read_text(encoding="utf-8"))
    notater: list[str] = []

    def flett(mål: dict, ny: dict, sti: str) -> None:
        for nøkkel, verdi in ny.items():
            full = f"{sti}.{nøkkel}" if sti else nøkkel
            if nøkkel not in mål:
                raise SystemExit(
                    f"redaksjon.json for {slug}: «{full}» finnes ikke i det "
                    f"byggescriptet lager. Har figuren byttet navn?"
                )
            if isinstance(verdi, dict) and isinstance(mål[nøkkel], dict):
                flett(mål[nøkkel], verdi, full)
            else:
                if mål[nøkkel] != verdi:
                    notater.append(f"{full}\n      generert:    {mål[nøkkel]!r}"
                                   f"\n      håndskrevet: {verdi!r}")
                mål[nøkkel] = verdi

    flett(data, overstyring, "")
    return data, notater


def er_utkast(data: dict) -> bool:
    """True hvis historien bevisst holdes utenfor manifestet.

    Et utkast valideres som alle andre historier — det skal være publiserbart i det
    øyeblikket flagget fjernes — men bygg_manifest.py tar det ikke med på forsiden.
    """
    return bool((data.get("meta") or {}).get("utkast"))


def valider_historie(mappe: Path) -> list[str]:
    """Validerer én historiemappe: data.json + tekst.md + at viz-referansene stemmer."""
    slug = mappe.name
    feil = []

    datafil = mappe / "data.json"
    tekstfil = mappe / "tekst.md"
    if not datafil.exists():
        return [f"{slug}: mangler data.json"]
    if not tekstfil.exists():
        feil.append(f"{slug}: mangler tekst.md")

    try:
        data = json.loads(datafil.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return feil + [f"{slug}: data.json er ikke gyldig JSON ({e})"]

    feil += valider_snapshot(data, slug)

    if tekstfil.exists():
        import re

        tekst = tekstfil.read_text(encoding="utf-8")
        refererte = re.findall(r"\[\[viz:([\w-]+)\]\]", tekst)
        definerte = set(data.get("visninger", {}) or {})
        for ref in refererte:
            if ref not in definerte:
                feil.append(f"{slug}: tekst.md refererer [[viz:{ref}]] som ikke finnes i data.json")
        if not refererte:
            feil.append(f"{slug}: tekst.md har ingen [[viz:...]]-markører (trenger minst hero)")

    return feil


def main() -> int:
    mapper = sorted(p for p in INNHOLD_DIR.iterdir() if p.is_dir())
    alle_feil = []
    for mappe in mapper:
        alle_feil += valider_historie(mappe)

    if alle_feil:
        print("Kontraktsbrudd funnet:")
        for f in alle_feil:
            print(f"  ✗ {f}")
        return 1
    print(f"✓ {len(mapper)} historier følger metadata-kontrakten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
