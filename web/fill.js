/* Scanline flood fill on an RGBA array (ImageData.data). Kept apart from app.js so it can be tested in Node. */
(function (root) {
  "use strict";

  /**
   * Paints with `rgb` the region around (x0, y0) made of pixels close to the clicked one.
   * `tol` is the max sum of the channel differences, so anti-aliased edges are covered too.
   * Returns the number of pixels painted.
   */
  function floodFill(d, W, H, x0, y0, rgb, tol) {
    if (x0 < 0 || y0 < 0 || x0 >= W || y0 >= H) return 0;
    const base = (y0 * W + x0) * 4;
    const tr = d[base], tg = d[base + 1], tb = d[base + 2];
    if (tr === rgb[0] && tg === rgb[1] && tb === rgb[2]) return 0;
    const seen = new Uint8Array(W * H);
    const ok = (x, y) => {
      const k = y * W + x;
      if (seen[k]) return false;
      const i = k * 4;
      return Math.abs(d[i] - tr) + Math.abs(d[i + 1] - tg) + Math.abs(d[i + 2] - tb) <= tol;
    };
    const stack = [x0, y0];
    let painted = 0;
    while (stack.length) {
      const y = stack.pop(), x = stack.pop();
      if (!ok(x, y)) continue;
      let l = x, r = x;
      while (l > 0 && ok(l - 1, y)) l--;
      while (r < W - 1 && ok(r + 1, y)) r++;
      for (let i = l; i <= r; i++) {
        const k = y * W + i;
        seen[k] = 1;
        d[k * 4] = rgb[0]; d[k * 4 + 1] = rgb[1]; d[k * 4 + 2] = rgb[2]; d[k * 4 + 3] = 255;
      }
      painted += r - l + 1;
      for (const ny of [y - 1, y + 1]) {
        if (ny < 0 || ny >= H) continue;
        let inSpan = false;
        for (let i = l; i <= r; i++) {
          if (ok(i, ny)) { if (!inSpan) { stack.push(i, ny); inSpan = true; } }
          else inSpan = false;
        }
      }
    }
    return painted;
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { floodFill };
  else root.floodFill = floodFill;
})(typeof window !== "undefined" ? window : globalThis);
