# mvis_site: the Python behind the generated pages

The sensor pages, the results tables and the UZH-FPV table on openmvis.com are generated, not hand-written. The code
that writes them is this lib. The scripts in `site/scripts/` only parse arguments and call it.

```
python/
  pyproject.toml   pytest and coverage settings (not a package; scripts put python/ on sys.path)
  cov.sh           tests under coverage; fails unless every lib line and branch runs (Playwright run() functions excluded)
  mvis_site/       the lib
  data/            public_sensors.yaml (page text) and photos/ (product photos)
  tests/           unit tests on synthetic fixtures (make_fixtures.py), golden files (fixtures/golden/), real-data tests behind env
```

| Module | What it does |
|---|---|
| `geometry` | rotations as log(R), lens fits, field of view, baseline |
| `results` | reads MVIS run folders; `solve_config` takes the only slice of the private config the export may see |
| `markup` | HTML shared with mira's private report pages (tables, SVG charts, the AprilGrid) |
| `lint` | `public_problems` (BANNED patterns), `refusals` (/home/, HF_TOKEN and the login name of whoever runs it) |
| `sensor_rig`, `sensor_parts`, `sensor_header`, `site_files` | the parts of a sensor page and the site-wide files |
| `export_examples` | the example pages: one run per example in seven steps, the overview cards and the sidebar entries; the config shown is the run's own with paths cut to file names |
| `export_sensors` | `collect` (reads results) → `render` (pure, returns a Plan) → `write` (the only step that touches the site) |
| `leaderboard`, `space` | the results tables, made by the leaderboard Space's own renderer; `space.CONTRACT` lists the names it uses |
| `repeatability` | per family x group of parameters, which tool scatters less on the recordings every compared tool ran (paired label-swap test, Holm within the cell, ties, too few); `gate` refuses records that are not the stats file's blocks; `check_public` keeps recording names and per-recording values out |
| `checks`, `browser/` | rules and printed reports of the nav, layout and hero checks; `browser/` drives Chrome (`run()`) and ffprobe |
| `assets` | the only reader of `mvis_site/assets/` and of `site/src/styles/custom.css` |

## Data contract

- **Public** (committed here): `data/public_sensors.yaml` holds every word on a sensor page. It names no run path,
  recording path, commit or device id; `tests/test_lint.py` checks the committed file.
- **Private** (stays in mira): `scripts/mvis/huggingface/community_sensors/data/sensors.yaml` holds roots, run
  paths and the recording to hash. It is passed by path; the lib reads only `roots` and, per sensor, `variants`
  (without `ref`), `board`, `series`, `sha256_of` and `demo_media` (public clip name to the file in `--media`, for
  clip files whose names carry a take id).
- **Results and clips** stay outside this repo: run folders under the private roots, demo clips in the `--media` dir.
- `lint.public_problems` checks every text drawn from the data before anything is written: each sensor's JSON
  (links stripped), its MDX, its process figures' strings and `sensor-nav.json`; one problem and nothing is written.
  The overview `index.mdx` prose is fixed in `site_files`, and `sensor.css` / `sensor-page.js` are the lib's own
  assets, so those are not linted. `lint.refusals` guards the results tables (board, UZH). Camera frames in a process figure stop the export.
- `assets/progress.js` is the `_PROGRESS_JS` player of openmvis `src/mvis/analysis/report_shell.py` at ec4475e
  (GPL-3.0-only), byte-exact; `test_progress_matches_mvis` compares it when `MVIS_SRC` is set.

## Commands

Run with a python whose numpy is < 2 (the anaconda base env; `/usr/bin/python3` has numpy 2), and always with
`PYTHONNOUSERSITE=1`: `~/.local` holds numpy 2 (its number reprs change the output; the scripts refuse it) and a
pytest plugin that breaks pytest.

```bash
# tests and coverage
cd python && PYTHONNOUSERSITE=1 python3 -m pytest -q
python/cov.sh                                    # fails on any missed line or branch; prints the pragma-excluded count
MVIS_GOLDEN=update PYTHONNOUSERSITE=1 python3 -m pytest -q tests/test_golden.py   # after a deliberate output change; review the diff
cd site && npm test                              # post-build rename steps (node --test)

# real-data tests (skipped without the env)
MVIS_SENSORS_CONFIG=<mira sensors.yaml> MVIS_MEDIA=<clips> MVIS_LEADERBOARD=<mira leaderboard dir> \
MVIS_UZH_ROOT=<uzh study dir, e.g. ~/Project/openmvis-internal/results/datacard/uzh_fpv> MVIS_SRC=<openmvis checkout> PYTHONNOUSERSITE=1 python3 -m pytest -q -m real_data

# exports (run from a worktree, review the diff before it reaches main)
PYTHONNOUSERSITE=1 python3 site/scripts/export_sensors.py --private-config <mira sensors.yaml> --media <clips dir> [--site <checkout>]
PYTHONNOUSERSITE=1 python3 site/scripts/export_uzh.py --leaderboard <mira leaderboard dir> --uzh-root ~/Project/openmvis-internal/results/datacard/uzh_fpv [--out FILE]
PYTHONNOUSERSITE=1 python3 site/scripts/export_board.py --leaderboard <mira leaderboard dir> [--records <snapshot> [--results-commit <its full sha>]] [--out DIR]
```

`export_board.py` without `--records` reads the current calibench-vi/results main, so it changes the live tables.
With `--records <snapshot> --results-commit <full sha>` it reproduces what a Hub read of that commit writes; a
short sha, or `--results-commit` without `--records`, is refused.

The Playwright drivers (`browser/*.run`) are not unit-tested: they need Chrome and a served build, and carry a
`pragma: no cover`. Everything they print or decide is a `checks.py` function with tests.

mira's private pages (`scripts/mvis/huggingface/community_sensors/page.py`) import this lib through
`$MVIS_SITE_LIB`, default `~/Project/mvis_pages/python`. Merge this lib into main and pull the main checkout before
mira's side, or the private pages stop building.

The generated files still say "Generated by export_sensor.py"; that text is kept so the output stays byte-identical
through the move.
