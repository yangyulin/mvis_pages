"""Homepage device matrix in Chrome: screenshots plus the layout verdicts of checks.evaluate."""
from __future__ import annotations

import json
import os
import time

from .. import checks

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


def run(base: str, out: str, only: str | None = None) -> int:  # pragma: no cover - drives Chrome through Playwright; run against a served build
    from playwright.sync_api import sync_playwright
    os.makedirs(out, exist_ok=True)
    report, failed = {}, []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for name, cls, (w, h), dpr, mobile in checks.DEVICES:
            if not checks.wanted(name, cls, only):
                continue
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=dpr, is_mobile=mobile,
                                      has_touch=mobile, reduced_motion="reduce")
            page = ctx.new_page()
            page.goto(base, wait_until="networkidle")
            time.sleep(0.8)
            m = page.evaluate(MEASURE)
            res = checks.evaluate(cls, m)
            page.screenshot(path=os.path.join(out, f"{name}.png"))
            report[name] = dict(cls=cls, viewport=[w, h], checks=res, metrics=m)
            bad = checks.device_failure(name, res)
            if bad:
                failed.append(bad)
            print(checks.device_line(name, cls, res))
            ctx.close()
        browser.close()
    json.dump(report, open(os.path.join(out, "report.json"), "w"), indent=1)
    print(checks.devices_summary(len(report), failed))
    return 1 if failed else 0


PAGE_MEASURE = r"""
() => ({ vw: innerWidth, scrollW: document.documentElement.scrollWidth, theme: document.documentElement.dataset.theme,
         wide: [...document.querySelectorAll('main *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1
                 && !e.closest('[style*=overflow], .ev-tw, .rp-tw, .tw')).slice(0, 3).map(e => e.tagName + '.' + e.className) })
"""


def run_pages(base: str, out: str, pages: list[str]) -> int:  # pragma: no cover - drives Chrome through Playwright; run against a served build
    """Full-page screenshots of each content page at checks.PAGE_VIEWS, and checks.page_problems."""
    from playwright.sync_api import sync_playwright
    os.makedirs(out, exist_ok=True)
    problems = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for view, w, h, theme in checks.PAGE_VIEWS:
            ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=w < 600, has_touch=w < 600, reduced_motion="reduce")
            ctx.add_init_script(f"localStorage.setItem('starlight-theme', '{theme}')")
            page = ctx.new_page()
            for path in pages:
                page.goto(base.rstrip("/") + path, wait_until="networkidle")
                bad = checks.page_problems(path, view, theme, page.evaluate(PAGE_MEASURE))
                page.screenshot(path=os.path.join(out, checks.shot_name(path, view, theme)), full_page=True)
                print(checks.verdict(not bad), path, view, theme)
                problems += bad
            ctx.close()
        browser.close()
    print("\n".join(problems) or f"{len(pages)} pages x {len(checks.PAGE_VIEWS)} views pass")
    return 1 if problems else 0
