from playwright.sync_api import sync_playwright
import pathlib, sys
src = pathlib.Path('print.html').resolve().as_uri()
out = 'Kulturfondets-geografi-2024-2026.pdf'
errs=[]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
                          args=['--no-sandbox'])
    pg = b.new_page(viewport={'width':1180,'height':1500})
    pg.on('console', lambda m: errs.append(m.type+': '+m.text) if m.type=='error' else None)
    pg.on('pageerror', lambda e: errs.append('pageerror: '+str(e)))
    pg.emulate_media(color_scheme='light', media='print')
    pg.goto(src, wait_until='networkidle')
    pg.wait_for_timeout(1500)
    # sanitetssjekk: er figurene faktisk tegnet?
    stats = pg.evaluate("""() => {
      const ids=['c-indeks','c-sokere','c-scatter','c-dekomp','c-just','c-dumbbell','c-trend'];
      const svgs=Object.fromEntries(ids.map(i=>[i, document.getElementById(i)?.querySelector('svg')?1:0]));
      return {svgs, ordningRader: document.querySelectorAll('#t-ordning tbody tr').length,
              fylkeRader: document.querySelectorAll('#t-fylke tbody tr').length,
              feiltekst: document.body.innerText.includes('kunne ikke tegnes')};
    }""")
    print('FIGURER:', stats)
    pg.pdf(path=out, prefer_css_page_size=True, print_background=True,
           margin={'top':'16mm','bottom':'18mm','left':'14mm','right':'14mm'},
           display_header_footer=True,
           header_template='<div></div>',
           footer_template='<div style="width:100%;font-family:sans-serif;font-size:8px;color:#6E7880;padding:0 14mm;display:flex;justify-content:space-between;"><span>Kulturfondets geografi 2024–2026 · Impromptu Analytics</span><span class="pageNumber"></span></div>')
    b.close()
if errs: print('KONSOLLFEIL:', errs[:10], file=sys.stderr)
print('skrevet', out)
