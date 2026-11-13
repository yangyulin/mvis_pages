"""Validate the homepage hero media against what HomeHero.astro loads.

  python site/scripts/check_hero_media.py [site/public/media/hero]

rigs.json (written by the maintainers' hero-media build script) must list, for every recording,
files the page will request, and those files must be playable in sync: the files and fields each recording needs,
one frame count per rig (they share one clock), the sizes, keyframe spacing (sparse keyframes froze companion seeks
on phones) and the phone first-load budget. The rules and limits are in mvis_site/checks.py (check_hero_media).
Exit code 1 on any violation.
"""
import argparse
from pathlib import Path

import _lib
from mvis_site.browser import media_probe

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("media", nargs="?", type=Path, default=media_probe.DEFAULT, help="the hero media folder (default: site/public/media/hero)")
raise SystemExit(media_probe.run(ap.parse_args().media))
