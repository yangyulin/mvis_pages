# Open MVIS — Site Modernization & Leaderboard Plan

> **Vision (10–20 year horizon).** Establish Open MVIS as the de-facto public benchmark
> for camera and visual-inertial sensor calibration, in the same role KITTI/nuScenes
> play for autonomous driving and Papers with Code plays for ML. Every paper that
> proposes a new calibration method should be expected to report its results on the
> Open MVIS leaderboard.

---

## 1. Why now

The current site is built with `jemdoc` (early-2010s static generator). It works but:

- **Looks dated** — table-based layout, no responsive design, no dark mode, no search.
- **Hard to extend** — adding interactive pages (a leaderboard) requires hand-rolled HTML.
- **No social signal** — no GitHub stars badge, no citation widget, no paper card.
- **No content discoverability** — sidebar menu only, no full-text search, no tag/category index.

Meanwhile, the broader landscape moved on:

- **Papers with Code, KITTI, nuScenes, Hilti SLAM Challenge** all run interactive,
  filterable leaderboards with code/paper links and per-sequence drill-down.
- **Astro Starlight, Nextra v4, Fumadocs** are the modern documentation stacks of
  choice (sleek defaults, built-in search, MDX, dark mode, fast static output, easy
  to embed React/Vue islands for the interactive leaderboard).

---

## 2. Goals (in priority order)

1. **Preserve every page of existing content.** Nothing is removed; everything
   migrates. The 18 `.jemdoc` source files in `openmvis/` map 1:1 to new MDX pages.
2. **Look professional and modern.** Responsive, dark mode, fast load, embedded
   figures, LaTeX (MathJax/KaTeX) parity, mobile-readable.
3. **Add a leaderboard page** with multi-axis filtering and per-sequence drill-down
   (see §5).
4. **Make submission easy.** A documented YAML/JSON schema + a "Submit" page that
   either accepts a PR to the data repo or a Google Form bridge — same model the
   Hilti challenge uses.
5. **Position as the long-term benchmark.** Add a "Cite this benchmark" block,
   versioned dataset releases, and a public roadmap.

---

## 3. Stack recommendation

**Recommended: Astro + Starlight** (with React islands for the leaderboard).

| Reason | Detail |
|---|---|
| Best-in-class default look | Starlight's defaults already exceed what we'd hand-build; clean typography, sticky nav, sidebar, dark mode, search out of the box. |
| Static output | Ships pure HTML; trivial to host on the existing GitHub Pages (`docs/` folder via `CNAME`). |
| MDX content | Existing prose content moves over; we can embed interactive leaderboard React component on a single page without making the rest of the site heavy. |
| Math support | KaTeX or MathJax via remark plugin — drop-in replacement for the current MathJax setup. |
| Migration cost | Low: 18 jemdoc files → 18 MDX files. Most content is paragraphs + lists + figures + equations, all of which translate mechanically. |

**Alternatives considered:**
- *Docusaurus* — heavier, React-only, slower builds. Fine but Starlight wins on visual default.
- *Nextra v4* — great if we later need full Next.js features; overkill today.
- *VitePress* — leaner but less featureful than Starlight; ecosystem smaller.
- *Stay on jemdoc, restyle the CSS* — cheapest, but caps the ceiling. Will not get us a credible leaderboard or modern feel. **Rejected** as inconsistent with the 10–20 year goal.

---

## 4. Phased plan

### Phase 0 — Decisions (before any code)
- Confirm Astro + Starlight as the stack.
- Confirm hosting stays on GitHub Pages with the existing `CNAME`.
- Pick a colour palette and logo treatment (suggest: neutral slate + one accent;
  align with the VI-Rig photo).
- Decide leaderboard data location: same repo (`/data/leaderboard/*.yaml`) or a
  sibling `mvis_benchmark` repo. **Recommend same repo for now**; split later if size demands.

### Phase 1 — Skeleton & content migration (no leaderboard yet)
1. Scaffold Starlight in a new branch. Keep `docs/` as the build output so GitHub
   Pages keeps working.
2. Carry the menu structure from `openmvis/MENU` to Starlight's sidebar config.
3. Convert the 18 `.jemdoc` files to MDX:
   - `index.jemdoc → index.mdx`
   - `Contributors / OverView / Results / MvisData / 4IMUs3Cams / 4IMUs4Cams /
     Analysis / CalibGraph / BaseImuCalib / AuxImuCalib / CameraCalib /
     Observability / Degeneracy / Compilation / Procedures / QuickStart /
     Sensors / AuxImuCalib`
4. Move figures from `docs/fig/` into `src/assets/` (Astro optimises them).
5. Verify every equation renders identically.
6. Add: GitHub stars badge, citation block (BibTeX), license, contact.
7. Add a homepage hero: short tagline ("The benchmark for multi-visual-inertial
   sensor calibration"), VI-Rig photo, three CTAs (Get started / Datasets / Leaderboard).

**Exit criteria:** every URL in `docs/` resolves to equivalent or better content,
site passes Lighthouse ≥ 90 on all four axes.

### Phase 2 — Leaderboard MVP
1. Add a new top-level menu item **Leaderboard**.
2. Define the **submission schema** (see §5) and commit `data/leaderboard/schema.json`.
3. Seed the leaderboard with at least three rows derived from the in-house repos:
   - **CamCalib** — already produces YAML reports under `results/regression/`; write
     a small script `scripts/ingest_camcalib.py` that extracts the per-run summary
     into a leaderboard row.
   - **MVIS** — text outputs in `data/calib_3D_v*.txt`; write `scripts/ingest_mvis.py`.
   - **Kalibr / OpenVINS / Basalt** — manual entries from published papers as
     reference baselines.
4. Build the React leaderboard component (see §5 for UX).
5. Add a "How to submit" page with the schema, an example PR, and a Google Form
   link as a low-friction alternative.

**Exit criteria:** leaderboard renders, filters work, at least 5 rows visible,
sorting is correct, mobile layout is usable.

### Phase 3 — Polish & growth
- Per-row "details" page with full report, plots, and reproducibility instructions.
- Versioned leaderboard snapshots (so paper authors can cite "Open MVIS v1.2 leaderboard, accessed YYYY-MM-DD").
- Public submission queue (open PRs visible on the site).
- Annual challenge announcement (model: Hilti SLAM Challenge — saw 27→42→69 teams in three years).

---

## 5. Leaderboard design

### 5.1 Filter axes (the user's spec, refined)

**Sensor configuration** (primary categorical filter, mutually exclusive):
1. Camera only — mono
2. Camera only — stereo
3. Camera only — multi (≥3)
4. Single IMU + single camera
5. Single IMU + multiple cameras
6. Multiple IMUs + single camera
7. Multiple IMUs + multiple cameras
8. *(consider also)* Camera + LiDAR, Camera + IMU + LiDAR — flag as "future scope" so we don't bake in a closed taxonomy.

**Algorithm family** (secondary multi-select):
- Continuous-time / B-spline (Kalibr, Basalt)
- Discrete-time batch / factor graph (CamCalib, MVIS, GTSAM-based)
- Filter-based / EKF online (OpenVINS-style)
- Learning-based (Calib-Net etc.)
- Other / hybrid

**Calibration target** (secondary multi-select):
- AprilGrid, ChArUco, Chessboard, ArUco, Targetless, Custom

**Dataset / sequence** (filter to scope the comparison):
- Open MVIS sequences (4IMU+3Cam, 4IMU+4Cam, etc.)
- EuRoC MAV
- TUM-VI
- Monado SLAM
- Custom (tagged)

**Modality flags shown as badges, not filters** (because they're orthogonal):
- Solves intrinsics? extrinsics? time offset? rolling shutter? IMU intrinsics?
- Online vs offline
- Open source? (link to repo)

### 5.2 Ranking metrics

Pick a small primary set and let users re-sort by any. Borrow KITTI's lesson: avoid
a single aggregate metric that hides per-class performance — expose the raw numbers.

| Metric | Unit | Notes |
|---|---|---|
| Reprojection RMSE | px | per-camera, mean across sequences |
| Extrinsic rotation error vs GT | deg | when GT exists |
| Extrinsic translation error vs GT | cm | when GT exists |
| Time-offset error vs GT | ms | the metric the recent ultrafast-calib paper used |
| IMU-IMU rotation error | deg | multi-IMU configs only |
| Wall-clock runtime | s | on a stated reference machine |
| Convergence success rate | % | over N independent runs |

Each cell shows **value · stddev (n runs)**. Missing metrics show "—" (don't penalise — make the absence visible).

### 5.3 Leaderboard UX (steal from the best)

- **Sticky filter sidebar** (Papers with Code style) on the left; result table on the right.
- **Sortable column headers** with arrow indicator and stable sort.
- **Sparkline / mini-bar in cell** for quick visual ranking (nuScenes-style).
- **Code / paper / report icons per row**: 📄 paper, 💾 code, 📊 full report (links to the per-run HTML report — CamCalib already generates one).
- **Per-row "expand"** to show per-sequence breakdown without leaving the page.
- **URL-encoded filter state** so a researcher can share `…/leaderboard?config=multi-imu-multi-cam&metric=t_offset_rms` directly.
- **"Submit your result"** button always visible top-right.
- **Last updated** timestamp + "data revision" git hash for citability.

### 5.4 Submission schema (draft)

```yaml
# data/leaderboard/<method>__<config>__<dataset>.yaml
method:
  name: CamCalib
  version: 0.4.2
  url_repo: https://github.com/.../CamCalib
  url_paper: https://arxiv.org/abs/...
  family: discrete_factor_graph     # see §5.1
  open_source: true
sensor_config:
  category: multi_imu_multi_cam     # one of the 7 categories
  num_imus: 4
  num_cams: 4
  imus: [MicroStrain GX3-25, GX3-35, Xsens MTI-100, RealSense T265]
  cameras: [BlackFly, T265-L, T265-R, ELP-L]
dataset:
  name: open_mvis_4imu4cam
  version: v1.0
  sequences: [seq01, seq02, seq03]
results:
  reprojection_rmse_px:    {value: 0.41, stddev: 0.03, n_runs: 5}
  extrinsic_rot_err_deg:   {value: 0.08, stddev: 0.02, n_runs: 5}
  extrinsic_trans_err_cm:  {value: 0.12, stddev: 0.04, n_runs: 5}
  timeoffset_err_ms:       {value: 0.31, stddev: 0.05, n_runs: 5}
  runtime_s:               {value: 142,  stddev: 8,    n_runs: 5}
  convergence_rate_pct:    100
artifacts:
  report_html: reports/camcalib__open_mvis_4imu4cam.html
  raw_yaml:    raw/camcalib__open_mvis_4imu4cam.yaml
submitted:
  by: Linde Yang
  date: 2026-04-19
  hardware: AMD 7950X, 64GB RAM, no GPU
```

This is the contract — once frozen, both `ingest_camcalib.py` and `ingest_mvis.py`
emit this format, and external submitters file PRs adding files of this shape.

---

## 6. Risks & open questions

- **Scope creep into a full benchmark suite.** Adding LiDAR, depth cameras, event cameras is tempting. Keep v1 to camera + IMU; document the extensibility.
- **Submission verification.** Hilti runs server-side eval on hidden GT. We don't have that infrastructure. Start with self-reported + reproducibility links; revisit hidden-GT eval at Phase 3.
- **GT availability.** For some Open MVIS sequences, true extrinsic GT may not exist (only consensus from multiple methods). Mark these explicitly as "consensus baseline" not "ground truth".
- **Schema bikeshed.** The schema in §5.4 will need one or two iterations once real data flows through it. Lock it after Phase 2.

---

## 7. Concrete next actions (in order)

1. Approve stack choice (Astro + Starlight) or pick alternative.
2. Confirm leaderboard data lives in this repo under `data/leaderboard/`.
3. Phase 1 work: scaffold Starlight, migrate one page end-to-end as the template.
4. Once one page works, batch-migrate the other 17.
5. Phase 2: implement the React leaderboard component against the schema in §5.4 with three seeded entries.

The three repos already in place — **mvis_pages** (this site), **CamCalib**, and
**mvis** — give us everything needed to seed the leaderboard with credible
in-house entries on day one. External baselines (Kalibr, OpenVINS, Basalt) come
from published numbers.
