"""Write the UZH-FPV results table (site/src/data/leaderboard/uzh_fpv.json) with the leaderboard Space's renderer.

  PYTHONNOUSERSITE=1 python3 site/scripts/export_uzh.py --leaderboard <leaderboard Space checkout> \
      --uzh-root <openmvis checkout>/results/datacard/uzh_fpv [--hub-stage DIR] [--out FILE]
"""
import argparse
from pathlib import Path

import _lib
from mvis_site.env import require_numpy_1

require_numpy_1()
from mvis_site import space

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--leaderboard", type=Path, required=True, help="the Space folder (app.py, export_threeway.py)")
ap.add_argument("--uzh-root", type=Path, required=True, help="UZH study results: three_way/ and hub_stage/")
ap.add_argument("--hub-stage", type=Path, help="default: <uzh-root>/hub_stage/<leaderboard.BATCH>")
ap.add_argument("--out", type=Path, help="default: this checkout's site/src/data/leaderboard/uzh_fpv.json")
a = ap.parse_args()
x = lambda p: p and p.expanduser()
print("wrote", space.export_uzh_from_root(x(a.leaderboard), x(a.uzh_root), x(a.out), x(a.hub_stage)))
