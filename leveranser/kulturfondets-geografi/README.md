# Kulturfondets geografi 2024–2026

Leveranser bygget fra datahistorien «Hvem søker, og hvem får» — geografisk analyse av
Norsk kulturfonds tildelinger.

| Fil | Innhold |
|---|---|
| `Kulturfondets-geografi-2024-2026.pdf` | Hele rapporten, 12 sider. Alle sju figurer og begge tabellene. Fylkestabellen med 18 kolonner ligger på egen liggende side. |
| `Kulturfondets-geografi-2024-2026.pptx` | Presentasjon, 16 slides, med talerpunkter i notatfeltet. |

## Datagrunnlag

Alle tall kommer fra `kilde/data.json`, som er rapportens egen datablokk — de samme
tallene som figurene i rapporten tegnes fra. Ingenting er tastet inn på nytt.

- Kilde: Kulturdirektoratets vedtakseksport pr. 13.08.2026
- Befolkningstall: SSB tabell 06913, 1.1.2026
- Periode: søknadsfrister 30.11.2023–18.06.2026
- Omfang: 19 566 søknader fra 8 372 søkere i 15 fylker, 1,86 mrd. kroner tildelt

Merk: geografien er **søkerens registrerte adresse**, ikke der aktiviteten foregår.
2026 er ufullstendig (sju søknadsrunder mot ti–elleve de foregående årene), så nivåtall
per år er ikke sammenlignbare. Analysen dekker Norsk kulturfond alene.

## Utvidelse: hvor kulturorganisasjonene faktisk holder til

`kilde/hent_brreg_kulturenheter.py` henter alle enheter med næringskode 90 (kunstnerisk
virksomhet og underholdning) og 91 (biblioteker, arkiver, museer) fra Enhetsregisteret,
fordeler dem på fylke etter kommunenummer og kobler dem mot folketallet og søkerbasen i
`kilde/data.json`. Det gir nevneren analysen mangler: er få søkere fra et fylke et tegn
på at kulturlivet der er lite, eller på at et stort kulturliv ikke søker?

**Ikke kjørt ennå.** Scriptet er skrevet uten nettilgang til data.brreg.no, og
API-kontrakten er derfor ikke verifisert. All øvrig logikk — paginering, avduplisering,
fylkesmapping, kobling og snapshot — er tørrkjørt mot simulerte svar. Første ekte kjøring
må kontrolleres mot kanaritallene scriptet printer.

## Bygge på nytt

```bash
cd kilde
python3 lag_pdf.py                 # rapport-print.html → PDF (krever playwright + chromium)
npm install pptxgenjs && node lag_deck.js   # data.json → PPTX
```

`rapport-print.html` er rapporten med egen utskrifts-CSS: sidestørrelse, sideskift som
ikke bryter figurer, og en liggende side til den brede fylkestabellen.

Presentasjonen følger Impromptu-paletten fra `historier/motor/tokens.css`. Fontene er
byttet til Cambria/Calibri/Consolas, som følger med Office — Jost og IBM Plex Mono ville
blitt substituert på en vilkårlig maskin.
