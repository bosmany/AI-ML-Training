// Structural verification for every .html file in the repo:
// - JS syntax check on each inline <script> block
// - <div>/</div> balance
// - <textarea>/</textarea> balance
// Run locally with: node scripts/verify-html.js
// Runs automatically on every push/PR via .github/workflows/verify.yml

const fs = require('fs');
const path = require('path');

const SKIP_DIRS = new Set(['.git', 'node_modules', '.github']);

function walk(dir, results) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP_DIRS.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full, results);
    } else if (entry.name.endsWith('.html')) {
      results.push(full);
    }
  }
  return results;
}

const files = walk('.', []).sort();
let failedCount = 0;

for (const file of files) {
  const html = fs.readFileSync(file, 'utf8');
  const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);

  let jsOk = true;
  const jsErrors = [];
  for (const s of scripts) {
    try {
      new Function(s);
    } catch (e) {
      jsOk = false;
      jsErrors.push(e.message);
    }
  }

  const openDiv = (html.match(/<div/g) || []).length;
  const closeDiv = (html.match(/<\/div>/g) || []).length;
  const openTa = (html.match(/<textarea/g) || []).length;
  const closeTa = (html.match(/<\/textarea>/g) || []).length;

  const divOk = openDiv === closeDiv;
  const taOk = openTa === closeTa;

  if (!jsOk || !divOk || !taOk) {
    failedCount++;
    console.error(`FAIL: ${file}`);
    jsErrors.forEach((msg) => console.error(`  JS syntax error: ${msg}`));
    if (!divOk) console.error(`  div mismatch: open=${openDiv} close=${closeDiv}`);
    if (!taOk) console.error(`  textarea mismatch: open=${openTa} close=${closeTa}`);
  } else {
    console.log(`OK:   ${file}`);
  }
}

console.log('');
if (failedCount > 0) {
  console.error(`Verification FAILED: ${failedCount}/${files.length} files have syntax errors or unbalanced tags.`);
  process.exit(1);
} else {
  console.log(`Verification passed: all ${files.length} HTML files OK.`);
}
