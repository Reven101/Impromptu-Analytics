# Datanotat: Ibsen reiste ikke på norsk

Publisert 2026-08-28. Kilde: [IbsenStage](https://ibsenstage.hf.uio.no/), Universitetet i Oslo.
Deler grunnlag med [Hundre år til Kina](../hundre-ar-til-kina/DATANOTAT.md), der kildens
egenskaper og hentingen er dokumentert.

## Reproduksjon

```
python pipeline/bygg_analysetabell.py
python pipeline/bygg_historie_sprak.py
python pipeline/kontrakt.py && python pipeline/bygg_manifest.py
```

## Hva som telles

Forestillingsspråk er oppgitt på **25 339 av 25 342** oppsetninger — den mest komplette
kolonnen i hele materialet, og registrert av arkivarene ved Senter for Ibsen-studier, ikke
utledet av oss. 82 ulike språk.

Oppsetninger med flere språk teller for hvert av dem (kilden skriver «English , French»),
så andelene summerer til over 100 prosent. 20 av oppsetningene har mer enn ett språk.

Andelene er av oppsetninger, ikke av forestillinger. Tiår med under 40 registrerte
oppsetninger er utelatt fra kurvene, og 2020-tallet er ufullstendig.

## Det bærende grepet

Et språk kan være mye brukt av to grunner: fordi landet det snakkes i spiller mye Ibsen,
eller fordi *andre* land bruker det. Bare det siste er en observasjon om språket.

Historien er derfor bygget på et par av kurver — språkets andel mot landets andel — og
ikke på språkkurven alene:

| Tiår | Norsk språk | Norge som land | Tysk språk | Tyskland som land |
|---|---|---|---|---|
| 1910 | 2,9 % | 2,7 % | 45,0 % | 33,2 % |
| 1950 | 34,1 % | 32,4 % | 11,6 % | 7,6 % |
| 1990 | 33,9 % | 34,2 % | 13,6 % | — |
| 2010 | 17,1 % | 17,5 % | 17,2 % | 12,3 % |

Norsk følger Norge i hvert eneste tiår. Tysk ligger over Tyskland i hvert eneste tiår.
Samlet over hele perioden: **11 prosent av de norskspråklige oppsetningene er utenfor
Norge, mot 30 prosent av de tyskspråklige utenfor Tyskland.**

## Feilen redaktørsjekken fant

Første utkast skrev at tysk fortsatt gjør denne jobben, med «187 tyskspråklige oppsetninger
utenfor Tyskland på 1910-tallet, 211 på 2010-tallet». Tallene stemmer, men sammenligningen
gjør det ikke: **verden spiller 2,6 ganger så mye Ibsen nå.** Normalisert er andelen falt
fra 11,9 til 5,2 prosent — tysk har mer enn halvert sin rolle som transportspråk, ikke
holdt den.

To andre punkter fra samme sjekk er også rettet:

- «Språket krysser ikke grensen» om norsk var for absolutt. Det gjør det, i 531 tilfeller
  (11 %), de fleste i Danmark. Poenget er at det er unntaket, ikke at det ikke skjer.
- Påstanden om at «Østerrike, Sveits, Tsjekkia, Polen og Romania» sto for tyskspråklig
  Ibsen utenfor Tyskland var skrevet uten å telle. Tellingen gir Østerrike 512, Sveits 446,
  Tsjekkia 114 — men USA (76) og Frankrike (54) kommer før Polen (79 er nær) og Romania
  (44). Teksten navngir nå de tre største og nevner USA og Frankrike.

## Begrensninger

**Den viktigste skjevheten er at IbsenStage drives fra Oslo.** Norske oppsetninger er
trolig mer komplett registrert enn andre lands. Det trekker i én retning: den norske
andelen er for høy og den tyske for lav, og hovedfunnet — at tysk reiser og norsk ikke —
er dermed sannsynligvis undervurdert, ikke overdrevet.

**Kontrollen mot land er robust mot nettopp den skjevheten**, fordi den sammenligner to
tall fra samme kilde med samme dekning. Er norske oppsetninger overrepresentert, er både
«norsk språk» og «Norge som land» overrepresentert like mye, og forholdet mellom dem står.

**Markedsstørrelse er ikke kontrollert for.** De tyskspråklige landene har til sammen et
langt større teatermarked enn Norge. At tysk når flere land kan delvis være størrelse og
ikke bare språkets rolle som transportmiddel. Vi har ikke data til å skille de to.

**Tiårene før 1890 hviler på få oppsetninger** — 223 på 1870-tallet mot 4 071 på
2010-tallet. Prosentene der er ustabile, og 1870-tallets 34,1 prosent tysk skal leses med
det for øye.

## Status

Historien er ferdig og faktasjekket, men merket `utkast` fordi forsiden allerede har to
Ibsen-saker. Fjern flagget i `pipeline/bygg_historie_sprak.py` og kjør
`bygg_manifest.py` for å publisere den.
