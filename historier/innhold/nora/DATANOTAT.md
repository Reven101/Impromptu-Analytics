# Datanotat: 1 937 kvinner, én dør

Publisert 2026-08-28. Kilde: [IbsenStage](https://ibsenstage.hf.uio.no/), Universitetet i Oslo,
hentet 27.–28. august 2026. Deler grunnlag med [Hundre år til Kina](../hundre-ar-til-kina/DATANOTAT.md),
der kildens egenskaper og hentingen er dokumentert.

## Reproduksjon

```
python pipeline/berik_kjonn.py               # utleder kjønn av fornavn (~$1,09)
python pipeline/rett_kjonn_rollefigur.py     # korrigerer mot rollefigur
python pipeline/bygg_analysetabell.py
python pipeline/bygg_historie_nora.py
python pipeline/kontrakt.py && python pipeline/bygg_manifest.py
```

## Hva som telles

**Krediteringer, ikke forestillinger.** En skuespiller som spilte Nora hundre kvelder i
samme oppsetning teller én gang. Tallet 4 832 er altså «hvor mange ganger noen er ført
opp i rollen», ikke «hvor mange ganger rollen er spilt».

**Rollefiguren er ført konsekvent.** Vi telte med en streng match på «Nora», i tilfelle
kilden også brukte varianter som «Nora Helmer». Det gjør den ikke: samtlige 4 832
krediteringer står som nøyaktig «Nora». Det er uvanlig ryddig for et felt med 425 ulike
verdier, og betyr at tallet ikke er et utvalg.

Rollefigurfeltet er ført av arkivarene ved Senter for Ibsen-studier, ikke utledet av oss.
187 064 av 349 041 krediteringer har det — altså 54 %. Oppsetninger uten rollefigur er
usynlige i denne historien, og det er ikke tilfeldig hvilke: eldre og mindre omtalte
oppsetninger har oftere tom rollebesetning.

## Kjønnet er utledet, og deretter korrigert

IbsenStage registrerer ikke kjønn. Kolonnen er bygget i to trinn:

1. `berik_kjonn.py` spør `gemini-3.1-flash-lite` om sannsynlig kjønn ut fra **fornavn og
   land**. Målt mot Wikidatas `P21` for 2 844 regissører: 99,9 % treff blant besvarte,
   92 % dekning, og en skjevhet på −0,2 prosentpoeng i kvinneandelen.
2. `rett_kjonn_rollefigur.py` korrigerer mot rollefigur. En håndskrevet liste over 55
   utvetydige roller (Nora, Hedda, Fru Alving → kvinne; Torvald, Peer Gynt, Dr. Rank →
   mann) gir en uavhengig kilde til det samme.

**Korreksjonen ga et tall vi ikke hadde: navnemetoden bommer på 1,50 %.** Av 35 098
personer der begge kilder sier noe, er 527 uenige — 231 der navnet sa mann og rollen sier
kvinne, 296 motsatt. Det er femten ganger verre enn de 0,1 % vi målte mot Wikidata, og
forskjellen er lærerik: Wikidata-fasiten var regissører som er kjent nok til å ha en
oppføring, altså mer vestlige og mer konvensjonelt navngitte enn skuespillerpopulasjonen
i 116 land.

3 919 personer ble rettet (527 uenigheter, resten hadde «vet ikke» og fikk et kjønn fra
rollen). «Vet ikke» falt fra 10,1 % til 6,6 %. Aggregatene rikket seg knapt — kvinneandel
blant skuespillere gikk fra 43,9 til 44,2 % — fordi feilene var symmetriske og kansellerte
hverandre. **De betydde mye for enkeltpersoner og lite for fordelingene.**

Hver person har `kjonn_kilde`: `navn` (92 496) eller `rollefigur` (3 919).

## Tore Segelcke, og de to som ble stående

Før korreksjonen sto **59 Nora-spillere som menn**. Den mest iøynefallende var Tore
Segelcke, en av Norges mest kjente Nora-skuespillerinner — «Tore» er normalt et mannsnavn
på norsk, og modellen svarte deretter.

Etterpå står to igjen, og de er **ikke feil**:

- **Andrus Vaarik**, Estland 1995 — spilte også Osvald Alving
- **Burton W. James**, USA 1932 — spilte også Peer Gynt og Hjalmar Ekdal

Begge spiller roller av begge kjønn, og korreksjonen er skrevet slik at den da **ikke**
overstyrer noe. 261 personer i materialet er i samme situasjon. Kryssrollebesetning er
ekte teater, ikke registreringsfeil, og en regel som «rettet» dem ville skjult noe ekte.

## Kartet og grafen

**Kartet viser årstall, ikke antall.** Samme regel som i spredningshistorien: et
koroplettkart vekter etter areal, så «hvor mange Noraer» ville gjort Russland til
hovedpersonen. «Året Nora først gikk ut» er et tidspunkt, der arealet ikke lyver. Antall
krediteringer per land står i tabellen under kartet.

Skalaen er kvantil og ikke logaritmisk her, fordi verdiene er årstall i et smalt spenn
(1879–2020) der forholdstall er meningsløse.

**Søylegrafen stopper ved 2010-tallet.** Vi er i 2026, så 2020-tallet er ikke halvveis
ferdig, og en kort søyle ved siden av fulle tiår leser som et fall som ikke finnes. Samme
grep som i `bygda-savner-barn`, av samme grunn. Så langt teller 2020-tallet 245 Noraer.

## Janet Achurch

47 krediteringer mellom 1889 og 1904, i åtte land: England, Skottland, Australia,
New Zealand, India, Sri Lanka, Egypt og USA. Turneen 1889–1892 alene dekker seks av dem.

Merk at antallet krediteringer ikke er antall kvelder — det er antall oppsetninger hun er
ført opp i. En turné med tjue spillesteder kan stå som tjue oppsetninger eller som én,
avhengig av hvordan arkivaren har registrert den. Det gjør henne til den mest markante
enkeltpersonen i materialet, men tallet 47 skal ikke leses som «47 forestillinger».

## Begrensninger

**Fordelingen er ekstrem, og det er delvis et registreringsfenomen.** 73 % av de 1 941
skuespillerne er ført opp én gang. Noe av det er ekte — de fleste spiller en rolle i én
produksjon — men en skuespiller i en oppsetning som gikk i to år står også bare én gang.

**«Første registrerte» gjelder også her.** Kartets årstall er første oppsetning arkivet
kjenner til, ikke første oppsetning. For ikke-europeisk teater før 1950 er dekningen
svakere, så ankomsten kan se senere ut enn den var.

**Kjønnet er utledet.** Ingen av tallene om kvinner i denne historien er registrerte
opplysninger. De hviler på en språkmodell med målt feilrate på 1,50 %, korrigert der
rollefiguren sier noe annet. For selve Nora-rollen er korreksjonen sterk — er du kreditert
som Nora, er du nesten sikkert kvinne — men det gjelder ikke aggregater om andre roller.
