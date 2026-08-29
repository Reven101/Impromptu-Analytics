/* ============================================================
   VISUALISERINGSKOMPONENTER
   Fem gjenbrukbare typer: hero, tidslinje, kart, verdenskart,
   kortgalleri.
   Alle er rent datadrevne: lagVisning(spec, meta) -> HTMLElement.
   Nye historier skal aldri trenge endringer her — bare nye
   data.json + tekst.md. Ny komponent legges til i REGISTER.
   ============================================================ */

import { escapeHtml } from "./markdown.js";
import { VERDEN, VERDEN_VIEWBOX } from "./verdensgeometri.js";

const nb = new Intl.NumberFormat("nb-NO");
const SERIE_FARGER = ["#0E7D59", "#A9761B", "#B23A28", "#3E6CB0", "#C05A6E", "#8A4A82"];
const RAMPE = ["#8FB6A6", "#699C88", "#47836D", "#2C6752", "#1A4C3B", "#0F3527"];

function el(tag, klasse, tekst) {
  const e = document.createElement(tag);
  if (klasse) e.className = klasse;
  if (tekst !== undefined) e.textContent = tekst;
  return e;
}

function formatVerdi(v, enhet) {
  const tall = typeof v === "number" ? nb.format(v) : String(v);
  return enhet ? `${tall} ${enhet}` : tall;
}

/* -- Delt tooltip (én per figur, følger peker/fokus) --------- */
function lagTooltip(beholder) {
  const t = el("div", "viz-tooltip");
  t.setAttribute("role", "status");
  t.hidden = true;
  beholder.appendChild(t);
  return {
    vis(x, y, rader) {
      t.replaceChildren();
      for (const rad of rader) {
        const r = el("div", "viz-tooltip-rad");
        if (rad.farge) {
          const strek = el("span", "viz-tooltip-strek");
          strek.style.background = rad.farge;
          r.appendChild(strek);
        }
        r.appendChild(el("strong", null, rad.verdi));
        r.appendChild(el("span", null, rad.etikett));
        t.appendChild(r);
      }
      t.hidden = false;
      const bb = beholder.getBoundingClientRect();
      const tb = t.getBoundingClientRect();
      t.style.left = Math.max(4, Math.min(x - tb.width / 2, bb.width - tb.width - 4)) + "px";
      t.style.top = Math.max(4, y - tb.height - 14) + "px";
    },
    skjul() { t.hidden = true; },
  };
}

/* -- Tabellvisning (WCAG-tvilling for alle figurer) ---------- */
function lagTabell(kolonner, rader) {
  const detaljer = el("details", "viz-tabell");
  detaljer.appendChild(el("summary", null, "Vis tallene som tabell"));
  const tabell = el("table");
  const thead = el("thead");
  const hr = el("tr");
  for (const k of kolonner) hr.appendChild(el("th", null, k));
  thead.appendChild(hr);
  tabell.appendChild(thead);
  const tbody = el("tbody");
  for (const rad of rader) {
    const tr = el("tr");
    for (const c of rad) tr.appendChild(el("td", null, typeof c === "number" ? nb.format(c) : String(c)));
    tbody.appendChild(tr);
  }
  tabell.appendChild(tbody);
  detaljer.appendChild(tabell);
  return detaljer;
}

function figurRamme(spec) {
  const fig = el("figure", "viz-figur kort-flate");
  if (spec.tittel) {
    const cap = el("figcaption");
    cap.appendChild(el("div", "mono-etikett", spec.undertekst || ""));
    cap.appendChild(el("div", "viz-tittel", spec.tittel));
    fig.appendChild(cap);
  }
  return fig;
}

/* ============================================================
   1. HERO — stort oppslag øverst. To moduser:
      - interaktiv: kontroll (select) + oppslag pr. nøkkel
      - statisk: faste rader
   ============================================================ */
function lagHero(spec) {
  const seksjon = el("section", "viz-hero kort-flate");

  if (spec.eyebrow) seksjon.appendChild(el("div", "eyebrow", spec.eyebrow));
  if (spec.sporsmal) seksjon.appendChild(el("h2", "viz-hero-sporsmal", spec.sporsmal));

  const resultat = el("div", "viz-hero-resultat");

  function visRader(rader) {
    resultat.replaceChildren();
    for (const rad of rader || []) {
      const boks = el("div", "viz-hero-boks");
      boks.appendChild(el("div", "mono-etikett", rad.etikett || ""));
      boks.appendChild(el("div", "viz-hero-verdi", rad.verdi));
      if (rad.detalj) boks.appendChild(el("div", "viz-hero-detalj", rad.detalj));
      resultat.appendChild(boks);
    }
  }

  if (spec.kontroll && spec.oppslag) {
    const skjema = el("div", "viz-hero-kontroll");
    const id = "hero-" + Math.random().toString(36).slice(2, 8);
    const etikett = el("label", "mono-etikett", spec.kontroll.etikett);
    etikett.setAttribute("for", id);
    const velger = el("select");
    velger.id = id;
    const nokler = Object.keys(spec.oppslag).sort((a, b) => b.localeCompare(a, "nb", { numeric: true }));
    for (const n of nokler) {
      const o = el("option", null, n);
      o.value = n;
      velger.appendChild(o);
    }
    velger.value = spec.kontroll.standard && spec.oppslag[spec.kontroll.standard]
      ? spec.kontroll.standard : nokler[0];
    velger.addEventListener("change", () => visRader(spec.oppslag[velger.value]?.rader));
    skjema.appendChild(etikett);
    skjema.appendChild(velger);
    seksjon.appendChild(skjema);
    seksjon.appendChild(resultat);
    visRader(spec.oppslag[velger.value]?.rader);
  } else {
    seksjon.appendChild(resultat);
    visRader(spec.rader);
  }

  if (spec.fotnote) seksjon.appendChild(el("div", "viz-hero-fotnote", spec.fotnote));
  return seksjon;
}

/* ============================================================
   2. TIDSLINJE — SVG-graf. stil: "linje" (flerserie) eller
      "søyle" (én serie). Crosshair + tooltip, direktelabels på
      linjeender, legend ved ≥ 2 serier, tabelltvilling.
   ============================================================ */
const SVG_NS = "http://www.w3.org/2000/svg";
function svgEl(tag, attrs) {
  const e = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  return e;
}

function fineTicks(maks) {
  const rå = maks / 4;
  const tiPotens = Math.pow(10, Math.floor(Math.log10(rå)));
  const steg = [1, 2, 2.5, 5, 10].map((s) => s * tiPotens).find((s) => maks / s <= 4.5) || tiPotens * 10;
  const antall = Math.ceil(maks / steg); /* øverste gridlinje skal dekke maksverdien */
  return Array.from({ length: antall + 1 }, (_, i) => Math.round(i * steg * 100) / 100);
}

function kompakt(v) {
  if (Math.abs(v) >= 1_000_000) return nb.format(Math.round(v / 100_000) / 10).replace(",0", "") + " mill.";
  if (Math.abs(v) >= 10_000) return nb.format(Math.round(v / 1000)) + " k";
  return nb.format(v);
}

function lagTidslinje(spec, meta) {
  const fig = figurRamme({ ...spec, undertekst: spec.undertekst || spec.enhet || meta.enhet });
  const serier = spec.serier || [];
  const stil = spec.stil || "linje";

  const B = 760, H = 380;
  const M = { topp: 18, hoyre: stil === "linje" && serier.length ? 108 : 20, bunn: 40, venstre: 56 };
  const pb = B - M.venstre - M.hoyre, ph = H - M.topp - M.bunn;

  const alleX = serier.flatMap((s) => s.punkter.map((p) => p[0]));
  const alleY = serier.flatMap((s) => s.punkter.map((p) => p[1]));
  let xMin = Math.min(...alleX), xMax = Math.max(...alleX);
  if (stil === "søyle") {
    /* innrykk så ytterste søyler ikke henger utenfor plotteområdet */
    const punktAvstand = (xMax - xMin) / Math.max(1, alleX.length - 1);
    xMin -= punktAvstand / 2;
    xMax += punktAvstand / 2;
  }
  const yMaksData = Math.max(...alleY);
  const yTicks = fineTicks(yMaksData);
  const yMaks = yTicks[yTicks.length - 1];

  const sx = (x) => M.venstre + ((x - xMin) / (xMax - xMin || 1)) * pb;
  const sy = (y) => M.topp + ph - (y / yMaks) * ph;

  const svg = svgEl("svg", { viewBox: `0 0 ${B} ${H}`, class: "viz-svg", role: "img" });
  svg.appendChild(svgEl("title")).textContent = spec.tittel || "Tidslinje";

  /* gridlinjer: solide hårlinjer, recessive */
  for (const t of yTicks) {
    svg.appendChild(svgEl("line", { x1: M.venstre, x2: B - M.hoyre, y1: sy(t), y2: sy(t), class: "viz-grid" }));
    const lbl = svgEl("text", { x: M.venstre - 8, y: sy(t) + 4, class: "viz-akse", "text-anchor": "end" });
    lbl.textContent = kompakt(t);
    svg.appendChild(lbl);
  }

  /* x-akse: årstall hvert ~tiår */
  const span = xMax - xMin;
  const xSteg = span > 60 ? 20 : span > 25 ? 10 : span > 10 ? 5 : 1;
  for (let x = Math.ceil(xMin / xSteg) * xSteg; x <= xMax; x += xSteg) {
    const lbl = svgEl("text", { x: sx(x), y: H - M.bunn + 22, class: "viz-akse", "text-anchor": "middle" });
    lbl.textContent = x;
    svg.appendChild(lbl);
  }

  const beholder = el("div", "viz-plott");
  beholder.appendChild(svg);
  const tooltip = lagTooltip(beholder);

  if (stil === "søyle") {
    const s = serier[0];
    const n = s.punkter.length;
    const bredde = Math.min(24, (pb / n) * 0.72);
    const maksP = s.punkter.reduce((a, p) => (p[1] > a[1] ? p : a));
    for (const [x, y] of s.punkter) {
      const h = Math.max(0, sy(0) - sy(y));
      const r = Math.min(4, bredde / 2, h);
      /* 4px avrundet data-ende, kvadratisk mot grunnlinjen */
      const cx = sx(x) - bredde / 2, topp = sy(y);
      const bane = svgEl("path", {
        d: `M ${cx} ${sy(0)} V ${topp + r} Q ${cx} ${topp} ${cx + r} ${topp} H ${cx + bredde - r} Q ${cx + bredde} ${topp} ${cx + bredde} ${topp + r} V ${sy(0)} Z`,
        fill: SERIE_FARGER[0], class: "viz-soyle", tabindex: "0",
      });
      const visT = () => tooltip.vis(
        (sx(x) / B) * beholder.clientWidth, (topp / H) * beholder.clientHeight,
        [{ verdi: formatVerdi(y, spec.enhet), etikett: String(x), farge: SERIE_FARGER[0] }]);
      bane.addEventListener("pointerenter", visT);
      bane.addEventListener("focus", visT);
      bane.addEventListener("pointerleave", tooltip.skjul);
      bane.addEventListener("blur", tooltip.skjul);
      svg.appendChild(bane);
      if (x === maksP[0]) {
        const lbl = svgEl("text", { x: sx(x), y: topp - 8, class: "viz-direkte", "text-anchor": "middle" });
        lbl.textContent = kompakt(y);
        svg.appendChild(lbl);
      }
    }
  } else {
    serier.forEach((s, i) => {
      const farge = SERIE_FARGER[i % SERIE_FARGER.length];
      const d = s.punkter.map((p, j) => `${j ? "L" : "M"} ${sx(p[0])} ${sy(p[1])}`).join(" ");
      svg.appendChild(svgEl("path", { d, fill: "none", stroke: farge, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
      const siste = s.punkter[s.punkter.length - 1];
      /* endepunkt med 2px kort-farget ring */
      svg.appendChild(svgEl("circle", { cx: sx(siste[0]), cy: sy(siste[1]), r: 4.5, fill: farge, stroke: "#FBF8F0", "stroke-width": 2 }));
    });

    /* direktelabels på linjeender, med kollisjonsdytt */
    const ender = serier.map((s, i) => ({
      navn: s.navn, farge: SERIE_FARGER[i % SERIE_FARGER.length],
      y: sy(s.punkter[s.punkter.length - 1][1]),
    })).sort((a, b) => a.y - b.y);
    for (let i = 1; i < ender.length; i++) {
      if (ender[i].y - ender[i - 1].y < 16) ender[i].y = ender[i - 1].y + 16;
    }
    if (serier.length <= 4) {
      for (const e of ender) {
        const lbl = svgEl("text", { x: B - M.hoyre + 12, y: e.y + 4, class: "viz-direkte" });
        lbl.textContent = e.navn;
        svg.appendChild(lbl);
        svg.appendChild(svgEl("line", { x1: B - M.hoyre + 2, x2: B - M.hoyre + 9, y1: e.y, y2: e.y, stroke: e.farge, "stroke-width": 2 }));
      }
    }

    /* crosshair + samle-tooltip: nærmeste x, alle serier */
    const hår = svgEl("line", { y1: M.topp, y2: H - M.bunn, class: "viz-crosshair" });
    hår.style.display = "none";
    svg.appendChild(hår);
    const xVerdier = [...new Set(alleX)].sort((a, b) => a - b);
    svg.addEventListener("pointermove", (ev) => {
      const rekt = svg.getBoundingClientRect();
      const px = ((ev.clientX - rekt.left) / rekt.width) * B;
      const dataX = xMin + ((px - M.venstre) / pb) * (xMax - xMin);
      const nærmest = xVerdier.reduce((a, b) => (Math.abs(b - dataX) < Math.abs(a - dataX) ? b : a));
      hår.setAttribute("x1", sx(nærmest));
      hår.setAttribute("x2", sx(nærmest));
      hår.style.display = "";
      const rader = serier.map((s, i) => {
        const p = s.punkter.find((q) => q[0] === nærmest);
        return p && {
          verdi: nb.format(p[1]), etikett: s.navn || String(nærmest),
          farge: SERIE_FARGER[i % SERIE_FARGER.length],
        };
      }).filter(Boolean);
      tooltip.vis((sx(nærmest) / B) * beholder.clientWidth, (M.topp / H) * beholder.clientHeight + 20,
        [{ verdi: String(nærmest), etikett: "" }, ...rader]);
    });
    svg.addEventListener("pointerleave", () => { hår.style.display = "none"; tooltip.skjul(); });
  }

  fig.appendChild(beholder);

  /* legend ved ≥ 2 serier (én serie: tittelen sier hva som vises) */
  if (stil === "linje" && serier.length >= 2) {
    const legend = el("div", "viz-legend");
    serier.forEach((s, i) => {
      const rad = el("span", "viz-legend-rad");
      const strek = el("span", "viz-tooltip-strek");
      strek.style.background = SERIE_FARGER[i % SERIE_FARGER.length];
      rad.appendChild(strek);
      rad.appendChild(document.createTextNode(s.navn));
      legend.appendChild(rad);
    });
    fig.appendChild(legend);
  }

  const xNavn = spec.x_navn || "År";
  fig.appendChild(lagTabell(
    [xNavn, ...serier.map((s) => s.navn || spec.enhet || meta.enhet || "Verdi")],
    [...new Set(alleX)].sort((a, b) => a - b).map((x) => [
      x, ...serier.map((s) => s.punkter.find((p) => p[0] === x)?.[1] ?? "–"),
    ])
  ));
  return fig;
}

/* ============================================================
   3. KART — stilisert rutenett av norske fylker (2024-inndeling).
      Sekvensiell rampe (validert), tooltip pr. flis, tabelltvilling.
      Verdier kan nøkles på fylkesnavn eller fylkesnummer.
   ============================================================ */
const FYLKER = [
  { navn: "Finnmark", nr: "56", kort: "FIN", kol: 5, rad: 1 },
  { navn: "Troms", nr: "55", kort: "TRO", kol: 4, rad: 2 },
  { navn: "Nordland", nr: "18", kort: "NOR", kol: 3, rad: 3 },
  { navn: "Trøndelag", nr: "50", kort: "TRØ", kol: 2, rad: 4 },
  { navn: "Møre og Romsdal", nr: "15", kort: "M&R", kol: 1, rad: 5 },
  { navn: "Innlandet", nr: "34", kort: "INN", kol: 3, rad: 5 },
  { navn: "Vestland", nr: "46", kort: "VLD", kol: 1, rad: 6 },
  { navn: "Buskerud", nr: "33", kort: "BUS", kol: 2, rad: 6 },
  { navn: "Oslo", nr: "03", kort: "OSL", kol: 3, rad: 6 },
  { navn: "Akershus", nr: "32", kort: "AKH", kol: 4, rad: 6 },
  { navn: "Rogaland", nr: "11", kort: "ROG", kol: 1, rad: 7 },
  { navn: "Telemark", nr: "40", kort: "TEL", kol: 2, rad: 7 },
  { navn: "Vestfold", nr: "39", kort: "VFD", kol: 3, rad: 7 },
  { navn: "Østfold", nr: "31", kort: "ØST", kol: 4, rad: 7 },
  { navn: "Agder", nr: "42", kort: "AGD", kol: 2, rad: 8 },
];

function lagKart(spec, meta) {
  const fig = figurRamme({ ...spec, undertekst: spec.undertekst || spec.enhet || meta.enhet });
  const verdier = spec.verdier || {};
  const finn = (f) => verdier[f.navn] ?? verdier[f.nr];

  const tall = FYLKER.map(finn).filter((v) => typeof v === "number");
  const min = Math.min(...tall), maks = Math.max(...tall);
  const trinn = (v) => Math.min(RAMPE.length - 1, Math.floor(((v - min) / (maks - min || 1)) * RAMPE.length));
  /* etiketten inne i flisen velger blekk/hvit etter fyllets lyshet */
  const lys = (hex) => {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };

  const ytre = el("div", "viz-kart-ytre");
  const rute = el("div", "viz-kart");
  const tooltip = lagTooltip(ytre);

  for (const f of FYLKER) {
    const v = finn(f);
    const flis = el("button", "viz-flis", f.kort);
    flis.type = "button";
    flis.style.gridColumn = f.kol;
    flis.style.gridRow = f.rad;
    flis.setAttribute("aria-label", `${f.navn}: ${v === undefined ? "ingen data" : formatVerdi(v, spec.enhet || meta.enhet)}`);
    if (typeof v === "number") {
      const farge = RAMPE[trinn(v)];
      flis.style.background = farge;
      flis.style.color = lys(farge) > 0.45 ? "#27332D" : "#FBF8F0";
    } else {
      flis.classList.add("viz-flis-tom");
    }
    const visT = () => {
      const rb = ytre.getBoundingClientRect(), fb = flis.getBoundingClientRect();
      tooltip.vis(fb.left - rb.left + fb.width / 2, fb.top - rb.top,
        [{ verdi: v === undefined ? "ingen data" : formatVerdi(v, spec.enhet || meta.enhet), etikett: f.navn }]);
    };
    flis.addEventListener("pointerenter", visT);
    flis.addEventListener("focus", visT);
    flis.addEventListener("pointerleave", tooltip.skjul);
    flis.addEventListener("blur", tooltip.skjul);
    rute.appendChild(flis);
  }
  ytre.appendChild(rute);

  /* fargeskala-legend */
  const legend = el("div", "viz-kart-legend");
  legend.appendChild(el("span", "mono-etikett", kompakt(min)));
  const skala = el("span", "viz-kart-skala");
  for (const farge of RAMPE) {
    const s = el("span");
    s.style.background = farge;
    skala.appendChild(s);
  }
  legend.appendChild(skala);
  legend.appendChild(el("span", "mono-etikett", kompakt(maks)));
  ytre.appendChild(legend);

  fig.appendChild(ytre);
  fig.appendChild(lagTabell(
    ["Fylke", spec.enhet || meta.enhet || "Verdi"],
    FYLKER.map((f) => [f.navn, finn(f) ?? "–"]).sort((a, b) => (b[1] || 0) - (a[1] || 0))
  ));
  return fig;
}

/* ============================================================
   4. VERDENSKART — koroplett over landomriss, nøklet på ISO2.

   Geometrien er generert av pipeline/lag_verdensgeometri.py og
   ligger ferdig projisert i verdensgeometri.js. Ingen projeksjon
   skjer her; komponenten maler `d`-strenger.

   MERK: et koroplettkart vekter etter AREAL. Bruk det til
   tidspunkt og rater — ikke til volum, der Russland ville
   dominert et bilde Norge egentlig eier.
   ============================================================ */

function lagVerdenskart(spec, meta) {
  const fig = figurRamme({ ...spec, undertekst: spec.undertekst || spec.enhet || meta.enhet });
  const verdier = spec.verdier || {};
  const enhet = spec.enhet || meta.enhet;

  const tall = Object.values(verdier).filter((v) => typeof v === "number");
  const sortert = tall.slice().sort((a, b) => a - b);
  const min = sortert[0], maks = sortert[sortert.length - 1];

  /* Skala: logaritmisk som standard, ikke lineær.

     Landtall spenner nesten alltid over flere størrelsesordener. Med spennet
     1-147 år og median 114 legger en lineær skala 25 land i det laveste
     trinnet: Norge (1 år) og Russland (16 år) får samme farge, og hele Europa
     blir én flate. Kvantiler jevner ut antallet, men skiller fortsatt ikke 1
     fra 16. Logaritmen gjør det, fordi den måler forhold og ikke differanser
     — og forskjellen mellom ett og seksten år ER større enn mellom 130 og 145.

     Prisen er at trinnene dekker ulike spenn, så legenden må skrive ut hver
     grense. En jevn rampe merket bare «1» og «147» ville lovet en lineær
     skala vi ikke har. */
  const skalatype = spec.skala || (min > 0 ? "log" : "kvantil");
  const grenser = [];
  if (skalatype === "log") {
    const lo = Math.log(min), hi = Math.log(maks);
    for (let i = 1; i < RAMPE.length; i++) {
      grenser.push(Math.exp(lo + ((hi - lo) * i) / RAMPE.length));
    }
  } else if (skalatype === "kvantil") {
    for (let i = 1; i < RAMPE.length; i++) {
      grenser.push(sortert[Math.min(sortert.length - 1,
        Math.floor((i / RAMPE.length) * sortert.length))]);
    }
  } else {
    for (let i = 1; i < RAMPE.length; i++) {
      grenser.push(min + ((maks - min) * i) / RAMPE.length);
    }
  }
  const trinn = (v) => {
    let i = 0;
    while (i < grenser.length && v >= grenser[i]) i++;
    return i;
  };

  const ytre = el("div", "viz-kart-ytre");
  const tooltip = lagTooltip(ytre);

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", VERDEN_VIEWBOX);
  svg.setAttribute("class", "viz-verdenskart");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", spec.tittel || "Verdenskart");

  for (const [kode, d] of Object.entries(VERDEN)) {
    const v = verdier[kode];
    const bane = document.createElementNS("http://www.w3.org/2000/svg", "path");
    bane.setAttribute("d", d);
    bane.setAttribute("class", typeof v === "number" ? "viz-land" : "viz-land viz-land-tom");
    if (typeof v === "number") bane.style.fill = RAMPE[trinn(v)];
    /* Landnavnet kommer fra data.json når det finnes der; ellers står koden.
       Geometrifila bærer ingen navn — den skal være ren geometri. */
    const navn = (spec.navn && spec.navn[kode]) || kode;
    const visT = (ev) => {
      const rb = ytre.getBoundingClientRect();
      tooltip.vis(ev.clientX - rb.left, ev.clientY - rb.top,
        [{ verdi: v === undefined ? "ingen registrert" : formatVerdi(v, enhet), etikett: navn }]);
    };
    bane.addEventListener("pointerenter", visT);
    bane.addEventListener("pointermove", visT);
    bane.addEventListener("pointerleave", tooltip.skjul);
    svg.appendChild(bane);
  }
  ytre.appendChild(svg);

  const legend = el("div", "viz-kart-legend");
  /* Med kvantiler er svakhetene ulikt brede, så grensene må stå under dem.
     «1 – 147» over en jevn rampe ville lovet en lineær skala vi ikke har. */
  const trapp = el("div", "viz-kart-trapp");
  const skala = el("span", "viz-kart-skala");
  for (const farge of RAMPE) {
    const s = el("span");
    s.style.background = farge;
    skala.appendChild(s);
  }
  trapp.appendChild(skala);
  const merker = el("div", "viz-kart-merker");
  for (const v of [min, ...grenser, maks]) {
    merker.appendChild(el("span", "mono-etikett", kompakt(Math.round(v))));
  }
  trapp.appendChild(merker);
  legend.appendChild(trapp);
  /* Umalte land betyr «ingen registrert oppsetning», ikke «ingen oppsetning».
     Forskjellen er hele forbeholdet i spredningshistorien, og den hører hjemme
     i legenden framfor bare i brødteksten. */
  if (spec.tom_etikett) {
    const tom = el("span", "viz-kart-tom-nokkel");
    tom.appendChild(el("span", "viz-kart-tom-rute"));
    tom.appendChild(el("span", "mono-etikett", spec.tom_etikett));
    legend.appendChild(tom);
  }
  ytre.appendChild(legend);

  fig.appendChild(ytre);
  /* `antall` er valgfritt og sier hvor mange observasjoner hvert lands verdi
     hviler på. Et kart kan ikke vise det — alle flater ser like sikre ut — så
     tabellen er stedet leseren kan se at Norges median bygger på 28 verk og
     Qatars på ett. */
  const harAntall = spec.antall && Object.keys(spec.antall).length;
  fig.appendChild(lagTabell(
    harAntall ? ["Land", enhet || "Verdi", spec.antall_navn || "Antall"]
              : ["Land", enhet || "Verdi"],
    Object.entries(verdier)
      .map(([kode, v]) => {
        const navn = (spec.navn && spec.navn[kode]) || kode;
        return harAntall ? [navn, v, spec.antall[kode] ?? "–"] : [navn, v];
      })
      .sort((a, b) => (a[1] || 0) - (b[1] || 0))
  ));
  return fig;
}

/* ============================================================
   5. KORTGALLERI — rutenett av fakta-kort.
   ============================================================ */
function lagKortgalleri(spec) {
  const fig = figurRamme(spec);
  const rute = el("div", "viz-kortrute");
  for (const kort of spec.kort || []) {
    const k = el("div", "viz-kort");
    if (kort.overtittel) k.appendChild(el("div", "mono-etikett", kort.overtittel));
    k.appendChild(el("div", "viz-kort-verdi", kort.verdi));
    if (kort.detalj) k.appendChild(el("div", "viz-kort-detalj", kort.detalj));
    rute.appendChild(k);
  }
  fig.appendChild(rute);
  return fig;
}

/* ============================================================
   6. RANGERING — liggende sorterte søyler for kategorisammenligning.
      Tidslinjen er numerisk x/y og kortgalleriet er tekst; en rangert
      sammenligning av kategorier (oppdragsgivere, temaer, trinnene i en
      trakt) hadde ingen form før denne.

      Én farge for alle søyler. Fargen følger entiteten, aldri rangen —
      en gradient nedover lista ville kodet rekkefølgen to ganger, og
      lengden gjør allerede den jobben. `fremhev` maler navngitte rader
      i serie 2: det er identitet («dette er saken vår»), ikke rang.

      Fargevalidering av paret serie-1/serie-2 mot kortflaten (#FBF8F0):
      lyshet, kroma og kontrast passerer; CVD-separasjonen er ΔE 7,7 for
      protanopi — i gulvbåndet 6–8, som er lovlig BARE med en annen
      kanal ved siden av fargen. Den har vi: hver søyle bærer sitt eget
      kategorinavn til venstre og sin egen verdi til høyre, så identitet
      hviler aldri på farge alene. Fjernes direktelabelene, faller den
      begrunnelsen bort.
   ============================================================ */
function kutt(tekst, n) {
  const t = String(tekst ?? "");
  return t.length > n ? t.slice(0, n - 1) + "…" : t;
}

function lagRangering(spec, meta) {
  const fig = figurRamme({ ...spec, undertekst: spec.undertekst || spec.enhet || meta.enhet });

  /* Sorteres synkende som standard. En trakt (publisert → navngitt → vedtatt)
     har semantisk rekkefølge og setter "sorter": false — der er rekkefølgen
     poenget, ikke størrelsen. */
  const rader = [...(spec.rader || [])];
  if (spec.sorter !== false) rader.sort((a, b) => (b.verdi ?? 0) - (a.verdi ?? 0));

  const fremhev = new Set(spec.fremhev || []);
  const enhet = spec.enhet || meta.enhet || "";

  const B = 760, RAD = 30, SOYLE = 18;   /* 30 − 18 = 12px luft mellom søylene */
  const M = { topp: 10, hoyre: 84, bunn: 34, venstre: 232 };
  const H = M.topp + rader.length * RAD + M.bunn;
  const pb = B - M.venstre - M.hoyre;

  const maks = Math.max(1, ...rader.map((r) => r.verdi ?? 0));
  /* fineTicks legger øverste gridlinje PÅ eller OVER maksverdien. Skalerer vi mot
     datamaksimum, havner den siste tikkmerkelappen utenfor plottet og blir klippet.
     Skalaen går derfor til øverste tikk, ikke til største søyle. */
  const ticks = fineTicks(maks);
  const skalaMaks = Math.max(maks, ...ticks);
  const sx = (v) => M.venstre + (Math.max(0, v) / skalaMaks) * pb;
  const sy = (i) => M.topp + i * RAD + (RAD - SOYLE) / 2;

  const svg = svgEl("svg", { viewBox: `0 0 ${B} ${H}`, class: "viz-svg", role: "img" });
  svg.appendChild(svgEl("title")).textContent = spec.tittel || "Rangering";

  /* loddrette gridlinjer — recessive, og de eneste akse-hjelpemidlene figuren har */
  for (const t of ticks) {
    svg.appendChild(svgEl("line", {
      x1: sx(t), x2: sx(t), y1: M.topp, y2: H - M.bunn, class: "viz-grid",
    }));
    const lbl = svgEl("text", { x: sx(t), y: H - M.bunn + 20, class: "viz-akse", "text-anchor": "middle" });
    lbl.textContent = kompakt(t);
    svg.appendChild(lbl);
  }

  const beholder = el("div", "viz-plott viz-rangering");
  beholder.appendChild(svg);
  const tooltip = lagTooltip(beholder);

  rader.forEach((rad, i) => {
    const verdi = rad.verdi ?? 0;
    const farge = fremhev.has(rad.navn) ? SERIE_FARGER[1] : SERIE_FARGER[0];
    const y = sy(i), x0 = M.venstre, x1 = sx(verdi);
    const r = Math.min(4, SOYLE / 2, Math.max(0, x1 - x0));

    /* 4px avrundet data-ende, kvadratisk mot grunnlinjen — samme grep som søylene
       i tidslinjen, speilvendt fordi søyla ligger. */
    const bane = svgEl("path", {
      d: `M ${x0} ${y} H ${x1 - r} Q ${x1} ${y} ${x1} ${y + r} V ${y + SOYLE - r} `
       + `Q ${x1} ${y + SOYLE} ${x1 - r} ${y + SOYLE} H ${x0} Z`,
      fill: farge, class: "viz-soyle", tabindex: "0",
    });
    const visT = () => tooltip.vis(
      (x1 / B) * beholder.clientWidth, ((y + SOYLE) / H) * beholder.clientHeight,
      [{ verdi: formatVerdi(verdi, enhet), etikett: rad.navn, farge },
       ...(rad.detalj ? [{ verdi: "", etikett: rad.detalj }] : [])]);
    bane.addEventListener("pointerenter", visT);
    bane.addEventListener("focus", visT);
    bane.addEventListener("pointerleave", tooltip.skjul);
    bane.addEventListener("blur", tooltip.skjul);
    svg.appendChild(bane);

    /* Kategorinavnet står som etikett til venstre, ikke i en legend: én serie,
       og et navn per søyle er direktelabeling, ikke støy. SVG bryter ikke tekst,
       så lange virksomhetsnavn kuttes — hele navnet ligger i tooltip og tabell. */
    const navn = svgEl("text", {
      x: M.venstre - 10, y: y + SOYLE / 2 + 4, class: "viz-akse", "text-anchor": "end",
    });
    navn.textContent = kutt(rad.navn, 30);
    navn.appendChild(svgEl("title")).textContent = rad.navn || "";
    svg.appendChild(navn);

    const tall = svgEl("text", {
      x: x1 + 8, y: y + SOYLE / 2 + 4, class: "viz-direkte", "text-anchor": "start",
    });
    tall.textContent = kompakt(verdi);
    svg.appendChild(tall);
  });

  fig.appendChild(beholder);
  fig.appendChild(lagTabell(
    [spec.x_navn || "Kategori", enhet || "Verdi", ...(rader.some((r) => r.detalj) ? ["Merknad"] : [])],
    rader.map((r) => [r.navn, r.verdi ?? "–", ...(rader.some((x) => x.detalj) ? [r.detalj || "–"] : [])])
  ));
  return fig;
}

/* ============================================================
   REGISTER + fabrikk
   ============================================================ */
const REGISTER = {
  hero: lagHero,
  tidslinje: lagTidslinje,
  kart: lagKart,
  verdenskart: lagVerdenskart,
  kortgalleri: lagKortgalleri,
  rangering: lagRangering,
};

export function lagVisning(spec, meta) {
  const fabrikk = REGISTER[spec?.type];
  if (!fabrikk) {
    const feil = el("div", "viz-feil", `Ukjent visningstype: ${escapeHtml(spec?.type)}`);
    return feil;
  }
  return fabrikk(spec, meta || {});
}
