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

import { readdir, rename, readFile, writeFile, stat } from 'node:fs/promises';
import { join, extname } from 'node:path';

const OUT = new URL('../../docs/', import.meta.url).pathname;
const FROM = '_astro';
const TO = 'astro';
// Files that can contain a path reference.
const TEXT = new Set(['.html', '.css', '.js', '.mjs', '.json', '.xml', '.txt', '.map']);

async function walk(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await walk(p)));
    else out.push(p);
  }
  return out;
}

const src = join(OUT, FROM);
let exists = true;
try { await stat(src); } catch { exists = false; }

if (!exists) {
  console.log(`post-build: no ${FROM}/ in output — nothing to do`);
} else {
  await rename(src, join(OUT, TO));

  let touched = 0;
  for (const file of await walk(OUT)) {
    if (!TEXT.has(extname(file))) continue;
    const before = await readFile(file, 'utf8');
    const after = before.split(`/${FROM}/`).join(`/${TO}/`);
    if (after !== before) { await writeFile(file, after); touched++; }
  }
  console.log(`post-build: ${FROM}/ -> ${TO}/, rewrote ${touched} files`);
}

// Fail loudly rather than shipping a half-renamed site.
const leftovers = (await walk(OUT)).filter(
  (f) => TEXT.has(extname(f)) && f.indexOf(`${OUT}${TO}/`) !== 0,
);
for (const f of leftovers) {
  if ((await readFile(f, 'utf8')).includes(`/${FROM}/`)) {
    console.error(`post-build: FAILED — ${f} still references /${FROM}/`);
    process.exit(1);
  }
}
