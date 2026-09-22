#!/usr/bin/env python3
"""Check that the homepage names the recording that is playing, at every width.

The hero bar lists one chip per recording in rigs.json. With seven recordings the chips no
longer fitted the narrow column they used to live in, and nothing scrolled them, so from the
third recording on the highlighted name was faded out or off-screen for the whole cycle
(see mira docs/plans/mvis/web-pages/hero-rig-labels).

Rules checked, for every device profile and every recording:
  wide (>= 1100 px)  every chip fits without scrolling, so no name is ever cut
  narrow             selecting a recording brings its chip fully into view, clear of the fade

Also checked: no readout label or value is clipped by its column, in the bar and in the
phone Details block (three columns did not hold "3 cam · 4 IMU" below 400 px).

    python site/scripts/hero_labels_check.py http://127.0.0.1:8841
    python site/scripts/hero_labels_check.py https://openmvis.com
"""
import sys
from playwright.sync_api import sync_playwright

DEVICES = [
    ("phone-320", 320, 568), ("phone-360", 360, 740), ("phone-390", 390, 844),
    ("phone-430", 430, 932), ("tablet-834", 834, 1112),
    ("laptop-1280", 1280, 720), ("laptop-1440", 1440, 900),
    ("desktop-1920", 1920, 1080), ("desktop-2560", 2560, 1440),
]
FADE_PX = 36

MEASURE = """(i) => {
  const box = document.getElementById('mhChips');
  const chips = [...document.querySelectorAll('.mh-chip')];
  const a = chips[i];
  const b = box.getBoundingClientRect(), r = a.getBoundingClientRect();
  const over = box.scrollWidth > box.clientWidth + 2;
  const fade = (over && !box.classList.contains('at-end')) ? 36 : 0;
  const ro = [...document.querySelectorAll('.mh-ro div')]
    .filter(d => d.getBoundingClientRect().width > 0)
    .filter(d => { const dt = d.querySelector('dt'), dd = d.querySelector('dd');
                   return dt.scrollWidth > dt.clientWidth || dd.scrollWidth > dd.clientWidth; })
    .map(d => d.querySelector('dt').textContent.trim());
  return {name: a.textContent.trim(), pressed: a.getAttribute('aria-pressed') === 'true',
          scrolls: over, visible: r.left >= b.left - 1 && r.right <= b.right - fade + 1,
          hidden: Math.round(box.scrollWidth - box.clientWidth), clipped: ro};
}"""


def main() -> int:
    base = sys.argv[1].rstrip("/")
    bad = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        for name, w, h in DEVICES:
            page = browser.new_page(viewport={"width": w, "height": h})
            page.goto(base + "/", wait_until="load")
            page.wait_for_selector(".mh-chip")
            if w <= 640:                      # the phone readout continues inside Details
                page.evaluate("() => { const d = document.getElementById('mhMore'); if (d) d.open = true; }")
            page.wait_for_timeout(2000)
            n = page.locator(".mh-chip").count()
            problems, clipped, hidden, scrolls = [], set(), 0, False
            for i in range(n):
                # start from the left, then select like the cycle does (no focus scrolling)
                page.evaluate("() => { document.getElementById('mhChips').scrollLeft = 0; }")
                page.evaluate("(i) => document.querySelectorAll('.mh-chip')[i].click()", i)
                page.wait_for_timeout(900)
                r = page.evaluate(MEASURE, i)
                hidden, scrolls = r["hidden"], r["scrolls"]
                clipped.update(r["clipped"])
                if not r["pressed"] or not r["visible"]:
                    problems.append(r["name"])
            if w >= 1100 and scrolls:
                problems.append(f"chips need scrolling ({hidden} px hidden)")
            if clipped:
                problems.append("clipped readout: " + ", ".join(sorted(clipped)))
            status = "ok  " if not problems else "FAIL"
            bad += bool(problems)
            print(f"{status} {name:<14} {n} recordings, {'scroller' if scrolls else 'all fit'}"
                  f"{'' if not problems else '  ' + '; '.join(problems)}")
            page.close()
        browser.close()
    print(f"\n{len(DEVICES) - bad}/{len(DEVICES)} widths name every recording and fit their readout")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
