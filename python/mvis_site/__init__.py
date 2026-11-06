"""Page generation for openmvis.com: sensor pages, leaderboard tables and the checks the site scripts run.

Paths are relative to this checkout; nothing is read at import.
"""
from pathlib import Path

PKG = Path(__file__).resolve().parent
ASSETS = PKG / "assets"
REPO = PKG.parents[1]
SITE = REPO / "site"
DATA = REPO / "python" / "data"
