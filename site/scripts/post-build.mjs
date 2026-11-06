// Rename `_astro/` -> `astro/` in the published output, and rewrite every
// reference to it.
//
// WHY: this repo publishes via GitHub Pages `build_type: "legacy"` (Jekyll),
// which drops any path beginning with `_`. That silently 404'd every stylesheet
// and script while pages still returned 200 — the site rendered unstyled.
// A committed `docs/.nojekyll` did NOT fix it (verified: a fresh, uncached 404
// on `/_astro/<file>` while `/fig/<file>` from the same commit served 200).
//
// WHY NOT `build.assets`: setting it makes Astro look for its image cache under
// `.astro/<name>/` and the build dies with ENOENT during image generation.
// Renaming after the build avoids that entirely.
//
// The proper long-term fix is switching Pages to GitHub Actions
// (`build_type: "workflow"`), which skips Jekyll. That needs a repo-settings
// change; delete this script when it happens.

import { postBuild } from './rename-assets.mjs';

const { lines, code } = await postBuild(new URL('../../docs/', import.meta.url).pathname);
for (const l of lines) (l.err ? console.error : console.log)(l.text);
if (code) process.exit(code);
