// node --test site/scripts/rename-assets.test.mjs   (no packages needed)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { leftovers, postBuild, renameAssets, walk } from './rename-assets.mjs';

async function site() {
  const out = (await mkdtemp(join(tmpdir(), 'postbuild-'))) + '/';
  await mkdir(join(out, '_astro'), { recursive: true });
  await mkdir(join(out, 'a/b'), { recursive: true });
  await writeFile(join(out, '_astro/x.css'), 'url(/_astro/f.woff)');
  await writeFile(join(out, 'index.html'), '<link href="/_astro/x.css"><script src="/_astro/y.js">');
  await writeFile(join(out, 'a/b/page.json'), '{"p": "/_astro/z.png"}');
  await writeFile(join(out, 'a/plain.html'), 'no assets here');
  await writeFile(join(out, 'a/pic.png'), '/_astro/ inside a binary stays');
  return out;
}

test('walk lists every file, nested too', async () => {
  const out = await site();
  assert.deepEqual((await walk(out)).map((f) => f.slice(out.length)).sort(),
    ['_astro/x.css', 'a/b/page.json', 'a/pic.png', 'a/plain.html', 'index.html']);
});

test('renameAssets moves the folder and rewrites text files only', async () => {
  const out = await site();
  assert.equal(await renameAssets(out, '_astro', 'astro'), 3);
  await assert.rejects(stat(join(out, '_astro')));
  assert.equal(await readFile(join(out, 'astro/x.css'), 'utf8'), 'url(/astro/f.woff)');
  assert.equal(await readFile(join(out, 'index.html'), 'utf8'), '<link href="/astro/x.css"><script src="/astro/y.js">');
  assert.equal(await readFile(join(out, 'a/b/page.json'), 'utf8'), '{"p": "/astro/z.png"}');
  assert.equal(await readFile(join(out, 'a/pic.png'), 'utf8'), '/_astro/ inside a binary stays');
  assert.deepEqual(await leftovers(out, '_astro', 'astro'), []);
});

test('renameAssets without the folder does nothing', async () => {
  const out = await site();
  assert.equal(await renameAssets(out, '_none', 'none'), null);
  assert.equal(await readFile(join(out, 'index.html'), 'utf8'), '<link href="/_astro/x.css"><script src="/_astro/y.js">');
});

test('leftovers names a text file that still references the old folder, but not the renamed folder itself', async () => {
  const out = await site();
  await renameAssets(out, '_astro', 'astro');
  await writeFile(join(out, 'a/late.txt'), 'see /_astro/q.js');
  await writeFile(join(out, 'astro/self.js'), '"/_astro/" as a string');
  assert.deepEqual(await leftovers(out, '_astro', 'astro'), [join(out, 'a/late.txt')]);
});

test('postBuild with no folder says so and passes', async () => {
  const out = await site();
  assert.deepEqual(await postBuild(out, '_none', 'none'), { lines: [{ text: 'post-build: no _none/ in output — nothing to do' }], code: 0 });
});

test('postBuild renames, reports the count and passes', async () => {
  const out = await site();
  assert.deepEqual(await postBuild(out), { lines: [{ text: 'post-build: _astro/ -> astro/, rewrote 3 files' }], code: 0 });
  await assert.rejects(stat(join(out, '_astro')));
});

test('postBuild fails on a reference left without its folder', async () => {
  const out = await site();
  await writeFile(join(out, 'a/late.txt'), 'see /_gone/q.js');
  assert.deepEqual(await postBuild(out, '_gone', 'gone'), { lines: [{ text: 'post-build: no _gone/ in output — nothing to do' },
    { text: `post-build: FAILED — ${join(out, 'a/late.txt')} still references /_gone/`, err: true }], code: 1 });
});
