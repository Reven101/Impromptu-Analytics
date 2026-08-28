# Redaktørsjekk: kostymene-er-kvinner

Maskinelt generert av anthropic/claude-sonnet-5, 2026-08-28.

**Dette er råd, ikke fasit.** Punktene under er en modells forsøk på å motsi
historien. Noen treffer, noen bommer. De skal vurderes av et menneske, og
ingenting stoppes eller publiseres automatisk på grunnlag av dem.

---

# Gjennomgang som dataredaktør

## 1. Påstander uten dekning

**"Å sette opp et Ibsen-stykke krever tjuefem mennesker."** Dette tallet finnes ikke i noen av visningene. Det er tolv roller i datamaterialet, ikke 25 personer per oppsetning — tallet er ikke utledbart fra "roller"-grafen eller hero. Enten stryk det, eller vis regnestykket (snitt antall krediteringer per oppsetning) i en fotnote.

**"det er ikke et arbeidsmarked, det er Ibsens rollegalleri. Han skrev de rollene han skrev, og teatrene besetter dem."** Dette er en kausal forklaring på skuespiller-tallet (41 %) som ikke er testet mot data. Metadata sier kilden er IbsenStage — men er dette *bare* Ibsen-oppsetninger, eller registrerer basen også andre stykker/forfattere spilt ved samme teatre? Hvis det siste, faller premisset for forklaringen bort. Teksten sjekker ikke dette, den påstår det.

**Metabeskrivelsen sier regissørandelen "har doblet seg siden 1980"**, mens hero viser 14 % (1980-tallet) → 21 % (hele perioden, altså inkludert alle tiår til og med i dag) — det er en faktor på 1,5, ikke en dobling. Tidslinjen viser derimot 13,8 % (1980) → 34 % (2020), en faktor på 2,46. To ulike tall brukes til å underbygge samme påstand, og det ene (hero: 21 %) er faktisk et gjennomsnitt over hele perioden, ikke et "nå"-tall. Dette bør rettes til konsistente størrelser.

**"Regissøren — den som bestemmer — ligger på 21 prosent."** En rolletolkning presentert som fakta. Ikke noe i datamaterialet viser maktforhold, bare krediteringsandeler.

## 2. Manglende normalisering

**Dekningsgrad varierer sterkt mellom roller og perioder, men brukes ikke til å justere selve prosenttallene.** Teksten nevner selv at kostymedesigner bare er ført på 54–66 % av oppsetningene mot regissørens 91–99 %, og at regissør har 39 % dekning "på 1900-tallet" mot 95–99 % etter 1950. Dette er korrekt påpekt som en svakhet ved kostymekurven, men samme forbehold tas ikke for skuespiller-kurven, som sammenlignes direkte med regissør-kurven i avsnittet ("Skuespillerne, til sammenligning..."). Hvis skuespillerdekningen også varierer over tid, er sammenligningen mellom kurvene ikke rettferdig.

**Ingen normalisering for geografi.** Geografifeltet sier "115 land", men det er ingen kontroll for at datasettet kan domineres av noen få lands teatertradisjoner (typisk skandinaviske, tyske, engelske). Hvis kjønnsbalansen i yrker varierer sterkt mellom land, og landfordelingen har endret seg over tid, kan det forklare deler av tidslinjekurvene uten at det sier noe om et generelt "teater"-mønster.

**Krediteringer, ikke produksjoner eller årsvekst.** Antall krediteringer per tiår er ikke vist. Metodenotatet nevner at 79 % av kostymekrediteringene er fra 1980 eller senere, men det samme forholdet er ikke vist for de andre elleve rollene i "roller"-visningen, der totaltallene (f.eks. 349 041 krediteringer) fremstår som jevnt fordelt over "hele perioden fra 1850".

## 3. Alternative forklaringer

- **Endret registreringspraksis, ikke endret kjønnsbalanse.** Dekningen for regissør går fra 39 % til 95–99 % rundt 1950. Det er fullt mulig at det er de *store, kjente* produksjonene som ble registrert i tidlig periode, og at disse hadde en annen kjønnssammensetning enn de små/oversette produksjonene. Da er ikke stigningen i kvinnelige regissører nødvendigvis reell — den kan delvis skyldes hvilke oppsetninger som kom inn i registeret.
- **Systematisk bias i navnebasert kjønnsgjetting.** Feilraten på 1,50 % er *uenighet mellom to metoder*, ikke en uavhengig validert feilrate. Hvis begge metoder (LLM og rollefigur-korrigering) deler samme svakhet — f.eks. med kjønnsneutrale eller ikke-vestlige navn — kan den reelle feilraten være høyere, og skjevheten kan variere systematisk mellom roller eller land (visse nasjonaliteter kan være overrepresentert i visse yrker, f.eks. komponister/lysdesignere fra land med andre navnekonvensjoner).
- **Usynliggjøring i krediteringspraksis over tid.** At kvinner "ikke gjorde arbeidet" og at "kvinner ikke ble kreditert" er to ulike forklaringer på lave historiske andeler, og teksten velger implisitt den første uten å diskutere den andre.

## 4. Hva ville avkreftet dette

- **IbsenStage sin egen metadata om dekningsgrad per rolle og år** (om denne finnes separat fra selve krediteringstabellen) — for å skille "endret kjønnsbalanse" fra "endret registreringspraksis".
- **Et uavhengig, manuelt kodet valideringssample** (f.eks. 500 tilfeldig trukne personer, kodet av mennesker) for å få en ekte feilrate på kjønnsgjetting, i stedet for uenighet mellom to korrelerte metoder.
- **Statistikk fra en fagforening/register med faktisk registrert kjønn**, f.eks. Norsk Skuespillerforbund eller tyske/britiske teaterforbund sine medlemsstatistikker fordelt på kjønn og yrke over tid, som kunne krysskontrollere om trendene i IbsenStage-materialet samsvarer med bransjedata der kjønn ikke er utledet.
- **Fordeling av krediteringer per land og år**, for å sjekke om tidslinjetrendene (særlig regissør-oppgangen fra 1990) sammenfaller med at flere land/teatre kom inn i registeret, snarere enn med en reell endring i hvem som ble ansatt.
