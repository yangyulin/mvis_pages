import re

import numpy as np

import make_fixtures as F
from mvis_site import sensor_rig as R


def test_drawn_fov_uses_the_value_when_known():
    assert R.drawn_fov({"h": 120.0, "v": 80.0, "reach": 60.0, "turn": 180.0}, "h") == (120.0, True)


def test_drawn_fov_past_the_fit_goes_to_the_corners_reach():
    assert R.drawn_fov({"h": None, "v": 80.0, "reach": 69.6, "turn": 180.0}, "h") == (139.2, False)


def test_drawn_fov_without_corner_data_stays_on_the_fit_and_under_the_cap():
    assert R.drawn_fov({"h": None, "v": None, "reach": None, "turn": 75.0}, "v") == (150.0, False)
    assert R.drawn_fov({"h": None, "v": None, "reach": None, "turn": 180.0}, "v") == (170.0, False)


def test_rig_drawing_shows_solved_numbers(variant):
    svg = R.rig_drawing(variant)
    assert "From above" in svg and "From the front" in svg and "baseline" in svg
    assert svg.count('fill-opacity=".12"') == 2 and "stroke-dasharray" not in svg and "past the fit" not in svg
    table = R.rig_table(variant)
    for c in variant["run"]["cams"]:
        assert f'<td>{float(np.linalg.norm(c["p_CinI_mm"])):.1f}</td>' in table
    assert table.count("<tr>") == 3


def test_a_fan_past_the_fit_is_dashed_and_explained(variant):
    variant["fov"] = [{**f, "h": None, "v": None} for f in variant["fov"]]
    svg = R.rig_drawing(variant)
    assert "stroke-dasharray" in svg and R.e(R.PAST_FIT_NOTE) in svg


def test_one_camera_rig_has_no_baseline(variant):
    variant["run"]["cams"] = variant["run"]["cams"][:1]
    variant["fov"] = variant["fov"][:1]
    svg = R.rig_drawing(variant)
    assert "baseline" not in svg and svg.count('fill-opacity=".12"') == 1


def test_cameras_pointing_apart_fall_back_to_cam0(variant):
    variant["run"]["cams"][1]["rotvec"] = [0.0, np.pi, 0.0]  # looks back the other way
    f, r, u, _ = R._rig_frame(variant)
    assert np.allclose(f, R.exp_so3(variant["run"]["cams"][0]["rotvec"])[:, 2])
    assert abs(f @ r) < 1e-9 and abs(np.linalg.norm(u) - 1) < 1e-9


def test_cameras_stacked_along_the_view_keep_camera_right(variant):
    variant["run"]["cams"][1]["p_CinI_mm"] = [variant["run"]["cams"][0]["p_CinI_mm"][0], 2.0, 40.0]
    f, r, _, Rs = R._rig_frame(variant)
    assert r @ Rs[0][:, 0] > 0.9


def test_baseline_against_camera_right_is_flipped(variant):
    a, b = variant["run"]["cams"]
    a["p_CinI_mm"], b["p_CinI_mm"] = b["p_CinI_mm"], a["p_CinI_mm"]
    _, r, _, Rs = R._rig_frame(variant)
    assert r @ Rs[0][:, 0] > 0


def test_a_crowded_plate_drops_labels_rather_than_overlap(variant):
    cams = [F.cam(f"cam{i}", F.KB4, [0.5 * i, 0.0, 0.0], [0.0, 0.0, 0.0]) for i in range(4)]
    variant["run"]["cams"] = cams
    variant["fov"] = variant["fov"] * 2
    svg = R.rig_drawing(variant)
    assert re.findall(r">cam\d<", svg) == [">cam0<", ">cam0<"]  # 4 cameras in two views; only cam0 finds a free spot in each
