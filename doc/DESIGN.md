# Open MVIS Site — Design Document

Companion to [`PLAN.md`](./PLAN.md). `PLAN.md` is the *what* and *why*; this
document is the *how* — concrete architecture decisions, file layout, schemas,
and the rationale behind each non-obvious choice. It is meant to outlive the
specific tickets that produced it.

---

## 1. Goals (recap)

1. Become the de-facto public benchmark for camera + visual-inertial sensor
   calibration over a 10–20 year horizon.
2. Preserve every page of the legacy jemdoc site.
3. Look professional on first load, not just functional.
4. Make submission to the leaderboard a one-PR operation.
5. Static, free hosting (GitHub Pages) with zero ongoing infra cost.

The architecture below derives from these five constraints in roughly that
order of priority.

---

## 2. Stack

| Layer | Choice | Why |
|---|---|---|
| Framework | **Astro 6** | Static-by-default, zero JS shipped on prose pages, content collections with Zod typing. |
| Doc theme | **Starlight 0.38** | Sleek defaults exceed what we'd hand-build; sidebar, search (Pagefind), dark mode, mobile responsive, MDX, citations all out of the box. |
| Math | **remark-math + rehype-katex** | KaTeX > MathJax for static sites: no client-side TeX engine, smaller payload, faster paint. |
| Runtime | **Node 22 (via nvm)** | User-local, no sudo. `nvm use` brings up the exact version. |
| Hosting | **GitHub Pages** | Free, the existing `docs/CNAME` carries over. `dist/` → `docs/` at cut-over. |
| Image opt | **Astro `<Image>` + sharp** | 1.6 MB JPGs become 16 KB WebP automatically. |
| Search | **Pagefind** (bundled w/ Starlight) | Static full-text index, no server, works offline. |

**Rejected alternatives:**

- *Restyle existing jemdoc CSS* — caps the credibility ceiling, no path to a
  leaderboard or modern UX. Inconsistent with goal (1).
- *Docusaurus* — heavier, React-only, less polished default look.
- *Nextra v4* — fine but pulls in full Next.js for what is essentially a static
  doc site. Overkill today.
- *VitePress* — leaner but smaller ecosystem; Starlight wins on features.
- *Hugo / Jekyll* — strong static generators but their MDX/content-collection
  story is weaker than Astro's, which matters for the leaderboard.

---

## 3. Repository layout

```
mvis_pages/
├── doc/
│   ├── PLAN.md              # the product plan (vision, phases, risks)
│   └── DESIGN.md            # this file
├── site/                    # Astro app — the source of truth for the site
│   ├── astro.config.mjs
│   ├── package.json
│   ├── src/
│   │   ├── assets/          # images, optimised at build time
│   │   ├── components/
│   │   │   ├── ThemeProvider.astro     # forces light default
│   │   │   ├── Footer.astro            # custom footer (cite, GH, license)
│   │   │   └── LeaderboardTable.astro  # filter/sort island
│   │   ├── content/
│   │   │   ├── docs/        # MDX prose pages, mirrors sidebar structure
│   │   │   └── leaderboard/ # one YAML file per submission row
│   │   ├── content.config.ts           # Zod schemas
│   │   └── styles/custom.css
│   └── tsconfig.json
├── docs/                    # GitHub Pages serves this (legacy + future cut-over)
│   └── CNAME
├── openmvis/                # legacy jemdoc sources (kept for reference until cut-over)
└── README.md
```

The legacy `openmvis/` and `jemdoc` toolchain stay in place during the
transition. After the cut-over (Phase 1 exit) they can be archived or removed.

---

## 4. Theme system

### 4.1 Default mode

**Light is the default.** Every comparable benchmark site (KITTI, Papers with
Code, nuScenes, Hilti) is light-by-default. Researchers screenshot for papers
and pair the page with white-background plots. Dark stays available via the
sun/moon picker top-right.

Implementation: `src/components/ThemeProvider.astro` overrides the Starlight
default, which would otherwise follow `prefers-color-scheme`. The override
runs as an inline `<head>` script before paint, so there's no flash of dark
mode for system-dark users.

### 4.2 Palette

| Token | Light | Dark | Source |
|---|---|---|---|
| Page bg | `#ffffff` (Starlight default) | `#0f172a` (Tailwind slate-900) | warmer than near-black, more "research" |
| Sidebar / cards | `#f6f6f6` (default) | `#1e293b` (slate-800) | one step lighter than bg |
| Body text | dark slate | `#e2e8f0` (slate-200) | high contrast |
| Accent | `#0284c7` (sky-600) | `#38bdf8` (sky-400) | picks up the lens-glass tone in the VI-Rig hero |
| Accent low | `#e0f2fe` | `#0c4a6e` | for cite-pill / highlights |

Palette is set in `src/styles/custom.css` using Starlight's CSS variable hooks
(`--sl-color-*`). No Tailwind dependency.

### 4.3 Layout density

- `--sl-content-width: 72rem` (~1150 px). Up from Starlight's 45 rem default.
  Research pages carry tables, code blocks, equations, and figures that
  benefit from horizontal room.
- `--sl-sidebar-width: 19.5 rem`. Bumped slightly to fit the longest menu
  labels ("Base IMU Calib").

### 4.4 Typography

Starlight's default sans-serif (system stack) — no web font dependency, instant
paint. Code and tables get `font-variant-numeric: tabular-nums` so columns of
numbers align.

---

## 5. Content model

### 5.1 Two collections

```ts
// src/content.config.ts
collections = {
  docs:        defineCollection({ loader: docsLoader(),  schema: docsSchema() }),
  leaderboard: defineCollection({ loader: glob({ pattern: '**/*.yaml', ... }),
                                  schema: leaderboardEntry }),
};
```

- **`docs`** — Markdown/MDX prose pages. One file per sidebar entry. Loaded via
  Starlight's standard `docsLoader`.
- **`leaderboard`** — one YAML file per submission row. Loaded via Astro's
  `glob` loader with a strict Zod schema (see §6).

### 5.2 Sidebar structure

Mirrors the legacy `MENU` jemdoc file 1:1:

- **Open MVIS** — Home, Compilation, Quick Start, Contributors
- **Calibration** — Overview, Procedures, Results
- **MVIS Datasets** — Sensors, MVIS Data, 4 IMUs + 3 Cams, 4 IMUs + 4 Cams,
  Analysis
- **MVIS Math** — Calib Graph, Base IMU Calib, Aux IMU Calib, Camera Calib,
  Observability, Degeneracy
- **Leaderboard** — Browse, Submit

### 5.3 Math pages

Six pages currently stubbed ("Coming soon"). When written, they should use:

- `$inline math$` for inline expressions
- `$$display math$$` (with blank lines around) for display equations
- AMS environments inside `$$...$$` blocks for aligned multi-line derivations

KaTeX rendering is already wired, so these "just work" once the prose lands.

**MDX gotcha:** raw `{...}` in markdown is parsed as JSX. Wrap any LaTeX with
literal braces in `$...$` math delimiters or escape with `\{`. Inline-code
substitutions (e.g. `R_CI` instead of `\mathbf{R}_{CI}`) are an acceptable
placeholder before math is wired into a page.

---

## 6. Leaderboard architecture

### 6.1 Submission schema (Zod)

Every row in the leaderboard is one YAML file under
`src/content/leaderboard/<method>__<config>.yaml`, validated at build time
against the schema in `content.config.ts`. The schema is the contract.

Top-level blocks:

| Block | Purpose |
|---|---|
| `method` | Name, version, algorithm family, repo / paper URLs, `open_source` flag. |
| `sensor_config` | One of seven categories, plus integer counts and free-form sensor lists. |
| `dataset` | Dataset name + version + sequences this entry was evaluated on. |
| `results` | Each metric is `{value, stddev, n_runs}` or a bare number. Missing metrics are `null`/omitted (rendered as `—`, never as `0`). |
| `artifacts` | Optional links to a full HTML report and the raw YAML for re-ingestion. |
| `submitted` | Author, date, hardware. The accountability trail. |

YAML dates must be quoted (`"2026-04-20"`) because the loader otherwise
auto-coerces unquoted ISO strings to `Date` objects, which fail the
`z.string()` validation.

### 6.2 Sensor configuration taxonomy

Seven mutually-exclusive categories. The set is closed for v1 to keep
apples-to-apples filtering meaningful:

| Slug | Label |
|---|---|
| `cam_only_mono` | Camera only — mono |
| `cam_only_stereo` | Camera only — stereo |
| `cam_only_multi` | Camera only — multi (≥3) |
| `single_imu_single_cam` | 1 IMU + 1 cam |
| `single_imu_multi_cam` | 1 IMU + multi cams |
| `multi_imu_single_cam` | Multi IMU + 1 cam |
| `multi_imu_multi_cam` | Multi IMU + multi cams |

Future scope (LiDAR, depth, event cameras) is documented but not in v1.

### 6.3 Algorithm families

Five families. Closed set — submissions that don't fit map to `other`:

- `discrete_factor_graph` (CamCalib, MVIS — GTSAM/Ceres batch MAP)
- `continuous_time_bspline` (Kalibr, Basalt — SE(3) B-splines)
- `filter_ekf` (OpenVINS — online EKF in the state)
- `learning_based` (Calib-Net etc.)
- `other` (hybrid, none of the above)

### 6.4 Metrics

Borrowed from the literature. KITTI's lesson against single-aggregate rankings
applies — every metric is shown, none is hidden behind a "score":

| Metric | Unit | Direction |
|---|---|---|
| `reprojection_rmse_px` | px | lower = better |
| `extrinsic_rot_err_deg` | deg | lower = better |
| `extrinsic_trans_err_cm` | cm | lower = better |
| `timeoffset_err_ms` | ms | lower = better |
| `runtime_s` | s | lower = better (with caveats) |
| `convergence_rate_pct` | % | higher = better |

### 6.5 Rendering

`src/components/LeaderboardTable.astro` is the table. Behaviour:

- Server-renders a `<table>` of all rows (Pagefind index includes them).
- Three `<select>` controls: filter by category, filter by family, sort by
  metric. State changes are handled by a vanilla `<script is:inline>` — no
  React/Vue dependency.
- Each row carries `data-*` attributes for the filter/sort fields, so the
  client script never re-fetches anything.
- Visible row count and total are shown next to the controls.
- 💾 / 📄 icons per row link to the repo and paper if present.

### 6.6 Submission flow

PR-based, no server side:

1. Submitter forks the site repo.
2. Adds one YAML file under `src/content/leaderboard/`.
3. Optionally adds a full HTML report under `site/public/reports/` and links
   from `artifacts.report_html`.
4. Opens a PR. CI runs `npm run build`; the Zod schema fails the build if the
   submission is malformed.
5. A maintainer merges. The next site deploy includes the new row.

This mirrors the workflow Hilti's SLAM Challenge uses (which grew from 27 →
42 → 69 teams in three years). When traffic warrants, we revisit hidden-GT
server-side eval.

---

## 7. Build and deploy

### 7.1 Local development

```bash
nvm use 22
cd site/
npm install        # only needed once
npm run dev        # http://localhost:4321
npm run build      # writes to site/dist/
```

### 7.2 Production deploy

The legacy jemdoc site lives in `docs/` and is served by GitHub Pages via the
`CNAME` file. The new Starlight site builds into `site/dist/`.

**Cut-over (one-time, when ready):**

1. `mv docs docs_jemdoc_archive`
2. `cp -r site/dist docs`
3. `cp docs_jemdoc_archive/CNAME docs/CNAME`
4. Commit, push, verify the live site.

After cut-over, automate the build with a GitHub Action that runs
`npm run build` on every push to `main` and commits `site/dist/` → `docs/`.

### 7.3 Astro 6 outDir gotcha

We initially configured `outDir: '../docs_new'` to build directly into a
sibling folder. Astro 6 + Starlight 0.38 hits an asset-pipeline bug here
(ENOENT on hashed image filenames in `.astro/_astro/`). Reverted to the
default `dist/` and copy at deploy time. Worth retrying after Astro 6.x
patches the pipeline; tracked nowhere yet — this doc is the record.

---

## 8. Decisions and tradeoffs

| Decision | Chosen | Alternative | Why |
|---|---|---|---|
| Doc framework | Astro Starlight | Docusaurus, Nextra, VitePress | Best default look + lightest output. |
| Theme default | Light | System pref (Starlight default), Dark | Academic norm; researchers screenshot for papers. |
| Dark palette | Slate-900 | Pure black, Zinc | Cohesive with sky-blue accent; less consumer-product feel. |
| Math engine | KaTeX | MathJax | Static, smaller, faster paint. |
| Content width | 72 rem | 45 rem (default), 60 rem | Explicit user preference; suits tables/code/figures. |
| Leaderboard interactivity | Vanilla JS island | React/Preact island | No framework dep for one filter widget. |
| Submission flow | PR-based | Web form + Google Sheet | No infra; mirrors Hilti; PR diff is the audit trail. |
| Verification | Self-reported v1 | Hidden-GT server eval | No infra. Revisit at Phase 3. |
| Schema location | `site/src/content/leaderboard/` | Sibling repo `mvis_benchmark` | Same repo for v1; split if size demands. |
| Cut-over strategy | Manual `cp` to `docs/` | Direct outDir override | Astro 6 asset bug forces this; revisit. |

---

## 9. What this doc deliberately does NOT cover

- Implementation details of any single MDX page — read the file.
- Future leaderboard features (per-row drill-down, versioned snapshots,
  hidden-GT eval) — those live in `PLAN.md` Phase 3.
- The content of the math pages — those are stubs awaiting the paper.
- Marketing / communications strategy — out of scope here.

---

## 10. Update protocol

Edit this document when:

- A stack component is swapped (Starlight → X, KaTeX → Y).
- The schema changes shape (not just a new optional field).
- A category or family is added to the leaderboard taxonomy.
- A non-obvious workaround is added (Astro outDir bug, MDX `{}` parsing, etc.).

Do **not** edit this document for routine page additions or bug fixes — those
live in commits.
