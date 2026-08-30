[[viz:hero]]

Hver uke legges det ut nye evalueringer av norsk forvaltning. Noen er bestilt av et departement som vil vite om en reform virket, noen av et direktorat som må dokumentere at et tilskudd traff, noen av et tilsyn som har gått gjennom sin egen praksis. De havner i Kudos, DFØs register over kunnskapsdokumenter i offentlig sektor, og der ligger de.

Det finnes ingen publisert oversikt over hvor mange de er blitt, hvem som bestiller dem, eller hva som skjer med dem etterpå. Denne artikkelen er et forsøk på å telle.

## Kunnskap i industriell skala

[[viz:tempo]]

Kurven skal leses med ett forbehold, og det er historiens viktigste: **den måler også registreringspraksis.** Kudos er bygget opp i etterkant, sammen med Nasjonalbiblioteket, og et dokument fra 2005 må være funnet og lagt inn av noen for å telle med her. At det ligger flere evalueringer fra de siste årene enn fra tidlig 2000-tall er delvis at det ble laget flere — og delvis at de nyere er registrert. Hvor mye som er hva, kan vi ikke skille ut. Nivået de siste ti årene er derfor et mer robust tall enn stigningen dit.

[[viz:bestillerne]]

Toppen av lista er robust; halen er det ikke. Kudos identifiserer oppdragsgiveren med et virksomhetsnavn, og en virksomhet som har vært gjennom en omorganisering står under flere navn. Det trekker de store nedover, ikke oppover — så konsentrasjonen i toppen er om noe undervurdert.

[[viz:temaene]]

Klassifiseringen er gjort av en språkmodell som velger blant seksten håndskrevne politikkområder. Den finner ikke på kategorier: gjør den det, stopper scriptet. Modellen ser tittelen og de første 600 tegnene av sammendraget, og svarene er sjekket inn, så det er etterprøvbart hvilken modell som sa hva.

Lista er skrevet etter departementsstrukturen, ikke etter hva som ligger i dataene — en kategori ingen evaluering havner i, er en opplysning om forvaltningen og ikke en feil i lista. Og en slik kategori finnes: **forsvarssektoren er så godt som fraværende.** Det betyr ikke at Forsvaret ikke evalueres. Det betyr at evalueringene ikke ligger her.

Kategoriene ble justert én gang underveis, og det er verdt å si hvorfor. Vi kjørte to uavhengige modeller over de samme 200 tekstene og så på hvor de var uenige. Uenighetene var ikke tilfeldig spredt — de klumpet seg rundt barnevern og familie, som ikke hadde noe hjem i lista og derfor ble presset inn i «arbeid og velferd» eller «kommunal og distrikt» alt etter hvilken modell som svarte. Andelen «annet» var hele tiden lav, så feilen var usynlig i det målet vi vanligvis stoler på. Kategorien ble lagt til, og hele korpuset klassifisert på nytt.

## Gapet

Så: hva skjer med dem?

Det spørsmålet har ingen god operasjonalisering. En evaluering kan bli lest av en saksbehandler som skriver et notat som påvirker en proposisjon, uten at det finnes et spor noe sted. Vi har derfor valgt det eneste sporet som er etterprøvbart: at rapporten **navngis ordrett** i et stortingsdokument — en innstilling, et representantforslag, et referat.

[[viz:trakten]]

Tre ting om dette tallet, og de gjelder hver gang det nevnes:

**Det er en nedre grense.** En evaluering kan bli lest, brukt og fulgt opp uten å bli navngitt. Vi teller det vi kan se, og det er mindre enn det som skjer.

**De fleste evalueringer er aldri ment å nå Stortinget.** Et direktorat som evaluerer sitt eget prosjekt skal ikke dit. At andelen er lav er derfor ikke i seg selv en skandale — det er fordelingen som er interessant, ikke gjennomsnittet.

**Nevneren er ikke hele korpuset.** Vi har fulltekst for de nyeste stortingssesjonene, ikke for alle. En evaluering fra 2008 kan ikke telles som «aldri nevnt» når vi ikke har lett i 2008-sesjonen, så bare evalueringer publisert innenfor dekningsvinduet er med.

Og det er fordelingen som er verdt å se på:

[[viz:hvem_blir_lest]]

## Sporet i budsjettet

Den siste akten stiller det spørsmålet som egentlig ligger under: koster kunnskapen noe å ignorere? Vi kan ikke måle det direkte, men vi kan måle noe i nærheten — om bevilgningene til bestillerens kapittel beveger seg etter en evaluering.

Testen er definert på forhånd, i kode, og kjørt én gang. Uten en kontrollgruppe ville svaret vært verdiløst: bevilgninger vokser stort sett, av lønns- og prisjustering alene. Utfallet måles derfor som kapitlets **andel av statsbudsjettet**, og de samme kapitlene i år uten evaluering utgjør kontrollen.

[[viz:budsjettsporet]]

Dette måler **samvariasjon, ikke årsak** — og her er den innvendingen sterkere enn vanlig: en evaluering bestilles ofte nettopp *fordi* noe er i endring. En omorganisering, et kutt, en ny satsing. Da er evalueringen et symptom på bevegelsen, ikke en årsak til den.

Og koblingen går gjennom bestillerens organisasjonsnummer til de kapitlene virksomheten fører utgifter på. Det er **bestillerens budsjett, ikke det evaluerte tiltakets**. Evaluerer Helsedirektoratet en kommunal ordning, er det Helsedirektoratets kapitler vi ser på. Det er analysens største metodiske svakhet, og den lar seg ikke reparere med disse dataene.

[[viz:forbeholdene]]

**Metodenotat:** Én rad er ett dokument i Kudos av typen «Evaluering» — ikke ett evalueringsprosjekt. Et prosjekt som leverer tre delrapporter teller tre ganger. Inneværende år er utelatt fra tempokurven, siden det ikke er ferdig. Treffene på Stortinget er ordrette tittelmatcher; titler som er for korte eller for generiske («Evaluering av tilskuddsordningen») er utelatt, fordi et treff på dem ikke ville bevist noe. All kode og alle mellomregninger ligger i `pipeline/` i repoet.
