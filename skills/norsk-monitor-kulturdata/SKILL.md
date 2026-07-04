---
name: norsk-monitor-kulturdata
description: Analyse av kulturdeltakelsesdata fra Norsk Monitor (Ipsos) og SSBs kulturbruksundersøkelser (Norsk kulturbarometer) — variabelvalg, metodefeller og sammenligning mellom kildene. Bruk denne skillen alltid når Simen analyserer kulturbruk/kulturdeltakelse i befolkningen, spør om Norsk Monitor-variabler eller kodebok, SSB-tabellene 13503/13504, eller bryter kulturvaner ned på utdanning, alder eller tid. Gjelder HVEM som deltar (personer/andeler); for pengestrømmer og budsjettandeler, bruk kulturstatistikk-formidling i stedet.
---

# Norsk Monitor og SSB-kulturdata — deltakelsesanalyse

## Verifiseringsstatus — LES FØRST

**Delvis verifisert.** To kilder med svært ulik status:

1. **SSB Norsk kulturbarometer: VERIFISERT** mot faktisk pipeline-kode i
   `Reven101/Impromptu-Analytics` (hent_ssb_kultur.py / hent_ssb_kulturgap.py, lest
   2026-07-04). Alt i SSB-delen under er lest ut av kjørende kode.
2. **Norsk Monitor: IKKE verifisert.** Kodebok/variabeldefinisjoner ble ikke funnet i
   noen tilgjengelige repoer, og Google Drive var utilgjengelig i økten. Norsk
   Monitor-delen er generell kunnskap om undersøkelsen — **obligatorisk steg 0: be om
   den faktiske kodeboken/datafilen og verifiser variabelnavn, skalaer og filterspørsmål
   før analyse. Oppdater deretter denne skillen.**

## SSB Norsk kulturbarometer [VERIFISERT mot kode]

- **Tabell 13503**: bruk av kulturtilbud etter kjønn og alder, 1991–. **Tabell 13504**:
  samme etter kjønn og utdanningsnivå. Åpen PxWeb-API (data.ssb.no). Befolkning 9–79 år.
- Måltall: **andel som har brukt tilbudet siste 12 måneder** — tabellene inneholder OGSÅ
  gjennomsnittlig antall besøk; å velge feil måltall er den klassiske feilen. Pipelinen
  scorer valueTexts (straffer «besøk/gonger/ganger/gjennomsnitt/tal på») og validerer at
  alle verdier er 0–100.
- Undersøkelsen går ca. hvert fjerde år → **seriene har ekte hull; ikke interpoler**.
- **2021 er pandemiår**: alle kurver stuper (kino mistet nesten halve publikummet);
  målingen etter viser kraftig rekyl. Flagg 2021 eksplisitt i enhver trendtolkning.
- **Digitale tilbud og «i alt»-aggregater utelates** fra tidsserier — digitale serier
  starter først i 2021 og gjør lange linjer misvisende.
- SSB veksler bokmål/nynorsk i kategoritekster («strøym»/«strømm») — match på nøkkelord.
- Rimelighets-kanarifugl fra koden: kino-andelen skal være > 40 % i toppår; teater/kino/
  idrett/bibliotek/museum er «de store fem», opera/ballett/kunstutstilling/tros- og
  livssynsmøte er småserier.

## Utdanningsgradienten [VERIFISERT — dette er kjernefunnet i kulturgap-historien]

- Jo lengre utdanning, desto mer kulturbruk — nesten uansett tilbud og år siden 1991.
- Men gapet varierer: **kino har nesten lukket gapet** (fra ~40 pp i 1991 til omtrent
  halvert), **kunstutstilling/museum består** (lang høyere utdanning 2–3x grunnskole,
  tiår etter tiår), idrettsarrangement jevnest.
- **Komposisjonsfellen** (formulert i kulturgap/tekst.md): langt flere har lang utdanning
  i dag enn i 1991 — gruppene som sammenlignes endrer sammensetning over tid. Gapet innen
  hver måling er reelt, men trenden i gapet kan ikke tolkes uten dette forbeholdet.
- Pris forklarer ikke gapet alene: folkebiblioteket er gratis, gapet der er likevel
  nesten 30 pp. Standardtolkningsramme: kulturell kapital.

## Norsk Monitor [IKKE VERIFISERT — generell kunnskap, sjekk mot faktisk kodebok]

- Ipsos' sosiokulturelle studie, gjennomført annethvert år (oddetallshøst → datasett
  merkes gjerne f.eks. «2023/2024») siden 1985; stort selvutfyllingsskjema, typisk
  3 000–4 000 respondenter 15 år+; inneholder verdisegmenter (moderne/tradisjonell,
  idealistisk/materialistisk) i tillegg til aktivitets-/deltakelsesspørsmål.
- Kulturdeltakelse måles med frekvensskalaer (f.eks. antall ganger siste 12 mnd i
  kategorier), ikke bare ja/nei — **ikke direkte sammenlignbart med SSBs andeler** uten
  omkoding til «minst én gang siste år».
- Kjente metodefeller (generelle, må verifiseres mot kodeboken): endrede spørsmålsformuleringer
  mellom bølger; selvutfylling gir annen sosial ønskverdighet enn SSBs intervjuer;
  vekting (kjønn/alder/geografi) må brukes; verdisegmentene er Ipsos-proprietære
  konstrukter med egen operasjonalisering per bølge.

## Sammenligning på tvers av kildene

Sjekk alltid, punkt for punkt, før tall fra Norsk Monitor og SSB settes ved siden av
hverandre: aldersunivers (9–79 hos SSB), referanseperiode (siste 12 mnd?), måltall
(andel vs. frekvens), innsamlingsmodus, vekting og årstall (SSB-bølger og NM-bølger
treffer ulike år). Avvik mellom kildene er oftest metodeforskjell, ikke virkelighet —
si det eksplisitt i formidlingen.

## Arbeidsflyt

1. Steg 0 for Norsk Monitor-data: innhent kodebok, verifiser variabler, oppdater skillen.
2. Profiler datasettet (se `nytt-datasett-onboarding`; generell analysemetode:
   `data-analyse-metodikk`-skillen).
3. Analyser med fallgruvene over som sjekkliste; 2021-pandemiflagg og komposisjonsforbehold
   er obligatoriske i alt som publiseres.
4. Formidling: bruk impromptu-dataengine-skillen (snapshot + metadata-kontrakt) hvis
   resultatet skal bli en datahistorie.
