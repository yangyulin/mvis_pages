// node --test site/scripts/moved-pages.test.mjs   (no packages needed)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { movedPage, writeMovedPages } from './moved-pages.mjs';

test('movedPage keeps the query and hash, and falls back without script', () => {
  const html = movedPage('/old/', '/new/');
  assert.match(html, /<link rel="canonical" href="https:\/\/openmvis\.com\/new\/">/);
  assert.match(html, /<meta name="robots" content="noindex">/);
  assert.match(html, /location\.replace\('\/new\/' \+ location\.search \+ location\.hash\)/);
  assert.match(html, /<noscript><meta http-equiv="refresh" content="0;url=\/new\/"><\/noscript>/);
  assert.match(html, /<a href="\/new\/">/);
  // no bare refresh outside noscript: it would race the script and drop the hash
  assert.equal(html.replace(/<noscript>.*?<\/noscript>/s, '').includes('http-equiv'), false);
});

test('movedPage refuses addresses that would break out of the string or the folder', () => {
  for (const bad of [["/a'/", '/b/'], ['/a/', '/b"/'], ['a/', '/b/'], ['/../x/', '/b/'], ['/a/', '//evil.com/']])
    assert.throws(() => movedPage(...bad), /bad address/);
});

test('writeMovedPages writes each old address and replaces what Astro left there', async () => {
  const out = (await mkdtemp(join(tmpdir(), 'moved-'))) + '/';
  await mkdir(join(out, 'old/a'), { recursive: true });
  await writeFile(join(out, 'old/a/index.html'), 'astro redirect');
  const n = await writeMovedPages(out, { '/old/a/': '/new/a/', '/old/b/': '/new/b/' });
  assert.equal(n, 2);
  assert.match(await readFile(join(out, 'old/a/index.html'), 'utf8'), /location\.replace\('\/new\/a\/'/);
  assert.match(await readFile(join(out, 'old/b/index.html'), 'utf8'), /location\.replace\('\/new\/b\/'/);
});
