# Datanotat: Verden vil se folkefienden

Publisert 2026-08-28. Kilde: [IbsenStage](https://ibsenstage.hf.uio.no/), Universitetet i Oslo,
hentet 27.–28. august 2026. Deler grunnlag med [Hundre år til Kina](../hundre-ar-til-kina/DATANOTAT.md),
der kildens egenskaper og hentingen er dokumentert.

## Reproduksjon

```
python pipeline/bygg_analysetabell.py
python pipeline/bygg_historie_repertoar.py
python pipeline/kontrakt.py && python pipeline/bygg_manifest.py
```

## Hva som telles

Andel av **oppsetninger**, ikke av forestillinger. En produksjon som gikk femti kvelder
teller like mye som en som gikk én. Vi har forestillingstall for 18,5 % av oppsetningene
(`ibsenstage_forestillinger.json`), men dekningen er for skjev til å vekte med: tallet
finnes der arkivarene har ført det, og det er ikke tilfeldig hvilke oppsetninger det
gjelder.

Hvert verk telles én gang per oppsetning (`set(r["verk"])`). En kveld med to Ibsen-stykker
teller for begge, men en kompilasjon som spiller samme stykke i to bearbeidelser teller
bare én gang.

**2026 er utelatt.** Arkivet har registreringer fram til oktober 2026, altså etter
hentedatoen: det er annonserte oppsetninger, ikke spilte. Å ta dem med ville blandet plan
og historie. Dette er også grunnen til at ett tall måtte rettes etter faktasjekk — «i 33
land» var regnet med 2026 inkludert, riktig tall for 2022–2025 er 30.

## Hvorfor bolker i én graf og årstall i den andre

Årsandelene per verk er for støyende til å leses: «Et dukkehjem» går fra 11,7 % (2015) til
23,3 % (2016) uten at noe har skjedd. Andelsgrafen bruker derfor femårsbolker.

Konsentrasjonen — topp tre sin andel — er stabil nok per år til at nivåskiftet i 2017 er
synlig uten glatting, og der ville bolker skjult nettopp det som er poenget.

**Siste punkt i andelsgrafen er 2025 alene**, ikke en full femårsbolk, og er derfor mer
utsatt for støy enn punktene før det. Kortgalleriet sammenligner ti år (2010–2019) med
fire (2022–2025). Begge deler står i teksten.

## Rammen som ble forkastet

Historien begynte som et spørsmål om hva som spilles **etter pandemien**. Den rammen
overlevde ikke testen.

Pandemien er utvetydig i volumet: 449 oppsetninger i 2018, **89 i 2021**, tilbake på 347 i
2025. Men konsentrasjonen — det egentlige funnet — begynte før:

| År | Oppsetninger | Topp 3 | Ulike verk | Land |
|---|---|---|---|---|
| 2012 | 479 | 52,0 % | 19 | 44 |
| 2015 | 389 | 51,7 % | 21 | 38 |
| 2018 | 449 | 62,4 % | 18 | 47 |
| 2021 | 89 | 72,2 % | 10 | 23 |
| 2025 | 347 | 74,8 % | 15 | 47 |

Testet formelt: **ni av ni år fra og med 2017 har topp tre over 57 %. Av de sytten årene
før gjelder det bare seks.** Nivåskiftet ligger i 2017, tre år før pandemien.

Underveis overtolket vi årsdataene i motsatt retning først — påstanden «innsnevringen
begynner i 2017» ble opprinnelig lest ut av en støyete årsserie ved øyemål. Den ble så
testet ordentlig, og holdt. Men den er en observasjon om et nivåskift, ikke om en
enkeltårsak.

## Den nærliggende innvendingen, og hvorfor den ikke holder

At ferske år er dårligere registrert, og at et arkiv lettere fanger opp en stor «Et
dukkehjem» enn et lite «Vildanden», ville gitt nøyaktig dette mønsteret.

Men dekningen har ikke falt bort: 2015 hadde 389 oppsetninger i 38 land, 2025 har 347 i
**47** land. Elleve prosent færre oppsetninger, ni flere land — og likevel 15 ulike stykker
mot 21. Var det et registreringsproblem, skulle antall land falt sammen med antall verk.

Dette er en svekkelse av innvendingen, ikke en avvisning. En helt sikker test krever en
uavhengig kilde — for eksempel nasjonal teaterstatistikk fra Spania eller Tyrkia, som er
blant toppland for «En folkefiende». Det er ikke gjort.

## Om «En folkefiende»

Stigningen er monoton over fem femårsbolker: 6,8 % (2005–09) → 13,3 → 16,4 → 19,4 → 23,8 %
(2025). Det er det som gjør funnet sterkt — ikke nivået.

Nivået er nemlig ikke enestående: i 1950–54 lå stykket på 19,1 %, med 63 oppsetninger bak
tallet. Men serien svingte den gangen (19,1 → 3,4 → 16,5 → 5,6), og har aldri før steget
fire bolker på rad. Datagrunnlaget er solid i alle bolker, fra 329 oppsetninger på
femtitallet til 2 949 i 2005–09, så svingningene er ekte og ikke småtallsstøy.

Fordelingen over land er sjekket for begge de to verkene som vokser: «En folkefiende» er
satt opp i 30 land siden 2022, «Et dukkehjem» i 45. Økningen hviler ikke på ett land.

## Begrensninger

**Ingen visning viser landfordelingen.** Påstanden om 30 land og rangeringen Spania / USA /
Tyrkia står bare i teksten. Tallene er verifisert mot analysetabellen i faktasjekken, men
leseren kan ikke etterprøve dem i en graf.

**Vi sier ikke hvorfor.** At de to stykkene som vokser er de mest uttalt politiske, mens
«Peer Gynt» og «Vildanden» faller, er lagt fram uten forklaring. Materialet kan ikke
skille mellom repertoarmoter, rettighetsforhold, enkeltregissørers innflytelse og
tidsånd.

**Andelene er relative.** Når topp tre vokser, må noe annet krympe per definisjon. At
«Fruen fra havet» faller fra 5,0 % til 1,8 % betyr ikke nødvendigvis færre oppsetninger i
absolutte tall — men i dette tilfellet gjør det det også: 209 oppsetninger i 2010–2019 mot
19 i 2022–2025. Periodene er ulikt lange, så det riktige sammenligningsgrunnlaget er
21 oppsetninger i året mot 5.

## Redaktørsjekk

`REDAKTORSJEKK.md` er maskingenerert kritikk fra `anthropic/claude-sonnet-5`. Tre punkter
traff og er rettet:

- «Samme mengde teater» om 389 mot 347 var en overdrivelse — det er 11 % nedgang. Rettet.
- «Det begynte rundt 2010» kan ikke leses ut av femårsbolker som et årstall. Endret til at
  stigningen var i gang i bolken 2010–14.
- «Faller ikke sammen med pandemien» kunne ikke avkreftes med bolkede data. Endret til at
  stigningen var i gang lenge før pandemien, som bolkene faktisk viser.

Kritikken om at siste bolk er kortere enn de andre traff også, og står nå i metodenotatet i
selve historien.
