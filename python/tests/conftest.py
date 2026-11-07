import os
import sys
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # make_fixtures

import make_fixtures as F  # noqa: E402
from mvis_site import DATA  # noqa: E402


def env_path(name: str) -> Path:
    """A real-data root from the environment, or skip."""
    v = os.environ.get(name)
    if not v or not Path(v).expanduser().exists():
        pytest.skip(f"{name} not set")
    return Path(v).expanduser()


@pytest.fixture
def pub():
    """The committed public sensor text, fresh per test so a test may change it."""
    return yaml.safe_load((DATA / "public_sensors.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def run_dir(tmp_path):
    return F.write_run(tmp_path / "run")


@pytest.fixture
def variant(run_dir):
    from mvis_site.results import load_variant
    return load_variant({"label": "Take 0123", "run": "{X}/run", "report": True}, {"X": str(run_dir.parent)})


@pytest.fixture
def real_cfg():
    """The private sensors.yaml, solve slice only."""
    from mvis_site.results import solve_config
    return solve_config(yaml.safe_load(env_path("MVIS_SENSORS_CONFIG").read_text()))


@pytest.fixture(autouse=True)
def _pinned_mvis_views(monkeypatch):
    """MVIS's canvas player (views.js / views.css) is MVIS's to change and lives in its repo; tests pin it, so they
    need no MVIS checkout and the goldens cover only the site's own output."""
    from mvis_site import assets
    monkeypatch.setattr(assets, "views_js", lambda: "/* mvis views.js */")
    monkeypatch.setattr(assets, "views_css", lambda: "/* mvis views.css */")
