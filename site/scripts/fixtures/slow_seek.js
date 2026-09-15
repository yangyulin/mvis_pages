// Slow-decoder simulation for every companion video (all videos except the hero #mhVideo).
// Seek latency = 40 ms + LAT_PER_S * seconds decoded from the previous keyframe; KEYINT from window flag.
(() => {
  const KEYINT = +(new URLSearchParams(location.search).get('keyint') || 8.333);
  const PER_S = +(new URLSearchParams(location.search).get('perS') || 90);
  const desc = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'currentTime');
  const seekDesc = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'seeking');
  const pend = new WeakMap();
  window.__simSeeks = 0;
  Object.defineProperty(HTMLMediaElement.prototype, 'seeking', { configurable: true,
    get() { return pend.has(this) ? true : seekDesc.get.call(this); } });
  Object.defineProperty(HTMLMediaElement.prototype, 'currentTime', { configurable: true,
    get() { return desc.get.call(this); },
    set(t) {
      if (this.id === 'mhVideo') return desc.set.call(this, t);
      const key = Math.floor(t / KEYINT) * KEYINT, lat = 40 + PER_S * (t - key);
      const old = pend.get(this); if (old) clearTimeout(old.timer);
      window.__simSeeks++;
      const rate = this.playbackRate; this.__savedRate = old ? this.__savedRate : rate;
      this.playbackRate = 0.0625;
      const timer = setTimeout(() => { pend.delete(this); desc.set.call(this, t); this.dispatchEvent(new Event('seeked')); this.playbackRate = 1; }, lat);
      pend.set(this, { timer });
    } });
})();
