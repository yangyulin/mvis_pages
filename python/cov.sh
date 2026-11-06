#!/usr/bin/env bash
# Tests under coverage; fails unless every line and branch of mvis_site runs. The Playwright run() functions in browser/
# are excluded by their pragma (they need Chrome and a served build); the count of excluded lines is printed.
# PYTHONNOUSERSITE keeps ~/.local's numpy 2 and its broken pytest plugin out, but coverage lives there,
# so only the coverage package is linked into a temp dir on PYTHONPATH.
set -euo pipefail
cd "$(dirname "$0")"
cov=$(python3 -c "import coverage, os; print(os.path.dirname(coverage.__file__))")
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
ln -s "$cov" "$tmp/coverage"
run() { PYTHONNOUSERSITE=1 PYTHONPATH="$tmp" python3 -m coverage "$@"; }
run erase
run run -m pytest -q "$@" || { echo "tests failed"; exit 1; }
run report
run json -q -o "$tmp/cov.json"
python3 - "$tmp/cov.json" <<'PY'
import json, sys
t = json.load(open(sys.argv[1]))["totals"]
print(f"lines {t['covered_lines']}/{t['num_statements']} missing {t['missing_lines']}; "
      f"branches {t['covered_branches']}/{t['num_branches']} missing {t['missing_branches']}; "
      f"excluded by pragma {t['excluded_lines']} lines (Playwright drivers)")
sys.exit(1 if t["missing_lines"] or t["missing_branches"] else 0)
PY
