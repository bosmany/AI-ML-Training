/* AI/ML: Zero to Hero - site search (command palette).
 * Ctrl/Cmd+K or "/" opens it (anywhere except while typing in a field); Esc closes.
 * The index (assets/search-index.json, built by scripts/build-search-index.py) is fetched lazily on first open
 * and turned into a small in-memory inverted index: exact + prefix + light fuzzy matching, per-field boosts.
 * Results open `page#:~:text=<heading>` (browser text fragment, scrolls to and highlights the heading) or the plain page.
 * Needs http(s) (GitHub Pages / python -m http.server); over file:// the palette explains that and stays usable as a launcher.
 */
(function () {
  'use strict';
  if (window.__aimlSearch) return;
  window.__aimlSearch = true;

  var script = document.currentScript;
  var base = script && script.src ? script.src : '';
  var ROOT = '', INDEX_URL = '';
  try { ROOT = new URL('../', base).href; INDEX_URL = new URL('search-index.json', base).href; } catch (e) { /* file:// odd cases */ }

  // ---- field boosts -----------------------------------------------------------
  var W = { page: 10, g: 8.5, h: 6, h3: 4, k: 4.2, x: 3.6, i: 2.6, r: 2.2 };
  var LABEL = { page: 'Page', g: 'Glossary', h: 'Section', h3: 'Topic', k: 'Key term', x: 'Code term', i: 'Note', r: 'Recap' };
  var MAX_RESULTS = 30, PER_PAGE = 3;

  var state = { ready: false, loading: false, failed: false, units: [], pages: [], domains: {}, vocab: [], post: null };
  var ui = {}, open = false, lastFocus = null, results = [], active = -1, qTimer;

  // ---- text helpers -----------------------------------------------------------
  function stem(t) {
    if (t.length > 4 && /(ss|x|ch|sh)es$/.test(t)) return t.slice(0, -2);
    if (t.length > 3 && /[^su]s$/.test(t)) return t.slice(0, -1);
    return t;
  }
  function tokens(s) {
    var out = [], m = String(s).toLowerCase().match(/[a-z0-9_]+/g) || [];
    for (var i = 0; i < m.length; i++) {
      var w = m[i].replace(/^_+|_+$/g, '');
      if (!w) continue;
      out.push(stem(w));
      if (w.indexOf('_') > 0) w.split('_').forEach(function (p) { if (p) out.push(stem(p)); });
    }
    return out;
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function frag(text) {
    var t = String(text).replace(/…$/, '').trim();
    if (t.length > 80) t = t.slice(0, 80).replace(/\s+\S*$/, '');
    return '#:~:text=' + encodeURIComponent(t).replace(/-/g, '%2D');
  }
  function chapLabel(p) {
    if (!p || !p.c) return '';
    var m = /^ch0*(\d+)$/.exec(p.c);
    return m ? 'Ch ' + m[1] : ''; // other series (OOP, DSA, DevOps...) already carry their number in the title
  }

  // ---- index ----------------------------------------------------------------------
  function addUnit(type, text, pi, extra) {
    var u = { type: type, text: text, p: pi, w: W[type] };
    if (extra) for (var k in extra) u[k] = extra[k];
    state.units.push(u);
  }
  function build(data) {
    state.pages = data.p; state.domains = data.d || {};
    data.p.forEach(function (p, pi) {
      var cn = /^ch0*(\d+)$/.exec(p.c || ''), ctx = [p.t, p.c || '', cn ? 'chapter ' + cn[1] : '', state.domains[p.f] || '', p.f || ''].join(' ');
      addUnit('page', p.t, pi, { hay: ctx, href: p.u });
      (p.h || []).forEach(function (h) { addUnit('h', h, pi, { href: p.u + frag(h) }); });
      (p.h3 || []).forEach(function (h) { addUnit('h3', h, pi, { href: p.u + frag(h) }); });
      (p.k || []).forEach(function (h) { addUnit('k', h, pi, { href: p.u + frag(h) }); });
      (p.x || []).forEach(function (h) { addUnit('x', h, pi, { href: p.u + frag(h) }); });
      (p.i || []).forEach(function (h) { addUnit('i', h, pi, { href: p.u + frag(h) }); });
      (p.r || []).forEach(function (h) { addUnit('r', h, pi, { href: p.u + frag(h) }); });
    });
    (data.g || []).forEach(function (g) {
      addUnit('g', g[0], g[3], { sub: g[1], href: 'glossary.html#' + g[2], hay: g[0] + ' ' + (g[4] || []).join(' ') });
    });
    var post = Object.create(null);
    state.units.forEach(function (u, id) {
      var seen = Object.create(null), tk = tokens((u.hay || u.text));
      for (var i = 0; i < tk.length; i++) {
        var t = tk[i];
        if (seen[t]) continue;
        seen[t] = 1;
        (post[t] || (post[t] = [])).push(id);
      }
      u.n = tk.length || 1;
    });
    state.post = post;
    state.vocab = Object.keys(post).sort();
    state.ready = true;
  }

  function lowerBound(arr, x) {
    var lo = 0, hi = arr.length;
    while (lo < hi) { var mid = (lo + hi) >> 1; if (arr[mid] < x) lo = mid + 1; else hi = mid; }
    return lo;
  }
  function editWithin(a, b, max) { // bounded Damerau-Levenshtein (transposition counts as 1)
    var la = a.length, lb = b.length;
    if (Math.abs(la - lb) > max) return false;
    var prev2 = null, prev = [], cur, i, j;
    for (j = 0; j <= lb; j++) prev[j] = j;
    for (i = 1; i <= la; i++) {
      cur = [i]; var best = i;
      for (j = 1; j <= lb; j++) {
        var c = a.charAt(i - 1) === b.charAt(j - 1) ? 0 : 1;
        var v = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + c);
        if (i > 1 && j > 1 && a.charAt(i - 1) === b.charAt(j - 2) && a.charAt(i - 2) === b.charAt(j - 1)) v = Math.min(v, prev2[j - 2] + 1);
        cur[j] = v; if (v < best) best = v;
      }
      if (best > max) return false;
      prev2 = prev; prev = cur;
    }
    return prev[lb] <= max;
  }

  // vocab terms matching one query token -> [{t, q}] with quality q in (0,1]
  function expand(tok) {
    var out = [], v = state.vocab, i;
    if (state.post[tok]) out.push({ t: tok, q: 1 });
    if (tok.length >= 2) {
      i = lowerBound(v, tok);
      var n = 0;
      for (; i < v.length && v[i].indexOf(tok) === 0 && n < 60; i++) {
        if (v[i] !== tok) { out.push({ t: v[i], q: 0.72 - Math.min(0.3, (v[i].length - tok.length) * 0.03) }); n++; }
      }
    }
    if (out.length < 3 && tok.length >= 4) {
      var d = tok.length >= 8 ? 2 : 1;
      for (i = 0; i < v.length; i++) {
        var w = v[i];
        if (Math.abs(w.length - tok.length) > d) continue;
        if (editWithin(tok, w, d)) out.push({ t: w, q: d === 1 ? 0.45 : 0.36 });
      }
    }
    return out;
  }

  function search(query) {
    var qt = tokens(query);
    if (!qt.length) return [];
    var seenTok = Object.create(null); qt = qt.filter(function (t) { return seenTok[t] ? false : (seenTok[t] = 1); });
    var per = qt.map(expand);
    var scores = Object.create(null), hits = Object.create(null), i, j, k;
    for (i = 0; i < per.length; i++) {
      for (j = 0; j < per[i].length; j++) {
        var m = per[i][j], list = state.post[m.t];
        for (k = 0; k < list.length; k++) {
          var id = list[k], u = state.units[id], s = u.w * m.q;
          var key = id + ':' + i, prevBest = hits[key] || 0;
          if (s > prevBest) { hits[key] = s; scores[id] = (scores[id] || 0) + s - prevBest; }
        }
      }
    }
    var ql = query.toLowerCase().replace(/\s+/g, ' ').trim();
    var list2 = [];
    for (var idS in scores) {
      var un = state.units[idS], matched = 0;
      for (i = 0; i < qt.length; i++) if (hits[idS + ':' + i]) matched++;
      if (matched < qt.length && qt.length > 1) { if (matched < Math.ceil(qt.length / 2)) continue; }
      var sc = scores[idS] * (matched / qt.length) * (matched === qt.length ? 1 : 0.5);
      var tl = (un.text || '').toLowerCase();
      if (tl === ql) sc += 14; else if (tl.indexOf(ql) === 0) sc += 6; else if (tl.indexOf(ql) > -1) sc += 3;
      sc -= Math.min(4, Math.max(0, un.n - 6) * 0.05); // shorter, tighter units first
      list2.push({ id: +idS, s: sc, u: un });
    }
    list2.sort(function (a, b) { return b.s - a.s || a.id - b.id; });
    var count = Object.create(null), out = [];
    for (i = 0; i < list2.length && out.length < MAX_RESULTS; i++) {
      var r = list2[i], pk = r.u.type === 'g' ? 'g' + r.id : r.u.p;
      count[pk] = (count[pk] || 0) + 1;
      if (count[pk] > PER_PAGE) continue;
      out.push(r);
    }
    return out;
  }

  // ---- UI -------------------------------------------------------------------------
  var STYLE =
    '.aiml-s-ov{position:fixed;inset:0;z-index:2147483100;background:rgba(6,8,14,.62);display:flex;align-items:flex-start;justify-content:center;padding:11vh 12px 12px}' +
    '.aiml-s-ov[hidden]{display:none}' +
    '.aiml-s{width:min(660px,100%);max-height:min(76vh,640px);display:flex;flex-direction:column;background:var(--card,#1A1D27);color:var(--text,#E8EAF0);border:1px solid var(--border,#2A2D3E);border-radius:14px;box-shadow:0 24px 70px rgba(0,0,0,.45);overflow:hidden;font:400 14px/1.45 var(--sans,system-ui,sans-serif)}' +
    '.aiml-s-top{display:flex;align-items:center;gap:10px;padding:0 14px;border-bottom:1px solid var(--border,#2A2D3E)}' +
    '.aiml-s-top svg{flex:none;color:var(--t2,#9196A8)}' +
    '.aiml-s-in{flex:1;min-width:0;background:transparent;border:0;outline:0;color:var(--text,#E8EAF0);font:500 16px var(--sans,system-ui,sans-serif);padding:15px 0}' +
    '.aiml-s-in::placeholder{color:var(--t3,#5A5F72)}' +
    '.aiml-s-x{flex:none;border:1px solid var(--border,#2A2D3E);background:var(--card2,#21253A);color:var(--t2,#9196A8);border-radius:6px;font:600 10.5px var(--mono,monospace);padding:3px 7px;cursor:pointer}' +
    '.aiml-s-x:hover{border-color:var(--violet,#7C5CFC);color:var(--text,#E8EAF0)}' +
    '.aiml-s-list{list-style:none;margin:0;padding:6px;overflow-y:auto;overscroll-behavior:contain}' +
    '.aiml-s-item a{display:block;padding:8px 10px;border-radius:9px;color:inherit;text-decoration:none;border:1px solid transparent}' +
    '.aiml-s-item.on a,.aiml-s-item a:hover{background:var(--violet-bg,rgba(124,92,252,.12));border-color:var(--violet,#7C5CFC)}' +
    '.aiml-s-row{display:flex;align-items:baseline;gap:8px}' +
    '.aiml-s-tag{flex:none;font:700 9.5px var(--mono,monospace);letter-spacing:.5px;text-transform:uppercase;color:var(--t2,#9196A8);border:1px solid var(--border,#2A2D3E);background:var(--card2,#21253A);border-radius:5px;padding:1px 6px}' +
    '.aiml-s-tag.g{color:var(--cyan,#00D9A6)}.aiml-s-tag.h{color:var(--violet-light,#9B7FFF)}' +
    '.aiml-s-tx{min-width:0;font-weight:600;overflow-wrap:anywhere}' +
    '.aiml-s-sub{font-size:12px;color:var(--t2,#9196A8);margin:2px 0 0;overflow-wrap:anywhere}' +
    '.aiml-s-tx mark,.aiml-s-sub mark{background:var(--gold-bg,rgba(255,184,0,.18));color:var(--gold,#FFB800);border-radius:3px;padding:0 1px;font-weight:700}' +
    '.aiml-s-msg{padding:18px 16px;color:var(--t2,#9196A8);font-size:13.5px}' +
    '.aiml-s-msg b{color:var(--text,#E8EAF0)}' +
    '.aiml-s-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}' +
    '.aiml-s-chip{border:1px solid var(--border,#2A2D3E);background:var(--card2,#21253A);color:var(--text,#E8EAF0);border-radius:14px;padding:3px 11px;font:600 12px var(--sans,system-ui,sans-serif);cursor:pointer;text-decoration:none}' +
    '.aiml-s-chip:hover,.aiml-s-chip:focus-visible{border-color:var(--violet,#7C5CFC);outline:0}' +
    '.aiml-s-foot{display:flex;gap:14px;flex-wrap:wrap;padding:8px 14px;border-top:1px solid var(--border,#2A2D3E);color:var(--t3,#5A5F72);font-size:11.5px}' +
    '.aiml-s-foot kbd{font:600 10px var(--mono,monospace);border:1px solid var(--border,#2A2D3E);background:var(--card2,#21253A);color:var(--t2,#9196A8);border-radius:4px;padding:1px 5px}' +
    '.aiml-s-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}' +
    '@media(max-width:560px){.aiml-s-ov{padding:8px}.aiml-s{max-height:88vh}.aiml-s-foot .aiml-s-k{display:none}}' +
    '@media print{.aiml-s-ov{display:none!important}}';

  function mount() {
    if (ui.ov) return;
    var st = document.createElement('style'); st.id = 'aiml-s-style'; st.textContent = STYLE; document.head.appendChild(st);
    var ov = document.createElement('div');
    ov.className = 'aiml-s-ov'; ov.hidden = true;
    ov.innerHTML =
      '<div class="aiml-s" role="dialog" aria-modal="true" aria-label="Search the course">' +
      '<div class="aiml-s-top"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>' +
      '<input class="aiml-s-in" type="text" role="combobox" aria-expanded="false" aria-controls="aiml-s-list" aria-autocomplete="list" aria-label="Search lessons, headings and glossary" placeholder="Search lessons, sections and terms..." autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="go"/>' +
      '<button type="button" class="aiml-s-x" aria-label="Close search">Esc</button></div>' +
      '<div class="aiml-s-body"><ul class="aiml-s-list" id="aiml-s-list" role="listbox" aria-label="Search results" hidden></ul><div class="aiml-s-msg" role="status"></div></div>' +
      '<div class="aiml-s-foot"><span class="aiml-s-k"><kbd>&uarr;</kbd> <kbd>&darr;</kbd> move</span><span class="aiml-s-k"><kbd>Enter</kbd> open</span><span class="aiml-s-k"><kbd>Ctrl</kbd>+<kbd>Enter</kbd> new tab</span><span><kbd>Esc</kbd> close</span></div>' +
      '</div><div class="aiml-s-sr" aria-live="polite"></div>';
    document.body.appendChild(ov);
    ui.ov = ov; ui.box = ov.firstChild; ui.in = ov.querySelector('.aiml-s-in'); ui.list = ov.querySelector('.aiml-s-list');
    ui.msg = ov.querySelector('.aiml-s-msg'); ui.sr = ov.querySelector('.aiml-s-sr');
    ov.addEventListener('mousedown', function (e) { if (e.target === ov) close(); });
    ov.querySelector('.aiml-s-x').addEventListener('click', close);
    ui.in.addEventListener('input', function () { clearTimeout(qTimer); qTimer = setTimeout(run, 40); });
    ui.in.addEventListener('keydown', onKey);
    ui.list.addEventListener('mousemove', function (e) {
      var li = e.target.closest && e.target.closest('.aiml-s-item');
      if (li) setActive(+li.getAttribute('data-i'), false);
    });
    ov.addEventListener('keydown', function (e) { // simple focus trap: dialog has input, close button and chips
      if (e.key !== 'Tab') return;
      var f = [].slice.call(ov.querySelectorAll('input,button,a.aiml-s-chip')).filter(function (x) { return x.offsetParent !== null; });
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
  }

  function load() {
    if (state.ready || state.loading) return;
    state.loading = true;
    fetch(INDEX_URL).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (d) {
      build(d); state.loading = false; if (open) run();
    }).catch(function () { state.loading = false; state.failed = true; if (open) run(); });
  }

  function homeChips() {
    var terms = ['decorator', 'classmethod', 'PSI', 'gradient descent', 'overfitting', 'idempotent'];
    return '<div class="aiml-s-chips">' + terms.map(function (t) { return '<a href="#" class="aiml-s-chip" data-q="' + esc(t) + '">' + esc(t) + '</a>'; }).join('') + '</div>';
  }

  function setMsg(html) { ui.msg.innerHTML = html; ui.msg.hidden = !html; }
  function announce(t) { ui.sr.textContent = t; }

  function run() {
    var q = ui.in.value.trim();
    ui.list.innerHTML = ''; active = -1; results = [];
    ui.in.setAttribute('aria-expanded', 'false'); ui.in.removeAttribute('aria-activedescendant');
    ui.list.hidden = true;
    if (state.failed) {
      setMsg('<b>Search could not load its index.</b><br>It needs the site to be served over http(s), for example on GitHub Pages or with <code>python3 -m http.server</code>. Opening the page straight from disk (file://) blocks it.');
      return;
    }
    if (!state.ready) { setMsg('Loading search index...'); return; }
    if (!q) { setMsg('Search every lesson, section heading, recap and glossary term. Try:' + homeChips()); announce(''); return; }
    results = search(q);
    if (!results.length) { setMsg('No results for <b>' + esc(q) + '</b>. Try a shorter word or check the spelling.'); announce('No results'); return; }
    setMsg('');
    var qt = (q.toLowerCase().match(/[a-z0-9_]+/g) || []).filter(function (t) { return t.length > 0; });
    var rx = null;
    try { rx = new RegExp('(' + qt.map(function (t) { return t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }).sort(function (a, b) { return b.length - a.length; }).join('|') + ')', 'ig'); } catch (e) { rx = null; }
    var hl = function (s) { var e = esc(s); return rx ? e.replace(rx, '<mark>$1</mark>') : e; };
    ui.list.innerHTML = results.map(function (r, i) {
      var u = r.u, p = state.pages[u.p], href = ROOT + u.href, ctx = '';
      if (p) ctx = [state.domains[p.f], chapLabel(p), u.type === 'page' ? '' : p.t].filter(Boolean).join(' · ');
      if (u.type === 'g') ctx = (u.sub || '') + (p ? '  — taught in ' + [chapLabel(p), p.t].filter(Boolean).join(' ') : '');
      var tag = '<span class="aiml-s-tag ' + (u.type === 'g' ? 'g' : u.type === 'h' ? 'h' : '') + '">' + LABEL[u.type] + '</span>';
      return '<li class="aiml-s-item" role="presentation" data-i="' + i + '"><a id="aiml-s-o' + i + '" role="option" aria-selected="false" tabindex="-1" href="' + esc(href) + '">' +
        '<div class="aiml-s-row">' + tag + '<span class="aiml-s-tx">' + hl(u.text) + '</span></div>' +
        (ctx ? '<div class="aiml-s-sub">' + hl(ctx) + '</div>' : '') + '</a></li>';
    }).join('');
    ui.list.hidden = false;
    ui.in.setAttribute('aria-expanded', 'true');
    setActive(0, true);
    announce(results.length + ' result' + (results.length === 1 ? '' : 's'));
  }

  function setActive(i, scroll) {
    var items = ui.list.querySelectorAll('.aiml-s-item');
    if (!items.length) return;
    i = (i + items.length) % items.length;
    if (active >= 0 && items[active]) { items[active].classList.remove('on'); items[active].firstChild.setAttribute('aria-selected', 'false'); }
    active = i;
    items[i].classList.add('on'); items[i].firstChild.setAttribute('aria-selected', 'true');
    ui.in.setAttribute('aria-activedescendant', items[i].firstChild.id);
    if (scroll !== false && items[i].scrollIntoView) items[i].scrollIntoView({ block: 'nearest' });
  }

  function onKey(e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(active + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(active - 1); }
    else if (e.key === 'Home' && results.length && !ui.in.value) { e.preventDefault(); setActive(0); }
    else if (e.key === 'End' && results.length && !ui.in.value) { e.preventDefault(); setActive(results.length - 1); }
    else if (e.key === 'Enter') {
      var a = ui.list.querySelectorAll('.aiml-s-item a')[active];
      if (a) { e.preventDefault(); if (e.ctrlKey || e.metaKey) window.open(a.href, '_blank', 'noopener'); else location.href = a.href; }
    }
  }

  function openPalette(seed) {
    mount();
    if (open) { ui.in.focus(); return; }
    open = true; lastFocus = document.activeElement;
    ui.ov.hidden = false;
    document.documentElement.setAttribute('data-aiml-search-open', '');
    ui.in.value = seed || '';
    load(); run();
    ui.in.focus();
    if (seed) ui.in.select();
  }
  function close() {
    if (!open) return;
    open = false; ui.ov.hidden = true;
    document.documentElement.removeAttribute('data-aiml-search-open');
    if (lastFocus && lastFocus.focus) { try { lastFocus.focus(); } catch (e) { /* element gone */ } }
  }

  function isTyping(t) {
    if (!t) return false;
    var tag = (t.tagName || '').toLowerCase();
    return tag === 'input' || tag === 'textarea' || tag === 'select' || t.isContentEditable || (t.closest && t.closest('.CodeMirror,.cm-editor,[contenteditable="true"]'));
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && open) { e.preventDefault(); close(); return; }
    if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); open ? close() : openPalette(); return; }
    if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey && !open && !isTyping(e.target)) { e.preventDefault(); openPalette(); }
  });

  document.addEventListener('click', function (e) {
    var chip = e.target.closest && e.target.closest('.aiml-s-chip');
    if (chip) { e.preventDefault(); ui.in.value = chip.getAttribute('data-q'); run(); ui.in.focus(); return; }
    var b = e.target.closest && e.target.closest('[data-aiml-search]');
    if (b) { e.preventDefault(); openPalette(); }
  });
  ['mouseover', 'focusin', 'touchstart'].forEach(function (ev) {
    document.addEventListener(ev, function (e) { if (!state.ready && e.target.closest && e.target.closest('[data-aiml-search]')) load(); }, { passive: true });
  });

  function ensureButton() {
    if (document.querySelector('[data-aiml-search]')) {
      var idx = document.querySelector('.aiml-sb-index');
      if (idx && idx.parentElement && getComputedStyle(idx.parentElement).position === 'static') idx.parentElement.style.position = 'relative';
      return;
    }
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'aiml-sb aiml-sb-fixed'; b.setAttribute('data-aiml-search', '');
    b.setAttribute('aria-label', 'Search the course (Ctrl+K)'); b.setAttribute('aria-haspopup', 'dialog');
    b.innerHTML = '<span aria-hidden="true">🔍</span><span class="aiml-sb-t">Search</span><kbd>Ctrl K</kbd>';
    document.body.appendChild(b);
  }
  function init() {
    ensureButton();
    if (/Mac|iPhone|iPad/.test(navigator.platform || '')) {
      [].forEach.call(document.querySelectorAll('.aiml-sb kbd'), function (k) { k.textContent = '⌘ K'; });
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();

  window.aimlSearch = { open: openPalette, close: close };
})();
