// Shared reads of repeatability.json (site/scripts/export_repeatability.py, python/mvis_site/repeatability.py).
// Every sentence on the page comes from the JSON, where the export lints it; this file only arranges it.
import rep from '../data/leaderboard/repeatability.json';

export type Cell = (typeof rep.datasets)[number]['families'][number]['cells'][string];
export const data = rep as any;
export const groupOf = Object.fromEntries(data.groups.map((g: any) => [g.id, g]));

export function dataset(id: string) {
  const ds = data.datasets.find((d: any) => d.id === id);
  if (!ds) throw new Error(`no repeatability dataset ${id}`);
  return ds;
}

/** Caveat id -> letter, in order of first use in the dataset. */
export function caveatLetters(ds: any): Record<string, string> {
  const out: Record<string, string> = {};
  for (const f of ds.families)
    for (const g of ds.groups) for (const c of f.cells[g]?.caveats ?? []) if (!(c in out)) out[c] = 'abcdefghijklmnop'[Object.keys(out).length];
  return out;
}

export const detailId = (T: string, g: string) => `rp-${T}-${g}`;
export const hasDetail = (c: any) => c && c.state !== 'na';
export const isVerdict = (s: string) => s === 'most' || s === 'tie_top';
export const nMatched = (f: any) =>
  !f.n_matched ? 'no tool pair' : f.n_matched[0] === f.n_matched[1] ? `n = ${f.n_matched[0]} matched` : `n = ${f.n_matched[0]}–${f.n_matched[1]} matched`;
export const mode = (f: any) => (f.mode === 'cam' ? 'camera' : 'cam+IMU');
export const fmtSd = (x: number | null | undefined) => (x === null || x === undefined ? '–' : String(x));
