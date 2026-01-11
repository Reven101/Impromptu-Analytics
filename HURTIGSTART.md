# 🚀 HURTIGSTART - Impromptu Analytics

## Du har 4 filer:
1. `index.html` - Hovedsiden (analyseappen)
2. `personvern.html` - Personvernerklæring (GDPR)
3. `vilkar.html` - Vilkår for bruk
4. `README.md` - Detaljert dokumentasjon

---

## ⚡ Deploy på 5 minutter (Vercel - GRATIS)

### Steg 1: Gå til Vercel
Åpne: https://vercel.com/new

### Steg 2: Logg inn
Klikk "Continue with GitHub" eller "Continue with Email"

### Steg 3: Last opp
- Klikk på "Import Git Repository" → "Browse" under "Or start from a template"
- Eller bruk Vercel CLI: `npx vercel`
- Eller dra `impromptu-analytics`-mappen inn

### Steg 4: Deploy
Klikk "Deploy" - vent 30 sekunder

### Steg 5: Koble til impromptu.no
1. Gå til prosjektet på Vercel
2. Settings → Domains
3. Skriv inn: impromptu.no
4. Oppdater DNS hos din registrar:
   - Type: CNAME
   - Name: @
   - Value: cname.vercel-dns.com

---

## 💳 Legg til betaling (Stripe)

1. Opprett konto: https://stripe.com/no
2. Lag produkter (Pro: 149 kr/mnd, Business: 499 kr/mnd)
3. Opprett Payment Links
4. Bytt ut lenkene i index.html

---

## 📧 Oppsett av e-post

Anbefalt: Zoho Mail (gratis)
1. https://zoho.com/mail
2. Legg til impromptu.no
3. Sett opp MX-records

---

## ✅ Sjekkliste

- [ ] Deploy til Vercel
- [ ] Koble til impromptu.no
- [ ] Sett opp Stripe
- [ ] Sett opp e-post
- [ ] Test analysetjenesten
- [ ] Del på LinkedIn!

---

**Les README.md for full dokumentasjon, markedsføringsstrategi og tekniske detaljer.**
