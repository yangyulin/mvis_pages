"""Sensor pages for openmvis.com: data, media and thin MDX wrappers, written into a site checkout.

Only sensors in data/public_sensors.yaml are exported. Numbers come from the private sensors.yaml (passed by path),
read through results.solve_config, so reference columns never get here. Camera frames are refused. lint.public_problems
checks every text drawn from the data before anything is written: each sensor's JSON (links stripped, as a maker's URL
may hold /home/), its MDX, its process figures' strings and the sidebar entries. The overview's prose is fixed in
site_files (it says the pages have no scores, which the lint would flag), and sensor.css / sensor-page.js are the lib's
own assets, so those three are not linted.

collect() reads results, render() is pure and returns a Plan, write() is the only step that touches the site.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import DATA, assets
from .lint import process_strings, public_problems, strip_urls
from .results import expand_root, load_all_series, load_variant, refuse_frames, solve_config
from .sensor_header import header_parts
from .sensor_parts import demo_keys, parts_for
from .site_files import mdx, overview_mdx, sensor_json, sensor_nav, site_css, site_js

MEDIA = "site/public/media/sensors"
DATA_DIR = "site/src/data/sensors"
DOCS = "site/src/content/docs/benchmark/sensors"
MAKE_DIRS = (DATA_DIR, DOCS, "site/src/scripts")


@dataclass
class Plan:
    """Everything one export writes. texts and copies are keyed by path relative to the site checkout."""
    texts: dict[str, str] = field(default_factory=dict)
    copies: list[tuple[Path, str]] = field(default_factory=list)
    clear: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    slugs: list[str] = field(default_factory=list)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def public_sensors() -> dict:
    return yaml.safe_load((DATA / "public_sensors.yaml").read_text(encoding="utf-8"))


def collect(pub: dict, solve_cfg: dict) -> dict:
    """Per public sensor: its loaded runs (public labels), repeatability sets, board and recording sha256."""
    roots = solve_cfg["roots"]
    out = {}
    for slug, p in pub["sensors"].items():
        s = solve_cfg["sensors"][p.get("key", slug)]
        vs = [load_variant({k: x for k, x in vc.items() if k != "ref"}, roots) for vc in s["variants"]]
        for i, v in enumerate(vs):  # takes are labelled by device id in the private data
            v["label"] = p["run_labels"][i] if p.get("run_labels") else ("Recording 1" if v["label"].startswith("Take ") else v["label"])
        refuse_frames(slug, vs)
        sha = sha256(expand_root(s["sha256_of"], roots)) if s.get("sha256_of") else None
        out[slug] = {"variants": vs, "series": load_all_series(s.get("series"), roots), "board": s["board"], "sha": sha,
                     "media": s.get("demo_media", {})}
    return out


def render(pub: dict, collected: dict, media: Path, photos: Path) -> Plan:
    """The whole export as data. Works on a copy of pub; reads only the lib's own asset files."""
    pub = copy.deepcopy(pub)
    tags = assets.apriltag()
    plan = Plan()
    for slug, p in pub["sensors"].items():
        c = collected[slug]
        vs = c["variants"]
        if c["sha"]:
            p["sha"] = c["sha"]
        procs = [json.dumps(v["process"], separators=(",", ":")) for v in vs]
        plan.problems += [f"{slug} process: {x}" for t in procs for x in public_problems(process_strings(t))]
        if not p.get("header", {}).get("image", {}).get("file"):
            raise ValueError(f"{slug}: needs a header with an image file; the Sensors overview card shows it")
        parts = parts_for(slug, p, {"board": c["board"]}, vs, c["series"], pub["data_url"], f"/media/sensors/{slug}", tags)
        header_parts(slug, p, vs, parts)
        txt = json.dumps(sensor_json(slug, p, parts, vs), ensure_ascii=False)
        m = mdx(slug, p)
        plan.problems += [f"{slug}: {x}" for x in public_problems(strip_urls(txt)) + public_problems(m)]
        out = f"{MEDIA}/{slug}"
        plan.clear.append(out)
        for i, t in enumerate(procs):
            plan.texts[f"{out}/process{i}.json"] = t
        plan.copies.append((photos / p["header"]["image"]["file"], f'{out}/{p["header"]["image"]["file"]}'))
        if p.get("image"):
            plan.copies.append((photos / p["image"]["file"], f'{out}/{p["image"]["file"]}'))
        clip = lambda name, ext: media / f'{c.get("media", {}).get(name, name)}.{ext}'
        if "from" in p.get("demo", {}):
            plan.copies += [(clip(p["demo"]["from"], "mp4"), f"{out}/demo.mp4"), (clip(p["demo"]["from"], "jpg"), f"{out}/demo.jpg")]
        if "by_variant" in p.get("demo", {}):
            for k, x in zip(demo_keys(p["demo"]), p["demo"]["by_variant"]):
                plan.copies += [(clip(x["from"], "mp4"), f"{out}/demo{k}.mp4"), (clip(x["from"], "jpg"), f"{out}/demo{k}.jpg")]
        plan.texts[f"{DATA_DIR}/{slug}.json"] = txt.replace("↗", "↗︎")  # text-style arrow; after the lint, which never sees it
        plan.texts[f"{DOCS}/{slug}.mdx"] = m
        plan.slugs.append(slug)
    nav = json.dumps(sensor_nav(pub), indent=1) + "\n"
    plan.problems += [f"sidebar: {x}" for x in public_problems(nav)]
    plan.texts["site/src/data/sensor-nav.json"] = nav
    plan.texts[f"{DOCS}/index.mdx"] = overview_mdx(pub)
    plan.texts[f"{DATA_DIR}/sensor.css"] = site_css(assets.page_css(), assets.header_css())
    plan.texts["site/src/scripts/sensor-page.js"] = site_js(assets.progress_js(), assets.page_js())
    return plan


def _inside(site: Path, rel: str) -> Path:
    target = (site / rel).resolve()
    if not target.is_relative_to(site.resolve()):
        raise ValueError(f"refusing to write outside the site checkout: {rel}")
    return target


def write(site: Path, plan: Plan) -> list[str]:
    """Write a Plan into a site checkout; nothing at all when the lint found a problem."""
    if plan.problems:
        raise SystemExit("Public lint failed, nothing written:\n" + "\n".join(plan.problems))
    for d in MAKE_DIRS:
        _inside(site, d).mkdir(parents=True, exist_ok=True)
    for d in plan.clear:  # only exported sensors' media: other files there (the plotly bundle) stay
        out = _inside(site, d)
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
    for rel, text in plan.texts.items():
        out = _inside(site, rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    for src, rel in plan.copies:
        shutil.copyfile(src, _inside(site, rel))
    return plan.slugs


def main(site: Path, private_config: Path, media: Path) -> list[str]:
    pub = public_sensors()
    cfg = solve_config(yaml.safe_load(Path(private_config).read_text(encoding="utf-8")))
    plan = render(pub, collect(pub, cfg), Path(media), DATA / "photos")
    return write(Path(site), plan)
