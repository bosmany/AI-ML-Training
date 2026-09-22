/* AI/ML Zero-to-Hero - learning mechanics (spaced repetition, mastery, streak).
 * Data contract: localStorage `aimlZTH_learn_v1` (see blueprint/contract.md).
 * Second key `aimlZTH_learn_q_v1` keeps question text/options/answer so items can be re-asked.
 * Chapter pages are never modified: results are observed with a MutationObserver.
 * Public API: window.AIML.learn  (also module.exports under node, for the unit tests).
 */
(function (root) {
  'use strict';
  var KEY = 'aimlZTH_learn_v1', QKEY = 'aimlZTH_learn_q_v1';
  var DAY = 864e5, ALPHA = 0.3, ITEMS_PER_SKILL = 10; // every chapter: 5 quiz + 5 exercise items
  var hasDom = typeof document !== 'undefined' && typeof window !== 'undefined';

  /* ---------- storage (localStorage with in-memory fallback) ---------- */
  var mem = {};
  function rd(k) {
    if (mem[k] !== undefined) return mem[k];
    try { return localStorage.getItem(k); } catch (e) { return null; }
  }
  function wr(k, v) {
    try { localStorage.setItem(k, v); delete mem[k]; } catch (e) { mem[k] = v; }
  }
  function del(k) { delete mem[k]; try { localStorage.removeItem(k); } catch (e) {} }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function isObj(o) { return o && typeof o === 'object' && !Array.isArray(o); }

  /* ---------- dates (calendar days as YYYY-MM-DD, tz independent math) ---------- */
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function dayStr(ms) {
    var d = new Date(ms);
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  }
  function parseDay(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || '');
    return m ? Date.UTC(+m[1], +m[2] - 1, +m[3]) : NaN;
  }
  function addDays(s, n) { return new Date(parseDay(s) + n * DAY).toISOString().slice(0, 10); }
  function diffDays(a, b) { return Math.round((parseDay(b) - parseDay(a)) / DAY); }
  function weekKey(s) { // Monday of the ISO week
    var dow = (new Date(parseDay(s)).getUTCDay() + 6) % 7;
    return addDays(s, -dow);
  }
  function nowMs(o) { return o && typeof o.now === 'number' ? o.now : Date.now(); }
  function r2(x) { return Math.round(x * 100) / 100; }
  function r1(x) { return Math.round(x * 10) / 10; }

  /* ---------- state ---------- */
  function fresh() {
    return {
      version: 1, items: {}, skills: {},
      streak: { count: 0, best: 0, lastDay: '', freezes: 1 },
      activity: {}, placement: null, projects: {},
      graduation: { junior: false, mid: false, senior: false }
    };
  }
  function normalize(s) {
    var f = fresh();
    if (!isObj(s)) return f;
    for (var k in s) if (Object.prototype.hasOwnProperty.call(s, k)) f[k] = s[k]; // keep other features' keys
    f.version = 1;
    ['items', 'skills', 'activity', 'projects'].forEach(function (k) { if (!isObj(f[k])) f[k] = {}; });
    if (!isObj(f.streak)) f.streak = fresh().streak;
    f.streak.count = +f.streak.count || 0;
    f.streak.best = +f.streak.best || 0;
    f.streak.lastDay = typeof f.streak.lastDay === 'string' ? f.streak.lastDay : '';
    f.streak.freezes = typeof f.streak.freezes === 'number' ? f.streak.freezes : 1;
    if (!isObj(f.graduation)) f.graduation = fresh().graduation;
    return f;
  }
  function load() {
    var raw = rd(KEY), s = null;
    if (raw) { try { s = JSON.parse(raw); } catch (e) { s = null; } }
    return normalize(s);
  }
  function save(s) {
    wr(KEY, JSON.stringify(s));
    if (hasDom) { try { window.dispatchEvent(new CustomEvent('aiml:learn')); } catch (e) {} }
  }
  function loadQ() {
    var raw = rd(QKEY), q = null;
    if (raw) { try { q = JSON.parse(raw); } catch (e) { q = null; } }
    if (!isObj(q)) q = {};
    if (!isObj(q.q)) q.q = {};
    q.version = 1;
    return q;
  }
  function saveQ(q) { wr(QKEY, JSON.stringify(q)); }

  /* ---------- SM-2-lite ---------- */
  // success: interval 1d (first) -> 3d (second) -> round(interval*ease); ease +0.05 (max 3)
  // failure: interval 1d, ease -0.2 (min 1.3), lapses++, reps reset
  function schedule(it, ok, today, now) {
    var n = {
      skill: it.skill, kind: it.kind,
      ease: typeof it.ease === 'number' ? it.ease : 2.5,
      interval: typeof it.interval === 'number' ? it.interval : 1,
      reps: it.reps || 0, lapses: it.lapses || 0
    };
    if (ok) {
      n.interval = n.reps === 0 ? 1 : n.reps === 1 ? 3 : Math.round(n.interval * n.ease);
      n.reps += 1;
      n.ease = r2(Math.min(3, n.ease + 0.05));
    } else {
      n.interval = 1;
      n.ease = r2(Math.max(1.3, n.ease - 0.2));
      n.lapses += 1;
      n.reps = 0;
    }
    n.due = addDays(today, n.interval);
    n.last = ok ? 1 : 0;
    n.ts = now;
    return n;
  }
  // retention R = exp(-days_since_last / (interval * 1.5))
  function retention(it, now) {
    var t = Math.max(0, (now - (it.ts || 0)) / DAY);
    return Math.exp(-t / ((it.interval || 1) * 1.5));
  }
  // per-skill accuracy is stored (EMA); ret & breadth are derived from the items.
  function skillStats(state, now) {
    var by = {}, id, it;
    for (id in state.items) {
      it = state.items[id];
      if (!it || !it.skill) continue;
      var b = by[it.skill] || (by[it.skill] = { n: 0, r: 0, ok: 0 });
      b.n++; b.r += retention(it, now); if (it.last === 1) b.ok++;
    }
    var out = {};
    for (var sid in by) {
      var rec = state.skills[sid] || {};
      var acc = typeof rec.acc === 'number' ? rec.acc : 0;
      var ret = by[sid].r / by[sid].n;
      var breadth = Math.min(1, by[sid].ok / ITEMS_PER_SKILL);
      out[sid] = {
        acc: acc, ret: ret, breadth: breadth, items: by[sid].n,
        mastery: r1(100 * (0.5 * acc + 0.3 * ret + 0.2 * breadth))
      };
    }
    return out;
  }

  /* ---------- streak (1 freeze per ISO week) ---------- */
  function streakAdvance(st, today) {
    var s = clone(st);
    if (s.lastDay === today) return s;
    var gap = s.lastDay ? diffDays(s.lastDay, today) : 0;
    if (!s.lastDay) s.count = 1;
    else if (gap <= 0) return s; // clock skew: never rewind
    else {
      if (weekKey(s.lastDay) !== weekKey(today)) s.freezes = 1;
      var missed = gap - 1;
      if (missed <= 0) s.count += 1;
      else if (missed <= s.freezes) { s.freezes -= missed; s.count += 1; }
      else s.count = 1;
    }
    s.lastDay = today;
    s.best = Math.max(s.best || 0, s.count);
    return s;
  }
  function streakInfo(o) {
    var st = load().streak, today = dayStr(nowMs(o)), count = st.count, alive = true, atRisk = false;
    if (!st.lastDay) return { count: 0, best: st.best, lastDay: '', freezes: st.freezes, activeToday: false, atRisk: false };
    var gap = diffDays(st.lastDay, today);
    if (gap >= 1) atRisk = true;
    if (gap >= 2) {
      var fr = weekKey(st.lastDay) !== weekKey(today) ? 1 : st.freezes;
      if (gap - 1 > fr) { alive = false; count = 0; atRisk = false; }
    }
    return { count: count, best: st.best, lastDay: st.lastDay, freezes: st.freezes, activeToday: gap <= 0 && alive, atRisk: alive && atRisk };
  }

  /* ---------- skills map (assets/skills.json) ---------- */
  var skillsData = null, scriptBase = '';
  function skillList() { return skillsData ? skillsData.skills : []; }
  function setSkills(j) { if (j && Array.isArray(j.skills)) skillsData = j; return skillsData; }
  var readyP = null;
  function loadSkills() {
    if (readyP) return readyP;
    if (typeof fetch !== 'function') return (readyP = Promise.resolve(null));
    readyP = fetch(scriptBase + 'assets/skills.json').then(function (r) { return r.json(); })
      .then(setSkills, function () { return null; });
    return readyP;
  }
  function skillTitle(id) {
    var l = skillList();
    for (var i = 0; i < l.length; i++) if (l[i].id === id) return l[i].title;
    return id;
  }
  function skillOfChapter(ch) {
    var l = skillList();
    for (var i = 0; i < l.length; i++) if (l[i].chapter === ch) return l[i].id;
    return null;
  }

  /* ---------- public operations ---------- */
  function recordResult(itemId, correct, meta) {
    meta = meta || {};
    if (typeof itemId !== 'string' || !itemId) return null;
    var pre = itemId.split(':')[0];
    var skill = meta.skill || skillOfChapter(pre);
    if (!skill) { try { console.warn('AIML.learn: no skill for ' + itemId); } catch (e) {} return null; }
    var kind = meta.kind || (/:ex\d/.test(itemId) ? 'exercise' : /:q\d/.test(itemId) ? 'quiz' : 'question');
    var now = nowMs(meta), today = dayStr(now), ok = !!correct;
    var s = load();
    var it = s.items[itemId];
    var dup = !!(it && it.last === (ok ? 1 : 0) && it.ts && dayStr(it.ts) === today);
    if (!dup) {
      var base = it || { skill: skill, kind: kind, ease: 2.5, interval: 1, reps: 0, lapses: 0 };
      base.skill = skill; base.kind = it ? it.kind : kind;
      it = s.items[itemId] = schedule(base, ok, today, now);
      var sk = s.skills[skill] || { acc: 0, ret: 0, breadth: 0, mastery: 0, updated: 0 };
      sk.acc = Math.round((ALPHA * (ok ? 1 : 0) + (1 - ALPHA) * (sk.acc || 0)) * 1e4) / 1e4;
      s.skills[skill] = sk;
      var st = skillStats(s, now)[skill];
      sk.ret = r2(st.ret); sk.breadth = r2(st.breadth); sk.mastery = st.mastery; sk.updated = now;
      s.streak = streakAdvance(s.streak, today);
      var a = s.activity[today] || (s.activity[today] = { n: 0 });
      a.n += 1;
      save(s);
    }
    return { dup: dup, item: clone(it), skill: skill, mastery: s.skills[skill].mastery, streak: clone(s.streak) };
  }
  // items due today (or overdue); with relearn (default) also items answered wrong and not yet answered right
  function dueItems(o) {
    o = o || {};
    var now = nowMs(o), today = dayStr(now), s = load(), out = [];
    for (var id in s.items) {
      var it = s.items[id];
      if (!it || (o.skill && it.skill !== o.skill)) continue;
      var due = it.due <= today, relearn = o.relearn !== false && it.last === 0;
      if (!due && !relearn) continue;
      var c = clone(it); c.id = id; c.overdue = Math.max(0, diffDays(it.due, today)); c.retention = retention(it, now);
      out.push(c);
    }
    out.sort(function (a, b) {
      return a.due < b.due ? -1 : a.due > b.due ? 1 : a.retention - b.retention || (a.id < b.id ? -1 : 1);
    });
    return o.limit ? out.slice(0, o.limit) : out;
  }
  function nextDue(o) {
    var s = load(), best = '', today = dayStr(nowMs(o));
    for (var id in s.items) { var d = s.items[id].due; if (d > today && (!best || d < best)) best = d; }
    return best;
  }
  function mastery(skill, o) { var m = skillStats(load(), nowMs(o))[skill]; return m ? m.mastery : 0; }
  function skillDetail(skill, o) { var m = skillStats(load(), nowMs(o))[skill]; return m ? m : { acc: 0, ret: 0, breadth: 0, items: 0, mastery: 0 }; }
  function domainSkillIds(domain, s) {
    var ids = skillList().filter(function (k) { return k.domain === domain; }).map(function (k) { return k.id; });
    if (!ids.length) ids = Object.keys(s.skills).filter(function (k) { return k.indexOf(domain + '.') === 0; });
    return ids;
  }
  // average over ALL chapters of the domain (untouched chapter = 0)
  function domainMastery(domain, o) {
    var s = load(), st = skillStats(s, nowMs(o)), ids = domainSkillIds(domain, s);
    if (!ids.length) return 0;
    var sum = 0; ids.forEach(function (id) { sum += st[id] ? st[id].mastery : 0; });
    return r1(sum / ids.length);
  }
  function allMastery(o) { return skillStats(load(), nowMs(o)); }
  function exportJSON() {
    return JSON.stringify({ format: 'aimlZTH_learn_export', exported: new Date().toISOString(), learn: load(), q: loadQ() }, null, 2);
  }
  function importJSON(text) {
    var j;
    try { j = typeof text === 'string' ? JSON.parse(text) : text; } catch (e) { throw new Error('Not valid JSON'); }
    var learn = j && j.format === 'aimlZTH_learn_export' ? j.learn : j;
    if (!isObj(learn) || !isObj(learn.items) || !isObj(learn.skills)) throw new Error('Not an AI/ML learning export');
    if (learn.version !== 1) throw new Error('Unsupported version ' + learn.version);
    var s = normalize(learn);
    for (var id in s.items) {
      var it = s.items[id];
      if (!isObj(it) || typeof it.skill !== 'string' || typeof it.due !== 'string' || isNaN(parseDay(it.due))) throw new Error('Bad item ' + id);
    }
    save(s);
    if (j.q && isObj(j.q) && isObj(j.q.q)) saveQ({ version: 1, q: j.q.q });
    return { items: Object.keys(s.items).length, skills: Object.keys(s.skills).length };
  }
  function reset() { del(KEY); del(QKEY); if (hasDom) { try { window.dispatchEvent(new CustomEvent('aiml:learn')); } catch (e) {} } }

  var api = {
    version: 1, KEY: KEY, QKEY: QKEY,
    getState: function () { return clone(load()); },
    getQuestions: function () { return clone(loadQ().q); },
    setQuestion: function (id, q) { var s = loadQ(); s.q[id] = q; saveQ(s); },
    dueItems: dueItems, nextDue: nextDue, recordResult: recordResult,
    mastery: mastery, skillDetail: skillDetail, domainMastery: domainMastery, allMastery: allMastery,
    streak: streakInfo, exportJSON: exportJSON, importJSON: importJSON, reset: reset,
    loadSkills: loadSkills, setSkills: setSkills, skills: function () { return skillsData; }, skillTitle: skillTitle,
    today: function (o) { return dayStr(nowMs(o)); },
    root: function () { return scriptBase; },
    // pure helpers (unit-tested)
    _: { schedule: schedule, retention: retention, skillStats: skillStats, streakAdvance: streakAdvance, addDays: addDays, diffDays: diffDays, weekKey: weekKey, dayStr: dayStr, fresh: fresh, normalize: normalize }
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (!hasDom) return;
  root.AIML = root.AIML || {};
  root.AIML.learn = api;

  /* ================= browser only: capture + chip ================= */
  var me = document.currentScript || document.querySelector('script[src*="assets/learn.js"]');
  if (me && me.src) scriptBase = me.src.replace(/assets\/learn\.js.*$/, '');
  else scriptBase = '';
  var pageSkillId = null, chapterId = null;
  (function () {
    var m = /([a-z0-9-]+)\/([a-z]+\d+)-[^\/]*\.html$/i.exec(location.pathname);
    if (m) { pageSkillId = m[1] + '.' + m[2]; chapterId = m[2]; }
  })();

  var ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
  function esc(t) { return String(t).replace(/[&<>"]/g, function (c) { return ESC[c]; }); }
  var KEEP = { code: 1, pre: 1, strong: 1, em: 1, b: 1, i: 1 }, DROP = { script: 1, style: 1, textarea: 1, button: 1, input: 1, select: 1 };
  function clean(node) { // tiny whitelist sanitizer: text + code/pre/strong/em/br only
    var o = '';
    for (var c = node.firstChild; c; c = c.nextSibling) {
      if (c.nodeType === 3) o += esc(c.nodeValue);
      else if (c.nodeType === 1) {
        var t = c.tagName.toLowerCase();
        if (t === 'br') o += '<br>';
        else if (KEEP[t]) o += '<' + t + '>' + clean(c) + '</' + t + '>';
        else if (!DROP[t]) o += clean(c);
      }
    }
    return o;
  }
  function squash(h) { return h.replace(/^\s+|\s+$/g, ''); }

  function storeQuestion(id, q) {
    var s = loadQ(), old = s.q[id];
    if (old && JSON.stringify(old) === JSON.stringify(q)) return;
    s.q[id] = q; saveQ(s);
  }

  function initCapture() {
    if (!pageSkillId) return;
    var sigs = {}, timer = 0;
    var exDirty = {}, fbDirty = {}, quizDirty = false;

    function scanExercise(el) {
      var m = /^ex(\d+)-result$/.exec(el.id || '');
      if (!m || !el.classList.contains('show')) return;
      var pass = el.classList.contains('pass'), fail = el.classList.contains('fail');
      if (!pass && !fail) return;
      var id = chapterId + ':ex' + m[1], card = el.closest('.exercise');
      var q = { skill: pageSkillId, kind: 'exercise', n: +m[1] };
      if (card) {
        var t = card.querySelector('.ex-title'), d = card.querySelector('.ex-desc'), k = card.querySelector('.ex-task');
        q.title = t ? t.textContent.trim() : ''; q.desc = d ? d.textContent.trim() : ''; q.task = k ? k.textContent.trim() : '';
      }
      storeQuestion(id, q);
      recordResult(id, pass, { skill: pageSkillId, kind: 'exercise' });
    }
    function scanFeedback(el) { // free-text quiz question (e.g. q4): the feedback element carries the verdict
      var m = /^q(\d+)-feedback$/.exec(el.id || '');
      if (!m || !el.classList.contains('show')) return;
      var ok = el.classList.contains('correct'), bad = el.classList.contains('wrong');
      if (!ok && !bad) return;
      var id = chapterId + ':q' + m[1], card = el.closest('.quiz-card'), qt = card && card.querySelector('.q-text');
      storeQuestion(id, {
        skill: pageSkillId, kind: 'quiz', type: 'text', n: +m[1],
        text: qt ? squash(clean(qt)) : '', expl: el.textContent.replace(/^[^A-Za-z(]+/, '').trim()
      });
      recordResult(id, ok, { skill: pageSkillId, kind: 'quiz' });
    }
    function scanQuiz() {
      var boxes = document.querySelectorAll('[id^="q"][id$="-opts"]');
      for (var i = 0; i < boxes.length; i++) {
        var box = boxes[i], m = /^q(\d+)-opts$/.exec(box.id);
        if (!m) continue;
        var opts = box.querySelectorAll('.q-opt'), corr = null, given = null, list = [];
        for (var j = 0; j < opts.length; j++) {
          var o = opts[j], lt = o.querySelector('.q-opt-letter');
          var letter = lt ? lt.textContent.trim() : String.fromCharCode(65 + j);
          var cl = o.cloneNode(true), l2 = cl.querySelector('.q-opt-letter');
          if (l2) l2.parentNode.removeChild(l2);
          list.push({ k: letter, t: squash(clean(cl)) });
          if (o.classList.contains('correct')) corr = { el: o, k: letter };
          if (o.classList.contains('selected') || (!given && o.classList.contains('wrong'))) given = { el: o, k: letter };
        }
        if (!corr) { delete sigs[box.id]; continue; } // not graded yet (or retake reset the page)
        var sig = (given ? given.k : '-') + '|' + corr.k;
        if (sigs[box.id] === sig) continue;
        sigs[box.id] = sig;
        var id = chapterId + ':q' + m[1], card = box.closest('.quiz-card'), qt = card && card.querySelector('.q-text');
        storeQuestion(id, {
          skill: pageSkillId, kind: 'quiz', type: 'mcq', n: +m[1],
          text: qt ? squash(clean(qt)) : '', opts: list, correct: corr.k
        });
        recordResult(id, !!(given && given.el === corr.el), { skill: pageSkillId, kind: 'quiz' });
      }
    }
    function flush() {
      timer = 0;
      var e = exDirty, f = fbDirty, qd = quizDirty;
      exDirty = {}; fbDirty = {}; quizDirty = false;
      try {
        for (var k in e) scanExercise(e[k]);
        for (var k2 in f) scanFeedback(f[k2]);
        if (qd) scanQuiz();
      } catch (err) { try { console.warn('AIML.learn capture', err); } catch (x) {} }
    }
    var mo = new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        var t = muts[i].target;
        if (!t || t.nodeType !== 1) continue;
        var c = t.classList;
        if (c.contains('ex-result')) exDirty[t.id || i] = t;
        else if (c.contains('q-feedback')) fbDirty[t.id || i] = t;
        else if (c.contains('q-opt') || c.contains('quiz-result-banner')) quizDirty = true;
      }
      if (!timer) timer = setTimeout(flush, 30);
    });
    mo.observe(document.body, { attributes: true, attributeFilter: ['class'], subtree: true });
  }

  /* ---------- chip: streak + due count in the topbar ---------- */
  var CSS = '.lrn-chip{display:inline-flex;align-items:center;gap:2px;background:var(--card2);border:1px solid var(--border);border-radius:20px;padding:2px;font-size:11.5px;font-weight:600;color:var(--t2);white-space:nowrap;flex-shrink:0}' +
    '.lrn-chip a{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:16px;color:var(--t2);text-decoration:none}' +
    '.lrn-chip a b{color:var(--text)}.lrn-chip a:hover{background:var(--card);color:var(--violet)}' +
    '.lrn-chip a:focus-visible{outline:2px solid var(--violet);outline-offset:1px}' +
    '.lrn-chip .lrn-due.has b{color:var(--gold)}' +
    '.lrn-links{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:-22px 0 34px}' +
    '.lrn-links>a:not(.lrn-x){display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:20px;background:var(--card);border:1px solid var(--border);font-size:13px;font-weight:600;color:var(--text)}' +
    '.lrn-links>a:not(.lrn-x):hover{border-color:var(--violet);color:var(--violet)}' +
    '@media(max-width:600px){#topbar .lrn-chip{display:none}}';
  function renderChip(chip) {
    var s = streakInfo(), due = dueItems().length;
    chip.innerHTML = '<a class="lrn-x lrn-streak" href="' + scriptBase + 'dashboard.html" title="Study streak: ' + s.count + ' day(s), best ' + s.best + '. Open dashboard">🔥 <b>' + s.count + '</b></a>' +
      '<a class="lrn-x lrn-due' + (due ? ' has' : '') + '" href="' + scriptBase + 'review.html" title="Items due for review">📝 <b>' + due + '</b> due</a>';
  }
  function initChip() {
    var host = document.getElementById('topbar'), links = document.querySelector('.lrn-links');
    if (!host && !links) return;
    if (document.getElementById('lrn-chip')) return;
    var chip = document.createElement('span');
    chip.className = 'lrn-chip'; chip.id = 'lrn-chip';
    if (host) {
      var gap = host.querySelector('.tb-gap');
      if (gap && gap.nextSibling) host.insertBefore(chip, gap.nextSibling); else host.appendChild(chip);
    } else links.appendChild(chip);
    var up = function () { try { renderChip(chip); } catch (e) {} };
    up();
    window.addEventListener('aiml:learn', up);
    window.addEventListener('storage', function (e) { if (!e.key || e.key === KEY) up(); });
  }

  function boot() {
    if (!document.getElementById('aiml-learn-css')) {
      var st = document.createElement('style'); st.id = 'aiml-learn-css'; st.textContent = CSS;
      document.head.appendChild(st);
    }
    try { initCapture(); } catch (e) { try { console.warn('AIML.learn', e); } catch (x) {} }
    try { initChip(); } catch (e) {}
    loadSkills();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})(typeof window !== 'undefined' ? window : this);
