// web/checkpoint_prefix.js
//
// Panel for "Freedom Checkpoint Front Text" (user, 2026-09-29).
//  - Shows the model STEP 1 has picked and the front text saved for it
//    (or "n/a - nothing saved for this checkpoint"). Follows STEP 1 by itself.
//  - Edit unlocks the box, Save stores it for this model, Delete (press twice)
//    removes this model's entry. No browser dialogs.
//  - PROMPT WATCHER: after every run, the finished prompt STEP 7b built, and this
//    node's own status line ("added '...'" / "n/a ..." / a warning).
// The panel is a label/control strip, not a setting: serialize = false.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE = "FreedomCheckpointFrontText";
const PANEL = "freedom_ckpt_front_panel";
const LOADERS = ["CheckpointLoaderSimple", "CheckpointLoader", "CheckpointLoaderNF4",
                 "ImageOnlyCheckpointLoader", "unCLIPCheckpointLoader"];

function css() {
  if (document.getElementById("freedom-cfp-css")) return;
  const s = document.createElement("style");
  s.id = "freedom-cfp-css";
  s.textContent = `
    .cfp { font: 12px/1.5 sans-serif; color: #ccc; padding: 6px 8px; margin: 0 4px;
           border: 1px solid #555; border-radius: 4px; background: #1c1c1c; }
    .cfp .t { font-weight: bold; color: #cde3ff; }
    .cfp .ck { color: #ffd580; font-weight: bold; word-break: break-all; margin: 2px 0 4px; }
    .cfp textarea { width: 100%; box-sizing: border-box; min-height: 48px; background: #111; color: #eee;
                    border: 1px solid #666; border-radius: 3px; font: 12px sans-serif; padding: 3px; resize: vertical; }
    .cfp textarea[readonly] { color: #aaa; background: #181818; }
    .cfp .row { display: flex; gap: 6px; margin: 5px 0; }
    .cfp button { font: 11px sans-serif; padding: 2px 10px; background: #333; color: #eee;
                  border: 1px solid #666; border-radius: 3px; cursor: pointer; }
    .cfp button:hover { background: #444; }
    .cfp button.danger { border-color: #a55; }
    .cfp .msg { color: #bbb; font-size: 11px; min-height: 14px; }
    .cfp .msg.err { color: #f99; }
    .cfp .w { margin-top: 6px; border-top: 1px solid #444; padding-top: 5px; }
    .cfp .w .t { color: #b8f0b8; }
    .cfp .st { font-size: 11px; color: #9c9; }`;
  document.head.appendChild(s);
}

function stepOneModel() {
  const loaders = (app.graph?._nodes || []).filter((n) => LOADERS.includes(n.comfyClass) && n.mode !== 4 && n.mode !== 2);
  if (loaders.length !== 1) return { name: "", problem: loaders.length ? "more than one model picker - not guessing" : "no model picker found" };
  const w = (loaders[0].widgets || []).find((x) => x.name === "ckpt_name");
  return { name: w ? String(w.value || "") : "", problem: w ? null : "model picker has no ckpt_name" };
}

async function jget(url) { return (await api.fetchApi(url)).json(); }
async function jpost(url, body) {
  return (await api.fetchApi(url, { method: "POST", headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify(body) })).json();
}

class Panel {
  constructor(node) {
    this.node = node; this.ckpt = null; this.editing = false; this.armed = false;
    this.el = document.createElement("div"); this.el.className = "cfp";
    this.el.innerHTML = `
      <div class="t">CHECKPOINT FRONT TEXT - goes at the very start of the prompt</div>
      <div>Model picked in STEP 1:</div><div class="ck">-</div>
      <textarea class="box" readonly></textarea>
      <div class="row"><button class="edit">Edit</button><button class="save">Save</button>
        <button class="del danger">Delete</button></div>
      <div class="row"><select class="other" title="Save this text as another model's entry"></select>
        <button class="saveas">Save as</button></div>
      <div class="msg"></div>
      <div class="w"><div class="t">PROMPT WATCHER - finished prompt from the last run</div>
        <div class="st">(nothing run yet)</div>
        <textarea class="watch" readonly placeholder="Runs a picture to see the finished prompt here."></textarea></div>`;
    this.q = (s) => this.el.querySelector(s);
    this.q(".edit").onclick = () => this.edit();
    this.q(".save").onclick = () => this.save();
    this.q(".del").onclick = () => this.del();
    this.q(".saveas").onclick = () => this.saveAs();
    this.fillModels();
    for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"])
      this.el.addEventListener(ev, (e) => e.stopPropagation());
  }
  say(t, err) { const m = this.q(".msg"); m.textContent = t || ""; m.classList.toggle("err", !!err); }
  async follow() {                                   // called on a timer: keep up with STEP 1
    const m = stepOneModel();
    const key = m.problem ? "!" + m.problem : m.name;
    if (key === this.ckpt || this.editing) return;
    this.ckpt = key; this.armed = false; this.q(".del").textContent = "Delete";
    this.q(".ck").textContent = m.problem ? "WARNING: " + m.problem : m.name;
    if (m.problem) { this.q(".box").value = ""; return; }
    const d = await jget(`/freedom/ckptfront/entry?ckpt=${encodeURIComponent(m.name)}`);
    this.q(".box").value = d.exists && d.front ? d.front : "n/a - nothing saved for this checkpoint";
    this.say(d.exists && d.front ? "Loaded - this will go first in the prompt." : "Nothing will be added for this model.");
  }
  edit() {
    const m = stepOneModel(); if (m.problem) return this.say("Can't edit: " + m.problem, true);
    this.editing = true; const b = this.q(".box"); b.readOnly = false;
    if (b.value.startsWith("n/a - ")) b.value = "";
    b.focus(); this.say("Type the front text for this model, then press Save.");
  }
  async save() {
    const m = stepOneModel(); if (m.problem) return this.say("Can't save: " + m.problem, true);
    const d = await jpost("/freedom/ckptfront/save", { ckpt: m.name, front: this.q(".box").value });
    if (!d.ok) return this.say(d.error || "Could not save.", true);
    this.editing = false; this.q(".box").readOnly = true; this.ckpt = null; await this.follow();
    this.say(d.front ? "Saved for " + m.name + "." : "Saved as empty - n/a for " + m.name + ".");
  }
  async del() {
    const m = stepOneModel(); if (m.problem) return this.say("Can't delete: " + m.problem, true);
    if (!this.armed) { this.armed = true; this.q(".del").textContent = "Press again to delete";
      return this.say("Press Delete again to remove the entry for " + m.name + "."); }
    this.armed = false; this.q(".del").textContent = "Delete";
    const d = await jpost("/freedom/ckptfront/delete", { ckpt: m.name });
    if (!d.ok) return this.say(d.error || "Could not delete.", true);
    this.editing = false; this.q(".box").readOnly = true; this.ckpt = null; await this.follow();
    this.say("Deleted the entry for " + m.name + ".");
  }
  async fillModels() {                            // every checkpoint ComfyUI knows, for "Save as"
    try {
      const d = await jget("/object_info/CheckpointLoaderSimple");
      const list = d.CheckpointLoaderSimple.input.required.ckpt_name[0] || [];
      const sel = this.q(".other");
      sel.innerHTML = `<option value="">-- save as which model? --</option>` +
        list.map((n) => `<option value="${n.replace(/"/g, "&quot;")}">${n}</option>`).join("");
    } catch (e) { this.say("Could not list the models for Save as.", true); }
  }
  async saveAs() {
    const target = this.q(".other").value;
    if (!target) return this.say("Pick the model to save this text for, then press Save as.", true);
    let text = this.q(".box").value;
    if (text.startsWith("n/a - ")) text = "";
    const had = (await jget(`/freedom/ckptfront/entry?ckpt=${encodeURIComponent(target)}`)).exists;
    if (had && this.armedSaveAs !== target) {
      this.armedSaveAs = target;
      return this.say(target + " already has front text. Press Save as again to replace it.");
    }
    this.armedSaveAs = null;
    const d = await jpost("/freedom/ckptfront/save", { ckpt: target, front: text });
    if (!d.ok) return this.say(d.error || "Could not save.", true);
    this.say("Saved this text as the entry for " + target + ".");
  }
  watch(finished) { this.q(".watch").value = finished; }
  status(s) { this.q(".st").textContent = "This node: " + s; }
}

const panels = () => (app.graph?._nodes || []).filter((n) => n.__cfp).map((n) => n.__cfp);

app.registerExtension({
  name: "freedom.checkpoint_prefix",
  async setup() {
    api.addEventListener("executed", ({ detail }) => {
      const n = app.graph?.getNodeById?.(Number(detail?.node));
      const out = detail?.output || {};
      if (out.finished_prompt && (!n || n.comfyClass === "FreedomPromptParts"))
        for (const p of panels()) p.watch(out.finished_prompt[0] ?? "");
      if (out.status && (!n || n.comfyClass === NODE))
        for (const p of panels()) p.status(out.status[0] ?? "");
    });
    setInterval(() => { for (const p of panels()) p.follow(); }, 700);
  },
  async nodeCreated(node) {
    if (LOADERS.includes(node.comfyClass)) {
      // React the moment STEP 1's model changes. The timer in setup() is only a backup:
      // Chrome slows timers in tabs that are not on screen (found in testing, 2026-09-29).
      const w = (node.widgets || []).find((x) => x.name === "ckpt_name");
      if (w && !w.__cfpHooked) {
        const orig = w.callback;
        w.callback = function (...args) {
          const r = orig?.apply(this, args);
          for (const p of panels()) p.follow();
          return r;
        };
        w.__cfpHooked = true;
      }
      return;
    }
    if (node.comfyClass !== NODE) return;
    css();
    const p = new Panel(node); node.__cfp = p;
    const w = node.addDOMWidget(PANEL, "FREEDOM_CKPT_FRONT", p.el, { serialize: false, hideOnZoom: false, getMinHeight: () => 370 });
    w.serialize = false;
    node.widgets.splice(node.widgets.indexOf(w), 1); node.widgets.unshift(w);
    p.follow();
  },
});
