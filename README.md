# AI/ML: Zero to Hero

An interactive, self-contained, browser-based course that takes someone from zero programming knowledge to a working AI/ML skillset — Python fundamentals, math, data tools, classical ML, deep learning, NLP/LLMs, and MLOps deployment.

Every chapter is a single standalone `.html` file: open it in a browser (double-click, or host it anywhere) and it runs real Python **in the browser** via [Pyodide](https://pyodide.org/) (actual CPython + NumPy/Pandas compiled to WebAssembly) — no server, no install. Each chapter follows the same shape: **Lesson → 5 auto-graded Practice exercises → a Mini Project → a Quiz** (80% to unlock the next chapter). Progress is saved per-browser via `localStorage`.

## Status: all 32 core chapters complete, verified, committed & pushed. Module 8 (bonus) in progress.

The course was expanded from 30 to 32 chapters partway through Module 1 (see renumbering note
below), then expanded again with two more asks mid-build: an **Interview Prep** tab on every
module capstone (Ch 7, 10, 14, 20, 26, 30, 32), and a bonus **Module 8: Production Projects**
appended after Ch 32 (no renumbering — Module 8 lives in a new `projects/` folder, chapters 33+,
explicitly including a dedicated **Agentic AI** project).

**Verification done on the full 32-chapter set**: every `.html` file passes a syntax + div-balance
+ textarea-balance check; the entire `sb-back`/`prereq`/`next-chapter-card` link chain from Ch 1
through Ch 32 was walked programmatically and confirmed consistent (no gaps, no mismatches); a
factual error (a chapter cross-reference off by one) and an outdated model-name string were found
and fixed during a content spot-check of Ch 29/30. `index.html`'s `MODULES` object now lists all
32 chapters across 7 modules plus a placeholder Module 8.

| # | Chapter | File |
|---|---------|------|
| 1 | Python Basics | `python/ch01-python-basics.html` |
| 2 | Control Flow | `python/ch02-control-flow.html` |
| 3 | Functions & Modules | `python/ch03-functions-modules.html` |
| 4 | Data Structures | `python/ch04-data-structures.html` |
| 5 | OOP, Files & Errors | `python/ch05-oop-files-errors.html` |
| 6 | Professional Python | `python/ch06-professional-python.html` |
| 7 | Python for DevOps & APIs *(Module 1 capstone 💼)* | `python/ch07-python-devops-apis.html` |
| 8 | Linear Algebra for ML | `math/ch08-linear-algebra.html` |
| 9 | Probability & Statistics | `math/ch09-probability-statistics.html` |
| 10 | Calculus & Optimization *(Module 2 capstone 💼)* | `math/ch10-calculus-optimization.html` |
| 11 | NumPy Deep Dive | `data/ch11-numpy-deep-dive.html` |
| 12 | Pandas Fundamentals | `data/ch12-pandas-fundamentals.html` |
| 13 | Data Cleaning & Wrangling | `data/ch13-data-cleaning-wrangling.html` |
| 14 | Data Visualization *(Module 3 capstone 💼)* | `data/ch14-data-visualization.html` |
| 15 | ML Foundations & Workflow | `ml/ch15-ml-foundations-workflow.html` |
| 16 | Linear & Logistic Regression | `ml/ch16-linear-logistic-regression.html` |
| 17 | Trees, Forests & Ensembles | `ml/ch17-trees-forests-ensembles.html` |
| 18 | Clustering & Dimensionality Reduction | `ml/ch18-clustering-dimensionality-reduction.html` |
| 19 | Feature Engineering & Model Selection | `ml/ch19-feature-engineering-model-selection.html` |
| 20 | Classical ML Capstone *(Module 4 capstone 💼)* | `ml/ch20-classical-ml-capstone.html` |
| 21 | Neural Network Fundamentals (in-browser NumPy backprop) | `dl/ch21-neural-network-fundamentals.html` |
| 22 | Intro to PyTorch *(🎬 Colab chapter)* | `dl/ch22-intro-to-pytorch.html` |
| 23 | Convolutional Neural Networks *(🎬 Colab chapter)* | `dl/ch23-convolutional-neural-networks.html` |
| 24 | RNNs & LSTMs *(🎬 Colab chapter)* | `dl/ch24-rnns-lstms.html` |
| 25 | Transformers Explained (in-browser attention from scratch) | `dl/ch25-transformers-explained.html` |
| 26 | Deep Learning Capstone *(🎬 Colab, Module 5 capstone 💼)* | `dl/ch26-deep-learning-capstone.html` |
| 27 | NLP Fundamentals | `nlp/ch27-nlp-fundamentals.html` |
| 28 | Modern NLP with Transformers *(🎬 Colab chapter)* | `nlp/ch28-modern-nlp-transformers.html` |
| 29 | How LLMs Actually Work (in-browser char-level LM) | `nlp/ch29-how-llms-work.html` |
| 30 | Building with LLM APIs *(Module 6 capstone 💼, hybrid Colab-reference/runnable)* | `nlp/ch30-building-with-llm-apis-capstone.html` |
| 31 | Model Deployment | `mlops/ch31-model-deployment.html` |
| 32 | MLOps Fundamentals *(core-curriculum capstone 💼)* | `mlops/ch32-mlops-fundamentals-capstone.html` |
| 33+ | **Module 8: Production Projects** — end-to-end ML pipeline, **Agentic AI system**, deployed RAG chatbot | `projects/` | ⬜ In progress |

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

### Two more things learned while building Ch 13-14

- **Never print `list(numpy_array_or_series)` in a graded checker.** NumPy 2.0 changed scalar `repr()` to `np.int64(5)` instead of `5`, which breaks any autograder check written as `'[0, 2, 4]'` if Pyodide's NumPy is 2.x — `list.__repr__` calls `repr()` on each element. `f'{scalar}'` and `.4f`-formatted values are unaffected (they use `__format__`/`str()`, not `repr()`); only bracket-printed lists/arrays of numeric NumPy scalars are at risk. **Always use `.tolist()`** (on a NumPy array) or build a plain Python list via a comprehension before printing/checking — this was retrofitted into Ch 8 and Ch 11's exercises after the fact, so check those two files' `EXERCISES` objects as the reference pattern.
- **Ch 14 (Data Visualization) added chart-image rendering**, the first chapter to need it. `runPy()` now does a second, hidden `runPythonAsync` call after the user's code succeeds, which checks `plt.get_fignums()`, saves the current figure to a base64 PNG (`facecolor='white'`, since charts render on a transparent/white background that needs a white card behind it on this dark theme), and calls `plt.close('all')` so figures don't accumulate across re-runs in the same Pyodide session. The result is rendered as an `<img class="chart-img">` under exercise/project output and `<img class="cl-img">` in the console log. Every graded exercise still ALSO prints plain text facts checked the normal way — the image is for the student to see, not for the autograder to parse. If a future chapter needs charts again, copy this mechanism from `data/ch14-data-visualization.html` rather than re-deriving it.

### The Colab-chapter pattern (Ch 22-24, 26, 28)

PyTorch and HuggingFace `transformers` can't run in Pyodide (large compiled native libraries, no
WASM build). For these chapters, copy `dl/ch22-intro-to-pytorch.html`'s exact shell, not a normal
chapter's:
- A `.colab-banner` div near the top of the lesson (and again in the project section) linking to
  `https://colab.research.google.com/github/bosmany/AI-ML-Training/blob/main/<folder>/<slug>.ipynb`
  (the actual `.ipynb` files don't exist yet anywhere in this repo — that's a known gap, see below).
- Lesson code blocks have NO `▶ Run` button (just a "Colab / real Python — reference only" label).
- Practice exercises are graded by **pattern-matching the typed code** (`checkTextEx(n)`, checks
  matched against the student's code with all whitespace stripped and lowercased), not by
  executing it — copy this mechanism from ch22's script exactly.
- The Pyodide console at the bottom still loads (for light non-PyTorch snippets), but its status
  text should say PyTorch/transformers aren't available there.
- **Known gap:** no actual `.ipynb` notebook files have been created yet for any Colab chapter —
  the HTML pages link to notebook URLs that will 404 until those notebooks are authored and
  committed. This is real, deliberately-deferred work, not an oversight to "fix later and forget."

### The Interview Prep pattern (every module capstone: Ch 7, 10, 14, 20, 26, 30, 32)

A 5th tab/section alongside Lesson/Practice/Project/Quiz, not counted toward chapter XP/completion.
Copy verbatim from `mlops/ch32-mlops-fundamentals-capstone.html`:
- CSS: `.interview-section`, `.interview-intro`, `.iq-card`, `.iq-q`, `.iq-a`, `.iq-a-inner` (add
  right before the closing `</style>`).
- Sidebar: `<div class="sb-item" id="sb-interview" onclick="showSection('interview')">...` right
  after the `sb-quiz` item.
- Tab: `<div class="stab" id="tab-interview" onclick="showSection('interview')">💼 Interview Prep</div>`
  right after `tab-quiz`.
- A `<div class="interview-section" id="sec-interview">` with 10-12 real Q&A cards (click-to-expand
  via `onclick="this.classList.toggle('open')"`), placed right after `</div><!-- end quiz -->`.
- **JS: add `'interview'` to the array in `showSection(name){ ['lesson','practice','project','quiz','interview'].forEach(...) }`** — this is the one line every one of these five edits depends on, and it's easy to forget.
- ⚠️ **Insertion-point bug hit once already**: if you search-replace using an anchor that is
  *inside* the quiz section (e.g. the `next-chapter-card` block) rather than the literal
  `</div><!-- end quiz -->` line itself, you can end up creating a duplicate closing `</div>` and
  break div-balance. Always anchor on the exact `</div><!-- end quiz -->` comment line. (This
  happened once, in `data/ch14-data-visualization.html`, and was caught and fixed via the
  div-balance check — always re-run that check after adding an Interview Prep section.)

## Resuming this project

**The core 32-chapter curriculum is done, verified, and pushed.** What's left is entirely additive:

1. **Module 8: Production Projects** (`projects/ch33-...html` onward, folder not yet created) — the
   current plan (see `index.html`'s `mod8` array) is three portfolio-worthy end-to-end builds:
   - **Ch 33 — End-to-End ML Pipeline**: data → train → evaluate → deploy, tying Modules 3-4-7
     together into one real project (not a toy dataset).
   - **Ch 34 — Agentic AI System**: this is the big one the user explicitly asked for. Go beyond
     Ch 30's single-step simulated tool-calling toward a genuine multi-step agent LOOP: a planning
     step, tool selection, tool execution, observing the result, and deciding whether to continue
     or respond (the "ReAct" pattern — Reason+Act — is the standard reference point; ground the
     lesson in it explicitly). Same constraint as Ch 30: no real LLM call available in-browser, so
     simulate the "reasoning" step deterministically (e.g. keyword/state-machine-driven decisions)
     while being explicit in the lesson about where a real LLM call (`client.messages.create(...)`)
     would plug into each step. This chapter is the difference between "job-ready" and "portfolio
     standout" for agentic AI roles — don't shortcut it.
   - **Ch 35 — RAG Chatbot, Deployed**: combine Ch 30's RAG pattern with Ch 31's deployment
     patterns (FastAPI-shaped request handling, health checks) into one deployable service.
   - Each should probably ALSO get real, runnable `.ipynb` Colab notebooks (see next item) since
     "production project" implies actually running it somewhere real, more than the Colab-chapter
     pattern's usual "read the reference code" treatment.
   - No renumbering of Ch 1-32 needed — this is purely additive. Follow the same per-chapter
     process as everywhere else in this README (copy a template, verify every number via `py -3`,
     run the syntax/div/textarea checks, wire up `sb-back`/prereq/`next-chapter-card`, update
     `index.html`'s `mod8` array `avail:true` and this README's status table as each one ships).
2. **Author the Colab `.ipynb` notebooks** — every Colab-chapter HTML page (Ch 22-24, 26, 28, and
   whichever Module 8 projects need one) already links to a specific GitHub path
   (`https://colab.research.google.com/github/bosmany/AI-ML-Training/blob/main/<folder>/<slug>.ipynb`)
   but none of those notebook files exist in the repo yet — the badges currently 404. This is real,
   deliberately-deferred work, not an oversight.
3. **Re-run the full-repo verification sweep** (syntax/div/textarea-balance) and the cross-chapter
   link-chain check after adding Module 8 — both scripts are in "Quick verification commands used
   throughout" above; both passed cleanly across the full Ch 1-32 set as of this writing.
4. Numeric verification discipline continues to apply: every checker's expected value must come
   from actually running the exact solution code (this machine's Anaconda Python works via
   `py -3` after a one-time PATH fix for a DLL-loading quirk — search this file's own text/history
   for `Library/bin` if the exact command is needed again), never hand-calculated.

Tell whoever picks this up: **"Continue the AI/ML Zero to Hero course — the 32-chapter core curriculum is done and pushed; build Module 8: Production Projects next, per the plan in README.md's 'Resuming this project' section, prioritizing the Agentic AI chapter."**
