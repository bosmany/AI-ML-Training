#!/usr/bin/env bash
# Verify every lab honours the contract (CI entry point):
#   * solution tests must ALL pass
#   * starter tests must ALL fail (none may pass by accident)
# Usage:  labs/run_all.sh [lab-name ...]      (default: every labs/*/ directory that has a tests/ folder)
# Env:    VENV=/path/to/venv   create/use an isolated venv and pip-install each lab's requirements.txt
#                              (unset: use the current python, which must already have the dependencies)
#         PYTHON=python3.12    interpreter used to create the venv / run tests when VENV is unset
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python}"
export PYTHONDONTWRITEBYTECODE=1

if [ -n "${VENV:-}" ]; then
  [ -x "$VENV/bin/python" ] || "$PYTHON" -m venv "$VENV" || { echo "cannot create venv at $VENV" >&2; exit 2; }
  PY="$VENV/bin/python"
else
  PY="$PYTHON"
fi

if [ "$#" -gt 0 ]; then
  labs=("$@")
else
  labs=()
  for d in "$HERE"/*/; do
    [ -d "$d/tests" ] && labs+=("$(basename "$d")")
  done
fi

violations=0
rows=()

summary_line() { grep -E '[0-9]+ (passed|failed|error)' | tail -n 1; }
count_of() { grep -oE "[0-9]+ $2" <<<"$1" | head -n 1 | grep -oE '[0-9]+' || echo 0; }

for lab in "${labs[@]}"; do
  dir="$HERE/$lab"
  if [ ! -d "$dir/tests" ]; then
    rows+=("$lab|missing|missing|FAIL (no such lab)")
    violations=$((violations + 1))
    continue
  fi
  if [ -n "${VENV:-}" ] && [ -f "$dir/requirements.txt" ]; then
    "$PY" -m pip install -q -r "$dir/requirements.txt" >/dev/null 2>&1 || echo "warning: pip install failed for $lab" >&2
  fi

  sol_out="$(cd "$dir" && LAB_TARGET=solution "$PY" -m pytest -q -p no:cacheprovider 2>&1)"; sol_rc=$?
  sta_out="$(cd "$dir" && LAB_TARGET=starter "$PY" -m pytest -q -p no:cacheprovider 2>&1)"; sta_rc=$?
  sol_sum="$(summary_line <<<"$sol_out")"; sta_sum="$(summary_line <<<"$sta_out")"

  verdict="ok"
  if [ "$sol_rc" -ne 0 ]; then verdict="FAIL (solution tests do not all pass)"; fi
  sta_passed="$(count_of "$sta_sum" passed)"
  if [ "$sta_rc" -eq 0 ] || [ "$sta_passed" -gt 0 ]; then
    verdict="FAIL (starter has passing tests: $sta_passed)"
  elif [ "$sta_rc" -ne 1 ]; then
    verdict="FAIL (starter did not run cleanly, pytest exit $sta_rc)"
  fi
  [ "$verdict" != "ok" ] && violations=$((violations + 1))
  rows+=("$lab|${sol_sum:-no result}|${sta_sum:-no result}|$verdict")
  if [ "$verdict" != "ok" ]; then
    echo "----- $lab: solution output (tail) -----"; tail -n 15 <<<"$sol_out"
    echo "----- $lab: starter output (tail) -----";  tail -n 8 <<<"$sta_out"
  fi
done

echo
printf '%-28s | %-30s | %-30s | %s\n' "LAB" "SOLUTION (must all pass)" "STARTER (must all fail)" "RESULT"
printf '%-28s-+-%-30s-+-%-30s-+-%s\n' "----------------------------" "------------------------------" "------------------------------" "------"
for r in "${rows[@]}"; do
  IFS='|' read -r a b c d <<<"$r"
  printf '%-28s | %-30s | %-30s | %s\n' "$a" "$b" "$c" "$d"
done
echo
if [ "$violations" -gt 0 ]; then
  echo "$violations lab(s) violate the contract"
  exit 1
fi
echo "all ${#labs[@]} lab(s) satisfy the contract"
