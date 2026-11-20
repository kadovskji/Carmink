"use strict";
/* Carmink Mini App: the drawer's canvas, the word picker and the live viewer for everybody else.
   It only talks to /api/* (see webserver.py); the server owns every rule and every timer. */
(() => {
  const tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    try { tg.disableVerticalSwipes(); } catch (e) { /* older clients */ }
  }
  const initData = (tg && tg.initData) || "";
  const $ = (id) => document.getElementById(id);

  // ------------------------------------------------------------------ texts
  const I18N = {
    it: {
      none: "Nessuna partita in corso in questo gruppo.",
      lobby: "Le iscrizioni sono aperte: scrivete /join nel gruppo.",
      unauth: "Apri Carmink dal pulsante nel gruppo.",
      next: "Prossimo disegnatore: {name}. Si comincia tra {s}s",
      nextYou: "Tocca a te! Prepara la matita: {s}s",
      choosingOther: "{name} sta scegliendo la parola… {s}s",
      pick: "Scegli la parola",
      diff: ["Facile", "Media", "Difficile"],
      startOther: "{name} sta per iniziare a disegnare…",
      startYou: "Inizia a disegnare entro {s}s: il tempo parte dal primo tratto",
      draw: "Disegna:",
      watching: "{name} sta disegnando. Scrivi la risposta nella chat!",
      nohint: "Nessun suggerimento (potrebbero arrivare)",
      timeUp: "Round concluso: guarda la chat.",
      skipConfirm: "Saltare il tuo turno?",
      wipeConfirm: "Cancellare tutta la tela?",
      round: "Round {n}/{total}",
    },
    en: {
      none: "No match running in this group.",
      lobby: "Sign-ups are open: type /join in the group.",
      unauth: "Open Carmink from the button in the group.",
      next: "Next drawer: {name}. Starting in {s}s",
      nextYou: "It's your turn! Get ready: {s}s",
      choosingOther: "{name} is picking a word… {s}s",
      pick: "Pick a word",
      diff: ["Easy", "Medium", "Hard"],
      startOther: "{name} is about to start drawing…",
      startYou: "Start drawing within {s}s: the clock starts at your first stroke",
      draw: "Draw:",
      watching: "{name} is drawing. Type your answer in the chat!",
      nohint: "No hint yet (some may come)",
      timeUp: "Round over: check the chat.",
      skipConfirm: "Skip your turn?",
      wipeConfirm: "Wipe the whole canvas?",
      round: "Round {n}/{total}",
    },
  };
  let lang = "it";
  const t = (key, vars) => {
    let s = (I18N[lang] || I18N.it)[key];
    if (s === undefined) s = I18N.it[key];
    if (typeof s === "string" && vars) for (const k in vars) s = s.replace("{" + k + "}", vars[k]);
    return s;
  };
  const ICON = { objects: "🪑", living: "🐾", actions: "🎭", custom: "✏️" };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ------------------------------------------------------------------ server state
  let st = { phase: "none" };
  let endsAt = 0;
  let turnKey = null;
  let startSent = false;
  let lastSnap = -1;
  let viewUrl = null;
  let msgFn = null;
  let choicesKey = "";

  async function api(path, method, body) {
    const headers = { Authorization: "tma " + initData };
    let payload;
    if (body instanceof Blob) { headers["Content-Type"] = "image/jpeg"; payload = body; }
    else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
    return fetch("/api/" + path, { method: method || "GET", headers, body: payload });
  }

  async function refresh() {
    try {
      const res = await api("state");
      if (res.ok) { st = await res.json(); onState(); }
      else if (res.status === 401 || res.status === 400) { st = { phase: "none", unauth: true }; onState(); }
    } catch (e) { /* offline for a moment: keep trying */ }
  }
  function poll() { refresh().finally(() => setTimeout(poll, 1000)); }

  // ------------------------------------------------------------------ rendering
  const secs = () => Math.max(0, Math.ceil((endsAt - performance.now()) / 1000));
  const show = (id, on) => { $(id).hidden = !on; };

  function onState() {
    if (st.lang) lang = st.lang;
    endsAt = st.ends_in != null ? performance.now() + st.ends_in * 1000 : 0;
    const key = st.turn != null ? String(st.turn) : null;
    if (key !== turnKey) {
      turnKey = key; resetCanvas(); startSent = false; lastSnap = -1;
      $("view").removeAttribute("src");
    }

    const phase = st.phase, drawer = st.role === "drawer";
    const canvasOn = drawer && (phase === "starting" || phase === "drawing");
    const viewOn = !drawer && phase === "drawing";
    show("choose", drawer && phase === "choosing");
    show("board", canvasOn || viewOn);
    show("tools", canvasOn);
    document.body.classList.toggle("has-tools", canvasOn);
    show("cv", drawer);
    show("view", !drawer);
    show("msg", !(canvasOn || viewOn || (drawer && phase === "choosing")));
    $("info").textContent = st.turn ? t("round", { n: st.turn, total: st.turns }) : "Carmink";

    msgFn = null;
    if (st.unauth) msgFn = () => t("unauth");
    else if (phase === "none") msgFn = () => t("none");
    else if (phase === "lobby") msgFn = () => t("lobby");
    else if (phase === "break") {
      msgFn = drawer ? () => t("nextYou", { s: secs() }) : () => t("next", { name: st.drawer, s: secs() });
    } else if (phase === "choosing" && !drawer) msgFn = () => t("choosingOther", { name: st.drawer, s: secs() });
    else if (phase === "starting" && !drawer) msgFn = () => t("startOther", { name: st.drawer });
    else if (phase === "done") msgFn = () => t("timeUp");

    if (drawer && phase === "choosing") renderChoices();
    if (canvasOn || viewOn) renderBoard(drawer, phase);
    if (viewOn && st.snap !== lastSnap) { lastSnap = st.snap; loadSnapshot(); }
    tick();
  }

  function renderChoices() {
    const key = JSON.stringify(st.choices);
    if (key === choicesKey) return;
    choicesKey = key;
    $("choose-title").textContent = t("pick");
    $("choices").innerHTML = st.choices.map((c) =>
      `<button data-i="${c.i}"><span>${ICON[c.cat] || ""} ${esc(c.word)}</span>` +
      `<small>${"★".repeat(c.diff)}${"☆".repeat(3 - c.diff)} ${t("diff")[c.diff - 1]}</small></button>`).join("");
  }
  $("choices").addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    choicesKey = "";
    await api("choose", "POST", { index: Number(b.dataset.i) });
    await refresh();
  });

  function renderBoard(drawer, phase) {
    const w = $("word");
    if (drawer) {
      w.innerHTML = `${t("draw")} <b>${esc(st.word || "")}</b>` + (st.mask ? `<br><code>${esc(st.mask)}</code>` : "");
      const h = $("hint");
      h.textContent = `💡 ${st.hints || 0}/${st.hints_max || 0}`;
      h.disabled = phase !== "drawing" || (st.hints || 0) >= (st.hints_max || 0);
      h.title = `-${st.penalty || 20}%`;
      $("skip").disabled = false;
    } else {
      w.innerHTML = st.mask ? `<code>${esc(st.mask)}</code>` : `${ICON[st.cat] || ""} <small>${t("nohint")}</small>`;
    }
  }

  async function loadSnapshot() {
    try {
      const res = await api("snapshot.jpg");
      if (res.status !== 200) return;
      const url = URL.createObjectURL(await res.blob());
      $("view").src = url;
      if (viewUrl) URL.revokeObjectURL(viewUrl);
      viewUrl = url;
    } catch (e) { /* next poll retries */ }
  }

  function tick() {
    $("clock").textContent = endsAt ? String(secs()) : "";
    if (msgFn) $("msg").textContent = msgFn();
    if (st.role === "drawer" && st.phase === "starting") {
      $("info").textContent = t("startYou", { s: secs() });
    }
  }
  setInterval(tick, 250);

  // ------------------------------------------------------------------ canvas
  const W = 800, H = 600;
  const cv = $("cv");
  const ctx = cv.getContext("2d", { willReadFrequently: true });
  const COLORS = ["#000000", "#7f7f7f", "#c3c3c3", "#ffffff", "#880015", "#ed1c24", "#ff7f27", "#fff200",
    "#22b14c", "#b5e61d", "#00a2e8", "#3f48cc", "#a349a4", "#ffaec9", "#b97a57", "#ffc90e"];
  const SIZES = [3, 7, 14, 26];
  let ops = [], redoStack = [], cur = null;
  let tool = "pen", color = "#000000", size = 7;
  let dirty = false;

  const hexRgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));

  function white() { ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, W, H); }

  function drawOp(op) {
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.strokeStyle = op.c; ctx.fillStyle = op.c; ctx.lineWidth = op.w;
    if (op.k === "s") {
      const p = op.p;
      ctx.beginPath();
      if (p.length === 1) { ctx.arc(p[0][0], p[0][1], op.w / 2, 0, 2 * Math.PI); ctx.fill(); return; }
      ctx.moveTo(p[0][0], p[0][1]);
      for (let i = 1; i < p.length; i++) ctx.lineTo(p[i][0], p[i][1]);
      ctx.stroke();
    } else if (op.k === "sh") {
      const [x0, y0] = op.a, [x1, y1] = op.b;
      ctx.beginPath();
      if (op.t === "circle") ctx.ellipse((x0 + x1) / 2, (y0 + y1) / 2, Math.abs(x1 - x0) / 2, Math.abs(y1 - y0) / 2, 0, 0, 2 * Math.PI);
      else ctx.rect(Math.min(x0, x1), Math.min(y0, y1), Math.abs(x1 - x0), Math.abs(y1 - y0));
      if (op.f) ctx.fill(); else ctx.stroke();
    } else if (op.k === "f") {
      const img = ctx.getImageData(0, 0, W, H);
      if (window.floodFill(img.data, W, H, op.x, op.y, hexRgb(op.c), 96)) ctx.putImageData(img, 0, 0);
    }
  }

  function redraw(preview) {
    white();
    for (const op of ops) { if (op.k === "x") white(); else drawOp(op); }
    if (preview) drawOp(preview);
  }

  function resetCanvas() { ops = []; redoStack = []; cur = null; dirty = false; white(); updateUndo(); }

  function point(e) {
    const r = cv.getBoundingClientRect();
    return [Math.max(0, Math.min(W, (e.clientX - r.left) * W / r.width)),
            Math.max(0, Math.min(H, (e.clientY - r.top) * H / r.height))];
  }

  function canDraw() { return st.role === "drawer" && (st.phase === "starting" || st.phase === "drawing"); }

  function commit(op) { ops.push(op); redoStack = []; dirty = true; updateUndo(); queueUpload(); }

  cv.addEventListener("pointerdown", (e) => {
    if (!canDraw()) return;
    e.preventDefault();
    try { cv.setPointerCapture(e.pointerId); } catch (err) { /* synthetic or lost pointer */ }
    if (!startSent && st.phase === "starting") {
      startSent = true;
      api("start", "POST").then((r) => { if (!r.ok) startSent = false; }).catch(() => { startSent = false; });
    }
    const p = point(e);
    if (tool === "fill") { commit({ k: "f", c: color, x: Math.floor(p[0]), y: Math.floor(p[1]) }); redraw(); return; }
    if (tool === "pen" || tool === "eraser") {
      cur = { k: "s", c: tool === "eraser" ? "#ffffff" : color, w: tool === "eraser" ? size * 2 : size, p: [p] };
      drawOp(cur);
    } else {
      const [shape, mode] = tool.split("-");
      cur = { k: "sh", t: shape, f: mode === "f", c: color, w: size, a: p, b: p };
    }
  });

  cv.addEventListener("pointermove", (e) => {
    if (!cur) return;
    e.preventDefault();
    let events = e.getCoalescedEvents ? e.getCoalescedEvents() : [];
    if (!events.length) events = [e];     // not supported, or synthetic event
    for (const ev of events) {
      const p = point(ev);
      if (cur.k === "s") {
        const last = cur.p[cur.p.length - 1];
        cur.p.push(p);
        ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.strokeStyle = cur.c; ctx.lineWidth = cur.w;
        ctx.beginPath(); ctx.moveTo(last[0], last[1]); ctx.lineTo(p[0], p[1]); ctx.stroke();
      } else { cur.b = p; }
    }
    if (cur.k === "sh") redraw(cur);
  });

  function endStroke() {
    if (!cur) return;
    const op = cur; cur = null;
    commit(op);
    if (op.k === "sh") redraw();
  }
  cv.addEventListener("pointerup", endStroke);
  cv.addEventListener("pointercancel", endStroke);

  // ------------------------------------------------------------------ buttons
  function updateUndo() { $("undo").disabled = !ops.length; $("redo").disabled = !redoStack.length; }

  $("undo").addEventListener("click", () => { if (ops.length) { redoStack.push(ops.pop()); redraw(); dirty = true; updateUndo(); queueUpload(); } });
  $("redo").addEventListener("click", () => { if (redoStack.length) { ops.push(redoStack.pop()); redraw(); dirty = true; updateUndo(); queueUpload(); } });

  const confirmBox = (text, yes) => {
    if (tg && tg.showConfirm) tg.showConfirm(text, (ok) => ok && yes());
    else if (window.confirm(text)) yes();
  };
  $("wipe").addEventListener("click", () => confirmBox(t("wipeConfirm"), () => { commit({ k: "x" }); redraw(); }));
  $("skip").addEventListener("click", () => confirmBox(t("skipConfirm"), async () => { await api("skip", "POST"); refresh(); }));
  $("hint").addEventListener("click", async () => { $("hint").disabled = true; await api("hint", "POST"); refresh(); });

  function pick(container, selector, handler) {
    container.addEventListener("click", (e) => { const b = e.target.closest(selector); if (b) handler(b); });
  }
  pick($("row-tools"), "button[data-tool]", (b) => {
    tool = b.dataset.tool;
    document.querySelectorAll("#row-tools button").forEach((x) => x.classList.toggle("on", x === b));
  });
  $("row-colors").innerHTML = COLORS.map((c) => `<button class="swatch" data-c="${c}" style="background:${c}"></button>`).join("");
  pick($("row-colors"), ".swatch", (b) => {
    color = b.dataset.c;
    if (tool === "eraser") selectTool("pen");
    document.querySelectorAll(".swatch").forEach((x) => x.classList.toggle("on", x === b));
  });
  $("sizes").innerHTML = SIZES.map((s) => `<button class="dot" data-s="${s}"><i style="width:${Math.max(4, s * .7)}px;height:${Math.max(4, s * .7)}px"></i></button>`).join("");
  pick($("sizes"), ".dot", (b) => {
    size = Number(b.dataset.s);
    document.querySelectorAll(".dot").forEach((x) => x.classList.toggle("on", x === b));
  });
  function selectTool(name) { document.querySelector(`#row-tools [data-tool="${name}"]`).click(); }
  selectTool("pen");
  document.querySelector(`.swatch[data-c="${color}"]`).classList.add("on");
  document.querySelector(`.dot[data-s="${size}"]`).classList.add("on");

  // ------------------------------------------------------------------ pictures for the chat and the viewers
  let uploading = false, lastUpload = 0;
  function queueUpload() { if (Date.now() - lastUpload > 1000) upload(); }
  async function upload() {
    if (uploading || !dirty || st.phase !== "drawing" || st.role !== "drawer") return;
    uploading = true;
    dirty = false;
    try {
      const blob = await new Promise((resolve) => cv.toBlob(resolve, "image/jpeg", 0.72));
      const res = await api("snapshot", "POST", blob);
      if (!res.ok && res.status !== 409) dirty = true;
      if (res.status === 409) { const j = await res.json().catch(() => ({})); if (j.error === "too_fast") dirty = true; }
    } catch (e) { dirty = true; }
    lastUpload = Date.now();
    uploading = false;
  }
  setInterval(upload, 1500);

  resetCanvas();
  poll();
})();
