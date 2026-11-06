"""ffprobe readers for checks.check_hero_media."""
from __future__ import annotations

import json
import os
import shutil
import subprocess

from .. import SITE, checks


def _ffprobe(*args) -> str:
    exe = shutil.which("ffprobe") or "ffprobe"
    return subprocess.run([exe, "-v", "error", "-select_streams", "v:0", *args], capture_output=True, text=True, check=True).stdout


def stream(path) -> str:
    return _ffprobe("-show_entries", "stream=width,height,nb_frames,r_frame_rate", "-of", "csv=p=0", path)


def keyframes(path) -> str:
    return _ffprobe("-skip_frame", "nokey", "-show_entries", "frame=pts_time", "-of", "csv=p=0", path)


DEFAULT = SITE / "public/media/hero"


def run(media=DEFAULT, probe_stream=None, probe_keyframes=None, out=print) -> int:
    """Check the hero media folder; the readers default to ffprobe."""
    with open(os.path.join(media, "rigs.json")) as f:
        rigs = json.load(f)["rigs"]
    errors, lines = checks.check_hero_media(str(media), rigs, probe_stream or stream, probe_keyframes or keyframes)
    out("\n".join(checks.media_report(errors, lines, len(rigs))))
    return 1 if errors else 0
