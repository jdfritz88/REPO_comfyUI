// ==========================================
// FREEDOM SYSTEM - ComfyUI Video Queue panel  (Phase B)
// web/video_queue.js
// ==========================================
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const CSS = `
.fvq-root{display:flex;flex-direction:column;gap:6px;height:100%;min-height:460px;font:12px/1.35 system-ui,Segoe UI,sans-serif;color:#ddd;background:#1c1c1c;border:1px solid #444;border-radius:6px;padding:8px;overflow:auto}
.fvq-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
.fvq-slot{position:relative;aspect-ratio:16/10;border:2px solid #3a3a3a;border-radius:6px;background:#111;overflow:hidden;cursor:pointer;display:flex;align-items:center;justify-content:center}
.fvq-slot.sel{border-color:#4aa3ff;box-shadow:0 0 0 2px #4aa3ff55}
.fvq-slot.video{border-color:#3fb950}
.fvq-slot.empty{border-style:dashed;color:#555;font-size:22px}
.fvq-slot img{width:100%;height:100%;object-fit:cover}
.fvq-slot .n{position:absolute;top:2px;left:4px;background:#000a;padding:0 5px;border-radius:6px;font-size:10px}
.fvq-slot .st{position:absolute;bottom:2px;left:0;right:0;text-align:center;background:#000a;font-size:10px}
.fvq-slot .st.running{background:#6b4d00cc}.fvq-slot .st.done{background:#1f5a2acc}.fvq-slot .st.pending{background:#26364ecc}
.fvq-slot .x{position:absolute;top:2px;right:2px;background:#000a;border:0;color:#eaa;width:18px;height:18px;border-radius:4px;cursor:pointer;line-height:1}
.fvq-vtag{position:absolute;bottom:2px;right:4px;background:#1f5a2a;color:#dfffdf;font-size:9px;padding:0 4px;border-radius:5px}
.fvq-prompts{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.fvq-pane{display:flex;flex-direction:column;gap:3px}
.fvq-pane .lbl{color:#8ab4ff;font-weight:600;font-size:11px}
.fvq-pane textarea{width:100%;min-height:88px;resize:vertical;background:#141414;color:#eee;border:1px solid #444;border-radius:5px;padding:5px;font:11px/1.35 inherit}
.fvq-pane textarea[readonly]{background:#101010;color:#aaa}
.fvq-row{display:flex;gap:5px;flex-wrap:wrap;align-items:center}
.fvq-row .k{color:#999}
.fvq-btn{background:#2b2b2b;color:#ddd;border:1px solid #555;border-radius:4px;padding:3px 8px;cursor:pointer;white-space:nowrap;font-size:11px}
.fvq-btn:hover{background:#3a3a3a}
.fvq-btn.on{background:#26406b;border-color:#3f6db0;color:#dce9ff}
.fvq-btn.copy{background:#26406b;border-color:#3f6db0;color:#dce9ff}
.fvq-status{color:#9cc4ff;font-size:11px;min-height:14px}
.fvq-hint{color:#9a9a9a;font-size:10.5px;line-height:1.4;background:#161616;border:1px solid #333;border-radius:5px;padding:5px 7px}
.fvq-hint b{color:#cde3ff}
.fvq-chk{display:flex;gap:6px;align-items:center}
`;
function injectCss(){ if(!document.getElementById("fvq-css")){ const s=document.createElement("style"); s.id="fvq-css"; s.textContent=CSS; document.head.appendChild(s);} }
async function get(r){ return (await api.fetchApi(r)).json(); }
async function post(r,b){ return (await api.fetchApi(r,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b||{})})).json(); }
function debounce(fn,ms){ let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a),ms); }; }

class QueuePanel {
    constructor(node){
        this.node = node;
        this.state = null;
        this.root = document.createElement("div");
        this.root.className = "fvq-root";
        this.root.innerHTML = `
          <div class="fvq-grid"></div>
          <div class="fvq-prompts">
            <div class="fvq-pane">
              <span class="lbl">LAST PROMPT USED</span>
              <textarea class="prev" readonly placeholder="(no motion prompt used yet)"></textarea>
            </div>
            <div class="fvq-pane">
              <span class="lbl">THIS SLOT'S PROMPT</span>
              <textarea class="cur" placeholder="Type or paste the motion for this clip - or click Copy from previous"></textarea>
              <button class="fvq-btn copy">Copy from previous prompt</button>
            </div>
          </div>
          <div class="fvq-row"><span class="k">Size:</span><span class="sizes"></span></div>
          <div class="fvq-row"><span class="k">Length:</span><span class="lengths"></span></div>
          <div class="fvq-hint">Default is <b>832&times;480, 3.4&nbsp;s</b> - that's the big video model's
            native clip and the fastest it goes (~2.5&nbsp;min on your card, in Video Mode).
            Bigger size or longer time costs proportionally more. 5&nbsp;s and up are stitched
            from 3.4&nbsp;s pieces.</div>
          <div class="fvq-row">
            <label class="fvq-chk"><input type="checkbox" class="autostart"> Auto-start when an image is sent to the queue</label>
          </div>
          <div class="fvq-row">
            <button class="fvq-btn loadvid" title="Pick a finished video from disk to extend (its saved prompt comes with it)">Load a video to extend</button>
            <button class="fvq-btn clearall">Clear all slots</button>
            <span class="fvq-status"></span>
          </div>
        `;
        this.grid = this.root.querySelector(".fvq-grid");
        this.prevTA = this.root.querySelector(".prev");
        this.curTA = this.root.querySelector(".cur");
        this.sizesEl = this.root.querySelector(".sizes");
        this.lengthsEl = this.root.querySelector(".lengths");
        this.autostartEl = this.root.querySelector(".autostart");
        this.statusEl = this.root.querySelector(".fvq-status");

        this.root.querySelector(".copy").onclick = () => { this.curTA.value = this.prevTA.value; this.saveCur(); };
        this.root.querySelector(".clearall").onclick = async () => { await post("/freedom/video/clear",{all:true}); };
        this.root.querySelector(".loadvid").onclick = async () => {
            this.say("File window open on your desktop...");
            const r = await post("/freedom/video/load_to_queue",{});
            if (r.ok) this.say("Loaded into the queue (green slot). Prompt: " + (r.prompt || "(none saved on that video)"));
            else this.say(r.cancelled ? "Cancelled." : (r.error || "Could not load"), !r.cancelled);
        };
        this.curTA.addEventListener("input", debounce(()=>this.saveCur(), 400));
        this.autostartEl.onchange = () => post("/freedom/video/settings",{auto_start:this.autostartEl.checked});
        for (const ev of ["pointerdown","mousedown","wheel","contextmenu","keydown"]) this.root.addEventListener(ev, e=>e.stopPropagation());

        api.addEventListener("freedom.video.state", e => this.apply(e.detail));
        get("/freedom/video/state").then(s => this.apply(s));
    }

    say(m){ this.statusEl.textContent = m || ""; }
    sel(){ return this.state ? this.state.selected : 0; }

    saveCur(){ post("/freedom/video/set_prompt",{index:this.sel(), prompt:this.curTA.value}); }

    apply(s){
        this.state = s;
        // mirror into the node's `state` widget so it serializes with the workflow (#9, #9b, #19)
        const w = (this.node.widgets||[]).find(x=>x.name==="state");
        if (w){ w.value = JSON.stringify({slots:s.slots, selected:s.selected, last_prompt:s.last_prompt}); this.node.setDirtyCanvas(true,true); }

        this.prevTA.value = s.last_prompt || "";
        const cur = s.slots[s.selected] || {};
        if (document.activeElement !== this.curTA) this.curTA.value = cur.prompt || "";

        // grid
        this.grid.innerHTML = "";
        s.slots.forEach((sl,i)=>{
            const d = document.createElement("div");
            const isVid = sl.kind === "video";
            d.className = "fvq-slot" + (i===s.selected?" sel":"") + (isVid?" video":"") + (sl.status==="empty"?" empty":"");
            if (sl.status==="empty"){
                d.textContent = "+";
                d.title = "Send an image here from the Preview & Pick panel";
            } else {
                const t = sl.thumb ? api.apiURL(sl.thumb + "&t=" + Date.now()) : "";
                d.innerHTML = `<img src="${t}" alt="">`
                  + `<span class="n">${i+1}</span>`
                  + `<span class="st ${sl.status}">${sl.status}</span>`
                  + (isVid?`<span class="fvq-vtag">from video</span>`:"")
                  + `<button class="x" title="Clear this slot">&times;</button>`;
                d.querySelector(".x").onclick = (e)=>{ e.stopPropagation(); post("/freedom/video/clear",{index:i}); };
            }
            d.onclick = ()=> post("/freedom/video/select",{index:i});
            this.grid.appendChild(d);
        });

        // presets
        const setDim = s.settings;
        this.sizesEl.innerHTML = "";
        s.size_presets.forEach(p=>{
            const b=document.createElement("button");
            b.className="fvq-btn"+((cur.width||setDim.width)===p.w && (cur.height||setDim.height)===p.h ? " on":"");
            b.textContent=p.label;
            b.onclick=async()=>{ await post("/freedom/video/set_slot",{index:this.sel(),width:p.w,height:p.h});
                                 await post("/freedom/video/settings",{width:p.w,height:p.h}); };
            this.sizesEl.appendChild(b);
        });
        this.lengthsEl.innerHTML = "";
        s.length_presets.forEach(n=>{
            const b=document.createElement("button");
            b.className="fvq-btn"+((cur.length_s||setDim.length_s)===n ? " on":"");
            b.textContent=n+"s";
            b.onclick=async()=>{ await post("/freedom/video/set_slot",{index:this.sel(),length_s:n});
                                 await post("/freedom/video/settings",{length_s:n}); };
            this.lengthsEl.appendChild(b);
        });
        this.autostartEl.checked = !!setDim.auto_start;

        const pend = s.slots.filter(x=>x.status==="pending"||x.status==="ready").length;
        const done = s.slots.filter(x=>x.status==="done").length;
        this.say(`${pend} waiting, ${done} done. Slot ${s.selected+1} selected.`);
    }
}

app.registerExtension({
    name: "freedom.video_queue",
    async beforeRegisterNodeDef(nodeType, nodeData){
        if (nodeData.name !== "FreedomVideoQueue") return;
        injectCss();
        const onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function(){
            if (onCreated) onCreated.apply(this, arguments);
            const panel = new QueuePanel(this);
            this.__fvq = panel;
            this.addDOMWidget("video_queue","FREEDOM_VIDEO_QUEUE",panel.root,{serialize:false,hideOnZoom:false});
            this.setSize([680, 720]);
            // hide the raw state textarea widget - it's machine data, panel drives it
            const sw = (this.widgets||[]).find(x=>x.name==="state");
            if (sw){ sw.type = "hidden_freedom"; sw.computeSize = ()=>[0,-4]; }
        };
    },
});
