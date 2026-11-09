"""Copy the calibration-motion guide data into site/public/data/calib-motion/ (stdlib only).

  python3 site/scripts/export_calib_motion.py --anim <mira>/slides/mvis/calib-motion-demo/data \
      [--verdicts <dir>/twin_verdicts.json] [--placeholder "text"] [--out DIR] [--variants ID ...]

Three folders feed the page (each run copies one):
  --anim <data>             --out public/data/calib-motion             AprilGrid twin (bad examples, reference)
  --anim <data>/v3          --out public/data/calib-motion/v3          chessboard twin (guide motion, steps)
  --anim <data>/real_takes  --out public/data/calib-motion/real_takes  real AprilGrid takes (needs --variants,
                                                                       that folder has no index.json)
  --anim <data>/v4          --out public/data/calib-motion/v4          AprilGrid guide motions built from real takes
                                                                       (--variants guide04_60 --verdict-ids ...)

--anim      folder with index.json (or --variants) + <variant>.json (calib-motion-demo/anim v1, written by
            mira scripts/mvis/calib_motion_demo/export_anim.py). Each variant is slimmed for the page: the
            *_cam IMU copies and the internal "description" are dropped and the image outline is rounded to 0.1 px.
--verdicts  twin_verdicts.json written by mira scripts/mvis/calib_motion_demo/gate.py
            (schema "calib-motion-demo/twin-verdict v1", "v2" or "v3"). The local results paths ("root", a string
            or, for real takes, a dict of paths) are dropped.
            Default: <anim>/twin_verdicts.json when it exists.
--placeholder  marks the verdicts as not final; the page shows the text above the table.
--variants  variant ids to copy (required when --anim has no index.json); the index is built from the anim files.
--verdict-ids  keep only these variants in the copied twin_verdicts.json (default: all). The reference motion
            (the file's "ref") is always dropped: it is hidden on the page, its sigma is in every params[*].sigma_good.
Information-only fields of the gate (duration_matched, frame_scale, sigma_ratio_scaled, groups) are dropped too:
the page judges by "passed" and the raw sigma_ratio_vs_good only. The output is refused if a local path remains.

twin_verdicts.json, as the page reads it (everything else in the file is ignored):
  schema, rule, rig, seeds, z_max, sigma_ratio_max, rotation  -- header from gate.py
  placeholder (optional str)                                  -- added here
  variants: {<id>: {status: "judged" | "missing", passed, failed_params: [name],
                    n_frames: [int], n_frames_good: [int], worst_sigma_ratio, worst_sigma_param (v3),
                    solves: {s0, s1, s2, nf: bool},
                    params: {<name>: {unit, sigma, sigma_good, sigma_ratio_vs_good, z_max,
                                      nf_err, nf_limit, passed, failed: [reason], rot_norm_only?,
                                      z_seeds?, n_z_over? (v2)}}}}
  v2 and v3 also have per variant reproj_px, reproj_bad (rule (a) check); v2 has groups {duration_matched,
  other_duration}. v3 rule (d) compares raw sigma with the 80 s reference's (no duration match): duration_matched and
  sigma_ratio_scaled are information only and the page does not use them.
  parameter names: R_CI_x/y/z (log(R) rotation vector, cam axes, mrad), lever_x/y/z (mm), td, t_ga (ms),
  gyro_scale_x/y/z, accel_scale_x/y/z (ppm), fx, fy, cx, cy (px), k1..k4.
"""
import argparse
import json
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
DROP = ("gyro_cam", "accel_cam", "grav_cam")
INFO = ("duration_matched", "frame_scale", "sigma_ratio_scaled")
LOCAL = ("/home/", "/tmp/", "~/", "Datasets", "openmvis-internal")


def slim(d):
    d.pop("description", None)  # internal design notes; the page captions come from calib-motion.js
    s = d["samples"]
    for k in DROP:
        s.pop(k, None)
    s["outline_px"] = [[[round(x, 1), round(y, 1)] for x, y in f] for f in s["outline_px"]]
    m = d.get("metrics") or {}
    d["metrics"] = {k: m[k] for k in ("hand_peaks", "metrics") if k in m}
    return d


def dump(obj, path):
    txt = json.dumps(obj, separators=(",", ":"))
    bad = [m for m in LOCAL if m in txt]
    if bad:
        raise SystemExit(f"{path.name}: local path marker(s) {bad} left in the public JSON")
    path.write_text(txt)
    return path.stat().st_size


ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--anim", type=Path, required=True)
ap.add_argument("--verdicts", type=Path)
ap.add_argument("--placeholder")
ap.add_argument("--out", type=Path, default=SITE / "public" / "data" / "calib-motion")
ap.add_argument("--variants", nargs="+")
ap.add_argument("--verdict-ids", nargs="+")
a = ap.parse_args()
src, out = a.anim.expanduser(), a.out.expanduser()
out.mkdir(parents=True, exist_ok=True)

if a.variants:
    index = {"variants": []}
    for vid in a.variants:
        d = json.loads((src / f"{vid}.json").read_text())
        index.setdefault("rig", d.get("rig"))
        index.setdefault("hz", d.get("hz"))
        index["variants"].append({k: d.get(k) for k in ("kind", "description", "duration_s")} | {"id": vid, "file": f"{vid}.json"})
else:
    index = json.loads((src / "index.json").read_text())
for v in index["variants"]:
    v["bytes"] = dump(slim(json.loads((src / v["file"]).read_text())), out / v["file"])
    print(f"{v['file']}: {v['bytes'] / 1e3:.0f} kB")
for v in index["variants"]:
    v.pop("description", None)
dump(index, out / "index.json")

vpath = a.verdicts.expanduser() if a.verdicts else src / "twin_verdicts.json"
if vpath.exists():
    ver = json.loads(vpath.read_text())
    if not str(ver.get("schema", "")).startswith("calib-motion-demo/twin-verdict"):
        raise SystemExit(f"{vpath}: not a gate.py twin_verdicts.json")
    ver.pop("root", None)
    ver.pop("groups", None)
    ver.pop("verdicts", None)
    ref = ver.get("ref")
    keep = set(a.verdict_ids) if a.verdict_ids else None
    ver["variants"] = {k: v for k, v in ver["variants"].items() if k != ref and (keep is None or k in keep)}
    for v in ver["variants"].values():
        for k in INFO:
            v.pop(k, None)
        for r in (v.get("params") or {}).values():
            for k in INFO:
                r.pop(k, None)
    if a.placeholder:
        ver["placeholder"] = a.placeholder
    dump(ver, out / "twin_verdicts.json")
    print("twin_verdicts.json", "(placeholder)" if a.placeholder else "")
else:
    print("no twin_verdicts.json; the page shows 'verdicts pending'")
