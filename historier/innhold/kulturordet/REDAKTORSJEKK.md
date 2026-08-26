# Redaktørsjekk: kulturordet

Maskinelt generert av anthropic/claude-sonnet-5, 2026-08-26.

**Dette er råd, ikke fasit.** Punktene under er en modells forsøk på å motsi
historien. Noen treffer, noen bommer. De skal vurderes av et menneske, og
ingenting stoppes eller publiseres automatisk på grunnlag av dem.

---

# Gjennomgang som dataredaktør

## 1. Påstander uten dekning

**"~14× oftere" (hero-boksen)**
Jeg får ikke dette tallet til å stemme uansett hvordan jeg regner på seriene i `aviser`. 1860 = 4,432, 2022 = 50,596 → det gir 11,4×, ikke 14×. Bruker jeg gjennomsnitt for 1860-tallet (≈5,16) mot siste tiår 2013–2022 (≈74,0) får jeg 14,3× — nærmest treff, men da har redaksjonen valgt en spesifikk beregningsmetode (dekadegjennomsnitt) som ikke står i fotnoten. Fotnoten sier bare "enn på 1860-tallet, målt per million avisord", uten å spesifisere hvilke år eller om det er gjennomsnitt, enkeltår eller toppår. Leseren kan ikke etterprøve tallet fra det som står.

**"brukes ordet mange ganger oftere i dag enn den gang" og hele "erobret Norge"-fortellingen**
Dette er den klart største svakheten. Tallene viser en tydelig **nedgang** de siste ti årene som ikke omtales i teksten:
- Aviskurven topper i 2011 med 133,769 og faller til 50,596 i 2022 — en nedgang på 62 % fra toppen.
- Stortingskurven topper i 2020 med 49 saker, og faller til 23 (2022), 26 (2023), 27 (2025) — under nivået fra 2011–2019.

Teksten og tittelen ("erobret Norge", "ordet vant") formidler en entydig vekstfortelling, men det siste tiåret av begge datasettene viser tilbakegang. Dette nevnes ikke i brødteksten og skjules i hero-boksen ved å bruke et forholdstall som ikke viser trendbrudd.

**"Politikken fulgte etter språket" / "Språket gikk foran, politikken kom etter"**
Dette er en kausal og sekvensiell påstand som verken visualiseringene eller metodebeskrivelsen underbygger. Det som vises er to uavhengige tidsserier med grov samvariasjon i noen tiår — ingen lag-analyse, ingen test av om avisveksten faktisk går forut for stortingsveksten. Med de tilgjengelige tallene er "fulgte etter" en tolkning, ikke en observasjon.

## 2. Manglende normalisering

**Stortingsserien er ikke normalisert mot totalt antall saker.** `storting`-visningen viser rene antall kultursaker per sesjon, ikke andel av alle saker. Stortingets totale saksmengde har endret seg over tid (flere spørsmål, interpellasjoner, dokumentsaker registreres i dag enn i 1998). Hvis totaltallet har vokst tilsvarende, kan andelen kultursaker ha vært stabil selv om det absolutte antallet stiger. Dette ville endret hele "politikken fulgte etter"-narrativet.

**Sammenligning av korpus over 160 år uten kontroll for korpussammensetning.** "Per million avisord" korrigerer for lengde, men ikke for hvilke aviser som er digitalisert i ulike perioder. Et konkret varsel: hoppet fra 65,646 (2009) til 118,997 (2010) er nesten en dobling på ett år — det er mer sannsynlig et utslag av at NB har lagt til flere/andre avistitler i korpuset det året enn en reell endring i språkbruk. Dette drøftes ikke.

## 3. Alternative forklaringer

- **OCR-kvalitet og digitaliseringsdekning**: Eldre aviser er vanskeligere å OCR-lese. Lavere gjenkjennelse av "kultur" i 1860–1890-tallet kan i seg selv produsere en stigende kurve uten at reell bruk har endret seg. NB har egne kvalitetsmål for dette som ikke er brukt.
- **Krigsårenes topp (1941–1943: 41–54)**: Teksten forklarer generell vekst med "betydningsutvidelse" og "folkeopplysning, radio, velstand", men nevner ikke okkupasjonstidens propagandaspråk ("kulturkamp", nazistisk kulturretorikk), som er en like plausibel driver av toppen i nettopp disse årene.
- **Semantisk tvetydighet i "kultur" som landbruksterm**: Ordet "kultur" brukes historisk også om jordkultur/kultivering (kulturmark, kulturbeite). I et fortsatt jordbrukstungt Norge på 1800-tallet kan en del av 1860-frekvensen komme fra landbrukskontekst, og nedgangen i denne bruken (i takt med urbanisering) kan maskeres som "vekst i kulturbegrepet" når det egentlig er en forskyvning mellom to helt forskjellige betydninger av samme streng.
- **Endret sakstagging i Stortinget**: Data.stortinget.no sin praksis for emneord/tittelsetting kan ha endret seg over 27 år (bedre metadata, flere emneord per sak i nyere tid), noe som kan gi flere treff uten at politisk oppmerksomhet faktisk har økt.

## 4. Hva ville avkreftet dette

- **NB N-gram med korpusstørrelse per år** (antall digitaliserte sider/titler i avissamlingen for hvert år) — for å sjekke om hoppet i 2010 og andre brå skift korrelerer med utvidet digitaliseringsdekning snarere enn språkbruk.
- **Totalt antall saker i Stortinget per sesjon** fra data.stortinget.no — for å regne kultursaker som andel, ikke absolutt tall, og se om "vekst" overlever normalisering.
- **Sammenligning med kontrollord** i NB Ngram (f.eks. "idrett", "religion", "utdanning") for samme periode — om alle samfunnsord vokser likt i takt med korpusendringer/OCR, er "kultur" ikke spesielt, og hovedpåstanden faller.
