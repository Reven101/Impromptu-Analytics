# Impromptu Analytics

Tre-lags datafortellingsmotor: `pipeline/` (Python, kun standardbibliotek) skriver validerte,
innsjekkede JSON-snapshots til `historier/innhold/<slug>/`, som `historier/motor/` rendrer.
Helstatisk — ingen backend, ingen database, ingen live API-kall i drift. Deploy: push til main
→ Vercel → impromptu.no.

Full arkitektur, kontrakten og fallgruvene ligger i skillen `impromptu-dataengine`. Denne fila
dekker bare det som ikke står der.

## Windows

Utviklingsmaskinen er Windows. README og docstrings er skrevet på Mac:

- **`python`, ikke `python3`.** Alle `python3 ...`-kall i dokumentasjonen må leses om.
- **Konsollen er cp1252.** Scriptene skriver `✓`/`✗`, som ga `UnicodeEncodeError` *etter* at
  jobben var gjort — så det så ut som en feilet kjøring, men snapshotet var allerede skrevet.
  `kontrakt.py` setter derfor `sys.stdout/stderr.reconfigure(encoding="utf-8")` ved import.
  Det er en no-op på macOS/Linux. Nye scripts skal importere `kontrakt` for å arve dette.
- Lokal visning: `python -m http.server 8000` fra repo-roten. ES-moduler krever http, ikke
  `file://`. `.claude/launch.json` starter den samme serveren.

## LLM som byggesteg

`pipeline/llm_klient.py` kaller OpenRouter. Regelen er at modellen kjøres **kun ved
bygging** — resultatet er et datert, innsjekket snapshot, og nettsiden gjør aldri et
API-kall. Et LLM-steg er en datakilde med egen feilrate, og behandles som det:

- **Kategorilister skrives for hånd.** Modellen velger blant dem; den finner dem ikke på.
  Finner den på en kategori, stopper scriptet framfor å opprette den i etterkant.
- **`PROMPTVERSJON` inngår i cache-nøkkelen.** Endrer du prompten eller kategoriene, bumper
  du versjonen — da blir gamle svar ugyldige i stedet for å blandes med nye.
- **Cachen sjekkes inn.** Den er både sporingslogg (hvilken modell sa hva) og
  kostnadssparer: en ny kjøring betaler bare for det som faktisk er nytt.
- **Listepris er ikke pris.** `forbruk_oppsummert()` leser faktisk kostnad fra OpenRouters
  `usage.cost`. Resonnerende modeller fakturerer tenketokens som output, og det snur
  rangeringen: `gemini-3.7-flash` har lavere listepris enn Haiku, men brukte 415 av 458
  output-tokens på resonnering og ble dobbelt så dyr. Sonnet 5 ble 5,3× dyrere av samme
  grunn. Mål alltid før du bytter modell.
- **Gratismodellene er ikke tilgjengelige i praksis.** `:free`-variantene ligger i en delt
  pulje hos leverandøren. Gemma 4 31b ga 429 på åtte forsøk over 248 sekunder, på seks
  tekster. `--reserve` finnes, men regn ikke med den.
- **Rådata skal ikke inn i repoet.** Alt her serveres statisk av Vercel, så en innsjekket
  CSV blir offentlig nedlastbar. `.gitignore` sperrer `*.csv` og `*.xlsx`; hentescriptene
  leser utenfra (`TILDELINGER_CSV`).
- **`maks_tokens` skal være realistisk, ikke «romslig for sikkerhets skyld».** OpenRouter
  reserverer kreditt mot `maks_tokens` for hver forespørsel i luften. Et oppblåst tak ganget
  med antall tråder sprenger in-flight-budsjettet og gir HTTP 402 med god saldo på konto —
  feilteksten sier «given your current in-flight requests», ikke «tom konto». Mål faktisk
  forbruk og legg på dobbel margin.
- **Skill bunt-feil fra API-feil.** `BuntFeil` (feil antall svar, ukjent kategori) løses ved
  å dele bunten og prøve igjen. SystemExit (kreditt, avkutting, nettverk) skal boble opp:
  å dele opp mot dem ganger bare opp antall mislykkede kall — på hver tråd.
- **Hva som ikke får sendes:** se [SIKKERHET.md](SIKKERHET.md).

## Når en historie påstår noe statistisk

Fire regler, alle kjøpt dyrt under arbeidet med `evalueringene` (august 2026).

**Et nullresultat fra en ødelagt måling er ikke et nullresultat.** Akt 3 ga
p = 0,90 og «ingen målbar forskjell» — akkurat det forhåndsdefinerte svaret vi
hadde skrevet testen for å kunne rapportere. I samme utskrift sto det at hele
statsregnskapet 2014–2026 summerte til 10,1 mrd. Utfallet var en *andel* av den
summen, så hver eneste verdi var regnet mot feil nevner, og testen kjørte like
pent. **Verifiser nevneren mot et tall du kjenner utenfra** før du tolker noe
som helst. Etter retting: 1 897 mrd i et typisk år, som er statsbudsjettet.
Legg sjekken inn som en hard port i scriptet, ikke som noe du husker å gjøre.

**Ytterpunkter som er valgt fordi de er ytterpunkter, krever permutasjonstest.**
En vanlig tosproporsjonstest på topp mot bunn later som paret var plukket på
forhånd. Med et titalls grupper finnes det førti-femti par, og det største
spriket er stort selv når ingenting skiller gruppene. Målt her: p = 0,0097
naivt mot 0,034 korrigert — og i en mellomvariant 0,0097 mot 0,17. Stokk om
utfallet på tvers av gruppene og mål hvor ofte tilfeldighet gir like stort
spenn; da er utvalget av ytterpunkter en del av nullhypotesen.

**Uenighet mellom to modeller måler kategorilista bedre enn «annet»-andelen.**
Husregelen sier at andelen `annet`/`uklar` er kvalitetsmålet på lista. Den
fanger ikke alt: her lå den på 2 % mens barnevernsdokumenter ble presset inn i
`arbeid_og_velferd` eller `kommunal_og_distrikt` alt etter hvilken modell som
svarte. Uenighetene var ikke tilfeldig spredt — de klumpet seg der lista manglet
et hjem. **Kjør to modeller på et utvalg og se HVOR de er uenige**, ikke bare
hvor ofte.

**Byggescriptet skal stoppe når brødteksten motsier tallene.** Teksten gjentar
hovedtallene med ord, som den skal — et tall som bare står i en figur blir ikke
lest. Men da kan teksten drifte i stillhet neste gang noe hentes på nytt.
`bygg_historie_evalueringer.py` sammenligner derfor prosenttallet og den
statistiske dommen i `tekst.md` mot det den nettopp regnet ut, og feiler på
avvik. Den porten fanget en påstand som var blitt gal mellom to kjøringer.

## Upubliserte historier: `"utkast": true`

`bygg_manifest.py` tar med **hver** mappe under `historier/innhold/` som har en gyldig
`data.json`. Skal en historie holdes tilbake, sett `"utkast": true` i `meta` — da valideres den
fortsatt som alle andre (den skal være publiserbar i det øyeblikket flagget fjernes), men den
havner ikke på forsiden, og scriptet skriver ut hvilke historier som ble holdt utenfor.

Tidligere fantes ingen slik mekanisme: eneste måte å holde tilbake på var å la være å commite
manifestet, og da ble historien stille republisert neste gang noen kjørte scriptet av andre
grunner. `tilskuddskontroll` («21 milliarder, 3 evalueringer») ble tatt ut på den måten
5. juli 2026 for faktasjekk (commit 4383201) og er nå merket som utkast i stedet.
