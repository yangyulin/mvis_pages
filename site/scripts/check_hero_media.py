"""Validate the homepage hero media against what HomeHero.astro loads.

  python site/scripts/check_hero_media.py [site/public/media/hero]

rigs.json (written by openmvis-internal demo_video/build_site_media.py) must list, for every recording,
files the page will request, and those files must be playable in sync:
  files      hero_<k>.mp4/.jpg, hero_<k>_960.mp4/.jpg, <k>_<cam>.mp4/.jpg, <k>_<cam>_240.mp4/.jpg
  fields     chip, caption, duration, live_cycle, sensors, window, rms, td, xlabel, xval, corners, tiles
  timeline   hero, phone loop and every tile of a rig have the same frame count (they share one clock)
  sizes      hero 1920x1080, phone loop 960x540, tiles 400 px wide, small tiles 240 px wide
  keyframes  at most 1 s apart in every mp4 (sparse keyframes froze companion seeks on phones)
  budget     phone first load (hero_960.mp4 + poster) <= 2.5 MB per recording
Exit code 1 on any violation.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

REQUIRED = ["key", "chip", "caption", "duration", "live_cycle", "sensors", "window", "rms", "td", "xlabel", "xval", "corners", "tiles"]


def probe(path):
    out = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,nb_frames,r_frame_rate",
                          "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout.strip().split(",")
    num, den = out[2].split("/")
    return int(out[0]), int(out[1]), float(num) / float(den), int(out[3])


def max_keyframe_gap(path, fps, nframes):
    out = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey", "-show_entries", "frame=pts_time",
                          "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout
    ts = sorted(float(x.strip(",")) for x in out.split() if x.strip(","))
    return max([b - a for a, b in zip(ts, ts[1:])] + [nframes / fps - ts[-1]])


def main():
    media = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "public", "media", "hero")
    errors = []
    rigs = json.load(open(os.path.join(media, "rigs.json")))["rigs"]
    if not rigs:
        errors.append("rigs.json lists no recordings")
    for r in rigs:
        k = r.get("key", "?")
        missing = [f for f in REQUIRED if f not in r]
        if missing:
            errors.append(f"{k}: rigs.json missing {missing}")
            continue
        files = {"hero": f"hero_{k}.mp4", "phone": f"hero_{k}_960.mp4"}
        for cam in r["tiles"]:
            files[f"tile {cam[0]}"] = f"{k}_{cam[0]}.mp4"
            files[f"small {cam[0]}"] = f"{k}_{cam[0]}_240.mp4"
        frames = {}
        for role, f in files.items():
            path = os.path.join(media, f)
            for need in (path, path[:-4] + ".jpg"):
                if not os.path.exists(need):
                    errors.append(f"{k}: missing {os.path.basename(need)}")
            if not os.path.exists(path):
                continue
            w, h, fps, n = probe(path)
            frames[role] = n
            want_w = {"hero": 1920, "phone": 960}.get(role.split()[0], 400 if role.startswith("tile") else 240)
            if w != want_w or (role in ("hero", "phone") and h != want_w * 9 // 16):
                errors.append(f"{k}: {f} is {w}x{h}, expected width {want_w}")
            gap = max_keyframe_gap(path, fps, n)
            if gap > 1.05:
                errors.append(f"{k}: {f} keyframes up to {gap:.2f} s apart (max 1 s)")
        if len(set(frames.values())) > 1:
            errors.append(f"{k}: frame counts differ across hero/phone/tiles {frames}")
        if abs(frames.get("hero", 0) / 30 - r["duration"]) > 0.05:
            errors.append(f"{k}: rigs.json duration {r['duration']} s != hero {frames.get('hero', 0) / 30:.2f} s")
        phone_mb = sum(os.path.getsize(os.path.join(media, f)) for f in (f"hero_{k}_960.mp4", f"hero_{k}_960.jpg") if os.path.exists(os.path.join(media, f))) / 1e6
        if phone_mb > 2.5:
            errors.append(f"{k}: phone first load {phone_mb:.2f} MB > 2.5 MB")
        print(f"{'ok  ' if not any(e.startswith(k + ':') for e in errors) else 'FAIL'} {k:7s} {len(r['tiles'])} cams, {frames.get('hero', 0)} frames, phone {phone_mb:.2f} MB")
    for e in errors:
        print("  -", e)
    print(f"\n{len(rigs)} recordings, {len(errors)} problems")
    sys.exit(1 if errors else 0)


FFPROBE = shutil.which("ffprobe") or "ffprobe"
if __name__ == "__main__":
    main()
