// ==========================================================================
// FREEDOM SYSTEM - Face Competition panel
// Draws the shared inputs + five skip checkboxes + Run button on the
// "Freedom Face Competition - inputs" node. A ticked checkbox bypasses that
// method's whole group so the chain skips it. Run queues the workflow once;
// ComfyUI runs the un-skipped methods one at a time, top to bottom.
// ==========================================================================
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const CSS = `
.ffc-root{display:flex;flex-direction:column;gap:7px;height:100%;min-height:520px;overflow:auto;
  font:12px/1.4 system-ui,Segoe UI,sans-serif;color:#ddd;background:#1c1c1c;border:1px solid #444;border-radius:6px;padding:9px}
.ffc-h{font-weight:700;color:#cde3ff;font-size:11px;letter-spacing:.4px;margin-top:4px}
.ffc-row{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.ffc-btn{background:#2b2b2b;color:#ddd;border:1px solid #555;border-radius:4px;padding:4px 10px;cursor:pointer;font-size:11px}
.ffc-btn:hover{background:#3a3a3a}
.ffc-btn.run{background:#1f5a2a;border-color:#2e7d3a;color:#e8ffe8;font-weight:700;font-size:12px;padding:6px 14px}
.ffc-btn.set{background:#26406b;border-color:#3f6db0;color:#dce9ff}
.ffc-ta{width:100%;min-height:52px;resize:vertical;background:#141414;color:#eee;border:1px solid #444;border-radius:5px;padding:5px;font:11px/1.35 inherit}
.ffc-in{flex:1;min-width:120px;background:#141414;color:#eee;border:1px solid #444;border-radius:4px;padding:4px}
.ffc-sel{background:#141414;color:#eee;border:1px solid #444;border-radius:4px;padding:4px}
.ffc-m{display:flex;gap:7px;align-items:flex-start;background:#161616;border:1px solid #333;border-radius:5px;padding:6px 7px}
.ffc-m input{margin-top:2px}
.ffc-m .t{flex:1}
.ffc-m .name{font-weight:600;color:#eee}
.ffc-m.skip .name{color:#888;text-decoration:line-through}
.ffc-m .uses{font-size:10px;color:#9a9a9a}
.ffc-status{color:#9cc4ff;font-size:11px;min-height:14px}
.ffc-k{color:#999;font-size:10.5px}
`;
function css(){ if(!document.getElementById("ffc-css")){ const s=document.createElement("style"); s.id="ffc-css"; s.textContent=CSS; document.head.appendChild(s);} }
async function get(r){ return (await api.fetchApi(r)).json(); }
async function post(r,b){ return (await api.fetchApi(r,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b||{})})).json(); }

const USES = {
  "1_faceswap":    "her photos (averaged) -> pasted onto the pose. Face only. Highest likeness.",
  "2_instruct":    "her photos + the INSTRUCTION box. Rewrites the whole picture.",
  "3_fingerprint": "her photos + her trained file + InstantID + FaceID. Freshly drawn.",
  "4_expression":  "her photo + the DRIVING PHOTO's expression, then a swap.",
  "5_shapetracer": "her TRAINED FILE + body pose + dense face mesh. Face + body + hair.",
};
const GROUP_PREFIX = {                       // group title starts with this
  "1_faceswap": "METHOD 1", "2_instruct": "METHOD 2", "3_fingerprint": "METHOD 3",
  "4_expression": "METHOD 4", "5_shapetracer": "METHOD 5",
};

class Panel {
  constructor(node){
    this.node = node;
    this.root = document.createElement("div");
    this.root.className = "ffc-root";
    this.root.innerHTML = `
      <div class="ffc-h">THE PICTURE TO PUT HER INTO</div>
      <div class="ffc-row"><span class="ffc-k">pose image (in ComfyUI/input):</span></div>
      <div class="ffc-row"><input class="ffc-in pose" placeholder="filename, e.g. my_pose.png"></div>

      <div class="ffc-h">HER FACE</div>
      <div class="ffc-row">
        <button class="ffc-btn set folder">Choose folder of her photos</button>
        <span class="ffc-k foldertxt">(not set)</span>
      </div>
      <div class="ffc-k">Method 5 also needs your trained file - pick it in the LoRA box inside the METHOD 5 group.</div>

      <div class="ffc-h">DRIVING EXPRESSION PHOTO  (Method 4)</div>
      <div class="ffc-row">
        <input class="ffc-in driving" placeholder="filename in ComfyUI/input - a photo with the expression you want on her">
      </div>
      <div class="ffc-k">Method 4 copies this photo's mouth / eyes / brows / gaze onto her face. Leave blank to use the by-hand dials on the node.</div>

      <div class="ffc-h">HER REAL HAIR  (hair fixes on Methods 1 and 4)</div>
      <div class="ffc-row">
        <input class="ffc-in hairref" placeholder="filename in ComfyUI/input - a clear photo of her real hairstyle">
      </div>
      <div class="ffc-k">Methods 1 and 4 are face-only swaps and keep whatever hair was already in the pose picture. Their repaint and hair-transfer outputs use this photo to put her real hair on instead.</div>

      <div class="ffc-h">INSTRUCTION  (Method 2 only)</div>
      <textarea class="ffc-ta instr" placeholder="e.g. Replace the woman's face and hair with the woman in images 2 and 3; keep the pose, clothes and background"></textarea>

      <div class="ffc-h">SCENE DESCRIPTION  (Methods 3 and 5; Methods 1, 2 and 4 ignore it)</div>
      <textarea class="ffc-ta prompt" placeholder="what the finished picture should be, e.g. a woman in armor under a streetlight"></textarea>
      <textarea class="ffc-ta neg" placeholder="what to avoid"></textarea>

      <div class="ffc-h">THE FIVE METHODS - tick to skip until you untick</div>
      <div class="ffc-methods"></div>

      <div class="ffc-row"><button class="ffc-btn run">Run the competition</button><span class="ffc-status"></span></div>
    `;
    this.methodsEl = this.root.querySelector(".ffc-methods");
    this.statusEl  = this.root.querySelector(".ffc-status");
    this.poseEl    = this.root.querySelector(".pose");
    this.drivingEl = this.root.querySelector(".driving");
    this.hairRefEl = this.root.querySelector(".hairref");
    this.instrEl   = this.root.querySelector(".instr");
    this.promptEl  = this.root.querySelector(".prompt");
    this.negEl     = this.root.querySelector(".neg");
    this.folderTxt = this.root.querySelector(".foldertxt");

    this.root.querySelector(".folder").onclick = () => this.pickFolder();
    this.root.querySelector(".run").onclick    = () => this.run();
    this.poseEl.onchange     = () => this.save({pose_image: this.poseEl.value.trim()});
    this.drivingEl.onchange  = () => this.save({driving_image: this.drivingEl.value.trim()});
    this.hairRefEl.onchange  = () => this.save({hair_reference_image: this.hairRefEl.value.trim()});
    this.instrEl.onchange    = () => this.save({instruction: this.instrEl.value});
    this.promptEl.onchange   = () => this.save({prompt: this.promptEl.value});
    this.negEl.onchange      = () => this.save({negative: this.negEl.value});
    for (const ev of ["pointerdown","mousedown","wheel","contextmenu"]) this.root.addEventListener(ev, e=>e.stopPropagation());
    this.refresh();
  }

  say(m,err){ this.statusEl.textContent=m||""; this.statusEl.style.color=err?"#ff9c9c":"#9cc4ff"; }
  stateWidget(){ return (this.node.widgets||[]).find(w=>w.name==="state"); }

  async save(patch){
    const r = await post("/freedom/facecomp/state", patch);
    if (r && r.state) this.mirror(r.state);
  }

  mirror(s){
    const w = this.stateWidget();
    if (w){ w.value = JSON.stringify(s); this.node.setDirtyCanvas(true,true); }
  }

  async refresh(){
    const s = await get("/freedom/facecomp/state");
    this.poseEl.value    = s.pose_image || "";
    this.drivingEl.value = s.driving_image || "";
    this.hairRefEl.value = s.hair_reference_image || "";
    this.instrEl.value   = s.instruction || "";
    this.promptEl.value  = s.prompt || "";
    this.negEl.value     = s.negative || "";
    this.folderTxt.textContent = s.photo_folder || "(not set)";
    this.methodsEl.innerHTML = "";
    for (const [key, label] of (s._methods || [])){
      const skip = !!s["skip_"+key];
      const row = document.createElement("label");
      row.className = "ffc-m" + (skip ? " skip" : "");
      row.innerHTML = `<input type="checkbox" ${skip?"checked":""}>
        <div class="t"><div class="name">${label}</div><div class="uses">${USES[key]||""}</div></div>`;
      row.querySelector("input").onchange = (e) => this.toggleSkip(key, e.target.checked, row);
      this.methodsEl.appendChild(row);
    }
    this.mirror(s);
    // re-apply bypass state to the graph on load
    for (const [key] of (s._methods || [])) this.applyBypass(key, !!s["skip_"+key]);
  }

  applyBypass(key, skip){
    // Bypass by the node's freedom_method tag, NOT by which group box it sits
    // in - the group boxes overlap on the canvas, so a box for Method 5 can
    // contain Method 3/4 save nodes and switch them off too.
    const num  = String(key).split("_")[0];           // "5_shapetracer" -> "5"
    const mode = skip ? 4 : 0;                         // 4 = bypass, 0 = normal
    let tagged = 0;
    for (const n of (app.graph._nodes || [])){
      if (n.properties && n.properties.freedom_method === num){ n.mode = mode; tagged++; }
    }
    if (!tagged){                                      // old workflow, no tags: fall back to the group box
      const pfx = GROUP_PREFIX[key] || "~nomatch~";
      const g = (app.graph._groups || []).find(gr => (gr.title||"").startsWith(pfx));
      if (g){
        g.recomputeInsideNodes && g.recomputeInsideNodes();
        for (const n of (g._nodes || [])) n.mode = mode;
      }
    }
    app.graph.setDirtyCanvas(true, true);
  }

  toggleSkip(key, skip, row){
    row.classList.toggle("skip", skip);
    this.applyBypass(key, skip);
    this.save({["skip_"+key]: skip});
    this.say(skip ? "Skipping "+key+" until you untick it." : "Now running "+key+".");
  }

  async pickFolder(){
    this.say("Folder window open on your desktop (may be behind ComfyUI)...");
    const r = await post("/freedom/facecomp/browse_folder", {});
    if (r.ok){ this.folderTxt.textContent = r.folder; this.say(`Folder set - ${r.count} photos found.`); this.refresh(); }
    else this.say(r.cancelled ? "Unchanged." : ("Could not open folder window: "+(r.error||"")), !r.cancelled);
  }

  run(){
    if (!this.poseEl.value.trim()){ this.say("Set the pose image filename first.", true); return; }
    this.say("Queued. The un-skipped methods run one at a time, top to bottom - watch the five save files appear.");
    app.queuePrompt(0, 1);
  }
}

app.registerExtension({
  name: "freedom.face_competition",
  async beforeRegisterNodeDef(nodeType, nodeData){
    if (nodeData.name !== "FreedomFaceComp") return;
    css();
    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function(){
      if (onCreated) onCreated.apply(this, arguments);
      const p = new Panel(this);
      this.__ffc = p;
      this.addDOMWidget("face_competition", "FREEDOM_FACE_COMP", p.root, {serialize:false, hideOnZoom:false});
      const sw = (this.widgets||[]).find(w=>w.name==="state");
      if (sw){ sw.type = "hidden"; sw.computeSize = () => [0,0]; }
      this.setSize([440, 720]);
    };
  },
});
