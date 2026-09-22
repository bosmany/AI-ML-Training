## What changed

<!-- One or two sentences. Link the issue it fixes, if there is one. -->

## Checklist

Tick what applies. Leave a box unticked and say why rather than ticking it by habit.

### Accuracy
- [ ] Every technical claim I added or changed is correct (I checked it, not just wrote it).
- [ ] Definitions match the official docs or a standard reference, and numbers/thresholds are labelled as rules of thumb where they are.
- [ ] I did not add a claim of human review. The footer badge says "human review pending" until a person actually reviews the chapter.

### It runs
- [ ] Every code block I added or changed runs. For Pyodide chapters: `node scripts/pyodide-grade.js --file <page>` passes.
- [ ] `node scripts/verify-html.js` passes.
- [ ] I opened the page in a browser: no console errors, no horizontal scroll at 390px wide, readable in both light and dark themes.
- [ ] If I changed lesson text: rebuilt the generated files (`python3 scripts/build-glossary.py`, `build-cheatsheets.py`, `build-search-index.py`) and they are committed.

### Sources
- [ ] I list the sources for facts, figures and API behaviour below (official docs, papers, RFCs, version-pinned pages).
- [ ] Anything I could not verify is called out here instead of being stated as fact.

**Sources**

<!-- e.g. https://docs.python.org/3/library/functools.html#functools.wraps -->

**Not verified / open questions**

<!-- Optional. -->
