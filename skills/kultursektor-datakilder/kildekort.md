# Kildekort — endepunkter, mønstre og feller per kilde

Alt verifisert mot kjørende kode 2026-07-04 der ikke annet er merket.
Referansescript i parentes ved hvert kort.

## 1. SSB PxWeb (data.ssb.no) — offisiell statistikk

*(hent_ssb_kultur.py, hent_ssb_kulturgap.py i Impromptu-Analytics/pipeline/)*

- **Metadata**: `GET https://data.ssb.no/api/v0/no/table/<TABELL_ID>` → `variables`.
- **Data**: `POST` samme URL med `{"query": [...], "response": {"format": "json-stat2"}}`.
- json-stat2 er flat-indeksert: `flat = flat * size[dim] + indeks` i rekkefølgen fra
  `stat["id"]`. Kun standardbiblioteket trengs (urllib).
- **Kjente tabeller**: 13503 kulturbruk × kjønn/alder (1991–), 13504 kulturbruk ×
  utdanning, 10467 navn, 06913 befolkning.
- **Feller** (alle håndtert i koden — gjenbruk mønstrene):
  - Finn variabler ved TEKSTSØK i variabelnavn, ikke hardkodede koder (de endres).
  - Tabeller har flere måltall (andel OG gj.sn. besøk) — scor `valueTexts`, feil hardt
    hvis andels-målet ikke finnes; valider 0–100 per verdi.
  - Bakgrunnsvariabler: dropp ved `elimination: true` (API-et aggregerer), ellers velg
    totalkategori («alle»/«begge»/«i alt»/«total»).
  - Kategoritekster veksler bokmål/nynorsk («strøym»/«strømm») — match på nøkkelord.
  - Utvalgsundersøkelser har ekte hull i seriene (kulturbruk ~hvert 4. år) — ikke interpoler.
  - Faller en tabell bort: søk statistikknavnet på data.ssb.no og oppdater TABELL_ID.

## 2. tilskudd.no (Lotteri- og stiftelsestilsynet) — tilskudd til frivilligheten

*(hent_bulk_tildelinger.py, hent_utvidet_data.py, tilskuddsdata.py)*

- **Bulk-tildelinger**: `GET https://tilskudd.lottstift.no/api/download/allocation-to-volunteers?year=<ÅÅÅÅ>`
  → Excel. **Ett budsjettår per kall** — loop over årene og slå sammen. Rask (~5 sek/år).
- **Per-ordning metadata**: ordningssidene er Next.js; les `__NEXT_DATA__`-JSON-blokken
  (strukturert og stabil, HTML-fallback ved behov). Ordnings-ID-rom crawlet: 1–1200.
  Inneholder allocationSummary (totalRecipients, totalGrantedAmount, totalApplications …),
  tidsserier og sjekkliste-tekstene (mål, hvem kan søke, kriterier, rapportering).
- **Feller**:
  - `__NEXT_DATA__` gir kun **topp 10 mottakere** per ordning; backend-API er ikke
    offentlig. Full mottakerliste = bulk-filen. Summary-tallene dekker likevel alle.
  - Summary-tall gjelder **siste rapporterte budsjettår** — ikke bland med flerårstall.
  - Budsjettår > inneværende = ubehandlede søknader; filtrer bort.
  - Avhengigheter: requests + openpyxl (bulk) / beautifulsoup4 (sider).

## 3. kulturdirektoratet.no — Kulturfondet, FLB, spillemidler

*(hent_kulturdirektoratet_innhold.py; bygg_nkf_flb_v2.py for vedtaksdata)*

- **INGEN åpen API.** To innganger:
  1. **Vedtaksdata**: manuell CSV-eksport fra kulturdirektoratet.no/vedtak
     (filter: Status = Innvilget + Avslått; alle finansieringskilder). Halvårlig rutine.
  2. **Ordningsinnhold**: server-rendret HTML; slugs høstes med regex fra
     `/tilskuddsordninger`-listesiden, innhold leses som tekst under faste overskrifter
     (formål, hvem kan søke, …). Matches mot egne ordningskoder via sidetittel.
- **Feller**:
  - **2021–23-vedtakene kommer fra den GAMLE plattformen, nedlagt 2026** — kan aldri
    re-hentes. De lokale filene i tilskudd_data/ er uerstattelige arkiver.
  - Eksportene fra gammel og ny plattform har ulik feltstruktur; harmoniseringen (med
    all dokumentert rensing: duplikater, bevilgningsår-vindu [2018, 2035], status avledet
    av beløp, FLB-omleggingen 2024) ligger i bygg_nkf_flb_v2.py — les docstringen før
    du rører noe.
  - Statens kunstnerstipend er bevisst ekskludert (individstipend). KUL-DATA, KUL-IND
    og NKF-IBK er fortsatt uidentifiserte ordningskoder.

## 4. nfi.no (Norsk filminstitutt) — filmtilskudd

*(hent_nfi_tildelinger.py, hent_nfi_ordninger.py)*

- Craft CMS + **Sprig (HTMX)**: innholdet er server-rendret, men lastes via
  `POST https://www.nfi.no/actions/sprig-core/components/render` med **HMAC-signert
  config**. Oppskrift som virker: hent listesiden (`/tildelinger`) én gang → plukk
  CraftSessionId-cookie + `sprig:config` → kall renderpunktet per år/side → paginer til
  neste-knappen er disabled. `PAGE_LIMIT=20` er NFI-s faste valg — ikke endre.
- Ordningsmetadata: kategorisidene under `/tilskudd/*` + fristene fra `/soeknadsfrister`.
- Kun standardbiblioteket (urllib + http.cookiejar + html.parser).
- **Feller**:
  - **Ingen avslagsdata** → innvilgelsesgrad kan aldri beregnes for NFI.
  - Frister på norsk datoformat («12. august 2026») → konverter til ISO
    (`_norsk_til_iso()` i lag_v4_data.py) — dette har vært en produksjonsbug før.
  - Tildelinger uten ordningsnavn grupperes «Øvrige <område>».
  - Sprig-configen kan endres ved CMS-oppgradering — feiler kallet, hent forsiden på
    nytt og les config-strukturen om igjen.

## 5. Brønnøysundregistrene (data.brreg.no) — organisasjonsberiking

*(tilskudd_data/hent_brreg_lookup.py, berik_nkf_flb_brreg.py)*

- `GET https://data.brreg.no/enhetsregisteret/api/enheter?organisasjonsnummer=nr1,nr2,…&size=N`
  — **batch på ~300 orgnr per kall** (aldri én-og-én; 14 000 enkeltkall er unødvendig last).
- Gir forretningsadresse (kommune/kommunenummer) og institusjonell sektorkode —
  **samme klassifisering** som `mottaker_sektor` i tilskuddsdataene (7000 = Ideelle org.).
- **Feller**: valider orgnr som `\d{9}` først (eksporter har «123456789.0»-artefakter);
  cache resultatet (brreg_lookup.csv) og slå kun opp NYE numre; ved beriking fyll bare
  tomme celler, aldri overskriv; fylke avledes av kommunenummer-prefiks
  (2024-strukturen: 03 Oslo, 11 Rogaland, … 56 Finnmark).

## 6. statsregnskapet.no (DFØ) — statens regnskap [IKKE VERIFISERT]

Ingen script i repoene per 2026-07-04. Generell kunnskap: åpne data med API/CSV for
utgifter per departement/virksomhet/kapittel/post og artskonto. Fallgruvene (kontoklasser,
bevilgning vs. regnskap, dobbelttelling i artskontodata) er beskrevet i
`kulturstatistikk-formidling`-skillen — les den FØR første uttrekk, og oppgrader dette
kortet til verifisert når det første scriptet er skrevet og kontrollert.
