# Datanotat: bygda-savner-barn

Bygges av `pipeline/hent_frivillighet_korps.py`, som henter alt gjennom
`pipeline/kulturforeninger.py`. Kjøring:

    python pipeline/hent_frivillighet_korps.py
    python pipeline/bygg_manifest.py

Rådata caches i `IMPROMPTU_CACHE` (som standard `~/.impromptu-cache/brreg`) — **utenfor
repoet**. Registerfila er 210 MB, og alt i dette repoet serveres statisk av Vercel.

## Kilder

| Kilde | Hva | Merknad |
|---|---|---|
| Enhetsregisteret, `/enheter/lastned` | 1 171 548 enheter: navn, stiftelsesdato, kommunenummer, organisasjonsform | ~210 MB gzip-JSON, cachet et døgn |
| Frivillighetsregisteret | ICNPO-kategori og grasrotandel for 72 707 organisasjoner | searchAfter-sideblad, maks 100 per side |
| Enhetsregisteret, `/enheter/{orgnr}/roller` | styresammensetning for de 5 397 foreningene | ett kall per organisasjon, 8 tråder |
| SSB tabell 07459 | folkemengde per kommune og alder, 2009 og 2026 | PxWeb v0, json-stat2 |
| SSB KLASS 131 | kommuneendringer 2009–2026 | brukes til å gjøre de to årene sammenlignbare |

Ingen språkmodell inngår i denne historien. Alt er regelbasert.

## Den viktigste begrensningen: slettinger finnes ikke

Det opprinnelige narrative grepet var «nyregistreringer, slettinger og styresammensetninger».
**Slettingene lot seg ikke skaffe.** Seks endepunkter ble prøvd; verken Enhetsregisteret
eller Frivillighetsregisteret publiserer et uttrekk over slettede enheter.
`oppdateringer/enheter` starter først 2018-04-23 og gir `endringstype: "Ukjent"` for
historikken, og en stikkprøve på 1 000 poster i Frivillighetsregisteret ga 100 prosent
`frivilligOrganisasjonsstatus.innfoert`.

Følgen er at hele analysen hviler på **den stående bestanden**: organisasjoner som finnes i
registeret i dag. Det gir en systematisk overlevelsesskjevhet — «stiftet per år» blir mer og
mer ufullstendig jo lenger tilbake i tid man går, fordi de som er lagt ned underveis mangler.

Skjevheten går bare én vei, og det er verdt å være presis om retningen:

- **Nedgangen fra 1960-tallet er et minimum.** Det virkelige antallet korps stiftet i 1955 er
  høyere enn søylen viser, ikke lavere. Skjevheten demper funnet, den forsterker det ikke.
- **Konklusjonen om nystiftelser står seg.** De siste ti–femten årene har frafallet knapt
  rukket å virke, og det er der påstanden «det stiftes ikke nye skolekorps» hviler.
- **Aldersprofilen i `bestand` skal leses som aldersprofil**, ikke som stiftelseshistorie.
  Undertittelen sier «dagens bestand».

Dødeligheten er derfor besvart indirekte — gjennom stiftelsestakt og aldersprofil — og det er
sagt eksplisitt i teksten. En direkte dødelighetsanalyse krever innsyn eller et kjøpt uttrekk.

## Klassifisering på navn, ikke næringskode

Næringskoden kan ikke skille et skolekorps fra et kor: begge står som regel på 90.201
«Utøvende kunstnerisk virksomhet innenfor musikk», som også rommer platestudioer og
enkeltpersonforetak. Navnene er til gjengjeld påfallende konsekvente. `kategoriser()` i
`kulturforeninger.py` sorterer i fem kategorier:

| Kategori | Antall | Regel (forkortet) |
|---|---|---|
| skolekorps | 829 | «KORPS» + skole/skule/junior/aspirant/knøtte/barne/ungdom |
| voksenkorps | 532 | «KORPS» uten de nevnte |
| kor | 1 372 | ord som slutter på «KOR», eller songlag/sanglag/sangforening/vokalensemble |
| teater | 970 | teater/teatret/teatre/revy |
| tradisjon | 1 694 | spelemannslag/leikarring/folkedans/folkemusikk/husflidslag/bygdekvinnelag/mållag/historielag |

**Totalt 5 397 organisasjoner** av 1 171 548 enheter.

### To filtre som må være der

1. **Organisasjonsform.** Uten filteret drar navnereglene med seg 713 kommersielle treff:
   `ELKOR AS`, `FALKOR HOLDING ASA`, `KORPSBUTIKKEN AS`, `MATSKOR SAMDRIFT DA`,
   `TEATERBYGG AS`. Bare `FLI, FORB, SA, STI, ANNA, KIRK, BA` slipper gjennom. Feilen var
   konsentrert i kor (+236) og teater (+120); skolekorpstallene og alle geografiske funn var
   upåvirket.
2. **Negativ ordliste (`IKKE_KULTUR`).** Tre falske positive overlever formfilteret:
   `SKOR SKYTTARLAG` (skytterlag), `ØIE JULETRE OG DEKOR SA`, og `NORD AURDAL RØDEKORS
   HJELPEKORPS` (beredskap, ikke musikk). Lista er `HJELPEKORPS, RØDEKORS, RØDE KORS,
   SANITETSKORPS, SKYTTARLAG, SKYTTERLAG, JULETRE`.

Merk hvorfor lista er så snever: `DEKOR` kan ikke svartelistes generelt. Det finnes et kor som
heter `DEKOR`, og `BLANDAKORET DEKOR`. Det samme gjelder `BYGDEKOR`, `GRENDEKOR`,
`PARADEKORPS` og `BYGDEKORPS` — alle ekte.

### Uavhengig kontroll av utvalget

4 420 av de 5 397 står også i Frivillighetsregisteret. Av dem er **87,8 prosent kodet ICNPO
1100 «Kunst og kultur»** av registeret selv, og 81,4 prosent deltar i grasrotandelen. Per
kategori: skolekorps 96 %, teater 95 %, kor 94 %, voksenkorps 83 %, tradisjon 74 % (mållag og
historielag kodes ofte som interesseorganisasjoner, ikke kultur).

Teater er bare rundt 50 prosent dekket i Frivillighetsregisteret — mange teatre er AS eller
profesjonelle, og faller da ut av utvalget vårt på organisasjonsform.

## Stiftelsesdato, og 1995-artefakten

`registreringsdatoEnhetsregisteret` kan ikke brukes: den klumper seg i 1995 (Enhetsregisteret
ble opprettet) og i 2009 (Frivillighetsregisteret og grasrotandelen). Den måler
registreringsbølger, ikke aktivitet. `stiftelsesdato` er utfylt for 97–99 prosent og brukes i
stedet.

Men også den har en artefakt: for organisasjoner stiftet lenge før 1995 ble stiftelsesdatoen
mange steder satt lik registreringsdatoen. **61 skolekorps står som «stiftet» i 1995, mot ett
til fire i hvert av årene rundt.** `stiftelsesaar()` forkaster radene der de to datoene er
identiske. Det fjerner 54 av de 61, og nesten ingenting utenfor 1995 — en organisasjon rekker
sjelden å bli registrert samme dag den stiftes.

61 av 829 skolekorps har derfor ikke brukbart stiftelsesår. `bestand`-diagrammet viser bare
hele tiår (1900–2019), så 75 av 829 faller utenfor søylene: 61 uten dato, 13 stiftet i
2020-årene, ett før 1900. En halvferdig 2020-søyle ved siden av fulle tiår ville lest som et
fall som ikke finnes.

## Sammenlignbare kommuner: union-find, ikke oppslagstabell

SSB tilbakedaterer ikke kommunenummer — Halden er `0101` i 2009 og `3101` i 2026, og et
direkte oppslag på dagens kode gir 0 for 2009. Kommunereformene gikk dessuten begge veier:
Ålesund ble delt i 2024 (`1507` → `1508` + `1580`). En ren gammel-til-ny-oppslagstabell
mister den ene halvparten av en deling **stille**, uten feilmelding — det skjedde i første
forsøk, der `1508` bare manglet.

`sammenlignbare_enheter()` kjører derfor union-find over alle `codeChanges` i KLASS 131 og
slår alle koder som henger sammen gjennom en endring inn i én gruppe. Resultatet er **352
reform-uavhengige kommunegrupper** som er summerbare i begge ender av perioden. Prisen er at
noen grupper dekker flere av dagens kommuner — derfor står det «kommunegrupper» og ikke
«kommuner» i metodeteksten. Summen ble kontrollert mot SSBs publiserte landstall for 2010.

Gruppene deles i vekst (≥ +5 %), stabil, og nedgang (≤ −5 %) etter folketallsendring
2009–2026: 169 / 118 / 65 grupper.

## Personopplysninger i `/roller`

Endepunktet returnerer **navn og full fødselsdato** for sittende styremedlemmer.
`hent_styrer()` plukker ut `int(fdato[:4])` — fødselsåret — og kaster navnet og resten før noe
skrives til disk. Cachen skal ikke være et personregister. Snapshotet inneholder bare
aggregater: medianalder, andel over 60, andel under 40, og antall styremedlemmer per kategori.

Ingenting fra denne historien sendes til noen språkmodell. Se [SIKKERHET.md](../../../SIKKERHET.md).

## Øvrige forbehold

- **Registrering er ikke aktivitet.** Et korps som ikke har øvd på fem år, står fortsatt i
  registeret til noen melder det slettet. Bestandstallene er et tak, ikke et aktivitetsmål.
- **Fylkeskartet bruker 2024-inndelingen** (15 fylker) og normaliserer mot barn 6–15 år i 2026
  fra SSB. Kommunenummeret er organisasjonens forretningsadresse, som for små foreninger ofte
  er kassererens hjemmeadresse — det flytter enkeltforeninger, men ikke mønsteret.
- **«Uorganiserte kulturtiltak»** fra den opprinnelige bestillingen er per definisjon ikke i et
  organisasjonsregister og er ikke forsøkt målt. Nærmeste tilnærming er teater- og
  revygruppene, som er den yngste og raskest voksende kategorien.
- **Aldersprofilen på styrene er et øyeblikksbilde** (august 2026), ikke en tidsserie.
  Registeret har ingen historikk på roller i åpne data.
