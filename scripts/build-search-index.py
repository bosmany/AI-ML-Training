#!/usr/bin/env python3
"""Build assets/search-index.json for the site search (assets/search.js).

    python3 scripts/build-glossary.py            # first: the glossary terms are embedded in the index
    python3 scripts/build-search-index.py [--out assets/search-index.json]

Per page it keeps: title, folder (domain), chapter id, section headings (.lesson-h2), sub-headings (.lesson-h3),
recap bullets, callout titles (bold lead of each tip/warn box), bold key terms and inline identifiers used in the
prose (so `classmethod` or `psi` are findable), and the glossary terms (top-level list). Code blocks are never
indexed. The file stays compact (no whitespace, one array per field) and the script fails above 1.5 MB.
"""
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _course_parse as cp  # noqa: E402

MAX_BYTES = 1_500_000
PREFIX = re.compile(r'^AI/ML: Zero to Hero\s*[—-]\s*')
IDENT = re.compile(r'^[@A-Za-z_][\w.@]{2,39}$')


def clip(s, n):
    s = cp.norm(s)
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(' ', 1)[0]
    return (cut or s[:n]).rstrip(' ,;:-') + '…'


def uniq(seq, limit=None, key=str.lower):
    seen, out = set(), []
    for s in seq:
        k = key(s)
        if not s or k in seen:
            continue
        seen.add(k)
        out.append(s)
        if limit and len(out) >= limit:
            break
    return out


def page_entry(p, domains):
    e = {}
    if p.skill:
        e['t'] = p.skill['title']
        e['f'] = p.skill['domain']
        e['c'] = p.skill['chapter']
    else:
        e['t'] = PREFIX.sub('', p.doc_title) or p.h1 or p.rel
    e['u'] = p.rel
    h2 = [clip(cp.text(h), 140) for h in p.h2]
    h3 = [clip(cp.text(h), 120) for h in p.h3]
    rec = []
    for box in cp.find_cls(p.lesson, 'recap'):
        for li in cp.find_all(box, lambda n: n.tag == 'li'):
            rec.append(clip(cp.text(li), 220))
    lead = []
    for box in cp.find_cls(p.lesson, 'info-box'):
        st = cp.find_all(box, lambda n: n.tag in ('strong', 'b'))
        if st:
            lead.append(clip(cp.text(st[0]).rstrip('.:'), 100))
    strongs = [s for s in p.strongs() if 2 <= len(s) <= 50]
    codes = []
    freq = Counter()
    for c in p.inline_code():
        c = re.sub(r'\(.*?\)$', '', c.strip())
        if IDENT.match(c):
            freq[c] += 1
    codes = [c for c, _ in freq.most_common(90)]
    if h2:
        e['h'] = uniq(h2, key=lambda s: s)
    if h3:
        e['h3'] = uniq(h3, key=lambda s: s)
    if rec:
        e['r'] = uniq(rec, key=lambda s: s)
    if lead:
        e['i'] = uniq(lead, 40)
    if strongs:
        e['k'] = uniq(strongs, 60)
    if codes:
        e['x'] = uniq(codes, key=lambda s: s)
    return e


def main(argv):
    out = os.path.join(cp.ROOT, 'assets', 'search-index.json')
    if '--out' in argv:
        out = os.path.abspath(argv[argv.index('--out') + 1])
    skills = cp.load_skills()
    entries = []
    for p in cp.pages():
        entries.append(page_entry(p, skills['domains']))
    # extra generated pages (kept out of the crawl because they are outputs)
    cs = os.path.join(cp.ROOT, 'cheatsheets', 'index.html')
    if os.path.exists(cs):
        entries.append({'t': 'Cheat sheets', 'u': 'cheatsheets/index.html'})
    order = {'index.html': 0, 'glossary.html': 1}
    # keep course order for chapters (skills.json order)
    pos = {s['file']: i for i, s in enumerate(skills['skills'])}
    entries.sort(key=lambda e: (0, pos[e['u']]) if e['u'] in pos else (1, order.get(e['u'], 2), e['u']))
    idx = {e['u']: i for i, e in enumerate(entries)}
    gl = []
    gpath = os.path.join(cp.ROOT, 'assets', 'glossary.json')
    if os.path.exists(gpath):
        with open(gpath, encoding='utf-8') as f:
            g = json.load(f)
        for t in g['terms']:
            first = cp.sentences(t['definition'])[0]
            gl.append([t['term'], clip(first, 140), t['id'], idx.get(t['href'], -1), t.get('alt', [])])
        # alt forms only when present, keeps the file small
        gl = [x if x[4] else x[:4] for x in gl]
    doc = {'v': 1, 'd': skills['domains'], 'p': entries, 'g': gl}
    data = json.dumps(doc, ensure_ascii=False, separators=(',', ':'))
    if len(data.encode('utf-8')) > MAX_BYTES:
        print('ERROR index is %d bytes (> %d)' % (len(data.encode('utf-8')), MAX_BYTES))
        return 1
    with open(out, 'w', encoding='utf-8') as f:
        f.write(data)
    print('wrote %s: %d pages, %d glossary terms, %.0f KB' % (os.path.relpath(out, cp.ROOT), len(entries), len(gl), len(data.encode('utf-8')) / 1024))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
