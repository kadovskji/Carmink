"use strict";
/* Carmink Mini App: the group dictionary page (opened from /settings -> Dictionary).
   Everything is checked again by the server (webserver.py /api/dict*): admins, or members if the group chose so. */
(() => {
  const tg = window.Telegram && window.Telegram.WebApp;
  const getInit = () => (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || "";
  const root = document.getElementById("dict");
  root.hidden = false;
  document.getElementById("bar").hidden = true;
  document.querySelector("main").hidden = true;

  const I18N = {
    it: {
      title: "📚 Dizionario", words: "parole", search: "Cerca…", all: "Tutte", add: "＋ Aggiungi", none: "Nessuna parola.",
      denied: "Non puoi modificare il dizionario di questo gruppo.", load: "Caricamento…",
      lvl: ["Facile", "Media", "Difficile"], newWord: "Nuova parola o frase", edit: "Modifica",
      category: "Categoria", cats: { animals: "Animali e creature", nature: "Natura e ambienti", plants: "Piante", body: "Corpo e abbigliamento", food: "Cibi e bevande", people: "Mestieri e personaggi", places: "Edifici e monumenti", vehicles: "Veicoli", objects: "Oggetti e dispositivi", actions: "Azioni ed emozioni", sport: "Sport e giochi", music: "Musica e strumenti", other: "Altro" },
      word: "Parola o frase", alts: "Sinonimi (separati da virgola)", level: "Difficoltà", auto: "Livello automatico",
      autoHelp: "Il livello si adatta a quanti la indovinano. Se lo cambi a mano resta fisso finché non riattivi l'automatico.",
      save: "Salva", del: "Elimina", sure: "Tocca ancora per eliminare", cancel: "Chiudi",
      saved: "Salvato ✅", deleted: "Eliminata 🗑", added: "Aggiunta ✅",
      export: "📤 Esporta file", exportHelp: "Ti mando il file in privato, nella chat col bot.", exported: "File inviato nella chat privata col bot ✅",
      import: "📥 Importa", code: "🔗 Codice", code_make: "Crea un codice", code_use: "Usa un codice",
      codeShow: "Codice per importare questo dizionario in un altro gruppo (valido {h} ore):", copy: "Copia", copied: "Copiato ✅",
      importTitle: "Importa parole", importHelp: "Scegli un file esportato da Carmink, oppure incolla un elenco (una parola per riga: parola | sinonimo | 2) o un codice.",
      file: "Scegli file…", paste: "Incolla qui il contenuto…", codeIn: "Codice (XXXX-XXXX)", preview: "Anteprima", doImport: "Importa",
      preview1: "Nuove: {new} · già presenti: {existing}", previewChanged: " · diverse da quelle del gruppo: {changed}", update: "Aggiorna anche le parole già presenti (livello, sinonimi, statistiche)", previewMore: " · non valide: {invalid}", previewFull: " · scartate (dizionario pieno): {full}",
      imported: "Importazione completata ✅ (nuove: {new})",
      e: { not_allowed: "Non puoi modificare questo dizionario.", bad_word: "Non valida: 2-40 caratteri, solo lettere, al massimo 6 parole.",
        word_dup: "C'è già una parola uguale.", dict_full: "Il dizionario è pieno.", dict_min: "Servono almeno {min} parole: non puoi eliminarne altre.",
        need_dm: "Apri il bot in privato, premi Start e riprova.", bad_code: "Codice non valido o scaduto.", too_big: "File troppo grande.",
        bad_file: "Non ho trovato parole valide.", word_missing: "Parola non trovata.", unauthorized: "Apri il dizionario dal pulsante in /settings.",
        generic: "Qualcosa non ha funzionato, riprova." },
    },
    en: {
      title: "📚 Dictionary", words: "words", search: "Search…", all: "All", add: "＋ Add", none: "No words.",
      denied: "You can't edit this group's dictionary.", load: "Loading…",
      lvl: ["Easy", "Medium", "Hard"], newWord: "New word or phrase", edit: "Edit",
      category: "Category", cats: { animals: "Animals & creatures", nature: "Nature & places", plants: "Plants", body: "Body & clothing", food: "Food & drinks", people: "Jobs & characters", places: "Buildings & landmarks", vehicles: "Vehicles", objects: "Objects & devices", actions: "Actions & emotions", sport: "Sports & games", music: "Music & instruments", other: "Other" },
      word: "Word or phrase", alts: "Synonyms (comma separated)", level: "Difficulty", auto: "Automatic level",
      autoHelp: "The level follows how many players guess it. If you change it by hand it stays fixed until you turn automatic back on.",
      save: "Save", del: "Delete", sure: "Tap again to delete", cancel: "Close",
      saved: "Saved ✅", deleted: "Deleted 🗑", added: "Added ✅",
      export: "📤 Export file", exportHelp: "I'll send you the file in private, in the chat with the bot.", exported: "File sent in your private chat with the bot ✅",
      import: "📥 Import", code: "🔗 Code", code_make: "Make a code", code_use: "Use a code",
      codeShow: "Code to import this dictionary into another group (valid {h} hours):", copy: "Copy", copied: "Copied ✅",
      importTitle: "Import words", importHelp: "Pick a file exported by Carmink, or paste a list (one word per line: word | synonym | 2) or a code.",
      file: "Choose file…", paste: "Paste the content here…", codeIn: "Code (XXXX-XXXX)", preview: "Preview", doImport: "Import",
      preview1: "New: {new} · already there: {existing}", previewChanged: " · different from the group's: {changed}", update: "Also update the words already there (level, synonyms, statistics)", previewMore: " · not valid: {invalid}", previewFull: " · left out (dictionary full): {full}",
      imported: "Import done ✅ (new: {new})",
      e: { not_allowed: "You can't edit this dictionary.", bad_word: "Not valid: 2-40 characters, letters only, at most 6 words.",
        word_dup: "That word already exists.", dict_full: "The dictionary is full.", dict_min: "At least {min} words are needed: you can't delete more.",
        need_dm: "Open the bot in private, press Start and try again.", bad_code: "Invalid or expired code.", too_big: "File too big.",
        bad_file: "I found no valid words.", word_missing: "Word not found.", unauthorized: "Open the dictionary from the button in /settings.",
        generic: "Something went wrong, try again." },
    },
  };
  const guess = ((tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.language_code) || "it").slice(0, 2);
  let lang = I18N[guess] ? guess : "it";            // interface language: the group's, once known
  const t = (k, v) => {
    let s = I18N[lang][k];
    if (typeof s === "string" && v) for (const x in v) s = s.replace("{" + x + "}", v[x]);
    return s;
  };
  const err = (code, extra) => {
    const e = I18N[lang].e;
    let s = e[code] || e.generic;
    if (extra && extra.min) s = s.replace("{min}", extra.min);
    return s;
  };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const ICON = { animals: "🐾", nature: "🏔", plants: "🌿", body: "👕", food: "🍕", people: "👷", places: "🏛", vehicles: "🚗", objects: "🪑", actions: "🎭", sport: "⚽", music: "🎸", other: "✨" };
  const DOT = ["🟢", "🟡", "🔴"];

  async function api(path, method, body) {
    const headers = { Authorization: "tma " + getInit() };
    let payload;
    if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
    try {
      const res = await fetch("/api/" + path, { method: method || "GET", headers, body: payload });
      const j = await res.json().catch(() => ({}));
      return { ok: res.ok, status: res.status, ...j };
    } catch (e) { return { ok: false, error: "network" }; }
  }

  let data = null, dictLang = null, query = "", level = 0, flashTimer = null;

  function flash(text, bad) {
    const f = document.getElementById("dflash");
    if (!f) return;
    f.textContent = text;
    f.className = bad ? "bad" : "good";
    f.hidden = !text;
    clearTimeout(flashTimer);
    if (text) flashTimer = setTimeout(() => { f.hidden = true; }, 3500);
  }

  async function load() {
    const res = await api("dict" + (dictLang ? "?lang=" + dictLang : ""));
    if (!res.ok) {
      root.innerHTML = `<p class="dmsg">${esc(res.status === 401 || res.status === 400 ? err("unauthorized") : t("denied"))}</p>`;
      return false;
    }
    data = res;
    dictLang = res.lang;
    if (I18N[res.ui]) lang = res.ui;
    render();
    return true;
  }

  function visible() {
    const q = query.trim().toLowerCase();
    return data.words.filter((w) => (!level || w.d === level) &&
      (!q || w.w.toLowerCase().includes(q) || w.alts.some((a) => a.toLowerCase().includes(q))));
  }

  function render() {
    root.innerHTML = `
      <header class="dhead">
        <b>${t("title")}</b>
        <span class="dcount">${data.words.length} ${t("words")}</span>
        <span class="dlangs">${data.langs.map((l) => `<button data-lang="${l}" class="${l === dictLang ? "on" : ""}">${l.toUpperCase()}</button>`).join("")}</span>
      </header>
      <div class="dtools">
        <input id="dq" type="search" placeholder="${esc(t("search"))}" value="${esc(query)}" autocomplete="off" autocorrect="off" spellcheck="false">
        <button id="dadd">${t("add")}</button>
      </div>
      <div class="dchips">
        <button data-lv="0" class="${!level ? "on" : ""}">${t("all")}</button>
        ${[1, 2, 3].map((l) => `<button data-lv="${l}" class="${level === l ? "on" : ""}">${DOT[l - 1]} ${t("lvl")[l - 1]}</button>`).join("")}
      </div>
      <div id="dflash" hidden></div>
      <div id="dlist"></div>
      <footer class="dfoot">
        <button id="dexport">${t("export")}</button>
        <button id="dimport">${t("import")}</button>
        <button id="dcode">${t("code")}</button>
      </footer>
      <div id="dsheet" hidden></div>`;
    renderList();
  }

  function renderList() {
    const rows = visible();
    document.getElementById("dlist").innerHTML = rows.length ? rows.map((w) =>
      `<button class="drow" data-w="${esc(w.w)}"><span class="dw">${ICON[w.cat] || ""} ${esc(w.w)}` +
      (w.alts.length ? `<small>${esc(w.alts.join(", "))}</small>` : "") +
      `</span><span class="dl">${w.lock ? "🔒 " : ""}${DOT[w.d - 1]}</span></button>`).join("")
      : `<p class="dmsg">${t("none")}</p>`;
  }

  // ---------------------------------------------------------------- sheets
  const sheet = () => document.getElementById("dsheet");
  const closeSheet = () => { sheet().hidden = true; sheet().innerHTML = ""; };
  function openSheet(html) { sheet().innerHTML = `<div class="dcard">${html}</div>`; sheet().hidden = false; }

  function editSheet(w) {
    const isNew = !w;
    const cur = w || { w: "", alts: [], d: 2, lock: false, cat: "other" };
    const cats = (data && data.cats) || Object.keys(ICON);
    openSheet(`
      <h3>${isNew ? t("newWord") : t("edit")}</h3>
      <label>${t("word")}<input id="fw" type="text" maxlength="40" value="${esc(cur.w)}" autocomplete="off" autocorrect="off" spellcheck="false"></label>
      <label>${t("alts")}<input id="fa" type="text" maxlength="200" value="${esc(cur.alts.join(", "))}" autocomplete="off" autocorrect="off" spellcheck="false"></label>
      <label>${t("category")}<select id="fc">${cats.map((c) => `<option value="${c}" ${c === (cur.cat || "other") ? "selected" : ""}>${ICON[c] || ""} ${esc(t("cats")[c] || c)}</option>`).join("")}</select></label>
      <div class="dlv">${t("level")}
        ${[1, 2, 3].map((l) => `<button type="button" data-d="${l}" class="${l === cur.d ? "on" : ""}">${DOT[l - 1]} ${t("lvl")[l - 1]}</button>`).join("")}
      </div>
      ${isNew ? "" : `<label class="dauto"><input id="fauto" type="checkbox" ${cur.lock ? "" : "checked"}> ${t("auto")}</label><small>${t("autoHelp")}</small>`}
      <p id="serr" class="bad" hidden></p>
      <div class="dbtns">
        <button id="fsave" class="main">${t("save")}</button>
        ${isNew ? "" : `<button id="fdel" class="danger">${t("del")}</button>`}
        <button id="fclose">${t("cancel")}</button>
      </div>`);
    let diff = cur.d, armed = false;
    const s = sheet();
    const shake = (m) => { const e = document.getElementById("serr"); e.textContent = m; e.hidden = false; };
    s.querySelectorAll("[data-d]").forEach((b) => b.addEventListener("click", () => {
      diff = Number(b.dataset.d);
      s.querySelectorAll("[data-d]").forEach((x) => x.classList.toggle("on", x === b));
      const a = document.getElementById("fauto");
      if (a && diff !== cur.d) a.checked = false;       // set by hand: fixed
    }));
    document.getElementById("fclose").addEventListener("click", closeSheet);
    document.getElementById("fsave").addEventListener("click", async () => {
      const word = document.getElementById("fw").value.trim();
      const alts = document.getElementById("fa").value.split(",").map((x) => x.trim()).filter(Boolean);
      let res;
      if (isNew) res = await api("dict/add", "POST", { lang: dictLang, text: [word, ...alts].join(" | "), diff,
        cat: document.getElementById("fc").value });
      else res = await api("dict/edit", "POST", { lang: dictLang, word: cur.w, new: word, alts, diff, cat: document.getElementById("fc").value,
        lock: !document.getElementById("fauto").checked });
      if (!res.ok) return shake(err(res.error, res));
      closeSheet();
      await load();
      flash(isNew ? t("added") : t("saved"));
    });
    const del = document.getElementById("fdel");
    if (del) del.addEventListener("click", async () => {
      if (!armed) { armed = true; del.textContent = t("sure"); return; }
      const res = await api("dict/delete", "POST", { lang: dictLang, word: cur.w });
      if (!res.ok) { armed = false; del.textContent = t("del"); return shake(err(res.error, res)); }
      closeSheet();
      await load();
      flash(t("deleted"));
    });
  }

  function importSheet(withCode) {
    openSheet(`
      <h3>${t("importTitle")}</h3>
      <small>${t("importHelp")}</small>
      <label class="dfile"><input id="ifile" type="file" accept=".json,.txt,text/plain,application/json"> ${t("file")}</label>
      <textarea id="itext" rows="5" placeholder="${esc(t("paste"))}"></textarea>
      <input id="icode" type="text" maxlength="12" placeholder="${esc(t("codeIn"))}" autocomplete="off" autocapitalize="characters" spellcheck="false" value="">
      <label class="dauto"><input id="iupd" type="checkbox"> ${t("update")}</label>
      <p id="sinfo" class="good" hidden></p>
      <p id="serr" class="bad" hidden></p>
      <div class="dbtns">
        <button id="iprev" class="main">${t("preview")}</button>
        <button id="iok" class="main" hidden>${t("doImport")}</button>
        <button id="iclose">${t("cancel")}</button>
      </div>`);
    const $ = (id) => document.getElementById(id);
    if (withCode) $("icode").focus();
    const body = (dry) => {
      const code = $("icode").value.trim();
      const update = $("iupd").checked;
      return code ? { lang: dictLang, code, dry, update } : { lang: dictLang, text: $("itext").value, dry, update };
    };
    const msg = (id, text) => { $("serr").hidden = $("sinfo").hidden = true; if (text) { $(id).textContent = text; $(id).hidden = false; } };
    $("ifile").addEventListener("change", () => {
      const f = $("ifile").files[0];
      if (!f) return;
      const r = new FileReader();
      r.onload = () => { $("itext").value = String(r.result || ""); $("icode").value = ""; $("iok").hidden = true; };
      r.readAsText(f);
    });
    for (const id of ["itext", "icode", "iupd"]) $(id).addEventListener("input", () => { $("iok").hidden = true; });
    $("iclose").addEventListener("click", closeSheet);
    $("iprev").addEventListener("click", async () => {
      const res = await api("dict/import", "POST", body(true));
      if (!res.ok) { $("iok").hidden = true; return msg("serr", err(res.error, res)); }
      let s = t("preview1", res);
      if (res.changed) s += t("previewChanged", res);
      if (res.invalid) s += t("previewMore", res);
      if (res.full) s += t("previewFull", res);
      msg("sinfo", s);
      $("iok").hidden = !(res.new || ($("iupd").checked && res.changed));
    });
    $("iok").addEventListener("click", async () => {
      const res = await api("dict/import", "POST", body(false));
      if (!res.ok) return msg("serr", err(res.error, res));
      closeSheet();
      await load();
      flash(t("imported", res));
    });
  }

  async function codeSheet() {
    const res = await api("dict/code", "POST", {});
    if (!res.ok) return flash(err(res.error, res), true);
    openSheet(`
      <h3>${t("code")}</h3>
      <small>${t("codeShow", { h: res.hours })}</small>
      <div class="dcode">${esc(res.code)}</div>
      <div class="dbtns">
        <button id="ccopy" class="main">${t("copy")}</button>
        <button id="cuse">${t("code_use")}</button>
        <button id="cclose">${t("cancel")}</button>
      </div>`);
    document.getElementById("cclose").addEventListener("click", closeSheet);
    document.getElementById("cuse").addEventListener("click", () => importSheet(true));
    document.getElementById("ccopy").addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(res.code); document.getElementById("ccopy").textContent = t("copied"); }
      catch (e) { /* the code is on screen anyway */ }
    });
  }

  // ---------------------------------------------------------------- events
  root.addEventListener("input", (e) => { if (e.target.id === "dq") { query = e.target.value; renderList(); } });
  root.addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.lang) { dictLang = b.dataset.lang; query = ""; level = 0; await load(); }
    else if (b.dataset.lv !== undefined && b.closest(".dchips")) {
      level = Number(b.dataset.lv);
      root.querySelectorAll(".dchips button").forEach((x) => x.classList.toggle("on", x === b));
      renderList();
    } else if (b.classList.contains("drow")) editSheet(data.words.find((w) => w.w === b.dataset.w));
    else if (b.id === "dadd") editSheet(null);
    else if (b.id === "dimport") importSheet(false);
    else if (b.id === "dcode") codeSheet();
    else if (b.id === "dexport") {
      const res = await api("dict/export", "POST", {});
      flash(res.ok ? t("exported") : err(res.error, res), !res.ok);
    }
  });

  root.innerHTML = `<p class="dmsg">${t("load")}</p>`;
  load();
})();
