import json

import pytest

from mvis_site import checks as C


def test_routes_from_the_mdx_tree(tmp_path):
    for rel in ("index.mdx", "a/index.mdx", "a/b.mdx", "c.md"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x")
    assert C.routes(tmp_path) == {"/", "/a/", "/a/b/"}


NAV = [{"label": "T265", "link": "/devices/t265/", "group": "Tracking"}, {"label": "Ego", "link": "/devices/ego/", "group": "Head-worn"},
       {"label": "Ego GS", "link": "/devices/ego-gs/", "group": "Head-worn"}]


def _sidebar(**kw):
    s = {"sections": C.SECTIONS, "children": {"Benchmark": C.BENCHMARK, "Device wiki": ["Overview", "Tracking", "Head-worn"]},
         "groups": {"Device wiki": {"Tracking": ["T265"], "Head-worn": ["Ego", "Ego GS"]}}}
    s.update(kw)
    return s


def test_sidebar_has_benchmark_then_sensor_wiki():
    assert C.SECTIONS.index("Device wiki") == C.SECTIONS.index("Benchmark") + 1
    assert C.BENCHMARK == ["Examples", "Results", "Methodology"]
    assert C.sidebar_problems(_sidebar(), NAV) == []


RNAV = [{"label": "VI-Rig 4 IMUs + 3 cams", "link": "/benchmark/results/virig-4imus-3cams/"}, {"label": "TUM-VI", "link": "/benchmark/results/tum-vi/"}]


def test_results_holds_the_leaderboard_then_one_eval_page_per_results_nav_entry():
    paths = {"Benchmark › Results": ["Leaderboard", "Datasets eval"], "Benchmark › Results › Datasets eval": ["VI-Rig 4 IMUs + 3 cams", "TUM-VI"]}
    assert C.sidebar_problems(_sidebar(paths=paths), NAV, RNAV) == []
    swapped = dict(paths, **{"Benchmark › Results › Datasets eval": ["TUM-VI", "VI-Rig 4 IMUs + 3 cams"]})
    assert C.sidebar_problems(_sidebar(paths=swapped), NAV, RNAV) == [
        "Benchmark › Results › Datasets eval holds ['TUM-VI', 'VI-Rig 4 IMUs + 3 cams'], want ['VI-Rig 4 IMUs + 3 cams', 'TUM-VI']"]
    assert C.sidebar_problems(_sidebar(), NAV, RNAV) == [
        "Benchmark › Results holds None, want ['Leaderboard', 'Datasets eval']",
        "Benchmark › Results › Datasets eval holds None, want ['VI-Rig 4 IMUs + 3 cams', 'TUM-VI']"]


def test_page_problems_name_a_sideways_scroll_and_a_theme_that_did_not_apply():
    ok = {"vw": 390, "scrollW": 390, "theme": "dark", "wide": []}
    assert C.page_problems("/p/", "phone-390", "dark", ok) == []
    assert C.page_problems("/p/", "phone-390", "light", dict(ok, scrollW=420, wide=["DIV.x"])) == [
        "/p/ phone-390 light: scrolls sideways (420 > 390 px; widest ['DIV.x'])", "/p/ phone-390 light: page theme is dark"]
    assert C.shot_name("/benchmark/results/", "laptop-1360", "dark") == "benchmark_results-laptop-1360-dark.png"
    assert C.shot_name("/", "phone-390", "light") == "home-phone-390-light.png"
    assert {(v, t) for v, _, _, t in C.PAGE_VIEWS} == {(v, t) for v in ("phone-390", "laptop-1360") for t in ("light", "dark")}


def test_sidebar_problems_name_what_is_wrong():
    assert C.sidebar_problems({"sections": ["X"], "children": {}, "groups": {}}, NAV) == [
        "sections are ['X']", "Benchmark holds None", "Device wiki holds None, want ['Overview', 'Tracking', 'Head-worn']",
        "Device wiki › Tracking holds None, want ['T265']", "Device wiki › Head-worn holds None, want ['Ego', 'Ego GS']"]


def test_a_sensor_under_benchmark_fails():
    s = _sidebar(children={"Benchmark": [*C.BENCHMARK, "Sensors"], "Device wiki": ["Overview", "Tracking", "Head-worn"]})
    assert C.sidebar_problems(s, NAV) == ["Benchmark holds ['Examples', 'Results', 'Methodology', 'Sensors']"]


def test_a_sensor_missing_or_twice_in_the_groups_fails():
    missing = _sidebar(groups={"Device wiki": {"Tracking": ["T265"], "Head-worn": ["Ego"]}})
    assert C.sidebar_problems(missing, NAV) == ["Device wiki › Head-worn holds ['Ego'], want ['Ego', 'Ego GS']"]
    twice = _sidebar(groups={"Device wiki": {"Tracking": ["T265", "Ego"], "Head-worn": ["Ego", "Ego GS"]}})
    assert C.sidebar_problems(twice, NAV) == ["Device wiki › Tracking holds ['T265', 'Ego'], want ['T265']"]


def test_deep_pages_use_the_new_addresses():
    assert "/devices/intel-t265/" in C.DEEP_PAGES and "/benchmark/examples/monado/" in C.DEEP_PAGES
    assert not [p for p in C.DEEP_PAGES if p.startswith(("/benchmark/sensors/", "/examples/"))]


def _redirect(to):  # Astro's static redirect page
    return (f'<!doctype html><title>Redirecting to: {to}</title><meta http-equiv="refresh" content="0;url={to}">'
            f'<meta name="robots" content="noindex"><link rel="canonical" href="https://openmvis.com{to}"><body><a href="{to}">x</a></body>')


def _docs(tmp_path, pages):
    for route, html in pages.items():
        f = tmp_path / route.strip("/") / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(html)
    return tmp_path


PAGE = '<html><body><a href="/new/">self</a><a href="/media/x.jpg">m</a><a href="https://x.org/">ext</a><a href="/new/#top">h</a></body></html>'


def test_check_moves_passes_a_clean_move(tmp_path):
    docs = _docs(tmp_path, {"/old/": _redirect("/new/"), "/new/": PAGE})
    (tmp_path / "media").mkdir()
    (tmp_path / "media/x.jpg").write_text("j")
    assert C.check_moves(docs, {"/old/": "/new/"}) == []


def test_check_moves_flags_wrong_target_missing_redirect_and_a_page_left_behind(tmp_path):
    docs = _docs(tmp_path, {"/old/": _redirect("/other/"), "/other/": "<p>o</p>", "/new/": "<p>n</p>", "/kept/": "<p>still a page</p>",
                            "/new2/": "<p>n2</p>"})
    assert C.check_moves(docs, {"/old/": "/new/", "/gone/": "/new2/", "/kept/": "/new/"}) == [
        "/old/: redirects to /other/, want /new/", "/gone/: no page at the old address", "/kept/: still a real page, want a redirect to /new/"]


def test_check_moves_flags_a_new_address_that_is_missing_or_a_redirect(tmp_path):
    docs = _docs(tmp_path, {"/a/": _redirect("/b/"), "/b/": _redirect("/c/"), "/c/": "<p>c</p>", "/d/": _redirect("/e/")})
    assert C.check_moves(docs, {"/a/": "/b/", "/d/": "/e/"}) == [
        "/b/: new address is a redirect, not a page", "/e/: new address has no page", "/a/: redirects to /b/, which redirects again",
        "/d/: redirects to /e/, which has no page"]


def test_check_moves_flags_two_hop_chains_outside_the_moves(tmp_path):
    docs = _docs(tmp_path, {"/x/": _redirect("/y/"), "/y/": _redirect("/z/"), "/z/": "<p>z</p>"})
    assert C.check_moves(docs, {}) == ["/x/: redirects to /y/, which redirects again"]


def test_check_moves_flags_broken_internal_links(tmp_path):
    docs = _docs(tmp_path, {"/p/": '<a href="/missing/">a</a><a href="/p/">b</a><a href="/f.css">c</a><a href="/q">d</a><a href="#x">e</a>', "/q/": "<p>q</p>"})
    assert C.check_moves(docs, {}) == ["/p/: broken link /missing/", "/p/: broken link /f.css"]


def test_hash_keeping_redirect_page_counts_as_a_redirect(tmp_path):
    keep = ('<head><meta name="robots" content="noindex"><link rel="canonical" href="https://openmvis.com/new/">'
            "<script>location.replace('/new/' + location.search + location.hash)</script></head>")
    docs = _docs(tmp_path, {"/old/": keep, "/new/": "<p>n</p>"})
    assert C.redirect_target((docs / "old/index.html").read_text()) == "/new/"
    assert C.check_moves(docs, {"/old/": "/new/"}) == []


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


def test_a_real_page_that_calls_location_replace_is_not_a_redirect():
    page = "<main><button onclick=\"location.replace('/x/')\">go</button></main>"
    assert C.redirect_target(page) is None



def test_device_wiki_moved_from_sensors_in_one_hop():
    """Phase 3 (2026-11-10): the device pages live under /devices/; every old /sensors/ and /benchmark/sensors/ address
    redirects straight there, and no redirect or link points at /sensors/ any more."""
    import re
    from mvis_site import REPO
    moved = json.loads((REPO / "site/src/data/moved.json").read_text(encoding="utf-8"))
    nav = json.loads((REPO / "site/src/data/sensor-nav.json").read_text(encoding="utf-8"))
    new_since_move = {"cyperstereo"}   # first published under /devices/, so never had a /sensors/ address
    slugs = [n["link"].removeprefix("/devices/").strip("/") for n in nav]
    slugs = [s for s in slugs if s not in new_since_move]
    assert all(n["link"].startswith("/devices/") for n in nav)
    for old in ("/sensors/", "/benchmark/sensors/"):
        assert moved[old] == "/devices/"
        assert all(moved[f"{old}{s}/"] == f"/devices/{s}/" for s in slugs)
    assert not [t for t in moved.values() if t.startswith("/sensors/")]
    config = (REPO / "site/astro.config.mjs").read_text(encoding="utf-8")
    assert not re.findall(r":\s*'/sensors/", config), "astro.config redirects must go straight to /devices/"
