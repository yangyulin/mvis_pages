"""The drivers without a browser: every module imports, media_probe runs on stub readers, and the printed reports."""
import importlib
import json
import subprocess

import pytest

from mvis_site import checks as C
from mvis_site.browser import hero_sync, media_probe

DRIVERS = ["hero_labels", "hero_sync", "media_probe", "nav", "responsive"]


@pytest.mark.parametrize("name", DRIVERS)
def test_every_driver_imports_without_playwright_and_has_run(name):
    mod = importlib.import_module(f"mvis_site.browser.{name}")
    assert callable(mod.run)


def test_measure_scripts_are_js_functions():
    from mvis_site.browser import hero_labels, nav, responsive
    for js in (hero_labels.MEASURE, hero_sync.SAMPLE, nav.SIDEBAR, nav.CURRENT_OPEN, responsive.MEASURE):
        assert js.strip().startswith("(") and "=>" in js and js.strip().endswith("}")


def test_bust_adds_a_fresh_query(monkeypatch):
    monkeypatch.setattr(hero_sync.time, "time", lambda: 1.5)
    assert hero_sync.bust("http://x/") == "http://x/?t=1500" and hero_sync.bust("http://x/?a=1", "&k=1") == "http://x/?a=1&t=1500&k=1"


def _rig(media, k="r1", cams=("cam0",)):
    tiles = [[c, c.upper()] for c in cams]
    files = C.hero_files({"key": k, "tiles": tiles})
    for f in files.values():
        for ext in (".mp4", ".jpg"):
            (media / (f[:-4] + ext)).write_bytes(b"x")
    return {"key": k, "chip": "c", "caption": "c", "duration": 1.0, "live_cycle": 1, "sensors": "s", "window": [0, 1], "rms": 1, "td": 1,
            "xlabel": "x", "xval": 1, "corners": 1, "tiles": tiles}


def _stream(path):
    w = C.want_width("small" if path.endswith("_240.mp4") else "phone" if path.endswith("_960.mp4") else
                     "hero" if "/hero_" in path else "tile")
    return f"{w},{w * 9 // 16},30/1,30\n"


def test_media_probe_runs_on_stub_readers(tmp_path):
    rig = _rig(tmp_path)
    (tmp_path / "rigs.json").write_text(json.dumps({"rigs": [rig]}))
    out = []
    rc = media_probe.run(tmp_path, _stream, lambda p: "0.0\n0.5\n", out.append)
    assert rc == 0 and out[0].splitlines()[0].startswith("ok   r1") and out[0].endswith("\n1 recordings, 0 problems")


def test_media_probe_reports_problems(tmp_path):
    rig = _rig(tmp_path)
    (tmp_path / "rigs.json").write_text(json.dumps({"rigs": [rig]}))
    (tmp_path / "r1_cam0.jpg").unlink()
    out = []
    assert media_probe.run(tmp_path, _stream, lambda p: "0.0\n", out.append) == 1
    assert "\n  - r1: missing r1_cam0.jpg\n" in out[0] and out[0].startswith("FAIL r1")


def test_ffprobe_readers_ask_for_the_first_video_stream(monkeypatch):
    calls = []

    def fake(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok")
    monkeypatch.setattr(media_probe.subprocess, "run", fake)
    monkeypatch.setattr(media_probe.shutil, "which", lambda n: f"/opt/bin/{n}")
    assert media_probe.stream("a.mp4") == "ok" and media_probe.keyframes("a.mp4") == "ok"
    head = ["/opt/bin/ffprobe", "-v", "error", "-select_streams", "v:0"]
    assert calls == [[*head, "-show_entries", "stream=width,height,nb_frames,r_frame_rate", "-of", "csv=p=0", "a.mp4"],
                     [*head, "-skip_frame", "nokey", "-show_entries", "frame=pts_time", "-of", "csv=p=0", "a.mp4"]]
    monkeypatch.setattr(media_probe.shutil, "which", lambda n: None)  # not on PATH: let subprocess name the error
    media_probe.stream("a.mp4")
    assert calls[-1][0] == "ffprobe"


def test_ffprobe_failure_raises(monkeypatch):
    seen = {}

    def fake(cmd, **kw):
        seen.update(kw)
        raise subprocess.CalledProcessError(1, cmd)
    monkeypatch.setattr(media_probe.subprocess, "run", fake)
    with pytest.raises(subprocess.CalledProcessError):
        media_probe.stream("a.mp4")
    assert seen == {"capture_output": True, "text": True, "check": True}


def test_report_lines():
    assert C.verdict(True) == "ok  " and C.verdict(False) == "FAIL"
    assert C.media_report(["r1: bad"], ["FAIL r1"], 2) == ["FAIL r1", "  - r1: bad", "", "2 recordings, 1 problems"]
    assert C.nav_report(["/a/", "/b/"], ["x"]) == ({"links": 2, "problems": ["x"]}, ["2 links, 1 problems", "x"])
    res = {"overflow": True, "taps": False, "note": "n"}
    assert C.device_line("iPhone", "phone", res) == "iPhone                 phone      overflow=ok  taps=FAIL"
    assert C.device_failure("iPhone", res) == "iPhone: taps" and C.device_failure("iPhone", {"a": True}) is None
    assert C.devices_summary(3, []) == "\n3/3 devices pass" and C.devices_summary(3, ["a: x", "b: y"]) == "\n1/3 devices pass\nFAILED: a: x | b: y"
    assert C.wanted("iPhone", "phone", None) and C.wanted("iPhone", "phone", "phone") and C.wanted("iPhone", "phone", "iPhone")
    assert not C.wanted("iPhone", "phone", "laptop")
    assert C.label_line("phone", 7, True, []) == "ok   phone          7 recordings, scroller"
    assert C.label_line("wide", 7, False, ["a", "b"]) == "FAIL wide           7 recordings, all fit  a; b"
    assert C.labels_summary(5, 1) == "\n4/5 widths name every recording and fit their readout"
    assert C.sync_line("pause/laptop", True, "m") == "ok   pause/laptop             m"
    assert C.sync_summary([True, False]) == "\n1/2 sync checks pass"
