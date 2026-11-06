import ast

import pytest

from conftest import env_path
from mvis_site import ASSETS, SITE, assets


def test_asset_files_read():
    assert assets.page_css().startswith(":") or ".chips{" in assets.page_css()
    assert "RIGS" in assets.page_js()
    assert ".sd" in assets.header_css()
    assert "mvisProgress" in assets.progress_js()
    assert len(assets.apriltag()["0"]) == 6


def test_site_tokens_from_the_stylesheet():
    css = ":root[data-theme='light']{--sl-color-accent: #b00;--x:1;}\n:root[data-theme='dark']{--sl-color-accent:#f80;}"
    assert assets.site_tokens(css) == {"light": {"sl-color-accent": "#b00", "x": "1"}, "dark": {"sl-color-accent": "#f80"}}


def test_custom_css_is_this_checkout_and_has_both_themes():
    css = assets.custom_css()
    assert css == (SITE / "src/styles/custom.css").read_text()
    t = assets.site_tokens(css)
    assert "sl-color-accent" in t["light"] and "sl-color-gray-6" in t["dark"]


@pytest.mark.real_data
def test_progress_matches_mvis():
    """The vendored player is byte-exact with MVIS: MVIS_SRC is an openmvis checkout."""
    src = env_path("MVIS_SRC") / "src/mvis/analysis/report_shell.py"
    for n in ast.parse(src.read_text()).body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "_PROGRESS_JS":
            assert ast.literal_eval(n.value) == (ASSETS / "progress.js").read_text()
            return
    raise AssertionError("_PROGRESS_JS not found")
