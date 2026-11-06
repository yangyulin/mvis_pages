window.mvisProgress = window.mvisProgress || function (id, s) {
  var gd = document.getElementById(id);
  var strip = document.querySelector('.mvis-progress[data-plot="' + id + '"]');
  if (!gd || !strip) return;
  var btn = strip.querySelector('button'), rng = strip.querySelector('input');
  var lab = strip.querySelector('.mvis-progress-label');
  var pick = strip.querySelector('.mvis-progress-cam');
  var n = s.xyz.length, t = s.t, cur = n - 1, playing = false, t0, i0;
  var X = s.xyz.map(function (p) { return p[0]; });
  var Y = s.xyz.map(function (p) { return p[1]; });
  var Z = s.xyz.map(function (p) { return p[2]; });
  var V = s.views || [], sel = 0;
  function label(i) {
    var pct = 100 * (t && t[n - 1] > 0 ? t[i] / t[n - 1] : i / (n - 1));
    var when = t ? t[i].toFixed(1) + ' / ' + t[n - 1].toFixed(1) + ' s \u00b7 ' : '';
    return Math.round(pct) + ' % \u00b7 ' + when + s.unit + ' ' + (i + 1) + ' / ' + n;
  }
  // per-view panel corner pixels (plot_3d._pack_uv: int16 + offsets)
  V.forEach(function (v) {
    var P = v.panel;
    if (!P || !P.uvb) return;
    var bin = atob(P.uvb), u8 = new Uint8Array(bin.length);
    for (var b = 0; b < bin.length; b++) u8[b] = bin.charCodeAt(b);
    P.uvArr = new Int16Array(u8.buffer);
  });
  function uvAt(P, i) { return P.uvArr.subarray(P.uvo[i], P.uvo[i + 1]); }
  // per-view frustum image bytes (plot_3d.add_progress views[k].img)
  V.forEach(function (v) {
    if (!v.img) return;
    var bin = atob(v.img);
    v.pix = new Uint8Array(bin.length);
    for (var b = 0; b < bin.length; b++) v.pix[b] = bin.charCodeAt(b);
  });
  // pose glyph (mirrors plot_3d._glyph_xyz / _image_grid / _cam_pose)
  var HW = 0.6;
  function mul(A, B) {
    var C = [];
    for (var r = 0; r < 3; r++) for (var c = 0; c < 3; c++)
      C.push(A[3 * r] * B[c] + A[3 * r + 1] * B[3 + c] + A[3 * r + 2] * B[6 + c]);
    return C;
  }
  function at(p, R, v, k) {
    return [0, 1, 2].map(function (r) {
      return p[r] + k * (R[3 * r] * v[0] + R[3 * r + 1] * v[1] + R[3 * r + 2] * v[2]);
    });
  }
  function camPose(i) {
    var p = s.xyz[i], R = s.R[i], v = V[sel];
    if (!v || !v.cam) return {p: p, R: R};
    return {p: at(p, R, v.cam.slice(9, 12), 1), R: mul(R, v.cam.slice(0, 9))};
  }
  function nearest(idx, i) {            // position in sorted idx closest to i
    var lo = 0, hi = idx.length - 1;
    while (lo < hi) { var mid = (lo + hi) >> 1; if (idx[mid] < i) lo = mid + 1; else hi = mid; }
    if (lo > 0 && Math.abs(idx[lo - 1] - i) < Math.abs(idx[lo] - i)) lo--;
    return lo;
  }
  function image(i) {
    var v = V[sel], iw = v.iw, ih = v.ih, HH = v.hh;
    var off = (v.img_idx ? nearest(v.img_idx, i) : i) * iw * ih;
    var C = camPose(i), gx = [], gy = [], gz = [], gc = [];
    for (var r = 0; r < ih; r++) {
      var rx = [], ry = [], rz = [], rc = [];
      for (var c = 0; c < iw; c++) {
        var q = at(C.p, C.R, [-HW + 2 * HW * c / (iw - 1), -HH + 2 * HH * r / (ih - 1), 1], s.fr);
        rx.push(q[0]); ry.push(q[1]); rz.push(q[2]); rc.push(v.pix[off + r * iw + c]);
      }
      gx.push(rx); gy.push(ry); gz.push(rz); gc.push(rc);
    }
    Plotly.restyle(gd, {x: [gx], y: [gy], z: [gz], surfacecolor: [gc]}, [s.glyph.image]);
  }
  function glyph(i, xs, ys, zs, idx) {
    var g = s.glyph, p = s.xyz[i], C = camPose(i), HH = V[sel] ? V[sel].hh : 0.4;
    var CORNERS = [[-HW, -HH, 1], [HW, -HH, 1], [HW, HH, 1], [-HW, HH, 1]];
    var UP = [[-0.2, -HH - 0.05, 1], [0, -HH - 0.22, 1], [0.2, -HH - 0.05, 1]];
    function put(pts, trace) {
      xs.push(pts.map(function (q) { return q && q[0]; }));
      ys.push(pts.map(function (q) { return q && q[1]; }));
      zs.push(pts.map(function (q) { return q && q[2]; }));
      idx.push(trace);
    }
    if (g.frustum !== undefined) {
      var c = CORNERS.map(function (v) { return at(C.p, C.R, v, s.fr); });
      var u = UP.map(function (v) { return at(C.p, C.R, v, s.fr); });
      var f = [];
      c.forEach(function (q) { f.push(C.p, q, null); });
      put(f.concat([c[0], c[1], c[2], c[3], c[0], null, u[0], u[1], u[2]]), g.frustum);
      if (g.plane !== undefined) put(c, g.plane);
    }
    if (g.ray !== undefined) {           // optical axis -> plane n.x = d (plot_3d._ray_end)
      var nn = s.plane, dz = [C.R[2], C.R[5], C.R[8]], end = C.p;
      var den = nn[0] * dz[0] + nn[1] * dz[1] + nn[2] * dz[2];
      var num = nn[3] - (nn[0] * C.p[0] + nn[1] * C.p[1] + nn[2] * C.p[2]);
      if (Math.abs(den) > 1e-9 && num / den > 0) end = at(C.p, [1, 0, 0, 0, 1, 0, 0, 0, 1], dz, num / den);
      put([C.p, end], g.ray);
    }
    ['x', 'y', 'z'].forEach(function (a, k) {
      var e = [0, 0, 0]; e[k] = 1;
      put([p, at(p, s.R[i], e, s.ax)], g[a]);
    });
  }
  // board co-visibility (mirrors plot_3d._covis_style)
  var covisNote = document.querySelector('.mvis-panel[data-plot="' + id + '"] .mvis-covis-note');
  function covis(i) {
    if (!s.covis) return;
    var cs = s.covis, col = cs.color.slice(), size = cs.size.slice(), seen = {}, both = 0, any = 0;
    V.forEach(function (v, k) {
      if (!v.ids) return;
      v.ids[i].forEach(function (pid) { (seen[pid] = seen[pid] || []).push(k); });
    });
    Object.keys(seen).forEach(function (pid) {
      var ks = seen[pid];
      if (pid < 0 || pid >= col.length) return;
      any++;
      if (ks.length > 1) { both++; col[pid] = cs.both; size[pid] = 6; }
      else { col[pid] = V[ks[0]].color; size[pid] = 4.5; }
    });
    Plotly.restyle(gd, {'marker.color': [col], 'marker.size': [size]}, [cs.trace]);
    if (covisNote) covisNote.innerHTML = '<span class="mvis-swatch" style="background:' + cs.both
      + '"></span>co-visible now: <b>' + both + '</b> of ' + any + ' detected corners seen by '
      + '\u2265 2 cameras';
  }
  // side panel cards (pose_images.pose_panel): camera view + image coverage
  var aside = document.querySelector('.mvis-panel[data-plot="' + id + '"]');
  var cards = aside ? Array.prototype.slice.call(aside.querySelectorAll('.mvis-card')) : [];
  cards.forEach(function (el) {
    var v = V[+el.dataset.view];
    v.el = {cam: el.querySelector('.mvis-cam'), camNote: el.querySelector('.mvis-cam-note'),
            covNote: el.querySelector('.mvis-cov-note'),
            base: el.querySelector('.mvis-cov-base'), top: el.querySelector('.mvis-cov-top'),
            card: el};
    v.drawn = -1;
    if (V.length > 1) {
      el.addEventListener('click', function () { select(+el.dataset.view); });
      el.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(+el.dataset.view); }
      });
    }
  });
  function fit(cv, P) {
    var dpr = Math.min(2, window.devicePixelRatio || 1), w = cv.clientWidth;
    cv.width = Math.max(1, Math.round(w * dpr));
    cv.height = Math.max(1, Math.round(w * P.h / P.w * dpr));
    var g = cv.getContext('2d'); g.setTransform(cv.width / P.w, 0, 0, cv.height / P.h, 0, 0);
    return g;
  }
  function card(v, i) {
    var P = v.panel, E = v.el;
    if (!P || !E) return;
    if (P.jpg.length) E.cam.src = 'data:image/jpeg;base64,' + P.jpg[nearest(P.jpg_idx, i)];
    E.camNote.textContent = s.unit + ' ' + (i + 1) + (t ? ' \u00b7 t = ' + t[i].toFixed(1) + ' s' : '')
      + ' \u00b7 ' + (uvAt(P, i).length ? (uvAt(P, i).length / 2) + ' corners' : 'no detection used here');
    var gx = P.grid[0], gy = P.grid[1], cw = P.w / gx, ch = P.h / gy, g;
    if (i < v.drawn || v.drawn < 0 || !E.base.width) {   // rewind / first draw: start over
      g = fit(E.base, P); g.fillStyle = '#0F172A'; g.fillRect(0, 0, P.w, P.h);
      g.strokeStyle = 'rgba(148,163,184,0.25)'; g.lineWidth = P.w / 400;
      for (var a = 1; a < gx; a++) { g.beginPath(); g.moveTo(a * cw, 0); g.lineTo(a * cw, P.h); g.stroke(); }
      for (var b = 1; b < gy; b++) { g.beginPath(); g.moveTo(0, b * ch); g.lineTo(P.w, b * ch); g.stroke(); }
      v.seen = {}; v.drawn = -1;
    } else {
      g = E.base.getContext('2d');
    }
    var r = Math.max(1.5, P.w / 260);
    for (var k = v.drawn + 1; k <= i; k++) {
      var uv = uvAt(P, k);
      for (var j = 0; j < uv.length; j += 2) {
        var cx = Math.min(gx - 1, Math.floor(uv[j] / cw)), cy = Math.min(gy - 1, Math.floor(uv[j + 1] / ch));
        if (!v.seen[cx + ',' + cy]) {
          v.seen[cx + ',' + cy] = 1;
          g.fillStyle = 'rgba(56,189,248,0.16)'; g.fillRect(cx * cw, cy * ch, cw, ch);
        }
        g.fillStyle = 'rgba(125,211,252,0.55)';
        g.fillRect(uv[j] - r / 2, uv[j + 1] - r / 2, r, r);
      }
    }
    v.drawn = i;
    var o = fit(E.top, P), cu = uvAt(P, i), rr = Math.max(3, P.w / 110);
    o.fillStyle = '#F59E0B';
    for (var q = 0; q < cu.length; q += 2) { o.beginPath(); o.arc(cu[q], cu[q + 1], rr / 2, 0, 6.2832); o.fill(); }
    E.covNote.textContent = Math.round(P.cov[i]) + ' % of the image \u00b7 ' + P.n[i].toLocaleString() + ' corners';
  }
  function show(i) {
    cur = Math.max(0, Math.min(n - 1, i));
    rng.value = cur; lab.textContent = label(cur);
    var xs = [X.slice(0, cur + 1), [X[cur]]], ys = [Y.slice(0, cur + 1), [Y[cur]]];
    var zs = [Z.slice(0, cur + 1), [Z[cur]]], idx = [s.done, s.cur];
    if (s.glyph) glyph(cur, xs, ys, zs, idx);
    Plotly.restyle(gd, {x: xs, y: ys, z: zs}, idx);
    if (s.glyph && s.glyph.image !== undefined && V[sel] && V[sel].pix) image(cur);
    covis(cur);
    V.forEach(function (v) { card(v, cur); });
  }
  function select(k) {                 // camera shown on the trajectory
    sel = k;
    if (pick) pick.value = String(k);
    cards.forEach(function (el) { el.classList.toggle('is-sel', +el.dataset.view === k); });
    var g = s.glyph, col = V[k].color, tr = [];
    if (g.frustum !== undefined) tr.push(g.frustum);
    if (g.ray !== undefined) tr.push(g.ray);
    if (tr.length) Plotly.restyle(gd, {'line.color': col}, tr);
    if (g.plane !== undefined) Plotly.restyle(gd, {color: col}, [g.plane]);
    if (g.image !== undefined) Plotly.restyle(gd, {visible: !!V[k].pix}, [g.image]);
    show(cur);
  }
  function stop() { playing = false; btn.innerHTML = '&#9654; Play'; }
  function step(ts) {
    if (!playing) return;
    if (t0 === undefined) t0 = ts;
    var f = (ts - t0) / 12000, i = i0;
    if (t && t[n - 1] > 0) {
      var target = t[i0] + f * t[n - 1];
      while (i < n - 1 && t[i + 1] <= target) i++;
    } else {
      i = i0 + Math.floor(f * (n - 1));
    }
    if (i >= n - 1) { show(n - 1); stop(); return; }
    if (i !== cur) show(i);
    requestAnimationFrame(step);
  }
  btn.onclick = function () {
    if (playing) { stop(); return; }
    i0 = cur >= n - 1 ? 0 : cur; t0 = undefined; playing = true;
    btn.innerHTML = '&#10074;&#10074; Pause';
    show(i0); requestAnimationFrame(step);
  };
  rng.oninput = function () { stop(); show(+rng.value); };
  if (pick) pick.onchange = function () { select(+pick.value); };
  if (cards.length) {
    V.forEach(function (v) { card(v, n - 1); });
    window.addEventListener('resize', function () {
      V.forEach(function (v) { v.drawn = -1; card(v, cur); });
    });
  }
  if (covisNote && s.covis) covis(n - 1);
};
