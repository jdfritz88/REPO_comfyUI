// ==========================================================================
// FREEDOM SYSTEM - Prompt Shelf drawer
// Adds a list of clickable saved prompts under the node's positive/negative
// text boxes. Click one to drop its text into the boxes; Save current keeps
// what's in the boxes as a new named prompt.
// ==========================================================================
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const CSS = `
.fps-root{display:flex;flex-direction:column;gap:5px;font:11px/1.35 system-ui,Segoe UI,sans-serif;
  color:#ddd;background:#1c1c1c;border:1px solid #444;border-radius:6px;padding:7px;max-height:230px;overflow:auto}
.fps-bar{display:flex;align-items:center;gap:6px}
.fps-bar .t{font-weight:700;color:#cde3ff;font-size:10px;letter-spacing:.3px;flex:1}
.fps-btn{background:#2b2b2b;color:#ddd;border:1px solid #555;border-radius:4px;padding:3px 8px;cursor:pointer;font-size:10px}
.fps-btn:hover{background:#3a3a3a}
.fps-item{background:#161616;border:1px solid #333;border-radius:5px;padding:5px 6px;display:flex;gap:6px;align-items:flex-start}
.fps-item .m{flex:1;cursor:pointer}
.fps-item .nm{font-weight:600;color:#eee}
.fps-item .no{color:#9a9a9a;font-size:9.5px;margin-top:1px}
.fps-item .x{color:#a66;cursor:pointer;font-size:11px;padding:0 3px}
.fps-item:hover{border-color:#5a7fb0}
.fps-status{color:#9cc4ff;font-size:9.5px;min-height:12px}
`;
function css(){ if(!document.getElementById("fps-css")){ const s=document.createElement("style"); s.id="fps-css"; s.textContent=CSS; document.head.appendChild(s);} }
async function get(r){ return (await api.fetchApi(r)).json(); }
async function post(r,b){ return (await api.fetchApi(r,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b||{})})).json(); }

class Drawer {
  constructor(node){
    this.node = node;
    this.root = document.createElement("div");
    this.root.className = "fps-root";
    this.root.innerHTML = `
      <div class="fps-bar">
        <span class="t">SAVED PROMPTS - click to load</span>
        <button class="fps-btn save">Save current</button>
        <button class="fps-btn refresh">Refresh</button>
      </div>
      <div class="fps-list"></div>
      <div class="fps-status"></div>`;
    this.listEl = this.root.querySelector(".fps-list");
    this.statusEl = this.root.querySelector(".fps-status");
    this.root.querySelector(".save").onclick = () => this.saveCurrent();
    this.root.querySelector(".refresh").onclick = () => this.load();
    for (const ev of ["pointerdown","wheel","contextmenu"]) this.root.addEventListener(ev, e => e.stopPropagation());
    this.load();
  }

  w(name){ return (this.node.widgets||[]).find(x => x.name === name); }
  setW(name, val){
    const w = this.w(name);
    if (!w) return;
    w.value = val;
    if (w.inputEl) w.inputEl.value = val;
    if (w.callback) w.callback(val);
    this.node.setDirtyCanvas(true, true);
  }
  say(m){ this.statusEl.textContent = m || ""; }

  apply(p){
    this.setW("positive", p.positive || "");
    this.setW("negative", p.negative || "");
    this.say(`Loaded "${p.name}". Edit the text above; fill in the <...> parts.`);
  }

  async load(){
    let prompts = [];
    try { prompts = (await get("/freedom/promptshelf/list")).prompts || []; }
    catch(e){ this.say("could not reach the server"); return; }
    this.listEl.innerHTML = "";
    for (const p of prompts){
      const row = document.createElement("div");
      row.className = "fps-item";
      row.innerHTML = `<div class="m"><div class="nm"></div><div class="no"></div></div><div class="x" title="delete">x</div>`;
      row.querySelector(".nm").textContent = p.name;
      row.querySelector(".no").textContent = p.note || "";
      row.querySelector(".m").onclick = () => this.apply(p);
      row.querySelector(".x").onclick = () => this.del(p.name);
      this.listEl.appendChild(row);
    }
  }

  async saveCurrent(){
    const name = prompt("Save the current prompt as:");
    if (!name) return;
    const r = await post("/freedom/promptshelf/save", {
      name: name.trim(),
      positive: this.w("positive")?.value || "",
      negative: this.w("negative")?.value || "",
      note: "your saved prompt",
    });
    if (r.ok){ this.say(`Saved "${name}".`); this.load(); }
    else this.say("save failed: " + (r.error || ""));
  }

  async del(name){
    if (!confirm(`Delete saved prompt "${name}"?`)) return;
    await post("/freedom/promptshelf/delete", { name });
    this.load();
  }
}

app.registerExtension({
  name: "freedom.prompt_shelf",
  async beforeRegisterNodeDef(nodeType, nodeData){
    if (nodeData.name !== "FreedomPromptShelf") return;
    css();
    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function(){
      if (onCreated) onCreated.apply(this, arguments);
      const d = new Drawer(this);
      this.__fps = d;
      this.addDOMWidget("prompt_shelf", "FREEDOM_PROMPT_SHELF", d.root, { serialize: false, hideOnZoom: false });
      this.setSize([420, 560]);
    };
  },
});
