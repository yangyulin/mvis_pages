"""Example pages for openmvis.com (/benchmark/examples/): one MVIS run per example, in seven steps, plus the overview cards.

The words come from data/public_examples.yaml. The run of each example is named in the private mira sensors.yaml
`examples:` section (passed by path); only its run folders and config files are read, through example_config. An example
whose run has no cam_imu_views.json yet is pending: its page is written without the player, map, result and check.
The config shown is the run's own, with paths cut to file names, so it is never retyped. lint.public_problems checks
every text drawn from the data (page JSON with links stripped, the MDX, the views' strings, the sidebar) and one
problem stops the whole export; nothing is written.

collect() reads runs, render() is pure and returns a Plan, write() (export_sensors.write) is the only step that writes.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import re
from pathlib import Path

import numpy as np
import yaml

from . import DATA
from .export_sensors import Plan, write
from .geometry import rot_angle_between
from .lint import process_strings, public_problems, strip_urls
from .markup import MAP_STAGE, e, num, reproj, vec
from .results import expand_root, load_variant, refuse_frames
from .sensor_header import process_block
from .sensor_parts import MAP_LEAD, PLOTLY_LOCAL, map_panel, rig_json

EX_DATA = "site/src/data/examples"
EX_MEDIA = "site/public/media/examples"
EX_DOCS = "site/src/content/docs/benchmark/examples"
NAV = "site/src/data/examples-nav.json"
BASE = "/benchmark/examples/"
EVAL = "/benchmark/results/"
CLIPS = "/media/hero"
PENDING = "This example's run is being solved on current MVIS. This step fills in when the solve lands."


def strip_links(text: str) -> str:
    """Links leave the lint: outside links (strip_urls) and the site's own routes, such as /benchmark/results/, which
    the internal-path rule would flag. Only an href, a Markdown link target or a nav "link" counts as a route."""
    return re.sub(r'(href="|\]\(|"link": ")/[^"\s)]*', r"\1", strip_urls(text))


def public_examples() -> dict:
    return yaml.safe_load((DATA / "public_examples.yaml").read_text(encoding="utf-8"))


def example_config(cfg: dict) -> dict:
    """The slice of the private sensors.yaml this export may read: roots, and per example its run folder and config
    file, and the same for a second device (other)."""
    keep = lambda x: {k: x[k] for k in ("run", "config") if k in x}
    out = {}
    for slug, x in (cfg.get("examples") or {}).items():
        out[slug] = keep(x)
        if x.get("other"):
            out[slug]["other"] = keep(x["other"])
    return {"roots": dict(cfg["roots"]), "examples": out}


def own_config(run_dir: Path) -> Path | None:
    """The run's config when the private map names none: the one YAML in the run folder with input and output."""
    hits = [p for p in sorted(run_dir.glob("*.yaml")) if {"input", "output"} <= set(yaml.safe_load(p.read_text()) or {})]
    return hits[0] if len(hits) == 1 else None


def load_run(entry: dict | None, roots: dict) -> dict | None:
    """One example run with its views, config and date, or None while it is pending (no folder or no views yet)."""
    if not entry:
        return None
    d = expand_root(entry["run"], roots)
    if not (d / "cam_imu_views.json").exists():
        return None
    v = load_variant({"label": "Run", "run": entry["run"], "report": True}, roots)
    cfg = expand_root(entry["config"], roots) if entry.get("config") else own_config(d)
    if cfg is None:
        raise SystemExit(f"{entry['run']}: no config; name it as config: in the private examples map")
    v["config"] = yaml.safe_load(cfg.read_text())
    v["date"] = dt.date.fromtimestamp((d / "cam_imu.json").stat().st_mtime).isoformat()
    return v


def collect(pub: dict, cfg: dict) -> dict:
    """Per public example: its run and its second device's run, each None while pending. Frames stop the export."""
    out = {}
    for slug in pub["examples"]:
        x = cfg["examples"].get(slug, {})
        runs = {"main": load_run(x, cfg["roots"]), "other": load_run(x.get("other"), cfg["roots"])}
        refuse_frames(slug, [v for v in runs.values() if v])
        out[slug] = runs
    return out


# --- the config, as run ------------------------------------------------------------------------------------------

CONFIG_KEYS = ("mode", "input", "board", "camera_input", "solve", "estimate", "output")


def _short(path: str) -> str:
    parts = Path(str(path)).parts
    return "/".join(parts[-2:]) if parts[-1] == "mav0" else parts[-1]


def public_config(cfg: dict) -> str:
    """The run's config as MVIS reads it: only its MVIS sections (CONFIG_KEYS), every path cut to its file name (a mav0
    folder keeps its parent), no cache folder, and the output written beside the config."""
    c = {k: copy.deepcopy(v) for k, v in cfg.items() if k in CONFIG_KEYS}  # a reference: block names private files
    inp = c.get("input", {})
    inp.pop("cache_dir", None)
    if "path" in inp:
        inp["path"] = _short(inp["path"])
    if "path" in c.get("camera_input", {}):
        c["camera_input"]["path"] = _short(c["camera_input"]["path"])
    if "output" in c:
        c["output"] = {"path": "cam_imu.json"}
    return yaml.safe_dump(c, sort_keys=False, allow_unicode=True, default_flow_style=False, width=110)


def key_lines(text: str) -> dict[str, list[int]]:
    """Each mapping key's dotted path (input.imu_topics) to its 1-based lines: the key's own and its nested block."""
    lines = text.splitlines()
    out, stack = {}, []
    for i, line in enumerate(lines):
        m = re.match(r"( *)([A-Za-z_]\w*):", line)
        if not m:
            continue
        ind = len(m.group(1))
        stack = [(n, k) for n, k in stack if n < ind] + [(ind, m.group(2))]
        j = i + 1
        while j < len(lines) and ((len(lines[j]) - len(lines[j].lstrip())) > ind or lines[j].startswith(" " * ind + "- ")):
            j += 1
        out[".".join(k for _, k in stack)] = list(range(i + 1, j + 1))
    return out


def marks(lines: list[int]) -> str:
    """Expressive Code line marks, {3,5-7}."""
    if not lines:
        return ""
    runs, start = [], lines[0]
    for a, b in zip(lines, lines[1:] + [None]):
        if b != a + 1:
            runs.append(f"{start}" if start == a else f"{start}-{a}")
            start = b
    return "{" + ",".join(runs) + "}"


def config_block(c: dict, v: dict | None) -> tuple[str, str, list[str]]:
    """The config fence, the notes under it, and problems (a note on a key the config lacks)."""
    if not v:
        return "", f"<p class=note>{PENDING}</p>", []
    text = public_config(v["config"])
    where = key_lines(text)
    missing = [k for k in c["why"] if k not in where]
    hl = sorted({n for k in c["why"] if k in where for n in where[k]})
    fence = f'```yaml title="{c["name"]}" {marks(hl)}\n{text}```\n\n'
    notes = "".join(f"<li><code>{e(k)}</code>: {e(t)}</li>" for k, t in c["why"].items())
    notes = (f"<p>The marked lines are the choices that matter for this rig:</p><ul class=list>{notes}</ul>" if notes else "") + \
        "<p class=note>This is the config of the run on this page, with every path cut to its file name. Point the paths at your copy.</p>"
    return fence, notes, [f"config note on {k}, which the config lacks" for k in missing]


# --- page parts --------------------------------------------------------------------------------------------------

def window_s(v: dict) -> float:
    return float(v["views"]["t"][-1])


def link(x: dict) -> str:
    return f'<a href="{e(x["url"])}">{e(x["label"])} →</a>'


def eval_link(p: dict, have: set[str]) -> dict | None:
    """The example's Dataset eval page, or the Results overview until that page exists in the site."""
    ev = p.get("eval")
    if not ev:
        return None
    if ev["slug"] in have:
        return {"url": f"{EVAL}{ev['slug']}/", "label": f"{ev['label']}: Dataset eval"}
    return {"url": EVAL, "label": f"{ev['label']}: Results"}


def header(slug: str, p: dict, ev: dict | None) -> str:
    img = p["image"]
    cap = f'<a href="{e(img["url"])}">{e(img["credit"])} ↗</a>' if img.get("url") else e(img["credit"])
    links = [x for x in (ev, p.get("sensor"), {"url": p["dataset"]["url"], "label": f'Downloads: {p["dataset"]["label"]}'}) if x]
    return (f'<div class=ex-head><figure class=ex-photo><img src="/media/examples/{slug}/{e(img["file"])}" alt="{e(img["alt"])}" width="800" height="533">'
            f'<figcaption>{cap}</figcaption></figure><div><div class=chips>' + "".join(f"<span class=chip>{e(c)}</span>" for c in p["chips"])
            + f'</div><p class=lead><b>What you\'ll see:</b> {e(p["lead"])}</p><p class=ex-links>' + " ".join(link(x) for x in links) + "</p></div></div>")


def data_part(p: dict, v: dict | None) -> str:
    items = list(p["data"])
    if v:
        items.append(f"Solve window: {num(window_s(v), 1)} s.")
    return ("<ul class=list>" + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul>"
            + f'<p>Download: {link(p["dataset"])} The recordings are listed there, not copied here.</p>')


def run_part(v: dict | None) -> str:
    if not v:
        return f"<p class=note>{PENDING}</p>"
    return f'<p>The solve took about {max(1, round(v["run"]["solve_s"] / 60))} min on one desktop. It writes <code>cam_imu.json</code>, a calibration YAML and a report beside the config.</p>'


def process_part(slug: str, v: dict | None) -> str:
    if not v:
        return f"<div class=\"demo empty\"><b>Player waiting for the solve.</b> {PENDING}</div>"
    return ("<p>MVIS's own player, from this run: the detected board corners, then the rig's path as the solve refines it. "
            "Press <b>Play</b> or drag the bar; pick a camera card to look through that camera. We publish no camera images.</p>"
            + process_block(slug, v, 0, f"/media/examples/{slug}"))


def _intr(c: dict) -> str:
    return ", ".join(num(x, 1) for x in c["intr"][:4])


def result_table(v: dict) -> str:
    r = v["run"]
    rs = any(abs(x) > 0.01 for x in v["readout_ms"])
    head = "<th>Sensor</th><th>fx, fy, cx, cy px</th><th>Lever mm</th><th>log(R) rad</th><th>td ms</th>" + ("<th>Readout ms</th>" if rs else "") + "<th>t_ga ms</th><th>Reprojection px</th>"
    rows = []
    for i, c in enumerate(r["cams"]):
        ro = f'<td>{num(v["readout_ms"][i], 2) if abs(v["readout_ms"][i]) > 0.01 else "global"}</td>' if rs else ""
        rows.append(f'<tr><th>{e(c["name"])}</th><td>{_intr(c)}</td><td>{vec(c["p_CinI_mm"], 1)}</td><td>{vec(c["rotvec"], 4)}</td><td>{num(c["td_ms"], 2, True)}</td>{ro}<td></td>'
                    f'<td>{num(c.get("reproj_median", c["reproj"]), 3)}</td></tr>')
    blank = "<td></td>" if rs else ""
    rows.append(f'<tr><th>IMU (base)</th><td></td><td>0</td><td>0</td><td>0</td>{blank}<td>{num(r.get("t_ga_ms"), 2, True)} ± {num(r.get("t_ga_sigma_ms"), 2)}</td><td></td></tr>')
    for m in r.get("imus", []):
        rows.append(f'<tr><th>IMU {e(m["name"])}</th><td></td><td>{vec(m["p_IsinI_mm"], 1)}</td><td>{vec(m["rotvec"], 4)}</td><td>{num(m["td_ms"], 2, True)}</td>{blank}'
                    f'<td>{num(m.get("t_ga_ms"), 2, True)} ± {num(m.get("t_ga_sigma_ms"), 2)}</td><td></td></tr>')
    kind, val = reproj(r)
    return (f'<div class=scroll><table class=num><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            f'<p class=note>Lever arms and rotations are each sensor in the base IMU frame; rotation is log(R) in rad. td is the time offset to the base IMU, '
            f't_imu = t_sensor + td. Reprojection is the median per camera (all cameras: {kind} {num(val, 3)} px): how well the model fits the corners, not how accurate it is.</p>')


def result_part(v: dict | None) -> str:
    if not v:
        return f"<div class=\"demo empty\"><b>Result waiting for the solve.</b> {PENDING}</div>"
    return f"<p>{MAP_LEAD}</p>{MAP_STAGE}{map_panel()}{result_table(v)}"


def check_table(ref: dict, v: dict) -> str:
    cams = {c["name"]: c for c in v["run"]["cams"]}
    rows = []
    for f in ref["cams"]:
        c = cams[f["name"]]
        dp = float(np.linalg.norm(np.subtract(c["p_CinI_mm"], f["p_mm"])))
        dth = 1000 * rot_angle_between(c["rotvec"], f["rotvec"])
        td = f.get("td_ms")
        rows += [f'<tr class=grp><th colspan=4>{e(f["name"])}</th></tr>',
                 f'<tr><td>Lever mm</td><td>{vec(c["p_CinI_mm"], 2)}</td><td>{vec(f["p_mm"], 2)}</td><td>Δp {num(dp, 2)} mm</td></tr>',
                 f'<tr><td>log(R) rad</td><td>{vec(c["rotvec"], 4)}</td><td>{vec(f["rotvec"], 4)}</td><td>Δθ {num(dth, 2)} mrad</td></tr>',
                 f'<tr><td>fx px</td><td>{num(c["intr"][0], 2)}</td><td>' + (f'{num(f["fx"], 2)}</td><td>Δfx {num(c["intr"][0] - f["fx"], 2, True)} px</td></tr>' if f.get("fx") is not None else f'{e(ref.get("fx_text", "not given"))}</td><td></td></tr>'),
                 f'<tr><td>td ms</td><td>{num(c["td_ms"], 3, True)}</td><td>' + (f'{num(td, 3, True)}</td><td>Δtd {num(c["td_ms"] - td, 3, True)} ms</td></tr>' if td is not None else f'{e(ref.get("td_text", "not given"))}</td><td></td></tr>')]
    return (f'<div class=scroll><table class=num><thead><tr><th>Value</th><th>MVIS</th><th>{e(ref["label"])}</th><th>Difference</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            "<p class=note>Δp is the distance between the two lever arms. Δθ = ‖log(R<sub>a</sub><sup>T</sup> R<sub>b</sub>)‖, the angle between the two rotations. "
            "A reference, not ground truth: it was solved by another tool on the same kind of data.</p>"
            + "".join(f"<p class=note>{e(n)}</p>" for n in ref.get("notes", [])))


def check_part(ref: dict, v: dict | None, ev: dict | None) -> str:
    if "none" in ref:
        more = f" {link(ev)}" if ev else ""
        return f"<div class=ex-callout><p><b>No published reference.</b> {e(ref['none'])}{more}</p></div>"
    src = f'<p>Reference: <a href="{e(ref["url"])}">{e(ref["source"])}</a>.</p>'
    if not v:
        return src + f"<p class=note>The comparison table appears with the solve. {PENDING}</p>"
    return src + check_table(ref, v)


def reproduce_part(p: dict, v: dict | None, name: str) -> str:
    if not v:
        return f"<p class=note>{PENDING}</p>"
    batch = (p.get("reproduce") or {}).get("batch", "MVIS main")
    rows = [("MVIS", batch), ("Run date", v["date"]), ("Data", link(p["dataset"])), ("Config", f"<code>{e(name)}</code>, step 2"),
            ("Command", f"<code>mvis cam-imu -c {e(name)}</code>")]
    return "<dl class=ex-kv>" + "".join(f"<dt>{a}</dt><dd>{b if b.startswith('<') else e(b)}</dd>" for a, b in rows) + "</dl>"


def more_part(p: dict) -> str:
    return "".join(f'<details class=fold><summary>{e(f["title"])} <span>{e(f["key"])}</span></summary><div><p>{e(f["text"])} {link(f["link"])}</p></div></details>'
                   for f in p.get("folds", []))


def other_part(o: dict, v: dict | None) -> str:
    """A second device: its lead, result table and check, no map (one map per page)."""
    body = result_table(v) + check_part(o["reference"], v, None) if v else f"<div class=\"demo empty\"><b>Waiting for the solve.</b> {PENDING}</div>"
    return f"<p>{e(o['lead'])}</p>{body}"


def next_part(slug: str, pub: dict, ev: dict | None, p: dict) -> str:
    others = [f'<a href="{BASE}{s}/">{e(x["nav"])}</a>' for s, x in pub["examples"].items() if s != slug]
    nxt = [link(x) for x in (ev, p.get("sensor")) if x]
    return f'<p class=ex-links>{" ".join(nxt)}</p><p class=note>Other examples: {" · ".join(others)}</p>'


# --- card, MDX, sidebar ------------------------------------------------------------------------------------------

def card(slug: str, p: dict, v: dict | None) -> dict:
    """Overview card. Stats come from the run, so they're empty while the example waits for its solve."""
    c = p["card"]
    img = p["image"]
    stats = []
    if v:
        r = v["run"]
        stats = [[f'{len(r["cams"])} cam · {1 + len(r.get("imus", []))} IMU', "sensors"], [f"{num(window_s(v), 1)} s", "window"],
                 [f"{num(reproj(r)[1], 2)} px", f"reproj {reproj(r)[0]}"], [f'{num(r["cams"][0]["td_ms"], 2, True)} ms', "cam0 td"]]
    return {"title": p["title"], "href": f"{BASE}{slug}/", "image": f"/media/examples/{slug}/{img['file']}", "alt": img["alt"], "credit": img["credit"],
            "maker": p["maker"], "rig": c["rig"], "format": c["format"], "shows": c["shows"], "tags": c["tags"], "featured": bool(p.get("featured")),
            "ours": bool(p.get("ours")), "clip": f"{CLIPS}/hero_{p['clip']}_960.mp4", "poster": f"{CLIPS}/hero_{p['clip']}_960.jpg", "stats": stats}


def card_problems(slug: str, tags: list[str], v: dict | None) -> list[str]:
    """Camera and IMU counts on a card's tags must match its run."""
    if not v:
        return []
    have = {"cameras": len(v["run"]["cams"]), "IMUs": 1 + len(v["run"].get("imus", []))}
    out = []
    for t in tags:
        m = re.fullmatch(r"(\d+) (cameras|IMUs)", t)
        if m and int(m.group(1)) != have[m.group(2)]:
            out.append(f"{slug}: card says {t}, the run has {have[m.group(2)]}")
    return out


def example_mdx(slug: str, p: dict, steps: list[dict], fences: dict, other: dict | None) -> str:
    q = lambda t: json.dumps(t, ensure_ascii=False)
    part = lambda k: f'<ExamplePart example="{slug}" part="{k}" />\n\n'
    keys = ["data", "config", "run", "process", "result", "check", "reproduce"]
    body = ""
    for n, (s, k) in enumerate(zip(steps, keys), 1):
        body += f"## {n}. {s['name']}\n\n" + (fences.get(k, "")) + part(k)
    if other:
        body += f"## {other['title']}\n\n" + fences.get("other", "") + part("other")
    if p.get("folds"):
        body += "## More on this data\n\n" + part("more")
    body += "## Next\n\n" + part("next")
    return (f"---\ntitle: {q(p['title'])}\ndescription: {q(p['description'])}\npageType: example\nwide: true\n---\n\n"
            "{/* Generated by export_examples.py. Edit python/data/public_examples.yaml, not this file. */}\n"
            "import ExamplePart from '../../../../components/ExamplePart.astro';\n\n" + part("header") + body)


def overview_mdx(pub: dict) -> str:
    steps = "".join(f"{n}. **{s['name']}:** {s['text']}\n" for n, s in enumerate(pub["steps"], 1))
    return ("---\ntitle: Examples\ndescription: Complete MVIS calibration runs on released datasets. Pick the one whose rig looks most like yours.\npageType: reference\nwide: true\n---\n\n"
            "{/* Generated by export_examples.py. Edit python/data/public_examples.yaml, not this file. */}\n"
            "import ExampleGrid from '../../../../components/ExampleGrid.astro';\n\n"
            "Each example is a complete calibration run on a released dataset. It shows:\n\n"
            "- the **configuration** we used\n- the **result** it produced\n- how far the result is from a **reference calibration**, where one exists\n\n"
            "Pick the one whose rig looks most like yours.\n\n"
            f"<ExampleGrid slugs={{{json.dumps(list(pub['examples']))}}} />\n\n"
            "Looking for a specific sensor? See the [Sensor wiki](/sensors/). All tools on all recordings? See [Results](/benchmark/results/).\n\n"
            "## How to read these pages\n\nEvery example has the same seven steps, in this order:\n\n" + steps +
            "\nDownloads are on each dataset's own page, and comparisons across tools are on the Results pages.\n\n"
            ":::note[Figures come from the run]\nThe player, the map and the tables on each page are generated from the run they document. "
            "If a figure and the text disagree, the figure is right.\n:::\n\n"
            "## Contributing an example\n\nThe most useful thing you can send is a run on a dataset we don't have.\n\n"
            "- For the format, see [Submit a dataset](/contribute/submit-dataset/).\n"
            "- To add it to the [results](/benchmark/results/) as well, see [Submit results](/contribute/submit-results/).\n")


def examples_nav(pub: dict) -> list[dict]:
    return [{"label": "Overview", "link": BASE}] + [{"label": p["nav"], "link": f"{BASE}{s}/"} for s, p in pub["examples"].items()]


def render(pub: dict, collected: dict, photos: Path, have_eval: set[str]) -> Plan:
    """The whole export as data. have_eval: the Dataset eval slugs that exist in the site, linked once they do."""
    plan = Plan()
    for slug, p in pub["examples"].items():
        v, ov = collected[slug]["main"], collected[slug]["other"]
        ev = eval_link(p, have_eval)
        fence, notes, probs = config_block(p["config"], v)
        fences, plan.problems = {"config": fence}, plan.problems + [f"{slug}: {x}" for x in probs]
        parts = {"header": header(slug, p, ev), "data": data_part(p, v), "config": notes, "run": run_part(v), "process": process_part(slug, v),
                 "result": result_part(v), "check": check_part(p["reference"], v, ev), "reproduce": reproduce_part(p, v, p["config"]["name"]),
                 "more": more_part(p), "next": next_part(slug, pub, ev, p)}
        if v:
            fences["run"] = f'```bash title="shell"\nmvis cam-imu -c {p["config"]["name"]}\n```\n\n'
        o = p.get("other")
        if o:
            ofence, onotes, oprobs = config_block(o["config"], ov)
            fences["other"] = ofence
            parts["other"] = other_part(o, ov) + onotes
            plan.problems += [f"{slug} other: {x}" for x in oprobs]
        plan.problems += card_problems(slug, p["card"]["tags"], v)
        page = {"title": p["title"], "parts": parts, "rigs": [rig_json(v)] if v else [], "procs": [None] if v else [], "plotly": PLOTLY_LOCAL,
                "card": card(slug, p, v), "pending": (["main"] if not v else []) + (["other"] if o and not ov else [])}
        txt = json.dumps(page, ensure_ascii=False)
        m = example_mdx(slug, p, pub["steps"], fences, o)
        plan.problems += [f"{slug}: {x}" for x in public_problems(strip_links("\n".join(parts.values()) + json.dumps(page["card"], ensure_ascii=False))) + public_problems(strip_links(m))]
        out = f"{EX_MEDIA}/{slug}"
        plan.clear.append(out)
        if v:
            views = json.dumps(v["views"], separators=(",", ":"))
            plan.problems += [f"{slug} views: {x}" for x in public_problems(process_strings(views))]
            plan.texts[f"{out}/views0.json"] = views
        plan.copies.append((photos / p["image"]["file"], f"{out}/{p['image']['file']}"))
        plan.texts[f"{EX_DATA}/{slug}.json"] = txt.replace("↗", "↗︎")
        plan.texts[f"{EX_DOCS}/{slug}.mdx"] = m
        plan.slugs.append(slug)
    nav = json.dumps(examples_nav(pub), indent=1, ensure_ascii=False) + "\n"
    ov_mdx = overview_mdx(pub)
    plan.problems += [f"sidebar: {x}" for x in public_problems(strip_links(nav))] + [f"overview: {x}" for x in public_problems(strip_links(ov_mdx))]
    plan.texts[NAV] = nav
    plan.texts[f"{EX_DOCS}/index.mdx"] = ov_mdx
    return plan


def eval_pages(site: Path) -> set[str]:
    d = Path(site) / "site/src/content/docs/benchmark/results"
    return {f.stem for f in d.glob("*.mdx") if f.stem != "index"} if d.is_dir() else set()


def main(site: Path, private_config: Path) -> list[str]:
    """Export every example, its media and MDX, the overview and the sidebar entries; nothing if the lint fails."""
    pub = public_examples()
    cfg = example_config(yaml.safe_load(Path(private_config).read_text(encoding="utf-8")))
    plan = render(pub, collect(pub, cfg), DATA / "photos", eval_pages(site))
    return write(Path(site), plan)


def pending(site: Path) -> dict[str, list[str]]:
    """Which written examples still wait for a solve: slug to [main] / [other]."""
    out = {}
    for f in sorted((Path(site) / EX_DATA).glob("*.json")):
        p = json.loads(f.read_text(encoding="utf-8")).get("pending")
        if p:
            out[f.stem] = p
    return out
