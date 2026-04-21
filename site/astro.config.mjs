import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

// Build into ../docs so the existing GitHub Pages setup (CNAME in docs/) keeps working
// once we cut over. Until then, only run `npm run build` after confirming you want to
// replace the current jemdoc-rendered HTML.
export default defineConfig({
  site: 'https://openmvis.github.io',
  srcDir: './src',
  publicDir: './public',
  markdown: {
    remarkPlugins: [remarkMath],
    rehypePlugins: [rehypeKatex],
  },
  integrations: [
    starlight({
      title: 'Open MVIS',
      description:
        'The benchmark for multi-visual-inertial sensor calibration — multi-IMU, multi-camera, with leaderboard.',
      logo: { src: './src/assets/logo-placeholder.svg' },
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/rpng/mvis' },
      ],
      editLink: {
        baseUrl: 'https://github.com/rpng/mvis_pages/edit/main/site/',
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
      },
      sidebar: [
        {
          label: 'Open MVIS',
          items: [
            { label: 'Home', link: '/' },
            { label: 'Compilation', link: '/compilation/' },
            { label: 'Quick Start', link: '/quick-start/' },
            { label: 'Contributors', link: '/contributors/' },
          ],
        },
        {
          label: 'Calibration',
          items: [
            { label: 'Overview', link: '/calibration/overview/' },
            { label: 'Procedures', link: '/calibration/procedures/' },
            { label: 'Results', link: '/calibration/results/' },
          ],
        },
        {
          label: 'MVIS Datasets',
          items: [
            { label: 'Sensors', link: '/datasets/sensors/' },
            { label: 'MVIS Data', link: '/datasets/mvis-data/' },
            { label: '4 IMUs + 3 Cams', link: '/datasets/4imus-3cams/' },
            { label: '4 IMUs + 4 Cams', link: '/datasets/4imus-4cams/' },
            { label: 'Analysis', link: '/datasets/analysis/' },
          ],
        },
        {
          label: 'MVIS Math',
          items: [
            { label: 'Calib Graph', link: '/math/calib-graph/' },
            { label: 'Base IMU Calib', link: '/math/base-imu-calib/' },
            { label: 'Aux IMU Calib', link: '/math/aux-imu-calib/' },
            { label: 'Camera Calib', link: '/math/camera-calib/' },
            { label: 'Observability', link: '/math/observability/' },
            { label: 'Degeneracy', link: '/math/degeneracy/' },
          ],
        },
        {
          label: 'Leaderboard',
          items: [
            { label: 'Browse', link: '/leaderboard/' },
            { label: 'Submit', link: '/leaderboard/submit/' },
          ],
        },
      ],
    }),
  ],
});
