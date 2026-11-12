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


def test_views_dir_prefers_the_env_var(tmp_path, monkeypatch):
    (tmp_path / "views.js").write_text("x")
    monkeypatch.setenv("MVIS_VIEWS_ASSETS", str(tmp_path))
    assert assets.views_dir() == tmp_path


def test_views_dir_refuses_a_folder_without_the_player(tmp_path, monkeypatch):
    monkeypatch.setenv("MVIS_VIEWS_ASSETS", str(tmp_path))
    with pytest.raises(FileNotFoundError, match="MVIS_VIEWS_ASSETS"):
        assets.views_dir()


def test_views_dir_falls_back_to_the_installed_package(tmp_path, monkeypatch):
    import sys
    import types
    monkeypatch.delenv("MVIS_VIEWS_ASSETS", raising=False)
    pkg = tmp_path / "mvis" / "analysis" / "views"
    (pkg / "assets").mkdir(parents=True)
    (pkg / "assets" / "views.js").write_text("x")
    analysis = types.ModuleType("mvis.analysis")
    views = types.ModuleType("mvis.analysis.views")
    views.__file__ = str(pkg / "__init__.py")
    analysis.views = views
    monkeypatch.setitem(sys.modules, "mvis", types.ModuleType("mvis"))
    monkeypatch.setitem(sys.modules, "mvis.analysis", analysis)
    monkeypatch.setitem(sys.modules, "mvis.analysis.views", views)
    assert assets.views_dir() == pkg / "assets"


def test_views_dir_names_the_fix_when_mvis_is_not_installed(monkeypatch):
    import sys
    monkeypatch.delenv("MVIS_VIEWS_ASSETS", raising=False)
    monkeypatch.setitem(sys.modules, "mvis", None)
    monkeypatch.setitem(sys.modules, "mvis.analysis", None)
    with pytest.raises(FileNotFoundError, match="pymvis"):
        assets.views_dir()


def test_views_dir_refuses_a_package_without_a_file(monkeypatch):
    import sys
    import types
    monkeypatch.delenv("MVIS_VIEWS_ASSETS", raising=False)
    analysis = types.ModuleType("mvis.analysis")
    views = types.ModuleType("mvis.analysis.views")  # no __file__, like a namespace package
    analysis.views = views
    monkeypatch.setitem(sys.modules, "mvis", types.ModuleType("mvis"))
    monkeypatch.setitem(sys.modules, "mvis.analysis", analysis)
    monkeypatch.setitem(sys.modules, "mvis.analysis.views", views)
    with pytest.raises(FileNotFoundError, match="__file__"):
        assets.views_dir()
