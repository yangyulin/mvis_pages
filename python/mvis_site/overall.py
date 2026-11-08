"""Overall tab: tier values (measured A, capability C, usability U), head to head, derived total, reader presets and
the leave-one-aspect-out check, from rubric_v1.yaml and the batch's repeatability.json. Pure: dicts in, a dict out
(overall.json). Every number on the tab is computed here; the page only arranges it.

Tier A is pairwise and gated: per cell of repeatability.json a decisive pair gives 1 / 0 and a tie 0.5 / 0.5. A pair
counts only when neither tool carries an excluding caveat in the cell (unless the rubric counts it despite the caveat),
and a cell whose remaining decisive pairs form a cycle gives no points. Family points per pair = mean over its groups;
aspect value per tool = mean over every (pair, family) it took part in. Tiers C and U are absolute: 1 / 0.5 / 0, an
aspect with sub-checks the mean of them. A tier value is the mean of its aspects that have points.
"""
from __future__ import annotations

import itertools
import json
import re
from collections import defaultdict
from pathlib import Path

import yaml

from .lint import public_problems, refusals

VERSION = 1
POINTS = {"a": (1.0, 0.0), "b": (0.0, 1.0), "tie": (0.5, 0.5)}
EPS = 0.005   # values closer than this are shown as level
RUBRIC = Path(__file__).resolve().parents[1] / "data" / "rubric_v1.yaml"
TIER_LABEL = {"A": "Measured"}


def r2(x: float | None) -> float | None:
    return None if x is None else round(x + 0.0, 2)


def r3(x: float | None) -> float | None:
    return None if x is None else round(x + 0.0, 3)


def mean(xs) -> float | None:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


# ---------------------------------------------------------------- tier A from repeatability.json
def _has_cycle(wins: list[tuple[str, str]]) -> bool:
    beats = defaultdict(set)
    for w, l in wins:
        beats[w].add(l)
    return any(a in beats[c] for a in list(beats) for b in beats[a] for c in list(beats[b]))


def _excluded_tools(fid: str, caveats: list[str], m: dict, tools: tuple) -> set | None:
    """Tools a cell's caveats exclude; None when every pair is excluded."""
    despite = {(d["caveat"], f) for d in m.get("count_despite", []) for f in d["families"]}
    out = set()
    for cv in caveats:
        who = m["excluding_caveats"].get(cv)
        if who is None or (cv, fid) in despite:
            continue
        if who == "all":
            return None
        out |= set(who)
    return out


def measured_aspect(asp: dict, rep: dict, m: dict, tools: tuple) -> dict:
    """Pairwise points of one measured aspect: per pair, per family, then the per-tool mean."""
    out_of_scope = {o["family"] for o in m.get("out_of_scope", [])}
    fam_pts = defaultdict(lambda: defaultdict(list))
    first_cell = {}
    for ds in rep["datasets"]:
        for f in ds["families"]:
            fid = f["id"]
            if fid in out_of_scope or f.get("mode") != asp["mode"]:
                continue
            for g in asp["groups"]:
                c = (f.get("cells") or {}).get(g)
                if not isinstance(c, dict):
                    continue
                excl = _excluded_tools(fid, c.get("caveats", []), m, tools)
                if excl is None:
                    continue
                pairs = [p for p in c.get("pairs", []) if p["decision"] in POINTS and not {p["a"], p["b"]} & excl]
                wins = [(p["a"], p["b"]) if p["decision"] == "a" else (p["b"], p["a"]) for p in pairs if p["decision"] != "tie"]
                if not pairs or _has_cycle(wins):
                    continue
                first_cell.setdefault(fid, (ds["id"], g))
                for p in pairs:
                    fam_pts[(p["a"], p["b"])][fid].append(POINTS[p["decision"]])
    per_tool = defaultdict(list)
    pairs_out = []
    for (a, b), fams in sorted(fam_pts.items(), key=lambda kv: (tools.index(kv[0][0]), tools.index(kv[0][1]))):
        fl = []
        for fid in sorted(fams, key=_fam_key):
            pa = mean(x for x, _ in fams[fid])
            per_tool[a].append(pa)
            per_tool[b].append(1 - pa)
            ds_id, g = first_cell[fid]
            fl.append({"id": fid, "points": {a: r2(pa), b: r2(1 - pa)}, "href": f"#rp-{fid}-{g}", "dataset": ds_id})
        pa = mean(f["points"][a] for f in fl)
        lead = a if pa > 0.5 + EPS else b if pa < 0.5 - EPS else None
        pairs_out.append({"a": a, "b": b, "points": {a: r2(pa), b: r2(1 - pa)}, "lead": lead, "families": fl})
    values = {t: mean(per_tool[t]) for t in tools}
    return {"values": values, "n": {t: len(per_tool[t]) for t in tools}, "pairs": pairs_out}


def _fam_key(fid: str):
    m = re.match(r"T(\d+)(\D*)", fid)
    return (int(m.group(1)), m.group(2)) if m else (999, fid)


def h2h_line(label: str, pairs: list[dict], tools: tuple) -> str:
    """Head to head in words: 'A and B repeat about equally well; both repeat better than C.' or one clause per pair."""
    if not pairs:
        return f"{label}: no pair of tools can be compared."
    lead = {frozenset((p["a"], p["b"])): p["lead"] for p in pairs}
    present = sorted({t for p in pairs for t in (p["a"], p["b"])}, key=tools.index)
    if len(present) == 3 and len(lead) == 3:
        for top in itertools_perms(present):
            x, y, z = top
            if lead[frozenset((x, y))] is None and lead[frozenset((x, z))] == x and lead[frozenset((y, z))] == y:
                return f"{label}: {x} and {y} repeat about equally well; both repeat better than {z}."
            if lead[frozenset((x, y))] == x and lead[frozenset((y, z))] == y and lead[frozenset((x, z))] == x:
                return f"{label}: {x} repeats better than {y}, and {y} better than {z}."
    fams = lambda p: ", ".join(f["id"] for f in p["families"])
    bits = [f"{p['lead']} repeats better than {p['b'] if p['lead'] == p['a'] else p['a']} ({fams(p)})"
            for p in pairs if p["lead"]]
    level = [f"{p['a']} and {p['b']} ({fams(p)})" for p in pairs if not p["lead"]]
    if level:
        bits.append("about equal: " + ", ".join(level))
    return f"{label}: " + "; ".join(bits) + "."


def itertools_perms(xs):
    return itertools.permutations(xs)


# ---------------------------------------------------------------- tiers C and U
def sub_ids(asp: dict) -> list[str]:
    return [s["id"] for s in asp.get("subs", [])]


def aspect_points(asp: dict, tool: str, keep=None) -> float | None:
    """Points of one absolute aspect; keep = sub-check ids to use (None = all)."""
    p = asp["points"][tool]
    if not isinstance(p, list):
        return float(p)
    ids = sub_ids(asp)
    vals = [v for i, v in zip(ids, p) if keep is None or i in keep]
    return mean(vals)


def _home(asp: dict) -> list[str]:
    h = asp.get("home", "shared")
    return h if isinstance(h, list) else [h]


def _tool_home(h: list[str], tools) -> bool:
    return any(x in tools for x in h)


# ---------------------------------------------------------------- build
def build(rubric: dict, rep: dict) -> dict:
    tools = tuple(rubric["tools"])
    m = rubric["measured"]
    w = rubric["wording"]
    home_label = w["home"]

    # tier A
    a_aspects, h2h, a_vals = [], [], {}
    for asp in m["aspects"]:
        row = {"id": asp["id"], "label": asp["label"], "rule": asp["rule"]}
        if asp.get("why"):
            row["why"] = asp["why"]
        if "groups" in asp:
            res = measured_aspect(asp, rep, m, tools)
            vals = res["values"]
            row["cells"] = {t: {"points": r2(vals[t]), "text": f"{res['n'][t]} pair-families" if vals[t] is not None else None,
                                "na": None if vals[t] is not None else "no pair compared"} for t in tools}
            h2h.append({"aspect": asp["id"], "label": asp["label"], "pairs": res["pairs"],
                        "line": h2h_line(asp["label"], res["pairs"], tools)})
            a_vals[asp["id"]] = vals
        elif "points" in asp:
            vals = {t: float(asp["points"][t]) for t in tools}
            row["cells"] = {t: {"points": vals[t], "text": asp.get("detail", {}).get(t), "na": None} for t in tools}
            a_vals[asp["id"]] = vals
        else:
            row["cells"] = {t: {"points": None, "text": None, "na": asp["na"]} for t in tools}
        a_aspects.append(row)

    # tiers C, U
    abs_tiers = {t["id"]: t for t in rubric["tiers"]}
    tier_rows = {"A": a_aspects}
    asp_vals = dict(a_vals)
    for tid, tier in abs_tiers.items():
        rows = []
        for asp in tier["aspects"]:
            vals = {t: aspect_points(asp, t) for t in tools}
            asp_vals[asp["id"]] = vals
            h = _home(asp)
            row = {"id": asp["id"], "label": asp["label"], "group": asp.get("group"),
                   "home": " / ".join(home_label.get(x, x) for x in h),
                   "rule": asp.get("rule"), "cells": {}}
            for t in tools:
                cell = {"points": r2(vals[t]), "na": None, "text": (asp.get("note") or {}).get(t)}
                if asp.get("subs"):
                    cell["subs"] = [{"label": s["label"] + (f" ({home_label[s['home']]})" if s.get("home") else ""),
                                     "points": v} for s, v in zip(asp["subs"], asp["points"][t])]
                row["cells"][t] = cell
            rows.append(row)
        tier_rows[tid] = rows

    order = ["A"] + list(abs_tiers)
    tier_of = {a: tid for tid in order for a in ([x["id"] for x in tier_rows[tid]])}
    counted = [a for a in asp_vals if all(asp_vals[a][t] is not None for t in tools)]

    def tier_value(tid, t, drop=()):
        return mean(asp_vals[a][t] for a in counted if tier_of[a] == tid and a not in drop)

    def total(tids, t, drop=()):
        return mean(tier_value(tid, t, drop) for tid in tids)

    tiers_out = []
    for tid in order:
        label = TIER_LABEL.get(tid) or abs_tiers[tid]["label"]
        n_all = len(tier_rows[tid])
        n_pts = sum(1 for a in counted if tier_of[a] == tid)
        tiers_out.append({"id": tid, "label": label, "values": {t: r2(tier_value(tid, t)) for t in tools},
                          "leader": _leader({t: tier_value(tid, t) for t in tools}),
                          "coverage": f"{n_pts} of {n_all} aspects have points", "aspects": tier_rows[tid]})

    eq = {t: total(order, t) for t in tools}
    loo = defaultdict(int)
    for a in counted:
        lt = _leader({t: total(order, t, drop=(a,)) for t in tools})
        loo[lt or "level"] += 1
    lead = _leader(eq)
    badge = (f"Equal tiers: {lead} first in {loo[lead]} of {len(counted)} leave-one-aspect-out variants."
             if lead else f"Equal tiers: no tool leads; {len(counted)} leave-one-aspect-out variants checked.")

    presets = [_preset(p, rubric, asp_vals, counted, tier_of, order, tools, total) for p in rubric["presets"]]
    first = next((p for p in presets if p["id"] == "first_draft"), None)
    disclosure = w["facts_note"]
    if first and first["leader"] and first["leader"] != lead:
        v = first["values"]
        disclosure += (f" Counting them as in the first draft puts {first['leader']} first "
                       f"({v[first['leader']]:.2f} against {v[lead]:.2f} for {lead}).")

    return {
        "version": VERSION, "rubric": rubric["rubric"], "date": str(rubric["date"]),
        "batch": rep["batch"], "results_commit": rep["results_commit"], "tools": list(tools),
        "wording": {"banner": w["banner"].format(date=rubric["date"]), "truth": w["truth"], "total_note": w["total_note"],
                    "disclosure": disclosure, "columns": w["columns"], "challenge_url": rubric["challenge_url"]},
        "tiers": tiers_out,
        "head_to_head": h2h,
        "total": {"values": {t: r2(eq[t]) for t in tools}, "leader": lead,
                  "sum": {t: r2(sum(asp_vals[a][t] for a in counted)) for t in tools}, "n_aspects": len(counted)},
        "badge": badge,
        "presets": presets,
        "facts": [{"id": f["id"], "label": f["label"], "values": f["values"], "note": f.get("note")} for f in rubric["facts"]],
        "not_counted": rubric["not_counted"],
        "rules": [f"{d['families'][0] if len(d['families']) == 1 else ', '.join(d['families'])} counted despite "
                  f"'{d['caveat'].replace('_', ' ')}': {d['why']}" for d in m.get("count_despite", [])]
                 + [f"{o['family']} left out: {o['why']}" for o in m.get("out_of_scope", [])],
    }


def _leader(vals: dict) -> str | None:
    if any(v is None for v in vals.values()):
        return None
    top = max(vals.values())
    lead = [t for t, v in vals.items() if v >= top - EPS]
    return lead[0] if len(lead) == 1 else None


def _preset(p, rubric, asp_vals, counted, tier_of, order, tools, total):
    if p.get("first_draft"):
        vals = _first_draft(rubric, asp_vals, counted, tools)
    elif "tiers" in p and not p.get("drop_home"):
        vals = {t: total(p["tiers"], t) for t in tools}
    elif p.get("drop_home"):
        vals = {t: _no_home(rubric, p["tiers"], t) for t in tools}
    else:
        vals = {t: mean(_aspect_ref(rubric, asp_vals, a, t) for a in p["aspects"]) for t in tools}
    return {"id": p["id"], "label": p["label"], "values": {t: r2(vals[t]) for t in tools}, "leader": _leader(vals)}


def _abs_aspect(rubric, aid):
    for tier in rubric["tiers"]:
        for asp in tier["aspects"]:
            if asp["id"] == aid:
                return asp
    return None


def _aspect_ref(rubric, asp_vals, ref, t):
    """'C4a+b' = sub-checks a and b of C4; 'C5' = the whole aspect."""
    m = re.fullmatch(r"([ACU]\d+)([a-z+]*)", ref)
    aid, subs = m.group(1), m.group(2)
    if not subs:
        return asp_vals[aid][t]
    return aspect_points(_abs_aspect(rubric, aid), t, keep=set(subs.split("+")))


def _no_home(rubric, tids, t):
    """Tier values without any aspect a tool calls home, and mixed aspects without their home sub-checks."""
    tools = set(rubric["tools"])
    tier_vals = []
    for tier in rubric["tiers"]:
        if tier["id"] not in tids:
            continue
        vals = []
        for asp in tier["aspects"]:
            h = _home(asp)
            if _tool_home(h, tools):
                continue
            keep = [s["id"] for s in asp.get("subs", []) if not s.get("home")] if asp.get("subs") else None
            vals.append(aspect_points(asp, t, keep=set(keep) if keep is not None else None))
        tier_vals.append(mean(vals))
    return mean(tier_vals)


def _first_draft(rubric, asp_vals, counted, tools):
    """The first draft's tiers: A; C with U3 and U4 inside it; G = maturity, papers, install, licence, docs."""
    draft = {f["id"]: f["draft_points"] for f in rubric["facts"]}
    out = {}
    for t in tools:
        a = mean(asp_vals[x][t] for x in counted if x.startswith("A"))
        c = mean([asp_vals[x][t] for x in counted if x.startswith("C")] + [asp_vals["U3"][t], asp_vals["U4"][t]])
        g = mean([draft["P1"][t], draft["P2"][t], asp_vals["U1"][t], draft["P3"][t], asp_vals["U2"][t]])
        out[t] = mean([a, c, g])
    return out


# ---------------------------------------------------------------- export
def check_public(text: str, results_commit: str) -> list[str]:
    found = [f"refused: {w}" for w in refusals(text)]
    return found + public_problems(text.replace(results_commit, ""))


def dumps(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def load_rubric(path: Path = RUBRIC) -> dict:
    return yaml.safe_load(Path(path).read_text())


def export(repeatability_file: Path, out: Path, rubric_file: Path = RUBRIC) -> Path:
    rep = json.loads(Path(repeatability_file).read_text())
    text = dumps(build(load_rubric(rubric_file), rep))
    found = check_public(re.sub(r"https?://[^\s\"']+", "", text), rep["results_commit"])
    if found:
        raise SystemExit("refusing to write: " + "; ".join(found[:10]))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out
