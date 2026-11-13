"""Homepage responsive check — device matrix screenshots + layout assertions.

  pip install playwright            # uses the system Chrome (channel="chrome"), no browser download
  python site/scripts/responsive_check.py <base_url> <out_dir> [--only phone|laptop|...]

Checks per device (the design note lives in the maintainers' plan, outside this repo):
  overflow   no horizontal page scroll
  first      phones/tablets: title, video and a primary call to action inside the first viewport
  fold       laptops/desktops: the whole hero including the readout bar inside the first viewport
  taps       phones: visible buttons/chips/links in the hero, and the primary CTA, are tall enough to tap
  video      the hero video box takes a minimum share of the viewport width
The limits are in mvis_site/checks.py (evaluate). With --pages it checks content pages instead (checks.page_problems).
Writes <out_dir>/<device>.png and <out_dir>/report.json; exit code 1 if any check fails.
"""
import argparse

import _lib
from mvis_site.browser import responsive

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("base", help="site root URL")
ap.add_argument("out", help="folder for the screenshots and report.json")
ap.add_argument("--only", help="one device name or class (phone, laptop, ...)")
ap.add_argument("--pages", help="comma-separated content pages (e.g. /benchmark/results/,/benchmark/results/tum-vi/): "
                "screenshots at 390 and 1360 px in light and dark, and no horizontal page scroll, in place of the homepage matrix")
a = ap.parse_args()
raise SystemExit(responsive.run_pages(a.base, a.out, a.pages.split(",")) if a.pages else responsive.run(a.base, a.out, a.only))
