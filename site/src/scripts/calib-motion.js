// Calibration-motion guide: player (3D view, camera image, IMU traces) and the twin verdict table.
// Data (public/data/calib-motion/): four sets, same schemas (calib-motion-demo/anim v1 + twin-verdict v3, documented
// in site/scripts/export_calib_motion.py):
//   v4/          AprilGrid twin: the guide motion (guide06c_60, built from the AprilGrid example; the only v4 anim file) and,
//                table only, its 50 s version, the fast-wobble guide06b_60, the first guide and the smoothed real-speed fit;
//                verdicts against the hidden 80 s AprilGrid reference.
//   real_takes/  the AprilGrid example (real take 06 of 2026-11-08, 41.2 s), replayed on the AprilGrid twin; same reference.
//   real_chess/  the chessboard example (real take 01 of 2026-11-07, 60.8 s), replayed on the chessboard twin.
//   v3/          chessboard twin (Looper Insight 9, monitor chessboard): the chessboard version of the guide (guide60b, the
//                only v3 anim file); table rows only: guide60 (its fast-wobble predecessor), the 80 s version and the
//                30 s chessboard take 11-08 01 it is built from; verdicts against the hidden chessboard reference.
// Verdicts: a motion is good when `passed` is true; dots, captions and tables use `passed` and the raw
// `sigma_ratio_vs_good` (rule (d) compares σ with the reference's directly, whatever the length: no duration match).
// Two players can share the page: data-mode="main" (guide motion, chessboard version, coverage maps) and
// data-mode="real" (the AprilGrid and the chessboard example). A table click plays the motion in the player that lists it.
// A verdict table shows one set, or several (TABLES: 'real' = the AprilGrid and the chessboard example).
// Frames in the anim JSON: board frame B (x along the board rows, to the image LEFT for a face-on camera; y down =
// gravity; z toward the camera). R_BC = quaternion [w, x, y, z]; p_C = camera centre in B. The 3D view draws in
// D = diag(-1, -1, 1) B: x to the operator's right, y up, z toward the operator.

export const VARIANTS = {
  // ---- AprilGrid guide motions built from the AprilGrid example (v4) ----
  guide06c_60: { set: 'v4', label: 'Guide motion, 60 s', why: 'Built from the AprilGrid example below: its four moves in the same order (left-right, up-down, back-forth with roll, a loop parallel to the board), with the take\'s coupling and amplitudes, slowed to a pace a hand keeps up comfortably. Added: 3 s rests, a speed that varies on every sweep, turns past the board at the ends of left-right (about 22°, with a sharp turnaround) and up-down (about 34°), an off-centre roll during back-forth, a counter-turn and a 25° roll in the loop, so the board reaches all four picture corners. The fine wobble on top is the slow, natural shake of a hand (1.5-3.5 times a second). 2 left-right, 2 up-down, 3 in-outs, 2.1 loops.' },
  guide06c_50: { set: 'v4', label: 'Guide motion, 50 s', why: 'The guide motion with one in-out and about one loop fewer: the same rates, amplitudes and cues.' },
  guide06b_60: { set: 'v4', label: 'Guide with a fast wobble, 60 s', why: 'The previous guide motion: the same moves, but its hand wobble was a 4-6 Hz buzz, faster than a hand shakes. It passes too, with larger σ.' },
  guide06_60: { set: 'v4', label: 'First guide, 60 s', why: 'The first guide built from the AprilGrid example: the same blocks, but it turned only about 15° past the board at the ends of left-right, barely rolled in the loop and had less jiggle. Slowed down, it lost td.' },
  guide06_50: { set: 'v4', label: 'First guide, 50 s', why: 'The first guide cut to 50 s.' },
  base06_fit: { set: 'v4', label: 'AprilGrid example, smoothed real-speed fit', why: 'A smooth fit of the AprilGrid example at the speed it was recorded (41 s), faster than the hand limits. Not the real take: its twin row is with the real examples below.' },
  // ---- chessboard twin (v3) ----
  guide60b: { set: 'v3', label: 'Chessboard version, 60 s', why: 'The guide motion for a chessboard, derived from our 30 s chessboard take of 2026-11-08: the speed varies on every sweep, left-right and up-down turn past the board so it reaches the picture edges, back-forth holds the board off-centre while rolling, and a corner square ends the motion. Tamed to a comfortable pace and cut to 60 s: 2 left-right, 2 up-down, 3 in-outs. The fine wobble on top is the slow, natural shake of a hand. The whole chessboard stays in view, since a chessboard is only detected when every corner is visible.' },
  guide60: { set: 'v3', label: 'Chessboard version with a fast wobble, 60 s', why: 'The previous chessboard version: the same moves, but its hand wobble was a 4-6 Hz buzz, faster than a hand shakes. It passes too, with larger σ.' },
  derived_good_tamed: { set: 'v3', label: 'Chessboard version, 80 s', why: 'The chessboard version before it was cut to 60 s: 3 left-right, 3 up-down and 4 in-outs, and a 10 s corner square. The same rates, amplitudes and cues.' },
  real_take: { set: 'v3', label: 'Chessboard take 11-08 01, 30 s', why: 'Our hand-held 30 s recording in front of a monitor chessboard, the take the chessboard version is built from: twice left-right, twice up-down, twice back-forth, with the roll tied to the in-out.' },
  // ---- real AprilGrid take (real_takes/, AprilGrid twin) ----
  aprilgrid_06: { set: 'real', label: 'AprilGrid example', why: 'Our 41 s hand-held recording (take 06 of 2026-11-08) in front of a monitor AprilGrid, our best real take and the one the guide motion is built from: three times left-right, three times up-down, four in-outs (0.16-0.53 m) while rolling about ±60°, then 3 loops parallel to the board. Trajectory only, replayed from the calibrated poses; no camera images.' },
  // ---- real chessboard take (real_chess/, chessboard twin) ----
  chessboard_1107_01: { set: 'realc', label: 'Chessboard example', why: 'Our 61 s hand-held recording of 2026-11-07 in front of a monitor chessboard, the whole board kept in view: in-outs while rolling first, then left-right, up-down, about four rolls in place, a short up-down by translation and a mixed block of rolls and reaches toward the corners. Not in the guide order, and the board never reaches the picture corners, but long enough to pass. Trajectory only, replayed from the calibrated poses; no camera images.' },
};
const MAIN = ['guide06c_60', 'guide60b'];
const REAL = ['aprilgrid_06', 'chessboard_1107_01'];
const SETS = {
  v4: { ids: ['guide06c_60', 'guide06c_50', 'guide06b_60', 'guide06_60', 'guide06_50', 'base06_fit'], first: 'guide06c_60', rig: 'AprilGrid twin',
    verdicts: '/data/calib-motion/v4/twin_verdicts.json', dir: 'v4/' },
  v3: { ids: ['guide60b', 'guide60', 'derived_good_tamed', 'real_take'],
    first: 'guide60b', rig: 'chessboard twin', verdicts: '/data/calib-motion/v3/twin_verdicts.json', dir: 'v3/' },
  real: { ids: ['aprilgrid_06'], first: 'aprilgrid_06', rig: 'AprilGrid twin',
    verdicts: '/data/calib-motion/real_takes/twin_verdicts.json', dir: 'real_takes/' },
  realc: { ids: ['chessboard_1107_01'], first: 'chessboard_1107_01', rig: 'chessboard twin',
    verdicts: '/data/calib-motion/real_chess/twin_verdicts.json', dir: 'real_chess/' },
};
const TABLES = { real: ['real', 'realc'] };
const COVCMP = ['guide06c_60', 'aprilgrid_06'];
const MODES = {
  main: { groups: [[MAIN, 'variants-main']], first: 'guide06c_60' },
  real: { groups: [[REAL, 'variants-real']], first: 'aprilgrid_06' },
};
// Path colours in the 3D view: one per move, keyed by the segment role without its trailing number
// (roll-in-place counts as back-forth + roll, a corner square or mixed block as the loop). CSS vars --cm-s-<key>.
const SEG_KEYS = ['lr', 'ud', 'bf', 'loop', 'rest'];
const SEG_OF_ROLE = { lr: 'lr', ud: 'ud', bf: 'bf', roll: 'bf', circle: 'loop', mix: 'loop', rest: 'rest' };
const segKey = (g) => SEG_OF_ROLE[String(g.role || g.name || '').replace(/\d+$/, '')] || 'rest';
const PLAYABLE = new Set(Object.values(MODES).flatMap((m) => m.groups.flatMap(([ids]) => ids)));

export const GROUPS = [
  { name: 'Rotation R_CI', params: ['R_CI_x', 'R_CI_y', 'R_CI_z'] },
  { name: 'Lever arm', params: ['lever_x', 'lever_y', 'lever_z'] },
  { name: 'td, t_ga', params: ['td', 't_ga'] },
  { name: 'Gyro scale', params: ['gyro_scale_x', 'gyro_scale_y', 'gyro_scale_z'] },
  { name: 'Accel scale', params: ['accel_scale_x', 'accel_scale_y', 'accel_scale_z'] },
  { name: 'fx fy cx cy', params: ['fx', 'fy', 'cx', 'cy'] },
  { name: 'k1-k4', params: ['k1', 'k2', 'k3', 'k4'] },
];
const SHORT = (p) => p.replace('R_CI_', 'R ').replace('lever_', '').replace('gyro_scale_', '').replace('accel_scale_', '');

const bus = new EventTarget();
const verdicts = {};
const verdictsReady = Promise.all(Object.entries(SETS).map(([k, S]) =>
  fetchJSON(S.verdicts).then((v) => (verdicts[k] = v)).catch(() => null)));
const vOf = (id) => verdicts[VARIANTS[id]?.set]?.variants?.[id];
const worstRatio = (v) => v.worst_sigma_ratio ?? Math.max(...Object.values(v.params || {}).map((r) => r.sigma_ratio_vs_good ?? 0));
const dotClass = (v) => (!v || v.status !== 'judged' ? 'none' : v.passed === true ? 'pass' : 'fail');

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

// ---------- small math ----------
function quatToR([w, x, y, z]) {
  return [
    [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
    [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
    [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
  ];
}
const mv = (R, v) => [0, 1, 2].map((i) => R[i][0] * v[0] + R[i][1] * v[1] + R[i][2] * v[2]);
const mm = (A, B) => [0, 1, 2].map((i) => [0, 1, 2].map((j) => A[i][0] * B[0][j] + A[i][1] * B[1][j] + A[i][2] * B[2][j]));
const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const scl = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a) => scl(a, 1 / Math.hypot(...a));
const toD = (p) => [-p[0], -p[1], p[2]];

function css(el, name) {
  return getComputedStyle(el).getPropertyValue(name).trim();
}

function fitCanvas(c) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = Math.max(1, Math.round(c.clientWidth * dpr));
  const h = Math.max(1, Math.round(c.clientHeight * dpr));
  if (c.width !== w || c.height !== h) {
    c.width = w;
    c.height = h;
    return true;
  }
  return false;
}

// ---------- player ----------
export function mount(root) {
  const $ = (r) => root.querySelector(`[data-role="${r}"]`);
  const c3d = $('c3d'), ccam = $('ccam'), cimu = $('cimu');
  const ui = {
    play: $('play'), scrub: $('scrub'), time: $('time'), speed: $('speed'), segname: $('segname'),
    segcue: $('segcue'), segchips: $('segchips'), cov: $('cov'), caption: $('caption'), status: $('status'),
    pathlegend: $('pathlegend'),
  };
  const base = root.dataset.base;
  const mode = MODES[root.dataset.mode] || MODES.main;
  const cache = new Map();
  const st = { d: null, vid: null, t: 0, playing: false, speed: 1, last: 0, az: 0.75, el: 0.32, dirtyImu: true, theme: {} };

  // variant chips
  const chips = new Map();
  for (const [ids, role] of mode.groups) {
    const box = $(role);
    if (!box) continue;
    for (const id of ids) {
      const b = document.createElement('button');
      b.type = 'button';
      b.dataset.vid = id;
      b.innerHTML = `<span class="cm-dot none"></span>${VARIANTS[id].label}`;
      b.addEventListener('click', () => load(id));
      box.append(b);
      chips.set(id, b);
    }
  }
  verdictsReady.then(() => {
    for (const [id, b] of chips) {
      const cls = dotClass(vOf(id));
      b.querySelector('.cm-dot').className = `cm-dot ${cls}`;
      b.title = { none: 'verdict pending', pass: 'twin: passes every parameter', fail: 'twin: fails' }[cls];
    }
    caption();
  });

  function readTheme() {
    st.theme = {
      x: css(root, '--cm-x'), y: css(root, '--cm-y'), z: css(root, '--cm-z'), g: css(root, '--cm-g'), t: css(root, '--cm-t'),
      board: css(root, '--cm-board'), tag: css(root, '--cm-tag'), cov: css(root, '--cm-cov'),
      line: css(root, '--sl-color-gray-5'), faint: css(root, '--sl-color-gray-6'), text: css(root, '--sl-color-gray-3'),
      strong: css(root, '--sl-color-white'), accent: css(root, '--sl-color-accent'),
      seg: Object.fromEntries(SEG_KEYS.map((k) => [k, css(root, `--cm-s-${k}`)])),
    };
    st.dirtyImu = true;
  }
  readTheme();
  new MutationObserver(() => { readTheme(); draw(); drawCov(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  new ResizeObserver(() => { st.dirtyImu = true; draw(); drawCov(); }).observe(root);

  async function load(id) {
    for (const [k, b] of chips) b.setAttribute('aria-pressed', String(k === id));
    if (id === st.vid) return;
    ui.status.textContent = 'Loading…';
    try {
      await getData(id);
    } catch (e) {
      ui.status.textContent = `Could not load ${id}: ${e.message}`;
      return;
    }
    const keepT = st.d ? st.t : 0;
    st.d = await getData(id);
    st.vid = id;
    st.t = Math.min(keepT, st.d.dur);
    ui.scrub.max = String(st.d.dur);
    ui.status.textContent = '';
    segChips();
    pathLegend();
    caption();
    st.dirtyImu = true;
    draw();
    bus.dispatchEvent(new CustomEvent('variant', { detail: id }));
  }

  async function getData(id) {
    if (!cache.has(id)) cache.set(id, fetchJSON(`${base}${SETS[VARIANTS[id].set].dir}${id}.json`).then(prep));
    try {
      return await cache.get(id);
    } catch (e) {
      cache.delete(id);
      throw e;
    }
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

  function prep(d) {
    const s = d.samples, n = s.t.length;
    const fine = d.coverage.fine_grid, metric = d.coverage.metric_grid;
    const first = new Float32Array(fine[0] * fine[1]).fill(Infinity);
    const first100 = new Float32Array(metric[0] * metric[1]).fill(Infinity);
    for (let i = 0; i < n; i++) {
      for (const c of s.cov_new[i] || []) if (first[c] === Infinity) first[c] = s.t[i];
      for (const c of s.cov100_new[i] || []) if (first100[c] === Infinity) first100[c] = s.t[i];
    }
    const R_CI = d.camera.R_CI;
    const T = d.camera.T_CtoI;
    const t_CI = [T[0][3], T[1][3], T[2][3]];
    const p_I_C = scl(mv(R_CI, t_CI), -1); // IMU origin in camera axes
    const reach = d.coverage.metric_reach;
    const nReach = reach.reduce((a, b) => a + (b ? 1 : 0), 0);
    const rng = (k) => {
      let m = 0;
      for (const v of s[k]) for (const x of v) m = Math.max(m, Math.abs(x));
      return m * 1.05 || 1;
    };
    const segs = mergeSegs(d.segments);
    // whole camera-centre path in D, and the path colour key of every sample (rests before / after: neutral)
    const path = s.p_C.map(toD);
    const key = new Array(n).fill('rest');
    for (const g of segs) {
      const k = segKey(g);
      for (let i = Math.max(0, Math.round(g.t0 * d.hz)); i < Math.min(n, Math.round(g.t1 * d.hz) + 1); i++) key[i] = k;
    }
    // runs of one colour; each starts at the previous run's last sample so the line has no gaps
    const runs = [];
    for (let i = 0; i < n; i++) {
      const last = runs[runs.length - 1];
      if (last && last.key === key[i]) last.k1 = i;
      else runs.push({ key: key[i], k0: Math.max(0, i - 1), k1: i });
    }
    // legend: the move names of this motion, per colour, in order of first appearance
    const names = new Map();
    for (const g of segs) {
      const k = segKey(g);
      const nm = g.label.replace(/\s+/g, ' ').replace(/^\d+ /, '').replace(/ \d+$/, '').trim();
      if (!names.has(k)) names.set(k, []);
      if (!names.get(k).includes(nm)) names.get(k).push(nm);
    }
    const legend = SEG_KEYS.filter((k) => names.has(k)).map((k) => [k, names.get(k).join(' / ')]);
    const outline = d.board.outline.map(toD);
    return {
      raw: d, s, n, hz: d.hz, dur: d.duration_s, first, first100, reach, nReach, R_CI, p_I_C,
      gmax: rng('gyro'), amax: rng('accel'), segs, path, key, runs, legend, proj: null,
      tags: boardTiles(d.board),
      outline, center: toD(d.board.center),
    };
  }

  // Adjacent segments with the same label and cue play as one step (the real take is split per swing pair);
  // cues use the degree sign like the page text, and whole swing counts read "2 times", not "2.0 times".
  function mergeSegs(segs) {
    const out = [];
    for (const g of segs) {
      if (!(g.t1 - g.t0 > 1e-6)) continue; // drop empty segments (some takes start with a 0 s rest)
      const last = out[out.length - 1];
      if (last && last.label === g.label && last.cue === g.cue && Math.abs(last.t1 - g.t0) < 1e-6) last.t1 = g.t1;
      else out.push({ ...g, cue: (g.cue || '').replace(/(\d) deg\b/g, '$1°').replace(/\b(\d+)\.0 times\b/g, '$1 times') });
    }
    return out;
  }

  function idx(t) {
    return Math.max(0, Math.min(st.d.n - 1, Math.round(t * st.d.hz)));
  }
  function segAt(t) {
    const segs = st.d.segs;
    return segs.find((g) => t >= g.t0 && t < g.t1) || segs[segs.length - 1];
  }

  function segChips() {
    ui.segchips.replaceChildren();
    st.d.segs.forEach((g, k) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = `${g.label.replace(/\s+/g, ' ')} · ${Math.round(g.t1 - g.t0)} s`;
      b.dataset.k = String(k);
      b.addEventListener('click', () => { st.t = g.t0 + 1e-3; draw(); });
      ui.segchips.append(b);
    });
  }

  function pathLegend() {
    if (!ui.pathlegend) return;
    ui.pathlegend.innerHTML = st.d.legend.map(([k, nm]) => `<span><i class="cm-sw cm-s-${k}"></i>${nm}</span>`).join('');
  }

  function caption() {
    if (!st.vid) return;
    const v = vOf(st.vid);
    let tail = '';
    if (v && v.status === 'judged') {
      const w = `σ at most ${worstRatio(v).toFixed(2)}× the 80 s reference${v.worst_sigma_param ? ` (${v.worst_sigma_param.replace(/_/g, ' ')})` : ''}`;
      tail = v.passed ? ` Twin: good, every parameter passes; ${w}.`
        : ` Twin: fails ${v.failed_params.length} of 22 parameters${v.failed_params.length <= 3 ? ` (${v.failed_params.map((p) => p.replace(/_/g, ' ')).join(', ')})` : ''}.`;
    }
    const rig = SETS[VARIANTS[st.vid].set].rig;
    ui.caption.innerHTML = `<span class="cm-rig">${rig}</span> <b>${VARIANTS[st.vid].label}.</b> ${VARIANTS[st.vid].why}${tail}`;
  }

  // ---- 3D view ----
  function view3d() {
    const ctx = c3d.getContext('2d');
    fitCanvas(c3d);
    const W = c3d.width, H = c3d.height, th = st.theme, d = st.d;
    ctx.clearRect(0, 0, W, H);
    const pj = projection(W, H);
    const { eye, f, r, u, foc } = pj;
    const P = (p) => {
      const q = sub(p, eye);
      const z = Math.max(dot(q, f), 0.05);
      return [W / 2 + (foc * dot(q, r)) / z, H / 2 - (foc * dot(q, u)) / z];
    };
    const line = (pts, color, w = 1, dash) => {
      ctx.beginPath();
      pts.forEach((p, k) => { const [x, y] = P(p); k ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
      ctx.strokeStyle = color;
      ctx.lineWidth = w * (W / c3d.clientWidth);
      ctx.setLineDash(dash ? dash.map((x) => x * (W / c3d.clientWidth)) : []);
      ctx.stroke();
      ctx.setLineDash([]);
    };
    const poly = (pts, fill, stroke) => {
      ctx.beginPath();
      pts.forEach((p, k) => { const [x, y] = P(p); k ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
      ctx.closePath();
      if (fill) { ctx.fillStyle = fill; ctx.fill(); }
      if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = W / c3d.clientWidth; ctx.stroke(); }
    };
    const px = W / c3d.clientWidth;

    // floor grid ~1.25 m below the board centre (board at chest height)
    const fy = d.center[1] - 1.25;
    ctx.globalAlpha = 0.35;
    for (let x = -1; x <= 1.001; x += 0.25) line([[d.center[0] + x, fy, -0.2], [d.center[0] + x, fy, 1.4]], th.line);
    for (let z = -0.2; z <= 1.401; z += 0.2) line([[d.center[0] - 1, fy, z], [d.center[0] + 1, fy, z]], th.line);
    ctx.globalAlpha = 1;

    // board: back plate + tags (front side faces +z)
    const front = dot(sub(eye, d.center), [0, 0, 1]) > 0;
    const m = 0.03;
    const [o0, , o2] = d.outline;
    const xs = [o0[0], o2[0]], ys = [o0[1], o2[1]];
    const plate = [[Math.min(...xs) - m, Math.max(...ys) + m, 0], [Math.max(...xs) + m, Math.max(...ys) + m, 0],
      [Math.max(...xs) + m, Math.min(...ys) - m, 0], [Math.min(...xs) - m, Math.min(...ys) - m, 0]];
    poly(plate, th.board, th.line);
    if (front) for (const t of d.tags) poly(t, th.tag);
    // stand
    line([[d.center[0], Math.min(...ys) - m, -0.01], [d.center[0], fy, -0.01]], th.line, 2);

    // gravity arrow beside the board
    const g0 = [Math.max(...xs) + 0.09, Math.max(...ys), 0];
    const g1 = add(g0, [0, -0.2, 0]);
    line([g0, g1], th.g, 2);
    line([add(g1, [-0.02, 0.035, 0]), g1, add(g1, [0.02, 0.035, 0])], th.g, 2);
    const [gx, gy] = P(add(g1, [0.03, 0.02, 0]));
    ctx.fillStyle = th.g;
    ctx.font = `${12 * px}px system-ui, sans-serif`;
    ctx.fillText('g', gx, gy);

    // camera-centre path: whole recording faint, the part travelled solid, both in the move colours;
    // the last 4 s as a fading halo under the travelled line, the current position as a dot
    const i = idx(st.t), s = d.s, xy = pj.xy;
    const strokeRun = (k0, k1, color, w, alpha) => {
      if (k1 <= k0) return;
      ctx.beginPath();
      ctx.moveTo(xy[2 * k0], xy[2 * k0 + 1]);
      for (let k = k0 + 1; k <= k1; k++) ctx.lineTo(xy[2 * k], xy[2 * k + 1]);
      ctx.strokeStyle = color;
      ctx.lineWidth = w * px;
      ctx.globalAlpha = alpha;
      ctx.stroke();
    };
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    for (const run of d.runs) strokeRun(run.k0, run.k1, th.seg[run.key], 1.2, 0.38);
    const i0 = Math.max(0, i - Math.round(4 * d.hz));
    const step = Math.max(1, Math.round(d.hz / 6));
    for (let k = i0; k < i; k += step) strokeRun(k, Math.min(i, k + step), th.t, 5.5, 0.12 + 0.6 * ((k - i0) / Math.max(1, i - i0)));
    for (const run of d.runs) strokeRun(run.k0, Math.min(run.k1, i), th.seg[run.key], 2.2, 0.95);
    ctx.globalAlpha = 1;

    // rig
    const R_BC = quatToR(s.q_wxyz[i]);
    const D = [[-1, 0, 0], [0, -1, 0], [0, 0, 1]];
    const R_DC = mm(D, R_BC);
    const pc = toD(s.p_C[i]);
    const [fx, fy2, cx, cy] = d.raw.camera.intr8;
    const [iw, ih] = d.raw.camera.image_size;
    const dep = 0.09;
    const corners = [[0, 0], [iw, 0], [iw, ih], [0, ih]].map(([uu, vv]) =>
      add(pc, mv(R_DC, [((uu - cx) / fx) * dep, ((vv - cy) / fy2) * dep, dep])));
    // optical axis to the board plane (B z = 0)
    const zc = mv(R_DC, [0, 0, 1]);
    if (zc[2] < -1e-3) {
      const hit = add(pc, scl(zc, -pc[2] / zc[2]));
      line([pc, hit], th.accent, 1, [4, 4]);
    }
    poly(corners, `rgba(${th.cov}, 0.18)`, th.strong);
    for (const c of corners) line([pc, c], th.strong, 1.2);
    // top edge marker (image row 0)
    const top = add(pc, mv(R_DC, [0, (-cy / fy2) * dep * 1.25, dep]));
    line([corners[0], top, corners[1]], th.strong, 1.2);
    // IMU axes
    const R_DI = mm(R_DC, d.R_CI);
    const pi = add(pc, mv(R_DC, d.p_I_C));
    line([pc, pi], th.line, 2);
    const L = 0.06;
    [th.x, th.y, th.z].forEach((col, a) => line([pi, add(pi, scl([R_DI[0][a], R_DI[1][a], R_DI[2][a]], L))], col, 2.4));
    // current camera position
    ctx.beginPath();
    ctx.arc(xy[2 * i], xy[2 * i + 1], 4 * px, 0, 2 * Math.PI);
    ctx.fillStyle = th.seg[d.key[i]];
    ctx.fill();
    ctx.strokeStyle = th.strong;
    ctx.lineWidth = 1.2 * px;
    ctx.stroke();
    ctx.lineCap = 'butt';
    ctx.lineJoin = 'miter';
  }

  // View camera fitted to the whole path, the board and the gravity arrow (not just the current pose), and the
  // path projected once per view change (orbit, resize, new motion).
  function projection(W, H) {
    const d = st.d;
    const keyV = `${st.az}|${st.el}|${W}|${H}`;
    if (d.proj && d.proj.keyV === keyV) return d.proj;
    if (!d.fitPts) {
      const [o0, , o2] = d.outline;
      const m = 0.03;
      const x0 = Math.min(o0[0], o2[0]) - m, x1 = Math.max(o0[0], o2[0]) + m;
      const y0 = Math.min(o0[1], o2[1]) - m, y1 = Math.max(o0[1], o2[1]) + m;
      const pts = [[x0, y0, 0], [x1, y0, 0], [x0, y1, 0], [x1, y1, 0], [x1 + 0.12, y1, 0], [x1 + 0.12, y1 - 0.22, 0]];
      const stepP = Math.max(1, Math.floor(d.n / 600));
      for (let k = 0; k < d.n; k += stepP) pts.push(d.path[k]);
      pts.push(d.path[d.n - 1]);
      const lo = [0, 1, 2].map((a) => Math.min(...pts.map((p) => p[a])));
      const hi = [0, 1, 2].map((a) => Math.max(...pts.map((p) => p[a])));
      d.fitPts = pts;
      d.fitCtr = scl(add(lo, hi), 0.5);
    }
    const dir = [Math.sin(st.az) * Math.cos(st.el), Math.sin(st.el), Math.cos(st.az) * Math.cos(st.el)];
    const f = scl(dir, -1);
    const r = norm(cross(f, [0, 1, 0]));
    const u = cross(r, f);
    const foc = Math.min(W, H) * 1.3;
    const pad = 0.09; // frustum and IMU axes around the camera centre
    let dist = 0.5;
    for (const p of d.fitPts) {
      const q = sub(p, d.fitCtr);
      const c = dot(q, f);
      dist = Math.max(dist, (foc * (Math.abs(dot(q, r)) + pad)) / (0.46 * W) - c,
        (foc * (Math.abs(dot(q, u)) + pad)) / (0.45 * H) - c, 0.2 - c);
    }
    const eye = add(d.fitCtr, scl(dir, dist));
    const xy = new Float32Array(2 * d.n);
    for (let k = 0; k < d.n; k++) {
      const q = sub(d.path[k], eye);
      const z = Math.max(dot(q, f), 0.05);
      xy[2 * k] = W / 2 + (foc * dot(q, r)) / z;
      xy[2 * k + 1] = H / 2 - (foc * dot(q, u)) / z;
    }
    d.proj = { keyV, eye, f, r, u, foc, xy };
    return d.proj;
  }

  // ---- camera image ----
  function viewcam() {
    const ctx = ccam.getContext('2d');
    fitCanvas(ccam);
    const W = ccam.width, H = ccam.height, th = st.theme, d = st.d;
    ctx.clearRect(0, 0, W, H);
    const [iw, ih] = d.raw.camera.image_size;
    const k = Math.min(W / iw, H / ih);
    const ox = (W - iw * k) / 2, oy = (H - ih * k) / 2;
    const [nx, ny] = d.raw.coverage.fine_grid, cell = d.raw.coverage.fine_px;
    for (let c = 0; c < nx * ny; c++) {
      const t0 = d.first[c];
      if (t0 > st.t) continue;
      const age = st.t - t0;
      ctx.fillStyle = `rgba(${th.cov}, ${age < 1 ? 0.55 - 0.25 * age : 0.3})`;
      ctx.fillRect(ox + (c % nx) * cell * k, oy + Math.floor(c / nx) * cell * k, cell * k + 0.5, cell * k + 0.5);
    }
    // metric grid lines (100 px cells)
    const mp = d.raw.coverage.metric_px;
    ctx.strokeStyle = th.line;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.6;
    for (let x = mp; x < iw; x += mp) { ctx.beginPath(); ctx.moveTo(ox + x * k, oy); ctx.lineTo(ox + x * k, oy + ih * k); ctx.stroke(); }
    for (let y = mp; y < ih; y += mp) { ctx.beginPath(); ctx.moveTo(ox, oy + y * k); ctx.lineTo(ox + iw * k, oy + y * k); ctx.stroke(); }
    ctx.globalAlpha = 1;
    ctx.strokeRect(ox + 0.5, oy + 0.5, iw * k - 1, ih * k - 1);

    const i = idx(st.t);
    const o = d.s.outline_px[i];
    const px = W / ccam.clientWidth;
    if (o && o.every((p) => p)) {
      const order = [0, 4, 1, 5, 2, 6, 3, 7];
      ctx.save();
      ctx.beginPath();
      ctx.rect(ox, oy, iw * k, ih * k);
      ctx.clip();
      ctx.beginPath();
      order.forEach((j, n) => { const x = ox + o[j][0] * k, y = oy + o[j][1] * k; n ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
      ctx.closePath();
      ctx.fillStyle = `rgba(${th.cov}, 0.12)`;
      ctx.fill();
      ctx.strokeStyle = th.strong;
      ctx.lineWidth = 2 * px;
      ctx.stroke();
      ctx.fillStyle = th.t;
      ctx.beginPath();
      ctx.arc(ox + o[0][0] * k, oy + o[0][1] * k, 4 * px, 0, 2 * Math.PI);
      ctx.fill();
      ctx.restore();
    }
    if (d.s.vis_frac[i] < 0.05) {
      ctx.fillStyle = th.text;
      ctx.font = `${12 * px}px system-ui, sans-serif`;
      ctx.textAlign = 'center';
      ctx.fillText('board out of view', W / 2, H / 2);
      ctx.textAlign = 'start';
    }
    let got = 0;
    d.first100.forEach((t0, c) => { if (t0 <= st.t && d.reach[c]) got++; });
    ui.cov.textContent = String(Math.round((100 * got) / Math.max(1, d.nReach)));
  }

  // ---- IMU traces ----
  let imuBg = null;
  const pad = { l: 44, r: 8, t: 6, gap: 14, b: 18 };
  function imuGeom() {
    const W = cimu.width, H = cimu.height, px = W / cimu.clientWidth;
    const l = pad.l * px, r = W - pad.r * px, t = pad.t * px, gap = pad.gap * px, b = H - pad.b * px;
    const h = (b - t - gap) / 2;
    return { W, H, px, l, r, rows: [[t, t + h], [t + h + gap, b]] };
  }
  function imuStatic() {
    fitCanvas(cimu);
    const g = imuGeom(), th = st.theme, d = st.d;
    imuBg = document.createElement('canvas');
    imuBg.width = g.W;
    imuBg.height = g.H;
    const ctx = imuBg.getContext('2d');
    const X = (t) => g.l + ((g.r - g.l) * t) / d.dur;
    ctx.font = `${10 * g.px}px system-ui, sans-serif`;
    // segment bands
    d.segs.forEach((s, k) => {
      if (k % 2) { ctx.fillStyle = th.faint; ctx.fillRect(X(s.t0), g.rows[0][0], X(s.t1) - X(s.t0), g.rows[1][1] - g.rows[0][0]); }
    });
    const rows = [['gyro', d.gmax, 'gyro rad/s'], ['accel', d.amax, 'accel m/s²']];
    rows.forEach(([key, mx, lab], ri) => {
      const [y0, y1] = g.rows[ri];
      const Y = (v) => (y0 + y1) / 2 - ((y1 - y0) / 2) * (v / mx);
      ctx.strokeStyle = th.line;
      ctx.lineWidth = g.px;
      ctx.beginPath(); ctx.moveTo(g.l, Y(0)); ctx.lineTo(g.r, Y(0)); ctx.stroke();
      ctx.fillStyle = th.text;
      ctx.fillText(lab, 2 * g.px, y0 + 10 * g.px);
      ctx.fillText(`±${mx.toFixed(mx < 3 ? 1 : 0)}`, 2 * g.px, y1 - 2 * g.px);
      [th.x, th.y, th.z].forEach((col, a) => {
        ctx.strokeStyle = col;
        ctx.lineWidth = 1.1 * g.px;
        ctx.globalAlpha = 0.9;
        ctx.beginPath();
        const s = d.s[key];
        for (let i = 0; i < d.n; i++) { const x = X(d.s.t[i]), y = Y(s[i][a]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }
        ctx.stroke();
      });
      ctx.globalAlpha = 1;
    });
    ctx.fillStyle = th.text;
    for (let t = 0; t <= d.dur + 1e-6; t += 10) {
      ctx.textAlign = t === 0 ? 'left' : 'center';
      ctx.fillText(`${t} s`, X(t), g.H - 4 * g.px);
    }
    ctx.textAlign = 'left';
    st.dirtyImu = false;
  }
  function imu() {
    if (st.dirtyImu || !imuBg || fitCanvas(cimu)) imuStatic();
    const ctx = cimu.getContext('2d'), g = imuGeom();
    ctx.clearRect(0, 0, g.W, g.H);
    ctx.drawImage(imuBg, 0, 0);
    const x = g.l + ((g.r - g.l) * st.t) / st.d.dur;
    ctx.strokeStyle = st.theme.accent;
    ctx.lineWidth = 2 * g.px;
    ctx.beginPath(); ctx.moveTo(x, g.rows[0][0]); ctx.lineTo(x, g.rows[1][1]); ctx.stroke();
  }
  cimu.addEventListener('click', (e) => {
    if (!st.d) return;
    const rect = cimu.getBoundingClientRect();
    const f = (e.clientX - rect.left - pad.l) / (rect.width - pad.l - pad.r);
    st.t = Math.max(0, Math.min(st.d.dur, f * st.d.dur));
    draw();
  });

  // ---- coverage map: guide motion vs real take (final state) ----
  const covBox = $('covcmp');
  const covData = [];
  function covMap(c, d) {
    const ctx = c.getContext('2d');
    fitCanvas(c);
    const W = c.width, H = c.height, th = st.theme;
    ctx.clearRect(0, 0, W, H);
    const [iw, ih] = d.raw.camera.image_size;
    const k = Math.min(W / iw, H / ih);
    const ox = (W - iw * k) / 2, oy = (H - ih * k) / 2;
    const [nx] = d.raw.coverage.fine_grid, cell = d.raw.coverage.fine_px;
    ctx.fillStyle = `rgba(${th.cov}, 0.35)`;
    d.first.forEach((t0, n) => {
      if (t0 === Infinity) return;
      ctx.fillRect(ox + (n % nx) * cell * k, oy + Math.floor(n / nx) * cell * k, cell * k + 0.5, cell * k + 0.5);
    });
    const [mx] = d.raw.coverage.metric_grid, mp = d.raw.coverage.metric_px, px = W / c.clientWidth;
    let got = 0;
    d.first100.forEach((t0, n) => {
      if (!d.reach[n]) return;
      const x = ox + (n % mx) * mp * k, y = oy + Math.floor(n / mx) * mp * k;
      const w = Math.min(mp, iw - (n % mx) * mp) * k, h = Math.min(mp, ih - Math.floor(n / mx) * mp) * k;
      if (t0 !== Infinity) {
        got++;
        return;
      }
      ctx.strokeStyle = th.x;
      ctx.lineWidth = 1.5 * px;
      ctx.setLineDash([4 * px, 3 * px]);
      ctx.strokeRect(x + 2 * px, y + 2 * px, w - 4 * px, h - 4 * px);
      ctx.setLineDash([]);
    });
    ctx.strokeStyle = th.line;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.6;
    for (let x = mp; x < iw; x += mp) { ctx.beginPath(); ctx.moveTo(ox + x * k, oy); ctx.lineTo(ox + x * k, oy + ih * k); ctx.stroke(); }
    for (let y = mp; y < ih; y += mp) { ctx.beginPath(); ctx.moveTo(ox, oy + y * k); ctx.lineTo(ox + iw * k, oy + y * k); ctx.stroke(); }
    ctx.globalAlpha = 1;
    ctx.strokeRect(ox + 0.5, oy + 0.5, iw * k - 1, ih * k - 1);
    return Math.round((100 * got) / Math.max(1, d.nReach));
  }
  function drawCov() {
    if (!covBox) return;
    covData.forEach((d, n) => {
      if (!d) return;
      const pct = covMap(covBox.querySelector(`[data-cov="${n}"]`), d);
      covBox.querySelector(`[data-covpct="${n}"]`).textContent = `${pct} %`;
    });
  }
  if (covBox) {
    COVCMP.forEach((id, n) => getData(id).then((d) => { covData[n] = d; drawCov(); }).catch(() => {}));
    covBox.querySelectorAll('[data-covplay]').forEach((b) => b.addEventListener('click', () =>
      bus.dispatchEvent(new CustomEvent('select', { detail: b.dataset.covplay }))));
  }

  function draw() {
    if (!st.d) return;
    view3d();
    viewcam();
    imu();
    const g = segAt(st.t);
    ui.segname.textContent = g.label.replace(/\s+/g, ' ');
    ui.segcue.textContent = g.cue || '';
    ui.scrub.value = String(st.t);
    ui.time.textContent = `${st.t.toFixed(1)} / ${st.d.dur.toFixed(1)} s`;
    const k = st.d.segs.indexOf(g);
    ui.segchips.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(Number(b.dataset.k) === k)));
  }

  function tick(now) {
    if (!st.playing) return;
    const dt = Math.min(0.1, (now - st.last) / 1000);
    st.last = now;
    st.t += dt * st.speed;
    if (st.t >= st.d.dur) st.t = 0;
    draw();
    requestAnimationFrame(tick);
  }
  function setPlaying(on) {
    st.playing = on && !!st.d;
    ui.play.textContent = st.playing ? 'Pause' : 'Play';
    ui.play.setAttribute('aria-label', st.playing ? 'Pause' : 'Play');
    if (st.playing) { st.last = performance.now(); requestAnimationFrame(tick); }
  }
  ui.play.addEventListener('click', () => setPlaying(!st.playing));
  ui.scrub.addEventListener('input', () => { st.t = Number(ui.scrub.value); draw(); });
  ui.speed.addEventListener('change', () => { st.speed = Number(ui.speed.value); });

  // orbit the 3D view
  let drag = null;
  c3d.addEventListener('pointerdown', (e) => { drag = { x: e.clientX, y: e.clientY, az: st.az, el: st.el, type: e.pointerType }; c3d.setPointerCapture(e.pointerId); });
  c3d.addEventListener('pointermove', (e) => {
    if (!drag) return;
    st.az = drag.az - (e.clientX - drag.x) * 0.008;
    if (drag.type === 'mouse') st.el = Math.max(-0.2, Math.min(1.3, drag.el + (e.clientY - drag.y) * 0.006));
    draw();
  });
  const end = () => { drag = null; };
  c3d.addEventListener('pointerup', end);
  c3d.addEventListener('pointercancel', end);
  c3d.addEventListener('dblclick', () => { st.az = 0.75; st.el = 0.32; draw(); });

  bus.addEventListener('select', (e) => {
    if (!chips.has(e.detail)) return;
    load(e.detail);
    root.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  load(mode.first);
}

// ---------- verdict table ----------
const fmt = (x, d = 3) => (x == null ? '–' : Math.abs(x) >= 1e4 || (Math.abs(x) < 1e-3 && x !== 0) ? x.toExponential(1) : Number(x.toPrecision(d)).toString());

function groupCell(v, grp) {
  const fails = grp.params.filter((p) => v.params[p] && !v.params[p].passed);
  if (!fails.length) {
    const r = Math.max(...grp.params.map((p) => v.params[p]?.sigma_ratio_vs_good ?? 0));
    return `<td class="ok" title="all pass; worst σ ${fmt(r, 2)}× the reference">✓</td>`;
  }
  const ratios = fails.map((p) => v.params[p].sigma_ratio_vs_good).filter((x) => x != null);
  const worst = ratios.length ? Math.max(...ratios) : null;
  const letters = [...new Set(fails.flatMap((p) => v.params[p].failed.map((w) => w[0])))].sort().join('');
  const tip = fails.map((p) => `${p}: ${v.params[p].failed.join('; ')}`).join('\n').replace(/"/g, '&quot;');
  return `<td class="bad" title="${tip}"><b>✗ ${fails.map(SHORT).join(', ')}</b><br><span>${letters}${worst != null ? ` · σ ×${fmt(worst, 2)}` : ''}</span></td>`;
}

export async function mountVerdicts(root) {
  await verdictsReady;
  const set = root.dataset.set || 'v3';
  const sets = TABLES[set] || [set];
  const S = SETS[sets[0]];
  const vOfSet = (id) => verdicts[VARIANTS[id]?.set]?.variants?.[id];
  const tbl = root.querySelector('[data-role="table"]');
  const note = root.querySelector('[data-role="note"]');
  const detail = root.querySelector('[data-role="detail"]');
  if (!sets.every((k) => verdicts[k])) {
    note.textContent = 'Twin verdicts are not available yet.';
    return;
  }
  const ph = sets.map((k) => verdicts[k].placeholder).filter(Boolean);
  if (ph.length) note.textContent = ph.join(' ');
  else note.hidden = true;
  const ids = sets.flatMap((k) => SETS[k].ids.filter((id) => verdicts[k].variants?.[id]));
  const head = `<thead><tr><th>Motion</th><th>Verdict</th>${GROUPS.map((g) => `<th>${g.name}</th>`).join('')}</tr></thead>`;
  const rows = ids.map((id) => {
    const v = vOfSet(id);
    const tag = '';
    const name = PLAYABLE.has(id) ? `<button type="button" class="cm-link" data-vid="${id}">${VARIANTS[id].label}</button>${tag}` : `${VARIANTS[id].label}${tag}`;
    if (v.status !== 'judged') return `<tr><th scope="row">${name}</th><td colspan="${GROUPS.length + 1}">pending</td></tr>`;
    const frames = v.n_frames?.[0] ? ` · ${v.n_frames[0]} frames` : '';
    const verdict = v.passed
      ? `<td class="ok"><b>good</b><br><span>σ ≤ ${fmt(worstRatio(v), 2)}×${frames}</span></td>`
      : `<td class="bad"><b>fails</b><br><span>${v.failed_params.length} / 22${frames}</span></td>`;
    return `<tr><th scope="row">${name}</th>${verdict}${GROUPS.map((g) => groupCell(v, g)).join('')}</tr>`;
  });
  tbl.innerHTML = `${head}<tbody>${rows.join('')}</tbody>`;
  tbl.querySelectorAll('.cm-link').forEach((b) => b.addEventListener('click', () => bus.dispatchEvent(new CustomEvent('select', { detail: b.dataset.vid }))));

  const showDetail = (id) => {
    const v = vOfSet(id);
    const title = detail.querySelector('[data-role="dname"]');
    const body = detail.querySelector('[data-role="dtable"]');
    title.textContent = VARIANTS[id]?.label || id;
    if (!v || v.status !== 'judged') { body.innerHTML = '<tbody><tr><td>pending</td></tr></tbody>'; return; }
    const names = GROUPS.flatMap((g) => g.params);
    body.innerHTML = `<thead><tr><th>Parameter</th><th>Unit</th><th>σ</th><th>σ / σ ref</th><th>max |err| / σ</th><th>noise-free |err|</th><th>Result</th></tr></thead><tbody>${
      names.map((p) => {
        const r = v.params[p];
        if (!r) return '';
        const res = r.passed ? 'pass' : r.failed.join('; ');
        return `<tr class="${r.passed ? '' : 'bad'}"><th scope="row">${p}${r.rot_norm_only ? '*' : ''}</th><td>${r.unit || '–'}</td><td>${fmt(r.sigma)}</td><td>${fmt(r.sigma_ratio_vs_good, 2)}</td><td>${fmt(r.z_max, 2)}${r.n_z_over ? ` <small>(${r.n_z_over} of ${Object.keys(r.z_seeds || {}).length || 3} seeds > 3)</small>` : ''}</td><td>${r.nf_err == null ? '–' : fmt(Math.abs(r.nf_err))}</td><td>${res}</td></tr>`;
      }).join('')}</tbody>`;
  };
  bus.addEventListener('variant', (e) => { if (sets.includes(VARIANTS[e.detail]?.set)) showDetail(e.detail); });
  showDetail(S.first);
}
