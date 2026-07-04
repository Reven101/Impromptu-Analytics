---
name: impromptu-dataengine
description: Arbeid med tre-lags datafortellingsmotoren på impromptu.no (repo Reven101/Impromptu-Analytics) — lage nye datahistorier, nye hentescripts mot SSB PxWeb, nye visualiseringstyper, eller feilsøke kontraktsbrudd. Brukes når oppgaven gjelder impromptu.no, historier/-mappen, pipeline/-scriptene, data.json/tekst.md-filer, manifest.json eller motor-komponentene (hero, tidslinje, kart, kortgalleri).
---

# Impromptu datamotor — tre-lags datafortellingsmotor

## Verifiseringsstatus

**Verifisert mot kildekode 2026-07-04** (repo `Reven101/Impromptu-Analytics`, main): all
arkitektur, kontrakten, visualiseringstypene og arbeidsflyten under er lest direkte ut av
`pipeline/kontrakt.py`, `pipeline/bygg_manifest.py`, `pipeline/hent_ssb_kultur.py`,
`pipeline/hent_ssb_kulturgap.py`, `historier/motor/*` og begge README-filene.

**Viktig korreksjon:** Det finnes **ingen branch `claude/impromptu-data-engine`** i repoet.
Motoren ligger på `main` (merget via PR #8, kulturbarometer-story). Ikke let etter den branchen.

## Arkitektur (slik den faktisk er bygget)

Helstatisk: ingen backend, ingen database, ingen skedulerte jobber. Python-scripts kjøres
**manuelt** og sjekker inn statiske JSON-snapshots. Deploy: push til main → Vercel → impromptu.no.

```
pipeline/                      1. DATALAG (Python 3.11+, kun standardbibliotek)
  kontrakt.py                  metadata-kontrakt + validering (importeres av alle hentescripts)
  hent_ssb_*.py                ett script per SSB-tabell → skriver innhold/<slug>/data.json
  lag_demodata.py              plassholderdata, merket "demo": true
  bygg_manifest.py             validerer ALT innhold + bygger manifest.json for forsiden

historier/motor/               2. FRONTEND-LAG (delt, vanilla JS/CSS, ES-moduler)
  tokens.css                   designtokens; serie-/kartfarger er kontrast-/fargeblindvalidert
  komponenter.js/.css          4 komponenter i REGISTER: hero, tidslinje, kart, kortgalleri
  markdown.js                  mini-markdown (escaper all tekst — trygt for innerHTML)
  historie.js                  én universell mal: hero → prosa → grafer → kildekort

historier/innhold/<slug>/      3. INNHOLDSLAG (én mappe per historie)
  data.json                    følger kontrakten; tekst.md refererer visninger med [[viz:id]]
  tekst.md                     markdown; FØRSTE [[viz:...]] i teksten rendres som hero
```

## Metadata-kontrakten (håndheves av kontrakt.py)

`data.json` = `{"meta": {...}, "visninger": {"<viz-id>": {"type": ...}}}`.
Åtte påkrevde meta-felt (alle ikke-tomme strenger): `tittel`, `kilde`, `kilde_url`,
`dato_hentet` (ISO), `geografi`, `enhet`, `oppdateringsfrekvens`, `beskrivelse`.
Valgfritt: `"demo": true` → synlig "Demodata"-merke på siden.
Gyldige visningstyper: `hero`, `tidslinje`, `kart`, `kortgalleri` — feltspesifikasjon
per type står i [referanse.md](referanse.md).

## Ny historie — arbeidsflyt (verifisert oppskrift)

1. Lag `historier/innhold/<kort-slug>/`.
2. Skriv hentescript i `pipeline/` med `hent_ssb_befolkning.py`/`hent_ssb_kultur.py` som mal.
   Kun genuint offentlige kilder (SSB, Kartverket, Frost, Brreg, Doffin …).
   Scriptet skal: importere `valider_snapshot` fra `kontrakt.py`, printe kontrolltall for
   manuell rimelighetssjekk, og **nekte å skrive** urimelige snapshots (`raise SystemExit`).
3. Skriv `tekst.md` — prosa med `[[viz:<id>]]`-linjer; id-ene må finnes i `visninger`.
4. `python3 pipeline/bygg_manifest.py` — validerer alt og oppdaterer forsiden. Manifestet
   bygges IKKE hvis én historie bryter kontrakten.
5. Commit + push. Ingen ny frontend-kode.

Ny visualiseringstype = én funksjon i `komponenter.js` + registrering i `REGISTER` nederst.

## Fallgruver (alle observert i faktisk kode)

- **Første viz i tekst.md blir hero** — rekkefølgen i `tekst.md` styrer, ikke rekkefølgen i
  `data.json`. En tekst uten `[[viz:...]]`-markører er kontraktsbrudd.
- **Seriefarger/karturampe i tokens.css/komponenter.js er validert for fargeblindhet og
  kontrast** — ikke bytt uten å validere på nytt (eksplisitt advarsel i historier/README.md).
- **SSB-serier har ekte hull**: kulturbruksundersøkelsen går ca. hvert fjerde år; hull mellom
  målinger er riktig, ikke en feil som skal interpoleres bort.
- **Velg riktig måltall i PxWeb**: tabellene inneholder både andel (%) og gj.sn. antall besøk.
  `velg_andel_maal()` scorer valueTexts og feiler hardt hvis andels-målet ikke finnes.
  Verdisjekk 0–100 på hvert punkt; kino-serien brukes som kanarifugl (maks < 40 % = feil mål).
- **Digitale tilbud og «i alt»-aggregater utelates** fra tidsserier — de digitale seriene
  starter først i 2021 og gjør lange tidslinjer misvisende.
- **SSB veksler bokmål/nynorsk i kategoritekster** — matching gjøres på nøkkelord
  (f.eks. «strøym»/«strømm»), aldri på eksakt streng.
- **Bakgrunnsvariabler i PxWeb**: utelat variabler med `elimination: true` (API-et aggregerer
  selv); ellers velg totalkategorien («alle», «begge», «i alt», «total»).
- **Snapshots er bevisst statiske** — nettsiden spør aldri SSB i drift. Ikke «forbedre» ved å
  hente live.
- **Fylkeskartet bruker 2024-fylkesinndelingen** (15 fylker, nye nummer, f.eks. Østfold=31);
  verdier kan nøkles på fylkesnavn eller -nummer.
- Lokal test: `python3 -m http.server 8000` fra repo-roten (ES-moduler krever http, ikke file://).
- `api/analyze.js` er legacy fra et tidligere produkt — ikke i bruk, ikke bygg videre på den.

## Detaljert referanse

Full feltspesifikasjon for de fire visningstypene, PxWeb-mønsteret (json-stat2 flat
indeksering) og eksempel-data.json: se [referanse.md](referanse.md).
