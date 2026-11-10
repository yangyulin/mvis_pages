// node --test site/scripts/calib-motion.test.mjs   (no packages needed)
// The calibration-motion player's pure helpers: kb4 projection, the Now panel state and the exported move beats.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  kb4Project, boardDetections, nowState, prep, segSecs, segAt, largestRegion, mergeSegs, prepCams, bracket,
  lerpOutline, camFrame, cardNote,
  camCoverage, fillNext, advance, quatToR, screenStep, playMode, startLabel, getReadyText, hardestMove, enterPractice,
  exitPractice, practiceBadge, PRACTICE_SPEED, followPractice, toggleRepeat, VARIANTS,
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
  for (const [f, id, max] of [['v4/guide06c_60', 'guide06c_60', 80], ['v5/guide09_60', 'guide09_60', 80],
    ['real_takes/aprilgrid_06', 'aprilgrid_06', 60], ['real_chess/chessboard_1109_09', 'chessboard_1109_09', 60]]) {
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
  const d = read(`${DATA}v5/guide09_60.json`);
  const s = d.samples;
  for (let i = 0; i < s.t.length; i += 7) {
    const n = boardDetections(d.board, d.camera.intr8, d.camera.image_size, quatToR(s.q_wxyz[i]), s.p_C[i]).n;
    assert.ok(n === 0 || n === 54, `t ${s.t[i]}: ${n}`);
  }
});

test('labels: chips and the Now panel share names and seconds; repeats get (2nd); the last rest says Done', () => {
  const chess = prep(read(`${DATA}real_chess/chessboard_1109_09.json`), 'chessboard_1109_09');
  const names = chess.segs.map((g) => g.name);
  assert.deepEqual(names, ['Hold still', 'Left-right', 'Up-down', 'Back-forth + roll', 'Loop', 'Hold still']);
  assert.ok(names.every((x) => !/\s\d+$/.test(x)));
  // a real take that repeats a move (labels "Left-right 2", as the export writes them) gets "(2nd)"
  const rep = read(`${DATA}real_chess/chessboard_1109_09.json`);
  rep.segments[1].label = 'Left-right 1'; rep.segments[2].label = 'Left-right 2'; rep.segments[2].role = 'lr2';
  assert.deepEqual(prep(rep, 'chessboard_1109_09').segs.slice(1, 3).map((g) => g.name), ['Left-right', 'Left-right (2nd)']);
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

const ALL = [['v4/guide06c_60', 'guide06c_60'], ['v5/guide09_60', 'guide09_60'], ['real_takes/aprilgrid_06', 'aprilgrid_06'],
  ['real_chess/chessboard_1109_09', 'chessboard_1109_09']].map(([f, id]) => prep(read(`${DATA}${f}.json`), id));

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
  for (const id of ['aprilgrid_06', 'chessboard_1109_09']) {
    const dir = id.startsWith('april') ? 'real_takes' : 'real_chess';
    for (const k of prepCams(read(`${DATA}${dir}/${id}.cams.json`))) {
      const [W, H] = k.size;
      for (const f of k.uv) for (let q = 0; q < f.length; q += 2) assert.ok(f[q] >= -2 && f[q] <= W + 2 && f[q + 1] >= -2 && f[q + 1] <= H + 2, `${id} ${k.name}`);
    }
  }
});

test('sidecar: the frame period comes from the sidecar hz (one rule, the exporter one), not a second median', () => {
  const cam = { uv: [[], [], []], reach: [1], T_C0_Ck: [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]] };
  const [c] = prepCams({ hz: 20, t: [0, 0.1, 0.2], cams: [cam] });
  assert.equal(c.period, 0.05);
});

test('sidecar: an old v1 file (no t, cached across a deploy) gets frame times from its hz, so cards still move', () => {
  const cam = { uv: [[], [], []], reach: [1], T_C0_Ck: [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]] };
  const [c] = prepCams({ hz: 10, cams: [cam] });
  assert.deepEqual(c.t, [0, 0.1, 0.2]);
  assert.equal(bracket(c.t, 0.15).k0, 1);
});

test('coverage: a cell first seen at 0.15 s does not count at 0.11 s (no 0.05 s lead from the old 10 Hz slack)', () => {
  const c = { cov100_first: [0.15], reach: [1], nReach: 1 };
  assert.equal(camCoverage(c, 0.11), 0);
  assert.equal(camCoverage(c, 0.15), 100);
});

const REAL = [['real_takes', 'aprilgrid_06'], ['real_chess', 'chessboard_1109_09']];
const realCams = Object.fromEntries(REAL.map(([dir, id]) => [id, prepCams(read(`${DATA}${dir}/${id}.cams.json`))]));
const realDur = Object.fromEntries(REAL.map(([dir, id]) => [id, read(`${DATA}${dir}/index.json`).variants.find((v) => v.id === id).duration_s]));

test('sidecar: every frame of the views file (600 per take, with times), an outline in every frame of every camera', () => {
  for (const [id, cams] of Object.entries(realCams)) {
    for (const c of cams) {
      assert.equal(c.t.length, 600);
      assert.equal(c.uv.length, 600);
      assert.ok(c.t.every((x, k) => !k || x > c.t[k - 1]), `${id}: times rise`);
      assert.ok(c.outline.every((o) => o && o.length === 4), `${id} ${c.name}: outline in every frame`);
    }
    assert.ok(Math.abs(cams[0].t.at(-1) - realDur[id]) < 0.1, `${id}: frames span the take`);
  }
  assert.ok(Math.abs(realCams.aprilgrid_06[0].period - 0.05) < 1e-9);        // 20 Hz
  assert.ok(Math.abs(realCams.chessboard_1109_09[0].period - 0.1) < 1e-9);   // 10 Hz
});

test('bracket and outline interpolation: the midpoint between two frames is the mean of their outlines', () => {
  const T = [0, 0.1, 0.3];
  assert.deepEqual(bracket(T, -1), { k0: 0, k1: 0, a: 0 });
  assert.deepEqual(bracket(T, 0.1), { k0: 1, k1: 2, a: 0 });
  assert.ok(Math.abs(bracket(T, 0.2).a - 0.5) < 1e-9);
  assert.deepEqual(bracket(T, 5), { k0: 2, k1: 2, a: 0 });
  const o0 = [[0, 0], [10, 0], [10, 10], [0, 10]], o1 = [[4, 2], [14, 2], [14, 12], [4, 12]];
  assert.deepEqual(lerpOutline(o0, o1, 0.5), [[2, 1], [12, 1], [12, 11], [2, 11]]);
  assert.deepEqual(lerpOutline(o0, null, 0.4), o0);                 // out of view on one side: the nearer frame
  assert.equal(lerpOutline(o0, null, 0.6), null);
  for (const c of realCams.aprilgrid_06) {                          // on the real take, at each frame midpoint
    for (let k = 0; k + 1 < c.t.length; k += 37) {
      const o = camFrame(c, (c.t[k] + c.t[k + 1]) / 2).outline;
      o.forEach(([u, v], j) => {
        assert.ok(Math.abs(u - (c.outline[k][j][0] + c.outline[k + 1][j][0]) / 2) < 1e-6);
        assert.ok(Math.abs(v - (c.outline[k][j][1] + c.outline[k + 1][j][1]) / 2) < 1e-6);
      });
    }
  }
});

const mkCam = (t, uv, period) => ({ t, period, uv: uv.map((f) => new Int16Array(f)), outline: t.map(() => null),
  n_so_far: uv.map((_, k) => uv.slice(0, k + 1).reduce((s, f) => s + f.length / 2, 0)), dist_cm: t.map(() => 1), off_deg: t.map(() => 1) });

test('corners: a normal gap (up to two periods) shows the nearer frame, or the other when the nearer has none', () => {
  const c = mkCam([0, 0.1, 0.2, 0.3], [[1, 2], [3, 4, 5, 6], [], [7, 8]], 0.1);
  assert.equal(camFrame(c, 0.04).n, 1);
  assert.equal(camFrame(c, 0.06).n, 2);
  assert.equal(camFrame(c, 0.11).n, 2);
  assert.equal(camFrame(c, 0.19).n, 2);          // nearer frame (0.2) has none: the other one
  assert.equal(camFrame(c, 0.2).n, 1);           // on the empty frame itself: the next one (it brackets 0.2-0.3)
  assert.equal(camFrame(c, 0.26).n, 1);
  assert.equal(camFrame(c, 0.34).n, 1);          // after the last frame, within half a period
  assert.equal(camFrame(c, 0.36).n, 0);          // beyond: none
  assert.equal(camFrame(c, -0.04).n, 1);
  assert.equal(camFrame(c, -0.06).n, 0);
  const e = mkCam([0, 0.1, 0.2], [[], [], [1, 2]], 0.1);
  assert.equal(camFrame(e, 0.05).n, 0);          // both frames of the gap without corners: none
});

test('corners: uneven 0.05 / 0.10 s frames (20 Hz take) show corners on every 1/30 s draw, no blink', () => {
  const t = [0];
  for (let k = 1; k < 40; k++) t.push(+(t[k - 1] + (k % 3 ? 0.05 : 0.1)).toFixed(3));
  const c = mkCam(t, t.map(() => [1, 2, 3, 4]), 0.05);
  for (let i = 0; i / 30 <= t.at(-1); i++) assert.equal(camFrame(c, i / 30).n, 2, `t ${(i / 30).toFixed(3)}`);
});

test('corners: a real gap (over two periods) shows none away from its frames, the nearest frame within half a period', () => {
  const c = mkCam([0, 0.1, 1.1, 1.2], [[1, 2], [3, 4, 5, 6], [7, 8], [9, 10]], 0.1);
  assert.equal(camFrame(c, 0.14).n, 2);
  assert.equal(camFrame(c, 0.16).n, 0);
  assert.equal(camFrame(c, 0.6).n, 0);
  assert.equal(camFrame(c, 0.6).soFar, 3);       // so far: frames up to now
  assert.equal(camFrame(c, 1.06).n, 1);
  assert.equal(camFrame(c, 1.04).n, 0);
});

test('corners: whole takes, every 1/30 s in a normal gap with corners on both sides shows corners (0 blinks)', () => {
  let blinks = 0, samples = 0, realGap = 0, realGapNone = 0;
  for (const [, id] of REAL) {
    for (const c of realCams[id]) {
      for (let i = 0; i / 30 <= realDur[id]; i++) {
        const t = i / 30, { k0, k1 } = bracket(c.t, t);
        if (k0 === k1 || !c.uv[k0].length || !c.uv[k1].length) continue;
        const none = /^no corners/.test(cardNote({ ...camFrame(c, t), pct: 0 }));
        if (c.t[k1] - c.t[k0] <= 2 * c.period + 1e-6) { samples++; if (none) blinks++; } else { realGap++; if (none) realGapNone++; }
      }
    }
  }
  assert.ok(samples > 5000, `${samples}`);
  assert.equal(blinks, 0);
  assert.equal(realGapNone, realGap, 'a real gap (longer than 2 frames) shows none');   // synthetic gaps: test above
});

test('corners: a real cam2 frame without corners between two others without corners: none, outline kept', () => {
  const cam2 = realCams.aprilgrid_06[2];
  const empty = cam2.t.findIndex((x, k) => k > 0 && !cam2.uv[k - 1].length && !cam2.uv[k].length && !cam2.uv[k + 1]?.length);
  assert.ok(empty > 0);
  const f = camFrame(cam2, cam2.t[empty]);
  assert.equal(f.n, 0);
  assert.ok(f.outline, 'cam2 keeps its outline in a frame without corners');
  assert.match(cardNote({ ...f, pct: 54 }), /^no corners this frame · 54 % of the image · /);
});

// The card note at time t of every camera; every 1/30 s (a drawn frame at 1x) plus every frame time of the take.
function* notesOf(id) {
  for (const c of realCams[id]) {
    const ts = [...c.t];
    for (let t = 0; t <= realDur[id]; t += 1 / 30) ts.push(t);
    for (const t of ts) yield [c, t, cardNote({ ...camFrame(c, t), pct: camCoverage(c, t) })];
  }
}

test('card note: one line of fixed form for every frame of both takes, at most 64 characters (no wrap, no fallback)', () => {
  const form = /^(\d+ corners|no corners this frame) · \d{1,3} % of the image · \d{1,3}(,\d{3})* so far$/;
  let longest = '';
  for (const [id] of REAL.map(([, x]) => [x])) {
    for (const [c, t, note] of notesOf(id)) {
      assert.match(note, form, `${id} ${c.name} t ${t}`);
      if (note.length > longest.length) longest = note;
    }
  }
  assert.ok(longest.length <= 64, longest);
  assert.ok(!/nearest/.test(longest));
});

test('outline at 1x: a drawn frame (1/30 s) moves it no further than the frames around it move in 1/30 s', () => {
  // interpolation, no steps: the jump between two drawn frames is bounded by the fastest frame interval they span
  for (const [, id] of REAL) {
    for (const c of realCams[id]) {
      const span = (k) => Math.max(...c.outline[k + 1].map(([u, v], j) => Math.hypot(u - c.outline[k][j][0], v - c.outline[k][j][1])));
      let prev = null, tp = 0;
      for (let t = 0; t <= realDur[id]; t += 1 / 30) {
        const o = camFrame(c, t).outline;
        if (prev) {
          const jump = Math.max(...o.map(([u, v], j) => Math.hypot(u - prev[j][0], v - prev[j][1])));
          let speed = 0;
          for (let k = bracket(c.t, tp).k0; k <= bracket(c.t, t).k0 && k + 1 < c.t.length; k++) speed = Math.max(speed, span(k) / (c.t[k + 1] - c.t[k]));
          assert.ok(jump <= speed * (t - tp) + 1e-6, `${id} ${c.name} t ${t.toFixed(3)}: ${jump.toFixed(1)} px`);
        }
        prev = o; tp = t;
      }
    }
  }
});

test('coverage: the cam0 card at the end equals the index cov_cam0 (81 % chessboard, 98 % AprilGrid); it grows', () => {
  for (const [dir, id, want] of [['real_chess', 'chessboard_1109_09', 81], ['real_takes', 'aprilgrid_06', 98]]) {
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

test('repeat switched off during the hold (another example loaded): the clock resumes in place, no crash', () => {
  const st = { t: 12, last: 0, speed: 1, hold: 500, repeat: null };
  assert.equal(advance(st, 600, guide.dur), false);
  assert.equal(st.hold, 0);
  assert.equal(st.t, 12);
  advance(st, 616, guide.dur);
  assert.ok(Math.abs(st.t - 12.016) < 1e-9);
});

const chess = prep(read(`${DATA}v5/guide09_60.json`), 'guide09_60');
const realAG = prep(read(`${DATA}real_takes/aprilgrid_06.json`), 'aprilgrid_06');
const realCB = prep(read(`${DATA}real_chess/chessboard_1109_09.json`), 'chessboard_1109_09');

test('start / end screen: start until the first play or seek, end only after playing to the end, start again on load', () => {
  let s = 'start';
  assert.equal(screenStep(s, 'end'), 'start');        // nothing played yet: no end screen
  s = screenStep(s, 'play'); assert.equal(s, 'none');
  assert.equal(screenStep('start', 'seek'), 'none');  // a chip, step or the scrubber also dismisses it
  s = screenStep(s, 'end'); assert.equal(s, 'end');
  assert.equal(screenStep(s, 'seek'), 'none');
  assert.equal(screenStep(s, 'play'), 'none');        // Watch again
  for (const x of ['start', 'none', 'end']) assert.equal(screenStep(x, 'load'), 'start');
});

test('primary button: Play, Pause while playing or counting, Again at the end', () => {
  assert.equal(playMode({ playing: false, counting: 0, t: 0, dur: 60 }), 'play');
  assert.equal(playMode({ playing: true, counting: 0, t: 10, dur: 60 }), 'pause');
  assert.equal(playMode({ playing: false, counting: 7, t: 0, dur: 60 }), 'pause');
  assert.equal(playMode({ playing: false, counting: 0, t: 60, dur: 60 }), 'again');
  assert.equal(playMode({ playing: false, counting: 0, t: 59.9, dur: 60 }), 'play');
});

test('start labels name the board and say the length: 60 s guides, 41 s and 51 s real takes', () => {
  assert.equal(startLabel(guide, false), 'Start the AprilGrid motion · 60 s');
  assert.equal(startLabel(chess, false), 'Start the chessboard motion · 60 s');
  assert.equal(startLabel(realAG, true), 'Play the real recording · 41 s');
  assert.equal(startLabel(realCB, true), 'Play the real recording · 51 s');
});

test('guide chips are named after their board', () => {
  assert.equal(VARIANTS.guide06c_60.label, 'AprilGrid');
  assert.equal(VARIANTS.guide09_60.label, 'Chessboard');
});

test('get-ready line: the start distance to the board plane, as in the setup line and the first cue', () => {
  assert.equal(getReadyText(guide), 'Get in position: board 42 cm ahead, face-on');
  assert.equal(getReadyText(chess), 'Get in position: board 47 cm ahead, face-on');
  // the first cue of each guide says the same distance
  for (const d of [guide, chess]) assert.ok(d.segs[0].short.includes(getReadyText(d).match(/\d+ cm/)[0]), d.segs[0].short);
});

test('hardest move: a move (never a rest) with the fastest peak; loop in the AprilGrid guide, left-right in the chessboard', () => {
  assert.equal(hardestMove(guide).name, 'Loop + roll');
  assert.equal(hardestMove(chess).name, 'Left-right');
  for (const d of [guide, chess, realAG, realCB]) assert.ok(hardestMove(d).k);
  assert.equal(hardestMove({ ...guide, segs: guide.segs.filter((g) => !g.k) }), null);
});

test('practise: jumps into the move at 0.5x, repeats it, stays inside it; exit restores speed and repeat', () => {
  const g = guide.segs[2];
  const st = { t: 33, speed: 1, repeat: null, hold: 0, last: 0, practice: null, saved: null };
  assert.equal(enterPractice(st, guide.segs, guide.segs[0]), false);   // a rest: refused, nothing changed
  assert.equal(enterPractice(st, guide.segs, chess.segs[2]), false);   // a move of another take: refused
  assert.equal(enterPractice(st, guide.segs, null), false);
  assert.deepEqual([st.t, st.speed, st.repeat, st.practice], [33, 1, null, null]);
  assert.equal(enterPractice(st, guide.segs, g), true);
  assert.equal(st.speed, PRACTICE_SPEED);
  assert.equal(st.repeat, g);
  assert.ok(st.t > g.t0 && st.t < g.t0 + 0.01);
  assert.equal(practiceBadge(st), 'Practising: Up-down · 0.5× · repeating');
  // 40 s of frames at 60 Hz: the clock never leaves the move
  for (let now = 16.7; now < 40000; now += 16.7) {
    advance(st, now, guide.dur);
    assert.ok(st.t >= g.t0 && st.t <= g.t1, `t ${st.t}`);
  }
  // switching to another move keeps what was set before the first one
  enterPractice(st, guide.segs, guide.segs[3]);
  assert.equal(st.practice, guide.segs[3]);
  assert.equal(exitPractice(st), true);
  assert.deepEqual([st.speed, st.repeat, st.practice, practiceBadge(st)], [1, null, null, '']);
  assert.equal(exitPractice(st), false);                                // not practising: nothing to undo
  // a repeat and 0.25x set before practice come back after it
  const st2 = { t: 5, speed: 0.25, repeat: guide.segs[1], hold: 0, practice: null };
  enterPractice(st2, guide.segs, guide.segs[4]);
  exitPractice(st2);
  assert.deepEqual([st2.speed, st2.repeat], [0.25, guide.segs[1]]);
});

test('practise follows a chip or step to the next move, ends on a rest; repeat off during practise stays off', () => {
  const [m1, m2, m3] = guide.segs.filter((g) => g.k), rest = guide.segs.find((g) => !g.k);
  const st = { t: m1.t0 + 0.1, speed: 1, repeat: m1, hold: 0, practice: null, saved: null };
  enterPractice(st, guide.segs, m2);
  assert.equal(followPractice(st, m2), false);                          // in the practised move: nothing changes
  assert.equal(followPractice(st, m3), false);                          // a step to the next move: practise follows
  assert.deepEqual([st.practice, st.repeat, st.speed], [m3, m3, PRACTICE_SPEED]);
  assert.equal(followPractice(st, rest), true);                         // a rest: practise ends, speed back
  assert.deepEqual([st.practice, st.speed], [null, 1]);
  // Repeat on at move 1, practise move 2, repeat off: no repeat, also on the next frame
  const s2 = { t: m1.t0 + 0.1, speed: 1, repeat: m1, hold: 0, practice: null, saved: null };
  enterPractice(s2, guide.segs, m2);
  toggleRepeat(s2, m2);
  followPractice(s2, m2);
  assert.deepEqual([s2.practice, s2.repeat, s2.speed], [null, null, 1]);
  // outside practise the toggle switches the move the clock is in on and off
  toggleRepeat(s2, m3);
  assert.equal(s2.repeat, m3);
  toggleRepeat(s2, m3);
  assert.equal(s2.repeat, null);
});
