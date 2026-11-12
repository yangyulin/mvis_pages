import { defineCollection, z } from 'astro:content';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';

// Page-type rule (guide-site design plan §3.1, binding).
// Every docs page declares exactly one type and obeys that type's contract:
//   tutorial  — one ordered happy path; no alternatives, options, or theory
//   guide     — task-oriented steps; no derivations (link to a concept)
//   concept   — explanation + math; no commands (link to a guide)
//   reference — exhaustive, anchor-per-entry, generated where possible
//   example   — a real run: config + generated plots + reproducibility
//   landing   — homepage only
//   embed     — hosts an external island (the Calibench leaderboard Space)
const pageType = z.enum([
  'tutorial',
  'guide',
  'concept',
  'reference',
  'example',
  'landing',
  'embed',
]);

export const collections = {
  docs: defineCollection({
    loader: docsLoader(),
    schema: docsSchema({
      extend: z.object({
        pageType,
        // Opt back into the wide content column (design plan §4): reference
        // tables, example galleries, and the leaderboard embed need 72rem;
        // prose pages keep the ~60rem measure.
        wide: z.boolean().default(false),
        sensor: z.string().optional(),
        example: z.string().optional(),
      }),
    }),
  }),
};
