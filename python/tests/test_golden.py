"""The whole sensor export on the synthetic world, pinned byte for byte, so a drawing or wording change can't pass
unnoticed. After a deliberate change: MVIS_GOLDEN=update python3 -m pytest -q tests/test_golden.py, then review the diff."""
import hashlib
import json
import os
from pathlib import Path

import pytest
import yaml

import make_fixtures as F
from mvis_site import export_sensors as X
from mvis_site.results import solve_config

GOLDEN = Path(__file__).resolve().parent / "fixtures/golden"
HASHED = ("site/src/data/sensors/sensor.css", "site/src/scripts/sensor-page.js")  # asset copies, pinned by hash; test_assets checks their sources


def _plan(tmp_path):
    root = tmp_path / "priv"
    cfg = solve_config(yaml.safe_load(F.write_private_config(root).read_text()))
    pub = F.pub_doc()
    return X.render(pub, X.collect(pub, cfg), root / "media", root / "photos")


def _golden(plan) -> dict[str, str]:
    out = {}
    for rel, text in plan.texts.items():
        out[rel] = text if rel not in HASHED else "sha256 " + hashlib.sha256(text.encode()).hexdigest() + "\n"
    out["copies.json"] = json.dumps(sorted([rel, src.name] for src, rel in plan.copies), indent=1) + "\n"
    return out


def test_render_matches_the_golden_files(tmp_path):
    got = _golden(_plan(tmp_path))
    if os.environ.get("MVIS_GOLDEN") == "update":
        for rel, text in got.items():
            (GOLDEN / rel).parent.mkdir(parents=True, exist_ok=True)
            (GOLDEN / rel).write_text(text, encoding="utf-8")
    have = {str(p.relative_to(GOLDEN)): p.read_text(encoding="utf-8") for p in GOLDEN.rglob("*") if p.is_file()}
    assert sorted(have) == sorted(got), "files added or gone; regenerate with MVIS_GOLDEN=update"
    for rel in got:
        assert got[rel] == have[rel], f"{rel} changed; regenerate with MVIS_GOLDEN=update if that was meant"
