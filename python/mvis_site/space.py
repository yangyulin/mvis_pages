"""Adapter to the leaderboard Space (mira tasks/mvis/huggingface/leaderboard): runs its own renderer so the site and
the Space show the same rows. The Space stays the source; this only calls the names in CONTRACT.

Gradio isn't needed to render, so a stub stands in when it is missing. Every import is undone afterwards (sys.path,
sys.modules, CALIBENCH_LOCAL), because the Space modules read their records at import and keep patched globals.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from unittest import mock

import yaml

from . import REPO
from . import leaderboard as L
from .lint import refusals

CONTRACT = (("app", ("load_data", "render_dataset_tab", "how_to_read_html", "READ_FIRST", "READ_MORE", "CSS", "DATA",
                     "merge_family", "delta", "PAIRS", "cell_state", "missing_reason", "DECIMALS", "read_first", "notes")),
            ("export_threeway", ("DATASETS", "EXCLUDED", "OUT", "build", "write")))
SPACE_MODULES = ("gradio", *(m for m, _ in CONTRACT))  # imported fresh each time, then removed


@contextlib.contextmanager
def space(leaderboard_dir: Path, records: Path | None = None):
    """Import the Space fresh from leaderboard_dir; yields a function name -> module. records sets CALIBENCH_LOCAL."""
    saved_path = list(sys.path)
    saved_mods = {m: sys.modules.pop(m) for m in SPACE_MODULES if m in sys.modules}
    saved_env = os.environ.get("CALIBENCH_LOCAL")
    try:
        sys.path.insert(0, str(leaderboard_dir))
        try:
            import gradio  # noqa: F401
        except ImportError:
            sys.modules["gradio"] = mock.MagicMock()
        if records is not None:
            os.environ["CALIBENCH_LOCAL"] = str(records)  # before the import: app loads its records at import

        def load(name):
            __import__(name)
            mod = sys.modules[name]
            missing = [n for m, names in CONTRACT if m == name for n in names if not hasattr(mod, n)]
            if missing:
                raise AttributeError(f"{name} lacks {missing}: the Space changed, update space.CONTRACT and the lib")
            return mod
        yield load
    finally:
        sys.path[:] = saved_path
        for m in SPACE_MODULES:
            sys.modules.pop(m, None)
        sys.modules.update(saved_mods)
        if saved_env is None:
            os.environ.pop("CALIBENCH_LOCAL", None)
        else:
            os.environ["CALIBENCH_LOCAL"] = saved_env


def write_records(leaderboard_dir: Path, stats: dict, batch: str, out: Path) -> None:
    """Leaderboard-style records of one study, written by the Space's own exporter, with only this dataset on the board."""
    with space(leaderboard_dir) as load:
        X = load("export_threeway")
        X.DATASETS = [("uzh_fpv", "uzh", "UZH-FPV", list(L.FAMILIES))]
        X.EXCLUDED = []
        X.OUT = Path(out)
        X.write(X.build(stats), stats, batch)


def read_hub(hub_stage: Path) -> dict:
    """The UZH hub stage files the run-config folds quote, per family."""
    weights = yaml.safe_load((hub_stage / "imu_weights.yaml").read_text())
    out = {}
    for fid in L.FAMILIES:
        jobs = L.jobs_for(weights, fid)
        first = jobs[0]
        out[fid] = dict(jobs=jobs, weights=weights,
                        mvis_file=(hub_stage / "configs" / f"cam_imu_{first}_kalibr_model.yaml").read_text(),
                        kalibr_file=(hub_stage / "kalibr" / first / "imu.yaml").read_text(),
                        basalt_status=json.loads((hub_stage / "basalt" / first / "basalt_status.json").read_text()))
    return out


def _checked(text: str) -> str:
    found = refusals(text)
    if found:
        raise SystemExit(f"refusing to write: found {found[0]}")
    return text


def uzh_text(leaderboard_dir: Path, stats: dict, hub_stage: Path) -> str:
    stats = L.without_repeated_weights_note(L.rekey(stats))
    hub = read_hub(hub_stage)
    with tempfile.TemporaryDirectory(prefix="uzh_site_") as tmp:
        write_records(leaderboard_dir, stats, L.BATCH, Path(tmp))
        with space(leaderboard_dir, Path(tmp)) as load:
            app = load("app")
            data = app.load_data()
            data["run_configs"] = {fid: L.run_configs_html(**hub[fid]) for fid in L.FAMILIES}
            for fid in L.FAMILIES:
                app.READ_FIRST[fid] = L.READ_FIRST
                app.READ_MORE[fid] = L.LIKE_FOR_LIKE
            ds = data["families"]["datasets"][0]
            result = L.uzh_json(L.strip_title(app.render_dataset_tab(data, ds)), L.how_to_read(app.how_to_read_html()))
    return _checked(L.dumps(result))


def export_uzh(leaderboard_dir: Path, stats_file: Path, hub_stage: Path, out: Path) -> Path:
    text = uzh_text(Path(leaderboard_dir), json.loads(Path(stats_file).read_text()), Path(hub_stage))
    Path(out).write_text(text, encoding="utf-8")
    return Path(out)


def export_uzh_from_root(leaderboard_dir: Path, uzh_root: Path, out: Path | None = None, hub_stage: Path | None = None) -> Path:
    """The UZH table from a study folder in its usual layout: three_way/ stats and hub_stage/<batch>/."""
    uzh_root = Path(uzh_root)
    return export_uzh(leaderboard_dir, uzh_root / L.UZH_STATS, hub_stage or uzh_root / "hub_stage" / L.BATCH, out or REPO / L.UZH_FILE)


def _family_rows(app, data, families) -> dict:
    """Per family the Space's merged rows, each tool cell's state and reason, its ◆ differences and its notes."""
    out = {}
    for t in families:
        rows = []
        for r in app.merge_family(data, t):
            cells = {tool: r[tool] and dict(r[tool], state=app.cell_state(tool, r[tool], t),
                                            reason=app.missing_reason(tool, r[tool], t))
                     for tool in ("mvis", "calyx", "kalibr", "basalt")}
            rows.append(dict(r, **cells, deltas={p[0]: app.delta(p[0], r[p[1]], r[p[2]], t) for p in app.PAIRS}))
        out[t] = {"rows": rows, "read_first": app.read_first(t), "notes": [list(n) for n in app.notes(data, t)]}
    return out


def space_rows(leaderboard_dir: Path, records: Path, results_commit: str | None = None) -> dict:
    """What the dataset eval pages take from the Space, so they count ◆ with the board's own code: PAIRS, DECIMALS and
    per family the rows of _family_rows."""
    check_results_commit(records, results_commit)
    with space(Path(leaderboard_dir), Path(records)) as load:
        app = load("app")
        data = app.DATA
        fams = [t for ds in data["families"]["datasets"] for t in ds["families"]]
        return {"pairs": [list(p) for p in app.PAIRS], "decimals": dict(app.DECIMALS),
                "families": _family_rows(app, data, fams)}


def uzh_rows(leaderboard_dir: Path, stats: dict, records_out: Path) -> dict:
    """The same for the UZH-FPV study: its records are written by the Space's exporter to records_out first (as
    uzh_text does), with the UZH read-first text in place of the leaderboard's. stats: already rekeyed, notes cleaned."""
    write_records(leaderboard_dir, stats, L.BATCH, Path(records_out))
    with space(Path(leaderboard_dir), Path(records_out)) as load:
        app = load("app")
        for fid in L.FAMILIES:
            app.READ_FIRST[fid] = L.READ_FIRST
            app.READ_MORE[fid] = L.LIKE_FOR_LIKE
        return {"pairs": [list(p) for p in app.PAIRS], "decimals": dict(app.DECIMALS),
                "families": _family_rows(app, app.DATA, list(L.FAMILIES))}


def board_texts(leaderboard_dir: Path, records: Path | None = None, results_commit: str | None = None) -> tuple[str, str]:
    """(board.json, board.css). Without records the Space reads calibench-vi/results (or CALIBENCH_LOCAL if set).
    results_commit names the snapshot that records holds: the full 40-hex sha, which fills the reported commit and the
    config links alike, so an offline run matches what a Hub read of that commit writes."""
    check_results_commit(records, results_commit)
    with space(Path(leaderboard_dir), records) as load:
        app = load("app")
        data = dict(app.DATA)
        if results_commit:
            data.update(sha=results_commit, version=results_commit[:7])
        tabs = {ds["id"]: L.strip_title(app.render_dataset_tab(data, ds)) for ds in data["families"]["datasets"]}
        board = L.board_json(data["families"]["batch"], data.get("version") or "", app.how_to_read_html(), tabs)
        css = L.site_css(app.CSS)
    return _checked(L.dumps(board)), _checked(css)


def check_results_commit(records: Path | None, results_commit: str | None) -> None:
    """A short sha would label the board with one commit while its links keep the records' own; a Hub read has its own sha."""
    if results_commit is None:
        return
    if records is None:
        raise ValueError("results_commit names a local snapshot, so it needs records")
    if not re.fullmatch(r"[0-9a-f]{40}", results_commit):
        raise ValueError("results_commit must be the full 40-hex sha of the records snapshot")


def export_board(leaderboard_dir: Path, out: Path | None = None, records: Path | None = None, results_commit: str | None = None) -> list[Path]:
    board, css = board_texts(leaderboard_dir, records, results_commit)
    out = Path(out) if out else REPO / L.BOARD_DIR
    out.mkdir(parents=True, exist_ok=True)
    (out / "board.json").write_text(board, encoding="utf-8")
    (out / "board.css").write_text(css, encoding="utf-8")
    return [out / "board.json", out / "board.css"]
