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
