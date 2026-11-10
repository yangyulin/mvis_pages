"""Example pages: the private run map slice, the config as run, the parts, the cards, the lint gate and the writer.
Runs are synthetic (make_fixtures); the committed public_examples.yaml is checked as content."""
import base64
import json
import os
import re

import numpy as np
import pytest
import yaml
from PIL import Image

import make_fixtures as F
from mvis_site import DATA
from mvis_site import export_examples as X
from mvis_site.lint import public_problems


def write_views(d, cams=("cam0", "cam1"), frames=False):
    uv = base64.b64encode(np.array([[100, 100], [200, 120]], np.int16).tobytes()).decode()
    scene = {"v": 2, "t": [0.0, 1.0, 2.5], "unit": "s", "xyz": [[0.1 * k, 0.0, 0.5] for k in range(12)], "R": [],
             "board": {"outline": [[0, 0, 0], [0.3, 0, 0], [0.3, 0.3, 0], [0, 0.3, 0]]},
             "cams": [{"name": c, "uvb": uv, **({"jpg": ["/9j/AA"]} if frames else {})} for c in cams]}
    (d / "cam_imu_views.json").write_text(json.dumps({"scene": scene, "rig": {}}))


CFG = {"mode": "cam-imu", "input": {"format": "ros1", "path": "/data/somewhere/rec_01.bag", "imu_topics": ["/imu0", "/imu1"],
                                    "cache_dir": "/scratch/cache", "window_mode": "motion"},
       "board": {"rows": 2, "cols": 3, "tag_size": 0.088, "tag_spacing": 0.3}, "camera_input": {"path": "/x/y/seed_calib.yaml", "cameras": [{}, {"factor_hz": 4.0}]},
       "solve": {"sigma_g": 0.001, "estimate_t_ga": True}, "estimate": {"camera": {"intrinsics": True}},
       "reference": {"camchain": "/private/ref.yaml"}, "output": {"path": "/deep/out/cam_imu.json"}}


def write_example_run(d, imus=0, config=True, **kw):
    F.write_run(d, report=False, solve_s=125.0, imus=[{"name": f"aux{k}", "p_IsinI_mm": [1.0, 2.0, 3.0], "rotvec": [0.1, 0.0, 0.0], "td_ms": 0.5,
                                                       "t_ga_ms": 0.1, "t_ga_sigma_ms": 0.02} for k in range(imus)], **kw)
    write_views(d)
    if config:
        (d / "config.yaml").write_text(yaml.safe_dump(CFG))
    return d


def pub_doc():
    ref = {"label": "Ref", "source": "Their calibration", "url": "https://example.org/ref",
           "cams": [{"name": "cam0", "p_mm": [-31.0, 2.0, 5.0], "rotvec": [0.02, -0.01, 0.001], "fx": 299.5, "td_ms": 1.0},
                    {"name": "cam1", "p_mm": [32.0, 1.0, 4.0], "rotvec": [0.01, 0.02, 0.0]}], "td_text": "fixed at 0", "notes": ["A note."]}
    base = lambda title, **kw: {"title": title, "nav": title, "description": "D.", "maker": "Maker", "image": {"file": "a.jpg", "alt": "A rig", "credit": "Photo: us"},
                                "clip": "k", "card": {"rig": "R", "format": "ROS1 bag", "shows": "S", "tags": ["2 cameras"]}, "facts": [["Board", "AprilGrid"]],
                                "lead": "L.", "dataset": {"url": "/reference/datasets/a/", "label": "Data page"}, "data": ["One."],
                                "config": {"name": "a.yaml", "why": {"input.imu_topics": "Two IMUs.", "solve.sigma_g": "Measured."}}, **kw}
    return {"steps": [{"name": n, "text": "t."} for n, _ in X.SECTIONS],
            "examples": {"ours": base("Ours", card={"rig": "R", "format": "ROS1 bag", "shows": "S", "tags": ["2 cameras", "2 IMUs"]}, featured=True, ours=True, eval={"slug": "ours", "label": "All runs"},
                                      reference={"none": "No reference."}, reproduce={"batch": "MVIS main, batch X"},
                                      folds=[{"title": "More", "key": "k", "text": "T.", "link": {"url": "/x/", "label": "X"}}]),
                         "theirs": base("Theirs", image={"file": "b.jpg", "alt": "B", "credit": "Photo: them", "url": "https://example.org/b"},
                                        sensor={"url": "/sensors/b/", "label": "B wiki"}, reference=ref,
                                        other={"title": "Other device", "lead": "Second.", "config": {"name": "b2.yaml", "why": {}}, "reference": ref}),
                         "waiting": base("Waiting", reference=ref, eval={"slug": "w", "label": "All"})}}


@pytest.fixture
def world(tmp_path):
    root = tmp_path / "priv"
    write_example_run(root / "ours", imus=1)
    write_example_run(root / "theirs")
    write_example_run(root / "theirs2", config=False)
    (root / "theirs2/config.yaml").write_text(yaml.safe_dump(CFG))
    (root / "waiting").mkdir()
    photos = F.write_photos(tmp_path / "photos", ["a.jpg", "b.jpg"])
    priv = {"roots": {"X": str(root)}, "sensors": {}, "examples": {
        "ours": {"run": "{X}/ours", "config": "{X}/ours/config.yaml", "note": "private text"},
        "theirs": {"run": "{X}/theirs", "other": {"run": "{X}/theirs2", "extra": 1}},
        "waiting": {"run": "{X}/waiting"}}}
    return dict(root=root, photos=photos, priv=priv, cfg=X.example_config(priv), pub=pub_doc(), site=tmp_path / "site")


def _plan(w, have=frozenset()):
    return X.render(w["pub"], X.collect(w["pub"], w["cfg"]), w["photos"], set(have))


# --- private slice and the config --------------------------------------------------------------------------------

def test_example_config_keeps_only_runs_and_configs(world):
    assert world["cfg"]["examples"]["ours"] == {"run": "{X}/ours", "config": "{X}/ours/config.yaml"}
    assert world["cfg"]["examples"]["theirs"]["other"] == {"run": "{X}/theirs2"}
    assert X.example_config({"roots": {}, "sensors": {}}) == {"roots": {}, "examples": {}}


def test_public_config_drops_private_sections_and_cuts_paths():
    t = X.public_config(CFG)
    c = yaml.safe_load(t)
    assert "reference" not in c and "cache_dir" not in c["input"]
    assert c["input"]["path"] == "rec_01.bag" and c["camera_input"]["path"] == "seed_calib.yaml" and c["output"] == {"path": "cam_imu.json"}
    assert "/" not in t.replace("/imu", "")
    mav = X.public_config({"input": {"path": "${D}/looper/1/mav0"}, "camera_input": {}})
    assert yaml.safe_load(mav)["input"]["path"] == "1/mav0"
    assert yaml.safe_load(X.public_config({"input": {"format": "euroc"}})) == {"input": {"format": "euroc"}}


def test_key_lines_and_marks():
    t = X.public_config(CFG)
    where = X.key_lines(t)
    lines = t.splitlines()
    assert lines[where["input.imu_topics"][0] - 1].strip() == "imu_topics:" and len(where["input.imu_topics"]) == 3
    assert len(where["camera_input.cameras"]) == 3 and lines[where["solve.sigma_g"][0] - 1].strip().startswith("sigma_g")
    assert X.marks([2, 3, 4, 7, 9, 10]) == "{2-4,7,9-10}" and X.marks([]) == ""


def test_own_config_needs_exactly_one_candidate(tmp_path):
    (tmp_path / "cam_imu_calib.yaml").write_text("cameras: []\n")
    assert X.own_config(tmp_path) is None
    (tmp_path / "a.yaml").write_text(yaml.safe_dump(CFG))
    assert X.own_config(tmp_path).name == "a.yaml"
    (tmp_path / "b.yaml").write_text(yaml.safe_dump(CFG))
    assert X.own_config(tmp_path) is None
    (tmp_path / "empty.yaml").write_text("")
    assert X.own_config(tmp_path) is None


# --- collect -----------------------------------------------------------------------------------------------------

def test_collect_loads_views_and_config_and_leaves_pending_runs_empty(world):
    c = X.collect(world["pub"], world["cfg"])
    assert c["ours"]["main"]["views"]["v"] == 2 and c["ours"]["main"]["config"]["board"]["tag_size"] == 0.088
    assert c["theirs"]["other"]["config"] == CFG  # found in the run folder
    assert c["waiting"] == {"main": None, "other": None} and c["ours"]["other"] is None
    assert re.fullmatch(r"\d{4}-\d\d-\d\d", c["ours"]["main"]["date"])


def test_collect_needs_a_config_for_a_landed_run(world):
    os.remove(world["root"] / "theirs/config.yaml")
    with pytest.raises(SystemExit, match="no config"):
        X.collect(world["pub"], world["cfg"])


def test_collect_refuses_camera_frames(world):
    write_views(world["root"] / "theirs", frames=True)
    with pytest.raises(RuntimeError, match="camera frames"):
        X.collect(world["pub"], world["cfg"])


# --- render ------------------------------------------------------------------------------------------------------

def test_render_writes_every_example_and_one_map_per_page(world):
    plan = _plan(world)
    assert plan.problems == [] and plan.slugs == ["ours", "theirs", "waiting"]
    for s in plan.slugs:
        page = json.loads(plan.texts[f"{X.EX_DATA}/{s}.json"])
        mdx = plan.texts[f"{X.EX_DOCS}/{s}.mdx"]
        assert mdx.count('part="result"') == 1 and len(page["rigs"]) <= 1
        assert re.findall(r"^## (.+)$", mdx, re.M)[:6] == [h for h, _ in X.SECTIONS] and f"example: {s}\n" in mdx
        assert not re.search(r'"(roll|pitch|yaw|rpy)"', plan.texts[f"{X.EX_DATA}/{s}.json"], re.I)
    ours = json.loads(plan.texts[f"{X.EX_DATA}/ours.json"])
    assert len(ours["rigs"]) == 1 and ours["pending"] == [] and 'data-src="/media/examples/ours/views0.json"' in ours["parts"]["process"]
    assert f"{X.EX_MEDIA}/ours/views0.json" in plan.texts and f"{X.EX_MEDIA}/waiting/views0.json" not in plan.texts


def test_pending_example_has_no_player_map_or_stats(world):
    plan = _plan(world)
    w = json.loads(plan.texts[f"{X.EX_DATA}/waiting.json"])
    assert w["rigs"] == [] and w["pending"] == ["main"] and w["card"]["stats"] == []
    assert "mvv" not in w["parts"]["process"] and "stage" not in w["parts"]["result"] and "waiting for the solve" in w["parts"]["result"]
    assert "comparison table appears with the solve" in w["parts"]["check"]
    mdx = plan.texts[f"{X.EX_DOCS}/waiting.mdx"]
    assert "```yaml" not in mdx and "```bash" not in mdx and "waiting for the solve" in w["parts"]["glance"] and "<svg" not in w["parts"]["dataset"]


def test_config_fence_marks_the_explained_lines(world):
    mdx = _plan(world).texts[f"{X.EX_DOCS}/ours.mdx"]
    fence = re.search(r'```yaml title="a.yaml" (\{[^}]*\})\n(.*?)```', mdx, re.S)
    lines = fence.group(2).splitlines()
    marked = [int(n) for part in fence.group(1)[1:-1].split(",") for n in (range(int(part.split("-")[0]), int(part.split("-")[-1]) + 1))]
    assert {lines[n - 1].strip().split(":")[0] for n in marked} >= {"imu_topics", "sigma_g"}
    assert "```bash title=\"shell\"\nmvis cam-imu -c a.yaml\n```" in mdx


def test_a_note_on_a_missing_config_key_is_a_problem(world):
    world["pub"]["examples"]["ours"]["config"]["why"]["solve.nope"] = "x"
    assert any("solve.nope" in p for p in _plan(world).problems)


def test_header_is_the_sensor_datasheet_with_our_rig_mark_and_links(world):
    plan = _plan(world)
    ours = json.loads(plan.texts[f"{X.EX_DATA}/ours.json"])["parts"]
    th = json.loads(plan.texts[f"{X.EX_DATA}/theirs.json"])["parts"]
    assert "class=ex-ours>Our rig<" in ours["header"] and "ex-ours" not in th["header"]
    assert 'class="sd-btn primary" href="/reference/datasets/a/">Downloads: Data page →' in ours["header"]
    assert 'href="/benchmark/results/">All runs: Results →' in ours["header"] and 'href="/sensors/b/">B wiki →' in th["header"]
    assert "<dt>Board</dt><dd>AprilGrid</dd>" in ours["header"] and 'href="https://example.org/b">Photo: them ↗' in th["header"]
    assert "class=tiles" in ours["glance"] and "/media/hero/hero_k_960.mp4" in ours["glance"]
    assert "AprilGrid 2 × 3" in ours["dataset"] and "Solve window: 2.5 s." in ours["dataset"]
    assert "Run date" in ours["config"] and "MVIS main, batch X" in ours["config"]


def test_results_table_holds_every_sensor_with_rotation_vectors(world):
    ours = json.loads(_plan(world).texts[f"{X.EX_DATA}/ours.json"])
    r = ours["parts"]["result"]
    assert "log(R) rad" in r and "IMU aux0" in r and "Readout" not in r and 'id=rig' in r
    world["root"].joinpath("theirs/cam_imu_calib.yaml").write_text(yaml.safe_dump({"cameras": [{"image_size": F.SIZE, "rolling_shutter_readout": 0.0},
                                                                                              {"image_size": F.SIZE, "rolling_shutter_readout": 0.03}]}))
    th = json.loads(_plan(world).texts[f"{X.EX_DATA}/theirs.json"])["parts"]["result"]
    assert "Readout ms" in th and ">30.00<" in th and ">global<" in th


def test_check_table_differences(world):
    th = json.loads(_plan(world).texts[f"{X.EX_DATA}/theirs.json"])["parts"]
    c = th["check"]
    assert "Δp 1.00 mm" in c and "Δfx +0.50 px" in c and "Δtd +0.500 ms" in c and "fixed at 0" in c and "not given" in c
    assert "A reference, not ground truth" in c and "A note." in c and 'href="https://example.org/ref"' in c
    assert "Other device" not in th["other"] and "Second." in th["other"] and "Δp" in th["other"]
    w = pub_doc()["examples"]["theirs"]["reference"]
    w["cams"][1]["fx"] = None
    assert ">not given<" in X.check_table({**w, "fx_text": "not given"}, X.collect(world["pub"], world["cfg"])["theirs"]["main"])


def test_no_reference_says_so_and_links_the_eval(world):
    ours = json.loads(_plan(world, {"ours"}).texts[f"{X.EX_DATA}/ours.json"])["parts"]
    assert "No published reference" in ours["check"] and 'href="/benchmark/results/ours/"' in ours["check"]
    assert X.check_part({"none": "x"}, None, None) == "<div class=ex-callout><p><b>No published reference.</b> x</p></div>"


def test_eval_link_falls_back_to_results_until_the_page_exists():
    p = {"eval": {"slug": "a", "label": "All"}}
    assert X.eval_link(p, set()) == {"url": "/benchmark/results/", "label": "All: Results"}
    assert X.eval_link(p, {"a"}) == {"url": "/benchmark/results/a/", "label": "All: Dataset eval"}
    assert X.eval_link({}, {"a"}) is None


def test_card_stats_come_from_the_run(world):
    card = json.loads(_plan(world).texts[f"{X.EX_DATA}/ours.json"])["card"]
    assert card["stats"] == [["2 cam · 2 IMU", "sensors"], ["2.5 s", "window"], ["0.21 px", "reproj median"], ["+1.50 ms", "cam0 td"]]
    assert card["featured"] and card["ours"] and card["clip"] == "/media/hero/hero_k_960.mp4" and card["href"] == "/benchmark/examples/ours/"


def test_card_counts_must_match_the_run(world):
    world["pub"]["examples"]["theirs"]["card"]["tags"] = ["3 cameras", "1 IMUs", "Global shutter"]
    probs = _plan(world).problems
    assert "theirs: card says 3 cameras, the run has 2" in probs and not any("1 IMUs" in p for p in probs)
    world["pub"]["examples"]["theirs"]["card"]["tags"] = ["2 IMUs"]
    assert any("2 IMUs" in p for p in _plan(world).problems)


def test_lint_stops_the_export_and_nothing_is_written(world):
    world["pub"]["examples"]["ours"]["data"].append("Saved in /home/someone/x")
    plan = _plan(world)
    assert any("internal path" in p for p in plan.problems)
    with pytest.raises(SystemExit, match="nothing written"):
        X.write(world["site"], plan)
    assert not world["site"].exists()


def test_site_routes_pass_the_lint_but_paths_do_not():
    assert public_problems(X.strip_links('<a href="/benchmark/results/x/">r</a> [a](/benchmark/results/) "link": "/benchmark/results/"')) == []
    assert public_problems(X.strip_links("see results/x")) != []


def test_no_private_path_reaches_any_output(world):
    plan = _plan(world)
    for rel, text in plan.texts.items():
        assert str(world["root"]) not in text and "/scratch/" not in text and "/private/" not in text, rel


def test_nav_and_overview_follow_the_yaml_order(world):
    plan = _plan(world)
    nav = json.loads(plan.texts[X.NAV])
    assert [n["link"] for n in nav] == ["/benchmark/examples/", "/benchmark/examples/ours/", "/benchmark/examples/theirs/", "/benchmark/examples/waiting/"]
    assert '<ExampleGrid slugs={["ours", "theirs", "waiting"]} />' in plan.texts[f"{X.EX_DOCS}/index.mdx"]


def test_main_writes_into_a_site_and_lists_pending(world, monkeypatch, tmp_path):
    priv = tmp_path / "sensors.yaml"
    priv.write_text(yaml.safe_dump(world["priv"]))
    monkeypatch.setattr(X, "public_examples", lambda: world["pub"])
    monkeypatch.setattr(X, "DATA", world["photos"].parent)
    (world["site"] / "site/src/content/docs/benchmark/results").mkdir(parents=True)
    (world["site"] / "site/src/content/docs/benchmark/results/ours.mdx").write_text("x")
    (world["site"] / "site/src/content/docs/benchmark/results/index.mdx").write_text("x")
    assert X.eval_pages(world["site"]) == {"ours"} and X.eval_pages(tmp_path / "none") == set()
    assert X.main(world["site"], priv) == ["ours", "theirs", "waiting"]
    assert (world["site"] / X.EX_MEDIA / "theirs/b.jpg").read_bytes() == b"photo b.jpg"
    assert X.pending(world["site"]) == {"waiting": ["main"]}
    assert '/benchmark/results/ours/' in (world["site"] / X.EX_DATA / "ours.json").read_text()


# --- the committed public data -----------------------------------------------------------------------------------

PUB = X.public_examples()


def test_committed_examples_order_and_featured_rig():
    assert list(PUB["examples"]) == ["virig-4imus-3cams", "tum-vi", "monado", "looper-insight9", "uzh-fpv"]
    assert [s for s, p in PUB["examples"].items() if p.get("featured")] == ["virig-4imus-3cams"]
    assert [s["name"] for s in PUB["steps"]] == [h for h, _ in X.SECTIONS]


@pytest.mark.parametrize("slug", list(PUB["examples"]))
def test_committed_example_has_a_photo_credit_and_clean_text(slug):
    p = PUB["examples"][slug]
    im = Image.open(DATA / "photos" / p["image"]["file"])
    assert im.size == (800, 533) and p["image"]["credit"]
    assert (DATA.parent.parent / "site/public/media/hero" / f"hero_{p['clip']}_960.mp4").exists()
    text = json.dumps(p, ensure_ascii=False)
    assert public_problems(X.strip_links(text)) == [], slug
    assert "six" not in text.lower() and "SA16" not in text


def test_no_photo_carries_gps_exif():
    for f in sorted((DATA / "photos").iterdir()):
        exif = Image.open(f).getexif()
        assert not exif.get_ifd(0x8825) and 0x8825 not in exif, f.name


def test_tum_vi_names_kb4_and_monado_and_uzh_equidistant():
    ex = PUB["examples"]
    assert "kb4" in " ".join(ex["tum-vi"]["data"]) and "equidistant" not in " ".join(ex["tum-vi"]["data"]).replace("pinhole-equidistant", "")
    for s in ("monado", "uzh-fpv"):
        assert "equidistant" in " ".join(ex[s]["data"]) and "kb4" not in " ".join(ex[s]["data"])
    for s, p in ex.items():
        assert "ground truth" not in json.dumps(p) or "not ground truth" in json.dumps(p), s
