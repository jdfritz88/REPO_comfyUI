// web/selected_face_stack.js
//
// The trained-face strength notes, on BOTH the Face Shelf and the Selected Face
// LoRA Stack - the user's layout, 2026-09-25 (step letters live in the workflow
// titles, not here, so this reads right in every version):
//
//   Combined trained LoRA face strength (default) 1.0 =
//       0.4 face shelf + 0.3 row 1 + 0.2 row 2 + 0.1 row 3
//   Current: <live counter>
//
// The live counter adds the face shelf's strength and all three Selected Face LoRA Stack row
// strengths, ON or OFF (the user's choice for the counter), and updates the
// moment any of them changes - a change on either node refreshes both at once
// (the half-second timer is only a backstop, since Chrome slows timers in a
// background tab). Both nodes show the same number.
//
// The defaults are the user's (2026-09-25): shelf 0.4, rows 0.3 / 0.2 / 0.1,
// stronger first, each next one 0.1 lower. nodes.py FACE_SHELF_DEFAULT and
// FACE_PASS_DEFAULTS hold the same numbers.
//
// The Selected Face LoRA Stack also keeps: a "Reset to default" button (puts the three row strengths
// back to 0.3 / 0.2 / 0.1; the ON/OFF switches and the shelf are left alone), and
// one line per row - its ON/OFF button and strength box side by side, a gap
// between rows. The real enabled_N / strength_N widgets stay on the node, hidden,
// and are what get saved and sent to the server.
//
// Each note is a label rebuilt from the real settings, so it is marked
// serialize = false on the widget itself - frontend 1.53.6's
// serialiseWidgetValues and its positional restore both skip such widgets.
import { app } from "../../scripts/app.js";

const STACK = "FreedomSelectedFaceLoraStack";
const SHELF = "FreedomFaceShelf";
const SHELF_DEFAULT = 0.4;
const PASS_DEFAULTS = [0.3, 0.2, 0.1];
const ROWS = PASS_DEFAULTS.length;
const TOTAL_DEFAULT = SHELF_DEFAULT + PASS_DEFAULTS.reduce((a, b) => a + b, 0);
const FORMULA = `${TOTAL_DEFAULT.toFixed(1)} = ${SHELF_DEFAULT.toFixed(1)} face shelf + `
  + PASS_DEFAULTS.map((v, i) => `${v.toFixed(1)} row ${i + 1}`).join(" + ");

function css() {
  if (document.getElementById("freedom-sfs-css")) return;
  const s = document.createElement("style");
  s.id = "freedom-sfs-css";
  s.textContent = `
    .sfs-top { font: 12px/1.5 sans-serif; color: #ccc; padding: 4px 8px; margin: 0 4px;
               border: 1px solid #555; border-radius: 4px; background: #1c1c1c; }
    .sfs-top .row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
    .sfs-top .lbl { min-width: 70px; }
    .sfs-top .formula { color: #ddd; }
    .sfs-top .box { min-width: 70px; padding: 1px 8px; border: 1px solid #666;
                    border-radius: 3px; background: #111; color: #fff; font-weight: bold;
                    text-align: right; }
    .sfs-top .hint { color: #999; font-size: 11px; }
    .sfs-top button { margin-left: auto; font: 11px sans-serif; padding: 2px 8px;
                      background: #333; color: #eee; border: 1px solid #666;
                      border-radius: 3px; cursor: pointer; }
    .sfs-top button:hover { background: #444; }
    .sfs-top .passes { margin-top: 8px; border-top: 1px solid #444; padding-top: 6px; }
    .sfs-top .pass { display: flex; align-items: center; gap: 10px; margin: 0 0 10px 0; }
    .sfs-top .pass:last-child { margin-bottom: 2px; }
    .sfs-top .pass .name { min-width: 52px; color: #ddd; }
    .sfs-top .pass button.tog { margin-left: 0; min-width: 64px; }
    .sfs-top .pass button.tog.on { background: #2d5a2d; border-color: #4a4; color: #fff; }
    .sfs-top .pass input { width: 70px; background: #111; color: #fff; border: 1px solid #666;
                           border-radius: 3px; padding: 1px 4px; font: 12px sans-serif; }
    .sfs-top .pass .dflt { color: #888; font-size: 11px; }
    .sfs-shelfrow { display: flex; gap: 14px; align-items: center; margin: 2px 4px;
                    font: 12px sans-serif; color: #ccc; }
    .sfs-shelfrow label { display: flex; gap: 6px; align-items: center; }
    .sfs-shelfrow input { width: 70px; background: #111; color: #fff; border: 1px solid #666;
                          border-radius: 3px; padding: 1px 4px; font: 12px sans-serif; }`;
  document.head.appendChild(s);
}

function linkById(id) {
  return app.graph.links.get ? app.graph.links.get(id) : app.graph.links[id];
}

function upstream(node, inputName) {
  const inp = (node.inputs || []).find((i) => i.name === inputName);
  if (!inp || inp.link == null) return null;
  const link = linkById(inp.link);
  return link ? app.graph.getNodeById(link.origin_id) : null;
}

// From the shelf: the Selected Face LoRA Stack its lora_file output is wired to, if any.
function stackOf(shelf) {
  const out = (shelf.outputs || []).find((o) => o.name === "lora_file");
  for (const id of out?.links || []) {
    const link = linkById(id);
    const n = link && app.graph.getNodeById(link.target_id);
    if (n?.comfyClass === STACK) return n;
  }
  return null;
}

function wv(node, name) {
  return (node?.widgets || []).find((w) => w.name === name)?.value;
}

// shelf + every row strength, ON or OFF
function combined(shelf, stack) {
  let t = Number(wv(shelf, "strength") ?? 0);
  for (let i = 1; i <= ROWS; i++) t += Number(wv(stack, `strength_${i}`) ?? 0);
  return t;
}

function noteHtml(extra) {
  return `
    <div class="row"><span class="formula">Combined trained LoRA face strength (default)
      <b>${FORMULA}</b></span></div>
    <div class="row"><span class="lbl">Current:</span><span class="box score"></span>
      <span class="hint"></span>${extra || ""}</div>`;
}

function addTopNote(node, el, minHeight) {
  const w = node.addDOMWidget("freedom_sfs_top", "FREEDOM_SFS_TOP", el,
    { serialize: false, hideOnZoom: false, getMinHeight: () => minHeight });
  w.serialize = false;                            // what 1.53.6 actually checks
  node.widgets.splice(node.widgets.indexOf(w), 1);
  node.widgets.unshift(w);                        // at the top of the node
  for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"])
    el.addEventListener(ev, (e) => e.stopPropagation());
  return w;
}

function refreshBoth(node) {
  if (node?.comfyClass === STACK) { refreshStack(node); const sh = upstream(node, "face_lora"); if (sh) refreshShelf(sh); }
  else if (node?.comfyClass === SHELF) { refreshShelf(node); const st = stackOf(node); if (st) refreshStack(st); }
}

function refreshStack(node) {
  const el = node.__sfsTop;
  if (!el) return;
  const shelf = upstream(node, "face_lora");
  el.querySelector(".score").textContent = combined(shelf, node).toFixed(2);
  el.querySelector(".hint").textContent = shelf ? "" : "(no face shelf wired in)";
  for (let i = 1; i <= ROWS; i++) {
    const on = !!wv(node, `enabled_${i}`);
    const tog = el.querySelector(`.tog[data-i="${i}"]`);
    tog.textContent = on ? `row ${i} ON` : `row ${i} OFF`;
    tog.classList.toggle("on", on);
    const inp = el.querySelector(`input[data-i="${i}"]`);
    if (document.activeElement !== inp)            // never overwrite what is being typed
      inp.value = Number(wv(node, `strength_${i}`) ?? 0).toFixed(2);
  }
}

function refreshShelf(node) {
  const el = node.__sfsShelfTop;
  if (!el) return;
  const stack = stackOf(node);
  el.querySelector(".score").textContent = combined(node, stack).toFixed(2);
  el.querySelector(".hint").textContent = stack ? "" : "(no Selected Face LoRA Stack wired in - shelf only)";
  const row = node.__sfsShelfRow;
  if (row) {
    for (const inp of row.querySelectorAll("input")) {
      if (document.activeElement === inp) continue;       // never overwrite what is being typed
      inp.value = Number(wv(node, inp.dataset.w) ?? 0).toFixed(2);
    }
  }
}

function setWidget(node, name, value) {
  const w = (node.widgets || []).find((x) => x.name === name);
  if (!w) return;
  w.value = value;
  w.callback?.(value);                    // same path as a hand edit: marks the workflow changed
  node.setDirtyCanvas?.(true, true);
}

function everyHalfSecond(node, fn) {
  node.__sfsTimer = setInterval(fn, 500);
  const onRemoved = node.onRemoved;
  node.onRemoved = function () {
    clearInterval(this.__sfsTimer);
    return onRemoved ? onRemoved.apply(this, arguments) : undefined;
  };
}

function buildStack(node) {
  const el = document.createElement("div");
  el.className = "sfs-top";
  el.innerHTML = noteHtml(
    `<button class="reset" title="Put the three row strengths back to ${PASS_DEFAULTS.join(" / ")}">Reset to default</button>`)
    + `<div class="passes">${PASS_DEFAULTS.map((d, k) => `
        <div class="pass"><span class="name">Row ${k + 1}</span>
          <button class="tog" data-i="${k + 1}"></button>
          <span>strength</span><input type="number" step="0.05" min="-2" max="2" data-i="${k + 1}">
          <span class="dflt">default ${d.toFixed(1)}</span></div>`).join("")}
      </div>`;
  node.__sfsTop = el;
  el.querySelector(".reset").addEventListener("click", (e) => {
    e.stopPropagation();
    for (let i = 1; i <= ROWS; i++) setWidget(node, `strength_${i}`, PASS_DEFAULTS[i - 1]);
    refreshBoth(node);
  });
  for (const b of el.querySelectorAll(".tog"))
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      const i = b.dataset.i;
      setWidget(node, `enabled_${i}`, !wv(node, `enabled_${i}`));
      refreshBoth(node);
    });
  for (const inp of el.querySelectorAll(".pass input"))
    inp.addEventListener("change", () => {
      let v = parseFloat(inp.value);
      if (!Number.isFinite(v)) { refreshStack(node); return; }
      v = Math.min(2, Math.max(-2, Math.round(v * 100) / 100));
      setWidget(node, `strength_${inp.dataset.i}`, v);
      refreshBoth(node);
    });
  // The real settings stay on the node (saved, sent to the server) but are
  // drawn by the panel instead of as separate rows.
  for (const x of node.widgets) {
    if (!/^(enabled|strength)_\d$/.test(x.name)) continue;
    x.type = "hidden";
    x.options = x.options || {};
    x.options.hidden = true;
    x.computeSize = () => [0, -4];
  }
  addTopNote(node, el, 60 + 40 * ROWS);
  for (const x of node.widgets) {
    if (!/^strength_\d$/.test(x.name)) continue;
    const cb = x.callback;
    x.callback = function () {
      const r = cb ? cb.apply(this, arguments) : undefined;
      refreshBoth(node);
      return r;
    };
  }
  everyHalfSecond(node, () => refreshStack(node));   // the shelf lives on another node
  refreshStack(node);
  node.setSize([Math.max(node.size[0], 520), node.computeSize()[1]]);
}

function buildShelf(node) {
  const el = document.createElement("div");
  el.className = "sfs-top";
  el.innerHTML = noteHtml("");
  node.__sfsShelfTop = el;
  addTopNote(node, el, 56);
  // strength and trigger_weight side by side on one row, above "enabled"
  // (user, 2026-09-27). The real widgets stay on the node, hidden, and are what
  // get saved and sent to the server; this row reads and writes them.
  const row = document.createElement("div");
  row.className = "sfs-shelfrow";
  row.innerHTML = `
    <label>strength <input type="number" step="0.05" min="-2" max="2" data-w="strength"></label>
    <label>trigger_weight <input type="number" step="0.05" min="0.1" max="2" data-w="trigger_weight"></label>`;
  node.__sfsShelfRow = row;
  for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"])
    row.addEventListener(ev, (e) => e.stopPropagation());
  for (const inp of row.querySelectorAll("input")) {
    inp.addEventListener("change", () => {
      const name = inp.dataset.w;
      const lo = name === "trigger_weight" ? 0.1 : -2;
      let v = parseFloat(inp.value);
      if (!Number.isFinite(v)) { refreshShelf(node); return; }
      v = Math.min(2, Math.max(lo, Math.round(v * 100) / 100));
      setWidget(node, name, v);          // the widget's own callback repaints the shelf
      refreshBoth(node);
    });
  }
  const rw = node.addDOMWidget("freedom_sfs_shelf_row", "FREEDOM_SFS_ROW", row,
    { serialize: false, hideOnZoom: false, getMinHeight: () => 30 });
  rw.serialize = false;                            // what 1.53.6 actually checks
  node.widgets.splice(node.widgets.indexOf(rw), 1);
  node.widgets.splice(1, 0, rw);                   // right under the note, above "enabled"
  for (const name of ["strength", "trigger_weight"]) {
    const x = (node.widgets || []).find((w) => w.name === name);
    if (!x) continue;
    x.type = "hidden";
    x.options = x.options || {};
    x.options.hidden = true;
    x.computeSize = () => [0, -4];
  }
  const sw = (node.widgets || []).find((x) => x.name === "strength");
  if (sw) {
    const cb = sw.callback;
    sw.callback = function () {
      const r = cb ? cb.apply(this, arguments) : undefined;
      refreshBoth(node);          // the stack's counter changes at the same moment
      return r;
    };
  }
  everyHalfSecond(node, () => refreshShelf(node));   // the rows live on the Selected Face LoRA Stack
  refreshShelf(node);
}

app.registerExtension({
  name: "freedom.selected_face_stack",
  async nodeCreated(node) {
    if (node.comfyClass !== STACK && node.comfyClass !== SHELF) return;
    css();
    if (node.comfyClass === STACK) buildStack(node);
    else buildShelf(node);
  },
  async afterConfigureGraph() {
    for (const node of app.graph?.nodes || []) {
      if (node.comfyClass === STACK) refreshStack(node);
      if (node.comfyClass === SHELF) refreshShelf(node);
    }
  },
});
