"""Sidebar check: sections, every link, every page reachable, current page shown open.

  python site/scripts/nav_check.py <base_url> <out_dir>

Exit code 1 if any check fails; findings are in <out_dir>/nav_report.json.
"""
import argparse

import _lib
from mvis_site.browser import nav

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("base", help="site root URL")
ap.add_argument("out", help="folder for nav_report.json")
a = ap.parse_args()
raise SystemExit(nav.run(a.base, a.out))
