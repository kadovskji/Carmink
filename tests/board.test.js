// Run with: node tests/board.test.js  (pytest runs it too when Node is installed)
const assert = require("assert");
const { Board } = require("../web/board.js");

const pen = (p) => ({ k: "s", c: "#000000", w: 7, p: [p] });
const shape = { k: "sh", t: "rect", f: false, c: "#ff0000", w: 7, a: [0, 0], b: [0, 0] };

// a scripted drawing session, as the drawer's app would emit it
const session = [
  { e: "begin", op: pen([1, 1]) }, { e: "pt", p: [[2, 2], [3, 3]] }, { e: "pt", p: [[4, 4]] }, { e: "end" },
  { e: "op", op: { k: "f", c: "#00ff00", x: 10, y: 10 } },
  { e: "begin", op: shape }, { e: "sh", b: [5, 5] }, { e: "sh", b: [9, 9] }, { e: "end", b: [20, 30] },
  { e: "undo" }, { e: "undo" }, { e: "redo" },
  { e: "begin", op: pen([7, 7]) }, { e: "end" },                // a new stroke clears the redo stack
  { e: "redo" },                                               // nothing to redo: no-op
  { e: "op", op: { k: "x" } },
];

const a = new Board();
const results = session.map((ev) => a.apply(ev));
assert.deepStrictEqual(results.map((r) => r && r.r),
  ["begin", "seg", "seg", "end", "op", "begin", "preview", "preview", "end", "redraw", "redraw", "redraw",
   "begin", "end", null, "op"]);
assert.strictEqual(results[1].from, 0);            // the segment to draw starts at the last known point
assert.strictEqual(results[2].from, 2);

// a viewer who replays the same events ends up with the same picture
const b = new Board();
session.forEach((ev) => b.apply(JSON.parse(JSON.stringify(ev))));
assert.deepStrictEqual(b.ops, a.ops);
assert.deepStrictEqual(b.undone, a.undone);
assert.deepStrictEqual(a.ops.map((o) => o.k), ["s", "f", "s", "x"]);   // wipe is an op like any other
assert.deepStrictEqual(a.ops[0].p, [[1, 1], [2, 2], [3, 3], [4, 4]]);

// the shape keeps the corner given with "end"
const c = new Board();
[{ e: "begin", op: shape }, { e: "end", b: [20, 30] }].forEach((ev) => c.apply(ev));
assert.deepStrictEqual(c.ops[0].b, [20, 30]);

// stray or unknown events are ignored
const d = new Board();
for (const ev of [{ e: "pt", p: [[1, 1]] }, { e: "sh", b: [1, 1] }, { e: "end" }, { e: "undo" }, { e: "zzz" }, null, {}]) {
  assert.strictEqual(d.apply(ev), null);
}
assert.deepStrictEqual(d.ops, []);

// the board does not keep references to the events it was given
const op = pen([1, 1]);
const e = new Board();
e.apply({ e: "begin", op });
op.p.push([99, 99]);
assert.deepStrictEqual(e.cur.p, [[1, 1]]);

console.log("board tests passed");
