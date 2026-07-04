---
name: nytt-datasett-onboarding
description: Standardprosedyre for å profilere, rense og dokumentere et nytt kultursektor-datasett — fra rå fil/API til datasettprofil, verifiserte lærdommer og et forslag til ny dedikert skill for datasettet. Brukes hver gang brukeren introduserer et nytt datasett eller en ny datakilde (CSV/Excel/API/skraping) som skal analyseres eller inn i et av verktøyene, eller sier «her er et nytt datasett».
---

# Nytt datasett — onboarding (metaskill)

## Verifiseringsstatus

Brukerens navngitte «data-analyse-metodikk-rammeverk» ble **ikke funnet som dokument** i
tilgjengelige repoer (Google Drive utilgjengelig i økten som laget skillen). Prosedyren
under er i stedet **rekonstruert fra brukerens faktiske, verifiserte praksis** slik den er
nedfelt i kode i Impromptu-Analytics og tilskuddskompasset (lest 2026-07-04) — hvert
prinsipp har en kildehenvisning. Hvis rammeverk-dokumentet finnes: hent det i steg 0 og
harmoniser denne skillen med det.

## Prinsipper (utledet av verifisert praksis)

1. **Rådata er hellige og caches** — last ned én gang, behandle lokalt
   (hent_bulk_tildelinger.py, brreg_lookup-cache).
2. **Hver renseavgjørelse dokumenteres med antall** — «fjernet N duplikater (X → Y)»
   printes og havner i docstring/commit (bygg_nkf_flb_v2.py er gullstandarden).
3. **Feil hardt, ikke stille** — scripts nekter å skrive output som ikke består
   rimelighetssjekk (SystemExit-mønsteret i hent_ssb_*.py).
4. **Kontrakt før innhold** — definer påkrevd felt-/metadatastruktur og valider maskinelt
   (kontrakt.py).
5. **Snapshot, ikke live** — analyser/produkter bygger på statiske, daterte uttrekk.
6. **Skill verifisert fra antatt** — usikre verdier flagges i egne kolonner
   (bevilgningsaar_usikker-mønsteret), demo-data merkes synlig (demo: true).
7. **Høflig innhenting** — User-Agent med kontaktinfo, pause mellom kall, batch-oppslag
   der API-et støtter det.

## Prosedyre

### Steg 0 — kontekst
Spør/avklar: Hva er kilden (eier, URL, lisens/åpenhet)? Hvilket produkt skal det inn i
(impromptu.no-historie, tilskuddskompasset, egen analyse)? Finnes kodebok/dokumentasjon?
Inneholder det personopplysninger (→ da gjelder strengere regler: ikke inn i offentlige
repoer, aggregering før deling)?

### Steg 1 — skaff og frys rådata
Hent med høflig-innhenting-mønsteret; legg råfil i datamappe med dato i navnet; noter
nedlastingsdato og eksakt kilde-URL. Rør aldri råfilen etterpå.

### Steg 2 — teknisk profilering
Kartlegg og noter i profilen: format/encoding (norske eksporter er ofte `utf-8-sig` +
semikolon-separert — verifisert gjennomgående i tilskudd_data), radantall, kolonner med
typer, nøkkelkandidater og duplikater (rå + semantiske), dekning per år/kategori,
manglende verdier per kolonne, ekstremverdier, og **gyldighetsvinduer for årstall/datoer**
(jf. [2018, 2035]-vinduet for bevilgningsaar). Norske datoformater («12. august 2026»)
og desimalkomma er standardfeller.

### Steg 3 — semantisk profilering
Hva betyr hver kolonne EGENTLIG? Klassiske kultursektor-feller (alle observert i faktiske
datasett i repoene): beløp søkt vs. tildelt vs. utbetalt; status avledet vs. eksplisitt;
enhet person vs. organisasjon; fylkesstruktur (2024-inndelingen vs. eldre); bokmål/nynorsk-
variasjon i kategoritekster; «i alt»-aggregater blandet inn blant kategoriene; samme
krone i flere ledd (dobbelttelling). Identifiser en **kanarifugl**: ett tall du kan
kontrollere mot en uavhengig kilde.

### Steg 4 — rens med regnskap
Skriv rensescript som printer antall for hver operasjon. Fyll bare tomme celler ved
beriking, aldri overskriv (berik_nkf_flb_brreg-prinsippet). Uidentifiserbare rader får
eksplisitt «Uidentifisert (…)»-merke i stedet for å slettes stille.

### Steg 5 — dokumenter
Skriv datasettprofil etter malen i [profil-mal.md](profil-mal.md), med tydelig skille
mellom **verifisert** (mot kilde/kode) og **antatt** (må sjekkes med eier).

### Steg 6 — foreslå ny skill (obligatorisk avslutning)
Avslutt alltid med et utkast til en ny dedikert skill for datasettet:
- `name`: kort slug for datasettet
- `description`: hva datasettet er OG når skillen skal trigges
- Innhold: verifiseringsstatus, feltstruktur, fallgruvene funnet i steg 2–4 (de konkrete,
  ikke generiske), oppdateringsprosedyre og kanarifugl-tall.
Presenter utkastet for brukeren og tilby å legge det i `skills/`-mappen sammen med de
øvrige, klart til zip og opplasting i Customize > Skills.

## Kvalitetskrav til leveransen

En onboarding er ferdig når: råfil + rensescript + profil finnes; hver renseoperasjon har
et tall; kanarifuglen stemmer; personvernvurderingen er notert; og skill-utkastet er levert.
