"""Moved-page check on the built site: every old address in site/src/data/moved.json redirects straight to its new one,
no redirect chains, and every internal link on a real page resolves.

  python site/scripts/check_moves.py [docs_dir]

Run after npm run build. Exit code 1 if any check fails.
"""
import argparse
import json

import _lib
from mvis_site import SITE, checks

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("docs", nargs="?", default=str(_lib.REPO / "docs"), help="built site (default: this checkout's docs/)")
a = ap.parse_args()
problems = checks.check_moves(a.docs, json.loads((SITE / "src/data/moved.json").read_text(encoding="utf-8")))
print(f"{len(problems)} problems", *problems, sep="\n")
raise SystemExit(1 if problems else 0)
