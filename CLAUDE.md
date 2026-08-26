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
- **Mål, ikke anslå.** `forbruk_oppsummert()` leser faktisk pris fra OpenRouters
  `usage.cost`. Resonnerende modeller koster langt mer enn tokentellingen antyder — Sonnet 5
  brukte 66 % av output-budsjettet på resonnering og ble 5,3× dyrere enn Haiku 4.5 på samme
  jobb, mot 5 prosentpoeng bedre treff.
- **`maks_tokens` skal være realistisk, ikke «romslig for sikkerhets skyld».** OpenRouter
  reserverer kreditt mot `maks_tokens` for hver forespørsel i luften. Et oppblåst tak ganget
  med antall tråder sprenger in-flight-budsjettet og gir HTTP 402 med god saldo på konto —
  feilteksten sier «given your current in-flight requests», ikke «tom konto». Mål faktisk
  forbruk og legg på dobbel margin.
- **Skill bunt-feil fra API-feil.** `BuntFeil` (feil antall svar, ukjent kategori) løses ved
  å dele bunten og prøve igjen. SystemExit (kreditt, avkutting, nettverk) skal boble opp:
  å dele opp mot dem ganger bare opp antall mislykkede kall — på hver tråd.
- **Hva som ikke får sendes:** se [SIKKERHET.md](SIKKERHET.md).

## Upubliserte historier: `"utkast": true`

`bygg_manifest.py` tar med **hver** mappe under `historier/innhold/` som har en gyldig
`data.json`. Skal en historie holdes tilbake, sett `"utkast": true` i `meta` — da valideres den
fortsatt som alle andre (den skal være publiserbar i det øyeblikket flagget fjernes), men den
havner ikke på forsiden, og scriptet skriver ut hvilke historier som ble holdt utenfor.

Tidligere fantes ingen slik mekanisme: eneste måte å holde tilbake på var å la være å commite
manifestet, og da ble historien stille republisert neste gang noen kjørte scriptet av andre
grunner. `tilskuddskontroll` («21 milliarder, 3 evalueringer») ble tatt ut på den måten
5. juli 2026 for faktasjekk (commit 4383201) og er nå merket som utkast i stedet.
