"""The datasheet header of a sensor page, its specifications table and the folded detail sections."""
from __future__ import annotations

import base64
import re

import numpy as np

from .geometry import baseline_mm
from .markup import MAP_STAGE, e, each, fov_pair, num, proc_html
from .sensor_parts import map_panel
from .sensor_rig import rig_drawing, rig_table


def _tag(row: dict) -> str:
    tag = row.get("tag", "measured")
    if tag in ("maker", "listing"):
        return f'<a class=sd-tag href="{e(row["src"])}">{tag.capitalize()} ↗</a>'
    return f'<span class=sd-tag>{e({"measured": "Measured", "not_published": "Not published", "supplier": "Supplier's sheet", "dataset": "Dataset", "catalog": "Catalog"}.get(tag, tag))}</span>'


def _auto(row: dict, v: dict) -> dict:
    """Baseline and field of view read from the solve, labelled Measured."""
    if row.get("auto") == "baseline":
        b = baseline_mm(v["run"]["cams"])
        return {"v": f"{num(b, 1)} mm" if b else "One camera in this run"}
    if row.get("auto") == "fov":
        fov = v["fov"]
        if row.get("cams"):  # cameras that differ, labelled in the order given
            text = ", ".join(f"{lab} {fov_pair(fov[i])}" for lab, i in row["cams"].items())
        else:
            text = fov_pair(fov[0])
        out = {"v": f"Calibrated {text}"}
        if row.get("also"):
            out["also"] = row["also"]
        return out
    return row


FOV_FOOT = "~ is read past the range the board corners reached. Past the fit: no value, the edge lies beyond where the lens fit holds."

def _fov_row(k: str, row: dict) -> str:
    html = f'{e(row["v"])}{_tag(row)}'
    if k == "fov" and row.get("also"):
        html += f'<br>{e(row["also"]["v"])}{_tag(row["also"])}'
    return html


def fov_spec(v: dict) -> dict:
    """Specifications row: every camera of the first run, from the calibration."""
    return {"item": "Calibrated field of view", "v": " · ".join(f"cam{i} {fov_pair(f)}" for i, f in enumerate(v["fov"]))}


KEY_ROWS = [("cameras", "Cameras"), ("shutter", "Shutter"), ("fov", "Field of view"), ("baseline", "Baseline"), ("imu", "IMU"), ("output", "Output")]

def thanks_html(t: dict | None) -> str:
    """Strip under a page's header thanking the people named in its data; nothing without an entry."""
    if not t:
        return ""
    name = lambda x: f'<a href="{e(x["url"])}">{e(x["name"])}</a>' if x.get("url") else e(x["name"])
    people = "".join(f'<div><b>{name(x)}</b><span>{e(x["role"])}</span></div>' for x in t["people"])
    return f'<aside class=sd-thanks aria-label="With thanks"><p class=sd-thanks-label>With thanks</p><div class=sd-thanks-people>{people}</div><p class=sd-thanks-note>{e(t["note"])}</p></aside>'


def header_html(slug: str, p: dict, h: dict, v: dict) -> str:
    h = dict(h)
    h["key_specs"] = {k: _auto(r, v) for k, r in h["key_specs"].items()}
    missing = [k for k, _ in KEY_ROWS if k not in h["key_specs"]]
    if missing:
        raise SystemExit(f"{p['title']}: header needs {missing}")
    for k, row in [*h["key_specs"].items(), ("fov", h["key_specs"]["fov"].get("also") or {})]:
        if row.get("tag") in ("maker", "listing") and not str(row.get("src", "")).startswith("https://"):
            raise SystemExit(f"{p['title']}: {k} has no {row['tag']} source")
    if len(h["type"]) > 90:
        raise SystemExit(f"{p['title']}: type line is {len(h['type'])} characters")
    m = h.get("maker")
    maker = f'<a class=sd-maker href="{e(m["url"])}">{e(m["name"])} ↗</a>' if m and m.get("url") else f'<span class="sd-maker none">{e(m["name"] if m else "Maker not confirmed")}</span>'
    fov_v = h["key_specs"]["fov"]["v"]
    foot = h["foot"] + (" · " + FOV_FOOT if "~" in fov_v or "past the fit" in fov_v else "")
    rows = "".join(f'<div class=sd-row><dt>{lab}</dt><dd>{_fov_row(k, h["key_specs"][k])}</dd></div>' for k, lab in KEY_ROWS)
    n = sum(len(g["rows"]) for g in spec_groups(p))
    links = h.get("links", {})
    btn = (f'<a class="sd-btn primary" href="{e(links["product"])}">{e(links.get("product_label", "Product page"))} ↗</a>' if links.get("product") else "") + f'<a class=sd-btn href="#specifications">All specs ({n}) ↓</a>'
    more = "".join(f'<a href="{e(x["url"])}">{e(x["label"])} ↗</a> · ' for x in links.get("more", [])).rstrip(" · ")
    more = f'<p class=sd-more>{more}</p>' if more else ""
    img = h["image"]
    if img.get("kind") != "photo":  # the Sensors overview card shows the same photo
        raise SystemExit(f"{p['title']}: header image must be a photo")
    art = f'<img src="/media/sensors/{slug}/{e(img["file"])}" alt="{e(img["alt"])}" width="800" height="533">'
    cap = f'<a href="{e(img["url"])}">{e(img["credit"])} ↗</a>' if img.get("url") else e(img["credit"])
    return (f'<div class=sd><div class=sd-grid><div class=sd-head>{maker}<h1 id="_top">{e(p["title"])}</h1><p class=sd-type>{e(h["type"])}</p></div>'
            f'<figure class=sd-plate><div class=sd-frame>{art}</div><figcaption>{cap}</figcaption></figure>'
            f'<div class=sd-cta><div class=sd-buttons>{btn}</div>{more}</div>'
            f'<div class=sd-specs><dl class=sd-rows>{rows}</dl><p class=sd-foot>{e(foot)}</p></div></div>{thanks_html(p.get("thanks"))}</div>')


def _decode(a):
    if isinstance(a, dict):
        return np.frombuffer(base64.b64decode(a["bdata"]), dtype=a["dtype"])
    return np.array(a, float)


def proc_preview(v: dict) -> str:
    """A light static picture of the board and rig path, shown on phones before the 3D figure loads."""
    p = v["process"]
    eye = np.array([1.4, -1.4, 0.8])
    fw = -eye / np.linalg.norm(eye)
    rt = np.cross(fw, [0, 0, 1.0])
    rt = rt / np.linalg.norm(rt)
    up = np.cross(rt, fw)
    pr = lambda q: np.c_[q @ rt, q @ up]
    path = pr(np.array(p["spec"]["xyz"], float)[::3])
    out = next((t for t in p["data"] if t.get("name") == "Board Outline"), None)
    board = pr(np.c_[_decode(out["x"]), _decode(out["y"]), _decode(out["z"])]) if out else path[:0]
    board = board[~np.isnan(board).any(axis=1)]
    allp = np.vstack([path, board])
    lo, hi = allp.min(0), allp.max(0)
    W, H = 400, 220
    s = min((W - 40) / np.ptp(allp[:, 0]), (H - 40) / np.ptp(allp[:, 1]))
    S = lambda q: " ".join(f"{W / 2 + s * (x - (lo[0] + hi[0]) / 2):.1f},{H / 2 - s * (y - (lo[1] + hi[1]) / 2):.1f}" for x, y in q)
    return (f'<svg viewBox="0 0 {W} {H}" aria-hidden="true"><polygon points="{S(board)}" fill="var(--strong)" fill-opacity=".1" stroke="var(--muted)"/>'
            f'<polyline points="{S(path)}" fill="none" stroke="var(--accent)" stroke-width="2"/></svg>')


PCHIPS = ('<div class=pchips><span><i style="background:#9333ea"></i>Board corners</span><span><i class=ln style="background:#2563eb"></i>Rig path, darker is later</span>'
          '<span><i style="background:#16a34a"></i>Start</span><span><i style="background:#f59e0b"></i>Current position</span></div>')

def spec_groups(p: dict) -> list:
    """Hand-written groups, or the page's hardware rows grouped by where they came from."""
    h = p["header"]
    if h.get("groups"):
        return [*h["groups"], *([{"title": "Measured in these recordings", "rows": [p["_fov_spec"]]}] if p.get("_fov_spec") else [])]
    titles = {"Maker": "Published by the maker", "Supplier": "From the supplier's sheet", "Listing": "From the seller's listing", "Dataset": "From the dataset", "Catalog": "From our catalog", "Measured": "Measured in these recordings", "Owner": "Maker"}
    groups, unknown = {}, []
    for item, val, tag in p["hardware"]:
        if tag == "Unknown":
            unknown.append(item if val in ("Not published", "Not given", "Not recorded", "Not stated", "Not confirmed") else f"{item}: {val}")
        else:
            groups.setdefault(titles.get(tag, tag), []).append({"item": item, "v": val})
    if p.get("_fov_spec"):
        groups.setdefault(titles["Measured"], []).append(p["_fov_spec"])
    out = [{"title": t, "rows": r} for t, r in groups.items()]
    if unknown:
        out.append({"title": "Not published", "rows": [{"item": "Open", "v": ", ".join(unknown)}]})
    return out


def specs_html(p: dict, v: dict) -> str:
    h = p["header"]
    out = []
    for g in spec_groups(p):
        out.append(f'<tr class=grp><th colspan=2>{e(g["title"])}</th></tr>')
        for r in g["rows"]:
            val = e(r["v"])
            if r.get("url"):
                val = f'<a href="{e(r["url"])}">{val}</a>'
            elif r.get("src"):
                val += f' <a href="{e(r["src"])}" aria-label="Source">↗</a>'
            out.append(f'<tr><td>{e(r["item"])}</td><td>{val}</td></tr>')
    note = f'<p class=note>{e(h["spec_note"])}</p>' if h.get("spec_note") else ""
    if h.get("contact"):
        rows = "".join(f'<tr><td>{e(r["item"])}</td><td>' + (f'<a href="{e(r["url"])}">{e(r["v"])}</a>' if r.get("url") else e(r["v"])) + "</td></tr>" for r in h["contact"])
        note += fold("sales-contact", "Sales contact", "Provided by the maker", f"<div class=scroll><table class=spec-table><tbody>{rows}</tbody></table></div>")
    return f'<div class=scroll><table class=spec-table><tbody>{"".join(out)}</tbody></table></div>{note}'


def fold(fid: str, title: str, key: str, body: str) -> str:
    return f'<details class=fold id="{fid}"><summary>{e(title)} <span>{key}</span></summary><div>{body}</div></details>'


HEADER_PARTS = [("Demo and values", "glance"), ("Calibration process", "process"), ("Solved rig", "rig"), ("Specifications", "specifications"),
                ("Dataset", "dataset"), ("Detailed results", "detail"), ("Limits", "limits"), ("How it was run", "run")]



def header_parts(slug: str, p: dict, vs: list, parts: dict) -> dict:
    """The datasheet layout for a page with a header: adds header and specifications, rewrites glance, process, rig and
    detail. Sets p["_runs"] and p["_fov_spec"], and changes parts in place, so pass copies."""
    h = p["header"]
    p["_runs"] = len(vs)
    p["_fov_spec"] = fov_spec(vs[0])
    parts["header"] = header_html(slug, p, h, vs[0])
    parts["specifications"] = specs_html(p, vs[0])
    band = re.search(r'<div class=band>.*</div>$', parts["glance"], re.S).group(0)
    tabs = re.search(r'<div class=vtabs.*?</div>', parts["lead"], re.S)
    parts["glance"] = (tabs.group(0) if tabs else "") + f'<p>{e(p["lead"])}</p>' + band + f'<p class=sd-note>{e(p["limits"][0])}</p>'
    r0 = vs[0]["run"]
    parts["process"] = ("<p>The solved path of the rig around the board. Press Play or drag the bar to follow it, and use the buttons to change the view.</p>"
                        + each({"variants": vs}, lambda x, i: f'<div class=proc-wrap><button type=button class=proc-open hidden>{proc_preview(x)}<span>Explore in 3D (about 5 MB)</span></button>{proc_html(x, i).replace("▶ Play", "▶\ufe0e Play")}</div>') + PCHIPS)
    parts["rig"] = (f'<p>The solved rig in 3D, to scale. Tap a sensor for its values. Full screen lets you rotate and zoom. Grid squares are 20 mm.</p>{MAP_STAGE}{map_panel()}'
                    '<h3 class=rig-h>To scale, from above and the front</h3>' + each({"variants": vs}, lambda x, i: rig_drawing(x) + rig_table(x))
                    + '<p class=rig-note>Solved by MVIS. Lever arms are in the IMU frame. Rotation is log(R), camera in the IMU frame.</p>')
    parts["detail"] = (fold("lens", "Lens", "Calibrated field of view", parts["lens"]) + fold("imu", "IMU", f'Gyro-to-accel offset {num(r0.get("t_ga_ms"), 2, True)} ms', parts["imu"])
                       + fold("timing", "Timing", f'cam0 td {num(r0["cams"][0]["td_ms"], 2, True)} ms', parts["timing"]) + fold("full-results", "Full results", "Every solved parameter", parts["results"]))
    return parts
