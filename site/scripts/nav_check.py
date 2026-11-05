"""Sidebar check: sections, every link, every page reachable, current page shown open.

  python site/scripts/nav_check.py <base_url> <out_dir>

Exit code 1 if any check fails; findings are in <out_dir>/nav_report.json.
"""
from __future__ import annotations

import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

SECTIONS = ["Getting started", "Guides", "Examples & benchmark", "Concepts", "Reference", "Contribute", "About"]
COMBINED = ["Examples", "Sensors", "Results", "Methodology"]
DEEP_PAGES = ["/benchmark/sensors/intel-t265/", "/examples/monado/", "/concepts/notation/", "/reference/cli/", "/about/license/"]
NOT_IN_SIDEBAR = {"/"}
DOCS = pathlib.Path(__file__).resolve().parents[1] / "src/content/docs"


def routes() -> set[str]:
    out = set()
    for p in DOCS.rglob("*.mdx"):
        rel = p.relative_to(DOCS).with_suffix("").as_posix()
        rel = "" if rel == "index" else rel.removesuffix("/index")
        out.add(f"/{rel}/" if rel else "/")
    return out


def sidebar(page) -> dict:
    return page.evaluate("""() => {
      const nav = document.querySelector('nav[aria-label="Main"]');
      const top = nav.querySelector('ul');
      const label = (li) => { const s = li.querySelector(':scope > details > summary span, :scope > a span'); return s ? s.textContent.trim() : ''; };
      const kids = [...top.children];
      return {
        sections: kids.map(label),
        children: Object.fromEntries(kids.map(li => [label(li), [...(li.querySelector(':scope > details > ul')?.children || [])].map(label)])),
        links: [...nav.querySelectorAll('a[href]')].map(a => a.getAttribute('href')),
      };
    }""")


def current_is_open(page) -> bool:
    return page.evaluate("""() => {
      const a = document.querySelector('nav[aria-label="Main"] a[aria-current="page"]');
      if (!a) return false;
      for (let d = a.closest('details'); d; d = d.parentElement.closest('details')) if (!d.open) return false;
      return true;
    }""")


def main() -> int:
    base, out = sys.argv[1].rstrip("/"), pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{base}/getting-started/overview/")
        s = sidebar(page)
        if s["sections"] != SECTIONS:
            problems.append(f"sections are {s['sections']}")
        if s["children"].get("Examples & benchmark") != COMBINED:
            problems.append(f"combined section holds {s['children'].get('Examples & benchmark')}")
        links = sorted({link for link in s["links"] if link.startswith("/")})  # the sidebar also holds external links
        for link in links:
            r = page.request.get(base + link)
            if r.status != 200:
                problems.append(f"{link}: HTTP {r.status}")
        for route in sorted(routes() - set(links) - NOT_IN_SIDEBAR):
            problems.append(f"{route}: not in the sidebar")
        for link in DEEP_PAGES:
            page.goto(base + link)
            if not current_is_open(page):
                problems.append(f"{link}: current page not shown open")
        phone = browser.new_page(viewport={"width": 320, "height": 640})
        phone.goto(f"{base}/benchmark/sensors/")
        heights = set(phone.evaluate("[...document.querySelectorAll('.sg-maker')].map(m => Math.round(m.getBoundingClientRect().height))"))
        if len(heights) > 1:
            problems.append(f"maker lines differ in height at 320 px: {sorted(heights)}")
        browser.close()
    (out / "nav_report.json").write_text(json.dumps({"links": len(links), "problems": problems}, indent=1))
    print(f"{len(links)} links, {len(problems)} problems")
    print("\n".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
