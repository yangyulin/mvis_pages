"""The results tables on openmvis.com, from the leaderboard Space's own renderer. Pure: text in, text out.

board.json / board.css feed DatasetLeaderboard.astro; uzh_fpv.json feeds UzhFpvResults.astro. space.py runs the
Space code; everything here only shapes what it returns.
"""
from __future__ import annotations

import html
import json
import re

# Where the site reads the tables, relative to the checkout.
BOARD_DIR = "site/src/data/leaderboard"
UZH_FILE = f"{BOARD_DIR}/uzh_fpv.json"

# The site's theme in place of Gradio's. Starlight sets data-theme on <html>.
THEME = """.cb{--body-text-color:var(--sl-color-white);--border-color-primary:var(--sl-color-gray-5);
--background-fill-primary:var(--sl-color-bg);--link-text-color:var(--sl-color-text-accent);
--primary-700:#b8360f;--primary-400:#fb923c}
"""


def site_css(css):
    """Drop the tab rules, which target Gradio's own elements."""
    css = re.sub(r"[^{}]*(?:#lb-tabs|main\.app)[^{}]*\{[^{}]*\}\s*", "", css)
    return THEME + css.replace(".dark .cb", ":root[data-theme='dark'] .cb")


def strip_title(tab_html):
    """A dataset's tables, without its title: the page has its own heading."""
    return re.sub(r"<h2>.*?</h2>", "", tab_html, count=1)


def board_json(batch, results_commit, how_to_read, datasets):
    """board.json; datasets maps dataset id to its fragment, in board order."""
    return {"batch": batch, "results_commit": results_commit, "how_to_read": how_to_read, "datasets": datasets}


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


# UZH-FPV: the same table the leaderboard shows, on this study's stats, leaving the leaderboard batch alone.
BATCH = "2026-11-04"
UZH_STATS = "three_way/three_way_comparison_stats.json"  # in the study folder, beside hub_stage/<BATCH>/

FAMILIES = {"DAVIS": "UD", "SNAP": "US"}

PREFIX = {"DAVIS": "davis_", "SNAP": "snapdragon_"}
READ_FIRST = ("All three tools use each bag's IMU weights from the residuals in UZH's own Kalibr results. Kalibr's intrinsics and "
              "baseline are inputs from the calibration UZH ships.")

LIKE_FOR_LIKE = ("Every tool starts from the camera chain UZH ships and uses the same IMU sigmas on the same bags. Kalibr keeps "
                 "the camera values fixed; MVIS and Basalt refine them.")

WEIGHTS_NOTE = "All tools use each bag's IMU weights from UZH's Kalibr residuals."

FIXED_OLD = ("Its camera + IMU runs take intrinsics and baselines as input, from an MVIS export or, on T6 and T11, from its own "
             "camera-only calibration; T7 ELP-L readout is held at 0.")

FIXED_NEW = "Its camera + IMU runs take intrinsics and baselines as input, here from the calibration UZH ships."

KALIBR_CMD = ("kalibr_calibrate_imu_camera --bag input.bag --cams camchain.yaml --imu imu.yaml \\\n"
              "    --imu-models scale-misalignment --target target.yaml --timeoffset-padding 0.1 --dont-show-report")



def jobs_for(weights, fid):
    """A family's bags, read from the hub stage's imu_weights.yaml so the list can't drift from the runs."""
    jobs = sorted(k for k in weights if k.startswith(PREFIX[fid]))
    if not jobs:
        raise ValueError(f"no {fid} bags in imu_weights.yaml")
    return jobs


def rekey(stats):
    """The stats file's families under the names the page shows."""
    return dict(stats, families={new: stats["families"][old] for new, old in FAMILIES.items()})


def how_to_read(text):
    """The leaderboard's How to read this, with its one sentence about other families' Kalibr inputs replaced."""
    if text.count(FIXED_OLD) != 1:
        raise ValueError("leaderboard How to read this changed")
    return text.replace(FIXED_OLD, FIXED_NEW)


def _mono(text):
    return f"<span class='mono'>{html.escape(str(text))}</span>"


def _pre(text):
    return f"<pre class='cfg'>{html.escape(text.rstrip())}</pre>"


def _fold(title, cmd, body):
    return f"<details class='cfgfold'><summary>Run config · {title}</summary>{_pre(cmd)}{body}</details>"


def run_configs_html(jobs, weights, mvis_file, kalibr_file, basalt_status):
    """Each tool's run config: its command, the first bag's file, and how the other bags differ. Local paths are already out."""
    first = jobs[0]
    runs = "".join(f"<li>{_mono(j)} · gyro {weights[j]['sigma_g']:.2e} · accel {weights[j]['sigma_a']:.2e}</li>" for j in jobs)
    others = f"<p class='cfgp'>Runs ({len(jobs)}, gyro and accel noise density; bias sigmas are 0.1 of these):</p><ul class='cfgl'>{runs}</ul>"
    basalt_cmd = " \\\n    ".join(basalt_status["command"])
    return {"MVIS": _fold(f"MVIS · {_mono('mvis cam-imu')}", "mvis cam-imu -c configs/cam_imu_<bag>_kalibr_model.yaml",
                          f"<p class='cfgp'>{_mono(first)}, commit f5cdce0</p>{_pre(mvis_file)}{others}"),
            "Kalibr": _fold(f"Kalibr · {_mono('kalibr_calibrate_imu_camera')}", KALIBR_CMD,
                            f"<p class='cfgp'>{_mono('imu.yaml')} for {_mono(first)}</p>{_pre(kalibr_file)}{others}"),
            "Basalt": _fold(f"Basalt · {_mono('basalt_calibrate_imu')}", basalt_cmd,
                            f"<p class='cfgp'>{_mono(first)}, build 77daf1c</p>{others}")}


def without_repeated_weights_note(stats):
    """READ_FIRST already says this, above the family's notes."""
    for fam in stats["families"].values():
        fam["caveat"] = fam["caveat"].replace(WEIGHTS_NOTE, "").strip()
    return stats


def uzh_json(fragment, how_to_read_text, batch=BATCH):
    return dict(batch=batch, fragment=fragment, how_to_read=how_to_read_text)
