"""Check that the homepage names the recording that is playing, at every width.

The hero bar lists one chip per recording in rigs.json. With seven recordings the chips no
longer fitted the narrow column they used to live in, and nothing scrolled them, so from the
third recording on the highlighted name was faded out or off-screen for the whole cycle
(the design note lives in the maintainers' plan, outside this repo).

Rules checked, for every device profile and every recording:
  wide (checks.WIDE_PX and up)  every chip fits without scrolling, so no name is ever cut
  narrow             selecting a recording brings its chip fully into view, clear of the fade

Also checked: no readout label or value is clipped by its column, in the bar and in the
phone Details block (three columns did not hold "3 cam · 4 IMU" below 400 px).

    python site/scripts/hero_labels_check.py http://127.0.0.1:8841
    python site/scripts/hero_labels_check.py https://openmvis.com
"""
import argparse

import _lib
from mvis_site.browser import hero_labels

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("base", help="site root URL")
raise SystemExit(hero_labels.run(ap.parse_args().base))
