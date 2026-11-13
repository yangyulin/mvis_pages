"""Write the example pages' data, media and MDX, the Examples overview and its sidebar entries into a site checkout.

  PYTHONNOUSERSITE=1 python3 site/scripts/export_examples.py --private-config <maintainers' sensors.yaml> [--site <checkout>]

Examples whose run has no views yet are written without player, map and result; the script lists them. Run it on a
worktree, never on a checkout you will push to main without review.
"""
import argparse
from pathlib import Path

import _lib
from mvis_site.env import require_numpy_1

require_numpy_1()
from mvis_site import export_examples

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--private-config", type=Path, required=True, help="the maintainers' sensors.yaml (a private config outside this repo): roots and its examples: run map")
ap.add_argument("--site", type=Path, default=_lib.REPO, help="site checkout to write into (default: this one)")
a = ap.parse_args()
site = a.site.expanduser()
print("exported", export_examples.main(site, a.private_config.expanduser()))
for slug, what in export_examples.pending(site).items():
    print(f"waiting for a solve: {slug} ({', '.join(what)})")
