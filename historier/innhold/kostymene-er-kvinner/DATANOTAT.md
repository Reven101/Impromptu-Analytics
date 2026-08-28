# Datanotat: Kostymene er kvinner, lyset er menn

Publisert 2026-08-28. Kilde: [IbsenStage](https://ibsenstage.hf.uio.no/), Universitetet i Oslo.
Deler grunnlag med [Hundre år til Kina](../hundre-ar-til-kina/DATANOTAT.md), der kildens
egenskaper og hentingen er dokumentert.

## Reproduksjon

```
python pipeline/berik_kjonn.py               # utleder kjønn av fornavn (~$1,09)
python pipeline/rett_kjonn_rollefigur.py     # korrigerer mot rollefigur
python pipeline/bygg_historie_hvem.py
python pipeline/kontrakt.py && python pipeline/bygg_manifest.py
```

## Kjønn er utledet, ikke registrert

Dette er hele historiens forutsetning. IbsenStage fører ikke kjønn. Kolonnen er bygget
i to trinn, dokumentert i [Nora-notatet](../nora/DATANOTAT.md):

1. `gemini-3.1-flash-lite` gjetter ut fra **fornavn og land**. Målt mot Wikidatas `P21`
   for 2 844 regissører: 99,9 % treff blant besvarte, 92 % dekning.
2. Korrigert mot rollefigur der personen har spilt en utvetydig kjønnet rolle.

**Målt feilrate: 1,50 %.** Av 35 098 personer der begge metoder sier noe, er 527 uenige.
6,6 % lar seg ikke bestemme og er holdt utenfor alle andeler.

Feilene er tilnærmet symmetriske — 231 den ene veien, 296 den andre — og de påvirket
aggregatene lite da korreksjonen ble kjørt: kvinneandelen blant skuespillere flyttet seg
fra 43,9 til 44,2 %. Det er grunnen til at vi tør bruke tallene til fordelinger. De ville
ikke holdt for påstander om enkeltpersoner.

## Krediteringer, ikke personer

Vi teller krediteringer. Spørsmålet er hvem som gjør arbeidet, ikke hvem som har gjort det
minst én gang.

Forskjellen er reell og verdt å kjenne: blant skuespillere er kvinneandelen **41,3 % målt
i krediteringer og 44,2 % målt i personer**. Menn har i snitt flere oppsetninger hver.
Samme forhold gjelder de fleste rollene.

## Hvorfor tidsserien starter i 1950

Rollene registreres ulikt ofte, og dekningen har endret seg dramatisk:

| Rolle | 1900-tallet | 1940-tallet | 1980-tallet | 2020-tallet |
|---|---|---|---|---|
| Regissør | 39 % | 81 % | 99 % | 91 % |
| Kostymedesigner | 1 % | 25 % | 60 % | 57 % |
| Komponist | 3 % | 12 % | 24 % | 31 % |
| Oversetter | 26 % | 31 % | 58 % | 19 % |

**At det ikke finnes én eneste kvinnelig regissør på 1880-tallet i dette materialet er ikke
en observasjon om teatret — det er 46 % dekning.** Fra 1950 ligger dekningen for regissør
og skuespiller stabilt på 91–99 %, og først da måler en kurve noe annet enn hvor godt
arkivet fører.

Kostymekurven er tatt med, men skal leses varsomt: dekningen er 54–66 %, og den svinger
tilsvarende (45 % kvinner på 1970-tallet, 80 % på 2000-tallet).

## Tre kontroller redaktørsjekken utløste

**«Å sette opp et Ibsen-stykke krever tjuefem mennesker»** sto i første utkast. Tallet var
funnet på. Fasit: median 12 medvirkende per oppsetning, snitt 13,8 — og 15,7 for
oppsetninger fra 2000. Teksten sier nå «et dusin».

**Skuespillerandelen mot rollegalleriet.** Påstanden om at 41 % er bundet av hvilke roller
Ibsen skrev, var en forklaring uten belegg. Den lot seg teste: blant de 104 572
krediteringene på roller vi kan kjønnsbestemme, er **45,9 % kvinneroller**.
Skuespillerandelen ligger tett under det. Påstanden holder, og står nå med tallet.

**Geografi som sammensetningseffekt.** Hvis landfordelingen har endret seg, kan
regissørkurven være et resultat av at andre land har kommet til. Testet mot de 18 landene
med minst 200 oppsetninger siden 1950: kurven er den samme — 21,0 % på 1950-tallet
(mot 19,8 for alle), 13,9 på 1980-tallet (13,8), 35,0 på 2020-tallet (34,0).

## Begrensninger

**Kjønn er binært her, og det er en forenkling.** Modellen svarer «kvinne», «mann» eller
«vet ikke». Wikidatas `P21` har 16 personer i referansesettet med andre verdier; de er
holdt utenfor. Materialet kan ikke si noe om ikke-binære teaterarbeidere.

**Tverrsnittet er et moderne bilde.** 79 % av kostymekrediteringene, 78 % av
komponistkrediteringene og 87 % av koreografkrediteringene er fra 1980 eller senere.
Rangeringen av de tolv rollene beskriver i praksis de siste førti årene, ikke 176.

**Ingen kontroll for markedsstørrelse eller teatertradisjon.** Om kjønnsbalansen i et yrke
varierer mellom land, og landsammensetningen endrer seg, ville det påvirket tallene. For
regissørkurven er dette testet og avvist. For tverrsnittet er det ikke gjort.

**Vi sier ikke hvorfor.** At kostyme er kvinnedominert og lyd mannsdominert er et mønster
materialet viser, ikke forklarer.
