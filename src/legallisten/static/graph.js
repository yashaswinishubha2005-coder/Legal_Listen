/* Legal Case Graph as a readable left-to-right "case map" (no dependencies).
 *
 *   People  →  (Your statements)  →  What happened & evidence  →  Legal requirements  →  Legal issues  →  Laws
 *
 * Cards are coloured by epistemic status; clicking a card highlights everything connected to it.
 * Statements (Claim nodes) are hidden by default and their links are drawn through to what they are about.
 */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const CARD_W = 152, GAP_X = 30, GAP_Y = 10, PAD = 14, HEAD = 34, LINE_H = 14, FONT = 11.5;
  const STATUS = {
    evidence_supported: { fill: "#e3f4ea", stroke: "#2e9e5b", key: "evidence_supported" },
    reported: { fill: "#e7f0fa", stroke: "#3b78b8", key: "reported" },
    inferred: { fill: "#fff4e0", stroke: "#c98a1a", key: "inferred" },
    conflicting: { fill: "#fdecea", stroke: "#d62728", key: "conflicting" },
    contradicted: { fill: "#f1f1f1", stroke: "#8a8a8a", key: "contradicted" },
    unknown: { fill: "#fff8ec", stroke: "#e39b2d", key: "unknown", dash: "4 3" },
    not_discussed: { fill: "#f7f8fa", stroke: "#b8c0cc", key: "not_discussed", dash: "2 3" },
    neutral: { fill: "#ffffff", stroke: "#9aa6b4", key: "" },
  };
  const TYPE_ACCENT = { Person: "#1f77b4", Organization: "#4c78a8", Event: "#f58518", Evidence: "#54a24b", Risk: "#d62728",
    Claim: "#72b7b2", Element: "#9d755d", Issue: "#7b4fa0", Provision: "#c43c39" };
  let state = { graph: null, opts: {}, showClaims: false, showUnlikely: false, scale: 1, selected: null };

  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  function wrap(text, maxChars, maxLines) {
    const words = String(text || "").split(/\s+/).filter(Boolean);
    const lines = [];
    let cur = "";
    for (const w of words) {
      if ((cur + " " + w).trim().length > maxChars && cur) { lines.push(cur); cur = w; } else cur = (cur + " " + w).trim();
      if (lines.length === maxLines) break;
    }
    if (lines.length < maxLines && cur) lines.push(cur);
    const used = lines.join(" ").length;
    if (used < String(text || "").trim().length - 1 && lines.length) lines[lines.length - 1] = lines[lines.length - 1].replace(/.{0,2}$/, "…");
    return lines.map(l => (l.length > maxChars + 6 ? l.slice(0, maxChars + 4) + "…" : l));
  }

  function statusOf(n) {
    if (n.type === "Element") {
      if (n.status === "conflicting") return STATUS.conflicting;
      if (n.value === "not_discussed") return STATUS.not_discussed;
      if (n.value === "unknown") return STATUS.unknown;
      if (n.value === "contradicted") return STATUS.contradicted;
      return STATUS[n.status] || STATUS.reported;
    }
    if (n.type === "Claim") return STATUS[n.status] || STATUS.reported;
    if (n.type === "Evidence") return n.availability === "held" ? STATUS.evidence_supported : n.availability === "missing" ? STATUS.contradicted : STATUS.unknown;
    if (n.type === "Risk") return STATUS.conflicting;
    if (n.type === "Issue") return n.identified ? STATUS.reported : STATUS.not_discussed;
    return STATUS.neutral;
  }

  // --------------------------------------------------------------- model
  function build(graph, ui) {
    const t = ui || {};
    const nodes = {};
    (graph.nodes || []).forEach(n => { nodes[n.id] = n; });
    const issues = Object.values(nodes).filter(n => n.type === "Issue" && (state.showUnlikely || n.identified || (n.belief || 0) >= 0.5));
    const keepIssue = new Set(issues.map(n => n.id));
    if (!issues.length) Object.values(nodes).filter(n => n.type === "Issue").forEach(n => keepIssue.add(n.id));
    const elemIssue = {};
    (graph.edges || []).forEach(e => { if (e.type === "HAS_ELEMENT") elemIssue[e.target] = e.source; });
    const visible = n => {
      if (n.type === "Question" || n.type === "Contradiction") return false;
      if (n.type === "Claim") return state.showClaims;
      if (n.type === "Event") return !!n.date && !n.negated;   // undated events repeat the requirement cards
      if (n.type === "Issue") return keepIssue.has(n.id);
      if (n.type === "Element") return keepIssue.has(elemIssue[n.id]);
      return true;
    };
    const vis = {};
    Object.values(nodes).forEach(n => { if (visible(n)) vis[n.id] = n; });
    // edges, drawing statements through when they are hidden
    const edges = [];
    const add = (a, b, type) => { if (vis[a] && vis[b] && a !== b) edges.push({ source: a, target: b, type }); };
    const claimLinks = {};
    (graph.edges || []).forEach(e => {
      const s = nodes[e.source], d = nodes[e.target];
      if (!s || !d) return;
      if (!state.showClaims && (s.type === "Claim" || d.type === "Claim")) {
        const c = s.type === "Claim" ? s.id : d.id, other = s.type === "Claim" ? d.id : s.id;
        (claimLinks[c] = claimLinks[c] || []).push({ other, type: e.type });
        return;
      }
      if (["ASSERTS", "RAISES"].includes(e.type)) return;
      add(e.source, e.target, e.type);
    });
    Object.values(claimLinks).forEach(list => {
      const els = list.filter(x => x.type === "BEARS_ON").map(x => x.other);
      const evs = list.filter(x => x.type === "ABOUT").map(x => x.other);
      const sup = list.filter(x => x.type === "SUPPORTS").map(x => x.other);
      els.forEach(elId => { evs.forEach(ev => add(ev, elId, "ABOUT")); sup.forEach(sv => add(sv, elId, "SUPPORTS")); });
      const con = list.filter(x => x.type === "CONTRADICTS");
      if (con.length) els.forEach(elId => { if (vis[elId]) vis[elId].status = "conflicting"; });
    });
    // columns
    const cols = [
      { key: "people", title: t.col_people || "People", types: ["Person", "Organization"] },
      ...(state.showClaims ? [{ key: "claims", title: t.col_claims || "Your statements", types: ["Claim"] }] : []),
      { key: "events", title: t.col_events || "What happened & evidence", types: ["Risk", "Event", "Evidence"] },
      { key: "elements", title: t.col_elements || "Legal requirements", types: ["Element"] },
      { key: "issues", title: t.col_issues || "Legal issues", types: ["Issue"] },
      { key: "laws", title: t.col_laws || "Laws (to verify)", types: ["Provision"] },
    ];
    cols.forEach(c => { c.items = Object.values(vis).filter(n => c.types.includes(n.type)); });
    // ordering: issues by belief; elements grouped under their issue; laws by issue; events by date
    const issueRank = {};
    cols.find(c => c.key === "issues").items.sort((a, b) => (b.belief || 0) - (a.belief || 0)).forEach((n, i) => { issueRank[n.id] = i; });
    cols.find(c => c.key === "elements").items.sort((a, b) =>
      (issueRank[elemIssue[a.id]] ?? 99) - (issueRank[elemIssue[b.id]] ?? 99) || (a.order || 0) - (b.order || 0));
    const lawIssue = {};
    edges.forEach(e => { if (e.type === "APPLIES_TO") lawIssue[e.source] = e.target; });
    cols.find(c => c.key === "laws").items.sort((a, b) => (issueRank[lawIssue[a.id]] ?? 99) - (issueRank[lawIssue[b.id]] ?? 99));
    const typeOrder = { Risk: 0, Event: 1, Evidence: 2, Person: 0, Organization: 1 };
    ["events", "people"].forEach(k => cols.find(c => c.key === k).items.sort((a, b) =>
      (typeOrder[a.type] - typeOrder[b.type]) || String(a.date || "").localeCompare(String(b.date || "")) || (a.id === "per_0" ? -1 : b.id === "per_0" ? 1 : 0)));
    return { cols, edges, vis, elemIssue };
  }

  function layout(model) {
    let maxH = 0;
    model.cols.forEach((c, ci) => {
      c.x = PAD + ci * (CARD_W + GAP_X);
      let y = HEAD + 6;
      let lastIssue = null;
      c.items.forEach(n => {
        const maxChars = 22;
        let lines = wrap(n.label, maxChars, n.type === "Claim" ? 3 : 2);
        const sub = subtitle(n);
        n._lines = lines;
        n._sub = sub;
        n._h = 10 + lines.length * LINE_H + (sub ? LINE_H : 0) + (n.type === "Issue" ? 8 : 0);
        if (c.key === "elements" && model.elemIssue[n.id] !== lastIssue && lastIssue !== null) y += 10;  // group gap
        lastIssue = model.elemIssue[n.id] || lastIssue;
        n._x = c.x; n._y = y;
        y += n._h + GAP_Y;
      });
      c.h = y;
      maxH = Math.max(maxH, y);
    });
    return { width: PAD * 2 + model.cols.length * CARD_W + (model.cols.length - 1) * GAP_X, height: maxH + PAD };
  }

  function subtitle(n) {
    const ui = state.opts.ui || {};
    if (n.type === "Element") {
      if (n.status === "conflicting") return "⚠ " + (ui.conflicting || "conflicting");
      if (n.value === "not_discussed") return "? " + (ui.not_discussed || "not discussed yet");
      if (n.value === "unknown") return "? " + (ui.unknown || "unknown");
      if (n.value === "contradicted") return "✗ " + (ui.contradicted || "no");
      return (n.status === "evidence_supported" ? "✔✔ " : "✔ ") + (ui[n.status] || n.status);
    }
    if (n.type === "Issue") return Math.round((n.belief || 0) * 100) + "%";
    if (n.type === "Provision") return n.title_hint || "";
    if (n.type === "Event") return (n.date || "") + (n.negated ? " ✗" : "");
    if (n.type === "Evidence") return ui[n.availability] || n.availability;
    if (n.type === "Person" && n.relation) return n.relation.replace(/_/g, " ");
    if (n.type === "Claim") return ui[n.status] || n.status;
    return "";
  }

  // --------------------------------------------------------------- draw
  function draw(svg) {
    const ui = state.opts.ui || {};
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    const model = build(state.graph, ui);
    const size = layout(model);
    const container = svg.parentElement;
    const avail = Math.max(320, (container && container.clientWidth) || 640);
    const fit = Math.min(1, avail / size.width);
    const scale = Math.max(0.86, fit) * state.scale;
    svg.setAttribute("viewBox", `0 0 ${size.width} ${size.height}`);
    svg.style.width = Math.round(size.width * scale) + "px";
    svg.style.height = Math.round(size.height * scale) + "px";
    if (!Object.keys(model.vis).length) return;
    const defs = el("defs", {}, svg);
    const mk = el("marker", { id: "arrow", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" }, defs);
    el("path", { d: "M 0 0 L 10 5 L 0 10 z", class: "arrowhead" }, mk);
    // column headers + guides
    model.cols.forEach(c => {
      el("rect", { x: c.x - 6, y: 4, width: CARD_W + 12, height: Math.max(c.h, size.height - PAD) - 4, rx: 10, class: "col-bg" }, svg);
      const h = el("text", { x: c.x + CARD_W / 2, y: 22, class: "col-title", "text-anchor": "middle" }, svg);
      h.textContent = c.title + (c.items.length ? ` (${c.items.length})` : "");
    });
    const gEdges = el("g", {}, svg), gNodes = el("g", {}, svg);
    const col = {};
    model.cols.forEach((c, i) => c.items.forEach(n => { col[n.id] = i; }));
    const edgeEls = [];
    model.edges.forEach(e => {
      const a = model.vis[e.source], b = model.vis[e.target];
      if (!a || !b) return;
      let L = a, R = b;
      if (col[a.id] > col[b.id]) { L = b; R = a; }
      const x1 = L._x + CARD_W, y1 = L._y + L._h / 2, x2 = R._x, y2 = R._y + R._h / 2;
      let d;
      if (col[L.id] === col[R.id]) {
        const xr = L._x + CARD_W;
        d = `M ${xr} ${y1} C ${xr + 30} ${y1}, ${xr + 30} ${R._y + R._h / 2}, ${xr} ${R._y + R._h / 2}`;
      } else {
        const mx = (x1 + x2) / 2;
        d = `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
      }
      const p = el("path", { d, class: "link " + e.type + (e.type === "RELEVANT_BECAUSE" ? " secondary" : ""), fill: "none" }, gEdges);
      p._ends = [e.source, e.target];
      edgeEls.push(p);
    });
    const cardEls = {};
    Object.values(model.vis).forEach(n => {
      const st = statusOf(n);
      const g = el("g", { transform: `translate(${n._x},${n._y})`, class: "card-node", tabindex: 0 }, gNodes);
      el("rect", { width: CARD_W, height: n._h, rx: 8, fill: st.fill, stroke: st.stroke, "stroke-width": 1.6, "stroke-dasharray": st.dash, class: "card-box" }, g);
      el("rect", { width: 4, height: n._h - 8, x: 3, y: 4, rx: 2, fill: TYPE_ACCENT[n.type] || "#999" }, g);
      n._lines.forEach((line, i) => {
        const tx = el("text", { x: 12, y: 15 + i * LINE_H, class: "card-text" + (n.type === "Issue" || n.type === "Provision" ? " strong" : "") }, g);
        tx.textContent = line;
      });
      if (n._sub) {
        const tx = el("text", { x: 12, y: 15 + n._lines.length * LINE_H, class: "card-sub" }, g);
        tx.textContent = wrap(n._sub, 28, 1)[0] || "";
      }
      if (n.type === "Issue") {
        el("rect", { x: 12, y: n._h - 9, width: CARD_W - 24, height: 4, rx: 2, class: "bar-bg" }, g);
        el("rect", { x: 12, y: n._h - 9, width: (CARD_W - 24) * Math.max(0.02, n.belief || 0), height: 4, rx: 2, class: "bar-fg" }, g);
      }
      const title = el("title", {}, g); title.textContent = n.label + (n.answer ? " — " + n.answer : "") + (n.quote ? " — “" + n.quote + "”" : "");
      const select = () => {
        state.selected = state.selected === n.id ? null : n.id;
        highlight(cardEls, edgeEls, model);
        if (state.opts.onSelect) state.opts.onSelect(n);
      };
      g.addEventListener("click", select);
      g.addEventListener("keydown", ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); select(); } });
      cardEls[n.id] = g;
    });
    highlight(cardEls, edgeEls, model);
  }

  function highlight(cardEls, edgeEls, model) {
    const sel = state.selected && model.vis[state.selected] ? state.selected : null;
    if (!sel) {
      Object.values(cardEls).forEach(g => g.classList.remove("dim", "sel"));
      edgeEls.forEach(p => p.classList.remove("dim", "hot"));
      return;
    }
    const near = new Set([sel]);
    edgeEls.forEach(p => { if (p._ends.includes(sel)) p._ends.forEach(x => near.add(x)); });
    // second hop towards issues / laws so the legal chain is visible
    const n0 = model.vis[sel];
    if (n0 && ["Element", "Event", "Evidence", "Person"].includes(n0.type)) {
      edgeEls.forEach(p => { if ([...near].some(x => p._ends.includes(x)) && p._ends.some(x => ["Issue", "Element"].includes((model.vis[x] || {}).type))) p._ends.forEach(x => near.add(x)); });
    }
    Object.entries(cardEls).forEach(([id, g]) => { g.classList.toggle("dim", !near.has(id)); g.classList.toggle("sel", id === sel); });
    edgeEls.forEach(p => { const hot = p._ends.every(x => near.has(x)); p.classList.toggle("hot", hot); p.classList.toggle("dim", !hot); });
  }

  window.CaseGraph = {
    reset() { state.selected = null; },
    render(svg, graph, opts) { state.graph = graph; state.opts = opts || {}; draw(svg); },
    redraw(svg) { if (state.graph) draw(svg); },
    setOption(name, value, svg) { state[name] = value; if (state.graph) draw(svg); },
    zoom(f, svg) { state.scale = Math.max(0.5, Math.min(2.2, state.scale * f)); if (state.graph) draw(svg); },
    legend(container, ui) {
      const t = ui || {};
      container.innerHTML = "";
      const items = [["evidence_supported", t.evidence_supported || "evidence-supported"], ["reported", t.reported || "you reported"],
        ["inferred", t.inferred || "inferred"], ["unknown", (t.unknown || "unknown") + " / " + (t.missing_info || "missing")],
        ["not_discussed", t.not_discussed || "not discussed"], ["contradicted", t.contradicted || "no / not met"],
        ["conflicting", t.conflicting || "conflicting"]];
      items.forEach(([k, label]) => {
        const st = STATUS[k];
        const s = document.createElement("span");
        s.innerHTML = `<i style="background:${st.fill};border:1.6px ${st.dash ? "dashed" : "solid"} ${st.stroke}"></i>`;
        s.appendChild(document.createTextNode(label));
        container.appendChild(s);
      });
    },
  };
})();
