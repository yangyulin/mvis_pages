"""Homepage hero video-sync suites in Chrome; the statistics are checks.pause_round, handover_bad and stall_back."""
from __future__ import annotations

import os
import time

from .. import SITE, checks

FIX = str(SITE / "scripts/fixtures")
SAMPLE = """() => { const h = document.getElementById('mhVideo');
  const c = [...document.querySelectorAll('#mhTiles video, #mhStrip video')];
  return {rig: (document.querySelector('.mh-chip[aria-pressed=true]') || {dataset: {}}).dataset.rig, h: h.currentTime, hp: h.paused,
          c: c.map(v => ({cam: v.dataset.cam, t: v.currentTime, p: v.paused, err: !!v.error}))}; }"""


def context(p, browser, profile):  # pragma: no cover - drives Chrome through Playwright; run against a served build
    if profile == "laptop":
        return browser.new_context(viewport={"width": 1366, "height": 712})
    return browser.new_context(**p.devices["iPhone 13"])


def bust(url, extra=""):
    return url + ("&" if "?" in url else "?") + f"t={int(time.time() * 1000)}" + extra


def suite_pause(p, browser, base, profile):  # pragma: no cover - drives Chrome through Playwright; run against a served build
    ctx = context(p, browser, profile)
    page = ctx.new_page()
    page.add_init_script(path=os.path.join(FIX, "slow_seek.js"))
    page.goto(bust(base, "&keyint=1"), wait_until="load")
    page.wait_for_timeout(2500)
    if profile == "phone":
        page.locator("#mhMore summary").click()
        page.wait_for_timeout(1500)
    frame = page.locator("#mhFrame")
    worst_freeze = worst_drift = 0.0
    for kind, play_s, pause_s in [("click", 1.2, 1.0), ("dbl", 2.6, 0), ("click", 3.4, 1.6), ("dbl", 1.1, 0), ("click", 5.9, 0.8)]:
        page.wait_for_timeout(int(play_s * 1000))
        if kind == "dbl":
            frame.dblclick()
        else:
            frame.click()
            page.wait_for_timeout(int(pause_s * 1000))
            frame.click()
        rows = []
        for _ in range(40):
            rows.append(page.evaluate(SAMPLE))
            page.wait_for_timeout(100)
        f, d = checks.pause_round(rows)
        worst_freeze, worst_drift = max(worst_freeze, f), max(worst_drift, d)
    ctx.close()
    return checks.pause_verdict(worst_freeze, worst_drift)


def suite_handover(p, browser, base, profile):  # pragma: no cover - drives Chrome through Playwright; run against a served build
    ctx = context(p, browser, profile)
    page = ctx.new_page()
    page.goto(bust(base), wait_until="load")
    page.wait_for_timeout(1500)
    if profile == "phone":
        page.locator("#mhMore summary").click()
    samples = []
    for _ in range(170):  # 34 s at 5 Hz: two hand-overs
        samples.append(page.evaluate(SAMPLE))
        page.wait_for_timeout(200)
    ctx.close()
    bad = checks.handover_bad(samples)
    return bad == 0, f"{bad} drifting samples after hand-overs"


def suite_stall(p, browser, base):  # pragma: no cover - drives Chrome through Playwright; run against a served build
    ctx = context(p, browser, "laptop")
    page = ctx.new_page()
    logs = []
    page.on("console", lambda m: logs.append(m.text) if "openmvis hero" in m.text else None)
    aborted = {"n": 0}

    def route(r):
        if r.request.url.split("?")[0].endswith("_cam2.mp4") and "&r=" not in r.request.url and aborted["n"] == 0:
            aborted["n"] += 1
            return r.abort()
        return r.continue_()
    page.route("**/media/hero/*.mp4*", route)
    page.add_init_script(path=os.path.join(FIX, "stall_tile.js"))  # freezes cam1 after 6 s
    page.goto(bust(base), wait_until="load")
    samples = []
    for _ in range(30):
        page.wait_for_timeout(500)
        samples.append(page.evaluate(SAMPLE))
    ctx.close()
    back = checks.stall_back(samples)
    return checks.stall_verdict(aborted["n"], back), f"aborted tile back at {back.get('cam2')} s, frozen tile back at {back.get('cam1')} s (frozen at 6 s); log: {len(logs)} reloads"


def run(base: str) -> int:  # pragma: no cover - drives Chrome through Playwright; run against a served build
    from playwright.sync_api import sync_playwright
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
            print(checks.sync_line(name, ok, msg), flush=True)
        browser.close()
    print(checks.sync_summary(results))
    return 0 if all(results) else 1
