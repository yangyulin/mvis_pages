# Open MVIS — Project Site & Benchmark

Source for the [Open MVIS](https://openmvis.github.io) website: documentation
for the multi-visual-inertial sensor calibration toolbox, the open MVIS
datasets, and the public **calibration leaderboard**.

The site is built with [Astro 6](https://astro.build) and the
[Starlight](https://starlight.astro.build) docs theme. Static HTML is served
by GitHub Pages from `docs/`.

> **Vision.** Open MVIS aims to become the de-facto public benchmark for
> camera and visual-inertial sensor calibration over the next 10–20 years —
> the role KITTI plays for driving and Papers with Code plays for ML. See
> [`doc/PLAN.md`](doc/PLAN.md) for the roadmap and [`doc/DESIGN.md`](doc/DESIGN.md)
> for the architecture.

---

## Quick start (developing the site)

Prerequisites: Node 22 (via [nvm](https://github.com/nvm-sh/nvm) recommended).

```bash
nvm use 22                  # or `nvm install 22` first
cd site/
npm install
npm run dev                 # http://localhost:4321
```

Build the static site:

```bash
npm run build               # writes to site/dist/
npm run preview             # serve the built site locally
```

---

## Repository layout

```
mvis_pages/
├── doc/
│   ├── PLAN.md              # product plan: vision, phases, risks
│   └── DESIGN.md            # architecture: stack, schema, decisions
├── site/                    # Astro source — edit here
│   ├── astro.config.mjs
│   └── src/
│       ├── content/docs/    # prose pages (MDX) — mirrors sidebar
│       └── content/leaderboard/  # one YAML per leaderboard row
├── docs/                    # GitHub Pages output (currently legacy jemdoc)
├── openmvis/                # legacy jemdoc sources (kept for reference)
├── jemdoc                   # legacy generator script (kept for reference)
└── README.md
```

---

## Adding content

### A new doc page

Create an MDX file under `site/src/content/docs/` matching the URL you want.
Example — `site/src/content/docs/calibration/my-page.mdx`:

```mdx
---
title: My Page
description: Short description used by search and social cards.
---

## Heading

Body content. Inline math: $f_x = 287.84$. Display math:

$$
\arg\min_{\boldsymbol{x}} \sum_i \rho(\|\mathbf{r}_i\|^2)
$$
```

Then add the page to the sidebar in `site/astro.config.mjs`.

### A new leaderboard entry

Drop a YAML file under `site/src/content/leaderboard/` following the schema
in [`doc/DESIGN.md` §6.1](doc/DESIGN.md#61-submission-schema-zod). The build
validates the schema; malformed entries fail the build.

The site shows the submission flow at `/leaderboard/submit/`.

---

## Math, MDX gotchas

- Use `$...$` for inline and `$$...$$` for display math (KaTeX).
- Raw `{...}` in MDX is parsed as JSX — wrap LaTeX braces inside `$...$` or
  escape with `\{`.
- Code blocks are syntax-highlighted by Expressive Code (Starlight default).

---

## Deploying

Currently the live site is the legacy jemdoc HTML in `docs/`. The cut-over
plan (manual, one-time) is documented in
[`doc/DESIGN.md` §7.2](doc/DESIGN.md#72-production-deploy).

Until the cut-over, both are kept in the repo.

---

## Documents

- [`doc/PLAN.md`](doc/PLAN.md) — long-term vision, phased roadmap, leaderboard
  filter/metric design, risks.
- [`doc/DESIGN.md`](doc/DESIGN.md) — architecture, stack rationale, content
  model, schema, theme system, Astro/MDX gotchas.

---

## Contributors

See [the Contributors page on the live site](https://openmvis.github.io/contributors/).

---

## License

MIT.
