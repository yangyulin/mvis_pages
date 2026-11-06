import json
import shutil

import pytest
import yaml

import make_fixtures as F
from mvis_site import DATA
from mvis_site import export_sensors as X
from mvis_site.results import solve_config


@pytest.fixture
def world(tmp_path):
    cfg_path = F.write_private_config(tmp_path / "priv")
    pub = F.pub_doc()
    cfg = solve_config(yaml.safe_load(cfg_path.read_text()))
    return dict(root=tmp_path / "priv", cfg_path=cfg_path, pub=pub, cfg=cfg, site=tmp_path / "site")


def test_sha256(tmp_path):
    p = tmp_path / "x"
    p.write_bytes(b"abc")
    assert X.sha256(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_collect_labels_takes_and_hashes_the_recording(world):
    c = X.collect(world["pub"], world["cfg"])
    assert [v["label"] for v in c["rig-photo"]["variants"]] == ["Hand-held", "Arm"]  # run_labels
    assert [v["label"] for v in c["rig-groups"]["variants"]] == ["Recording 1"]  # a take id never shows
    assert [v["label"] for v in c["rig-old"]["variants"]] == ["Bag 1"]
    assert c["rig-photo"]["sha"] == X.sha256(world["root"] / "rec.bin") and c["rig-old"]["sha"] is None
    assert len(c["rig-photo"]["series"][0]["runs"]) == 3 and c["rig-photo"]["variants"][0]["ref"] is None


def test_collect_drops_reference_columns_even_from_a_full_config(world):
    full = yaml.safe_load(world["cfg_path"].read_text())
    assert X.collect(world["pub"], full)["rig-photo"]["variants"][0]["ref"] is None


def test_collect_refuses_a_run_without_a_process_figure(world):
    del world["cfg"]["sensors"]["shared"]["variants"][0]["report"]
    with pytest.raises(RuntimeError, match="rig-groups: process figure missing"):
        X.collect(world["pub"], world["cfg"])


def test_collect_refuses_camera_frames(world):
    cams = F.two_cams()
    (world["root"] / "runs/c/cam_imu_report.html").write_text(F.report_html(cams, frames=True))
    with pytest.raises(RuntimeError, match="holds camera frames"):
        X.collect(world["pub"], world["cfg"])


def _plan(world):
    return X.render(world["pub"], X.collect(world["pub"], world["cfg"]), world["root"] / "media", world["root"] / "photos")


def test_render_plans_every_file_and_leaves_pub_alone(world):
    before = json.dumps(world["pub"], sort_keys=True)
    plan = _plan(world)
    assert json.dumps(world["pub"], sort_keys=True) == before
    assert plan.problems == [] and plan.slugs == ["rig-photo", "rig-groups", "rig-old"]
    assert set(plan.texts) == {
        "site/public/media/sensors/rig-photo/process0.json", "site/public/media/sensors/rig-photo/process1.json",
        "site/public/media/sensors/rig-groups/process0.json", "site/public/media/sensors/rig-old/process0.json",
        *(f"site/src/data/sensors/{s}.json" for s in plan.slugs), *(f"site/src/content/docs/benchmark/sensors/{s}.mdx" for s in plan.slugs),
        "site/src/data/sensor-nav.json", "site/src/content/docs/benchmark/sensors/index.mdx", "site/src/data/sensors/sensor.css",
        "site/src/scripts/sensor-page.js"}
    copies = {rel: src.name for src, rel in plan.copies}
    assert copies == {"site/public/media/sensors/rig-photo/rig.jpg": "rig.jpg",
                      "site/public/media/sensors/rig-photo/demo0.mp4": "clip_a.mp4", "site/public/media/sensors/rig-photo/demo0.jpg": "clip_a.jpg",
                      "site/public/media/sensors/rig-photo/demo1.mp4": "clip_b.mp4", "site/public/media/sensors/rig-photo/demo1.jpg": "clip_b.jpg",
                      "site/public/media/sensors/rig-groups/rig2.jpg": "rig2.jpg",
                      "site/public/media/sensors/rig-groups/demo.mp4": "clip_c.mp4", "site/public/media/sensors/rig-groups/demo.jpg": "clip_c.jpg",
                      "site/public/media/sensors/rig-old/old.jpg": "old.jpg"}
    assert len(plan.copies) == 10  # the old page copies its photo twice: header and lead
    assert plan.clear == [f"site/public/media/sensors/{s}" for s in plan.slugs]


def test_render_page_content(world):
    plan = _plan(world)
    j = json.loads(plan.texts["site/src/data/sensors/rig-photo.json"])
    assert set(j) == {"title", "parts", "rigs", "procs", "plotly", "card"}
    assert "header" in j["parts"] and "specifications" in j["parts"] and "rig" in j["parts"] and "detail" in j["parts"]
    assert "sha256 of the recording: <code>" + X.sha256(world["root"] / "rec.bin") + "</code>" in j["parts"]["run"]
    assert "↗︎" in plan.texts["site/src/data/sensors/rig-photo.json"]  # the text-style arrow, in the data file only
    assert "︎" not in plan.texts["site/src/content/docs/benchmark/sensors/rig-photo.mdx"]
    assert j["procs"] == ["/media/sensors/rig-photo/process0.json", "/media/sensors/rig-photo/process1.json"]
    proc = json.loads(plan.texts["site/public/media/sensors/rig-photo/process0.json"])
    assert set(proc) == {"data", "layout", "spec"} and ", " not in plan.texts["site/public/media/sensors/rig-photo/process0.json"][:200]
    old = json.loads(plan.texts["site/src/data/sensors/rig-old.json"])
    assert "sensorimg" in old["parts"]["lead"] and "sha256" not in old["parts"]["run"] and old["card"]["maker"] is None
    nav = plan.texts["site/src/data/sensor-nav.json"]
    assert nav.endswith("]\n") and [n["group"] for n in json.loads(nav)] == ["Group One", "Group One", "Group Two"]


def test_render_collects_lint_problems_from_every_text(world):
    world["pub"]["groups"][0]["title"] = "Ranked rigs"  # only the sidebar and the overview carry group titles
    world["pub"]["sensors"]["rig-photo"]["lead"] = "The best rig."
    world["pub"]["sensors"]["rig-old"]["description"] = "vendor text"
    collected = X.collect(world["pub"], world["cfg"])
    collected["rig-groups"]["variants"][0]["process"]["spec"]["note"] = "from /home/u/run"
    plan = X.render(world["pub"], collected, world["root"] / "media", world["root"] / "photos")
    assert any(p.startswith("rig-photo: rating") for p in plan.problems)
    assert any(p.startswith("rig-old: maker comparison") for p in plan.problems)
    assert any(p.startswith("rig-groups process: internal path") for p in plan.problems)
    assert any(p.startswith("sidebar: rating: 'Ranked'") for p in plan.problems)


def test_render_ignores_private_text_in_links(world):
    world["pub"]["sensors"]["rig-photo"]["header"]["links"]["product"] = "https://example.com/home/vendor"
    assert _plan(world).problems == []


def test_write_refuses_on_problems_and_writes_nothing(world):
    plan = _plan(world)
    plan.problems = ["x: rating"]
    with pytest.raises(SystemExit, match="nothing written:\nx: rating"):
        X.write(world["site"], plan)
    assert not world["site"].exists()


def test_write_clears_only_exported_media_and_writes_everything(world):
    site = world["site"]
    keep = site / "site/public/media/sensors/plotly-3.0.1.min.js"
    stale = site / "site/public/media/sensors/rig-photo/old-file.json"
    for f in (keep, stale):
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x")
    plan = _plan(world)
    assert X.write(site, plan) == plan.slugs
    assert keep.exists() and not stale.exists()
    for rel, text in plan.texts.items():
        assert (site / rel).read_text(encoding="utf-8") == text
    for src, rel in plan.copies:
        assert (site / rel).read_bytes() == src.read_bytes()


def test_write_refuses_a_path_outside_the_site(world):
    plan = X.Plan(texts={"../escape.txt": "x"})
    with pytest.raises(ValueError, match="outside the site"):
        X.write(world["site"], plan)


def test_main_reads_the_committed_public_text(world, monkeypatch):
    monkeypatch.setattr(X, "public_sensors", lambda: world["pub"])
    monkeypatch.setattr(X, "DATA", world["root"])  # photos/
    assert X.main(world["site"], world["cfg_path"], world["root"] / "media") == ["rig-photo", "rig-groups", "rig-old"]
    assert (world["site"] / "site/src/data/sensors/sensor.css").read_text().startswith("/* Generated by export_sensor.py. */")


def test_main_is_repeatable(world, monkeypatch):
    monkeypatch.setattr(X, "public_sensors", lambda: world["pub"])
    monkeypatch.setattr(X, "DATA", world["root"])  # photos/
    X.main(world["site"], world["cfg_path"], world["root"] / "media")
    first = {p: p.read_bytes() for p in world["site"].rglob("*") if p.is_file()}
    X.main(world["site"], world["cfg_path"], world["root"] / "media")
    assert first == {p: p.read_bytes() for p in world["site"].rglob("*") if p.is_file()}


def test_public_sensors_reads_the_committed_file():
    assert X.public_sensors() == yaml.safe_load((DATA / "public_sensors.yaml").read_text())


@pytest.mark.parametrize("cut", ["header", "image", "file"])
def test_render_needs_a_header_photo_for_the_overview_card(world, cut):
    h = world["pub"]["sensors"]["rig-old"]
    {"header": lambda: h.pop("header"), "image": lambda: h["header"].pop("image"), "file": lambda: h["header"]["image"].pop("file")}[cut]()
    with pytest.raises(ValueError, match="rig-old: needs a header with an image file"):
        _plan(world)


def test_render_takes_demo_file_names_from_the_private_config(world):
    world["cfg"]["sensors"]["shared"]["demo_media"] = {"clip_c": "clip_a"}  # the private file name differs from the public clip name
    copies = {rel: src.name for src, rel in _plan(world).copies}
    assert copies["site/public/media/sensors/rig-groups/demo.mp4"] == "clip_a.mp4" and copies["site/public/media/sensors/rig-groups/demo.jpg"] == "clip_a.jpg"


def test_only_cuts_pub_to_one_sensor_and_refuses_unknown():
    pub = {"data_url": "u", "groups": [], "sensors": {"a": {"t": 1}, "b": {"t": 2}}}
    assert X.only(pub, "b") == {"data_url": "u", "groups": [], "sensors": {"b": {"t": 2}}}
    assert list(pub["sensors"]) == ["a", "b"]
    with pytest.raises(SystemExit):
        X.only(pub, "c")
