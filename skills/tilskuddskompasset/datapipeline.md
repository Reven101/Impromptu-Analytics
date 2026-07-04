# Datapipeline — kilder, kjørerekkefølge og lærdommer

Verifisert mot scriptene i repoet 2026-07-04. Alle skrapescripts bruker transparent
User-Agent med kontaktinfo (`kontakt@impromptu.no`), pause mellom kall (0,3–0,7 s) og
timeout — behold det mønsteret for nye kilder.

## Kilde 1: tilskudd.no (Lotteri- og stiftelsestilsynet) — helautomatisk, månedlig

```bash
python hent_bulk_tildelinger.py   # ~5 sek: Excel-bulk per budsjettår 2021–2026 → CSV/JSON
python hent_utvidet_data.py       # ~15 min: per-ordning metadata via __NEXT_DATA__-JSON
```
- Bulk-API-et (`/api/download/allocation-to-volunteers?year=X`) gir kun ett år per kall.
- `__NEXT_DATA__` er primærkilden for ordningssidene (strukturert og stabil), HTML-fallback.
- **Begrensning**: `__NEXT_DATA__` inneholder bare topp 10 mottakere per ordning; backend-API
  er ikke offentlig. Oppsummeringsstatistikken (totalRecipients osv.) dekker likevel alle.
- ID-rommet som crawles er `range(1, 1201)` — utvid ved behov.

## Kilde 2: Kulturrådet / Fond for lyd og bilde (NKF/FLB) — manuell nedlasting, halvårlig

Kulturdirektoratet har ingen åpen API. Manuell CSV-eksport fra kulturdirektoratet.no/vedtak
(Status = Innvilget + Avslått; alle fire finansieringskilder), legges i `tilskudd_data/`.

```bash
cd tilskudd_data
python bygg_nkf_flb_v2.py       # rens + innvilgelsesgrad-tabell
python hent_brreg_lookup.py     # kun ved nye org.nr (batch-oppslag, caches i brreg_lookup.csv)
python berik_nkf_flb_brreg.py   # fyller kommune/sektor/fylke — KUN tomme celler
cd .. && python hent_kulturdirektoratet_innhold.py   # skraper formål/frister per ordningsside
```

Lærdommer nedfelt i bygg_nkf_flb_v2.py (les docstringen der først):
- 2021–23- og 2024–26-eksportene har ULIK feltstruktur og harmoniseres kolonne for kolonne;
  2021–23 mangler soker_type, 2024–26 mangler kommune/sektor/ICNPO (fylles via Brreg).
- **Status i 2021–23-filen finnes ikke** — avledes av tildelt_belop > 0.
- **bevilgningsaar i 2024–26 er upålitelig**: gyldig vindu er verifisert til [2018, 2035];
  alt utenfor (2010, 2627, 7777 …) er placeholder/tastefeil og nulles + flagges.
- Duplikater fjernes i to omganger (rå + etter at årstall nulles og rader blir identiske).
- **FLB omstrukturerte til 4 brede kategorier i 2024** (FLB-AUDIO/CINE/LIVE/MEDIA) — de
  mappes manuelt til riktig ordningsside. KUL-DATA, KUL-IND og NKF-IBK er fortsatt
  uidentifiserte koder (ingen trygg match) — får «Uidentifisert ordning (…)»-navn.
- «(Innvilget Deltakelse)»-rader mangler orgnr; fylles via eksakt navnematch (uten suffiks)
  mot resten av datasettet.
- Brreg-oppslag gjøres i batch à 300 orgnr (ikke 14 000 enkeltkall); ugyldige orgnr
  (ikke 9 siffer) filtreres; resultat caches.
- Fylke avledes fra kommunenummer-prefiks kun for 2021–23 (2024–26 har søkers oppgitte fylke);
  bruker 2024-fylkesstrukturen.

## Kilde 3: NFI (Norsk filminstitutt) — helautomatisk, halvårlig

```bash
python hent_nfi_tildelinger.py   # ~3 min: nfi.no/tildelinger, 2020–i dag
python hent_nfi_ordninger.py     # ~1 min: ordningsmetadata + frister
```
- nfi.no kjører Craft CMS + Sprig (HTMX): data er server-rendret men lastes via
  `sprig-core/components/render` med HMAC-signert config. Strategien: hent forsiden én gang
  for CraftSessionId + sprig:config, kall deretter renderpunktet per år/side, paginer til
  neste-knapp er disabled. PAGE_LIMIT=20 er NFI-s valg — ikke endre.
- Kun standardbibliotek (urllib) — ingen requests/bs4 her.
- Tildelinger uten ordningsnavn grupperes som «Øvrige <område>».
- Frister på norsk datoformat → `_norsk_til_iso()` i lag_v4_data.py.

## Siste steg — alltid

```bash
python lag_v4_data.py    # bygger ordninger_v4.js (~10 sek)
git add ordninger_v4.js && git commit -m "Oppdater data" && git push   # Vercel deployer
```

Kontrolltall scriptet printer (rimelighetssjekk før commit):
antall ordninger totalt (~307), antall med mottaker-eksempler/fylkesfordeling/
beløpsfordeling, antall NKF/FLB-rader med skrapt innhold, antall foreldreløse lagt til.
Fall i disse tallene = en kilde har endret struktur; ikke push.
