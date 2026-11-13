"""Board shape on a sensor page: read from a run folder, drawn per corner, shown only when the run estimated it."""
import numpy as np
import pytest
import yaml

from mvis_site.markup import board_shape_svg
from mvis_site.results import read_board_shape
from mvis_site.sensor_parts import board_shape_section

BOARD = {"rows": 2, "cols": 3, "tag_mm": 50.0, "spacing": 0.3}


def _shape(n=24, unseen=()):
    h = np.linspace(-0.003, 0.005, n)
    obs = [0 if i in unseen else 7 for i in range(n)]
    return h, obs


def test_read_board_shape_uses_seen_corners_only(tmp_path):
    h, obs = _shape(unseen=(23,))
    (tmp_path / "cam_imu_board_shape.yaml").write_text(yaml.safe_dump({"board_shape": {"heights_m": h.tolist(), "n_obs": obs}}))
    s = read_board_shape(tmp_path)
    assert s["p2p_mm"] == pytest.approx(np.ptp(h[:23]) * 1e3) and s["rms_mm"] == pytest.approx(np.std(h[:23]) * 1e3)
    assert read_board_shape(tmp_path / "missing") is None


def test_svg_draws_every_corner_and_marks_unseen():
    h, obs = _shape(unseen=(0,))
    svg = board_shape_svg(BOARD, {"heights_m": h.tolist(), "n_obs": obs, "p2p_mm": 8.0, "rms_mm": 2.0})
    assert svg.count("<circle") == 24 and svg.count("not seen") == 1
    assert "peak to peak 8.0 mm" in svg and "+5.0 mm" in svg            # colour scale symmetric about flat
    # corner 0 of tag 0 sits bottom-left: smallest x, largest y in SVG coordinates
    first = svg.index('<circle cx="0.0" cy="115.0"')
    assert first > 0


def test_svg_refuses_heights_for_another_board():
    with pytest.raises(ValueError, match="AprilGrid"):
        board_shape_svg(BOARD, {"heights_m": [0.0] * 5, "n_obs": [1] * 5, "p2p_mm": 0, "rms_mm": 0})


def test_section_only_when_a_run_estimated_the_shape():
    flat = {"board_shape": None}
    assert board_shape_section([flat, flat], BOARD) == ""
    h, obs = _shape()
    shaped = {"board_shape": {"heights_m": h.tolist(), "n_obs": obs, "p2p_mm": 8.0, "rms_mm": 2.0}}
    html = board_shape_section([shaped, flat], BOARD)
    assert "<svg" in html and "assumed a flat board" in html

