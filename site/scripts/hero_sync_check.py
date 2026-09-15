"""Homepage hero video-sync checks (Playwright + system Chrome).

  pip install playwright
  npx http-server docs -p 8080 -s          # any server with HTTP Range support (python -m http.server has none)
  python site/scripts/hero_sync_check.py http://127.0.0.1:8080/      # or https://openmvis.com/

The hero loop is the clock; camera views (laptop tiles, phone Details strip) must follow it. Suites, each
pinning a bug found in review (2026-09-14/15):
  pause     click / double-click pause-resume cycles with a slow-seek decoder (fixtures/slow_seek.js):
            views must not freeze (> 0.3 s) or drift (> 0.3 s) — the old code re-seeked every frame and froze
  handover  two recording hand-overs: no view may run ahead of a still-loading loop (> 0.3 s after 1.4 s)
  stall     one tile frozen mid-playback (fixtures/stall_tile.js) + one tile request aborted:
            the watchdog must bring both back in sync within 4 s
Exit code 1 if any check fails.
"""
from __future__ import annotations

import os
import statistics
import sys
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
FREEZE_MAX, DRIFT_MAX, RECOVER_MAX_S = 0.3, 0.3, 4.0

SAMPLE = """() => { const h = document.getElementById('mhVideo');
  const c = [...document.querySelectorAll('#mhTiles video, #mhStrip video')];
  return {rig: (document.querySelector('.mh-chip[aria-pressed=true]') || {dataset: {}}).dataset.rig, h: h.currentTime, hp: h.paused,
          c: c.map(v => ({cam: v.dataset.cam, t: v.currentTime, p: v.paused, err: !!v.error}))}; }"""


def context(p, browser, profile):
    if profile == "laptop":
        return browser.new_context(viewport={"width": 1366, "height": 712})
    return browser.new_context(**p.devices["iPhone 13"])


def bust(url, extra=""):
    return url + ("&" if "?" in url else "?") + f"t={int(time.time() * 1000)}" + extra


def suite_pause(p, browser, base, profile):
    ctx = context(p, browser, profile); page = ctx.new_page()
    page.add_init_script(path=os.path.join(FIX, "slow_seek.js"))
    page.goto(bust(base, "&keyint=1"), wait_until="load"); page.wait_for_timeout(2500)
    if profile == "phone":
        page.locator("#mhMore summary").click(); page.wait_for_timeout(1500)
    frame = page.locator("#mhFrame")
    worst_freeze = worst_drift = 0.0
    for kind, play_s, pause_s in [("click", 1.2, 1.0), ("dbl", 2.6, 0), ("click", 3.4, 1.6), ("dbl", 1.1, 0), ("click", 5.9, 0.8)]:
        page.wait_for_timeout(int(play_s * 1000))
        if kind == "dbl":
            frame.dblclick()
        else:
            frame.click(); page.wait_for_timeout(int(pause_s * 1000)); frame.click()
        rows = []
        for _ in range(40):
            rows.append(page.evaluate(SAMPLE)); page.wait_for_timeout(100)
        n = len(rows[0]["c"]); run = [0] * n; freeze = [0] * n
        for a, b in zip(rows[5:], rows[6:]):                        # allow 0.5 s to settle after the click
            if b["hp"] or b["h"] < a["h"] or len(b["c"]) != n or a["rig"] != b["rig"]:
                continue
            for k in range(n):
                run[k] = run[k] + 1 if b["c"][k]["t"] - a["c"][k]["t"] < 0.02 else 0
                freeze[k] = max(freeze[k], run[k])
                worst_drift = max(worst_drift, abs(b["c"][k]["t"] - b["h"]))
        worst_freeze = max([worst_freeze] + [f * 0.1 for f in freeze])
    ctx.close()
    ok = worst_freeze <= FREEZE_MAX and worst_drift <= DRIFT_MAX
    return ok, f"freeze {worst_freeze:.1f} s, drift {worst_drift:.2f} s"


def suite_handover(p, browser, base, profile):
    ctx = context(p, browser, profile); page = ctx.new_page()
    page.goto(bust(base), wait_until="load"); page.wait_for_timeout(1500)
    if profile == "phone":
        page.locator("#mhMore summary").click()
    bad = 0; last_rig = None; rig_i = 0
    for i in range(170):                                             # 34 s at 5 Hz: two hand-overs
        r = page.evaluate(SAMPLE)
        if r["rig"] != last_rig:
            last_rig, rig_i = r["rig"], i
        if r["c"] and i - rig_i > 7 and not r["hp"] and max(abs(c["t"] - r["h"]) for c in r["c"]) > DRIFT_MAX:
            bad += 1
        page.wait_for_timeout(200)
    ctx.close()
    return bad == 0, f"{bad} drifting samples after hand-overs"


def suite_stall(p, browser, base):
    ctx = context(p, browser, "laptop"); page = ctx.new_page()
    logs = []; page.on("console", lambda m: logs.append(m.text) if "openmvis hero" in m.text else None)
    aborted = {"n": 0}

    def route(r):
        if r.request.url.split("?")[0].endswith("_cam2.mp4") and "&r=" not in r.request.url and aborted["n"] == 0:
            aborted["n"] += 1
            return r.abort()
        return r.continue_()
    page.route("**/media/hero/*.mp4*", route)
    page.add_init_script(path=os.path.join(FIX, "stall_tile.js"))        # freezes cam1 after 6 s
    page.goto(bust(base), wait_until="load")
    back = {}
    for i in range(30):
        page.wait_for_timeout(500)
        r = page.evaluate(SAMPLE)
        for c in r["c"]:
            if c["cam"] in ("cam1", "cam2") and not r["hp"] and abs(c["t"] - r["h"]) < DRIFT_MAX and not c["err"]:
                if c["cam"] == "cam2" or (i + 1) * 0.5 > 6.5:
                    back.setdefault(c["cam"], (i + 1) * 0.5)
    ctx.close()
    cam2_ok = aborted["n"] == 1 and "cam2" in back and back["cam2"] <= RECOVER_MAX_S
    cam1_ok = "cam1" in back and back["cam1"] - 6.0 <= RECOVER_MAX_S
    return cam2_ok and cam1_ok, f"aborted tile back at {back.get('cam2')} s, frozen tile back at {back.get('cam1')} s (frozen at 6 s); log: {len(logs)} reloads"


def main():
    base = sys.argv[1]
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for name, fn in [("pause/laptop", lambda: suite_pause(p, browser, base, "laptop")),
                         ("pause/phone-details", lambda: suite_pause(p, browser, base, "phone")),
                         ("handover/laptop", lambda: suite_handover(p, browser, base, "laptop")),
                         ("handover/phone-details", lambda: suite_handover(p, browser, base, "phone")),
                         ("stall/laptop", lambda: suite_stall(p, browser, base))]:
            ok, msg = fn()
            results.append(ok)
            print(f"{'ok  ' if ok else 'FAIL'} {name:24s} {msg}", flush=True)
        browser.close()
    print(f"\n{sum(results)}/{len(results)} sync checks pass")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
