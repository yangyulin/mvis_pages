"""Homepage responsive check — device matrix screenshots + layout assertions.

  pip install playwright            # uses the system Chrome (channel="chrome"), no browser download
  python site/scripts/responsive_check.py <base_url> <out_dir> [--only phone|laptop|...]

Checks per device (see docs/plans/mvis/web-pages/homepage-responsive in mira):
  overflow   no horizontal page scroll
  first      phones/tablets: title, video and a primary call to action inside the first viewport
  fold       laptops/desktops: the whole hero including the readout bar inside the first viewport
  taps       phones: visible buttons/chips/links in the hero are at least 40 px tall (primary CTA 44 px)
  video      the hero video box is at least 40 % of the viewport width on phones, 30 % elsewhere
Writes <out_dir>/<device>.png and <out_dir>/report.json; exit code 1 if any check fails.
"""
from __future__ import annotations

import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

DEVICES = [  # name, class, viewport, dpr, mobile
    ("iphone-se", "phone", (375, 553), 2, True),
    ("iphone-13", "phone", (390, 664), 3, True),
    ("pixel-7", "phone", (412, 839), 2.625, True),
    ("iphone-13-landscape", "phone-land", (750, 342), 3, True),
    ("ipad-mini", "tablet", (768, 1024), 2, True),
    ("ipad-air-landscape", "tablet", (1180, 820), 2, True),
    ("laptop-1280x720", "laptop", (1280, 664), 1, False),
    ("laptop-1366x768", "laptop", (1366, 712), 1, False),
    ("laptop-1440x900", "laptop", (1440, 844), 2, False),
    ("laptop-1536x864", "laptop", (1536, 808), 1.25, False),
    ("desktop-1920x1080", "desktop", (1920, 1024), 1, False),
    ("desktop-2560x1440", "desktop", (2560, 1384), 1, False),
]
# laptop/desktop viewports subtract ~56 px of browser chrome from the nominal screen height

MEASURE = r"""
() => {
  const vis = (el) => { if (!el) return false; const s = getComputedStyle(el); const r = el.getBoundingClientRect();
                        return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
  const rect = (el) => { const r = el.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height, bottom: r.bottom, right: r.right}; };
  const pick = (sels) => { for (const s of sels) { for (const el of document.querySelectorAll(s)) if (vis(el)) return el; } return null; };
  const hero = pick(['.mh']); const title = pick(['.mh h1']);
  const video = pick(['.mh-frame', '.mh-video']); const bar = pick(['.mh-bar', '.mh-readout']);
  const cta = pick(['.mh-cta-phone .mh-primary', '.mh-actions .mh-primary', '.mh-primary']);
  const taps = [...document.querySelectorAll('.mh a, .mh button, .mh summary')].filter(vis)
                 .map(el => ({t: (el.textContent || '').trim().slice(0, 24), h: el.getBoundingClientRect().height}));
  return {
    vw: innerWidth, vh: innerHeight, scrollW: document.documentElement.scrollWidth,
    hero: hero && rect(hero), title: title && rect(title), video: video && rect(video),
    bar: bar && rect(bar), cta: cta && rect(cta), taps,
  };
}
"""


def evaluate(cls, m):
    res = {}
    res["overflow"] = m["scrollW"] <= m["vw"] + 1
    vh, vw = m["vh"], m["vw"]
    if cls in ("phone", "tablet", "phone-land"):
        ok = all(m.get(k) and m[k]["bottom"] <= vh + 1 for k in ("title", "video", "cta"))
        res["first"] = ok
    else:
        res["fold"] = bool(m.get("bar")) and m["bar"]["bottom"] <= vh + 1
    if cls == "phone":
        small = [t for t in m["taps"] if t["h"] < 40]
        res["taps"] = not small and bool(m.get("cta")) and m["cta"]["h"] >= 44
        if small: res["taps_small"] = small[:6]
    vmin = 0.40 if cls == "phone" else 0.30
    res["video"] = bool(m.get("video")) and m["video"]["w"] >= vmin * vw
    return res


def main():
    base, out = sys.argv[1], sys.argv[2]
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    os.makedirs(out, exist_ok=True)
    report, failed = {}, []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for name, cls, (w, h), dpr, mobile in DEVICES:
            if only and only not in (cls, name):
                continue
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=dpr, is_mobile=mobile,
                                      has_touch=mobile, reduced_motion="reduce")
            page = ctx.new_page()
            page.goto(base, wait_until="networkidle")
            time.sleep(0.8)
            m = page.evaluate(MEASURE)
            checks = evaluate(cls, m)
            page.screenshot(path=os.path.join(out, f"{name}.png"))
            report[name] = dict(cls=cls, viewport=[w, h], checks=checks, metrics=m)
            bad = [k for k, v in checks.items() if v is False]
            if bad: failed.append(f"{name}: {', '.join(bad)}")
            print(f"{name:22s} {cls:10s} " + "  ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in checks.items() if isinstance(v, bool)))
            ctx.close()
        browser.close()
    json.dump(report, open(os.path.join(out, "report.json"), "w"), indent=1)
    print(f"\n{len(report) - len(failed)}/{len(report)} devices pass" + ("" if not failed else "\nFAILED: " + " | ".join(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
