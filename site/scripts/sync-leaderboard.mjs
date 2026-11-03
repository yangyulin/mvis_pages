// Copy the Calibench leaderboard records into the site: node scripts/sync-leaderboard.mjs <results-folder>
// Records come from calibench-vi/results (families.json, leaderboard.json). Run it after each new batch.
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const from = process.argv[2];
if (!from) throw new Error('usage: sync-leaderboard.mjs <folder with families.json and leaderboard.json>');
const read = (f) => JSON.parse(readFileSync(join(from, f), 'utf8'));
const families = read('families.json');
const board = read('leaderboard.json');

// History of a family's number belongs in the docs, not in a caveat on the board.
const clean = (t) => (t || '').replace(/^T\d+ since \d{4}-\d{2}-\d{2}: /, '').replace(/^Official since \d{4}-\d{2}-\d{2}, counted in the totals\. /, '');
const fam = Object.fromEntries(Object.entries(families.families).map(([k, v]) => [k, {
  mode: v.mode, title: v.title, subtitle: v.subtitle || '', caveat: clean(v.caveat), bas_caveat: clean(v.bas_caveat),
}]));
const out = 'src/data/leaderboard';
writeFileSync(join(out, 'families.json'), JSON.stringify({ batch: families.batch, scoring: families.scoring, families: fam }, null, 1) + '\n');
writeFileSync(join(out, 'leaderboard.json'), JSON.stringify(board, null, 1) + '\n');
console.log(`synced batch ${board.batch}: ${board.datasets.length} datasets, ${Object.keys(fam).length} families`);
