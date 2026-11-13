"""The rules behind the site's browser and media checks, as pure functions. browser/ only measures pages and files."""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import unquote

# --- sidebar (nav_check) ---------------------------------------------------------------------------------------
SECTIONS = ["Getting started", "Guides", "Why calibrate", "Benchmark", "Device wiki", "Datasets", "Concepts", "Reference", "Contribute", "About"]
BENCHMARK = ["Leaderboard", "Methodology", "Datasets eval", "Examples"]
DEEP_PAGES = ["/devices/intel-t265/", "/benchmark/examples/monado/", "/benchmark/results/tum-vi/", "/concepts/notation/", "/reference/cli/", "/about/license/", "/why/tga/"]
NOT_IN_SIDEBAR = {"/"}


def routes(docs: Path) -> set[str]:
    """Every page route from the MDX tree under site/src/content/docs."""
    out = set()
    for p in Path(docs).rglob("*.mdx"):
        rel = p.relative_to(docs).with_suffix("").as_posix()
        rel = "" if rel == "index" else rel.removesuffix("/index")
        out.add(f"/{rel}/" if rel else "/")
    return out


def sidebar_problems(s: dict, nav: list[dict], results_nav: list[dict] | None = None) -> list[str]:
    """Top-level sections, Benchmark, and the Device wiki: Overview, then one subgroup per sensor-nav.json group in its
    order, each holding its sensors once. With results_nav, Benchmark › Datasets eval holds one page per results-nav.json entry in its order. s is a measured sidebar
    {sections, children, groups, links, paths}; paths maps "A › B › C" to the labels inside that group."""
    out = []
    if results_nav is not None:
        paths = s.get("paths", {})
        want = {"Benchmark › Datasets eval": [n["label"] for n in results_nav]}
        out += [f"{p} holds {paths.get(p)}, want {w}" for p, w in want.items() if paths.get(p) != w]
    if s["sections"] != SECTIONS:
        out.append(f"sections are {s['sections']}")
    if s["children"].get("Benchmark") != BENCHMARK:
        out.append(f"Benchmark holds {s['children'].get('Benchmark')}")
    by_group = {}
    for n in nav:
        by_group.setdefault(n["group"], []).append(n["label"])
    want = ["Overview", *by_group]
    if s["children"].get("Device wiki") != want:
        out.append(f"Device wiki holds {s['children'].get('Device wiki')}, want {want}")
    got = s["groups"].get("Device wiki", {})
    out += [f"Device wiki › {g} holds {got.get(g)}, want {labels}" for g, labels in by_group.items() if got.get(g) != labels]
    return out


# --- moved pages and internal links (check_moves, on the built docs/) ---------------------------------------------
_REFRESH = re.compile(r'http-equiv="refresh"\s+content="0;\s*url=([^"]+)"')
_REPLACE = re.compile(r"<script>location\.replace\('([^']+)'")
_HREF = re.compile(r'href="(/(?!/)[^"]*)"')


def redirect_target(html: str) -> str | None:
    """Where a redirect page sends the reader (Astro's meta refresh, or a hash-keeping script page); None for a real page."""
    m = _REPLACE.search(html) or _REFRESH.search(html)
    return m.group(1) if m else None


def _route(docs: Path, f: Path) -> str:
    rel = f.relative_to(docs).as_posix()
    return "/" + rel.removesuffix("index.html") if rel.endswith("index.html") else "/" + rel


def _resolves(docs: Path, link: str) -> bool:
    path = unquote(link.split("#")[0].split("?")[0]).lstrip("/")
    if not path or path.endswith("/"):
        return (docs / path / "index.html").is_file()
    return (docs / path).is_file() or (docs / path / "index.html").is_file()


def check_moves(docs: Path, moved: dict[str, str]) -> list[str]:
    """On a built site: each moved old address is a redirect page straight to its new one, each new address a real page;
    no redirect anywhere points at a redirect or at nothing; every internal link on a real page resolves."""
    docs = Path(docs)
    pages = {_route(docs, f): f.read_text(encoding="utf-8", errors="replace") for f in sorted(docs.rglob("*.html"))}
    target = {r: redirect_target(h) for r, h in pages.items()}
    out = []
    for old, new in moved.items():
        if old not in pages:
            out.append(f"{old}: no page at the old address")
        elif target[old] is None:
            out.append(f"{old}: still a real page, want a redirect to {new}")
        elif target[old] != new:
            out.append(f"{old}: redirects to {target[old]}, want {new}")
        if new not in pages:
            out.append(f"{new}: new address has no page")
        elif target[new] is not None:
            out.append(f"{new}: new address is a redirect, not a page")
    for r, to in target.items():
        if to is None:
            continue
        dest = to if to.endswith("/") else to + "/"
        if dest not in pages:
            out.append(f"{r}: redirects to {to}, which has no page")
        elif target[dest] is not None:
            out.append(f"{r}: redirects to {to}, which redirects again")
    for r, h in pages.items():
        if target[r] is None:
            out += [f"{r}: broken link {link}" for link in dict.fromkeys(_HREF.findall(h)) if not _resolves(docs, link)]
    return out


def local_links(links) -> list[str]:
    """The sidebar's own links; it also holds external ones."""
    return sorted({link for link in links if link.startswith("/")})


def unlisted(all_routes: set[str], links) -> list[str]:
    return [f"{route}: not in the sidebar" for route in sorted(all_routes - set(links) - NOT_IN_SIDEBAR)]


def status_problems(statuses: dict[str, int]) -> list[str]:
    """Links that didn't load, from link -> HTTP status."""
    return [f"{link}: HTTP {code}" for link, code in statuses.items() if code != 200]


def closed_problems(opened: dict[str, bool]) -> list[str]:
    """Deep pages whose own sidebar entry sits in a folded section, from link -> shown open."""
    return [f"{link}: current page not shown open" for link, ok in opened.items() if not ok]


def maker_heights_problem(heights) -> list[str]:
    heights = set(heights)
    return [f"maker lines differ in height at 320 px: {sorted(heights)}"] if len(heights) > 1 else []


# --- homepage layout (responsive_check) ------------------------------------------------------------------------
TAP_MIN_PX, CTA_MIN_PX = 40, 44  # phone hero: every tap target, and the primary call to action
VIDEO_MIN_PHONE, VIDEO_MIN = 0.40, 0.30  # hero video width over viewport width
DEVICES = [  # name, class, viewport, dpr, mobile
    ("iphone-se", "phone", (375, 553), 2, True),
    ("iphone-13", "phone", (390, 664), 3, True),
    ("pixel-7", "phone", (412, 839), 2.625, True),
    ("iphone-13-landscape", "phone-land", (750, 342), 3, True),
    ("ipad-mini", "tablet", (768, 1024), 2, True),
    ("ipad-air-landscape", "tablet", (1180, 820), 2, True),
    ("laptop-1280x720", "laptop", (1280, 664), 1, False),
    ("laptop-1366x768", "laptop", (1366, 712), 1, False),
    ("laptop-1440x900", "laptop", (1440, 844), 2, False),
    ("laptop-1536x864", "laptop", (1536, 808), 1.25, False),
    ("desktop-1920x1080", "desktop", (1920, 1024), 1, False),
    ("desktop-2560x1440", "desktop", (2560, 1384), 1, False),
]
# laptop/desktop viewports subtract ~56 px of browser chrome from the nominal screen height


def evaluate(cls, m):
    """Layout verdicts for one device class from the page's measured boxes."""
    res = {}
    res["overflow"] = m["scrollW"] <= m["vw"] + 1
    vh, vw = m["vh"], m["vw"]
    if cls in ("phone", "tablet", "phone-land"):
        ok = all(m.get(k) and m[k]["bottom"] <= vh + 1 for k in ("title", "video", "cta"))
        res["first"] = ok
    else:
        res["fold"] = bool(m.get("bar")) and m["bar"]["bottom"] <= vh + 1
    if cls == "phone":
        small = [t for t in m["taps"] if t["h"] < TAP_MIN_PX]
        res["taps"] = not small and bool(m.get("cta")) and m["cta"]["h"] >= CTA_MIN_PX
        if small:
            res["taps_small"] = small[:6]
    vmin = VIDEO_MIN_PHONE if cls == "phone" else VIDEO_MIN
    res["video"] = bool(m.get("video")) and m["video"]["w"] >= vmin * vw
    return res


# Content pages (responsive_check --pages): at a phone and a laptop width, in both themes, no horizontal page scroll.
PAGE_VIEWS = [("phone-390", 390, 844, "light"), ("phone-390", 390, 844, "dark"),
              ("laptop-1360", 1360, 900, "light"), ("laptop-1360", 1360, 900, "dark")]


def page_problems(path: str, view: str, theme: str, m: dict) -> list[str]:
    """Why a content page fails at one view: it scrolls sideways, or the theme did not apply."""
    out = []
    if m["scrollW"] > m["vw"] + 1:
        out.append(f"{path} {view} {theme}: scrolls sideways ({m['scrollW']} > {m['vw']} px; widest {m.get('wide')})")
    if m.get("theme") != theme:
        out.append(f"{path} {view} {theme}: page theme is {m.get('theme')}")
    return out


def shot_name(path: str, view: str, theme: str) -> str:
    return f"{path.strip('/').replace('/', '_') or 'home'}-{view}-{theme}.png"


# --- hero media (check_hero_media) -----------------------------------------------------------------------------
REQUIRED = ["key", "chip", "caption", "duration", "live_cycle", "sensors", "window", "rms", "td", "xlabel", "xval", "corners", "tiles"]
KEYFRAME_GAP_S = 1.05
PHONE_BUDGET_MB = 2.5
FPS = 30


def parse_stream(csv: str) -> tuple[int, int, float, int]:
    """ffprobe stream=width,height,nb_frames,r_frame_rate as csv=p=0: (width, height, fps, frames)."""
    out = csv.strip().split(",")
    num, den = out[2].split("/")
    return int(out[0]), int(out[1]), float(num) / float(den), int(out[3])


def keyframe_times(csv: str) -> list[float]:
    return sorted(float(x.strip(",")) for x in csv.split() if x.strip(","))


def max_gap(ts: list[float], fps: float, nframes: int) -> float:
    """Longest stretch without a keyframe, the last one to the clip's end included."""
    return max([b - a for a, b in zip(ts, ts[1:])] + [nframes / fps - ts[-1]])


def hero_files(r: dict) -> dict:
    k = r["key"]
    files = {"hero": f"hero_{k}.mp4", "phone": f"hero_{k}_960.mp4"}
    for cam in r["tiles"]:
        files[f"tile {cam[0]}"] = f"{k}_{cam[0]}.mp4"
        files[f"small {cam[0]}"] = f"{k}_{cam[0]}_240.mp4"
    return files


def want_width(role: str) -> int:
    return {"hero": 1920, "phone": 960}.get(role.split()[0], 400 if role.startswith("tile") else 240)


def check_hero_media(media: Path, rigs: list, stream, keyframes) -> tuple[list[str], list[str]]:
    """(problems, one status line per recording). stream(path) and keyframes(path) are the ffprobe readers."""
    errors, lines = [], []
    if not rigs:
        errors.append("rigs.json lists no recordings")
    for r in rigs:
        k = r.get("key", "?")
        missing = [f for f in REQUIRED if f not in r]
        if missing:
            errors.append(f"{k}: rigs.json missing {missing}")
            continue
        frames = {}
        for role, f in hero_files(r).items():
            path = os.path.join(media, f)
            for need in (path, path[:-4] + ".jpg"):
                if not os.path.exists(need):
                    errors.append(f"{k}: missing {os.path.basename(need)}")
            if not os.path.exists(path):
                continue
            w, h, fps, n = parse_stream(stream(path))
            frames[role] = n
            ww = want_width(role)
            if w != ww or (role in ("hero", "phone") and h != ww * 9 // 16):
                errors.append(f"{k}: {f} is {w}x{h}, expected width {ww}")
            gap = max_gap(keyframe_times(keyframes(path)), fps, n)
            if gap > KEYFRAME_GAP_S:
                errors.append(f"{k}: {f} keyframes up to {gap:.2f} s apart (max 1 s)")
        if len(set(frames.values())) > 1:
            errors.append(f"{k}: frame counts differ across hero/phone/tiles {frames}")
        if abs(frames.get("hero", 0) / FPS - r["duration"]) > 0.05:
            errors.append(f"{k}: rigs.json duration {r['duration']} s != hero {frames.get('hero', 0) / FPS:.2f} s")
        phone = [os.path.join(media, f) for f in (f"hero_{k}_960.mp4", f"hero_{k}_960.jpg")]
        phone_mb = sum(os.path.getsize(f) for f in phone if os.path.exists(f)) / 1e6
        if phone_mb > PHONE_BUDGET_MB:
            errors.append(f"{k}: phone first load {phone_mb:.2f} MB > 2.5 MB")
        ok = not any(e.startswith(k + ":") for e in errors)
        lines.append(f"{'ok  ' if ok else 'FAIL'} {k:7s} {len(r['tiles'])} cams, {frames.get('hero', 0)} frames, phone {phone_mb:.2f} MB")
    return errors, lines


# --- hero video sync (hero_sync_check) -------------------------------------------------------------------------
FREEZE_MAX, DRIFT_MAX, RECOVER_MAX_S = 0.3, 0.3, 4.0
SAMPLE_S = 0.1


def pause_round(rows: list[dict]) -> tuple[float, float]:
    """(longest freeze in s, worst drift in s) of the views after one pause or double-click, sampled every 0.1 s.
    The first 0.5 s settle; samples while paused, rewinding, or across a recording change don't count."""
    n = len(rows[0]["c"])
    run, freeze, drift = [0] * n, [0] * n, 0.0
    for a, b in zip(rows[5:], rows[6:]):
        if b["hp"] or b["h"] < a["h"] or len(b["c"]) != n or a["rig"] != b["rig"]:
            continue
        for k in range(n):
            run[k] = run[k] + 1 if b["c"][k]["t"] - a["c"][k]["t"] < 0.02 else 0
            freeze[k] = max(freeze[k], run[k])
            drift = max(drift, abs(b["c"][k]["t"] - b["h"]))
    return max([0.0] + [f * SAMPLE_S for f in freeze]), drift


def pause_verdict(freeze: float, drift: float) -> tuple[bool, str]:
    return freeze <= FREEZE_MAX and drift <= DRIFT_MAX, f"freeze {freeze:.1f} s, drift {drift:.2f} s"


def handover_bad(samples: list[dict], settle: int = 7) -> int:
    """Samples where a view runs off the loop more than `settle` samples after a recording change."""
    bad, last, start = 0, None, 0
    for i, r in enumerate(samples):
        if r["rig"] != last:
            last, start = r["rig"], i
        if r["c"] and i - start > settle and not r["hp"] and max(abs(c["t"] - r["h"]) for c in r["c"]) > DRIFT_MAX:
            bad += 1
    return bad


def stall_back(samples: list[dict], step_s: float = 0.5, frozen_at: float = 6.0) -> dict:
    """When the aborted tile (cam2) and the frozen tile (cam1, after frozen_at) were back in sync."""
    back = {}
    for i, r in enumerate(samples):
        t = (i + 1) * step_s
        for c in r["c"]:
            if c["cam"] in ("cam1", "cam2") and not r["hp"] and abs(c["t"] - r["h"]) < DRIFT_MAX and not c["err"]:
                if c["cam"] == "cam2" or t > frozen_at + 0.5:
                    back.setdefault(c["cam"], t)
    return back


def stall_verdict(aborted: int, back: dict, frozen_at: float = 6.0) -> bool:
    cam2 = aborted == 1 and "cam2" in back and back["cam2"] <= RECOVER_MAX_S
    cam1 = "cam1" in back and back["cam1"] - frozen_at <= RECOVER_MAX_S
    return cam2 and cam1


# --- hero chip labels (hero_labels_check) ----------------------------------------------------------------------
LABEL_DEVICES = [
    ("phone-320", 320, 568), ("phone-360", 360, 740), ("phone-390", 390, 844),
    ("phone-430", 430, 932), ("tablet-834", 834, 1112),
    ("laptop-1280", 1280, 720), ("laptop-1440", 1440, 900),
    ("desktop-1920", 1920, 1080), ("desktop-2560", 2560, 1440),
]
WIDE_PX = 1100


def label_problems(width: int, measured: list[dict]) -> list[str]:
    """Per width: every selected chip in view, no scrolling when wide, no clipped readout."""
    problems = [r["name"] for r in measured if not r["pressed"] or not r["visible"]]
    clipped = sorted({c for r in measured for c in r["clipped"]})
    last = measured[-1] if measured else {"hidden": 0, "scrolls": False}
    if width >= WIDE_PX and last["scrolls"]:
        problems.append(f"chips need scrolling ({last['hidden']} px hidden)")
    if clipped:
        problems.append("clipped readout: " + ", ".join(clipped))
    return problems


# --- what the drivers print and save ---------------------------------------------------------------------------
def verdict(ok: bool) -> str:
    return "ok  " if ok else "FAIL"


def media_report(errors: list[str], lines: list[str], n_rigs: int) -> list[str]:
    return [*lines, *(f"  - {e}" for e in errors), "", f"{n_rigs} recordings, {len(errors)} problems"]


def nav_report(links: list[str], problems: list[str]) -> tuple[dict, list[str]]:
    """(nav_report.json, printed lines)."""
    return {"links": len(links), "problems": problems}, [f"{len(links)} links, {len(problems)} problems", "\n".join(problems)]


def device_line(name: str, cls: str, res: dict) -> str:
    return f"{name:22s} {cls:10s} " + "  ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in res.items() if isinstance(v, bool))


def device_failure(name: str, res: dict) -> str | None:
    bad = [k for k, v in res.items() if v is False]
    return f"{name}: {', '.join(bad)}" if bad else None


def devices_summary(n: int, failed: list[str]) -> str:
    return f"\n{n - len(failed)}/{n} devices pass" + ("" if not failed else "\nFAILED: " + " | ".join(failed))


def wanted(name: str, cls: str, only: str | None) -> bool:
    return not only or only in (cls, name)


def label_line(name: str, n: int, scrolls: bool, problems: list[str]) -> str:
    return (f"{verdict(not problems)} {name:<14} {n} recordings, {'scroller' if scrolls else 'all fit'}"
            f"{'' if not problems else '  ' + '; '.join(problems)}")


def labels_summary(n: int, bad: int) -> str:
    return f"\n{n - bad}/{n} widths name every recording and fit their readout"


def sync_line(name: str, ok: bool, msg: str) -> str:
    return f"{verdict(ok)} {name:24s} {msg}"


def sync_summary(results: list[bool]) -> str:
    return f"\n{sum(results)}/{len(results)} sync checks pass"
