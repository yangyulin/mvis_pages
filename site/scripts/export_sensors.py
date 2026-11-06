"""Write the sensor pages' data, media and MDX into a site checkout.

  PYTHONNOUSERSITE=1 python3 site/scripts/export_sensors.py --private-config <mira sensors.yaml> --media <clips dir> [--site <checkout>] [--only <slug>]

Run it on a worktree, never on a checkout you will push to main without review.
"""
import argparse
from pathlib import Path

import _lib
from mvis_site.env import require_numpy_1

require_numpy_1()
from mvis_site import export_sensors

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--private-config", type=Path, required=True, help="mira's sensors.yaml: roots and runs; only its solve slice is read")
ap.add_argument("--media", type=Path, required=True, help="folder with the <name>.mp4 / .jpg demo clips")
ap.add_argument("--site", type=Path, default=_lib.REPO, help="site checkout to write into (default: this one)")
ap.add_argument("--only", metavar="SLUG", help="export just this sensor (sidebar and overview still list all); for a machine without the others' results")
a = ap.parse_args()
print("exported", export_sensors.main(a.site.expanduser(), a.private_config.expanduser(), a.media.expanduser(), a.only))
