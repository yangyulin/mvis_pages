"""Write overall.json for the Overall tab: tier values, head to head, derived total and reader presets, from the
rubric (python/data/rubric_v1.yaml) and the batch's repeatability.json.

  PYTHONNOUSERSITE=1 python3 site/scripts/export_overall.py [--repeatability FILE] [--rubric FILE] [--out FILE]

Run it after export_repeatability.py on the same batch. The export refuses rating words and internal paths.
"""
import argparse
from pathlib import Path

import _lib
from mvis_site import overall

DATA = _lib.REPO / "site/src/data/leaderboard"
ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--repeatability", type=Path, default=DATA / "repeatability.json")
ap.add_argument("--rubric", type=Path, default=overall.RUBRIC)
ap.add_argument("--out", type=Path, default=DATA / "overall.json")
a = ap.parse_args()
print("wrote", overall.export(a.repeatability.expanduser(), a.out.expanduser(), a.rubric.expanduser()))
