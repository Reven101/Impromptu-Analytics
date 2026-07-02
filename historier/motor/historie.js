/* Historie-malen: laster innhold/<id>/data.json + tekst.md og rendrer
   hero øverst → narrativ tekst → støttegrafer → kildekort.
   Én mal for alle historier — strukturen styres av innholdsfilene. */

import { parseTekst } from "./markdown.js";
import { lagVisning } from "./komponenter.js";

const PAKREVDE_METAFELT = [
  "tittel", "kilde", "kilde_url", "dato_hentet", "geografi",
  "enhet", "oppdateringsfrekvens", "beskrivelse",
];

function el(tag, klasse, tekst) {
  const e = document.createElement(tag);
  if (klasse) e.className = klasse;
  if (tekst !== undefined) e.textContent = tekst;
  return e;
}

function visFeil(melding) {
  const rot = document.getElementById("historie");
  rot.replaceChildren(el("div", "viz-feil", melding));
}

async function hent(sti, somJson) {
  const svar = await fetch(sti);
  if (!svar.ok) throw new Error(`Fant ikke ${sti} (${svar.status})`);
  return somJson ? svar.json() : svar.text();
}

function lagKildekort(meta) {
  const seksjon = el("section", "kildekort kort-flate");
  seksjon.appendChild(el("div", "eyebrow", "Om dataene"));
  const rute = el("dl", "kildekort-rute");
  const rader = [
    ["Kilde", meta.kilde],
    ["Geografi", meta.geografi],
    ["Enhet", meta.enhet],
    ["Oppdateres", meta.oppdateringsfrekvens],
    ["Hentet", meta.dato_hentet],
  ];
  for (const [etikett, verdi] of rader) {
    const boks = el("div");
    boks.appendChild(el("dt", "mono-etikett", etikett));
    boks.appendChild(el("dd", null, verdi));
    rute.appendChild(boks);
  }
  seksjon.appendChild(rute);
  const lenke = el("a", "kildekort-lenke", `Datasettet hos ${meta.kilde} →`);
  lenke.href = meta.kilde_url;
  lenke.rel = "noopener";
  seksjon.appendChild(lenke);
  return seksjon;
}

async function main() {
  const id = new URLSearchParams(location.search).get("id");
  if (!id || !/^[\w-]+$/.test(id)) {
    return visFeil("Mangler historie-id. Gå via forsiden.");
  }

  let data, tekst;
  try {
    [data, tekst] = await Promise.all([
      hent(`innhold/${id}/data.json`, true),
      hent(`innhold/${id}/tekst.md`, false),
    ]);
  } catch (e) {
    return visFeil(`Kunne ikke laste historien «${id}»: ${e.message}`);
  }

  const meta = data.meta || {};
  const mangler = PAKREVDE_METAFELT.filter((f) => !meta[f]);
  if (mangler.length) {
    return visFeil(`data.json bryter metadata-kontrakten — mangler: ${mangler.join(", ")}`);
  }

  document.title = `${meta.tittel} — Impromptu Analytics`;

  const rot = document.getElementById("historie");
  rot.replaceChildren();

  /* topptekst: eyebrow → tittel → ev. demodata-merke */
  const topp = el("header", "historie-topp");
  topp.appendChild(el("div", "eyebrow", `${meta.kilde} · ${meta.geografi}`));
  topp.appendChild(el("h1", null, meta.tittel));
  if (meta.demo) {
    const merke = el("div");
    merke.appendChild(el("span", "demo-merke", "Demodata — kjør pipelinen for ekte tall"));
    topp.appendChild(merke);
  }
  rot.appendChild(topp);

  /* brødtekst med innfelte visualiseringer; første viz = hero */
  let førsteViz = true;
  for (const blokk of parseTekst(tekst)) {
    if (blokk.viz) {
      const spec = (data.visninger || {})[blokk.viz];
      if (!spec) {
        rot.appendChild(el("div", "viz-feil", `Visningen «${blokk.viz}» finnes ikke i data.json`));
        continue;
      }
      const visning = lagVisning(spec, meta);
      if (førsteViz) visning.classList.add("er-hero");
      førsteViz = false;
      rot.appendChild(visning);
    } else {
      const prosa = el("div", "historie-prosa");
      prosa.innerHTML = blokk.html; /* trygt: markdown.js escaper all tekst */
      rot.appendChild(prosa);
    }
  }

  rot.appendChild(lagKildekort(meta));
}

main();
