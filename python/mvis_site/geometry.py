"""Rotations and lens geometry for the sensor pages. Pure functions over numbers."""
from __future__ import annotations

import math

import numpy as np


def rotvec(R) -> list[float]:
    """log(R) in rad."""
    R = np.asarray(R, float)
    c = np.clip((np.trace(R) - 1) / 2, -1, 1)
    th = math.acos(c)
    if th < 1e-9:
        return [0.0, 0.0, 0.0]
    if math.pi - th < 1e-4:
        v = np.sqrt(np.maximum((np.diag(R) + 1) / 2, 0))
        i = int(np.argmax(v))
        v = np.sign(R[i]) * v
        v[i] = abs(v[i])
        return (v * th).tolist()
    return (np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) * th / (2 * math.sin(th))).tolist()


def rot_angle_between(a, b) -> float:
    return np.linalg.norm(rotvec(exp_so3(a).T @ exp_so3(b)))


def exp_so3(v) -> np.ndarray:
    v = np.asarray(v, float)
    t = np.linalg.norm(v)
    if t < 1e-12:
        return np.eye(3)
    k = v / t
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def _radius(th: float, k) -> float:
    t2 = th * th
    return th * (1 + t2 * (k[0] + t2 * (k[1] + t2 * (k[2] + t2 * k[3]))))


RADTAN_TOP = math.radians(89)  # a pinhole image never reaches 90 degrees from the axis


def _radtan_radius(th: float, k) -> float:
    """Image radius / f at ray angle th for pinhole + radial-tangential (k1, k2, p1, p2): the radial part only."""
    r2 = math.tan(th) ** 2
    return math.tan(th) * (1 + r2 * (k[0] + r2 * k[1]))


def turn_angle(k, radius=_radius, top: float = math.pi) -> float:
    """Angle (rad) where the fitted curve stops rising; the fit means nothing past it."""
    prev = 0.0
    for i in range(1, 1001):
        t = i * top / 1000
        r = radius(t, k)
        if r < prev:
            return (i - 1) * top / 1000
        prev = r
    return top


def theta_from_radius(rd: float, k, radius=_radius, top: float = math.pi) -> float | None:
    """Invert rd = radius(th) (default th (1 + k1 th^2 + ...)) by bisection; None if the fit never reaches rd."""
    hi = turn_angle(k, radius, top)
    if radius(hi, k) < rd:
        return None
    lo = 0.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if radius(mid, k) < rd:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def eucm_theta(mr: float, a: float, b: float) -> float | None:
    """Ray angle for normalized image radius mr on the EUCM model; None outside its valid range."""
    r2 = mr * mr
    disc = 1 - (2 * a - 1) * b * r2
    if disc < 0:
        return None
    return math.atan2(mr, (1 - b * a * a * r2) / (a * math.sqrt(disc) + 1 - a))


def fov_deg(intr, size, uv, model: str | None = None) -> dict:
    """Field of view from the calibration: the fit read at the image edges, through the principal point.

    An axis is None when a side lies past the fit's turn, or past 90 degrees when the corners never got there.
    h_ext / v_ext mark an axis with a side past the corners' reach (always, without corner data).
    model "radtan" reads the four coefficients as pinhole + radial-tangential; otherwise as the fisheye polynomial.
    """
    fx, fy, cx, cy, *k = intr
    w, h = size
    if len(k) == 2:
        ang = lambda rd: eucm_theta(rd, *k)
        turn = math.pi
    elif model == "radtan":
        ang = lambda rd: theta_from_radius(rd, k, _radtan_radius, RADTAN_TOP)
        turn = turn_angle(k, _radtan_radius, RADTAN_TOP)
    else:
        ang = lambda rd: theta_from_radius(rd, k)
        turn = turn_angle(k)
    reach = None
    if len(uv):
        rd = float(np.hypot((uv[:, 0] - cx) / fx, (uv[:, 1] - cy) / fy).max())
        t = ang(rd)
        reach = turn if t is None else t
    def axis(a, b):
        ts = ang(a), ang(b)
        if None in ts:
            return None, True
        past = reach is None or max(ts) > reach
        if max(ts) > math.pi / 2 and (reach is None or reach < math.pi / 2):
            return None, True
        return math.degrees(sum(ts)), past
    fh, he = axis(cx / fx, (w - cx) / fx)
    fv, ve = axis(cy / fy, (h - cy) / fy)
    return {"h": fh, "v": fv, "h_ext": he, "v_ext": ve, "reach": None if reach is None else math.degrees(reach), "turn": math.degrees(turn)}


def lens_radius(th: float, k, model: str | None = None) -> float:
    if model == "radtan":
        return _radtan_radius(th, k)
    if len(k) == 2:
        a, b = k
        x, z = math.sin(th), math.cos(th)
        return x / (a * math.sqrt(b * x * x + z * z) + (1 - a) * z)
    return _radius(th, k)


def baseline_mm(cams) -> float:
    return float(np.linalg.norm(np.subtract(cams[1]["p_CinI_mm"], cams[0]["p_CinI_mm"]))) if len(cams) > 1 else None


