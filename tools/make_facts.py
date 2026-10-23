#!/usr/bin/env python3
"""Write the AskCI fact sheet: reports/facts-<month>.md (brief §48, Phase A step 3).

The fact sheet is the questions tagged "lists": ["facts"] in tests/ask_cases.json, answered by the dashboard itself
(headless Chrome, the current data files) for one month: by default the last full month in the data. Each figure is
followed by the period before it and the change, its caveats sit under it, and the definitions are gathered at the
end. The footer names the data, config and outcome-rule versions and the page and data commits.

The deploy workflow runs it on every push, so the published site always carries the sheet for the data it serves, at
reports/facts-YYYY-MM.md and reports/facts-latest.md. reports/ is git-ignored: any month can be rebuilt from the repo's
data with --month. The sheet holds counts and rates only, never question or answer text.

Usage:
    python3 tools/make_facts.py                    # the last full month → reports/facts-YYYY-MM.md
    python3 tools/make_facts.py --month 2026-08    # a given month
    python3 tools/make_facts.py --stdout           # print instead of writing

Needs Google Chrome (or Chromium) and git.
"""
import argparse, html, json, os, re, socket, subprocess, sys, tempfile, threading, shutil
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_ask import chrome   # the same browser lookup as the Ask bar test

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HARNESS = r"""<script>
window.__e=[];window.addEventListener('error',e=>window.__e.push(e.message+' @'+e.lineno));
window.addEventListener('unhandledrejection',e=>window.__e.push('rejection: '+String(e.reason&&e.reason.stack||e.reason).slice(0,300)));
window.addEventListener('load',()=>{const t=setInterval(async()=>{if(typeof DATA!=='undefined'&&DATA&&window.__ql){clearInterval(t);
  let o={};try{const R=await window.__ql.facts(%s);o={text:R?R.text:'',head:R?R.head:''};}catch(e){o={err:String(e&&e.stack||e)};}
  o.errs=window.__e;document.body.setAttribute('data-facts',JSON.stringify(o));}},200);});
</script>"""


def git_short(*paths):
    r = subprocess.run(["git", "-C", REPO, "log", "-1", "--format=%h", "--", *paths], capture_output=True, text=True)
    return r.stdout.strip() or "local"


class Handler(SimpleHTTPRequestHandler):
    page = b""

    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(self.page))); self.end_headers(); self.wfile.write(self.page)
        else:
            super().do_GET()

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--month", help="YYYY-MM (default: the last full month in the data)")
    ap.add_argument("--out-dir", default=os.path.join(REPO, "reports"))
    ap.add_argument("--stdout", action="store_true")
    a = ap.parse_args()
    if a.month and not re.fullmatch(r"\d{4}-\d{2}", a.month):
        sys.exit("--month must be YYYY-MM")
    browser = chrome()
    if not browser:
        sys.exit("make_facts: no Chrome or Chromium found")
    with open(os.path.join(REPO, "index.html"), encoding="utf-8") as fh:
        page = fh.read()
    stamp = f"page={git_short('index.html')} data={git_short('*.csv', 'events.json')}"
    page = page.replace('content="page=local data=local"', f'content="{stamp}"', 1)
    page = page.replace("animation:{duration:350}", "animation:false")
    page = page.replace("</body>", HARNESS % json.dumps(("m:" + a.month) if a.month else "") + "</body>", 1)
    Handler.page = page.encode("utf-8")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    srv = ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=REPO))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    prof = tempfile.mkdtemp(prefix="facts-")
    try:
        dom = subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={prof}",
                              "--virtual-time-budget=60000", "--dump-dom", f"http://127.0.0.1:{port}/index.html"],
                             capture_output=True, text=True, timeout=300).stdout
    finally:
        srv.shutdown(); shutil.rmtree(prof, ignore_errors=True)
    m = re.search(r'data-facts="([^"]*)"', dom)
    if not m:
        sys.exit("make_facts: the page produced no fact sheet (it may not have loaded)")
    o = json.loads(html.unescape(m.group(1)))
    if o.get("err") or o.get("errs"):
        sys.exit("make_facts: page errors:\n  " + "\n  ".join([o.get("err") or ""] + o.get("errs", [])))
    text = o.get("text") or ""
    if not text.strip():
        sys.exit("make_facts: no questions are tagged \"facts\" in tests/ask_cases.json")
    if a.stdout:
        print(text); return 0
    month = a.month
    if not month:
        mm = re.search(r"^# AskCI fact sheet: (\w+) (\d{4})", text, re.M)
        names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        month = f"{mm.group(2)}-{names.index(mm.group(1)) + 1:02d}" if mm else "latest"
    os.makedirs(a.out_dir, exist_ok=True)
    out = os.path.join(a.out_dir, f"facts-{month}.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    if not a.month:   # the latest sheet also has a fixed address, linked from the Lists panel
        with open(os.path.join(a.out_dir, "facts-latest.md"), "w", encoding="utf-8") as fh:
            fh.write(text)
    print(f"wrote {os.path.relpath(out, REPO)} ({text.count(chr(10) + '- **')} figures)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
