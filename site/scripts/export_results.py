"""Write the Results pages' data: the Leaderboard rows, one Dataset eval page per dataset (JSON + its thin MDX) and
the Results sidebar (results-nav.json). Records are local (a snapshot of one batch); there is no Hub read.

  PYTHONNOUSERSITE=1 python3 site/scripts/export_results.py --leaderboard <Space folder> --records <results snapshot> \
      --stats <the batch's stats file> --batch <batch> --results-commit <full sha of the snapshot> --uzh-root <uzh study dir>

Run after export_board.py, export_uzh.py and export_repeatability.py of the same batch: it refuses when those files,
the records and the stats file are not one batch and one commit, when a ◆ count differs from the rendered board, and
when any output holds a path, a banned word, a recording name or a per-recording value. The stats file is private:
only min and max per row and tool leave it.
"""
import argparse
from pathlib import Path

import _lib
from mvis_site.env import require_numpy_1

require_numpy_1()
from mvis_site import results_eval as R

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--leaderboard", type=Path, required=True, help="the leaderboard Space folder (its app.py counts ◆)")
ap.add_argument("--records", type=Path, required=True, help="local results records of the batch (families.json, <tool>/<batch>/T*.json)")
ap.add_argument("--stats", type=Path, required=True, help="the stats file those records were exported from")
ap.add_argument("--batch", required=True)
ap.add_argument("--results-commit", required=True, help="the snapshot's full 40-hex sha")
ap.add_argument("--uzh-root", type=Path, required=True, help="the UZH-FPV study folder (three_way/ stats)")
ap.add_argument("--site", type=Path, default=_lib.REPO, help="the checkout to write into")
a = ap.parse_args()
x = lambda p: p.expanduser()
pages, pub, pairs, boards, private = R.collect(x(a.leaderboard), x(a.records), x(a.stats), a.batch, a.results_commit, x(a.uzh_root), x(a.site))
files = R.render(pages, pub, a.batch, a.results_commit, boards, pairs)
for p in R.write(files, x(a.site), a.results_commit, private):
    print("wrote", p)
