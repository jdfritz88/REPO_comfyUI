// ==========================================================================
// FREEDOM SYSTEM - Face Shelf panel
// A grid of trained-face cards on the "Freedom Face Shelf" node: thumbnail,
// person name, and whether it's the face-only or face+body LoRA. Three to a
// row, rows grow as more faces are trained. Click a card to select it - this
// node then loads that LoRA onto the model + CLIP passing through it.
// The FACE ON / FACE OFF button in the bar mirrors the node's "enabled"
// widget: off greys the shelf out and the node becomes a plain pass-through,
// while the card you picked stays picked for when you switch it back on.
// ==========================================================================
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const CSS = `
.ffs-root{display:flex;flex-direction:column;gap:6px;height:100%;min-height:300px;
  font:11px/1.35 system-ui,Segoe UI,sans-serif;color:#ddd;background:#1c1c1c;
  border:1px solid #444;border-radius:6px;padding:8px;overflow:hidden}
.ffs-bar{display:flex;align-items:center;gap:8px}
.ffs-bar .t{font-weight:700;color:#cde3ff;font-size:11px;letter-spacing:.3px}
.ffs-btn{background:#2b2b2b;color:#ddd;border:1px solid #555;border-radius:4px;
  padding:3px 9px;cursor:pointer;font-size:10px}
.ffs-btn:hover{background:#3a3a3a}
.ffs-sel{color:#9cc4ff;font-size:10px;flex:1;text-align:right;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ffs-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;overflow:auto;
  padding-right:2px;align-content:start}
.ffs-card{background:#161616;border:1px solid #333;border-radius:6px;overflow:hidden;
  cursor:pointer;display:flex;flex-direction:column}
.ffs-card:hover{border-color:#5a7fb0}
.ffs-card.on{border-color:#2e7d3a;box-shadow:0 0 0 1px #2e7d3a inset}
.ffs-card .ph{width:100%;aspect-ratio:1/1;background:#0f0f0f center/cover no-repeat;
  display:flex;align-items:center;justify-content:center;color:#555;font-size:9px}
.ffs-card .cap{padding:4px 5px}
.ffs-card .nm{font-weight:600;color:#eee;font-size:10px;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.ffs-card .sub{color:#9a9a9a;font-size:9px}
.ffs-card.part .nm{color:#b5872b}
.ffs-empty{color:#888;padding:24px 8px;text-align:center}
.ffs-sw{border:1px solid #555;border-radius:4px;padding:3px 10px;cursor:pointer;
  font-size:10px;font-weight:700;letter-spacing:.3px}
.ffs-sw.on{background:#204d2a;border-color:#2e7d3a;color:#b9e6c2}
.ffs-trig{display:flex;align-items:center;gap:6px;background:#141414;border:1px solid #3a3a3a;
  border-radius:5px;padding:4px 6px}
.ffs-trig .lbl{color:#7f7f7f;font-size:9px;letter-spacing:.4px;white-space:nowrap}
.ffs-trig .txt{flex:1;color:#ffd479;font:11px/1.3 ui-monospace,Consolas,monospace;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ffs-trig .txt.none{color:#777;font-style:italic}
.ffs-root.is-off .ffs-trig .txt{color:#777;text-decoration:line-through}
.ffs-sw.off{background:#4a2020;border-color:#7d2e2e;color:#e6b9b9}
.ffs-root.is-off .ffs-grid{opacity:.32;filter:grayscale(1)}
.ffs-root.is-off .ffs-sel{color:#8a8a8a}
.ffs-compat{color:#7fa8d9;font-size:9.5px}
.ffs-compat.unknown{color:#a08040}
`;
function css(){ if(!document.getElementById("ffs-css")){ const s=document.createElement("style");
  s.id="ffs-css"; s.textContent=CSS; document.head.appendChild(s);} }

class Shelf {
  constructor(node){
    this.node = node;
    this.root = document.createElement("div");
    this.root.className = "ffs-root";
    this.root.innerHTML = `
      <div class="ffs-bar">
        <span class="t">FACE SHELF</span>
        <button class="ffs-sw on">FACE ON</button>
        <button class="ffs-btn refresh">Refresh</button>
        <button class="ffs-btn clear">None</button>
        <span class="ffs-sel"></span>
      </div>
      <div class="ffs-trig">
        <span class="lbl">PROMPT GETS</span>
        <span class="txt none">(no face selected)</span>
        <button class="ffs-btn copy">Copy</button>
      </div>
      <div class="ffs-compat"></div>
      <div class="ffs-grid"></div>`;
    this.grid  = this.root.querySelector(".ffs-grid");
    this.compatEl = this.root.querySelector(".ffs-compat");
    this.selEl = this.root.querySelector(".ffs-sel");
    this.swEl  = this.root.querySelector(".ffs-sw");
    this.trigEl = this.root.querySelector(".ffs-trig .txt");
    this.copyEl = this.root.querySelector(".ffs-trig .copy");
    this.cards = {};                       // name -> card, for person + trigger
    this.copyEl.onclick = () => {
      const t = this.trigEl.dataset.text || "";
      if (t) navigator.clipboard?.writeText(t);
      this.copyEl.textContent = t ? "Copied" : "Nothing";
      setTimeout(() => { this.copyEl.textContent = "Copy"; }, 1200);
    };
    this.root.querySelector(".refresh").onclick = () => this.load();
    this.root.querySelector(".clear").onclick   = () => this.pick("");
    this.swEl.onclick = () => this.setEnabled(!this.isEnabled());
    for (const ev of ["pointerdown","wheel","contextmenu"])
      this.root.addEventListener(ev, e => e.stopPropagation());
    this.load();
  }

  widget(){ return (this.node.widgets||[]).find(w => w.name === "selected"); }
  enWidget(){ return (this.node.widgets||[]).find(w => w.name === "enabled"); }

  // Is a Freedom Face Source wired into this node's "face_mode" input? If so
  // IT is the single source of truth (one shared switch, not two independent
  // ones), and this panel becomes a read-only mirror of its value rather than
  // its own clickable control.
  sourceModeWidget(){
    const input = (this.node.inputs || []).find(i => i.name === "face_mode");
    if (!input || !input.link) return null;
    const link = app.graph.links[input.link];
    if (!link) return null;
    const src = app.graph.getNodeById(link.origin_id);
    const w = (src?.widgets || []).find(w => w.name === "mode") || null;
    // The switch lives on a different node, so nothing repaints this panel when
    // its value changes except its own callback - hook it once, here, the first
    // time we actually find it (creation order between the two nodes isn't
    // guaranteed, so this can't be done up front in onNodeCreated).
    if (w && !w.__ffsHooked){
      w.__ffsHooked = true;
      const prev = w.callback;
      const self = this;
      w.callback = function(){
        const r = prev ? prev.apply(this, arguments) : undefined;
        self.syncEnabled();
        return r;
      };
    }
    return w;
  }

  isEnabled(){
    const sw = this.sourceModeWidget();
    if (sw) return sw.value === "trained_face";
    const w = this.enWidget();
    return w ? w.value !== false : true;
  }

  setEnabled(on){
    if (this.sourceModeWidget()) return;   // the shared switch decides, not a click here
    const w = this.enWidget();
    if (w){
      w.value = !!on;
      // Fire the widget's own callback so the node reacts exactly as it would
      // to a click on the native toggle - this button is a second face on the
      // same switch, not a parallel one that can drift out of step.
      if (typeof w.callback === "function") w.callback(w.value);
    }
    this.syncEnabled();
    this.node.setDirtyCanvas(true, true);
  }

  wWidget(){ return (this.node.widgets||[]).find(w => w.name === "trigger_weight"); }

  // Walk upstream from this node's own MODEL input, through any number of
  // pass-through nodes, until a node with a ckpt_name widget is found.
  // Depth-limited so a cycle or an unusual graph can never hang the browser.
  // Same technique as freedom_lora_stack's findCheckpointWidget().
  findCheckpointWidget(){
    let node = this.node;
    for (let hop = 0; hop < 12 && node; hop++){
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

  findCheckpointName(){ return this.findCheckpointWidget()?.value || ""; }

  // Re-filter the moment the actual checkpoint changes, not only on a manual
  // Refresh click. Re-attempted on every load in case the wiring changed -
  // guarded so the same widget is never wrapped twice.
  hookCheckpointWidget(){
    const w = this.findCheckpointWidget();
    if (!w || w.__ffsCkptHooked) return;
    w.__ffsCkptHooked = true;
    const prev = w.callback;
    const self = this;
    w.callback = function(){
      const r = prev ? prev.apply(this, arguments) : undefined;
      self.load();
      return r;
    };
  }

  renderCompatBar(ckpt, family, hiddenCount){
    if (!ckpt){
      this.compatEl.textContent = "No checkpoint found upstream - showing every trained face, unfiltered.";
      this.compatEl.className = "ffs-compat unknown";
      return;
    }
    this.compatEl.textContent = `Showing faces trained for ${family} - from ${ckpt}`
      + (hiddenCount ? ` (${hiddenCount} hidden - wrong checkpoint family)` : "");
    this.compatEl.className = "ffs-compat";
  }

  async syncTrigger(){
    const name = this.widget()?.value || "";
    if (!name){
      this.trigEl.dataset.text = "";
      this.trigEl.textContent = "(no face selected)";
      this.trigEl.classList.add("none");
      return;
    }
    const w = this.wWidget()?.value ?? 1;
    let text = "";
    try {
      // The node formats this string; asking it here means the shelf cannot
      // drift from what actually reaches the prompt.
      const r = await api.fetchApi("/freedom/faceshelf/trigger?name="
        + encodeURIComponent(name) + "&weight=" + encodeURIComponent(w));
      text = (await r.json()).text || "";
    } catch (e) {
      const t = this.cards[name]?.trigger || "";
      text = t ? (Math.abs(w - 1) < 0.001 ? t : `(${t}:${w})`) : "";
    }
    this.trigEl.dataset.text = text;
    this.trigEl.textContent = text || "(this face has no trigger word)";
    this.trigEl.classList.toggle("none", !text);
  }

  syncEnabled(){
    // Older workflows were saved before this switch existed, so they carry no
    // value for it. Anything that is not an explicit false counts as on, which
    // is how those workflows behaved when they were saved.
    const w = this.enWidget();
    if (w && typeof w.value !== "boolean") w.value = true;
    const sourceMode = this.sourceModeWidget();
    const on = this.isEnabled();
    this.copyEl.title = on ? "Copy this text"
      : "The face is switched off - this text is not being added to the prompt";
    this.swEl.className = "ffs-sw " + (on ? "on" : "off");
    if (sourceMode){
      // Mirrors the shared switch - not clickable, so it can never disagree
      // with the thing actually deciding.
      this.swEl.textContent = on ? "TRAINED FACE (via switch)" : "OFF (via switch)";
      this.swEl.style.cursor = "default";
      this.swEl.title = on
        ? "The shared Face Source switch is set to Trained Face"
        : `The shared Face Source switch is set to "${sourceMode.value}" - click that node to change it`;
    } else {
      this.swEl.textContent = on ? "FACE ON" : "FACE OFF";
      this.swEl.style.cursor = "pointer";
      this.swEl.title = on
        ? "Click to switch this face OFF - the picture passes through untouched"
        : "Click to switch this face back ON - your pick below is remembered";
    }
    this.root.classList.toggle("is-off", !on);
  }

  pick(name){
    const w = this.widget();
    if (w){ w.value = name; }
    const c = this.cards[name];
    // Show WHO, not the file name. The file name used to be the only string in
    // this panel, so it was the thing people copied into prompts - where it
    // means nothing. The trigger line below is the text that actually works.
    this.selEl.textContent = c ? `${c.person} - ${c.crop_label}` : (name || "(no face)");
    this.selEl.title = name || "";
    this.syncTrigger();
    for (const el of this.grid.querySelectorAll(".ffs-card"))
      el.classList.toggle("on", el.dataset.name === name);
    this.node.setDirtyCanvas(true, true);
  }

  // Graph configure restores links one at a time, so several things can ask
  // for a re-filter in the same tick - collapse them into a single request.
  reload(){
    clearTimeout(this.__reloadT);
    this.__reloadT = setTimeout(() => this.load(), 50);
  }

  async load(){
    this.hookCheckpointWidget();
    const ckpt = this.findCheckpointName();
    let cards = [], allCount = 0, family = "";
    try {
      const q = ckpt ? ("?checkpoint=" + encodeURIComponent(ckpt)) : "";
      const r = await api.fetchApi("/freedom/faceshelf/list" + q);
      const info = await r.json();
      cards = info.cards || [];
      allCount = (info.all_cards || cards).length;
      family = info.family || "";
    } catch (e) { /* server not ready */ }
    this.renderCompatBar(ckpt, family, Math.max(0, allCount - cards.length));

    this.grid.innerHTML = "";
    if (!cards.length){
      const d = document.createElement("div");
      d.className = "ffs-empty";
      d.textContent = allCount
        ? `No trained faces match ${family} yet - only faces trained for a different `
          + "checkpoint family exist. Train one for this checkpoint, or switch STEP 1's model."
        : "No trained faces yet. Use the Face Tool (launcher option 4) "
          + "to train some, then press Refresh.";
      this.grid.appendChild(d);
      this.pick(this.widget()?.value || "");
      return;
    }
    this.cards = {};
    for (const c of cards) this.cards[c.name] = c;
    for (const c of cards){
      const card = document.createElement("div");
      card.className = "ffs-card" + (c.partial ? " part" : "");
      card.dataset.name = c.name;
      const ph = document.createElement("div");
      ph.className = "ph";
      if (c.has_thumb){
        ph.style.backgroundImage =
          `url(${api.apiURL("/freedom/faceshelf/thumb?name=" + encodeURIComponent(c.name))})`;
      } else {
        ph.textContent = c.partial ? "unfinished" : "no preview";
      }
      const cap = document.createElement("div");
      cap.className = "cap";
      cap.innerHTML = `<div class="nm">${c.person}</div>`
        + `<div class="sub">${c.crop_label} - ${c.family_label}`
        + `${c.partial ? " (paused)" : ""}</div>`;
      card.appendChild(ph); card.appendChild(cap);
      card.title = c.trigger ? `trigger: ${c.trigger}` : "no trigger word recorded";
      card.onclick = () => this.pick(c.name);
      this.grid.appendChild(card);
    }
    this.pick(this.widget()?.value || "");
  }
}

app.registerExtension({
  name: "freedom.face_shelf",

  // A workflow load builds every node BEFORE it restores the links between
  // them, so a shelf's constructor runs while its MODEL input still leads
  // nowhere - no checkpoint can be found and the grid comes back unfiltered.
  // Re-filter once the graph is fully wired.
  afterConfigureGraph(){
    for (const n of (app.graph?._nodes || []))
      if (n.__ffs) n.__ffs.reload();
  },

  async beforeRegisterNodeDef(nodeType, nodeData){
    if (nodeData.name !== "FreedomFaceShelf") return;
    css();
    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function(){
      if (onCreated) onCreated.apply(this, arguments);
      const s = new Shelf(this);
      this.__ffs = s;
      this.addDOMWidget("face_shelf", "FREEDOM_FACE_SHELF", s.root,
        { serialize: false, hideOnZoom: false });
      const sw = (this.widgets||[]).find(w => w.name === "selected");
      if (sw){ sw.type = "hidden"; sw.computeSize = () => [0,0]; }
      // The native BOOLEAN widget stays visible and is the value that gets
      // saved; the bar button just mirrors it. Wrap its callback so flipping
      // either one repaints the panel.
      const en = (this.widgets||[]).find(w => w.name === "enabled");
      if (en){
        const prev = en.callback;
        en.callback = function(){
          const r = prev ? prev.apply(this, arguments) : undefined;
          s.syncEnabled();
          return r;
        };
      }
      const tw = (this.widgets||[]).find(w => w.name === "trigger_weight");
      if (tw){
        const prevW = tw.callback;
        tw.callback = function(){
          const r = prevW ? prevW.apply(this, arguments) : undefined;
          s.syncTrigger();
          return r;
        };
      }
      s.syncEnabled();
      s.syncTrigger();
      this.setSize([360, 450]);
    };

    // A workflow load writes widget values straight in, without callbacks -
    // so repaint from the restored value once configure has finished.
    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function(){
      if (onConfigure) onConfigure.apply(this, arguments);
      if (this.__ffs){ this.__ffs.syncEnabled(); this.__ffs.syncTrigger(); }
    };

    // Wiring the MODEL input - on a node just dragged in, or when it is moved
    // to a different checkpoint loader - changes which faces are compatible.
    const onConn = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function(){
      const r = onConn ? onConn.apply(this, arguments) : undefined;
      if (this.__ffs) this.__ffs.reload();
      return r;
    };
  },
});
