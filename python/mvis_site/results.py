"""Read MVIS run folders: solved values, corner pixels and the process figure without camera frames."""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import numpy as np
import yaml

from .geometry import fov_deg, rotvec


def corner_uv(report: Path) -> list:
    """Corner pixels per camera, from the report's process figure. Empty for a camera without them."""
    t = report.read_text()
    i = t.rindex('mvisProgress("')
    spec, _ = json.JSONDecoder().raw_decode(t[t.index(",", i) + 1:])
    out = []
    for v in spec.get("views", []):
        p = v.get("panel") or {}
        out.append(np.frombuffer(base64.b64decode(p["uvb"]), np.int16).reshape(-1, 2).astype(float) if p.get("uvb") else np.zeros((0, 2)))
    return out


def read_factory(path: Path, results: Path | None = None) -> list[dict]:
    d = yaml.safe_load(path.read_text())
    txt = results.read_text() if results and results.exists() else ""
    out = []
    for name in sorted(k for k in d if k.startswith("cam")):
        c = d[name]
        T = np.array(c["T_cam_imu"], float)
        R_ic = T[:3, :3].T
        m = re.search(rf"Reprojection error \({name}\)[^:]*:\s*mean\s*([\d.]+)", txt)
        intr = list(c["intrinsics"])
        if c.get("camera_model") == "eucm":
            intr = intr[2:6] + intr[:2]
        else:
            intr += list(c["distortion_coeffs"])
        out.append({"name": name, "intr": intr, "p_CinI_mm": (-R_ic @ T[:3, 3] * 1000).tolist(), "rotvec": rotvec(R_ic),
                    "td_ms": c.get("timeshift_cam_imu", 0.0) * 1000, "reproj": float(m.group(1)) if m else None,
                    "size": c["resolution"]})
    return out


def expand_root(tpl: str, roots: dict) -> Path:
    """"{R}/x" with roots {"R": "~/r"} becomes ~/r/x, expanded."""
    for k, v in roots.items():
        tpl = tpl.replace("{" + k + "}", v)
    return Path(tpl).expanduser()


def extract_process(report: Path) -> dict | None:
    """The process figure from a MVIS report, without camera frames: panels removed, image plane blank."""
    if not report.exists():
        return None
    t = report.read_text()
    if "mvisProgress(\"" not in t:
        return None
    i = t.rindex('mvisProgress("')
    j = t.index(",", i)
    pid = t[i + 14:j - 1]
    dec = json.JSONDecoder()
    spec, _ = dec.raw_decode(t[j + 1:])
    k = t.index(f'"{pid}",', t.index("Plotly.newPlot("))
    s = t.index("[", k)
    data, n = dec.raw_decode(t[s:])
    l = t.index("{", s + n)
    layout, _ = dec.raw_decode(t[l:])
    for v in spec.get("views", []):
        v.pop("panel", None)
        if "img" in v:
            v["img"] = base64.b64encode(bytes([128]) * (v["iw"] * v["ih"])).decode()
            v["img_idx"] = [0]
    for tr in data:
        if "surfacecolor" in tr:
            tr["surfacecolor"] = [[128, 128], [128, 128]]
            for ax in "xyz":
                tr[ax] = [[0, 0], [0, 0]]
            tr["visible"] = False
    layout.pop("title", None)
    layout.pop("template", None)
    layout["paper_bgcolor"] = "rgba(0,0,0,0)"
    layout["height"] = None
    layout["autosize"] = True
    layout["margin"] = {"l": 0, "r": 0, "t": 0, "b": 0}
    return {"data": data, "layout": layout, "spec": spec}


def _strings(o):
    if isinstance(o, dict):
        for x in o.values():
            yield from _strings(x)
    elif isinstance(o, list):
        for x in o:
            yield from _strings(x)
    elif isinstance(o, str):
        yield o


def process_has_no_frames(p: dict) -> bool:
    """No JPEG string and no embedded image. Base64 number arrays can contain "/9j/" by chance, so a
    JPEG counts only at the start of a string."""
    if any(s.startswith("/9j/") or "data:image/" in s for s in _strings(p)):
        return False
    return not any("panel" in v for v in p["spec"].get("views", []))


VIEWS_VERSION = 2


def read_views(run_dir: Path) -> dict | None:
    """The run's calibration-process spec for the MVIS canvas player, from `cam_imu_views.json` (written by MVIS
    beside the report, frames already stripped; older runs get it from `mvis.analysis.views.legacy`). None if absent."""
    f = Path(run_dir) / "cam_imu_views.json"
    if not f.exists():
        return None
    scene = json.loads(f.read_text()).get("scene")
    if scene is not None and scene.get("v") != VIEWS_VERSION:
        raise RuntimeError(f"{f}: view spec v{scene.get('v')}, the site knows v{VIEWS_VERSION}")
    return scene


def views_have_no_frames(spec: dict) -> bool:
    """No camera image in a view spec: no image keys, and no string that starts like a JPEG, a PNG or a data URL
    (packed number arrays may contain those letters elsewhere)."""
    if any(k in c for c in spec.get("cams", []) for k in ("jpg", "jpg_idx", "img")):
        return False
    return not any(s.startswith(("/9j/", "iVBOR", "data:image/")) for s in _strings(spec))


def refuse_frames(key: str, variants: list, require_process: bool = True) -> None:
    """Stop before any page is written when a process figure holds camera frames. Public pages also need the figure
    (the canvas views or the older Plotly one); the private pages show older runs without one."""
    for v in variants:
        views, proc = v.get("views"), v["process"]
        if not views and not proc and require_process:
            raise RuntimeError(f"{key}: process figure missing or holds camera frames")
        if views and not views_have_no_frames(views):
            raise RuntimeError(f"{key}: process views hold camera frames")
        if proc and not process_has_no_frames(proc):
            raise RuntimeError(f"{key}: process figure missing or holds camera frames")


def load_variant(v: dict, roots: dict) -> dict:
    d = expand_root(v["run"], roots)
    run = json.loads((d / "cam_imu.json").read_text())
    cal = yaml.safe_load((d / "cam_imu_calib.yaml").read_text())["cameras"]
    sizes = [c["image_size"] for c in cal]
    rd = expand_root(v["readout_run"], roots) if v.get("readout_run") else d
    rcal = yaml.safe_load((rd / "cam_imu_calib.yaml").read_text())["cameras"]
    readout = [c.get("rolling_shutter_readout", 0.0) * 1000 for c in rcal]
    ref = None
    if v.get("ref", {}).get("camchain"):
        r = v["ref"]
        ref = read_factory(expand_root(r["camchain"], roots), expand_root(r["results"], roots) if r.get("results") else None)
    elif v.get("ref", {}).get("json"):
        rr = json.loads((expand_root(v["ref"]["json"], roots) / "cam_imu.json").read_text())
        ref = [{"name": c["name"], "intr": c["intr"], "p_CinI_mm": c["p_CinI_mm"], "rotvec": c["rotvec"], "td_ms": c["td_ms"], "reproj": c["reproj"]} for c in rr["cams"]]
    if ref and v.get("ref", {}).get("order"):
        ref = [ref[i] for i in v["ref"]["order"]]
    uvs = corner_uv(d / "cam_imu_report.html") if v.get("report") else []
    uvs += [np.zeros((0, 2))] * (len(run["cams"]) - len(uvs))
    if v.get("stitched"):  # cameras solved in other pair recordings, chained on through a shared camera
        root = expand_root(v["stitched"], roots)
        st = json.loads((root / "stitched.json").read_text())
        have = {c["name"] for c in run["cams"]}
        for c in st["cams"]:
            if c["name"] in have:
                continue
            pair = json.loads((root / c["pair"] / "cam_imu.json").read_text())["cams"][c["index"]]
            run["cams"].append({**pair, "name": c["name"], "p_CinI_mm": c["p_CinI_mm"], "rotvec": c["rotvec"]})
            uvs.append(corner_uv(root / c["pair"] / "cam_imu_report.html")[c["index"]])
            sizes.append(sizes[0])
            readout.append(0.0)
    proc = extract_process(d / "cam_imu_report.html") if v.get("report") else None
    views = read_views(d) if v.get("report") else None
    fov = [fov_deg(c["intr"], s, u) for c, s, u in zip(run["cams"], sizes, uvs)]
    if v.get("fov_past_fit"):  # the rules let this value through, but it conflicts with a published figure
        fov = [{**f, "h": None, "v": None, "h_ext": True, "v_ext": True} for f in fov]
    return {"label": v["label"], "run": run, "ref": ref, "sizes": sizes, "readout_ms": readout, "process": proc,
            "views": views, "fov": fov}


def load_series(cfg: dict, roots: dict) -> dict | None:
    if not cfg:
        return None
    dirs = []
    for g in cfg["glob"].split(","):
        p = expand_root(g, roots)
        dirs += sorted(p.parent.glob(p.name))
    runs = [json.loads((x / "cam_imu.json").read_text()) for x in dirs]
    return {"label": cfg["label"], "runs": runs}


def load_all_series(cfg, roots: dict) -> list[dict]:
    """A page's repeatability sets: `series` may be one dict or a list. Each stays its own table, never pooled."""
    if not cfg:
        return []
    return [load_series(c, roots) for c in ([cfg] if isinstance(cfg, dict) else cfg)]


def load_sensor(key: str, s: dict, cfg: dict) -> dict:
    roots = cfg["roots"]
    return {"key": key, "meta": s, "variants": [load_variant(v, roots) for v in s["variants"]], "series": load_all_series(s.get("series"), roots)}




SOLVE_KEYS = ("variants", "board", "series", "sha256_of", "demo_media")


def solve_config(cfg: dict) -> dict:
    """The slice of the private sensors.yaml the public export may read: roots, and per sensor its runs (no reference
    columns), board, repeatability sets, the recording to hash and the
    demo clips' file names (demo_media: public clip name to the file stem in the media folder, which may hold a device id). Everything else there is private text."""
    sensors = {}
    for key, s in cfg["sensors"].items():
        keep = {k: s[k] for k in SOLVE_KEYS if k in s}
        keep["variants"] = [{k: x for k, x in v.items() if k != "ref"} for v in s["variants"]]
        sensors[key] = keep
    return {"roots": dict(cfg["roots"]), "sensors": sensors}
