"""Tiny synthetic inputs in the formats the lib reads: MVIS run folders and reports, a factory camchain, demo media,
and a fake leaderboard Space. No real result, path or device id appears here; the repo is public.

Every writer takes a target folder, so tests build them in tmp_path.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import numpy as np
import yaml

KB4 = [300.0, 300.0, 320.0, 240.0, 0.01, -0.002, 0.0005, -0.0001]
EUCM = [280.0, 280.0, 320.0, 240.0, 0.6, 1.1]
SIZE = [640, 480]


def cam(name, intr, p, r, td=1.5, reproj=0.25):
    return {"name": name, "intr": list(intr), "p_CinI_mm": list(p), "rotvec": list(r), "td_ms": td, "reproj": reproj}


def run_json(cams, **kw):
    out = {"cams": cams, "t_ga_ms": -2.5, "t_ga_sigma_ms": 0.12, "Dw_diag": [1.01, 0.99, 1.0], "Da_diag": [1.0, 1.02, 0.97],
           "imu_model": "calyx", "reproj_median_px": 0.21}
    out.update(kw)
    return out


def two_cams():
    # cameras look along the IMU's z axis; a small turn keeps the frame derivation honest
    return [cam("cam0", KB4, [-30.0, 2.0, 5.0], [0.02, -0.01, 0.0]), cam("cam1", KB4, [32.0, 1.0, 4.0], [0.01, 0.02, 0.0], td=1.6)]


def uv_corners(intr, rd=0.6, n=4):
    fx, fy, cx, cy = intr[:4]
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.c_[cx + rd * fx * np.cos(a), cy + rd * fy * np.sin(a)].astype(np.int16)


def b64f(a):
    return {"dtype": "f8", "bdata": base64.b64encode(np.asarray(a, "<f8").tobytes()).decode()}


def report_html(cams, pid="mvis-plot-0001", frames=False):
    """An MVIS cam_imu_report.html reduced to what the lib parses: a Plotly figure and its mvisProgress spec.

    Each view carries a panel with a JPEG string and corner pixels (dropped by extract_process), and a small image
    plane (replaced by grey). frames=True leaves a JPEG outside the panel, as a broken report would.
    """
    views = []
    for c in cams:
        uv = uv_corners(c["intr"])
        views.append({"name": c["name"], "panel": {"w": SIZE[0], "h": SIZE[1], "jpg": ["/9j/AAAA"], "uvb": base64.b64encode(uv.tobytes()).decode()},
                      "img": base64.b64encode(bytes(range(12))).decode(), "img_idx": [0, 1], "iw": 4, "ih": 3})
    xyz = [[0.1 * np.cos(t), 0.1 * np.sin(t), 0.5 + 0.01 * t] for t in np.linspace(0, 3, 12)]
    spec = {"done": 11, "cur": 11, "xyz": xyz, "unit": "s", "t": list(range(12)), "views": views}
    if frames:
        spec["leak"] = "/9j/4AAQ"
    data = [{"name": "Board Outline", "type": "scatter3d", "x": b64f([0, 0.3, 0.3, 0, 0, float("nan")]), "y": [0, 0, 0.3, 0.3, 0, 0],
             "z": [0, 0, 0, 0, 0, 0]},
            {"name": "Image", "type": "surface", "surfacecolor": [[1, 2], [3, 4]], "x": [[1, 1], [1, 1]], "y": [[1, 1], [1, 1]], "z": [[1, 1], [1, 1]]},
            {"name": "Path", "type": "scatter3d", "x": [0, 1], "y": [0, 1], "z": [0, 1]}]
    layout = {"title": {"text": "x"}, "template": {}, "height": 600, "scene": {"aspectmode": "data"}}
    return (f'<html><script>var a = "Plotly.newPlot(gd, data)";</script>'
            f'<script>Plotly.newPlot("{pid}", {json.dumps(data)}, {json.dumps(layout)}, {{"responsive": true}})</script>'
            f'<script>mvisProgress("{pid}",{json.dumps(spec)});</script></html>')


def write_run(d: Path, cams=None, report=True, readout=(0.0, 0.0), frames=False, **run_kw) -> Path:
    cams = two_cams() if cams is None else cams
    d.mkdir(parents=True, exist_ok=True)
    (d / "cam_imu.json").write_text(json.dumps(run_json(cams, **run_kw)))
    (d / "cam_imu_calib.yaml").write_text(yaml.safe_dump({"cameras": [{"image_size": SIZE, "rolling_shutter_readout": r} for r in readout[:len(cams)]]}))
    if report:
        (d / "cam_imu_report.html").write_text(report_html(cams, frames=frames))
    return d


def write_camchain(path: Path, models=("pinhole-equi", "eucm")) -> Path:
    """A Kalibr camchain and its results text, one camera per model."""
    chain = {}
    for i, m in enumerate(models):
        T = np.eye(4)
        T[:3, 3] = [0.03 * (1 if i else -1), 0.0, 0.005]
        c = {"camera_model": m, "resolution": SIZE, "T_cam_imu": T.tolist(), "timeshift_cam_imu": 0.0012}
        if m == "eucm":
            c["intrinsics"] = [0.6, 1.1, 280.0, 280.0, 320.0, 240.0]
        else:
            c["intrinsics"] = [300.0, 300.0, 320.0, 240.0]
            c["distortion_coeffs"] = [0.01, -0.002, 0.0005, -0.0001]
        chain[f"cam{i}"] = c
    path.write_text(yaml.safe_dump(chain))
    path.with_suffix(".txt").write_text("Reprojection error (cam0) [px]:     mean 0.215, median 0.2\n")
    return path


def write_series(root: Path, name: str, t_gas) -> str:
    for i, t in enumerate(t_gas):
        write_run(root / f"{name}{i}", report=False, t_ga_ms=t)
    return f"{{X}}/{name}?"


def write_stitched(root: Path) -> Path:
    """A rig whose third camera was solved in a pair recording and chained on."""
    pair = write_run(root / "pair01", cams=[cam("cam0", KB4, [0, 0, 0], [0, 0, 0]), cam("cam2", KB4, [5, 5, 5], [0, 0.1, 0])])
    (root / "stitched.json").write_text(json.dumps({"cams": [{"name": "cam0"}, {"name": "cam2", "pair": pair.name, "index": 1,
                                                                "p_CinI_mm": [0.0, -40.0, 3.0], "rotvec": [0.0, 0.05, 0.0]}]}))
    return root


def write_media(d: Path, names) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    for n in names:
        (d / f"{n}.mp4").write_bytes(b"mp4 " + n.encode())
        (d / f"{n}.jpg").write_bytes(b"jpg " + n.encode())
    return d


def write_photos(d: Path, names) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    for n in names:
        (d / n).write_bytes(b"photo " + n.encode())
    return d


# --- a fake leaderboard Space, with exactly the names space.CONTRACT lists ---------------------------------------
FAKE_APP = '''
import json
import os

import gradio as gr  # stubbed by the lib when absent

READ_FIRST = {}
READ_MORE = {}
CSS = """#lb-tabs button{color:red}
.cb .x{color:blue}
.dark .cb .x{color:white}
main.app{padding:0}
"""
FIXED = "Its camera + IMU runs take intrinsics and baselines as input from an MVIS export, and T7 ELP-L readout is held at 0."


PAIRS = (("mk", "mvis", "kalibr", "MVIS", "− Kalibr"), ("bk", "basalt", "kalibr", "Basalt", "− Kalibr"),
         ("bm", "basalt", "mvis", "Basalt", "− MVIS"))
DECIMALS = {"fx": 2, "td_ms": 3}
NONE = {"value": None, "marked": False, "unequal_n": False, "reason": None}


def load_data():
    d = os.environ.get("CALIBENCH_LOCAL")
    fams = json.load(open(os.path.join(d, "families.json"))) if d else {"batch": "", "datasets": []}
    rows = os.path.join(d, "rows.json") if d else ""
    return {"families": fams, "version": "local" if d else "?", "sha": None, "run_configs": {},
            "rows": json.load(open(rows)) if os.path.exists(rows) else {}}


def merge_family(data, t):
    return [dict(r) for r in data["rows"].get(t, [])]


def cell_state(tool, row, t, N=None):
    return row.get("status") or "ok"


def missing_reason(tool, row, t):
    return "not in one run" if t == "T1" else "no data"


def delta(pair, a, b, t):
    if not a or not b or a.get("med") is None or b.get("med") is None:
        return dict(NONE)
    v = a["med"] - b["med"]
    return {"value": v, "marked": abs(v) > max(a["sd"], b["sd"]), "unequal_n": a["n"] != b["n"], "reason": None}


def read_first(t):
    return READ_FIRST.get(t, "")


def notes(data, t):
    return [("Like for like", READ_MORE[t])] if t in READ_MORE else []


def render_dataset_tab(data, ds):
    link = "main" if not data.get("sha") else data["sha"]
    rows = "".join("<p>%s %s %s %s</p>" % (f, READ_FIRST.get(f, ""), READ_MORE.get(f, ""), "".join((data.get("run_configs") or {}).get(f, {}).values()))
                   for f in ds["families"])
    return '<div class="cb"><h2>%s</h2>%s<a href="/tree/%s">configs</a><h2>keep</h2></div>' % (ds["title"], rows, link)


def how_to_read_html():
    return "<ul><li>" + FIXED + "</li></ul>"


DATA = load_data()
with gr.Blocks() as demo:
    pass
'''

FAKE_THREEWAY = '''
import json
from pathlib import Path

OUT = Path("never-written")
DATASETS = [("a", "a", "A", ["T1"])]
EXCLUDED = ["T9"]


def build(stats):
    return {T: stats["families"][T] for _, _, _, Ts in DATASETS for T in Ts}


def write(results, stats, batch):
    OUT.mkdir(parents=True, exist_ok=True)
    fams = {"batch": batch, "datasets": [{"id": pid, "title": title, "families": Ts} for pid, _, title, Ts in DATASETS],
            "excluded": EXCLUDED, "families": results}
    (OUT / "families.json").write_text(json.dumps(fams))
'''


def write_leaderboard(d: Path, records: bool = True) -> Path:
    """The fake Space, and with records a results snapshot it reads (two datasets) at d/records."""
    d.mkdir(parents=True, exist_ok=True)
    (d / "app.py").write_text(FAKE_APP)
    (d / "export_threeway.py").write_text(FAKE_THREEWAY)
    if records:
        r = d / "records"
        r.mkdir()
        (r / "families.json").write_text(json.dumps({"batch": "2026-01-01", "datasets": [
            {"id": "one", "title": "One", "families": ["T1"]}, {"id": "two", "title": "Two", "families": ["T2"]}]}))
    return d


UZH_JOBS = ["davis_indoor_45", "davis_indoor_forward", "snapdragon_indoor_45"]


def write_uzh(root: Path) -> Path:
    """A UZH study folder: three_way stats and a hub stage, in the layout export_uzh reads."""
    (root / "three_way").mkdir(parents=True)
    note = "All tools use each bag's IMU weights from UZH's Kalibr residuals."
    (root / "three_way/three_way_comparison_stats.json").write_text(json.dumps(
        {"about": "x", "families": {"UD": {"caveat": f"{note} Davis caveat."}, "US": {"caveat": f"Snap {note}"}}}))
    hub = root / "hub_stage/2026-11-04"
    (hub / "configs").mkdir(parents=True)
    weights = {j: {"sigma_g": 1.5e-3 * (i + 1), "sigma_a": 2.5e-2} for i, j in enumerate(UZH_JOBS)}
    weights["other_bag"] = {"sigma_g": 1, "sigma_a": 1}
    (hub / "imu_weights.yaml").write_text(yaml.safe_dump(weights))
    for j in ("davis_indoor_45", "snapdragon_indoor_45"):
        (hub / "configs" / f"cam_imu_{j}_kalibr_model.yaml").write_text(f"input: {j}.bag\n<b>tags</b>\n")
        (hub / "kalibr" / j).mkdir(parents=True)
        (hub / "kalibr" / j / "imu.yaml").write_text("accelerometer_noise_density: 0.025\n")
        (hub / "basalt" / j).mkdir(parents=True)
        (hub / "basalt" / j / "basalt_status.json").write_text(json.dumps({"command": ["basalt_calibrate_imu", "--dataset-path", "x.bag"]}))
    return root


# --- public page text, synthetic: one datasheet page with a photo, one with hand-written spec groups, one in the older layout ----
def key_specs(**over):
    ks = {"cameras": {"v": "2 × 640×480"}, "shutter": {"v": "Global", "tag": "maker", "src": "https://example.com/spec"},
          "fov": {"auto": "fov", "also": {"v": "120° × 90°", "tag": "listing", "src": "https://example.com/listing"}},
          "baseline": {"auto": "baseline"}, "imu": {"v": "400 Hz", "tag": "not_published"}, "output": {"v": "USB", "tag": "supplier"}}
    ks.update(over)
    return ks


def pub_entry(kind="photo"):
    p = {"group": "g1", "title": f"Rig {kind}", "description": "A test rig.", "lead": "Two cameras & an IMU.", "chips": ["2 cameras"],
         "hardware": [["Shutter", "Global", "Maker"], ["Weight", "Not published", "Unknown"], ["Mount", "Clip", "Unknown"], ["Lens", "M12", "Custom"]],
         "dataset": [["Board", "AprilGrid 6×6"]], "folder": "rig/", "method": "Camera + IMU, intrinsics free.",
         "limits": ["One recording.", "No second unit."], "card": {"tags": ["Global shutter", "2 cameras", "400 Hz IMU"]}}
    if kind == "photo":
        p["header"] = {"type": "Stereo module", "foot": "Values from the maker.", "maker": {"name": "Maker Co", "url": "https://example.com"},
                       "image": {"kind": "photo", "file": "rig.jpg", "alt": "The rig", "credit": "Maker Co", "url": "https://example.com/p"},
                       "key_specs": key_specs(), "links": {"product": "https://example.com/p", "more": [{"url": "https://example.com/d", "label": "Docs"}]},
                       "spec_note": "Checked once.", "contact": [{"item": "Email", "v": "sales", "url": "mailto:s@example.com"}, {"item": "Phone", "v": "1"}]}
        p["demo"] = {"by_variant": [{"from": "clip_a", "note": "A"}, {"from": "clip_b", "note": "B"}]}
        p["thanks"] = {"people": [{"name": "A B", "role": "Lab"}], "note": "They recorded it."}
        p["run_labels"] = ["Hand-held", "Arm"]
        p["card"]["name"] = "Rig"
    elif kind == "groups":  # hand-written spec groups, no maker, a key shared with another entry
        p["header"] = {"type": "Head-worn camera", "foot": "Measured.", "image": {"kind": "photo", "file": "rig2.jpg", "alt": "x", "credit": "Ours"},
                       "key_specs": key_specs(cameras={"v": "2", "tag": "dataset"}),
                       "groups": [{"title": "From the dataset", "rows": [{"item": "Rate", "v": "30 Hz", "src": "https://example.com/r"}]}]}
        p["demo"] = {"from": "clip_c", "note": "C"}
        p["key"] = "shared"
    else:
        p["image"] = {"file": "old.jpg", "alt": "Old", "caption": "Old photo"}  # the lead photo, before headers had one
        p["header"] = {"type": "Headset", "foot": "Maker data.", "maker": {"name": "Old Co"}, "image": {"kind": "photo", "file": "old.jpg", "alt": "Old", "credit": "Old Co"},
                       "key_specs": key_specs(fov={"auto": "fov"})}
        p["demo"] = {"existing": "/media/old/demo", "note": "D"}
        p["source"] = "https://example.com/old"
        p["company"] = {"name": "Old Co", "url": "https://example.com/co"}
        p["data_link"] = {"url": "https://example.com/data", "label": "Elsewhere"}
        p["example"] = {"url": "/benchmark/examples/x/", "label": "Example"}
        del p["folder"]
        p["group"] = "g2"
    return p


def pub_doc():
    return {"data_url": "https://example.com/datasets", "groups": [{"id": "g1", "title": "Group One"}, {"id": "g2", "title": "Group Two"}, {"id": "g3", "title": "Empty"}],
            "sensors": {"rig-photo": pub_entry("photo"), "rig-groups": pub_entry("groups"), "rig-old": pub_entry("old")}}


def write_private_config(root: Path) -> Path:
    """Runs for pub_doc(), a sensors.yaml with private fields the export must ignore, and its media and photos."""
    for n in ("a", "b", "c", "d"):
        write_run(root / "runs" / n)
    F_series = write_series(root / "runs", "s", [-1.0, -1.2, -0.8])
    (root / "rec.bin").write_bytes(b"recording")
    board = {"rows": 2, "cols": 2, "tag_mm": 30, "spacing": 0.3}
    cfg = {"roots": {"X": str(root / "runs"), "Y": str(root)}, "sensors": {
        "rig-photo": {"name": "Private name", "board": board, "sha256_of": "{Y}/rec.bin", "series": {"glob": F_series, "label": "3 recordings"},
                      "variants": [{"label": "Take 0123", "run": "{X}/a", "report": True, "ref": {"json": "{X}/b"}},
                                   {"label": "Take 4567", "run": "{X}/b", "report": True}]},
        "shared": {"board": board, "variants": [{"label": "Take 89ab", "run": "{X}/c", "report": True}]},
        "rig-old": {"board": board, "variants": [{"label": "Bag 1", "run": "{X}/d", "report": True, "fov_past_fit": True}]}}}
    p = root / "sensors.yaml"
    p.write_text(yaml.safe_dump(cfg, allow_unicode=True))
    write_media(root / "media", ["clip_a", "clip_b", "clip_c"])
    write_photos(root / "photos", ["rig.jpg", "rig2.jpg", "old.jpg"])
    return p
