import json

import pytest

from mvis_site import leaderboard as L


def test_site_css_drops_gradio_rules_and_follows_the_site_theme():
    css = L.site_css("#lb-tabs button{a:1}\n.cb .x{b:2}\nmain.app .y{c:3}\n.dark .cb .z{d:4}")
    assert css == L.THEME + ".cb .x{b:2}:root[data-theme='dark'] .cb .z{d:4}"  # the dropped rule takes the newline before it


def test_strip_title_takes_only_the_first_heading():
    assert L.strip_title("<div><h2>A</h2>x<h2>B</h2></div>") == "<div>x<h2>B</h2></div>"


def test_board_json_and_dumps():
    b = L.board_json("b", "abc1234", "how", {"one": "<p>é</p>"})
    assert list(b) == ["batch", "results_commit", "how_to_read", "datasets"]
    assert L.dumps(b) == json.dumps(b, ensure_ascii=False, indent=1) + "\n" and "é" in L.dumps(b)


def test_jobs_follow_the_weights_file():
    w = {"snapdragon_b": 1, "davis_outdoor_45": 1, "davis_indoor_forward": 1, "davis_indoor_45": 1, "x": 1}
    assert L.jobs_for(w, "DAVIS") == ["davis_indoor_45", "davis_indoor_forward", "davis_outdoor_45"]
    assert L.jobs_for(w, "SNAP") == ["snapdragon_b"]
    with pytest.raises(ValueError, match="no SNAP bags"):
        L.jobs_for({"davis_a": 1}, "SNAP")


def test_site_how_to_read_swaps_only_the_kalibr_input_sentence():
    assert L.how_to_read(f"a {L.FIXED_OLD} b") == f"a {L.FIXED_NEW} b"
    with pytest.raises(ValueError):
        L.how_to_read("changed text")
    with pytest.raises(ValueError):
        L.how_to_read(L.FIXED_OLD * 2)


def test_rekey_names_the_two_families():
    assert L.rekey(dict(about="x", families=dict(UD=1, US=2))) == dict(about="x", families=dict(DAVIS=1, SNAP=2))


def test_weights_note_is_said_once():
    s = {"families": {"A": {"caveat": f"{L.WEIGHTS_NOTE} Other."}}}
    assert L.without_repeated_weights_note(s)["families"]["A"]["caveat"] == "Other."


def test_run_configs_fold_each_tool():
    w = {"a": {"sigma_g": 1.5e-3, "sigma_a": 2e-2}, "b": {"sigma_g": 1e-3, "sigma_a": 3e-2}}
    out = L.run_configs_html(["a", "b"], w, "mvis: <x>\n", "kalibr: 1\n", {"command": ["basalt", "--x", "y"]})
    assert list(out) == ["MVIS", "Kalibr", "Basalt"]
    assert "Runs (2," in out["MVIS"] and "gyro 1.50e-03 · accel 2.00e-02" in out["MVIS"] and "mvis: &lt;x&gt;</pre>" in out["MVIS"]
    assert L.KALIBR_CMD.split()[0] in out["Kalibr"] and "basalt \\\n    --x \\\n    y" in out["Basalt"]
    assert out["MVIS"].startswith("<details class='cfgfold'><summary>Run config · MVIS · <span class='mono'>mvis cam-imu</span></summary>")


def test_uzh_json():
    assert L.uzh_json("f", "h") == {"batch": L.BATCH, "fragment": "f", "how_to_read": "h"}
