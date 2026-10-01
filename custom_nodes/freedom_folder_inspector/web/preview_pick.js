// ==========================================
// FREEDOM SYSTEM - ComfyUI "Preview & Pick" panel
// web/preview_pick.js
// ==========================================
// Shows each picture from the batch with a tick box. Nothing saves until you
// click "Save Image". The save folder lives in the node's `save_folder`
// widget, so it is remembered inside the workflow.

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const CSS = `
.pp-root{display:flex;flex-direction:column;height:100%;min-height:300px;font:13px/1.35 system-ui,Segoe UI,sans-serif;color:#ddd;background:#1e1e1e;border:1px solid #444;border-radius:6px;overflow:hidden}
.pp-grid{flex:1;min-height:0;overflow:auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px;padding:8px}
.pp-card{position:relative;border:2px solid #444;border-radius:6px;overflow:hidden;background:#111;cursor:pointer}
.pp-card.on{border-color:#3fb950;box-shadow:0 0 0 2px #3fb95055}
.pp-card img{display:block;width:100%;height:auto}
.pp-card .tick{position:absolute;top:6px;left:6px;width:20px;height:20px;accent-color:#3fb950;cursor:pointer}
.pp-card .idx{position:absolute;bottom:4px;right:6px;background:#000a;padding:1px 6px;border-radius:8px;font-size:12px}
.pp-empty{padding:24px;color:#888;text-align:center}
.pp-foot{display:flex;flex-direction:column;gap:6px;padding:8px;border-top:1px solid #444}
.pp-row{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.pp-foot button{background:#333;color:#ddd;border:1px solid #555;border-radius:4px;padding:4px 10px;cursor:pointer;white-space:nowrap}
.pp-foot button:hover{background:#444}
.pp-foot .save{background:#1f5a2a;border-color:#2e7d3a;color:#e8ffe8;font-weight:700;padding:6px 16px;font-size:13.5px}
.pp-foot .save:disabled{opacity:.45;cursor:default}
.pp-foot .setfolder{background:#26364e;border-color:#39547a;color:#dce9ff}
.pp-foot .status{flex:1;min-width:120px;color:#9cc4ff;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pp-foot .status.err{color:#ff9c9c}
.pp-foot .folder{flex:1;min-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#cfe2ff}
.pp-foot .lbl{color:#999}
.pp-viewer{position:fixed;inset:0;z-index:100000;background:rgba(0,0,0,.88);display:flex;align-items:center;justify-content:center}
.pp-viewer .pic{max-width:calc(100vw - 220px);max-height:calc(100vh - 90px);object-fit:contain;user-select:none;box-shadow:0 0 30px #000}
.pp-viewer .nav{position:fixed;top:50%;transform:translateY(-50%);width:84px;height:140px;border:none;border-radius:10px;background:rgba(255,255,255,.08);color:#fff;font:64px/1 sans-serif;cursor:pointer}
.pp-viewer .nav:hover{background:rgba(255,255,255,.22)}
.pp-viewer .prev{left:16px}.pp-viewer .next{right:16px}
.pp-viewer .close{position:fixed;top:14px;right:16px;width:52px;height:52px;border:none;border-radius:10px;background:rgba(255,255,255,.08);color:#fff;font:30px/1 sans-serif;cursor:pointer}
.pp-viewer .close:hover{background:rgba(255,80,80,.5)}
.pp-viewer .count{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);color:#eee;font:20px sans-serif;background:rgba(0,0,0,.6);padding:5px 14px;border-radius:8px}
`;

function injectCss() {
    if (document.getElementById("pp-css")) return;
    const s = document.createElement("style");
    s.id = "pp-css";
    s.textContent = CSS;
    document.head.appendChild(s);
}

async function postJSON(route, body) {
    return (await api.fetchApi(route, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
    })).json();
}

class PickPanel {
    constructor(node) {
        this.node = node;
        this.files = [];
        this.prefix = "freedom";
        this.root = document.createElement("div");
        this.root.className = "pp-root";
        this.root.innerHTML = `
          <div class="pp-grid"><div class="pp-empty">Press Run. Your pictures appear here - nothing is saved until you click "Save Image".</div></div>
          <div class="pp-foot">
            <div class="pp-row">
              <button class="save" disabled>Save Image</button>
              <button class="b-all">Select all</button>
              <button class="b-none">Select none</button>
              <span class="status"></span>
            </div>
            <div class="pp-row">
              <button class="setfolder" title="Pick the folder that Save Image writes to (Windows folder window)">Set User Save Folder</button>
              <button class="b-open" title="Open that folder in Explorer">Open Folder</button>
              <span class="lbl">to:</span><span class="folder" title=""></span>
            </div>
            <div class="pp-row">
              <button class="tovideo setfolder" title="Send the ticked pictures to the 9-slot video queue">Send selected image to video workflow queue</button>
              <span class="lbl" style="opacity:.8">To send an image to the video generation queue, click the image (or several for a batch), then click this button.</span>
            </div>
            <div class="pp-row">
              <button class="b-archive setfolder" title="Open output/freedom_archive in Explorer - every picture, kept automatically">Open Archive Folder</button>
              <span class="lbl archive-line" style="opacity:.8">Auto-save keeps a copy of every picture in output/freedom_archive (switch below).</span>
            </div>
          </div>`;
        this.grid = this.root.querySelector(".pp-grid");
        this.saveBtn = this.root.querySelector(".save");
        this.status = this.root.querySelector(".status");
        this.folderEl = this.root.querySelector(".folder");
        this.root.querySelector(".setfolder").onclick = () => this.setFolder();
        this.root.querySelector(".tovideo").onclick = () => this.sendToVideoQueue();
        this.root.querySelector(".b-open").onclick = () => postJSON("/freedom/save/open", { folder: this.folder() });
        // The same GET route the old "about AUTO-SAVE" note linked to.
        this.root.querySelector(".b-archive").onclick = () =>
            api.fetchApi("/freedom/save/open_folder?sub=freedom_archive");
        this.archiveLine = this.root.querySelector(".archive-line");
        this.root.querySelector(".b-all").onclick = () => this.setAll(true);
        this.root.querySelector(".b-none").onclick = () => this.setAll(false);
        this.saveBtn.onclick = () => this.save();
        for (const ev of ["pointerdown", "mousedown", "wheel", "contextmenu"]) {
            this.root.addEventListener(ev, e => e.stopPropagation());
        }
        this.refreshFolderDisplay();
    }

    say(msg, err) { this.status.textContent = msg; this.status.className = "status" + (err ? " err" : ""); }

    _widget() { return (this.node.widgets || []).find(w => w.name === "save_folder"); }

    folder() { const w = this._widget(); return (w && w.value ? String(w.value) : "").trim(); }

    setWidget(path) {
        const w = this._widget();
        if (w) { w.value = path; if (w.callback) w.callback(path); }
        this.refreshFolderDisplay();
        this.node.setDirtyCanvas(true, true);   // mark workflow dirty so it serializes
    }

    refreshFolderDisplay() {
        const f = this.folder();
        this.folderEl.textContent = f || "(not set - click Set User Save Folder)";
        this.folderEl.title = f || "";
    }

    async setFolder() {
        this.say("Folder window is open on your desktop (it may be behind ComfyUI)...");
        const r = await postJSON("/freedom/save/browse", { folder: this.folder() });
        if (r.ok) { this.setWidget(r.folder); this.say("Save folder set to " + r.folder); }
        else this.say(r.cancelled ? "Folder unchanged." : "Could not open folder window: " + (r.error || ""), !r.cancelled);
    }

    render(message) {
        const files = (message && message.freedom_files) || [];
        if (message && message.freedom_folder && message.freedom_folder[0]) {
            // server resolved the folder (e.g. filled a blank widget with the default)
            const resolved = message.freedom_folder[0];
            if (!this.folder()) this.setWidget(resolved); else this.refreshFolderDisplay();
        }
        if (message && message.freedom_prefix && message.freedom_prefix[0]) this.prefix = message.freedom_prefix[0];
        if (message && Array.isArray(message.freedom_archived)) {
            const a = message.freedom_archived;
            this.archiveLine.textContent = a.length
                ? `Auto-saved ${a.length} to output/${a[0].subfolder || ""} (${a[0].filename}${a.length > 1 ? " ... " + a[a.length - 1].filename : ""}).`
                : "Auto-save is off - this run was not archived.";
        }
        this.files = files.map(f => ({ ...f, on: files.length === 1 }));
        this.urls = [];                       // every picture of this run, for the viewer
        this.grid.innerHTML = "";
        if (!files.length) {
            this.grid.innerHTML = `<div class="pp-empty">No pictures came out of this run.</div>`;
            this.updateButtons();
            return;
        }
        this.files.forEach((f, i) => {
            const card = document.createElement("div");
            card.className = "pp-card" + (f.on ? " on" : "");
            const url = api.apiURL("/view?filename=" + encodeURIComponent(f.filename)
                + "&subfolder=" + encodeURIComponent(f.subfolder) + "&type=temp&t=" + Date.now());
            card.innerHTML = `<img src="${url}" alt=""><input class="tick" type="checkbox" ${f.on ? "checked" : ""}>`
                + `<span class="idx">${i + 1} of ${files.length}${f.width ? " - " + f.width + "x" + f.height : ""}</span>`;
            const tick = card.querySelector(".tick");
            const toggle = (v) => { f.on = v; tick.checked = v; card.classList.toggle("on", v); this.updateButtons(); };
            card.onclick = (e) => { if (e.target !== tick) toggle(!f.on); };
            tick.onchange = () => toggle(tick.checked);
            this.urls.push(url);
            card.ondblclick = () => this.openViewer(i);
            card.title = "Click = select / unselect.  Double-click = open full size.";
            this.grid.appendChild(card);
        });
        this.say(files.length === 1
            ? "1 picture ready. Click \"Save Image\" to keep it."
            : files.length + " pictures. Tick the ones you want, then \"Save Selected Images\".");
        this.updateButtons();
    }

    // Double-click a picture: it opens large ON TOP OF ComfyUI (no new tab, so Chrome
    // can never block it), with arrows left and right, the arrow keys, a "2 of 4" count,
    // and an X. Esc or a click on the dark area closes it (user, 2026-09-30, Q = 1).
    openViewer(start) {
        const urls = this.urls || [];
        if (!urls.length) return;
        document.querySelector(".pp-viewer")?.remove();
        const many = urls.length > 1;
        const v = document.createElement("div");
        v.className = "pp-viewer";
        v.innerHTML = `<img class="pic" alt="">
          <button class="nav prev" title="Previous picture (left arrow key)">&#8249;</button>
          <button class="nav next" title="Next picture (right arrow key)">&#8250;</button>
          <button class="close" title="Close (Esc)">&#10005;</button>
          <div class="count"></div>`;
        const pic = v.querySelector(".pic"), count = v.querySelector(".count");
        let i = start;
        const show = () => { pic.src = urls[i]; count.textContent = (i + 1) + " of " + urls.length; };
        const step = (d) => { i = (i + d + urls.length) % urls.length; show(); };   // wraps around
        const close = () => { v.remove(); document.removeEventListener("keydown", onKey, true); };
        // Keys go to the viewer only while it is open, so ComfyUI's own shortcuts don't fire.
        const onKey = (e) => {
            if (e.key === "ArrowLeft" && many) step(-1);
            else if (e.key === "ArrowRight" && many) step(1);
            else if (e.key === "Escape") close();
            else return;
            e.preventDefault(); e.stopPropagation();
        };
        v.querySelector(".prev").onclick = (e) => { e.stopPropagation(); step(-1); };
        v.querySelector(".next").onclick = (e) => { e.stopPropagation(); step(1); };
        v.querySelector(".close").onclick = (e) => { e.stopPropagation(); close(); };
        pic.onclick = (e) => e.stopPropagation();          // clicking the picture keeps it open
        v.onclick = close;                                 // clicking the dark area closes it
        for (const ev of ["pointerdown", "mousedown", "wheel", "contextmenu", "dblclick"]) {
            v.addEventListener(ev, e => e.stopPropagation());
        }
        if (!many) { v.querySelector(".prev").style.display = "none"; v.querySelector(".next").style.display = "none"; }
        document.addEventListener("keydown", onKey, true);
        document.body.appendChild(v);
        show();
    }

    setAll(v) {
        this.files.forEach(f => f.on = v);
        [...this.grid.querySelectorAll(".pp-card")].forEach(c => {
            c.classList.toggle("on", v);
            c.querySelector(".tick").checked = v;
        });
        this.updateButtons();
    }

    updateButtons() {
        const n = this.files.filter(f => f.on).length;
        this.saveBtn.disabled = n === 0;
        this.saveBtn.textContent = this.files.length <= 1 ? "Save Image" : "Save Selected Images (" + n + ")";
    }

    async sendToVideoQueue() {
        const picked = this.files.filter(f => f.on);
        if (!picked.length) { this.say("Click the picture(s) you want first, then Send selected image to video workflow queue.", true); return; }
        const refs = picked.map(f => ({ filename: f.filename, subfolder: f.subfolder, type: "temp" }));
        try {
            const r = await postJSON("/freedom/video/enqueue", { images: refs, prompt: "" });
            if (!r.ok) { this.say("Video queue error.", true); return; }
            this.say(`Sent ${r.added} to the video queue${r.full ? " (queue was full - " + (picked.length - r.added) + " didn't fit)" : ""}.`);
            if (r.auto_start && r.added && window.app && window.app.queuePrompt) {
                window.app.queuePrompt(0, 1);
                this.say(this.status.textContent + "  Auto-starting...");
            }
        } catch (e) {
            this.say("Video queue not found - add a 'Freedom: Video Queue' node / open the video workflow. (" + e + ")", true);
        }
    }

    async save() {
        const picked = this.files.filter(f => f.on).map(f => f.filename);
        if (!picked.length) return;
        if (!this.folder()) { this.say("Set a save folder first (button below).", true); return; }
        this.saveBtn.disabled = true;
        this.say("Saving...");
        const r = await postJSON("/freedom/save/pick", { files: picked, prefix: this.prefix, folder: this.folder() });
        if (r.saved && r.saved.length) {
            const names = r.saved.map(p => p.split(/[\\/]/).pop()).join(", ");
            this.say("Saved " + r.saved.length + " to " + r.folder + "  (" + names + ")"
                + (r.errors && r.errors.length ? "  - problems: " + r.errors.join("; ") : ""),
                !!(r.errors && r.errors.length));
        } else {
            this.say("Nothing saved: " + ((r.errors || []).join("; ") || r.error || "unknown error"), true);
        }
        this.updateButtons();
    }
}

app.registerExtension({
    name: "freedom.preview_pick",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "FreedomPreviewPick") return;
        injectCss();
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            if (onNodeCreated) onNodeCreated.apply(this, arguments);
            const panel = new PickPanel(this);
            this.__pp = panel;
            this.addDOMWidget("preview_pick", "FREEDOM_PREVIEW_PICK", panel.root, { serialize: false, hideOnZoom: false });
            // One picture display, not two: the server still reports the pictures
            // under "images" (the phone and /history need that), but the desktop
            // must not draw them a second time under the picker. hideOutputImages
            // is the frontend's own switch for this (used by its ImageCompositor).
            this.hideOutputImages = true;
            // auto_save is created from INPUT_TYPES BEFORE the picker panel, but
            // workflows saved before it existed store [prefix, folder, <panel>].
            // Keep the panel's slot third so those old values land where they
            // belong and auto_save falls back to its default (on).
            // Same for archive_prefix: both new settings go after the panel, in
            // this order, so old saves never shift into them.
            const ws = this.widgets || [];
            for (const name of ["auto_save", "archive_prefix"]) {
                const ai = ws.findIndex(x => x.name === name);
                const pi = ws.findIndex(x => x.name === "preview_pick");
                if (ai !== -1 && pi !== -1 && ai < pi) ws.push(ws.splice(ai, 1)[0]);
            }
            this.setSize([640, 720]);
            // keep the folder line in sync if the user edits the widget text directly
            const w = (this.widgets || []).find(x => x.name === "save_folder");
            if (w) {
                const cb = w.callback;
                w.callback = (v) => { if (cb) cb(v); panel.refreshFolderDisplay(); };
            }
        };
        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            if (onExecuted) onExecuted.apply(this, arguments);
            if (this.__pp) this.__pp.render(message);
        };
    },
});
