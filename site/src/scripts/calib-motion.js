// Calibration-motion guide: a player made to be followed. A Now panel (which move, what to do, how long is left, what
// comes next), a 3D view seen from behind the operator, camera cards (what the camera detects, coverage so far), a
// transport with move steps, repeat and speed, and the sensor traces folded away.
// Data (public/data/calib-motion/, schemas in site/scripts/export_calib_motion.py):
//   v4/guide06c_60.json          AprilGrid guide motion (calib-motion-demo/anim v1, segments with beats)
//   v3/guide60b.json             chessboard version
//   real_takes/aprilgrid_06.json the AprilGrid example (real take 06 of 2026-11-08), + .cams.json (camera cards)
//   real_chess/chessboard_1107_01.json  the chessboard example (real take 01 of 2026-11-07), + .cams.json
//   <set>/index.json (length, coverage) and <set>/twin_verdicts.json (passed) for the chip dots and the table.
// The camera cards draw the board and its detected corners, never a camera image. In the guides they are computed here
// from the pose (kb4 projection, detection rule of the twin); in the real examples they come from the MVIS-detected
// corners in the .cams.json sidecar, loaded when that example is first opened.
// Frames in the anim JSON: board frame B (x along the board rows, to the image LEFT for a face-on camera, i.e. the
// operator's left; y down = gravity; z toward the camera). R_BC = quaternion [w, x, y, z]; p_C = camera centre in B.
// The 3D view draws in D = diag(-1, -1, 1) B: x to the operator's right, y up, z toward the operator.

export const VARIANTS = {
  guide06c_60: { set: 'v4', label: 'Guide motion, 60 s', why: 'Four moves at a comfortable hand pace, built from the AprilGrid example.' },
  guide60b: { set: 'v3', label: 'Chessboard version, 60 s', why: 'Smaller swings so the whole chessboard stays in view, and a corner square instead of the loop.' },
  aprilgrid_06: { set: 'real', label: 'AprilGrid example', why: 'Our 41 s hand-held take in front of a monitor AprilGrid, the take the guide motion is built from.',
    diff: 'The same four moves in the same order, but in 41 s: about twice the guide’s speed (up to 0.75 m/s and 5 rad/s) and closer to the board (16 cm).' },
  chessboard_1107_01: { set: 'realc', label: 'Chessboard example', why: 'Our 61 s hand-held take in front of a monitor chessboard, the whole board kept in view.',
    diff: 'A different order (in-out first, a roll in place, then repeats and a mixed corner block), farther from the board (43–73 cm), so cam0 covers less of the image (71 %).' },
};
const SETS = {
  v4: { dir: 'v4/' }, v3: { dir: 'v3/' }, real: { dir: 'real_takes/', cams: true }, realc: { dir: 'real_chess/', cams: true },
};
const MODES = { main: ['guide06c_60', 'guide60b'], real: ['aprilgrid_06', 'chessboard_1107_01'] };
// One short cue per move (at most 80 characters; real takes: what was done, at most 60), by variant and segment role.
export const SHORT = {
  guide06c_60: {
    rest0: 'Hold still, face-on, about 42 cm away. Count 3.',
    lr: 'Swing left–right round the board, 2×; turn past it at each end.',
    ud: 'Swing up–down, 2×; tip past the board at the top and bottom.',
    bf: 'In to 22 cm, out to 52 cm, 3×, rolling like a steering wheel.',
    circle: 'Circle parallel to the board, about 40 cm across, 2×, rolling a little.',
    rest1: 'Hold still. Count 3. Done.',
  },
  guide60b: {
    rest0: 'Hold still, face-on, about 46 cm away. Count 3.',
    lr: 'Swing left–right, 2×; turn past the board; keep the whole board in view.',
    ud: 'Swing up–down, 2×; tip past the board; keep the whole board in view.',
    bf: 'In to 28 cm, out to 80 cm, 3×, rolling; board off-centre.',
    mix: 'Turn in place round a slow square so the board visits each picture corner.',
    rest1: 'Hold still. Count 3. Done.',
  },
  aprilgrid_06: {
    rest0: 'Held still, face-on.', lr: 'Swung left–right round the board, turning past it.',
    ud: 'Swung up–down, tipping past the board.', bf: 'In and out 4×, rolling as it went.',
    circle: 'Circled parallel to the board, 3×.', rest1: 'Held still. Done.',
  },
  chessboard_1107_01: {
    rest0: 'Held still, face-on.', bf1: 'In and out, rolling, the whole board in view.',
    lr1: 'Swung left–right, the whole board in view.', ud1: 'Swung up–down, tipping past the board.',
    roll1: 'Rolled in place, both ways.', ud2: 'Up–down again, shorter.', lr2: 'A short left–right.',
    mix: 'Turned the board into each picture corner, mixed moves.', rest1: 'Held still. Done.',
  },
};
// Path colours per move (CSS --cm-s-<key>): roll in place counts as back-forth, a corner square or mixed block as the loop.
const SEG_KEYS = ['lr', 'ud', 'bf', 'loop', 'rest'];
const SEG_OF_ROLE = { lr: 'lr', ud: 'ud', bf: 'bf', roll: 'bf', circle: 'loop', mix: 'loop', rest: 'rest' };
const segKey = (g) => SEG_OF_ROLE[String(g.role || g.name || '').replace(/\d+$/, '')] || 'rest';
const SPEEDS = [0.25, 0.5, 1];
const FILL = 0.8;
const FOV = (95 * Math.PI) / 180, INC = Math.cos((75 * Math.PI) / 180);

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private window */ } },
};

// ---------- small math ----------
export function quatToR([w, x, y, z]) {
  return [
    [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
    [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
    [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
  ];
}
const mv = (R, v) => [0, 1, 2].map((i) => R[i][0] * v[0] + R[i][1] * v[1] + R[i][2] * v[2]);
const mtv = (R, v) => [0, 1, 2].map((i) => R[0][i] * v[0] + R[1][i] * v[1] + R[2][i] * v[2]);
const mm = (A, B) => [0, 1, 2].map((i) => [0, 1, 2].map((j) => A[i][0] * B[0][j] + A[i][1] * B[1][j] + A[i][2] * B[2][j]));
const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const scl = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a) => scl(a, 1 / (Math.hypot(...a) || 1));
const toD = (p) => [-p[0], -p[1], p[2]];
const DM = [[-1, 0, 0], [0, -1, 0], [0, 0, 1]];

// Kannala-Brandt (kb4) projection of a point in camera axes; null beyond the 95° field of view.
export function kb4Project(intr8, X) {
  const [fx, fy, cx, cy, k1, k2, k3, k4] = intr8;
  const r = Math.hypot(X[0], X[1]);
  const th = Math.atan2(r, X[2]);
  if (th > FOV) return null;
  if (r < 1e-12) return [cx, cy];
  const t2 = th * th;
  const dd = th * (1 + t2 * (k1 + t2 * (k2 + t2 * (k3 + t2 * k4))));
  return [(fx * dd * X[0]) / r + cx, (fy * dd * X[1]) / r + cy];
}

// The board corners a camera at (R_BC, p_C) sees, with the twin's detection rule: an AprilGrid tag counts when its 4
// corners are in the image and seen at under 75° incidence; a chessboard counts only whole.
export function boardDetections(board, intr8, size, R_BC, p_C) {
  const [W, H] = size;
  const pts = board.points;
  const uv = [], ok = [];
  for (const X of pts) {
    const ray = sub(p_C, X);
    const q = kb4Project(intr8, mtv(R_BC, sub(X, p_C)));
    const inc = ray[2] / (Math.hypot(...ray) || 1);
    uv.push(q);
    ok.push(!!q && q[0] >= 0 && q[0] < W && q[1] >= 0 && q[1] < H && inc > INC);
  }
  const det = new Array(pts.length).fill(false);
  if (board.type === 'chessboard') {
    if (ok.every(Boolean)) det.fill(true);
  } else {
    for (let k = 0; k + 3 < pts.length; k += 4) if (ok[k] && ok[k + 1] && ok[k + 2] && ok[k + 3]) det.fill(true, k, k + 4);
  }
  return { uv, det, n: det.filter(Boolean).length };
}

export const segAt = (segs, t) => segs.find((g) => t >= g.t0 && t < g.t1) || segs[segs.length - 1];
export function beatAt(g, t) {
  let b = null;
  for (const x of g.beats || []) if (x.t <= t + 1e-6) b = x;
  return b;
}
// A move's length in whole seconds (its chip, "Count N", the Now panel at its start): the difference of its rounded
// boundaries, so the chips add up to the take's rounded length and match the guide table (3–20 s is 17 s). The Now
// panel's "s left" and "Next in" count down to the rounded end, from this value to 1.
export const segSecs = (g) => Math.max(1, Math.round(g.t1) - Math.round(g.t0));
const ORD = ['', '', '2nd', '3rd', '4th', '5th'];
const cut = (s, n) => (s.length <= n ? s : `${s.slice(0, n - 1).replace(/[\s,;–-]+\S*$/, '')}…`);

// What the Now panel shows at time t.
export function nowState(d, t) {
  const g = segAt(d.segs, t);
  const j = d.segs.indexOf(g);
  const nx = d.segs[j + 1] || null;
  const b = beatAt(g, t);
  let beatText = '';
  if (g.unit === 'Rest') beatText = j === d.segs.length - 1 ? 'Done' : `Count ${segSecs(g)}`;
  else if (b && g.nbeat > 0) {
    const of = `${g.unit} ${b.i} of ${g.nbeat}`;
    beatText = b.word ? `${of} · ${b.word}` : of;
  }
  const span = Math.max(1e-6, g.t1 - g.t0);
  return {
    j, k: g.k, K: d.K, name: g.name, short: g.short, cue: g.cue, key: g.key,
    left: t >= g.t1 - 1e-6 ? 0 : Math.min(segSecs(g), Math.max(1, Math.round(Math.round(g.t1) - t))), until: g.t1 - t,
    beatText, frac: Math.max(0, Math.min(1, (t - g.t0) / span)),
    ticks: (g.beats || []).filter((x) => x.t > g.t0 + 1e-3).map((x) => (x.t - g.t0) / span),
    next: nx ? { k: nx.k, name: nx.name, short: nx.short, key: nx.key } : null,
  };
}

// Adjacent segments with the same label and cue play as one move; moves are numbered, rests are not.
export function mergeSegs(segs) {
  const out = [];
  for (const g of segs) {
    if (!(g.t1 - g.t0 > 1e-6)) continue;
    const last = out[out.length - 1];
    const cue = (g.cue || '').replace(/(\d) deg\b/g, '$1°').replace(/\b(\d+)\.0 times\b/g, '$1 times');
    if (last && last.label === g.label && last.cue === cue && Math.abs(last.t1 - g.t0) < 1e-6) {
      last.t1 = g.t1;
      last.beats = [...last.beats, ...(g.beats || []).map((b) => ({ ...b, i: b.i + last.nbeat }))];
      last.nbeat += g.nbeat || 0;
    } else out.push({ ...g, beats: g.beats || [], nbeat: g.nbeat || 0, cue });
  }
  return out;
}

function boardTiles(b) {
  if (b.type === 'chessboard' && b.spec) {
    const { cols, rows, square: q } = b.spec;
    const tiles = [];
    for (let j = -1; j < rows; j++) {
      for (let i = -1; i < cols; i++) {
        if ((((i + j) % 2) + 2) % 2) continue;
        tiles.push([[i * q, j * q, 0], [(i + 1) * q, j * q, 0], [(i + 1) * q, (j + 1) * q, 0], [i * q, (j + 1) * q, 0]].map(toD));
      }
    }
    return tiles;
  }
  return Array.from({ length: b.points.length / 4 }, (_, k) => b.points.slice(4 * k, 4 * k + 4).map(toD));
}

// Everything the player needs from one anim file (pure: also used by the tests).
export function prep(d, vid = d.variant) {
  const s = d.samples, n = s.t.length, hz = d.hz;
  const fine = d.coverage.fine_grid, metric = d.coverage.metric_grid;
  const first = new Float32Array(fine[0] * fine[1]).fill(Infinity);
  const first100 = new Float32Array(metric[0] * metric[1]).fill(Infinity);
  for (let i = 0; i < n; i++) {
    for (const c of s.cov_new[i] || []) if (first[c] === Infinity) first[c] = s.t[i];
    for (const c of s.cov100_new[i] || []) if (first100[c] === Infinity) first100[c] = s.t[i];
  }
  const T = d.camera.T_CtoI;
  const p_I_C = scl(mv(d.camera.R_CI, [T[0][3], T[1][3], T[2][3]]), -1);
  const segs = mergeSegs(d.segments);
  const short = SHORT[vid] || {};
  let K = 0;
  const times = {};
  for (const g of segs) {
    g.key = segKey(g);
    g.k = g.key === 'rest' ? null : ++K;
    // "1  Left-right" -> "Left-right"; "Left-right 2" (a repeat in a real take) -> "Left-right (2nd)"; rests "Hold still"
    const base = g.label.replace(/\s+/g, ' ').replace(/^\d+ /, '').replace(/ \d+$/, '').trim();
    times[base] = (times[base] || 0) + 1;
    g.name = !g.k ? 'Hold still' : times[base] > 1 ? `${base} (${ORD[times[base]] || `${times[base]}th`})` : base;
    g.short = short[g.role] || short[String(g.role).replace(/\d+$/, '')] || g.cue.split('. ')[0] || '';
  }
  const path = s.p_C.map(toD);
  const key = new Array(n).fill('rest');
  for (const g of segs) for (let i = Math.max(0, Math.round(g.t0 * hz)); i < Math.min(n, Math.round(g.t1 * hz) + 1); i++) key[i] = g.key;
  // one path run per move (sample range, one sample of overlap so the runs join)
  const runs = segs.map((g) => ({ g, key: g.key, k0: Math.max(0, Math.round(g.t0 * hz) - 1), k1: Math.min(n - 1, Math.round(g.t1 * hz)) }));
  const rng = (k) => { let m = 0; for (const v of s[k]) for (const x of v) m = Math.max(m, Math.abs(x)); return m * 1.05 || 1; };
  return {
    raw: d, vid, s, n, hz, dur: d.duration_s, first, first100, reach: d.coverage.metric_reach,
    nReach: d.coverage.metric_reach.reduce((a, b) => a + (b ? 1 : 0), 0), R_CI: d.camera.R_CI, p_I_C,
    gmax: rng('gyro'), amax: rng('accel'), segs, K, path, key, runs, tags: boardTiles(d.board),
    outline: d.board.outline.map(toD), center: toD(d.board.center), cams: null, soFar: null,
  };
}

// Guide cards: corners detected per camera frame (20 Hz) summed up to each sample.
function guideSoFar(d) {
  const raw = d.raw, hz = raw.camera.cam_hz || 20, soFar = new Int32Array(d.n);
  let acc = 0, j = 0;
  for (let i = 0; i < d.n; i++) {
    while (j / hz <= d.s.t[i] + 1e-9) {
      const k = Math.min(d.n - 1, Math.round((j / hz) * d.hz));
      acc += boardDetections(raw.board, raw.camera.intr8, raw.camera.image_size, quatToR(d.s.q_wxyz[k]), d.s.p_C[k]).n;
      j++;
    }
    soFar[i] = acc;
  }
  return soFar;
}

// Real-example cards: decode the sidecar (delta-coded corners) once.
export function prepCams(side) {
  return side.cams.map((c) => {
    const uv = c.uv.map((f) => {
      const a = new Int16Array(f.length);
      for (let q = 0; q < f.length; q++) a[q] = q < 2 ? f[q] : a[q - 2] + f[q];
      return a;
    });
    const R = c.T_C0_Ck.slice(0, 3).map((r) => r.slice(0, 3));
    const tt = c.T_C0_Ck.slice(0, 3).map((r) => r[3]);
    return { ...c, uv, R, tt, nReach: c.reach.reduce((a, b) => a + b, 0) };
  });
}

// No corners at sidecar step k (the first frame of a take, a blink): the nearest step with corners within 1 s (10
// steps), later first, so a card never starts empty; k itself when none.
export function nearestStep(uv, k) {
  let ks = k;
  for (let j = 1; !uv[ks].length && j <= 10; j++) {
    if (k + j < uv.length && uv[k + j].length) ks = k + j;
    else if (k - j >= 0 && uv[k - j].length) ks = k - j;
  }
  return ks;
}

// Share (%) of a sidecar camera's reachable 100 px cells with a detected corner by time t; at the end it is the
// index's cov_cam0 for cam0.
export function camCoverage(c, t) {
  let got = 0;
  c.cov100_first.forEach((t0, n) => { if (t0 != null && t0 <= t + 0.05 && c.reach[n]) got++; });
  return (100 * got) / Math.max(1, c.nReach);
}

// "Fill next": the largest connected still-empty region, once part of the image is seen (nothing while nothing is).
export const fillNext = (empty, nReach, gx, gy) => (empty.length < nReach ? largestRegion(empty, gx, gy) : new Set());

// The play clock for one animation frame at `now` (ms): at most 0.1 s of take time per frame times the speed (a tab
// in the background does not jump); a repeated move holds 1 s at its end, then restarts. True when the take ended.
export function advance(st, now, dur) {
  const dt = Math.min(0.1, (now - st.last) / 1000);
  st.last = now;
  if (st.hold) {
    if (now >= st.hold) { st.hold = 0; if (st.repeat) st.t = st.repeat.t0 + 1e-3; }
    return false;
  }
  st.t += dt * st.speed;
  if (st.repeat && st.t >= st.repeat.t1) { st.t = Math.min(dur, st.repeat.t1) - 1e-3; st.hold = now + 1000; return false; }
  if (st.t >= dur) { st.t = dur; return true; }
  return false;
}

// ---------- start screen, practise mode, end screen (pure: also used by the tests) ----------
// The overlay on the 3D view: 'start' before the first play (back after loading another example), 'none' while the
// take plays or is scrubbed, 'end' once it played to its end. Events: 'play', 'seek', 'end', 'load'.
export function screenStep(screen, ev) {
  if (ev === 'load') return 'start';
  if (ev === 'end') return screen === 'start' ? 'start' : 'end';
  return 'none';   // play or seek leaves the start and end screens
}
// What the primary button offers: play, pause (also during the 3-2-1), or again at the end of the take.
export const playMode = ({ playing, counting, t, dur }) => (playing || counting ? 'pause' : t >= dur - 1e-3 ? 'again' : 'play');
export const PLAY_TEXT = { play: ['▶\uFE0E', 'Play'], pause: ['❚❚', 'Pause'], again: ['↺', 'Again'] };
// The start screen's button: the guides are followed, the real examples watched; each says its length.
export const startLabel = (d, real) => `${real ? 'Play the real recording' : 'Start the guided motion'} · ${Math.round(d.dur)} s`;
// The 3-2-1 before the first move: where to stand, from the camera's distance to the board plane at the start.
export function getReadyText(d) {
  const p = d.s.p_C[0], c = d.raw.board.center;
  return `Get in position: board ${Math.round(100 * Math.abs(p[2] - c[2]))} cm ahead, face-on`;
}
// The hardest move to practise: the one with the fastest peak, linear and angular speed each as a share of the take's
// peak, added. Rests never count. null when the take has no moves.
export function hardestMove(d) {
  const { s, n, hz } = d;
  const v = new Float64Array(n), w = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    const a = s.p_C[Math.max(0, i - 1)], b = s.p_C[Math.min(n - 1, i + 1)];
    v[i] = (Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]) * hz) / (Math.min(n - 1, i + 1) - Math.max(0, i - 1) || 1);
    w[i] = Math.hypot(...s.gyro[i]);
  }
  const V = Math.max(1e-9, ...v), Wp = Math.max(1e-9, ...w);
  let best = null, score = -1;
  for (const g of d.segs) {
    if (!g.k) continue;
    let pv = 0, pw = 0;
    for (let i = Math.max(0, Math.round(g.t0 * hz)); i < Math.min(n, Math.round(g.t1 * hz) + 1); i++) { pv = Math.max(pv, v[i]); pw = Math.max(pw, w[i]); }
    if (pv / V + pw / Wp > score + 1e-12) { score = pv / V + pw / Wp; best = g; }
  }
  return best;
}
export const PRACTICE_SPEED = 0.5;
// Practise one move: jump to it, 0.5x, repeat it; what was set before is kept to restore. Only moves (not rests).
// Returns false (nothing changed) for a rest or a move not in the take.
export function enterPractice(st, segs, g) {
  if (!g || !g.k || !segs.includes(g)) return false;
  if (!st.practice) st.saved = { speed: st.speed, repeat: st.repeat };
  st.practice = g;
  st.repeat = g;
  st.speed = PRACTICE_SPEED;
  st.hold = 0;
  st.t = g.t0 + 1e-3;
  return true;
}
// Leave practice: the speed and repeat from before it, the clock where it is. False when not practising.
export function exitPractice(st) {
  if (!st.practice) return false;
  const sv = st.saved || { speed: 1, repeat: null };
  st.speed = sv.speed;
  st.repeat = sv.repeat;
  st.practice = null;
  st.saved = null;
  st.hold = 0;
  return true;
}
export const practiceBadge = (st) => (st.practice ? `Practising: ${st.practice.name} · ${st.speed}× · ${st.repeat ? 'repeating' : 'once'}` : '');

// The largest 4-connected group of cells (indices into a gx x gy grid) among `cells`.
export function largestRegion(cells, gx, gy) {
  const left = new Set(cells);
  let best = new Set();
  for (const c of cells) {
    if (!left.has(c)) continue;
    const grp = new Set([c]), q = [c];
    left.delete(c);
    while (q.length) {
      const n = q.pop(), x = n % gx, y = Math.floor(n / gx);
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const xx = x + dx, yy = y + dy, m = yy * gx + xx;
        if (xx >= 0 && xx < gx && yy >= 0 && yy < gy && left.has(m)) { left.delete(m); grp.add(m); q.push(m); }
      }
    }
    if (grp.size > best.size) best = grp;
  }
  return best;
}

// ---------- player ----------
export function mount(root) {
  const $ = (r) => root.querySelector(`[data-role="${r}"]`);
  const c3d = $('c3d'), cimu = $('cimu');
  const ui = {
    variants: $('variants'), caption: $('caption'), diff: $('diff'), title: $('title'), sw: $('sw'), left: $('left'),
    cue: $('cue'), beat: $('beat'), bar: $('bar'), ticks: $('ticks'), next: $('next'), more: $('more'), moretext: $('moretext'),
    readout: $('readout'), cards: $('cards'), tabs: $('tabs'), play: $('play'), prev: $('prev'), nextB: $('nextmove'),
    scrub: $('scrub'), time: $('time'), speeds: $('speeds'), repeat: $('repeat'), axes: $('axes'), img: $('img'), fs: $('fs'),
    camfs: $('camfs'), play2: $('play2'), segchips: $('segchips'), traces: $('traces'), status: $('status'), count: $('count'),
    views: $('views'), table: $('table'), now: $('now'), countn: $('countn'), ready: $('ready'), start: $('start'),
    startbtn: $('startbtn'), startlab: $('startlab'), end: $('end'), endcov: $('endcov'), endpct: $('endpct'), again: $('again'),
    hard: $('hard'), pbadge: $('pbadge'), ptext: $('ptext'), pexit: $('pexit'),
  };
  const real = root.dataset.mode === 'real';
  const base = root.dataset.base;
  const ids = MODES[root.dataset.mode] || MODES.main;
  const cache = new Map();
  const st = {
    d: null, vid: null, t: 0, playing: false, speed: 1, last: 0, view: 'op', az: 0.75, el: 0.32, zoom: 1,
    axes: false, img: true, sel: 0, repeat: null, hold: 0, want: null, counting: 0, theme: {}, dirtyImu: true, lastTitle: '',
    screen: 'start', practice: null, saved: null,
  };
  const sp = Number(store.get('cm-speed'));
  if (SPEEDS.includes(sp)) st.speed = sp;

  // variant chips
  const chips = new Map();
  for (const id of ids) {
    const b = document.createElement('button');
    b.type = 'button';
    b.innerHTML = `<span class="cm-dot none"></span>${VARIANTS[id].label}`;
    b.addEventListener('click', () => load(id));
    ui.variants.append(b);
    chips.set(id, b);
  }

  function readTheme() {
    const c = (n) => getComputedStyle(root).getPropertyValue(n).trim();
    st.theme = {
      x: c('--cm-x'), y: c('--cm-y'), z: c('--cm-z'), g: c('--cm-g'), board: c('--cm-board'), tag: c('--cm-tag'),
      cov: c('--cm-cov'), corner: c('--cm-corner'), ghost: c('--cm-ghost'), line: c('--sl-color-gray-5'),
      faint: c('--sl-color-gray-6'), text: c('--sl-color-gray-3'), strong: c('--sl-color-white'), accent: c('--sl-color-accent'),
      panel: c('--sl-color-bg-nav') || c('--sl-color-black'),
      cam: [c('--cm-cam0'), c('--cm-cam1'), c('--cm-cam2')],
      seg: Object.fromEntries(SEG_KEYS.map((k) => [k, c(`--cm-s-${k}`)])),
    };
    st.dirtyImu = true;
    cards.forEach((cd) => (cd.covCv = null));
  }
  let cards = [];
  readTheme();
  new MutationObserver(() => { readTheme(); draw(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  new ResizeObserver(() => { st.dirtyImu = true; cards.forEach((cd) => (cd.covCv = null)); draw(); }).observe(root);

  async function getData(id) {
    if (!cache.has(id)) cache.set(id, fetchJSON(`${base}${SETS[VARIANTS[id].set].dir}${id}.json`).then((raw) => prep(raw, id)));
    try {
      return await cache.get(id);
    } catch (e) {
      cache.delete(id);
      throw e;
    }
  }

  async function load(id) {
    for (const [k, b] of chips) b.setAttribute('aria-pressed', String(k === id));
    st.want = id;   // a slower earlier click must not replace this one when its data lands
    if (id === st.vid) return;
    ui.status.textContent = 'Loading…';
    let d;
    try {
      d = await getData(id);
    } catch (e) {
      if (st.want !== id) return;
      ui.status.textContent = `Could not load ${VARIANTS[id].label}: ${e.message}`;
      return;
    }
    if (st.want !== id) return;
    st.d = d;
    st.vid = id;
    st.t = 0;
    if (st.saved) st.speed = st.saved.speed;
    st.practice = null;
    st.saved = null;
    st.repeat = null;
    st.hold = 0;
    st.sel = 0;
    st.zoom = 1;
    setPlaying(false);
    setScreen('load');
    syncSpeeds();
    ui.startlab.textContent = startLabel(d, real);
    ui.scrub.max = String(d.dur);
    ui.status.textContent = '';
    const V = VARIANTS[id];
    ui.caption.innerHTML = `<b>${V.label}.</b> ${V.why}`;
    if (ui.diff) ui.diff.textContent = V.diff || '';
    ui.repeat.setAttribute('aria-pressed', 'false');
    segChips();
    scrubBands();
    buildCards();
    if (SETS[V.set].cams && !d.cams) loadCams(id, d);
    else if (!SETS[V.set].cams && !d.soFar) d.soFar = guideSoFar(d);
    st.dirtyImu = true;
    draw();
  }

  async function loadCams(id, d) {
    try {
      const side = await fetchJSON(`${base}${SETS[VARIANTS[id].set].dir}${id}.cams.json`);
      d.cams = prepCams(side);
      if (st.vid === id) { buildCards(); draw(); }
    } catch (e) {
      if (st.vid === id) ui.cards.querySelectorAll('small').forEach((x) => (x.textContent = 'Detected corners not available.'));
    }
  }

  // ---- camera cards ----
  function camList() {
    const d = st.d, V = VARIANTS[st.vid];
    if (!SETS[V.set].cams) {
      const [W, H] = d.raw.camera.image_size;
      return [{ name: 'cam0', size: [W, H], color: st.theme.cam[0] }];
    }
    if (!d.cams) return ['cam0', 'cam1', 'cam2'].map((name, i) => ({ name, size: i < 2 ? [544, 640] : [1920, 1088], color: st.theme.cam[i], pending: true }));
    return d.cams.map((c, i) => ({ name: c.name, size: c.size, color: st.theme.cam[i] || c.color }));
  }
  function buildCards() {
    const list = camList();
    ui.cards.replaceChildren();
    ui.tabs.replaceChildren();
    cards = list.map((c, i) => {
      const el = document.createElement('div');
      el.className = 'cm-card';
      el.setAttribute('aria-current', String(i === st.sel));
      const ar = `aspect-ratio:${c.size[0]} / ${c.size[1]};--ar:${(c.size[0] / c.size[1]).toFixed(4)}`;
      el.innerHTML = `<b><i style="background:${c.color}"></i>${c.name}<span class="cm-tag">drawn, no frame</span></b>`
        + `<div class="cm-pair"><canvas style="${ar}" aria-label="${c.name}: board and detected corners"></canvas>`
        + `<canvas style="${ar}" aria-label="${c.name}: image coverage so far"></canvas></div>`
        + `<small>${c.pending ? 'loading detected corners…' : ''}</small>`
        + '<small class="cm-key">filled: seen · dashed: still empty · <span>fill next</span>: the biggest gap</small>';
      el.addEventListener('click', () => pick(i));
      ui.cards.append(el);
      const tab = document.createElement('button');
      tab.type = 'button';
      tab.textContent = c.name;
      tab.setAttribute('aria-pressed', String(i === st.sel));
      tab.addEventListener('click', () => pick(i));
      ui.tabs.append(tab);
      const [view, cov] = el.querySelectorAll('canvas');
      return { el, tab, view, cov, note: el.querySelector('small'), cam: c, covCv: null, covAt: -1 };
    });
    root.classList.toggle('cm-multi', cards.length > 1);
  }
  function pick(i) {
    st.sel = i;
    cards.forEach((c, j) => { c.el.setAttribute('aria-current', String(j === i)); c.tab.setAttribute('aria-pressed', String(j === i)); c.covCv = null; });
    draw();
  }
  function fit(c) {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(1, Math.round(c.clientWidth * dpr)), h = Math.max(1, Math.round(c.clientHeight * dpr));
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; return true; }
    return false;
  }

  // Camera pose of card i at sample index i0 (board frame B).
  function camPose(ci, i0) {
    const d = st.d, R = quatToR(d.s.q_wxyz[i0]), p = d.s.p_C[i0];
    if (!ci || !d.cams) return { R, p };
    const c = d.cams[ci];
    return { R: mm(R, c.R), p: add(p, mv(R, c.tt)) };
  }
  const idx = (t) => Math.max(0, Math.min(st.d.n - 1, Math.round(t * st.d.hz)));
  const sidx = (t) => Math.max(0, Math.min(st.d.cams ? st.d.cams[0].uv.length - 1 : 0, Math.round(t * 10)));

  // What one card shows now: {uv: [[u, v, detected]], n, outline, pct, soFar, dist, off}
  function cardNow(ci) {
    const d = st.d, i = idx(st.t), raw = d.raw;
    if (d.cams) {
      const c = d.cams[ci], k = sidx(st.t);
      const ks = nearestStep(c.uv, k), f = c.uv[ks], uv = [];
      for (let q = 0; q + 1 < f.length; q += 2) uv.push([f[q], f[q + 1], true]);
      return { uv, n: uv.length, near: ks !== k ? (ks - k) / 10 : 0, outline: c.outline[ks] || c.outline[k], pct: camCoverage(c, st.t),
        soFar: c.n_so_far[k], dist: c.dist_cm[ks], off: c.off_deg[ks] };
    }
    const { R, p } = camPose(0, i);
    const det = boardDetections(raw.board, raw.camera.intr8, raw.camera.image_size, R, p);
    const o = d.s.outline_px[i];
    const order = [0, 4, 1, 5, 2, 6, 3, 7];
    let got = 0;
    d.first100.forEach((t0, n) => { if (t0 <= st.t && d.reach[n]) got++; });
    const nb = [0, 0, 1];
    return {
      uv: det.uv.map((q, k) => (q ? [q[0], q[1], det.det[k]] : null)).filter(Boolean), n: det.n,
      outline: o && o.every(Boolean) ? order.map((j) => o[j]) : null, pct: (100 * got) / Math.max(1, d.nReach),
      soFar: d.soFar ? d.soFar[i] : 0, dist: Math.abs(dot(nb, sub(p, raw.board.center))) * 100,
      off: (Math.acos(Math.min(1, Math.abs(R[2][2]))) * 180) / Math.PI,
    };
  }

  function drawCards() {
    const th = st.theme, d = st.d;
    cards.forEach((card, ci) => {
      if (card.cam.pending || !card.view.clientWidth) return;
      const now = cardNow(ci), [iw, ih] = card.cam.size;
      card.now = now;
      // view: board outline, detected corners filled, missed ones hollow
      fit(card.view);
      let ctx = card.view.getContext('2d');
      let W = card.view.width, H = card.view.height, k = W / iw, px = W / card.view.clientWidth;
      ctx.fillStyle = th.panel;
      ctx.fillRect(0, 0, W, H);
      if (now.outline) {
        ctx.beginPath();
        now.outline.forEach(([u, v], j) => (j ? ctx.lineTo(u * k, v * k) : ctx.moveTo(u * k, v * k)));
        ctx.closePath();
        ctx.fillStyle = `rgba(${th.cov}, 0.10)`;
        ctx.fill();
        ctx.strokeStyle = th.text;
        ctx.lineWidth = 1.2 * px;
        ctx.stroke();
      }
      const r = Math.max(1.1 * px, W / 110);
      for (const [u, v, ok] of now.uv) {
        if (u < -2 || v < -2 || u > iw + 2 || v > ih + 2) continue;
        ctx.beginPath();
        ctx.arc(u * k, v * k, r, 0, 7);
        if (ok) { ctx.globalAlpha = now.near ? 0.55 : 1; ctx.fillStyle = th.corner; ctx.fill(); ctx.globalAlpha = 1; } else { ctx.strokeStyle = th.text; ctx.lineWidth = px; ctx.stroke(); }
      }
      if (!now.n && !now.outline) {
        ctx.fillStyle = th.text;
        ctx.font = `${11 * px}px system-ui, sans-serif`;
        ctx.textAlign = 'center';
        ctx.fillText('board out of view', W / 2, H / 2);
        ctx.textAlign = 'start';
      }
      const sel = ci === st.sel;
      const nowText = `${now.n ? `${now.n} corners ${now.near ? `(nearest frame, ${now.near > 0 ? '+' : ''}${now.near.toFixed(1)} s)` : 'now'}` : 'no corners now'}`;
      if (!card.cov.clientWidth) { card.note.textContent = nowText; return; }   // a thumbnail: the view only
      // coverage: first-seen cells (guides: fine grid; real: the detected corners), 100 px grid, empty cells dashed
      fit(card.cov);
      W = card.cov.width; H = card.cov.height; k = W / iw;
      ctx = card.cov.getContext('2d');
      ctx.fillStyle = th.panel;
      ctx.fillRect(0, 0, W, H);
      if (d.cams) {
        if (!card.covCv || card.covAt > sidx(st.t) || card.covCv.width !== W) {
          card.covCv = document.createElement('canvas');
          card.covCv.width = W; card.covCv.height = H; card.covAt = -1;
        }
        const cg = card.covCv.getContext('2d'), c = d.cams[ci];
        cg.fillStyle = `rgba(${th.cov}, 0.45)`;
        for (let s = card.covAt + 1; s <= sidx(st.t); s++) { const f = c.uv[s]; for (let q = 0; q + 1 < f.length; q += 2) cg.fillRect(f[q] * k - px, f[q + 1] * k - px, 2 * px, 2 * px); }
        card.covAt = sidx(st.t);
        ctx.drawImage(card.covCv, 0, 0);
      } else {
        const [nx] = d.raw.coverage.fine_grid, cell = d.raw.coverage.fine_px;
        for (let c = 0; c < d.first.length; c++) {
          const t0 = d.first[c];
          if (t0 > st.t) continue;
          const age = st.t - t0;
          ctx.fillStyle = `rgba(${th.cov}, ${age < 1 ? 0.55 - 0.25 * age : 0.3})`;
          ctx.fillRect((c % nx) * cell * k, Math.floor(c / nx) * cell * k, cell * k + 0.5, cell * k + 0.5);
        }
      }
      const [gx, gy] = d.cams ? d.cams[ci].grid : d.raw.coverage.metric_grid;
      const reach = d.cams ? d.cams[ci].reach : d.reach;
      const seen = (n) => (d.cams ? d.cams[ci].cov100_first[n] != null && d.cams[ci].cov100_first[n] <= st.t + 0.05 : d.first100[n] <= st.t);
      const empty = [];
      for (let n = 0; n < gx * gy; n++) if (reach[n] && !seen(n)) empty.push(n);
      // "fill next" (selected card only)
      const next = sel ? fillNext(empty, reach.reduce((a, b) => a + (b ? 1 : 0), 0), gx, gy) : new Set();
      const cellRect = (n) => {
        const cx = n % gx, cy = Math.floor(n / gx);
        return [cx * 100 * k + 2 * px, cy * 100 * k + 2 * px, Math.min(100, iw - cx * 100) * k - 4 * px, Math.min(100, ih - cy * 100) * k - 4 * px];
      };
      for (const n of empty) {
        const [x, y, w, h] = cellRect(n), hot = next.has(n);
        if (hot) { ctx.globalAlpha = 0.16; ctx.fillStyle = th.accent; ctx.fillRect(x, y, w, h); ctx.globalAlpha = 1; }
        ctx.strokeStyle = hot ? th.accent : th.text;
        ctx.lineWidth = (hot ? 2 : 1) * px;
        ctx.setLineDash(hot ? [] : [3 * px, 3 * px]);
        ctx.strokeRect(x, y, w, h);
      }
      ctx.setLineDash([]);
      if (next.size) {   // the label on the region's cell nearest its centre
        const cs = [...next], mx = cs.reduce((a, n) => a + (n % gx), 0) / cs.length, my = cs.reduce((a, n) => a + Math.floor(n / gx), 0) / cs.length;
        const dc = (n) => Math.hypot((n % gx) - mx, Math.floor(n / gx) - my);
        const c0 = cs.reduce((b, n) => (dc(n) < dc(b) ? n : b));
        const [x, y, w, h] = cellRect(c0), fs = Math.max(9, Math.min(12, w / px / 4.2));
        ctx.font = `600 ${fs * px}px system-ui, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.lineWidth = 3 * px;
        ctx.strokeStyle = th.panel;
        const hw = ctx.measureText('fill next').width / 2 + 2 * px, lx = Math.max(hw, Math.min(W - hw, x + w / 2));   // keep the label inside the card
        const ly = Math.max(fs * px, Math.min(H - fs * px, y + h / 2));
        ctx.strokeText('fill next', lx, ly);
        ctx.fillStyle = th.accent;
        ctx.fillText('fill next', lx, ly);
        ctx.textAlign = 'start';
        ctx.textBaseline = 'alphabetic';
      }
      ctx.strokeStyle = th.line;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.6;
      for (let x = 100; x < iw; x += 100) { ctx.beginPath(); ctx.moveTo(x * k, 0); ctx.lineTo(x * k, H); ctx.stroke(); }
      for (let y = 100; y < ih; y += 100) { ctx.beginPath(); ctx.moveTo(0, y * k); ctx.lineTo(W, y * k); ctx.stroke(); }
      ctx.globalAlpha = 1;
      card.note.textContent = `${nowText} · ${Math.round(now.pct)} % of the image · ${now.soFar.toLocaleString('en-US')} so far`;
    });
  }

  // ---- 3D view ----
  const fitPts = () => {
    const d = st.d;
    if (d.fitPts) return d.fitPts;
    const [o0, , o2] = d.outline, m = 0.03;
    const x0 = Math.min(o0[0], o2[0]) - m, x1 = Math.max(o0[0], o2[0]) + m, y0 = Math.min(o0[1], o2[1]) - m, y1 = Math.max(o0[1], o2[1]) + m;
    const pts = [[x0, y0, 0], [x1, y0, 0], [x0, y1, 0], [x1, y1, 0]];
    const step = Math.max(1, Math.floor(d.n / 600));
    for (let k = 0; k < d.n; k += step) pts.push(d.path[k]);
    pts.push(d.path[d.n - 1]);
    const lo = [0, 1, 2].map((a) => Math.min(...pts.map((p) => p[a]))), hi = [0, 1, 2].map((a) => Math.max(...pts.map((p) => p[a])));
    d.fitPts = pts;
    d.fitCtr = scl(add(lo, hi), 0.5);
    d.opEye = add(d.path[0], [0, 0.3, 0.55]);
    return pts;
  };
  function projection(W, H) {
    const d = st.d, pts = fitPts();
    const keyV = `${st.view}|${st.az}|${st.el}|${st.zoom}|${W}|${H}`;
    if (d.proj && d.proj.keyV === keyV) return d.proj;
    const pad = 0.09;
    let eye, f, r, u, foc = Math.min(W, H) * 1.3, mid = [0, 0];
    if (st.view === 'op') {
      eye = d.opEye;
      f = norm(sub(d.center, eye));
      r = norm(cross(f, [0, 1, 0]));
      u = cross(r, f);
    } else {
      const [dir, up] = st.view === 'top' ? [[0, 1, 0], [0, 0, -1]] : st.view === 'side' ? [[1, 0, 0], [0, 1, 0]]
        : [[Math.sin(st.az) * Math.cos(st.el), Math.sin(st.el), Math.cos(st.az) * Math.cos(st.el)], [0, 1, 0]];
      f = scl(dir, -1);
      r = norm(cross(f, up));
      u = cross(r, f);
      let dist = 0.5;
      for (const p of pts) {
        const q = sub(p, d.fitCtr), c = dot(q, f);
        dist = Math.max(dist, (foc * (Math.abs(dot(q, r)) + pad)) / (0.46 * W) - c, (foc * (Math.abs(dot(q, u)) + pad)) / (0.45 * H) - c, 0.2 - c);
      }
      eye = add(d.fitCtr, scl(dir, dist));
    }
    if (st.view !== '3d') {   // fixed views: the board and the whole path fill about 80 % of the canvas, centred
      let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
      for (const p of pts) {
        const q = sub(p, eye), z = Math.max(dot(q, f), 0.08), x = dot(q, r) / z, y = dot(q, u) / z;
        x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
      }
      foc = Math.min((FILL * W) / Math.max(1e-6, x1 - x0), (FILL * H) / Math.max(1e-6, y1 - y0));
      mid = [(x0 + x1) / 2, (y0 + y1) / 2];
    }
    foc *= st.zoom;
    const ox = W / 2 - foc * mid[0], oy = H / 2 + foc * mid[1];
    const xy = new Float32Array(2 * d.n);
    for (let k = 0; k < d.n; k++) {
      const q = sub(d.path[k], eye), z = Math.max(dot(q, f), 0.05);
      xy[2 * k] = ox + (foc * dot(q, r)) / z;
      xy[2 * k + 1] = oy - (foc * dot(q, u)) / z;
    }
    d.proj = { keyV, eye, f, r, u, foc, ox, oy, xy };
    return d.proj;
  }

  function view3d() {
    const ctx = c3d.getContext('2d');
    fit(c3d);
    const W = c3d.width, H = c3d.height, th = st.theme, d = st.d, px = W / (c3d.clientWidth || 1);
    ctx.clearRect(0, 0, W, H);
    const pj = projection(W, H), { eye, f, r, u, foc, ox, oy, xy } = pj;
    const P = (p) => { const q = sub(p, eye), z = Math.max(dot(q, f), 0.05); return [ox + (foc * dot(q, r)) / z, oy - (foc * dot(q, u)) / z]; };
    const path = (pts, close) => { ctx.beginPath(); pts.forEach((p, k) => { const [x, y] = P(p); k ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); if (close) ctx.closePath(); };
    const line = (pts, color, w = 1, dash) => {
      path(pts);
      ctx.strokeStyle = color; ctx.lineWidth = w * px; ctx.setLineDash(dash ? dash.map((x) => x * px) : []); ctx.stroke(); ctx.setLineDash([]);
    };
    const [o0, , o2] = d.outline, m = 0.03;
    const xs = [o0[0], o2[0]], ys = [o0[1], o2[1]];
    const fy = d.center[1] - 1.25;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    // 1. floor grid and gravity (Axes on)
    if (st.axes) {
      ctx.globalAlpha = 0.35;
      for (let x = -1; x <= 1.001; x += 0.25) line([[d.center[0] + x, fy, -0.2], [d.center[0] + x, fy, 1.4]], th.line);
      for (let z = -0.2; z <= 1.401; z += 0.2) line([[d.center[0] - 1, fy, z], [d.center[0] + 1, fy, z]], th.line);
      ctx.globalAlpha = 1;
      const g0 = [Math.max(...xs) + 0.09, Math.max(...ys), 0], g1 = add(g0, [0, -0.2, 0]);
      line([g0, g1], th.g, 2);
      line([add(g1, [-0.02, 0.035, 0]), g1, add(g1, [0.02, 0.035, 0])], th.g, 2);
      const [gx, gy] = P(add(g1, [0.03, 0.02, 0]));
      ctx.fillStyle = th.g;
      ctx.font = `${12 * px}px system-ui, sans-serif`;
      ctx.fillText('g', gx, gy);
    }
    // 2. board and stand
    const plate = [[Math.min(...xs) - m, Math.max(...ys) + m, 0], [Math.max(...xs) + m, Math.max(...ys) + m, 0],
      [Math.max(...xs) + m, Math.min(...ys) - m, 0], [Math.min(...xs) - m, Math.min(...ys) - m, 0]];
    path(plate, true);
    ctx.fillStyle = th.board; ctx.fill(); ctx.strokeStyle = th.line; ctx.lineWidth = px; ctx.stroke();
    if (dot(sub(eye, d.center), [0, 0, 1]) > 0) for (const t of d.tags) { path(t, true); ctx.fillStyle = th.tag; ctx.fill(); }
    line([[d.center[0], Math.min(...ys) - m, -0.01], [d.center[0], fy, -0.01]], th.line, 2);
    // 3. whole path in move colours: ahead faint, behind solid; 4. look-ahead 1.5 s with an arrowhead
    const i = idx(st.t);
    const stroke = (k0, k1, color, w, alpha) => {
      if (k1 <= k0) return;
      ctx.beginPath(); ctx.moveTo(xy[2 * k0], xy[2 * k0 + 1]);
      for (let k = k0 + 1; k <= k1; k++) ctx.lineTo(xy[2 * k], xy[2 * k + 1]);
      ctx.strokeStyle = color; ctx.lineWidth = w * px; ctx.globalAlpha = alpha; ctx.stroke();
    };
    // moves already done: thin and dim; moves to come: thin and faint; the current move: full colour and width
    const cur = segAt(d.segs, st.t);
    for (const run of d.runs) if (run.g !== cur) stroke(run.k0, run.k1, th.seg[run.key], 1.1, run.g.t1 <= st.t ? 0.14 : 0.3);
    for (const run of d.runs) if (run.g === cur) stroke(run.k0, run.k1, th.seg[run.key], 2.6, 1);
    const ia = Math.min(d.n - 1, i + Math.round(1.5 * d.hz));
    for (const run of d.runs) stroke(Math.max(run.k0, i), Math.min(run.k1, ia), th.seg[run.key], 4, 1);
    ctx.globalAlpha = 1;
    if (ia > i + 1) {
      const ib = Math.max(i, ia - 3), ax = xy[2 * ia], ay = xy[2 * ia + 1], a = Math.atan2(ay - xy[2 * ib + 1], ax - xy[2 * ib]);
      if (Math.hypot(ax - xy[2 * ib], ay - xy[2 * ib + 1]) > 0.5 * px) {
        ctx.beginPath(); ctx.moveTo(ax + 9 * px * Math.cos(a), ay + 9 * px * Math.sin(a));
        ctx.lineTo(ax + 7 * px * Math.cos(a + 2.3), ay + 7 * px * Math.sin(a + 2.3));
        ctx.lineTo(ax + 7 * px * Math.cos(a - 2.3), ay + 7 * px * Math.sin(a - 2.3));
        ctx.closePath(); ctx.fillStyle = th.seg[d.key[ia]]; ctx.fill();
      }
    }
    // 5. ghost frustum at t + 1 s; 6. current frustum, its ray to the board, the card on its face
    const cam = cards[st.sel] ? cards[st.sel].cam : { size: d.raw.camera.image_size };
    const K = d.cams && d.cams[st.sel] ? d.cams[st.sel].k : d.raw.camera.intr8.slice(0, 4);
    const [iw, ih] = cam.size;
    const frustum = (k) => {
      const { R, p } = camPose(st.sel, k), R_D = mm(DM, R), pc = toD(p), dep = 0.09;
      const cs = [[0, 0], [iw, 0], [iw, ih], [0, ih]].map(([uu, vv]) => add(pc, mv(R_D, [((uu - K[2]) / K[0]) * dep, ((vv - K[3]) / K[1]) * dep, dep])));
      return { R_D, pc, cs, top: add(pc, mv(R_D, [0, (-K[3] / K[1]) * dep * 1.25, dep])) };
    };
    const ig = Math.min(d.n - 1, i + Math.round(d.hz));
    if (ig > i) {
      const gf = frustum(ig);
      line([...gf.cs, gf.cs[0]], th.ghost, 1, [3, 3]);
      for (const c of gf.cs) line([gf.pc, c], th.ghost, 0.8, [3, 3]);
    }
    const cf = frustum(i), cc = cam.color || th.cam[0];
    const zc = mv(cf.R_D, [0, 0, 1]);
    if (zc[2] < -1e-3) line([cf.pc, add(cf.pc, scl(zc, -cf.pc[2] / zc[2]))], cc, 1.2, [5, 4]);
    const src = cards[st.sel] && cards[st.sel].view;
    const sc = cf.cs.map(P);
    if (st.img && src && src.width > 1 && src.clientWidth) {
      const [p00, p10, , p01] = sc;
      const det = (p10[0] - p00[0]) * (p01[1] - p00[1]) - (p10[1] - p00[1]) * (p01[0] - p00[0]);
      ctx.save();
      ctx.globalAlpha = det > 0 ? 0.92 : 0.4;
      ctx.transform((p10[0] - p00[0]) / src.width, (p10[1] - p00[1]) / src.width, (p01[0] - p00[0]) / src.height, (p01[1] - p00[1]) / src.height, p00[0], p00[1]);
      ctx.drawImage(src, 0, 0);
      ctx.restore();
    } else {
      path(cf.cs, true); ctx.fillStyle = `rgba(${th.cov}, 0.18)`; ctx.fill();
    }
    line([...cf.cs, cf.cs[0]], cc, 1.8);
    for (const c of cf.cs) line([cf.pc, c], cc, 1.2);
    line([cf.cs[0], cf.top, cf.cs[1]], cc, 1.2);
    if (st.axes) {
      const R0 = mm(DM, quatToR(d.s.q_wxyz[i])), pc0 = toD(d.s.p_C[i]);   // the IMU hangs off cam0
      const R_DI = mm(R0, d.R_CI), pi = add(pc0, mv(R0, d.p_I_C));
      line([pc0, pi], th.line, 2);
      [th.x, th.y, th.z].forEach((col, a) => line([pi, add(pi, scl([R_DI[0][a], R_DI[1][a], R_DI[2][a]], 0.06))], col, 2.4));
    }
    // 7. current position
    ctx.beginPath();
    ctx.arc(xy[2 * i], xy[2 * i + 1], 4.5 * px, 0, 2 * Math.PI);
    ctx.fillStyle = th.seg[d.key[i]]; ctx.fill();
    ctx.strokeStyle = th.strong; ctx.lineWidth = 1.4 * px; ctx.stroke();
    ctx.lineCap = 'butt';
    ctx.lineJoin = 'miter';
  }

  // ---- Now panel ----
  function drawNow() {
    const d = st.d, n = nowState(d, st.t);
    const title = n.k ? `Move ${n.k} of ${n.K} · ${n.name}` : 'Hold still';
    if (title !== st.lastTitle) {
      ui.title.textContent = title;
      st.lastTitle = title;
      ui.moretext.textContent = n.cue || '';
      ui.more.hidden = !n.cue;
      ui.ticks.innerHTML = n.ticks.map((f) => `<i style="left:${(100 * f).toFixed(2)}%"></i>`).join('');
    }
    ui.sw.style.background = st.theme.seg[n.key];
    ui.bar.style.background = st.theme.seg[n.key];
    ui.bar.style.width = `${(100 * n.frac).toFixed(2)}%`;
    ui.left.textContent = `${n.left} s left`;
    const ready = st.screen === 'start';
    ui.now.classList.toggle('cm-ready', ready);
    ui.cue.textContent = ready ? 'Press Play to start' : n.short;
    ui.beat.textContent = ready ? (real ? '\u00a0' : `${getReadyText(d)}, then hold still.`) : n.beatText || '\u00a0';
    const soon = n.next && n.until <= 3;
    ui.next.classList.toggle('soon', !!soon);
    ui.next.textContent = n.next
      ? `${soon ? `Next in ${n.left} s` : 'Next'}: ${n.next.k ? `${n.next.k} ${n.next.name}` : n.next.name} — ${cut(n.next.short, 60)}`
      : 'Last step. Then stop recording.';
    const on = cards[st.sel] && cards[st.sel].now;
    ui.readout.textContent = on ? `${cards[st.sel].cam.name}: ${Math.round(on.dist)} cm from the board, ${Math.round(on.off)}° off its normal` : '';
    const g = d.segs[n.j];
    ui.segchips.querySelectorAll('.cm-jump').forEach((b, k) => b.setAttribute('aria-pressed', String(k === n.j)));
    if (st.repeat && st.repeat !== g && !st.hold) st.repeat = g;
    // practise follows the move the clock is in (a chip, a step, the scrubber); on a rest it ends
    if (st.practice && st.repeat !== st.practice) {
      if (st.repeat && st.repeat.k) st.practice = st.repeat;
      else { exitPractice(st); syncSpeeds(); ui.repeat.setAttribute('aria-pressed', String(!!st.repeat)); }
    }
    showPractice();
  }

  function segChips() {
    ui.segchips.replaceChildren();
    st.d.segs.forEach((g) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'cm-jump';
      b.innerHTML = `<i class="cm-sw cm-s-${g.key}"></i>${g.k ? `${g.k} ${g.name}` : g.name} · ${segSecs(g)} s`;
      b.addEventListener('click', () => { setScreen('seek'); goSeg(g); });
      if (real || !g.k) { ui.segchips.append(b); return; }
      const w = document.createElement('span');
      w.className = 'cm-segchip';
      const pb = document.createElement('button');
      pb.type = 'button';
      pb.className = 'cm-pbtn';
      pb.textContent = 'Practise';
      pb.setAttribute('aria-label', `Practise ${g.name}: 0.5× speed, repeating`);
      pb.setAttribute('aria-pressed', 'false');
      pb.addEventListener('click', () => practise(g));
      w.append(b, pb);
      ui.segchips.append(w);
    });
  }
  function scrubBands() {
    const d = st.d;
    const stops = d.segs.map((g) => `var(--cm-s-${g.key}) ${((100 * g.t0) / d.dur).toFixed(2)}% ${((100 * g.t1) / d.dur).toFixed(2)}%`);
    ui.scrub.style.setProperty('--cm-bands', `linear-gradient(90deg, ${stops.join(', ')})`);
  }

  // ---- sensor traces (drawn only while open) ----
  let imuBg = null;
  const pad = { l: 44, r: 8, t: 6, gap: 14, b: 18 };
  function imuGeom() {
    const W = cimu.width, H = cimu.height, px = W / (cimu.clientWidth || 1);
    const l = pad.l * px, r = W - pad.r * px, t = pad.t * px, gap = pad.gap * px, b = H - pad.b * px, h = (b - t - gap) / 2;
    return { W, H, px, l, r, rows: [[t, t + h], [t + h + gap, b]] };
  }
  function imuStatic() {
    fit(cimu);
    const g = imuGeom(), th = st.theme, d = st.d;
    imuBg = document.createElement('canvas');
    imuBg.width = g.W; imuBg.height = g.H;
    const ctx = imuBg.getContext('2d'), X = (t) => g.l + ((g.r - g.l) * t) / d.dur;
    ctx.font = `${10 * g.px}px system-ui, sans-serif`;
    d.segs.forEach((s, k) => { if (k % 2) { ctx.fillStyle = th.faint; ctx.fillRect(X(s.t0), g.rows[0][0], X(s.t1) - X(s.t0), g.rows[1][1] - g.rows[0][0]); } });
    [['gyro', d.gmax, 'gyro rad/s'], ['accel', d.amax, 'accel m/s²']].forEach(([key, mx, lab], ri) => {
      const [y0, y1] = g.rows[ri], Y = (v) => (y0 + y1) / 2 - ((y1 - y0) / 2) * (v / mx);
      ctx.strokeStyle = th.line; ctx.lineWidth = g.px;
      ctx.beginPath(); ctx.moveTo(g.l, Y(0)); ctx.lineTo(g.r, Y(0)); ctx.stroke();
      ctx.fillStyle = th.text;
      ctx.fillText(lab, 2 * g.px, y0 + 10 * g.px);
      ctx.fillText(`±${mx.toFixed(mx < 3 ? 1 : 0)}`, 2 * g.px, y1 - 2 * g.px);
      [th.x, th.y, th.z].forEach((col, a) => {
        ctx.strokeStyle = col; ctx.lineWidth = 1.1 * g.px; ctx.globalAlpha = 0.9; ctx.beginPath();
        const s = d.s[key];
        for (let i = 0; i < d.n; i++) { const x = X(d.s.t[i]), y = Y(s[i][a]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }
        ctx.stroke();
      });
      ctx.globalAlpha = 1;
    });
    ctx.fillStyle = th.text;
    for (let t = 0; t <= d.dur + 1e-6; t += 10) { ctx.textAlign = t === 0 ? 'left' : 'center'; ctx.fillText(`${t} s`, X(t), g.H - 4 * g.px); }
    st.dirtyImu = false;
  }
  function drawTraces() {
    if (!ui.traces.open || !cimu.clientWidth) return;
    if (st.dirtyImu || !imuBg || fit(cimu)) imuStatic();
    const ctx = cimu.getContext('2d'), g = imuGeom();
    ctx.clearRect(0, 0, g.W, g.H);
    ctx.drawImage(imuBg, 0, 0);
    const x = g.l + ((g.r - g.l) * st.t) / st.d.dur;
    ctx.strokeStyle = st.theme.accent; ctx.lineWidth = 2 * g.px;
    ctx.beginPath(); ctx.moveTo(x, g.rows[0][0]); ctx.lineTo(x, g.rows[1][1]); ctx.stroke();
  }
  ui.traces.addEventListener('toggle', () => { st.dirtyImu = true; drawTraces(); });
  cimu.addEventListener('click', (e) => {
    if (!st.d) return;
    const rect = cimu.getBoundingClientRect();
    seek(((e.clientX - rect.left - pad.l) / (rect.width - pad.l - pad.r)) * st.d.dur);
  });

  function draw() {
    if (!st.d) return;
    drawCards();
    view3d();
    drawNow();
    drawTraces();
    ui.scrub.value = String(st.t);
    ui.time.textContent = `${st.t.toFixed(1)} / ${st.d.dur.toFixed(1)} s`;
    const m = playMode({ playing: st.playing, counting: st.counting, t: st.t, dur: st.d.dur });
    if (m !== st.lastMode) playLabel(m === 'pause');
  }

  // ---- transport ----
  function seek(t) {
    st.t = Math.max(0, Math.min(st.d.dur, t));
    st.hold = 0;
    draw();
  }
  function goSeg(g) {
    if (st.repeat) st.repeat = g;
    seek(g.t0 + 1e-3);
  }
  function step(dir) {
    if (!st.d) return;
    const segs = st.d.segs, g = segAt(segs, st.t), j = segs.indexOf(g);
    if (dir < 0) goSeg(st.t - g.t0 > 1.5 ? g : segs[Math.max(0, j - 1)]);
    else if (j + 1 < segs.length) goSeg(segs[j + 1]);
  }
  function tick(now) {
    if (!st.playing) return;
    if (advance(st, now, st.d.dur)) { setPlaying(false); draw(); setScreen('end'); return; }
    draw();
    requestAnimationFrame(tick);
  }
  function setPlaying(on) {
    st.playing = on && !!st.d;
    if (!st.playing) { clearInterval(st.counting); st.counting = 0; ui.count.hidden = true; }
    playLabel(st.playing);
    if (st.playing) { st.last = performance.now(); requestAnimationFrame(tick); }
  }
  function playLabel(on) {
    const m = on ? 'pause' : playMode({ playing: false, counting: 0, t: st.t, dur: st.d ? st.d.dur : Infinity });
    st.lastMode = m;
    const [ic, lab] = PLAY_TEXT[m];
    for (const b of [ui.play, ui.play2]) {
      if (!b) continue;
      b.querySelector('.cm-ic').textContent = ic;
      b.querySelector('.cm-pl').textContent = lab;
      b.setAttribute('aria-label', m === 'again' ? 'Play again from the start' : lab);
    }
  }
  // start / end screens over the 3D view
  function setScreen(ev) {
    const was = st.screen;
    st.screen = screenStep(st.screen, ev);
    ui.start.hidden = st.screen !== 'start';
    ui.end.hidden = st.screen !== 'end';
    if (st.screen === 'end' && was !== 'end') showEnd();
  }
  function showEnd() {
    const card = cards[st.sel];
    const c = ui.endcov, src = card && card.cov;
    if (src && src.width > 1 && src.clientWidth) {
      c.width = src.width; c.height = src.height;
      c.style.aspectRatio = `${src.width} / ${src.height}`;
      c.getContext('2d').drawImage(src, 0, 0);
      c.hidden = false;
    } else c.hidden = true;
    const pct = card && card.now ? Math.round(card.now.pct) : null;
    ui.endpct.textContent = pct == null ? '' : pct >= 100 ? `${card.cam.name}: every reachable part of the image seen (100 %).`
      : `${card.cam.name}: ${pct} % of the image seen; the dashed cells were never reached.`;
    if (ui.hard) {
      const h = hardestMove(st.d);
      ui.hard.hidden = !h;
      if (h) ui.hard.textContent = `Practise the hardest move: ${h.name}`;
    }
    ui.again.focus({ preventScroll: true });
  }
  // practise mode (the guides only)
  function syncSpeeds() { ui.speeds.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', String(Number(x.dataset.v) === st.speed))); }
  function showPractice() {
    if (!ui.pbadge) return;
    ui.pbadge.hidden = !st.practice;
    const txt = practiceBadge(st);
    if (ui.ptext.textContent !== txt) ui.ptext.textContent = txt;
    const jumps = [...ui.segchips.querySelectorAll('.cm-jump')];
    ui.segchips.querySelectorAll('.cm-segchip').forEach((w) => {
      const mine = !!st.practice && st.d.segs[jumps.indexOf(w.querySelector('.cm-jump'))] === st.practice;
      w.querySelector('.cm-pbtn').setAttribute('aria-pressed', String(mine));
    });
  }
  function practise(g) {
    if (real || !st.d || !enterPractice(st, st.d.segs, g)) return;
    if (st.playing || st.counting) setPlaying(false);
    syncSpeeds();
    ui.repeat.setAttribute('aria-pressed', 'true');
    togglePlay();
  }
  function leavePractice() {
    if (!exitPractice(st)) return;
    syncSpeeds();
    ui.repeat.setAttribute('aria-pressed', String(!!st.repeat));
    draw();
  }
  if (ui.pexit) ui.pexit.addEventListener('click', leavePractice);
  // one player at a time: starting this one pauses the other; a player scrolled out of view pauses
  document.addEventListener('cm-play', (e) => { if (e.detail !== root && (st.playing || st.counting)) setPlaying(false); });
  new IntersectionObserver((es) => { if (!es[es.length - 1].isIntersecting && (st.playing || st.counting)) setPlaying(false); }).observe(root);
  function togglePlay() {
    if (!st.d) return;
    if (st.playing || st.counting) return setPlaying(false);
    document.dispatchEvent(new CustomEvent('cm-play', { detail: root }));
    if (st.t >= st.d.dur - 1e-3) st.t = 0;
    setScreen('play');
    draw();
    const g = segAt(st.d.segs, st.t);
    if (st.t - g.t0 > 0.2) return setPlaying(true);
    // lead-in: 3-2-1 in real seconds before a move starts; at the take's start, where to stand
    let n = 3;
    ui.count.hidden = false;
    ui.countn.textContent = String(n);
    ui.ready.textContent = st.d.segs.indexOf(g) === 0 && !real ? getReadyText(st.d)
      : st.practice ? `Practise: ${g.name}` : g.k ? `Get ready: ${g.name}` : '';
    playLabel(true);
    st.counting = setInterval(() => {
      n -= 1;
      if (n > 0) { ui.countn.textContent = String(n); return; }
      clearInterval(st.counting);
      st.counting = 0;
      ui.count.hidden = true;
      setPlaying(true);
    }, 1000);
  }
  ui.play.addEventListener('click', togglePlay);
  ui.start.addEventListener('click', () => { if (!st.playing && !st.counting) togglePlay(); });
  ui.again.addEventListener('click', () => { st.t = 0; togglePlay(); });
  if (ui.hard) ui.hard.addEventListener('click', () => practise(hardestMove(st.d)));
  if (ui.play2) ui.play2.addEventListener('click', togglePlay);
  ui.prev.addEventListener('click', () => { setScreen('seek'); step(-1); });
  ui.nextB.addEventListener('click', () => { setScreen('seek'); step(1); });
  ui.scrub.addEventListener('input', () => { setScreen('seek'); seek(Number(ui.scrub.value)); });
  SPEEDS.forEach((v) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = `${v}×`;
    b.dataset.v = String(v);
    b.setAttribute('aria-pressed', String(v === st.speed));
    b.addEventListener('click', () => {
      st.speed = v;
      if (st.practice) st.saved.speed = v;   // also the speed after practice
      else store.set('cm-speed', String(v));
      syncSpeeds();
      showPractice();
    });
    ui.speeds.append(b);
  });
  function toggleRepeat() {
    if (!st.d) return;
    if (st.practice) return leavePractice();   // repeat off ends practice
    st.repeat = st.repeat ? null : segAt(st.d.segs, st.t);
    st.hold = 0;
    ui.repeat.setAttribute('aria-pressed', String(!!st.repeat));
  }
  ui.repeat.addEventListener('click', toggleRepeat);
  const toggle = (b, k) => b.addEventListener('click', () => { st[k] = !st[k]; b.setAttribute('aria-pressed', String(st[k])); draw(); });
  toggle(ui.axes, 'axes');
  toggle(ui.img, 'img');
  function setFs(on) {
    // the page's main pane isolates its stacking context: lift the player out to <body> while in full screen
    if (on && !st.ph) { st.ph = document.createComment('cm'); root.before(st.ph); document.body.append(root); }
    if (!on && st.ph) { st.ph.replaceWith(root); st.ph = null; }
    // the browser's full screen puts the player above the site header and sidebar; the class lays it out (after the move:
    // moving a full-screen element out of the DOM ends full screen)
    if (on && !document.fullscreenElement && root.requestFullscreen) root.requestFullscreen().catch(() => {});
    if (!on && document.fullscreenElement === root) document.exitFullscreen().catch(() => {});
    root.classList.toggle('cm-fs', on);
    ui.fs.textContent = on ? 'Exit full screen' : 'Full screen';
    ui.fs.setAttribute('aria-pressed', String(on));
    document.documentElement.style.overflow = on ? 'hidden' : '';
    if (on) root.focus({ preventScroll: true });
    cards.forEach((c) => (c.covCv = null));
    requestAnimationFrame(draw);
  }
  ui.fs.addEventListener('click', () => setFs(!root.classList.contains('cm-fs')));
  document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement && root.classList.contains('cm-fs')) setFs(false); });
  ui.camfs.addEventListener('click', () => { const on = root.classList.toggle('cm-fs-cams'); ui.camfs.setAttribute('aria-pressed', String(on)); draw(); });

  // view buttons; dragging the canvas from any view switches to the free 3D orbit
  function setView(v) {
    st.view = v;
    st.zoom = 1;
    ui.views.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.view === v)));
    c3d.style.touchAction = v === '3d' ? 'none' : 'pan-y';
    draw();
  }
  ui.views.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => setView(b.dataset.view)));
  let drag = null;
  const pts = new Map();
  c3d.addEventListener('pointerdown', (e) => {
    if (!st.d) return;
    pts.set(e.pointerId, [e.clientX, e.clientY]);
    if (pts.size === 2) { const [a, b] = [...pts.values()]; drag = { pinch: Math.hypot(a[0] - b[0], a[1] - b[1]), zoom: st.zoom }; return; }
    if (e.pointerType !== 'mouse' && st.view !== '3d') return;   // a touch on a fixed view scrolls the page
    c3d.setPointerCapture(e.pointerId);
    drag = { x: e.clientX, y: e.clientY, moved: false };
  });
  c3d.addEventListener('pointermove', (e) => {
    if (!drag) return;
    if (pts.has(e.pointerId)) pts.set(e.pointerId, [e.clientX, e.clientY]);
    if (drag.pinch) {
      if (pts.size === 2) { const [a, b] = [...pts.values()]; st.zoom = Math.max(0.4, Math.min(6, (drag.zoom * Math.hypot(a[0] - b[0], a[1] - b[1])) / drag.pinch)); draw(); }
      return;
    }
    if (!drag.moved) {
      if (Math.hypot(e.clientX - drag.x, e.clientY - drag.y) < 4) return;
      drag.moved = true;
      if (st.view !== '3d') {   // start the orbit from the view on screen
        const pj = st.d.proj, dir = pj ? norm(scl(pj.f, -1)) : [0, 0.3, 1];
        st.az = Math.atan2(dir[0], dir[2]);
        st.el = Math.max(-0.2, Math.min(1.45, Math.asin(dir[1])));
        setView('3d');
      }
      drag.az = st.az; drag.el = st.el;
    }
    st.az = drag.az - (e.clientX - drag.x) * 0.008;
    st.el = Math.max(-0.2, Math.min(1.45, drag.el + (e.clientY - drag.y) * 0.006));
    draw();
  });
  const end = (e) => { pts.delete(e.pointerId); if (pts.size < 2) drag = null; };
  c3d.addEventListener('pointerup', end);
  c3d.addEventListener('pointercancel', end);
  c3d.addEventListener('dblclick', () => setView('op'));
  c3d.addEventListener('wheel', (e) => {
    if (!e.ctrlKey && !root.classList.contains('cm-fs')) return;
    e.preventDefault();
    st.zoom = Math.max(0.4, Math.min(6, st.zoom * (e.deltaY < 0 ? 1.1 : 1 / 1.1)));
    draw();
  }, { passive: false });

  // keyboard: only with focus inside the player, or in full screen
  const onKey = (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key, inRange = e.target && e.target.type === 'range';
    if (k === ' ' || k === 'k' || k === 'K') togglePlay();
    else if ((k === 'ArrowLeft' || k === 'ArrowRight') && !inRange) step(k === 'ArrowLeft' ? -1 : 1);
    else if (k === 'r' || k === 'R') toggleRepeat();
    else if (k === 'f' || k === 'F') setFs(!root.classList.contains('cm-fs'));
    else if (k === 'Escape' && root.classList.contains('cm-fs')) setFs(false);
    else if (k === 'Escape' && st.practice) leavePractice();
    else return;
    e.preventDefault();
    e.stopPropagation();
  };
  root.addEventListener('keydown', onKey);
  document.addEventListener('keydown', (e) => { if (root.classList.contains('cm-fs') && !root.contains(e.target)) onKey(e); });

  // chip dots and, for the real examples, the small table (length, coverage, twin) from the page data
  (async () => {
    const sets = [...new Set(ids.map((id) => VARIANTS[id].set))];
    const got = {};
    await Promise.all(sets.map(async (k) => {
      const [ix, ver] = await Promise.all([fetchJSON(`${base}${SETS[k].dir}index.json`).catch(() => null), fetchJSON(`${base}${SETS[k].dir}twin_verdicts.json`).catch(() => null)]);
      got[k] = { ix, ver };
    }));
    const rows = [];
    for (const id of ids) {
      const { ix, ver } = got[VARIANTS[id].set], v = ver?.variants?.[id], e = ix?.variants?.find((x) => x.id === id);
      const cls = !v || v.status !== 'judged' ? 'none' : v.passed ? 'pass' : 'fail';
      const b = chips.get(id);
      b.querySelector('.cm-dot').className = `cm-dot ${cls}`;
      b.title = { none: 'twin verdict pending', pass: 'twin: good', fail: 'twin: fails' }[cls];
      if (e) rows.push(`<tr><th scope="row"><button type="button" class="cm-link" data-vid="${id}">${VARIANTS[id].label}</button></th><td>${Math.round(e.duration_s)} s</td>`
        + `<td>${(e.cov_cam0 ?? e.cov_reach) != null ? `${Math.round(100 * (e.cov_cam0 ?? e.cov_reach))} %` : '–'}</td><td>${{ none: 'pending', pass: 'good', fail: 'fails' }[cls]}</td></tr>`);
    }
    if (ui.table && rows.length) {
      ui.table.innerHTML = `<thead><tr><th>Example</th><th>Length</th><th>Image coverage</th><th>Twin</th></tr></thead><tbody>${rows.join('')}</tbody>`;
      ui.table.querySelectorAll('.cm-link').forEach((b) => b.addEventListener('click', () => { load(b.dataset.vid); root.scrollIntoView({ behavior: 'smooth', block: 'start' }); }));
    }
  })();

  setView('op');
  load(ids[0]);
}
