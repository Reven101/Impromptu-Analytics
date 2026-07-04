---
name: kultursektor-datakilder
description: Kilderegister for åpne norske kultursektor-data — SSB PxWeb, tilskudd.no, kulturdirektoratet.no, NFI, Brønnøysundregistrene og statsregnskapet.no — med verifiserte API-mønstre, tilgangstriks og feller per kilde. Bruk denne skillen alltid når Simen skal hente data fra en av disse kildene, spør «hvor finner jeg tall om …» i kultursektoren, skal skrive et nytt hentescript, eller når en eksisterende kilde har endret struktur og pipelinen feiler. Gjelder kildene og innhentingen; produktpipelinene eies av tilskuddskompasset- og impromptu-dataengine-skillene.
---

# Kultursektor-datakilder — register og API-mønstre

## Verifiseringsstatus

**Verifisert 2026-07-04** mot kjørende hentescripts i `Reven101/Impromptu-Analytics`
(hent_ssb_*.py) og `Reven101/tilskuddskompasset` (hent_bulk_tildelinger.py,
hent_utvidet_data.py, tilskuddsdata.py, hent_kulturdirektoratet_innhold.py,
hent_nfi_*.py, tilskudd_data/hent_brreg_lookup.py). Unntak: statsregnskapet.no er
**ikke verifisert** (ingen script i repoene) — merket under.

## Felles innhentingsetikk (Simens standard, verifisert i alle scripts)

- User-Agent med formål og kontaktinfo: `"<Produkt>-datainnsamling (kontakt: kontakt@impromptu.no)"`.
- Pause mellom kall (0,3–0,7 s), timeout (20–30 s), batch-endepunkt der det finnes.
- Last ned rådata ÉN gang, cache lokalt, behandle offline. Snapshots dateres.
- Ved ny kilde: kjør `nytt-datasett-onboarding`-prosedyren (profilering + renseregnskap).

## Kilderegisteret

| Kilde | Hva | Tilgang | Modenhet |
|---|---|---|---|
| SSB PxWeb | Offisiell statistikk (kulturbruk, befolkning, navn …) | Åpent API, std-lib holder | Verifisert, stabil |
| tilskudd.no (Lottstift) | Statlige tilskudd til frivilligheten: ordninger + tildelinger | Åpen bulk-nedlasting + strukturert sidedata | Verifisert |
| kulturdirektoratet.no | Kulturfondet/FLB: vedtak + ordningsinnhold | INGEN API — manuell eksport + skraping | Verifisert, skjør |
| nfi.no | Filmtilskudd: tildelinger + ordninger | Skraping av Sprig-endepunkt | Verifisert, teknisk kinkig |
| Brreg Enhetsregisteret | Org-beriking: kommune, sektorkode | Åpent API, batch | Verifisert |
| statsregnskapet.no (DFØ) | Statens utgifter per kapittel/post/artskonto | Åpne data/API | **IKKE verifisert** |

Detaljerte API-mønstre, endepunkter og feller per kilde: **[kildekort.md](kildekort.md)**.

## De viktigste fellene på tvers (kortversjon)

- **Norske eksporter**: `utf-8-sig` + semikolon-separator + desimalkomma + norske
  datoformater («12. august 2026») — håndter alle fire før noe annet.
- **Samme penger, flere snitt**: søkt ≠ tildelt ≠ utbetalt; bevilgning ≠ regnskap;
  tilskudd i flere ledd dobbelttelles. Deklarer alltid hvilket tall du bruker.
- **Fylkesstruktur**: bruk 2024-inndelingen (15 fylker); eldre data må mappes om.
- **Kilder dør**: Kulturdirektoratets gamle plattform (2021–23-vedtakene) er nedlagt —
  de lokale filene er uerstattelige. Behandle historiske uttrekk som arkivmateriale.
- **Struktursjekk før tillit**: alle Simens scripts feiler hardt med forklarende melding
  når kilden ser annerledes ut enn ventet, og printer kontrolltall (kanarifugl) for
  manuell rimelighetssjekk. Nye scripts skal gjøre det samme.

## Vedlikehold av dette registeret

Når en ny kilde tas i bruk (via `nytt-datasett-onboarding`): legg til rad i registeret og
et kildekort i kildekort.md med endepunkt, autentisering/triks, kjente feller og dato for
siste verifisering. Når en kilde endrer struktur: oppdater kortet med hva som endret seg.
