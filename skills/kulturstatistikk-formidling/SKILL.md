---
name: kulturstatistikk-formidling
description: Analyse og formidling av statlig kulturfinansiering — statsregnskapet, kulturbudsjettandeler, bevilgning vs. regnskap og artskonto-feller — kombinert med Impromptu-metodikken for å gjøre tallene til etterprøvbare datahistorier. Brukes ved spørsmål om kulturbudsjettet, statsregnskapet.no-data, KUDs budsjettkapitler, «hvor stor andel av statsbudsjettet går til kultur», eller når kulturøkonomi-tall skal formidles offentlig.
---

# Kulturstatistikk: statsregnskap-analyse og formidling

## Verifiseringsstatus — LES FØRST

**Delvis verifisert.** Tidligere statsregnskaps-analyser ble **ikke funnet** i tilgjengelige
repoer (GitHub-søk på statsregnskap/kontoklasse/artskonto ga null treff 2026-07-04;
Google Drive utilgjengelig). Status per del:

- **Formidlingsmetodikken: VERIFISERT** mot faktisk kode og publiserte historier i
  `Reven101/Impromptu-Analytics` (kultur- og kulturgap-historiene).
- **Statsregnskaps-fallgruvene (kontoklasser, bevilgning vs. regnskap, dobbelttelling)**:
  oppgitt av brukeren som egne lærdommer i bestillingen av denne skillen — de er
  brukerens erfaring, men **ikke etterprøvd mot brukerens faktiske analyser** i denne
  økten. Detaljene om statsregnskapet.no er generell kunnskap.
- **Obligatorisk steg 0**: be brukeren om de tidligere analysene (notebook/regneark) og
  verifiser fallgruvene mot dem; oppdater skillen med konkrete kontonumre/kapitler.

## Datagrunnlag [generell kunnskap — verifiser mot statsregnskapet.no før bruk]

- statsregnskapet.no (DFØ) publiserer åpne regnskapsdata for statsforvaltningen, med
  API/CSV-nedlasting. Sentrale dimensjoner: departement, virksomhet, kapittel/post
  (bevilgningsregnskapet) og artskonto (kontoplanen).
- Kulturfeltet: Kultur- og likestillingsdepartementets kapitler (300-serien), pluss
  kulturformål under andre departementer (f.eks. kirkeformål, medier, idrettens
  spillemidler som IKKE går over statsbudsjettet).

## Fallgruver i statsregnskapsdata [oppgitt av bruker — verifiser i steg 0]

- **Kontoklasser må ikke blandes**: bevilgningsregnskapet (kapittel/post) og
  artskontorapporteringen (kontoklasse 1–9) er to ulike snitt av samme penger. Å summere
  på tvers gir meningsløse tall.
- **Bevilgning ≠ regnskap**: saldert budsjett, revidert budsjett og faktisk regnskapsført
  beløp er tre ulike tall for samme post og år. Si alltid hvilket du bruker; bruk regnskap
  for «hva ble faktisk brukt», bevilgning for «hva ble prioritert».
- **Dobbelttelling i artskontodata**: overføringer mellom statlige virksomheter og
  tilskudd som går i flere ledd (departement → direktorat → mottaker) vises som utgift i
  flere virksomheters artskontodata. Summering per artskonto over alle virksomheter
  teller da samme krone flere ganger. Konsolider per endelig mottakerledd, eller hold deg
  til bevilgningsregnskapet for totaler.
- [Generelt:] **«Kulturbudsjettandelen» avhenger helt av teller- og nevnerdefinisjon**:
  med/uten idrett og frivillighet, med/uten medier, brutto- vs. nettobudsjett, med/uten
  SDØE/petroleum og lånetransaksjoner i nevneren. Den mye brukte «1 % av statsbudsjettet
  til kultur»-debatten er definisjonsfølsom — deklarer definisjonen eksplisitt.
- [Generelt:] Nominelle kroner over tid uten KPI-justering (eller andel av totalbudsjett)
  er villedende; kapittel-/postnumre endres mellom år (omorganiseringer) — bygg
  overgangsnøkkel før tidsserier lages.

## Formidlingsmetodikken [VERIFISERT mot Impromptu-Analytics]

Slik gjøres tallene til publiserbare historier på impromptu.no (jf. kultur/kulturgap):

1. **Snapshot-prinsippet**: analysen fryses som statisk data.json med full
   metadata-kontrakt (kilde, kilde_url, dato_hentet, enhet, oppdateringsfrekvens) —
   tallene skal kunne ettergås av leseren. Ingen live-oppslag i drift.
2. **Rimelighetssjekk før publisering**: hentescriptet printer kontrolltall og NEKTER å
   skrive urimelige verdier (SystemExit). Definer en kanarifugl (kjent tall, f.eks.
   totalbevilgning KUD) som må stemme.
3. **Narrativ struktur** (mønsteret i tekst.md-filene): hero med ETT tall som bærer
   historien → 2–3 seksjoner som hver forklarer én graf i prosa FØR grafen vises →
   kortgalleri med «tilbud for tilbud»-oversikt → avsluttende avsnitt som eksplisitt
   sier hva tallene IKKE måler og legger igjen ett åpent spørsmål.
4. **Forbehold i selve produktet**, ikke i fotnoter: enhet og univers i hero-fotnote,
   kildekort nederst, komposisjonsforbehold i brødteksten (jf. kulturgap).
5. **Enheter**: prosentpoeng (pp) for differanser i andeler, aldri «prosent»;
   nb-NO-tallformat; kompakte storheter («mill.») i akser.

## Arbeidsflyt

1. Steg 0: innhent og verifiser mot tidligere analyser; fest konkrete kapitler/kontoer.
2. Definér teller/nevner skriftlig FØR uttrekk (hva er «kultur», hvilket regnskapsbegrep).
3. Uttrekk → profilering (se `nytt-datasett-onboarding`) → dobbelttellingskontroll:
   summer både per kapittel/post og per artskonto; avvik skal kunne forklares.
4. Tidsserie: KPI-juster eller bruk andeler; dokumenter kapittel-overgangsnøkkel.
5. Formidling etter metodikken over; bruk `impromptu-dataengine` for selve produksjonen.
