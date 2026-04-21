import { defineCollection, z } from 'astro:content';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';
import { glob } from 'astro/loaders';

// Result stat: either {value, stddev, n_runs} or just a number (e.g. percentage).
const statObj = z.object({
  value: z.number(),
  stddev: z.number().nullable().optional(),
  n_runs: z.number().optional(),
});
const stat = z.union([statObj, z.number()]);

const leaderboardEntry = z.object({
  method: z.object({
    name: z.string(),
    version: z.string(),
    // High-level algorithm family (see Leaderboard page for full taxonomy).
    family: z.enum([
      'discrete_factor_graph',
      'continuous_time_bspline',
      'filter_ekf',
      'learning_based',
      'other',
    ]),
    open_source: z.boolean(),
    url_repo: z.string().optional().default(''),
    url_paper: z.string().optional().default(''),
  }),
  sensor_config: z.object({
    category: z.enum([
      'cam_only_mono',
      'cam_only_stereo',
      'cam_only_multi',
      'single_imu_single_cam',
      'single_imu_multi_cam',
      'multi_imu_single_cam',
      'multi_imu_multi_cam',
    ]),
    num_imus: z.number(),
    num_cams: z.number(),
    imus: z.array(z.string()).default([]),
    cameras: z.array(z.string()).default([]),
  }),
  dataset: z.object({
    name: z.string(),
    version: z.string(),
    sequences: z.array(z.string()).default([]),
  }),
  results: z.object({
    reprojection_rmse_px:   stat.optional(),
    extrinsic_rot_err_deg:  stat.optional(),
    extrinsic_trans_err_cm: stat.optional(),
    timeoffset_err_ms:      stat.optional(),
    runtime_s:              stat.optional(),
    convergence_rate_pct:   stat.optional(),
  }),
  artifacts: z.object({
    report_html: z.string().optional().default(''),
    raw_yaml:    z.string().optional().default(''),
  }).optional(),
  submitted: z.object({
    by:       z.string(),
    date:     z.string(),
    hardware: z.string().optional().default(''),
  }),
});

export const collections = {
  docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),
  leaderboard: defineCollection({
    loader: glob({ pattern: '**/*.yaml', base: './src/content/leaderboard' }),
    schema: leaderboardEntry,
  }),
};
