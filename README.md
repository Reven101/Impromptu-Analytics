# impromptu.no — datahistorier fra offentlige data

impromptu.no gjør offentlig tilgjengelige data spennende og forståelige.
Forsiden er et galleri av visuelle datahistorier bygget på åpne kilder som
Statistisk sentralbyrå. Kilden står alltid oppgitt, og tallene kan ettergås.

Nettstedet er helstatisk: ingen backend, ingen database, ingen skedulerte
jobber. Data hentes manuelt med Python-scripts og sjekkes inn som statiske
JSON-snapshots.

## Arkitektur — tre lag

```
pipeline/                      1. DATALAG (Python, kjøres manuelt)
  kontrakt.py                  felles metadata-kontrakt + validering
  hent_ssb_navn.py             SSB-tabell 10467 (navn) → snapshot
  hent_ssb_befolkning.py       SSB-tabell 06913 (befolkning) → snapshot
  lag_demodata.py              merkede plassholderdata (for utvikling)
  bygg_manifest.py             skanner innhold/ → manifest.json

historier/motor/               2. FRONTEND-LAG (delt av alle historier)
  tokens.css                   designtokens (farger, typografi, avstand)
  komponenter.css / .js        hero, tidslinje, kart, kortgalleri
  markdown.js, historie.js     tekstrendring og historie-mal

historier/innhold/             3. INNHOLDSLAG (én mappe per historie)
  <slug>/data.json             datafil som følger metadata-kontrakten
  <slug>/tekst.md              narrativ tekst med [[viz:…]]-markører
  manifest.json                generert — forsiden bygger galleriet av denne
```

Hver `data.json` har et `meta`-objekt med åtte påkrevde felt (tittel, kilde,
kilde_url, dato_hentet, geografi, enhet, oppdateringsfrekvens, beskrivelse).
Kontrakten er definert og håndhevet i `pipeline/kontrakt.py`.

## Kjøre pipelinen lokalt

Krever bare Python 3.11+ (standardbiblioteket) og nett mot data.ssb.no:

```bash
python3 pipeline/hent_ssb_navn.py          # henter navnestatistikk → snapshot
python3 pipeline/hent_ssb_befolkning.py    # henter befolkningstall → snapshot
python3 pipeline/bygg_manifest.py          # validerer alt + oppdaterer forsiden
```

Hentescriptene skriver ut valgt måltall og kontrollår for manuell rimelighets-
sjekk, og nekter å skrive snapshots med urealistiske tall. `bygg_manifest.py`
stopper hvis en historie bryter metadata-kontrakten.

Lokal forhåndsvisning:

```bash
python3 -m http.server 8000    # fra repo-roten, åpne http://localhost:8000/
```

## Legge til en ny historie

En ny historie er én datafil + én tekstfil — ingen ny frontend-kode.
Oppskriften (fem steg) står i [historier/README.md](historier/README.md),
sammen med dokumentasjon av visualiseringstypene og designtokens.

## API-atlas — kartlagte norske datakilder

[api-atlas/](api-atlas/README.md) er et kjørbart oppslagsverk over 15
offentlige norske API-er (SSB, Brreg, tilskudd.no, Kartverket, MET,
Entur, Nasjonalbiblioteket, Stortinget m.fl.): ett frittstående
eksempelscript per kilde, med lisensnotat og prosjektidéer. Sjekk at
kildene fortsatt svarer med:

```bash
python3 api-atlas/test_atlas.py
```

Nye datahistorier starter her: finn kilden i atlaset, kopier scriptet,
bygg pipeline etter mønsteret i `pipeline/`.

## Deploy

Repoet deployes som statiske filer via GitHub → Vercel: push til main,
så bygger og publiserer Vercel automatisk mot impromptu.no. Ingen
byggesteg — filene serveres som de er.

## Øvrige sider

- `tjenester.html` — nøktern presentasjon av konsulentvirksomheten
  (Impromptu Analytics), lenket diskret fra footeren
- `personvern.html` / `vilkar.html`
- `api/analyze.js` — legacy fra et tidligere analyseprodukt; ikke i bruk
  på nettstedet
