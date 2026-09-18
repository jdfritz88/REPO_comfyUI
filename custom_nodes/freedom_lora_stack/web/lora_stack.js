// ==========================================================================
// FREEDOM SYSTEM - LoRA Stack panel
// A growing list of LoRA rows (on/off, file, strength) on the node. Starts
// with 3 rows; "+ Add LoRA" appends another (up to MAX_ROWS); each row has
// its own X to delete it. Never lists or applies a face LoRA - those are
// picked from the Face Shelf node instead.
//
// The real per-row values live in hidden native widgets (enabled_i / lora_i /
// strength_i) so they serialize with the workflow and reach the Python node
// at run time - this panel is just the visible front end for them, same
// technique as face_shelf.js's "selected" widget.
// ==========================================================================
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const CSS = `
.fls-root{display:flex;flex-direction:column;gap:6px;font:11px/1.35 system-ui,Segoe UI,sans-serif;
  color:#ddd;background:#1c1c1c;border:1px solid #444;border-radius:6px;padding:8px;overflow:auto}
.fls-bar{display:flex;align-items:center;gap:6px}
.fls-bar .t{font-weight:700;color:#cde3ff;font-size:11px;letter-spacing:.3px;flex:1}
.fls-btn{background:#2b2b2b;color:#ddd;border:1px solid #555;border-radius:4px;padding:3px 9px;cursor:pointer;font-size:10px}
.fls-btn:hover{background:#3a3a3a}
.fls-row{background:#161616;border:1px solid #333;border-radius:5px;padding:5px 6px;
  display:flex;gap:6px;align-items:center}
.fls-row select{flex:1;min-width:0;background:#111;color:#ddd;border:1px solid #444;border-radius:4px;font-size:10.5px;padding:2px}
.fls-row .strength{width:52px;background:#111;color:#ddd;border:1px solid #444;border-radius:4px;font-size:10.5px;padding:2px 4px}
.fls-row .x{color:#a66;cursor:pointer;font-size:12px;padding:0 3px;flex-shrink:0}
.fls-row .x:hover{color:#e88}
.fls-add{align-self:flex-start}
.fls-empty{color:#888;padding:6px 2px}
.fls-compat{color:#7fa8d9;font-size:9.5px}
.fls-compat.unknown{color:#a08040}
.fls-warn{color:#c98a4a;font-size:9.5px;padding:2px 2px 0}
`;
function css() {
  if (!document.getElementById("fls-css")) {
    const s = document.createElement("style");
    s.id = "fls-css";
    s.textContent = CSS;
    document.head.appendChild(s);
  }
}

const MAX_ROWS = 12;
const STARTER_ROWS = 3;

class Stack {
  constructor(node) {
    this.node = node;
    this.loraChoices = [];
    this.root = document.createElement("div");
    this.root.className = "fls-root";
    this.root.innerHTML = `
      <div class="fls-bar">
        <span class="t">LORA STACK - everything except her face</span>
        <button class="fls-btn refresh">Refresh list</button>
      </div>
      <div class="fls-compat"></div>
      <div class="fls-warn" hidden></div>
      <div class="fls-rows"></div>
      <button class="fls-btn fls-add">+ Add LoRA</button>`;
    this.rowsEl = this.root.querySelector(".fls-rows");
    this.addBtn = this.root.querySelector(".fls-add");
    this.compatEl = this.root.querySelector(".fls-compat");
    this.warnEl = this.root.querySelector(".fls-warn");
    this.root.querySelector(".refresh").onclick = () => this.loadChoices(true);
    this.addBtn.onclick = () => this.addRow();
    for (const ev of ["pointerdown", "wheel", "contextmenu"])
      this.root.addEventListener(ev, e => e.stopPropagation());

    // hide the real per-row widgets - they carry the data, they're just not drawn.
    // computeSize returns -4 (not 0): the layout still adds a fixed per-widget
    // margin regardless of reported height, so 0 alone leaves a hairline gap -
    // negligible for one widget (see face_shelf.js's single "selected" widget)
    // but visible as many thin rows once you stack 36 of them. options.hidden
    // is what the current frontend actually gates drawing on, not widget.type.
    for (let i = 1; i <= MAX_ROWS; i++) {
      for (const suf of ["enabled_", "lora_", "strength_"]) {
        const w = this.widget(suf + i);
        if (w) {
          w.type = "hidden";
          w.options = w.options || {};
          w.options.hidden = true;
          w.computeSize = () => [0, -4];
        }
      }
    }

    this.rows = this.readRowsFromWidgets();
    this.loadChoices(false);
  }

  widget(name) { return (this.node.widgets || []).find(w => w.name === name); }

  // Walk upstream from this node's own MODEL input, through any number of
  // pass-through nodes (the Face Shelf included - it also takes and returns
  // MODEL), until a node with a ckpt_name widget is found. Depth-limited so a
  // cycle or an unusual graph can never hang the browser.
  findCheckpointName() {
    return this.findCheckpointWidget()?.value || "";
  }

  findCheckpointWidget() {
    let node = this.node;
    for (let hop = 0; hop < 12 && node; hop++) {
      const ckw = (node.widgets || []).find(w => w.name === "ckpt_name");
      if (ckw) return ckw;
      const idx = (node.inputs || []).findIndex(i => i.type === "MODEL");
      if (idx < 0) return null;
      const input = node.inputs[idx];
      if (!input.link) return null;
      const link = app.graph.links[input.link];
      if (!link) return null;
      node = app.graph.getNodeById(link.origin_id);
    }
    return null;
  }

  // Re-filter the moment the actual checkpoint changes, not only on a manual
  // Refresh click. Re-attempted on every load in case the wiring changed (a
  // different Load Checkpoint node now feeds this stack) - guarded so the same
  // widget is never wrapped twice.
  hookCheckpointWidget() {
    const w = this.findCheckpointWidget();
    if (!w || w.__flsHooked) return;
    w.__flsHooked = true;
    const prev = w.callback;
    const self = this;
    w.callback = function () {
      const r = prev ? prev.apply(this, arguments) : undefined;
      self.loadChoices(true);
      return r;
    };
  }

  // rebuild the visible row list from whatever the hidden widgets already
  // hold (a workflow just loaded from disk) - at least STARTER_ROWS shown.
  readRowsFromWidgets() {
    let lastUsed = 0;
    for (let i = 1; i <= MAX_ROWS; i++) {
      const en = this.widget("enabled_" + i)?.value;
      const lo = this.widget("lora_" + i)?.value;
      if (en || (lo && lo.length)) lastUsed = i;
    }
    const count = Math.max(STARTER_ROWS, lastUsed);
    const rows = [];
    for (let i = 1; i <= count; i++) {
      rows.push({
        enabled: !!this.widget("enabled_" + i)?.value,
        lora: this.widget("lora_" + i)?.value || "",
        strength: this.widget("strength_" + i)?.value ?? 0.8,
      });
    }
    return rows;
  }

  async loadChoices(forceRedraw) {
    this.hookCheckpointWidget();
    const ckpt = this.findCheckpointName();
    let info = null;
    try {
      const q = ckpt ? ("?checkpoint=" + encodeURIComponent(ckpt)) : "";
      const r = await api.fetchApi("/freedom/lorastack/list" + q);
      info = await r.json();
      this.loraChoices = info.loras || [];
    } catch (e) {
      this.loraChoices = [];
      info = null;
    }
    this.renderCompatBar(ckpt, info);
    this.render();
  }

  renderCompatBar(ckpt, info) {
    if (!ckpt) {
      this.compatEl.textContent = "No checkpoint found upstream - showing every LoRA, unfiltered.";
      this.compatEl.className = "fls-compat unknown";
      this.warnEl.hidden = true;
      return;
    }
    if (!info || info.checkpoint_base === "unknown") {
      this.compatEl.textContent = `Could not identify "${ckpt}"'s architecture - showing every LoRA, unfiltered.`;
      this.compatEl.className = "fls-compat unknown";
      this.warnEl.hidden = true;
      return;
    }
    const nUnver = (info.unverified || []).length;
    this.compatEl.textContent = `Showing LoRAs compatible with ${info.checkpoint_base}`
      + (nUnver ? ` (+ ${nUnver} unverified)` : "")
      + ` - from ${ckpt}`;
    this.compatEl.className = "fls-compat";
    const inc = info.incompatible || [];
    if (inc.length) {
      const names = inc.slice(0, 4).map(x => `${x.name} (${x.base})`).join(", ");
      this.warnEl.textContent = `Hidden as wrong architecture: ${names}`
        + (inc.length > 4 ? ` + ${inc.length - 4} more` : "");
      this.warnEl.hidden = false;
    } else {
      this.warnEl.hidden = true;
    }
  }

  addRow() {
    if (this.rows.length >= MAX_ROWS) return;
    this.rows.push({ enabled: true, lora: "", strength: 0.8 });
    this.sync();
    this.render();
  }

  deleteRow(idx) {
    this.rows.splice(idx, 1);
    this.sync();
    this.render();
  }

  // push this.rows into the hidden widgets 1..MAX_ROWS (extra slots cleared)
  sync() {
    for (let i = 1; i <= MAX_ROWS; i++) {
      const row = this.rows[i - 1];
      const wEn = this.widget("enabled_" + i);
      const wLo = this.widget("lora_" + i);
      const wSt = this.widget("strength_" + i);
      if (wEn) wEn.value = row ? row.enabled : false;
      if (wLo) wLo.value = row ? row.lora : "";
      if (wSt) wSt.value = row ? row.strength : 0.8;
    }
    this.node.setDirtyCanvas(true, true);
  }

  render() {
    this.rowsEl.innerHTML = "";
    if (!this.loraChoices.length) {
      const d = document.createElement("div");
      d.className = "fls-empty";
      d.textContent = "No LoRAs outside the faces/ folder match this checkpoint's "
        + "architecture yet. Click Refresh list after adding one, or after "
        + "changing STEP 1's model.";
      this.rowsEl.appendChild(d);
    }
    this.rows.forEach((row, idx) => {
      const el = document.createElement("div");
      el.className = "fls-row";

      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = row.enabled;
      cb.onchange = () => { row.enabled = cb.checked; this.sync(); };

      const sel = document.createElement("select");
      const noneOpt = document.createElement("option");
      noneOpt.value = ""; noneOpt.textContent = "(pick a LoRA)";
      sel.appendChild(noneOpt);
      for (const name of this.loraChoices) {
        const opt = document.createElement("option");
        opt.value = name; opt.textContent = name;
        if (name === row.lora) opt.selected = true;
        sel.appendChild(opt);
      }
      // A row already pointing at a LoRA the current checkpoint doesn't match
      // (switched checkpoints since this was picked, most likely) still needs
      // to show its real value - silently falling back to blank in the <select>
      // would look like the pick was lost, when the saved value is untouched.
      if (row.lora && !this.loraChoices.includes(row.lora)) {
        const opt = document.createElement("option");
        opt.value = row.lora;
        opt.textContent = `${row.lora}  (wrong architecture for this checkpoint)`;
        opt.selected = true;
        sel.appendChild(opt);
      }
      sel.onchange = () => { row.lora = sel.value; this.sync(); };

      const st = document.createElement("input");
      st.className = "strength";
      st.type = "number";
      st.step = "0.05"; st.min = "-2"; st.max = "2";
      st.value = row.strength;
      st.onchange = () => { row.strength = parseFloat(st.value) || 0; this.sync(); };

      const x = document.createElement("span");
      x.className = "x";
      x.title = "remove this row";
      x.textContent = "✕";
      x.onclick = () => this.deleteRow(idx);

      el.appendChild(cb); el.appendChild(sel); el.appendChild(st); el.appendChild(x);
      this.rowsEl.appendChild(el);
    });
    this.addBtn.style.display = this.rows.length >= MAX_ROWS ? "none" : "";
    this.sync();
  }
}

app.registerExtension({
  name: "freedom.lora_stack",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "FreedomLoraStack") return;
    css();
    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      if (onCreated) onCreated.apply(this, arguments);
      const s = new Stack(this);
      this.__fls = s;
      this.addDOMWidget("lora_stack", "FREEDOM_LORA_STACK", s.root,
        { serialize: false, hideOnZoom: false });
      this.setSize([420, 260]);
    };
    // a workflow just loaded from disk - widget values are restored by now,
    // rebuild the visible rows from them instead of the 3-row default
    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      if (onConfigure) onConfigure.apply(this, arguments);
      if (this.__fls) {
        this.__fls.rows = this.__fls.readRowsFromWidgets();
        this.__fls.render();
      }
    };
  },
});
