import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { readFileSync } from 'node:fs';

// Written by site/scripts/export_sensors.py (python/mvis_site) with the Sensors overview, so both list sensors in one order.
const sensorNav = JSON.parse(readFileSync(new URL('./src/data/sensor-nav.json', import.meta.url), 'utf8'));
// Sensor wiki subgroups, one per sensor-nav.json group in file order.
const sensorGroups = [...new Set(sensorNav.map((n) => n.group))].map((group) => ({
  label: group,
  collapsed: true,
  items: sensorNav.filter((n) => n.group === group).map(({ label, link }) => ({ label, link })),
}));
// Written by site/scripts/export_results.py: one Dataset eval page per dataset, in page order (ours first).
const resultsNav = JSON.parse(readFileSync(new URL('./src/data/results-nav.json', import.meta.url), 'utf8'));

// GitHub Pages serves `main:/docs`, so the build writes there. A build therefore
// publishes the site — there is no separate deploy step.
//
// Astro EMPTIES outDir before every build. Anything that must survive a build
// lives in `public/`, not in `docs/` directly. Currently:
//   - CNAME  the custom domain. Lose it and openmvis.com goes down.
//   - fig/   legacy jemdoc images, kept so old inbound image links still resolve.
//   - .nojekyll  Pages uses LEGACY (Jekyll) builds on this repo. Without this,
//               Jekyll strips `_astro/` (all CSS+JS -> 404) and its Liquid
//               parser fails the build on the BibTeX `{{` in citation blocks.
export default defineConfig({
  site: 'https://openmvis.com',
  srcDir: './src',
  publicDir: './public',
  outDir: '../docs',

  markdown: {
    remarkPlugins: [remarkMath],
    rehypePlugins: [rehypeKatex],
  },

  // Redirects — design plan §3.2 (O7).
  // These cover the first Starlight tree (5 groups), superseded by the 8-group
  // migration. The *legacy jemdoc* URLs (openmvis.com/*.html) cannot live here:
  // a redirects key ending in `.html` builds as a directory, so /Foo.html would
  // 404. They are static files in `public/` instead.
  redirects: {
    '/benchmark/sensors/looper-insight9-arm': '/sensors/looper-insight9/',
    '/compilation': '/getting-started/installation/',
    '/quick-start': '/getting-started/quickstart/',
    '/contributors': '/about/contributors/',
    '/calibration/overview': '/getting-started/overview/',
    '/calibration/procedures': '/guides/camera-imu-calibration/',
    '/calibration/results': '/reference/result-formats/',
    '/datasets/sensors': '/getting-started/requirements/',
    '/datasets/mvis-data': '/reference/datasets/',
    '/datasets/analysis': '/reference/evaluation/',
    '/datasets/4imus-3cams': '/reference/datasets/virig-4imus-3cams/',
    '/datasets/4imus-4cams': '/reference/datasets/virig-4imus-4cams/',

    // --- Examples reshaped to Monado / Looper / TUM VI (2026-08-05) ---
    '/examples/in-house-4imus-3cams': '/reference/datasets/virig-4imus-3cams/',
    '/examples/in-house-4imus-4cams': '/reference/datasets/virig-4imus-4cams/',
    '/examples/monado-msd': '/benchmark/examples/monado/',
    '/examples/tum-vie': '/benchmark/examples/',
    '/math/calib-graph': '/concepts/calibration-graph/',
    '/math/camera-calib': '/concepts/camera-model/',
    '/math/base-imu-calib': '/concepts/camera-imu-math/base-imu/',
    '/math/aux-imu-calib': '/concepts/camera-imu-math/aux-imu/',
    '/math/observability': '/concepts/observability/',
    '/math/degeneracy': '/concepts/degeneracy/',
    '/leaderboard': '/benchmark/results/',
    '/leaderboard/submit': '/contribute/submit-results/',
    '/examples/hanpo': '/sensors/hampo/',
    '/examples/hampo': '/sensors/hampo/',
    '/examples/a4n': '/sensors/xq20/',
    '/benchmark/sensors/a4n': '/sensors/xq20/',
    '/examples/dibuli-prism-a4l': '/sensors/dibuli-prism-a4l/',
    '/examples/gi-ego1': '/sensors/gi-ego1/',
    '/examples/gi-ego1gs': '/sensors/gi-ego1gs/',
    '/examples/gi-ego1-gs-module': '/sensors/gi-ego1gs/',
    '/benchmark/sensors/gi-ego1-gs-module': '/sensors/gi-ego1gs/',
    '/examples/looper-insight9': '/sensors/looper-insight9/',
    // Pages moved on 2026-11-09 (Benchmark and Sensor wiki split) are not here: scripts/moved-pages.mjs writes
    // their redirects from src/data/moved.json after the build, keeping the #fragment of old deep links.
  },

  integrations: [
    starlight({
      title: 'Open MVIS',
      description:
        'The benchmark for multi-visual-inertial sensor calibration — multi-IMU, multi-camera, with leaderboard.',
      logo: { src: './src/assets/logo-placeholder.svg' },
      // Both links must point at a PUBLIC repo or they 404 for visitors.
      // The toolbox repos (yangyulin/MVIS, yangyulin/mvis-code) are private,
      // so the public site repo is the only working target today. Switch the
      // social link to MVIS once that repo is published.
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/yangyulin/mvis_pages' },
      ],
      editLink: {
        baseUrl: 'https://github.com/yangyulin/mvis_pages/edit/main/site/',
      },
      lastUpdated: true,
      pagination: true,
      tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 4 },
      customCss: [
        './src/styles/custom.css',
        'katex/dist/katex.min.css',
      ],
      components: {
        ThemeProvider: './src/components/ThemeProvider.astro',
        // Homepage hero: calibration loop + synced camera tiles + readout. Starlight
        // only renders Hero on pages with `hero` frontmatter (the landing page).
        Hero: './src/components/HomeHero.astro',
        Footer: './src/components/Footer.astro',
        // Applies the `wide: true` frontmatter opt-in (design plan §4).
        Head: './src/components/Head.astro',
        PageTitle: './src/components/PageTitle.astro',
      },

      // Sidebar — design plan §3. Eight sections (Benchmark then Sensor wiki since 2026-11-09), ordered concepts → how-to →
      // reference (COLMAP's spine, §1.1). Every leaf declares its pageType in
      // its own frontmatter, enforced by the §3.1 rule.
      sidebar: [
        {
          label: 'Getting started',
          items: [
            { label: 'Overview', link: '/getting-started/overview/' },
            { label: 'Requirements', link: '/getting-started/requirements/' },
            { label: 'Installation', link: '/getting-started/installation/' },
            { label: 'Quickstart', link: '/getting-started/quickstart/' },
          ],
        },
        {
          label: 'Guides',
          items: [
            { label: 'Calibration motion', link: '/guides/calibration-motion/' },
            { label: 'Camera calibration', link: '/guides/camera-calibration/' },
            { label: 'Camera–IMU calibration', link: '/guides/camera-imu-calibration/' },
            { label: 'Multi-camera / multi-IMU rigs', link: '/guides/multi-sensor-rigs/' },
            { label: 'Rolling shutter', link: '/guides/rolling-shutter/' },
            { label: 'Corrected-dataset export', link: '/guides/corrected-datasets/' },
            { label: 'Round-trip validation', link: '/guides/roundtrip/' },
            { label: 'Simulation & synthetic data', link: '/guides/simulation/' },
          ],
        },
        {
          label: 'Benchmark',
          items: [
            {
              label: 'Examples',
              collapsed: true,
              // Written by site/scripts/export_examples.py with the Examples overview, so both list examples in one order.
              items: JSON.parse(readFileSync(new URL('./src/data/examples-nav.json', import.meta.url), 'utf8')),
            },
            { label: 'Why calibrate t_ga', link: '/benchmark/tga/' },
            {
              label: 'Results',
              collapsed: true,
              items: [
                { label: 'Leaderboard', link: '/benchmark/results/' },
                { label: 'Datasets eval', collapsed: true, items: resultsNav.map(({ label, link }) => ({ label, link })) },
              ],
            },
            { label: 'Methodology', link: '/benchmark/methodology/' },
          ],
        },
        {
          // Open, with collapsed device-kind subgroups: 4 rows on a phone; a sensor page opens its own subgroup.
          label: 'Sensor wiki',
          items: [{ label: 'Overview', link: '/sensors/' }, ...sensorGroups],
        },
        {
          label: 'Concepts',
          collapsed: true,
          items: [
            { label: 'Notation & glossary', link: '/concepts/notation/' },
            { label: 'Camera model', link: '/concepts/camera-model/' },
            { label: 'IMU model', link: '/concepts/imu-model/' },
            {
              label: 'Camera–IMU calibration math',
              collapsed: true,
              items: [
                { label: 'Overview', link: '/concepts/camera-imu-math/' },
                { label: 'Base IMU factor', link: '/concepts/camera-imu-math/base-imu/' },
                { label: 'Auxiliary IMU factor', link: '/concepts/camera-imu-math/aux-imu/' },
              ],
            },
            { label: 'Calibration graph', link: '/concepts/calibration-graph/' },
            { label: 'Observability', link: '/concepts/observability/' },
            { label: 'Degeneracy', link: '/concepts/degeneracy/' },
            { label: 'Continuous-time refinement', link: '/concepts/continuous-time/' },
          ],
        },
        {
          label: 'Reference',
          collapsed: true,
          items: [
            { label: 'Configuration', link: '/reference/configuration/' },
            { label: 'CLI', link: '/reference/cli/' },
            { label: 'Result formats', link: '/reference/result-formats/' },
            { label: 'Capture database', link: '/reference/database/' },
            { label: 'Evaluation & metrics', link: '/reference/evaluation/' },
            { label: 'Python API', link: '/reference/python-api/' },
            {
              label: 'Datasets',
              collapsed: true,
              items: [
                { label: 'Overview', link: '/reference/datasets/' },
                { label: 'VI-Rig — 4 IMUs + 3 cams', link: '/reference/datasets/virig-4imus-3cams/' },
                { label: 'VI-Rig — 4 IMUs + 4 cams', link: '/reference/datasets/virig-4imus-4cams/' },
              ],
            },
          ],
        },
        {
          label: 'Contribute',
          items: [
            { label: 'Submit results', link: '/contribute/submit-results/' },
            { label: 'Regression testing', link: '/contribute/regression-testing/' },
            { label: 'Submit a dataset', link: '/contribute/submit-dataset/' },
            { label: 'Governance', link: '/contribute/governance/' },
          ],
        },
        {
          label: 'About',
          collapsed: true,
          items: [
            { label: 'Contributors & citation', link: '/about/contributors/' },
            { label: 'Comparison vs Kalibr / Basalt', link: '/about/comparison/' },
            { label: 'FAQ & troubleshooting', link: '/about/faq/' },
            { label: 'Changelog', link: '/about/changelog/' },
            { label: 'Roadmap', link: '/about/roadmap/' },
            { label: 'License', link: '/about/license/' },
          ],
        },
      ],
    }),
  ],
});
