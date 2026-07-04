# Referanse: visningstyper, PxWeb-mønster og eksempel

Alt under er lest ut av `historier/motor/komponenter.js`, `historier/motor/historie.js`
og pipeline-scriptene (verifisert 2026-07-04).

## Visningstypene — feltspesifikasjon

Alle visninger får automatisk tooltip, tastaturtilgang og «Vis tallene som tabell»-tvilling
(WCAG). `lagVisning(spec, meta) -> HTMLElement`; ukjent type gir synlig feilboks.

### hero
Stort oppslag. To moduser:
- **Statisk**: `{"type":"hero", "eyebrow": str?, "sporsmal": str?, "rader": [{"etikett","verdi","detalj"?}], "fotnote": str?}`
- **Interaktiv**: `kontroll: {"etikett", "standard"?}` + `oppslag: {"<nøkkel>": {"rader": [...]}}`
  — rendrer en `<select>`; nøkler sorteres synkende (numerisk-bevisst, nb-locale).

### tidslinje
SVG-graf 760×380. `{"type":"tidslinje", "tittel", "undertekst"?, "enhet"?, "stil"?: "linje"|"søyle", "x_navn"?, "serier": [{"navn", "punkter": [[x,y],...]}]}`
- `stil:"linje"` (default): flerserie; direktelabels på linjeender ved ≤ 4 serier (med
  kollisjonsdytt), legend ved ≥ 2 serier, crosshair-tooltip som samler alle serier på nærmeste x.
- `stil:"søyle"`: kun ÉN serie; avrundet data-ende, verdi-label på maks-søylen.
- Y-aksen starter på 0; ticks via `fineTicks` (1/2/2.5/5/10-steg). Store tall
  kompakteres («mill.», «k»).

### kart
Stilisert rutenettkart, norske fylker **2024-inndeling** (15 fylker).
`{"type":"kart", "tittel", "undertekst"?, "enhet"?, "verdier": {"<fylkesnavn eller nr>": tall}}`
Fylkesnummer som brukes: Oslo 03, Rogaland 11, Møre og Romsdal 15, Nordland 18, Østfold 31,
Akershus 32, Buskerud 33, Innlandet 34, Vestfold 39, Telemark 40, Agder 42, Vestland 46,
Trøndelag 50, Troms 55, Finnmark 56. Sekvensiell 6-trinns grønn rampe (validert);
tekstfarge i flis velges automatisk etter luminans. Fylker uten data får tom flis.

### kortgalleri
`{"type":"kortgalleri", "tittel", "undertekst"?, "kort": [{"overtittel"?, "verdi", "detalj"?}]}`

## tekst.md

Vanlig markdown (mini-parser: overskrifter, avsnitt, *kursiv* — all tekst escapes).
Linjen `[[viz:<id>]]` (egen linje) setter inn visningen. Første viz = hero (får klassen
`er-hero`). Manglende id gir synlig feilboks i historien, ikke krasj.

## PxWeb-mønsteret (hent_ssb_*.py)

1. `GET https://data.ssb.no/api/v0/no/table/<TABELL_ID>` → metadata med `variables`.
2. Finn variabelkoder ved **tekstsøk i variabelnavn** (ikke hardkodede koder — de endres).
3. Velg måltall med scoring av `valueTexts` (straff «besøk/gonger/ganger/gjennomsnitt/tal på»,
   belønn «andel/prosent/del av»); `SystemExit` hvis ikke funnet.
4. Bakgrunnsvariabler: hopp over ved `elimination: true`, ellers velg totalkategori.
5. `POST` samme URL med `{"query": [...], "response": {"format": "json-stat2"}}`.
6. json-stat2 er flat-indeksert: verdi på koordinat beregnes med
   `flat = flat * size[dim] + indeks` i dimensjonsrekkefølgen fra `stat["id"]`.
7. Valider hver verdi (f.eks. 0–100 for prosent), kjør kanarifugl-sjekk på kjent serie,
   `valider_snapshot()` fra kontrakt.py, skriv med `ensure_ascii=False, indent=1`.
8. Print kontrolltall og avslutt med påminnelsen «Husk: python3 pipeline/bygg_manifest.py».

Robusthetsprinsipp fra koden: **feil hardt og forklarende** («Tabell X ser annerledes ut enn
ventet — sjekk den på data.ssb.no») i stedet for å skrive tvilsomme snapshots.

## Minimal gyldig data.json

```json
{
 "meta": {
  "tittel": "Eksempel", "kilde": "Statistisk sentralbyrå",
  "kilde_url": "https://www.ssb.no/...", "dato_hentet": "2026-07-04",
  "geografi": "Norge", "enhet": "prosent",
  "oppdateringsfrekvens": "årlig", "beskrivelse": "En til to setninger til galleriet."
 },
 "visninger": {
  "hero": {"type": "hero", "rader": [{"etikett": "Nøkkeltall", "verdi": "42 %"}]},
  "utvikling": {"type": "tidslinje", "tittel": "Utviklingen",
                "serier": [{"navn": "Norge", "punkter": [[2020, 40], [2024, 42]]}]}
 }
}
```

Tilhørende tekst.md må inneholde minst `[[viz:hero]]` (og gjerne `[[viz:utvikling]]`).

## Eksisterende historier (per 2026-07-04)

`kultur` (SSB 13503, kulturbarometer), `kulturgap` (SSB 13504, kulturbruk etter utdanning),
`navn` (SSB 10467), `befolkning` (SSB 06913). De to kultur-historiene er de beste malene
for nye SSB-historier.
