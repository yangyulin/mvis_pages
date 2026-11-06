"""Homepage responsive check — device matrix screenshots + layout assertions.

  pip install playwright            # uses the system Chrome (channel="chrome"), no browser download
  python site/scripts/responsive_check.py <base_url> <out_dir> [--only phone|laptop|...]

Checks per device (see docs/plans/mvis/web-pages/homepage-responsive in mira):
  overflow   no horizontal page scroll
  first      phones/tablets: title, video and a primary call to action inside the first viewport
  fold       laptops/desktops: the whole hero including the readout bar inside the first viewport
  taps       phones: visible buttons/chips/links in the hero, and the primary CTA, are tall enough to tap
  video      the hero video box takes a minimum share of the viewport width
The limits are in mvis_site/checks.py (evaluate).
Writes <out_dir>/<device>.png and <out_dir>/report.json; exit code 1 if any check fails.
"""
import argparse

import _lib
from mvis_site.browser import responsive

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("base", help="site root URL")
ap.add_argument("out", help="folder for the screenshots and report.json")
ap.add_argument("--only", help="one device name or class (phone, laptop, ...)")
a = ap.parse_args()
raise SystemExit(responsive.run(a.base, a.out, a.only))
