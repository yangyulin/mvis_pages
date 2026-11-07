"""repeatability.py on synthetic stats + records that belong together (the exporter's own mapping), plus the gate,
the public check and the golden repeatability.json. After a deliberate output change:
MVIS_GOLDEN=update PYTHONNOUSERSITE=1 python3 -m pytest -q tests/test_repeatability.py, then review the diff."""
import itertools
import json
import math
import os
import statistics
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from conftest import env_path
from mvis_site import REPO
from mvis_site import repeatability as R

BATCH = "2026-01-01"
SHA = "0123456789abcdef0123456789abcdef01234567"
GOLDEN = Path(__file__).resolve().parent / "fixtures/golden_repeatability/repeatability.json"


# ---------------------------------------------------------------- a synthetic stats file and its records
def recs(n, prefix="rec_"):
    return [f"{prefix}{i:02d}" for i in range(n)]


def series(seed, n, sd, mean=10.0):
    return list(mean + sd * np.random.default_rng(seed).standard_normal(n))


def blk(d):
    v = [x for x in (d or {}).values() if x is not None and math.isfinite(x)]
    if not v:
        return None
    return {"med": statistics.median(v), "sd": statistics.stdev(v) if len(v) > 1 else 0.0, "min": min(v), "max": max(v), "n": len(v)}


def row(sensor, key, kind="cmp", mvis=None, kalibr=None, basalt=None, calyx=None, bkind="cmp", names=None):
    """A stats row; tool values are lists over `names` (None = no value) or dicts."""
    def d(x):
        if x is None:
            return {}
        if isinstance(x, dict):
            return x
        return {r: v for r, v in zip(names, x) if v is not None}
    r = {"sensor": sensor, "key": key, "label": key, "unit": "px", "dec": 2, "kind": kind,
         "mvis_all": d(mvis), "mvis": d(mvis), "kalibr": d(kalibr), "basalt": d(basalt), "calyx": d(calyx)}
    r["stats"] = {"mvis_all": blk(r["mvis_all"]), "mvis": blk(r["mvis"]), "kalibr": blk(r["kalibr"]), "calyx": blk(r["calyx"])}
    r["bstats"] = {"basalt_all": blk(r["basalt"]), "basalt": None, "kind": bkind}
    return r


def fam(mode, rows, n):
    return {"mode": "camera only" if mode == "cam" else "camera + IMU", "recs": [{"label": r, "mvis": f"tree/{r}"} for r in recs(n)],
            "rows": rows}


def rnd(x):
    return None if x is None else float(f"{x:.6g}")


def held(row_, method):
    if method == "Kalibr" and row_["kind"] == "fixed":
        return "fixed"
    if method == "Basalt":
        if row_["bstats"]["kind"] == "fixed":
            return "fixed"
        if row_["bstats"]["kind"] == "info":
            return "shown"
    return None


def records_for(stats, datasets, batch=BATCH, skip=()):
    """Records as export_threeway writes them from the stats file."""
    out = {"families": {"batch": batch, "datasets": [{"id": i, "title": t, "families": fs} for i, t, fs in datasets],
                        "families": {T: {"title": f"title {T}", "n_recordings": len(f["recs"])} for T, f in stats["families"].items()}},
           "tools": {t: {} for t in R.TOOLS}}
    files = {"MVIS": ("MVIS", "MVIS (Kalibr IMU model)"), "Kalibr": ("Kalibr",), "Basalt": ("Basalt",)}
    for T, f in stats["families"].items():
        cam = f["mode"] != "camera only"
        for tool, methods in files.items():
            if (tool, T) in skip:
                continue
            ms = {}
            for m in methods:
                rows, nrec = [], 0
                for r in f["rows"]:
                    if r["kind"] == "note":
                        continue
                    st = R.block(r, m, cam)
                    rows.append({"sensor": r["sensor"], "key": r["key"], "label": r["label"], "unit": r["unit"], "kind": r["kind"],
                                 "status": held(r, m) or ("ok" if st else "missing"), "med": rnd(st["med"]) if st else None,
                                 "sd": rnd(st["sd"]) if st else None, "n": st["n"] if st else 0})
                    nrec = max(nrec, st["n"] if st else 0)
                ms[m] = {"n_recordings": nrec, "ran": nrec > 0, "rows": rows}
            out["tools"][tool][T] = {"family": T, "batch": batch, "tool": tool, "methods": ms}
    return out


def world():
    """Families covering every state: decided, tie (both reasons), tie_top, not_separated, too few, input, shown,
    not run, other model, MVIS only, a text note, a constant parameter and unequal n."""
    n8, n4 = recs(8), recs(4)
    tight = lambda s, n=8: series(s, n, 0.1)
    loose = lambda s, n=8: series(s, n, 1.0)
    mid = lambda s, n=8: series(s, n, 0.35)
    fams = {}
    # TA (camera): focal not separated (MVIS < Kalibr decided, Basalt in between at n = 8); distortion tie_top MVIS = Basalt > Kalibr; baseline: Kalibr misses two
    # recordings (unequal n) plus a text note row; readout: tie from noise.
    fams["TA"] = fam("cam", [
        row("cam0 – A", "fx", mvis=tight(1), kalibr=loose(2), basalt=mid(3), names=n8),
        row("cam0 – A", "fy", mvis=tight(4), kalibr=loose(5), basalt=mid(6), names=n8),
        row("cam0 – A", "dist[0]", mvis=tight(7), kalibr=loose(8), basalt=tight(9), names=n8),
        row("cam0 – A", "dist[1]", mvis=tight(10), kalibr=loose(11), basalt=tight(12), names=n8),
        row("cam0 – A", "baseline_mm", mvis=tight(13), kalibr=loose(14)[:6] + [None, None], names=n8),
        row("cam1 – B", "baseline_mm", kind="note", names=n8),
        row("cam0 – A", "tr_ms", mvis=series(15, 8, 1.0), kalibr=series(16, 8, 1.05), names=n8),
        row("cam0 – A", "reproj_median", kind="metric", mvis=tight(17), names=n8),
    ], 8)
    # TB (camera, 16 recordings): focal most MVIS over two; distortion: tie from a small gap;
    # baseline: Kalibr constant (dropped, pair not compared) with Basalt shown only.
    base = series(20, 16, 1.0)
    n16 = recs(16)
    fams["TB"] = fam("cam", [
        row("cam0 – A", "fx", mvis=tight(21, 16), kalibr=loose(22, 16), basalt=series(23, 16, 0.32), names=n16),
        row("cam0 – A", "cx", mvis=tight(24, 16), kalibr=loose(25, 16), basalt=series(26, 16, 0.32), names=n16),
        row("cam0 – A", "dist[0]", mvis=base, kalibr=[10 + 1.15 * (v - 10) for v in base], names=n16),
        row("cam0 – A", "baseline_mm", mvis=tight(27, 16), kalibr=[5.0] * 16, basalt=tight(28, 16), bkind="info", names=n16),
    ], 16)
    # TC (camera+IMU, per-recording seed): camera rows Kalibr input, Basalt not run; td decided with MVIS calyx;
    # gyro with the MVIS Kalibr-IMU-model values; Tg / t_ga rows; an RS camera MVIS only (nok, no Kalibr values);
    # distortion other model (nok with Kalibr values).
    fams["TC"] = fam("camimu", [
        row("cam0 – A", "fx", kind="fixed", mvis=tight(30), calyx=tight(30), kalibr=tight(31), names=n8),
        row("cam0 – A", "dist[0]", kind="nok", mvis=tight(32), calyx=tight(32), kalibr=tight(33), names=n8),
        row("cam0 – A", "td_ms", mvis=tight(34), calyx=tight(35), kalibr=loose(36), names=n8),
        row("cam0 – A", "Dw[0,0]", mvis=tight(37), kalibr=loose(38), names=n8),
        row("cam0 – A", "Tg[0,0]", kind="model", mvis=tight(39), names=n8),
        row("cam0 – A", "t_ga_ms", kind="mvis", mvis=tight(40), names=n8),
        row("cam1 – RS", "tr_ms", kind="nok", mvis=tight(41), calyx=tight(41), names=n8),
        row("cam1 – RS", "td_ms", kind="nok", mvis=tight(43), calyx=tight(43), names=n8),
        row("cam1 – RS", "reproj_median", kind="nok", mvis=tight(42), names=n8),
    ], 8)
    # TD (camera+IMU, single seed, 4 recordings): too few everywhere; Basalt fixed input on a camera row; lever with
    # no value from any tool; accel with one shared recording.
    fams["TD"] = fam("camimu", [
        row("cam0 – A", "fx", kind="fixed", mvis=tight(50, 4), calyx=tight(50, 4), kalibr=tight(51, 4), basalt=tight(52, 4), bkind="fixed", names=n4),
        row("cam0 – A", "td_ms", mvis=tight(53, 4), calyx=tight(54, 4), kalibr=loose(55, 4), basalt=mid(56, 4), names=n4),
        row("cam0 – A", "lever_mm", names=n4),
        row("cam0 – A", "Da[0,0]", mvis=[1.0, None, None, None], kalibr=[None, 2.0, 2.1, None], names=n4),
    ], 4)
    return {"about": "x", "sources": {"x": "/home/x"}, "families": fams}


DATASETS = [("one", "One", ["TA", "TB"]), ("two", "Two", ["TC", "TD"])]
NOT_RUN = {("Basalt", "TC"), ("Basalt", "TD")}


@pytest.fixture(scope="module")
def built():
    stats = world()
    # TD Basalt values exist but its record says not run, like T6: drop them so stats and records still agree.
    for r in stats["families"]["TC"]["rows"]:
        assert not r["basalt"]
    recs_ = records_for(stats, DATASETS, skip={("Basalt", "TC")})
    return stats, recs_, R.build(stats, recs_, BATCH, SHA)


def cell(built, T, g):
    for ds in built[2]["datasets"]:
        for f in ds["families"]:
            if f["id"] == T:
                return f["cells"].get(g)
    raise KeyError(T)


# ---------------------------------------------------------------- the statistic and its test
def brute_p(XA, XB):
    n = XA.shape[1]
    A, B = XA - XA.mean(1, keepdims=True), XB - XB.mean(1, keepdims=True)
    g0 = R.pair_stat(A, B)
    hits = 0
    for s in itertools.product((0, 1), repeat=n):
        s = np.array(s, bool)
        pa, pb = np.where(s, B, A), np.where(s, A, B)
        hits += abs(R.pair_stat(pa, pb)) >= abs(g0) - 1e-12
    return hits / 2 ** n


def test_exact_p_matches_a_direct_enumeration_at_n6():
    rng = np.random.default_rng(0)
    XA, XB = rng.normal(0, 1, (3, 6)), rng.normal(0, 2, (3, 6))
    p, exact = R.perm_p(XA, XB)
    assert exact and p == pytest.approx(brute_p(XA, XB)) and 64 * p == round(64 * p)


@pytest.mark.parametrize("n", [4, 5, 6, 8])
def test_the_smallest_p_is_two_over_two_to_the_n(n):
    rng = np.random.default_rng(n)
    base = rng.normal(0, 1, (2, n))
    p, _ = R.perm_p(base * 0.01, base * 100 + rng.normal(0, 1e-3, (2, n)))
    assert p == pytest.approx(2 / 2 ** n)


def test_above_16_recordings_p_is_sampled_and_the_same_in_every_process():
    rng = np.random.default_rng(1)
    XA, XB = rng.normal(0, 1, (2, 18)), rng.normal(0, 1.5, (2, 18))
    p, exact = R.perm_p(XA, XB, "TX|focal_pp|MVIS|Kalibr")
    assert not exact and 1 / (R.N_RANDOM + 1) <= p <= 1
    code = ("import numpy as np, sys; sys.path.insert(0, %r); from mvis_site import repeatability as R; rng = np.random.default_rng(1); "
            "XA, XB = rng.normal(0, 1, (2, 18)), rng.normal(0, 1.5, (2, 18)); print(repr(R.perm_p(XA, XB, 'TX|focal_pp|MVIS|Kalibr')[0]))") % str(REPO / "python")
    for seed in ("1", "2"):
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=dict(os.environ, PYTHONHASHSEED=seed), check=True)
        assert float(out.stdout) == p


def test_holm_keeps_order_and_is_monotone():
    assert R.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert R.holm([0.5, 0.2]) == pytest.approx([0.5, 0.4])
    assert R.holm([0.9, 0.8, 0.7]) == pytest.approx([1.0, 1.0, 1.0])


def test_interval_contains_r_and_its_edges_match_a_fine_grid():
    rng = np.random.default_rng(3)
    XA, XB = rng.normal(0, 1, (2, 8)), rng.normal(0, 3, (2, 8))
    lo, hi = R.interval(XA, XB)
    r = math.exp(R.pair_stat(XA, XB))
    assert lo < r < hi
    sw = R.Swaps(XA, XB, "")
    g0 = R.pair_stat(XA, XB)
    grid = np.arange(g0, math.log(100), 0.0002)
    first_out = next(c for c in grid if sw.p(c) < R.ALPHA)
    assert abs(math.log(hi) - first_out) < R.TOL + 0.0002


def test_an_end_that_never_crosses_is_not_bounded():
    class Never:
        def p(self, c):
            return 1.0
    assert R._edge(Never(), 0.0, +1) is None and R._edge(Never(), 0.0, -1) is None


def test_leave_one_out_flags_a_single_recording():
    XA = np.array([[0, 0.1, -0.1, 0.05, -0.05, 0.02, 0, 0.01]], float)
    XB = XA * 3
    assert R.loo(XA, XB)
    XB2 = XA.copy()
    XB2[0, 0] = 5.0  # one wild recording makes B look loose
    assert not R.loo(XA, XB2)


@pytest.mark.parametrize("n,p,k,want", [(4, 0.0, 9.0, ("too_few", None)), (8, 0.2, 9.0, ("tie", "noise")),
                                        (8, 0.01, 1.1, ("tie", "small")), (8, 0.01, 2.0, ("tighter", None))])
def test_decide(n, p, k, want):
    assert R.decide(n, p, k) == want


def test_masks_put_the_observed_pattern_first():
    m, exact = R.masks_for(3, "")
    assert exact and m.shape == (8, 3) and not m[0].any()
    m, exact = R.masks_for(17, "a")
    assert not exact and m.shape == (R.N_RANDOM + 1, 17) and not m[0].any()


# ---------------------------------------------------------------- cells on the synthetic world
def test_every_state_appears(built):
    states = {c["state"] for ds in built[2]["datasets"] for f in ds["families"] for c in f["cells"].values()}
    assert states == {"most", "tie_top", "tie", "not_separated", "too_few", "input", "single", "not_compared"}


def test_three_tools_most_and_two_tools_more(built):
    c = cell(built, "TB", "focal_pp")
    assert c["state"] == "most" and c["tools"] == ["MVIS"] and c["over"] == ["Kalibr", "Basalt"] and c["n"] == 16
    assert c["chip"] == "Most repeatable: MVIS" and "Across the same 16 recordings" in c["sentence"] and "(Basalt)" in c["sentence"]
    assert c["aria"].startswith("Focal length + principal point, TB: more repeatable MVIS")
    t = cell(built, "TC", "time_offset")
    assert t["state"] == "most" and t["chip"] == "More repeatable: MVIS" and t["compared"] == ["MVIS", "Kalibr"]
    assert t["variant_line"] == "MVIS here: its default IMU model." and "kalibr_seeded" not in t["caveats"]
    assert len(t["params"]) == 1 and {"tool": "MVIS", "role": "only", "reason": R.NOK_DEFAULT, "rows": 1} in t["excluded"]
    assert all(q["decision"] == "a" and q["ci"][0] < q["R"] < q["ci"][1] and q["loo_stable"] is not None for q in c["pairs"][:2])


def test_tie_top_and_its_words(built):
    c = cell(built, "TA", "distortion")
    assert c["state"] == "tie_top" and c["tools"] == ["MVIS", "Basalt"] and c["over"] == ["Kalibr"]
    assert c["chip"] == "Tie: MVIS = Basalt · both tighter than Kalibr" and "dist_tradeoff" in c["caveats"]
    assert "Both scatter less than Kalibr" in c["sentence"] and c["strip"] == "Distortion MVIS = Basalt"
    assert "tie between MVIS and Basalt" in c["aria"]


def test_tie_from_noise_and_from_a_small_gap(built):
    c = cell(built, "TA", "readout")
    assert c["state"] == "tie" and c["pairs"][0]["tie_reason"] == "noise" and "appears often by chance" in c["sentence"]
    assert c["strip"] == "Readout tie" and c["aria"].endswith("tie, 8 matched recordings.")
    s = cell(built, "TB", "distortion")
    assert s["state"] == "tie" and s["pairs"][0]["tie_reason"] == "small" and "under 20 %" in s["sentence"]
    assert s["pairs"][0]["p"] < 0.05 and s["k"] is None


def test_not_separated(built):
    c = cell(built, "TA", "focal_pp")
    assert c["state"] == "not_separated" and c["tools"] == [] and "MVIS is tighter than Kalibr" in c["sentence"]
    assert c["strip"] == "Focal + pp not separated"


def test_unequal_n_is_matched_and_stays_visible(built):
    c = cell(built, "TA", "baseline")
    assert c["n"] == 6 and c["n_all"] == {"MVIS": 8, "Kalibr": 6}
    p = c["params"][0]
    assert p["published"]["MVIS"]["n"] == 8 and p["published"]["Kalibr"]["n"] == 6
    assert {"tool": "all", "role": "note", "reason": R.NOTE_REASON, "rows": 1} in c["excluded"]


def test_a_constant_parameter_is_dropped_and_shown_only_is_listed(built):
    c = cell(built, "TB", "baseline")
    assert c["state"] == "not_compared" and c["reason"].startswith("no parameter varies")
    assert c["dropped"] == [{"tool": "Kalibr", "sensor": "cam0 – A", "key": "baseline_mm", "reason": "constant over recordings"}]
    assert any(e["tool"] == "Basalt" and e["role"] == "shown" for e in c["excluded"])
    assert c["params"][0]["sd"]["Kalibr"] is None


def test_input_rows_leave_the_comparison(built):
    c = cell(built, "TC", "focal_pp")
    assert c["state"] == "input" and c["chip"] == "Input, not compared" and "for each recording" in c["reason"]
    assert {e["role"] for e in c["excluded"]} == {"input", "not_run"} and c["n"] == 0 and c["pairs"] == []
    d = cell(built, "TD", "focal_pp")
    assert d["state"] == "input" and {e["tool"] for e in d["excluded"] if e["role"] == "input"} == {"Kalibr", "Basalt"}
    assert "one MVIS export used for all recordings" in R.input_reason("T9", "Kalibr")


def test_other_model_mvis_only_and_no_values(built):
    assert cell(built, "TC", "distortion")["state"] == "not_compared"
    r = cell(built, "TC", "readout")
    assert r["state"] == "single" and r["tools"] == ["MVIS"] and r["chip"] == "MVIS only" and r["strip"] is None
    assert r["reason"].startswith("MVIS only: ")
    lever = cell(built, "TD", "lever")
    assert lever["state"] == "not_compared" and lever["reason"] == R.MISSING_DEFAULT


def test_kalibr_imu_model_for_gyro(built):
    c = cell(built, "TC", "gyro")
    assert c["mvis_variant"] == "kalibr_imu" and "kimu" in c["caveats"] and c["strip"] == "Gyro MVIS K-IMU"
    assert c["variant_line"].endswith("(K-IMU).")


def test_too_few(built):
    c = cell(built, "TD", "time_offset")
    assert c["state"] == "too_few" and c["n"] == 4 and c["chip"] == "Too few recordings (n = 4)"
    assert all(q["decision"] == "too_few" and q["ci"] is None for q in c["pairs"]) and "smallest possible p is 0.12" in c["sentence"]
    assert c["strip"] is None and c["aria"].endswith("too few recordings (n = 4), 4 matched recordings.")
    a = cell(built, "TD", "accel")
    assert a["n"] == 0 and a["state"] == "too_few" and "cannot be computed" in a["sentence"]
    assert a["dropped"][0]["reason"] == "fewer than 2 shared recordings" and a["pairs"][0]["decision"] == "not_compared"


def test_family_lines(built):
    ds = built[2]["datasets"]
    tc = ds[1]["families"][0]
    assert tc["recordings"]["Basalt"] == {"n": 0, "of": 8, "reason": R.NOT_RUN_DEFAULT} and tc["fold_index"] == 0
    whats = {x["what"] for x in tc["not_part"]}
    assert {"IMU g-sensitivity Tg", "gyro–accel delay t_ga", "distortion coefficients of A", "reproj_median of RS"} <= whats
    assert ds[0]["groups"] == ["focal_pp", "distortion", "baseline", "readout"] and ds[0]["label"] == "One"
    assert built[2]["batch"] == BATCH and built[2]["results_commit"] == SHA


def test_a_family_without_any_pair_has_no_matched_n():
    stats = {"families": {"TZ": fam("cam", [row("cam0 – A", "fx", mvis=[1.0, 2.0], names=recs(2))], 2)}}
    rec = records_for(stats, [("z", "Z", ["TZ"])])
    f = R.build(stats, rec, BATCH, SHA)["datasets"][0]["families"][0]
    assert f["n_matched"] is None and f["cells"]["focal_pp"]["state"] == "single"


def test_lone_states():
    assert R._lone([], [], set(), True) == {"state": "not_compared", "reason": R.NOTE_REASON}
    s = R._lone([{}], ["MVIS"], {("Kalibr", "missing", "gone")}, False)
    assert s == {"state": "single", "tools": ["MVIS"], "reason": "MVIS only: gone"}


def test_role_reasons():
    r = row("cam0 – A", "baseline_mm", mvis=[1.0, 2.0], names=recs(2))
    ran = {t: True for t in R.TOOLS}
    assert R.role("T6c", {"mode": "camera only"}, r, "Basalt", ran, "baseline") == ("missing", "not in one run")
    assert R.role("T6", {"mode": "camera + IMU"}, r, "Basalt", dict(ran, Basalt=False), "baseline") == ("not_run", R.NOT_RUN["T6"])
    nok = dict(r, kind="nok")
    assert R.role("T8", {"mode": "camera + IMU"}, nok, "Kalibr", ran, "baseline") == ("missing", R.NOK_REASON["T8"])


@pytest.mark.parametrize("k,text", [(25.4, "25"), (3.62, "3.6"), (1.02, "1.02")])
def test_fmt_k(k, text):
    assert R.fmt_k(k) == text


def test_small_formats():
    assert R.fmt_pct(0.002) == "0.2 %" and R.fmt_pct(0.25) == "25 %" and R.join_and(["a", "b", "c"]) == "a, b and c"
    assert R.variant_line("T6c", False, "focal_pp").startswith("MVIS here: the camera values")
    assert R.variant_line("T1", False, "focal_pp") == "MVIS here: its camera-only run."


def test_verdict_without_a_three_tool_top():
    pairs = [{"a": "MVIS", "b": "Kalibr", "decision": "a", "k": 2.0}, {"a": "MVIS", "b": "Basalt", "decision": "tie", "k": 1.1},
             {"a": "Kalibr", "b": "Basalt", "decision": "tie", "k": 1.1}]
    assert R.verdict(["MVIS", "Kalibr", "Basalt"], pairs, 8)["state"] == "not_separated"
    assert R.verdict(["MVIS", "Kalibr"], [dict(pairs[0], decision="b")], 8) == {"state": "most", "tools": ["Kalibr"], "over": ["MVIS"], "k": 2.0}


def test_caveat_rules_name_real_families_and_groups():
    board = {"T1", "T2", "T3", "T4", "T5", "T6", "T6c", "T7", "T8", "T9", "T10", "T11", "T12"}
    groups = {g for g, *_ in R.GROUPS}
    for cid, fams, gs, _ in R.CAVEAT_RULES:
        assert cid in R.CAVEATS and set(gs) <= groups
        assert fams in (None, "camimu") or set(fams) <= board
    assert set(R.NOK_REASON) | set(R.NOT_RUN) | set(R.SHOWN) | set(R.SINGLE_SEED) <= board


# ---------------------------------------------------------------- the gate
def test_gate_passes_on_records_of_the_same_stats(built):
    assert R.gate(built[0], built[1], BATCH) == []


def test_gate_refuses_an_sd_off_by_1e6(built):
    stats, rec, _ = built
    rec = json.loads(json.dumps(rec))
    r = rec["tools"]["Kalibr"]["TA"]["methods"]["Kalibr"]["rows"][0]
    r["sd"] = r["sd"] * (1 + 1e-6)
    with pytest.raises(SystemExit, match=r"\(TA, cam0 – A, fx, Kalibr\)"):
        R.build(stats, rec, BATCH, SHA)


def test_gate_refuses_a_stats_file_of_another_batch(built):
    stats, rec, _ = built
    other = world()
    for r in other["families"]["TA"]["rows"]:
        if r["kalibr"]:
            r["kalibr"] = {k: v + 0.5 * i for i, (k, v) in enumerate(r["kalibr"].items())}
            r["stats"]["kalibr"] = blk(r["kalibr"])
    assert any("TA" in p and "Kalibr" in p for p in R.gate(other, rec, BATCH))
    assert any("not 2026-02-02" in p for p in R.gate(stats, rec, "2026-02-02"))


def test_gate_names_what_it_cannot_check(built):
    stats, rec, _ = built
    s = json.loads(json.dumps(stats))
    del s["families"]["TD"]
    s["families"]["TA"]["rows"] = [r for r in s["families"]["TA"]["rows"] if r["key"] != "fy"]
    del s["families"]["TB"]["rows"][0]["calyx"]
    s["families"]["TB"]["rows"][0]["stats"]["calyx"] = {"med": 1, "sd": 1, "n": 3}
    s["families"]["TB"]["rows"][1]["stats"]["mvis"] = {"med": 1, "sd": 1, "n": 16}
    out = R.gate(s, rec, BATCH)
    assert "TD: not in the stats file" in out and any("fy, MVIS): no stats row" in p for p in out)
    assert any("no per-recording dict" in p for p in out) and any("block is not its per-recording values" in p for p in out)


def test_block_maps_like_the_exporter():
    r = {"stats": {"calyx": 1, "mvis_all": 2, "kalibr": 3}, "bstats": {"basalt_all": None, "basalt": 4}}
    assert [R.block(r, m, True) for m in ("MVIS", "MVIS (Kalibr IMU model)", "Kalibr", "Basalt")] == [1, 2, 3, 4]
    assert R.block(r, "MVIS", False) == 2


# ---------------------------------------------------------------- what may be written
def test_the_output_is_public(built):
    stats, _, b = built
    text = R.dumps(b)
    assert R.check_public(text, SHA, R.private_words(stats)) == []
    assert "rec_0" not in text and "tree/" not in text and '"recs"' not in text


@pytest.mark.parametrize("plant,why", [("/home/someone/x", "refused: /home/"), ("the best tool", "rating"),
                                       ("no overall ranking", "rating"), ("rec_03", "private name")])
def test_planted_words_are_refused(built, plant, why):
    stats, _, b = built
    b = json.loads(json.dumps(b))
    b["caveats"]["dist_tradeoff"] = plant
    found = R.check_public(R.dumps(b), SHA, R.private_words(stats))
    assert any(why in f for f in found)


def test_private_keys_and_per_recording_arrays_are_refused():
    found = R.check_public(json.dumps({"recs": 1, "x": [1.0, 2.0, 3.0]}), SHA)
    assert "private key: recs" in found and "per-recording array" in found


def test_private_words_leave_out_plain_names():
    s = {"families": {"T": {"recs": [{"label": "cam1"}, {"label": "stereo01"}, {"label": "a_b", "mvis": "t/x"}], "rows": [{"kalibr": {"bag2": 1}}]}}}
    assert R.private_words(s) == ("a_b", "stereo01", "t/x")


def test_export_writes_and_refuses(built, tmp_path, monkeypatch):
    stats, rec, b = built
    root = tmp_path / "records"
    (root).mkdir()
    (root / "families.json").write_text(json.dumps(rec["families"]))
    for tool, per in rec["tools"].items():
        for T, r in per.items():
            (root / tool / BATCH).mkdir(parents=True, exist_ok=True)
            (root / tool / BATCH / f"{T}.json").write_text(json.dumps(r))
    sf = tmp_path / "stats.json"
    sf.write_text(json.dumps(stats))
    app = tmp_path / "app.py"
    app.write_text("X = 1\nGROUPS = %r\n" % {**R.APP_GROUP, "reproj_median": 4})
    out = R.export(sf, root, BATCH, SHA, tmp_path / "o/rep.json", app)
    assert json.loads(out.read_text()) == json.loads(R.dumps(b))
    assert R.load_records(root, BATCH)["tools"]["Basalt"].get("TC") is None
    with pytest.raises(ValueError, match="full 40-hex"):
        R.export(sf, root, BATCH, "abc1234", tmp_path / "x.json")
    app.write_text("GROUPS = {'fx': 1}\n")
    with pytest.raises(SystemExit, match="GROUPS changed"):
        R.export(sf, root, BATCH, SHA, tmp_path / "x.json", app)
    app.write_text("OTHER = 1\n")
    with pytest.raises(ValueError, match="no GROUPS"):
        R.export(sf, root, BATCH, SHA, tmp_path / "x.json", app)
    monkeypatch.setitem(R.CAVEATS, "kimu", "the best")
    with pytest.raises(SystemExit, match="refusing to write"):
        R.export(sf, root, BATCH, SHA, tmp_path / "x.json")


def test_golden_repeatability_json(built):
    text = R.dumps(built[2])
    if os.environ.get("MVIS_GOLDEN") == "update":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(text, encoding="utf-8")
    assert GOLDEN.read_text(encoding="utf-8") == text, "repeatability.json changed; regenerate with MVIS_GOLDEN=update if that was meant"


# ---------------------------------------------------------------- the committed site data
def test_each_fragment_has_one_family_fold_per_family_in_the_json():
    board = json.loads((REPO / "site/src/data/leaderboard/board.json").read_text())
    rep = json.loads((REPO / "site/src/data/leaderboard/repeatability.json").read_text())
    for ds in rep["datasets"]:
        html = board["datasets"][ds["id"]]
        assert len(__import__("re").findall(r"<details[^>]*class=[\"']fam[\" ]", html)) == len(ds["families"])


@pytest.mark.real_data
def test_the_space_groups_match():
    app = env_path("MVIS_LEADERBOARD") / "app.py"
    assert R.check_groups(R.app_groups(app)) == []
