"""Bygger en frittstående diagramside av snapshotet fra hent_ssb_italiensk_mat.py.

    python pipeline/lag_italiensk_mat_side.py [--ut sti.html]

Formen er valgt, ikke arvet:

- **Tolv grupper er for mange for kategorifarger.** Paletten har åtte plasser, og
  skal aldri sykles. Derfor small multiples: tolv små linjediagram med hver sin
  ramme, alle i samme blåtone. Fargen koder ingenting — identiteten ligger i
  overskriften over hvert felt — og da finnes det heller ingen palettgrense å
  bryte.
- **Faste kroner er standardvisningen.** Over 38 år er løpende kroner mest
  prisvekst. Løpende ligger i tabellvisningen for den som skal sitere et enkeltår.
- **De tynne årene er tegnet inn, ikke skjult.** Der scriptet har flagget at
  gruppen omsatte for under 2 mill. faste kroner, ligger et skravert felt bak
  kurven. En leser som ser brødkurven starte på null skal se med det samme at
  starten ikke er en målt størrelse.
- **Hver akse er sin egen.** Trøffel (3,5 mill.) og vin (1,4 mrd.) i samme skala
  ville gjort elleve av tolv felt til flate streker. Small multiples med individuell
  y-akse sammenligner *form*, ikke nivå — og nivået står som tall i overskriften.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import kontrakt  # noqa: F401

CACHE = Path(__file__).resolve().parent / "cache"


def kompakt(v: float) -> str:
    if abs(v) >= 1e9:
        return f"{v / 1e9:.1f} mrd".replace(".", ",")
    if abs(v) >= 1e6:
        return f"{v / 1e6:.0f} mill." if abs(v) >= 1e7 else f"{v / 1e6:.1f} mill.".replace(".", ",", 1)
    if abs(v) >= 1e3:
        return f"{v / 1e3:.0f} 000"
    return f"{v:.0f}"


def bygg(d: dict) -> str:
    aarene = d["meta"]["aarene"]
    siste = d["meta"]["siste_aar"]
    forste = aarene[0]

    grupper = []
    for g in sorted(d["grupper"], key=lambda x: -x["verdi_faste"].get(str(siste), 0)):
        dk = g["datakvalitet"]
        faste = [g["verdi_faste"].get(str(a), 0) for a in aarene]
        grupper.append({
            "id": g["id"],
            "navn": g["navn"],
            "note": g.get("note"),
            "faste": faste,
            "lopende": [g["verdi_lopende"].get(str(a), 0) for a in aarene],
            "kg": [g["kg"].get(str(a), 0) for a in aarene],
            # Liter finnes bare for vin; None der SSB ikke maalte volum det aaret.
            "liter": [g["liter"].get(str(a)) for a in aarene] if "liter" in g else None,
            "solid": dk["forste_solide_aar"],
            "tynn": dk["spinkelt_grunnlag"],
            "brudd": [b["aar"] for b in dk["mulige_omnummereringsbrudd"]],
            "under": [
                {"navn": uid.replace("_", " "),
                 "verdi": u["verdi"].get(str(siste), 0)}
                for uid, u in g["undergrupper"].items()
            ],
        })

    tot = d["all_mat_kap_01_24"]
    payload = {
        "aarene": aarene,
        "forste": forste,
        "siste": siste,
        "grupper": grupper,
        "total_faste": [tot["verdi_faste"].get(str(a), 0) for a in aarene],
        "total_lopende": [tot["verdi_lopende"].get(str(a), 0) for a in aarene],
        "hentet": d["meta"]["dato_hentet"],
        "kontroll": d["kontroll_mot_sitc"]["storste_avvik"],
        "andel_utenfor": d["utenfor_gruppene"]["andel_siste_aar"],
        "utenfor": d["utenfor_gruppene"]["storste_siste_aar"][:6],
    }

    tot_n = tot["verdi_faste"][str(siste)]
    tot_0 = tot["verdi_faste"][str(forste)]

    return SIDE.replace("__DATA__", json.dumps(payload, ensure_ascii=False)) \
               .replace("__HERO__", f"{tot_n / 1e9:.1f}".replace(".", ",")) \
               .replace("__VEKST__", f"{tot_n / tot_0:.1f}".replace(".", ",")) \
               .replace("__SISTE__", str(siste)) \
               .replace("__FORSTE__", str(forste)) \
               .replace("__HENTET__", d["meta"]["dato_hentet"]) \
               .replace("__AVVIK__", f"{100 * d['kontroll_mot_sitc']['storste_avvik']:.1f}".replace(".", ",")) \
               .replace("__DEKN__", f"{100 * (1 - d['utenfor_gruppene']['andel_siste_aar']):.0f}")                .replace("__ANTALL__", str(len(grupper)))


SIDE = r"""<title>Italiensk mat i Norge</title>
<style>
  :root {
    color-scheme: light;
    --plane:#f9f9f7; --surface:#fcfcfb;
    --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
    --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,0.10);
    --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a;
    --tynn:#e1e0d9;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      color-scheme: dark;
      --plane:#0d0d0d; --surface:#1a1a19;
      --ink:#ffffff; --ink-2:#c3c2b7; --muted:#898781;
      --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,0.10);
      --s1:#3987e5; --s2:#d95926; --s3:#199e70;
      --tynn:#2c2c2a;
    }
  }
  :root[data-theme="dark"] {
    color-scheme: dark;
    --plane:#0d0d0d; --surface:#1a1a19;
    --ink:#ffffff; --ink-2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,0.10);
    --s1:#3987e5; --s2:#d95926; --s3:#199e70;
    --tynn:#2c2c2a;
  }
  * { box-sizing:border-box; }
  body {
    margin:0; background:var(--plane); color:var(--ink);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    line-height:1.55; -webkit-font-smoothing:antialiased;
  }
  .wrap { max-width:1120px; margin:0 auto; padding:48px 24px 96px; }
  header { margin-bottom:40px; }
  h1 { font-size:clamp(28px,4vw,42px); line-height:1.12; margin:0 0 12px; letter-spacing:-0.02em; }
  .dek { color:var(--ink-2); font-size:17px; max-width:64ch; margin:0; }
  .kilde { color:var(--muted); font-size:13px; margin-top:14px; }
  h2 { font-size:20px; margin:0 0 6px; letter-spacing:-0.01em; }
  .h2sub { color:var(--ink-2); font-size:14.5px; margin:0 0 20px; max-width:70ch; }
  section { margin-top:56px; }

  .hero {
    background:var(--surface); border:1px solid var(--ring); border-radius:14px;
    padding:28px 30px; display:flex; flex-wrap:wrap; gap:36px; align-items:flex-end;
  }
  .heroval { font-size:clamp(44px,7vw,68px); font-weight:600; line-height:0.95; letter-spacing:-0.03em; }
  .herolab { color:var(--ink-2); font-size:14px; margin-top:8px; max-width:34ch; }
  .stat { border-left:1px solid var(--grid); padding-left:24px; }
  .statval { font-size:26px; font-weight:600; letter-spacing:-0.02em; }
  .statlab { color:var(--muted); font-size:12.5px; margin-top:3px; }

  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(248px,1fr)); gap:14px; }
  .facet {
    background:var(--surface); border:1px solid var(--ring); border-radius:12px;
    padding:14px 14px 8px;
  }
  /* Fast hoyde pa tittel og flagg: uten den skyver en tittel som brytes til to
     linjer kurven nedover, og sparklines i samme rad slutter a ligge pa linje —
     som er nettopp den sammenligningen small multiples finnes for. */
  .ftitle { font-size:13.5px; font-weight:600; line-height:1.3; min-height:35px; }
  .fval { font-size:12.5px; color:var(--ink-2); margin-top:2px; font-variant-numeric:tabular-nums; }
  .fflag { font-size:11.5px; color:var(--muted); margin-top:4px; min-height:30px; }
  svg { display:block; width:100%; overflow:visible; }
  .gridline { stroke:var(--grid); stroke-width:1; }
  .axisline { stroke:var(--axis); stroke-width:1; }
  .tick { fill:var(--muted); font-size:10px; font-variant-numeric:tabular-nums; }

  .cardwide {
    background:var(--surface); border:1px solid var(--ring); border-radius:14px; padding:22px 24px 14px;
  }
  .legend { display:flex; flex-wrap:wrap; gap:18px; margin:0 0 14px; padding:0; list-style:none; }
  .legend li { display:flex; align-items:center; gap:7px; font-size:13px; color:var(--ink-2); }
  .key { width:14px; height:3px; border-radius:2px; flex:none; }

  table { border-collapse:collapse; width:100%; font-size:13px; }
  th,td { text-align:right; padding:7px 10px; border-bottom:1px solid var(--grid); font-variant-numeric:tabular-nums; }
  th:first-child, td:first-child { text-align:left; font-variant-numeric:normal; }
  thead th { color:var(--ink-2); font-weight:600; font-size:12px; position:sticky; top:0; background:var(--surface); }
  .tblwrap { overflow-x:auto; max-height:520px; overflow-y:auto; border:1px solid var(--ring); border-radius:12px; background:var(--surface); }
  button.toggle {
    font:inherit; font-size:13.5px; color:var(--ink); background:var(--surface);
    border:1px solid var(--axis); border-radius:8px; padding:7px 14px; cursor:pointer;
  }
  button.toggle:hover { border-color:var(--ink-2); }
  .caveat { background:var(--surface); border:1px solid var(--ring); border-left:3px solid var(--s2); border-radius:10px; padding:16px 20px; margin-bottom:12px; }
  .caveat h3 { font-size:14.5px; margin:0 0 5px; }
  .caveat p { margin:0; font-size:13.5px; color:var(--ink-2); }
  #tip {
    position:fixed; pointer-events:none; opacity:0; transition:opacity .09s;
    background:var(--surface); border:1px solid var(--axis); border-radius:8px;
    padding:8px 11px; font-size:12.5px; box-shadow:0 4px 16px rgba(0,0,0,.14); z-index:9;
    font-variant-numeric:tabular-nums; white-space:nowrap;
  }
  @media (max-width:640px){ .hero{gap:22px} .stat{border-left:0;padding-left:0} }
</style>

<div class="wrap">
<header>
  <h1>Italiensk mat i Norge, __FORSTE__–__SISTE__</h1>
  <p class="dek">Norsk import av matvarer fra Italia, hentet på varenummernivå fra SSBs
  utenrikshandelsstatistikk og gruppert i __ANTALL__ varegrupper. Alle beløp er i faste
  __SISTE__-kroner om ikke annet står.</p>
  <p class="kilde">Kilde: SSB tabell 08801 (varenummer × land), deflatert med tabell 08981.
  Hentet __HENTET__. Kontrollert mot SSBs publiserte SITC-aggregat (tabell 08809);
  største avvik __AVVIK__ % over 38 år.</p>
</header>

<div class="hero">
  <div>
    <div class="heroval">__HERO__ mrd</div>
    <div class="herolab">kroner brukt på mat og drikke fra Italia i __SISTE__, i faste kroner</div>
  </div>
  <div class="stat">
    <div class="statval">__VEKST__×</div>
    <div class="statlab">realvekst siden __FORSTE__</div>
  </div>
  <div class="stat">
    <div class="statval">__DEKN__ %</div>
    <div class="statlab">av verdien ligger i de __ANTALL__ gruppene<br>(resten er mest epler, druer og fersk frukt)</div>
  </div>
</div>

<section>
  <h2>Tolv varegrupper, hver sin kurve</h2>
  <p class="h2sub">Faste __SISTE__-kroner, __FORSTE__–__SISTE__. Hvert felt har sin egen y-akse —
  formen skal sammenlignes, ikke nivået, og nivået står som tall over kurven.
  Det <span style="color:var(--ink-2)">skraverte feltet</span> er år der gruppen
  omsatte for under 2 mill. kroner: for få forsendelser til at kurven måler noe.</p>
  <div class="grid" id="facets"></div>
</section>

<section>
  <h2>De tre kjernevarene</h2>
  <p class="h2sub">Ost, pasta og tomatprodukter — de tre gruppene som fantes i målbart
  omfang allerede i __FORSTE__, og derfor kan følges hele veien uten forbehold.</p>
  <div class="cardwide">
    <ul class="legend" id="legend3"></ul>
    <div id="kjerne"></div>
  </div>
</section>

<section>
  <h2>Forbehold</h2>
  <div id="caveats"></div>
</section>

<section>
  <h2>Tallene</h2>
  <p class="h2sub">Alle __ANTALL__ gruppene, per år, i faste kroner. Hold over en celle for løpende kroner og mengde.</p>
  <p style="margin:0 0 14px"><button class="toggle" id="tbtn" aria-expanded="false">Vis tabellen</button></p>
  <div class="tblwrap" id="tblwrap" hidden><table id="tbl"></table></div>
</section>
</div>
<div id="tip" role="status" aria-live="polite"></div>

<script>
const D = __DATA__;
const NS = "http://www.w3.org/2000/svg";
const el = (n, a={}) => { const e = document.createElementNS(NS, n);
  for (const k in a) e.setAttribute(k, a[k]); return e; };
const nf = n => n.toLocaleString("nb-NO", {maximumFractionDigits:0});
const kort = v => v >= 1e9 ? (v/1e9).toFixed(1).replace(".",",")+" mrd"
                : v >= 1e6 ? (v/1e6).toFixed(v>=1e7?0:1).replace(".",",")+" mill."
                : v >= 1e3 ? (v/1e3).toFixed(0)+" 000" : Math.round(v);

const tip = document.getElementById("tip");
function visTip(e, html){
  tip.innerHTML = html; tip.style.opacity = 1;
  const r = tip.getBoundingClientRect();
  let x = e.clientX + 14, y = e.clientY - r.height - 12;
  if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
  if (y < 8) y = e.clientY + 18;
  tip.style.left = x + "px"; tip.style.top = y + "px";
}
const skjulTip = () => tip.style.opacity = 0;

/* ---------- small multiples ---------- */
const W = 232, H = 96, PB = 18, PT = 8;
function facet(g){
  const card = document.createElement("div");
  card.className = "facet";
  const t = document.createElement("div");
  t.className = "ftitle"; t.textContent = g.navn;
  const v = document.createElement("div");
  v.className = "fval";
  v.textContent = kort(g.faste[g.faste.length-1]) + " kr i " + D.siste;
  card.append(t, v);

  const max = Math.max(...g.faste) || 1;
  const x = i => (i / (D.aarene.length - 1)) * W;
  const y = val => PT + (1 - val / max) * (H - PT - PB);

  const svg = el("svg", {viewBox:`0 0 ${W} ${H}`, role:"img",
    "aria-label":`${g.navn}: ${kort(g.faste[0])} kroner i ${D.forste}, ${kort(g.faste[g.faste.length-1])} kroner i ${D.siste}`});

  // skravert felt for de tynne arene
  if (g.solid && g.solid > D.forste){
    const bredde = x(D.aarene.indexOf(g.solid));
    svg.append(el("rect", {x:0, y:PT, width:Math.max(bredde,1), height:H-PT-PB,
      fill:"var(--tynn)", opacity:"0.55"}));
  }
  svg.append(el("line", {x1:0, y1:H-PB, x2:W, y2:H-PB, class:"axisline"}));

  const pts = g.faste.map((val,i) => [x(i), y(val)]);
  const dLine = pts.map((p,i)=>(i?"L":"M")+p[0].toFixed(1)+" "+p[1].toFixed(1)).join(" ");
  svg.append(el("path", {d:`${dLine} L ${W} ${H-PB} L 0 ${H-PB} Z`,
    fill:"var(--s1)", opacity:"0.10"}));
  svg.append(el("path", {d:dLine, fill:"none", stroke:"var(--s1)",
    "stroke-width":"2", "stroke-linejoin":"round", "stroke-linecap":"round"}));
  // sluttpunkt med 2px ring i flatefargen
  svg.append(el("circle", {cx:x(pts.length-1), cy:pts[pts.length-1][1], r:"4",
    fill:"var(--s1)", stroke:"var(--surface)", "stroke-width":"2"}));

  const t0 = el("text", {x:0, y:H-6, class:"tick"}); t0.textContent = D.forste;
  const t1 = el("text", {x:W, y:H-6, class:"tick", "text-anchor":"end"}); t1.textContent = D.siste;
  svg.append(t0, t1);

  // treffsone per ar, bredere enn marken
  const hit = el("rect", {x:0, y:0, width:W, height:H, fill:"transparent"});
  hit.style.cursor = "crosshair";
  const kryss = el("line", {y1:PT, y2:H-PB, stroke:"var(--axis)", "stroke-width":"1", opacity:"0"});
  const dot = el("circle", {r:"4", fill:"var(--s1)", stroke:"var(--surface)",
    "stroke-width":"2", opacity:"0"});
  svg.append(kryss, dot, hit);
  hit.addEventListener("pointermove", e => {
    const b = svg.getBoundingClientRect();
    const i = Math.round(((e.clientX-b.left)/b.width) * (D.aarene.length-1));
    const j = Math.max(0, Math.min(D.aarene.length-1, i));
    kryss.setAttribute("x1",x(j)); kryss.setAttribute("x2",x(j));
    kryss.setAttribute("opacity","1");
    dot.setAttribute("cx",x(j)); dot.setAttribute("cy",y(g.faste[j]));
    dot.setAttribute("opacity","1");
    const tynt = g.solid && D.aarene[j] < g.solid;
    visTip(e, `<b>${g.navn}</b><br>${D.aarene[j]}: ${nf(g.faste[j])} kr (faste)<br>
      <span style="color:var(--muted)">${nf(g.lopende[j])} kr løpende · ${nf(g.kg[j])} kg${
        g.liter && g.liter[j] != null ? " · " + nf(g.liter[j]) + " liter" : ""}</span>
      ${tynt ? '<br><span style="color:var(--muted)">for tynt til å måle</span>' : ''}`);
  });
  hit.addEventListener("pointerleave", () => {
    kryss.setAttribute("opacity","0"); dot.setAttribute("opacity","0"); skjulTip();
  });

  card.append(svg);
  // Alltid til stede, ogsa tom: reserverer hoyden slik at kortene i en rad
  // fortsatt har kurvene sine pa samme linje.
  const f = document.createElement("div");
  f.className = "fflag";
  f.textContent = g.tynn ? "tynt grunnlag " + g.tynn : "";
  card.append(f);
  return card;
}
const fw = document.getElementById("facets");
D.grupper.forEach(g => fw.append(facet(g)));

/* ---------- kjernevarene: 3 serier ---------- */
const KJERNE = [
  {id:"meieri",   navn:"Meieriprodukter (mest ost)", farge:"var(--s1)"},
  {id:"pasta",    navn:"Pasta og melprodukter",      farge:"var(--s2)"},
  {id:"gronnsaker",navn:"Bearbeidede grønnsaker (mest tomat)", farge:"var(--s3)"},
];
(function(){
  const w = 900, h = 340, ml = 62, mr = 168, mt = 14, mb = 34;
  const serier = KJERNE.map(k => ({...k, d: D.grupper.find(g=>g.id===k.id)}));
  const max = Math.max(...serier.flatMap(s => s.d.faste));
  const steg = Math.pow(10, Math.floor(Math.log10(max)));
  const topp = Math.ceil(max/steg)*steg;
  const x = i => ml + (i/(D.aarene.length-1))*(w-ml-mr);
  const y = v => mt + (1 - v/topp)*(h-mt-mb);

  const svg = el("svg", {viewBox:`0 0 ${w} ${h}`, role:"img",
    "aria-label":"Meieriprodukter, pasta og bearbeidede grønnsaker fra Italia, faste kroner"});
  for (let i=0;i<=4;i++){
    const v = topp*i/4;
    svg.append(el("line",{x1:ml,y1:y(v),x2:w-mr,y2:y(v),class: i? "gridline":"axisline"}));
    const tk = el("text",{x:ml-9,y:y(v)+3.5,class:"tick","text-anchor":"end"});
    tk.textContent = kort(v); svg.append(tk);
  }
  D.aarene.forEach((a,i) => { if (a%5===0 || i===D.aarene.length-1){
    const tk = el("text",{x:x(i),y:h-12,class:"tick","text-anchor":"middle"});
    tk.textContent = a; svg.append(tk);
  }});
  serier.forEach(s => {
    const pts = s.d.faste.map((v,i)=>[x(i),y(v)]);
    s._last = pts[pts.length-1];
    svg.append(el("path",{d:pts.map((p,i)=>(i?"L":"M")+p[0].toFixed(1)+" "+p[1].toFixed(1)).join(" "),
      fill:"none", stroke:s.farge, "stroke-width":"2",
      "stroke-linejoin":"round","stroke-linecap":"round"}));
    svg.append(el("circle",{cx:s._last[0],cy:s._last[1],r:"4",fill:s.farge,
      stroke:"var(--surface)","stroke-width":"2"}));
  });

  // Etikettene til hoyre kolliderer nar seriene lukker seg mot slutten (2025 skiller
  // gronnsaker og pasta med 39 mill. av en akse pa 600). A stable dem oppa hverandre
  // gjor dem uleselige; a dytte dem fra hverandre uten mer losriver dem fra kurven.
  // Losningen er a dytte OG tegne en tynn foringslinje tilbake til sluttpunktet.
  const LH = 30;                       // to tekstlinjer + luft
  const plassert = serier.map(s => ({s, y:s._last[1]})).sort((a,b)=>a.y-b.y);
  for (let i=1;i<plassert.length;i++)
    plassert[i].y = Math.max(plassert[i].y, plassert[i-1].y + LH);
  const overskudd = plassert[plassert.length-1].y - (h-mb);
  if (overskudd > 0) plassert.forEach(p => p.y -= overskudd);

  plassert.forEach(({s,y:ly}) => {
    const [lx,lyy] = s._last;
    svg.append(el("polyline",{
      points:`${lx+6},${lyy} ${lx+14},${lyy} ${lx+20},${ly} ${lx+28},${ly}`,
      fill:"none", stroke:s.farge, "stroke-width":"1.5",
      "stroke-linejoin":"round","stroke-linecap":"round", opacity:"0.85"}));
    const lab = el("text",{x:lx+34,y:ly-2,"font-size":"12.5",
      fill:"var(--ink)","font-weight":"600"});
    lab.textContent = kort(s.d.faste[s.d.faste.length-1]) + " kr";
    const lab2 = el("text",{x:lx+34,y:ly+12,"font-size":"11.5",fill:"var(--muted)"});
    lab2.textContent = s.navn.split(" (")[0];
    svg.append(lab, lab2);
  });

  const kryss = el("line",{y1:mt,y2:h-mb,stroke:"var(--axis)","stroke-width":"1",opacity:"0"});
  svg.append(kryss);
  const hit = el("rect",{x:ml,y:mt,width:w-ml-mr,height:h-mt-mb,fill:"transparent"});
  hit.style.cursor="crosshair"; svg.append(hit);
  hit.addEventListener("pointermove", e => {
    const b = svg.getBoundingClientRect();
    const px = (e.clientX-b.left)/b.width*w;
    const j = Math.max(0,Math.min(D.aarene.length-1,
      Math.round((px-ml)/((w-ml-mr)/(D.aarene.length-1)))));
    kryss.setAttribute("x1",x(j)); kryss.setAttribute("x2",x(j)); kryss.setAttribute("opacity","1");
    visTip(e, `<b>${D.aarene[j]}</b><br>` + serier.map(s =>
      `<span style="display:inline-block;width:9px;height:9px;border-radius:2px;background:${s.farge};margin-right:6px"></span>`+
      `${s.navn.split(" (")[0]}: ${nf(s.d.faste[j])} kr`).join("<br>"));
  });
  hit.addEventListener("pointerleave", ()=>{kryss.setAttribute("opacity","0"); skjulTip();});
  document.getElementById("kjerne").append(svg);

  const lg = document.getElementById("legend3");
  serier.forEach(s => { const li=document.createElement("li");
    li.innerHTML = `<span class="key" style="background:${s.farge}"></span>${s.navn}`;
    lg.append(li); });
})();

/* ---------- forbehold ---------- */
const FORBEHOLD = [
  ["Varenumrene er daterte, og flere varer bytter nummer underveis",
   "SSBs varekoder er HS-nummer pluss året versjonen trådte i kraft. Trøffel på glass "+
   "er 20032000 til 2011 og 20039010 fra 2012. Gruppene her er bygget på alle versjoner "+
   "av hvert nummer, men to av seriene har likevel hopp som faller sammen med en "+
   "tariffrevisjon — brød i 1995/96 og hermetisert sjømat i 1996/97."],
  ["Kapers og artisjokk kan ikke skilles etter 2006",
   "Fra 2007 slo tolltariffen sammen kapers, artisjokk og søte pepperfrukter til én "+
   "kode (20059901). Gruppen «oliven, kapers og artisjokk» er sammenlignbar hele veien, "+
   "men de tre kan bare skilles fra hverandre til og med 2006."],
  ["Nullene før 1995 er ekte, men de er politikk og ikke smak",
   "Spekemat og oliven ligger på null fram til midten av 1990-tallet. Spekeskinke var "+
   "null fra alle land til 1996 — det var veterinære importrestriksjoner, ikke "+
   "manglende interesse. Oliven importerte Norge allerede i 1988, bare fra Spania og "+
   "Hellas. Bruddet rundt 1994/95 følger EØS-avtalen."],
  ["Pesto, gnocchi og trøffelolje har ingen egen varelinje",
   "Pesto ligger i samlekoden 21039099 sammen med alle andre sauser som ikke er soya, "+
   "tomat, sennep eller majones. Gnocchi føres dels som pasta, dels som potetprodukt. "+
   "Trøffelolje og trøffelkrem er ikke med i trøffeltallet i det hele tatt. For disse "+
   "tre er tallene her et minimum."],
  ["Pizza er skilt ut av brødgruppen",
   "Ved første gjennomgang lå pizza og pizzabunner inne i «brød, kjeks og bakverk» "+
   "og utgjorde 69 % av den i __SISTE__ — 370 av 538 mill. Andelen var 29 % i 2015 og "+
   "67 % i 2020. Pizza har egne varenummer hele veien og er derfor lagt som egen "+
   "gruppe; «brød og kjeks» er nå det navnet sier."],
  ["Vin måles i liter, resten i kilo",
   "Vingruppen har egen literserie, men først fra 1989 — 1988-versjonene av "+
   "varenumrene registrerte ikke volum. År der en bidragsytende kode mangler "+
   "litermål er utelatt fra serien framfor å telles som null."],
  ["Landet er opprinnelsesland, og gruppene er ikke all italiensk mat",
   "Gruppene dekker __DEKN__ % av verdien i __SISTE__. Resten er i hovedsak fersk "+
   "frukt — epler alene er 422 mill. — druer, friske grønnsaker, ris og øl."],
];
const cw = document.getElementById("caveats");
FORBEHOLD.forEach(([h,p]) => { const d=document.createElement("div");
  d.className="caveat"; d.innerHTML=`<h3>${h}</h3><p>${p}</p>`; cw.append(d); });

/* ---------- tabellvisning ---------- */
(function(){
  const tbl = document.getElementById("tbl");
  const thead = document.createElement("thead");
  thead.innerHTML = "<tr><th>År</th>" + D.grupper.map(g=>`<th>${g.navn}</th>`).join("")
    + "<th>Alle matvarer</th></tr>";
  const tb = document.createElement("tbody");
  D.aarene.forEach((a,i) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${a}</td>` + D.grupper.map(g =>
      `<td title="${nf(g.lopende[i])} kr løpende · ${nf(g.kg[i])} kg${
        g.liter && g.liter[i] != null ? " · " + nf(g.liter[i]) + " liter" : ""}">${nf(g.faste[i])}</td>`).join("")
      + `<td>${nf(D.total_faste[i])}</td>`;
    tb.append(tr);
  });
  tbl.append(thead, tb);
  const btn = document.getElementById("tbtn"), wrap = document.getElementById("tblwrap");
  btn.addEventListener("click", () => {
    const vis = wrap.hasAttribute("hidden");
    wrap.toggleAttribute("hidden", !vis);
    btn.setAttribute("aria-expanded", String(vis));
    btn.textContent = vis ? "Skjul tabellen" : "Vis tabellen";
  });
})();
</script>
"""


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--inn", type=Path, default=CACHE / "ssb_italiensk_mat_italia.json")
    p.add_argument("--ut", type=Path, default=CACHE / "italiensk_mat.html")
    args = p.parse_args()

    d = json.loads(args.inn.read_text(encoding="utf-8"))
    args.ut.parent.mkdir(parents=True, exist_ok=True)
    args.ut.write_text(bygg(d), encoding="utf-8")
    print(f"✓ Side: {args.ut}")


if __name__ == "__main__":
    main()
