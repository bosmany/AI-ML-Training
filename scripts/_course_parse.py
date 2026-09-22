"""Shared HTML reader for the trust-layer build scripts (search index, cheat sheets, glossary).

Builds a tiny DOM from a course page and exposes the pieces the builders need. Standard library only.
"""
import json
import os
import re
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {'node_modules', '__pycache__', 'cheatsheets', 'labs'}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
RAW = {'script', 'style'}


class Node:
    __slots__ = ('tag', 'attrs', 'children', 'parent')

    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.children = []  # Node or str
        self.parent = parent

    @property
    def classes(self):
        return (self.attrs.get('class') or '').split()

    def has(self, cls):
        return cls in self.classes


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('#root')
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.children.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def parse(html):
    b = _Builder()
    b.feed(html)
    b.close()
    return b.root


def walk(node):
    for c in node.children:
        if isinstance(c, Node):
            yield c
            yield from walk(c)


def find_all(node, pred):
    return [n for n in walk(node) if pred(n)]


def find_cls(node, cls, tag=None):
    return [n for n in walk(node) if n.has(cls) and (tag is None or n.tag == tag)]


def text(node, skip_code=False, skip_tags=RAW):
    out = []

    def rec(n):
        for c in n.children:
            if isinstance(c, str):
                out.append(c)
            elif c.tag in skip_tags:
                continue
            elif skip_code and c.tag == 'code':
                continue
            else:
                if c.tag == 'br':
                    out.append(' ')
                rec(c)
    rec(node)
    return norm(''.join(out))


def norm(s):
    return re.sub(r'\s+', ' ', s).strip()


def ancestors(n):
    p = n.parent
    while p is not None:
        yield p
        p = p.parent


def html_files(root=ROOT):
    """Course pages (repo-relative posix paths), skipping dot-dirs, generated cheatsheets and labs."""
    out = []
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if not x.startswith('.') and x not in SKIP_DIRS)
        for f in sorted(files):
            if f.endswith('.html'):
                out.append(os.path.relpath(os.path.join(d, f), root).replace(os.sep, '/'))
    return out


def load_skills():
    with open(os.path.join(ROOT, 'assets', 'skills.json'), encoding='utf-8') as f:
        return json.load(f)


def sentences(s):
    """Split prose into sentences without breaking on e.g. 'e.g.' or decimals."""
    s = norm(s)
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9`(\[\'"])', s)
    fixed = []
    for p in parts:
        if fixed and re.search(r'(?:\b(?:e\.g|i\.e|vs|etc|approx|Fig|No)\.|\b[A-Za-z]\.)$', fixed[-1]):
            fixed[-1] += ' ' + p
        else:
            fixed.append(p)
    return fixed


class Page:
    """Everything the builders need from one course page."""

    def __init__(self, rel, skill=None):
        self.rel = rel
        self.skill = skill
        with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
            self.html = f.read()
        self.dom = parse(self.html)
        t = find_all(self.dom, lambda n: n.tag == 'title')
        self.doc_title = text(t[0]) if t else rel
        lesson = [n for n in walk(self.dom) if n.attrs.get('id') == 'sec-lesson']
        self.lesson = lesson[0] if lesson else (find_all(self.dom, lambda n: n.tag == 'body') or [self.dom])[0]
        self.h2 = find_cls(self.lesson, 'lesson-h2')
        self.h3 = find_cls(self.lesson, 'lesson-h3')
        h1 = find_all(self.lesson, lambda n: n.tag == 'h1')
        self.h1 = text(h1[0]) if h1 else ''

    # -- structure -----------------------------------------------------
    def sections(self):
        """[(heading_text, [content nodes])] following each .lesson-h2 in document order."""
        order = [n for n in walk(self.lesson)]
        idx = {id(n): i for i, n in enumerate(order)}
        heads = self.h2
        out = []
        for k, h in enumerate(heads):
            a = idx[id(h)]
            b = idx[id(heads[k + 1])] if k + 1 < len(heads) else len(order)
            out.append((text(h), order[a + 1:b]))
        return out

    def inline_code(self):
        toks = []
        for p in find_cls(self.lesson, 'lesson-p') + self.h2 + find_cls(self.lesson, 'recap') + find_cls(self.lesson, 'info-box'):
            for c in find_all(p, lambda n: n.tag == 'code'):
                toks.append(text(c))
        return toks

    def strongs(self):
        toks = []
        for p in find_cls(self.lesson, 'lesson-p'):
            for c in find_all(p, lambda n: n.tag in ('strong', 'b')):
                toks.append(text(c))
        return toks

    def prose(self):
        return ' '.join(text(p) for p in find_cls(self.lesson, 'lesson-p'))


def pages():
    """Yield Page objects for every course page (chapters carry their skill dict)."""
    skills = {s['file']: s for s in load_skills()['skills']}
    for rel in html_files():
        yield Page(rel, skills.get(rel))
