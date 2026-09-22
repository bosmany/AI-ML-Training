#!/usr/bin/env python3
"""Validate assets/glossary.json (the source of truth) and render glossary.html.

    python3 scripts/build-glossary.py            # validate + normalise json + write glossary.html
    python3 scripts/build-glossary.py --check    # validate only, write nothing

Each term needs: term, definition, example, chapter (a chapter id from assets/skills.json), cat.
Optional: alt (other surface forms matched in lesson text), amb (1 = ambiguous everyday word: the
tooltip script only decorates it when the lesson bolds it, i.e. where the course introduces it).
The script fills in `id` (URL slug) and `href` (page of the chapter that teaches it), keeps the file
sorted A-Z, and refuses duplicate terms/aliases, unknown chapters and terms that never appear in
their chapter.  After changing the json also run scripts/build-search-index.py (the search index
embeds the glossary).
"""
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _course_parse as cp  # noqa: E402

GJSON = os.path.join(cp.ROOT, 'assets', 'glossary.json')
OUT = os.path.join(cp.ROOT, 'glossary.html')
MIN_TERMS = 150
CATS = ['Python', 'OOP', 'Math', 'Data', 'ML', 'DL', 'NLP', 'MLOps', 'DevOps', 'FastAPI', 'Systems', 'DSA']


def slug(s):
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    return s or 'term'


def form_re(f):
    return re.compile(r'(?<![\w])' + re.escape(f.lower()) + r'(?![\w])')


def load():
    with open(GJSON, encoding='utf-8') as f:
        return json.load(f)


def validate_and_normalise(data):
    skills = {s['chapter']: s for s in cp.load_skills()['skills']}
    text_of = {}
    for p in cp.pages():
        if p.skill:
            text_of[p.skill['chapter']] = cp.text(p.dom).lower()
    errors, seen, ids = [], {}, set()
    for e in data['terms']:
        for k in ('term', 'definition', 'example', 'chapter', 'cat'):
            if not e.get(k):
                errors.append('%s: missing %s' % (e.get('term', '?'), k))
        if e.get('chapter') not in skills:
            errors.append('%s: unknown chapter %r' % (e['term'], e.get('chapter')))
            continue
        if e['cat'] not in CATS:
            errors.append('%s: unknown category %r' % (e['term'], e['cat']))
        if len(e['definition']) > 330:
            errors.append('%s: definition too long (%d)' % (e['term'], len(e['definition'])))
        e.setdefault('alt', [])
        for f in [e['term']] + e['alt']:
            k = f.lower()
            if k in seen and seen[k] != e['term']:
                errors.append('alias %r used by %r and %r' % (f, seen[k], e['term']))
            seen[k] = e['term']
        e['id'] = slug(e['term'])
        if e['id'] in ids:
            errors.append('duplicate id ' + e['id'])
        ids.add(e['id'])
        e['href'] = skills[e['chapter']]['file']
        if not any(form_re(f).search(text_of[e['chapter']]) for f in [e['term']] + e['alt']):
            errors.append('%s never appears in chapter %s' % (e['term'], e['chapter']))
    if len(data['terms']) < MIN_TERMS:
        errors.append('only %d terms, need >= %d' % (len(data['terms']), MIN_TERMS))
    data['terms'].sort(key=lambda e: e['term'].lower())
    # stable key order
    order = ['id', 'term', 'alt', 'cat', 'definition', 'example', 'chapter', 'href', 'amb']
    data['terms'] = [{k: e[k] for k in order if k in e} for e in data['terms']]
    return errors, skills


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>AI/ML: Zero to Hero — Glossary</title>
<meta name="description" content="Plain-English definitions of __N__ terms used across the course, each with a tiny example and a link to the chapter that teaches it."/>
<style>
:root{
  --bg:#0F1117; --card:#1A1D27; --card2:#21253A; --border:#2A2D3E;
  --violet:#7C5CFC; --violet-light:#9B7FFF; --violet-bg:rgba(124,92,252,.1);
  --cyan:#00D9A6; --cyan-bg:rgba(0,217,166,.08);
  --gold:#FFB800; --gold-bg:rgba(255,184,0,.1);
  --red:#FF5757; --text:#E8EAF0; --t2:#9196A8; --t3:#5A5F72;
  --sans:'Inter',system-ui,sans-serif; --mono:'JetBrains Mono',ui-monospace,monospace;
}
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:var(--sans);font-size:15px;line-height:1.6;min-height:100vh}
a{color:var(--violet);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:900px;margin:0 auto;padding:56px 20px 90px}
.crumb{font-size:12.5px;color:var(--t2);margin-bottom:18px}
h1{font-size:clamp(28px,5vw,40px);font-weight:800;letter-spacing:-.02em;line-height:1.1;margin-bottom:10px}
h1 span{background:linear-gradient(90deg,var(--violet),var(--cyan));-webkit-background-clip:text;background-clip:text;color:transparent}
.lede{color:var(--t2);max-width:640px;margin-bottom:22px}
.tools{position:sticky;top:0;z-index:20;background:var(--bg);padding:10px 0 8px;border-bottom:1px solid var(--border);margin-bottom:8px}
.g-search{width:100%;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);font:500 15px var(--sans);padding:11px 14px;outline:none}
.g-search:focus{border-color:var(--violet);box-shadow:0 0 0 3px var(--violet-bg)}
.g-search::placeholder{color:var(--t3)}
.chips,.az{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.chip,.az a{border:1px solid var(--border);background:var(--card);color:var(--t2);border-radius:14px;padding:3px 10px;font:600 11.5px var(--sans);cursor:pointer}
.az a{padding:2px 8px;border-radius:6px;font-family:var(--mono);text-decoration:none}
.chip:hover,.az a:hover{border-color:var(--violet);color:var(--text);text-decoration:none}
.chip[aria-pressed="true"]{background:var(--violet);border-color:var(--violet);color:#fff}
.az a.off{opacity:.35;pointer-events:none}
.count{font-size:12px;color:var(--t3);margin:10px 0 0}
.letter{font-family:var(--mono);font-size:13px;font-weight:700;color:var(--cyan);margin:26px 0 8px;padding-bottom:6px;border-bottom:1px solid var(--border);scroll-margin-top:110px}
.g-entry{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:13px 16px;margin-bottom:10px;scroll-margin-top:110px}
.g-entry:target{border-color:var(--violet);box-shadow:0 0 0 3px var(--violet-bg)}
.g-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 10px;margin-bottom:4px}
.g-term{font-size:16px;font-weight:700}
.g-cat{font:700 10px var(--mono);letter-spacing:.6px;text-transform:uppercase;color:var(--t2);background:var(--card2);border:1px solid var(--border);border-radius:5px;padding:1px 7px}
.g-def{color:var(--text);font-size:14px}
.g-ex{display:block;margin-top:8px;background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:6px 10px;font:12.5px/1.5 var(--mono);color:var(--t2);white-space:pre-wrap;overflow-wrap:anywhere}
.g-foot{margin-top:8px;font-size:12px;color:var(--t2)}
.none{color:var(--t2);padding:30px 0;text-align:center}
[hidden]{display:none!important}
:focus-visible{outline:2px solid var(--violet);outline-offset:2px}
@media(max-width:560px){.wrap{padding:52px 16px 70px}.g-entry{padding:12px 13px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="crumb"><a href="index.html">&larr; Course home</a> &middot; <a href="cheatsheets/index.html">Cheat sheets</a></div>
  <h1>Course <span>Glossary</span></h1>
  <p class="lede">__N__ terms in plain English, each with a tiny example and a link to the chapter that teaches it. In lessons, the first use of a term is underlined with a dotted line; hover, focus or tap it to see the definition.</p>
  <div class="tools">
    <input class="g-search" id="g-q" type="search" placeholder="Filter terms, e.g. decorator, PSI, softmax..." aria-label="Filter glossary terms" autocomplete="off"/>
    <div class="chips" id="g-cats" role="group" aria-label="Filter by area"></div>
    <div class="az" id="g-az" aria-label="Jump to letter"></div>
    <div class="count" id="g-count" role="status" aria-live="polite"></div>
  </div>
  <div id="g-list">
__BODY__
  </div>
  <p class="none" id="g-none" hidden>No terms match. Try fewer letters.</p>
</div>
<script>
(function(){
  var q=document.getElementById('g-q'),list=document.getElementById('g-list'),cnt=document.getElementById('g-count'),
      none=document.getElementById('g-none'),chipBox=document.getElementById('g-cats'),az=document.getElementById('g-az');
  var entries=[].slice.call(list.querySelectorAll('.g-entry')),groups=[].slice.call(list.querySelectorAll('.g-group'));
  var cat='';
  var cats=[];entries.forEach(function(e){var c=e.getAttribute('data-cat');if(cats.indexOf(c)<0)cats.push(c)});
  function chip(label,val){var b=document.createElement('button');b.type='button';b.className='chip';b.textContent=label;
    b.setAttribute('aria-pressed',val===cat?'true':'false');b.setAttribute('data-v',val);
    b.addEventListener('click',function(){cat=val;paint();apply()});chipBox.appendChild(b)}
  function paint(){chipBox.textContent='';chip('All','');cats.forEach(function(c){chip(c,c)})}
  groups.forEach(function(g){var a=document.createElement('a');a.href='#'+g.id;a.textContent=g.getAttribute('data-l');a.setAttribute('data-l',g.getAttribute('data-l'));az.appendChild(a)});
  function apply(){
    var s=q.value.toLowerCase().trim(),shown=0;
    entries.forEach(function(e){
      var ok=(!cat||e.getAttribute('data-cat')===cat)&&(!s||e.getAttribute('data-q').indexOf(s)>=0);
      e.hidden=!ok;if(ok)shown++;
    });
    groups.forEach(function(g){var any=g.querySelector('.g-entry:not([hidden])');g.hidden=!any;
      var l=az.querySelector('[data-l="'+g.getAttribute('data-l')+'"]');if(l)l.className=any?'':'off'});
    cnt.textContent='Showing '+shown+' of '+entries.length+' terms';
    none.hidden=shown>0;
  }
  q.addEventListener('input',apply);
  paint();apply();
  if(location.hash){var t=document.getElementById(decodeURIComponent(location.hash.slice(1)));if(t&&t.scrollIntoView)t.scrollIntoView()}
})();
</script>
</body>
</html>
"""


def label(ch, domains):
    m = re.match(r'^ch0*(\d+)$', ch['chapter'])
    if m:
        return 'Ch %s: %s' % (m.group(1), ch['title'])
    if re.match(r'^\w+ \d+', ch['title']):
        return ch['title']
    return '%s: %s' % (domains.get(ch['domain'], ch['domain']), ch['title'])


def render(data, skills):
    domains = cp.load_skills()['domains']
    by_file = {s['chapter']: s for s in skills.values()}
    groups = {}
    for e in data['terms']:
        c = e['term'][0].upper()
        c = c if c.isalpha() else '#'
        groups.setdefault(c, []).append(e)
    parts = []
    for letter in sorted(groups):
        parts.append('    <section class="g-group" id="letter-%s" data-l="%s"><div class="letter">%s</div>' % (letter, letter, letter))
        for e in groups[letter]:
            ch = by_file[e['chapter']]
            q = ' '.join([e['term']] + e['alt'] + [e['definition']]).lower()
            parts.append(
                '      <article class="g-entry" id="%s" data-cat="%s" data-q="%s">'
                '<div class="g-head"><span class="g-term">%s</span><span class="g-cat">%s</span></div>'
                '<div class="g-def">%s</div><code class="g-ex">%s</code>'
                '<div class="g-foot">Taught in <a href="%s">%s</a></div></article>' % (
                    e['id'], html.escape(e['cat']), html.escape(q, quote=True), html.escape(e['term']), html.escape(e['cat']),
                    html.escape(e['definition']), html.escape(e['example']), html.escape(e['href']),
                    html.escape(label(ch, domains))))
        parts.append('    </section>')
    return PAGE.replace('__N__', str(len(data['terms']))).replace('__BODY__', '\n'.join(parts))


def main(argv):
    data = load()
    errors, skills = validate_and_normalise(data)
    if errors:
        print('\n'.join('ERROR ' + e for e in errors))
        return 1
    if '--check' in argv:
        print('glossary ok: %d terms' % len(data['terms']))
        return 0
    with open(GJSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write('\n')
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(render(data, {s['id']: s for s in skills.values()}))
    print('wrote %s (%d terms) and glossary.html' % (os.path.relpath(GJSON, cp.ROOT), len(data['terms'])))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
