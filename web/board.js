"use strict";
/* The drawing model shared by the drawer and by everybody who watches: a list of finished
   operations plus the stroke being drawn, changed only through small events. The drawer
   applies its own events and streams them to the server; the viewers apply the same events in
   the same order, so both sides always hold the same picture.

   Events (see strokes.py for the server-side checks):
     {e:"op", op}        a finished operation at once (flood fill, wipe: op.k "f" / "x")
     {e:"begin", op}     a stroke or shape starts (op.k "s" with its first point / "sh")
     {e:"pt", p:[[x,y]]} more points for the current stroke
     {e:"sh", b:[x,y]}   the current shape's second corner moved
     {e:"end", b?}       the stroke or shape is finished
     {e:"undo"} {e:"redo"}
   apply() returns what the renderer has to do, or null when nothing changed. */
(function (root) {
  const clone = (o) => JSON.parse(JSON.stringify(o));

  class Board {
    constructor() { this.reset(); }

    reset() { this.ops = []; this.undone = []; this.cur = null; }

    apply(ev) {
      switch (ev && ev.e) {
        case "op":
          this.ops.push(clone(ev.op)); this.undone = [];
          return { r: "op", op: ev.op };
        case "begin":
          this.cur = clone(ev.op);
          return { r: "begin" };
        case "pt": {
          if (!this.cur || this.cur.k !== "s") return null;
          const from = this.cur.p.length - 1;
          for (const p of ev.p) this.cur.p.push(p);
          return { r: "seg", from };
        }
        case "sh":
          if (!this.cur || this.cur.k !== "sh") return null;
          this.cur.b = ev.b;
          return { r: "preview" };
        case "end": {
          if (!this.cur) return null;
          if (ev.b && this.cur.k === "sh") this.cur.b = ev.b;
          const op = this.cur;
          this.cur = null; this.ops.push(op); this.undone = [];
          return { r: "end", op };
        }
        case "undo":
          if (!this.ops.length) return null;
          this.undone.push(this.ops.pop());
          return { r: "redraw" };
        case "redo":
          if (!this.undone.length) return null;
          this.ops.push(this.undone.pop());
          return { r: "redraw" };
        default:
          return null;
      }
    }
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { Board };
  else root.Board = Board;
})(typeof window !== "undefined" ? window : globalThis);
