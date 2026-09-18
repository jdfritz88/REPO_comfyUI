// ==========================================
// FREEDOM SYSTEM - ComfyUI Folder Inspector
// web/folder_inspector.js  (the panel you see inside the node)
// ==========================================
//
// Left column  = files in the folder (click one; drag it onto another inspector to move it)
// Right column = description of the clicked file, with a colour banner on top:
//     green = correct folder      amber = right folder but caution (e.g. wrong base model)
//     red   = wrong folder / not a model  (a "Move it there" button appears)

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const LIVE = new Set();   // every inspector panel currently on the canvas

const CSS = `
.fi-root{display:flex;flex-direction:column;height:100%;min-height:260px;font:12px/1.35 system-ui,Segoe UI,sans-serif;color:#ddd;background:#1e1e1e;border:1px solid #444;border-radius:6px;overflow:hidden}
.fi-banner{padding:6px 8px;font-weight:600;border-bottom:1px solid #444;min-height:18px;display:flex;gap:8px;align-items:center}
.fi-banner.green{background:#1f5a2a;color:#d8ffd8}
.fi-banner.amber{background:#6b4d00;color:#ffe9b0}
.fi-banner.red{background:#6e1c1c;color:#ffd6d6}
.fi-banner.grey{background:#333;color:#bbb;font-weight:400}
.fi-banner button{margin-left:auto;background:#eee;color:#222;border:0;border-radius:4px;padding:3px 8px;cursor:pointer;font-weight:600;white-space:nowrap}
.fi-body{display:flex;flex:1;min-height:0}
.fi-list{flex:0 0 46%;margin:0;padding:4px;list-style:none;overflow:auto;border-right:1px solid #444}
.fi-list li{padding:4px 6px;margin:2px 0;border-radius:4px;cursor:grab;display:flex;gap:6px;align-items:center;border-left:4px solid transparent}
.fi-list li:hover{background:#2c2c2c}
.fi-list li.sel{background:#2f3f5f}
.fi-list li.green{border-left-color:#3fb950}
.fi-list li.amber{border-left-color:#e3b341}
.fi-list li.red{border-left-color:#f85149}
.fi-list li.grey{border-left-color:#666;color:#999}
.fi-list .nm{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fi-list .sz{color:#999;font-size:11px}
.fi-desc{flex:1;padding:6px 8px;overflow:auto;white-space:pre-wrap;word-break:break-word}
.fi-desc h4{margin:8px 0 3px;font-size:12px;color:#9cc4ff}
.fi-desc .chip{display:inline-block;background:#2f3f5f;border-radius:10px;padding:1px 7px;margin:2px 3px 2px 0}
.fi-desc table{border-collapse:collapse;font-size:11px}
.fi-desc td{padding:1px 6px 1px 0;vertical-align:top;color:#bbb}
.fi-desc td:first-child{color:#888;white-space:nowrap}
.fi-foot{display:flex;gap:8px;align-items:center;padding:4px 8px;border-top:1px solid #444;color:#999;font-size:11px}
.fi-foot button{background:#333;color:#ddd;border:1px solid #555;border-radius:4px;padding:2px 8px;cursor:pointer}
.fi-foot .path{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fi-root.dropping{outline:3px dashed #9cc4ff;outline-offset:-3px}
`;

function injectCss() {
    if (document.getElementById("fi-css")) return;
    const s = document.createElement("style");
    s.id = "fi-css";
    s.textContent = CSS;
    document.head.appendChild(s);
}

async function getJSON(route) {
    const r = await api.fetchApi(route);
    return r.json();
}

async function postJSON(route, body) {
    const r = await api.fetchApi(route, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    return r.json();
}

function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function shortPath(p) {
    if (!p) return "(folder not found)";
    const parts = p.replace(/\\/g, "/").split("/").filter(Boolean);
    return parts.length > 3 ? ".../" + parts.slice(-3).join("/") : parts.join("/");
}

function refreshAll(types) {
    for (const panel of LIVE) {
        if (!types || types.includes(panel.folderType())) panel.refresh();
    }
}

class InspectorPanel {
    constructor(node) {
        this.node = node;
        this.selected = "";
        this.root = document.createElement("div");
        this.root.className = "fi-root";
        this.root.innerHTML = `
            <div class="fi-banner grey">Click a file to read about it. Drag a file onto another inspector to move it.</div>
            <div class="fi-body"><ul class="fi-list"></ul><div class="fi-desc"></div></div>
            <div class="fi-foot"><button class="fi-refresh">Refresh</button><span class="path"></span><span class="count"></span></div>`;
        this.banner = this.root.querySelector(".fi-banner");
        this.list = this.root.querySelector(".fi-list");
        this.desc = this.root.querySelector(".fi-desc");
        this.pathEl = this.root.querySelector(".path");
        this.countEl = this.root.querySelector(".count");
        this.root.querySelector(".fi-refresh").onclick = () => this.refresh();

        // keep the canvas from grabbing our clicks / scroll
        for (const ev of ["pointerdown", "mousedown", "wheel", "contextmenu"]) {
            this.root.addEventListener(ev, e => e.stopPropagation());
        }
        // drop target
        this.root.addEventListener("dragover", e => { e.preventDefault(); this.root.classList.add("dropping"); });
        this.root.addEventListener("dragleave", () => this.root.classList.remove("dropping"));
        this.root.addEventListener("drop", e => this.onDrop(e));
        LIVE.add(this);
    }

    folderType() {
        const w = this.node.widgets && this.node.widgets.find(w => w.name === "folder_type");
        return w ? w.value : "loras";
    }

    setBanner(colour, text, button) {
        this.banner.className = "fi-banner " + colour;
        this.banner.innerHTML = esc(text);
        if (button) {
            const b = document.createElement("button");
            b.textContent = button.label;
            b.onclick = button.onclick;
            this.banner.appendChild(b);
        }
    }

    async refresh() {
        const type = this.folderType();
        let data;
        try {
            data = await getJSON("/freedom/inspector/list?type=" + encodeURIComponent(type));
        } catch (e) {
            this.setBanner("red", "Could not talk to ComfyUI: " + e);
            return;
        }
        this.node.title = "[" + type + "]  " + shortPath(data.dir);
        this.pathEl.textContent = data.dir || "";
        this.pathEl.title = data.dir || "";
        this.countEl.textContent = data.items.length + " file" + (data.items.length === 1 ? "" : "s");
        this.list.innerHTML = "";
        for (const it of data.items) {
            const li = document.createElement("li");
            li.className = it.colour || "grey";
            li.draggable = it.kind !== "other";
            li.dataset.rel = it.rel;
            li.innerHTML = `<span class="nm" title="${esc(it.rel)}">${esc(it.rel)}</span><span class="sz">${esc(it.size_h)}</span>`;
            li.onclick = () => this.select(it.rel);
            li.addEventListener("dragstart", e => {
                e.dataTransfer.setData("text/plain", JSON.stringify({ fi: 1, src_type: type, rel: it.rel }));
                e.dataTransfer.effectAllowed = "move";
            });
            if (it.rel === this.selected) li.classList.add("sel");
            this.list.appendChild(li);
        }
        if (this.selected && data.items.some(i => i.rel === this.selected)) {
            this.select(this.selected);
        } else {
            this.selected = "";
            this.desc.innerHTML = `<h4>${esc(type)}</h4>${esc(data.about || "")}<br><br>Colour bars: green = fine, amber = caution, red = wrong folder.`;
        }
        this.node.setDirtyCanvas(true, true);
    }

    async select(rel) {
        const type = this.folderType();
        this.selected = rel;
        for (const li of this.list.children) li.classList.toggle("sel", li.dataset.rel === rel);
        const w = this.node.widgets.find(w => w.name === "selected_file");
        if (w) w.value = rel;
        let d;
        try {
            d = await getJSON("/freedom/inspector/describe?type=" + encodeURIComponent(type) + "&file=" + encodeURIComponent(rel));
        } catch (e) {
            this.setBanner("red", "Could not read file: " + e);
            return;
        }
        if (d.error && !d.banner) { this.setBanner("red", d.error); return; }
        const b = d.banner || { colour: "grey", text: "" };
        let button = null;
        if (b.move_to) {
            button = { label: "Move it to '" + b.move_to + "'", onclick: () => this.move(type, rel, b.move_to) };
        }
        this.setBanner(b.colour, b.text, button);

        const rows = [
            ["File", d.file], ["Size", d.size_h], ["What it is", d.kind], ["Made for", d.base],
        ];
        if (d.tensor_count) rows.push(["Tensors", d.tensor_count]);
        let html = "<table>" + rows.map(r => `<tr><td>${esc(r[0])}</td><td>${esc(r[1])}</td></tr>`).join("") + "</table>";
        if (d.about_kind) html += `<h4>About this kind of file</h4>${esc(d.about_kind)}`;
        if (d.triggers && d.triggers.length) {
            html += "<h4>Trigger words (from training tags)</h4>" + d.triggers.map(t => `<span class="chip">${esc(t)}</span>`).join("");
        }
        if (d.notes && d.notes.length) html += "<h4>Notes</h4>" + d.notes.map(n => "- " + esc(n)).join("<br>");
        if (d.error) html += `<h4>Problem</h4>${esc(d.error)}`;
        const meta = d.meta || {};
        const mk = Object.keys(meta);
        if (mk.length) {
            html += "<h4>Details stored inside the file</h4><table>" + mk.map(k => `<tr><td>${esc(k)}</td><td>${esc(meta[k])}</td></tr>`).join("") + "</table>";
        }
        if (d.sidecars && d.sidecars.length) {
            for (const sc of d.sidecars) html += `<h4>Notes file: ${esc(sc[0])}</h4>${esc(sc[1])}`;
        }
        this.desc.innerHTML = html;
    }

    onDrop(e) {
        e.preventDefault();
        this.root.classList.remove("dropping");
        let payload;
        try { payload = JSON.parse(e.dataTransfer.getData("text/plain")); } catch (_) { return; }
        if (!payload || payload.fi !== 1) return;
        const dst = this.folderType();
        if (payload.src_type === dst) { this.setBanner("grey", "That file is already in this folder."); return; }
        this.move(payload.src_type, payload.rel, dst);
    }

    async move(srcType, rel, dstType) {
        const ok = window.confirm("Move '" + rel + "'\nfrom  " + srcType + "\nto    " + dstType + " ?\n\nThe file (and any notes next to it) will be moved on disk.");
        if (!ok) return;
        this.setBanner("grey", "Moving...");
        const r = await postJSON("/freedom/inspector/move", { src_type: srcType, file: rel, dst_type: dstType });
        if (!r.ok) { this.setBanner("red", "Move failed: " + (r.error || "unknown error")); return; }
        refreshAll([srcType, dstType]);
        setTimeout(() => this.setBanner("green", "Moved to " + r.moved_to + (r.extras ? " (+" + r.extras + " notes file(s))" : ""),
            { label: "Undo", onclick: () => this.undo() }), 150);
    }

    async undo() {
        const r = await postJSON("/freedom/inspector/undo", {});
        if (!r.ok) { this.setBanner("red", "Undo failed: " + (r.error || "")); return; }
        refreshAll();
        setTimeout(() => this.setBanner("green", "Put back: " + r.restored), 150);
    }

    destroy() { LIVE.delete(this); }
}

app.registerExtension({
    name: "freedom.folder_inspector",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "FreedomFolderInspector") return;
        injectCss();

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            if (onNodeCreated) onNodeCreated.apply(this, arguments);
            const panel = new InspectorPanel(this);
            this.__fiPanel = panel;
            this.addDOMWidget("inspector", "FREEDOM_INSPECTOR", panel.root, { serialize: false, hideOnZoom: false });
            const ft = this.widgets.find(w => w.name === "folder_type");
            if (ft) {
                const prev = ft.callback;
                ft.callback = function () {
                    if (prev) prev.apply(this, arguments);
                    panel.selected = "";
                    panel.refresh();
                };
            }
            this.setSize([660, 500]);
            setTimeout(() => panel.refresh(), 50);
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            if (onConfigure) onConfigure.apply(this, arguments);
            if (this.__fiPanel) setTimeout(() => this.__fiPanel.refresh(), 50);
        };

        const onRemoved = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            if (this.__fiPanel) this.__fiPanel.destroy();
            if (onRemoved) onRemoved.apply(this, arguments);
        };
    },
});
