"""Shared start-up for the site scripts: the lib lives in <repo>/python."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python"))
