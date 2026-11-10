"""The parts of a public sensor page, one HTML fragment per section. Pure: loaded runs and page text in, markup out."""
from __future__ import annotations

import re

from .geometry import baseline_mm
from .markup import (MAP_STAGE, PARAMS, board_svg, e, each, fov_text, imu_bars, lens_svg, num, proc_html, series_tables, tiles, timing_svg,
                     vec)
from .sensor_rig import drawn_fov

PARTS = [("Demo and values", "glance"), ("Calibration process", "process"), ("Sensor calibration map", "map"), ("Hardware", "hardware"),
         ("Dataset", "dataset"), ("Lens", "lens"), ("IMU", "imu"), ("Timing", "timing"), ("Full results", "results"),
         ("Limits", "limits"), ("How it was run", "run")]

PLOTLY_LOCAL = "/media/sensors/plotly-3.0.1.min.js"



def _no_cells(kind, i, c, j):
    return ""


def public_results(v, cells=_no_cells, ref_label: str | None = None) -> str:
    """The full results table. cells(kind, cam index, cam, row index) adds cells to a row; mira's private pages put
    their reference columns there, headed by ref_label. The public pages add none."""
    extra = 0 if ref_label is None else 2
    span = f"<th colspan={2 + extra}>"
    rows = []
    for i, c in enumerate(v["run"]["cams"]):
        rows.append(f'<tr class=grp>{span}{e(c["name"])}</th></tr>')
        names = PARAMS.get(len(c["intr"]), [f"p{j}" for j in range(len(c["intr"]))])
        for j, n in enumerate(names):
            rows.append(f'<tr><td>{n}{" px" if j < 4 else ""}</td><td>{num(c["intr"][j], 2 if j < 4 else 5)}</td>{cells("intr", i, c, j)}</tr>')
        for k, ax in enumerate("xyz"):
            rows.append(f'<tr><td>Lever {ax} mm</td><td>{num(c["p_CinI_mm"][k], 2, True)}</td>{cells("lever", i, c, k)}</tr>')
        rows.append(f'<tr><td>log(R) rad</td><td>{vec(c["rotvec"], 4)}</td>{cells("rot", i, c, 0)}</tr>')
        rows.append(f'<tr><td>td ms</td><td>{num(c["td_ms"], 3, True)}</td>{cells("td", i, c, 0)}</tr>')
        rows.append(f'<tr><td>Reprojection px</td><td>{num(c["reproj"], 3)}</td>{cells("reproj", i, c, 0)}</tr>')
        if abs(v["readout_ms"][i]) > 0.01:
            rows.append(f'<tr><td>Readout ms</td><td>{num(v["readout_ms"][i], 2, True)}</td>{cells("readout", i, c, 0)}</tr>')
    rows.append(f"<tr class=grp>{span}IMU</th></tr>")
    r = v["run"]
    rows.append(f'<tr><td>t_ga ms</td><td>{num(r.get("t_ga_ms"), 2, True)} ± {num(r.get("t_ga_sigma_ms"), 2)}</td>{cells("tga", None, None, 0)}</tr>')
    head = "" if ref_label is None else f"<th>{e(ref_label)}</th><th>MVIS − {e(ref_label)}</th>"
    return f'<div class=scroll><table class=num><thead><tr><th>Parameter</th><th>MVIS</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def rig_json(v, site: bool = True) -> dict:
    """One run for the map script. The site draws fans from the field of view (draw_h/draw_v); the private pages
    trace image-edge rays instead, so they get the plain values. ref is None unless the run carries reference columns."""
    def fov(i):
        f = v["fov"][i]
        return {**f, "draw_h": drawn_fov(f, "h")[0], "draw_v": drawn_fov(f, "v")[0]} if site else f
    cams = [{"name": c["name"], "p": c["p_CinI_mm"], "r": c["rotvec"], "intr": c["intr"], "size": v["sizes"][i], "td": c["td_ms"],
             "reproj": c["reproj"], "fov": fov(i), "readout": v["readout_ms"][i]} for i, c in enumerate(v["run"]["cams"])]
    ref = v.get("ref")
    refs = [{"name": f["name"], "p": f["p_CinI_mm"], "r": f["rotvec"], "intr": f["intr"], "size": v["sizes"][i], "td": f["td_ms"]}
            for i, f in enumerate(ref[:len(cams)])] if ref else None
    return {"cams": cams, "ref": refs, "imu": {"Dw": v["run"].get("Dw_diag"), "Da": v["run"].get("Da_diag"), "tga": v["run"].get("t_ga_ms")},
            "baseline": baseline_mm(v["run"]["cams"]), "label": v["label"]}


# Section text and markup shared with mira's private pages, so the two can't drift apart.
PROCESS_LEAD = "The path of the rig around the board, as MVIS solved it. Press Play or drag the bar to follow the calibration."
MAP_LEAD = "The solved positions and orientations, to scale in the IMU frame. Drag sideways to orbit. Tap a sensor to see its values."
LENS_NOTE = ("We read these from the calibrated lens fit at the image edges, through the principal point (where the optical axis meets the image). "
             "~ marks an axis past where the corners reached, so the fit is extrapolated there. "
             "Past the fit means an edge lies beyond where the fit holds, so we give no value.")


def run_tabs(vs) -> str:
    if len(vs) < 2:
        return ""
    return '<div class=vtabs role=group aria-label="Choose a run">' + "".join(
        f'<button type=button data-vt="{i}" aria-pressed="{"true" if i == 0 else "false"}">{e(v["label"])}</button>' for i, v in enumerate(vs)) + "</div>"


def fov_line(v) -> str:
    return " · ".join(fov_text(i, f) for i, f in enumerate(v["fov"]))


def lens_section(vs) -> str:
    legend = "".join(f'<i class=c{i}></i>{e(c["name"])} ' for i, c in enumerate(vs[0]["run"]["cams"]))
    return (each({"variants": vs}, lambda v, i: f'<p>Calibrated field of view, horizontal × vertical. {fov_line(v)}</p><div class=chart>{lens_svg(v)}</div>')
            + f'<p class=legend>{legend}</p><p class=note>{LENS_NOTE}</p>')


def imu_pinned(r) -> bool:
    """IMU intrinsics held at identity in the solve: every gyro and accel scale is exactly 1."""
    vals = list(r.get("Dw_diag") or []) + list(r.get("Da_diag") or [])
    return bool(vals) and all(v == 1.0 for v in vals)


def imu_section(vs) -> str:
    def one(v, i):
        r = v["run"]
        tga = f'<code>t_ga</code>, the time offset between the gyroscope and accelerometer channels: {num(r.get("t_ga_ms"), 2, True)} ± {num(r.get("t_ga_sigma_ms"), 2)} ms.'
        if imu_pinned(r):
            return f'<p>This solve pinned the IMU intrinsics at identity, so it estimated no scales. {tga}</p>'
        return f'<p>Each bar shows a scale as its deviation from 1. IMU model: {e(r["imu_model"])}. {tga}</p>{imu_bars(r)}'
    return each({"variants": vs}, one)


def timing_section(vs) -> str:
    return '<p>The time offsets, to scale. td is the camera–IMU time offset, with t_imu = t_cam + td.</p>' + each({"variants": vs}, lambda v, i: f'<div class=chart>{timing_svg(v["run"])}</div>')


def source_note(p: dict) -> str:
    """Where the maker's specs came from, if the page says."""
    if not p.get("source"):
        return ""
    label = p.get("source_label", p["source"].replace("https://", ""))
    return f'<p class=note>Maker\'s specs from <a href="{e(p["source"])}">{e(label)}</a>, checked {p.get("checked", "2026-10-15")}.</p>'


def demo_keys(d: dict) -> list[int]:
    """For each tab, the index of the first entry with the same clip, so tabs can share a file."""
    froms = [x["from"] for x in d["by_variant"]]
    return [froms.index(f) for f in froms]


def clip(src: str, poster: str, note: str, autoplay: bool = True) -> str:
    """A demo video with its caption."""
    return (f'<figure class=demo><video src="{e(src)}" poster="{e(poster)}"{" autoplay" if autoplay else ""} muted loop playsinline controls preload=metadata></video>'
            f'<figcaption>{e(note)}</figcaption></figure>')


def _clip(base: str, note: str, autoplay: bool = True) -> str:
    return clip(f"{base}.mp4", f"{base}.jpg", note, autoplay)


def demo_block(d: dict | None, media_url: str) -> str:
    """The clip on a page, or with `by_variant` one per tab; only the first tab's plays on load."""
    if not d:
        return '<div class="demo empty"><b>No video on this page.</b> The values below come from the solved run.</div>'
    if "by_variant" in d:
        keys = demo_keys(d)
        return each({"variants": d["by_variant"]}, lambda x, i: _clip(f"{media_url}/demo{keys[i]}", x["note"], i == 0))
    return _clip(d["existing"] if "existing" in d else f"{media_url}/demo", d["note"])


def hub_links(html: str) -> str:
    """__HUB:community/xq20/__ or __HUB:datasets/converted/x/__ becomes a link to that folder on the Hub."""
    def link(m: re.Match) -> str:
        repo, path = m.group(1), m.group(2)
        name = "Calibench community" if repo == "community" else "Calibench"
        return f'<a href="https://huggingface.co/datasets/calibench-vi/{repo}/tree/main/{e(path)}">{name}, {e(path)}</a> (access by automatic approval)'
    return re.sub(r"__HUB:(community|datasets)/(.+?)__", link, html)


def dataset_rows(p: dict, data_url: str) -> str:
    """Dataset table rows. A page whose own rows place __LINK__ scopes the licence itself, so the generic rows stay out."""
    return hub_links(_dataset_rows(p, data_url))


def _dataset_rows(p: dict, data_url: str) -> str:
    rows = list(p["dataset"])
    if p.get("folder"):
        link = f"{data_url}/{p['folder']}"
        if not any("__LINK__" in b for _, b in rows):
            rows += [["Licence", "CC BY-NC 4.0, for the data and for this page's clip and figures; commercial use by request"], ["Hosted", "__LINK__"]]
        return "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td></tr>" for a, b in rows).replace("__LINK__", f'<a href="{e(link)}">Calibench, {e(p["folder"])}</a> (access by automatic approval)')
    if p.get("data_link"):
        rows.append(["Data", "__LINK__"])
    ds = "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td></tr>" for a, b in rows)
    if p.get("data_link"):
        ds = ds.replace("__LINK__", f'<a href="{e(p["data_link"]["url"])}">{e(p["data_link"]["label"])}</a>')
    return ds


def glance(demo: str, vs: list) -> str:
    """The demo beside each run's value tiles."""
    return f'<div class=band>{demo}{each({"variants": vs}, lambda v, i: tiles(v["run"]))}</div>'


def process_section(note: str, vs: list) -> str:
    """The lead, a note on what the figures leave out, and each run's process figure."""
    return f"<p>{PROCESS_LEAD} {note}</p>" + each({"variants": vs}, proc_html)


def map_panel(extra: str = "") -> str:
    """The pick list and info box under the map stage, closing the stage's wrapper; extra goes between them."""
    return f'<div class=panel><div class=picks id=picks></div>{extra}<div id=info></div></div></div>'


def hardware_table(rows: str, note: str = "") -> str:
    return f'<div class=scroll><table><thead><tr><th>Item</th><th>Value</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table></div>{note}'


def dataset_block(rows: str, board: dict, tags: dict) -> str:
    """The dataset table beside the drawn board."""
    return f'<div class=two><div class=scroll><table><tbody>{rows}</tbody></table></div><div>{board_svg(board, tags)}</div></div>'


def example_row(p: dict) -> str:
    """Dataset table row linking the worked example for this rig, if it has one."""
    ex = p.get("example")
    return f'<tr><td>Worked example</td><td><a href="{e(ex["url"])}">{e(ex["label"])}</a></td></tr>' if ex else ""


def parts_for(key: str, p: dict, s: dict, vs: list, series, data_url: str, media_url: str, tags: dict) -> dict:
    """Every part of a page. p["sha"], when set, is the recording's sha256 (computed by export_sensors.collect)."""
    demo = demo_block(p.get("demo"), media_url)
    both = {"variants": vs}
    src = source_note(p)
    if p.get("company"):
        src += f'<p class=note>Company: <a href="{e(p["company"]["url"])}">{e(p["company"]["name"])}</a>.</p>'
    hw = "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td><td><span class=chip>{e(c)}</span></td></tr>" for a, b, c in p["hardware"])
    ds = dataset_rows(p, data_url) + example_row(p)
    run = [p["method"]]
    if p.get("sha"):
        run.append(f'sha256 of the recording: <code>{p["sha"]}</code>')
    return {
        "lead": (f'<figure class=sensorimg><img src="{media_url}/{e(p["image"]["file"])}" alt="{e(p["image"]["alt"])}" loading=lazy><figcaption>{e(p["image"]["caption"])}</figcaption></figure>' if p.get("image") else "") + f'<p class=lead>{e(p["lead"])}</p><div class=chips>' + "".join(f"<span class=chip>{e(c)}</span>" for c in p["chips"]) + "</div>" + run_tabs(vs),
        "glance": glance(demo, vs),
        "process": process_section("Camera images are left out to keep the page small.", vs),
        "map": f'<p>{MAP_LEAD}</p>{MAP_STAGE}{map_panel()}',
        "hardware": hardware_table(hw, src),
        "dataset": dataset_block(ds, s["board"], tags),
        "lens": lens_section(vs),
        "imu": imu_section(vs),
        "timing": timing_section(vs),
        "results": f'<p>Rotation is log(R) in rad, camera in the IMU frame.</p>' + each(both, lambda v, i: public_results(v)) + series_tables(series),
        "limits": '<ul class=list>' + "".join(f"<li>{e(x)}</li>" for x in p["limits"]) + "</ul>",
        "run": '<ul class=list>' + "".join(f"<li>{x if x.startswith('sha256') else e(x)}</li>" for x in run) + "</ul>",
    }


