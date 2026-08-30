"""Lager en frittstående diagramside av snapshotet fra hent_ssb_matimport.py.

Kjøring:

    python pipeline/hent_ssb_matimport.py --html
    python pipeline/lag_matimport_side.py pipeline/cache/ssb_matimport_italia.json

Siden er én selvforsynt HTML-fil (ingen bygg, ingen CDN) i husets tokens fra
historier/motor/tokens.css. Den er et arbeidsdokument for å se på tallene — skal
de publiseres, går de gjennom motoren og kontrakten som alle andre historier.

Diagramvalg: tidsserien er en linje (endring over tid, to serier → tegnforklaring
+ direkte etiketter), sammensetningen er liggende stolper sortert etter størrelse
(rangering av magnitude → én kulør, verdien direkte på stolpen). Ingen tofarget
akse, ingen kakediagram, ingen farge som eneste bærer av identitet.
"""

from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

import kontrakt  # noqa: F401  — importen setter UTF-8 på Windows-konsollen
from hent_ssb_matimport import kroner

# (nøkkel, tegnforklaring, kort direkte etikett i diagrammet, seriefarge).
# Fargene er husets --serie-1 og --serie-2 i fast rekkefølge. Paret ligger på
# ΔE 7,7 for protanopi — innenfor gulvet, men KUN fordi begge linjene også har
# direkte etikett ved endepunktet og siden har tabellvisning. Fjerner du de
# direkte etikettene, bærer fargen identiteten alene, og da er paret for tett.
SERIER = [
    ("mat", "Matvarer og levende dyr (SITC 0)", "Matvarer", "#0E7D59"),
    ("drikke_tobakk", "Drikkevarer og tobakk (SITC 1)", "Drikke/tobakk", "#A9761B"),
]

B, H = 760, 320                      # linjediagrammets flate
MARG = {"v": 104, "h": 152, "o": 18, "n": 34}


def _nice(maks: float) -> float:
    """Runder toppen av y-aksen opp til 1/2/5 × tierpotens."""
    if maks <= 0:
        return 1.0
    import math
    eksp = math.floor(math.log10(maks))
    for trinn in (1, 2, 2.5, 5, 10):
        kandidat = trinn * 10 ** eksp
        if kandidat >= maks:
            return kandidat
    return 10 ** (eksp + 1)


def linjediagram(data: dict) -> str:
    enhet = data["enhet"]
    aarene = [int(a) for a in data["serier"]["mat"]]
    x0, x1 = min(aarene), max(aarene)
    maks = _nice(max(v for navn, _, _, _ in SERIER for v in data["serier"][navn].values()))

    def px(aar: int) -> float:
        return MARG["v"] + (aar - x0) / max(x1 - x0, 1) * (B - MARG["v"] - MARG["h"])

    def py(v: float) -> float:
        return H - MARG["n"] - v / maks * (H - MARG["n"] - MARG["o"])

    ut = [f'<svg viewBox="0 0 {B} {H}" role="img" aria-label="Importverdi per år" '
          f'class="linje" id="linje">']

    for i in range(5):                                   # recessivt rutenett + y-etiketter
        v = maks * i / 4
        y = py(v)
        ut.append(f'<line class="rute" x1="{MARG["v"]}" x2="{B - MARG["h"]}" y1="{y:.1f}" y2="{y:.1f}"/>')
        ut.append(f'<text class="akse" x="{MARG["v"] - 10}" y="{y + 4:.1f}" text-anchor="end">'
                  f'{escape(kroner(v, enhet))}</text>')

    steg = max(1, round((x1 - x0) / 6 / 5) * 5)
    for aar in range(x0, x1 + 1):
        if aar != x1 and (x1 - aar) < steg * 0.6:
            continue                                     # unngå kollisjon med siste år
        if (aar - x0) % steg == 0 or aar == x1:
            ut.append(f'<text class="akse" x="{px(aar):.1f}" y="{H - 12}" text-anchor="middle">{aar}</text>')

    for navn, _, kort, farge in SERIER:
        rad = {int(a): v for a, v in data["serier"][navn].items()}
        punkter = " ".join(f"{px(a):.1f},{py(rad[a]):.1f}" for a in sorted(rad))
        ut.append(f'<polyline class="serie" points="{punkter}" stroke="{farge}"/>')
        sist = max(rad)
        ut.append(f'<circle cx="{px(sist):.1f}" cy="{py(rad[sist]):.1f}" r="4.5" fill="{farge}" '
                  f'stroke="var(--kort)" stroke-width="2"/>')
        ut.append(f'<text class="etikett" x="{px(sist) + 12:.1f}" y="{py(rad[sist]) + 4:.1f}">'
                  f'{escape(kort)}</text>')

    ut.append(f'<line id="haarkors" class="haarkors" y1="{MARG["o"]}" y2="{H - MARG["n"]}" '
              f'x1="0" x2="0" style="opacity:0"/>')
    ut.append(f'<rect id="flate" x="{MARG["v"]}" y="{MARG["o"]}" width="{B - MARG["v"] - MARG["h"]}" '
              f'height="{H - MARG["o"] - MARG["n"]}" fill="transparent"/>')
    ut.append("</svg>")
    return "\n".join(ut)


def stolper(data: dict) -> str:
    enhet, siste = data["enhet"], data["siste_aar"]
    rader = [r for r in data["divisjoner_siste_aar"] if r["seksjon"] == "0"][:8]
    if not rader:
        return "<p>Ingen varegruppefordeling i snapshotet.</p>"
    maks = max(r["verdi"] for r in rader)
    sum_mat = data["serier"]["mat"][str(siste)]
    ut = ['<div class="stolper">']
    for r in rader:
        bredde = 100 * r["verdi"] / maks
        andel = 100 * r["verdi"] / sum_mat if sum_mat else 0
        tip = f'{escape(r["navn"])}: {kroner(r["verdi"], enhet)} — {andel:.1f} % av matimporten'
        ut.append(
            f'<div class="stolpe" data-tip="{escape(tip)}">'
            f'<span class="navn">{escape(r["navn"])}</span>'
            f'<span class="spor"><span class="fyll" style="width:{bredde:.1f}%"></span></span>'
            f'<span class="verdi">{escape(kroner(r["verdi"], enhet))}</span></div>'
        )
    ut.append("</div>")
    return "\n".join(ut)


def tabell(data: dict) -> str:
    enhet = data["enhet"]
    aarene = sorted(int(a) for a in data["serier"]["mat"])
    rader = "\n".join(
        f"<tr><td>{a}</td>"
        + "".join(f'<td class="tall">{escape(kroner(data["serier"][n].get(str(a), 0), enhet))}</td>'
                  for n, _, _, _ in SERIER)
        + "</tr>"
        for a in aarene
    )
    hoder = "".join(f"<th>{escape(e)}</th>" for _, e, _, _ in SERIER)
    return (f'<details><summary>Vis tallene som tabell</summary><table>'
            f'<thead><tr><th>År</th>{hoder}</tr></thead><tbody>{rader}</tbody></table></details>')


def skriv_side(data: dict, utfil: Path) -> Path:
    enhet, siste, land = data["enhet"], data["siste_aar"], data["land"]
    mat = data["serier"]["mat"][str(siste)]
    drikke = data["serier"]["drikke_tobakk"].get(str(siste))
    alt = (data.get("all_import_fra_landet") or {}).get(str(siste))
    andel = f"{100 * mat / alt:.1f}".replace(".", ",") + f" % av all vareimport fra {escape(land)}" if alt else \
        "andel av samlet vareimport ikke i snapshotet"
    serieprikker = "".join(
        f'<span class="nokkel"><i style="background:{f}"></i>{escape(e)}</span>'
        for _, e, _, f in SERIER
    )

    html = f"""<!doctype html>
<html lang="no"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Matimport fra {escape(land)} — SSB {escape(data['tabell'])}</title>
<style>
:root {{
  --papir:#F2EDE0; --kort:#FBF8F0; --linje:#C9C0AC; --linje-svak:#DDD6C4;
  --blekk:#27332D; --blekk-sekundaer:#46514A; --blekk-dempet:#5F6A62;
  --gran:#1F4E45; --sennep:#D9A441;
  --font-sans:'Jost','Avenir Next','Futura',sans-serif;
  --font-mono:'IBM Plex Mono','Menlo',monospace;
}}
body {{ margin:0; padding:40px 20px; background:var(--papir); color:var(--blekk);
        font-family:var(--font-sans); }}
main {{ max-width:820px; margin:0 auto; }}
h1 {{ font-size:30px; font-weight:500; color:var(--gran); margin:0 0 4px; }}
.ingress {{ color:var(--blekk-sekundaer); margin:0 0 28px; max-width:60ch; }}
section {{ background:var(--kort); border:1px solid var(--linje); border-radius:8px;
           padding:24px; margin-bottom:20px; }}
h2 {{ font-size:15px; text-transform:uppercase; letter-spacing:.08em;
      color:var(--blekk-dempet); margin:0 0 16px; font-weight:600; }}
.hero {{ font-family:var(--font-mono); font-size:46px; color:var(--gran); line-height:1.1; }}
.hero small {{ display:block; font-family:var(--font-sans); font-size:15px;
               color:var(--blekk-sekundaer); margin-top:8px; }}
.nokler {{ display:flex; gap:20px; flex-wrap:wrap; margin-bottom:8px; }}
.nokkel {{ display:flex; align-items:center; gap:8px; font-size:13px;
           color:var(--blekk-sekundaer); }}
.nokkel i {{ width:10px; height:10px; border-radius:50%; }}
.linjeboks {{ position:relative; overflow-x:auto; }}
svg.linje {{ width:100%; height:auto; display:block; min-width:560px; }}
.rute {{ stroke:var(--linje-svak); stroke-width:1; }}
.akse {{ font-family:var(--font-mono); font-size:11px; fill:var(--blekk-dempet); }}
.etikett {{ font-family:var(--font-sans); font-size:12px; fill:var(--blekk-sekundaer); }}
.serie {{ fill:none; stroke-width:2; stroke-linejoin:round; stroke-linecap:round; }}
.haarkors {{ stroke:var(--blekk-dempet); stroke-width:1; stroke-dasharray:3 3; }}
.stolper {{ display:grid; gap:10px; }}
.stolpe {{ display:grid; grid-template-columns:minmax(150px,1.1fr) 3fr auto;
           gap:12px; align-items:center; font-size:14px; }}
.stolpe .navn {{ color:var(--blekk-sekundaer); }}
.spor {{ background:var(--linje-svak); border-radius:4px; height:14px; }}
.fyll {{ display:block; height:14px; background:#0E7D59; border-radius:0 4px 4px 0; }}
.verdi {{ font-family:var(--font-mono); font-size:13px; color:var(--blekk); }}
.stolpe:hover .fyll {{ filter:brightness(.88); }}
#tips {{ position:fixed; pointer-events:none; opacity:0; transition:opacity .1s;
         background:var(--blekk); color:var(--kort); font-size:12px; padding:6px 10px;
         border-radius:6px; max-width:280px; z-index:9; }}
details {{ margin-top:8px; font-size:14px; color:var(--blekk-sekundaer); }}
summary {{ cursor:pointer; }}
table {{ border-collapse:collapse; margin-top:12px; font-size:13px; width:100%; }}
th, td {{ text-align:left; padding:4px 10px; border-bottom:1px solid var(--linje-svak); }}
.tall {{ font-family:var(--font-mono); text-align:right; }}
footer {{ font-size:13px; color:var(--blekk-dempet); max-width:65ch; }}
footer a {{ color:var(--gran); }}
</style></head>
<body data-palette="#0E7D59,#A9761B">
<main>
<h1>Matimport fra {escape(land)}</h1>
<p class="ingress">Verdien av varer Norge importerte fra {escape(land)} i SITC-seksjon 0,
matvarer og levende dyr. Drikkevarer og tobakk (SITC 1) er en egen seksjon og er
holdt utenfor mat-tallet — for {escape(land)} er den forskjellen stor.</p>

<section>
  <h2>{siste}</h2>
  <div class="hero">{escape(kroner(mat, enhet))}
    <small>matvarer og levende dyr — {andel}.
    {('Drikkevarer og tobakk kom i tillegg på ' + escape(kroner(drikke, enhet)) + '.') if drikke is not None else ''}</small>
  </div>
</section>

<section>
  <h2>Utvikling {min(int(a) for a in data['serier']['mat'])}–{siste} (løpende kroner)</h2>
  <div class="nokler">{serieprikker}</div>
  <div class="linjeboks">{linjediagram(data)}</div>
  {tabell(data)}
</section>

<section>
  <h2>Hva maten er, {siste} (tosifret SITC)</h2>
  {stolper(data)}
</section>

<footer>
  Kilde: Statistisk sentralbyrå, tabell {escape(data['tabell'])} —
  <a href="{escape(data['kilde_url'])}">{escape(data['kilde_url'])}</a>.
  Hentet {escape(data['hentet'])}. Enhet i kilden: {escape(enhet)}. Løpende kroner,
  ikke inflasjonsjustert. Tallene er importverdi (cif), ikke forbruk: varer kan
  komme fra {escape(land)} uten å være produsert der, og italiensk mat kan komme
  til Norge via et tredjeland.
</footer>
</main>
<div id="tips"></div>
<script>
const data = {json.dumps({'aar': sorted(int(a) for a in data['serier']['mat']),
                          'serier': {n: data['serier'][n] for n, _, _, _ in SERIER},
                          'etiketter': {n: k for n, _, k, _ in SERIER},
                          'enhet': enhet}, ensure_ascii=False)};
const tips = document.getElementById('tips');
function vis(html, x, y) {{
  tips.innerHTML = html; tips.style.opacity = 1;
  tips.style.left = Math.min(x + 14, innerWidth - 300) + 'px';
  tips.style.top = (y + 16) + 'px';
}}
function skjul() {{ tips.style.opacity = 0; }}

const svg = document.getElementById('linje');
const haarkors = document.getElementById('haarkors');
const V = {MARG['v']}, HH = {MARG['h']}, BREDDE = {B};
const x0 = data.aar[0], x1 = data.aar[data.aar.length - 1];
svg.addEventListener('mousemove', e => {{
  const boks = svg.getBoundingClientRect();
  const sx = (e.clientX - boks.left) / boks.width * BREDDE;
  if (sx < V || sx > BREDDE - HH) return skjul();
  const andel = (sx - V) / (BREDDE - V - HH);
  const aar = Math.round(x0 + andel * (x1 - x0));
  const px = V + (aar - x0) / (x1 - x0) * (BREDDE - V - HH);
  haarkors.setAttribute('x1', px); haarkors.setAttribute('x2', px);
  haarkors.style.opacity = 1;
  let html = '<strong>' + aar + '</strong>';
  for (const n of Object.keys(data.serier)) {{
    const v = data.serier[n][aar];
    if (v !== undefined) html += '<br>' + data.etiketter[n] + ': ' + fmt(v);
  }}
  vis(html, e.clientX, e.clientY);
}});
svg.addEventListener('mouseleave', () => {{ skjul(); haarkors.style.opacity = 0; }});

for (const el of document.querySelectorAll('[data-tip]')) {{
  el.addEventListener('mousemove', e => vis(el.dataset.tip, e.clientX, e.clientY));
  el.addEventListener('mouseleave', skjul);
}}

function fmt(v) {{
  const kr = /1\\s?000/.test(data.enhet) ? v * 1000 : v;
  if (Math.abs(kr) >= 1e9) return (kr / 1e9).toFixed(1).replace('.', ',') + ' mrd. kr';
  if (Math.abs(kr) >= 1e6) return (kr / 1e6).toFixed(1).replace('.', ',') + ' mill. kr';
  return Math.round(kr).toLocaleString('nb-NO') + ' kr';
}}
</script>
</body></html>
"""
    utfil.write_text(html, encoding="utf-8")
    return utfil


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Bruk: python pipeline/lag_matimport_side.py <snapshot.json>")
    kilde = Path(sys.argv[1])
    d = json.loads(kilde.read_text(encoding="utf-8"))
    print("✓", skriv_side(d, kilde.with_suffix(".html")))
