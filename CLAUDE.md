# Repo rules for Claude

## Format
- Course = standalone HTML chapters. Python runs in-browser via Pyodide 0.26.4.
- Chapter shape: Lesson -> 5 exercises (EXERCISES[n]: solution, checks, optional checkFn) -> Mini project (runProject/checkProject + PROJECT_SOLUTION) -> Quiz (5 questions, 80% to pass).
- Copy structure, CSS classes and JavaScript from the sibling chapter in the same folder. Never invent layout.
- Starter code in <textarea id="exN-code"> must NOT pass its own checks.
- Code needing libraries Pyodide 0.26.4 cannot load uses the Colab pattern: reference code + matching .ipynb + checkTextEx grading (see dl/ch22-intro-to-pytorch.html).
- Data: sklearn bundled datasets (load_breast_cancer, load_diabetes, load_wine, load_digits) or small CSVs committed under assets/datasets/. No network calls in runnable lesson code.

## Writing
- Lesson style: problem first, analogy, runnable example, line-by-line explanation, real error + fix, check-yourself, recap. Core chapters: 8,000+ words.
- Every chapter ends its lesson with "Interview questions" containing 5 to 8 questions and answers.
- Keep existing correct content. Expand and upgrade it. Do not delete existing concepts.

## Workflow
Follow this workflow for every task:

1. Show a section outline and the proposed library and dataset choices.
2. WAIT for my approval before modifying files.
3. After I approve, write or update the chapter.
4. Verify only the chapter being changed using:
   node scripts/pyodide-grade.js --file <path>
   node scripts/verify-html.js
5. If a notebook changed, run:
   python3 scripts/check-notebooks.py <notebook>
6. Fix every failure before finishing.
7. Regenerate the chapter cheat sheet using:
   python3 scripts/build-cheatsheets.py --only chNN
8. If a new chapter or glossary term was added, run:
   python3 scripts/build-glossary.py
   python3 scripts/build-search-index.py
9. If a new chapter was added, update index.html MODULES and the previous/next links on neighbouring chapters.
10. Summarise what changed in exactly 5 concise lines.
11. Do not commit changes. I will inspect and commit them manually.

## Safety rules
- Never modify unrelated chapters or files.
- Never run the full test suite unless I explicitly request it.
- Never put API keys, tokens, passwords or credentials in source files.
- Read API keys from environment variables.
- Never replace working content merely to increase the word count.
- Do not claim that a command passed unless you actually ran it and saw a successful result.
- If a required library is unavailable in Pyodide, use the documented Colab pattern instead of pretending the code runs in the browser.
- If a referenced file, dataset, notebook, script or lab does not exist, report that clearly before continuing.
