// node --test site/scripts/calib-motion.test.mjs   (no packages needed)
// The calibration-motion player's pure helpers: kb4 projection, the Now panel state and the exported move beats.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  kb4Project, boardDetections, nowState, prep, segSecs, segAt, largestRegion, mergeSegs, prepCams, nearestStep,
  camCoverage, fillNext, advance,
} from '../src/scripts/calib-motion.js';

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
  const [, , cx, cy] = fx.intr8, a = (d) => [Math.sin((d * Math.PI) / 180), 0, Math.cos((d * Math.PI) / 180)];
  assert.deepEqual(kb4Project(fx.intr8, [0, 0, 1]), [cx, cy]);   // on the axis: the principal point
  assert.ok(kb4Project(fx.intr8, a(94.9)));                       // the field of view ends at 95°, behind the camera
  assert.equal(kb4Project(fx.intr8, a(95.1)), null);
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
  assert.equal(a.left, segSecs(ag.segs[0]));
  assert.equal(nowState(guide, 58).beatText, 'Done');
  assert.equal(nowState(guide, 1).beatText, 'Count 3');
  assert.equal(segSecs({ t0: 0, t1: 0.3 }), 1);          // never 0 s on a chip
  assert.equal(segSecs({ t0: 3, t1: 19.67 }), 17);
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

const ALL = [['v4/guide06c_60', 'guide06c_60'], ['v3/guide60b', 'guide60b'], ['real_takes/aprilgrid_06', 'aprilgrid_06'],
  ['real_chess/chessboard_1107_01', 'chessboard_1107_01']].map(([f, id]) => prep(read(`${DATA}${f}.json`), id));

test('mergeSegs: same label and cue back to back play as one move, beats renumbered; empty segments dropped', () => {
  const b = (t, i) => ({ t, word: 'w', i });
  const m = mergeSegs([
    { label: 'Rest', cue: '', t0: 0, t1: 0, nbeat: 1, beats: [b(0, 1)] },
    { label: 'Left-right', cue: 'Turn 30 deg, 2.0 times', t0: 0, t1: 4, nbeat: 2, beats: [b(0, 1), b(2, 2)] },
    { label: 'Left-right', cue: 'Turn 30 deg, 2.0 times', t0: 4, t1: 6, nbeat: 1, beats: [b(4, 1)] },
    { label: 'Up-down', cue: 'x', t0: 6, t1: 8 },
    { label: 'Left-right', cue: 'Turn 30 deg, 2.0 times', t0: 8, t1: 9, nbeat: 1, beats: [] },
  ]);
  assert.deepEqual(m.map((g) => [g.label, g.t0, g.t1, g.nbeat]), [['Left-right', 0, 6, 3], ['Up-down', 6, 8, 0], ['Left-right', 8, 9, 1]]);
  assert.deepEqual(m[0].beats.map((x) => x.i), [1, 2, 3]);
  assert.equal(m[0].cue, 'Turn 30°, 2 times');
  assert.deepEqual(m[1].beats, []);
});

test('moves are numbered 1..K in order, rests are not, and segments tile the take from 0 to its end', () => {
  for (const d of ALL) {
    assert.deepEqual(d.segs.filter((g) => g.k).map((g) => g.k), Array.from({ length: d.K }, (_, i) => i + 1), d.vid);
    assert.ok(d.segs.filter((g) => !g.k).every((g) => g.key === 'rest' && g.name === 'Hold still'), d.vid);
    assert.equal(d.segs[0].t0, 0);
    d.segs.slice(1).forEach((g, j) => assert.ok(Math.abs(g.t0 - d.segs[j].t1) < 1e-6, `${d.vid} gap before ${g.name}`));
    assert.ok(Math.abs(d.segs[d.segs.length - 1].t1 - d.dur) < 0.01, d.vid);
  }
});

test('segAt: a boundary belongs to the move it starts; past the end is the last step', () => {
  const g = guide.segs;
  assert.equal(segAt(g, 0), g[0]);
  assert.equal(segAt(g, g[1].t0), g[1]);
  assert.equal(segAt(g, g[1].t1), g[2]);
  assert.equal(segAt(g, g[1].t1 - 1e-9), g[1]);
  assert.equal(segAt(g, guide.dur), g[g.length - 1]);
  assert.equal(segAt(g, guide.dur + 5), g[g.length - 1]);
});

test('seconds: chips add up to the take (60 s guides), the Now panel starts at the chip and counts down to 1', () => {
  assert.deepEqual(guide.segs.map(segSecs), [3, 17, 12, 15, 10, 3]);    // the guide table: 0-3, 3-20, 20-32, 32-47, 47-57, 57-60 s
  for (const d of ALL) {
    assert.equal(d.segs.reduce((a, g) => a + segSecs(g), 0), Math.round(d.dur), d.vid);
    for (const g of d.segs) {
      assert.equal(nowState(d, g.t0 + 1e-4).left, segSecs(g), `${d.vid} ${g.name}`);
      assert.equal(nowState(d, g.t1 - 1e-3).left, 1, `${d.vid} ${g.name} end`);
    }
  }
  const lefts = [];
  for (let t = guide.segs[1].t0; t < guide.segs[1].t1; t += 0.05) lefts.push(nowState(guide, t).left);
  assert.ok(lefts.every((x, i) => !i || x <= lefts[i - 1]), 'never counts up within a move');
});

test('beats: words alternate, sweep numbers rise 1..nbeat, beats lie inside their move', () => {
  for (const d of [guide, ALL[1]]) {
    for (const g of d.segs.filter((x) => x.nbeat && x.unit !== 'Rest')) {
      const w = g.beats.map((b) => b.word).filter(Boolean);
      assert.ok(w.every((x, i) => !i || x !== w[i - 1]), `${d.vid} ${g.name}: ${w}`);
      const is = g.beats.map((b) => b.i);
      assert.ok(is.every((x, i) => !i || x >= is[i - 1]) && is[0] === 1 && is[is.length - 1] === g.nbeat, `${d.vid} ${g.name}: ${is}`);
      assert.ok(g.beats.every((b) => b.t >= g.t0 - 1e-3 && b.t < g.t1), `${d.vid} ${g.name}`);
    }
  }
  const lr = guide.segs.find((g) => g.role === 'lr');
  assert.match(lr.beats[0].word, /^going (left|right)$/);
  assert.equal(nowState(guide, lr.beats[1].t + 0.01).beatText, `Sweep ${lr.beats[1].i} of 2 · ${lr.beats[1].word}`);
});

test('sidecar: delta-coded corners decode to the exporter pairs and land inside each image', () => {
  const enc = (pts) => pts.flatMap(([u, v], q) => (q ? [u - pts[q - 1][0], v - pts[q - 1][1]] : [u, v]));
  const pts = [[250, 150], [40, 30], [41, 199], [-3, 641]];
  const [c] = prepCams({ cams: [{ uv: [enc(pts), []], reach: [1, 0, 1], T_C0_Ck: [[1, 0, 0, 0.1], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]] }] });
  assert.deepEqual([...c.uv[0]], pts.flat());
  assert.equal(c.uv[1].length, 0);
  assert.deepEqual(c.tt, [0.1, 0, 0]);
  assert.equal(c.nReach, 2);
  for (const id of ['aprilgrid_06', 'chessboard_1107_01']) {
    const dir = id.startsWith('april') ? 'real_takes' : 'real_chess';
    for (const k of prepCams(read(`${DATA}${dir}/${id}.cams.json`))) {
      const [W, H] = k.size;
      for (const f of k.uv) for (let q = 0; q < f.length; q += 2) assert.ok(f[q] >= -2 && f[q] <= W + 2 && f[q + 1] >= -2 && f[q + 1] <= H + 2, `${id} ${k.name}`);
    }
  }
});

test('nearestStep: no corners now shows a later step first, then an earlier one, within 1 s (10 steps)', () => {
  const uv = (ks, n = 30) => Array.from({ length: n }, (_, k) => (ks.includes(k) ? [1, 2] : []));
  assert.equal(nearestStep(uv([5]), 5), 5);           // corners now: itself
  assert.equal(nearestStep(uv([7, 3]), 5), 7);        // 2 later beats 2 earlier
  assert.equal(nearestStep(uv([8, 3]), 5), 3);        // earlier wins when it is closer
  assert.equal(nearestStep(uv([15]), 5), 15);         // 10 steps = 1 s: still shown
  assert.equal(nearestStep(uv([16]), 5), 5);          // 11 steps: none
  assert.equal(nearestStep(uv([0], 3), 2), 0);        // at the end of the take: only earlier steps exist
});

test('coverage: the cam0 card at the end equals the index cov_cam0 (71 % chessboard, 98 % AprilGrid); it grows', () => {
  for (const [dir, id, want] of [['real_chess', 'chessboard_1107_01', 71], ['real_takes', 'aprilgrid_06', 98]]) {
    const ix = read(`${DATA}${dir}/index.json`).variants.find((v) => v.id === id);
    const [c0] = prepCams(read(`${DATA}${dir}/${id}.cams.json`));
    const end = camCoverage(c0, ix.duration_s);
    assert.equal(Math.round(end), want);
    assert.ok(Math.abs(end / 100 - ix.cov_cam0) < 1e-4, `${id}: card ${end} vs table ${ix.cov_cam0}`);
    assert.equal(camCoverage(c0, -1), 0);
    assert.ok(camCoverage(c0, ix.duration_s / 2) <= end);
  }
});

test('fill next: nothing while nothing is seen, nothing when all is seen, the first region in raster order on a tie', () => {
  assert.equal(fillNext([0, 1, 2, 3, 4, 5], 6, 3, 2).size, 0);     // nothing seen yet: no hint
  assert.equal(fillNext([], 6, 3, 2).size, 0);                     // all seen
  assert.deepEqual([...fillNext([0, 2], 6, 3, 2)], [0]);           // two single cells: the first
  assert.deepEqual([...fillNext([2, 5, 0], 6, 3, 2)].sort(), [2, 5]);   // the bigger one, whatever the order
});

test('speed clock: at most 0.1 s per frame times the speed; the take stops at its end', () => {
  const st = { t: 0, last: 0, speed: 1, hold: 0, repeat: null };
  assert.equal(advance(st, 16, 60), false);
  assert.ok(Math.abs(st.t - 0.016) < 1e-9);
  advance(st, 5016, 60);                                // a 5 s stall (a background tab): only 0.1 s
  assert.ok(Math.abs(st.t - 0.116) < 1e-9);
  st.speed = 0.25;
  advance(st, 5056, 60);
  assert.ok(Math.abs(st.t - 0.126) < 1e-9);
  st.t = 59.95; st.speed = 1;
  assert.equal(advance(st, 5156, 60), true);
  assert.equal(st.t, 60);
});

test('repeat: a move plays to its end, holds 1 s, restarts just inside it; the last step loops too', () => {
  for (const g of [guide.segs[1], guide.segs[guide.segs.length - 1]]) {
    const st = { t: g.t1 - 0.05, last: 0, speed: 1, hold: 0, repeat: g };
    assert.equal(advance(st, 100, guide.dur), false);
    assert.ok(Math.abs(st.t - (g.t1 - 1e-3)) < 1e-9 && st.t < g.t1);
    assert.equal(segAt(guide.segs, st.t), g);            // still shown as the repeated move during the hold
    assert.equal(st.hold, 1100);
    advance(st, 600, guide.dur);
    assert.ok(Math.abs(st.t - (g.t1 - 1e-3)) < 1e-9);  // holding
    assert.equal(advance(st, 1100, guide.dur), false);
    assert.equal(st.hold, 0);
    assert.ok(Math.abs(st.t - (g.t0 + 1e-3)) < 1e-9);
    assert.equal(segAt(guide.segs, st.t), g);
  }
});
