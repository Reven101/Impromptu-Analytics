---
name: arkitektur-husregler
description: Simens husarkitektur og teknologivalg på tvers av prosjektene — valgregelen mellom statisk dataprodukt, Next.js-app og backend-tjeneste, pluss de tverrgående husreglene (valideringsport, feil hardt, snapshots, norsk i kode). Bruk denne skillen alltid når Simen starter et nytt prosjekt eller repo, spør «hvordan bør jeg bygge dette», velger stack/rammeverk/hosting, eller når et arkitekturvalg skal tas i et eksisterende prosjekt. Denne eier valgene PÅ TVERS av prosjekter; detaljer per repo hører hjemme i repoets CLAUDE.md, utseende i impromptu-designsystem, datakilder i kultursektor-datakilder.
---

# Arkitektur-husregler

## Verifiseringsstatus

**Verifisert 2026-07-04 mot alle seks repoer** (Impromptu-Analytics, tilskuddskompasset,
slektstre, Ledige-baner, Banemangel, Kanonhallen): lanes, stacks og husregler under er
observert praksis, ikke ønsketenkning. Unntak er merket. Kanonhallen er tomt (kun .git).

## Valgregelen — tre lanes

Velg lane etter behovet, ikke etter vane. Default er **Lane A** — den letteste som løser
oppgaven.

### Lane A: Statisk dataprodukt (default for datafortellinger og oppslagsverk)
*Verifisert: impromptu.no, tilskuddskompasset*
- **Ingen backend, ingen database, ingen skedulerte jobber.** Python-pipeline kjøres
  manuelt → daterte, statiske JSON/JS-snapshots sjekkes inn i repoet.
- Vanilla HTML/JS/CSS uten byggsteg. To varianter i bruk: ES-moduler med delt motor
  (impromptu — krever `python3 -m http.server` lokalt) eller én selvbærende index.html
  (tilskuddskompasset — kan åpnes direkte).
- Deploy: push til main → Vercel serverer filene som de er.
- Nettsiden spør ALDRI kilden live — alt som kan knekke i drift, er allerede fjernet.
- Velg denne når innholdet endres sjeldnere enn ukentlig og brukerne bare leser/filtrerer.

### Lane B: Next.js-app (når brukerne skal interagere med tilstand)
*Verifisert: slektstre (Next 15, React 19, TS strict, ren CSS), Ledige-baner (Next 16,
React 19, TS, Tailwind 4)*
- App Router (`app/`), TypeScript, komponenter i egen mappe, data som lokal
  JSON/TS-modul så lenge det holder.
- **Valideringsport i bygget**: slektstre-mønsteret er husregelen —
  `"build": "npm run validate && next build"`, der validate-scriptet sjekker
  dataintegritet og feiler bygget ved brudd. Nye Lane B-prosjekter skal ha dette fra dag 1.
- Velg denne ved klientinteraktivitet (utforsking, sanntid, navigasjon i datastruktur).

### Lane C: Backend-tjeneste (kun når data må hentes/lagres kontinuerlig)
*Verifisert: Banemangel (tidlig fase — FastAPI-skjelett)*
- FastAPI + PostgreSQL + Redis, alt i docker-compose; SQLAlchemy/Alembic for skjema;
  Playwright/bs4 for innhenting som krever ekte nettleser.
- Terskelen for Lane C er HØY: begge de modne produktene klarte seg uten. Kravet som
  utløser den: data som må hentes oftere enn et menneske gidder å kjøre et script.
- Hemmeligheter: `.env` + `.env.example` sjekket inn; compose-filens innloggingsverdier
  er dev-plassholdere og skal aldri gjenbrukes mot noe ekte.

## Tverrgående husregler (gjelder alle lanes)

1. **Valideringsport før publisering**: ingenting publiseres uten maskinell sjekk —
   kontrakt.py (Lane A), validate-script i build (Lane B). Porten skal FEILE bygget,
   ikke advare.
2. **Feil hardt og forklarende**: scripts som møter uventet struktur stopper med
   beskjed om hvor man skal sjekke — de skriver aldri tvilsom output stille.
3. **Kontrolltall/kanarifugl**: hentescripts printer et kjent tall for manuell
   rimelighetssjekk før commit.
4. **Daterte snapshots**: datafiler bærer sin egen hentedato (GENERERT/dato_hentet);
   rådata caches og røres aldri.
5. **Norsk i alt**: kode, kommentarer, commit-meldinger, README-er og variabelnavn er
   på norsk i alle repoene. Nye prosjekter fortsetter det.
6. **README med arkitektur-seksjon fra start** — alle aktive repoer har det; pluss
   CLAUDE.md i repoet for Claude-spesifikke arbeidsregler (denne skillen eier bare
   tverrgående valg).
7. **Tilgjengelighet er ikke valgfritt**: synlig fokusring, prefers-reduced-motion,
   tabell-tvillinger for grafer (se impromptu-designsystem for detaljene).
8. **Åpenhet som produktverdi**: kilde oppgis alltid, forbehold står i produktet,
   interessekonflikter deklareres (jf. om-sidene).
9. **Minst mulig avhengigheter**: standardbiblioteket foretrekkes i Python-scripts
   (flere av skraperne bruker KUN std-lib); ingen rammeverk der én HTML-fil holder.

## Sjekkliste for nytt prosjekt

☐ Hvilken lane? (tvil = Lane A; oppgrader når behovet er bevist, ikke før)
☐ README med arkitektur-seksjon + CLAUDE.md skrevet
☐ Valideringsport koblet inn i bygg/publisering
☐ Datafiler datert; rådata cachet utenfor git om de er store/uerstattelige
☐ Design: impromptu-designsystem hvis produktet bærer merkevaren
☐ Ny datakilde? → kultursektor-datakilder + nytt-datasett-onboarding
☐ Deploy: Vercel via push til main; domene under impromptu.no for merkevareprodukter

## Kjente avvik (per 2026-07-04)

- **Ledige-baner er i brukket byggtilstand**: `app/globals` og `app/lib/data` er
  committet uten filendelse, og lib/data-filen inneholder feil innhold (en kopi av
  QuickStats-komponenten i stedet for datalaget). Se repoets CLAUDE.md før arbeid der.
- **Banemangel** er et skjelett (main.py = 14 linjer, frontend = én prototype-tsx
  utenfor byggsystem) — behandle som utkast, ikke som etablert Lane C-fasit.
- **Kanonhallen** er tomt — lane ikke valgt ennå; bruk sjekklisten når det starter.
