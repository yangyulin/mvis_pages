"""Write the results tables (board.json, board.css) with the leaderboard Space's renderer.

  PYTHONNOUSERSITE=1 python3 site/scripts/export_board.py --leaderboard <leaderboard Space checkout> \
      [--records <results snapshot> [--results-commit <its full sha>]] [--out DIR]

Without --records it reads the current calibench-vi/results main, which changes the live tables.
"""
import argparse
from pathlib import Path

import _lib
from mvis_site.env import require_numpy_1

require_numpy_1()
from mvis_site import space

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--leaderboard", type=Path, required=True, help="the Space folder (app.py, export_threeway.py)")
ap.add_argument("--records", type=Path, help="local results records (CALIBENCH_LOCAL) instead of the Hub")
ap.add_argument("--results-commit", help="with --records: the snapshot's full 40-hex sha, reported and used in the config links")
ap.add_argument("--out", type=Path, help="default: this checkout's site/src/data/leaderboard")
a = ap.parse_args()
x = lambda p: p and p.expanduser()
print("wrote", *space.export_board(x(a.leaderboard), x(a.out), x(a.records), a.results_commit))
