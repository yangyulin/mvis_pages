"""Old deep links of the one-page results (/benchmark/results/#...) keep landing: every id the old page had either
stays on the Leaderboard (#ds-overall, #ov-h) or is a legacy hash of one dataset eval page, which it opens at the top
(the repeatability ids are off those pages since 2026-11-11). moved.json and check_moves cover whole pages only, not hashes."""
import json
import re

import pytest

from mvis_site import REPO

NAV = json.loads((REPO / "site/src/data/results-nav.json").read_text())
OLD = json.loads((REPO / "python/tests/fixtures/old_results_ids.json").read_text())["ids"]
STAYS = {"ds-overall", "ov-h"}  # the rubric total is dropped; its old hashes just open the Leaderboard


def built_ids(link: str) -> set[str]:
    f = REPO / "docs" / link.strip("/") / "index.html"
    if not f.exists():
        pytest.skip("no built site: run npm run build in site/")
    return set(re.findall(r'\sid="([^"]+)"', f.read_text(encoding="utf-8")))


def test_every_old_id_has_a_new_home():
    legacy = {h for p in NAV for h in p["legacy"]}
    assert sorted(set(OLD) - legacy - STAYS) == []
    assert not legacy & STAYS and len(legacy) == sum(len(p["legacy"]) for p in NAV)  # one page per hash


def test_every_legacy_target_page_is_built():
    for p in NAV:
        assert built_ids(p["link"]), p["slug"]


def test_the_leaderboard_carries_the_jump_and_no_old_dataset_ids():
    ids = built_ids("/benchmark/results/")
    html = (REPO / "docs/benchmark/results/index.html").read_text(encoding="utf-8")
    assert not [i for i in ids if i.startswith(("ds-", "rp-"))]
    assert '"ds-virig"' in html and "location.replace" in html
