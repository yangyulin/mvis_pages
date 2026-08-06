import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

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
    '/examples/monado-msd': '/examples/monado/',
    '/examples/tum-vie': '/examples/',
    '/math/calib-graph': '/concepts/calibration-graph/',
    '/math/camera-calib': '/concepts/camera-model/',
    '/math/base-imu-calib': '/concepts/camera-imu-math/base-imu/',
    '/math/aux-imu-calib': '/concepts/camera-imu-math/aux-imu/',
    '/math/observability': '/concepts/observability/',
    '/math/degeneracy': '/concepts/degeneracy/',
    '/leaderboard': '/benchmark/leaderboard/',
    '/leaderboard/submit': '/contribute/submit-results/',
  },

  integrations: [
    starlight({
      title: 'Open MVIS',
      description:
        'The benchmark for multi-visual-inertial sensor calibration — multi-IMU, multi-camera, with leaderboard.',
      logo: { src: './src/assets/logo-placeholder.svg' },
      // Both links must point at a PUBLIC repo or they 404 for visitors.
      // The toolbox repos (yangyulin/CamCalib, yangyulin/mvis-code) are private,
      // so the public site repo is the only working target today. Switch the
      // social link to CamCalib once that repo is published.
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
        Footer: './src/components/Footer.astro',
        // Applies the `wide: true` frontmatter opt-in (design plan §4).
        Head: './src/components/Head.astro',
      },

      // Sidebar — design plan §3. Eight groups, ordered concepts → how-to →
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
          label: 'Concepts',
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
          label: 'Examples',
          items: [
            { label: 'Overview', link: '/examples/' },
            { label: 'TUM VI', link: '/examples/tum-vi/' },
            { label: 'Monado', link: '/examples/monado/' },
            { label: 'Looper SA16', link: '/examples/looper-sa16/' },
          ],
        },
        {
          label: 'Reference',
          items: [
            { label: 'Configuration', link: '/reference/configuration/' },
            { label: 'CLI', link: '/reference/cli/' },
            { label: 'Result formats', link: '/reference/result-formats/' },
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
          label: 'Benchmark',
          items: [
            { label: 'Leaderboard', link: '/benchmark/leaderboard/' },
            { label: 'Methodology', link: '/benchmark/methodology/' },
          ],
        },
        {
          label: 'Contribute',
          items: [
            { label: 'Submit results', link: '/contribute/submit-results/' },
            { label: 'Submit a dataset', link: '/contribute/submit-dataset/' },
            { label: 'Governance', link: '/contribute/governance/' },
          ],
        },
        {
          label: 'About',
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
