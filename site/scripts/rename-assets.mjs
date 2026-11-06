// The steps of post-build.mjs as functions, so node --test can run them on a temp folder.
// Why the rename exists at all is explained in post-build.mjs.

import { readdir, rename, readFile, writeFile, stat } from 'node:fs/promises';
import { join, extname } from 'node:path';

// Files that can contain a path reference.
export const TEXT = new Set(['.html', '.css', '.js', '.mjs', '.json', '.xml', '.txt', '.map']);

export async function walk(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await walk(p)));
    else out.push(p);
  }
  return out;
}

// Move <out>/<from>/ to <out>/<to>/ and rewrite /<from>/ to /<to>/ in every text file.
// Returns null when there is no <from>/ folder, else the number of files rewritten.
export async function renameAssets(out, from, to) {
  try { await stat(join(out, from)); } catch { return null; }
  await rename(join(out, from), join(out, to));
  let touched = 0;
  for (const file of await walk(out)) {
    if (!TEXT.has(extname(file))) continue;
    const before = await readFile(file, 'utf8');
    const after = before.split(`/${from}/`).join(`/${to}/`);
    if (after !== before) { await writeFile(file, after); touched++; }
  }
  return touched;
}

// Text files outside <out>/<to>/ that still reference /<from>/. out must end with a slash.
export async function leftovers(out, from, to) {
  const found = [];
  for (const f of await walk(out)) {
    if (!TEXT.has(extname(f)) || f.indexOf(`${out}${to}/`) === 0) continue;
    if ((await readFile(f, 'utf8')).includes(`/${from}/`)) found.push(f);
  }
  return found;
}

// The whole post-build step: rename, then fail loudly rather than ship a half-renamed site.
// Returns the lines to print (err: to stderr) and the exit code.
export async function postBuild(out, from = '_astro', to = 'astro') {
  const touched = await renameAssets(out, from, to);
  const lines = [touched === null
    ? { text: `post-build: no ${from}/ in output — nothing to do` }
    : { text: `post-build: ${from}/ -> ${to}/, rewrote ${touched} files` }];
  const [left] = await leftovers(out, from, to);
  if (left) {
    lines.push({ text: `post-build: FAILED — ${left} still references /${from}/`, err: true });
    return { lines, code: 1 };
  }
  return { lines, code: 0 };
}
