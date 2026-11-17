#!/usr/bin/env python3
"""Injection test: markup planted in the data files must never run or become an element (brief §108, handoff 9c).

Builds the site in a temporary folder from the CURRENT index.html and data/, plants payloads, renders every view in
headless Chrome, opens a day panel and asks the Ask bar a few questions, and then checks the page:
  - no payload ran (each one calls window.__pwn, which records the call);
  - no element carries the payload's data-pwn attribute (markup was not parsed into the page);
  - no link has a javascript: address;
  - every inline handler whose text carries a payload, when called, does not run it (an argument stays a string).

Two passes:
  text       every text value of every CSV the page loads (dates, months and numbers left alone) and every string in
             its JSON files gets a suffix that tries each context: text, both attribute quotes, a handler argument
             and an HTML entity; plus an event whose date tries to break out of a handler.
  addresses  in every address column (URL, page, Address) half the values get an address-shaped suffix and half are
             replaced by a javascript: address, so the links themselves are tried.

Prints counts only. Needs Google Chrome (or Chromium). Takes about a minute.

Usage:
    python3 tools/test_inject.py
    python3 tools/test_inject.py --page FILE   # test another copy of the page
"""
import csv, glob, html, io, json, os, re, shutil, socket, subprocess, sys, tempfile, threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'tools'))
from test_ask import chrome  # noqa: E402

PAY = """"'><img data-pwn src=x onerror="__pwn('img')"><svg data-pwn onload=__pwn('svg')>&#39;);__pwn('entity');//\\');__pwn('quote');//"""
ADDR_PAY = """'onmouseover='__pwn("addr")'x="<b data-pwn>"""
JS_ADDR = "javascript:__pwn('scheme')"
ADDR_COL = re.compile(r'^(?:url|page|address|link)$', re.I)
DATEISH = re.compile(r'^\s*(?:\d{4}-\d{2}(?:-\d{2})?|\d{8}|\(all\)|-?[\d.,]+%?|)\s*$')
SKIP_COLS = re.compile(r'^(?:date|month|year|week|day|hour)$', re.I)
# columns the page filters the whole file on: planted there, the file is rightly read as empty and nothing renders
KEEP = {'costs.csv': {'ResourceGroupName', 'Currency', 'ResourceType', 'ResourceLocation', 'UsageDate'}}
PANES = ['home', 'overview', 'breakdown', 'usage', 'reach', 'quality', 'clicks', 'pages', 'wording', 'register', 'asked',
         'categories', 'convs', 'llm', 'impact', 'projections']
QUESTIONS = ['most cited pages', 'latest change', 'events', 'top topics', 'pages people say are missing information',
             'rising topics', 'costs by service', 'register']

HARNESS = r"""<script>
window.__pwnHits=[];window.__pwn=x=>window.__pwnHits.push(String(x));
window.__errs=[];window.addEventListener('error',e=>window.__errs.push(String(e.message).slice(0,160)));
const __P=%s,__Q=%s;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
window.addEventListener('load',()=>{const t0=Date.now();const t=setInterval(()=>{if(typeof DATA!=='undefined'&&DATA&&window.askQuery){clearInterval(t);go();}
  else if(Date.now()-t0>60000){clearInterval(t);document.body.setAttribute('data-test',JSON.stringify({noload:true,errs:window.__errs.slice(0,20),hits:window.__pwnHits.slice(0,20),elements:document.querySelectorAll('[data-pwn]').length}));}},200);});
function scan(where,R){
  R.elements+=document.querySelectorAll('[data-pwn]').length;
  document.querySelectorAll('a[href]').forEach(a=>{if(/^\s*javascript:/i.test(a.getAttribute('href')))R.jsLinks++;});
  document.querySelectorAll('*').forEach(el=>{for(const at of el.attributes){
    if(!/^on/i.test(at.name)||at.value.indexOf('__pwn')<0)continue;R.handlers++;
    const before=window.__pwnHits.length;
    try{const f=el[at.name];if(typeof f==='function')f.call(el,new MouseEvent(at.name.slice(2)));}catch(e){}
    if(window.__pwnHits.length>before)R.ranFrom.push(where+': '+at.name);}});
}
async function go(){
  const R={elements:0,jsLinks:0,handlers:0,ranFrom:[],panes:0,paneErrors:[]};
  for(const p of __P){try{renderPane(p);R.panes++;}catch(e){R.paneErrors.push(p+': '+String(e.message).slice(0,120));}await sleep(250);scan(p,R);}
  try{const m=DATA.merged;openDayPanel(m[m.length-1].date);}catch(e){R.paneErrors.push('day panel: '+String(e.message).slice(0,120));}
  await sleep(300);scan('day panel',R);
  for(const q of __Q){try{window.askQuery(q);}catch(e){R.paneErrors.push('ask '+q+': '+String(e.message).slice(0,120));}await sleep(250);scan('ask: '+q,R);}
  R.hits=window.__pwnHits.slice(0,20);R.errs=window.__errs.slice(0,20);
  document.body.setAttribute('data-test',JSON.stringify(R));
}
</script>"""


def plant_csv(path, mode):
    with open(path, encoding='utf-8-sig', newline='') as f: text = f.read()
    if path.endswith('.csv') and os.path.basename(path).startswith('Ask-ci-click-throughs'): return 0
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2: return 0
    head, n = rows[0], 0
    for c, name in enumerate(head):
        if SKIP_COLS.match(name.strip()) or name.strip() in KEEP.get(os.path.basename(path), ()): continue
        addr = bool(ADDR_COL.match(name.strip()))
        if mode == 'addresses' and not addr: continue
        for i, r in enumerate(rows[1:]):
            if c >= len(r) or DATEISH.match(r[c]): continue
            if mode == 'text': r[c] = r[c] + PAY
            else: r[c] = (r[c] + ADDR_PAY) if i % 2 == 0 else JS_ADDR
            n += 1
    buf = io.StringIO(newline='')
    csv.writer(buf, lineterminator='\n').writerows(rows)
    with open(path, 'w', encoding='utf-8', newline='') as f: f.write(buf.getvalue())
    return n


def plant_json(path):
    n = 0
    def walk(o):
        nonlocal n
        if isinstance(o, str):
            if DATEISH.match(o): return o
            n += 1; return o + PAY
        if isinstance(o, list): return [walk(x) for x in o]
        if isinstance(o, dict): return {k: walk(v) for k, v in o.items()}
        return o
    j = walk(json.load(open(path, encoding='utf-8')))
    if os.path.basename(path) == 'events.json' and isinstance(j, dict):
        j.setdefault('events', []).append({'start': "2026-01-01');__pwn('date');('", 'kind': 'model', 'status': 'confirmed',
                                           'title': 'planted', 'detail': '', 'evidence': '', 'applies_to': 'all'})
        n += 1
    json.dump(j, open(path, 'w', encoding='utf-8'))
    return n


def run_pass(mode, browser, page_path):
    tmp = tempfile.mkdtemp(prefix='injtest-')
    try:
        shutil.copytree(os.path.join(REPO, 'data'), os.path.join(tmp, 'data'))
        planted = 0
        skip = set(filter(None, os.environ.get('INJECT_SKIP', '').split(',')))   # for finding a file that stops the load
        for p in glob.glob(os.path.join(tmp, 'data', '**', '*.csv'), recursive=True):
            if os.path.basename(p) not in skip: planted += plant_csv(p, mode)
        if mode == 'text':
            for p in glob.glob(os.path.join(tmp, 'data', '**', '*.json'), recursive=True):
                if os.path.basename(p) not in skip: planted += plant_json(p)
        page = open(page_path, encoding='utf-8').read()
        page = page.replace('animation:{duration:350}', 'animation:false')
        page = page.replace('<head>', '<head><script>window.__plainLoad=1</script>', 1)
        page = page.replace('</body>', HARNESS % (json.dumps(PANES), json.dumps(QUESTIONS)) + '</body>', 1)
        open(os.path.join(tmp, 'index.html'), 'w', encoding='utf-8').write(page)
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
        srv = ThreadingHTTPServer(('127.0.0.1', port), partial(Quiet, directory=tmp))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        dom = subprocess.run([browser, '--headless=new', '--disable-gpu', '--no-first-run', f'--user-data-dir={tmp}/_profile',
                              '--virtual-time-budget=120000', '--dump-dom', f'http://127.0.0.1:{port}/index.html'],
                             capture_output=True, text=True, timeout=300).stdout
        srv.shutdown()
        m = re.search(r'data-test="([^"]*)"', dom)
        if not m: return planted, None
        return planted, json.loads(html.unescape(m.group(1)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


def main():
    page_path = sys.argv[sys.argv.index('--page') + 1] if '--page' in sys.argv else os.path.join(REPO, 'index.html')
    browser = chrome()
    if not browser:
        print('test_inject: no Chrome or Chromium found; FAILED'); return 1
    bad = 0
    for mode in ('text', 'addresses'):
        planted, R = run_pass(mode, browser, page_path)
        if R is None or R.get('noload'):
            print(f'{mode}: the page did not finish loading' + (f" (payloads run {len(R['hits'])}, elements {R['elements']}; errors: {'; '.join(R['errs'])})" if R else '')); bad += 1; continue
        fail = R['hits'] or R['elements'] or R['jsLinks'] or R['ranFrom']
        print(f"{mode}: {planted} values planted; {R['panes']} of {len(PANES)} views rendered; "
              f"payloads run {len(R['hits'])}, elements created {R['elements']}, javascript: links {R['jsLinks']}, "
              f"handlers carrying a payload {R['handlers']} (ran one: {len(R['ranFrom'])}) — {'FAIL' if fail else 'ok'}")
        for x in R['hits']: print('   ran:', x)
        for x in R['ranFrom']: print('   from handler:', x)
        for x in R['paneErrors']: print('   view error (not an injection):', x)
        bad += bool(fail)
    print('injection test ' + ('FAILED' if bad else 'passed'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
