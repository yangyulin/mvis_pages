"""HTML pieces shared by the public sensor pages and the private report pages. Pure: numbers in, markup out."""
from __future__ import annotations

import html
import math

import numpy as np

from .geometry import baseline_mm, lens_radius

e = html.escape


def num(v, dec=2, sign=False) -> str:
    if v is None:
        return "not stored"
    s = f"{v:+.{dec}f}" if sign else f"{v:.{dec}f}"
    return s.replace("-", "−")


def vec(v, dec=2) -> str:
    return "[" + ", ".join(num(x, dec, True) for x in v) + "]"


def chip(text, state) -> str:
    return f'<span class="chip {state}">{e(text)}</span>'


def fov_pair(f: dict) -> str:
    """H x V; ~ marks an axis read past the corners' reach."""
    one = lambda x, ext: "past the fit" if x is None else f"{'~' if ext else ''}{num(x, 0)}°"
    if f["h"] is None and f["v"] is None:
        return "past the fit"
    return f"{one(f['h'], f['h_ext'])} × {one(f['v'], f['v_ext'])}"


def fov_text(i: int, f: dict) -> str:
    seen = f", corners reach {num(f['reach'], 0)}° from the axis" if f["reach"] is not None else ", no corner data"
    return f"cam{i}: {fov_pair(f)}{seen}"


def lens_svg(v) -> str:
    W, H, L, B = 560, 260, 54, 40
    deg_max = 90
    r_max = 2.0 if len(v["run"]["cams"][0]["intr"]) == 6 else 1.6
    x = lambda t: L + t / deg_max * (W - L - 12)
    y = lambda r: H - B - r / r_max * (H - B - 12)
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Image radius against ray angle for each camera">']
    for t in range(0, 91, 15):
        parts.append(f'<line class=g x1={x(t):.1f} x2={x(t):.1f} y1=12 y2={H-B} /><text x={x(t):.1f} y={H-B+16} text-anchor=middle>{t}°</text>')
    for i in range(5):
        r = r_max * i / 4
        parts.append(f'<line class=g x1={L} x2={W-12} y1={y(r):.1f} y2={y(r):.1f} /><text x={L-6} y={y(r)+4:.1f} text-anchor=end>{r:.1f}</text>')
    parts.append(f'<text x={(W+L)/2} y={H-6} text-anchor=middle>Ray angle from the optical axis</text><text x=12 y={(H-B)/2} text-anchor=middle transform="rotate(-90 12 {(H-B)/2})">Image radius / f</text>')
    for i, c in enumerate(v["run"]["cams"]):
        k = c["intr"][4:]
        pts = []
        for t in range(0, 91, 3):
            r = lens_radius(math.radians(t), k)
            if 0 <= r <= r_max:
                pts.append(f"{x(t):.1f},{y(r):.1f}")
        parts.append(f'<polyline class="c{i}" points="{" ".join(pts)}"/>')
    parts.append("</svg>")
    return "".join(parts)


def chessboard_svg(b) -> str:
    """A chessboard to scale: rows x cols squares, black at the top left, one square of white margin."""
    sq, cols, rows = b["square_mm"], b["cols"], b["rows"]
    w, h = cols * sq, rows * sq
    d = "".join(f"M{c * sq:.2f} {r * sq:.2f}h{sq:.2f}v{sq:.2f}h{-sq:.2f}z" for r in range(rows) for c in range(cols) if (r + c) % 2 == 0)
    m = sq
    return (f'<figure class=board><svg viewBox="{-m:.1f} {-m:.1f} {w + 2 * m:.1f} {h + 2 * m:.1f}" role="img" aria-label="Chessboard {rows} by {cols} squares, to scale">'
            f'<rect x="{-m:.1f}" y="{-m:.1f}" width="{w + 2 * m:.1f}" height="{h + 2 * m:.1f}" fill="#fff"/><path fill="#111" d="{d}"/></svg>'
            f'<figcaption>Chessboard {cols} × {rows} squares ({cols - 1} × {rows - 1} inner corners), {sq:g} mm squares, '
            f'{w:.0f} × {h:.0f} mm. To scale</figcaption></figure>')


def charuco_svg(b) -> str:
    """A ChArUco board to scale: the chessboard squares, black at the top left, and each white square's marker as a plain
    black square (marker_mm); the ArUco bit patterns aren't drawn."""
    sq, mk, cols, rows = b["square_mm"], b["marker_mm"], b["cols"], b["rows"]
    w, h, o = cols * sq, rows * sq, (sq - mk) / 2
    d = "".join(f"M{c * sq:.2f} {r * sq:.2f}h{sq:.2f}v{sq:.2f}h{-sq:.2f}z" if (r + c) % 2 == 0
                else f"M{c * sq + o:.2f} {r * sq + o:.2f}h{mk:.2f}v{mk:.2f}h{-mk:.2f}z" for r in range(rows) for c in range(cols))
    m = sq
    return (f'<figure class=board><svg viewBox="{-m:.1f} {-m:.1f} {w + 2 * m:.1f} {h + 2 * m:.1f}" role="img" aria-label="ChArUco board {rows} by {cols} squares, to scale">'
            f'<rect x="{-m:.1f}" y="{-m:.1f}" width="{w + 2 * m:.1f}" height="{h + 2 * m:.1f}" fill="#fff"/><path fill="#111" d="{d}"/></svg>'
            f'<figcaption>ChArUco {cols} × {rows} squares ({cols - 1} × {rows - 1} inner corners), {sq:g} mm squares, '
            f'{mk:g} mm {b.get("dictionary", "ArUco")} markers, {w:.0f} × {h:.0f} mm. To scale; marker patterns not drawn</figcaption></figure>')


def board_svg(b, tags: dict) -> str:
    """The AprilGrid to scale: Kalibr layout, tag 0 at bottom left, each tag 6x6 data bits inside a 2-bit black border, black squares at the gaps' crossings.

    tags: tag id (as a string) to its 6x6 bit rows, from assets.apriltag().
    A board with type "chessboard" (rows, cols = squares, square_mm) is drawn by chessboard_svg instead, and one with
    type "charuco" (also marker_mm, dictionary) by charuco_svg.
    """
    if b.get("type") == "chessboard":
        return chessboard_svg(b)
    if b.get("type") == "charuco":
        return charuco_svg(b)
    tag = b["tag_mm"]
    gap = tag * b["spacing"]
    cols, rows = b["cols"], b["rows"]
    w, h = cols * tag + (cols - 1) * gap, rows * tag + (rows - 1) * gap
    bits = tags
    cell = tag / 10
    d = []
    box = lambda x, y, a, c: d.append(f"M{x:.2f} {y:.2f}h{a:.2f}v{c:.2f}h{-a:.2f}z")
    for r in range(rows + 1):
        for c in range(cols + 1):
            box(c * (tag + gap) - gap, r * (tag + gap) - gap, gap, gap)
    white = []
    for r in range(rows):
        for c in range(cols):
            x, y = c * (tag + gap), r * (tag + gap)
            box(x, y, tag, tag)
            code = bits[str((rows - 1 - r) * cols + c)]
            for i, row in enumerate(code):
                for j, v in enumerate(row):
                    if v == "0":
                        white.append(f"M{x + (j + 2) * cell:.2f} {y + (i + 2) * cell:.2f}h{cell:.2f}v{cell:.2f}h{-cell:.2f}z")
    m = gap * 2
    return (f'<figure class=board><svg viewBox="{-m:.1f} {-m:.1f} {w + 2 * m:.1f} {h + 2 * m:.1f}" role="img" aria-label="AprilGrid {rows} by {cols}, to scale">'
            f'<rect x="{-m:.1f}" y="{-m:.1f}" width="{w + 2 * m:.1f}" height="{h + 2 * m:.1f}" fill="#fff"/><path fill="#111" d="{"".join(d)}"/><path fill="#fff" d="{"".join(white)}"/></svg>'
            f'<figcaption>AprilGrid {rows} × {cols}, {w:.0f} × {h:.0f} mm. Standard pattern, to scale</figcaption></figure>')


def imu_bars(r) -> str:
    rows = []
    for label, vals in (("Gyro scale", r.get("Dw_diag")), ("Accel scale", r.get("Da_diag"))):
        for ax, val in zip("xyz", vals or []):
            dev = (val - 1) * 100
            w = min(abs(dev) / 8 * 50, 50)
            left = 50 if dev >= 0 else 50 - w
            rows.append(f'<div class=bar><span>{label} {ax}</span><i><u style="left:{left:.2f}%;width:{w:.2f}%"></u></i><b>{num(dev, 2, True)} %</b></div>')
    return "<div class=bars>" + "".join(rows) + '<div class=bar><span></span><em><s>−8 %</s><s>0</s><s>+8 %</s></em><b></b></div></div>'


def timing_svg(r) -> str:
    vals = [(c["name"] + " td", c["td_ms"]) for c in r["cams"]] + [("t_ga", r["t_ga_ms"])]
    lim = max(10, math.ceil(max(abs(v) for _, v in vals) / 10) * 10)
    W, L, row = 560, 70, 34
    H = row * len(vals) + 34
    x = lambda v: L + (v + lim) / (2 * lim) * (W - L - 60)
    p = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Time offsets in milliseconds, to scale">']
    for v in (-lim, -lim / 2, 0, lim / 2, lim):
        p.append(f'<line class="g{" z" if v == 0 else ""}" x1={x(v):.1f} x2={x(v):.1f} y1=4 y2={H-24} /><text x={x(v):.1f} y={H-8} text-anchor=middle>{v:+.0f} ms</text>')
    for i, (n, v) in enumerate(vals):
        cy = 18 + i * row
        p.append(f'<text x=0 y={cy+4}>{n}</text><line class=stem x1={x(0):.1f} x2={x(v):.1f} y1={cy} y2={cy} /><circle class=dot cx={x(v):.1f} cy={cy} r=5 /><text x={x(v)+(9 if v>=0 else -9):.1f} y={cy+4} text-anchor={"start" if v>=0 else "end"}>{num(v,2,True)}</text>')
    p.append("</svg>")
    return "".join(p)


MAP_STAGE = """<div class=map><div class=stage><canvas id=rig tabindex=0 aria-label="3D map of the cameras and IMU"></canvas><div class=tools><button data-view=iso type=button>3D</button><button data-view=front type=button>Front</button><button data-view=top type=button>Top</button><button data-view=side type=button>Side</button><button data-z=1 type=button aria-label="Zoom in">+</button><button data-z=-1 type=button aria-label="Zoom out">−</button></div></div>"""

PARAMS = {8: ["fx", "fy", "cx", "cy", "k1", "k2", "k3", "k4"], 6: ["fx", "fy", "cx", "cy", "alpha", "beta"]}

def _ms(vals, dec=2) -> str:
    return f"{num(float(np.median(vals)),dec,True)} ± {num(float(np.std(vals, ddof=1)),dec)}"


def series_table(s) -> str:
    runs = s["runs"]
    rows = []
    for i, c0 in enumerate(runs[0]["cams"]):
        rows.append(f'<tr class=grp><th colspan=2>{e(c0["name"])}</th></tr>')
        for k, ax in enumerate("xyz"):
            rows.append(f'<tr><td>Lever {ax} mm</td><td>{_ms([r["cams"][i]["p_CinI_mm"][k] for r in runs])}</td></tr>')
        rows.append(f'<tr><td>td ms</td><td>{_ms([r["cams"][i]["td_ms"] for r in runs],3)}</td></tr>')
    rows.append("<tr class=grp><th colspan=2>IMU</th></tr>")
    rows.append(f'<tr><td>t_ga ms</td><td>{_ms([r["t_ga_ms"] for r in runs])}</td></tr>')
    return f'<h3>Across {e(s["label"])}: median ± sd</h3><div class=scroll><table class=num><tbody>{"".join(rows)}</tbody></table></div>'


def series_tables(series: list[dict]) -> str:
    return "".join(series_table(s) for s in series)


def reproj(r) -> tuple[str, float]:
    """The run's headline reprojection error: the median when the solve gives one, else the RMS."""
    med = r.get("reproj_median_px")
    return ("median", med) if med is not None else ("RMS", r["reproj_rms_px"])


def tiles(r) -> str:
    kind, value = reproj(r)
    rep = (f"Reprojection {kind}", value)
    c0 = r["cams"][0]
    base = baseline_mm(r["cams"])
    b = f'<b>{num(base,1)}<small> mm</small></b>' if base is not None else "<b>–</b>"
    return (f'<div class=tiles><div><span>{rep[0]}</span><b>{num(rep[1],2)}<small> px</small></b></div><div><span>cam0–cam1 baseline</span>{b}</div>'
            f'<div><span>cam0 td</span><b>{num(c0["td_ms"],2,True)}<small> ms</small></b></div><div><span>cam0 lever arm</span><b>{num(float(np.linalg.norm(c0["p_CinI_mm"])),1)}<small> mm</small></b></div></div>')


def each(d, fn) -> str:
    multi = len(d["variants"]) > 1
    return "".join(f'<div class=v data-v="{i}"{" hidden" if multi and i else ""}>{fn(v, i)}</div>' for i, v in enumerate(d["variants"]))


def proc_html(v, i):
    if not v["process"]:
        return '<div class=empty><b>Needs a new solve.</b> This run predates the figure. A solve on current MVIS adds it.</div>'
    last = len(v["process"]["spec"]["xyz"]) - 1
    views = v["process"]["spec"].get("views", [])
    pick = (f'<select class="mvis-progress-cam" aria-label="Camera shown">' + "".join(f'<option value="{k}">{e(x["name"])}</option>' for k, x in enumerate(views)) + "</select>") if len(views) > 1 else ""
    return (f'<div class=procplot id="proc{i}"></div><div class="mvis-progress" data-plot="proc{i}"><button type=button>▶ Play</button>{pick}<input type=range min=0 max={last} value={last} step=1 aria-label="Calibration progress"><span class="mvis-progress-label">Loading</span></div>')


