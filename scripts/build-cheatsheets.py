#!/usr/bin/env python3
"""Generate printable one-chapter cheat sheets: cheatsheets/<chapterid>.html plus cheatsheets/index.html.

    python3 scripts/build-cheatsheets.py [--budget LINES] [--only ch03,ch16]
    python3 /home/laborant/.cache/course-work/blueprint/cheat_patch.py     # adds the sidebar links

Content is compiled from the chapter itself (nothing is invented): the chapter's summary list, the recap boxes /
lead sentences of each section, "watch out" callouts (warn/danger boxes), small lesson tables and short code
snippets. A line budget keeps every sheet within 2 printed A4 pages (checked in Chromium with the print CSS).
"""
import datetime
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _course_parse as cp  # noqa: E402

OUT_DIR = os.path.join(cp.ROOT, 'cheatsheets')
BUDGET = 232          # estimated printed lines (2 pages x 2 columns)
CHARS_PER_LINE = 50
PREFIX = {'ch': 'Ch', 'oop': 'OOP', 'sf': 'Systems', 'ds': 'DSA', 'do': 'DevOps', 'mp': 'MLOps'}
SUMMARY_RX = re.compile(r'summary|takeaway|what you can now do', re.I)
SKIP_RX = re.compile(r'summary|takeaway|bridge:|mock interview', re.I)


def esc(s):
    return html.escape(s, quote=False)


def inline(node, keep=('code', 'strong', 'b', 'em', 'i')):
    """Sanitised inline HTML: keep code/strong/em, flatten everything else to text."""
    out = []

    def rec(n):
        for c in n.children:
            if isinstance(c, str):
                out.append(esc(c))
            elif c.tag in ('script', 'style'):
                continue
            elif c.tag in keep:
                t = 'strong' if c.tag == 'b' else 'em' if c.tag == 'i' else c.tag
                out.append('<%s>' % t)
                rec(c)
                out.append('</%s>' % t)
            elif c.tag == 'br':
                out.append(' ')
            else:
                rec(c)
    rec(node)
    return re.sub(r'\s+', ' ', ''.join(out)).strip()


def plain_len(h):
    return len(re.sub(r'<[^>]+>', '', html.unescape(h)))


def clip_html(h, n):
    """Trim inline html to about n visible chars at a sentence (or word) boundary, keeping tags balanced."""
    if plain_len(h) <= n:
        return h
    sents = cp.sentences(h)
    out = ''
    for s in sents:
        if out and plain_len(out + ' ' + s) > n:
            break
        out = (out + ' ' + s).strip()
        if plain_len(out) > n:
            break
    if plain_len(out) > n * 1.25 or not out:  # single very long sentence: cut on a word boundary
        words, out2, cnt = h.split(' '), [], 0
        for w in words:
            cnt += plain_len(w) + 1
            if cnt > n:
                break
            out2.append(w)
        out = ' '.join(out2).rstrip(',;: ') + '…'
    for tag in ('code', 'strong', 'em'):
        d = out.count('<%s>' % tag) - out.count('</%s>' % tag)
        if d > 0:
            out += '</%s>' % tag * d
    return out


def heading_text(h):
    t = cp.norm(h)
    return re.sub(r'^\s*[\w.]*\d[\w.]*\s*[—–:-]\s*', '', t)


def chapter_label(skill):
    m = re.match(r'^([a-z]+)0*(\d+)$', skill['chapter'])
    pre, n = PREFIX.get(m.group(1), m.group(1).upper()), m.group(2)
    title = skill['title']
    if re.match(r'^\w+ \d+:', title):
        return title
    return '%s %s: %s' % (pre, n, title)


def lines_for(h, per=CHARS_PER_LINE):
    return max(1, -(-plain_len(h) // per)) + 0.35


NARRATIVE = re.compile(r'^(suppose|imagine|think|picture|here|now|so|let|consider|remember|notice|you|in this|this chapter|why|what|how|when|if you|by now|so far|last|in chapter|chapter)\b', re.I)


def score_sentence(s, pos):
    n = plain_len(s)
    if n < 35 or n > 330:
        return -9
    sc = 3.0 * ('<strong>' in s) + 1.2 * ('<code>' in s) + (1.0 if 60 <= n <= 220 else 0)
    if re.search(r'\b(is|are|means|returns|gives|holds|makes|turns|splits|stores|runs|raises|measures|computes)\b', re.sub(r'<[^>]+>', '', s)):
        sc += 1.0
    if NARRATIVE.match(re.sub(r'<[^>]+>', '', s)):
        sc -= 2.5
    if '?' in s:
        sc -= 1.5
    return sc - 0.15 * pos


def best_sentences(paras, k):
    scored, pos = [], 0
    for para in paras:
        for s in cp.sentences(inline(para)):
            scored.append((score_sentence(s, pos), pos, s))
            pos += 1
    scored = [x for x in scored if x[0] > -5]
    scored.sort(key=lambda x: -x[0])
    out = []
    for sc, ps, s in scored:
        if True:
            out.append((sc, ps, s))
        if len(out) >= k:
            break
    if not out and paras:
        ss = cp.sentences(inline(paras[0]))
        return ss[:1]
    return [x[2] for x in out]


def build_content(p, budget):
    """Return dict of ordered blocks chosen within the line budget."""
    sections = p.sections()
    used = [0.0]

    def take(cost):
        if used[0] + cost > budget:
            return False
        used[0] += cost
        return True

    summary, ideas, watch, tables, snippets = [], [], [], [], []
    body = [(h, n) for h, n in sections if not SKIP_RX.search(h)]
    summ = [(h, n) for h, n in sections if SUMMARY_RX.search(h)]

    # 1. the chapter's own summary list ("In short")
    if summ:
        for n in summ[-1][1]:
            if n.tag == 'ul' and 'step-list' in n.classes:
                for li in [c for c in n.children if hasattr(c, 'tag') and c.tag == 'li']:
                    summary.append(clip_html(inline(li), 250))
                break
    summary_cost = sum(lines_for(s) for s in summary)
    cap = budget * 0.40
    while summary and summary_cost > cap:
        summary.pop()
        summary_cost = sum(lines_for(s) for s in summary)
    used[0] += summary_cost + 1.6 if summary else 0

    # 2. per-section key ideas (recap bullets, else definition-style lead sentence)
    idea_rows = []
    for h, nodes in body:
        bullets = []
        recaps = [n for n in nodes if n.tag == 'div' and 'recap' in n.classes]
        if recaps:
            for li in cp.find_all(recaps[0], lambda x: x.tag == 'li'):
                bullets.append(clip_html(inline(li), 170))
            bullets = bullets[:3]
        else:
            paras = [n for n in nodes if n.tag == 'p' and 'lesson-p' in n.classes][:4]
            bullets = [clip_html(x, 230) for x in best_sentences(paras, 3)]
        if bullets:
            idea_rows.append((heading_text(h), h, bullets))
    # add rounds so every section gets its first bullet before anyone gets a second
    chosen = {}
    for rnd in range(3):
        for title, raw, bullets in idea_rows:
            if rnd < len(bullets):
                cost = lines_for(bullets[rnd]) + (1.7 if title not in chosen else 0)
                if used[0] + cost <= budget * 0.72:
                    used[0] += cost
                    chosen.setdefault(title, []).append(bullets[rnd])
    for title, raw, _ in idea_rows:
        if title in chosen:
            ideas.append((title, raw, chosen[title]))

    # 3. watch-outs
    boxes = []
    for h, nodes in body:
        for n in nodes:
            if n.tag == 'div' and 'info-box' in n.classes and ('warn' in n.classes or 'danger' in n.classes):
                b = cp.find_cls(n, 'ib-body')
                if b:
                    boxes.append(clip_html(inline(b[0]), 200))
    for b in boxes[:8]:
        if take(lines_for(b)):
            watch.append(b)
    if watch:
        used[0] += 1.6

    # 4. code snippets (short, self-contained looking) - one per section first
    cands = []
    for si, (h, nodes) in enumerate(body):
        for n in nodes:
            if n.tag == 'div' and 'code-block' in n.classes:
                code = cp.find_cls(n, 'cb-code')
                if not code:
                    continue
                txt = ''.join(_raw(code[0])).strip('\n').rstrip()
                ls = txt.split('\n')
                lab = cp.text(cp.find_cls(n, 'cb-label')[0]) if cp.find_cls(n, 'cb-label') else ''
                if 2 <= len(ls) <= 8 and max(len(x) for x in ls) <= 76 and len(txt) <= 420 and 'input(' not in txt:
                    cands.append((si, lab, txt))
    seen_sec, final = set(), []
    for si, lab, txt in cands:
        if si not in seen_sec:
            seen_sec.add(si)
            final.append((lab, txt))
    for lab, txt in final[:7]:
        if take(len(txt.split('\n')) + 1.6 + (0.4 if lab else 0)):
            snippets.append((lab, txt))
    # 5. tables (compact ones)
    for h, nodes in body:
        for n in nodes:
            if n.tag == 'table':
                rows = cp.find_all(n, lambda x: x.tag == 'tr')
                data = [[inline(c) for c in r.children if hasattr(c, 'tag') and c.tag in ('td', 'th')] for r in rows]
                data = [r for r in data if r]
                if not data or len(data) > 10 or max(len(r) for r in data) > 5:
                    continue
                if sum(plain_len(c) for r in data for c in r) > 900:
                    continue
                cost = sum(max(lines_for(c, 22) for c in r) for r in data) + 1.5
                if len(tables) < 3 and take(cost):
                    tables.append((heading_text(h), data))
    return dict(summary=summary, ideas=ideas, watch=watch, snippets=snippets, tables=tables, used=used[0])


def _raw(node):
    for c in node.children:
        if isinstance(c, str):
            yield c
        elif c.tag == 'br':
            yield '\n'
        else:
            yield from _raw(c)


CSS = """
:root{
  --bg:#0F1117; --card:#1A1D27; --card2:#21253A; --border:#2A2D3E;
  --violet:#7C5CFC; --violet-light:#9B7FFF; --violet-bg:rgba(124,92,252,.1);
  --cyan:#00D9A6; --cyan-bg:rgba(0,217,166,.08);
  --gold:#FFB800; --gold-bg:rgba(255,184,0,.1); --red:#FF5757; --red-bg:rgba(255,87,87,.08);
  --text:#E8EAF0; --t2:#9196A8; --t3:#5A5F72;
  --sans:'Inter',system-ui,sans-serif; --mono:'JetBrains Mono',ui-monospace,monospace;
}
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:var(--sans);font-size:15px;line-height:1.55;min-height:100vh}
a{color:var(--violet);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1100px;margin:0 auto;padding:60px 22px 70px;position:relative}
.eyebrow{font-family:var(--mono);font-size:11.5px;letter-spacing:1.6px;text-transform:uppercase;color:var(--cyan);font-weight:700;margin-bottom:12px;display:flex;align-items:center;gap:10px}
.eyebrow::before{content:'';width:26px;height:1px;background:var(--cyan)}
h1{font-size:clamp(24px,4.2vw,36px);font-weight:800;line-height:1.12;letter-spacing:-.02em;margin-bottom:8px}
h1 span{background:linear-gradient(90deg,var(--violet),var(--cyan));-webkit-background-clip:text;background-clip:text;color:transparent}
.cs-crumb{font-size:12.5px;color:var(--t2);margin-bottom:6px}
.cs-meta{font-size:13px;color:var(--t2);margin-bottom:16px}
.cs-print{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--border);background:var(--card2);color:var(--text);border-radius:8px;padding:6px 12px;font:600 12.5px var(--sans);cursor:pointer;margin-bottom:18px}
.cs-print:hover{border-color:var(--violet)}
.cs-grid{column-count:2;column-gap:22px}
.cs-sec{break-inside:auto;-webkit-box-decoration-break:clone;box-decoration-break:clone;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px 15px;margin:0 0 14px}
.cs-sec h2{font:700 11px var(--mono);letter-spacing:.9px;text-transform:uppercase;color:var(--cyan);margin-bottom:7px}
.cs-sec h3{font-size:13.5px;font-weight:700;margin:9px 0 3px;line-height:1.3;break-after:avoid}
.cs-sec li,.cs-sec tr{break-inside:avoid}
.cs-sec h3:first-of-type{margin-top:0}
.cs-sec h3 a{color:var(--text)}
.cs-sec h3 a:hover{color:var(--violet)}
.cs-sec ul{margin:0 0 0 17px;font-size:13px;color:var(--text)}
.cs-sec li{margin:2px 0}
.cs-sec code{font:12px var(--mono);background:var(--card2);border:1px solid var(--border);border-radius:4px;padding:0 4px;overflow-wrap:anywhere}
.cs-warn ul{list-style:none;margin:0}
.cs-warn li{border-left:3px solid var(--gold);padding:1px 0 1px 9px;margin:6px 0}
figure.cs-code{margin:0 0 9px;break-inside:avoid}
figure.cs-code:last-child{margin-bottom:0}
figure.cs-code figcaption{font-size:11.5px;color:var(--t2);margin-bottom:2px}
figure.cs-code pre{background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:7px 9px;font:11.5px/1.5 var(--mono);white-space:pre-wrap;overflow-wrap:anywhere;color:var(--text)}
.cs-tbl-t{font-size:12px;font-weight:700;margin:8px 0 3px}
.cs-tbl-t:first-of-type{margin-top:0}
table.cs-table{width:100%;border-collapse:collapse;font-size:12px;margin-bottom:6px}
table.cs-table th,table.cs-table td{border:1px solid var(--border);padding:3px 6px;text-align:left;vertical-align:top;overflow-wrap:anywhere}
table.cs-table th{background:var(--card2);font-weight:700}
.cs-foot{margin-top:16px;font-size:12px;color:var(--t2)}
.cs-nav{display:flex;justify-content:space-between;gap:10px;margin-top:14px;font-size:13px}
.idx-group{margin-bottom:26px}
.idx-group h2{font-size:17px;font-weight:800;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid var(--border)}
.idx-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:8px}
.idx-card{display:block;background:var(--card);border:1px solid var(--border);border-radius:9px;padding:9px 12px;color:var(--text);font-size:13.5px;font-weight:600}
.idx-card small{display:block;font:500 11px var(--mono);color:var(--t2);margin-bottom:1px}
.idx-card:hover{border-color:var(--violet);text-decoration:none}
:focus-visible{outline:2px solid var(--violet);outline-offset:2px}
@media(max-width:820px){.cs-grid{column-count:1}}
@media(max-width:560px){.wrap{padding:54px 16px 60px}}
@page{size:A4;margin:9mm 10mm}
@media print{
  :root:root{--bg:#fff;--card:#fff;--card2:#f1f2f7;--border:#b9bfd3;--text:#111;--t2:#333;--t3:#555;--violet:#3a25a8;--cyan:#005a44;--gold:#8a5a00;--violet-bg:transparent;color-scheme:light}
  html,body{background:#fff!important;color:#111!important;font-size:8.6pt;line-height:1.32}
  .wrap{max-width:none;padding:0}
  .eyebrow{display:none}
  h1{font-size:15pt;margin-bottom:2pt}h1 span{background:none;color:#3a25a8;-webkit-text-fill-color:#3a25a8}
  .cs-crumb,.cs-print,.cs-nav,.aiml-sb,.theme-toggle,.aiml-s-ov{display:none!important}
  .cs-meta{font-size:8pt;margin-bottom:5pt}
  .cs-grid{column-count:2;column-gap:5mm}
  .cs-sec{border:0.6pt solid #b9bfd3;border-radius:2pt;padding:4pt 6pt;margin:0 0 4.5pt}
  .cs-sec h2{font-size:7.6pt;margin-bottom:3pt}
  .cs-sec h3{font-size:8.8pt;margin:4pt 0 1pt}
  .cs-sec ul{font-size:8.4pt;margin-left:11pt}
  .cs-sec li{margin:0.6pt 0}
  .cs-sec code{font-size:7.9pt;padding:0 1pt;border:0}
  figure.cs-code{margin-bottom:3pt}figure.cs-code figcaption{font-size:7.6pt}
  figure.cs-code pre{font-size:7.4pt;line-height:1.35;padding:2.5pt 4pt}
  table.cs-table{font-size:7.8pt}table.cs-table th,table.cs-table td{padding:1.2pt 3pt}
  .cs-tbl-t{font-size:7.9pt}
  .cs-foot{font-size:7.2pt;margin-top:4pt}
  a{color:inherit;text-decoration:none}
}
"""

HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>%(title)s</title>
<meta name="description" content="%(desc)s"/>
<style>%(css)s</style>
</head>
<body>
"""


def cell(tag, h):
    return '<%s>%s</%s>' % (tag, h, tag)


def render_sheet(skill, c, nav, today):
    label = chapter_label(skill)
    chap_href = '../' + skill['file']
    parts = []
    if c['summary']:
        parts.append('<section class="cs-sec"><h2>In short</h2><ul>%s</ul></section>' % ''.join('<li>%s</li>' % s for s in c['summary']))
    if c['ideas']:
        rows = []
        for title, raw, bullets in c['ideas']:
            link = chap_href + '#:~:text=' + _frag(raw)
            rows.append('<h3><a href="%s">%s</a></h3><ul>%s</ul>' % (html.escape(link, quote=True), esc(title), ''.join('<li>%s</li>' % b for b in bullets)))
        parts.append('<section class="cs-sec"><h2>Key ideas by section</h2>%s</section>' % ''.join(rows))
    if c['watch']:
        parts.append('<section class="cs-sec cs-warn"><h2>Watch out</h2><ul>%s</ul></section>' % ''.join('<li>%s</li>' % w for w in c['watch']))
    if c['tables']:
        tb = []
        for title, data in c['tables']:
            rows = ''.join('<tr>%s</tr>' % ''.join(cell('th' if ri == 0 else 'td', x) for x in r) for ri, r in enumerate(data))
            tb.append('<div class="cs-tbl-t">%s</div><table class="cs-table">%s</table>' % (esc(title), rows))
        parts.append('<section class="cs-sec"><h2>Reference tables</h2>%s</section>' % ''.join(tb))
    if c['snippets']:
        sn = []
        for lab, txt in c['snippets']:
            sn.append('<figure class="cs-code">%s<pre><code>%s</code></pre></figure>' % (('<figcaption>%s</figcaption>' % esc(lab)) if lab else '', esc(txt)))
        parts.append('<section class="cs-sec"><h2>Snippets</h2>%s</section>' % ''.join(sn))
    prev_l, next_l = nav
    navh = '<div class="cs-nav"><span>%s</span><span>%s</span></div>' % (
        ('<a href="%s.html">&larr; %s</a>' % (prev_l[0], esc(prev_l[1]))) if prev_l else '',
        ('<a href="%s.html">%s &rarr;</a>' % (next_l[0], esc(next_l[1]))) if next_l else '')
    body = HEAD % dict(title=esc('AI/ML: Zero to Hero — Cheat sheet: ' + label), desc=html.escape('One-page recap of %s, compiled from the chapter.' % label, quote=True), css=CSS)
    body += ('<div class="wrap"><div class="eyebrow">Cheat sheet</div>\n'
             '<div class="cs-crumb"><a href="index.html">&larr; All cheat sheets</a> &middot; <a href="%s">Open the full chapter</a> &middot; <a href="../glossary.html">Glossary</a></div>\n'
             '<h1>%s</h1>\n'
             '<p class="cs-meta">Compiled from the chapter text on %s. A study aid: the lesson has the explanations and the caveats.</p>\n'
             '<button type="button" class="cs-print" onclick="window.print()">&#128424; Print or save as PDF</button>\n'
             '<main class="cs-grid">\n%s\n</main>\n%s\n'
             '<p class="cs-foot">Generated by <code>scripts/build-cheatsheets.py</code> from <a href="%s">%s</a>. Section titles link to the matching part of the lesson.</p>\n</div>\n</body>\n</html>\n') % (
        html.escape(chap_href, quote=True), esc(label), today, '\n'.join(parts), navh, html.escape(chap_href, quote=True), esc(skill['file']))
    return body


def _frag(raw):
    import urllib.parse
    t = cp.norm(raw)
    if len(t) > 80:
        t = t[:80].rsplit(' ', 1)[0]
    return urllib.parse.quote(t, safe='').replace('-', '%2D')


def render_index(skills, domains, today):
    groups = {}
    for s in skills:
        groups.setdefault(s['domain'], []).append(s)
    parts = []
    for d, name in domains.items():
        if d not in groups:
            continue
        cards = ''.join('<a class="idx-card" href="%s.html"><small>%s</small>%s</a>' % (
            s['chapter'], esc(re.sub(r'^([A-Za-z]+)0*(\d+)$', lambda m: PREFIX.get(m.group(1), m.group(1).upper()) + ' ' + m.group(2), s['chapter'])),
            esc(re.sub(r'^\w+ \d+:\s*', '', s['title']))) for s in groups[d])
        parts.append('<section class="idx-group"><h2>%s</h2><div class="idx-grid">%s</div></section>' % (esc(name), cards))
    return (HEAD % dict(title='AI/ML: Zero to Hero — Cheat sheets', desc='Printable two-page cheat sheets, one per chapter.', css=CSS) +
            '<div class="wrap"><div class="eyebrow">Cheat sheets</div>\n'
            '<div class="cs-crumb"><a href="../index.html">&larr; Course home</a> &middot; <a href="../glossary.html">Glossary</a></div>\n'
            '<h1>Chapter <span>cheat sheets</span></h1>\n'
            '<p class="cs-meta">One printable sheet per chapter (two A4 pages at most), compiled from the lesson text. Compiled %s.</p>\n%s\n</div>\n</body>\n</html>\n' % (today, '\n'.join(parts)))


def main(argv):
    budget = BUDGET
    only = None
    if '--budget' in argv:
        budget = float(argv[argv.index('--budget') + 1])
    if '--only' in argv:
        only = set(argv[argv.index('--only') + 1].split(','))
    data = cp.load_skills()
    skills = data['skills']
    os.makedirs(OUT_DIR, exist_ok=True)
    today = datetime.date.today().isoformat()
    made = 0
    for i, s in enumerate(skills):
        if only and s['chapter'] not in only:
            continue
        p = cp.Page(s['file'], s)
        c = build_content(p, budget)
        prev_l = (skills[i - 1]['chapter'], re.sub(r'^\w+ \d+:\s*', '', skills[i - 1]['title'])) if i else None
        next_l = (skills[i + 1]['chapter'], re.sub(r'^\w+ \d+:\s*', '', skills[i + 1]['title'])) if i + 1 < len(skills) else None
        with open(os.path.join(OUT_DIR, s['chapter'] + '.html'), 'w', encoding='utf-8') as f:
            f.write(render_sheet(s, c, (prev_l, next_l), today))
        made += 1
    if not only:
        with open(os.path.join(OUT_DIR, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(render_index(skills, data['domains'], today))
    print('wrote %d cheat sheets%s (budget %.0f lines)' % (made, '' if only else ' + index', budget))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
