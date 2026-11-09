"""site/scripts/export_calib_motion.py on a synthetic MVIS views file: local-path refusal, the sidecar size budget, the
delta-coded corners, the full-rate frames, cov_cam0 and the move beats. The script is stdlib only and outside mvis_site, so it is loaded
by path."""
import array
import base64
import gzip
import importlib.util
import json
import math
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "site/scripts/export_calib_motion.py"
_spec = importlib.util.spec_from_file_location("export_calib_motion", SCRIPT)
X = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(X)

I9 = [1, 0, 0, 0, 1, 0, 0, 0, 1]
# corners per frame (u, v) in a 300 x 200 image; frame 1 holds an older detection before the last one (ids trim it)
FRAMES = [[], [(250, 150), (40, 30), (41, 199)], [(5, 5)], [(120, 80), (110, 90)]]
OLDER = [(299, 199), (0, 0)]


def views():
    flat, uvo, ids = [], [0], []
    for k, f in enumerate(FRAMES):
        pts = (OLDER if k == 1 else []) + f
        flat += [x for p in pts for x in p]
        uvo.append(len(flat))
        ids.append(list(range(len(f))))
    uvb = base64.b64encode(array.array("h", flat).tobytes()).decode()
    cam = dict(name="cam0", color="#000", R=I9, p=[0, 0, 0], uvb=uvb, uvo=uvo, ids=ids, size=[300, 200],
               k=[200.0, 200.0, 150.0, 100.0], outline=[None] * 4, n=[0, 3, 4, 6])
    return {"scene": {"t": [0.0, 0.1, 0.2, 0.3], "R": [I9] * 4, "xyz": [[0, 0, 0.5]] * 4,
                      "board": {"normal": [0, 0, 1], "center": [0, 0, 0]}, "cams": [cam]}}


ANIM = {"variant": "take", "duration_s": 0.3, "coverage": {"cov_reach_final": 0.5}}


def decode(f):
    """The page's decoding (calib-motion.js prepCams): first pair absolute, every later value + the one 2 before."""
    a = list(f[:2])
    for q in range(2, len(f)):
        a.append(a[q - 2] + f[q])
    return [tuple(a[q:q + 2]) for q in range(0, len(a), 2)]


@pytest.fixture
def take(tmp_path):
    (tmp_path / "views.json").write_text(json.dumps(views()))
    (tmp_path / "take.json").write_text(json.dumps(ANIM))
    (tmp_path / "index.json").write_text(json.dumps({"variants": [{"id": "take"}, {"id": "other"}]}))
    return tmp_path


def run_cams(d):
    X.main(["--cams", str(d / "views.json"), "--cams-anim", str(d / "take.json")])


def test_dump_refuses_a_local_path_and_writes_nothing(tmp_path):
    out = tmp_path / "x.json"
    with pytest.raises(SystemExit, match="local path"):
        X.dump({"root": "/home/someone/results/run"}, out)
    assert not out.exists()
    assert X.dump({"ok": 1}, out) == len('{"ok":1}')


def test_sidecar_corners_round_trip_through_the_delta_coding():
    side = X.cams_sidecar(views(), ANIM)
    assert side["n"] == 4
    uv = side["cams"][0]["uv"]
    assert [decode(f) for f in uv] == FRAMES          # frame 1: only the last detection, the older one dropped
    assert uv[1][2:4] == [40 - 250, 30 - 150]         # stored as differences, negative ones too


def test_sidecar_keeps_every_views_frame_with_its_time_and_outline():
    """Full rate: one sidecar entry per views frame (here 20 Hz with a gap), not 10 Hz steps; outline in every frame."""
    v = views()
    t = [0.0, 0.05, 0.1, 0.3]                                         # 20 Hz, then a 0.2 s gap
    v["scene"]["t"] = t
    o = [[[10 * k, 0], [10 * k + 50, 0], [10 * k + 50, 40], [10 * k, 40]] for k in range(4)]
    v["scene"]["cams"][0]["outline"] = o
    side = X.cams_sidecar(v, ANIM)
    assert side["schema"] == "calib-motion/cams v2"
    assert side["n"] == 4 and side["t"] == t and side["hz"] == 20.0
    c = side["cams"][0]
    assert len(c["uv"]) == len(c["outline"]) == len(c["n_so_far"]) == len(c["dist_cm"]) == 4
    assert c["outline"] == o                                          # frame 0 has no corners but keeps its outline
    assert c["uv"][0] == [] and c["n_so_far"] == [0, 3, 4, 6]


def test_sidecar_cell_first_times_keep_the_frame_time_not_a_10hz_step():
    """cov100_first holds the frame time to 1 ms (a cell first seen at 0.15 s must not count from 0.1 s)."""
    v = views()
    v["scene"]["t"] = [0.0, 0.15, 0.2, 0.3]
    c = X.cams_sidecar(v, ANIM)["cams"][0]
    assert 0.15 in c["cov100_first"]


def test_sidecar_budget_fits_a_600_frame_three_camera_take():
    """The budget (1.5 MB raw, 450 kB gzip) holds the real AprilGrid take at full rate (1.36 MB, 426 kB)."""
    assert (X.CAMS_RAW_MAX, X.CAMS_GZ_MAX) == (1_500_000, 450_000)
    site = SCRIPT.parents[1] / "public/data/calib-motion"
    for f in ("real_takes/aprilgrid_06.cams.json", "real_chess/chessboard_1107_01.cams.json"):
        txt = (site / f).read_bytes()
        side = json.loads(txt)
        assert side["n"] == len(side["t"]) == 600
        assert len(txt) <= X.CAMS_RAW_MAX and len(gzip.compress(txt, 9)) <= X.CAMS_GZ_MAX


def test_cams_writes_the_sidecar_and_cov_cam0_as_the_card_final_value(take):
    run_cams(take)
    side = json.loads((take / "take.cams.json").read_text())
    c = side["cams"][0]
    assert c["grid"] == [3, 2] and all(c["reach"])
    # corners fell in cells (2,1), (0,0), (0,1), (1,0): 4 of the 6 reachable 100 px cells
    assert [f is not None for f in c["cov100_first"]] == [True, True, False, True, False, True]
    ix = json.loads((take / "index.json").read_text())["variants"]
    assert ix[0]["cov_cam0"] == round(4 / 6, 4)
    assert "cov_cam0" not in ix[1]


def test_cams_over_the_size_budget_keeps_the_old_sidecar_and_the_index(take, monkeypatch):
    (take / "take.cams.json").write_text("old")
    monkeypatch.setattr(X, "CAMS_RAW_MAX", 100)
    with pytest.raises(SystemExit, match="over the budget"):
        run_cams(take)
    assert (take / "take.cams.json").read_text() == "old"
    assert "cov_cam0" not in json.loads((take / "index.json").read_text())["variants"][0]


def test_left_right_beats_count_two_sweeps_and_name_the_direction():
    hz, T = 30, 4.0                                  # two 4 s sweeps: x = 0.3 sin(2 pi t / T), board 0.5 m away
    t = [i / hz for i in range(int(2 * T * hz) + 1)]
    s = {"t": t, "p_C": [[0.3 * math.sin(2 * math.pi * x / T), 0, 0.5] for x in t], "q_wxyz": [[1, 0, 0, 0]] * len(t)}
    b = X.seg_beats({"role": "lr", "t0": 0, "t1": t[-1]}, s, hz, [0, 0, 0])
    assert (b["unit"], b["nbeat"]) == ("Sweep", 2)
    assert [x["word"] for x in b["beats"]] == ["going left", "going right", "going left", "going right", "going left"]
    assert [x["i"] for x in b["beats"]] == [1, 1, 2, 2, 2]
    assert b["beats"][0]["t"] == 0 and b["beats"][1]["t"] == pytest.approx(T / 4, abs=0.1)
    rest = X.seg_beats({"role": "rest", "t0": 1.0, "t1": 4.0}, s, hz, [0, 0, 0])
    assert rest == {"unit": "Rest", "nbeat": 1, "beats": [{"t": 1.0, "word": "Count 3", "i": 1}]}
