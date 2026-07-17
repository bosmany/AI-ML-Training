# AI/ML: Zero to Hero

An interactive, self-contained, browser-based course that takes someone from zero programming knowledge to a working AI/ML skillset — Python fundamentals, math, data tools, classical ML, deep learning, NLP/LLMs, and MLOps deployment.

Every chapter is a single standalone `.html` file: open it in a browser (double-click, or host it anywhere) and it runs real Python **in the browser** via [Pyodide](https://pyodide.org/) (actual CPython + NumPy/Pandas compiled to WebAssembly) — no server, no install. Each chapter follows the same shape: **Lesson → 5 auto-graded Practice exercises → a Mini Project → a Quiz** (80% to unlock the next chapter). Progress is saved per-browser via `localStorage`.

## Status: ~30 of 32 core chapters written, verification/integration pass still needed (Modules 1-7 drafted)

The course was expanded from 30 to 32 chapters partway through Module 1 (see renumbering note
below), and then expanded AGAIN mid-build with two more asks: **Interview Prep** tabs on every
module capstone, and a bonus **Module 8: Production Projects** appended after Ch 32 (no
renumbering — Module 8 lives in a new `projects/` folder, chapters 33+).

| # | Chapter | File | Status |
|---|---------|------|--------|
| 1 | Python Basics | `python/ch01-python-basics.html` | ✅ Done, committed |
| 2 | Control Flow | `python/ch02-control-flow.html` | ✅ Done, committed |
| 3 | Functions & Modules | `python/ch03-functions-modules.html` | ✅ Done, committed |
| 4 | Data Structures | `python/ch04-data-structures.html` | ✅ Done, committed |
| 5 | OOP, Files & Errors | `python/ch05-oop-files-errors.html` | ✅ Done, committed |
| 6 | Professional Python | `python/ch06-professional-python.html` | ✅ Done, committed |
| 7 | Python for DevOps & APIs *(Module 1 capstone + Interview Prep)* | `python/ch07-python-devops-apis.html` | ✅ Done, **uncommitted local edit** (Interview Prep tab added) |
| 8 | Linear Algebra for ML | `math/ch08-linear-algebra.html` | ✅ Done, committed |
| 9 | Probability & Statistics | `math/ch09-probability-statistics.html` | ✅ Done, committed |
| 10 | Calculus & Optimization *(Module 2 capstone + Interview Prep)* | `math/ch10-calculus-optimization.html` | ✅ Done, **uncommitted local edit** (Interview Prep tab added) |
| 11 | NumPy Deep Dive | `data/ch11-numpy-deep-dive.html` | ✅ Done, committed |
| 12 | Pandas Fundamentals | `data/ch12-pandas-fundamentals.html` | ✅ Done, committed |
| 13 | Data Cleaning & Wrangling | `data/ch13-data-cleaning-wrangling.html` | ✅ Done, committed |
| 14 | Data Visualization *(Module 3 capstone + Interview Prep)* | `data/ch14-data-visualization.html` | ✅ Done, **uncommitted local edit** (Interview Prep tab added) |
| 15 | ML Foundations & Workflow | `ml/ch15-ml-foundations-workflow.html` | ✅ Done, committed |
| 16 | Linear & Logistic Regression | `ml/ch16-linear-logistic-regression.html` | ✅ Done, committed |
| 17 | Trees, Forests & Ensembles | `ml/ch17-trees-forests-ensembles.html` | ✅ Done, committed |
| 18 | Clustering & Dimensionality Reduction | `ml/ch18-clustering-dimensionality-reduction.html` | ✅ Done, committed |
| 19 | Feature Engineering & Model Selection | `ml/ch19-feature-engineering-model-selection.html` | ✅ Done, **NOT YET committed** |
| 20 | Classical ML Capstone *(Module 4 capstone + Interview Prep)* | `ml/ch20-classical-ml-capstone.html` | ✅ Done, **NOT YET committed** |
| 21 | Neural Network Fundamentals (in-browser NumPy backprop) | `dl/ch21-neural-network-fundamentals.html` | ✅ Done, committed |
| 22 | Intro to PyTorch *(Colab chapter)* | `dl/ch22-intro-to-pytorch.html` | ✅ Done, committed |
| 23 | Convolutional Neural Networks *(Colab chapter)* | `dl/ch23-convolutional-neural-networks.html` | ✅ Done, committed |
| 24 | RNNs & LSTMs *(Colab chapter)* | `dl/ch24-rnns-lstms.html` | ✅ Done, **NOT YET committed** |
| 25 | Transformers Explained (in-browser attention from scratch) | `dl/ch25-transformers-explained.html` | ✅ Done, committed |
| 26 | Deep Learning Capstone *(Colab chapter, Module 5 capstone)* | `dl/ch26-deep-learning-capstone.html` | ✅ Done, **NOT YET committed** |
| 27 | NLP Fundamentals | `nlp/ch27-nlp-fundamentals.html` | ✅ Done, **NOT YET committed** |
| 28 | Modern NLP with Transformers *(Colab chapter)* | `nlp/ch28-modern-nlp-transformers.html` | ✅ Done, **NOT YET committed** |
| 29 | How LLMs Actually Work (in-browser) | `nlp/ch29-how-llms-work.html` | ✅ Done, **NOT YET committed** — **NOT YET reviewed by the orchestrating session either**, was written by a background agent right before this checkpoint |
| 30 | Building with LLM APIs *(Module 6 capstone, hybrid Colab/runnable + Interview Prep)* | `nlp/ch30-building-with-llm-apis-capstone.html` | ⬜ **NOT YET BUILT** — a background agent was actively working on this when this checkpoint was written |
| 31 | Model Deployment | `mlops/ch31-model-deployment.html` | ✅ Done, **NOT YET committed** |
| 32 | MLOps Fundamentals *(core-curriculum capstone + Interview Prep)* | `mlops/ch32-mlops-fundamentals-capstone.html` | ✅ Done, **NOT YET committed** |
| 33+ | Module 8: Production Projects (2-3 end-to-end builds, e.g. deployed ML API, RAG/LLM app) | `projects/` | ⬜ **NOT YET BUILT** |

Open `index.html` at the repo root to see the full course map and live per-chapter progress (reads from `localStorage`, key `aimlZTH_progress_v1`) — **NOTE: `index.html`'s `MODULES` object and this README's status table both still reflect the OLD 14-chapter state as of the last commit; they have not been updated for Ch 15-32 yet.** That update, plus a final full-repo verification sweep, is the very next thing to do — see "Resuming this project" at the bottom.

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

## Resuming this project — READ THIS FIRST, do these in order

This checkpoint was written in a hurry (approaching a context/token limit) with several
background agents mid-flight, so the state is messier than usual. In order:

1. **Check on the two things that may still be running or may have failed**: at checkpoint time,
   a background agent was actively writing `nlp/ch30-building-with-llm-apis-capstone.html` (the
   Module 6 capstone, which also needs an Interview Prep tab per the pattern above), and
   `nlp/ch29-how-llms-work.html` had just been written but **not yet content-reviewed** by the
   orchestrating session. Read ch29 in full before trusting it — confirm its bigram
   character-level language model example actually produces the exact deterministic output its
   checkers claim (re-run the solution code through `py -3`, see verification note below), and
   confirm ch30 exists, is complete (not mid-write/truncated), and has the Interview Prep tab.
2. **Run the full-repo verification sweep** (all `.html` files, not just the new ones):
   ```bash
   node -e "
   const fs=require('fs');
   const path=require('path');
   function walk(dir){
     let out=[];
     for(const f of fs.readdirSync(dir)){
       const p=path.join(dir,f);
       if(fs.statSync(p).isDirectory()) out=out.concat(walk(p));
       else if(f.endsWith('.html')) out.push(p);
     }
     return out;
   }
   const files=walk('.');
   let anyFail=false;
   files.forEach(f=>{
     const html=fs.readFileSync(f,'utf8');
     const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
     let jsOk=true;
     scripts.forEach((s)=>{ try{ new Function(s); } catch(e){ jsOk=false; console.log(f,'SYNTAX ERROR:', e.message); } });
     const openDiv=(html.match(/<div/g)||[]).length, closeDiv=(html.match(/<\/div>/g)||[]).length;
     const openTa=(html.match(/<textarea/g)||[]).length, closeTa=(html.match(/<\/textarea>/g)||[]).length;
     if(!jsOk || openDiv!==closeDiv || openTa!==closeTa){ anyFail=true; console.log(f,'div',openDiv,closeDiv,'textarea',openTa,closeTa); }
   });
   console.log(anyFail?'SOME FILES HAVE ISSUES':'ALL '+files.length+' FILES OK');
   "
   ```
   Fix anything that fails before proceeding.
3. **Re-verify the full cross-chapter link chain** (this passed cleanly once already, at the point
   Ch 1-27 existed — re-run after Ch 28-32 are confirmed, to make sure nothing regressed):
   ```bash
   node -e "
   const fs=require('fs'); const path=require('path');
   function walk(dir){ let out=[]; for(const f of fs.readdirSync(dir)){ const p=path.join(dir,f); if(fs.statSync(p).isDirectory()) out=out.concat(walk(p)); else if(f.endsWith('.html')&&f!=='index.html') out.push(p); } return out; }
   walk('.').sort().forEach(f=>{
     const html=fs.readFileSync(f,'utf8');
     const chId=(html.match(/CH_ID='(ch\d+)'/)||[])[1];
     const sbBack=(html.match(/class=\"sb-back\" href=\"([^\"]+)\"/)||[])[1];
     const prereq=(html.match(/store\.chapters\['(ch\d+)'\]/)||[])[1];
     const nccHref=(html.match(/class=\"ncc-btn\" href=\"([^\"]+)\"/)||[])[1];
     console.log(f.padEnd(55),'ID='+chId,'back='+sbBack,'prereq='+prereq,'next='+nccHref);
   });
   "
   ```
   Every row's `back`/`prereq` should point to the PREVIOUS chapter, and its `next` to the NEXT —
   read down the list and confirm the chain has no gaps or mismatches.
4. **Spot-check content quality**, not just structure, on anything you didn't personally write —
   read at least the lesson-intro + one exercise of each background-agent-produced chapter
   (`ml/ch15-20`, `dl/ch23`, `dl/ch24`, `dl/ch26`, and all of `nlp/`) before trusting it. This was
   done for `ml/ch17` and found genuinely good (clear pedagogy, verified numbers, honest framing
   of a noisy-features example) — but that was only ONE spot-check across ~15 agent-written files.
5. **Numeric verification**: every checker in every chapter should have been verified by actually
   running its exact solution code through `py -3` (works via the Anaconda Python on this machine
   with a DLL PATH fix — see the exact `export PATH=...` line used throughout this build, findable
   by searching this repo's git history / prior session transcripts for
   `Library/bin:.../Library/mingw-w64/bin`). If you find a checker whose value looks hand-waved
   rather than run, re-verify it before trusting it — this project has a documented history of
   exactly that mistake shipping broken.
6. **Update `index.html`'s `MODULES` object** to add `mod4`-`mod8` (mirroring the existing
   `mod1`-`mod3` pattern) with every chapter 15-32+ and `avail:true` once verified, and flip the
   overall chapter count / lede text from "32" to whatever the final count is once Module 8 exists.
7. **Update this README's status table** (above) to remove all the "uncommitted"/"NOT YET"
   caveats once everything is committed and verified.
8. **Build Module 8: Production Projects** (`projects/ch33-...html` onward) — 2-3 substantial,
   portfolio-worthy end-to-end builds (e.g. a deployed ML API end-to-end, a RAG/LLM application).
   Not yet started. No renumbering of Ch 1-32 needed — this is purely additive.
9. **Author the missing Colab `.ipynb` notebooks** for Ch 22-24, 26, 28 (and whatever Module 8
   projects need one) — every Colab-chapter HTML page already links to a specific GitHub path;
   those files need to actually exist and be pushed for the Colab badges to work.
10. **Commit and push everything**, in reasonably-sized logical chunks (e.g. "Module 6 NLP
    complete", "Module 7 MLOps complete", "Interview Prep sections added to all capstones",
    "index.html + README final update") rather than one giant commit — easier to review and to
    bisect later if something's wrong.

Tell whoever picks this up: **"Continue the AI/ML Zero to Hero course by following the 10 steps at the top of 'Resuming this project' in README.md, in order — start with checking on Ch 29-30's status since a background agent was mid-write on those when the last session ended."**
