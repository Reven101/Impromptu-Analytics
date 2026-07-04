# Feltstruktur: ORDNINGER-rader i ordninger_v4.js

Verifisert mot generert fil (GENERERT 2026-07-02) og lag_v4_data.py. 38 felter per rad;
alle kan være null/tom — UI-et er felt-drevet og skjuler det som mangler.

## Identitet og innhold
| Felt | Innhold |
|---|---|
| `id` | Prefiks angir kilde: `DT-` tilskudd.no, `NKF-`/`KUL-`/`FLB-` Kulturrådet/FLB-vedtaksdata, `KD-<slug>` foreldreløs Kulturdirektoratet-ordning, `NFI-<slug>` filminstituttet |
| `tittel`, `beskrivelse` | Navn + ingress |
| `forvalter`, `forvalter_kort`, `dep` | Forvalter (langt/kort) og departement |
| `formaal`, `hvem`, `hva`, `kriterier`, `rapportering`, `hvordan` | Sjekkliste-tekstene (mål/hvem kan søke/hva midlene kan brukes til/tildelingskriterier/rapporteringskrav/hvordan søke) |
| `soknadslenke`, `regelverk` | URL-er (regelverk ofte Lovdata for NFI) |

## Frister og krav
| Felt | Innhold |
|---|---|
| `frist` | Neste/første frist, ISO `YYYY-MM-DD` (UI regner selv ut neste kommende fra `frister`) |
| `frister` | Alle kjente frister, ISO-liste |
| `fristtype` | `"CONTINUOUS"` = løpende (påvirker åpen-filter og badge) |
| `krever_frivillig` | Krever registrering i Frivillighetsregisteret |
| `typer` | `["Driftsmidler"]`/`["Prosjektmidler"]`/begge |
| `mottakerkategorier` | tilskudd.no-kategorier (rå) |

## Statistikk (transparensdelen)
| Felt | Innhold / regler |
|---|---|
| `grad` | Innvilgelsesgrad 0–1 = grantedApplications/totalApplications. **null for NFI** (ingen avslagsdata) |
| `soknader`, `innvilget`, `soekere` | Grunnlagstall; UI viser lav-n-varsel når soknader < 20 |
| `mottakere_n` | Unike mottakere **siste rapporterte budsjettår** |
| `belop` | Budsjettramme (kun tilskudd.no-ordninger) |
| `total_soekt`, `total_tildelt` | Sum omsøkt/tildelt (siste år) |
| `typisk_tildeling` | total_tildelt / mottakere_n — brukes av beløpsfilteret |
| `konkurranse` | total omsøkt / total tildelt (f.eks. 3.2 = 3,2x overtegning); badge ved > 3 |
| `avkorting` | Snitt av tildelt/omsøkt for innvilgede; UI viser når < 0.95 |
| `fordeling` | `{min,q1,median,q3,max,snitt}` for tildelt per mottaker (boksplott) |
| `topp_mottakere` | Inntil 8: `{n: navn, t: tildelt, s: omsøkt eller null, tiltak (maks 100 tegn), f: fylke}` |
| `fylker` | `{fylkesnavn: antall tildelinger}` — hele perioden for NKF/FLB, sortert synkende |
| `ts_tildelt`, `ts_mottakere` | Tidsserier `[{x: "2021", y: tall}]` for sparklines |

## Klassifisering (filtergrunnlag)
| Felt | Innhold |
|---|---|
| `icnpo` | Topp 3 ICNPO-kategorier fra tildelingsdata; NKF/FLB/NFI hardkodes `["Kunst og kultur"]` |
| `orgform` | Delmengde av `Frivillig/ideell`, `Privat virksomhet`, `Offentlig` (fra sektorkoder/mottakerkategorier via SEKTOR_TIL_GRUPPE/KATEGORI_TIL_GRUPPE) |

## UI-koblinger å huske
- Fagfelt-chipsene i UI mapper til ICNPO via `FAGFELT_ICNPO` i index.html.
- Formål-chipsene er fritekst-nøkkelord mot haystack (tittel+beskrivelse+hvem+formål+mottakere).
- Beløpsfilteret bruker `typisk_tildeling ?? belop`; ordninger uten begge slipper gjennom.
- `kildeNavn()` i index.html er definert men ubrukt per 2026-07-04, og kjenner ikke NFI
  (DT → «tilskudd.no», alt annet → «kulturdirektoratet.no») — oppdater den før eventuell bruk.
