import json
import os
import sys
from pathlib import Path

import pytest

import make_fixtures as F
from conftest import env_path
from mvis_site import space as S


@pytest.fixture
def lb(tmp_path):
    return F.write_leaderboard(tmp_path / "lb")


def test_space_imports_fresh_and_undoes_everything(lb, monkeypatch):
    monkeypatch.setenv("CALIBENCH_LOCAL", "/before")
    path = list(sys.path)
    with S.space(lb, lb / "records") as load:
        app = load("app")
        assert os.environ["CALIBENCH_LOCAL"] == str(lb / "records") and app.DATA["families"]["batch"] == "2026-01-01"
        app.READ_FIRST["x"] = 1
    assert os.environ["CALIBENCH_LOCAL"] == "/before" and sys.path == path and "app" not in sys.modules and "gradio" not in sys.modules
    with S.space(lb, lb / "records") as load:
        assert load("app").READ_FIRST == {}  # no patch leaks into the next export


def test_space_keeps_an_unset_env_unset_and_restores_modules(lb, monkeypatch):
    monkeypatch.delenv("CALIBENCH_LOCAL", raising=False)
    sentinel = object()
    monkeypatch.setitem(sys.modules, "app", sentinel)
    with S.space(lb, lb / "records") as load:
        load("app")
    assert "CALIBENCH_LOCAL" not in os.environ and sys.modules["app"] is sentinel


def test_space_without_records_leaves_the_env_alone(lb, monkeypatch):
    monkeypatch.delenv("CALIBENCH_LOCAL", raising=False)
    with S.space(lb) as load:
        assert load("app").DATA["version"] == "?"


def test_a_real_gradio_is_used_when_present(lb):
    (lb / "gradio.py").write_text("class Blocks:\n    def __init__(self, **k): pass\n    def __enter__(self): return self\n    def __exit__(self, *a): pass\nREAL = True\n")
    with S.space(lb, lb / "records") as load:
        load("app")
        assert sys.modules["gradio"].REAL


def test_a_changed_space_is_named(lb):
    (lb / "app.py").write_text((lb / "app.py").read_text().replace("def how_to_read_html", "def how_to_read"))
    with pytest.raises(AttributeError, match=r"app lacks \['how_to_read_html'\]"):
        with S.space(lb, lb / "records") as load:
            load("app")


def test_board_texts_from_the_fake_space(lb):
    board, css = S.board_texts(lb, lb / "records")
    b = json.loads(board)
    assert b["batch"] == "2026-01-01" and b["results_commit"] == "local" and list(b["datasets"]) == ["one", "two"]
    assert "<h2>One</h2>" not in b["datasets"]["one"] and "<h2>keep</h2>" in b["datasets"]["one"] and "/tree/main" in b["datasets"]["one"]
    assert "#lb-tabs" not in css and ":root[data-theme='dark'] .cb" in css


def test_board_results_commit_fills_the_label_and_the_links(lb):
    sha = "0123456789abcdef0123456789abcdef01234567"
    full = json.loads(S.board_texts(lb, lb / "records", sha)[0])
    assert full["results_commit"] == sha[:7] and f"/tree/{sha}" in full["datasets"]["one"] and "/tree/main" not in full["datasets"]["one"]


@pytest.mark.parametrize("commit", ["abc1234", "0123456789ABCDEF0123456789ABCDEF01234567", "0123456789abcdef0123456789abcdef0123456"])
def test_board_refuses_a_results_commit_that_is_not_a_full_sha(lb, commit):
    with pytest.raises(ValueError, match="full 40-hex sha"):
        S.board_texts(lb, lb / "records", commit)


def test_board_refuses_a_results_commit_on_a_hub_read(lb):
    with pytest.raises(ValueError, match="needs records"):
        S.board_texts(lb, None, "0123456789abcdef0123456789abcdef01234567")


def test_board_with_no_commit_at_all(lb, monkeypatch):
    (lb / "app.py").write_text((lb / "app.py").read_text().replace('"version": "local" if d else "?"', '"version": None'))
    assert json.loads(S.board_texts(lb, lb / "records")[0])["results_commit"] == ""


def test_export_board_writes_both_files(lb, tmp_path):
    out = S.export_board(lb, tmp_path / "out", lb / "records")
    assert [p.name for p in out] == ["board.json", "board.css"]
    assert [p.read_text(encoding="utf-8") for p in out] == list(S.board_texts(lb, lb / "records"))


def test_export_board_defaults_to_the_site_data_folder(lb, tmp_path, monkeypatch):
    monkeypatch.setattr(S, "REPO", tmp_path / "repo")
    out = S.export_board(lb, records=lb / "records")
    assert out == [tmp_path / "repo/site/src/data/leaderboard/board.json", tmp_path / "repo/site/src/data/leaderboard/board.css"]


def test_refusals_stop_a_write(lb, tmp_path):
    (lb / "app.py").write_text((lb / "app.py").read_text().replace("<ul><li>", "<ul><li>HF_TOKEN "))
    with pytest.raises(SystemExit, match="found HF_TOKEN"):
        S.export_board(lb, tmp_path / "out", lb / "records")
    assert not (tmp_path / "out").exists()


def test_uzh_from_the_fake_space(lb, tmp_path):
    root = F.write_uzh(tmp_path / "uzh")
    before = set(os.listdir(os.environ.get("TMPDIR", "/tmp")))
    out = S.export_uzh(lb, root / "three_way/three_way_comparison_stats.json", root / "hub_stage/2026-11-04", tmp_path / "uzh.json")
    assert set(os.listdir(os.environ.get("TMPDIR", "/tmp"))) - before == set()  # the records folder is gone
    text = out.read_text()
    assert text.endswith("\n") and list(json.loads(text)) == ["batch", "fragment", "how_to_read"]
    d = json.loads(text)
    assert d["batch"] == "2026-11-04" and "<h2>UZH-FPV</h2>" not in d["fragment"]
    assert S.L.READ_FIRST in d["fragment"] and S.L.LIKE_FOR_LIKE in d["fragment"] and "Run config · MVIS" in d["fragment"]
    assert "here from the calibration UZH ships" in d["how_to_read"]


def test_uzh_from_a_study_folder_finds_its_files(lb, tmp_path, monkeypatch):
    root = F.write_uzh(tmp_path / "uzh")
    want = S.export_uzh(lb, root / "three_way/three_way_comparison_stats.json", root / "hub_stage/2026-11-04", tmp_path / "a.json").read_text()
    assert S.export_uzh_from_root(lb, root, tmp_path / "b.json").read_text() == want
    monkeypatch.setattr(S, "REPO", tmp_path / "repo")
    (tmp_path / "repo/site/src/data/leaderboard").mkdir(parents=True)
    assert S.export_uzh_from_root(lb, root) == tmp_path / "repo/site/src/data/leaderboard/uzh_fpv.json"
    (root / "hub_stage/2026-11-04").rename(root / "hub_stage/other")
    assert S.export_uzh_from_root(lb, root, tmp_path / "c.json", root / "hub_stage/other").read_text() == want


def test_space_modules_are_the_contract_and_gradio():
    assert S.SPACE_MODULES == ("gradio", "app", "export_threeway")


def test_read_hub(tmp_path):
    hub = F.write_uzh(tmp_path / "uzh") / "hub_stage/2026-11-04"
    h = S.read_hub(hub)
    assert h["DAVIS"]["jobs"] == ["davis_indoor_45", "davis_indoor_forward"] and h["SNAP"]["jobs"] == ["snapdragon_indoor_45"]
    assert h["SNAP"]["basalt_status"]["command"][0] == "basalt_calibrate_imu"


def test_records_written_by_the_space_exporter(lb, tmp_path):
    S.write_records(lb, {"families": {"DAVIS": {}, "SNAP": {}}}, "b1", tmp_path / "rec")
    fams = json.loads((tmp_path / "rec/families.json").read_text())
    assert fams["batch"] == "b1" and fams["datasets"] == [{"id": "uzh_fpv", "title": "UZH-FPV", "families": ["DAVIS", "SNAP"]}] and fams["excluded"] == []


@pytest.mark.real_data
def test_the_real_space_has_every_contract_name():
    """app.py reads the Hub at import, so its names are read from the source; export_threeway is imported."""
    import ast
    lb = env_path("MVIS_LEADERBOARD")
    tree = ast.parse((lb / "app.py").read_text())
    top = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)} | {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    assert set(dict(S.CONTRACT)["app"]) <= top
    with S.space(lb) as load:
        load("export_threeway")


@pytest.mark.real_data
def test_the_real_uzh_hub_names_the_eight_bags():
    hub = env_path("MVIS_UZH_ROOT") / "hub_stage/2026-11-04"
    h = S.read_hub(hub)
    assert h["DAVIS"]["jobs"] == [f"davis_{e}_{a}" for e in ("indoor", "outdoor") for a in ("45", "forward")]
    assert h["SNAP"]["jobs"] == [f"snapdragon_{e}_{a}" for e in ("indoor", "outdoor") for a in ("45", "forward")]


def test_fake_space_texts_match_the_golden_files(lb, tmp_path):
    """The public wording of both tables (read-first notes, weights note, how to read) pinned byte for byte.
    After a deliberate change: MVIS_GOLDEN=update python3 -m pytest -q tests/test_space.py, then review the diff."""
    golden = Path(__file__).resolve().parent / "fixtures/golden_space"
    root = F.write_uzh(tmp_path / "uzh")
    board, css = S.board_texts(lb, lb / "records", "0123456789abcdef0123456789abcdef01234567")
    uzh = S.uzh_text(lb, json.loads((root / "three_way/three_way_comparison_stats.json").read_text()), root / "hub_stage/2026-11-04")
    got = {"board.json": board, "board.css": css, "uzh_fpv.json": uzh}
    if os.environ.get("MVIS_GOLDEN") == "update":
        golden.mkdir(parents=True, exist_ok=True)
        for name, text in got.items():
            (golden / name).write_text(text, encoding="utf-8")
    for name, text in got.items():
        assert (golden / name).read_text(encoding="utf-8") == text, f"{name} changed; regenerate with MVIS_GOLDEN=update if that was meant"
