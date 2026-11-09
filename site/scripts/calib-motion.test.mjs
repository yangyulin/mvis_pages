// node --test site/scripts/calib-motion.test.mjs   (no packages needed)
// The calibration-motion player's pure helpers: kb4 projection, the Now panel state and the exported move beats.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { kb4Project, boardDetections, nowState, prep, secs, largestRegion } from '../src/scripts/calib-motion.js';

const read = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url), 'utf8'));
const DATA = '../public/data/calib-motion/';
const guide = prep(read(`${DATA}v4/guide06c_60.json`), 'guide06c_60');

test('kb4 projection matches the MVIS views outline within 0.5 px', () => {
  const fx = read('./fixtures/calib-motion-kb4.json');
  for (const p of fx.poses) {
    fx.outline_W.forEach((X, j) => {
      const q = [0, 1, 2].map((a) => X[a] - p.p_WC[a]);
      const Xc = [0, 1, 2].map((i) => p.R_WC[0][i] * q[0] + p.R_WC[1][i] * q[1] + p.R_WC[2][i] * q[2]);
      const uv = kb4Project(fx.intr8, Xc);
      assert.ok(Math.hypot(uv[0] - p.outline_px[j][0], uv[1] - p.outline_px[j][1]) < 0.5, `step ${p.step} corner ${j}: ${uv}`);
    });
  }
});

test('nowState: start, a move boundary +-1 ms, last sample', () => {
  const a = nowState(guide, 0);
  assert.equal(a.k, null);
  assert.equal(a.name, 'Hold still');
  assert.equal(a.beatText, 'Count 3');
  assert.equal(a.next.k, 1);
  const t1 = guide.segs[1].t0;
  const b = nowState(guide, t1 - 1e-3);
  assert.equal(b.k, null);
  assert.equal(b.left, 1);
  assert.ok(b.until <= 3);
  const c = nowState(guide, t1 + 1e-3);
  assert.equal(c.k, 1);
  assert.equal(c.K, 4);
  assert.equal(c.name, 'Left-right');
  assert.match(c.beatText, /^Sweep 1 of 2 · going (left|right)$/);
  assert.equal(c.next.k, 2);
  assert.equal(c.next.name, 'Up-down');
  assert.ok(c.short.length <= 80);
  const z = nowState(guide, guide.s.t[guide.n - 1]);
  assert.equal(z.k, null);
  assert.equal(z.left, 0);
  assert.equal(z.next, null);
});

test('every short cue fits: at most 80 characters (real takes 60)', () => {
  for (const [f, id, max] of [['v4/guide06c_60', 'guide06c_60', 80], ['v3/guide60b', 'guide60b', 80],
    ['real_takes/aprilgrid_06', 'aprilgrid_06', 60], ['real_chess/chessboard_1107_01', 'chessboard_1107_01', 60]]) {
    for (const g of prep(read(`${DATA}${f}.json`), id).segs) assert.ok(g.short && g.short.length <= max, `${id} ${g.label}: ${g.short}`);
  }
});

test('beats: 2 sweeps left-right and up-down, 3 in-outs in the guide motion', () => {
  const by = Object.fromEntries(guide.segs.map((g) => [g.role, g]));
  assert.equal(by.lr.unit, 'Sweep');
  assert.equal(by.lr.nbeat, 2);
  assert.equal(by.ud.nbeat, 2);
  assert.equal(by.bf.unit, 'In-out');
  assert.equal(by.bf.nbeat, 3);
  assert.equal(by.circle.nbeat, 2);
});

test('chessboard detections are all or none', () => {
  const d = read(`${DATA}v3/guide60b.json`);
  const s = d.samples;
  for (let i = 0; i < s.t.length; i += 7) {
    const [w, x, y, z] = s.q_wxyz[i];
    const R = [[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]];
    const n = boardDetections(d.board, d.camera.intr8, d.camera.image_size, R, s.p_C[i]).n;
    assert.ok(n === 0 || n === 54, `t ${s.t[i]}: ${n}`);
  }
});

test('labels: chips and the Now panel share names and seconds; repeats get (2nd); the last rest says Done', () => {
  const chess = prep(read(`${DATA}real_chess/chessboard_1107_01.json`), 'chessboard_1107_01');
  const names = chess.segs.map((g) => g.name);
  assert.deepEqual(names, ['Hold still', 'Back-forth + roll', 'Left-right', 'Up-down', 'Roll in place', 'Up-down (2nd)',
    'Left-right (2nd)', 'Corners + mixed', 'Hold still']);
  assert.ok(names.every((x) => !/\s\d+$/.test(x)));
  const ag = prep(read(`${DATA}real_takes/aprilgrid_06.json`), 'aprilgrid_06');
  const a = nowState(ag, 0);
  assert.equal(a.name, 'Hold still');
  assert.equal(a.beatText, 'Count 1');     // a 1.05 s rest: same seconds as its chip
  assert.equal(a.left, secs(ag.segs[0].t1 - ag.segs[0].t0));
  assert.equal(nowState(guide, 58).beatText, 'Done');
  assert.equal(nowState(guide, 1).beatText, 'Count 3');
  assert.equal(secs(1.05), 1);
  assert.equal(secs(16.67), 17);
  assert.equal(secs(10.3), 10);
  assert.equal(secs(0.001), 1);
  assert.equal(secs(0), 0);
});

test('fill next: the largest 4-connected empty region', () => {
  // 4 x 3 grid; empty cells 0, 1, 4 (one region of 3) and 7, 11 (a region of 2)
  assert.deepEqual([...largestRegion([0, 1, 4, 7, 11], 4, 3)].sort((x, y) => x - y), [0, 1, 4]);
  assert.equal(largestRegion([], 4, 3).size, 0);
  assert.equal(largestRegion([3, 4], 4, 3).size, 1);   // 3 and 4 are on different rows, not neighbours
});

test('real-example table coverage equals the cam0 card at the end (71 % chessboard, 98 % AprilGrid)', () => {
  for (const [dir, id, want] of [['real_chess', 'chessboard_1107_01', 71], ['real_takes', 'aprilgrid_06', 98]]) {
    const ix = read(`${DATA}${dir}/index.json`).variants.find((v) => v.id === id);
    const c0 = read(`${DATA}${dir}/${id}.cams.json`).cams[0];
    const got = c0.reach.filter((r, n) => r && c0.cov100_first[n] != null).length;
    const card = Math.round((100 * got) / c0.reach.reduce((x, y) => x + y, 0));
    assert.equal(Math.round(100 * ix.cov_cam0), card);
    assert.equal(card, want);
  }
});
