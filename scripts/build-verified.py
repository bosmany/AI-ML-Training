#!/usr/bin/env python3
"""Write assets/verified.json from a real run of the Pyodide grading harness.

    node scripts/pyodide-grade.js --json=/tmp/grade.json        # runs every chapter under Pyodide 0.26.4
    python3 scripts/build-verified.py /tmp/grade.json [--date YYYY-MM-DD]
    python3 /home/laborant/.cache/course-work/blueprint/verified_patch.py --refresh   # re-bake the footer badges

Only chapters whose harness result is "ok" are listed. Two honest methods exist:
  * kind "pyodide": every runnable lesson block and every exercise solution was executed in Pyodide.
  * kind "colab":   the chapter needs libraries the browser cannot run (PyTorch, FastAPI, transformers); the harness
                    pattern-checks the exercise answers and parses them, but the code is NOT executed in the browser.
Neither claims human review; every record says so ("human review pending"). Change that only when a person signs off.
"""
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYODIDE = 'executed under Pyodide 0.26.4 + reviewed by AI, human review pending'
COLAB = 'exercise answers pattern-checked (code runs on Colab, not in the browser) + reviewed by AI, human review pending'


def main(argv):
    if not argv or argv[0].startswith('--'):
        print(__doc__)
        return 2
    date = datetime.date.today().isoformat()
    if '--date' in argv:
        date = argv[argv.index('--date') + 1]
    with open(argv[0], encoding='utf-8') as f:
        grade = json.load(f)
    with open(os.path.join(ROOT, 'assets', 'skills.json'), encoding='utf-8') as f:
        skills = json.load(f)['skills']
    by_file = {r['file']: r for r in grade['results']}
    chapters, skipped = {}, []
    for s in skills:
        r = by_file.get(s['file'])
        if not r or r.get('status') != 'ok':
            skipped.append(s['chapter'])
            continue
        ex, lb = r['exercises'], r['lesson']
        checks = 'exercise solutions %d/%d' % (ex['solutionsPassed'], ex['total'])
        if lb['total']:
            checks = 'lesson blocks %d/%d, ' % (lb['passed'], lb['total']) + checks
        chapters[s['chapter']] = {
            'file': s['file'],
            'date': date,
            'method': PYODIDE if r['kind'] == 'pyodide' else COLAB,
            'checks': checks,
            'human_review': 'pending',
        }
    out = {
        'version': 1,
        'note': 'Automated checks only. "human_review": "pending" means no person has signed off yet; do not change it without a real review.',
        'harness': 'scripts/pyodide-grade.js (Pyodide %s)' % grade.get('pyodide', '?'),
        'chapters': chapters,
    }
    with open(os.path.join(ROOT, 'assets', 'verified.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write('\n')
    print('verified.json: %d chapters (%d not listed: %s)' % (len(chapters), len(skipped), ', '.join(skipped) or '-'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
