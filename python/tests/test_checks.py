import pytest

from mvis_site import checks as C


def test_routes_from_the_mdx_tree(tmp_path):
    for rel in ("index.mdx", "a/index.mdx", "a/b.mdx", "c.md"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x")
    assert C.routes(tmp_path) == {"/", "/a/", "/a/b/"}


def test_sidebar_problems():
    good = {"sections": C.SECTIONS, "children": {"Examples & benchmark": C.COMBINED}}
    assert C.sidebar_problems(good) == []
    bad = {"sections": ["X"], "children": {}}
    assert C.sidebar_problems(bad) == ["sections are ['X']", "combined section holds None"]


def test_links_and_unlisted_routes():
    assert C.local_links(["/b/", "https://x", "/a/", "/a/"]) == ["/a/", "/b/"]
    assert C.unlisted({"/", "/a/", "/b/"}, ["/a/"]) == ["/b/: not in the sidebar"]


def test_status_and_closed_section_problems_keep_the_page_order():
    assert C.status_problems({"/a/": 200, "/b/": 404, "/c/": 500}) == ["/b/: HTTP 404", "/c/: HTTP 500"]
    assert C.status_problems({"/a/": 200}) == []
    assert C.closed_problems({"/x/": True, "/y/": False}) == ["/y/: current page not shown open"]
    assert C.closed_problems({"/x/": True}) == []


def test_maker_heights():
    assert C.maker_heights_problem([20, 20]) == []
    assert C.maker_heights_problem([20, 38, 20]) == ["maker lines differ in height at 320 px: [20, 38]"]


def _m(**kw):
    box = lambda bottom, w=300, h=50: {"bottom": bottom, "w": w, "h": h}
    m = {"vw": 400, "vh": 700, "scrollW": 400, "title": box(100), "video": box(400, w=380), "cta": box(600, h=48), "bar": box(650), "taps": [{"t": "a", "h": 44}]}
    m.update(kw)
    return m


def test_evaluate_phone_and_laptop():
    assert C.evaluate("phone", _m()) == {"overflow": True, "first": True, "taps": True, "video": True}
    r = C.evaluate("phone", _m(scrollW=420, taps=[{"t": "x", "h": 30}], cta=None))
    assert r["overflow"] is False and r["first"] is False and r["taps"] is False and r["taps_small"] == [{"t": "x", "h": 30}]
    assert C.evaluate("tablet", _m(video={"bottom": 400, "w": 100, "h": 1})) == {"overflow": True, "first": True, "video": False}
    assert C.evaluate("laptop", _m()) == {"overflow": True, "fold": True, "video": True}
    assert C.evaluate("desktop", _m(bar=None, video=None))["fold"] is False


def test_device_matrix_covers_each_class():
    assert {d[1] for d in C.DEVICES} == {"phone", "phone-land", "tablet", "laptop", "desktop"}


def test_ffprobe_parsing_and_keyframe_gap():
    assert C.parse_stream("1920,1080,30/1,450\n") == (1920, 1080, 30.0, 450)
    ts = C.keyframe_times("0.000000,\n1.000000\n\n2.500000,\n")
    assert ts == [0.0, 1.0, 2.5]
    assert C.max_gap(ts, 30, 90) == 1.5
    assert C.max_gap([0.0], 30, 60) == 2.0  # the last keyframe to the clip's end counts


def test_hero_files_and_widths():
    files = C.hero_files({"key": "k", "tiles": [["cam0"], ["cam1"]]})
    assert files == {"hero": "hero_k.mp4", "phone": "hero_k_960.mp4", "tile cam0": "k_cam0.mp4", "small cam0": "k_cam0_240.mp4",
                     "tile cam1": "k_cam1.mp4", "small cam1": "k_cam1_240.mp4"}
    assert [C.want_width(r) for r in ("hero", "phone", "tile cam0", "small cam0")] == [1920, 960, 400, 240]


def _rig(**kw):
    r = {f: 1 for f in C.REQUIRED}
    r.update(key="k", duration=15.0, tiles=[["cam0"]])
    r.update(kw)
    return r


def _media(tmp_path, skip=(), big=False):
    for f in [*C.hero_files(_rig()).values()]:
        for ext in (".mp4", ".jpg"):
            name = f[:-4] + ext
            if name not in skip:
                (tmp_path / name).write_bytes(b"x" * (3_000_000 if big and name == "hero_k_960.mp4" else 10))
    return tmp_path


def _probe(sizes, frames=450, keys="0\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n11\n12\n13\n14\n"):
    stream = lambda path: "%d,%d,30/1,%d" % (*sizes[path.rsplit("/", 1)[1]], frames.get(path.rsplit("/", 1)[1], 450) if isinstance(frames, dict) else frames)
    return stream, lambda path: keys


SIZES = {"hero_k.mp4": (1920, 1080), "hero_k_960.mp4": (960, 540), "k_cam0.mp4": (400, 300), "k_cam0_240.mp4": (240, 180)}


def test_hero_media_all_good(tmp_path):
    errors, lines = C.check_hero_media(_media(tmp_path), [_rig()], *_probe(SIZES))
    assert errors == [] and lines == ["ok   k       1 cams, 450 frames, phone 0.00 MB"]


def test_hero_media_finds_every_kind_of_problem(tmp_path):
    sizes = dict(SIZES, **{"hero_k_960.mp4": (960, 600)})
    errors, lines = C.check_hero_media(_media(tmp_path, skip={"k_cam0_240.jpg", "k_cam0_240.mp4"}, big=True), [_rig(duration=20.0), {"key": "bad"}],
                                       *_probe(sizes, frames={"k_cam0.mp4": 449}, keys="0\n2\n"))
    text = "\n".join(errors)
    for want in ("missing k_cam0_240.mp4", "missing k_cam0_240.jpg", "hero_k_960.mp4 is 960x600", "keyframes up to 13.00 s apart",
                 "frame counts differ", "duration 20.0 s != hero 15.00 s", "phone first load 3.00 MB > 2.5 MB", "bad: rigs.json missing"):
        assert want in text, want
    assert lines[0].startswith("FAIL k")


def test_hero_media_needs_recordings(tmp_path):
    assert C.check_hero_media(tmp_path, [], None, None) == (["rigs.json lists no recordings"], [])


def _row(h, ts, rig="a", hp=False):
    return {"rig": rig, "h": h, "hp": hp, "c": [{"cam": f"cam{i}", "t": t, "p": False, "err": False} for i, t in enumerate(ts)]}


def test_pause_round_measures_freeze_and_drift():
    rows = [_row(i * 0.1, [i * 0.1, i * 0.1]) for i in range(10)]
    assert C.pause_round(rows) == (0.0, 0.0)
    frozen = [_row(i * 0.1, [i * 0.1, 0.5 if i >= 5 else i * 0.1]) for i in range(12)]
    f, d = C.pause_round(frozen)
    assert abs(f - 0.6) < 1e-9 and abs(d - 0.6) < 1e-9
    assert C.pause_verdict(f, d) == (False, "freeze 0.6 s, drift 0.60 s")
    assert C.pause_verdict(0.1, 0.05)[0]
    assert not C.pause_verdict(C.FREEZE_MAX + 0.1, 0.05)[0] and not C.pause_verdict(0.1, C.DRIFT_MAX + 0.01)[0]


def test_pause_round_skips_paused_rewound_and_changed_samples():
    rows = [_row(i * 0.1, [0.0]) for i in range(6)]
    rows += [_row(0.7, [0.0], hp=True), _row(0.1, [0.0]), _row(0.2, [0.0, 0.0]), _row(0.3, [0.0], rig="b")]
    assert C.pause_round(rows) == (0.0, 0.0)


def test_handover_counts_drift_after_the_settle_time():
    samples = [_row(1.0, [1.0])] * 5 + [_row(1.0, [2.0], rig="b")] * 10 + [_row(1.0, [], rig="b"), _row(1.0, [2.0], rig="b", hp=True)]
    assert C.handover_bad(samples) == 2


def test_stall_recovery():
    samples = [{"rig": "a", "h": 1.0, "hp": False, "c": [{"cam": "cam2", "t": 1.0, "err": False}, {"cam": "cam1", "t": 1.0, "err": False},
                                                         {"cam": "cam0", "t": 1.0, "err": False}]} for _ in range(20)]
    samples[0]["c"][0]["err"] = True
    back = C.stall_back(samples)
    assert back == {"cam2": 1.0, "cam1": 7.0}
    assert C.stall_verdict(1, back) and not C.stall_verdict(0, back) and not C.stall_verdict(1, {"cam2": 1.0})
    assert C.stall_back([dict(samples[1], hp=True)]) == {}


def test_label_problems():
    ok = {"name": "A", "pressed": True, "visible": True, "clipped": [], "hidden": 0, "scrolls": False}
    assert C.label_problems(1440, [ok, dict(ok, name="B")]) == []
    bad = [dict(ok, visible=False), dict(ok, name="B", clipped=["IMU"], scrolls=True, hidden=40)]
    assert C.label_problems(1440, bad) == ["A", "chips need scrolling (40 px hidden)", "clipped readout: IMU"]
    assert C.label_problems(390, bad) == ["A", "clipped readout: IMU"]
    assert C.label_problems(390, []) == []
