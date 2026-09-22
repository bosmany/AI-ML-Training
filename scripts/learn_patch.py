#!/usr/bin/env python3
"""Idempotent patcher for the learning-mechanics feature (assets/learn.js).

Run from the repo root:

    python3 /home/laborant/.cache/course-work/blueprint/learn_patch.py [options] [files...]

  no files        every *.html under the current dir (skips .git, node_modules, .github, .fastapi-venv)
  --check         list pages missing the feature; change nothing; exit 1 if any are missing
  --dry-run       report what would change, write nothing
  --refresh       replace existing marked blocks with the current text (still idempotent)
  --remove        strip the blocks
  --exclude GLOB  skip files whose repo-relative path or basename matches GLOB (repeatable)

Marked blocks (inserted only if the start marker is absent, so re-runs never double-insert):

  <!-- feat:learn:start --><script src="<depth-correct>assets/learn.js" defer></script><!-- feat:learn:end -->
        just before the last </body> of every page (adds the streak/due chip and captures quiz results)
  <!-- feat:learn-links:start --> ... <!-- feat:learn-links:end -->
        index.html only: Dashboard + Review links above the first module
"""
import fnmatch, os, re, sys

SKIP_DIRS = {'.git', 'node_modules', '.github', '.fastapi-venv', '.venv', '__pycache__'}
LINKS = ('<!-- feat:learn-links:start -->\n'
         '  <p class="lrn-links"><a href="dashboard.html">\U0001F4CA Dashboard</a><a href="review.html">\U0001F4DD Review</a></p>\n'
         '  <!-- feat:learn-links:end -->\n  ')


def rel_asset(path):
    d = os.path.dirname(os.path.normpath(path)) or '.'
    return os.path.relpath('assets/learn.js', d).replace(os.sep, '/')


def script_block(path):
    return '<!-- feat:learn:start --><script src="%s" defer></script><!-- feat:learn:end -->\n' % rel_asset(path)


def block_re(name):
    return re.compile(r'<!-- feat:%s:start -->.*?<!-- feat:%s:end -->\n?(?:  )?' % (name, name), re.S)


def has(html, name):
    return ('<!-- feat:%s:start -->' % name) in html


def is_index(path):
    return os.path.normpath(path) == 'index.html'


def patch(html, path, refresh=False):
    changed = []
    blk = script_block(path)
    if has(html, 'learn'):
        if refresh:
            new = re.sub(r'<!-- feat:learn:start -->.*?<!-- feat:learn:end -->\n?', lambda m: blk, html, count=1, flags=re.S)
            if new != html:
                html = new; changed.append('learn')
    else:
        i = html.lower().rfind('</body>')
        if i < 0:
            raise ValueError('no </body> found')
        html = html[:i] + blk + html[i:]
        changed.append('learn')
    if is_index(path):
        if has(html, 'learn-links'):
            if refresh:
                new = block_re('learn-links').sub(lambda m: LINKS, html, count=1)
                if new != html:
                    html = new; changed.append('learn-links')
        else:
            m = re.search(r'<div class="module">', html)
            if not m:
                raise ValueError('no <div class="module"> anchor in index.html')
            # replace the two-space indent that precedes the anchor, keep it after the block
            start = m.start()
            if html[start - 2:start] == '  ':
                start -= 2
            html = html[:start] + '  ' + LINKS + html[m.start():]
            changed.append('learn-links')
    return html, changed


def remove(html):
    changed = []
    for n in ('learn', 'learn-links'):
        new = block_re(n).sub('', html)
        if new != html:
            html = new; changed.append(n)
    return html, changed


def collect(root='.'):
    out = []
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
        for f in sorted(files):
            if f.endswith('.html'):
                out.append(os.path.normpath(os.path.join(d, f)))
    return out


def main(argv):
    args = list(argv)
    flags = {'--check': False, '--dry-run': False, '--refresh': False, '--remove': False}
    excludes, files = [], []
    i = 0
    while i < len(args):
        a = args[i]
        if a in flags:
            flags[a] = True
        elif a == '--exclude':
            i += 1; excludes.append(args[i])
        elif a.startswith('--exclude='):
            excludes.append(a.split('=', 1)[1])
        elif a in ('-h', '--help'):
            print(__doc__); return 0
        elif a.startswith('--'):
            sys.exit('unknown option ' + a)
        else:
            files.append(a)
        i += 1
    targets = [os.path.normpath(f) for f in files] if files else collect('.')
    targets = [t for t in targets if not any(fnmatch.fnmatch(t, ex) or fnmatch.fnmatch(os.path.basename(t), ex) for ex in excludes)]

    if flags['--check']:
        missing = 0
        for t in targets:
            with open(t, encoding='utf-8', newline='') as f:
                h = f.read()
            if not has(h, 'learn') or (is_index(t) and not has(h, 'learn-links')):
                missing += 1; print('MISSING: %s' % t)
        print('%d/%d pages have the learn feature; %d missing' % (len(targets) - missing, len(targets), missing))
        return 1 if missing else 0

    patched = skipped = failed = 0
    for t in targets:
        try:
            with open(t, encoding='utf-8', newline='') as f:
                html = f.read()
            new, ch = remove(html) if flags['--remove'] else patch(html, t, refresh=flags['--refresh'])
            if not ch:
                skipped += 1; print('skip    %s' % t); continue
            if not flags['--dry-run']:
                tmp = t + '.learntmp'
                with open(tmp, 'w', encoding='utf-8', newline='') as f:
                    f.write(new)
                os.replace(tmp, t)
            patched += 1
            print('%s %s [%s]' % ('would  ' if flags['--dry-run'] else 'patched', t, ','.join(ch)))
        except Exception as e:  # noqa
            failed += 1; print('FAILED  %s: %s' % (t, e))
    print('done: %d patched, %d skipped, %d failed (%d files)' % (patched, skipped, failed, len(targets)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
