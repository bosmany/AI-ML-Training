#!/usr/bin/env node
/*
 * pyodide-grade.js - regression harness for the course chapters.
 *
 * WHAT IT DOES
 *   Runs every chapter's Python the way the page does (Pyodide 0.26.4) and checks the
 *   exercises grade the way a learner would experience them:
 *     1. Every runnable lesson block (a code-block with a "Run" button) must succeed.
 *        Blocks of one chapter share ONE Pyodide session, in document order, like the page.
 *     2. Every `EXERCISES[n].solution` must pass its own grader: run succeeds, every `checks`
 *        string is in the (lower-cased) output, and `checkFn(output)` (when defined) is true.
 *     3. Every starter <textarea id="exN-code"> must NOT already pass its own grader.
 *     4. "Colab-pattern" chapters (they cannot run their code and grade by pattern matching,
 *        `checkTextEx`): each solution must contain every `checks` string (whitespace stripped,
 *        lower-cased) and parse as Python; starters must not satisfy the checks.
 *     5. Capstone/project section: the page's own `runProject` / `checkProject` function is
 *        extracted from the HTML and executed against a stubbed DOM, so the real per-chapter
 *        grading rules are used. The starter must not pass. Where the chapter ships a reference
 *        solution (a PROJECT_SOLUTION constant, or reference code blocks inside <details>) it
 *        must pass; chapters without a reference solution are reported as "no reference".
 *   Each chapter gets a fresh Pyodide (own worker thread). Exercise/project snippets each run
 *   from a clean interpreter namespace (globals, cwd files, chdir, env are reset between runs),
 *   so a solution that only works because an earlier snippet left state behind is caught.
 *   Every snippet has a timeout (Python KeyboardInterrupt first, worker kill as last resort).
 *
 * USAGE
 *   node scripts/pyodide-grade.js                       # whole repo
 *   node scripts/pyodide-grade.js --folder python,math  # only these top-level folders
 *   node scripts/pyodide-grade.js --file ml/ch16-linear-logistic-regression.html
 *   node scripts/pyodide-grade.js --json                # machine readable summary on stdout
 *   node scripts/pyodide-grade.js --json=out.json       # ... or into a file
 *   node scripts/pyodide-grade.js --setup               # only download/prefetch the runtime
 *   Options: --timeout SEC (per snippet, default 60)  --jobs N (chapters in parallel, default 1)
 *            --baseline FILE (known failures, see below)  --verbose  --list
 *            --pyodide DIR (existing full Pyodide dir)  --cache-dir DIR
 *   Exit code: 0 all good, 1 at least one (non-baselined) failure, 2 usage/setup error.
 *
 * BASELINE (known failures)
 *   Older chapters were never executed under Pyodide. A baseline file
 *   ({"known":[{"key":"<file>::<phase>::<id>","note":"..."}]}) lets CI stay green on failures
 *   that are already understood while still failing on any NEW failure. Baselined failures are
 *   listed as "known"; a baselined entry that now passes is reported as "FIXED - remove from
 *   baseline" (and fails the run with --strict-baseline). Without --baseline every failure fails.
 *
 * PACKAGE STRATEGY (how Node-hosted Pyodide gets numpy/pandas/scipy/scikit-learn/matplotlib/...)
 *   Pyodide core (asm.js/wasm/stdlib/lock file) comes from the official npm tarball
 *   https://registry.npmjs.org/pyodide/-/pyodide-0.26.4.tgz (integrity-checked against the
 *   registry's sha512), extracted with `tar` - no npm needed. The wheels are fetched from the
 *   jsDelivr Pyodide CDN (the same files the browser loads), sha256-verified against
 *   pyodide-lock.json, into a package cache directory that Pyodide reads through its
 *   `packageCacheDir` option; anything not prefetched is fetched on demand and cached there too.
 *   Both live under one directory (default ~/.cache/aiml-pyodide-0.26.4, override PYODIDE_HOME),
 *   which is exactly what the GitHub Actions workflow caches. `--setup` fills it up front so
 *   every matrix job starts from an identical, complete cache.
 *
 * KNOWN HARNESS DIFFERENCES vs a real browser (kept deliberately small)
 *   - matplotlib uses the Agg backend (the browser wasm backend needs a DOM) and the
 *     "FigureCanvasAgg is non-interactive" warning is silenced.
 *   - input() sees EOF (the page's prompt() cancelled).
 *   - no network sockets exist in Pyodide anywhere, so nothing to emulate there.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const { execFileSync } = require('child_process');
const { Worker, isMainThread, parentPort, workerData } = require('worker_threads');

const PYODIDE_VERSION = '0.26.4';
const CDN_BASE = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
const NPM_META = `https://registry.npmjs.org/pyodide/${PYODIDE_VERSION}`;
const DEFAULT_PREFETCH = ['numpy', 'pandas', 'scipy', 'scikit-learn', 'matplotlib', 'pyyaml', 'pydantic', 'sqlite3'];
const SKIP_DIRS = new Set(['.git', 'node_modules', '.github', '.fastapi-venv', 'scripts', 'labs']);

/* ------------------------------------------------------------------------------------------ */
/* Python side helpers (executed inside the worker)                                            */
/* ------------------------------------------------------------------------------------------ */
const PY_ENV_SRC = `
import sys, os, shutil, types, warnings
warnings.filterwarnings('ignore', message='FigureCanvasAgg is non-interactive')
_mod = types.ModuleType('_grade_env')
_src = '''
import sys, os, shutil, warnings, __main__
_g0 = dict(__main__.__dict__)
_cwd = os.getcwd()
_path = list(sys.path)
_env = dict(os.environ)
_mods0 = set(sys.modules)
_filters = list(warnings.filters)
def _tree(root):
    out = set()
    for dp, dn, fn in os.walk(root):
        for n in dn + fn:
            out.add(os.path.join(dp, n))
    return out
_roots = [_cwd, '/tmp']
_fs0 = set()
for _r in _roots:
    if os.path.isdir(_r):
        _fs0 |= _tree(_r)
def reset():
    d = __main__.__dict__
    for k in list(d):
        if k not in _g0:
            del d[k]
    d.update(_g0)
    try:
        os.chdir(_cwd)
    except Exception:
        pass
    sys.path[:] = _path
    os.environ.clear(); os.environ.update(_env)
    warnings.filters[:] = _filters
    for r in _roots:
        if not os.path.isdir(r):
            continue
        for p in sorted(_tree(r) - _fs0, key=len, reverse=True):
            try:
                if os.path.isdir(p) and not os.path.islink(p):
                    shutil.rmtree(p, ignore_errors=True)
                elif os.path.lexists(p):
                    os.remove(p)
            except Exception:
                pass
    for name in list(sys.modules):
        if name in _mods0:
            continue
        f = getattr(sys.modules[name], '__file__', None) or ''
        if f.startswith(_cwd) or f.startswith('/tmp'):
            sys.modules.pop(name, None)
    plt = sys.modules.get('matplotlib.pyplot')
    if plt is not None:
        try:
            plt.close('all')
        except Exception:
            pass
'''
exec(_src, _mod.__dict__)
sys.modules['_grade_env'] = _mod
`;

const PY_SYNTAX_SRC = `
import ast, json
def _check(code):
    lines = [('' if l.lstrip().startswith(('!', '%')) else l) for l in code.split('\\n')]
    try:
        ast.parse('\\n'.join(lines))
        return ''
    except SyntaxError as e:
        return f'SyntaxError: {e.msg} (line {e.lineno})'
`;

/* ------------------------------------------------------------------------------------------ */
/* Worker thread                                                                               */
/* ------------------------------------------------------------------------------------------ */
async function workerMain() {
  const { pyoDir, cacheDir, verbose, interruptBuffer } = workerData;
  if (!verbose) { console.log = console.warn = console.info = () => {}; }
  const ib = new Int32Array(interruptBuffer);
  let py;
  try {
    const { loadPyodide } = require(path.join(pyoDir, 'pyodide.js'));
    py = await loadPyodide({
      indexURL: pyoDir + '/',
      packageCacheDir: cacheDir,
      stdin: () => undefined,
      env: { MPLBACKEND: 'agg' },
    });
    py.setInterruptBuffer(ib);
    py.runPython(PY_ENV_SRC);
    py.runPython(PY_SYNTAX_SRC);
  } catch (e) {
    parentPort.postMessage({ type: 'init-failed', error: String((e && e.message) || e) });
    return;
  }
  parentPort.postMessage({ type: 'ready' });

  const loadedPkgs = new Set();
  async function loadPackages(code) {
    let lastErr;
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        await py.loadPackagesFromImports(code, {
          messageCallback: (m) => { const mm = /^Loaded (.*)$/.exec(m); if (mm) mm[1].split(', ').forEach((p) => loadedPkgs.add(p)); },
          errorCallback: () => {},
        });
        if (/\bseaborn\b/.test(code) && !loadedPkgs.has('__seaborn')) {
          await py.loadPackage('micropip');
          await py.runPythonAsync("import micropip\nawait micropip.install('seaborn')");
          loadedPkgs.add('__seaborn');
        }
        return null;
      } catch (e) { lastErr = e; }
    }
    return String((lastErr && lastErr.message) || lastErr);
  }

  parentPort.on('message', async (msg) => {
    const { id } = msg;
    try {
      if (msg.type === 'reset') {
        py.runPython('import _grade_env; _grade_env.reset()');
        parentPort.postMessage({ id, type: 'result', ok: true });
      } else if (msg.type === 'syntax') {
        py.globals.set('__grade_code', msg.code);
        const r = py.runPython('_check(__grade_code)');
        py.runPython('del __grade_code');
        parentPort.postMessage({ id, type: 'result', ok: true, error: r });
      } else if (msg.type === 'packages') {
        parentPort.postMessage({ id, type: 'result', ok: true, packages: [...loadedPkgs].sort() });
      } else if (msg.type === 'exec') {
        let out = '';
        py.setStdout({ batched: (s) => { out += s + '\n'; } });
        py.setStderr({ batched: (s) => { out += s + '\n'; } });
        let ok = true; let err = ''; let tb = '';
        const perr = await loadPackages(msg.code);
        parentPort.postMessage({ id, type: 'started' });
        if (perr) { ok = false; err = 'PackageLoadError: ' + perr.trim().split('\n').slice(-1)[0]; }
        else {
          Atomics.store(ib, 0, 0);
          try { await py.runPythonAsync(msg.code); }
          catch (e) {
            ok = false;
            const m = String((e && e.message) || e).trim();
            tb = m;
            const lines = m.split('\n').filter((l) => l.trim());
            err = lines[lines.length - 1] || 'Error';
          }
        }
        py.setStdout({}); py.setStderr({});
        parentPort.postMessage({ id, type: 'result', ok, out, err, tb });
      }
    } catch (e) {
      parentPort.postMessage({ id, type: 'result', ok: false, out: '', err: 'HarnessError: ' + String((e && e.message) || e), tb: '' });
    }
  });
}

/* ------------------------------------------------------------------------------------------ */
/* Main-thread wrapper around one Pyodide worker                                               */
/* ------------------------------------------------------------------------------------------ */
class PyWorker {
  constructor(cfg) {
    this.cfg = cfg;
    this.history = []; // codes of successful shared-session snippets, replayed after a hard kill
    this.seq = 0;
    this.w = null;
    this.needRestart = false;
    this.pending = new Map();
  }

  async start() {
    this.sab = new SharedArrayBuffer(4);
    this.ib = new Int32Array(this.sab);
    const cfg = this.cfg;
    let lastErr = 'unknown';
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        await new Promise((resolve, reject) => {
          const w = new Worker(__filename, {
            workerData: { pyoDir: cfg.pyoDir, cacheDir: cfg.cacheDir, verbose: cfg.verbose, interruptBuffer: this.sab },
          });
          this.w = w;
          const timer = setTimeout(() => { w.terminate(); reject(new Error('Pyodide start timeout')); }, 240000);
          w.on('message', (m) => {
            if (m.type === 'ready') { clearTimeout(timer); resolve(); }
            else if (m.type === 'init-failed') { clearTimeout(timer); w.terminate(); reject(new Error(m.error)); }
            else this._onMessage(m);
          });
          w.on('error', (e) => { clearTimeout(timer); this._crash('worker error: ' + (e && e.message)); reject(e); });
          w.on('exit', (code) => { this._crash('worker exited (code ' + code + ')'); });
        });
        this.needRestart = false;
        return;
      } catch (e) { lastErr = String((e && e.message) || e); }
    }
    throw new Error('could not start Pyodide: ' + lastErr);
  }

  _onMessage(m) {
    const p = this.pending.get(m.id);
    if (!p) return;
    if (m.type === 'started') { p.started && p.started(); return; }
    this.pending.delete(m.id);
    p.resolve(m);
  }

  _crash(reason) {
    this.needRestart = true;
    for (const [id, p] of this.pending) { this.pending.delete(id); p.resolve({ type: 'result', ok: false, out: '', err: 'HarnessError: ' + reason, tb: '', crashed: true }); }
  }

  _call(msg, { execTimeout = 60000, loadTimeout = 300000 } = {}) {
    const id = ++this.seq;
    return new Promise((resolve) => {
      const p = { resolve: null, started: null };
      let loadTimer = null; let execTimer = null; let graceTimer = null; let timedOut = false; let hard = false;
      const finish = (m) => { clearTimeout(loadTimer); clearTimeout(execTimer); clearTimeout(graceTimer); resolve({ ...m, timedOut, hard }); };
      p.resolve = finish;
      p.started = () => {
        clearTimeout(loadTimer);
        if (msg.type !== 'exec') return;
        execTimer = setTimeout(() => {
          timedOut = true;
          Atomics.store(this.ib, 0, 2); // SIGINT -> KeyboardInterrupt inside Python
          graceTimer = setTimeout(() => { hard = true; this.needRestart = true; this.w.terminate(); this.pending.delete(id); finish({ type: 'result', ok: false, out: '', err: 'Timeout', tb: '' }); }, 10000);
        }, execTimeout);
      };
      this.pending.set(id, p);
      if (msg.type === 'exec') {
        loadTimer = setTimeout(() => { timedOut = true; hard = true; this.needRestart = true; this.w.terminate(); this.pending.delete(id); finish({ type: 'result', ok: false, out: '', err: 'Timeout while loading packages', tb: '' }); }, loadTimeout);
      }
      this.w.postMessage({ ...msg, id });
    });
  }

  async _ensure() {
    if (!this.needRestart) return;
    await this.start();
    const hist = this.history.slice();
    for (const code of hist) await this._call({ type: 'exec', code }, { execTimeout: this.cfg.timeoutMs });
  }

  /** Run code. shared=true keeps state (lesson blocks); otherwise run from a clean namespace. */
  async exec(code, { shared = false, timeoutMs } = {}) {
    await this._ensure();
    if (!shared) await this._call({ type: 'reset' });
    const r = await this._call({ type: 'exec', code }, { execTimeout: timeoutMs || this.cfg.timeoutMs });
    if (shared && r.ok) this.history.push(code);
    const res = { ok: !!r.ok, out: r.out || '', err: r.err || '', tb: r.tb || '', timedOut: !!r.timedOut };
    if (res.timedOut && !res.err) res.err = 'Timeout';
    if (res.timedOut) res.err = `Timeout after ${(timeoutMs || this.cfg.timeoutMs) / 1000}s` + (r.hard ? ' (worker killed)' : ' (interrupted)');
    return res;
  }

  async syntax(code) { await this._ensure(); const r = await this._call({ type: 'syntax', code }); return r.error || ''; }
  async packages() { if (this.needRestart) return []; const r = await this._call({ type: 'packages' }); return r.packages || []; }
  async close() { if (this.w) { try { await this.w.terminate(); } catch (e) { /* ignore */ } } }
}

/* ------------------------------------------------------------------------------------------ */
/* HTML extraction                                                                             */
/* ------------------------------------------------------------------------------------------ */
function decodeEntities(s) {
  return s.replace(/&(#x[0-9a-fA-F]+|#[0-9]+|lt|gt|quot|apos|amp|nbsp);/g, (m, e) => {
    if (e[0] === '#') {
      const cp = e[1] === 'x' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
      try { return String.fromCodePoint(cp); } catch (x) { return m; }
    }
    return { lt: '<', gt: '>', quot: '"', apos: "'", amp: '&', nbsp: ' ' }[e];
  });
}
// exactly what a browser's textContent does for a highlighted code block
const unesc = (s) => decodeEntities(s.replace(/<!--[\s\S]*?-->/g, '').replace(/<\/?[A-Za-z][^>]*>/g, ''));
const lineOf = (html, idx) => html.slice(0, idx).split('\n').length;

function extractLessonBlocks(html) {
  const re = /<div class="code-block">\s*<div class="cb-header">([\s\S]*?)<\/div>\s*<div class="cb-code">([\s\S]*?)<\/div>\s*<\/div>/g;
  const blocks = []; let m; let i = 0;
  while ((m = re.exec(html))) {
    i++;
    const label = unesc((/class="cb-label"[^>]*>([\s\S]*?)<\/span>/.exec(m[1]) || [])[1] || '').trim();
    blocks.push({ index: i, line: lineOf(html, m.index), label, runnable: /class="cb-run"/.test(m[1]), code: unesc(m[2]), pos: m.index });
  }
  return blocks;
}

function extractTextareas(html) {
  const re = /<textarea\b([^>]*)>([\s\S]*?)<\/textarea>/g; const map = {}; let m;
  while ((m = re.exec(html))) {
    const id = (/\bid="([^"]*)"/.exec(m[1]) || [])[1];
    if (!id) continue;
    let v = m[2].replace(/^\r?\n/, ''); // the HTML parser drops one leading newline
    map[id] = { value: decodeEntities(v).replace(/\r\n?/g, '\n'), pos: m.index, line: lineOf(html, m.index) };
  }
  return map;
}

function inlineScripts(html) {
  const out = []; const re = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g; let m;
  while ((m = re.exec(html))) out.push(m[1]);
  return out.join('\n;\n');
}

// Find the end of a JS expression starting at `start` by trial compilation (robust against braces in strings).
function sliceExpression(src, start, wrap) {
  const tryEnd = (j) => { try { new Function(wrap(src.slice(start, j + 1))); return true; } catch (e) { return false; } };
  let tries = 0;
  for (let j = src.indexOf('}', start); j !== -1 && tries < 4000; j = src.indexOf('}', j + 1)) {
    tries++;
    if (tryEnd(j)) return src.slice(start, j + 1);
  }
  return null;
}

function extractFunctionSource(script, name) {
  const re = new RegExp('(?:window\\.' + name + '\\s*=\\s*|\\bfunction\\s+' + name + '\\s*(?=\\())');
  const m = re.exec(script);
  if (!m) return null;
  let start = m.index + m[0].length;
  let text;
  if (/\bfunction\s/.test(m[0])) { // named declaration: "function name(...) {...}"
    start = m.index;
    text = sliceExpression(script, start, (s) => 'return (' + s.replace(/^(async\s+)?function\s+\w+/, '$1function') + ')');
    if (text) text = text.replace(/^(async\s+)?function\s+\w+/, '$1function');
  } else {
    text = sliceExpression(script, start, (s) => 'return (' + s + ')');
  }
  return text;
}

function extractExercises(script) {
  const mm = /const\s+EXERCISES\s*=\s*/.exec(script);
  if (!mm) return { error: 'no EXERCISES constant' };
  const start = mm.index + mm[0].length;
  let end = script.indexOf('\n};', start);
  let lit = null;
  if (end !== -1) { lit = script.slice(start, end + 2); try { new Function('return ' + lit); } catch (e) { lit = null; } }
  if (!lit) lit = sliceExpression(script, start, (s) => 'return (' + s + ')');
  if (!lit) return { error: 'could not delimit EXERCISES literal' };
  // EXERCISES may interpolate other top-level string constants (e.g. `${AGENT_CLASS_SRC}`): supply them on demand.
  const defs = {};
  for (let attempt = 0; attempt < 20; attempt++) {
    try {
      const names = Object.keys(defs);
      return { EX: new Function(...names, 'return (' + lit + ')')(...names.map((n) => defs[n])) };
    } catch (e) {
      const ref = /^(\w+) is not defined$/.exec(e.message);
      if (!ref || defs[ref[1]] !== undefined) return { error: 'EXERCISES did not evaluate: ' + e.message };
      const val = topLevelStringConst(script.slice(0, mm.index), ref[1]);
      if (val === null) return { error: `EXERCISES did not evaluate: ${e.message} (and no top-level string const of that name found)` };
      defs[ref[1]] = val;
    }
  }
  return { error: 'EXERCISES did not evaluate: too many dependent constants' };
}

function topLevelStringConst(src, name) {
  const m = new RegExp('const\\s+' + name + '\\s*=\\s*').exec(src);
  if (!m) return null;
  const st = m.index + m[0].length;
  if (!'"\'`'.includes(src[st])) return null;
  const en = scanJsString(src, st);
  if (en < 0) return null;
  try { return new Function('return ' + src.slice(st, en))(); } catch (e) { return null; }
}

function scanJsString(src, i) { // src[i] is a quote char; returns index after closing quote
  const q = src[i];
  for (let j = i + 1; j < src.length; j++) {
    if (src[j] === '\\') { j++; continue; }
    if (src[j] === q) return j + 1;
  }
  return -1;
}

function extractProjectReference(html, script, ta) {
  const m = /const\s+PROJECT_SOLUTION\s*=\s*/.exec(script);
  if (m) {
    const st = m.index + m[0].length;
    if (script[st] === '"' || script[st] === "'" || script[st] === '`') {
      const en = scanJsString(script, st);
      if (en > 0) { try { return { kind: 'PROJECT_SOLUTION', code: new Function('return ' + script.slice(st, en))() }; } catch (e) { /* fall through */ } }
    }
  }
  // reference code blocks inside a <details> that follows the project editor
  const pe = ta['project-editor'];
  if (!pe) return null;
  const rest = html.slice(pe.pos);
  const dm = /<details\b[\s\S]*?<\/details>/.exec(rest);
  if (!dm) return null;
  const inner = dm[0];
  if (!/reference solution/i.test(inner)) return null;
  const blocks = extractLessonBlocks(inner).filter((b) => !b.runnable).map((b) => b.code);
  if (!blocks.length) return null;
  return { kind: 'details-blocks', code: blocks.join('\n\n'), appendToStarter: true };
}

function extractCheckItems(html) {
  const items = []; const re = /<div[^>]*class="check-item"[^>]*>/g; let m;
  while ((m = re.exec(html))) { const a = /data-check="([^"]*)"/.exec(m[0]); if (a) items.push(decodeEntities(a[1])); }
  return items;
}

/* ------------------------------------------------------------------------------------------ */
/* Running the page's own project grader against a stubbed DOM                                 */
/* ------------------------------------------------------------------------------------------ */
function makeEl(props) {
  const cls = new Set();
  const el = {
    value: '', textContent: '', innerHTML: '', className: '', style: {}, dataset: {}, children: [],
    classList: { toggle() {}, add() {}, remove() {}, contains: () => false },
    appendChild() {}, setAttribute() {}, getAttribute: () => null, addEventListener() {}, remove() {}, querySelector: () => null, querySelectorAll: () => [],
    scrollTop: 0, scrollHeight: 0,
  };
  void cls;
  return Object.assign(el, props || {});
}

/** Returns {passed, message} for `code` graded by the page's own runProject (async, runs Python) or checkProject (sync). */
async function gradeProjectWithPageFn(fnName, fnSrc, code, ctx) {
  const els = new Map();
  const getEl = (id) => { if (!els.has(id)) els.set(id, makeEl()); return els.get(id); };
  getEl('project-editor').value = code;
  const items = ctx.checkItems.map((c) => makeEl({ getAttribute: (n) => (n === 'data-check' ? c : null) }));
  const doc = {
    getElementById: getEl,
    querySelectorAll: (sel) => (/check-item/.test(sel) ? items : []),
    querySelector: () => makeEl(), createElement: () => makeEl(), body: makeEl(), addEventListener() {},
  };
  let pyErr = null;
  const scope = {
    document: doc, window: {}, completedItems: new Set(), xp: 0,
    updateUI() {}, spark() {}, persistChapter() {}, clog() {}, console,
    runPy: async (c) => { const r = await ctx.worker.exec(c, { timeoutMs: ctx.timeoutMs }); if (r.timedOut) pyErr = r.err; return { ok: r.ok, out: r.out, err: r.err }; },
  };
  const proxy = new Proxy(scope, {
    has: (t, k) => typeof k === 'string',
    get: (t, k) => {
      if (k === Symbol.unscopables) return undefined;
      if (k in t) return t[k];
      if (k in globalThis) return globalThis[k];
      return function noop() {};
    },
    set: (t, k, v) => { t[k] = v; return true; },
  });
  const fn = new Function('__scope', 'with(__scope){ return (' + fnSrc + '); }')(proxy);
  await fn();
  const res = getEl('project-result');
  return { passed: /(^|\s)pass(\s|$)/.test(res.className), message: String(res.textContent || ''), pyErr };
}

/* ------------------------------------------------------------------------------------------ */
/* Grading one chapter                                                                         */
/* ------------------------------------------------------------------------------------------ */
const userTrace = (tb) => { const l = String(tb || '').split('\n'); const i = l.findIndex((x) => x.includes('File "<exec>"')); return (i >= 0 ? l.slice(i) : l).join('\n'); };
const tailLines = (s, n = 12) => { const l = String(s || '').replace(/\n+$/, '').split('\n'); return l.slice(-n).map((x) => (x.length > 220 ? x.slice(0, 217) + '...' : x)).join('\n'); };
const norm = (s) => s.replace(/#.*$/gm, '').toLowerCase().replace(/\s/g, '');

async function gradeChapter(file, root, cfg, log) {
  const rel = path.relative(root, file).split(path.sep).join('/');
  const html = fs.readFileSync(file, 'utf8');
  const script = inlineScripts(html);
  const res = {
    file: rel, kind: 'static', status: 'ok', seconds: 0,
    lesson: { total: 0, passed: 0 }, exercises: { total: 0, solutionsPassed: 0, starterOk: 0 },
    project: { status: 'none' }, packages: [], failures: [], warnings: [],
  };
  const fail = (phase, id, cls, message, detail) => res.failures.push({ key: `${rel}::${phase}::${id}`, phase, id, cls, message, detail: detail || {} });
  const t0 = Date.now();

  const isColab = /window\.checkTextEx\s*=/.test(script);
  const hasRunPy = /function\s+runPy\s*\(/.test(script) && /window\.runExercise\s*=/.test(script);
  const hasExercises = /const\s+EXERCISES\s*=/.test(script);
  if (!hasExercises && !isColab && !hasRunPy) { res.status = 'skipped'; res.note = 'no graded content'; return res; }
  res.kind = isColab ? 'colab' : 'pyodide';

  const ta = extractTextareas(html);
  const blocks = extractLessonBlocks(html);
  const ex = extractExercises(script);
  if (ex.error) { fail('structure', 'EXERCISES', 'harness', ex.error); res.status = 'failed'; return res; }
  const EX = ex.EX;
  const exNums = Object.keys(EX).map(Number).sort((a, b) => a - b);
  res.exercises.total = exNums.length;

  // structural sanity
  const editorIds = Object.keys(ta).filter((k) => /^ex\d+-code$/.test(k)).map((k) => Number(/\d+/.exec(k)[0]));
  for (const n of exNums) if (!ta[`ex${n}-code`]) fail('structure', `ex${n}`, 'structure', `EXERCISES[${n}] has no starter textarea #ex${n}-code`);
  for (const n of editorIds) if (!EX[n]) fail('structure', `ex${n}`, 'structure', `textarea #ex${n}-code has no EXERCISES[${n}] entry`);
  for (const n of exNums) {
    const e = EX[n];
    if (typeof e.solution !== 'string' || !e.solution.trim()) fail('structure', `ex${n}`, 'structure', `EXERCISES[${n}] has no solution`);
    if ((!Array.isArray(e.checks) || !e.checks.length) && typeof e.checkFn !== 'function') fail('structure', `ex${n}`, 'structure', `EXERCISES[${n}] has no checks (anything would pass)`);
  }
  const runEx = extractFunctionSource(script, 'runExercise');
  if (!isColab) {
    if (!runEx) res.warnings.push('page defines no runExercise(); grading with the standard rules');
    else {
      if (exNums.some((n) => typeof EX[n].checkFn === 'function') && !/checkFn/.test(runEx)) fail('structure', 'checkFn', 'chapter', 'EXERCISES define checkFn but the page runExercise() never calls it');
      // the page lower-cases the output; most pages also lower-case each check, a few (sf04) compare the raw check string
      if (!/includes\(\s*c\.toLowerCase\(\)\s*\)/.test(runEx)) {
        if (/lower\.includes\(\s*c\s*\)|toLowerCase\(\)\.includes\(\s*c\s*\)/.test(runEx)) res.strictChecks = true;
        else res.warnings.push('runExercise() uses an unrecognised check comparison; verify grading semantics by hand');
      }
    }
  }

  const passesChecks = (e, fullOut, lowerFull) => {
    const missing = (e.checks || []).filter((c) => !lowerFull.includes(res.strictChecks ? String(c) : String(c).toLowerCase()));
    if (missing.length) return { pass: false, why: 'checks', missing };
    if (typeof e.checkFn === 'function') {
      let v = false; try { v = !!e.checkFn(fullOut); } catch (x) { return { pass: false, why: 'checkFn-throws', error: String(x.message || x) }; }
      if (!v) return { pass: false, why: 'checkFn' };
    }
    return { pass: true };
  };

  // project bits
  const projFnName = /window\.runProject\s*=/.test(script) ? 'runProject' : (/window\.checkProject\s*=/.test(script) ? 'checkProject' : null);
  const projSrc = projFnName ? extractFunctionSource(script, projFnName) : null;
  const projStarter = ta['project-editor'] ? ta['project-editor'].value : null;
  const projRef = extractProjectReference(html, script, ta);
  res.project.status = projFnName ? 'starter-only' : 'none';

  const worker = new PyWorker(cfg);
  try {
    await worker.start();
  } catch (e) {
    fail('harness', 'pyodide-start', 'harness', String(e.message || e));
    res.status = 'failed'; res.seconds = (Date.now() - t0) / 1000; return res;
  }
  const timeoutMs = cfg.timeoutMs;
  try {
    /* --- colab (pattern-matching) chapters --- */
    if (isColab) {
      for (const n of exNums) {
        const e = EX[n]; const checks = (e.checks || []).map(norm);
        const sol = norm(e.solution || '');
        const missing = checks.filter((c) => !sol.includes(c));
        if (missing.length) fail('solution', `ex${n}`, 'chapter', `solution does not satisfy its own checks: missing ${JSON.stringify(missing)}`, { missing });
        else res.exercises.solutionsPassed++;
        const syn = await worker.syntax(e.solution || '');
        if (syn) fail('solution-syntax', `ex${n}`, 'chapter', `solution is not valid Python: ${syn}`);
        const st = ta[`ex${n}-code`];
        if (st) {
          const sn = norm(st.value);
          if (checks.every((c) => sn.includes(c))) fail('starter', `ex${n}`, 'chapter', 'starter code already passes its own checkTextEx grader (commented-out lines count as matches)');
          else res.exercises.starterOk++;
        }
      }
    } else {
      /* --- lesson blocks: one shared session, document order --- */
      const runnable = blocks.filter((b) => b.runnable);
      res.lesson.total = runnable.length;
      for (const b of runnable) {
        const r = await worker.exec(b.code, { shared: true, timeoutMs });
        if (r.ok) res.lesson.passed++;
        else fail('lesson', `block${b.index}`, 'error', `lesson block #${b.index} (line ${b.line}${b.label ? ', "' + b.label + '"' : ''}) failed: ${r.err}`, { error: r.err, traceback: tailLines(userTrace(r.tb), 8), output: tailLines(r.out), code: b.code.split('\n').slice(0, 3).join('\n') });
      }
      /* --- exercises: solution must pass, starter must not --- */
      for (const n of exNums) {
        const e = EX[n];
        const r = await worker.exec(e.solution || '', { timeoutMs });
        const full = r.out + (!r.ok && r.err ? '\n' + r.err : '');
        let v;
        if (!r.ok) v = { pass: false, why: r.timedOut ? 'timeout' : 'error' };
        else v = passesChecks(e, full, full.toLowerCase());
        if (v.pass) res.exercises.solutionsPassed++;
        else {
          const msg = v.why === 'error' ? `reference solution raises: ${r.err}`
            : v.why === 'timeout' ? `reference solution ${r.err}`
              : v.why === 'checks' ? `reference solution runs but output lacks required check(s) ${JSON.stringify(v.missing)}`
                : v.why === 'checkFn' ? 'reference solution runs but checkFn(output) is false'
                  : `checkFn threw: ${v.error}`;
          fail('solution', `ex${n}`, v.why, msg, { missing: v.missing, error: r.err, traceback: tailLines(userTrace(r.tb), 8), output: tailLines(r.out) });
        }
        const st = ta[`ex${n}-code`];
        if (st && st.value.trim()) {
          const s = await worker.exec(st.value, { timeoutMs: Math.min(timeoutMs, 20000) });
          const sfull = s.out + (!s.ok && s.err ? '\n' + s.err : '');
          const sv = s.ok ? passesChecks(e, sfull, sfull.toLowerCase()) : { pass: false };
          if (sv.pass) fail('starter', `ex${n}`, 'starter-passes', 'starter code already passes its own grader without the learner writing anything', { output: tailLines(sfull, 6) });
          else res.exercises.starterOk++;
        } else if (st) res.exercises.starterOk++;
      }
    }

    /* --- project / capstone --- */
    if (projFnName && !projSrc) {
      fail('project', 'grader', 'harness', `could not extract ${projFnName}() from the page`);
    } else if (projFnName) {
      const ctx = { worker, timeoutMs, checkItems: extractCheckItems(html) };
      if (projStarter !== null && projStarter.trim()) {
        try {
          const g = await gradeProjectWithPageFn(projFnName, projSrc, projStarter, ctx);
          if (g.passed) fail('project-starter', 'project', 'starter-passes', 'project starter already passes the project grader');
        } catch (e) { res.warnings.push(`project grader not emulated (${e.message}); project starter not checked`); }
      }
      if (projRef && projFnName === 'runProject') {
        res.project.status = 'reference:' + projRef.kind;
        const candidates = projRef.appendToStarter && projStarter ? [['starter+reference', projStarter + '\n\n' + projRef.code], ['reference-only', projRef.code]] : [['reference', projRef.code]];
        let ok = false; let last = null;
        for (const [mode, code] of candidates) {
          try {
            const g = await gradeProjectWithPageFn(projFnName, projSrc, code, ctx);
            last = { mode, ...g };
            if (g.passed) { ok = true; res.project.mode = mode; break; }
          } catch (e) { last = { mode, passed: false, message: 'grader stub error: ' + e.message }; }
        }
        if (!ok && projRef.kind === 'details-blocks') res.warnings.push(`partial reference (details block) does not complete the project on its own: ${last.message}`);
        else if (!ok) fail('project-solution', 'project', 'chapter', `reference project solution does not pass the project grader (${last.mode}): ${last.message}`, { pyErr: last.pyErr || undefined });
      } else if (projFnName === 'runProject' && !projStarter) {
        res.project.status = 'no-starter';
      } else {
        res.project.status = projFnName === 'runProject' ? 'no-reference' : 'no-reference (pattern grader)';
      }
    }
    res.packages = await worker.packages();
  } finally {
    await worker.close();
  }
  res.seconds = Math.round((Date.now() - t0) / 100) / 10;
  res.status = res.failures.length ? 'failed' : 'ok';
  log && log(`  ${res.status === 'ok' ? 'PASS' : 'FAIL'}  ${rel}  (${res.seconds}s)`);
  return res;
}

/* ------------------------------------------------------------------------------------------ */
/* Runtime provisioning                                                                        */
/* ------------------------------------------------------------------------------------------ */
async function fetchRetry(url, what, asJson) {
  let last;
  for (let i = 0; i < 3; i++) {
    try {
      const r = await fetch(url);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return asJson ? await r.json() : Buffer.from(await r.arrayBuffer());
    } catch (e) { last = e; await new Promise((res) => setTimeout(res, 1500 * (i + 1))); }
  }
  throw new Error(`download of ${what} failed: ${last && last.message}`);
}

function defaultHome() {
  if (process.env.PYODIDE_HOME) return process.env.PYODIDE_HOME;
  const base = process.env.XDG_CACHE_HOME || path.join(os.homedir(), '.cache');
  return path.join(base, `aiml-pyodide-${PYODIDE_VERSION}`);
}

async function setupRuntime(home, log, prefetch) {
  const core = path.join(home, 'core'); const pkgs = path.join(home, 'packages');
  fs.mkdirSync(pkgs, { recursive: true });
  if (!fs.existsSync(path.join(core, 'pyodide.js')) || !fs.existsSync(path.join(core, 'pyodide-lock.json'))) {
    log(`Fetching Pyodide ${PYODIDE_VERSION} core from npm ...`);
    const meta = await fetchRetry(NPM_META, 'npm metadata', true);
    const tgz = await fetchRetry(meta.dist.tarball, 'pyodide npm tarball');
    const integ = meta.dist.integrity; // "sha512-<base64>"
    if (integ && integ.startsWith('sha512-')) {
      const got = crypto.createHash('sha512').update(tgz).digest('base64');
      if (got !== integ.slice(7)) throw new Error('pyodide npm tarball integrity mismatch');
    }
    fs.mkdirSync(home, { recursive: true });
    const tmp = fs.mkdtempSync(path.join(home, 'dl-'));
    fs.writeFileSync(path.join(tmp, 'p.tgz'), tgz);
    execFileSync('tar', ['-xzf', path.join(tmp, 'p.tgz'), '-C', tmp]);
    fs.rmSync(core, { recursive: true, force: true });
    fs.renameSync(path.join(tmp, 'package'), core);
    fs.rmSync(tmp, { recursive: true, force: true });
  }
  if (prefetch) {
    const lock = JSON.parse(fs.readFileSync(path.join(core, 'pyodide-lock.json'), 'utf8')).packages;
    const byName = {}; for (const [k, v] of Object.entries(lock)) byName[k.toLowerCase().replace(/_/g, '-')] = v;
    const seen = new Set(); const todo = [...prefetch];
    while (todo.length) {
      const n = todo.pop().toLowerCase().replace(/_/g, '-');
      if (seen.has(n)) continue; seen.add(n);
      const p = byName[n]; if (!p) { log(`  (no such package in lock: ${n})`); continue; }
      (p.depends || []).forEach((d) => todo.push(d));
    }
    let fetched = 0;
    for (const n of [...seen].sort()) {
      const p = byName[n]; if (!p) continue;
      const dest = path.join(pkgs, p.file_name);
      if (fs.existsSync(dest)) continue;
      const buf = await fetchRetry(CDN_BASE + p.file_name, p.file_name);
      if (crypto.createHash('sha256').update(buf).digest('hex') !== p.sha256) throw new Error(`sha256 mismatch for ${p.file_name}`);
      fs.writeFileSync(dest + '.part', buf); fs.renameSync(dest + '.part', dest); fetched++;
    }
    log(`Package cache ready: ${seen.size} packages (${fetched} downloaded) in ${pkgs}`);
  }
  return { pyoDir: core, cacheDir: pkgs };
}

/* ------------------------------------------------------------------------------------------ */
/* CLI                                                                                         */
/* ------------------------------------------------------------------------------------------ */
function parseArgs(argv) {
  const a = { folders: null, files: [], json: null, timeout: 60, jobs: 1, baseline: null, verbose: false, list: false, setup: false, strictBaseline: false, pyodide: null, cacheDir: null };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i]; const val = () => { if (i + 1 >= argv.length) throw new Error(`${t} needs a value`); return argv[++i]; };
    if (t === '--folder' || t === '--folders') a.folders = val().split(',').map((s) => s.trim().replace(/\/$/, '')).filter(Boolean);
    else if (t === '--file') a.files.push(val());
    else if (t === '--json') a.json = '-';
    else if (t.startsWith('--json=')) a.json = t.slice(7);
    else if (t === '--timeout') a.timeout = Number(val());
    else if (t === '--jobs') a.jobs = Math.max(1, Number(val()));
    else if (t === '--baseline') a.baseline = val();
    else if (t === '--strict-baseline') a.strictBaseline = true;
    else if (t === '--pyodide') a.pyodide = val();
    else if (t === '--cache-dir') a.cacheDir = val();
    else if (t === '--verbose' || t === '-v') a.verbose = true;
    else if (t === '--list') a.list = true;
    else if (t === '--setup') a.setup = true;
    else if (t === '-h' || t === '--help') { console.log(fs.readFileSync(__filename, 'utf8').split('*/')[0].replace(/^\/\*\n?/, '')); process.exit(0); }
    else throw new Error(`unknown argument ${t}`);
  }
  if (!(a.timeout > 0)) throw new Error('--timeout must be positive');
  return a;
}

function walk(dir, out) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP_DIRS.has(e.name)) continue;
    const full = path.join(dir, e.name);
    if (e.isDirectory()) walk(full, out); else if (e.name.endsWith('.html')) out.push(full);
  }
  return out;
}

async function main() {
  let args;
  try { args = parseArgs(process.argv.slice(2)); } catch (e) { console.error('Usage error: ' + e.message + '  (see --help)'); process.exit(2); }
  const root = path.resolve(__dirname, '..');
  const jsonToStdout = args.json === '-';
  const say = (s) => (jsonToStdout ? console.error(s) : console.log(s));

  let files = args.files.length ? args.files.map((f) => path.resolve(f)) : walk(root, []).sort();
  if (args.folders) files = files.filter((f) => args.folders.includes(path.relative(root, f).split(path.sep)[0]));
  files = files.filter((f) => path.relative(root, f).includes(path.sep) || args.files.length); // root index.html has nothing to grade
  if (!args.setup && !files.length) { console.error('No chapter files matched.'); process.exit(2); }
  if (args.list) { files.forEach((f) => console.log(path.relative(root, f))); return; }

  let rt;
  try {
    if (args.pyodide) rt = { pyoDir: path.resolve(args.pyodide), cacheDir: path.resolve(args.cacheDir || args.pyodide) };
    else {
      rt = await setupRuntime(defaultHome(), say, args.setup ? DEFAULT_PREFETCH : null);
      if (args.cacheDir) rt.cacheDir = path.resolve(args.cacheDir);
    }
    if (!fs.existsSync(path.join(rt.pyoDir, 'pyodide.js'))) throw new Error(`no pyodide.js in ${rt.pyoDir}`);
  } catch (e) { console.error('SETUP ERROR: ' + e.message); process.exit(2); }
  if (args.setup) { say(`Pyodide runtime ready in ${rt.pyoDir}`); return; }

  let baseline = new Map();
  if (args.baseline) {
    try { for (const k of JSON.parse(fs.readFileSync(args.baseline, 'utf8')).known || []) baseline.set(k.key, k); }
    catch (e) { console.error('Cannot read baseline: ' + e.message); process.exit(2); }
  }

  const cfg = { pyoDir: rt.pyoDir, cacheDir: rt.cacheDir, verbose: args.verbose, timeoutMs: args.timeout * 1000 };
  say(`Grading ${files.length} chapter file(s) with Pyodide ${PYODIDE_VERSION} (timeout ${args.timeout}s/snippet, jobs ${args.jobs})`);
  const results = new Array(files.length); let next = 0;
  async function lane() {
    while (next < files.length) {
      const i = next++;
      try { results[i] = await gradeChapter(files[i], root, cfg, null); }
      catch (e) {
        const rel = path.relative(root, files[i]).split(path.sep).join('/');
        results[i] = { file: rel, kind: '?', status: 'failed', seconds: 0, lesson: { total: 0, passed: 0 }, exercises: { total: 0, solutionsPassed: 0, starterOk: 0 }, project: { status: '?' }, packages: [], warnings: [], failures: [{ key: `${rel}::harness::crash`, phase: 'harness', id: 'crash', cls: 'harness', message: 'harness crashed: ' + (e.stack || e.message), detail: {} }] };
      }
      const r = results[i];
      say(`${r.status === 'ok' ? 'PASS' : r.status === 'skipped' ? 'SKIP' : 'FAIL'}  ${r.file}  [${r.kind}]  lesson ${r.lesson.passed}/${r.lesson.total}  solutions ${r.exercises.solutionsPassed}/${r.exercises.total}  starters-ok ${r.exercises.starterOk}/${r.exercises.total}  project:${r.project.status}  (${r.seconds}s)`);
      for (const f of r.failures) {
        const known = baseline.has(f.key);
        say(`      ${known ? 'KNOWN' : 'FAILED'} [${f.phase} ${f.id}] ${f.message}`);
        if (args.verbose || !known) {
          if (f.detail.traceback) say('         ' + f.detail.traceback.split('\n').join('\n         '));
          else if (f.detail.output) say('         output: ' + f.detail.output.split('\n').join('\n                 '));
        }
      }
      for (const w of r.warnings) say(`      warn: ${w}`);
    }
  }
  await Promise.all(Array.from({ length: Math.min(args.jobs, files.length) }, lane));

  // baseline bookkeeping
  const allFailures = results.flatMap((r) => r.failures.map((f) => ({ ...f, file: r.file })));
  const newFailures = allFailures.filter((f) => !baseline.has(f.key));
  const knownFailures = allFailures.filter((f) => baseline.has(f.key));
  const failedKeys = new Set(allFailures.map((f) => f.key));
  const scopedFiles = new Set(results.map((r) => r.file));
  const fixed = [...baseline.keys()].filter((k) => scopedFiles.has(k.split('::')[0]) && !failedKeys.has(k));

  const summary = {
    pyodide: PYODIDE_VERSION,
    chapters: results.length,
    ok: results.filter((r) => r.status === 'ok').length,
    failedChapters: results.filter((r) => r.status === 'failed').length,
    skipped: results.filter((r) => r.status === 'skipped').length,
    failures: allFailures.length, newFailures: newFailures.length, knownFailures: knownFailures.length, fixedBaselineEntries: fixed,
    lessonBlocks: { total: results.reduce((s, r) => s + r.lesson.total, 0), passed: results.reduce((s, r) => s + r.lesson.passed, 0) },
    exercises: { total: results.reduce((s, r) => s + r.exercises.total, 0), solutionsPassed: results.reduce((s, r) => s + r.exercises.solutionsPassed, 0), startersOk: results.reduce((s, r) => s + r.exercises.starterOk, 0) },
    packagesLoaded: [...new Set(results.flatMap((r) => r.packages))].sort(),
    ok_exit: newFailures.length === 0 && !(args.strictBaseline && fixed.length),
    results: results.map((r) => ({ ...r, failures: r.failures.map((f) => ({ ...f, known: baseline.has(f.key) })) })),
  };
  say('');
  say(`Chapters: ${summary.ok} ok, ${summary.failedChapters} failed, ${summary.skipped} skipped | lesson blocks ${summary.lessonBlocks.passed}/${summary.lessonBlocks.total} | solutions ${summary.exercises.solutionsPassed}/${summary.exercises.total} | starters ok ${summary.exercises.startersOk}/${summary.exercises.total}`);
  say(`Failures: ${summary.failures} total = ${summary.newFailures} new + ${summary.knownFailures} known (baselined)`);
  if (fixed.length) say(`FIXED - remove from baseline: ${fixed.join(', ')}`);
  if (newFailures.length) { say('New failures:'); newFailures.forEach((f) => say(`  ${f.key}  ${f.message}`)); }
  if (args.json) {
    const txt = JSON.stringify(summary, null, 2) + '\n';
    if (jsonToStdout) process.stdout.write(txt); else fs.writeFileSync(args.json, txt);
  }
  process.exitCode = summary.ok_exit ? 0 : 1;
}

if (isMainThread) {
  main().then(() => setTimeout(() => process.exit(process.exitCode || 0), 50)).catch((e) => { console.error('ERROR: ' + (e.stack || e.message)); process.exit(2); });
} else {
  workerMain();
}
