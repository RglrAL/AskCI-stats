#!/usr/bin/env node
// Browser-free runner for the Ask bar regression suite (tests/ask_cases.json).
// Loads index.html in jsdom with Chart.js and lucide replaced by stand-ins, serves the data files from the
// repository, runs every case from a clean state and checks the answer text, like tools/test_ask.py.
// It does not draw anything, so it tests text, not pictures; keep tools/test_ask.py for visual checks.
//
// Setup (once):  npm install jsdom@24 papaparse@5.4.1
// Usage:         node tools/test_ask_node.js [--cases FILE] [-k substring] [--show] [--page FILE]
// Exit code 1 on any failure, page error or registry problem.
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');
const ARGS = {}; { const a = process.argv.slice(2); for (let i = 0; i < a.length; i++) { if (a[i] === '--show') ARGS.show = true; else if (a[i] === '-k') ARGS.k = a[++i]; else if (a[i] === '--cases') ARGS.cases = a[++i]; else if (a[i] === '--page') ARGS.page = a[++i]; } }
const REPO = path.resolve(__dirname, '..');

let html = fs.readFileSync(ARGS.page || path.join(REPO, 'index.html'), 'utf8');
html = html.replace('  let lastIntent=null;', '  let lastIntent=null;window.__resetAsk=()=>{lastIntent=null;};');
const papa = '';

const stubs = `<script>
// Minimal Chart.js stand-in: records configs so the harness can inspect datasets; draws nothing.
window.__charts=[];
class Chart{constructor(ctx,cfg){this.ctx=ctx;this.config=cfg;this.data=cfg&&cfg.data;this.options=cfg&&cfg.options||{};this.canvas=ctx&&ctx.canvas||ctx;window.__charts.push(this);this.scales={};this.chartArea={left:0,right:300,top:0,bottom:200};}
  update(){} destroy(){} resize(){} getDatasetMeta(){return {data:[]}} toBase64Image(){return ''} }
Chart.register=function(){};Chart.defaults={font:{},plugins:{legend:{labels:{}},tooltip:{}},color:'#000',borderColor:'#000'};Chart.helpers={};
Chart.getChart=function(){return null};
window.Chart=Chart;
window.lucide={createIcons(){},icons:{}};
</script>`;
html = html.replace(/<script src="https:\/\/cdnjs[^>]*><\/script>\s*/g, '').replace(/<script src="https:\/\/unpkg[^>]*><\/script>/, stubs);

const vc = new VirtualConsole();
const errs = [];
vc.on('jsdomError', e => { const m = String(e && e.message || e); if (!/not implemented/i.test(m)) errs.push('jsdomError: ' + m.slice(0, 300)); });
vc.on('error', (...a) => errs.push('console.error: ' + a.map(String).join(' ').slice(0, 300)));

const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost:8000/', virtualConsole: vc,
  beforeParse(window) {
    window.Papa = require(path.join(REPO, 'node_modules/papaparse'));
    window.fetch = async (u) => {
      const p = String(u).replace(/^https?:\/\/[^/]+\//, '').split('?')[0];
      const f = path.join(REPO, p);
      if (!fs.existsSync(f)) return { ok: false, status: 404, text: async () => '' , json: async () => ({})};
      const t = fs.readFileSync(f, 'utf8');
      return { ok: true, status: 200, text: async () => t, json: async () => JSON.parse(t) };
    };
    window.matchMedia = (q) => ({ matches: false, media: q, addEventListener(){}, removeEventListener(){}, addListener(){}, removeListener(){} });
    window.HTMLCanvasElement.prototype.getContext = function () { return { canvas: this, measureText: (t) => ({ width: String(t).length * 6 }), fillText(){}, clearRect(){}, save(){}, restore(){}, beginPath(){}, moveTo(){}, lineTo(){}, stroke(){}, fill(){}, arc(){}, setLineDash(){}, fillRect(){}, strokeRect(){}, closePath(){}, translate(){}, rotate(){}, scale(){}, createLinearGradient(){return {addColorStop(){}}}, getImageData(){return {data:[]}} }; };
    window.ResizeObserver = class { observe(){} unobserve(){} disconnect(){} };
    window.scrollTo = () => {};
    window.HTMLElement.prototype.scrollIntoView = function(){};
    window.addEventListener('error', e => errs.push('page error: ' + (e.message || e.error) + ' @' + e.lineno));
  } });

const w = dom.window;
const sleep = ms => new Promise(r => setTimeout(r, ms));


async function main() {
  const cases = JSON.parse(fs.readFileSync(ARGS.cases || path.join(REPO, 'tests', 'ask_cases.json'), 'utf8'))
    .filter(c => !ARGS.k || c.q.toLowerCase().includes(ARGS.k.toLowerCase()));
  for (let i = 0; i < 300 && !(w.eval("typeof DATA!=='undefined'&&!!DATA") && w.askQuery); i++) await sleep(100);
  if (!(w.eval("typeof DATA!=='undefined'&&!!DATA") && w.askQuery)) { console.error('page did not initialise', errs); process.exit(1); }
  let fails = 0;
  for (const c of cases) {
    w.__resetAsk(); const before = errs.length; let ans = '';
    for (const q of [c.q, ...(c.then || [])]) {
      try { w.askQuery(q); } catch (e) { errs.push('askQuery threw: ' + String(e && e.stack || e).slice(0, 400)); }
      await sleep(30);
      ans = cardText();
    }
    const up = s => s.toUpperCase();
    const missing = (c.expect || []).filter(e => !up(ans).includes(up(e)));
    const present = (c.not || []).filter(n => ans.includes(n));
    const pageErrs = errs.slice(before);
    if (missing.length || present.length || pageErrs.length) {
      fails++;
      console.log('FAIL: ' + c.q + (c.then ? ' -> ' + c.then.join(' -> ') : ''));
      if (missing.length) console.log('  missing: ' + JSON.stringify(missing));
      if (present.length) console.log('  must not contain: ' + JSON.stringify(present));
      if (pageErrs.length) console.log('  errors: ' + JSON.stringify(pageErrs));
      console.log('  answer: ' + ans.slice(0, 300));
    } else if (ARGS.show) console.log('ok: ' + c.q + '\n  ' + ans.slice(0, 200));
  }
  const reg = w.__askRegistryProblems || [];
  if (reg.length) { fails++; console.log('registry problems: ' + JSON.stringify(reg)); }
  console.log(`${cases.length - fails} of ${cases.length} cases pass`);
  process.exit(fails ? 1 : 0);
}
function cardText() {
  const a = w.document.getElementById('ask-answer'); if (!a) return '';
  const clone = a.cloneNode(true);
  clone.querySelectorAll('.ask-card-q,[hidden],[style*="display:none"],[style*="display: none"],select').forEach(e => e.remove());
  const tmp = w.document.createElement('textarea'); tmp.innerHTML = clone.innerHTML.replace(/<[^>]+>/g, ' ');
  return tmp.value.replace(/\s+/g, ' ').replace(/Read as.*/, '').trim();
}
main().catch(e => { console.error(e && e.stack || e); process.exit(1); });
