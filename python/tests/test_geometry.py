import math

import numpy as np

from mvis_site import geometry as g


def test_rotvec_roundtrip():
    v = [0.3, -1.1, 0.5]
    assert np.allclose(g.rotvec(g.exp_so3(v)), v)


def test_rotvec_of_identity_and_tiny_vector():
    assert g.rotvec(np.eye(3)) == [0.0, 0.0, 0.0]
    assert np.allclose(g.exp_so3([0, 0, 1e-13]), np.eye(3))


def test_rotvec_near_pi_keeps_the_axis():
    for axis in ([1, 0, 0], [0, 1, 0], [0, 0.6, 0.8]):
        v = np.array(axis) * (math.pi - 1e-6)
        out = np.array(g.rotvec(g.exp_so3(v)))
        assert abs(np.linalg.norm(out) - np.linalg.norm(v)) < 1e-4
        assert abs(abs(out @ np.array(axis)) / np.linalg.norm(out) - 1) < 1e-4


def test_rot_angle_between():
    assert abs(g.rot_angle_between([0, 0, 0.1], [0, 0, 0.3]) - 0.2) < 1e-12


def test_theta_inverts_model():
    k = [0.1, -0.02, 0.01, -0.001]
    th = 1.2
    t2 = th * th
    rd = th * (1 + t2 * (k[0] + t2 * (k[1] + t2 * (k[2] + t2 * k[3]))))
    assert abs(g.theta_from_radius(rd, k) - th) < 1e-9


def test_theta_none_past_the_turn():
    k = [-0.3, 0, 0, 0]  # rises, then folds back
    turn = g.turn_angle(k)
    assert turn < math.pi
    assert g.theta_from_radius(g._radius(turn, k) + 0.1, k) is None


def test_turn_angle_without_a_turn_is_pi():
    assert g.turn_angle([0, 0, 0, 0]) == math.pi


def test_eucm_theta_outside_valid_range():
    assert g.eucm_theta(10.0, 0.9, 2.0) is None
    assert g.eucm_theta(0.0, 0.6, 1.1) == 0.0


def _uv(fx, cx, cy, rd):
    return np.array([[cx - rd * fx, cy], [cx + rd * fx, cy], [cx, cy - rd * fx], [cx, cy + rd * fx]])


def test_fov_reads_the_image_edges_not_the_corners():
    f = 1000 / (np.pi / 2)
    fov = g.fov_deg([f, f, 800, 800, 0, 0, 0, 0], (1600, 1600), _uv(f, 800, 800, np.pi / 4))  # edges at 72 degrees
    assert abs(fov["h"] - 144) < 1e-6 and abs(fov["v"] - 144) < 1e-6 and abs(fov["reach"] - 45) < 1e-6
    assert fov["h_ext"] and fov["v_ext"]


def test_fov_inside_the_corners_is_not_marked():
    f = 500.0
    fov = g.fov_deg([f, f, 300, 300, 0, 0, 0, 0], (600, 600), _uv(f, 300, 300, 0.7))
    assert abs(fov["h"] - 2 * np.degrees(0.6)) < 1e-6 and not fov["h_ext"]


def test_fov_off_centre_is_marked_by_its_far_side():
    f = 500.0  # equidistant: left edge 0.4 rad, right 0.8 rad, corners reach 0.7 rad
    fov = g.fov_deg([f, f, 200, 300, 0, 0, 0, 0], (600, 600), _uv(f, 200, 300, 0.7))
    assert abs(fov["h"] - np.degrees(1.2)) < 1e-6 and fov["h_ext"] and not fov["v_ext"]


def test_fov_past_the_fold_gives_no_value():
    k = [-0.0251, -0.03, 0.0609, -0.0442]  # a fisheye fit that turns at about 70 degrees
    fov = g.fov_deg([746, 746, 960, 540, *k], (1920, 1080), _uv(746, 960, 540, 0.8))
    assert fov["h"] is None and fov["v"] is not None


def test_fov_corners_past_the_turn_reach_the_turn():
    k = [-0.0251, -0.03, 0.0609, -0.0442]
    fov = g.fov_deg([746, 746, 960, 540, *k], (1920, 1080), _uv(746, 960, 540, 5.0))
    assert abs(fov["reach"] - fov["turn"]) < 1e-9


def test_fov_past_90_needs_corners_there():
    k = [-0.0026, 0.0366, -0.0356, 0.006]  # no turn, but the fit runs to 107 degrees at the edge
    intr = [286, 286, 424, 400, *k]
    assert g.fov_deg(intr, (848, 800), _uv(286, 424, 400, 1.2))["h"] is None
    assert g.fov_deg(intr, (848, 800), _uv(286, 424, 400, 1.2))["v"] is not None


def test_fov_without_corners_is_marked_extrapolated():
    fov = g.fov_deg([500, 500, 300, 300, 0, 0, 0, 0], (600, 600), np.zeros((0, 2)))
    assert fov["h"] is not None and fov["h_ext"] and fov["reach"] is None


def test_eucm_fov_is_finite_and_eucm_has_no_turn():
    fov = g.fov_deg([463, 463, 637, 523, 0.65, 1.09], (1280, 1024), _uv(463, 637, 523, 1.3))
    assert (round(fov["h"], 3), round(fov["v"], 3), fov["h_ext"], fov["v_ext"], fov["turn"]) == (166.757, 130.337, True, False, 180.0)
    assert round(fov["reach"], 3) == 77.739


def test_eucm_fov_outside_the_model_is_none():
    fov = g.fov_deg([100, 100, 320, 240, 0.9, 2.0], (640, 480), np.zeros((0, 2)))
    assert fov["h"] is None and fov["h_ext"]


def test_lens_radius_both_models():
    assert g.lens_radius(0.5, [0, 0, 0, 0]) == 0.5
    a, b = 0.6, 1.1
    th = 0.5
    r = g.lens_radius(th, [a, b])
    assert abs(g.eucm_theta(r, a, b) - th) < 1e-9


def test_baseline():
    cams = [{"p_CinI_mm": [0, 0, 0]}, {"p_CinI_mm": [3, 4, 0]}]
    assert g.baseline_mm(cams) == 5.0 and g.baseline_mm(cams[:1]) is None
