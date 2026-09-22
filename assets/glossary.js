/* AI/ML: Zero to Hero - glossary tooltips.
 * On lesson pages, the FIRST use of each glossary term inside a `.lesson-p` paragraph gets a dotted underline and an
 * accessible tooltip (hover, keyboard focus, or tap). Only text nodes are touched, and never text inside
 * code, pre, links, headings, buttons or form fields. Data: assets/glossary.json (fetched lazily, once).
 * Works over http(s) (GitHub Pages, python -m http.server); silently does nothing if the file cannot be fetched.
 */
(function () {
  'use strict';
  if (window.__aimlGlossary) return;
  window.__aimlGlossary = true;

  var script = document.currentScript;
  var base = script && script.src ? script.src : '';
  var MAX_MARKS = 40;
  var SKIP = /^(CODE|PRE|A|H1|H2|H3|H4|H5|H6|BUTTON|KBD|SAMP|SCRIPT|STYLE|TEXTAREA|INPUT|SELECT|OPTION|SVG|ABBR)$/;
  var BOLD = /^(STRONG|EM|B|I)$/;
  var tip, tipTimer, cur, shownAt = 0, entries = {}, root = '';

  function ready(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn); else fn();
  }

  function css() {
    if (document.getElementById('gl-style')) return;
    var s = document.createElement('style');
    s.id = 'gl-style';
    s.textContent =
      '.gl-term{text-decoration:underline dotted;text-decoration-color:var(--violet,#7C5CFC);text-decoration-thickness:1.5px;text-underline-offset:3px;cursor:help;border-radius:2px}' +
      '.gl-term:hover,.gl-term.gl-on{background:var(--violet-bg,rgba(124,92,252,.12))}' +
      '.gl-term:focus-visible{outline:2px solid var(--violet,#7C5CFC);outline-offset:2px}' +
      '.gl-tip{position:fixed;z-index:2147483000;left:0;top:0;max-width:min(340px,calc(100vw - 20px));background:var(--card,#1A1D27);color:var(--text,#E8EAF0);border:1px solid var(--violet,#7C5CFC);border-radius:10px;padding:10px 12px;font:400 13px/1.5 var(--sans,system-ui,sans-serif);box-shadow:0 8px 28px rgba(0,0,0,.35);text-align:left}' +
      '.gl-tip[hidden]{display:none}' +
      '.gl-t{font-weight:700;font-size:13.5px;margin-bottom:3px;display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 8px}' +
      '.gl-c{font:700 9.5px var(--mono,monospace);letter-spacing:.6px;text-transform:uppercase;color:var(--t2,#9196A8);border:1px solid var(--border,#2A2D3E);border-radius:4px;padding:0 6px}' +
      '.gl-d{color:var(--text,#E8EAF0)}' +
      '.gl-e{display:block;margin-top:6px;background:var(--card2,#21253A);border:1px solid var(--border,#2A2D3E);border-radius:6px;padding:4px 8px;font:12px/1.45 var(--mono,monospace);color:var(--t2,#9196A8);white-space:pre-wrap;overflow-wrap:anywhere}' +
      '.gl-a{display:inline-block;margin-top:7px;font-size:12px;font-weight:600;color:var(--violet,#7C5CFC)}' +
      '@media print{.gl-term{text-decoration:none;background:none}.gl-tip{display:none}}';
    document.head.appendChild(s);
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  }

  // acronyms and camel-case names (PSI, API, ReAct, NumPy) must match exactly, so 'React' is not 'ReAct'
  function isCaseSensitive(f) { return /[A-Z]/.test(f.slice(1)); }

  function buildMatcher(terms) {
    var map = {}, forms = [];
    terms.forEach(function (e) {
      entries[e.id] = e;
      [e.term].concat(e.alt || []).forEach(function (f) {
        var k = f.toLowerCase();
        if (!f || map[k]) return;
        map[k] = { e: e, cs: isCaseSensitive(f), form: f };
        forms.push(f);
      });
    });
    forms.sort(function (a, b) { return b.length - a.length; });
    var re = new RegExp(forms.map(function (f) { return f.replace(/[.*+?^${}()|[\]\\\/]/g, '\\$&'); }).join('|'), 'gi');
    return { re: re, map: map };
  }

  function okBoundary(s, i, len) {
    var p = i > 0 ? s.charAt(i - 1) : ' ', n = i + len < s.length ? s.charAt(i + len) : ' ';
    return !/[\w-]/.test(p) && !/[\w-]/.test(n) && !(n === '.' && /\w/.test(s.charAt(i + len + 1) || ''));
  }

  function eligible(node, para) {
    var el = node.parentElement, bold = false;
    while (el && el !== para) {
      if (SKIP.test(el.tagName) || (el.classList && el.classList.contains('gl-term')) || el.isContentEditable) return null;
      if (BOLD.test(el.tagName)) bold = true;
      el = el.parentElement;
    }
    return { bold: bold };
  }

  function decorate(matcher) {
    var used = {}, count = 0, paras = document.querySelectorAll('.lesson-p');
    for (var pi = 0; pi < paras.length && count < MAX_MARKS; pi++) {
      var para = paras[pi], nodes = [], w = document.createTreeWalker(para, NodeFilter.SHOW_TEXT, null), n;
      while ((n = w.nextNode())) nodes.push(n);
      for (var ni = 0; ni < nodes.length && count < MAX_MARKS; ni++) {
        var node = nodes[ni], text = node.nodeValue;
        if (!text || text.length < 3) continue;
        var ctx = eligible(node, para);
        if (!ctx) continue;
        var re = matcher.re, hits = [], m;
        re.lastIndex = 0;
        while ((m = re.exec(text))) {
          var info = matcher.map[m[0].toLowerCase()];
          if (!info || !okBoundary(text, m.index, m[0].length)) { re.lastIndex = m.index + 1; continue; }
          if (info.cs && m[0] !== info.form) { re.lastIndex = m.index + 1; continue; }
          if (info.e.amb && !ctx.bold) continue;
          if (used[info.e.id]) continue;
          used[info.e.id] = 1;
          hits.push({ i: m.index, len: m[0].length, id: info.e.id });
          if (count + hits.length >= MAX_MARKS) break;
        }
        if (!hits.length) continue;
        var frag = document.createDocumentFragment(), pos = 0;
        hits.forEach(function (h) {
          if (h.i > pos) frag.appendChild(document.createTextNode(text.slice(pos, h.i)));
          var sp = document.createElement('span');
          sp.className = 'gl-term';
          sp.tabIndex = 0;
          sp.setAttribute('data-gl', h.id);
          sp.setAttribute('aria-describedby', 'gl-tip');
          sp.textContent = text.substr(h.i, h.len);
          frag.appendChild(sp);
          pos = h.i + h.len;
        });
        if (pos < text.length) frag.appendChild(document.createTextNode(text.slice(pos)));
        node.parentNode.replaceChild(frag, node);
        count += hits.length;
      }
    }
    return count;
  }

  function ensureTip() {
    if (tip) return tip;
    tip = document.createElement('div');
    tip.id = 'gl-tip';
    tip.className = 'gl-tip';
    tip.setAttribute('role', 'tooltip');
    tip.hidden = true;
    tip.addEventListener('mouseenter', function () { clearTimeout(tipTimer); });
    tip.addEventListener('mouseleave', function () { hide(200); });
    document.body.appendChild(tip);
    return tip;
  }

  function show(el) {
    var e = entries[el.getAttribute('data-gl')];
    if (!e) return;
    clearTimeout(tipTimer);
    ensureTip();
    if (cur && cur !== el) cur.classList.remove('gl-on');
    cur = el;
    shownAt = Date.now();
    el.classList.add('gl-on');
    tip.innerHTML = '<div class="gl-t">' + esc(e.term) + '<span class="gl-c">' + esc(e.cat) + '</span></div>' +
      '<div class="gl-d">' + esc(e.definition) + '</div>' +
      '<code class="gl-e">' + esc(e.example) + '</code>' +
      '<a class="gl-a" href="' + esc(root + 'glossary.html#' + e.id) + '">Open in glossary &rarr;</a>';
    tip.hidden = false;
    var r = el.getBoundingClientRect(), tw = tip.offsetWidth, th = tip.offsetHeight;
    var vw = document.documentElement.clientWidth, vh = window.innerHeight;
    var left = Math.min(Math.max(8, r.left + r.width / 2 - tw / 2), Math.max(8, vw - tw - 8));
    var top = r.bottom + 8;
    if (top + th > vh - 8 && r.top - th - 8 > 8) top = r.top - th - 8;
    tip.style.left = left + 'px';
    tip.style.top = Math.max(8, top) + 'px';
  }

  function hide(delay) {
    clearTimeout(tipTimer);
    tipTimer = setTimeout(function () {
      if (tip) tip.hidden = true;
      if (cur) { cur.classList.remove('gl-on'); cur = null; }
    }, delay || 0);
  }

  function bind() {
    var t = function (ev) { return ev.target && ev.target.closest ? ev.target.closest('.gl-term') : null; };
    document.addEventListener('mouseover', function (ev) { var el = t(ev); if (el) { clearTimeout(tipTimer); tipTimer = setTimeout(function () { show(el); }, 110); } });
    document.addEventListener('mouseout', function (ev) { if (t(ev)) hide(220); });
    document.addEventListener('focusin', function (ev) { var el = t(ev); if (el) show(el); });
    document.addEventListener('focusout', function (ev) { if (t(ev)) hide(0); });
    document.addEventListener('click', function (ev) {
      var el = t(ev);
      if (el) { if (cur === el && tip && !tip.hidden && Date.now() - shownAt > 400) hide(0); else show(el); }
      else if (!(tip && tip.contains(ev.target))) hide(0);
    });
    document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape') hide(0); });
    window.addEventListener('scroll', function () { if (tip && !tip.hidden) hide(0); }, { passive: true });
  }

  ready(function () {
    if (!document.querySelector('.lesson-p') || !base) return;
    root = new URL('../', base).href;
    fetch(new URL('glossary.json', base).href).then(function (r) { return r.ok ? r.json() : Promise.reject(); }).then(function (data) {
      var run = function () {
        try {
          css();
          var m = buildMatcher(data.terms || []);
          if (decorate(m)) bind();
        } catch (e) { /* never break a lesson page */ }
      };
      if (window.requestIdleCallback) requestIdleCallback(run, { timeout: 1500 }); else setTimeout(run, 50);
    }).catch(function () { /* offline or file:// - lessons work without glossary tooltips */ });
  });
})();
