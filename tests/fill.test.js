// Run with: node tests/fill.test.js  (pytest runs it too when Node is installed)
const assert = require("assert");
const { floodFill } = require("../web/fill.js");

function canvas(W, H, rgb) {
  const d = new Uint8ClampedArray(W * H * 4);
  for (let i = 0; i < W * H; i++) { d[i * 4] = rgb[0]; d[i * 4 + 1] = rgb[1]; d[i * 4 + 2] = rgb[2]; d[i * 4 + 3] = 255; }
  return d;
}
const px = (d, W, x, y) => Array.from(d.slice((y * W + x) * 4, (y * W + x) * 4 + 3));
const set = (d, W, x, y, rgb) => { d.set([...rgb, 255], (y * W + x) * 4); };

// fills a whole empty canvas
{
  const W = 20, H = 10, d = canvas(W, H, [255, 255, 255]);
  assert.strictEqual(floodFill(d, W, H, 3, 3, [255, 0, 0], 48), W * H);
  assert.deepStrictEqual(px(d, W, 19, 9), [255, 0, 0]);
}
// stops at a wall
{
  const W = 20, H = 10, d = canvas(W, H, [255, 255, 255]);
  for (let y = 0; y < H; y++) set(d, W, 10, y, [0, 0, 0]);
  const n = floodFill(d, W, H, 2, 5, [0, 0, 255], 48);
  assert.strictEqual(n, 10 * H);
  assert.deepStrictEqual(px(d, W, 15, 5), [255, 255, 255]);
  assert.deepStrictEqual(px(d, W, 10, 5), [0, 0, 0]);
}
// a closed shape is filled inside only, including concave bits
{
  const W = 30, H = 30, d = canvas(W, H, [255, 255, 255]);
  for (let i = 5; i <= 24; i++) { set(d, W, i, 5, [0, 0, 0]); set(d, W, i, 24, [0, 0, 0]); set(d, W, 5, i, [0, 0, 0]); set(d, W, 24, i, [0, 0, 0]); }
  const n = floodFill(d, W, H, 15, 15, [0, 255, 0], 48);
  assert.strictEqual(n, 18 * 18);
  assert.deepStrictEqual(px(d, W, 1, 1), [255, 255, 255]);
}
// same colour: nothing to do; outside: nothing to do
{
  const W = 5, H = 5, d = canvas(W, H, [10, 20, 30]);
  assert.strictEqual(floodFill(d, W, H, 1, 1, [10, 20, 30], 48), 0);
  assert.strictEqual(floodFill(d, W, H, 9, 9, [1, 2, 3], 48), 0);
}
// tolerance (96, as in app.js) covers light anti-aliasing but not a different colour
{
  const W = 10, H = 1, d = canvas(W, H, [255, 255, 255]);
  set(d, W, 4, 0, [235, 235, 235]);    // light grey: within tolerance
  set(d, W, 7, 0, [100, 100, 100]);    // dark: a wall
  floodFill(d, W, H, 0, 0, [255, 0, 0], 96);
  assert.deepStrictEqual(px(d, W, 4, 0), [255, 0, 0]);
  assert.deepStrictEqual(px(d, W, 8, 0), [255, 255, 255]);
}
console.log("fill ok");
