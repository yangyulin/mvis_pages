"""Homepage chip labels in Chrome at every width; the verdict is checks.label_problems."""
from __future__ import annotations

from .. import checks

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


def run(base: str) -> int:  # pragma: no cover - drives Chrome through Playwright; run against a served build
    from playwright.sync_api import sync_playwright
    base = base.rstrip("/")
    bad = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        for name, w, h in checks.LABEL_DEVICES:
            page = browser.new_page(viewport={"width": w, "height": h})
            page.goto(base + "/", wait_until="load")
            page.wait_for_selector(".mh-chip")
            if w <= 640:  # the phone readout continues inside Details
                page.evaluate("() => { const d = document.getElementById('mhMore'); if (d) d.open = true; }")
            page.wait_for_timeout(2000)
            n = page.locator(".mh-chip").count()
            measured = []
            for i in range(n):
                # start from the left, then select like the cycle does (no focus scrolling)
                page.evaluate("() => { document.getElementById('mhChips').scrollLeft = 0; }")
                page.evaluate("(i) => document.querySelectorAll('.mh-chip')[i].click()", i)
                page.wait_for_timeout(900)
                measured.append(page.evaluate(MEASURE, i))
            problems = checks.label_problems(w, measured)
            scrolls = bool(measured) and measured[-1]["scrolls"]
            bad += bool(problems)
            print(checks.label_line(name, n, scrolls, problems))
            page.close()
        browser.close()
    print(checks.labels_summary(len(checks.LABEL_DEVICES), bad))
    return 1 if bad else 0
