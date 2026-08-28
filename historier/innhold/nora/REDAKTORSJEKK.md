# Redaktørsjekk: nora

Maskinelt generert av anthropic/claude-sonnet-5, 2026-08-28.

**Dette er råd, ikke fasit.** Punktene under er en modells forsøk på å motsi
historien. Noen treffer, noen bommer. De skal vurderes av et menneske, og
ingenting stoppes eller publiseres automatisk på grunnlag av dem.

---

# Redaktørgjennomgang: «1 937 kvinner, én dør»

## 1. Påstander uten dekning

**Tittelen stemmer ikke med egne tall.** Metadata sier «1941 skuespillere», og metodenotatet sier at to av dem er menn («etterpå står to igjen, og begge er ekte rollebytter»). Det gir 1939 kvinner. Men tittelen sier «1 937 kvinner», og ingressen bygger opp til akkurat dette tallet («1 936 andre kvinner» + Betty Hennings = 1937). Det er et gap på to som ikke er forklart noe sted i teksten. Enten er totalen 1941 feil, kjønnstellingen feil, eller tittelen feil — men alle tre kan ikke være riktige samtidig.

**Eyebrow-tallet «4832 ganger» stemmer ikke med grafen.** Summerer man alle 14 tiårsverdiene i `tiar`-visualiseringen (164+410+489+…+245), får man 4831, ikke 4832. Lite avvik, men det er nøyaktig den typen detalj en leser kan sjekke selv, og som undergraver tilliten hvis det ikke stemmer.

**Den mest konkrete og fargerike påstanden i teksten har ingen visning å vise til.** Setningen om Janet Achurch («tok deretter rollen med seg til Australia, New Zealand, India, Sri Lanka og Egypt — alt sammen i løpet av tre år») og tallet «47 ganger» finnes ikke i noen av de tre visningene. Hero for 1890-tallet viser henne med 39 ganger, ikke 47 — de resterende åtte må stamme fra andre tiår, men det vises ikke. Reisepåstanden er dessuten en helt spesifikk biografisk kjede av premierer i fem land på tre år, og det er ingenting i datasettet (verken kartet, som bare viser første oppsetning per land, eller hero-tabellene) som viser at det var *henne* som sto for disse premierene. Dette er en sterk narrativ påstand bygget på research utenfor det som er dokumentert i visningene.

**Intern uoverensstemmelse i hero-dataene for 1960-tallet undergraver «flest ganger»-tallene.** Monna Tandberg er oppgitt med 69 ganger i rollen, og kortgalleriet bekrefter at alle 69 var i Norge i 1966–1967. Men samme tiårs rad sier at Norge sto for «51 av 168» oppsetninger totalt i hele tiåret. En enkelt skuespiller kan ikke ha 69 norske krediteringer i et tiår der Norge totalt har 51. Samme mønster, svakere, finnes for 1950-tallet: Liv Strømsted har 40 ganger, mens Norge totalt har 37 av 180 den dekaden. Dette er ikke en tolkningssak — det er et regnestykke som ikke går opp, og det bør rettes eller forklares før publisering.

## 2. Manglende normalisering

**Vekstkurven for antall Noraer over tid er ikke kontrollert for arkivets egen vekst.** Påstanden «899 Noraer på 2000-tallet, nesten dobbelt så mange som hundre år før» tolkes som et kulturelt gjenoppblomstring for stykket. Men IbsenStage er et løpende, arkivbasert register («oppdateringsfrekvens: Løpende»), og det er velkjent i digitale kulturarvsdatabaser at nyere tiår er mer fullstendig dokumentert enn eldre — flere land, flere teatre, bedre internettbaserte kilder. Uten et mål på *totalt* antall registrerte oppsetninger av alle Ibsen-stykker (eller alt teater) i databasen per tiår, kan man ikke skille «Nora ble mer populær» fra «arkivet ble mer komplett». Dette er den viktigste manglende normaliseringen i hele historien.

**Landtallene på kartet («antall») er ikke normalisert mot noe.** Norge har 505 krediteringer, Tyskland 689, USA 538 — dette sammenlignes implisitt (gjennom kartet) uten å normalisere for antall teatre, befolkning eller total teatervirksomhet i landet. For historiens hovedpoeng spiller dette mindre rolle siden kartet bare brukes til å vise spredningsår, men «antall»-feltet ligger i dataene og kan lett bli lest som et popularitetsmål land mot land uten at det er gjort sammenlignbart.

**2020-tallet er retorisk, men ikke tallmessig, korrigert for lengde.** Teksten er ærlig om at 2020-tallet er kuttet fra grafen fordi det bare er et halvt tiår («et halvt tiår … ville lest som et fall»). Det er bra og transparent, men selve poenget forsterker første svakhet: hvis man ikke vet hvor mye av forskjellen mellom tiår som skyldes registreringstakt/etterslep i digitalisering, er det heller ikke sikkert at et fullt 2020-tall ville vist et reelt fall i popularitet snarere enn et etterslep i registrering.

## 3. Alternative forklaringer

- **Digitaliserings- og registreringsbias**: Som nevnt i punkt 2 — økt arkivfullstendighet for nyere tiår kan produsere nøyaktig det samme mønsteret (to topper) uten at det reflekterer faktisk oppsetningsfrekvens.
- **Endring i hva som telles som «kreditering»**: Metodenotatet sier krediteringer telles per oppsetning, ikke per forestilling. Men det sier ikke noe om hvorvidt praksisen for å registrere studentoppsetninger, opplesninger, festivalforestillinger eller TV/film-versjoner har endret seg over tid. Hvis nyere tiår i økende grad inkluderer f.eks. skoleteater eller streamede oppsetninger som eldre tiår ikke fikk registrert i sin tid, vil det bidra til stigningen uten at det er en «renessanse» i klassisk forstand.
- **Krigsforklaring på bunnen i 1940-tallet er underforstått, ikke sagt**: Teksten nøyer seg med «nedturen bunner på 1940-tallet med 78» uten å nevne andre verdenskrig som årsak til redusert teatervirksomhet i store deler av Europa. Det er en åpenbar alternativ (eller utfyllende) forklaring som ikke er nevnt, og som gjør at «nedgang i interesse for stykket» er en mindre treffende beskrivelse enn «nedgang i teatervirksomhet generelt».
- **Kartets premiere-år kan reflektere når land ble digitalisert inn i IbsenStage, ikke faktisk premiereår**: Spesielt for land med sen «første Nora» (f.eks. Turkmenistan 2025, Moldova 2025) er det mer sannsynlig at dette er når disse landene fikk sine teaterarkiver katalogisert i IbsenStage, enn at Nora faktisk aldri ble spilt der før.

## 4. Hva ville avkreftet dette

- **Totalt antall registrerte produksjoner i IbsenStage per tiår, for alle Ibsen-stykker (eller helst all verdens teater i databasen)**: Hvis den samme veksttrenden (bunn på 1940-tallet, topp på 2000-tallet) finnes for f.eks. «Gengangere» eller «Peer Gynt» i samme database, er «Nora-renessansen» sannsynligvis et arkiv-artefakt, ikke et reelt kulturelt fenomen. Dette datasettet kan hentes direkte fra IbsenStage (samme kilde, bare uten filter på rollenavn).
- **Registreringsdato (når posten ble lagt inn i databasen) versus premiereår**, hvis IbsenStage har metadata om dette. Dette ville avgjøre om sen-registrerte land/tiår skyldes etterslep i katalogisering.
- **Uavhengig verifikasjon av Janet Achurch-touren** mot ekstern kilde, f.eks. samtidige teateranmeldelser eller en biografi/kildekritisk artikkel om Achurch, siden reisepåstanden ikke kan leses ut av de viste visningene.
- **Rådataene bak «flest ganger»/«flest oppsetninger»-feltene per tiår**, for å avklare Tandberg/Strømsted-uoverensstemmelsen — er det en filtreringsfeil (f.eks. teller «flest ganger» skuespillerens hele karriere, ikke bare tiåret) eller en reell datafeil i landstellingen.
