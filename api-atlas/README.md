# API-atlas — norske åpne datakilder

Et kartlagt og kjørbart atlas over 17 offentlige norske datakilder, bygget som
grunnmur for datahistorier og analyseprosjekter. Hver kilde har ett
frittstående Python-script i `eksempler/` som

- dokumenterer kilden (endepunkter, nøkkelkrav, lisens, dok-lenke),
- gjør et ekte kall og viser hvordan svaret parses,
- foreslår «gull å grave i» — konkrete prosjektidéer for akkurat den kilden.

Alt bruker kun Pythons standardbibliotek (3.11+). Ingen pip install,
ingen nøkler (unntatt Frost, som har gratis registrering). Scriptene er
bevisst frittstående: kopier ett av dem inn i et nytt prosjekt som
startpunkt, uten å dra med seg noe annet.

## Sjekk at atlaset er ferskt

```bash
python3 api-atlas/test_atlas.py
```

Kjøreren gjør ett lite kall mot hver kilde og skriver en statustabell på
under et minutt. Kjør den månedlig, og alltid før du starter et nytt
prosjekt på en av kildene.

| | |
|---|---|
| ✓ | kilden svarer og dataene ser riktige ut |
| – | hoppet over — API-nøkkel mangler (`FROST_CLIENT_ID`) |
| ? | kilden ble aldri nådd: nett, brannmur eller proxy her hos deg |
| ✗ | kilden svarte feil — åpne `DOK`-lenken øverst i scriptet og se hva som er endret |

Skillet mellom `?` og `✗` er verdt å merke seg: uten nett ser alle sytten
kildene ut som om de endret seg samtidig, og da leter du i dokumentasjonen
etter noe som står helt stille. `?` betyr hverken bekreftet eller avkreftet
— kjør på nytt fra et sted med åpen utgående forbindelse. Exit-koden er
antall `✗`, eller 1 om kjøringen bare var uten nett; 0 kommer kun når alt
faktisk er grønt.

### Eller la GitHub gjøre det

`.github/workflows/api-atlas.yml` kjører den samme testen den 1. hver
måned, og ellers når du trykker **Run workflow** under Actions-fanen — det
virker fra telefon og nettbrett, uten Codespace. Tabellen legges i
kjøringssammendraget, så du slipper å grave i loggen. Feiler en kilde,
feiler jobben, og GitHub sender deg e-post; ingen e-post betyr grønt.

Vil du ha Frost testet i tillegg til de seksten andre, legg
`FROST_CLIENT_ID` inn under Settings → Secrets and variables → Actions.
Uten den hopper den kilden over seg selv, som lokalt.

Merk at GitHub slår av planlagte workflows i repoer uten aktivitet på 60
dager. Skjer det, får du en e-post om det, og en knapp for å slå den på.

## Kildene

| Kilde | Hva | Nøkkel | Script |
|-------|-----|--------|--------|
| **SSB** (PxWebApi v2) | all offisiell statistikk, inkl. KOSTRA | nei | `hent_ssb_statistikk.py` |
| **Brreg Enhetsregisteret** | alle norske organisasjoner | nei | `hent_brreg_enheter.py` |
| **Brreg Frivillighetsregisteret** | frivillige org. med ICNPO-kategori | nei | `hent_brreg_frivillighet.py` |
| **tilskudd.no** (Lottstift) | statlige tildelinger til frivilligheten | nei | `hent_tilskudd_lottstift.py` |
| **Felles datakatalog** (Digdir) | kartet over alle åpne datasett | nei | `hent_datakatalog.py` |
| **Kudos** (DFØ) | evalueringer, årsrapporter, tildelingsbrev | nei | `hent_kudos.py` |
| **statsregnskapet.no** (DFØ) | statens utgifter/inntekter per kapittel, post og virksomhet siden 2014 | nei | `hent_statsregnskapet.py` |
| **Kartverket adresser** | geokoding av offisielle adresser | nei | `hent_kartverket_adresser.py` |
| **Kartverket stedsnavn** | 1M+ stedsnavn med historikk og språk | nei | `hent_kartverket_stedsnavn.py` |
| **MET Locationforecast** | værvarsel (yr-dataene) | nei¹ | `hent_met_vaervarsel.py` |
| **MET Frost** | værobservasjoner tilbake til 1800-tallet | gratis id | `hent_met_frost.py` |
| **Entur** | all kollektivtrafikk: ruter, stopp, sanntid | nei¹ | `hent_entur_reiser.py` |
| **Norges Bank** | valutakurser og renter, lang historikk | nei | `hent_norges_bank_valuta.py` |
| **Nasjonalbiblioteket** | alt digitalisert: bøker, aviser, n-gram | nei | `hent_nasjonalbiblioteket.py` |
| **Stortinget** | saker, voteringer, spørsmål siden 1945 | nei | `hent_stortinget.py` |
| **Valgdirektoratet** | valgresultater ned til kretsnivå | nei | `hent_valgresultater.py` |
| **Statens vegvesen NVDB** | vegnettet: fartsgrenser, trafikk, bommer | nei | `hent_nvdb_vegobjekter.py` |

¹ krever identifiserende header (User-Agent hos MET, ET-Client-Name hos
Entur) — scriptene setter den, med kontakt@impromptu.no som avsender.

## Metoden (samme som resten av repoet)

1. **Hent** med identifiserende User-Agent, lave voluner, pauser mellom
   batchkall. Vi er gjester hos forvaltningen.
2. **Valider** før du stoler på noe: rimelighetssjekker som i
   `pipeline/kontrakt.py` (en USD-kurs på 0,4 eller et toppnavn med 3
   bærere er parsefeil, ikke funn).
3. **Snapshot** til statiske filer med metadata (kilde, dato_hentet,
   lisens). Nettsiden spør aldri API-et direkte — den leser snapshots.
   Da er du immun mot nedetid, endringer og rate limits i produksjon.

## Åtte ting som koster tid første gang (målt, august 2026)

Feltnotater fra å bygge én historie på tre av kildene samtidig. De er sortert
etter hvor mye de sparte da vi endelig skjønte dem — og de gjelder på tvers,
ikke bare for kilden de ble oppdaget på.

1. **Be API-et fortelle deg reglene sine.** Send en ugyldig parameter med
   vilje. Kudos' 422 lister `allowed_parameters` og røper at `per_page` har
   tak på 50. Stortingets 400 navngir parameteren som mangler. Det er den
   billigste dokumentasjonen som finnes, og den er alltid fersk.

2. **Les kildens egen kolonnebeskrivelse, ikke bare kolonnenavnene.**
   Statsregnskapet leverer en CSV med én forklaring per kolonne. Vi brukte
   fire kjøringer på å tolke tallene baklengs før vi leste den. Svaret sto
   der hele tiden.

3. **Sonder før du planlegger.** Skriv et lite script som bare fastslår hva
   kilden faktisk gir, og som konkluderer eksplisitt. `sonder_stortinget.py`
   avgjorde om fulltekst i det hele tatt var tilgjengelig — hele analysen
   sto og falt på det, og et gjett ville gitt en stille degradering til noe
   svakere enn det vi hadde lovet i teksten.

4. **Let etter koblingsnøkkelen framfor å gjette den.** Skal to datasett
   kobles, ta verdier du VET finnes i det ene og søk rekursivt etter dem i
   det andre. Da fant vi at Stortingets `henvisning` inneholder
   publikasjonsreferansen som delstreng. Feltnavnet ville vi aldri gjettet,
   og eksakt likhet ville gitt null treff.

5. **Verifiser en total mot et tall du kjenner utenfra.** Er summen av
   statens bevilgninger 1 897 mrd i året, er filteret riktig. Er den 22, er
   det ikke det — uansett hvor pen resten av analysen ser ut.

6. **`meta.total` er ikke det samme som det du får servert.** Kudos teller
   7 138 og serverer 7 112, fordi nye dokumenter dyttes inn foran mens du
   paginerer. Krev dekning, ikke identitet, og skriv mankoen inn i
   snapshotet.

7. **Hent i skiver på noe stabilt, ikke på sidetall.** Er kilden sortert
   etter nyeste, driver pagineringen mens den går. Årsskiver
   (`published_year_from/to`) gjør hver spørring kort, og et nytt dokument i
   år rører ikke fjoråret.

8. **Preflight før en lang kjøring, og lagre ved ethvert avbrudd.** Et
   minimalt kall med kort tidsavbrudd skiller «tjenesten er nede» fra
   «modellen er treg» på tretti sekunder i stedet for tjue minutter. Og et
   sjekkpunkt som bare skrives ved normal slutt, finnes ikke den dagen du
   trenger det.

## Lisensnotat

De fleste kildene er NLOD (Norsk lisens for offentlige data) eller
CC BY 4.0: fri bruk, også kommersielt, mot navngivelse. Oppgi alltid
kilde — det gjør impromptu-historiene troverdige uansett. Metadata fra
Nasjonalbiblioteket er åpne, men selve verkene kan ha opphavsrett.

## Kilder som IKKE har åpne API-er (så du slipper å lete)

- **Kulturdirektoratets tildelinger** — kun manuell CSV-nedlasting fra
  kulturdirektoratet.no/vedtak (rutinen står i tilskuddskompassets README)
- **Anleggsregisteret** (idretts- og kulturanlegg) — data finnes på
  anleggsregisteret.no, men uten dokumentert åpent API; sjekk
  Felles datakatalog for status, eller spør Kulturdepartementet om uttrekk
- **Matrikkelen (full)** og **Folkeregisteret** — krever avtale/hjemmel

## Idéer på tvers av kildene

Kombinasjonene er gullet — én kilde er et faktum, to kilder er en historie:

- **Kulturkroner-kartet**: tilskudd.no + Brreg (kommune) + SSB-befolkning
  → tilskuddskroner per innbygger per kommune, år for år
- **Frivillighetens puls**: Frivillighetsregisteret + tilskudd.no →
  hvem får, hvem faller utenfor
- **Været og festivalen**: Frost + arrangementsdatoer → flaks-indeksen
  for norske utendørsfestivaler
- **Kulturpolitisk oppmerksomhet**: Stortinget (saker) +
  Nasjonalbiblioteket (avis-n-gram) → når snakker Norge om kultur?
- **Reisetid til kultur**: Entur + Kartverket-geokoding → hvor mange
  minutter unna er nærmeste scene, bibliotek, kino?

---

Vedlikeholdt som del av [impromptu.no](https://impromptu.no). Bygget
juli 2026; endepunktene bekreftes med `test_atlas.py`.
