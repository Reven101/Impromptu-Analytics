---
name: impromptu-designsystem
description: Impromptu Analytics' visuelle profil og skrivestil — Wes Anderson-estetikken (varmt papir, granittgrønn, sennep), validerte dataserie-farger, typografi (Jost + IBM Plex Mono) og den narrative stemmen fra datahistoriene. Bruk denne skillen alltid når Simen lager noe nytt under Impromptu-merkevaren — nye sider, produkter, artifacts, presentasjoner, plakater eller datavisualiseringer som skal se ut som impromptu.no eller tilskuddskompasset — og når tekst skal skrives i impromptu-stilen. Aktiveres ved «i impromptu-stil», «samme design som», eller nye leveranser til impromptu.no/tilskuddskompasset.
---

# Impromptu designsystem — visuell profil og stemme

## Verifiseringsstatus

**Fullt verifisert 2026-07-04** mot `historier/motor/tokens.css` (kanonisk kilde),
`komponenter.js`, tilskuddskompassets `index.html` og de publiserte historietekstene
(kultur/kulturgap). Fargekodene under er kopiert, ikke gjengitt etter hukommelsen.

## Estetikken i én setning

Wes Anderson-estetikk: varmt papir, granittgrønn, sennep og rose; symmetri, doble linjer
og typografisk presisjon. Helstatisk, rolig, etterprøvbart.

## Fargepalett (tokens.css er fasit)

**Flater og tekst:**
| Token | Hex | Bruk |
|---|---|---|
| `--papir` | `#F2EDE0` | sidebakgrunn |
| `--kort` | `#FBF8F0` | kort- og diagramflate |
| `--linje` / `--linje-svak` | `#C9C0AC` / `#DDD6C4` | hårlinjer, rammer / gridlinjer (recessive) |
| `--blekk` | `#27332D` | primærtekst |
| `--blekk-sekundaer` / `--blekk-dempet` | `#46514A` / `#5F6A62` | sekundær / akser og etiketter (4.5:1 på kort) |

**Merkevare — kun kromatikk/pynt, ALDRI dataserier** (regel fra tokens.css):
`--gran #1F4E45` (overskrifter/rammer/lenker), `--sennep #D9A441` (fokusring, aksenter),
`--rose #D9A199` (dekor), skygge `rgba(31,78,69,.12)`.

**Dataserier — kategorisk, validert for kroma/CVD/kontrast. Fast rekkefølge; aldri
resirkuler, aldri omfarg ved filtrering:**
`#0E7D59` gran-grønn → `#A9761B` sennep-oker → `#B23A28` teglstein → `#3E6CB0` støvblå
→ `#C05A6E` gammelrosa → `#8A4A82` plomme. Maks 6 serier; ved flere: aggreger.

**Sekvensiell rampe (kart/magnitude) — validert ordinal: monoton lyshet, én kulør,
lys ende ≥ 2:1 mot kortflaten:**
`#8FB6A6 → #699C88 → #47836D → #2C6752 → #1A4C3B → #0F3527`.
Etikett-tekst inne i fargede flater velges etter luminans (terskel ~0.45: blekk på lys,
`#FBF8F0` på mørk — jf. lagKart i komponenter.js).

Ikke bytt eller «forbedre» serie-/rampefargene uten å validere kontrast og fargeblindhet
på nytt — eksplisitt advarsel i repoet.

## Typografi og krom

- **Jost** (fallback Avenir Next/Futura) for alt løpende; **IBM Plex Mono** for etiketter,
  tall-chrome og metadata. Google Fonts-import på begge nettstedene.
- **Eyebrow**: mono, .66rem, letter-spacing .24em, uppercase, gran — over hver tittel.
- **Mono-etikett**: mono, .6rem, letter-spacing .14em, uppercase, blekk-dempet.
- **Doble linjer**: `3px double var(--gran)` under header/over footer — signaturen.
- **Kort-flate**: kort-bakgrunn, 1px linje-ramme, radius 3px, myk skygge. Tilskudds-
  kompasset bruker en hardere variant på ordningskortene: `border:1.5px solid var(--ink)`
  med offset-skygge `4px 4px 0` (verifisert forskjell — behold per produkt).
- Avstandsskala 4px-basert: 4/8/12/20/32/52/84. Spaltebredde 900px sentrert; prosa 62ch.
- H1 på tilskuddskompasset: uppercase, vekt 800; impromptu-historiene: normal store/små.
- Tall formateres alltid `nb-NO` (Intl.NumberFormat); kompakte storheter «mill.»/«k».

## Tilgjengelighet (ikke valgfritt — verifisert praksis i begge produkter)

- Fokusring: `outline: 3px solid var(--sennep); outline-offset: 2px` på alle interaktive.
- `prefers-reduced-motion: reduce` → all transition/animation av.
- Hver graf har en «Vis tallene som tabell»-tvilling (`<details>`); chips bruker
  `aria-pressed`; kartfliser har `aria-label` med navn + verdi; tooltips `role="status"`.
- Demodata merkes synlig (`.demo-merke`, sennep-pille) — aldri stille plassholdertall.

## Stemmen (verifisert fra kultur/kulturgap-tekstene og om-sidene)

- **Litterær men presis**: bilder som «et gruppebilde av folket, tatt om igjen og om
  igjen», «kurvene ligger i hver sin etasje» — men aldri på bekostning av presisjon.
- **Ett tall bærer heroen**; hver graf forklares i prosa FØR den vises.
- **Differanser i andeler oppgis i prosentpoeng (pp)**, aldri «prosent».
- **Avslutt med ydmykhet**: siste avsnitt sier eksplisitt hva tallene IKKE måler, og
  legger igjen ett åpent spørsmål («hvem er kulturtilbudene egentlig for?»).
- **Forbehold i selve produktet**: «Historiske tall – ikke et løfte om utfall», kildekort,
  interessekonflikt-deklarasjon (om.html). Kilden står alltid oppgitt og kan ettergås.
- Bokmål, «vi» om befolkningen, «dere» til organisasjoner (tilskuddskompasset).

## Bruk i praksis

- Nye sider/artifacts: start fra tokenene over; ved bruk av dataviz-verktøy, bytt inn
  seriepaletten og rampen herfra i stedet for standardpaletten.
- Kanonisk kilde ved tvil: `historier/motor/tokens.css` i Impromptu-Analytics-repoet —
  les den, ikke stol på gjengivelser (heller ikke denne).
