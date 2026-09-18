// ==========================================
// FREEDOM SYSTEM - ComfyUI Save Video panel  (Phase C)
// web/video_save.js
// ==========================================
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const CSS = `
.fvs-root{display:flex;flex-direction:column;gap:6px;height:100%;min-height:280px;font:12px/1.35 system-ui,Segoe UI,sans-serif;color:#ddd;background:#1c1c1c;border:1px solid #444;border-radius:6px;padding:8px}
.fvs-vid{flex:1;min-height:120px;background:#000;border:1px solid #333;border-radius:5px;display:flex;align-items:center;justify-content:center;overflow:hidden}
.fvs-vid video{max-width:100%;max-height:100%}
.fvs-empty{color:#777;text-align:center;padding:20px}
.fvs-row{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.fvs-btn{background:#2b2b2b;color:#ddd;border:1px solid #555;border-radius:4px;padding:4px 10px;cursor:pointer;font-size:11px;white-space:nowrap}
.fvs-btn:hover{background:#3a3a3a}
.fvs-btn.save{background:#1f5a2a;border-color:#2e7d3a;color:#e8ffe8;font-weight:700}
.fvs-btn.set{background:#26406b;border-color:#3f6db0;color:#dce9ff}
.fvs-folder{flex:1;min-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#cfe2ff}
.fvs-status{color:#9cc4ff;font-size:11px;min-height:14px}
.fvs-k{color:#999}
`;
function css(){ if(!document.getElementById("fvs-css")){ const s=document.createElement("style"); s.id="fvs-css"; s.textContent=CSS; document.head.appendChild(s);} }
async function get(r){ return (await api.fetchApi(r)).json(); }
async function post(r,b){ return (await api.fetchApi(r,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b||{})})).json(); }

class SavePanel {
    constructor(node){
        this.node = node;
        this.root = document.createElement("div");
        this.root.className = "fvs-root";
        this.root.innerHTML = `
          <div class="fvs-vid"><div class="fvs-empty">Run the queue - the finished video shows here.<br>It's already auto-saved to <b>output/freedom_video/</b>.</div></div>
          <div class="fvs-row">
            <button class="fvs-btn save">Save to my folder</button>
            <button class="fvs-btn set">Set User Save Folder</button>
            <button class="fvs-btn openauto">Open auto folder</button>
          </div>
          <div class="fvs-row">
            <button class="fvs-btn extend" title="Send this video back into the queue to add more onto the end">Extend video length</button>
          </div>
          <div class="fvs-row"><span class="fvs-k">my folder:</span><span class="fvs-folder"></span></div>
          <div class="fvs-status"></div>
        `;
        this.vid = this.root.querySelector(".fvs-vid");
        this.folderEl = this.root.querySelector(".fvs-folder");
        this.statusEl = this.root.querySelector(".fvs-status");
        this.root.querySelector(".save").onclick = () => this.saveMine();
        this.root.querySelector(".set").onclick = () => this.setFolder();
        this.root.querySelector(".openauto").onclick = () => post("/freedom/video/open_auto");
        this.root.querySelector(".extend").onclick = () => this.extend();
        for (const ev of ["pointerdown","mousedown","wheel","contextmenu"]) this.root.addEventListener(ev, e=>e.stopPropagation());
        this.refreshFolder();
    }
    say(m,err){ this.statusEl.textContent=m||""; this.statusEl.style.color=err?"#ff9c9c":"#9cc4ff"; }
    widget(){ return (this.node.widgets||[]).find(w=>w.name==="save_folder"); }
    folder(){ const w=this.widget(); return (w&&w.value?String(w.value):"").trim(); }
    setW(p){ const w=this.widget(); if(w){ w.value=p; if(w.callback)w.callback(p);} this.refreshFolder(); this.node.setDirtyCanvas(true,true); }
    refreshFolder(){ const f=this.folder(); this.folderEl.textContent=f||"(not set)"; this.folderEl.title=f||""; }

    async setFolder(){
        this.say("Folder window open on your desktop (may be behind ComfyUI)...");
        const r = await post("/freedom/video/browse_folder",{folder:this.folder()});
        if (r.ok){ this.setW(r.folder); this.say("Saved-to folder set to "+r.folder); }
        else this.say(r.cancelled?"Unchanged.":"Could not open folder window.", !r.cancelled);
    }
    async saveMine(){
        if (!this.folder()){ this.say("Set your folder first (button next to this one).", true); return; }
        const r = await post("/freedom/video/save_user",{folder:this.folder()});
        if (r.ok) this.say("Saved a copy to "+r.saved);
        else this.say(r.error||"Save failed", true);
    }
    async extend(){
        const r = await post("/freedom/video/extend",{});
        if (!r.ok){ this.say(r.error||"Could not extend", true); return; }
        this.say("Sent back to the queue (green slot). Type any extra motion, then Run to add onto the end.");
        if (r.auto_start && window.app && window.app.queuePrompt){
            setTimeout(()=>window.app.queuePrompt(0,1), 600);
        }
    }
    showVideo(url){
        this.vid.innerHTML = `<video src="${api.apiURL(url)}" controls autoplay loop muted></video>`;
    }
    onExecuted(msg){
        const v = (msg && msg.freedom_video && msg.freedom_video[0]) || null;
        if (!v) return;
        this.showVideo(v.url);
        this.say("Auto-saved: " + v.rel + (v.prompt ? "   (motion: " + v.prompt.slice(0,60) + ")" : ""));
        // continue: auto-chain a longer clip, then advance to the next queued item
        get("/freedom/video/last_video").then(s => {
            if (s.pending && s.auto_start && window.app && window.app.queuePrompt){
                this.say(this.statusEl.textContent + (s.chaining
                    ? "   Adding the next 5-second piece..."
                    : "   Next in queue starting..."));
                setTimeout(()=>window.app.queuePrompt(0,1), 600);
            }
        });
    }
}

app.registerExtension({
    name: "freedom.video_save",
    async beforeRegisterNodeDef(nodeType, nodeData){
        if (nodeData.name !== "FreedomVideoSave") return;
        css();
        const onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function(){
            if (onCreated) onCreated.apply(this, arguments);
            const panel = new SavePanel(this);
            this.__fvs = panel;
            this.addDOMWidget("video_save","FREEDOM_VIDEO_SAVE",panel.root,{serialize:false,hideOnZoom:false});
            this.setSize([560, 460]);
        };
        const onExec = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function(message){
            if (onExec) onExec.apply(this, arguments);
            if (this.__fvs) this.__fvs.onExecuted(message);
        };
    },
});
