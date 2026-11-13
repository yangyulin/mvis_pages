"""The only reader of files shipped with the lib, and of the site stylesheet the private pages follow; the extra colour tokens.

progress.js is the `_PROGRESS_JS` player from openmvis src/mvis/analysis/report_shell.py at ec4475e (GPL-3.0-only),
kept byte-exact so the site runs the same player as the MVIS report; tests/test_assets.py checks it against MVIS_SRC.
"""
from __future__ import annotations

import json
import re

from . import ASSETS, SITE


# Colours the site's stylesheet lacks (warnings, the reference overlay, cameras 2-3, axes), shared by the public
# sensor.css and the maintainer's private pages so the two can't drift apart. No trailing ";": each caller joins them.
EXTRA_DARK = "--warn:#e0b25c;--warn-bg:#3a2f18;--ghost:#f59e0b;--c2:#34d399;--c3:#e879f9;--x:#f87171;--y:#4ade80;--z:#60a5fa"
EXTRA_LIGHT = "--warn:#8a5a06;--warn-bg:#fdf3dc;--ghost:#b45309;--c2:#059669;--c3:#a21caf;--x:#dc2626;--y:#16a34a;--z:#2563eb"


def _read(name: str) -> str:
    return (ASSETS / name).read_text(encoding="utf-8")


def page_css() -> str:
    return _read("page.css")


def page_js() -> str:
    return _read("page.js")


def header_css() -> str:
    return _read("sensor_header.css")


def progress_js() -> str:
    return _read("progress.js")


def apriltag() -> dict:
    """AprilTag 36h11 bit rows by tag id, for board_svg."""
    return json.loads(_read("apriltag36h11.json"))


def aruco5x5() -> dict:
    """ArUco DICT_5X5 data bits (5 rows of 5, 1 = white) by marker id 0-249, for charuco_svg. From OpenCV 4.13
    cv2.aruco.generateImageMarker(DICT_5X5_250, id, 7); the smaller DICT_5X5 dictionaries are its first ids."""
    return json.loads(_read("aruco5x5.json"))


def custom_css() -> str:
    return (SITE / "src/styles/custom.css").read_text(encoding="utf-8")


def site_tokens(css: str) -> dict:
    """Accent and slate values from the site's stylesheet, so private pages follow it."""
    block = lambda sel: dict(re.findall(r"--([\w-]+):\s*([^;]+);", css[css.index(sel):css.index("}", css.index(sel))]))
    return {"light": block(":root[data-theme='light']"), "dark": block(":root[data-theme='dark']")}


def views_dir():
    """MVIS's canvas-view assets (views.js, views.css): $MVIS_VIEWS_ASSETS, else the installed `mvis` package
    (pip install pymvis, or an editable checkout of github.com/openmvis/openmvis). The site ships MVIS's own
    player, never a copy kept here."""
    import os
    from pathlib import Path
    env = os.environ.get("MVIS_VIEWS_ASSETS")
    if env:
        d = Path(env).expanduser()
    else:
        try:
            from mvis.analysis import views
        except ImportError:
            raise FileNotFoundError("MVIS view assets not found: install pymvis, set MVIS_VIEWS_ASSETS or pass --mvis-views") from None
        if not getattr(views, "__file__", None):  # a namespace package has no file to start from
            raise FileNotFoundError("MVIS view assets not found: mvis.analysis.views has no __file__; set MVIS_VIEWS_ASSETS or pass --mvis-views")
        d = Path(views.__file__).resolve().parent / "assets"
    if not (d / "views.js").exists():
        raise FileNotFoundError(f"MVIS view assets not found in {d}; set MVIS_VIEWS_ASSETS or pass --mvis-views")
    return d


def views_js() -> str:
    return (views_dir() / "views.js").read_text(encoding="utf-8")


def views_css() -> str:
    return (views_dir() / "views.css").read_text(encoding="utf-8")
