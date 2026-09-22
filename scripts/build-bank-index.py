#!/usr/bin/env python3
"""Build bank/questions/index.json, the manifest interview-bank.html loads.

    python3 scripts/build-bank-index.py

Lists every bank/questions/*.json (except index.json) that parses as a JSON array of
question objects, with per-file counts. Broken files are reported and left out so one bad
file cannot blank the page. Output is deterministic (sorted, no timestamps).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, 'bank', 'questions')


def main():
    files, counts, total, seen, bad = [], {}, 0, {}, 0
    for name in sorted(os.listdir(DIR)):
        if not name.endswith('.json') or name == 'index.json':
            continue
        try:
            with open(os.path.join(DIR, name), encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            print('SKIP %s: %s' % (name, e), file=sys.stderr)
            bad += 1
            continue
        if not isinstance(data, list):
            print('SKIP %s: not a JSON array' % name, file=sys.stderr)
            bad += 1
            continue
        for q in data:
            qid = q.get('id') if isinstance(q, dict) else None
            if not qid:
                print('WARN %s: question without id' % name, file=sys.stderr)
            elif qid in seen:
                print('WARN duplicate id %s in %s and %s' % (qid, seen[qid], name), file=sys.stderr)
            else:
                seen[qid] = name
        files.append(name)
        counts[name] = len(data)
        total += len(data)
    out = {'version': 1, 'total': total, 'files': files, 'counts': counts}
    with open(os.path.join(DIR, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print('bank/questions/index.json: %d files, %d questions' % (len(files), total))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
