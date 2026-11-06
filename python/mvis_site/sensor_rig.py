"""Rig drawings: the two to-scale views and their table. Pure: a solved variant in, SVG out."""
from __future__ import annotations

import math

import numpy as np

from .geometry import baseline_mm, exp_so3
from .markup import e, fov_pair, num, vec


FAN_CAP_DEG = 170.0

PAST_FIT_NOTE = "Dashed: past the fit, drawn to the corners' reach, so the lens sees at least this much."

def drawn_fov(f: dict, key: str) -> tuple[float, bool]:
    """Full angle to draw for an axis, and whether it's the measured value. Past the fit, draw what the corners reached."""
    if f[key] is not None:
        return f[key], True
    half = f["reach"] if f.get("reach") is not None else f["turn"]
    return min(2 * half, FAN_CAP_DEG), False


def _fan_style(known: bool) -> str:
    return "" if known else ' stroke-dasharray="5 4"'


def _rig_frame(v: dict):
    """Forward, right and up of the rig, from the cameras' own axes. Falls back to cam0 when they point apart."""
    Rs = [exp_so3(c["rotvec"]) for c in v["run"]["cams"]]
    f = np.mean([R[:, 2] for R in Rs], axis=0)
    if np.linalg.norm(f) < 0.5:
        f = Rs[0][:, 2]
    f = f / np.linalg.norm(f)
    pos = np.array([c["p_CinI_mm"] for c in v["run"]["cams"]], float)
    r = Rs[0][:, 0] - (Rs[0][:, 0] @ f) * f
    if len(pos) > 1:  # run across the plate along the baseline, keeping camera-right as its sign
        b = pos[1] - pos[0]
        b = b - (b @ f) * f
        if np.linalg.norm(b) > 1:
            r = b if b @ r >= 0 else -b
    r = r / np.linalg.norm(r)
    return f, r, -np.cross(f, r), Rs


def rig_drawing(v: dict) -> str:
    """Two views to scale, square to the rig, with solved dimensions. Inline SVG, themed by CSS."""
    cams = v["run"]["cams"]
    pos = np.array([c["p_CinI_mm"] for c in cams], float)
    f, r, u, Rs = _rig_frame(v)
    ext = max(float(np.ptp(np.vstack([pos, np.zeros((1, 3))]), axis=0).max()), 40.0)
    reach = ext * 0.42
    above = lambda p: np.array([p @ r, -(p @ f)])
    front = lambda p: np.array([-(p @ r), -(p @ u)])
    tips = [pos[i] + Rs[i][:, 2] * reach for i in range(len(cams))]
    fov = v["fov"]
    past_fit = any(x["h"] is None or x["v"] is None for x in fov)
    for i in range(len(cams)):  # keep the whole field-of-view fan inside the plate
        for k in (-1, 1):
            for t in np.linspace(0, 1, 5):
                h = math.radians(min(max(drawn_fov(fov[i], "h")[0], drawn_fov(fov[i], "v")[0]), FAN_CAP_DEG) / 2) * t
                a = Rs[i][:, 2] @ f, Rs[i][:, 2] @ r
                ang0 = math.atan2(a[1], a[0]) + k * h
                tips.append(pos[i] + reach * (math.cos(ang0) * f + math.sin(ang0) * r))
    pts_a = np.array([above(p) for p in [*pos, *tips, np.zeros(3)]])
    pts_f = np.array([front(p) for p in [*pos, np.zeros(3)]])
    W = 420
    s = min((W - 90) / max(np.ptp(pts_a[:, 0]), 1e-6), (W - 90) / max(np.ptp(pts_f[:, 0]), 1e-6), 300 / max(np.ptp(pts_a[:, 1]), 1e-6))
    colour = ["var(--accent)", "var(--ghost)", "var(--c2)", "var(--c3)"]
    txt = lambda x, y, t, c="dim", a="middle": f'<text class="{c}" x="{x:.1f}" y="{y:.1f}" text-anchor="{a}">{e(t)}</text>'

    box = lambda cx, cy, t: (cx - 3.7 * len(t) - 2, cy - 11, cx + 3.7 * len(t) + 2, cy + 4)
    hit = lambda p, q: p[0] < q[2] and q[0] < p[2] and p[1] < q[3] and q[1] < p[3]

    def place(taken, cands, t, H, cls="dim", style=""):
        """First candidate spot that hits nothing and stays on the plate; None if there is no room."""
        for cx, cy in cands:
            b_ = box(cx, cy, t)
            if b_[0] >= 1 and b_[2] <= W - 1 and b_[1] >= 1 and b_[3] <= H - 1 and not any(hit(b_, o) for o in taken):
                taken.append(b_)
                st = f' style="{style}"' if style else ""
                return f'<text class="{cls}" x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle"{st}>{e(t)}</text>'
        return ""

    def imu(P, taken, H):
        ix, iy = P(np.zeros(3))
        out = [f'<rect class=imu x="{ix - 5:.1f}" y="{iy - 5:.1f}" width="10" height="10" rx="1.5"/>']
        labels = []
        for ax, name, col in ((np.eye(3)[0], "x", "var(--x)"), (np.eye(3)[1], "y", "var(--y)"), (np.eye(3)[2], "z", "var(--z)")):
            tx, ty = P(ax * ext * 0.1)
            if math.hypot(tx - ix, ty - iy) > 6:
                out.append(f'<line x1="{ix:.1f}" y1="{iy:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" stroke="{col}" stroke-width="2"/>')
                taken.append((min(ix, tx) - 2, min(iy, ty) - 2, max(ix, tx) + 2, max(iy, ty) + 2))
                labels.append((tx, ty, tx - ix, ty - iy, name, col))
        for tx, ty, dx, dy, name, col in labels:
            n = math.hypot(dx, dy)
            ux, uy = dx / n, dy / n
            cands = [(tx + ux * 10 + a * uy * 10, ty + uy * 10 + 4 - a * ux * 10) for a in (0, 1, -1)] + [(tx + ux * 18, ty + uy * 18 + 4)]
            out.append(place(taken, cands, name, H, "axis", f"fill:{col};font-weight:700"))
        return "".join(out)

    def name_spots(x, y):
        return [(x, y + 24), (x - 30, y + 18), (x + 30, y + 18), (x - 34, y + 4), (x + 34, y + 4), (x, y + 38), (x, y - 14)]

    def panel(title, project, pts, extra):
        lo, hi = pts.min(0), pts.max(0)
        H = float(np.ptp(pts[:, 1])) * s + extra["pad_top"] + extra["pad_bot"]
        cx = (lo[0] + hi[0]) / 2
        P = lambda p: (W / 2 + s * (project(p)[0] - cx), extra["pad_top"] + s * (project(p)[1] - lo[1]))
        body = extra["draw"](P, H)
        bar = 20 * s
        body += f'<line class=sc x1="{W - 14 - bar:.1f}" y1="{H - 12:.1f}" x2="{W - 14}" y2="{H - 12:.1f}"/><text class=sct x="{W - 14 - bar / 2:.1f}" y="{H - 18:.1f}" text-anchor="middle">20 mm</text>'
        return f'<figure class=rig-view><figcaption>{title}</figcaption><svg viewBox="0 0 {W} {H:.0f}" role="img" aria-label="{title}: solved camera and IMU layout, to scale">{body}</svg></figure>'

    def draw_above(P, H):
        out, taken = [], []
        ix, iy = P(np.zeros(3))
        for i, c in enumerate(cams):  # lever arms first, so cameras sit on top
            x, y = P(pos[i])
            out.append(f'<line class=lever x1="{ix:.1f}" y1="{iy:.1f}" x2="{x:.1f}" y2="{y:.1f}"/>')
        for i, c in enumerate(cams):
            x, y = P(pos[i])
            tx, ty = P(pos[i] + Rs[i][:, 2] * reach)
            col = colour[i % 4]
            ang = math.atan2(ty - y, tx - x)
            R = Rs[i]
            key = "h" if (R[:, 0] @ r) ** 2 + (R[:, 0] @ f) ** 2 >= (R[:, 1] @ r) ** 2 + (R[:, 1] @ f) ** 2 else "v"
            drawn, known = drawn_fov(fov[i], key)
            half = math.radians(min(drawn, FAN_CAP_DEG) / 2)
            rad = math.hypot(tx - x, ty - y)
            a1, a2 = ang - half, ang + half
            out.append(f'<path d="M{x:.1f} {y:.1f}L{x + rad * math.cos(a1):.1f} {y + rad * math.sin(a1):.1f}A{rad:.1f} {rad:.1f} 0 0 1 {x + rad * math.cos(a2):.1f} {y + rad * math.sin(a2):.1f}Z" fill="{col}" fill-opacity=".12" stroke="{col}" stroke-opacity=".7"{_fan_style(known)}/>')
            deg = math.degrees(ang) + 90
            out.append(f'<g class=cam transform="translate({x:.1f} {y:.1f}) rotate({deg:.1f})"><rect x="-11" y="-3" width="22" height="9" rx="2.5" fill="{col}"/><rect x="-4.5" y="-6" width="9" height="4" rx="1" fill="{col}"/></g>')
            taken.append((x - 14, y - 12, x + 14, y + 12))
        taken.append((ix - 7, iy - 7, ix + 7, iy + 7))
        # Baseline sits under everything on the plate, so its line never crosses a label.
        bot = max(P(np.array(p))[1] for p in [*pos, *tips, np.zeros(3)]) + 34
        dim = ""
        if len(cams) > 1:
            (x0, y0), (x1, y1) = P(pos[0]), P(pos[1])
            dim = f'<path class=dl d="M{x0:.1f} {bot - 6:.1f}V{bot + 4:.1f}M{x1:.1f} {bot - 6:.1f}V{bot + 4:.1f}M{x0:.1f} {bot:.1f}H{x1:.1f}"/>'
            t = f'baseline {baseline_mm(cams):.1f} mm'
            dim += txt((x0 + x1) / 2, bot + 16, t)
            taken.append(box((x0 + x1) / 2, bot + 16, t))
            taken.append((min(x0, x1), bot - 6, max(x0, x1), bot + 4))
        out.append(imu(P, taken, H))
        for i, c in enumerate(cams):
            x, y = P(pos[i])
            out.append(place(taken, name_spots(x, y), c["name"], H))
        for i, c in enumerate(cams):
            x, y = P(pos[i])
            cands = [(ix + (x - ix) * k, iy + (y - iy) * k + d) for k in (.5, .4, .6, .3, .7) for d in (4, -12, 20)]
            out.append(place(taken, cands, f'{float(np.linalg.norm(pos[i])):.1f} mm', H))
        return "".join(out) + dim

    def draw_front(P, H):
        out, taken = [], []
        ix, iy = P(np.zeros(3))
        taken.append((ix - 7, iy - 7, ix + 7, iy + 7))
        for i, c in enumerate(cams):
            x, y = P(pos[i])
            col = colour[i % 4]
            out.append(f'<circle class=cam cx="{x:.1f}" cy="{y:.1f}" r="9" fill="none" stroke="{col}" stroke-width="3"/><circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{col}"/>')
            taken.append((x - 11, y - 11, x + 11, y + 11))
        out.append(imu(P, taken, H))
        for i, c in enumerate(cams):
            x, y = P(pos[i])
            out.append(place(taken, name_spots(x, y), c["name"], H))
        return "".join(out)

    return ('<div class=rig-c><div class=rig-views>' + panel("From above", above, pts_a, {"pad_top": 28, "pad_bot": 92, "draw": draw_above})
            + panel("From the front", front, pts_f, {"pad_top": 44, "pad_bot": 76, "draw": draw_front}) + "</div>"
            + (f'<p class=rig-note>{e(PAST_FIT_NOTE)}</p>' if past_fit else "") + "</div>")


def rig_table(v: dict) -> str:
    rows = []
    for i, c in enumerate(v["run"]["cams"]):
        f = v["fov"][i]
        fv = fov_pair(f)
        p = c["p_CinI_mm"]
        rows.append(f'<tr><th>{e(c["name"])}</th><td>{num(p[0], 1, True)}, {num(p[1], 1, True)}, {num(p[2], 1, True)}</td><td>{float(np.linalg.norm(p)):.1f}</td><td>{vec(c["rotvec"], 3)}</td><td>{num(c["td_ms"], 2, True)}</td><td>{fv}</td></tr>')
    return ('<div class="scroll rig-table"><table class=num><thead><tr><th>Camera</th><th>Lever x, y, z (mm)</th><th>Distance (mm)</th><th>log(R) (rad)</th><th>td (ms)</th><th>Field of view</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


