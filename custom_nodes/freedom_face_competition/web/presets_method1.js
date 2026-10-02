// ==========================================================================
// FREEDOM SYSTEM - Method 1 Presets
// Saves/loads a named snapshot of every widget value across every node
// tagged properties.freedom_method === "1" (the whole Method 1 pipeline -
// the face swap, and both hair fixes). Purely a panel: it reads and writes
// other nodes' live widgets directly and has nothing to do with the graph
// at execution time.
// ==========================================================================
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const CSS = `
.fp1-root{display:flex;flex-direction:column;gap:7px;font:13px/1.4 system-ui,Segoe UI,sans-serif;
  color:#ddd;background:#1c1c1c;border:1px solid #444;border-radius:6px;padding:9px}
.fp1-h{font-weight:700;color:#cde3ff;font-size:12px;letter-spacing:.4px}
.fp1-row{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.fp1-sel{flex:1;min-width:140px;background:#141414;color:#eee;border:1px solid #444;border-radius:4px;padding:5px}
.fp1-name{flex:1;min-width:140px;background:#141414;color:#eee;border:1px solid #444;border-radius:4px;padding:5px}
.fp1-btn{background:#2b2b2b;color:#ddd;border:1px solid #555;border-radius:4px;padding:5px 9px;cursor:pointer;font-size:12px}
.fp1-btn:hover{background:#3a3a3a}
.fp1-btn.primary{background:#1f5a2a;border-color:#2e7d3a;color:#e8ffe8}
.fp1-loaded{font-size:12px;color:#9cc4ff}
.fp1-dot{color:#2ecc40;font-size:14px}
.fp1-status{color:#9cc4ff;font-size:12px;min-height:14px}
`;
function css(){ if(!document.getElementById("fp1-css")){ const s=document.createElement("style"); s.id="fp1-css"; s.textContent=CSS; document.head.appendChild(s);} }
async function get(r){ return (await api.fetchApi(r)).json(); }
async function post(r,b){ return (await api.fetchApi(r,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b||{})})).json(); }

const GREEN_DOT = "\u{1F7E2}"; // 🟢

// --------------------------------------------------------------------------- //
// Rename in two steps (user, 2026-09-30) - every Rename button:
//   1st click: the name box gets the current name, selected, and blinks 3 times.
//   Then type the new name; Enter or a 2nd click ("Save new name") renames.
//   Esc puts the box back and renames nothing. (Same as prompt_slots.js.)
// --------------------------------------------------------------------------- //
function blinkThree(field) {
  try {
    field.animate([{ boxShadow: "0 0 0 3px #ffd479", backgroundColor: "#3a3215" },
                   { boxShadow: "0 0 0 3px transparent" }], { duration: 330, iterations: 3 });
  } catch (e) { /* an old browser simply skips the blink */ }
}

// The confirm/cancel box (user, 2026-10-01). A button that used to want a second
// press (Rename, Save as, Delete) opens this box under its row instead, and
// nothing happens until Confirm. Pressing the button again does nothing. Confirm
// ignores clicks for half a second, so a double-click can never reach it, and
// pressing Confirm or Cancel leaves the keyboard where it was (in the name box).
function askBox(button) {
  const box = document.createElement("div");
  box.style.cssText = "display:none;flex-direction:column;gap:5px;margin-top:5px;padding:6px;" +
    "border:1px solid #c66;border-radius:5px;background:#2a1c1c";
  const text = document.createElement("div");
  text.style.cssText = "color:#fbb;font-size:12px;font-weight:600;white-space:normal";
  const row = document.createElement("div");
  row.style.cssText = "display:flex;gap:5px;flex-wrap:wrap";
  const yes = document.createElement("button"), no = document.createElement("button");
  yes.textContent = "Confirm"; no.textContent = "Cancel";
  for (const b of [yes, no]) {
    b.className = button.className.replace(/\b(danger|warn)\b/g, "").trim();
    b.style.cssText = button.style.cssText;
    b.addEventListener("mousedown", (e) => e.preventDefault());
  }
  row.append(yes, no); box.append(text, row);
  let job = null;
  const close = () => { job = null; box.style.display = "none"; };
  yes.onclick = async () => {
    if (!job || performance.now() - job.at < 500) return;   // the 2nd half of a double-click
    const { onYes } = job; close(); await onYes();
  };
  no.onclick = () => { const j = job; close(); j?.onNo?.(); };
  const open = (message, onYes, onNo) => {
    const spot = button.parentElement || button;
    if (box.previousElementSibling !== spot) spot.after(box);
    text.textContent = message;
    box.style.display = "flex";
    job = { onYes, onNo, at: performance.now() };
  };
  return { open, close, isOpen: () => !!job };
}
function makeRenamer({ button, field, current, apply, say, blocked }) {
  let armed = null;
  const label = button.textContent;
  const ask = askBox(button);
  const end = (restore) => {
    if (!armed) return;
    const { el: f, before, onKey } = armed;
    f.removeEventListener("keydown", onKey, true);
    if (restore) f.value = before;
    armed = null;
    ask.close();
    button.textContent = label;
  };
  const confirm = async () => {
    if (!armed) return;
    const v = String(armed.el.value || "").trim();
    const cur = String(current() || "").trim();
    end(false);
    if (!v || v === cur) { say("The name was not changed."); return; }
    await apply(v);
  };
  const click = async () => {
    if (armed) { armed.el.focus(); return; }   // a 2nd press does nothing - the box's Confirm does it
    const stop = blocked?.();
    if (stop) { say(stop); return; }
    const f = field(); const cur = current();
    if (!f || !cur) { say("There is nothing here to rename."); return; }
    const before = f.value;
    f.value = cur; f.focus(); f.select(); blinkThree(f);
    const onKey = (e) => {
      if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); confirm(); }
      else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); end(true); say("Rename cancelled - the name is unchanged."); }
    };
    f.addEventListener("keydown", onKey, true);
    armed = { el: f, before, onKey };
    ask.open(`${label}: type the new name in the name box, then press Confirm.`, confirm,
      () => { end(true); say("Rename cancelled - the name is unchanged."); });
    say("Type the new name, then press Confirm (or Enter). Cancel or Esc stops.");
  };
  return { click };
}

class Presets1Panel {
  constructor(node){
    this.node = node;
    this.data = { loaded: null, presets: [] };
    this.root = document.createElement("div");
    this.root.className = "fp1-root";
    this.root.innerHTML = `
      <div class="fp1-h">METHOD 1 PRESETS - every dial, slider and setting in the whole Method 1 pipeline</div>
      <div class="fp1-row"><span class="fp1-loaded">Loaded: <b class="loadedname">(none)</b></span></div>
      <div class="fp1-row">
        <select class="fp1-sel picker"></select>
      </div>
      <div class="fp1-row">
        <input class="fp1-name namebox" placeholder="preset name">
      </div>
      <div class="fp1-row">
        <button class="fp1-btn primary load">Load Selected Preset</button>
        <button class="fp1-btn save">Save Loaded Preset</button>
      </div>
      <div class="fp1-row">
        <button class="fp1-btn dup">Duplicate Loaded Preset</button>
        <button class="fp1-btn new">New Preset</button>
        <button class="fp1-btn rename">Rename</button>
      </div>
      <div class="fp1-status"></div>
    `;
    this.pickerEl = this.root.querySelector(".picker");
    this.nameEl = this.root.querySelector(".namebox");
    this.loadedNameEl = this.root.querySelector(".loadedname");
    this.statusEl = this.root.querySelector(".status") || this.root.querySelector(".fp1-status");

    this.root.querySelector(".load").onclick = () => this.loadSelected();
    this.root.querySelector(".save").onclick = () => this.saveLoaded();
    this.root.querySelector(".dup").onclick = () => this.duplicateLoaded();
    this.root.querySelector(".new").onclick = () => this.newPreset();
    // Renaming already happened on Enter in the name box; this is the same
    // thing as a button you can see.
    const renamer = makeRenamer({
      button: this.root.querySelector(".rename"), field: () => this.nameEl,
      current: () => this.pickerEl.value || "",
      say: (t) => this.say(t),
      apply: async (newText) => { this.nameEl.value = newText; await this.renameIfChanged(); },
    });
    this.root.querySelector(".rename").onclick = () => renamer.click();
    this.pickerEl.onchange = () => { this.nameEl.value = this.pickerEl.value; };
    this.nameEl.onchange = () => this.renameIfChanged();
    for (const ev of ["pointerdown","mousedown","wheel","contextmenu"]) this.root.addEventListener(ev, e=>e.stopPropagation());

    this.init();
  }

  say(m, err){ this.statusEl.textContent = m || ""; this.statusEl.style.color = err ? "#ff9c9c" : "#9cc4ff"; }

  // -- read/write OTHER nodes' live widgets --------------------------------
  method1Nodes(){
    return (app.graph._nodes || []).filter(n => n.properties && String(n.properties.freedom_method) === "1"
      && n.type !== "FreedomPresetsMethod1" && n.type !== "MarkdownNote");
  }

  collectCurrentValues(){
    const out = {};
    for (const n of this.method1Nodes()){
      const widgets = n.widgets || [];
      if (!widgets.length) continue;
      const nv = {};
      for (const w of widgets) nv[w.name] = w.value;
      out[String(n.id)] = nv;
    }
    return out;
  }

  applyValues(values){
    let applied = 0, missingNodes = 0;
    const byId = {};
    for (const n of this.method1Nodes()) byId[String(n.id)] = n;
    for (const [nodeId, nv] of Object.entries(values || {})){
      const n = byId[nodeId];
      if (!n){ missingNodes++; continue; }
      for (const w of (n.widgets || [])){
        if (Object.prototype.hasOwnProperty.call(nv, w.name)){
          w.value = nv[w.name];
          if (w.callback) { try { w.callback(w.value); } catch(e){} }
          applied++;
        }
      }
    }
    app.graph.setDirtyCanvas(true, true);
    return { applied, missingNodes };
  }

  // -- panel state ----------------------------------------------------------
  render(){
    this.pickerEl.innerHTML = "";
    for (const p of this.data.presets){
      const opt = document.createElement("option");
      opt.value = p.name;
      opt.textContent = (p.name === this.data.loaded) ? `${p.name}  ${GREEN_DOT}` : p.name;
      this.pickerEl.appendChild(opt);
    }
    const sel = this.data.loaded && this.data.presets.some(p => p.name === this.data.loaded)
      ? this.data.loaded : (this.data.presets[0] && this.data.presets[0].name) || "";
    this.pickerEl.value = sel;
    this.nameEl.value = sel;
    this.loadedNameEl.textContent = this.data.loaded ? `${this.data.loaded} ${GREEN_DOT}` : "(none)";
  }

  focusNameForRename(){
    this.nameEl.focus();
    this.nameEl.select();
  }

  async init(){
    try { this.data = await get("/freedom/presets1/list"); }
    catch(e){ this.say("could not reach the server", true); return; }
    if (!this.data.presets || this.data.presets.length === 0){
      // First time this panel has ever run - seed "Susana" from whatever
      // Method 1's nodes are set to right now.
      const values = this.collectCurrentValues();
      if (Object.keys(values).length){
        const r = await post("/freedom/presets1/save", { name: "Susana", values });
        this.data = r;
        this.say('Seeded the "Susana" preset from the current settings.');
      }
    }
    this.render();
  }

  async loadSelected(){
    const name = this.pickerEl.value;
    if (!name){ this.say("no preset selected", true); return; }
    const p = this.data.presets.find(x => x.name === name);
    if (!p){ this.say("preset not found", true); return; }
    const { applied, missingNodes } = this.applyValues(p.values);
    const r = await post("/freedom/presets1/load", { name });
    if (r.ok) this.data = r;
    this.render();
    this.say(`Loaded "${name}" - ${applied} settings applied` + (missingNodes ? `, ${missingNodes} nodes not found (graph changed since this preset was saved)` : "."));
  }

  async saveLoaded(){
    const name = this.data.loaded;
    if (!name){ this.say("nothing is loaded - use New Preset instead", true); return; }
    const values = this.collectCurrentValues();
    const r = await post("/freedom/presets1/save", { name, values });
    if (r.ok){ this.data = r; this.render(); this.say(`Saved "${name}".`); }
    else this.say("save failed: " + (r.error || ""), true);
  }

  async duplicateLoaded(){
    const name = this.data.loaded;
    if (!name){ this.say("nothing is loaded to duplicate", true); return; }
    const r = await post("/freedom/presets1/duplicate", { name });
    if (r.ok){
      this.data = r;
      this.render();
      this.pickerEl.value = r.new_name;
      this.nameEl.value = r.new_name;
      this.focusNameForRename();
      this.say(`Duplicated "${name}" as "${r.new_name}" - type a new name and press Enter.`);
    } else this.say("duplicate failed: " + (r.error || ""), true);
  }

  async newPreset(){
    const values = this.collectCurrentValues();
    if (!Object.keys(values).length){ this.say("no Method 1 nodes found on the canvas", true); return; }
    const r = await post("/freedom/presets1/new", { values, base_name: "New Preset" });
    if (r.ok){
      this.data = r;
      this.render();
      this.pickerEl.value = r.new_name;
      this.nameEl.value = r.new_name;
      this.focusNameForRename();
      this.say(`Saved current settings as "${r.new_name}" - type a new name and press Enter.`);
    } else this.say("save failed: " + (r.error || ""), true);
  }

  async renameIfChanged(){
    const newName = this.nameEl.value.trim();
    const oldName = this.pickerEl.value;
    if (!newName || newName === oldName) return;
    const r = await post("/freedom/presets1/rename", { old_name: oldName, new_name: newName });
    if (r.ok){ this.data = r; this.render(); this.say(`Renamed to "${newName}".`); }
    else { this.nameEl.value = oldName; this.say("rename failed: " + (r.error || ""), true); }
  }
}

app.registerExtension({
  name: "freedom.presets_method1",
  async beforeRegisterNodeDef(nodeType, nodeData){
    if (nodeData.name !== "FreedomPresetsMethod1") return;
    css();
    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function(){
      if (onCreated) onCreated.apply(this, arguments);
      const p = new Presets1Panel(this);
      this.__fp1 = p;
      this.addDOMWidget("presets_method1", "FREEDOM_PRESETS_M1", p.root, { serialize: false, hideOnZoom: false });
      this.setSize([420, 300]);
    };
  },
});
