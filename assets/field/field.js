// The opening field: one dot per notice, rearranged between four groupings.
// Canvas for the dots (thousands of them), DOM for text so it stays crisp
// and selectable. Animation runs only while something moves.

// Indexed like the sorted theme names Python sends: AI & machine learning,
// Analytics & BI, Data engineering, Data infrastructure, Database services.
const THEME_COLORS = ["#E6C35F", "#D9955E", "#A68BD6", "#6F98D8", "#5FB59F", "#9AA1A9", "#D4797A"];
const VIEWS = {
  fit: { caption: "Grouped by profile fit. Colour shows the technology theme." },
  theme: { caption: "Grouped by technology theme." },
  country: { caption: "Grouped by buyer country, busiest first. Hover a column for its name." },
  deadline: { caption: "Grouped by time left to submit, measured from today (UTC)." },
};
const REDUCED = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const easeOut = (t) => 1 - Math.pow(1 - t, 4);

function groupsFor(view, d) {
  const n = d.id.length;
  let keys, labels, order;
  if (view === "theme") {
    keys = d.th; labels = d.themes.map((name) => ({ name }));
  } else if (view === "country") {
    keys = d.c; labels = d.countries.map((code, i) => ({ name: code, full: d.countryNames[i] }));
  } else if (view === "deadline") {
    keys = d.d; labels = d.buckets.map((name, i) => ({ name, muted: i === 0 || i === d.buckets.length - 1 }));
  } else {
    let lo = 100, hi = 0;
    for (let i = 0; i < n; i++) { lo = Math.min(lo, d.f[i]); hi = Math.max(hi, d.f[i]); }
    lo = Math.floor(lo / 5) * 5; hi = Math.floor(hi / 5) * 5;
    labels = []; for (let b = lo; b <= hi; b += 5) labels.push({ name: `${b}–${Math.min(b + 4, 100)}` });
    keys = new Int16Array(n); for (let i = 0; i < n; i++) keys[i] = Math.floor(d.f[i] / 5) - lo / 5;
  }
  const members = labels.map(() => []);
  for (let i = 0; i < n; i++) members[keys[i]].push(i);
  // Stack each column in theme bands, highest fit first within a band, so the
  // colours settle into clean strata instead of noise.
  members.forEach((m) => m.sort((a, b) => d.th[a] - d.th[b] || d.f[b] - d.f[a] || a - b));
  order = labels.map((_, g) => g);
  if (view === "theme" || view === "country") order.sort((a, b) => members[b].length - members[a].length);
  return order.map((g) => ({ ...labels[g], members: members[g] }));
}

function layout(view, d, W, H) {
  const groups = groupsFor(view, d);
  const labelSpace = view === "country" ? 22 : 34;
  const top = 8, usableH = H - labelSpace - top;
  const n = groups.length;
  const largest = Math.max(1, ...groups.map((g) => g.members.length));
  let best = null;
  for (const unit of [1, 2, 5, 10, 20]) {
    for (let cell = 9; cell >= 2.5; cell -= 0.5) {
      const gap = view === "country" ? Math.max(4, cell * 1.4) : Math.max(14, cell * 3);
      const perGroup = Math.floor((W - (n - 1) * gap) / n / cell);
      if (perGroup < 1) continue;
      const cols = Math.min(perGroup, Math.max(1, Math.ceil(Math.sqrt(largest / unit) * 1.9)));
      const rows = Math.ceil(largest / unit / cols);
      if (rows * cell <= usableH) { best = { unit, cell, gap, cols }; break; }
    }
    if (best) break;
  }
  if (!best) best = { unit: 50, cell: 2.5, gap: 4, cols: 1 };
  const { unit, cell, gap, cols } = best;
  const blockW = cols * cell;
  const totalW = n * blockW + (n - 1) * gap;
  const left = (W - totalW) / 2;
  const base = top + usableH;
  const pos = new Float32Array(d.id.length * 2);
  const visible = new Uint8Array(d.id.length);
  groups.forEach((g, gi) => {
    const x0 = left + gi * (blockW + gap);
    g.x = x0; g.w = blockW; g.cx = x0 + blockW / 2;
    g.rows = Math.ceil(g.members.length / unit / cols);
    g.members.forEach((idx, rank) => {
      const slot = Math.floor(rank / unit);
      const col = slot % cols, row = Math.floor(slot / cols);
      pos[idx * 2] = x0 + col * cell + cell / 2;
      pos[idx * 2 + 1] = base - row * cell - cell / 2;
      visible[idx] = rank % unit === 0 ? 1 : 0;
    });
  });
  return { groups, pos, visible, cell, unit, base, gap };
}

function formatInt(value) { return Math.round(value).toLocaleString("en-GB"); }

function createField(root, initial, setTriggerValue) {
  const $ = (s) => root.querySelector(s);
  const stage = $(".tm-stage"), canvas = $("canvas"), labelsEl = $(".tm-labels"), tip = $(".tm-tip");
  const ctx = canvas.getContext("2d");
  const buttons = [...root.querySelectorAll(".tm-views button")], ink = $(".tm-views__ink");
  const legend = $(".tm-legend"), caption = $('[data-slot="caption"]');
  const state = { d: null, view: null, W: 0, H: 0, cur: null, from: null, to: null, delay: null, alpha: null,
    alphaFrom: null, alphaTo: null, start: 0, dur: 0, raf: 0, hover: -1, focusTheme: -1, lay: null, grid: null, intro: true };

  function moveInk() {
    const active = buttons.find((b) => b.dataset.view === state.view) || buttons[0];
    ink.style.width = `${active.offsetWidth}px`;
    ink.style.transform = `translateX(${active.offsetLeft - 3}px)`;
    buttons.forEach((b) => b.setAttribute("aria-pressed", String(b === active)));
  }

  function resize() {
    const rect = stage.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    state.W = rect.width; state.H = rect.height;
    canvas.width = Math.round(rect.width * dpr); canvas.height = Math.round(rect.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function renderLabels(lay) {
    labelsEl.classList.remove("is-shown");
    const narrow = lay.groups.length > 12;
    labelsEl.innerHTML = "";
    lay.groups.forEach((g) => {
      const el = document.createElement("div");
      el.className = "tm-label" + (g.muted ? " is-muted" : "");
      el.style.left = `${g.cx}px`;
      const tooTight = narrow && g.w + lay.cell * 1.4 < 22;
      el.textContent = tooTight ? "" : g.name;
      if (!narrow) { const b = document.createElement("b"); b.textContent = formatInt(g.members.length); el.appendChild(b); }
      labelsEl.appendChild(el);
    });
    const unitText = lay.unit > 1 ? ` Each dot stands for ${lay.unit} notices.` : "";
    caption.textContent = VIEWS[state.view].caption + unitText;
    canvas.setAttribute("aria-label", `${formatInt(state.d.id.length)} notices grouped by ${state.view}: ` +
      lay.groups.slice(0, 12).map((g) => `${g.full || g.name} ${g.members.length}`).join(", "));
  }

  function buildGrid(lay) {
    const size = Math.max(lay.cell, 6), cols = Math.ceil(state.W / size) + 1, grid = new Map();
    const n = state.d.id.length;
    for (let i = 0; i < n; i++) {
      if (!lay.visible[i]) continue;
      const k = Math.floor(lay.pos[i * 2 + 1] / size) * cols + Math.floor(lay.pos[i * 2] / size);
      (grid.get(k) || grid.set(k, []).get(k)).push(i);
    }
    state.grid = { grid, size, cols };
  }

  function arrange(view, animate) {
    const d = state.d; if (!d) return;
    state.view = view; moveInk();
    try { sessionStorage.setItem("tm-field-view", view); } catch (e) { /* storage may be blocked */ }
    const lay = layout(view, d, state.W, state.H);
    const n = d.id.length;
    if (!state.cur || state.cur.length !== n * 2) {
      state.cur = new Float32Array(n * 2); state.alpha = new Float32Array(n);
      for (let i = 0; i < n; i++) { state.cur[i * 2] = lay.pos[i * 2]; state.cur[i * 2 + 1] = state.H + 12 + (i % 7) * 3; }
    }
    state.from = state.cur.slice(); state.alphaFrom = state.alpha.slice();
    state.to = lay.pos; state.alphaTo = new Float32Array(n);
    for (let i = 0; i < n; i++) state.alphaTo[i] = lay.visible[i] ? 1 : 0;
    state.delay = new Float32Array(n);
    const span = state.intro ? 900 : 420;
    for (let i = 0; i < n; i++) {
      const nx = lay.pos[i * 2] / Math.max(1, state.W), ny = 1 - lay.pos[i * 2 + 1] / Math.max(1, state.H);
      state.delay[i] = (nx * 0.75 + ny * 0.25) * span + ((i * 9301 + 49297) % 233280) / 233280 * 140;
    }
    state.dur = state.intro ? 1100 : 820;
    state.lay = lay; state.hover = -1; hideTip();
    renderLabels(lay); buildGrid(lay);
    if (!animate || REDUCED) {
      state.cur.set(lay.pos); state.alpha.set(state.alphaTo); state.start = 0; draw(); labelsEl.classList.add("is-shown"); return;
    }
    state.start = performance.now();
    kick();
  }

  function kick() { if (!state.raf) state.raf = requestAnimationFrame(frame); }

  function frame(now) {
    state.raf = 0;
    const { from, to, cur, delay, alpha, alphaFrom, alphaTo, dur } = state;
    const n = state.d.id.length, ease = state.intro ? easeOut : easeInOut;
    let moving = false;
    if (state.start) {
      const elapsed = now - state.start;
      for (let i = 0; i < n; i++) {
        let t = (elapsed - delay[i]) / dur;
        if (t < 1) moving = true;
        t = t <= 0 ? 0 : t >= 1 ? 1 : ease(t);
        cur[i * 2] = from[i * 2] + (to[i * 2] - from[i * 2]) * t;
        cur[i * 2 + 1] = from[i * 2 + 1] + (to[i * 2 + 1] - from[i * 2 + 1]) * t;
        alpha[i] = alphaFrom[i] + (alphaTo[i] - alphaFrom[i]) * t;
      }
      if (!moving) { state.start = 0; state.intro = false; labelsEl.classList.add("is-shown"); }
    }
    draw();
    if (moving) kick();
  }

  function draw() {
    const { d, cur, alpha, lay } = state; if (!d || !lay) return;
    ctx.clearRect(0, 0, state.W, state.H);
    const r = Math.max(0.9, lay.cell * 0.36), useRect = r < 1.6, n = d.id.length;
    // Faint baseline under every column.
    ctx.fillStyle = "rgba(255,255,255,.08)";
    lay.groups.forEach((g) => ctx.fillRect(g.x - 1, lay.base + 3, g.w + 2, 1));
    for (let theme = 0; theme < d.themes.length; theme++) {
      const dim = state.focusTheme >= 0 && state.focusTheme !== theme;
      ctx.fillStyle = THEME_COLORS[theme % THEME_COLORS.length];
      for (const pass of [0.35, 0.7, 1]) {
        ctx.globalAlpha = (dim ? 0.12 : 0.92) * pass;
        ctx.beginPath();
        let any = false;
        for (let i = 0; i < n; i++) {
          if (d.th[i] !== theme) continue;
          const a = alpha[i];
          if (a <= 0.01 || (pass === 1 ? a < 0.66 : pass === 0.7 ? a < 0.33 || a >= 0.66 : a >= 0.33)) continue;
          any = true;
          const x = cur[i * 2], y = cur[i * 2 + 1];
          if (useRect) ctx.rect(x - r, y - r, r * 2, r * 2);
          else { ctx.moveTo(x + r, y); ctx.arc(x, y, r, 0, Math.PI * 2); }
        }
        if (any) ctx.fill();
      }
    }
    ctx.globalAlpha = 1;
    if (state.hover >= 0 && !state.start) {
      const i = state.hover, x = cur[i * 2], y = cur[i * 2 + 1];
      ctx.beginPath(); ctx.arc(x, y, Math.max(r * 2.2, 4.5), 0, Math.PI * 2);
      ctx.fillStyle = THEME_COLORS[d.th[i] % THEME_COLORS.length]; ctx.fill();
      ctx.lineWidth = 1.5; ctx.strokeStyle = "#ECEDEE"; ctx.stroke();
    }
  }

  function nearest(px, py) {
    const { grid, size, cols } = state.grid, cur = state.cur;
    const gx = Math.floor(px / size), gy = Math.floor(py / size);
    let best = -1, bestD = Math.pow(Math.max(size, 7), 2);
    for (let yy = gy - 1; yy <= gy + 1; yy++) for (let xx = gx - 1; xx <= gx + 1; xx++) {
      const bucket = grid.get(yy * cols + xx); if (!bucket) continue;
      for (const i of bucket) {
        const dx = cur[i * 2] - px, dy = cur[i * 2 + 1] - py, dd = dx * dx + dy * dy;
        if (dd < bestD) { bestD = dd; best = i; }
      }
    }
    return best;
  }

  function groupAt(px) {
    const lay = state.lay;
    return lay.groups.find((g) => px >= g.x - lay.gap / 2 && px <= g.x + g.w + lay.gap / 2) || null;
  }

  function showTip(i, px, py) {
    const d = state.d, lay = state.lay;
    const metaEl = tip.querySelector(".tm-tip__meta"), titleEl = tip.querySelector(".tm-tip__title"), factsEl = tip.querySelector(".tm-tip__facts");
    metaEl.replaceChildren(); factsEl.replaceChildren();
    const swatch = document.createElement("i");
    swatch.style.background = THEME_COLORS[d.th[i] % THEME_COLORS.length];
    metaEl.append(swatch, document.createTextNode(`${d.countryNames[d.c[i]]} · ${d.id[i]}`));
    const facts = [["Fit", `${d.f[i]} / 100`], ["Deadline", d.dl[i] || "not disclosed"], ["Estimate", d.v[i] || "not disclosed"]];
    if (lay.unit > 1) {
      const g = groupAt(px);
      tip.classList.add("is-group");
      titleEl.textContent = g ? `${g.full || g.name}: ${formatInt(g.members.length)} notices` : d.t[i];
      metaEl.lastChild.textContent = d.themes[d.th[i]];
    } else {
      tip.classList.remove("is-group");
      titleEl.textContent = d.t[i];
      facts.forEach(([k, v]) => { const s = document.createElement("span"); s.append(`${k} `); const b = document.createElement("b"); b.textContent = v; s.append(b); factsEl.append(s); });
    }
    tip.hidden = false;
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    let x = px + 16, y = py - th - 14;
    if (x + tw > state.W) x = px - tw - 16;
    if (y < 0) y = py + 18;
    tip.style.left = `${Math.max(0, x)}px`; tip.style.top = `${Math.min(state.H - th, y)}px`;
  }
  function hideTip() { tip.hidden = true; stage.classList.remove("is-pointing"); }

  function onMove(event) {
    if (state.start || !state.grid) return;
    const rect = canvas.getBoundingClientRect(), px = event.clientX - rect.left, py = event.clientY - rect.top;
    const i = nearest(px, py);
    if (i !== state.hover) { state.hover = i; draw(); }
    if (i >= 0) { showTip(i, px, py); stage.classList.toggle("is-pointing", state.lay.unit === 1); }
    else if (state.view === "country") {
      const g = groupAt(px);
      if (g && g.members.length) { state.hover = -1; showTip(g.members[0], px, py); tip.classList.add("is-group"); tip.querySelector(".tm-tip__title").textContent = `${g.full}: ${formatInt(g.members.length)} notices`; tip.querySelector(".tm-tip__facts").replaceChildren(); }
      else hideTip();
    } else hideTip();
  }
  function onLeave() { state.hover = -1; hideTip(); draw(); }
  // Touch has no hover: the first tap shows the card, a second tap on the same dot opens it.
  let tapped = -1;
  function onClick(event) {
    if (event.pointerType && event.pointerType !== "mouse") {
      const previous = tapped;
      onMove(event);
      tapped = state.hover;
      if (tapped < 0 || tapped !== previous) return;
    }
    if (state.hover >= 0 && state.lay.unit === 1) setTriggerValue("open", state.d.id[state.hover]);
  }

  function renderLegend() {
    const d = state.d, counts = new Array(d.themes.length).fill(0);
    for (let i = 0; i < d.th.length; i++) counts[d.th[i]]++;
    legend.replaceChildren();
    d.themes.forEach((name, theme) => {
      if (!counts[theme]) return;
      const li = document.createElement("li"), button = document.createElement("button");
      button.type = "button";
      const dot = document.createElement("i"); dot.style.background = THEME_COLORS[theme % THEME_COLORS.length];
      const count = document.createElement("span"); count.textContent = formatInt(counts[theme]);
      button.append(dot, name, count);
      const on = () => { state.focusTheme = theme; legend.classList.add("is-focused"); button.classList.add("is-on"); draw(); };
      const off = () => { state.focusTheme = -1; legend.classList.remove("is-focused"); button.classList.remove("is-on"); draw(); };
      button.addEventListener("pointerenter", on); button.addEventListener("pointerleave", off);
      button.addEventListener("focus", on); button.addEventListener("blur", off);
      li.append(button); legend.append(li);
    });
  }

  function countUp(el, target) {
    if (REDUCED || !state.intro) { el.textContent = formatInt(target); return; }
    const start = performance.now(), dur = 1400;
    const step = (now) => {
      const t = Math.min(1, (now - start) / dur);
      el.textContent = formatInt(target * (1 - Math.pow(2, -10 * t)));
      if (t < 1) requestAnimationFrame(step); else el.textContent = formatInt(target);
    };
    requestAnimationFrame(step);
  }

  function update(d) {
    const same = state.d && state.d.signature === d.signature;
    state.d = d;
    $('[data-slot="updated"]').textContent = d.updated;
    $('[data-slot="title-rest"]').textContent = d.titleRest;
    if (!same) {
      countUp($('[data-slot="count"]'), d.id.length);
      renderLegend();
      if (state.view) { state.cur = null; state.intro = true; }
      arrange(state.view || d.initialView, true);
    }
  }

  buttons.forEach((b) => b.addEventListener("click", () => { if (b.dataset.view !== state.view) arrange(b.dataset.view, true); }));
  canvas.addEventListener("pointermove", onMove);
  canvas.addEventListener("pointerleave", onLeave);
  canvas.addEventListener("click", onClick);
  let resizeTimer = 0;
  const ro = new ResizeObserver(() => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      const before = state.W; resize();
      if (state.d && Math.abs(before - state.W) > 1) arrange(state.view, false);
      moveInk();
    }, 80);
  });
  resize(); ro.observe(stage);

  let initialView = "fit";
  try { initialView = sessionStorage.getItem("tm-field-view") || "fit"; } catch (e) { /* storage may be blocked */ }
  if (!VIEWS[initialView]) initialView = "fit";
  update({ ...initial, initialView });

  return {
    update: (d) => update({ ...d, initialView }),
    destroy: () => { ro.disconnect(); cancelAnimationFrame(state.raf); },
  };
}

export default function (component) {
  const { parentElement, data, setTriggerValue } = component;
  if (!data) return;
  if (parentElement.__tmField) parentElement.__tmField.update(data);
  else parentElement.__tmField = createField(parentElement, data, setTriggerValue);
  return () => {
    if (parentElement.__tmField && !parentElement.isConnected) {
      parentElement.__tmField.destroy();
      parentElement.__tmField = null;
    }
  };
}
