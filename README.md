# AI/ML: Zero to Hero

An interactive, self-contained, browser-based course that takes someone from zero programming knowledge to a working AI/ML skillset — Python fundamentals, math, data tools, classical ML, deep learning, NLP/LLMs, and MLOps deployment.

Every chapter is a single standalone `.html` file: open it in a browser (double-click, or host it anywhere) and it runs real Python **in the browser** via [Pyodide](https://pyodide.org/) (actual CPython + NumPy/Pandas compiled to WebAssembly) — no server, no install. Each chapter follows the same shape: **Lesson → 5 auto-graded Practice exercises → a Mini Project → a Quiz** (80% to unlock the next chapter). Progress is saved per-browser via `localStorage`.

## Status: 10 of 30 chapters complete (Modules 1–3)

| # | Chapter | File | Status |
|---|---------|------|--------|
| 1 | Python Basics | `python/ch01-python-basics.html` | ✅ Done |
| 2 | Control Flow | `python/ch02-control-flow.html` | ✅ Done |
| 3 | Functions & Modules | `python/ch03-functions-modules.html` | ✅ Done |
| 4 | Data Structures | `python/ch04-data-structures.html` | ✅ Done |
| 5 | OOP, Files & Errors *(Module 1 capstone)* | `python/ch05-oop-files-errors.html` | ✅ Done |
| 6 | Linear Algebra for ML | `math/ch06-linear-algebra.html` | ✅ Done |
| 7 | Probability & Statistics | `math/ch07-probability-statistics.html` | ✅ Done |
| 8 | Calculus & Optimization *(Module 2 capstone)* | `math/ch08-calculus-optimization.html` | ✅ Done |
| 9 | NumPy Deep Dive | `data/ch09-numpy-deep-dive.html` | ✅ Done |
| 10 | Pandas Fundamentals | `data/ch10-pandas-fundamentals.html` | ✅ Done |
| 11 | Data Cleaning & Wrangling | `data/ch11-data-cleaning-wrangling.html` | ⬜ Not started |
| 12 | Data Visualization *(Module 3 capstone)* | `data/ch12-data-visualization.html` | ⬜ Not started |
| 13–18 | Module 4: Classical ML (sklearn) | `ml/` | ⬜ Not started |
| 19–24 | Module 5: Deep Learning | `dl/` | ⬜ Not started |
| 25–28 | Module 6: NLP, LLMs & GenAI | `nlp/` | ⬜ Not started |
| 29–30 | Module 7: MLOps & Deployment | `mlops/` | ⬜ Not started |

Open `index.html` at the repo root to see the full course map and live per-chapter progress (reads from `localStorage`, key `aimlZTH_progress_v1`).

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

## Full 30-chapter curriculum (the plan)

**Module 1 — Python Foundations** (done): Basics, Control Flow, Functions & Modules, Data Structures, OOP/Files/Errors.

**Module 2 — Math & Stats for ML** (done): Linear Algebra, Probability & Statistics, Calculus & Optimization.

**Module 3 — Data Tools** (2/4 done): NumPy Deep Dive ✅, Pandas Fundamentals ✅, **Data Cleaning & Wrangling** (missing values, duplicates, merges, groupby, pivot tables), **Data Visualization** *(capstone: Matplotlib/Seaborn EDA story)*.

**Module 4 — Classical Machine Learning**: ML Foundations & Workflow (train/test split, bias-variance, metrics) → Linear & Logistic Regression (from scratch + sklearn) → Trees, Forests & Ensembles → Clustering & Dimensionality Reduction (K-Means, PCA) → Feature Engineering & Model Selection (pipelines, cross-validation) → **Classical ML Capstone** (end-to-end project).

**Module 5 — Deep Learning**: Neural Network Fundamentals (backprop from scratch with NumPy, runs in-browser) → Intro to PyTorch *(Colab notebook — full PyTorch can't run in-browser)* → CNNs *(Colab)* → RNNs/LSTMs *(Colab)* → Transformers Explained (attention from scratch, can run in-browser) → **Deep Learning Capstone** *(Colab)*.

**Module 6 — NLP, LLMs & GenAI**: NLP Fundamentals (tokenization, TF-IDF) → Modern NLP with Transformers *(Colab, HuggingFace)* → How LLMs Actually Work (next-token prediction, sampling, prompting) → **Building with LLM APIs Capstone** (RAG, embeddings search, a tool-calling agent).

**Module 7 — MLOps & Deployment**: Model Deployment (FastAPI, Docker) *(Colab)* → **MLOps Fundamentals Hero Project** (experiment tracking, monitoring, CI/CD for retraining).

Chapters marked *(Colab)* use a provided Colab notebook instead of the in-browser console, because Pyodide can't run PyTorch/TensorFlow — everything else runs live in the browser via Pyodide, including NumPy and Pandas.

## Resuming this project

Tell whoever picks this up: **"Continue the AI/ML Zero to Hero course from Chapter 11 (Data Cleaning & Wrangling), following the same process documented in README.md."** That's enough context to keep going without re-deriving the design decisions above.
