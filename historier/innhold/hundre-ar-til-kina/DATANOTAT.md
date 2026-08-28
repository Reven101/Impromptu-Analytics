# Datanotat: Hundre år til Kina

Publisert 2026-08-28. Kilde: [IbsenStage](https://ibsenstage.hf.uio.no/), Universitetet i Oslo,
hentet 27.–28. august 2026.

## Reproduksjon

```
python pipeline/hent_ibsenstage.py            # browse-tabellen, ~26 kall
python pipeline/hent_ibsenstage_detaljer.py   # 25 342 detaljsider, ~1,5 t
python pipeline/berik_verk.py                 # utgivelsesår fra Wikidata
python pipeline/berik_geodata.py              # koordinater og ISO-koder
python pipeline/berik_vdem.py                 # ikke brukt i denne historien
python pipeline/bygg_analysetabell.py
python pipeline/bygg_historie_spredningen.py
python pipeline/kontrakt.py && python pipeline/bygg_manifest.py
```

Rådata ligger i `impromptu_raadata/ibsenstage/` (665 MB), utenfor repoet. Rå HTML er
gzippet og mellomlagret, så parseren kan kjøres på nytt uten et eneste nettverkskall.

## Kilden

25 343 oppsetninger, 1850–2026, 115 land, 82 språk, 349 041 krediteringer på 96 415
personer. Basen har verken API eller eksport, bare en paginert HTML-tabell.

To ting gjorde hentingen mulig, og begge er verdt å kjenne:

- **`per_page` er en fri URL-parameter.** Standardvisningen er 100 per side (245 sider);
  1000 fungerer, 2500 gir HTTP 500. Hele basen ble hentet i 26 kall i stedet for 260.
- **Kilden oppgir sin egen fasit.** Hver kategoriside skriver «Count 24489» i overskriften.
  Scriptet krever at `parsede rader + talte hull == fasit` og stopper ellers.

**Åtte rader i basen gir HTTP 500 uansett sidestørrelse** — også i nettstedets egen
visning på 100 per side. De er ikke med. Én detaljside (`87506`) likeså. Til sammen ni
av 25 343, altså 0,04 %.

## Hva tallet på kartet er

Median antall år fra et Ibsen-verk ble utgitt til det ble spilt første gang i landet,
regnet over de verkene landet har satt opp.

- **Medianen er tatt over verk, ikke over oppsetninger.** Et land som spiller «Et
  dukkehjem» femti ganger ville ellers telt femti ganger.
- **Aggregeringen skjer på ISO-kode, ikke på landnavn.** England, Skottland, Wales og
  Nord-Irland deler koden GB. Grupperte man på navn og slo sammen etterpå, ville den ene
  overskrevet den andre — Englands 18 år ville blitt Wales' 120, avhengig av rekkefølgen
  i en dict. Kartet ville rendret pent og vist feil århundre. Derfor er 115 land i
  datasettet 112 flater på kartet.
- **Ventetidskurven måler mot en fast gruppe på 27 land** som har satt opp minst 15 av
  verkene. Uten den avgrensningen måler man noe annet enn man tror: se under.

## Feilen som formet historien

Det opprinnelige grepet var et kortgalleri som rangerte verkene etter «reisehastighet».
Det viste seg å være utgivelsesår i forkledning.

Korrelasjonen mellom et verks utgivelsesår og medianen for hvor lenge det ventet er
**r = −0,60** målt mot alle land. Mekanismen er triviell: et verk fra 1867 har hatt
hundre år ekstra på seg til å nå land som først fikk Ibsen i 1990, og de ventetidene
drar medianen opp.

Måler man i stedet mot de 27 kjernelandene, blir korrelasjonen **−0,88** — og da er det
som står igjen ikke en egenskap ved stykkene i det hele tatt. Det er Ibsens egen
berømmelse. «Peer Gynt» ventet 46 år på de samme landene som tok imot «Når vi døde
vågner» på ett.

Rangeringen ble derfor erstattet av ventetidskurven, som viser mekanismen i stedet for å
skjule den.

## Bugs som ble funnet, og hva de ville gjort

**Rosmersholm sto som utgitt i 1867.** Den er fra 1886. `verk_utgitt` i analysetabellen er
det *eldste* verket i oppsetningen — riktig for en rad per oppsetning, galt å bruke per
verk. I en kompilasjon med «Peer Gynt» arvet Rosmersholm 1867, og feilen la nitten år til
hvert eneste land som først så stykket i en slik kveld. Nå hentes årstall per verk fra
`ibsenstage_verk.json`. Feilen var stille: tallet så rimelig ut.

**Kartets fargeskala var lineær i første utgave.** Med spennet 1–147 år og median 114 la
den 25 land i det laveste trinnet: Norge (1 år) og Russland (16 år) fikk samme farge, og
hele Europa ble én flate. Skalaen er nå logaritmisk, som er riktig for en varighet over
to størrelsesordener — de fire nordiske landene står nå alene i lyseste trinn.

**«Ukjent visningstype: verdenskart».** Kontrakten fikk `verdenskart` inn i
`GYLDIGE_VISNINGSTYPER`, men `REGISTER` i `komponenter.js` fikk det ikke, fordi en
tekstutskifting lette etter en énlinjeversjon som ikke fantes og ikke sa fra. Resultatet
var det verst tenkelige mellomstadiet: validatoren godtok typen, motoren kunne ikke
rendre den. Historien validerte grønt og viste en rød boks.

## Wikidata som kilde til utgivelsesår

Verkstitlene er koblet til Wikidata **for hånd** — ett Q-nummer per verk, valgt ut fra de
192 treffene på «verk av Henrik Ibsen», som omfatter oversettelser, enkeltutgaver og
sceneadapsjoner om hverandre. Årstallene hentes så fra Wikidatas `P577`. Da hviler ikke
tallene på hukommelse, og lista kan etterprøves rad for rad i `pipeline/berik_verk.py`.

28 av 30 verk har utgivelsesår. De to som mangler får `null` framfor et gjettet årstall:
«Mountain Bird» (Fjeldfuglen) er en ufullført libretto, og «Svanhild» er et utkast som ble
til «Kjærlighedens komedie».

Merk at `P577` er *utgivelsesår*, ikke skriveår. For «Lady Inger» skiller de tre år:
skrevet 1854, urframført 1855, utgitt 1857. Én oppsetning i materialet har negativ verdi
— «Fru Inger til Østeraad» spilt i 1855, to år før utgivelsen. Det er ikke en feil.

## Begrensninger

**Den viktigste er at dette er første *registrerte* oppsetning.** IbsenStage er drevet fra
Oslo, og dekningen av tidlig ikke-europeisk teater er svakere enn av europeisk. Skjevheten
peker én vei: ankomsten ser senere ut enn den var. Tallene for Asia og Afrika er derfor et
tak, ikke et anslag.

**Kartet viser ikke hvor mange verk hver median hviler på.** Alle flater ser like sikre ut.
Norge har 28 verk bak sitt tall, 24 land har bare ett. Tabellen under kartet har kolonnen
«Verk satt opp» nettopp derfor.

**Kurven over antall land er ikke normalisert for at det er blitt flere land.**
Avkolonisering etter 1945 og oppløsningen av Sovjetunionen og Jugoslavia etter 1990 skapte
stater som ikke fantes før. En del av veksten er at det er flere enheter å telle.

**Koroplettkart vekter etter areal.** Derfor brukes det bare til tidspunkt, aldri til
volum: Norge har 4 743 oppsetninger og er en flekk, Russland har 263 og er en flate.

## Det som ble testet og forkastet

**Sensurhypotesen holder ikke.** Vi koblet hver oppsetning til V-Dems indikatorer for
statlig sensur og kunstnerisk ytringsfrihet (`berik_vdem.py`, 95,9 % dekning) for å teste
om «Gengangere» — Ibsens skandalestykke — systematisk spilles under mindre frihet.

Rå forskjell i kunstnerisk ytringsfrihet mellom «Gengangere» og de øvrige verkene:
**−0,39**. Kontrollert innenfor tiår: **−0,04**.

Hele den rå forskjellen var en tidseffekt. «Gengangere» ble spilt tidlig og mye, og verden
var mindre fri da. Hypotesen er avkreftet av våre egne data, og er ikke skrevet om til en
historie som «nyanserer».

V-Dem-koblingen har for øvrig et hull som er verdt å kjenne: Polen, Tsjekkia, Latvia og
Ukraina før 1918 får `null`, fordi statene ikke fantes. Det er riktig — men det betyr at
sensuranalyse i Sentral-Europa før første verdenskrig mangler nettopp de landene der
spørsmålet er mest interessant.

## Redaktørsjekk

`REDAKTORSJEKK.md` i samme mappe er maskingenerert kritikk fra `anthropic/claude-sonnet-5`.
Fire av punktene traff og er rettet i teksten:

- Beskrivelsen sa «resten av verden brukte i median 114 år». 114 er medianen for *alle*
  112 land inkludert Norden; uten Norden er den 116. Rettet.
- Forholdet mellom 115 land i metadata og 112 på kartet var uforklart. Nå forklart.
- Kurven over antall land manglet forbeholdet om at det er blitt flere stater. Lagt til.
- Kartet manglet en indikasjon på hvor mange verk hver median bygger på. Tabellen fikk
  kolonnen «Verk satt opp».
