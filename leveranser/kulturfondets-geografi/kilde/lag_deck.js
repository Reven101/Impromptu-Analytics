// Presentasjon: Kulturfondets geografi 2024–2026
// Tallene hentes fra rapportens egen datablokk (data.json) — ingen tall skrives inn for hånd
// der de finnes i kilden.
const pptxgen = require('pptxgenjs');
const fs = require('fs');

const D = JSON.parse(fs.readFileSync('data.json', 'utf8'));
const F = D.fylker;
const fy = Object.fromEntries(F.map(f => [f.fylke, f]));
const M = D.meta;

/* ---------- Impromptu-paletten (tokens.css) ---------- */
const PAPIR = 'F2EDE0', KORT = 'FBF8F0', BLEKK = '27332D', BLEKK2 = '46514A',
      DEMPET = '5F6A62', LINJE = 'C9C0AC', LINJESVAK = 'DDD6C4',
      GRAN = '1F4E45', SENNEP = 'D9A441', ROSE = 'D9A199',
      OVER = '0E7D59', UNDER = 'B23A28', OKER = 'A9761B', BLA = '3E6CB0',
      PLOMME = '8A4A82',
      // Oker som seriefarge er for lys for liten tekst — egen mørkere variant til etiketter
      TEKSTOKER = '8A5F14';

const TIT = 'Cambria', BOD = 'Calibri', MONO = 'Consolas';
const nb = (v, d = 1) => v.toLocaleString('nb-NO', { minimumFractionDigits: d, maximumFractionDigits: d });
const ni = v => Math.round(v).toLocaleString('nb-NO');

const p = new pptxgen();
p.layout = 'LAYOUT_WIDE';            // 13,333 × 7,5 tommer — settes før første slide
p.author = 'Impromptu Analytics';
p.title = 'Kulturfondets geografi 2024–2026';

const W = 13.333, H = 7.5, MG = 0.75;

/* ---------- byggeklosser ---------- */
function lysSlide() {
  const s = p.addSlide();
  s.background = { color: PAPIR };
  return s;
}
function morkSlide() {
  const s = p.addSlide();
  s.background = { color: GRAN };
  return s;
}
function eyebrow(s, tekst, y = 0.52, farge = GRAN) {
  s.addText(tekst.toUpperCase(), {
    x: MG, y, w: W - 2 * MG, h: 0.26, margin: 0,
    fontFace: MONO, fontSize: 10.5, bold: true, color: farge, charSpacing: 2.6
  });
}
function tittel(s, tekst, opt = {}) {
  s.addText(tekst, Object.assign({
    x: MG, y: 0.84, w: W - 2 * MG, h: 0.9, margin: 0,
    fontFace: TIT, fontSize: 32, bold: true, color: BLEKK, valign: 'top'
  }, opt));
}
function ingress(s, tekst, opt = {}) {
  s.addText(tekst, Object.assign({
    x: MG, y: 1.74, w: 9.4, h: 0.62, margin: 0,
    fontFace: BOD, fontSize: 15, color: BLEKK2, lineSpacing: 21
  }, opt));
}
// Kort-flaten fra designsystemet: kortfarge, hårlinje, liten radius, myk skygge.
function kort(s, x, y, w, h, opt = {}) {
  s.addShape(p.ShapeType.roundRect, Object.assign({
    x, y, w, h, rectRadius: 0.04,
    fill: { color: opt.fill || KORT },
    line: { color: opt.linje || LINJE, width: 0.75 },
    shadow: { type: 'outer', angle: 90, blur: 8, offset: 0.04, color: GRAN, opacity: 0.1 }
  }, opt.form || {}));
}
function kilde(s, tekst, farge = DEMPET) {
  s.addText(tekst, {
    x: MG, y: H - 0.62, w: W - 2 * MG, h: 0.3, margin: 0,
    fontFace: MONO, fontSize: 9, color: farge
  });
}
// Stort tall med etikett under — brukes i nøkkeltall-radene.
function statTall(s, x, y, w, tall, etikett, farge = BLEKK, tallSize = 34) {
  s.addText(tall, { x, y, w, h: 0.66, margin: 0, fontFace: TIT, fontSize: tallSize, bold: true, color: farge });
  s.addText(etikett, { x, y: y + 0.68, w, h: 0.72, margin: 0, fontFace: BOD, fontSize: 11.5, color: DEMPET, lineSpacing: 15 });
}

const AKSE = { catAxisLabelColor: BLEKK2, valAxisLabelColor: BLEKK2,
               catAxisLabelFontFace: BOD, valAxisLabelFontFace: BOD,
               catAxisLabelFontSize: 10.5, valAxisLabelFontSize: 10,
               catAxisLineShow: false, valAxisLineShow: false,
               valGridLine: { color: LINJESVAK, size: 0.75 },
               catGridLine: { style: 'none' },
               chartArea: { fill: { color: KORT } }, plotArea: { fill: { color: KORT } } };

/* ==================== 1 · Forside ==================== */
{
  const s = morkSlide();
  s.addText('NORSK KULTURFOND · GEOGRAFISK ANALYSE', {
    x: MG, y: 1.5, w: 11, h: 0.3, margin: 0,
    fontFace: MONO, fontSize: 11.5, bold: true, color: SENNEP, charSpacing: 3
  });
  s.addText('Hvem søker,\nog hvem får', {
    x: MG, y: 2.0, w: 9.2, h: 2.1, margin: 0,
    fontFace: TIT, fontSize: 52, bold: true, color: 'FBF8F0', lineSpacing: 56
  });
  s.addText(
    `${ni(8372)} kunstnere, selskaper, festivaler og institusjoner sendte ${ni(M.soknader)} søknader ` +
    `til Kulturfondet på tre år. ${nb(M.tildelt_mrd, 2)} milliarder kroner ble delt ut. ` +
    'Vinnerne og taperne er ikke dem sentrum–periferi-fortellingen peker på.', {
    x: MG, y: 4.35, w: 8.6, h: 1.2, margin: 0,
    fontFace: BOD, fontSize: 16, color: 'D8DED9', lineSpacing: 24
  });
  s.addText([
    { text: `Søknadsfrister ${M.periode}`, options: { breakLine: true } },
    { text: 'Kilde: Kulturdirektoratets vedtakseksport pr. 13.08.2026', options: { breakLine: true } },
    { text: 'Befolkningstall: SSB tabell 06913, 1.1.2026' }
  ], { x: MG, y: 5.95, w: 8, h: 0.9, margin: 0, fontFace: MONO, fontSize: 9.5, color: '9FB0A6', lineSpacing: 14 });
  s.addNotes('Analysen dekker Norsk kulturfond alene — ikke Statens kunstnerstipend eller Fond for lyd og bilde. ' +
    'Tre års søknadsfrister, aggregert fra 32 633 vedtaksrader til 19 829 søknader.');
}

/* ==================== 2 · Forbeholdet først ==================== */
{
  const s = lysSlide();
  eyebrow(s, 'Slik skal tallene leses');
  tittel(s, 'Et fylke søker ikke om noe');
  ingress(s, 'Alle tall gjelder søkerens registrerte adresse — hvor kunstneren bor eller virksomheten ' +
    'er registrert. Det sier ingenting om hvor aktiviteten foregår.');

  kort(s, MG, 2.65, 5.85, 2.35);
  s.addText('MÅLER', { x: MG + 0.35, y: 2.9, w: 5, h: 0.25, margin: 0, fontFace: MONO, fontSize: 9.5, bold: true, color: OVER, charSpacing: 2.2 });
  s.addText('Hvor pengene mottas', { x: MG + 0.35, y: 3.2, w: 5.1, h: 0.4, margin: 0, fontFace: TIT, fontSize: 20, bold: true, color: BLEKK });
  s.addText('Søkerens adresse, etter SSBs fylkesinndeling for 2024. ' +
    'Når Akershus får lite, betyr det at søkere med adresse i Akershus får lite.', {
    x: MG + 0.35, y: 3.68, w: 5.15, h: 1.1, margin: 0, fontFace: BOD, fontSize: 13, color: BLEKK2, lineSpacing: 19 });

  kort(s, MG + 6.25, 2.65, 5.85, 2.35);
  s.addText('MÅLER IKKE', { x: MG + 6.6, y: 2.9, w: 5, h: 0.25, margin: 0, fontFace: MONO, fontSize: 9.5, bold: true, color: UNDER, charSpacing: 2.2 });
  s.addText('Hvor aktiviteten skjer', { x: MG + 6.6, y: 3.2, w: 5.1, h: 0.4, margin: 0, fontFace: TIT, fontSize: 20, bold: true, color: BLEKK });
  s.addText('En turné i Nordland finansiert av et Oslo-basert kompani teller her som Oslo. ' +
    'Dette er en reell begrensning ved analysen.', {
    x: MG + 6.6, y: 3.68, w: 5.15, h: 1.1, margin: 0, fontFace: BOD, fontSize: 13, color: BLEKK2, lineSpacing: 19 });

  s.addText([
    { text: 'Kulturfondet er ikke et fordelingspolitisk virkemiddel, og skal det heller ikke være. ', options: { color: BLEKK2 } },
    { text: 'Men skjevheten er så stor, og så ulikt fordelt mellom ordningene, at den er verdt å kjenne presist.', options: { bold: true, color: BLEKK } }
  ], { x: MG, y: 5.35, w: 11.2, h: 0.7, margin: 0, fontFace: BOD, fontSize: 15, lineSpacing: 22 });
  kilde(s, `${ni(M.utenfor)} søknader (1,3 %) fra utenlandske eller ukjente adresser er holdt utenfor fylkessammenlikningen.`);
  s.addNotes('Ta forbeholdet før tallene, ikke etter. Det er den vanligste feillesningen av denne typen analyse.');
}

/* ==================== 3 · Nøkkeltall ==================== */
{
  const s = lysSlide();
  eyebrow(s, 'Hovedbildet');
  tittel(s, 'Én av åtte nordmenn bor i Oslo.\nNesten halvparten av kronene går dit.', { fontSize: 30, h: 1.3 });

  const O = fy['Oslo'];
  const tall = [
    [nb(O.kroneandel) + ' %', 'av kronene går til søkere\nmed Oslo-adresse', OVER],
    [nb(O.befandel) + ' %', 'av befolkningen\nbor i Oslo', BLEKK],
    [ni(O.unike_sokere), `av de ${ni(8372)} søkerne er\nregistrert i Oslo`, BLEKK],
    [nb(M.nasjonal_grad) + ' %', 'av søknadene innvilges\nnasjonalt', BLEKK],
    ['10,8×', 'forskjell i kroner per\ninnbygger, Oslo–Buskerud', UNDER]
  ];
  const kw = 2.28, gap = 0.15;
  tall.forEach((t, i) => {
    const x = MG + i * (kw + gap);
    kort(s, x, 2.6, kw, 2.05);
    statTall(s, x + 0.28, 2.85, kw - 0.5, t[0], t[1], t[2], 30);
  });

  s.addText([
    { text: 'Søkerne i Oslo står for ', options: { color: BLEKK2 } },
    { text: `${nb(O.soknadsandel)} prosent av alle søknader`, options: { bold: true, color: BLEKK } },
    { text: ' som sendes inn, og henter ', options: { color: BLEKK2 } },
    { text: '3,4 ganger befolkningsandelen', options: { bold: true, color: BLEKK } },
    { text: ' av kronene. Buskerud-søkerne får under en tredel av sin.', options: { color: BLEKK2 } }
  ], { x: MG, y: 5.15, w: 11.5, h: 0.8, margin: 0, fontFace: BOD, fontSize: 15, lineSpacing: 22 });
  kilde(s, `${ni(M.soknader)} søknader · ${nb(M.tildelt_mrd, 2)} mrd. kroner tildelt · ${M.ordninger} ordninger · ${M.periode}`);
}

/* ==================== 4 · Indeksfiguren ==================== */
{
  const s = lysSlide();
  eyebrow(s, 'Hovedbildet');
  tittel(s, 'Kroneandel målt mot befolkningsandel', { fontSize: 28 });
  s.addText('Indeks der 100 = fylket får nøyaktig sin befolkningsandel av kronene', {
    x: MG, y: 1.32, w: 9, h: 0.3, margin: 0, fontFace: BOD, fontSize: 12.5, color: DEMPET });

  const d = [...F].sort((a, b) => a.indeks - b.indeks);   // stigende: størst havner øverst
  s.addChart(p.ChartType.bar, [{
    name: 'Indeks', labels: d.map(f => f.fylke), values: d.map(f => f.indeks)
  }], Object.assign({}, AKSE, {
    x: MG, y: 1.75, w: 8.5, h: 5.0,
    barDir: 'bar', barGapWidthPct: 42,
    chartColors: d.map(f => f.indeks >= 100 ? OVER : UNDER),
    showValue: true, dataLabelPosition: 'outEnd', dataLabelColor: BLEKK2,
    dataLabelFontFace: MONO, dataLabelFontSize: 10, dataLabelFormatCode: '0',
    valAxisMinVal: 0, valAxisMaxVal: 400, valAxisMajorUnit: 100,
    showLegend: false, showTitle: false
  }));

  kort(s, 9.6, 2.3, 2.98, 3.3);
  s.addText('Fire fylker over,\nelleve under', { x: 9.9, y: 2.55, w: 2.5, h: 0.7, margin: 0, fontFace: TIT, fontSize: 17, bold: true, color: BLEKK, lineSpacing: 21 });
  s.addText([
    { text: 'Søkere i Oslo, Finnmark, Troms og Vestland henter inn mer enn fylkets befolkningsandel.', options: { breakLine: true } },
    { text: '', options: { breakLine: true, fontSize: 5 } },
    { text: 'Taperne er ikke periferien, men et belte på det sentrale Østlandet: Akershus, Østfold, Buskerud og Vestfold — med Agder like ved.' }
  ], { x: 9.9, y: 3.35, w: 2.45, h: 2.0, margin: 0, fontFace: BOD, fontSize: 11.5, color: BLEKK2, lineSpacing: 16 });
  kilde(s, 'Søkerens registrerte adresse. Befolkningsandel per 1.1.2026.');
  s.addNotes('Oslo-søkerne får 3,4 ganger befolkningsandelen; Buskerud-søkerne under en tredel.');
}

/* ==================== 5 · Ikke sentrum–periferi ==================== */
{
  const s = lysSlide();
  eyebrow(s, 'Hovedfunn');
  tittel(s, 'Det ventede mønsteret stemmer ikke');
  ingress(s, 'Nord-Norge taper ikke. Det sentrale Østlandet gjør det.');

  const kol = [
    { t: 'Over befolkningsandelen', f: OVER, rader: [
        ['Finnmark', `indeks ${ni(fy['Finnmark'].indeks)}`, 'dobbelt så mye per innbygger som folketallet tilsier'],
        ['Troms', `indeks ${ni(fy['Troms'].indeks)}`, 'høy uttelling tross lite folketall'],
        ['Vestland', `indeks ${ni(fy['Vestland'].indeks)}`, 'så vidt over egen befolkningsandel']
      ] },
    { t: 'Under befolkningsandelen', f: UNDER, rader: [
        ['Akershus', `indeks ${ni(fy['Akershus'].indeks)}`, `${ni(fy['Akershus'].folketall)} innbyggere — flere enn Oslo`],
        ['Vestfold', `indeks ${ni(fy['Vestfold'].indeks)}`, `lavest justert innvilgelsesgrad i landet: ${nb(fy['Vestfold'].justert)} %`],
        ['Buskerud', `indeks ${ni(fy['Buskerud'].indeks)}`, `kun ${ni(fy['Buskerud'].kr_per_innb)} kroner per innbygger`]
      ] }
  ];
  kol.forEach((k, i) => {
    const x = MG + i * 6.1;
    s.addText(k.t.toUpperCase(), { x, y: 2.62, w: 5.6, h: 0.25, margin: 0, fontFace: MONO, fontSize: 10, bold: true, color: k.f, charSpacing: 2.2 });
    k.rader.forEach((r, j) => {
      const y = 3.0 + j * 1.22;
      kort(s, x, y, 5.6, 1.05);
      s.addText(r[0], { x: x + 0.3, y: y + 0.13, w: 2.3, h: 0.35, margin: 0, fontFace: TIT, fontSize: 17, bold: true, color: BLEKK });
      s.addText(r[1], { x: x + 2.6, y: y + 0.18, w: 2.7, h: 0.3, margin: 0, fontFace: MONO, fontSize: 11.5, bold: true, color: k.f, align: 'right' });
      s.addText(r[2], { x: x + 0.3, y: y + 0.52, w: 5.0, h: 0.42, margin: 0, fontFace: BOD, fontSize: 11.5, color: BLEKK2, lineSpacing: 15 });
    });
  });
  kilde(s, 'Indeks 100 = kroneandel lik befolkningsandel.');
}

/* ==================== 6 · Akershus ==================== */
{
  const s = lysSlide();
  const A = fy['Akershus'];
  eyebrow(s, 'Den blinde flekken');
  tittel(s, 'Akershus er landets største fylke —\nog nest lavest på kroner per innbygger', { fontSize: 27, h: 1.35 });

  const rader = [
    [ni(A.folketall), 'innbyggere — flere enn Oslo', BLEKK],
    [nb(A.kroneandel) + ' %', `av kronene, mot en befolkningsandel på ${nb(A.befandel)} %`, UNDER],
    [nb(A.justert) + ' %', `justert innvilgelsesgrad, mot ${nb(M.nasjonal_grad)} % nasjonalt (z = −3,9)`, UNDER],
    [ni(A.arrangor_indeks), 'indeks på arrangør- og infrastrukturordninger — lavest i landet', UNDER]
  ];
  rader.forEach((r, i) => {
    const y = 2.6 + i * 0.95;
    s.addText(r[0], { x: MG, y, w: 2.5, h: 0.6, margin: 0, fontFace: TIT, fontSize: 26, bold: true, color: r[2], align: 'right' });
    s.addText(r[1], { x: MG + 2.75, y: y + 0.12, w: 4.6, h: 0.62, margin: 0, fontFace: BOD, fontSize: 13, color: BLEKK2, lineSpacing: 18 });
  });

  kort(s, 8.15, 2.6, 4.43, 3.5, { fill: GRAN, linje: GRAN });
  s.addText('KRONER PER INNBYGGER TIL ARRANGEMENT,\nVISNINGSSTEDER OG KULTURBYGG', {
    x: 8.5, y: 2.85, w: 3.75, h: 0.55, margin: 0, fontFace: MONO, fontSize: 9, bold: true, color: SENNEP, charSpacing: 1.8, lineSpacing: 13 });
  const kpi = [['Finnmark', 370], ['Oslo', 270], ['Akershus', 30]];
  kpi.forEach((k, i) => {
    const y = 3.6 + i * 0.78;
    s.addText(k[0], { x: 8.5, y, w: 1.9, h: 0.42, margin: 0, fontFace: BOD, fontSize: 14, color: 'D8DED9' });
    s.addText(ni(k[1]) + ' kr', { x: 10.2, y: y - 0.06, w: 2.05, h: 0.5, margin: 0, fontFace: TIT, fontSize: k[0] === 'Akershus' ? 24 : 19, bold: true, color: k[0] === 'Akershus' ? SENNEP : 'FBF8F0', align: 'right' });
  });
  s.addText('Ingen av de tre forklaringsfaktorene peker i Akershus’ favør. Dette er ikke et distriktsspørsmål — og fanges derfor ikke opp av tiltak innrettet mot distriktene.', {
    x: MG, y: 6.35, w: 11.5, h: 0.55, margin: 0, fontFace: BOD, fontSize: 14, bold: true, color: BLEKK, lineSpacing: 20 });
  s.addNotes(`Akershus har ${ni(A.unike_sokere)} søkere og ${nb(A.org_per_10k)} organisasjoner per 10 000 innbyggere som søker Kulturfondet.`);
}

/* ==================== 7 · Søkertetthet ==================== */
{
  const s = lysSlide();
  eyebrow(s, 'Søkerne');
  tittel(s, 'Hvor tett sitter søkerne?', { fontSize: 28 });
  s.addText('Unike søkere per 10 000 innbyggere, fordelt på enkeltpersoner og organisasjoner', {
    x: MG, y: 1.32, w: 9.5, h: 0.3, margin: 0, fontFace: BOD, fontSize: 12.5, color: DEMPET });

  const d = [...F].sort((a, b) => a.sokere_per_10k - b.sokere_per_10k);
  s.addChart(p.ChartType.bar, [
    { name: 'Enkeltpersoner', labels: d.map(f => f.fylke), values: d.map(f => f.personer_per_10k) },
    { name: 'Organisasjoner', labels: d.map(f => f.fylke), values: d.map(f => f.org_per_10k) }
  ], Object.assign({}, AKSE, {
    x: MG, y: 1.75, w: 8.5, h: 5.0,
    barDir: 'bar', barGrouping: 'clustered', barGapWidthPct: 34,
    chartColors: [OKER, GRAN],
    showValue: true, dataLabelPosition: 'outEnd', dataLabelColor: BLEKK2,
    dataLabelFontFace: MONO, dataLabelFontSize: 8.5, dataLabelFormatCode: '0.0',
    showLegend: true, legendPos: 't', legendColor: BLEKK2, legendFontFace: BOD, legendFontSize: 11,
    showTitle: false
  }));

  kort(s, 9.6, 2.3, 2.98, 3.5);
  s.addText('To ulike\nsøkergrupper', { x: 9.9, y: 2.55, w: 2.5, h: 0.7, margin: 0, fontFace: TIT, fontSize: 17, bold: true, color: BLEKK, lineSpacing: 21 });
  s.addText([
    { text: 'Enkeltkunstnere: Oslo 22,0 mot 2,1 i Møre og Romsdal — ti gangers forskjell. I tall: 1 602 kunstnere i Oslo mot 57.', options: { breakLine: true } },
    { text: '', options: { breakLine: true, fontSize: 5 } },
    { text: 'Organisasjoner: her følger Finnmark (15,7) og Troms (12,3) rett bak Oslo (23,3). Nederst ligger ikke distriktene, men Møre og Romsdal, Østfold, Vestfold og Rogaland.' }
  ], { x: 9.9, y: 3.35, w: 2.45, h: 2.2, margin: 0, fontFace: BOD, fontSize: 11, color: BLEKK2, lineSpacing: 15 });
  kilde(s, 'Samme søker teller én gang uansett antall søknader. Måler bredden i søkerbasen, ikke søknadsmengden.');
}

/* ==================== 8 · Personer vs organisasjoner ==================== */
{
  const s = lysSlide();
  eyebrow(s, 'Søkerne');
  tittel(s, 'De to gruppene lykkes ikke likt');
  ingress(s, 'Om lag 3 500 av søkerne er enkeltpersoner, 5 100 er organisasjoner. Forskjellen i uttelling er stor — og forsterkes av beløpene.');

  const par = [
    ['Innvilgelsesgrad', '26,9 %', '39,5 %'],
    ['Snittbeløp ved ja', '109 000 kr', '320 000 kr'],
    ['Andel av alle kronene', '9,8 %', '90,2 %']
  ];
  s.addText('ENKELTPERSONER', { x: 4.35, y: 2.62, w: 3.2, h: 0.25, margin: 0, fontFace: MONO, fontSize: 9.5, bold: true, color: TEKSTOKER, charSpacing: 2, align: 'center' });
  s.addText('ORGANISASJONER', { x: 8.15, y: 2.62, w: 3.2, h: 0.25, margin: 0, fontFace: MONO, fontSize: 9.5, bold: true, color: GRAN, charSpacing: 2, align: 'center' });
  par.forEach((r, i) => {
    const y = 3.0 + i * 1.02;
    kort(s, MG, y, 10.6, 0.86);
    s.addText(r[0], { x: MG + 0.32, y: y + 0.22, w: 3.4, h: 0.42, margin: 0, fontFace: BOD, fontSize: 13.5, color: BLEKK2 });
    s.addText(r[1], { x: 4.35, y: y + 0.14, w: 3.2, h: 0.55, margin: 0, fontFace: TIT, fontSize: 21, bold: true, color: OKER, align: 'center' });
    s.addText(r[2], { x: 8.15, y: y + 0.14, w: 3.2, h: 0.55, margin: 0, fontFace: TIT, fontSize: 21, bold: true, color: GRAN, align: 'center' });
  });
  s.addText([
    { text: 'I Oslo står enkeltkunstnere for 36,9 prosent av søknadene, men bare 11,4 prosent av kronene. ', options: { color: BLEKK2 } },
    { text: 'Bildet av Oslo som kunstnerbyen stemmer i antall søkere — men pengene går i hovedsak til virksomheter.', options: { bold: true, color: BLEKK } }
  ], { x: MG, y: 6.15, w: 11.3, h: 0.6, margin: 0, fontFace: BOD, fontSize: 14, lineSpacing: 20 });
  s.addNotes('Unntaket er Buskerud: 31,1 % av kronene går til enkeltpersoner — ikke fordi kunstnerne der gjør det bra, ' +
    'men fordi fylket nesten ikke har store institusjonelle søkere. Største mottaker i Buskerud fikk 2,0 mkr; i Oslo 17,6 mkr.');
}

/* ==================== 9 · To måter å tape på (matrise) ==================== */
{
  const s = lysSlide();
  eyebrow(s, 'Diagnose');
  tittel(s, 'To helt ulike måter å tape på', { fontSize: 28 });
  s.addText('Et fylke kan få lite av to grunner: få søker, eller de som søker får nei. Skillet avgjør hvilket tiltak som virker.', {
    x: MG, y: 1.3, w: 11, h: 0.32, margin: 0, fontFace: BOD, fontSize: 13, color: BLEKK2 });

  // Plottflate
  const px = 2.05, py = 1.95, pw = 8.35, ph = 4.5;
  kort(s, px, py, pw, ph);
  // Kvadratrotskala på x: søkertettheten er sterkt høyreskjev (Oslo 43,9 mot Rogaland 2,5),
  // og en lineær akse presser elleve fylker sammen i venstre kant. Aksemerkene under viser
  // skalaen eksplisitt.
  const xmax = 60, ymin = 27, ymax = 51;
  const X = v => px + Math.sqrt(v) / Math.sqrt(xmax) * pw;
  const Y = v => py + ph - (v - ymin) / (ymax - ymin) * ph;

  // Snittlinjer
  const snittX = 10, snittY = M.nasjonal_grad;
  s.addShape(p.ShapeType.line, { x: X(snittX), y: py, w: 0, h: ph, line: { color: LINJE, width: 1, dashType: 'dash' } });
  s.addShape(p.ShapeType.line, { x: px, y: Y(snittY), w: pw, h: 0, line: { color: LINJE, width: 1, dashType: 'dash' } });

  // Aksemerker
  [2.5, 5, 10, 20, 40].forEach(v => {
    s.addText(String(v).replace('.', ','), { x: X(v) - 0.3, y: py + ph + 0.04, w: 0.6, h: 0.22, margin: 0,
      fontFace: MONO, fontSize: 8, color: DEMPET, align: 'center' });
  });
  [30, 35, 40, 45, 50].forEach(v => {
    s.addText(v + ' %', { x: px - 0.62, y: Y(v) - 0.11, w: 0.54, h: 0.22, margin: 0,
      fontFace: MONO, fontSize: 8, color: DEMPET, align: 'right' });
  });

  // Boblene tegnes først, slik at ingen etikett havner under en boble
  const punkter = F.map(f => ({
    f, x: X(f.sokere_per_10k), y: Y(f.justert),
    r: 0.10 + Math.min(0.20, Math.sqrt(f.tildelt_mkr) / 90),
    farge: f.justert >= snittY ? OVER : UNDER
  }));
  punkter.forEach(pt => s.addShape(p.ShapeType.ellipse, {
    x: pt.x - pt.r, y: pt.y - pt.r, w: pt.r * 2, h: pt.r * 2,
    fill: { color: pt.farge, transparency: 25 }, line: { color: pt.farge, width: 1 }
  }));

  // Grådig etikettplassering: prøv høyre side først, så venstre, så gradvis
  // større loddrette forskyvninger. Første posisjon uten kollisjon vinner.
  const LH = 0.19;                                   // etiketthøyde ved 9,5 pt
  const bredde = navn => 0.062 * navn.length + 0.06; // konservativt anslag for Calibri 9,5 pt
  const lagt = [];
  const kolliderer = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  const kandidater = [];
  for (let dy = 0; dy <= 0.62; dy += 0.155) {
    for (const tegn of (dy === 0 ? [1] : [-1, 1])) {
      kandidater.push({ side: 'h', dy: tegn * dy });
      kandidater.push({ side: 'v', dy: tegn * dy });
    }
  }
  [...punkter].sort((a, b) => b.r - a.r).forEach(pt => {
    const w = bredde(pt.f.fylke);
    let valgt = null;
    for (const k of kandidater) {
      const x = k.side === 'h' ? pt.x + pt.r + 0.06 : pt.x - pt.r - 0.06 - w;
      const y = pt.y - LH / 2 + k.dy;
      const boks = { x, y, w, h: LH };
      if (x < px + 0.04 || x + w > px + pw - 0.04 || y < py + 0.04 || y + LH > py + ph - 0.04) continue;
      if (lagt.some(l => kolliderer(boks, l))) continue;
      // en etikett skal heller ikke legge seg oppå en annen fylkes boble
      if (punkter.some(o => o !== pt && kolliderer(boks, { x: o.x - o.r, y: o.y - o.r, w: o.r * 2, h: o.r * 2 }))) continue;
      valgt = { boks, side: k.side };
      break;
    }
    if (!valgt) {   // siste utvei: rett til høyre, uansett
      valgt = { boks: { x: pt.x + pt.r + 0.06, y: pt.y - LH / 2, w, h: LH }, side: 'h' };
    }
    lagt.push(valgt.boks);
    s.addText(pt.f.fylke, {
      x: valgt.boks.x, y: valgt.boks.y, w, h: LH, margin: 0,
      fontFace: BOD, fontSize: 9.5, color: BLEKK, align: valgt.side === 'h' ? 'left' : 'right'
    });
  });

  // Landssnitt-etiketten plasseres til slutt, i første ledige luke over linja
  {
    const w = 1.42, h = 0.22;
    const hindre = lagt.concat(punkter.map(o => ({ x: o.x - o.r, y: o.y - o.r, w: o.r * 2, h: o.r * 2 })));
    let x = px + pw - w - 0.08;
    for (let kand = px + pw - w - 0.08; kand >= px + 0.08; kand -= 0.12) {
      const boks = { x: kand, y: Y(snittY) - h - 0.04, w, h };
      if (!hindre.some(o => kolliderer(boks, o))) { x = kand; break; }
    }
    s.addText(`landssnitt ${nb(M.nasjonal_grad)} %`, {
      x, y: Y(snittY) - h - 0.04, w, h, margin: 0,
      fontFace: MONO, fontSize: 8.5, color: DEMPET, align: 'right' });
  }

  // Akser
  s.addText('Unike søkere per 10 000 innbyggere  →', { x: px, y: py + ph + 0.3, w: pw, h: 0.28, margin: 0, fontFace: BOD, fontSize: 11, color: DEMPET, align: 'center' });
  s.addText('Ordningsjustert\ninnvilgelsesgrad  →', { x: 0.42, y: py + 1.6, w: 1.25, h: 0.7, margin: 0, fontFace: BOD, fontSize: 11, color: DEMPET, align: 'right', lineSpacing: 15, rotate: 270 });

  kort(s, 10.7, 1.95, 1.88, 4.5, { fill: KORT });
  s.addText([
    { text: 'BEGGE PROBLEMER', options: { fontFace: MONO, fontSize: 8.5, bold: true, color: UNDER, charSpacing: 1.6, breakLine: true } },
    { text: 'Akershus, Østfold, Vestfold og Agder: få søker, og de som gjør det får sjeldnere ja.', options: { fontSize: 10.5, color: BLEKK2, breakLine: true } },
    { text: '', options: { breakLine: true, fontSize: 8 } },
    { text: 'BARE FÅ SØKERE', options: { fontFace: MONO, fontSize: 8.5, bold: true, color: TEKSTOKER, charSpacing: 1.6, breakLine: true } },
    { text: 'Rogaland og Møre og Romsdal treffer helt normalt — de er bare svært få.', options: { fontSize: 10.5, color: BLEKK2, breakLine: true } },
    { text: '', options: { breakLine: true, fontSize: 8 } },
    { text: 'HØY UTTELLING', options: { fontFace: MONO, fontSize: 8.5, bold: true, color: OVER, charSpacing: 1.6, breakLine: true } },
    { text: 'Finnmark og Troms, tross lite folketall.', options: { fontSize: 10.5, color: BLEKK2 } }
  ], { x: 10.9, y: 2.15, w: 1.5, h: 4.1, margin: 0, fontFace: BOD, lineSpacing: 14 });
  kilde(s, 'Boblestørrelse = tildelte millioner kroner. Justert innvilgelsesgrad er korrigert for hvilke ordninger søkerne faktisk søker på.');
}

/* ==================== 10 · Dekomponering ==================== */
{
  const s = lysSlide();
  eyebrow(s, 'Diagnose');
  tittel(s, 'Søkeaktivitet forklarer mest', { fontSize: 28 });
  s.addText('Kroner per innbygger er produktet av tre ting: hvor mange som søker, hvor ofte de får ja, og hvor store tildelingene er. ' +
    'Søylene viser hvor mye hver faktor trekker fylket over eller under landssnittet.', {
    x: MG, y: 1.3, w: 11.3, h: 0.5, margin: 0, fontFace: BOD, fontSize: 12.5, color: BLEKK2, lineSpacing: 17 });

  const utvalg = ['Oslo', 'Finnmark', 'Troms', 'Vestland', 'Trøndelag', 'Møre og Romsdal', 'Rogaland', 'Agder', 'Vestfold', 'Akershus', 'Buskerud'];
  const d = utvalg.map(n => fy[n]);
  s.addChart(p.ChartType.bar, [
    { name: 'Søkeaktivitet', labels: utvalg, values: d.map(f => f['Søkeaktivitet']) },
    { name: 'Treffprosent', labels: utvalg, values: d.map(f => f['Treffprosent']) },
    { name: 'Prosjektstørrelse', labels: utvalg, values: d.map(f => f['Prosjektstørrelse']) }
  ], Object.assign({}, AKSE, {
    x: MG, y: 1.95, w: 8.6, h: 4.7,
    barDir: 'col', barGrouping: 'stacked', barGapWidthPct: 45,
    chartColors: [GRAN, OKER, BLA],
    showValue: false,
    showLegend: true, legendPos: 't', legendColor: BLEKK2, legendFontFace: BOD, legendFontSize: 11,
    showTitle: false, catAxisLabelRotate: 300
  }));

  kort(s, 9.55, 2.4, 3.03, 3.3);
  s.addText('Tre ulike\ndiagnoser', { x: 9.85, y: 2.62, w: 2.5, h: 0.7, margin: 0, fontFace: TIT, fontSize: 17, bold: true, color: BLEKK, lineSpacing: 21 });
  s.addText([
    { text: 'Rogaland: −63 poeng totalt, hvorav −86 er svak søkeaktivitet — motvirket av større prosjekter.', options: { breakLine: true } },
    { text: '', options: { breakLine: true, fontSize: 5 } },
    { text: 'Buskerud: kommer dårligst ut totalt, men får ja like ofte som andre. Få søker, og prosjektene er små.', options: { breakLine: true } },
    { text: '', options: { breakLine: true, fontSize: 5 } },
    { text: 'Akershus: eneste fylke som ligger under på alle tre faktorene samtidig.', options: { bold: true, color: BLEKK } }
  ], { x: 9.85, y: 3.4, w: 2.45, h: 2.15, margin: 0, fontFace: BOD, fontSize: 11, color: BLEKK2, lineSpacing: 15 });
  kilde(s, 'Logaritmisk dekomponering; faktorene summerer til fylkets totalavvik fra landssnittet i kroner per innbygger.');
}

/* ==================== 11 · Signifikans ==================== */
{
  const s = lysSlide();
  eyebrow(s, 'Signifikans');
  tittel(s, 'Skjevheten forsvinner ikke når man\njusterer for hva fylkene søker på', { fontSize: 27, h: 1.3 });
  s.addText('Innvilgelsesgraden varierer fra 15,6 % på scenekunst forprosjekt til 69,4 % på litteraturproduksjon. ' +
    'Justeringen standardiserer over 36 ordninger × 3 årganger — og flytter lite.', {
    x: MG, y: 2.05, w: 11.3, h: 0.5, margin: 0, fontFace: BOD, fontSize: 12.5, color: BLEKK2, lineSpacing: 17 });

  const d = [...F].sort((a, b) => b.justert - a.justert);
  s.addChart(p.ChartType.bar, [
    { name: 'Rå innvilgelsesgrad', labels: d.map(f => f.fylke), values: d.map(f => f.grad) },
    { name: 'Ordningsjustert', labels: d.map(f => f.fylke), values: d.map(f => f.justert) }
  ], Object.assign({}, AKSE, {
    x: MG, y: 2.7, w: 8.6, h: 3.95,
    barDir: 'col', barGrouping: 'clustered', barGapWidthPct: 38,
    chartColors: [LINJE, GRAN],
    showValue: false,
    showLegend: true, legendPos: 't', legendColor: BLEKK2, legendFontFace: BOD, legendFontSize: 11,
    showTitle: false, catAxisLabelRotate: 300,
    valAxisMinVal: 0, valAxisMaxVal: 55, valAxisMajorUnit: 10, valAxisLabelFormatCode: '0"%"'
  }));

  kort(s, 9.55, 2.95, 3.03, 3.1, { fill: GRAN, linje: GRAN });
  s.addText('SJU SIGNIFIKANTE AVVIK', { x: 9.85, y: 3.15, w: 2.6, h: 0.25, margin: 0, fontFace: MONO, fontSize: 9, bold: true, color: SENNEP, charSpacing: 1.8 });
  s.addText([
    { text: 'Over landssnittet', options: { bold: true, color: 'FBF8F0', breakLine: true } },
    { text: 'Finnmark 49,4 %\nTroms 43,2 %\nOslo 36,6 %', options: { color: 'BFD3C7', breakLine: true } },
    { text: '', options: { breakLine: true, fontSize: 6 } },
    { text: 'Under landssnittet', options: { bold: true, color: 'FBF8F0', breakLine: true } },
    { text: 'Akershus 31,0 %\nAgder 31,2 %\nØstfold 30,7 %\nVestfold 28,8 %', options: { color: 'E8C0B4' } }
  ], { x: 9.85, y: 3.5, w: 2.5, h: 2.4, margin: 0, fontFace: BOD, fontSize: 11.5, lineSpacing: 16 });
  kilde(s, 'Mantel-Haenszel-test over ordning × årgang, p < 0,05. Landssnitt 35,5 %.');
  s.addNotes('Dette er det viktigste enkeltfunnet for direktoratet: Oslo-søkerne vinner ikke fordi søknadene deres vurderes mildere ' +
    '— justert grad er 36,6 % mot 35,5 % nasjonalt. De vinner fordi de er mange og sender mye: 41 % av alle søknader.');
}

/* ==================== 12 · To geografier ==================== */
{
  const s = lysSlide();
  eyebrow(s, 'Ordningsstruktur');
  tittel(s, 'Kulturfondet har to geografier, ikke én');
  ingress(s, 'Skillet går ikke mellom kunstarter, men mellom hva ordningen finansierer: et arrangement eller et bygg, ' +
    'eller en produksjon og et kunstnerskap.', { w: 11.3, h: 0.7 });

  const T = D.typer;
  const bokser = [
    { navn: '11 ORDNINGER · ARRANGØR, VISNINGSSTED, INFRASTRUKTUR', d: T.arrangor, f: GRAN,
      tekst: 'Søkerne er nesten uten unntak organisasjoner. Fem fylker utenom Oslo henter mer enn befolkningsandelen: Finnmark, Vestland, Troms, Nordland og Møre og Romsdal.' },
    { navn: '25 ORDNINGER · PRODUKSJON, KUNSTNERSKAP, PUBLISERING', d: T.produksjon, f: OKER,
      tekst: 'Her søker enkeltkunstnerne. Utenom Oslo holder bare Finnmark og Troms seg over befolkningsandelen.' }
  ];
  bokser.forEach((b, i) => {
    const x = MG + i * 6.1;
    kort(s, x, 2.85, 5.6, 3.15);
    s.addText(b.navn, { x: x + 0.32, y: 3.08, w: 5.0, h: 0.42, margin: 0, fontFace: MONO, fontSize: 8.5, bold: true, color: b.f === OKER ? TEKSTOKER : b.f, charSpacing: 1.5, lineSpacing: 12 });
    const tall = [[ni(b.d.sum_mkr) + ' mkr', 'tildelt'], [nb(b.d.oslo_andel) + ' %', 'til Oslo-søkere'], [nb(b.d.innv_grad) + ' %', 'innvilget']];
    tall.forEach((t, j) => {
      const tx = x + 0.32 + j * 1.72;
      s.addText(t[0], { x: tx, y: 3.55, w: 1.65, h: 0.5, margin: 0, fontFace: TIT, fontSize: 18, bold: true, color: b.f });
      s.addText(t[1], { x: tx, y: 4.03, w: 1.65, h: 0.28, margin: 0, fontFace: BOD, fontSize: 10.5, color: DEMPET });
    });
    s.addText(b.tekst, { x: x + 0.32, y: 4.45, w: 4.95, h: 1.35, margin: 0, fontFace: BOD, fontSize: 12, color: BLEKK2, lineSpacing: 17 });
  });
  s.addText([
    { text: 'Direktoratets geografiske profil avgjøres i praksis av hvordan rammen fordeles mellom disse to ordningstypene', options: { bold: true, color: BLEKK } },
    { text: ' — ikke av vurderingene i den enkelte ordning. Vrir man en krone fra produksjon til arrangør, flytter den seg også på kartet.', options: { color: BLEKK2 } }
  ], { x: MG, y: 6.15, w: 11.5, h: 0.6, margin: 0, fontFace: BOD, fontSize: 14, lineSpacing: 20 });
}

/* ==================== 13 · Ytterpunktene ==================== */
{
  const s = lysSlide();
  eyebrow(s, 'Ordningsstruktur');
  tittel(s, 'Oslos andel varierer fra 12 til 90 prosent', { fontSize: 28 });
  s.addText('Andel av ordningens tildelte kroner som går til søkere med Oslo-adresse. De 24 største ordningene.', {
    x: MG, y: 1.32, w: 10, h: 0.3, margin: 0, fontFace: BOD, fontSize: 12.5, color: DEMPET });

  const d = [...D.ordninger].sort((a, b) => a.oslo_kr - b.oslo_kr);
  const kort_navn = n => n.length > 44 ? n.slice(0, 42) + '…' : n;
  s.addChart(p.ChartType.bar, [{
    name: 'Oslos kroneandel', labels: d.map(o => kort_navn(o.navn)), values: d.map(o => o.oslo_kr)
  }], Object.assign({}, AKSE, {
    x: MG, y: 1.75, w: 9.3, h: 5.0,
    barDir: 'bar', barGapWidthPct: 32,
    chartColors: d.map(o => o.type === 'arrangor' ? GRAN : OKER),
    showValue: true, dataLabelPosition: 'outEnd', dataLabelColor: BLEKK2,
    dataLabelFontFace: MONO, dataLabelFontSize: 8.5, dataLabelFormatCode: '0.0"%"',
    catAxisLabelFontSize: 8.5,
    valAxisMaxVal: 100, valAxisMajorUnit: 25, valAxisLabelFormatCode: '0"%"',
    showLegend: false, showTitle: false
  }));

  kort(s, 10.4, 2.3, 2.18, 3.3);
  s.addText([
    { text: 'ARRANGØR', options: { fontFace: MONO, fontSize: 9, bold: true, color: GRAN, charSpacing: 1.6, breakLine: true } },
    { text: 'Litteraturformidling gir bare 12,3 % til Oslo, Utviklingstiltak 19,7 %.', options: { fontSize: 11, color: BLEKK2, breakLine: true } },
    { text: '', options: { breakLine: true, fontSize: 8 } },
    { text: 'PRODUKSJON', options: { fontFace: MONO, fontSize: 9, bold: true, color: TEKSTOKER, charSpacing: 1.6, breakLine: true } },
    { text: 'Litteraturproduksjon gir 90,4 % til Oslo — en forlagsgeografi mer enn en forfattergeografi.', options: { fontSize: 11, color: BLEKK2 } }
  ], { x: 10.6, y: 2.5, w: 1.8, h: 2.9, margin: 0, fontFace: BOD, lineSpacing: 15 });
  kilde(s, 'Ordninger med under 150 søknader i perioden er utelatt.');
}

/* ==================== 14 · Trendadvarsel ==================== */
{
  const s = lysSlide();
  eyebrow(s, 'Utvikling');
  tittel(s, 'Fordelingen er stabil. Det som ser ut\nsom bevegelse, er enkelttilsagn.', { fontSize: 27, h: 1.3 });

  const aar = ['2024', '2025', '2026'];
  const serier = ['Oslo', 'Vestland', 'Trøndelag', 'Akershus'];
  s.addChart(p.ChartType.line, serier.map(n => ({
    name: n, labels: aar, values: D.trend_kroneandel[n]
  })), Object.assign({}, AKSE, {
    x: MG, y: 2.35, w: 6.9, h: 4.0,
    chartColors: [GRAN, BLA, OKER, UNDER],
    lineSize: 2.5, lineSmooth: false,
    showValue: false,
    showLegend: true, legendPos: 'b', legendColor: BLEKK2, legendFontFace: BOD, legendFontSize: 11,
    showTitle: false,
    valAxisMaxVal: 55, valAxisMinVal: 0, valAxisMajorUnit: 10, valAxisLabelFormatCode: '0"%"'
  }));

  kort(s, 8.05, 2.35, 4.53, 4.0, { fill: GRAN, linje: GRAN });
  s.addText('LES IKKE ENKELTÅR SOM TREND', { x: 8.4, y: 2.6, w: 3.9, h: 0.25, margin: 0, fontFace: MONO, fontSize: 9.5, bold: true, color: SENNEP, charSpacing: 1.8 });
  s.addText([
    { text: 'Hoppet for Akershus fra 3,6 til 9,7 prosent ser dramatisk ut. Men 25 av de 40 millionene i 2026 gikk til to søkere: De Utvalgte og Nie Teater, med hvert sitt seksårige kunstnerskapstilsagn.', options: { breakLine: true } },
    { text: '', options: { breakLine: true, fontSize: 7 } },
    { text: 'For Vestfold står de fem største tilsagnene for 53 prosent av alle kronene, i Østfold 50 prosent.', options: { breakLine: true } },
    { text: '', options: { breakLine: true, fontSize: 7 } },
    { text: 'Oslo-serien, som hviler på 1 346 mottakere, er den eneste stabile nok til å tolkes direkte — og den ligger mellom 41 og 49 prosent alle tre årene, uten retning.', options: { bold: true, color: 'FBF8F0' } }
  ], { x: 8.4, y: 2.95, w: 3.85, h: 3.2, margin: 0, fontFace: BOD, fontSize: 11.5, color: 'C8D6CD', lineSpacing: 16 });
  kilde(s, 'Sammensetningsjusterte andeler, balansert panel på 27 ordninger med frist alle tre år (18 484 søknader). 2026 er ufullstendig: sju runder mot ti–elleve.');
}

/* ==================== 15 · Fire spørsmål ==================== */
{
  const s = lysSlide();
  eyebrow(s, 'Hva funnene betyr');
  tittel(s, 'Fire spørsmål til direktoratet', { fontSize: 30 });

  const q = [
    ['01', 'Er søkerne i Akershus en blind flekk?',
      'Nest lavest på kroner per innbygger, lavest i landet på arrangørordninger, og signifikant under landssnittet selv etter justering. Ikke et distriktsspørsmål — og fanges derfor ikke av distriktstiltak.'],
    ['02', 'Skal bredden i søkermassen måles som eget mål?',
      'Hvor mange som søker forklarer mer enn innvilgelsesgraden gjør. Uten et mål på søkerbredde per fylke rettes tiltakene mot vurderingspraksis, der problemet stort sett ikke ligger.'],
    ['03', 'Er balansen mellom ordningstypene et bevisst valg?',
      'Forholdet mellom arrangørpotten og produksjonspotten er i praksis direktoratets viktigste geografiske virkemiddel. Er dagens fordeling et resultat av en vurdering, eller av historikk?'],
    ['04', 'Hva gjør søkerne i Nord-Norge annerledes?',
      'Finnmark og Troms har landets høyeste justerte innvilgelsesgrad, på ordninger over hele bredden. Dette er den eneste dokumenterte suksessoppskriften i materialet — og den er ikke undersøkt.']
  ];
  q.forEach((k, i) => {
    const x = MG + (i % 2) * 6.1, y = 1.85 + Math.floor(i / 2) * 2.45;
    kort(s, x, y, 5.6, 2.2);
    s.addText(k[0], { x: x + 0.32, y: y + 0.2, w: 0.7, h: 0.4, margin: 0, fontFace: MONO, fontSize: 15, bold: true, color: TEKSTOKER });
    s.addText(k[1], { x: x + 1.0, y: y + 0.18, w: 4.35, h: 0.5, margin: 0, fontFace: TIT, fontSize: 16, bold: true, color: BLEKK, lineSpacing: 20 });
    s.addText(k[2], { x: x + 1.0, y: y + 0.78, w: 4.35, h: 1.25, margin: 0, fontFace: BOD, fontSize: 11.5, color: BLEKK2, lineSpacing: 16 });
  });
  kilde(s, 'Kulturfondets geografi 2024–2026 · Impromptu Analytics');
}

/* ==================== 16 · Metode ==================== */
{
  const s = morkSlide();
  s.addText('METODE OG FORBEHOLD', { x: MG, y: 0.72, w: 10, h: 0.3, margin: 0, fontFace: MONO, fontSize: 10.5, bold: true, color: SENNEP, charSpacing: 2.6 });
  s.addText('Slik er tallene regnet ut', { x: MG, y: 1.1, w: 10, h: 0.7, margin: 0, fontFace: TIT, fontSize: 30, bold: true, color: 'FBF8F0' });

  const m = [
    ['Enhet', `${ni(M.rader_kilde)} vedtaksrader aggregert til 19 829 søknader på nøkkelen ordning + frist + søker + tiltakstittel. Flerårige tilsagn gir 3–6 rader for samme søknad; rådata overteller derfor flerårige ordninger kraftig.`],
    ['Søkerne', '8 372 unike søkere i de 15 fylkene, identifisert ved søkernavn. Om lag 3 500 enkeltpersoner og 5 100 organisasjoner; summen overstiger 8 372 fordi noen navn opptrer i flere fylker eller under begge typer.'],
    ['Geografi', 'Søkers fylke, ikke tiltakets sted. Analysen måler hvor pengene mottas, ikke hvor aktiviteten skjer. 263 søknader (1,3 %) fra utenlandske eller ukjente adresser er holdt utenfor.'],
    ['Justering', 'Indirekte standardisering over ordning × søknadsår, testet med Mantel-Haenszel og hypergeometrisk varians.'],
    ['Avgrensning', 'Bare Norsk kulturfond. Statens kunstnerstipend, Fond for lyd og bilde og øvrige ordninger er ikke med — konklusjonene gjelder ikke for dem. 2026 er ufullstendig og nivåtall per år er ikke sammenlignbare.']
  ];
  m.forEach((r, i) => {
    const y = 2.05 + i * 0.92;
    s.addText(r[0].toUpperCase(), { x: MG, y: y + 0.02, w: 1.85, h: 0.3, margin: 0, fontFace: MONO, fontSize: 10, bold: true, color: SENNEP, charSpacing: 1.6 });
    s.addText(r[1], { x: MG + 2.0, y, w: 9.5, h: 0.82, margin: 0, fontFace: BOD, fontSize: 12, color: 'C8D6CD', lineSpacing: 17 });
  });
  s.addText('Kilde: Kulturdirektoratets vedtakseksport pr. 13.08.2026 · SSB tabell 06913 · Impromptu Analytics', {
    x: MG, y: H - 0.68, w: 11.5, h: 0.3, margin: 0, fontFace: MONO, fontSize: 9, color: '8FA398' });
}

p.writeFile({ fileName: 'Kulturfondets-geografi-2024-2026.pptx' })
 .then(f => console.log('skrevet', f));
