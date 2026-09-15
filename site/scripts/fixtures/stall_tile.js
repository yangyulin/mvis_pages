// After 6 s, freeze the cam1 tile of whatever rig is showing: picture stops, currentTime stops, play() does nothing.
// The freeze clears only when the page gives the element a new src (the watchdog's recovery path).
(() => {
  const protoSrc = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'src');
  setTimeout(() => {
    const v = [...document.querySelectorAll('#mhTiles video')].find(x => x.dataset.cam === 'cam1');
    if (!v) return;
    const frozen = v.currentTime; window.__stalledAt = performance.now();
    v.playbackRate = 0;
    Object.defineProperty(v, 'currentTime', { configurable: true, get() { return frozen; }, set() {} });
    v.play = () => Promise.resolve();
    Object.defineProperty(v, 'src', { configurable: true, get() { return protoSrc.get.call(this); },
      set(val) { delete v.currentTime; delete v.play; delete v.src; v.playbackRate = 1; window.__recoveredAt = performance.now(); protoSrc.set.call(this, val); } });
  }, 6000);
})();
