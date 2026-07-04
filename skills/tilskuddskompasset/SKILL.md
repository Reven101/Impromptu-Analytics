---
name: tilskuddskompasset
description: Vedlikehold og videreutvikling av Tilskuddskompasset (tilskuddskompasset.impromptu.no, repo Reven101/tilskuddskompasset) — grant-navigasjonsverktøy for frivillige organisasjoner med data fra tilskudd.no, Kulturdirektoratet og NFI. Bruk denne skillen alltid når Simen jobber med tilskuddskompasset: dataoppdatering (lag_v4_data.py-pipelinen), endringer i index.html/ordninger_v4.js, nye datakilder, eller spørsmål om filtre, innvilgelsesgrad-måleren (kompassnålen) og transparensfunksjonene. Aktiveres også ved omtale av tilskudd.no-data, NKF/FLB-vedtaksdata, NFI-tildelinger eller innvilgelsesgrad.
---

# Tilskuddskompasset — grant-navigasjon på åpne data

## Verifiseringsstatus

**Verifisert mot kildekode og data 2026-07-04** (repo `Reven101/tilskuddskompasset`, main):
alt under er lest ut av `index.html`, `lag_v4_data.py`, `tilskudd_data/bygg_nkf_flb_v2.py`,
øvrige pipeline-scripts, README.md, om.html og den genererte `ordninger_v4.js`.

**Faktisk tilstand per 2026-07-04:** dataversjon **v4** (`ordninger_v4.js`, `GENERERT =
"2026-07-02"`), **307 ordninger** fordelt på ID-prefiks: DT 152 (tilskudd.no), NFI 62,
NKF 48 (Kulturrådet), KUL 23, FLB 15 (Fond for lyd og bilde), KD 7 (foreldreløse
Kulturdirektoratet-ordninger uten vedtakshistorikk). Merk: det finnes ikke noe
«versjonsnummer» utover v4-navnet i filnavnene — nettsiden viser bare GENERERT-datoen.

## Arkitektur

Ren statisk HTML/JS uten byggsteg og rammeverk. `lag_v4_data.py` (kjøres lokalt) bygger
`ordninger_v4.js` som eksporterer to globale: `GENERERT` (ISO-dato) og `ORDNINGER`
(array med 38 felter per ordning — se [feltstruktur.md](feltstruktur.md)).
`index.html` leser den direkte. Deploy: push til main → Vercel.

Tre datakilder med hver sin delpipeline og hver sine begrensninger — kjørerekkefølge,
kadens og fallgruver per kilde står i [datapipeline.md](datapipeline.md).

## Verifiserte funksjoner i UI-et (index.html)

- **Fritekstsøk** over tittel/forvalter/beskrivelse/hvem/formål/dep/mottakere+tiltak.
  Søk under 4 tegn matcher på ordgrense (regex) for å unngå støytreff; ≥ 4 tegn substring.
- **Innvilgelsesgrad-måler** («kompassnål»): halvsirkel-SVG-gauge per ordning med nål,
  «X % får ja». Viser kursiv «historikk mangler» ved null data, **`n=<antall>`-varsel når
  soknader < 20** (lav-n), og egen linje «Får Y % av omsøkt» når avkorting < 0,95.
- **Filtre**: type-chips (Alle/Drift/Prosjekt); «kun åpne/kommende frist»-toggle (PÅ som
  default — husk denne når «en ordning mangler» feilsøkes!); avansert: departement, frist
  (30/90 dager/løpende), fylke, fagfelt (6 grupper mappet til ICNPO-kategorier), org.form
  (Frivillig/ideell, Privat, Offentlig), formål (fritekst-nøkkelordgrupper) og
  beløpsstørrelse (4 intervaller mot typisk_tildeling, velg én).
- **Sortering**: nærmeste frist (default), høyest innvilgelse, størst pott, størst typisk
  tildeling, lavest konkurranse, navn A–Å.
- **Detaljvisning med 3 faner**: Oversikt (beskrivelse/formål/hvem/hva), Tall og mottakere,
  Søk om dette (frister, hvordan søke, kriterier/rapportering, ICS-kalenderfil med
  14-dagers alarm, lenker til søknadsside/regelverk/tilskudd.no).
- **Transparensfunksjoner** (kjerneverdien i produktet):
  - Topp 8 mottakere siste år, rangert tabell med tildelt OG omsøkt beløp, tiltak, fylke.
  - Boksplott av beløpsfordeling (min/kvartiler/median/maks) med klarspråk-gloss.
  - Fylkesfordeling som horisontale søyler; sparklines for tildelt/mottakere per år.
  - Konkurranse-badge ved > 3x omsøkt vs. tildelt; avkortingsprosent.
  - Forbehold overalt: «Historiske tall – ikke et løfte om utfall», footer-tekst om at
    innvilgelsesgrad er historikk, kildeattribusjon og synlig GENERERT-dato topp og bunn.
  - om.html deklarerer interessekonflikt: personen bak er selv ansatt i offentlig
    forvaltning på tilskuddsfeltet.

## Fallgruver (alle dokumentert i faktisk kode)

- **Sammenlignbarhet på tvers av kilder**: tilskudd.no-tallene (totalRecipients osv.) gjelder
  ALLTID siste rapporterte budsjettår, mens NKF/FLB-rådata spenner 2021–2031. Derfor filtreres
  NKF/FLB til siste år med faktiske tildelinger før mottakere/beløp/typisk beregnes — ellers
  telles unike mottakere over ti år og tallene blir usammenlignbare. Fylkesfordeling bruker
  derimot bevisst hele perioden (rikere bilde for små ordninger).
- **Fremtidige budsjettår filtreres bort** (> 2026): det er ubehandlede søknader, ikke tildelinger.
- **NFI har ingen avslagsdata** → aldri beregn innvilgelsesgrad for NFI-ordninger (grad=null).
- **Innvilgelsesgrad for NKF/FLB krever avslags-eksporten** (bygg_nkf_flb_v2.py) — filen med
  kun innvilgede kan ikke gi grad.
- **Konkurranse-tallet for NKF/FLB undervurderes**: omsøkt beløp finnes bare for innvilgede
  i den filen (avslåttes omsøkte beløp mangler).
- **Norske datoer må til ISO**: NFI-frister kommer som «12. august 2026»; `_norsk_til_iso()`
  konverterer. En tidligere bug (fikset i commit 536d0fd-serien) var nettopp norske datoformat
  som ikke ble parset av `parseFrist`.
- **«Foreldreløse» ordninger**: ordninger med frist/innhold men uten vedtakshistorikk må
  legges til eksplisitt (KD-* og NFI-* uten historikk), ellers er helt nye ordninger usynlige
  akkurat når de er søkbare.
- **Statens kunstnerstipend er bevisst utelatt** (individstipend, ikke organisasjonstilskudd
  — avtalt med eier). Ikke «fiks» dette. Likeledes filtreres soker_type=Person bort.
- **XSS**: all ordningstekst går gjennom escHTML/escAttr før innerHTML — behold det mønsteret.
- Datakilden 2021–2023 er Kulturdirektoratets **gamle plattform, nedlagt 2026** — kan ikke
  re-hentes; behandle de historiske filene som uerstattelige.

## Typiske oppgaver

- **Dataoppdatering**: følg README-ens fire steg (tilskudd.no månedlig; NKF/FLB og NFI
  halvårlig; alltid avslutt med `python lag_v4_data.py` + commit av `ordninger_v4.js`).
  Detaljer og kontrolltall: [datapipeline.md](datapipeline.md).
- **Ny datakilde**: skriv egen `bygg_*_rader()` i lag_v4_data.py som produserer komplette
  rader med alle 38 felter (null der data mangler) — UI-et er felt-drevet og tåler null.
- **UI-endring**: alt ligger i index.html (én fil, ~740 linjer, vanilla JS). Test lokalt ved
  å åpne filen direkte (ingen moduler her, i motsetning til impromptu.no).
