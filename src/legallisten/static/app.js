/* LegalListen web client. No external dependencies. */
(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const state = { id: null, token: null, lang: "en", tts: false, config: {}, consult: null, busy: false, lastGraph: null, summary: {},
                  user: null, drafts: null, draftKind: null };
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { /* ignore */ } },
  };
  const ui = () => window.UI[state.lang] || window.UI.en;
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const linkify = (s) => esc(s).replace(/(https?:\/\/[^\s)]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');

  async function api(method, path, body, isForm) {
    const headers = {};
    if (state.token) headers["X-Session-Token"] = state.token;
    if (body && !isForm) headers["Content-Type"] = "application/json";
    const res = await fetch(path, { method, headers, body: body ? (isForm ? body : JSON.stringify(body)) : undefined });
    if (!res.ok) {
      let msg = res.statusText;
      try { msg = (await res.json()).detail || msg; } catch (e) { /* ignore */ }
      const err = new Error(msg); err.status = res.status; throw err;
    }
    const ct = res.headers.get("content-type") || "";
    return ct.includes("json") ? res.json() : res.text();
  }

  // ------------------------------------------------------------------ i18n
  function applyUI() {
    const t = ui();
    document.documentElement.lang = state.lang;
    document.querySelectorAll("[data-i18n]").forEach(e => { const k = e.dataset.i18n; if (t[k]) e.textContent = t[k]; });
    document.querySelectorAll("[data-i18n-ph]").forEach(e => { const k = e.dataset.i18nPh; if (t[k]) e.placeholder = t[k]; });
    $("#lang").value = state.lang;
    CaseGraph.legend($("#legend"), t);
    const b = $("#ai-badge");
    b.hidden = false;
    b.textContent = state.summary.llm ? `${t.ai_on} · ${state.config.llm_model || ""}` : t.ai_off;
    renderHeader();
    renderExamples();
    renderSideHistory();
    renderUser();
  }

  // Header: case title, triage pill and the five-step progress tracker.
  function renderHeader() {
    const t = ui(), s = state.summary || {};
    $("#case-title").textContent = (state.id && s.title) || t.new;
    const pillEl = $("#triage-pill");
    const tri = s.urgent ? "urgent" : (s.consultation_ready ? "self_help" : "");
    pillEl.hidden = !state.id || !tri;
    if (tri) { pillEl.className = "pill-tri " + tri; pillEl.textContent = s.urgent ? t.pill_urgent : t.pill_ready; }
    const issues = (s.issues || []).filter(i => i.identified).map(i => i.title);
    const extra = issues.filter(x => x !== s.title);
    const bits = [];
    if (extra.length) bits.push(extra.slice(0, 2).join(" · "));
    if (s.questions_asked) bits.push(`${s.questions_asked} ${t.q_asked || "questions"}`);
    if (s.law_regime) bits.push(s.law_regime === "old" ? "IPC / CrPC" : "BNS / BNSS");
    $("#case-sub").textContent = state.id ? bits.join(" · ") : "";
    const spoke = $("#messages").querySelector(".msg.user") !== null;
    let step = 0;
    if (spoke) step = 1;
    if (s.questions_asked > 0) step = 2;
    if (issues.length) step = 3;
    if (s.consultation_ready) step = 5;
    document.querySelectorAll("#stepper li").forEach(li => {
      const n = +li.dataset.step;
      li.classList.toggle("done", n <= step);
      li.classList.toggle("now", n === step + 1);
    });
  }

  function renderExamples() {
    const box = $("#examples"), ex = ui().examples || [];
    box.innerHTML = "";
    ex.forEach(text => {
      const b = document.createElement("button"); b.className = "example"; b.textContent = text;
      b.addEventListener("click", () => { state.prefill = text; $("#start").click(); });
      box.appendChild(b);
    });
  }

  function toast(text) {
    const el = $("#toast"); el.textContent = text; el.hidden = false;
    clearTimeout(toast.timer); toast.timer = setTimeout(() => { el.hidden = true; }, 2600);
  }

  // ------------------------------------------------------------------ chat
  const AVATAR = '<span class="avatar" aria-hidden="true"><svg viewBox="0 0 64 64"><path d="M18 44h28M32 14v30M20 24l-6 12h12zM44 24l-6 12h12zM20 24h24"/><circle cx="32" cy="14" r="3.5"/></svg></span>';

  // Assistant text → paragraphs, bullet / numbered lists and short "Heading:" lines.
  function richText(text) {
    let h = "", list = null;
    const close = () => { if (list) { h += `</${list}>`; list = null; } };
    String(text || "").split("\n").forEach(line => {
      const s = line.trim();
      let m;
      if ((m = s.match(/^[•·]\s*(.*)$/))) { if (list !== "ul") { close(); h += "<ul>"; list = "ul"; } h += `<li>${linkify(m[1])}</li>`; return; }
      if ((m = s.match(/^\d{1,2}[.)]\s+(.*)$/))) { if (list !== "ol") { close(); h += "<ol>"; list = "ol"; } h += `<li>${linkify(m[1])}</li>`; return; }
      close();
      if (!s) return;
      if (s.length <= 60 && /[:：]$/.test(s)) { h += `<h4>${esc(s.replace(/[:：]$/, ""))}</h4>`; return; }
      h += `<p>${linkify(s)}</p>`;
    });
    close();
    return h;
  }

  function timeOf(ts) {
    if (!ts) return "";
    const d = new Date(ts);
    return isNaN(d) ? "" : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function addMessage(m) {
    const box = $("#messages");
    const row = document.createElement("div");
    row.className = `msg-row ${m.role}`;
    if (m.turn != null) row.dataset.turn = String(m.turn);
    if (m.role === "assistant") row.innerHTML = AVATAR;
    const div = document.createElement("div");
    div.className = `msg ${m.role} ${m.kind || ""}`;
    if (m.role === "assistant" && m.kind === "consultation") {
      const lines = String(m.text).split("\n");
      div.innerHTML = `<div class="c-head"><span>📋 ${esc(lines[0])}</span></div><div class="c-body">${richText(lines.slice(1).join("\n"))}</div>`;
      const open = document.createElement("button"); open.className = "btn soft small c-open"; open.textContent = ui().open_full || ui().tab_consult;
      open.addEventListener("click", () => { setView("case"); showTab("consult"); });
      div.querySelector(".c-body").appendChild(open);
    } else {
      div.innerHTML = m.role === "assistant" ? richText(m.text) : `<p>${linkify(m.text).replace(/\n/g, "<br>")}</p>`;
    }
    const meta = document.createElement("div"); meta.className = "meta";
    const when = timeOf(m.ts);
    if (m.role === "user" && m.source === "voice") meta.append("🎤" + (m.asr_confidence != null ? ` ${(m.asr_confidence * 100).toFixed(0)}%` : "") + " · ");
    if (when) meta.append(when);
    if (m.role === "assistant") {
      if (m.why) { const w = document.createElement("span"); w.className = "why"; w.textContent = "💡 " + m.why; (div.querySelector(".c-body") || div).appendChild(w); }
      if ("speechSynthesis" in window) {
        const sp = document.createElement("button"); sp.className = "speak"; sp.title = ui().speak; sp.textContent = "🔊";
        sp.addEventListener("click", () => speak(m.text, true)); meta.appendChild(sp);
      }
    }
    if (meta.childNodes.length) (div.querySelector(".c-body") || div).appendChild(meta);
    row.appendChild(div);
    box.appendChild(row);
    box.scrollTop = box.scrollHeight;
  }

  function setChips(chips) {
    const c = $("#chips");
    c.innerHTML = "";
    (chips || []).forEach(ch => {
      const b = document.createElement("button");
      b.className = "chip" + (ch.id === "dk" || ch.id === "skip" ? " dk" : "");
      b.textContent = ch.label;
      b.addEventListener("click", () => {
        if (ch.id === "show:consultation") { setView("case"); showTab("consult"); return; }
        if (ch.id === "show:drafts") { setView("case"); showTab("drafts"); return; }
        send({ chip: ch.id, text: ch.label });
      });
      c.appendChild(b);
    });
  }

  function setBusy(on) {
    state.busy = on;
    $("#send").disabled = on;
    let t = $("#typing");
    if (on && !t) {
      t = document.createElement("div"); t.id = "typing"; t.className = "msg-row assistant typing";
      t.innerHTML = AVATAR + `<div class="dots" aria-label="${esc(ui().thinking)}"><i></i><i></i><i></i></div>`;
      $("#messages").appendChild(t); $("#messages").scrollTop = $("#messages").scrollHeight;
    }
    if (!on && t) t.remove();
  }

  async function send(payload) {
    if (state.busy || !state.id) return;
    setBusy(true);
    setChips([]);
    try {
      const r = await api("POST", `/api/session/${state.id}/message`, payload);
      setBusy(false);
      handleUpdate(r);
    } catch (e) {
      setBusy(false);
      if (e.status === 404) { resetSession(); return; }
      addMessage({ role: "assistant", kind: "alert", text: e.message });
    }
  }

  function handleUpdate(r) {
    const msgs = r.messages || [];
    msgs.forEach(m => { if (m.role === "user") addMessage(m); });
    msgs.forEach(m => { if (m.role === "assistant") addMessage(m); });
    const last = [...msgs].reverse().find(m => m.role === "assistant");
    setChips(last ? last.chips : []);
    const said = msgs.filter(m => m.role === "assistant").map(m => m.text).join(" ");
    if (said) speak(said);
    state.summary = r.summary || state.summary;
    remember();
    renderHeader(); renderSideHistory();
    updateUrgent(r);
    if (r.graph) { state.lastGraph = r.graph; drawGraph(); }
    renderFacts();
    if (state.summary.consultation_ready && $("#tab-consult").classList.contains("active")) loadConsultation();
    if (state.summary.consultation_ready && $("#tab-laws").classList.contains("active")) loadConsultation();
    if ($("#tab-drafts").classList.contains("active")) loadDrafts(); else state.drafts = null;
  }

  function updateUrgent(r) {
    const u = $("#urgent");
    const alerts = (r.messages || []).filter(m => m.kind === "alert");
    if (alerts.length) { u.textContent = alerts.map(a => a.text).join("\n"); u.hidden = false; }
    if (!state.summary.urgent && !alerts.length) u.hidden = true;
  }

  // ------------------------------------------------------------------ voice
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null, recording = false, mediaRec = null, chunks = [];
  const LOCALE = { en: "en-IN", kn: "kn-IN", hi: "hi-IN" };

  function voiceStatus(text) { const v = $("#voice-status"); v.hidden = !text; v.textContent = text || ""; }

  // Encode recorded audio as 16 kHz mono WAV (a format every speech model accepts).
  async function toWav(blob) {
    const buf = await blob.arrayBuffer();
    const AC = window.AudioContext || window.webkitAudioContext;
    const ctx = new AC();
    const decoded = await ctx.decodeAudioData(buf);
    ctx.close && ctx.close();
    const rate = 16000, len = Math.ceil(decoded.duration * rate);
    const off = new OfflineAudioContext(1, len, rate);
    const src = off.createBufferSource(); src.buffer = decoded; src.connect(off.destination); src.start();
    const pcm = (await off.startRendering()).getChannelData(0);
    const out = new DataView(new ArrayBuffer(44 + pcm.length * 2));
    const wstr = (o, s) => { for (let i = 0; i < s.length; i++) out.setUint8(o + i, s.charCodeAt(i)); };
    wstr(0, "RIFF"); out.setUint32(4, 36 + pcm.length * 2, true); wstr(8, "WAVE"); wstr(12, "fmt ");
    out.setUint32(16, 16, true); out.setUint16(20, 1, true); out.setUint16(22, 1, true); out.setUint32(24, rate, true);
    out.setUint32(28, rate * 2, true); out.setUint16(32, 2, true); out.setUint16(34, 16, true); wstr(36, "data");
    out.setUint32(40, pcm.length * 2, true);
    for (let i = 0; i < pcm.length; i++) { const v = Math.max(-1, Math.min(1, pcm[i])); out.setInt16(44 + i * 2, v < 0 ? v * 0x8000 : v * 0x7fff, true); }
    return new Blob([out], { type: "audio/wav" });
  }

  function startServerVoice() {
    navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
      chunks = []; mediaRec = new MediaRecorder(stream);
      mediaRec.ondataavailable = e => chunks.push(e.data);
      mediaRec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        recording = false; $("#mic").classList.remove("recording");
        const raw = new Blob(chunks, { type: mediaRec.mimeType || "audio/webm" });
        voiceStatus(ui().thinking);
        try {
          let wav = raw;
          try { wav = await toWav(raw); } catch (e) { /* send the original container */ }
          const fd = new FormData(); fd.append("audio", wav, wav.type === "audio/wav" ? "speech.wav" : "speech.webm"); fd.append("lang", state.lang);
          const r = await api("POST", "/api/transcribe", fd, true);
          $("#input").value = (($("#input").value ? $("#input").value + " " : "") + r.transcript).trim();
          $("#input").dataset.source = "voice"; $("#input").dataset.conf = String(r.confidence);
          voiceStatus(r.confidence < 0.6 ? ui().low_conf : ui().check_transcript);
        } catch (e) { voiceStatus(e.message); }
      };
      mediaRec.start(); recording = true; $("#mic").classList.add("recording"); voiceStatus(ui().listening);
    }).catch(() => voiceStatus(ui().mic_denied));
  }

  function startVoice() {
    // Prefer server transcription (Gemini handles code-mixed speech better); otherwise the browser recogniser.
    if (state.config.server_transcription && state.summary.llm && navigator.mediaDevices && window.MediaRecorder) {
      startServerVoice();
      return;
    }
    if (SR) {
      rec = new SR();
      rec.lang = LOCALE[state.lang] || "en-IN";
      rec.interimResults = true; rec.continuous = true; rec.maxAlternatives = 1;
      const base = $("#input").value ? $("#input").value + " " : "";
      let finalText = "", confs = [];
      rec.onresult = (ev) => {
        let interim = "";
        for (let i = ev.resultIndex; i < ev.results.length; i++) {
          const res = ev.results[i];
          if (res.isFinal) { finalText += res[0].transcript + " "; if (res[0].confidence) confs.push(res[0].confidence); }
          else interim += res[0].transcript;
        }
        $("#input").value = (base + finalText + interim).trim();
      };
      rec.onerror = (ev) => { voiceStatus(ev.error === "not-allowed" ? ui().mic_denied : ev.error); stopVoice(); };
      rec.onend = () => {
        recording = false; $("#mic").classList.remove("recording");
        const conf = confs.length ? confs.reduce((a, b) => a + b, 0) / confs.length : null;
        $("#input").dataset.source = finalText ? "voice" : "";
        $("#input").dataset.conf = conf == null ? "" : String(conf);
        voiceStatus(finalText ? (conf != null && conf < 0.6 ? ui().low_conf : ui().check_transcript) : "");
      };
      rec.start(); recording = true; $("#mic").classList.add("recording"); voiceStatus(ui().listening);
      return;
    }
    if (state.config.server_transcription && navigator.mediaDevices && window.MediaRecorder) {
      startServerVoice();
      return;
    }
    voiceStatus(ui().no_mic);
  }
  function stopVoice() {
    if (rec) { try { rec.stop(); } catch (e) { /* ignore */ } }
    if (mediaRec && mediaRec.state === "recording") mediaRec.stop();
    recording = false; $("#mic").classList.remove("recording");
  }

  function speak(text, force) {
    if (!(state.tts || force) || !("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(text.replace(/https?:\/\/\S+/g, ""));
    u.lang = LOCALE[state.lang] || "en-IN";
    const v = speechSynthesis.getVoices().find(v => v.lang && v.lang.toLowerCase().startsWith(state.lang));
    if (v) u.voice = v;
    u.rate = 0.95;
    speechSynthesis.cancel(); speechSynthesis.speak(u);
  }

  // ------------------------------------------------------------------ tabs
  function showTab(name) {
    document.querySelectorAll(".tabs button").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
    document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.id === "tab-" + name));
    if (name === "graph") drawGraph();
    if ((name === "laws" || name === "consult") && state.id) loadConsultation();
    if (name === "drafts") loadDrafts();
  }

  // ------------------------------------------------------------------ drafts
  // Ready-to-file documents built on the server from the case. Blank values stay in this browser only.
  function draftValues() { try { return JSON.parse(store.get("ll_dv_" + state.id) || "{}"); } catch (e) { return {}; } }
  function saveDraftValues(v) { store.set("ll_dv_" + state.id, JSON.stringify(v)); }

  async function loadDrafts() {
    const box = $("#tab-drafts");
    if (!state.id) { box.innerHTML = `<div class="empty">${esc(ui().no_consult)}</div>`; return; }
    if (!state.drafts) box.innerHTML = `<div class="empty">${esc(ui().thinking)}</div>`;
    try { state.drafts = await api("GET", `/api/session/${state.id}/drafts`); renderDrafts(); }
    catch (e) { box.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
  }

  function draftText(d) {
    const vals = draftValues();
    return d.blocks.map(b => b.t === "br" ? "\n" : b.t === "h" ? `\n${b.v}\n` : b.t === "blank" ? (vals[b.id] || `[${b.label}]`) : b.v)
      .join("").replace(/\n{3,}/g, "\n\n").trim() + "\n";
  }

  function renderDrafts() {
    const r = state.drafts, L = r.labels, t = ui(), box = $("#tab-drafts");
    const d = r.drafts.find(x => x.kind === state.draftKind) || r.drafts[0];
    state.draftKind = d.kind;
    const vals = draftValues();
    let h = `<p class="draft-intro">${esc(r.ready ? L.dr_intro : L.dr_none)}</p><div class="draft-picker">`;
    h += r.drafts.map(x => `<button class="dpick${x.kind === d.kind ? " sel" : ""}" data-kind="${esc(x.kind)}">
        <b>${esc(x.title)}</b><small>${esc(x.what)}</small>
        <span class="dmeta"><i class="ok">✓ ${x.n_facts} ${esc(L.dr_from_you)}</i><i>✎ ${x.n_blanks} ${esc(L.dr_fill)}</i></span></button>`).join("");
    h += `</div><div class="draft-where">📍 ${esc(d.where)}</div>`;
    if (r.unconfirmed.length) h += `<div class="draft-open"><b>${esc(L.dr_check)}</b><p>${esc(L.dr_unconfirmed)}</p><ul>${r.unconfirmed.map(q => `<li>${esc(q)}</li>`).join("")}</ul></div>`;
    h += `<div class="draft-bar"><div class="dprog-wrap"><div class="dprog"><span id="dprog-bar"></span></div><small id="dprog-text"></small></div>
          <button class="btn small" id="d-copy">${esc(L.dr_copy)}</button>
          <button class="btn small" id="d-dl">${esc(L.dr_download)}</button>
          <button class="btn small primary" id="d-print">${esc(L.dr_print)}</button></div>`;
    h += `<div class="fact-source" id="fact-source" hidden></div>`;
    h += `<article class="paper" id="paper" lang="en">` + d.blocks.map((b, i) => {
      if (b.t === "br") return "<br>";
      if (b.t === "h") return `<span class="p-h">${esc(b.v)}</span>`;
      if (b.t === "blank") return `<input class="blank" data-id="${esc(b.id)}" placeholder="${esc(b.label)}" aria-label="${esc(b.label)}" value="${esc(vals[b.id] || "")}">`;
      if (b.t === "fact") return `<mark class="fact" tabindex="0" role="button" data-i="${i}">${esc(b.v)}</mark>`;
      return esc(b.v);
    }).join("") + `</article><p class="disclaimer">${esc(L.dr_disclaimer)}</p>`;
    box.innerHTML = h;

    box.querySelectorAll(".dpick").forEach(b => b.addEventListener("click", () => { state.draftKind = b.dataset.kind; renderDrafts(); }));
    const fit = (inp) => { inp.style.width = Math.max(6, Math.min(48, (inp.value || inp.placeholder).length + 2)) + "ch"; };
    const progress = () => {
      const ids = [...new Set(d.blocks.filter(b => b.t === "blank").map(b => b.id))], v = draftValues();
      const done = ids.filter(id => (v[id] || "").trim()).length;
      $("#dprog-bar").style.width = (ids.length ? Math.round(done / ids.length * 100) : 100) + "%";
      $("#dprog-text").textContent = `${done} / ${ids.length} ${L.dr_progress}`;
    };
    box.querySelectorAll("input.blank").forEach(inp => {
      fit(inp);
      inp.addEventListener("input", () => {
        const v = draftValues(); v[inp.dataset.id] = inp.value; saveDraftValues(v);
        box.querySelectorAll(`input.blank[data-id="${CSS.escape(inp.dataset.id)}"]`).forEach(o => { if (o !== inp) o.value = inp.value; fit(o); });
        fit(inp); progress();
      });
    });
    progress();
    // Provenance: every highlighted fact shows the user's own words and can jump to that message.
    const showSource = (mk) => {
      const b = d.blocks[+mk.dataset.i], src = $("#fact-source");
      box.querySelectorAll("mark.fact.sel").forEach(x => x.classList.remove("sel"));
      mk.classList.add("sel");
      const when = b.ts ? ` · ${t.dr_when} ${timeOf(b.ts)}` : "";
      src.innerHTML = `<span class="src-ico" aria-hidden="true">🔗</span><div><b>${esc(L.dr_said)}:</b> “${esc(b.quote || b.v)}”<small>${esc(when)}</small></div>` +
        (b.turn != null ? `<button class="btn small soft" id="src-jump">${esc(t.dr_show_chat)}</button>` : "");
      src.hidden = false;
      const jump = $("#src-jump");
      if (jump) jump.addEventListener("click", () => {
        const row = document.querySelector(`#messages .msg-row.user[data-turn="${b.turn}"]`);
        if (!row) return;
        setView("chat");
        row.scrollIntoView({ behavior: "smooth", block: "center" });
        row.classList.remove("flash"); void row.offsetWidth; row.classList.add("flash");
      });
    };
    box.querySelectorAll("mark.fact").forEach(mk => {
      mk.addEventListener("click", () => showSource(mk));
      mk.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); showSource(mk); } });
    });
    $("#d-copy").addEventListener("click", async () => { try { await navigator.clipboard.writeText(draftText(d)); toast(t.dr_copied); } catch (e) { /* ignore */ } });
    $("#d-dl").addEventListener("click", () => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([draftText(d)], { type: "text/plain;charset=utf-8" }));
      a.download = `legallisten-${d.kind}-draft.txt`; document.body.appendChild(a); a.click();
      setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
    });
    $("#d-print").addEventListener("click", () => {
      document.body.classList.add("print-draft");
      window.print();
      setTimeout(() => document.body.classList.remove("print-draft"), 500);
    });
  }

  function drawGraph() {
    if (!state.lastGraph || !$("#tab-graph").classList.contains("active")) return;
    CaseGraph.render($("#graph"), state.lastGraph, { ui: ui(), onSelect: showNode });
  }

  function showNode(n) {
    const t = ui(), g = state.lastGraph || { nodes: [], edges: [] };
    const byId = {}; g.nodes.forEach(x => { byId[x.id] = x; });
    const lines = [`${(t.legend && t.legend[n.type]) || n.type}: ${n.label}`];
    if (n.type === "Element") {
      if (n.answer) lines.push(`→ ${n.answer}`);
      lines.push(`${t.status}: ${n.status === "conflicting" ? t.conflicting : (t[n.value] || n.value)}${n.value === "satisfied" || n.value === "contradicted" ? " · " + (t[n.status] || n.status) : ""}`);
      const said = g.edges.filter(e => e.type === "BEARS_ON" && e.target === n.id).map(e => byId[e.source]).filter(Boolean);
      said.forEach(c => lines.push(`${c.status === "corrected" ? "✎" : "“"} ${c.label}${c.status === "corrected" ? " (" + t.corrected + ")" : "”"}`));
      if (n.value === "not_discussed" || n.value === "unknown" || n.status === "conflicting") lines.push(`? ${n.question}`);
    } else {
      if (n.status && n.type !== "Person") lines.push(`${t.status}: ${t[n.status] || n.status}`);
      if (n.relation) lines.push(n.relation.replace(/_/g, " "));
      if (n.date) lines.push(`${t.date}: ${n.date}`);
      if (n.availability) lines.push(t[n.availability] || n.availability);
      if (n.act_title) lines.push(n.act_title);
      if (n.title_hint) lines.push(n.title_hint + (n.verification ? ` (${n.verification})` : ""));
      if (n.regime_note) lines.push(n.regime_note);
      if (n.gloss_en) lines.push(`EN: ${n.gloss_en}`);
      if (n.quote) lines.push(`“${n.quote}”`);
      if (n.belief != null) lines.push(`${Math.round(n.belief * 100)}%`);
    }
    $("#node-detail").textContent = lines.join("\n");
  }

  function pill(cls, text) { return `<span class="pill ${esc(cls)}">${esc(text)}</span>`; }

  function renderFacts() {
    const t = ui(), g = state.lastGraph, s = state.summary;
    const box = $("#tab-facts");
    if (!g || !(g.nodes || []).some(n => n.type === "Issue")) { box.innerHTML = `<div class="empty">${esc(t.no_facts)}</div>`; return; }
    const nodes = g.nodes, by = (ty) => nodes.filter(n => n.type === ty);
    let h = `<div class="card"><h3>${esc(t.issues)}</h3>`;
    (s.issues || []).forEach(i => {
      h += `<p>${esc(i.title)} ${pill(i.identified ? "satisfied" : "unknown", i.identified ? t.identified : t.possible)}</p>
            <div class="bar"><span style="width:${Math.round(i.belief * 100)}%"></span></div>`;
    });
    h += `<p>${esc(t.date)}: ${esc(s.incident_date || t.none)} · ${esc(t.regime)}: ${esc(s.law_regime ? (s.law_regime === "old" ? "IPC/CrPC" : "BNS/BNSS") : t.none)}
          · ${esc(t.pl)}: ${esc(s.personal_law || t.none)}</p></div>`;
    h += `<div class="card"><h3>${esc(t.elements)}</h3><table class="facts">`;
    by("Issue").forEach(iss => {
      h += `<tr><td colspan="2"><strong>${esc(iss.label)}</strong></td></tr>`;
      g.edges.filter(e => e.type === "HAS_ELEMENT" && e.source === iss.id).forEach(e => {
        const el = nodes.find(n => n.id === e.target);
        if (el) h += `<tr><td>${esc(el.label)}</td><td>${pill(el.value, t[el.value] || el.value)}${el.value !== "not_discussed" ? pill(el.status, t[el.status] || el.status) : ""}</td></tr>`;
      });
    });
    h += `</table></div>`;
    const people = by("Person").concat(by("Organization"));
    h += `<div class="card"><h3>${esc(t.people)}</h3><p>${people.map(p => esc(p.label) + (p.relation ? ` (${esc(p.relation.replace(/_/g, " "))})` : "")).join(", ")}</p></div>`;
    const ev = by("Event").filter(e => e.date).sort((a, b) => String(a.date).localeCompare(String(b.date)));
    if (ev.length) h += `<div class="card"><h3>${esc(t.timeline)}</h3>${ev.map(e => `<p>${esc(e.date)} — ${esc(e.label)}${e.negated ? " ✗" : ""}</p>`).join("")}</div>`;
    const evd = by("Evidence");
    if (evd.length) h += `<div class="card"><h3>${esc(t.evidence)}</h3>${evd.map(e => `<p>${esc(e.label)} ${pill(e.availability, t[e.availability] || e.availability)}</p>`).join("")}</div>`;
    const con = by("Contradiction");
    if (con.length) h += `<div class="card"><h3>${esc(t.contradictions)}</h3>${con.map(c => `<p>${esc(c.label)} ${pill(c.resolved ? "satisfied" : "conflicting", c.resolved ? (c.resolution || "") : t.conflicting)}</p>`).join("")}</div>`;
    const risks = by("Risk");
    if (risks.length) h += `<div class="card"><h3>${esc(t.risks)}</h3>${risks.map(r => `<p>${pill("conflicting", r.label)} ${esc(r.quote || "")}</p>`).join("")}</div>`;
    box.innerHTML = h;
  }

  // ------------------------------------------------------------ consultation
  let loading = false;
  async function loadConsultation() {
    if (loading || !state.id) return;
    loading = true;
    $("#tab-consult").innerHTML = `<div class="empty">${esc(ui().thinking)}</div>`;
    try {
      const r = await api("POST", `/api/session/${state.id}/consultation`);
      state.consult = r.consultation; state.markdown = r.markdown;
      renderConsultation(); renderLaws();
    } catch (e) {
      $("#tab-consult").innerHTML = `<div class="empty">${esc(e.message)}</div>`;
    } finally { loading = false; }
  }

  // Official text as printed: PDF line breaks joined, a new paragraph at each sub-section, Explanation or Illustration.
  function lawParas(text) {
    const flat = String(text).replace(/\s*\n\s*/g, " ").replace(/\s{2,}/g, " ").trim();
    return flat.split(/\s(?=\(\d{1,2}[A-Z]?\)\s|Explanation\s?\d*\s?\.?[—–―-]|Illustrations?\b)/)
      .map(x => `<p>${esc(x)}</p>`).join("");
  }

  function lawCard(p, withActions) {
    const L = p.labels;
    let h = `<div class="card law" data-pid="${esc(p.provision_id)}"><h3>${esc(p.act_title)} — ${esc(p.section)}</h3>`;
    if (p.title_hint) h += `<p><em>${esc(p.title_hint)}</em>${p.official_text ? "" : ` <span class="hint">${esc(L.p_heading_hint)}</span>`}</p>`;
    h += `${pill("", p.issue_title)}${pill(p.verification, p.verification)}`;
    if (p.regime_note) h += `<p class="hint">${esc(p.regime_note)}</p>`;
    if (p.conditional_on) h += `<p class="hint">⚑ ${esc(p.conditional_on)}</p>`;
    h += `<h4>${esc(L.p_what)}</h4>` + (p.official_text
      ? `<div class="law-text">${lawParas(p.official_text)}</div>` + (p.source_note ? `<p class="src-note">📄 ${esc(p.source_note)}</p>` : "")
      : `<p>${esc(p.no_text_note)}</p>`);
    h += `<h4>${esc(L.p_means)}</h4><p>${esc(p.explanation || p.means)}</p>`;
    h += `<h4>${esc(L.p_why)}</h4><p>${p.why.length ? p.why.map(esc).join("<br>") : "—"}</p>`;
    h += `<h4>${esc(L.p_help)}</h4><p>${esc(p.help)}</p>`;
    h += `<h4>${esc(L.p_conditions)}</h4><p>${p.conditions.length ? p.conditions.map(esc).join("<br>") : "—"}${p.note ? "<br><span class=hint>" + esc(p.note) + "</span>" : ""}</p>`;
    h += `<h4>${esc(L.p_verify)}</h4><p>${esc(p.verify_text)} <a href="${esc(p.official_url)}" target="_blank" rel="noopener noreferrer">${esc(p.official_url)}</a></p>`;
    if (withActions) {
      h += `<div class="law-actions"><button class="btn" data-mode="simpler">${esc(ui().explain_simpler)}</button>
            <button class="btn" data-mode="why">${esc(ui().explain_why)}</button></div><div class="explain-out" hidden></div>`;
    }
    return h + `</div>`;
  }

  function bindLawActions(root) {
    root.querySelectorAll(".law").forEach(card => {
      card.querySelectorAll("button[data-mode]").forEach(b => b.addEventListener("click", async () => {
        const out = card.querySelector(".explain-out");
        out.hidden = false; out.textContent = ui().thinking;
        try {
          const r = await api("POST", `/api/session/${state.id}/explain`, { provision_id: card.dataset.pid, mode: b.dataset.mode });
          out.innerHTML = linkify(r.text); speak(r.text);
        } catch (e) { out.textContent = e.message; }
      }));
    });
  }

  function renderLaws() {
    const c = state.consult, box = $("#tab-laws");
    if (!c || !c.provisions.length) { box.innerHTML = `<div class="empty">${esc(ui().no_laws)}</div>`; return; }
    box.innerHTML = c.provisions.map(p => lawCard(p, true)).join("") + `<p class="disclaimer">${esc(c.disclaimer)}</p>`;
    bindLawActions(box);
  }

  function list(items) { return items && items.length ? `<ul>${items.map(i => `<li>${linkify(i)}</li>`).join("")}</ul>` : "<p>—</p>"; }

  function renderConsultation() {
    const c = state.consult, t = ui(), L = c.labels, box = $("#tab-consult");
    let h = `<div class="consult-actions">
      <button class="btn primary" id="c-refresh">${esc(t.generate)}</button>
      <button class="btn" id="c-md">${esc(t.download_md)}</button>
      <button class="btn" id="c-json">${esc(t.download_json)}</button>
      <button class="btn" id="c-print">${esc(t.print)}</button>
      <button class="btn" id="c-copy">${esc(t.copy)}</button></div>`;
    h += `<h2>${esc(L.c_title)}</h2><div class="triage ${esc(c.triage)}">${esc(c.triage_text)}</div>`;
    h += `<div class="card"><h3>${esc(L.c_summary)}</h3><p>${esc(c.summary).replace(/\n/g, "<br>")}</p></div>`;
    h += `<div class="card"><h3>${esc(L.c_issues)}</h3>${c.issues.length ? c.issues.map(i => `<p><strong>${esc(i.title)}</strong> — ${esc(i.summary)}</p>`).join("") : "<p>—</p>"}</div>`;
    const gi = c.graph_insights;
    h += `<div class="card"><h3>${esc(L.c_graph)}</h3><p>${esc(gi.people)}</p><p>${esc(gi.timeline)}</p><p>${esc(gi.claims)}</p><p>${esc(gi.evidence)}</p></div>`;
    h += `<h3>${esc(L.c_laws)}</h3>` + (c.provisions.length ? c.provisions.map(p => lawCard(p, true)).join("") : `<p>—</p>`);
    h += `<div class="card"><h3>${esc(L.c_options)}</h3>${list(c.options)}<p class="hint">${esc(c.options_note)}</p></div>`;
    h += `<div class="card"><h3>${esc(L.c_evidence)}</h3>${c.evidence.length ? c.evidence.map(e => `<p>${e.status === "held" ? "☑" : "☐"} ${esc(e.label)} ${pill(e.status, L[e.status] || e.status)}</p>`).join("") : "<p>—</p>"}</div>`;
    h += `<div class="card"><h3>${esc(L.c_steps)}</h3>${c.steps.length ? "<ol>" + c.steps.map(s => `<li>${linkify(s)}</li>`).join("") + "</ol>" : "<p>—</p>"}</div>`;
    h += `<div class="card"><h3>${esc(L.c_authorities)}</h3>${list(c.authorities)}</div>`;
    h += `<div class="card"><h3>${esc(L.c_unresolved)}</h3>${list(c.unresolved)}</div>`;
    if (c.contradictions.length) h += `<div class="card"><h3>${esc(L.c_contradictions)}</h3>${list(c.contradictions.map(x => `“${x.a}” ↔ “${x.b}”` + (x.resolved ? ` ✓ ${x.resolution}` : "")))}</div>`;
    h += `<div class="card"><h3>${esc(L.c_risks)}</h3>${c.risks.map(r => `<p>${r.urgent ? "⚠ " : ""}<strong>${esc(r.name || r.flag.replace(/_/g, " "))}</strong>: ${linkify(r.advice)}${r.authorities.length ? "<br>" + r.authorities.map(linkify).join("<br>") : ""}</p>`).join("")}${c.no_urgent ? `<p>${esc(c.no_urgent)}</p>` : ""}</div>`;
    h += `<div class="card"><h3>${esc(L.lawyer_summary)}</h3><pre class="lawyer" id="lawyer-summary">${esc(c.lawyer_summary)}</pre></div>`;
    h += `<p class="disclaimer">${esc(c.disclaimer)}</p>`;
    box.innerHTML = h;
    bindLawActions(box);
    $("#c-refresh").addEventListener("click", loadConsultation);
    $("#c-md").addEventListener("click", () => download(`/api/session/${state.id}/export?fmt=md`, "legallisten-consultation.md"));
    $("#c-json").addEventListener("click", () => download(`/api/session/${state.id}/export?fmt=json`, "legallisten-case.json"));
    $("#c-print").addEventListener("click", () => window.print());
    $("#c-copy").addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(c.lawyer_summary); $("#c-copy").textContent = t.copied; toast(t.copied); } catch (e) { /* ignore */ }
    });
  }

  async function download(path, name) {
    const res = await fetch(path, { headers: { "X-Session-Token": state.token } });
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }

  // ------------------------------------------------------------------ session
  // Saved consultations live on this device (id + token + title); the case itself is on the server.
  function savedList() { try { return JSON.parse(store.get("ll_sessions") || "[]"); } catch (e) { return []; } }
  function saveList(list) { store.set("ll_sessions", JSON.stringify(list.slice(0, 50))); }
  function remember() {
    if (!state.id) return;
    const list = savedList().filter(x => x.id !== state.id);
    const sm = state.summary || {};
    list.unshift({ id: state.id, token: state.token, title: sm.title || "", updated: sm.updated || new Date().toISOString(),
                   lang: sm.lang || state.lang, urgent: !!sm.urgent, ready: !!sm.consultation_ready, acct: !!state.user });
    saveList(list);
    store.set("ll_session", JSON.stringify({ id: state.id, token: state.token }));
  }
  function forget(id) { saveList(savedList().filter(x => x.id !== id)); }

  function clearPanels() {
    state.consult = null;
    $("#messages").innerHTML = ""; setChips([]); $("#urgent").hidden = true; CaseGraph.reset();
    $("#graph").innerHTML = ""; $("#tab-facts").innerHTML = "";
    $("#tab-laws").innerHTML = `<div class="empty">${esc(ui().no_laws)}</div>`;
    $("#tab-consult").innerHTML = `<div class="empty">${esc(ui().no_consult)}</div>`;
    state.drafts = null; state.draftKind = null;
    $("#tab-drafts").innerHTML = `<div class="empty">${esc(ui().no_consult)}</div>`;
  }

  // ------------------------------------------------------------------ account
  function renderUser() {
    const t = ui(), u = state.user;
    $("#u-name").textContent = u ? u.name : t.u_guest;
    $("#u-sub").textContent = u ? u.email : t.u_guest_sub;
    $("#u-avatar").textContent = u ? (u.name.trim().split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase() || "🙂") : "👤";
    $("#user-card").classList.toggle("signed-in", !!u);
    $("#u-signin").hidden = !!u; $("#u-signout").hidden = !u; $("#u-delete").hidden = !u;
  }

  // Attach this device's guest consultations to the account, then take the account's list as the truth.
  async function syncAccount() {
    if (!state.user) return;
    for (const x of savedList().filter(x => !x.acct)) {
      try { await fetch(`/api/me/consultations/${encodeURIComponent(x.id)}/link`, { method: "POST", headers: { "X-Session-Token": x.token } }); }
      catch (e) { /* offline */ }
    }
    try {
      const r = await api("GET", "/api/me/consultations");
      const server = r.consultations.map(x => ({ ...x, acct: true }));
      const ids = new Set(server.map(x => x.id));
      saveList(server.concat(savedList().filter(x => !ids.has(x.id) && !x.acct)));
      renderSideHistory();
    } catch (e) { /* keep the local list */ }
  }

  async function signOut() {
    try { await api("POST", "/api/auth/logout"); } catch (e) { /* ignore */ }
    saveList(savedList().filter(x => !x.acct));          // do not leave the account's cases on a shared device
    store.del("ll_session"); store.del("ll_guest");
    location.href = "/login";
  }

  async function deleteAccount() {
    if (!window.confirm(ui().u_confirm_delete)) return;
    try { await api("DELETE", "/api/me"); } catch (e) { toast(e.message); return; }
    saveList(savedList().filter(x => !x.acct));
    store.del("ll_session"); store.del("ll_guest");
    toast(ui().u_deleted);
    setTimeout(() => { location.href = "/login"; }, 900);
  }

  async function startSession(useLlm) {
    const r = await api("POST", "/api/session", { lang: state.lang, use_llm: useLlm });
    state.id = r.session_id; state.token = r.token; state.summary = r.summary;
    clearPanels();
    r.messages.forEach(addMessage);
    state.lastGraph = r.graph; drawGraph(); renderFacts(); applyUI();
    remember(); renderSideHistory();
    if (state.prefill) { $("#input").value = state.prefill; state.prefill = null; autoGrow(); }
    $("#input").focus();
  }

  async function openSession(id, token) {
    state.id = id; state.token = token;
    const r = await api("GET", `/api/session/${id}`);
    state.summary = r.summary; state.lang = r.summary.lang || state.lang; store.set("ll_lang", state.lang);
    clearPanels();
    r.messages.forEach(addMessage);
    const last = [...r.messages].reverse().find(m => m.role === "assistant");
    setChips(last ? last.chips : []);
    if (state.summary.urgent) { const a = r.messages.filter(m => m.kind === "alert").pop(); if (a) { $("#urgent").textContent = a.text; $("#urgent").hidden = false; } }
    state.lastGraph = r.graph; applyUI(); drawGraph(); renderFacts();
    remember(); renderHeader(); renderSideHistory(); closeMenu();
    if (state.summary.consultation_ready && !$("#tab-graph").classList.contains("active")) loadConsultation();
  }

  async function resume() {
    const saved = store.get("ll_session");
    if (!saved) return false;
    try { const s = JSON.parse(saved); await openSession(s.id, s.token); return true; }
    catch (e) { store.del("ll_session"); state.id = state.token = null; return false; }
  }

  function resetSession() {
    store.del("ll_session"); state.id = state.token = null;
    clearPanels();
    state.summary = {};
    renderHeader(); renderSideHistory(); closeMenu();
    $("#welcome").hidden = false;
    $("#welcome-history").hidden = !savedList().length;
  }

  // Compact list of recent consultations in the sidebar.
  function renderSideHistory() {
    const t = ui(), list = savedList(), box = $("#side-history");
    if (!box) return;
    if (!list.length) { box.innerHTML = `<div class="side-empty">${esc(t.history_empty)}</div>`; $("#history").hidden = true; return; }
    $("#history").hidden = false;
    box.innerHTML = list.slice(0, 6).map(x => `<button class="side-item${x.id === state.id ? " current" : ""}" data-id="${esc(x.id)}">
        <b>${x.urgent ? "⚠ " : x.ready ? "✓ " : ""}${esc(x.title || t.new)}</b><small>${esc(new Date(x.updated).toLocaleDateString())}</small></button>`).join("");
    box.querySelectorAll(".side-item").forEach(b => b.addEventListener("click", async () => {
      const item = list.find(x => x.id === b.dataset.id);
      if (item.id === state.id) { closeMenu(); return; }
      try { await openSession(item.id, item.token); $("#welcome").hidden = true; }
      catch (e) { forget(item.id); toast(t.expired); renderSideHistory(); }
    }));
  }

  function openMenu() { $("#app").classList.add("menu-open"); $("#scrim").hidden = false; }
  function closeMenu() { $("#app").classList.remove("menu-open"); $("#scrim").hidden = true; }
  function setView(v) {
    $("#workspace").classList.toggle("case-view", v === "case");
    $("#view-chat").classList.toggle("active", v !== "case");
    $("#view-case").classList.toggle("active", v === "case");
    if (v === "case") drawGraph();
  }
  function autoGrow() { const i = $("#input"); i.style.height = "auto"; i.style.height = Math.min(i.scrollHeight, 160) + "px"; }
  function isDark() { return (document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark"; }
  function applyTheme(th) {
    if (th === "light" || th === "dark") document.documentElement.dataset.theme = th;
    else delete document.documentElement.dataset.theme;
    $("#theme").textContent = isDark() ? "☀️" : "🌙";
  }

  function renderHistory() {
    const t = ui(), list = savedList(), box = $("#history-list");
    if (!list.length) { box.innerHTML = `<p class="empty">${esc(t.history_empty)}</p>`; return; }
    box.innerHTML = list.map(x => `<div class="hist-item${x.id === state.id ? " current" : ""}" data-id="${esc(x.id)}">
        <div class="info"><strong>${x.urgent ? "⚠ " : ""}${esc(x.title || "—")}</strong>
        <span>${esc(t.last_updated)}: ${esc(new Date(x.updated).toLocaleString())}${x.id === state.id ? " · " + esc(t.current) : ""}</span></div>
        <button class="btn small primary" data-act="open">${esc(t.open)}</button>
        <button class="btn small danger" data-act="del">${esc(t.remove)}</button></div>`).join("");
    box.querySelectorAll(".hist-item").forEach(row => {
      const item = list.find(x => x.id === row.dataset.id);
      row.querySelector('[data-act="open"]').addEventListener("click", async () => {
        try { await openSession(item.id, item.token); $("#history-panel").hidden = true; $("#welcome").hidden = true; }
        catch (e) { forget(item.id); row.querySelector(".info span").textContent = t.expired; setTimeout(renderHistory, 900); }
      });
      row.querySelector('[data-act="del"]').addEventListener("click", async () => {
        if (!window.confirm(t.confirm_delete)) return;
        const prev = state.token; state.token = item.token;
        try { await api("DELETE", `/api/session/${item.id}`); } catch (e) { /* already gone */ }
        state.token = prev;
        forget(item.id);
        if (item.id === state.id) resetSession();
        renderHistory(); renderSideHistory(); toast(t.deleted);
      });
    });
  }

  // ------------------------------------------------------------------ wiring
  async function init() {
    try { state.user = (await api("GET", "/api/auth/me")).user; } catch (e) { state.user = null; }
    if (!state.user && store.get("ll_guest") !== "1") { location.replace("/login"); return; }
    try { state.config = await api("GET", "/api/config"); } catch (e) { state.config = {}; }
    const savedLang = store.get("ll_lang");
    if (savedLang && window.UI[savedLang]) state.lang = savedLang;
    state.tts = store.get("ll_tts") === "1";
    $("#tts").textContent = state.tts ? "🔊" : "🔇"; $("#tts").setAttribute("aria-pressed", String(state.tts));
    $("#ai-consent-row").hidden = !state.config.llm_available;
    applyUI();
    document.querySelectorAll(".lang-pick button").forEach(b => {
      b.classList.toggle("sel", b.dataset.lang === state.lang);
      b.addEventListener("click", () => {
        state.lang = b.dataset.lang; store.set("ll_lang", state.lang);
        document.querySelectorAll(".lang-pick button").forEach(x => x.classList.toggle("sel", x === b));
        applyUI();
      });
    });
    $("#start").addEventListener("click", async () => {
      $("#welcome").hidden = true;
      try { await startSession(state.config.llm_available && $("#ai-consent").checked); }
      catch (e) { addMessage({ role: "assistant", kind: "alert", text: e.message }); }
    });
    $("#composer").addEventListener("submit", (ev) => {
      ev.preventDefault();
      const inp = $("#input"), text = inp.value.trim();
      if (!text) return;
      if (recording) stopVoice();
      const source = inp.dataset.source === "voice" ? "voice" : "text";
      const conf = inp.dataset.conf ? parseFloat(inp.dataset.conf) : null;
      inp.value = ""; inp.dataset.source = ""; inp.dataset.conf = ""; voiceStatus(""); autoGrow();
      send({ text, source, asr_confidence: source === "voice" ? conf : null });
    });
    $("#input").addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); $("#composer").requestSubmit(); }
    });
    $("#input").addEventListener("input", autoGrow);
    applyTheme(store.get("ll_theme"));
    $("#theme").addEventListener("click", () => {
      const next = isDark() ? "light" : "dark";
      applyTheme(next); store.set("ll_theme", next); drawGraph();
    });
    $("#menu-btn").addEventListener("click", openMenu);
    $("#scrim").addEventListener("click", closeMenu);
    $("#view-chat").addEventListener("click", () => setView("chat"));
    $("#view-case").addEventListener("click", () => setView("case"));
    $("#mic").addEventListener("click", () => recording ? stopVoice() : startVoice());
    $("#tts").addEventListener("click", () => {
      state.tts = !state.tts; store.set("ll_tts", state.tts ? "1" : "0");
      $("#tts").textContent = state.tts ? "🔊" : "🔇"; $("#tts").setAttribute("aria-pressed", String(state.tts));
      if (!state.tts && "speechSynthesis" in window) speechSynthesis.cancel();
    });
    $("#lang").addEventListener("change", async () => {
      state.lang = $("#lang").value; store.set("ll_lang", state.lang); applyUI();
      if (state.id) {
        try { const r = await api("PATCH", `/api/session/${state.id}`, { lang: state.lang }); state.summary = r.summary; } catch (e) { /* ignore */ }
        const g = await api("GET", `/api/session/${state.id}/graph`); state.lastGraph = g; drawGraph(); renderFacts();
        if (state.consult) loadConsultation();
        state.drafts = null;
        if ($("#tab-drafts").classList.contains("active")) loadDrafts();
      }
    });
    $("#new").addEventListener("click", () => { resetSession(); });
    $("#history").addEventListener("click", () => { renderHistory(); closeMenu(); $("#history-panel").hidden = false; });
    $("#welcome-history").hidden = !savedList().length;
    $("#welcome-history").addEventListener("click", () => { renderHistory(); $("#history-panel").hidden = false; });
    $("#history-close").addEventListener("click", () => { $("#history-panel").hidden = true; });
    $("#history-new").addEventListener("click", () => { $("#history-panel").hidden = true; resetSession(); });
    $("#delete").addEventListener("click", async () => {
      if (!state.id) { resetSession(); return; }
      if (!window.confirm(ui().confirm_delete)) return;
      try { await api("DELETE", `/api/session/${state.id}`); } catch (e) { /* already gone */ }
      forget(state.id); resetSession(); toast(ui().deleted);
    });
    $("#get-consult").addEventListener("click", () => { setView("case"); showTab("consult"); });
    document.querySelectorAll(".tabs button").forEach(b => b.addEventListener("click", () => showTab(b.dataset.tab)));
    window.addEventListener("resize", () => drawGraph());
    $("#g-claims").addEventListener("change", e => CaseGraph.setOption("showClaims", e.target.checked, $("#graph")));
    $("#g-unlikely").addEventListener("change", e => CaseGraph.setOption("showUnlikely", e.target.checked, $("#graph")));
    $("#g-zoom-in").addEventListener("click", () => CaseGraph.zoom(1.2, $("#graph")));
    $("#g-zoom-out").addEventListener("click", () => CaseGraph.zoom(1 / 1.2, $("#graph")));
    $("#g-full").addEventListener("click", () => {
      const w = $("#graph-wrap");
      const on = !w.classList.contains("full");
      w.classList.toggle("full", on);
      let close = $("#g-close");
      if (on && !close) {
        close = document.createElement("button");
        close.id = "g-close"; close.className = "btn primary graph-close"; close.textContent = "✕";
        close.addEventListener("click", () => $("#g-full").click());
        document.body.appendChild(close);
      } else if (!on && close) close.remove();
      drawGraph();
    });
    document.addEventListener("keydown", e => {
      if (e.key !== "Escape") return;
      if ($("#graph-wrap").classList.contains("full")) $("#g-full").click();
      else if (!$("#history-panel").hidden) $("#history-panel").hidden = true;
      else closeMenu();
    });
    renderUser();
    $("#u-menu-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      const m = $("#u-menu"); m.hidden = !m.hidden; $("#u-menu-btn").setAttribute("aria-expanded", String(!m.hidden));
    });
    document.addEventListener("click", (e) => { if (!$("#user-card").contains(e.target)) $("#u-menu").hidden = true; });
    $("#u-signout").addEventListener("click", signOut);
    $("#u-delete").addEventListener("click", deleteAccount);
    await syncAccount();
    if (await resume()) $("#welcome").hidden = true;
  }
  document.addEventListener("DOMContentLoaded", init);
})();
