"""Sidebar check in Chrome: sections, every link, every page reachable, current page shown open."""
from __future__ import annotations

import json
import pathlib

from .. import SITE, checks

SIDEBAR = """() => {
  const nav = document.querySelector('nav[aria-label="Main"]');
  const top = nav.querySelector('ul');
  const label = (li) => { const s = li.querySelector(':scope > details > summary span, :scope > a span'); return s ? s.textContent.trim() : ''; };
  const kids = [...top.children];
  return {
    sections: kids.map(label),
    children: Object.fromEntries(kids.map(li => [label(li), [...(li.querySelector(':scope > details > ul')?.children || [])].map(label)])),
    groups: Object.fromEntries(kids.map(li => [label(li), Object.fromEntries([...(li.querySelector(':scope > details > ul')?.children || [])]
      .filter(c => c.querySelector(':scope > details')).map(c => [label(c), [...c.querySelector(':scope > details > ul').children].map(label)]))])),
    links: [...nav.querySelectorAll('a[href]')].map(a => a.getAttribute('href')),
  };
}"""
CURRENT_OPEN = """() => {
  const a = document.querySelector('nav[aria-label="Main"] a[aria-current="page"]');
  if (!a) return false;
  for (let d = a.closest('details'); d; d = d.parentElement.closest('details')) if (!d.open) return false;
  return true;
}"""


def run(base: str, out) -> int:  # pragma: no cover - drives Chrome through Playwright; run against a served build
    from playwright.sync_api import sync_playwright
    base, out = base.rstrip("/"), pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{base}/getting-started/overview/")
        s = page.evaluate(SIDEBAR)
        problems = checks.sidebar_problems(s, json.loads((SITE / "src/data/sensor-nav.json").read_text()))
        links = checks.local_links(s["links"])
        problems += checks.status_problems({link: page.request.get(base + link).status for link in links})
        problems += checks.unlisted(checks.routes(SITE / "src/content/docs"), links)
        opened = {}
        for link in checks.DEEP_PAGES:
            page.goto(base + link)
            opened[link] = page.evaluate(CURRENT_OPEN)
        problems += checks.closed_problems(opened)
        phone = browser.new_page(viewport={"width": 320, "height": 640})
        phone.goto(f"{base}/sensors/")
        problems += checks.maker_heights_problem(phone.evaluate("[...document.querySelectorAll('.sg-maker')].map(m => Math.round(m.getBoundingClientRect().height))"))
        browser.close()
    report, lines = checks.nav_report(links, problems)
    (out / "nav_report.json").write_text(json.dumps(report, indent=1))
    print("\n".join(lines))
    return 1 if problems else 0
