"""Write the t_ga page data (site/src/data/tga/tga.json) from the three-way round-trip runs (stdlib only).

  PYTHONNOUSERSITE=1 python3 site/scripts/export_tga.py \
      --looper-sweep <run>/looper_1/sweep2 --looper-forward <run>/looper_1/cells --looper-suffix "" \
      --t265-sweep <run>/t265_sweep --t265-forward <run>/cells --t265-suffix __april_01 [--out FILE]

--*-sweep    folder with sweep.json: {tau_ms: {M: {td_ms, t_ga_ms, t_ga_sigma_ms, reproj_rms_px},
             K: {td_ms, reproj_mean_px, gyro_err_mean, accel_err_mean}, B: {status, td_ms, reproj_mean_px}}},
             and sweep_scales.json: {scales: {tau_ms: {M|K|B: [gyro x, y, z, accel x, y, z]}}} (IMU scale factors).
             tau is the accel delay injected into the MVIS-corrected bag (accel stored at t = physical accel at t - tau).
--*-forward  folder with the raw-bag solves F_M<suffix> (cam_imu_calib.yaml), F_K<suffix> (input-camchain-imucam.yaml)
             and F_B<suffix> (calibration.json).
--bands      T265 band delays (default: site/scripts/data/tga_t265_bands.json, a checked-in input).

Computed here, so the page never types a number twice: least-squares slopes of each tool's td (Kalibr: mean of
the cameras) and MVIS t_ga against tau, over all tau and over |tau| <= 10 ms; the raw-bag gaps tool - MVIS per
camera; the predicted gap slope x t_ga; each tool's IMU scales as (scale - 1) in %. Sign: t_imu = t_cam + td.
Times in ms. The output is refused if it holds a local path or a word the public-text lint bans.
"""
import argparse
import json
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE.parent / "python"))
from mvis_site import lint  # noqa: E402  (pure stdlib module)

DEVICES = {
    "looper": {"label": "Looper Insight 9", "recording": "looper_1, 66 s, cam0 + cam1, intrinsics free"},
    "t265": {"label": "Intel T265", "recording": "VI-Rig april_01, 80 s window, intrinsics pinned"},
}


def fit(x, y):
    """Least-squares slope and intercept, and the largest residual."""
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    k = sum((a - mx) * (b - my) for a, b in zip(x, y)) / sxx
    c = my - k * mx
    return k, c, max(abs(b - (k * a + c)) for a, b in zip(x, y))


def forward(folder: Path, suffix: str):
    """Raw-bag td per tool, in ms, at full precision."""
    m = (folder / f"F_M{suffix}" / "cam_imu_calib.yaml").read_text(encoding="utf-8")
    k = (folder / f"F_K{suffix}" / "input-camchain-imucam.yaml").read_text(encoding="utf-8")
    b = json.loads((folder / f"F_B{suffix}" / "calibration.json").read_text(encoding="utf-8"))
    num = lambda key, text: [float(v) * 1e3 for v in re.findall(rf"^\s*{key}:\s*(\S+)\s*$", text, re.M)]
    return {
        "mvis_td": num("td", m), "mvis_tga": num("t_ga", m)[0], "mvis_tga_sigma": num("t_ga_sigma", m)[0],
        "kalibr_td": num("timeshift_cam_imu", k), "basalt_td": b["value0"]["cam_time_offset_ns"] * 1e-6,
    }


def device(sweep_dir: Path, fwd_dir: Path, suffix: str):
    s = json.loads((sweep_dir / "sweep.json").read_text(encoding="utf-8"))
    sc = json.loads((sweep_dir / "sweep_scales.json").read_text(encoding="utf-8"))["scales"]
    taus = sorted(s, key=float)
    tau = [float(t) for t in taus]
    col = lambda f: [f(s[t]) for t in taus]
    kal = col(lambda r: sum(r["K"]["td_ms"]) / len(r["K"]["td_ms"]))
    bas = col(lambda r: r["B"]["td_ms"][0])
    tga = col(lambda r: r["M"]["t_ga_ms"])
    near = [i for i, t in enumerate(tau) if abs(t) <= 10]
    sub = lambda v: ([tau[i] for i in near], [v[i] for i in near])
    kk, kb = fit(tau, kal), fit(tau, bas)
    raw = forward(fwd_dir, suffix)
    gap_k = [kt - mt for kt, mt in zip(raw["kalibr_td"], raw["mvis_td"])]
    gap_b = [raw["basalt_td"] - mt for mt in raw["mvis_td"]]
    r3 = lambda v: round(v, 3) if isinstance(v, float) else [r3(a) for a in v]
    r4 = lambda v: round(v, 4) if isinstance(v, float) else [r4(a) for a in v]  # raw values: printed to 2 places
    r2 = lambda v: round(v, 2) if isinstance(v, float) else [r2(a) for a in v]  # gaps: one rounding, from full values
    return {
        "tau": tau,
        "mvis_tga": r3(tga),
        "mvis_tga_sigma": r3(col(lambda r: r["M"]["t_ga_sigma_ms"])),
        "mvis_td": r3(col(lambda r: [float(v) for v in r["M"]["td_ms"]])),
        "kalibr_td": r3(col(lambda r: [float(v) for v in r["K"]["td_ms"]])),
        "kalibr_td_mean": r3(kal),
        "basalt_td": r3(bas),
        "basalt_status": col(lambda r: r["B"]["status"]),
        "kalibr_gyro_err": [round(v, 4) for v in col(lambda r: r["K"]["gyro_err_mean"])],
        "kalibr_accel_err": [round(v, 4) for v in col(lambda r: r["K"]["accel_err_mean"])],
        "reproj": {"mvis_rms_px": col(lambda r: r["M"]["reproj_rms_px"]),
                   "kalibr_mean_px": r3(col(lambda r: r["K"]["reproj_mean_px"])),
                   "basalt_mean_px": r3(col(lambda r: r["B"]["reproj_mean_px"]))},
        "scale_pct": {k: [[round((v - 1) * 100, 4) for v in sc[t][k]] for t in taus] for k in ("M", "K", "B")},
        "slope": {"mvis_tga": r3(fit(tau, tga)[0]), "mvis_tga_max_residual": r3(fit(tau, tga)[2]),
                  "kalibr": r3(kk[0]), "kalibr_near": r3(fit(*sub(kal))[0]),
                  "basalt": r3(kb[0]), "basalt_near": r3(fit(*sub(bas))[0])},
        "raw": {"mvis_td": r4(raw["mvis_td"]), "mvis_tga": r4(raw["mvis_tga"]),
                "mvis_tga_sigma": r4(raw["mvis_tga_sigma"]), "kalibr_td": r3(raw["kalibr_td"]),
                "basalt_td": r3(raw["basalt_td"])},
        "gap": {"kalibr": r2(gap_k), "basalt": r2(gap_b),
                "kalibr_predicted": r2(kk[0] * raw["mvis_tga"]), "basalt_predicted": r2(kb[0] * raw["mvis_tga"])},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for d in DEVICES:
        ap.add_argument(f"--{d}-sweep", type=Path, required=True)
        ap.add_argument(f"--{d}-forward", type=Path, required=True)
        ap.add_argument(f"--{d}-suffix", default="")
    ap.add_argument("--bands", type=Path, default=SITE / "scripts/data/tga_t265_bands.json")
    ap.add_argument("--out", type=Path, default=SITE / "src/data/tga/tga.json")
    a = ap.parse_args(argv)
    out = {"note": "Generated by site/scripts/export_tga.py; do not edit. Times in ms; t_imu = t_cam + td.",
           "devices": {}}
    for d, meta in DEVICES.items():
        g = lambda k: getattr(a, f"{d}_{k}").expanduser()
        out["devices"][d] = {**meta, **device(g("sweep"), g("forward"), getattr(a, f"{d}_suffix"))}
    bands = json.loads(a.bands.read_text(encoding="utf-8"))
    out["t265_bands"] = {k: bands[k] for k in ("bands_hz", "delay_ms", "gain", "uncertain_from_hz")}
    text = json.dumps(out, indent=1, ensure_ascii=False)
    problems = lint.public_problems(lint.process_strings(text)) + lint.refusals(text)
    if problems:
        raise SystemExit("refused: " + "; ".join(problems))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text + "\n", encoding="utf-8")
    return a.out


if __name__ == "__main__":
    print("wrote", main())
