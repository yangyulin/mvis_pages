"""Copy the calibration-motion guide data into site/public/data/calib-motion/ (stdlib only).

  python3 site/scripts/export_calib_motion.py --anim <mira>/slides/mvis/calib-motion-demo/data \
      [--verdicts <dir>/twin_verdicts.json] [--placeholder "text"] [--out DIR] [--variants ID ...]
  python3 site/scripts/export_calib_motion.py --refresh public/data/calib-motion/v4/guide06c_60.json ...
  python3 site/scripts/export_calib_motion.py --cams <solve>/cam_imu/cam_imu_views.json \
      --cams-anim public/data/calib-motion/real_takes/aprilgrid_06.json

Three folders feed the page (each run copies one):
  --anim <data>             --out public/data/calib-motion             AprilGrid twin (bad examples, reference)
  --anim <data>/v3          --out public/data/calib-motion/v3          chessboard twin (guide motion, steps)
  --anim <data>/real_takes  --out public/data/calib-motion/real_takes  real AprilGrid takes (needs --variants,
                                                                       that folder has no index.json)
  --anim <data>/v4          --out public/data/calib-motion/v4          AprilGrid guide motions built from real takes
                                                                       (--variants guide04_60 --verdict-ids ...)

--anim      folder with index.json (or --variants) + <variant>.json (calib-motion-demo/anim v1, written by
            mira scripts/mvis/calib_motion_demo/export_anim.py). Each variant is slimmed for the page: the
            *_cam IMU copies and the internal "description" are dropped, the image outline is rounded to 0.1 px and
            every segment gets its beats (below).
--refresh   recompute the beats of already exported anim files in place (nothing else changes).
--cams      an MVIS cam_imu_views.json of the real take that --cams-anim (an exported anim file) shows: writes the
            camera-card sidecar <variant>.cams.json next to that anim file (schema below).
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

Segment beats (added to every anim segment): unit ("Sweep", "In-out", "Roll", "Loop", "Corner", "Rest" or null),
nbeat (how many of them) and beats = [{t, word, i}], one per half-cycle (or per turn), i = which sweep / in-out /
loop it belongs to (1-based). Half-cycles are the turning points of one value per move, found on the 0.4 s Hann
smoothed value; half-cycles shorter than 0.8 s or under 20 % of the largest swing are merged into their neighbours.
  left-right (role lr)   azimuth of the camera centre round the board centre   going left / going right (operator's)
  up-down (ud)           elevation                                             going up / going down
  back-forth (bf)        distance to the board centre                          coming in / going out
  roll in place (roll)   roll of the camera about its optical axis             rolling one way / rolling back
  loop (circle)          angle of the camera centre in the board plane         one beat per full turn
  corner square (mix)    angle of the optical-axis hit point on the board      one beat per quarter turn (a corner)
  rest                   none                                                  "Count 3"

Camera-card sidecar (calib-motion/cams v1), derived from the views file, never copied raw; 10 Hz steps on the anim
time base (the views and the anim file share the time origin):
  {schema, variant, hz, n, licence, cams: [{name, color, size [w, h], k [fx, fy, cx, cy],
     T_C0_Ck (4x4, m: camera k in cam0 axes), grid [nx, ny] (100 px cells), reach [0/1 per cell: centre within
     fx * 90 deg of the principal point, the anim metric_reach rule with this camera's intrinsics],
     cov100_first [s or null per cell: first detected corner in it, all frames], uv [[u0, v0, du1, dv1, ...] per
     step: integer px of the detected corners of the last frame at that step, the first pair absolute, every later
     pair as the difference to the pair before it], outline [4 corners or null per step],
     n_so_far [detected corners up to the step], dist_cm, off_deg [per step: |n . (c - board centre)| and
     acos(|z_C . n|), the MVIS views readout]}]}
Dropped: ids, any jpg*, anything path-like. Budget per sidecar: 1.0 MB raw, 400 kB gzip.

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
import array
import base64
import bisect
import gzip
import json
import math
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
DROP = ("gyro_cam", "accel_cam", "grav_cam")
INFO = ("duration_matched", "frame_scale", "sigma_ratio_scaled")
LOCAL = ("/home/", "/tmp/", "~/", "Datasets", "openmvis-internal", "results/")
CAMS_HZ, CAMS_RAW_MAX, CAMS_GZ_MAX = 10.0, 1_000_000, 400_000


def slim(d):
    d.pop("description", None)  # internal design notes; the page captions come from calib-motion.js
    s = d["samples"]
    for k in DROP:
        s.pop(k, None)
    s["outline_px"] = [[[round(x, 1), round(y, 1)] for x, y in f] for f in s["outline_px"]]
    m = d.get("metrics") or {}
    d["metrics"] = {k: m[k] for k in ("hand_peaks", "metrics") if k in m}
    add_beats(d)
    return d


def dump(obj, path):
    txt = json.dumps(obj, separators=(",", ":"))
    bad = [m for m in LOCAL if m in txt]
    if bad:
        raise SystemExit(f"{path.name}: local path marker(s) {bad} left in the public JSON")
    path.write_text(txt)
    return path.stat().st_size


# ---------- beats ----------
def quat_R(q):
    w, x, y, z = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]]


def hann(x, hz, win=0.4):
    n = max(1, round(win * hz / 2))
    w = [0.5 + 0.5 * math.cos(math.pi * k / (n + 1)) for k in range(-n, n + 1)]
    out = []
    for i in range(len(x)):
        num = den = 0.0
        for j, wk in zip(range(i - n, i + n + 1), w):
            if 0 <= j < len(x):
                num += wk * x[j]
                den += wk
        out.append(num / den)
    return out


def unwrap(a):
    u = [a[0]]
    for k in range(1, len(a)):
        d = a[k] - a[k - 1]
        u.append(u[-1] + d - 2 * math.pi * round(d / (2 * math.pi)))
    return u


def half_cycles(v, hz, min_s=0.8, min_frac=0.2):
    """Turning points of v (indices, both ends included) after merging short or small half-cycles."""
    sm = hann(v, hz)
    tp, sign = [0], 0
    for k in range(len(sm) - 1):
        sg = 1 if sm[k + 1] > sm[k] else -1
        if sign and sg != sign:
            tp.append(k)
        sign = sg
    tp.append(len(sm) - 1)
    while len(tp) > 2:
        amp = [abs(sm[tp[k + 1]] - sm[tp[k]]) for k in range(len(tp) - 1)]
        big = max(amp) or 1.0
        bad = [k for k in range(len(amp)) if (tp[k + 1] - tp[k]) / hz < min_s or amp[k] < min_frac * big]
        if not bad:
            break
        k = min(bad, key=lambda j: amp[j])
        if k == 0:
            del tp[1]
        elif k == len(amp) - 1:
            del tp[-2]
        else:
            del tp[k:k + 2]
    return sm, tp


WORDS = {"lr": ("going left", "going right"), "ud": ("going up", "going down"),
         "bf": ("going out", "coming in"), "roll": ("rolling one way", "rolling back")}
UNITS = {"lr": "Sweep", "ud": "Sweep", "bf": "In-out", "roll": "Roll", "circle": "Loop", "mix": "Corner"}


def seg_beats(g, s, hz, center):
    role = str(g.get("role") or g.get("name") or "").rstrip("0123456789")
    t0, t1 = g["t0"], g["t1"]
    if role == "rest":
        return {"unit": "Rest", "nbeat": 1, "beats": [{"t": round(t0, 3), "word": "Count 3", "i": 1}]}
    n = len(s["t"])
    i0, i1 = max(0, round(t0 * hz)), min(n - 1, round(t1 * hz))
    if role not in UNITS or i1 - i0 < 4:
        return {"unit": None, "nbeat": 0, "beats": []}
    P = s["p_C"][i0:i1 + 1]
    c = center
    if role in ("circle", "mix"):
        pts = []
        for p, q in zip(P, s["q_wxyz"][i0:i1 + 1]):
            if role == "mix":   # where the optical axis meets the board plane (B z = 0)
                R = quat_R(q)
                z = [R[0][2], R[1][2], R[2][2]]
                lam = -p[2] / z[2] if abs(z[2]) > 1e-6 else 0.0
                pts.append((p[0] + lam * z[0] - c[0], p[1] + lam * z[1] - c[1]))
            else:
                pts.append((p[0] - c[0], p[1] - c[1]))
        u = unwrap([math.atan2(y, x) for x, y in pts])
        per = 2 * math.pi if role == "circle" else math.pi / 2
        total = abs(u[-1] - u[0]) / per
        nb = round(total)
        beats, k = [], 0
        for j in range(len(u)):
            while k < nb and abs(u[j] - u[0]) >= k * per - 1e-9:
                beats.append({"t": round(t0 + j / hz if k else t0, 3), "word": "", "i": k + 1})
                k += 1
        return {"unit": UNITS[role], "nbeat": nb, "beats": beats if nb else []}
    if role == "lr":
        v = [math.atan2(p[0] - c[0], p[2]) for p in P]          # + = B x up = the operator's left
    elif role == "ud":
        v = [-math.atan2(p[1] - c[1], p[2]) for p in P]         # + = up (B y is down)
    elif role == "bf":
        v = [math.dist(p, c) for p in P]                          # + = going out
    else:                                                         # roll about the optical axis
        v = unwrap([math.atan2(quat_R(q)[1][0], quat_R(q)[0][0]) for q in s["q_wxyz"][i0:i1 + 1]])
    sm, tp = half_cycles(v, hz)
    amp = [sm[tp[k + 1]] - sm[tp[k]] for k in range(len(tp) - 1)]
    big = max(abs(a) for a in amp) or 1.0
    total = sum(abs(a) for a in amp)
    nb = max(1, round(total / (2 * big)))      # a sweep / in-out = there and back at the largest swing
    beats, acc = [], 0.0
    for k, a in enumerate(amp):
        i = min(nb, int(acc / (total / nb) + 0.3) + 1)
        beats.append({"t": round(t0 + tp[k] / hz if k else t0, 3), "word": WORDS[role][0 if a > 0 else 1], "i": i})
        acc += abs(a)
    return {"unit": UNITS[role], "nbeat": nb, "beats": beats}


def add_beats(d):
    for g in d["segments"]:
        g.update(seg_beats(g, d["samples"], d["hz"], d["board"]["center"]))
    return d


# ---------- camera-card sidecar ----------
def R9(r):
    return [r[0:3], r[3:6], r[6:9]]


def mv(R, v):
    return [sum(R[i][j] * v[j] for j in range(3)) for i in range(3)]


def mtv(R, v):
    return [sum(R[j][i] * v[j] for j in range(3)) for i in range(3)]


def mm(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def cams_sidecar(views, anim):
    S = views["scene"]
    T, N = S["t"], len(S["t"])
    Rr, Pr = [R9(r) for r in S["R"]], S["xyz"]
    B = S["board"]
    bn = B["normal"]
    l = math.sqrt(sum(x * x for x in bn))
    bn = [x / l for x in bn]
    mean = [sum(p[i] for p in Pr) / N for i in range(3)]
    if sum(bn[i] * (mean[i] - B["center"][i]) for i in range(3)) < 0:
        bn = [-x for x in bn]
    dur = anim["duration_s"]
    n = int(math.floor(dur * CAMS_HZ + 1e-6)) + 1
    step = [min(range(max(0, j - 1), min(N, j + 2)), key=lambda k: abs(T[k] - i / CAMS_HZ))
            for i in range(n) for j in [bisect.bisect_left(T, i / CAMS_HZ)]]
    c0 = S["cams"][0]
    R0, p0 = R9(c0["R"]), c0["p"]
    out = []
    for c in S["cams"]:
        Rc, pc = R9(c["R"]), c["p"]
        uv = array.array("h")
        uv.frombytes(base64.b64decode(c["uvb"]))
        uvo = c["uvo"]
        W, H = c["size"]
        fx, fy, cx, cy = c["k"]
        nx, ny = math.ceil(W / 100), math.ceil(H / 100)
        reach = [int(math.hypot((x + 0.5) * 100 - cx, (y + 0.5) * 100 - cy) < fx * math.radians(90.0))
                 for y in range(ny) for x in range(nx)]
        first = [None] * (nx * ny)
        for k in range(N):
            for q in range(uvo[k], uvo[k + 1], 2):
                cell = min(ny - 1, max(0, uv[q + 1] // 100)) * nx + min(nx - 1, max(0, uv[q] // 100))
                if first[cell] is None:
                    first[cell] = round(T[k], 1)
        # cam k in cam0 axes: T_C0_Ck = T_B_C0^-1 T_B_Ck (B = the views rig body)
        Rk = mm([list(r) for r in zip(*R0)], Rc)
        tk = mtv(R0, [pc[i] - p0[i] for i in range(3)])
        Tk = [[round(Rk[i][j], 6) for j in range(3)] + [round(tk[i], 5)] for i in range(3)] + [[0, 0, 0, 1]]
        uvs, outl, nsf, dist, off = [], [], [], [], []
        for k in step:
            seg = uv[uvo[k]:uvo[k + 1]]
            m = 2 * len(c["ids"][k]) if c.get("ids") else len(seg)
            f = list(seg[len(seg) - m:]) if m <= len(seg) else list(seg)   # m = 0: nothing detected then
            uvs.append(f[:2] + [f[i] - f[i - 2] for i in range(2, len(f))])  # delta coded: about 20 % smaller
            o = c["outline"][k] if c.get("outline") else None
            outl.append([[round(a), round(b)] for a, b in o] if o else None)
            nsf.append(int(c["n"][k]) if c.get("n") else 0)
            Rw = mm(Rr[k], Rc)
            tw = [a + b for a, b in zip(mv(Rr[k], pc), Pr[k])]
            dist.append(round(100 * abs(sum(bn[i] * (tw[i] - B["center"][i]) for i in range(3)))))
            z = [Rw[0][2], Rw[1][2], Rw[2][2]]
            off.append(round(math.degrees(math.acos(min(1.0, abs(sum(z[i] * bn[i] for i in range(3))))))))
        out.append(dict(name=c["name"], color=c["color"], size=[W, H], k=[round(x, 3) for x in c["k"]], T_C0_Ck=Tk,
                        grid=[nx, ny], reach=reach, cov100_first=first, uv=uvs, outline=outl, n_so_far=nsf,
                        dist_cm=dist, off_deg=off))
    return {"schema": "calib-motion/cams v1", "variant": anim["variant"], "hz": CAMS_HZ, "n": n,
            "licence": "CC BY-NC 4.0", "cams": out}


def cov_pct(cam):
    got = sum(1 for r, f in zip(cam["reach"], cam["cov100_first"]) if r and f is not None)
    return 100 * got / max(1, sum(cam["reach"]))


ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--anim", type=Path)
ap.add_argument("--refresh", type=Path, nargs="+")
ap.add_argument("--cams", type=Path)
ap.add_argument("--cams-anim", type=Path)
ap.add_argument("--verdicts", type=Path)
ap.add_argument("--placeholder")
ap.add_argument("--out", type=Path, default=SITE / "public" / "data" / "calib-motion")
ap.add_argument("--variants", nargs="+")
ap.add_argument("--verdict-ids", nargs="+")
a = ap.parse_args()

if a.refresh:
    for f in a.refresh:
        d = add_beats(json.loads(f.read_text()))
        size = dump(d, f)
        print(f"{f.name}: {size / 1e3:.0f} kB,", ", ".join(f"{g['label'].split()[-1]} {g['nbeat']}" for g in d["segments"]))
        ip = f.with_name("index.json")
        if ip.exists():   # the page's real-example table reads length and coverage from the index
            ix = json.loads(ip.read_text())
            for v in ix["variants"]:
                if v["id"] == d["variant"]:
                    v["duration_s"], v["cov_reach"], v["bytes"] = d["duration_s"], d["coverage"]["cov_reach_final"], size
            dump(ix, ip)
    raise SystemExit(0)

if a.cams:
    if not a.cams_anim:
        raise SystemExit("--cams needs --cams-anim (the exported anim file of that take)")
    anim = json.loads(a.cams_anim.read_text())
    side = cams_sidecar(json.loads(a.cams.expanduser().read_text()), anim)
    path = a.cams_anim.with_name(f"{anim['variant']}.cams.json")
    raw = dump(side, path)
    gz = len(gzip.compress(path.read_bytes(), 9))
    print(f"{path.name}: {raw / 1e3:.0f} kB raw, {gz / 1e3:.0f} kB gzip, n {side['n']};",
          ", ".join(f"{c['name']} {cov_pct(c):.0f} %" for c in side["cams"]),
          f"(anim cov_reach {100 * anim['coverage']['cov_reach_final']:.0f} %)")
    if raw > CAMS_RAW_MAX or gz > CAMS_GZ_MAX:
        path.unlink()
        raise SystemExit(f"{path.name}: over the budget ({CAMS_RAW_MAX / 1e3:.0f} kB raw, {CAMS_GZ_MAX / 1e3:.0f} kB gzip)")
    raise SystemExit(0)

if not a.anim:
    raise SystemExit("give --anim, --refresh or --cams")
src, out = a.anim.expanduser(), a.out.expanduser()
out.mkdir(parents=True, exist_ok=True)

if a.variants:
    index = {"variants": []}
    for vid in a.variants:
        d = json.loads((src / f"{vid}.json").read_text())
        index.setdefault("rig", d.get("rig"))
        index.setdefault("hz", d.get("hz"))
        index["variants"].append({k: d.get(k) for k in ("kind", "description", "duration_s")}
                                 | {"id": vid, "file": f"{vid}.json", "cov_reach": d["coverage"]["cov_reach_final"]})
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
