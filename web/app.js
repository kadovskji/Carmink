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
  // read when needed: on some desktop clients the data is not there yet at the very first moment
  const getInit = () => (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || "";
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
      watching: "{name} sta disegnando. Scrivi la risposta qui sotto o nella chat!",
      bkPhraseTitle: "Scrivi una frase da far disegnare",
      bkDescribeTitle: "Descrivi il disegno",
      bkPhrasePh: "La tua frase…",
      bkDescribePh: "La tua descrizione…",
      nohint: "Nessun suggerimento (potrebbero arrivare)",
      timeUp: "Round concluso: guarda la chat.",
      skipConfirm: "Saltare il tuo turno?",
      wipeConfirm: "Cancellare tutta la tela?",
      round: "Round {n}/{total}",
      guessPh: "Scrivi la tua risposta…",
      send: "Invia",
      youGuessed: "✅ Hai indovinato! +{p} punti",
      close: "🔥 Ci sei vicino!",
      rightAtt: "✅ {name} ha indovinato!",
      bkStep: "Passo {n}/{total}",
      bkPhrase: "Frasi iniziali",
      bkWrite: "Scrivi la tua frase qui sotto (o al bot, in privato). {s}s",
      bkDescribe: "Descrivi il disegno qui sotto (o al bot, in privato). {s}s",
      bkWait: "Fatto! Aspettiamo gli altri… {s}s",
      bkOut: "Questo giro guardi: non sei tra i giocatori.",
      bkDone: "✅ Fatto",
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
      watching: "{name} is drawing. Type your answer below or in the chat!",
      bkPhraseTitle: "Write a phrase for the others to draw",
      bkDescribeTitle: "Describe the drawing",
      bkPhrasePh: "Your phrase…",
      bkDescribePh: "Your description…",
      nohint: "No hint yet (some may come)",
      timeUp: "Round over: check the chat.",
      skipConfirm: "Skip your turn?",
      wipeConfirm: "Wipe the whole canvas?",
      round: "Round {n}/{total}",
      guessPh: "Type your answer…",
      send: "Send",
      youGuessed: "✅ You got it! +{p} points",
      close: "🔥 So close!",
      rightAtt: "✅ {name} got it!",
      bkStep: "Pass {n}/{total}",
      bkPhrase: "First phrases",
      bkWrite: "Write your phrase below (or to the bot, in private). {s}s",
      bkDescribe: "Describe the drawing below (or to the bot, in private). {s}s",
      bkWait: "Done! Waiting for the others… {s}s",
      bkOut: "You are only watching: you are not one of the players.",
      bkDone: "✅ Done",
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
  const stash = {};                 // canvases of the fake players of a test match (see onState)
  let stashKey = null, stashTurn = null, stashDraw = false;
  let asUid = null;                 // test match: the fake player the admin is playing now
  let startSent = false;
  let msgFn = null;
  let choicesKey = "";

  async function api(path, method, body) {
    const headers = { Authorization: "tma " + getInit() };
    if (asUid) headers["X-Test-As"] = String(asUid);      // admin test match: act as a fake player
    let payload;
    if (body instanceof Blob) { headers["Content-Type"] = "image/jpeg"; payload = body; }
    else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
    // a request that hangs (a flaky mobile connection) must not stall the polling loops for good
    const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 10000);
    try { return await fetch("/api/" + path, { method: method || "GET", headers, body: payload, signal: ctl.signal }); }
    finally { clearTimeout(timer); }
  }

  async function refresh() {
    try {
      const res = await api("state");
      if (res.ok) { st = await res.json(); onState(); }
      else if (res.status === 401 || res.status === 403 || res.status === 400) { st = { phase: "none", unauth: true }; onState(); }
    } catch (e) { /* offline for a moment: keep trying */ }
  }
  function poll() { refresh().finally(() => setTimeout(poll, st.role === "drawer" && st.phase === "drawing" ? 400 : 1000)); }

  // ------------------------------------------------------------------ rendering
  const secs = () => Math.max(0, Math.ceil((endsAt - performance.now()) / 1000));
  const show = (id, on) => { $(id).hidden = !on; };

  function renderTestBar() {
    const box = $("testbar");
    if (!st.test) { box.hidden = true; return; }
    if (!asUid || !st.test.players.some(p => String(p.id) === String(asUid))) {
      asUid = st.test.players[0].id;
      setTimeout(refresh, 0);                             // reload the state as that player
    }
    if (box.dataset.n !== String(st.test.players.length)) {
      box.dataset.n = String(st.test.players.length);
      box.innerHTML = "🧪 ";
      const sel = document.createElement("select");
      st.test.players.forEach(p => { const o = document.createElement("option"); o.value = p.id; o.textContent = p.name; sel.appendChild(o); });
      sel.addEventListener("change", () => { asUid = sel.value; turnKey = null; refresh(); });
      box.appendChild(sel);
    }
    const sel = box.querySelector("select");
    if (sel && sel.value !== String(asUid)) sel.value = String(asUid);
    box.hidden = false;
  }

  function onState() {
    if (st.lang) lang = st.lang;
    endsAt = st.ends_in != null ? performance.now() + st.ends_in * 1000 : 0;
    renderTestBar();
    const key = st.turn != null ? String(st.turn) + "|" + (asUid || "") : null;
    if (key !== turnKey) {
      // test matches: each fake player keeps its own canvas while the admin plays someone else
      if (stashKey && stashDraw) stash[stashKey] = { ops: clone(board.ops), undone: clone(board.undone),
        evLog: clone(evLog), evSent, dirty, startSent };
      const turnPart = key ? key.split("|")[0] : null;
      if (turnPart !== stashTurn) for (const k of Object.keys(stash)) delete stash[k];
      stashTurn = turnPart; stashKey = key;
      turnKey = key; resetCanvas(); startSent = false; resetLive(); clearAttempts(); bkSubmitting = false;
      const saved = key && stash[key];
      if (saved) {
        board.ops = saved.ops; board.undone = saved.undone; evLog = saved.evLog; evSent = saved.evSent;
        dirty = saved.dirty; startSent = saved.startSent; redraw(); updateUndo();
      }
    }

    const phase = st.phase, drawer = st.role === "drawer";
    const broken = st.mode === "broken", bkDraw = bkDrawNow(), bkText = bkTextNow();
    const bkImg = bkText && !!st.bk.image;
    const canvasOn = (drawer && (phase === "starting" || phase === "drawing")) || bkDraw;
    const viewOn = !drawer && !broken && phase === "drawing";
    $("hint").hidden = broken; $("skip").hidden = broken; $("bkdone").hidden = !broken;
    $("bkdone").textContent = t("bkDone");
    const attOn = st.mode === "classic" && phase === "drawing" && (canvasOn || viewOn);
    // guesses in the Mini App: Classic and Speedrun (a field under the canvas); Broken Canva: the
    // phrases and descriptions, which can also be sent to the bot in private
    const guessOn = (attOn && !drawer && st.in_game) || (st.mode === "speedrun" && viewOn && st.in_game) || bkText;
    show("choose", drawer && phase === "choosing");
    show("board", canvasOn || viewOn || bkText);
    show("stage", !bkText || bkImg);
    show("tools", canvasOn);
    show("attempts", attOn);
    show("guessbar", guessOn && st.me_guessed == null);
    show("mine", guessOn && st.me_guessed != null);
    if (guessOn && st.me_guessed != null) $("mine").textContent = t("youGuessed", { p: st.me_guessed });
    $("send").textContent = t("send");
    document.body.classList.toggle("has-tools", canvasOn);
    document.body.classList.toggle("has-att", attOn && drawer);
    document.body.classList.toggle("has-guess", guessOn);
    show("msg", !(canvasOn || viewOn || bkText || (drawer && phase === "choosing")));
    const inp = $("guess");
    inp.maxLength = bkText ? (st.bk.max || 120) : 60;
    inp.placeholder = bkText ? t(bkImg ? "bkDescribePh" : "bkPhrasePh") : t("guessPh");
    if (bkText) $("word").textContent = t(bkImg ? "bkDescribeTitle" : "bkPhraseTitle");
    if (bkImg) loadGiven();
    if (broken && st.bk) $("info").textContent = st.bk.step ? t("bkStep", { n: st.bk.step, total: st.bk.steps }) : t("bkPhrase");
    else $("info").textContent = st.turn ? t("round", { n: st.turn, total: st.turns }) : "Carmink";

    msgFn = null;
    if (st.unauth) msgFn = () => t("unauth");
    else if (phase === "none") msgFn = () => t("none");
    else if (phase === "lobby") msgFn = () => t("lobby");
    else if (phase === "break") {
      msgFn = drawer ? () => t("nextYou", { s: secs() }) : () => t("next", { name: st.drawer, s: secs() });
    } else if (phase === "choosing" && !drawer) msgFn = () => t("choosingOther", { name: st.drawer, s: secs() });
    else if (phase === "starting" && !drawer) msgFn = () => t("startOther", { name: st.drawer });
    else if (phase === "done") msgFn = () => t("timeUp");
    else if (broken && st.bk && !bkDraw) {
      if (!st.bk.active) msgFn = () => t("bkOut");
      else if (st.bk.done) msgFn = () => t("bkWait", { s: secs() });
      else msgFn = () => t(st.bk.kind === "draw" ? "bkWait" : (phase === "writing" ? "bkWrite" : "bkDescribe"), { s: secs() });
    }

    stashDraw = canvasOn;
    if (drawer && phase === "choosing") renderChoices();
    fitLayout();
    if (st.final && drawer) sendFinal();
    if (bkDraw) renderBkBoard();
    else if (canvasOn || viewOn) renderBoard(drawer, phase);
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

  function bkTextNow() {
    const b = st.mode === "broken" ? st.bk : null;
    return !!(b && (st.phase === "writing" || st.phase === "step") && b.kind === "text" && b.active && !b.done);
  }

  // Broken Canva: the drawing to describe is shown on the canvas (read only)
  let givenKey = null;
  async function loadGiven() {
    if (givenKey === turnKey) return;
    givenKey = turnKey;
    const key = turnKey;
    try {
      const res = await api("bk/given");
      if (!res.ok || res.status === 204) { givenKey = null; return; }
      const url = URL.createObjectURL(await res.blob());
      const img = new Image();
      img.onload = () => {
        if (turnKey === key) { white(); ctx.drawImage(img, 0, 0, W, H); }
        URL.revokeObjectURL(url);
      };
      img.src = url;
    } catch (e) { givenKey = null; }
  }

  function bkDrawNow() {
    const b = st.mode === "broken" ? st.bk : null;
    return !!(b && st.phase === "step" && b.kind === "draw" && b.active && !b.done && b.prompt != null);
  }
  function renderBkBoard() {
    $("word").innerHTML = `${t("draw")} <b>${esc(st.bk.prompt)}</b>`;
  }

  function tick() {
    $("clock").textContent = endsAt ? String(secs()) : "";
    if (bkDrawNow() && endsAt && secs() === 0) bkSend(true);       // time is up: hand the drawing in
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
  const board = new window.Board();         // the shared drawing model (board.js)
  const COLORS = ["#000000", "#7f7f7f", "#c3c3c3", "#ffffff", "#880015", "#ed1c24", "#ff7f27", "#fff200",
    "#22b14c", "#b5e61d", "#00a2e8", "#3f48cc", "#a349a4", "#ffaec9", "#b97a57", "#ffc90e"];
  const SIZES = [3, 7, 14, 26];
  let tool = "pen", color = "#000000", size = 7;
  let dirty = false;

  const hexRgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const clone = (o) => JSON.parse(JSON.stringify(o));
  const r1 = (v) => Math.round(v * 10) / 10;

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

  function drawSeg(op, from) {
    ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.strokeStyle = op.c; ctx.lineWidth = op.w;
    ctx.beginPath(); ctx.moveTo(op.p[from][0], op.p[from][1]);
    for (let i = from + 1; i < op.p.length; i++) ctx.lineTo(op.p[i][0], op.p[i][1]);
    ctx.stroke();
  }

  function redraw() {
    white();
    for (const op of board.ops) { if (op.k === "x") white(); else drawOp(op); }
    if (board.cur) drawOp(board.cur);
  }

  /* Apply events to the model and paint them: strokes incrementally, anything that changes the
     past (undo, shapes, wipe) with one full redraw at the end of the batch. Returns what apply() said. */
  function applyBatch(events) {
    let full = false, preview = false;
    const out = [];
    for (const ev of events) {
      let r = null;
      try { r = board.apply(ev); } catch (e) { r = null; }
      out.push(r);
      if (!r) continue;
      switch (r.r) {
        case "redraw": full = true; break;
        case "op": if (!full) { if (r.op.k === "x") white(); else drawOp(r.op); } break;
        case "begin": if (board.cur.k === "s") { if (!full) drawOp(board.cur); } else preview = true; break;
        case "seg": if (!full) drawSeg(board.cur, r.from); break;
        case "preview": preview = true; break;
        case "end": if (r.op.k === "sh") full = true; preview = false; break;
      }
    }
    if (full || preview) redraw();
    return out;
  }

  // The canvas is as large as the free area allows, 4:3. Done here and not only in CSS because
  // desktop webviews can lack dvh / aspect-ratio, and the window there can be resized freely.
  function fitLayout() {
    const vw = window.innerWidth || document.documentElement.clientWidth;
    const vh = window.innerHeight || document.documentElement.clientHeight;
    document.body.style.height = vh + "px";
    // landscape (iPad, a phone on its side, a desktop window): tools and attempts go to the side, so
    // the canvas can use the whole height
    document.body.classList.toggle("wide", vw >= 520 && vw >= vh * 1.15);
    const stage = $("stage");
    if ($("board").hidden || !stage) return;
    const aw = stage.clientWidth, ah = stage.clientHeight;
    if (aw < 40 || ah < 40) return;
    const w = Math.floor(Math.min(aw, ah * 4 / 3));
    cv.style.width = w + "px";
    cv.style.height = Math.floor(w * 3 / 4) + "px";
  }
  // Telegram's full screen (Bot API 8.0+): a button, so it is the player's choice
  const fsBtn = $("fs");
  function safeTop() {
    const a = (tg && tg.safeAreaInset && tg.safeAreaInset.top) || 0, b = (tg && tg.contentSafeAreaInset && tg.contentSafeAreaInset.top) || 0;
    document.documentElement.style.setProperty("--safe-top", (tg && tg.isFullscreen ? a + b : 0) + "px");
    fitLayout();
  }
  if (tg && tg.requestFullscreen && (!tg.isVersionAtLeast || tg.isVersionAtLeast("8.0"))) {
    fsBtn.hidden = false;
    fsBtn.addEventListener("click", () => {
      try { if (tg.isFullscreen) tg.exitFullscreen(); else tg.requestFullscreen(); } catch (e) { fsBtn.hidden = true; }
    });
    for (const ev of ["fullscreenChanged", "safeAreaChanged", "contentSafeAreaChanged"]) tg.onEvent(ev, safeTop);
  }
  window.addEventListener("resize", fitLayout);
  window.addEventListener("orientationchange", () => setTimeout(fitLayout, 150));
  if (tg && tg.onEvent) tg.onEvent("viewportChanged", fitLayout);
  if (window.ResizeObserver) new ResizeObserver(fitLayout).observe($("stage"));
  document.addEventListener("visibilitychange", () => { if (!document.hidden) { refresh(); fitLayout(); } });

  function resetCanvas() { board.reset(); dirty = false; white(); updateUndo(); }

  function point(e) {
    const r = cv.getBoundingClientRect();
    return [r1(Math.max(0, Math.min(W, (e.clientX - r.left) * W / r.width))),
            r1(Math.max(0, Math.min(H, (e.clientY - r.top) * H / r.height)))];
  }

  function canDraw() {
    return bkDrawNow() || (st.role === "drawer" && (st.phase === "starting" || st.phase === "drawing"));
  }

  // ---- the drawer streams its events to the server, which hands them to everybody else
  // evLog holds every event of the turn; the first evSent are known to the server. Only events that
  // are neither sent nor being sent may still be merged with a new one.
  const BATCH_EVENTS = 400, BATCH_POINTS = 3000, MERGE_POINTS = 400;
  let evSent = 0, evLog = [], sendingEnd = 0, flushing = false, flushGen = 0;
  function emit(ev) {
    if (st.mode === "broken") return;     // Broken Canva: only the finished drawing is sent
    const i = evLog.length - 1, last = evLog[i];
    const open = last && i >= Math.max(evSent, sendingEnd);
    if (open && ev.e === "pt" && last.e === "pt" && last.p.length + ev.p.length <= MERGE_POINTS) last.p = last.p.concat(clone(ev.p));
    else if (open && ev.e === "sh" && last.e === "sh") last.b = ev.b.slice();
    else evLog.push(clone(ev));
  }
  async function flushEvents() {
    if (flushing || !canDraw() || st.mode === "broken" || evSent >= evLog.length) return;
    flushing = true;                      // one request at a time: a second one would race the first
    const gen = flushGen, from = evSent;
    let n = 0, pts = 0;
    while (from + n < evLog.length && n < BATCH_EVENTS && pts < BATCH_POINTS) {
      const e = evLog[from + n]; pts += e.p ? e.p.length : 1; n++;
    }
    sendingEnd = from + n;
    try {
      const res = await api("events", "POST", { from, events: evLog.slice(from, from + n) });
      if (gen !== flushGen) return;       // another turn began meanwhile
      if (res.ok) evSent = from + n;
      else {
        const j = await res.json().catch(() => ({}));
        if (j.error === "gap" && Number.isInteger(j.have) && j.have >= 0 && j.have < evLog.length) evSent = j.have;  // resend from what the server has
        else if (["bad_request", "too_many"].includes(j.error)) evSent = from + n;   // can't be fixed by retrying
      }
    } catch (e) { /* offline for a moment: the same batch is sent again */ }
    finally { if (gen === flushGen) { sendingEnd = 0; flushing = false; } }
  }
  setInterval(flushEvents, 150);

  /* A change made by the drawer: model + canvas + stream. */
  function local(ev, upload) {
    const res = applyBatch([ev]);
    if (!res[0]) return false;
    emit(ev); dirty = true; updateUndo();
    if (upload) queueUpload();
    return true;
  }

  // A stroke can be left open when the "up" never arrives (mouse released outside the window, focus
  // lost, pointer capture refused by a desktop webview): it is closed by any sign that it is over,
  // and a new press closes a stale one instead of being ignored.
  let activeId = null, lastMove = 0, lastPt = null;
  // Apple Pencil: the palm resting on the glass is a touch pointer. While the pencil is in use touches
  // don't draw, and a pencil stroke always wins over a finger stroke that began a moment before.
  let lastPen = 0, activeType = "", activeStart = 0;
  const PALM_MS = 2500;
  const penSeen = (e) => { if (e.pointerType === "pen") lastPen = Date.now(); };
  cv.addEventListener("pointerover", penSeen);
  cv.addEventListener("pointermove", penSeen);                // also the hovering pencil (newer iPads)
  cv.addEventListener("contextmenu", (e) => e.preventDefault());   // a long press must not cancel the stroke
  cv.addEventListener("pointerdown", (e) => {
    if (!canDraw()) return;
    penSeen(e);
    if (e.pointerType === "touch" && Date.now() - lastPen < PALM_MS) return;     // palm
    if (board.cur) {
      const pen = e.pointerType === "pen";
      if (!pen && e.pointerId !== activeId && Date.now() - lastMove < 600) return;    // a second finger
      const palm = pen && activeType === "touch" && Date.now() - activeStart < 1500;
      endStroke();                                                                    // stale stroke
      if (palm) local({ e: "undo" }, true);                                           // ...or a palm
    }
    e.preventDefault();
    activeType = e.pointerType; activeStart = Date.now();
    activeId = e.pointerId; lastMove = Date.now();
    try { cv.setPointerCapture(e.pointerId); } catch (err) { /* synthetic or lost pointer */ }
    if (!startSent && st.phase === "starting") {
      startSent = true;
      api("start", "POST").then((r) => { if (!r.ok) startSent = false; }).catch(() => { startSent = false; });
    }
    const p = lastPt = point(e);
    if (tool === "fill") { local({ e: "op", op: { k: "f", c: color, x: Math.floor(p[0]), y: Math.floor(p[1]) } }, true); return; }
    if (tool === "pen" || tool === "eraser") {
      local({ e: "begin", op: { k: "s", c: tool === "eraser" ? "#ffffff" : color, w: tool === "eraser" ? size * 2 : size, p: [p] } });
    } else {
      const [shape, mode] = tool.split("-");
      local({ e: "begin", op: { k: "sh", t: shape === "circle" ? "circle" : "rect", f: mode === "f", c: color, w: size, a: p, b: p } });
    }
  });

  cv.addEventListener("pointermove", (e) => {
    if (!board.cur || e.pointerId !== activeId) return;
    if (e.pointerType === "mouse" && e.buttons === 0) return endStroke(e);    // released elsewhere
    e.preventDefault();
    lastMove = Date.now();
    let events = e.getCoalescedEvents ? e.getCoalescedEvents() : [];
    if (!events.length) events = [e];     // not supported, or synthetic event
    const pts = events.map(point);
    lastPt = pts[pts.length - 1];
    if (board.cur.k === "s") local({ e: "pt", p: pts });
    else local({ e: "sh", b: pts[pts.length - 1] });
  });

  function endStroke(e) {
    if (!board.cur) return;
    const b = e && /^pointer(up|move|cancel)$/.test(e.type) ? point(e) : (lastPt || board.cur.b);
    local(board.cur.k === "sh" ? { e: "end", b } : { e: "end" }, true);
  }
  const ending = (e) => { if (e.pointerId === activeId) endStroke(e); };
  cv.addEventListener("pointerup", ending);
  cv.addEventListener("pointercancel", ending);
  // only the stroke that owns the pointer: with quick strokes the "lost capture" of the previous
  // one arrives after the next pen-down and would end the new stroke on its first point
  cv.addEventListener("lostpointercapture", (e) => { if (e.pointerId === activeId) endStroke(); });
  window.addEventListener("pointerup", ending);            // released outside the canvas
  window.addEventListener("blur", () => endStroke());

  // ------------------------------------------------------------------ buttons
  function updateUndo() { $("undo").disabled = !board.ops.length; $("redo").disabled = !board.undone.length; }

  $("undo").addEventListener("click", () => { if (canDraw()) local({ e: "undo" }, true); });
  $("redo").addEventListener("click", () => { if (canDraw()) local({ e: "redo" }, true); });

  const confirmBox = (text, yes) => {
    if (tg && tg.showConfirm) tg.showConfirm(text, (ok) => ok && yes());
    else if (window.confirm(text)) yes();
  };
  $("wipe").addEventListener("click", () => confirmBox(t("wipeConfirm"), () => { if (canDraw()) local({ e: "op", op: { k: "x" } }, true); }));
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

  // ------------------------------------------------------------------ live view and guesses
  let vTurn = null, vSince = 0, vAtt = 0;
  const myClose = new Set();
  function resetLive() {
    vTurn = null; vSince = 0; vAtt = 0;
    evSent = 0; evLog = []; sendingEnd = 0; flushing = false; flushGen++; myClose.clear();
  }

  function clearAttempts() { $("attempts").textContent = ""; }
  function addAttempt(i, a) {
    const list = $("attempts");
    const stick = list.scrollTop + list.clientHeight >= list.scrollHeight - 12;
    const d = document.createElement("div");
    d.className = "att" + (a.r ? " right" : "");
    if (a.r) d.textContent = t("rightAtt", { name: a.u });
    else {
      const b = document.createElement("b");
      b.textContent = a.u + ": ";
      d.append(b, document.createTextNode(String(a.t) + (myClose.has(i) ? " 🔥" : "")));
    }
    list.append(d);
    while (list.childElementCount > 80) list.firstChild.remove();
    if (stick) list.scrollTop = list.scrollHeight;
  }

  const liveActive = () => !st.unauth && (st.phase === "drawing" || st.phase === "starting") &&
    (st.role !== "drawer" || st.mode === "classic");

  async function pollLive() {
    try {
      if (liveActive()) {
        const drawer = st.role === "drawer";
        const res = await api(`live?turn=${vTurn == null ? -1 : vTurn}&since=${vSince}&att=${vAtt}` + (drawer ? "&ev=0" : ""));
        if (res.ok) {
          const j = await res.json();
          if (j.turn != null && j.turn === st.turn) {         // ignore answers about a turn that is over
            if (j.turn !== vTurn) { vTurn = j.turn; if (!drawer) resetCanvas(); clearAttempts(); }
            if (!drawer && j.events.length) applyBatch(j.events);
            vSince = j.ev + j.events.length;
            j.attempts.forEach((a, k) => addAttempt(j.att + k, a));
            vAtt = j.att + j.attempts.length;
          }
        }
      }
    } catch (e) { /* next round retries */ }
    setTimeout(pollLive, liveActive() ? 350 : 700);
  }

  let sending = false, flashTimer = null;
  function flash(text) {
    $("flash").textContent = text;
    clearTimeout(flashTimer);
    if (text) flashTimer = setTimeout(() => { $("flash").textContent = ""; }, 2500);
  }
  $("guessbar").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = $("guess"), text = input.value.trim();
    if (!text || sending) return;
    sending = true;
    try {
      const res = await api(st.mode === "broken" ? "bk/text" : "guess", "POST", { text });
      const j = await res.json().catch(() => ({}));
      if (res.ok) {
        input.value = "";
        if (st.mode === "broken") refresh();
        else if (j.result === "close") { myClose.add(j.id); flash(t("close")); }
        else if (j.result === "right") { flash(""); refresh(); }
      } else if (["already_guessed", "wrong_phase", "not_player", "no_game"].includes(j.error)) refresh();
      /* too_fast: keep the text, the player presses send again */
    } catch (err) { /* offline: keep the text */ }
    sending = false;
    input.focus();
  });

  // ------------------------------------------------------------------ pictures for the chat
  let uploading = false, lastUpload = 0;
  function queueUpload() { if (st.mode !== "broken" && Date.now() - lastUpload > 1000) upload(); }
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

  // the round is over: the server asks for the finished canvas, to post it in the chat
  let finalBusy = false, finalDone = null;
  async function sendFinal() {
    if (finalBusy || finalDone === turnKey) return;
    finalBusy = true;
    try {
      const blob = await new Promise((resolve) => cv.toBlob(resolve, "image/jpeg", 0.72));
      const res = await api("snapshot?final=1", "POST", blob);
      if (res.ok || res.status === 409) finalDone = turnKey;
    } catch (e) { /* the next state poll tries again */ }
    finalBusy = false;
  }

  // ---- Broken Canva: drafts every few seconds (used if the time runs out), the drawing at the end
  let bkSubmitting = false;
  async function bkSend(final) {
    if (!bkDrawNow() || bkSubmitting || (!final && !dirty)) return;
    if (final) bkSubmitting = true;
    dirty = final ? dirty : false;
    try {
      const blob = await new Promise((resolve) => cv.toBlob(resolve, "image/jpeg", 0.72));
      const res = await api(final ? "bk/submit" : "bk/draft", "POST", blob);
      if (final) {
        if (!res.ok) { const j = await res.json().catch(() => ({})); if (j.error === "bad_image") bkSubmitting = false; }
        await refresh();
        if (bkDrawNow()) bkSubmitting = false;     // not accepted: try again at the next tick
      } else if (!res.ok && res.status !== 409) dirty = true;
    } catch (e) { dirty = true; if (final) bkSubmitting = false; }
  }
  setInterval(() => bkSend(false), 4000);
  $("bkdone").addEventListener("click", () => bkSend(true));

  resetCanvas();
  poll();
  pollLive();
})();
