# AI/ML: Zero to Hero

An interactive, self-contained, browser-based course that takes someone from zero programming knowledge to a working AI/ML skillset — Python fundamentals, math, data tools, classical ML, deep learning, NLP/LLMs, and MLOps deployment.

Every chapter is a single standalone `.html` file: open it in a browser (double-click, or host it anywhere) and it runs real Python **in the browser** via [Pyodide](https://pyodide.org/) (actual CPython + NumPy/Pandas compiled to WebAssembly) — no server, no install. Each chapter follows the same shape: **Lesson → 5 auto-graded Practice exercises → a Mini Project → a Quiz** (80% to unlock the next chapter). Progress is saved per-browser via `localStorage`.

## Status: 12 of 32 chapters complete (Modules 1–2, and 2/4 of Module 3)

The course was expanded from 30 to 32 chapters partway through Module 1: the original Ch 1-5
(Python basics through OOP/files/errors) covers the *language*, but not the professional/DevOps
Python skills every ML engineer and DevOps engineer also needs (venvs, testing, logging,
decorators, generators, CLI tools, JSON/APIs, env-based config, async). Two chapters were
inserted — Ch 6 and Ch 7 — and everything from the old Ch 6 onward shifted by +2. See
"Full 32-chapter curriculum" below.

| # | Chapter | File | Status |
|---|---------|------|--------|
| 1 | Python Basics | `python/ch01-python-basics.html` | ✅ Done |
| 2 | Control Flow | `python/ch02-control-flow.html` | ✅ Done |
| 3 | Functions & Modules | `python/ch03-functions-modules.html` | ✅ Done |
| 4 | Data Structures | `python/ch04-data-structures.html` | ✅ Done |
| 5 | OOP, Files & Errors | `python/ch05-oop-files-errors.html` | ✅ Done |
| 6 | Professional Python (venv/pip, exceptions, context managers, decorators, generators, logging, testing) | `python/ch06-professional-python.html` | ✅ Done |
| 7 | Python for DevOps & APIs *(Module 1 capstone: argparse, JSON, requests/subprocess patterns, env config, asyncio)* | `python/ch07-python-devops-apis.html` | ✅ Done |
| 8 | Linear Algebra for ML | `math/ch08-linear-algebra.html` | ✅ Done |
| 9 | Probability & Statistics | `math/ch09-probability-statistics.html` | ✅ Done |
| 10 | Calculus & Optimization *(Module 2 capstone)* | `math/ch10-calculus-optimization.html` | ✅ Done |
| 11 | NumPy Deep Dive | `data/ch11-numpy-deep-dive.html` | ✅ Done |
| 12 | Pandas Fundamentals | `data/ch12-pandas-fundamentals.html` | ✅ Done |
| 13 | Data Cleaning & Wrangling | `data/ch13-data-cleaning-wrangling.html` | ⬜ Not started |
| 14 | Data Visualization *(Module 3 capstone)* | `data/ch14-data-visualization.html` | ⬜ Not started |
| 15–20 | Module 4: Classical ML (sklearn) | `ml/` | ⬜ Not started |
| 21–26 | Module 5: Deep Learning | `dl/` | ⬜ Not started |
| 27–30 | Module 6: NLP, LLMs & GenAI | `nlp/` | ⬜ Not started |
| 31–32 | Module 7: MLOps & Deployment | `mlops/` | ⬜ Not started |

Open `index.html` at the repo root to see the full course map and live per-chapter progress (reads from `localStorage`, key `aimlZTH_progress_v1`).

### Renumbering note (read this before touching Ch 8+ files)

Chapters 6-10 of the *original* 30-chapter plan were mechanically renumbered to 8-12 (old
`math/ch06-08` → `math/ch08-10`, old `data/ch09-10` → `data/ch11-12`) via a one-pass regex
mapping (`new = old <= 5 ? old : old + 2`) applied to `Chapter N`/`Ch N` text, `chNN` id tokens
(CH_ID, hrefs, `store.chapters[...]` keys, `N.M` section-header numbers), and `of 30` → `of 32`.
Two boundary links needed hand-fixing afterward because they cross the insertion point: Ch 5's
"coming next"/next-chapter-card (now points to the new Ch 6, not old Ch 6/Linear Algebra), and
Ch 8/Linear Algebra's back-link + prereq check (now points to Ch 7, not old-Ch-5). Ch 5 also had
its capstone framing (badges, "Module 1 Capstone" labels) removed, since Ch 7 is now the Module 1
capstone. If you ever renumber again, grep for `sb-back`, `next-chapter-card`, `store.chapters\[`,
and `apstone` across the affected files — those are the spots a blind number-shift won't fix.

## How this was built (read before resuming)

- **Engine:** every chapter loads Pyodide from a CDN (`https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js`) and calls `pyodide.loadPackagesFromImports(code)` before running student code, so `import numpy`, `import pandas`, etc. auto-fetch on first use. First load per chapter takes ~10-15s (one-time per browser tab); after that it's instant.
- **Autograding:** exercises and mini-projects check printed output via substring matching (case-insensitive) against pre-computed expected values. **Every numeric answer baked into a checker was independently verified** (via a Node.js arithmetic simulation, since no local Python was available while building) before shipping — this matters, because the original Chapter 1 prototype this course was rebuilt from had two real autograder bugs (a check hard-coded to one example answer despite the task saying "use your own values"; a check requiring text that never appeared in its own reference solution). Do not add a numeric checker without independently verifying the expected value first.
- **Floating-point care:** exercises that iterate many times (e.g. gradient descent) can't always use exact-string checks — different-but-equally-correct implementations can diverge in the last few float digits after hundreds/thousands of iterations (see Chapter 8's capstone, which uses a numeric tolerance range parsed via regex instead of exact match). Keep this in mind for future iterative/numerical chapters (optimizers, training loops in Module 5).
- **Cross-chapter continuity:** the "candidate scoring" dataset theme (Alice/Bob/Carol/Dave/Eve, Hubli/Pune/Mumbai/Delhi, scores) recurs across Chapters 1, 4, 5, and 10 deliberately, so returning learners see the same problem solved with progressively better tools (raw loops → data structures → OOP+files → Pandas one-liners).
- **Folder = module:** `python/` = Module 1, `math/` = Module 2, `data/` = Module 3. Continue this convention: `ml/` for Module 4, `dl/` for Module 5, `nlp/` for Module 6, `mlops/` for Module 7.
- **Per-chapter checklist when building a new one:**
  1. Copy the previous chapter's HTML as a template (CSS/JS shell is identical across chapters — only content, `CH_ID`, sidebar links, and exercise/quiz data change).
  2. Update `CH_ID`, the "back" link, the "coming next" sidebar list, and the previous-chapter-quiz-passed check (`store.chapters['chXX']`).
  3. Design exercises/project with **fixed, given inputs** (not "pick your own values") so outputs are deterministic and checkable.
  4. Verify every expected numeric answer independently (Node.js arithmetic or equivalent) before writing it into a checker.
  5. Run the JS syntax check and div-tag-balance check (see below) before considering the chapter done.
  6. Update `index.html`'s `MODULES` object (flip `avail:false` → `true`) and this README's table.

### Quick verification commands used throughout

```bash
# JS syntax check on a chapter file
node -e "
const fs=require('fs');
const html=fs.readFileSync('path/to/chXX.html','utf8');
const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
scripts.forEach((s,i)=>{ try{ new Function(s); console.log('OK'); } catch(e){ console.log('SYNTAX ERROR:', e.message); } });
"

# div tag balance check
node -e "
const fs=require('fs');
const html=fs.readFileSync('path/to/chXX.html','utf8');
console.log('open:', (html.match(/<div/g)||[]).length, 'close:', (html.match(/<\/div>/g)||[]).length);
"
```

## Full 32-chapter curriculum (the plan)

**Module 1 — Python Foundations** (done, 7 chapters): Basics, Control Flow, Functions & Modules, Data Structures, OOP/Files/Errors, **Professional Python** (venv/pip, custom exceptions, context managers, decorators, generators, logging, unittest), **Python for DevOps & APIs** *(capstone: argparse, JSON, requests/subprocess patterns, env-based config, asyncio)*.

**Module 2 — Math & Stats for ML** (done): Linear Algebra, Probability & Statistics, Calculus & Optimization.

**Module 3 — Data Tools** (2/4 done): NumPy Deep Dive ✅, Pandas Fundamentals ✅, **Data Cleaning & Wrangling** (missing values, duplicates, merges, groupby, pivot tables), **Data Visualization** *(capstone: Matplotlib/Seaborn EDA story)*.

**Module 4 — Classical Machine Learning** (Ch 15-20): ML Foundations & Workflow (train/test split, bias-variance, metrics) → Linear & Logistic Regression (from scratch + sklearn) → Trees, Forests & Ensembles → Clustering & Dimensionality Reduction (K-Means, PCA) → Feature Engineering & Model Selection (pipelines, cross-validation) → **Classical ML Capstone** (end-to-end project).

**Module 5 — Deep Learning** (Ch 21-26): Neural Network Fundamentals (backprop from scratch with NumPy, runs in-browser) → Intro to PyTorch *(Colab notebook — full PyTorch can't run in-browser)* → CNNs *(Colab)* → RNNs/LSTMs *(Colab)* → Transformers Explained (attention from scratch, can run in-browser) → **Deep Learning Capstone** *(Colab)*.

**Module 6 — NLP, LLMs & GenAI** (Ch 27-30): NLP Fundamentals (tokenization, TF-IDF) → Modern NLP with Transformers *(Colab, HuggingFace)* → How LLMs Actually Work (next-token prediction, sampling, prompting) → **Building with LLM APIs Capstone** (RAG, embeddings search, a tool-calling agent).

**Module 7 — MLOps & Deployment** (Ch 31-32): Model Deployment (FastAPI, Docker) *(Colab)* → **MLOps Fundamentals Hero Project** (experiment tracking, monitoring, CI/CD for retraining).

Chapters marked *(Colab)* use a provided Colab notebook instead of the in-browser console, because Pyodide can't run PyTorch/TensorFlow — everything else runs live in the browser via Pyodide, including NumPy and Pandas.

### A note on chapters 6-7's "unrunnable" sections

`python/ch06-professional-python.html` (venv/pip) and `python/ch07-python-devops-apis.html`
(`requests`, `subprocess`) each contain 1-2 lesson subsections that show real production code but
have **no Run button** — Pyodide is a WebAssembly sandbox with no real OS process/filesystem, so
`pip install`, `subprocess.run(...)`, and outbound `requests.get(...)` calls aren't meaningful
in-browser. Every *graded* exercise in both chapters only uses parts of the standard library that
genuinely execute in Pyodide (argparse, json, os.environ, asyncio, contextlib, unittest, logging
with `force=True` to avoid duplicate handlers across re-runs in the same session). Chapter 7's
async exercises use bare top-level `await` (Pyodide's `runPythonAsync` supports this natively,
the same mechanism as IPython's autoawait) — never `asyncio.run(...)`, which would raise
`RuntimeError` since Pyodide's own event loop is already running.

## Resuming this project

Tell whoever picks this up: **"Continue the AI/ML Zero to Hero course from Chapter 13 (Data Cleaning & Wrangling), following the same process documented in README.md."** That's enough context to keep going without re-deriving the design decisions above.
