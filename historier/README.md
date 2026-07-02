# Datahistorie-motoren

Gjenbrukbar motor for datahistorier på impromptu.no: offentlige data → statiske
snapshot-filer → én felles historie-mal i Wes Anderson-estetikk. Ingen backend,
ingen skedulerte jobber — alt er statiske filer som deployes via GitHub → Vercel.

## Arkitektur — tre lag

```
pipeline/                      DATALAG (Python, kjøres manuelt ved behov)
  kontrakt.py                  metadata-kontrakten + validering
  hent_ssb_navn.py             henter SSB-tabell 10467 (navn) → snapshot
  hent_ssb_befolkning.py       henter SSBs befolkningstall → snapshot
  lag_demodata.py              plassholderdata (merket «Demodata» på sidene)
  bygg_manifest.py             skanner innhold/ → manifest.json for forsiden

historier/motor/               FRONTEND-LAG (delt av alle historier)
  tokens.css                   designtokens: farger, typografi, avstand
  komponenter.css / .js        4 komponenter: hero, tidslinje, kart, kortgalleri
  markdown.js                  mini-markdown for tekstfilene
  historie.js                  malen: hero → tekst → grafer → kildekort

historier/                     INNHOLDSLAG
  historie.html                universell historie-side (?id=<slug>)
  (galleriet ligger på forsiden: index.html i repo-roten,
   generert fra manifest.json; /historier/ videresender dit)
  innhold/<slug>/data.json     ÉN datafil (følger kontrakten)
  innhold/<slug>/tekst.md      ÉN tekstfil (markdown + [[viz:…]]-markører)
```

## Metadata-kontrakten

Hver `data.json` har et `meta`-objekt med åtte påkrevde felt:

```json
{ "tittel": "…", "kilde": "…", "kilde_url": "…", "dato_hentet": "ÅÅÅÅ-MM-DD",
  "geografi": "…", "enhet": "…", "oppdateringsfrekvens": "…", "beskrivelse": "…" }
```

…pluss `"demo": true` hvis tallene er plassholdere (gir synlig merke).
`visninger` definerer visualiseringene; `tekst.md` bestemmer rekkefølgen.
`python3 pipeline/kontrakt.py` validerer alt innhold.

## Slik legger du til historie nummer tre

1. **Lag mappen** `historier/innhold/<slug>/` (kort slug, f.eks. `strom`).
2. **Lag `data.json`** — helst via et lite hentescript i `pipeline/`
   (kopier `hent_ssb_befolkning.py` som mal; det er ~100 linjer).
   Kun genuint offentlige kilder: SSB, Kartverket, Frost, Brreg, Doffin, osv.
3. **Skriv `tekst.md`** — vanlig markdown. Sett inn visualiseringer med en
   linje `[[viz:hero]]` osv.; id-ene må finnes i `data.json` sitt
   `visninger`-objekt. Første visning i teksten blir hero.
4. **Kjør** `python3 pipeline/bygg_manifest.py` — validerer kontrakten og
   oppdaterer forsiden automatisk.
5. **Commit og push.** Ferdig — ingen ny frontend-kode.

Ny kode trengs bare hvis du vil ha en helt ny visualiseringstype: legg da til
én funksjon i `komponenter.js` og registrer den i `REGISTER`-objektet nederst.

## Visualiseringstypene

| Type | Bruk | Viktigste felt |
|---|---|---|
| `hero` | stort oppslag øverst | `rader` (statisk) eller `kontroll` + `oppslag` (interaktiv) |
| `tidslinje` | linje- eller søylegraf | `serier[{navn, punkter[[x,y]]}]`, valgfri `stil: "søyle"` |
| `kart` | fylkeskart (rutenett) | `verdier: {fylkesnavn eller -nr: tall}` |
| `kortgalleri` | fakta-kort i rutenett | `kort[{overtittel, verdi, detalj}]` |

Alle får automatisk tooltip, tastaturtilgang og «vis som tabell»-tvilling.
Seriefargene og karturampen er validert for fargeblindhet og kontrast
(se tokens.css) — ikke bytt dem uten å validere på nytt.

## Demodata vs. ekte data

Snapshotene som ligger i repoet nå er **demodata** (`demo: true` — synlig
merke på sidene). Bytt til ekte tall når du har nett mot SSB:

```bash
python3 pipeline/hent_ssb_navn.py
python3 pipeline/hent_ssb_befolkning.py
python3 pipeline/bygg_manifest.py
```

Scriptene skriver over `data.json`-filene og fjerner demo-merket. Snapshots
er bevisst statiske: nettsiden spør aldri SSB direkte, så ingenting kan
knekke i drift. Oppdater ved å kjøre scriptene på nytt og pushe.

## Lokal utvikling

```bash
python3 -m http.server 8000        # fra repo-roten
# åpne http://localhost:8000/historier/
```
