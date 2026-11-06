import base64
import json

import numpy as np
import pytest
import yaml

import make_fixtures as F
from mvis_site import results as R


def test_expand_root(monkeypatch):
    monkeypatch.setenv("HOME", "/h")
    assert str(R.expand_root("{A}/x/{B}", {"A": "~/a", "B": "b"})) == "/h/a/x/b"


def test_corner_uv_reads_each_camera(run_dir):
    uv = R.corner_uv(run_dir / "cam_imu_report.html")
    assert len(uv) == 2 and uv[0].shape == (4, 2)
    assert np.allclose(uv[0], F.uv_corners(F.KB4))


def test_corner_uv_without_a_panel_is_empty(tmp_path):
    p = tmp_path / "r.html"
    p.write_text('mvisProgress("x",{"views": [{"name": "cam0"}, {"name": "cam1", "panel": {"w": 1}}]})')
    assert [u.shape for u in R.corner_uv(p)] == [(0, 2), (0, 2)]


def test_extract_process_drops_frames(run_dir):
    p = R.extract_process(run_dir / "cam_imu_report.html")
    assert set(p) == {"data", "layout", "spec"}
    v = p["spec"]["views"][0]
    assert "panel" not in v and v["img_idx"] == [0] and base64.b64decode(v["img"]) == bytes([128]) * 12
    surf = next(t for t in p["data"] if "surfacecolor" in t)
    assert surf["visible"] is False and surf["x"] == [[0, 0], [0, 0]] and surf["surfacecolor"] == [[128, 128], [128, 128]]
    assert "title" not in p["layout"] and "template" not in p["layout"] and p["layout"]["height"] is None
    assert p["layout"]["margin"] == {"l": 0, "r": 0, "t": 0, "b": 0} and p["layout"]["scene"] == {"aspectmode": "data"}
    assert R.process_has_no_frames(p)


def test_extract_process_missing_or_without_figure(tmp_path):
    assert R.extract_process(tmp_path / "none.html") is None
    (tmp_path / "plain.html").write_text("<html></html>")
    assert R.extract_process(tmp_path / "plain.html") is None


def test_extract_process_view_without_image(tmp_path):
    cams = F.two_cams()
    html = F.report_html(cams).replace('"img": ', '"imgx": ')
    (tmp_path / "r.html").write_text(html)
    v = R.extract_process(tmp_path / "r.html")["spec"]["views"][0]
    assert "img" not in v and "img_idx" in v


def _process(**trace):
    return {"data": [trace], "layout": {}, "spec": {"views": []}}


def test_numbers_that_happen_to_contain_the_jpeg_marker_are_not_a_frame():
    assert R.process_has_no_frames(_process(x={"dtype": "f8", "bdata": "cA/CwOmn/9j/Vw=="}))


def test_a_jpeg_string_is_a_frame_wherever_it_sits():
    assert not R.process_has_no_frames(_process(img="/9j/4AAQSkZJRg=="))
    assert not R.process_has_no_frames({"data": [], "layout": {}, "spec": {"views": [{"img": "/9j/4AAQ"}]}})
    assert not R.process_has_no_frames({"data": [["/9j/x"]], "layout": {}, "spec": {"views": []}})


def test_a_data_url_image_is_a_frame():
    assert not R.process_has_no_frames(_process(source="data:image/png;base64,iVBOR"))


def test_a_camera_panel_is_a_frame():
    assert not R.process_has_no_frames({"data": [], "layout": {}, "spec": {"views": [{"panel": "x"}]}})


def test_strings_walks_nested_values():
    assert list(R._strings({"a": ["x", {"b": "y", "n": 1}], "c": None})) == ["x", "y"]


def test_read_factory_both_models(tmp_path):
    chain = F.write_camchain(tmp_path / "camchain.yaml")
    out = R.read_factory(chain, chain.with_suffix(".txt"))
    assert [c["name"] for c in out] == ["cam0", "cam1"]
    assert out[0]["intr"] == [300.0, 300.0, 320.0, 240.0, 0.01, -0.002, 0.0005, -0.0001]
    assert out[1]["intr"] == [280.0, 280.0, 320.0, 240.0, 0.6, 1.1]  # eucm: alpha, beta moved to the end
    assert out[0]["reproj"] == 0.215 and out[1]["reproj"] is None
    assert np.allclose(out[0]["p_CinI_mm"], [30, 0, -5]) and abs(out[0]["td_ms"] - 1.2) < 1e-12
    assert R.read_factory(chain)[0]["reproj"] is None
    assert R.read_factory(chain, tmp_path / "missing.txt")[0]["reproj"] is None


def test_load_variant_plain(variant):
    assert variant["label"] == "Take 0123" and variant["ref"] is None
    assert variant["sizes"] == [F.SIZE, F.SIZE] and variant["readout_ms"] == [0.0, 0.0]
    assert len(variant["fov"]) == 2 and variant["fov"][0]["reach"] is not None
    assert variant["process"] and R.process_has_no_frames(variant["process"])


def test_load_variant_without_report_has_no_process_or_corners(tmp_path):
    F.write_run(tmp_path / "r", report=False)
    v = R.load_variant({"label": "a", "run": str(tmp_path / "r")}, {})
    assert v["process"] is None and all(f["reach"] is None for f in v["fov"])


def test_load_variant_reads_readout_from_its_own_run(tmp_path):
    F.write_run(tmp_path / "r")
    F.write_run(tmp_path / "ro", report=False, readout=(0.026, 0.0))
    v = R.load_variant({"label": "a", "run": "{X}/r", "readout_run": "{X}/ro"}, {"X": str(tmp_path)})
    assert v["readout_ms"] == [26.0, 0.0]


def test_load_variant_with_a_camchain_reference_in_order(tmp_path):
    F.write_run(tmp_path / "r")
    chain = F.write_camchain(tmp_path / "c.yaml", models=("pinhole-equi", "pinhole-equi"))
    v = R.load_variant({"label": "a", "run": "{X}/r", "ref": {"camchain": "{X}/c.yaml", "results": "{X}/c.txt", "order": [1, 0]}}, {"X": str(tmp_path)})
    assert [c["name"] for c in v["ref"]] == ["cam1", "cam0"]
    v = R.load_variant({"label": "a", "run": "{X}/r", "ref": {"camchain": "{X}/c.yaml"}}, {"X": str(tmp_path)})
    assert v["ref"][0]["reproj"] is None


def test_load_variant_with_a_json_reference(tmp_path):
    F.write_run(tmp_path / "r")
    F.write_run(tmp_path / "k", report=False)
    v = R.load_variant({"label": "a", "run": "{X}/r", "ref": {"json": "{X}/k"}}, {"X": str(tmp_path)})
    assert v["ref"][1]["p_CinI_mm"] == F.two_cams()[1]["p_CinI_mm"] and set(v["ref"][0]) == {"name", "intr", "p_CinI_mm", "rotvec", "td_ms", "reproj"}


def test_load_variant_stitches_cameras_from_pair_recordings(tmp_path):
    F.write_run(tmp_path / "r")
    F.write_stitched(tmp_path / "st")
    v = R.load_variant({"label": "a", "run": "{X}/r", "report": True, "stitched": "{X}/st"}, {"X": str(tmp_path)})
    names = [c["name"] for c in v["run"]["cams"]]
    assert names == ["cam0", "cam1", "cam2"]
    assert v["run"]["cams"][2]["p_CinI_mm"] == [0.0, -40.0, 3.0] and v["readout_ms"][2] == 0.0
    assert len(v["fov"]) == 3 and v["fov"][2]["reach"] is not None


def test_fov_past_fit_flag_clears_the_values(tmp_path):
    F.write_run(tmp_path / "r")
    v = R.load_variant({"label": "a", "run": str(tmp_path / "r"), "report": True, "fov_past_fit": True}, {})
    assert all(f["h"] is None and f["v"] is None and f["h_ext"] and f["v_ext"] for f in v["fov"])


def _series_cfg(tmp_path):
    hand = F.write_series(tmp_path, "h", [-5.25, -5.25])
    arm = F.write_series(tmp_path, "a", [-1.75, -1.75])
    return {"glob": hand, "label": "hand-held"}, {"glob": arm, "label": "arm"}


def test_load_all_series_accepts_one_or_many(tmp_path):
    hand, arm = _series_cfg(tmp_path)
    roots = {"X": str(tmp_path)}
    assert [len(s["runs"]) for s in R.load_all_series(hand, roots)] == [2]
    assert [len(s["runs"]) for s in R.load_all_series([hand, arm], roots)] == [2, 2]
    assert R.load_all_series(None, {}) == [] and R.load_series(None, {}) is None


def test_series_glob_may_list_several_patterns(tmp_path):
    hand, arm = _series_cfg(tmp_path)
    s = R.load_series({"glob": hand["glob"] + "," + arm["glob"], "label": "both"}, {"X": str(tmp_path)})
    assert [r["t_ga_ms"] for r in s["runs"]] == [-5.25, -5.25, -1.75, -1.75]


def test_load_sensor(tmp_path):
    F.write_run(tmp_path / "r")
    d = R.load_sensor("k", {"variants": [{"label": "a", "run": "{X}/r"}]}, {"roots": {"X": str(tmp_path)}})
    assert d["key"] == "k" and len(d["variants"]) == 1 and d["series"] == []


def test_solve_config_keeps_only_the_solve_slice():
    cfg = {"roots": {"R": "~/r"}, "sensors": {"s": {
        "name": "private", "tagline": "private", "board": {"rows": 6}, "series": {"glob": "g"}, "sha256_of": "{R}/x", "demo_media": {"c": "c-id"},
        "variants": [{"label": "a", "run": "{R}/a", "ref": {"json": "{R}/k"}, "report": True}]}, "t": {"variants": []}}}
    out = R.solve_config(cfg)
    assert out == {"roots": {"R": "~/r"}, "sensors": {
        "s": {"variants": [{"label": "a", "run": "{R}/a", "report": True}], "board": {"rows": 6}, "series": {"glob": "g"}, "sha256_of": "{R}/x",
              "demo_media": {"c": "c-id"}},
        "t": {"variants": []}}}
    assert "ref" in cfg["sensors"]["s"]["variants"][0]  # the input is left alone


def test_refuse_frames_needs_a_clean_figure_and_by_default_one_at_all():
    clean, dirty = _process(), _process(img="/9j/4AAQSkZJRg==")
    R.refuse_frames("k", [{"process": clean}])
    R.refuse_frames("k", [{"process": None}, {"process": clean}], require_process=False)  # older runs on the private pages
    for vs, need in (([{"process": None}], True), ([{"process": dirty}], True), ([{"process": None}, {"process": dirty}], False)):
        with pytest.raises(RuntimeError, match="^k: process figure missing or holds camera frames$"):
            R.refuse_frames("k", vs, require_process=need)
