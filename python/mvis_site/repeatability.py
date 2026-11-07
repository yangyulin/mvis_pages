"""Repeatability across recordings for the results page: per family and group of parameters, which tool's estimates
scatter less over the recordings every compared tool ran. Pure: dicts in, a dict out (repeatability.json).

No accuracy is claimed and nothing is summed across cells. The private per-recording stats file is read only to derive
spreads on matched recordings; no recording label, per-recording value or path leaves this module (`check_public`).

Method (one cell = one family x one group):
  roles      each tool on each row: compared, input (a value the tool was given), shown, not_run, missing, other_model, only
  matched    M = recordings with a finite value for every compared (tool, row) of the cell
  pair_stat  G = median over shared parameters of ln(sd_A / sd_B) on M; R = exp(G); k = exp(|G|)
  perm_p     paired label swap: swap A and B per recording (all parameters at once), centred per tool
  holm       within the cell; a tool is tighter if p_Holm < 0.05 and k >= 1.25, else a tie; n < 6 is too few
  interval   95 % test-inversion interval of R (not adjusted), loo = leave-one-recording-out diagnostic
"""
from __future__ import annotations

import ast
import hashlib
import itertools
import json
import math
import re
import statistics
from pathlib import Path

import numpy as np

from .lint import public_problems, refusals

VERSION = 1
TOOLS = ("MVIS", "Kalibr", "Basalt")
SHAPES = {"MVIS": "circle", "Kalibr": "square", "Basalt": "triangle"}
ALPHA, MIN_RATIO, MIN_N = 0.05, 1.25, 6
EXACT_MAX, N_RANDOM = 16, 65536
LN_MAX, STEP, TOL = math.log(100), 0.05, 0.001
METHOD = {"spread": "sample_sd_ddof1", "pair": "median_log_sd_ratio", "test": "paired_label_swap", "exact": True,
          "adjust": "holm_within_cell", "alpha": ALPHA, "min_ratio": MIN_RATIO, "min_n": MIN_N,
          "interval": "test_inversion_95_unadjusted"}

# id, page label, unit, key bases
GROUPS = (("focal_pp", "Focal length + principal point", "px", ("fx", "fy", "cx", "cy")),
          ("distortion", "Distortion coefficients", "", ("dist",)),
          ("baseline", "Camera–camera distance", "mm", ("baseline_mm",)),
          ("readout", "Rolling-shutter readout", "ms", ("tr_ms",)),
          ("time_offset", "Camera–IMU time offset", "ms", ("td_ms",)),
          ("lever", "Camera–IMU distance", "mm", ("lever_mm",)),
          ("gyro", "Gyro scale + cross-axis", "", ("Dw",)),
          ("accel", "Accel scale", "", ("Da",)))
GROUP_OF = {k: g for g, _, _, keys in GROUPS for k in keys}
LABEL = {g: label for g, label, _, _ in GROUPS}
SHORT = {"focal_pp": "Focal + pp", "distortion": "Distortion", "baseline": "Distance", "readout": "Readout",
         "time_offset": "Time offset", "lever": "Cam–IMU distance", "gyro": "Gyro", "accel": "Accel"}
IMU_GROUPS = ("gyro", "accel")
# The Space's table rule groups (app.GROUPS) of the same keys; a real-data test compares them.
APP_GROUP = {"fx": 0, "fy": 0, "cx": 0, "cy": 0, "dist": 1, "baseline_mm": 2, "tr_ms": 2, "td_ms": 3, "lever_mm": 3,
             "Dw": 5, "Da": 6}

DATASET_LABELS = {"virig": "VI-Rig 3 cams", "mvis_rig": "VI-Rig 4 cams", "tum_vi": "TUM-VI",
                  "looper_insight9": "Looper Insight-9", "monado_msd": "Monado MGC"}

# Rows of these kinds never enter a comparison; each is listed with its reason.
NOT_PART = {"metric": ("reprojection error", "fit quality, not repeatability and not accuracy"),
            "model": ("IMU g-sensitivity Tg", "Kalibr absorbs it in its IMU model"),
            "mvis": ("gyro–accel delay t_ga", "MVIS only")}
NOTE_REASON = "kept as text: Kalibr's rolling-shutter runs solve one camera per run"
NOK_REASON = {"T2": "other camera model: MVIS equidistant, Kalibr and Basalt radtan",
              "T8": "no Kalibr rolling-shutter run",
              "T11": "no Kalibr rolling-shutter run; Basalt has no rolling-shutter model"}
NOK_DEFAULT = "the tools' models differ here"
NOT_RUN = {"T6": "not run: one IMU per run; no run holds the whole rig",
           "T7": "not run: one IMU per run and no rolling-shutter model; no run holds the whole rig",
           "T8": "not run: no rolling-shutter model"}
NOT_RUN_DEFAULT = "not run on this family"
SHOWN = {"T6c": "other camera model (pinhole-radtan8)", "T2": "global-shutter model of a rolling-shutter rig"}
SHOWN_DEFAULT = "other camera model"
MISSING = {("T6c", "Basalt", "baseline"): "not in one run"}
MISSING_DEFAULT = "no value for this tool"
SINGLE_SEED = ("T9", "T10")
INPUT_TEXT = ("{tool}'s camera+IMU run starts from these values, exported from MVIS for each recording, and keeps them "
              "fixed. Their spread copies the input, so it is not {tool}'s repeatability.")
INPUT_TEXT_SEED = ("{tool}'s camera+IMU run starts from these values, from one MVIS export used for all recordings, and "
                   "keeps them fixed. Their spread copies the input, so it is not {tool}'s repeatability.")

CAVEATS = {
    "dist_tradeoff": "Coefficients trade off against each other, so their scatter can overstate differences in the lens mapping.",
    "mvis_from_camimu": "MVIS values come from the T6 camera+IMU solve, not a camera-only run; not like-for-like.",
    "settings_differ": "Data settings still differ between the tools on this family.",
    "kalibr_seeded": "Kalibr starts from MVIS camera values for each recording; its spread here includes the spread of that input.",
    "kalibr_gs_elp": "Kalibr ran ELP-L as a global-shutter camera.",
    "kalibr_old_seed": "Kalibr's t265 fisheye 1 intrinsics came from an older MVIS export.",
    "kalibr_view_filtered": "Kalibr ran on view-filtered bags (≤ 85°); MVIS and Basalt ran on the full bags.",
    "basalt_snapped": "Basalt's fisheye-2 frames are snapped onto fisheye-1 (1.8–5 ms apart).",
    "kimu": "MVIS here uses Kalibr's IMU model, so the gyro and accel terms mean the same thing in both tools.",
    "lens_models_differ": "MVIS uses an equidistant lens model here, Kalibr radtan, so focal length and principal point are not quite the same quantity.",
}
_ALL = tuple(g for g, *_ in GROUPS)
_CAM_IMU = ("time_offset", "lever", "gyro", "accel")
# (caveat, families, groups, needs Basalt compared); a test checks every family and group named here exists.
CAVEAT_RULES = (
    ("dist_tradeoff", None, ("distortion",), False),
    ("mvis_from_camimu", ("T6c",), _ALL, False),
    ("settings_differ", ("T6", "T7", "T8"), _ALL, False),
    ("kalibr_seeded", ("T6", "T7", "T11", "T12"), _CAM_IMU, False),
    ("kalibr_gs_elp", ("T7",), ("time_offset", "lever"), False),
    ("kalibr_old_seed", ("T7",), _CAM_IMU, False),
    ("kalibr_view_filtered", ("T3",), _ALL, False),
    ("basalt_snapped", ("T1", "T6c"), _ALL, True),
    ("kimu", "camimu", IMU_GROUPS, False),
    ("lens_models_differ", ("T2",), ("focal_pp",), False),
)
FOOTER = "Repeatability only — a tool can repeat well and still be biased."


# ---------------------------------------------------------------- small helpers
def base(key: str) -> str:
    return key.split("[")[0]


def is_camimu(fam: dict) -> bool:
    return fam["mode"] != "camera only"


def finite(d: dict | None) -> dict:
    return {k: float(v) for k, v in (d or {}).items() if isinstance(v, (int, float)) and math.isfinite(v)}


def sig(x: float | None, n: int) -> float | None:
    return None if x is None else float(f"{x:.{n}g}")


def r2(x: float | None) -> float | None:
    return None if x is None else round(x, 2)


def fmt_k(k: float) -> str:
    """A spread ratio for the page: two significant figures, no exponent."""
    return f"{k:.0f}" if k >= 10 else f"{k:.2g}" if k >= 1.05 else f"{k:.2f}"


def fmt_p(p: float) -> str:
    return f"{p:.2g}"


def fmt_pct(p: float) -> str:
    v = p * 100
    return f"{v:.2g} %" if v < 10 else f"{v:.0f} %"


def join_and(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


# ---------------------------------------------------------------- inputs and the consistency gate
def load_records(root: Path, batch: str) -> dict:
    """{families: families.json, tools: {tool: {T: record}}} of one batch from a local records snapshot."""
    root = Path(root)
    fams = json.loads((root / "families.json").read_text())
    tools = {}
    for tool in TOOLS:
        tools[tool] = {}
        for T in fams["families"]:
            p = root / tool / batch / f"{T}.json"
            if p.exists():
                tools[tool][T] = json.loads(p.read_text())
    return {"families": fams, "tools": tools}


def block(row: dict, method: str, camimu: bool) -> dict | None:
    """The stats block behind a record method on a row: the same mapping as export_threeway.block()."""
    s, b = row.get("stats") or {}, row.get("bstats") or {}
    if method == "MVIS":
        return s.get("calyx") if camimu else s.get("mvis_all")
    if method == "MVIS (Kalibr IMU model)":
        return s.get("mvis_all")
    if method == "Kalibr":
        return s.get("kalibr")
    return b.get("basalt_all") or b.get("basalt")


# stats block -> the per-recording dict it was computed from
BLOCK_DICT = (("stats", "mvis_all", "mvis_all"), ("stats", "calyx", "calyx"), ("stats", "kalibr", "kalibr"),
              ("stats", "mvis", "mvis"), ("bstats", "basalt_all", "basalt"))


def _close(a, b) -> bool:
    return a is not None and b is not None and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-15)


def gate(stats: dict, records: dict, batch: str) -> list[str]:
    """Problems that stop the export: the records must be exactly the stats file's blocks (as the exporter rounds them,
    6 significant figures) and each block must be its own per-recording dict. Empty when they belong together."""
    out = []
    fams = records["families"]
    if fams.get("batch") != batch:
        out.append(f"families.json is batch {fams.get('batch')}, not {batch}")
    for tool, per_fam in records["tools"].items():
        for T, rec in per_fam.items():
            if rec.get("batch") != batch:
                out.append(f"{tool} {T}: record batch {rec.get('batch')}, not {batch}")
            fam = stats["families"].get(T)
            if fam is None:
                out.append(f"{T}: not in the stats file")
                continue
            rows = {(r["sensor"], r["key"]): r for r in fam["rows"]}
            cam = is_camimu(fam)
            for method, blk in rec["methods"].items():
                for r in blk["rows"]:
                    row = rows.get((r["sensor"], r["key"]))
                    if row is None:
                        out.append(f"({T}, {r['sensor']}, {r['key']}, {method}): no stats row")
                        continue
                    st = block(row, method, cam)
                    want = (sig(st["med"], 6), sig(st["sd"], 6), st["n"]) if st else (None, None, 0)
                    if (r["med"], r["sd"], r["n"]) != want:
                        out.append(f"({T}, {r['sensor']}, {r['key']}, {method}): record {r['med']}, {r['sd']}, "
                                   f"{r['n']} vs stats {want}")
    for T, fam in stats["families"].items():
        for row in fam["rows"]:
            for part, name, dname in BLOCK_DICT:
                st = (row.get(part) or {}).get(name)
                if not st:
                    continue
                if dname not in row:
                    out.append(f"({T}, {row['sensor']}, {row['key']}, {name}): no per-recording dict to check")
                    continue
                v = list(finite(row[dname]).values())
                ok = len(v) == st["n"] and _close(statistics.median(v), st["med"]) if v else st["n"] == 0
                if ok and len(v) > 1:
                    ok = _close(statistics.stdev(v), st["sd"])
                if not ok:
                    out.append(f"({T}, {row['sensor']}, {row['key']}, {name}): block is not its per-recording values")
    return out


# ---------------------------------------------------------------- roles
def column(row: dict, tool: str, camimu: bool, gid: str) -> dict:
    """Per-recording values that stand for a tool on a row. Camera+IMU: MVIS default IMU model, except gyro and accel,
    where only the MVIS run with Kalibr's IMU model has comparable terms."""
    if tool == "MVIS":
        name = "calyx" if camimu and gid not in IMU_GROUPS else "mvis_all"
    else:
        name = tool.lower()
    return finite(row.get(name))


def input_reason(T: str, tool: str) -> str:
    return (INPUT_TEXT_SEED if T in SINGLE_SEED else INPUT_TEXT).format(tool=tool)


def role(T: str, fam: dict, row: dict, tool: str, ran: dict, gid: str) -> tuple[str, str | None]:
    """(role, reason) of one tool on one row."""
    if not ran[tool]:
        return "not_run", NOT_RUN.get(T, NOT_RUN_DEFAULT)
    vals = column(row, tool, is_camimu(fam), gid)
    if row["kind"] == "nok":
        why = NOK_REASON.get(T, NOK_DEFAULT)
        if tool == "MVIS":
            return "only", why
        return ("other_model" if vals else "missing"), why
    bk = (row.get("bstats") or {}).get("kind")
    if (tool == "Kalibr" and row["kind"] == "fixed") or (tool == "Basalt" and bk == "fixed"):
        return "input", input_reason(T, tool)
    if tool == "Basalt" and bk == "info":
        return "shown", SHOWN.get(T, SHOWN_DEFAULT)
    if not vals:
        return "missing", MISSING.get((T, tool, gid), MISSING_DEFAULT)
    return "compared", None


def matched(cols: dict) -> list[str]:
    """Recordings with a finite value in every compared (tool, row) column; cols maps (tool, row index) -> values."""
    sets = [set(v) for v in cols.values()]
    return sorted(set.intersection(*sets)) if sets else []


# ---------------------------------------------------------------- the statistic and its test
def pair_stat(XA: np.ndarray, XB: np.ndarray) -> float:
    """G = median over parameters (rows) of ln(sd_A / sd_B), sample sd over recordings (columns)."""
    return float(np.median(np.log(np.std(XA, ddof=1, axis=1) / np.std(XB, ddof=1, axis=1))))


def masks_for(n: int, seed_key: str) -> tuple[np.ndarray, bool]:
    """Swap patterns, the observed (no swap) first: all 2^n for n <= 16, else the observed plus 65 536 random ones
    seeded from the cell and pair (never Python's hash(), which changes per process)."""
    if n <= EXACT_MAX:
        return np.array(list(itertools.product((0.0, 1.0), repeat=n))), True
    seed = int.from_bytes(hashlib.sha256(seed_key.encode()).digest()[:8], "big")
    rnd = np.random.default_rng(seed).integers(0, 2, (N_RANDOM, n)).astype(float)
    return np.vstack([np.zeros((1, n)), rnd]), False


class Swaps:
    """The label-swap test of one pair, ready for any scale e^c of B (the interval inverts the test this way).
    Every pattern's sums are taken once, so p(c) costs one median per pattern."""

    def __init__(self, XA: np.ndarray, XB: np.ndarray, seed_key: str):
        self.n = XA.shape[1]
        A = XA - XA.mean(axis=1, keepdims=True)
        B = XB - XB.mean(axis=1, keepdims=True)
        S, self.exact = masks_for(self.n, seed_key)
        U = 1.0 - S
        self.sums = [m @ x.T for m in (U, S) for x in (A, A * A, B, B * B)]

    def G(self, c: float = 0.0) -> np.ndarray:
        uA1, uA2, uB1, uB2, sA1, sA2, sB1, sB2 = self.sums
        e, n = math.exp(c), self.n
        va = (uA2 + e * e * sB2 - (uA1 + e * sB1) ** 2 / n) / (n - 1)
        vb = (e * e * uB2 + sA2 - (e * uB1 + sA1) ** 2 / n) / (n - 1)
        tiny = np.finfo(float).tiny
        return np.median(0.5 * np.log(np.maximum(va, tiny) / np.maximum(vb, tiny)), axis=1)

    def p(self, c: float = 0.0) -> float:
        g = self.G(c)
        return float(np.mean(np.abs(g) >= abs(g[0]) - 1e-12))


def perm_p(XA: np.ndarray, XB: np.ndarray, seed_key: str = "") -> tuple[float, bool]:
    """(p, exact) of the paired label-swap test of G = 0."""
    sw = Swaps(XA, XB, seed_key)
    return sw.p(), sw.exact


def holm(ps: list[float]) -> list[float]:
    """Holm-adjusted p-values, in the input order."""
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    out, run = [0.0] * len(ps), 0.0
    for j, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - j) * ps[i]))
        out[i] = run
    return out


def _edge(sw: Swaps, g0: float, sign: int) -> float | None:
    """The first c from g0 outward (sign +1 or -1) where p(c) drops under alpha, bisected to TOL; None if unbounded."""
    inside = g0
    c = g0 + sign * STEP
    while abs(c) <= LN_MAX:
        if sw.p(c) < ALPHA:
            lo, hi = inside, c
            while abs(hi - lo) > TOL:
                mid = 0.5 * (lo + hi)
                lo, hi = (mid, hi) if sw.p(mid) >= ALPHA else (lo, mid)
            return 0.5 * (lo + hi)
        inside, c = c, c + sign * STEP
    return None


def interval(XA: np.ndarray, XB: np.ndarray, seed_key: str = "") -> tuple[float | None, float | None]:
    """95 % interval of R = exp(G) by inverting the swap test (not adjusted); an unbounded end is None."""
    sw = Swaps(XA, XB, seed_key)
    g0 = pair_stat(XA, XB)
    lo, hi = _edge(sw, g0, -1), _edge(sw, g0, +1)
    return (None if lo is None else math.exp(lo)), (None if hi is None else math.exp(hi))


def loo(XA: np.ndarray, XB: np.ndarray) -> bool:
    """True if G keeps its sign and exp(|G|) >= MIN_RATIO with any one recording left out."""
    g0 = pair_stat(XA, XB)
    for i in range(XA.shape[1]):
        g = pair_stat(np.delete(XA, i, axis=1), np.delete(XB, i, axis=1))
        if np.sign(g) != np.sign(g0) or math.exp(abs(g)) < MIN_RATIO:
            return False
    return True


def decide(n: int, p_holm: float, k: float) -> tuple[str, str | None]:
    """(decision, tie reason): 'tighter', 'tie' or 'too_few'."""
    if n < MIN_N:
        return "too_few", None
    if p_holm >= ALPHA:
        return "tie", "noise"
    if k < MIN_RATIO:
        return "tie", "small"
    return "tighter", None


def verdict(tools: list[str], pairs: list[dict], n: int) -> dict:
    """The cell's state from its pair decisions: most | tie_top | tie | not_separated | too_few."""
    if n < MIN_N:
        return {"state": "too_few", "tools": [], "over": [], "k": None}
    beats = {t: {} for t in tools}
    for q in pairs:
        if q["decision"] in ("a", "b"):
            w, l = (q["a"], q["b"]) if q["decision"] == "a" else (q["b"], q["a"])
            beats[w][l] = q["k"]
    if not any(beats.values()):
        return {"state": "tie", "tools": [], "over": [], "k": None}
    for x in tools:
        if len(beats[x]) == len(tools) - 1:
            return {"state": "most", "tools": [x], "over": [t for t in tools if t != x], "k": min(beats[x].values())}
    for x, y in itertools.combinations(tools, 2):
        for z in (t for t in tools if t not in (x, y)):  # only with three tools
            if z in beats[x] and z in beats[y]:
                return {"state": "tie_top", "tools": [x, y], "over": [z], "k": min(beats[x][z], beats[y][z])}
    return {"state": "not_separated", "tools": [], "over": [], "k": None}


# ---------------------------------------------------------------- one cell
def _published(records: dict, T: str, tool: str, camimu: bool, gid: str) -> dict:
    """(sensor, key) -> {sd, n} of the record method that stands for the tool in this cell."""
    method = "MVIS (Kalibr IMU model)" if tool == "MVIS" and camimu and gid in IMU_GROUPS else tool
    rec = records["tools"].get(tool, {}).get(T) or {"methods": {}}
    rows = (rec["methods"].get(method) or {}).get("rows") or []
    return {(r["sensor"], r["key"]): {"sd": sig(r["sd"], 3), "n": r["n"]} for r in rows}


def caveats_for(T: str, gid: str, camimu: bool, tools: list[str]) -> list[str]:
    out = []
    for cid, fams, groups, needs_basalt in CAVEAT_RULES:
        in_fam = fams is None or (camimu if fams == "camimu" else T in fams)
        if in_fam and gid in groups and (not needs_basalt or "Basalt" in tools):
            out.append(cid)
    return out


def _excluded(entries: dict) -> list[dict]:
    return [{"tool": t, "role": r, "reason": why, "rows": c} for (t, r, why), c in entries.items()]


def cell(T: str, fam: dict, gid: str, ran: dict, records: dict) -> dict | None:
    """One family x group, or None when the family has no row of the group."""
    camimu = is_camimu(fam)
    rows = [r for r in fam["rows"] if GROUP_OF.get(base(r["key"])) == gid and r["kind"] in ("cmp", "fixed", "nok", "note")]
    if not rows:
        return None
    out = {"state": None, "tools": [], "over": [], "k": None, "n": 0, "n_all": {}, "compared": [],
           "mvis_variant": "kalibr_imu" if camimu and gid in IMU_GROUPS else "default",
           "caveats": [], "pairs": [], "params": [], "excluded": [], "dropped": [], "reason": None}
    cols, excl, roles_seen = {}, {}, set()
    est = [r for r in rows if r["kind"] != "note"]
    if len(est) < len(rows):
        excl[("all", "note", NOTE_REASON)] = len(rows) - len(est)
    for i, row in enumerate(est):
        for tool in TOOLS:
            rl, why = role(T, fam, row, tool, ran, gid)
            roles_seen.add((tool, rl, why))
            if rl == "compared":
                cols[(tool, i)] = column(row, tool, camimu, gid)
            else:
                excl[(tool, rl, why)] = excl.get((tool, rl, why), 0) + 1
    out["excluded"] = _excluded(excl)
    tools = [t for t in TOOLS if any(k[0] == t for k in cols)]
    out["compared"] = tools
    if len(tools) < 2:
        return dict(out, **_lone(est, tools, roles_seen, bool(excl.get(("all", "note", NOTE_REASON)))))
    out["caveats"] = caveats_for(T, gid, camimu, tools)
    M = matched(cols)
    n = len(M)
    out["n"] = n
    out["n_all"] = {t: max(len(v) for (tt, _), v in cols.items() if tt == t) for t in tools}
    X, dropped = {}, set()
    for (tool, i), v in cols.items():
        x = np.array([v[r] for r in M], float)
        X[(tool, i)] = x
        s = float(np.std(x, ddof=1)) if n > 1 else float("nan")
        if not math.isfinite(s) or s <= 1e-12 * max(1.0, abs(float(np.median(x)))):
            dropped.add((tool, i))
            out["dropped"].append({"tool": tool, "sensor": est[i]["sensor"], "key": est[i]["key"],
                                   "reason": "constant over recordings" if n > 1 else "fewer than 2 shared recordings"})
    pairs = []
    for a, b in itertools.combinations(tools, 2):
        P = [i for i in range(len(est)) if (a, i) in X and (b, i) in X and (a, i) not in dropped and (b, i) not in dropped]
        q = {"a": a, "b": b, "n_params": len(P), "R": None, "k": None, "ci": None, "p": None, "p_holm": None,
             "decision": "not_compared", "tie_reason": None, "loo_stable": None, "exact": True}
        if P:
            XA, XB = np.array([X[(a, i)] for i in P]), np.array([X[(b, i)] for i in P])
            g = pair_stat(XA, XB)
            q.update(_G=g, _XA=XA, _XB=XB, R=math.exp(g), k=math.exp(abs(g)))
            q["p"], q["exact"] = perm_p(XA, XB, f"{T}|{gid}|{a}|{b}")
        pairs.append(q)
    tested = [q for q in pairs if q["p"] is not None]
    for q, ph in zip(tested, holm([q["p"] for q in tested])):
        q["p_holm"] = ph
        d, q["tie_reason"] = decide(n, ph, q["k"])
        q["decision"] = ("a" if q["R"] < 1 else "b") if d == "tighter" else d
        if n >= MIN_N:
            q["ci"] = list(interval(q["_XA"], q["_XB"], f"{T}|{gid}|{q['a']}|{q['b']}"))
        if d == "tighter":
            q["loo_stable"] = loo(q["_XA"], q["_XB"])
    out.update(verdict(tools, pairs, n))
    if n >= MIN_N and all(q["decision"] == "not_compared" for q in pairs):
        out.update(state="not_compared", reason="no parameter varies across the shared recordings")
    for i, row in enumerate(est):
        here = [t for t in tools if (t, i) in X]
        if not here:
            continue
        pub = {t: _published(records, T, t, camimu, gid).get((row["sensor"], row["key"])) for t in here}
        sd = {t: (None if (t, i) in dropped else sig(float(np.std(X[(t, i)], ddof=1)), 3)) for t in here}
        out["params"].append({"sensor": row["sensor"], "key": row["key"], "label": row["label"], "unit": row["unit"],
                              "sd": sd, "published": pub, "data_k": f"m|{row['sensor']}|{row['key']}"})
    out["pairs"] = [_public_pair(q) for q in pairs]
    return out


def _lone(est: list[dict], tools: list[str], roles_seen: set, has_note: bool) -> dict:
    """State and reason of a cell with fewer than two compared tools."""
    by_role = {}
    for tool, rl, why in sorted(roles_seen, key=lambda x: (TOOLS.index(x[0]), x[1], x[2] or "")):
        by_role.setdefault(rl, []).append((tool, why))
    if "input" in by_role:
        return {"state": "input", "reason": by_role["input"][0][1]}
    if "other_model" in by_role:
        return {"state": "not_compared", "reason": by_role["other_model"][0][1]}
    owners = tools or [t for t, _ in by_role.get("only", [])]
    if owners:
        why = (by_role.get("only") or by_role.get("missing") or by_role.get("shown") or by_role.get("not_run"))[0][1]
        return {"state": "single", "tools": owners[:1], "reason": f"{owners[0]} only: {why}"}
    return {"state": "not_compared", "reason": NOTE_REASON if has_note else MISSING_DEFAULT}


def _public_pair(q: dict) -> dict:
    ci = q["ci"]
    return {"a": q["a"], "b": q["b"], "n_params": q["n_params"], "R": r2(q["R"]), "k": r2(q["k"]),
            "ci": None if ci is None else [r2(ci[0]), r2(ci[1])], "p": sig(q["p"], 2), "p_holm": sig(q["p_holm"], 2),
            "decision": q["decision"], "tie_reason": q["tie_reason"], "loo_stable": q["loo_stable"], "exact": q["exact"],
            "k_text": None if q["k"] is None else fmt_k(q["k"]), "_k": q["k"], "_p": q["p"], "_ph": q["p_holm"]}


# ---------------------------------------------------------------- words
def chip(c: dict) -> str:
    s = c["state"]
    if s == "most":
        return ("Most" if len(c["compared"]) == 3 else "More") + f" repeatable: {c['tools'][0]}"
    if s == "tie_top":
        return f"Tie: {c['tools'][0]} = {c['tools'][1]} · both tighter than {c['over'][0]}"
    return {"tie": "Tie", "not_separated": "Not separated", "too_few": f"Too few recordings (n = {c['n']})",
            "input": "Input, not compared", "single": f"{(c['tools'] or ['One tool'])[0]} only",
            "not_compared": "Not compared"}[s]


def _pair(c: dict, x: str, y: str) -> dict:
    return next(q for q in c["pairs"] if {q["a"], q["b"]} == {x, y})


def _tie_text(q: dict, n: int) -> str:
    if q["tie_reason"] == "small":
        return f"The gap between {q['a']} and {q['b']} is clear but under 20 % ({q['k_text']}×), so it is treated as a tie."
    return (f"The spreads of {q['a']} and {q['b']} differ by {q['k_text']}×, but a gap this size appears often by chance "
            f"with {n} recordings (p = {fmt_p(q['_ph'])}). Treated as a tie.")


def _loo_text(qs: list[dict]) -> str:
    return "Holds with any one recording left out." if all(q["loo_stable"] for q in qs) else "Depends on one recording."


def sentence(c: dict) -> str:
    s, n = c["state"], c["n"]
    if s == "most":
        x = c["tools"][0]
        qs = [_pair(c, x, y) for y in c["over"]]
        bits = [f"{y}'s about {q['k_text']}×" for y, q in zip(c["over"], qs)]
        first = (f"Across the same {n} recordings, {c['over'][0]}'s estimates scatter about {qs[0]['k_text']}× more than "
                 f"{x}'s (median over {qs[0]['n_params']} parameters)")
        first += f"; {bits[1]}." if len(bits) > 1 else "."
        swaps = join_and([f"{fmt_pct(q['_p'])} ({y})" for y, q in zip(c["over"], qs)]) if len(qs) > 1 else fmt_pct(qs[0]["_p"])
        return f"{first} A gap this large appeared in {swaps} of recording-by-recording swaps. {_loo_text(qs)}"
    if s == "tie_top":
        x, y = c["tools"]
        z = c["over"][0]
        qx, qy = _pair(c, x, z), _pair(c, y, z)
        return (f"{_tie_text(_pair(c, x, y), n)} Both scatter less than {z}: across the same {n} recordings {z}'s "
                f"estimates scatter about {qx['k_text']}× more than {x}'s and {qy['k_text']}× more than {y}'s. "
                f"{_loo_text([qx, qy])}")
    if s == "tie":
        return " ".join(_tie_text(q, n) for q in c["pairs"] if q["decision"] == "tie")
    if s == "not_separated":
        dec = [f"{q['a'] if q['decision'] == 'a' else q['b']} is tighter than {q['b'] if q['decision'] == 'a' else q['a']}"
               for q in c["pairs"] if q["decision"] in ("a", "b")]
        return "; ".join(dec) + "; the other pairs are not separated. No single tool is marked."
    if s == "too_few":
        tail = " Ratios are shown for reference only." if n > 1 else " Ratios cannot be computed."
        return (f"Only {n} recordings were run by every compared tool. With {n} recordings the smallest possible p is "
                f"{fmt_p(2 / 2 ** n)}, so no gap can be decided.{tail}")
    return c["reason"]


def variant_line(T: str, camimu: bool, gid: str) -> str:
    if T == "T6c":
        return "MVIS here: the camera values of the T6 camera+IMU solve."
    if not camimu:
        return "MVIS here: its camera-only run."
    if gid in IMU_GROUPS:
        return "MVIS here: its run with Kalibr's IMU model (K-IMU)."
    return "MVIS here: its default IMU model."


def aria(c: dict, T: str, gid: str) -> str:
    s, n = c["state"], c["n"]
    head = f"{LABEL[gid]}, {T}: "
    if s == "most":
        over = join_and(c["over"])
        return head + f"more repeatable {c['tools'][0]}, {fmt_k(c['k'])} times tighter than {over}, {n} matched recordings."
    if s == "tie_top":
        return head + (f"tie between {c['tools'][0]} and {c['tools'][1]}, both tighter than {c['over'][0]}, "
                       f"{n} matched recordings.")
    if s in ("tie", "not_separated", "too_few"):
        return head + chip(c).lower() + f", {n} matched recordings."
    return head + c["reason"]


def strip_line(c: dict, gid: str) -> str | None:
    """A cell's word in a phone card's one-line verdict strip, or None for cells without a comparison."""
    s, g = c["state"], SHORT[gid]
    kimu = " K-IMU" if c["mvis_variant"] == "kalibr_imu" and "MVIS" in c["tools"] else ""
    if s == "most":
        return f"{g} {c['tools'][0]}{kimu}"
    if s == "tie_top":
        return f"{g} {c['tools'][0]} = {c['tools'][1]}"
    if s in ("tie", "not_separated"):
        return f"{g} {chip(c).lower()}"
    return None


# ---------------------------------------------------------------- the board
def ran_map(records: dict, T: str) -> dict:
    return {t: any(b.get("ran") for b in ((records["tools"].get(t, {}).get(T) or {}).get("methods") or {}).values())
            for t in TOOLS}


def recordings(records: dict, T: str, of: int) -> dict:
    out = {}
    for t in TOOLS:
        ms = ((records["tools"].get(t, {}).get(T) or {}).get("methods") or {}).values()
        n = max((b.get("n_recordings") or 0 for b in ms), default=0)
        out[t] = {"n": n, "of": of}
        if not any(b.get("ran") for b in ms):
            out[t]["reason"] = NOT_RUN.get(T, NOT_RUN_DEFAULT)
    return out


def not_part(T: str, fam: dict) -> list[dict]:
    seen = {}
    for r in fam["rows"]:
        if r["kind"] in NOT_PART:
            what, why = NOT_PART[r["kind"]]
        elif r["kind"] == "nok":
            g = GROUP_OF.get(base(r["key"]))
            what = (LABEL[g].lower() if g else r["label"]) + f" of {r['sensor'].split(' – ')[-1]}"
            why = NOK_REASON.get(T, NOK_DEFAULT)
        else:
            continue
        seen[(what, why)] = seen.get((what, why), 0) + 1
    return [{"what": w, "reason": y, "rows": c} for (w, y), c in seen.items()]


def family(T: str, fam: dict, meta: dict, records: dict, fold_index: int) -> dict:
    ran = ran_map(records, T)
    camimu = is_camimu(fam)
    cells = {}
    for gid, *_ in GROUPS:
        c = cell(T, fam, gid, ran, records)
        if c is None:
            continue
        c["chip"], c["sentence"], c["aria"] = chip(c), sentence(c), aria(c, T, gid)
        c["strip"], c["variant_line"] = strip_line(c, gid), variant_line(T, camimu, gid)
        c["k_text"] = None if c["k"] is None else fmt_k(c["k"])
        c["k"] = r2(c["k"])
        for q in c["pairs"]:
            for x in ("_k", "_p", "_ph"):
                q.pop(x)
        cells[gid] = c
    ns = sorted({c["n"] for c in cells.values() if c["compared"] and len(c["compared"]) > 1})
    return {"id": T, "fold_index": fold_index, "title": meta.get("title", T),
            "mode": "cam+imu" if camimu else "cam", "n_matched": [ns[0], ns[-1]] if ns else None,
            "recordings": recordings(records, T, meta.get("n_recordings") or len(fam.get("recs") or [])),
            "not_part": not_part(T, fam), "cells": cells}


def build(stats: dict, records: dict, batch: str, results_commit: str) -> dict:
    """repeatability.json as a dict. Refuses (SystemExit) when the records and the stats file don't belong together."""
    problems = gate(stats, records, batch)
    if problems:
        raise SystemExit("records and stats file disagree:\n  " + "\n  ".join(problems[:40]))
    fams = records["families"]
    datasets = []
    for ds in fams["datasets"]:
        fs = [family(T, stats["families"][T], fams["families"][T], records, i) for i, T in enumerate(ds["families"])]
        present = [g for g, *_ in GROUPS if any(g in f["cells"] for f in fs)]
        datasets.append({"id": ds["id"], "label": DATASET_LABELS.get(ds["id"], ds["title"]), "groups": present, "families": fs})
    return {"version": VERSION, "batch": batch, "results_commit": results_commit, "method": METHOD,
            "tools": [{"id": t, "shape": SHAPES[t]} for t in TOOLS],
            "groups": [{"id": g, "label": l, "short": SHORT[g], "unit": u} for g, l, u, _ in GROUPS],
            "caveats": CAVEATS, "footer": FOOTER, "datasets": datasets}


# ---------------------------------------------------------------- public check and output
PRIVATE_KEYS = ("recs", "sources", "label_of_recording", "values")


def check_public(text: str, results_commit: str, private_words: tuple[str, ...] = ()) -> list[str]:
    """Why the text may not be written: lint refusals and BANNED words (the one allowed hash is the results commit),
    any recording label or result-tree name of the stats file, and per-recording arrays."""
    found = [f"refused: {w}" for w in refusals(text)]
    found += public_problems(text.replace(results_commit, ""))
    found += [f"private name: {w}" for w in private_words if re.search(rf"(?<![\w/]){re.escape(w)}(?![\w/])", text)]
    obj = json.loads(text)

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in PRIVATE_KEYS:
                    found.append(f"private key: {k}")
                walk(v)
        elif isinstance(o, list):
            if len(o) > 2 and all(isinstance(v, (int, float)) for v in o):
                found.append("per-recording array")
            for v in o:
                walk(v)
    walk(obj)
    return found


def private_words(stats: dict) -> tuple[str, ...]:
    """Recording labels and result-tree names in the stats file, which must not reach the page. Plain words and short
    names (stereo, cam1, bag2) are left out: they are also ordinary sensor words."""
    out = set()
    for fam in stats["families"].values():
        for r in fam.get("recs") or []:
            for k in ("label", "mvis", "mvis_calyx"):
                if isinstance(r.get(k), str):
                    out.add(r[k])
        for row in fam["rows"]:
            for part in ("mvis_all", "calyx", "kalibr", "basalt", "mvis"):
                out.update((row.get(part) or {}).keys())
    return tuple(sorted(w for w in out if "_" in w or "/" in w or (len(w) >= 6 and re.search(r"\d", w))))


def dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def app_groups(app_py: Path) -> dict:
    """The Space's GROUPS literal, read without importing app.py."""
    for node in ast.parse(Path(app_py).read_text()).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "GROUPS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("app.py has no GROUPS")


def check_groups(app: dict) -> list[str]:
    """Keys whose table group in the Space differs from this module's."""
    return [k for k, g in APP_GROUP.items() if app.get(k) != g]


def export(stats_file: Path, records_dir: Path, batch: str, results_commit: str, out: Path,
           app_py: Path | None = None) -> Path:
    if not re.fullmatch(r"[0-9a-f]{40}", results_commit or ""):
        raise ValueError("results_commit must be the full 40-hex sha of the records snapshot")
    if app_py is not None:
        bad = check_groups(app_groups(app_py))
        if bad:
            raise SystemExit(f"the Space's GROUPS changed for {bad}: update repeatability.GROUPS")
    stats = json.loads(Path(stats_file).read_text())
    text = dumps(build(stats, load_records(records_dir, batch), batch, results_commit))
    found = check_public(text, results_commit, private_words(stats))
    if found:
        raise SystemExit("refusing to write: " + "; ".join(found[:10]))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out
