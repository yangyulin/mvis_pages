"""Write repeatability.json: per family and group of parameters, which tool's estimates scatter less across the
recordings every compared tool ran. Records are always local (a snapshot of one batch); there is no Hub read.

  PYTHONNOUSERSITE=1 python3 site/scripts/export_repeatability.py --records <results snapshot> --stats <three_way_compare_stats.json> \
      --batch <batch> --results-commit <full sha of the snapshot> [--leaderboard <Space folder>] [--out FILE]

The stats file is private: only derived spreads leave it. The export refuses when the records are not exactly the
stats file's blocks (a stats file of another batch), and when the output holds a path, a banned word or a recording name.
"""
import argparse
from pathlib import Path

import _lib
from mvis_site.env import require_numpy_1

require_numpy_1()
from mvis_site import repeatability

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--records", type=Path, required=True, help="local results records of the batch (families.json, <tool>/<batch>/T*.json)")
ap.add_argument("--stats", type=Path, required=True, help="the three_way_compare_stats.json those records were exported from")
ap.add_argument("--batch", required=True)
ap.add_argument("--results-commit", required=True, help="the snapshot's full 40-hex sha")
ap.add_argument("--leaderboard", type=Path, help="the Space folder: its app.py GROUPS are checked against this module's")
ap.add_argument("--out", type=Path, default=_lib.REPO / "site/src/data/leaderboard/repeatability.json")
a = ap.parse_args()
x = lambda p: p and p.expanduser()
app = x(a.leaderboard) / "app.py" if a.leaderboard else None
print("wrote", repeatability.export(x(a.stats), x(a.records), a.batch, a.results_commit, x(a.out), app))
