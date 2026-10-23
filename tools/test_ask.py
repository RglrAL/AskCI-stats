#!/usr/bin/env python3
"""Regression test for the dashboard's Ask bar.

Runs every question in tests/ask_cases.json through the real page (headless Chrome) and checks each
answer against what it should say. The page under test is the CURRENT index.html; the data is frozen at
the git commit named in tests/ask_fixture_ref, so data refreshes never change the expected answers.

Each case: {"q": "question", "then": ["follow-up", ...]?, "expect": ["text the answer must contain", ...],
"not": ["text it must not contain", ...]?, "note": "why"?, "copy": true?}. With "copy", the plain text that Copy answer
would put on the clipboard is appended to the answer after " || COPY ", so its definition, caveats and footer can be checked. A follow-up runs after the question without a
reset, as a person would type it. Before each case the Ask bar's memory of the previous answer is cleared.
A case with "type" (and optional "keys", e.g. ["ArrowDown", "Enter"]) types that text into the box after any
"q"/"then" and checks the suggestion dropdown (its preview line and options); with "Enter" among the keys it
checks the answer instead. "q" may be "" for a typing-only case.

Every suggestion the dropdown can offer is also asked through the page: none may give a "not understood"
card, and every suggestion template must name a backing case that exists in the case file.

Usage:
    python3 tools/test_ask.py                 # run all cases; exit 1 on any failure
    python3 tools/test_ask.py -k budget       # only cases whose question contains "budget"
    python3 tools/test_ask.py --show          # print every answer, passing or not
    python3 tools/test_ask.py --page FILE     # test another copy of the page (the pre-commit hook's staged copy)
    python3 tools/test_ask.py --record        # write each answer's headline into "expect" for cases that
                                              # have none (review the diff before committing)

Needs Google Chrome (or Chromium) and git. Takes about a minute.
"""
import argparse, html, json, os, re, shutil, socket, subprocess, sys, tempfile, threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(REPO, "tests", "ask_cases.json")
REF = os.path.join(REPO, "tests", "ask_fixture_ref")
DATA_FILES = ["usage.csv", "usage-hours.csv", "conversations-daily.csv", "category-outcomes-daily.csv", "categories-daily.csv",
              "categories.csv", "citations-monthly.csv", "journeys-monthly.csv", "starter-prompts-monthly.csv",
              "latency-buckets-daily.csv", "costs.csv", "events.json", "site-pages.csv", "ga4/session-and-users.csv",
              "ga4/searches-and-sessions.csv", "ga4/categories-and-views.csv", "ga4/clicks-daily.csv", "ga4/clicks-pages-daily.csv",
              "script-outcomes-daily.csv", "outcome-rules-daily.csv", "answer-style-daily.csv", "answer-next-daily.csv", "prompts.json", "pages-cited.csv", "repeat-questions-monthly.csv"]
CHROMES = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium",
           "google-chrome", "chromium", "chromium-browser"]
WAIT_MS = 250   # per question; the Ask bar renders synchronously, so this is ample

HARNESS = r"""<script>
window.__errs=[];window.addEventListener('error',e=>window.__errs.push(e.message+' @'+e.lineno));
window.addEventListener('unhandledrejection',e=>window.__errs.push('rejection: '+String(e.reason&&e.reason.stack||e.reason).slice(0,300)));
const __C=%s;
window.addEventListener('load',()=>{const t=setInterval(()=>{if(typeof DATA!=='undefined'&&DATA&&window.askQuery){clearInterval(t);go();}},200);});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function go(){
  const out=[];
  for(const c of __C){
    window.__resetAsk();let ans='';
    for(const q of [c.q,...(c.then||[])]){if(!q)continue;window.askQuery(q);await sleep(%d);const a=document.getElementById('ask-answer');
      // the card repeats the question; leave it out, so "not" checks test the answer and not the question asked
      const echo=a?[...a.querySelectorAll('.ask-card-q')]:[];echo.forEach(e=>e.style.display='none');
      ans=(a?a.innerText:'').replace(/\s+/g,' ').replace(/READ AS.*/,'').trim();echo.forEach(e=>e.style.display='');}
    // "copy": true appends what Copy answer would put on the clipboard (its plain-text form)
    if(c.copy){const P=window.askCopyPayload&&window.askCopyPayload();ans+=' || COPY '+(P?P.text.replace(/\s+/g,' '):'(none)');}
    if(c.type!==undefined){const inp=document.getElementById('ask-input');inp.focus();inp.value=c.type;inp.dispatchEvent(new Event('input',{bubbles:true}));
      if(!c.type)inp.dispatchEvent(new Event('focus'));await sleep(400);
      for(const k of (c.keys||[])){inp.dispatchEvent(new KeyboardEvent('keydown',{key:k,bubbles:true,cancelable:true}));if(k==='Enter'&&!document.getElementById('ask-sg').hidden===false){} await sleep(300);}
      if((c.keys||[]).includes('Enter')){const a=document.getElementById('ask-answer');const echo=a?[...a.querySelectorAll('.ask-card-q')]:[];echo.forEach(e=>e.style.display='none');ans=(a?a.innerText:'').replace(/\s+/g,' ').replace(/READ AS.*/,'').trim();echo.forEach(e=>e.style.display='');}
      else{const g=document.getElementById('ask-sg');ans=(g&&!g.hidden?g.innerText:'(closed)').replace(/\s+/g,' ').trim()+' | expanded='+inp.getAttribute('aria-expanded')+' | active='+(inp.getAttribute('aria-activedescendant')||'');}
      inp.blur();inp.value='';}
    out.push(ans);
  }
  // every suggestion the dropdown can offer must answer without a "not understood" card
  const sgBad=[];let tpl=[];
  if(window.__askSuggest){const S=window.__askSuggest();tpl=S.templates;
    for(const q of S.all){window.__resetAsk();window.askQuery(q);await sleep(60);const t=(document.getElementById('ask-answer').innerText||'').replace(/\s+/g,' ');
      if(/isn’t a topic or measure|aren’t topics or measures|couldn’t parse|Which measure|isn’t split by/.test(t))sgBad.push(q+' => '+t.slice(0,120));}}
  // a re-ask link is untrusted input: its question must arrive as text, never as markup
  window.__resetAsk();window.askFromHash('#ask='+encodeURIComponent('<img src=x onerror="window.__pwn=1">money and tax questions'));await sleep(600);
  {const inp=document.getElementById('ask-input'),inj=document.querySelector('#ask-answer img,#ask-answer [onerror]');
    if(window.__pwn||inj||!document.getElementById('ask-answer').innerHTML||inp.value!=='<img src=x onerror="window.__pwn=1">money and tax questions')window.__errs.push('re-ask link: the hash was not treated as plain text ('+inp.value+')');
    inp.value='';}
  // question lists: a shared link is untrusted (names and questions lose markup, unknown readings are dropped), and a
  // list runs as a report with the period before each single figure
  if(window.__ql){const b64=s=>btoa(unescape(encodeURIComponent(s))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
    const n=window.__ql.fromHash('#qlist='+b64(JSON.stringify({n:'<b>x</b>',i:[{q:'<img src=x onerror="window.__pwn=1">questions',r:{m:'evil'},t:'zzz'},{q:'cited answer rate in September',r:{m:'cited',c:'',f:'',s:'',a:'sum'},p:{kind:'month',from:'2026-09-01',to:'2026-09-30',label:'September'},t:'lastmonth'}]})));
    const L=n&&window.__ql.lists().lists[n];
    if(!L||/[<>]/.test(n)||L.length!==2||/[<>]/.test(L[0].q)||L[0].r!==null)window.__errs.push('question list link: not cleaned ('+JSON.stringify(L)+')');
    else{const R=await window.__ql.run(n,'m:2026-09');closeReportMode();
      if(!R||!R.text.includes('86.5%%')||!R.text.includes('August 2026: 91.9%% (−5.4 pts)')||!R.text.includes('## 2. cited answer rate, September 2026'))window.__errs.push('question list report: '+(R?R.text.slice(0,300):'none'));}
    if(window.__pwn)window.__errs.push('question list link ran markup');}
  // the CSV export: September 2026 as one month row, the same figures as the fact sheet, and the notes after the table
  if(typeof exportCsvText==='function'){const x=exportCsvText('month','2026-01-01','2026-10-23');
    const want=['Sep 2026,2026-09-01,2026-09-30,30,21718,11590,20790,17976,1249,1547,317,349,18,3738,86.5,6.0,7.4,20.8,33,1.8,11590,10195,88.0,1249,223,17.9,1547,998,64.5,873,110,983,5.5,11.8,1009.80','Notes','unvalidated','page '];
    const miss=want.filter(w=>!x.includes(w));if(miss.length)window.__errs.push('CSV export: missing '+miss.join(' | '));}
  document.body.setAttribute('data-test',JSON.stringify({out,sgBad,tpl,errs:window.__errs.concat((window.__askRegistryProblems||[]).map(x=>'registry: '+x))}));
}
</script>"""


def chrome():
    for c in CHROMES:
        p = c if os.path.isabs(c) else shutil.which(c)
        if p and os.path.exists(p):
            return p
    return None


def headline(ans):
    """A short form of an answer for printing."""
    return re.sub(r"\s*(Chart Table CSV|Open |Set dashboard).*$", "", ans).strip()[:200]


NOTICE_RE = re.compile(r"^((?:[A-Z][^.]*?(?:\.|”\.)\s)+?)(?=[A-Z0-9 ’'“”?&/\-]{6,})")


def key_parts(q, ans):
    """What --record pins for a case: any notices above the answer (sentences ending in a full stop before the
    first number), then the answer's value (the first number) with the word that follows it; for an answer with
    no number (a decline or a "which measure?" prompt), its first five words."""
    parts = []
    m = re.search(r"[≤≥]?\s?£?\d[\d,.]*(?:%|p|s|×| pts)?(?:\s+[A-Za-z’'-]+)?", ans)
    if not m:
        return [" ".join(ans.split()[:5])]
    lead = ans[:m.start()].rstrip()
    k = lead.rfind(".")
    if k > 0:
        parts.append(lead[:k + 1].strip())
    parts.append(m.group(0).strip())
    return parts


def build_site(tmp, ref, page_path):
    with open(page_path, encoding="utf-8") as fh:
        page = fh.read()
    if "  let lastIntent=null;" not in page:
        sys.exit("index.html: the Ask bar's `let lastIntent=null;` line moved; update tools/test_ask.py")
    page = page.replace("  let lastIntent=null;", "  let lastIntent=null;window.__resetAsk=()=>{lastIntent=null;};", 1)
    # chart animation off: the page is never looked at, and it keeps headless timing simple
    page = page.replace("animation:{duration:350}", "animation:false")
    for f in DATA_FILES:
        dest = os.path.join(tmp, f)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        r = subprocess.run(["git", "-C", REPO, "show", f"{ref}:{f}"], capture_output=True)
        if r.returncode:
            if "exists on disk, but not in" in r.stderr.decode() or "does not exist in" in r.stderr.decode():
                continue   # a file added after the fixture commit: the page runs without it, as it would then
            sys.exit(f"git show {ref}:{f} failed: {r.stderr.decode().strip()}")
        with open(dest, "wb") as fh:
            fh.write(r.stdout)
    return page


def run(cases, ref, browser, page_path):
    tmp = tempfile.mkdtemp(prefix="asktest-")
    try:
        page = build_site(tmp, ref, page_path)
        payload = [{k: c[k] for k in ("q", "then", "type", "keys", "copy") if k in c} for c in cases]
        with open(os.path.join(tmp, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(page.replace("</body>", HARNESS % (json.dumps(payload), WAIT_MS) + "</body>", 1))
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
        srv = ThreadingHTTPServer(("127.0.0.1", port), partial(QuietHandler, directory=tmp))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        prof = os.path.join(tmp, "_profile")
        budget = 60000 + len(cases) * (WAIT_MS * 2 + 900) + 400 * 200   # plus every suggestion, asked once
        dom = subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={prof}",
                              f"--virtual-time-budget={budget}", "--dump-dom", f"http://127.0.0.1:{port}/index.html"],
                             capture_output=True, text=True, timeout=900).stdout
        srv.shutdown()
        m = re.search(r'data-test="([^"]*)"', dom)
        if not m:
            sys.exit("the page produced no results (it may not have loaded); open index.html to check for errors")
        res = json.loads(html.unescape(m.group(1)))
        return res["out"], res["errs"], res.get("sgBad", []), res.get("tpl", [])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-k", help="only cases whose question contains this text")
    ap.add_argument("--show", action="store_true", help="print every answer")
    ap.add_argument("--record", action="store_true", help="fill empty expectations from the current answers")
    ap.add_argument("--page", default=os.path.join(REPO, "index.html"), help="the page to test (default: index.html; the pre-commit hook passes the staged copy)")
    a = ap.parse_args()
    browser = chrome()
    if not browser:
        print("test_ask: no Chrome or Chromium found; skipped"); return 0
    with open(CASES, encoding="utf-8") as fh:
        allc = json.load(fh)
    cases = [c for c in allc if not a.k or a.k.lower() in c["q"].lower()]
    ref = open(REF).read().strip()
    out, errs, sg_bad, tpl = run(cases, ref, browser, a.page)
    qs = {c["q"] for c in allc}
    tpl_missing = [t["t"] + " (backing case: " + t["case"] + ")" for t in tpl if t["case"] not in qs]
    fails = []
    for c, ans in zip(cases, out):
        missing = [e for e in c.get("expect", []) if e not in ans]
        present = [n for n in c.get("not", []) if n in ans]
        if a.record and not c.get("expect"):
            q = c["then"][-1] if c.get("then") else c["q"]
            c["expect"] = key_parts(q, ans)
        ok = not missing and not present and (c.get("expect") or a.record)
        if not ok:
            fails.append((c, ans, missing, present))
        if a.show or not ok:
            print(("PASS " if ok else "FAIL ") + c["q"] + (" → " + " → ".join(c["then"]) if c.get("then") else ""))
            if not ok:
                for e in missing: print("   missing:   " + e)
                for n in present: print("   should not contain: " + n)
            print("   answer:    " + headline(ans))
    if a.record:
        with open(CASES, "w", encoding="utf-8") as fh:
            json.dump(allc, fh, indent=1, ensure_ascii=False); fh.write("\n")
        print("recorded expectations for cases that had none; review `git diff tests/ask_cases.json`")
    if errs:
        print("page errors:"); [print("   " + e) for e in errs]
    if sg_bad:
        print("suggestions that are not understood:"); [print("   " + b) for b in sg_bad]
    if tpl_missing:
        print("suggestion templates without a backing case:"); [print("   " + b) for b in tpl_missing]
    print(f"{len(cases) - len(fails)} of {len(cases)} passed" + (f", {len(fails)} failed" if fails else ""))
    return 1 if fails or errs or sg_bad or tpl_missing else 0


if __name__ == "__main__":
    sys.exit(main())
