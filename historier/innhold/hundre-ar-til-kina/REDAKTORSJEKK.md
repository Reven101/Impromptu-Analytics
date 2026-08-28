# Redaktørsjekk: hundre-ar-til-kina

Maskinelt generert av anthropic/claude-sonnet-5, 2026-08-28.

**Dette er råd, ikke fasit.** Punktene under er en modells forsøk på å motsi
historien. Noen treffer, noen bommer. De skal vurderes av et menneske, og
ingenting stoppes eller publiseres automatisk på grunnlag av dem.

---

# Redaktørgjennomgang: «Hundre år til Kina»

## 1. Påstander uten dekning

**«Norden spilte Ibsen året han utga — resten av verden brukte i median 114 år på det samme»** (metadata-beskrivelsen, gjentatt implisitt i ingressen).

Dette stemmer ikke helt med tallene. Brødteksten sier riktig at *«Målt over de 112 landene som har spilt ham, er medianen 114 år»* — men de 112 landene inkluderer Norge, Sverige, Danmark og Finland (verdi = 1). Jeg har sortert de 112 verdiene i kartdatasettet: medianen på 114 kommer fra posisjon 56–57, som ligger et godt stykke fra de fire nordiske landene i den lave enden. Men hvis man faktisk trekker Norden ut og bare måler «resten av verden» (108 land), flytter medianposisjonen seg til verdien 116, ikke 114. Metadata-formuleringen «resten av verden brukte i median 114» er altså en liten, men reell regnefeil — riktig tall der er 116, ikke 114. 114 er medianen for *alle* 112 land inkludert Norden.

**Mindre, men verdt å nevne:** metadata sier geografien er «115 land», mens jeg teller 112 unike landkoder i kartdatasettet, og brødteksten selv bruker 112. Ett av tallene er feil.

**«Ibsen ga ut tolv skuespill mellom 1877 og 1899»** — dette stemmer med de 12 årstallene i ventetids-serien fra 1877–1899, men det underslår at samme visualisering (ventetid, kortgalleri) også bruker fire tidligere verk (1862, 1866, 1867, 1869) i beregningen av «de 27 landene». Leseren får ikke vite at «bruddet i 1877» dermed sammenligner 12 sene verk mot bare 4 tidlige — et spinkelt datagrunnlag for en så bastant konklusjon («berømmelsen kom først»). Hero-fotnoten nevner i tillegg 28 av 30 verk med kjent utgivelsesår, uten at forholdet mellom «12», «16» (i ventetidsgrafen) og «30» (i hero) noen gang forklares.

## 2. Manglende normalisering

Kartet fargelegger 112 land etter median ventetid, men medianen er beregnet over svært ulikt antall verk per land — fra Norges ~28-30 til land som bare har satt opp ett eller to. Dette er delvis erkjent i metodenotatet («Qatar havner på 147 år, men det betyr «ett stykke kom nylig»»), men erkjennelsen gjelder bare Qatar som eksempel. Kartet selv viser ingen indikasjon (f.eks. skravur, størrelse, eller n-verdi) på hvor mange verk medianen bygger på for de øvrige 111 landene. Uten det kan leseren ikke vite om f.eks. Kinas 116 år er en robust median over mange oppsetninger, eller et artefakt av 1-2 registrerte verk — noe som er avgjørende når hovedpåstanden bygger på nettopp Kinas tall.

«Utbredelse»-grafen (antall land kumulativt) normaliserer heller ikke for at antall *eksisterende, uavhengige stater* har økt dramatisk i perioden 1850–2025 (avkolonisering etter 1945, oppløsningen av Sovjetunionen og Jugoslavia etter 1990 — flere av landkodene i datasettet, som XK, ME, BA, er stater som ikke eksisterte som selvstendige rapporteringsenheter før 1990-tallet). Deler av «rykkene» i kurven kan dermed rett og slett skyldes at flere land å telle har kommet til, ikke at Ibsen har spredt seg raskere.

## 3. Alternative forklaringer

- **Arkivets egen vekst, ikke Ibsens spredning:** Kurven i «utbredelse» tar av etter 2000 (75 land i 2000 → 115 i 2025). Dette sammenfaller med perioden hvor digitalisering av teaterarkiver typisk har skutt fart. Teksten tolker dette som at «berømmelsen» drev spredningen, men det kan like gjerne være at IbsenStage har fått bedre/nyere datakilder å registrere fra i denne perioden — ikke at flere land faktisk begynte å spille Ibsen først da.
- **Antall stater i verden har økt** (se punkt 2) — en ren tellemessig effekt, ikke en kulturell.
- **Dramaturgisk vanskelighetsgrad, ikke berømmelse:** Peer Gynt (1867) og Brand (1866) er versdramaer skrevet som lesedrama, lenge ansett som praktisk uspillelige på grunn av lengde og form. At de brukte 44–46 år kan skyldes at de er tekniske utfordringer å sette opp, ikke at «ingen kjente Ibsen» før 1877. Artikkelens «berømmelse kom først»-narrativ utelukker ikke denne forklaringen, men diskuterer den heller ikke.
- **Politiske/historiske hindringer for Kina, Sør-Korea, Bangladesh:** lang ventetid i disse landene kan skyldes kulturpolitiske sperrer (f.eks. Kina under Mao) eller mangel på oversettelser, ikke bare arkivets registreringssvakhet som er den eneste forklaringen som nevnes.

## 4. Hva ville avkreftet dette

- **En uavhengig teaterdatabase for de aktuelle landene** (f.eks. nasjonale teaterarkiver i Kina, Sør-Korea, India, eller akademisk litteratur om Ibsen-mottakelse i Asia) for å sjekke om «første kjente oppsetning»-datoene i IbsenStage faktisk er de tidligste, eller bare de tidligste IbsenStage har registrert.
- **Antall uavhengige stater i verden per år 1850–2025** (f.eks. fra Correlates of War state-system membership-datasettet eller FNs medlemslister) sammenholdt med «utbredelse»-kurven, for å teste hvor mye av veksten som er en ren tellemessig effekt av flere stater.
- **IbsenStage sine egne metadata om når poster ble lagt inn i databasen** (registreringsdato, ikke fremføringsdato) — hvis tilgjengelig, ville dette vise om «hoppet» etter 2000 skyldes digitaliseringsarbeid snarere enn faktisk spredning.
- **Antall verk (n) bak hver landmedian** i kartdatasettet — dette datasettet finnes trolig allerede hos IbsenStage og bør publiseres sammen med kartet for å vise hvor mange av de 112 landmedianene som bygger på færre enn f.eks. 5 verk.
