// Redirect pages for addresses moved on 2026-11-09 (site/src/data/moved.json). Astro's own redirect pages use a
// meta refresh, which drops the #fragment of old deep links (results folds, sensor-page sections). These pages
// carry the query and hash over with location.replace; the meta refresh is only a no-script fallback.

import { access, mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const SAFE = /^\/(?!\/)(?:[a-z0-9-]+\/)*$/; // a site route: no quotes, no .., no protocol-relative host

export function movedPage(from, to) {
  for (const a of [from, to]) if (!SAFE.test(a)) throw new Error(`bad address: ${a}`);
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Redirecting to: ${to}</title>`
    + `<meta name="robots" content="noindex"><link rel="canonical" href="https://openmvis.com${to}">`
    + `<script>location.replace('${to}' + location.search + location.hash)</script>`
    + `<noscript><meta http-equiv="refresh" content="0;url=${to}"></noscript></head>`
    + `<body><a href="${to}">Moved from <code>${from}</code> to <code>${to}</code></a></body></html>\n`;
}

export async function writeMovedPages(out, moved) {
  for (const [from, to] of Object.entries(moved)) {
    const html = movedPage(from, to);
    const file = join(out, from, 'index.html');
    // Astro writes nothing at a moved address, so a file there is a real page that would be lost.
    if (await access(file).then(() => true, () => false)) throw new Error(`a page already exists at moved address ${from}`);
    await mkdir(join(out, from), { recursive: true });
    await writeFile(file, html);
  }
  return Object.keys(moved).length;
}
