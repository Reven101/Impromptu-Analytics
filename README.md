# Impromptu Analytics - AI Datainnsikt

En komplett SaaS-løsning for AI-drevet dataanalyse, klar til å deployes på impromptu.no.

## 💰 Forretningsmodell

| Plan | Pris | Mål-abonnenter for $1000/mnd |
|------|------|------------------------------|
| Gratis | 0 kr | Konvertering til Pro |
| Pro | 149 kr/mnd (~$14) | ~70 abonnenter |
| Business | 499 kr/mnd (~$47) | ~21 abonnenter |

**Break-even scenario:** 50 Pro + 5 Business = $910/mnd

## 🚀 Enkel Deploy (3 alternativer)

### Alternativ 1: Vercel (Anbefalt - Gratis)

1. **Opprett Vercel-konto:** https://vercel.com (gratis)

2. **Last opp prosjektet:**
   - Gå til https://vercel.com/new
   - Klikk "Upload" og dra `index.html`-filen inn
   - Klikk "Deploy"

3. **Koble til domenet:**
   - Gå til prosjektets "Settings" → "Domains"
   - Legg til `impromptu.no`
   - Følg instruksjonene for DNS-oppsett hos din domene-registrar

### Alternativ 2: Netlify (Gratis)

1. **Opprett Netlify-konto:** https://netlify.com

2. **Deploy:**
   - Gå til https://app.netlify.com/drop
   - Dra inn `impromptu-analytics`-mappen
   - Ferdig!

3. **Koble til domene:**
   - Domain settings → Add custom domain → impromptu.no

### Alternativ 3: GitHub Pages (Gratis)

1. Opprett GitHub-konto og nytt repository
2. Last opp `index.html`
3. Settings → Pages → Enable
4. Custom domain → impromptu.no

## 💳 Betalingsoppsett med Stripe

For å ta imot betalinger må du sette opp Stripe:

### Steg 1: Opprett Stripe-konto
1. Gå til https://stripe.com/no
2. Registrer deg med Impromptu Analytics-informasjon
3. Verifiser bedriften din

### Steg 2: Opprett produkter
I Stripe Dashboard → Products, opprett:

**Produkt 1: Pro**
- Navn: Impromptu Analytics Pro
- Pris: 149 NOK/måned (recurring)
- Beskrivelse: Ubegrensede analyser, avanserte innsikter

**Produkt 2: Business**
- Navn: Impromptu Analytics Business
- Pris: 499 NOK/måned (recurring)
- Beskrivelse: Team-tilgang, API, prioritert support

### Steg 3: Opprett betalingslenker
1. Gå til Payment Links i Stripe
2. Opprett en lenke for hver plan
3. Kopier lenkene

### Steg 4: Oppdater nettsiden
Bytt ut `#app`-lenkene i pricing-seksjonen med dine Stripe Payment Links:

```html
<a href="https://buy.stripe.com/din-pro-lenke" class="btn btn-primary">Start Pro</a>
```

## 📧 E-postoppsett

### Sett opp kontakt@impromptu.no

Alternativ 1: **Zoho Mail** (Gratis)
1. https://zoho.com/mail → Sign up free
2. Legg til domenet impromptu.no
3. Sett opp MX-records som instruert

Alternativ 2: **Google Workspace** (fra 72 kr/mnd)
1. https://workspace.google.com
2. Mer profesjonelt, inkluderer Google Drive etc.

## 📈 Markedsføringsstrategi

### Fase 1: Organisk vekst (Måned 1-3)

1. **LinkedIn-innhold:**
   - Del ukentlige tips om dataanalyse
   - Case studies med anonymiserte eksempler
   - "Slik fant vi X i kundens data"

2. **Norske fora og grupper:**
   - Facebook-grupper for småbedriftseiere
   - LinkedIn-grupper for norske gründere
   - Reddit r/norge (subtilt)

3. **SEO-optimalisering:**
   - Blog-innlegg om dataanalyse på norsk
   - Søkeord: "dataanalyse verktøy", "AI analyse norsk", "CSV analyse"

### Fase 2: Betalt annonsering (Måned 4+)

1. **Google Ads:**
   - Søkeord: "dataanalyse", "excel analyse", "business intelligence"
   - Budget: 2000-3000 kr/mnd
   - Mål: 10 kr per klikk, 5% konvertering = 40 nye leads

2. **LinkedIn Ads:**
   - Målrett småbedriftseiere og konsulenter
   - Budget: 3000 kr/mnd

### Målgrupper

1. **Konsulenter:** Trenger raske analyser for kunder
2. **Småbedriftseiere:** Vil forstå salgsdata, kundedata
3. **Forskere/studenter:** Analyserer spørreundersøkelser
4. **Regnskapsførere:** Analyserer finansdata

## 🔧 Teknisk vedlikehold

### Månedlige oppgaver (15 min)
- Sjekk Stripe Dashboard for betalinger
- Se på Google Analytics (legg til!) for trafikk
- Svar på support-e-post

### Tekniske oppdateringer
Nettsiden er statisk og trenger minimalt vedlikehold. AI-analysen bruker Anthropic API som oppdateres automatisk.

## 📊 KPIer å følge

| Metrikk | Mål (Måned 3) | Mål (Måned 6) |
|---------|---------------|---------------|
| Besøkende/mnd | 500 | 2000 |
| Gratis registreringer | 50 | 200 |
| Pro-abonnenter | 10 | 40 |
| Business-abonnenter | 2 | 10 |
| MRR (Monthly Recurring Revenue) | 2500 kr | 8000 kr |

## ⚠️ Viktige notater

1. **GDPR:** Du behandler brukerdata. Legg til:
   - Personvernerklæring
   - Cookie-samtykke
   - Databehandleravtale (hvis du lagrer data)

2. **Fakturering:** Stripe håndterer MVA automatisk for norske kunder

3. **Support:** Forvent 2-3 support-henvendelser per uke initialt

## 🎯 Neste steg

1. ✅ Kopier filene til din datamaskin
2. ⬜ Velg hosting-løsning (Vercel anbefales)
3. ⬜ Deploy nettsiden
4. ⬜ Sett opp Stripe
5. ⬜ Koble til impromptu.no
6. ⬜ Start markedsføring på LinkedIn

---

**Lykke til med Impromptu Analytics!** 🚀

Ved spørsmål, sjekk dokumentasjonen til verktøyene eller kontakt support hos respektive tjenester.
