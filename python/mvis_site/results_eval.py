"""The Results pages: the Leaderboard (one row per family) and one Dataset eval page per dataset. Pure: dicts in, texts
out; site/scripts/export_results.py reads the inputs and writes what `render` returns, or nothing.

Inputs
  pub     python/data/public_results.yaml: every word that is not computed, the page order and the sensor ids
  space   space.space_rows / space.uzh_rows: the Space's merged rows, cell states and ◆ differences (app.delta), so the
          site counts ◆ with the board's own code
  records repeatability.load_records of the same snapshot: solved n of N per tool
  stats   the private stats file of the batch: only min and max per (row, tool) leave it, as named keys
  rep     repeatability.json: the cells are read there by the page; here only for the legacy hashes
  boards  {dataset id: rendered board HTML} (board.json, uzh_fpv.json): the ◆ tallies must equal the board's

No total, rank or score is computed. Rows keep record order (sensor, then parameter), never a value order.
Rotation rows are not shown (none in the records; they wait for a user OK).
"""
from __future__ import annotations

import html
import json
import re
import statistics

from .lint import public_problems, refusals, strip_urls
from .repeatability import check_public, finite, recordings

RESULTS = "/benchmark/results/"
HUB_RESULTS = "https://huggingface.co/datasets/calibench-vi/results"
OUT_DIR = "site/src/data/eval"
NAV_FILE = "site/src/data/results-nav.json"
MDX_DIR = "site/src/content/docs/benchmark/results"

# Space column -> the tool it stands for (shape and colour mark identity only) and the record method behind it.
TOOL_OF = {"calyx": "MVIS", "mvis": "MVIS", "kalibr": "Kalibr", "basalt": "Basalt"}
METHOD = {"calyx": "MVIS", "mvis": "MVIS (Kalibr IMU model)", "kalibr": "Kalibr", "basalt": "Basalt"}
# The per-recording dict of the stats row behind each column (repeatability.BLOCK_DICT, the gate checks the pairing).
STATS_DICT = {"calyx": "calyx", "mvis": "mvis_all", "kalibr": "kalibr", "basalt": "basalt"}
KIMU = "MVIS (K-IMU)"
TOOLS = ("MVIS", "Kalibr", "Basalt")

CLASSES = (("intr", "Focal length + principal point"), ("dist", "Distortion"), ("length", "Baseline and lever"),
           ("time", "Time"), ("scale", "IMU scale"), ("cross", "IMU cross-axis"))
STATE_WORD = {"fixed": "input", "shown": "different model, not compared",
              "shown_no_value": "different model, no value", "other_model": "different model, not compared"}
# The Space's missing_reason words, as a lane says them.
MISSING_WORD = {"no data": "no value", "no run": "not run", "not in model": "not in this tool's model",
                "not in one run": "not in one run", "not reported": "not reported"}
ON_AXIS = ("ok", "fixed")  # a value of another model would stretch the axis; it is printed, not drawn


# ---------------------------------------------------------------- small helpers
def base(key: str) -> str:
    return key.split("[")[0]


def param_class(key: str) -> str | None:
    """The chart class of a parameter key; None for rows that are not charted (fit, Kalibr model terms)."""
    b = base(key)
    if b in ("fx", "fy", "cx", "cy"):
        return "intr"
    if b == "dist":
        return "dist"
    if b in ("baseline_mm", "lever_mm"):
        return "length"
    if b in ("td_ms", "tr_ms", "t_ga_ms"):
        return "time"
    if b in ("Dw", "Da"):
        i, j = re.findall(r"\d+", key)
        return "scale" if i == j else "cross"
    return None


def fmt(v: float, dec: int, sign: bool = False) -> str:
    s = "%.*f" % (dec, v)
    if float(s) == 0:
        s = s.lstrip("-")
    if sign and float(s) > 0:
        s = "+" + s
    return s.replace("-", "−")


def decimals(decs: dict, key: str, values=()) -> int:
    """The Space's precision per row (app.DECIMALS, and _row_dec's 3 decimals for large distortion coefficients)."""
    if base(key) == "dist" and any(abs(v) >= 10 for v in values):
        return 3
    return decs.get(base(key), 4)


def sig(x: float, n: int = 6) -> float:
    return float(f"{x:.{n}g}")


def is_camimu(mode: str) -> bool:
    return mode not in ("camera", "camera only")


def columns(camimu: bool) -> list[tuple[str, str]]:
    """(Space column, label) of a family. Camera-only families have one MVIS run, so one MVIS column."""
    if camimu:
        return [("calyx", "MVIS"), ("mvis", KIMU), ("kalibr", "Kalibr"), ("basalt", "Basalt")]
    return [("mvis", "MVIS"), ("kalibr", "Kalibr"), ("basalt", "Basalt")]


def pair_label(pair: list, camimu: bool) -> str:
    name = {"mvis": KIMU if camimu else "MVIS", "kalibr": "Kalibr", "basalt": "Basalt"}
    return f"{name[pair[1]]} − {name[pair[2]]}"


def short(sensor: str) -> str:
    return sensor.split(" – ")[-1]


# ---------------------------------------------------------------- min / max from the private stats file
def minmax(stats_row: dict | None, col: str, n: int) -> dict | None:
    """{min, max} of the per-recording values behind one record cell, or None. Only these two named numbers leave the
    stats file. The count must be the record's n, else the stats row is not the record's and the export stops."""
    if not stats_row or not n:
        return None
    v = list(finite(stats_row.get(STATS_DICT[col])).values())
    if len(v) != n:
        raise ValueError(f"{stats_row['sensor']} {stats_row['key']} {col}: {len(v)} values in the stats file, record n {n}")
    return {"min": sig(min(v)), "max": sig(max(v))}


# ---------------------------------------------------------------- one family
def lane(col: str, label: str, cell: dict | None, stats_row: dict | None, dec: int, other_model: bool = False) -> dict:
    """One tool's lane of a parameter chart. other_model: the Space says the tools' models differ on this row (its
    delta reason "model"), so a non-MVIS value is printed, not drawn, as repeatability.MODEL_DIFFERS treats it."""
    out = {"col": col, "tool": TOOL_OF[col], "label": label}
    if not cell:
        return dict(out, state="missing", note="no value")
    if cell["state"] in ("missing", "shown_no_value"):
        return dict(out, state="missing", note=STATE_WORD.get(cell["state"]) or MISSING_WORD.get(cell["reason"], cell["reason"]))
    if other_model and TOOL_OF[col] != "MVIS" and cell["state"] in ON_AXIS:
        cell = dict(cell, state="other_model")
    out.update(state=cell["state"], med=cell["med"], sd=cell["sd"], n=cell["n"], text=fmt(cell["med"], dec))
    if cell["state"] != "ok":
        out["note"] = STATE_WORD[cell["state"]]
    if cell["state"] not in ON_AXIS:
        return out
    mm = minmax(stats_row, col, cell["n"])
    if mm:
        out.update(mm)
    return out


def axis(lanes: list[dict]) -> dict | None:
    """Shared axis of one parameter: centred on the cross-tool median, half-width to the farthest whisker or box edge."""
    on = [x for x in lanes if x["state"] in ON_AXIS]
    if not on:
        return None
    c = statistics.median(x["med"] for x in on)
    far = [abs(v - c) for x in on
           for v in (x["med"], x["med"] - (x["sd"] or 0), x["med"] + (x["sd"] or 0), x.get("min", x["med"]), x.get("max", x["med"]))]
    h = max(far) * 1.1 or max(abs(c) * 1e-6, 1e-9)
    return {"c": sig(c), "h": sig(h)}


def tg_tiles(rows: list[dict], cols: list[tuple[str, str]], sid: dict) -> list[dict]:
    """Kalibr IMU-model terms (Tg), one 3x3 tile per sensor and tool that has values; never on the Dw scale."""
    out = []
    sensors = list(dict.fromkeys(r["sensor"] for r in rows if base(r["key"]) == "Tg"))
    for s in sensors:
        for col, label in cols:
            cells = {}
            for r in rows:
                c = r.get(col)
                if r["sensor"] == s and base(r["key"]) == "Tg" and c and c["state"] == "ok":
                    i, j = re.findall(r"\d+", r["key"])
                    cells[f"{i}{j}"] = {"med": c["med"], "sd": c["sd"], "text": fmt(c["med"], 3)}
            if cells:
                out.append({"sensor": short(s), "sensor_id": sid[s], "col": col, "tool": TOOL_OF[col], "label": label,
                            "cells": cells})
    return out


def fit_rows(rows: list[dict], cols: list[tuple[str, str]], decs: dict) -> list[dict]:
    """Reprojection median per camera and tool: fit of each tool's own model, not accuracy; never in differences."""
    out = []
    for r in rows:
        if r["key"] != "reproj_median":
            continue
        vals = {col: fmt(r[col]["med"], decimals(decs, r["key"])) for col, _ in cols
                if r.get(col) and r[col]["state"] == "ok"}
        if vals:
            out.append({"sensor": short(r["sensor"]), "by_col": vals})
    return out


def diffs(rows: list[dict], pairs: list, camimu: bool, decs: dict, sid: dict) -> list[dict]:
    """Per tool pair, every compared row in record order: Δ = a − b (the Space's app.delta) and Δ in units of the
    larger sd. A pair with nothing compared is left out."""
    out = []
    for p in pairs:
        items = []
        for r in rows:
            d = r["deltas"][p[0]]
            if d["value"] is None:
                continue
            a, b = r[p[1]], r[p[2]]
            spread = max(a["sd"] or 0.0, b["sd"] or 0.0)
            dec = decimals(decs, r["key"], [x["med"] for x in (a, b)])
            items.append({"sensor": short(r["sensor"]), "sensor_id": sid[r["sensor"]], "key": r["key"], "label": r["label"],
                          "unit": r["unit"], "text": fmt(d["value"], dec, sign=True), "spread": fmt(spread, dec),
                          "z": None if spread == 0 else round(d["value"] / spread, 3),
                          "marked": bool(d["marked"]), "unequal_n": bool(d["unequal_n"])})
        if items:
            out.append({"pair": p[0], "label": pair_label(p, camimu), "a": TOOL_OF[p[1]], "b": TOOL_OF[p[2]],
                        "marked": sum(x["marked"] for x in items), "compared": len(items), "rows": items})
    return out


def sensors(rows: list[dict], cols: list[tuple[str, str]], stats_rows: dict, decs: dict, sid: dict) -> list[dict]:
    """Charted parameters by sensor, in record order: one lane per tool column."""
    out = {}
    for r in rows:
        cls = param_class(r["key"])
        if cls is None:
            continue
        srow = stats_rows.get((r["sensor"], r["key"]))
        vals = [r[c]["med"] for c, _ in cols if r.get(c) and r[c]["med"] is not None]
        dec = decimals(decs, r["key"], vals)
        other = any(d.get("reason") == "model" for d in r["deltas"].values())
        lanes = [lane(c, label, r.get(c), srow, dec, other) for c, label in cols]
        if not any(x["state"] in ON_AXIS for x in lanes):
            continue
        s = out.setdefault(sid[r["sensor"]], {"id": sid[r["sensor"]], "label": short(r["sensor"]), "params": []})
        s["params"].append({"key": r["key"], "label": r["label"], "unit": r["unit"], "cls": cls, "axis": axis(lanes),
                            "lanes": lanes})
    return list(out.values())


def solved(records: dict, T: str, of: int) -> list[dict]:
    """Solved n of N per tool, from the records' n_recordings (repeatability.recordings); a reason where a tool did not run."""
    rec = recordings(records, T, of)
    return [dict(rec[t], tool=t) for t in TOOLS]


def family(T: str, meta: dict, shutter: str, sp: dict, pairs: list, decs: dict, records: dict, stats_fam: dict,
           sid: dict, hub: dict) -> dict:
    camimu = is_camimu(meta["mode"])
    of = meta.get("n_recordings") or 0
    done = solved(records, T, of)
    ran = {x["tool"] for x in done if "reason" not in x}
    rows = sp["rows"]
    # a tool that did not run gets no lanes, nor a method that holds no value (a study without the K-IMU run)
    cols = [(c, l) for c, l in columns(camimu) if TOOL_OF[c] in ran and any((r.get(c) or {}).get("med") is not None for r in rows)]
    unmapped = sorted({r["sensor"] for r in rows} - set(sid))
    if unmapped:
        raise ValueError(f"{T}: sensors without an id in public_results.yaml: {unmapped}")
    stats_rows = {(r["sensor"], r["key"]): r for r in stats_fam["rows"]}
    ds = diffs(rows, pairs, camimu, decs, sid)
    return {"id": T, "title": meta.get("title") or T, "mode": "cam+imu" if camimu else "cam", "shutter": shutter,
            "n": of, "columns": [{"col": c, "tool": TOOL_OF[c], "label": l} for c, l in cols],
            "solved": done, "read_first": _no_notes_ref(sp["read_first"]),
            "notes": sp["notes"], "records": hub, "fit": fit_rows(rows, cols, decs),
            "diffs": ds, "tally": {d["pair"]: [d["marked"], d["compared"]] for d in ds},
            "sensors": sensors(rows, cols, stats_rows, decs, sid), "model_terms": tg_tiles(rows, cols, sid),
            "has_tga": any(base(r["key"]) == "t_ga_ms" for r in rows)}


def hub_links(T: str, batch: str, commit: str | None) -> dict:
    """The public record files behind a family's numbers, at the results commit."""
    if not commit:
        return {}
    return {t: f"{HUB_RESULTS}/blob/{commit}/{t}/{batch}/{T}.json" for t in TOOLS}


# ---------------------------------------------------------------- ◆ tallies of a rendered board
_TH_D = re.compile(r'<th class="d" scope="col">(.*?)</th>', re.S)
_TD = re.compile(r'<td class="([^"]*)">(.*?)</td>', re.S)


def _text(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def board_tallies(board_html: str, pairs: list) -> dict:
    """{family: {pair: [marked, compared]}} read off the rendered board (main tables only, not the MVIS-default fold):
    a ◆ cell is marked, a cell with a number is compared."""
    head = {(p[3] + p[4]).replace(" ", ""): p[0] for p in pairs}
    out = {}
    for fam in re.split(r'<details class="fam"', board_html)[1:]:
        T = _text(re.search(r"<h3>(.*?)</h3>", fam).group(1)).split(" · ")[0]
        tally = out.setdefault(T, {})
        for sn in re.split(r'<details class="sn', fam)[1:]:
            if sn.startswith(' calyx"'):
                continue
            pids = [head[_text(h).replace(" ", "")] for h in _TH_D.findall(sn)]
            for tr in re.findall(r"<tr[^>]*data-k[^>]*>(.*?)</tr>", sn, re.S):
                dcells = [(c, t) for c, t in _TD.findall(tr) if c.split()[0] == "d"]
                for pid, (cls, txt) in zip(pids, dcells):
                    if "na" in cls.split() or not _text(txt):
                        continue
                    m, n = tally.get(pid, [0, 0])
                    tally[pid] = [m + ("fl" in cls.split()), n + 1]
    return out


def tally_problems(fams: list[dict], board: dict) -> list[str]:
    """Families whose ◆ counts differ from the rendered board's. The board wins."""
    return [f"{f['id']}: ◆ {f['tally']} here, board {board.get(f['id'])}" for f in fams if f["tally"] != board.get(f["id"], {})]


# ---------------------------------------------------------------- legacy hashes
def caveat_letters(rep_ds: dict) -> list[str]:
    """The caveat letters the old page used for a dataset (RepeatabilityMatrix: first use, a, b, c, ...)."""
    seen = []
    for f in rep_ds["families"]:
        for g in rep_ds["groups"]:
            for c in (f["cells"].get(g) or {}).get("caveats", []):
                if c not in seen:
                    seen.append(c)
    return list("abcdefghijklmnop"[:len(seen)])


def legacy(rep_ds: dict | None, ds_id: str) -> list[str]:
    """Old hashes of /benchmark/results/ that now live on this dataset's page. ds-<id> goes to the page's top; the
    caveat (rp-cav-*) and cell (rp-<family>-<group>) ids keep their names there, made by the same components."""
    if rep_ds is None:
        return []
    return [f"ds-{ds_id}", *(f"rp-cav-{ds_id}-{l}" for l in caveat_letters(rep_ds)),
            *(f"rp-{f['id']}-{g}" for f in rep_ds["families"] for g, c in f["cells"].items() if c["state"] != "na")]


# ---------------------------------------------------------------- pages
def _no_notes_ref(text: str) -> str:
    """The Space's read-first line points at a Notes section the dataset pages no longer show (2026-11-11)."""
    return text.replace("Data settings differ: see Notes.", "Data settings differ between the tools.")


def dataset(entry: dict, sp: dict, records: dict, stats: dict, batch: str, commit: str | None, rep_ds: dict | None) -> dict:
    fams_meta = records["families"]["families"]
    sid = entry["sensors"]
    fams = [family(f["id"], fams_meta[f["id"]], f["shutter"], sp["families"][f["id"]], sp["pairs"], sp["decimals"],
                   records, stats["families"][f["id"]], sid, hub_links(f["id"], batch, commit)) for f in entry["families"]]
    for f in fams:  # a study names why the other tools did not run (repeatability.NOT_RUN covers the board's families)
        for s in f["solved"]:
            if "reason" in s and entry.get("not_run"):
                s["reason"] = entry["not_run"]
    keep = ("slug", "id", "label", "title", "ours", "licence", "intro", "chips", "image", "links", "reading",
            "no_repeatability", "study_note")
    return {**{k: entry[k] for k in keep if k in entry}, "study": bool(entry.get("study")), "batch": batch,
            "results_commit": commit, "link": f"{RESULTS}{entry['slug']}/", "has_repeatability": rep_ds is not None,
            "legacy": legacy(rep_ds, entry["id"]), "families": fams,
            "full_tables": "study" if entry["id"] == "uzh_fpv" else None if entry.get("study") else "board"}


def leaderboard(pages: list[dict], pub: dict, batch: str, commit: str) -> dict:
    """The Leaderboard rows: every family of every dataset in page order; solved and ◆ tallies only. The repeatability
    cells are read from repeatability.json by the page itself."""
    rows = []
    for p in pages:
        if p["study"]:
            continue
        rows.append({"slug": p["slug"], "id": p["id"], "label": p["label"], "ours": p["ours"], "link": p["link"],
                     "families": [{"id": f["id"], "title": f["title"], "mode": f["mode"], "shutter": f["shutter"],
                                   "n": f["n"], "solved": f["solved"],
                                   "diffs": {d["pair"]: {"label": d["label"], "marked": d["marked"], "compared": d["compared"]}
                                             for d in f["diffs"]}} for f in p["families"]]})
    study = [{"label": p["label"], "link": p["link"], "batch": p["batch"], "note": p.get("study_note", "")} for p in pages if p["study"]]
    return {"batch": batch, "results_commit": commit, "honest": pub["leaderboard"]["honest"], "datasets": rows,
            "studies": study}


def nav(pages: list[dict]) -> list[dict]:
    return [{"label": p["label"], "link": p["link"], "slug": p["slug"], "legacy": p["legacy"]} for p in pages]


def mdx(page: dict) -> str:
    """The thin page wrapper: headings in MDX so they reach the table of contents; every part from the page JSON.
    Coverage and parameters by sensor only (user, 2026-11-11); repeatability, tool differences, model notes, reading
    notes and full tables stay in the JSON and are left off the page for now."""
    s = page["slug"]
    desc = (f"MVIS, Kalibr and Basalt over every recording of {page['label']}: what each tool solved, and each "
            "parameter's spread per sensor. Repeatability, not accuracy.")
    parts = [f"---\ntitle: {json.dumps(page['title'], ensure_ascii=False)}\ndescription: {json.dumps(desc, ensure_ascii=False)}\n"
             "pageType: reference\nwide: true\n---\n",
             "{/* Generated by site/scripts/export_results.py from python/data/public_results.yaml and the records. Edit those, not this file. */}\n",
             "import * as E from '../../../../components/eval/index';",
             f"import page from '../../../../data/eval/{s}.json';\n",
             "<E.EvalHeader page={page} />\n",
             "<E.RpOpen />\n"]
    for i, f in enumerate(page["families"]):
        parts.append(f"## {f['id']} · {'camera + IMU' if f['mode'] == 'cam+imu' else 'camera only'}\n")
        parts.append(f"<E.FamilyHead page={{page}} i={{{i}}} />\n")
        parts.append("### Coverage\n")
        parts.append(f"<E.Coverage page={{page}} i={{{i}}} />\n")
        parts.append("### Parameters by sensor\n")
        parts.append(f"<E.Parameters page={{page}} i={{{i}}} />\n")
    return "\n".join(parts)


# ---------------------------------------------------------------- checks and the plan
def lint_text(text: str, commit: str | None) -> str:
    """What the public lint sees: links, our own /benchmark/results/ paths and the results commit taken out."""
    text = strip_urls(text)
    text = re.sub(r"/benchmark/results/[a-z0-9-]*/?", "/", text)
    return text.replace(commit, "") if commit else text


def problems(files: dict[str, str], commit: str, private: tuple[str, ...] = ()) -> list[str]:
    """Every output through the public lint and repeatability.check_public (no recording names or per-recording arrays)."""
    out = []
    for name, text in files.items():
        clean = lint_text(text, commit)
        found = check_public(clean, commit, private) if name.endswith(".json") else public_problems(clean)
        found += [f"refused: {w}" for w in refusals(text)]
        out += [f"{name}: {p}" for p in found]
    return out


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def render(pages: list[dict], pub: dict, batch: str, commit: str, boards: dict[str, str], pairs: list) -> dict[str, str]:
    """{path relative to the checkout: text}. Refuses (ValueError) when a ◆ tally differs from its rendered board."""
    bad = []
    for p in pages:
        if p["id"] in boards:
            bad += tally_problems(p["families"], board_tallies(boards[p["id"]], pairs))
        elif not p["study"] or any(f["tally"] for f in p["families"]):
            bad.append(f"{p['id']}: no rendered board to check its ◆ counts against")
    if bad:
        raise ValueError("◆ counts differ from the rendered board:\n  " + "\n  ".join(bad))
    files = {f"{OUT_DIR}/index.json": dumps(leaderboard(pages, pub, batch, commit)), NAV_FILE: dumps(nav(pages))}
    for p in pages:
        files[f"{OUT_DIR}/{p['slug']}.json"] = dumps(p)
        files[f"{MDX_DIR}/{p['slug']}.mdx"] = mdx(p)
    return files


# ---------------------------------------------------------------- reading and writing (the only steps with files)
def collect(leaderboard_dir, records_dir, stats_file, batch: str, commit: str, uzh_root, site,
            studies: dict | None = None) -> tuple[list[dict], dict, list, dict, tuple]:
    """(pages, pub, pairs, boards, private words) from the inputs. Stops when the records, the stats file,
    repeatability.json and board.json are not one batch and one commit. studies: {slug: stats file} of every separate
    study other than UZH-FPV (its public_results.yaml entry names batch, read_first and like_for_like)."""
    import tempfile
    from pathlib import Path

    import yaml

    from . import DATA
    from . import leaderboard as L
    from . import space
    from .repeatability import gate, load_records, private_words

    if not re.fullmatch(r"[0-9a-f]{40}", commit or ""):
        raise ValueError("results_commit must be the full 40-hex sha of the records snapshot")
    site = Path(site)
    pub = yaml.safe_load((DATA / "public_results.yaml").read_text(encoding="utf-8"))
    stats = json.loads(Path(stats_file).read_text())
    records = load_records(records_dir, batch)
    found = gate(stats, records, batch)
    rep = json.loads((site / "site/src/data/leaderboard/repeatability.json").read_text())
    board = json.loads((site / "site/src/data/leaderboard/board.json").read_text())
    if (rep["batch"], rep["results_commit"]) != (batch, commit):
        found.append(f"repeatability.json is {rep['batch']} {rep['results_commit']}, not {batch} {commit}")
    if (board["batch"], board["results_commit"]) != (batch, commit[:7]):
        found.append(f"board.json is {board['batch']} {board['results_commit']}, not {batch} {commit[:7]}")
    sp = space.space_rows(leaderboard_dir, records_dir, commit)
    ustats = L.without_repeated_weights_note(L.rekey(json.loads((Path(uzh_root) / L.UZH_STATS).read_text())))
    with tempfile.TemporaryDirectory(prefix="results_eval_") as tmp:
        usp = space.uzh_rows(leaderboard_dir, ustats, Path(tmp) / "rec")
        urec = load_records(Path(tmp) / "rec", L.BATCH)
    found += gate(ustats, urec, L.BATCH)
    studies = {k: json.loads(Path(v).read_text()) for k, v in (studies or {}).items()}
    other = {e["slug"]: e for e in pub["datasets"] if e.get("study") and e["slug"] != "uzh-fpv"}
    if set(studies) != set(other):
        found.append(f"study stats given for {sorted(studies)}, public_results.yaml lists {sorted(other)}")
    srows = {}
    for slug in set(studies) & set(other):
        e, st = other[slug], studies[slug]
        with tempfile.TemporaryDirectory(prefix="results_eval_") as tmp:
            rows = space.study_rows(leaderboard_dir, st, Path(tmp) / "rec", e["batch"], (e["id"], e["stats_key"], e["label"]),
                                    e["read_first"], e["like_for_like"])
            recs = load_records(Path(tmp) / "rec", e["batch"])
        found += gate(st, recs, e["batch"])
        srows[slug] = (rows, recs, st)
    if found:
        raise SystemExit("inputs disagree:\n  " + "\n  ".join(found[:40]))
    boards = dict(board["datasets"], uzh_fpv=json.loads((site / L.UZH_FILE).read_text())["fragment"])
    reps = {d["id"]: d for d in rep["datasets"]}
    pages = [dataset(e, *srows[e["slug"]], e["batch"], None, None) if e["slug"] in srows
             else dataset(e, usp, urec, ustats, L.BATCH, None, None) if e.get("study")
             else dataset(e, sp, records, stats, batch, commit, reps[e["id"]]) for e in pub["datasets"]]
    # UZH bag names are UZH's own public sequence names, already on its page; only the batch's recording names are private.
    return pages, pub, sp["pairs"], boards, private_words(stats) + tuple(w for _, _, st in srows.values() for w in private_words(st))


def write(files: dict[str, str], site, commit: str, private: tuple = ()) -> list:
    """Writes every file, or none when one has a problem. Generated MDX of a dataset no longer listed is removed."""
    from pathlib import Path

    found = problems(files, commit, private)
    if found:
        raise SystemExit("refusing to write:\n  " + "\n  ".join(found[:20]))
    site = Path(site)
    keep = {site / p for p in files}
    for old in (site / MDX_DIR).glob("*.mdx"):
        if old not in keep:
            old.unlink()
    for p, text in files.items():
        (site / p).parent.mkdir(parents=True, exist_ok=True)
        (site / p).write_text(text, encoding="utf-8")
    return sorted(keep)
