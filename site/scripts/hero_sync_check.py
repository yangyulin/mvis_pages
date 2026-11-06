"""Homepage hero video-sync checks (Playwright + system Chrome).

  pip install playwright
  npx http-server docs -p 8080 -s          # any server with HTTP Range support (python -m http.server has none)
  python site/scripts/hero_sync_check.py http://127.0.0.1:8080/      # or https://openmvis.com/

The hero loop is the clock; camera views (laptop tiles, phone Details strip) must follow it. Suites, each
pinning a bug found in review (2026-09-14/15):
  pause     click / double-click pause-resume cycles with a slow-seek decoder (fixtures/slow_seek.js):
            views must neither freeze nor drift — the old code re-seeked every frame and froze
  handover  two recording hand-overs: no view may run ahead of a still-loading loop
  stall     one tile frozen mid-playback (fixtures/stall_tile.js) + one tile request aborted:
            the watchdog must bring both back in sync
The limits are in mvis_site/checks.py (FREEZE_MAX, DRIFT_MAX, RECOVER_MAX_S; handover settle in handover_bad).
Exit code 1 if any check fails.
"""
import argparse

import _lib
from mvis_site.browser import hero_sync

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("base", help="site root URL, served with HTTP Range support")
raise SystemExit(hero_sync.run(ap.parse_args().base))
