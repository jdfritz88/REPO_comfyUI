// web/checkpoint_prefix.js
//
// Panel for "STEP 7b Summary Signal" (node class FreedomCheckpointFrontText).
// User, 2026-09-29: Q55 = 1, Q71 = 1, Q72 = 1 - the front-text node and the summary
// signal box are ONE node.
//  - One box. It starts with the text saved for the model STEP 1 has picked (for
//    CyberRealistic Pony its score tags); your own words follow. The model's part is
//    locked in the box - "Edit model text" changes it, with Save / Cancel / Delete
//    (press twice) / Save as for another model. No browser dialogs.
//  - The counter counts with ComfyUI's own SDXL word-splitter (/freedom/summary/count):
//    model text + your words must fit on page 1 (75 places). Typing that would spill
//    past page 1 is refused.
//  - WATCHER: when STEP 1's model changes, the old model's text is taken out and the
//    new model's text put in, and then the box is checked for both. The result shows
//    on the node.
//  - PROMPT WATCHER: after every run, the finished prompt STEP 7c built, and this
//    node's own page-1 check from the run.
// Your words live in the node's hidden "signal" field, so they are saved with the
// workflow. The panel itself is not a setting: serialize = false.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE = "FreedomCheckpointFrontText";
const PANEL = "freedom_ckpt_front_panel";
const LOADERS = ["CheckpointLoaderSimple", "CheckpointLoader", "CheckpointLoaderNF4",
                 "ImageOnlyCheckpointLoader", "unCLIPCheckpointLoader"];
const SEP = ", ";                                   // same joiner as the server and STEP 7c

function css() {
  if (document.getElementById("freedom-cfp-css")) return;
  const s = document.createElement("style");
  s.id = "freedom-cfp-css";
  s.textContent = `
    .cfp { font: 12px/1.5 sans-serif; color: #ccc; padding: 6px 8px; margin: 0 4px;
           border: 1px solid #555; border-radius: 4px; background: #1c1c1c; }
    .cfp .t { font-weight: bold; color: #cde3ff; }
    .cfp .ex { color: #aaa; font-size: 11px; margin-bottom: 4px; }
    .cfp .ck { color: #ffd580; font-weight: bold; word-break: break-all; margin: 2px 0 4px; }
    .cfp textarea { width: 100%; box-sizing: border-box; min-height: 60px; background: #111; color: #eee;
                    border: 1px solid #666; border-radius: 3px; font: 12px sans-serif; padding: 3px; resize: vertical; }
    .cfp textarea[readonly] { color: #aaa; background: #181818; }
    .cfp textarea.modeltext { border-color: #d9a441; }
    .cfp .count { font-weight: bold; color: #9c9; margin: 2px 0; }
    .cfp .count.over { color: #f77; }
    .cfp .row { display: flex; gap: 6px; margin: 5px 0; flex-wrap: wrap; }
    .cfp button { font: 11px sans-serif; padding: 2px 10px; background: #333; color: #eee;
                  border: 1px solid #666; border-radius: 3px; cursor: pointer; }
    .cfp button:hover { background: #444; }
    .cfp button:disabled { opacity: 0.4; cursor: default; }
    .cfp button.danger { border-color: #a55; }
    .cfp .msg { color: #bbb; font-size: 11px; min-height: 14px; }
    .cfp .msg.err { color: #f99; }
    .cfp .wt { font-size: 11px; color: #9c9; min-height: 14px; }
    .cfp .wt.err { color: #f77; font-weight: bold; }
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
const countText = (text) => jpost("/freedom/summary/count", { text });
const shortName = (n) => String(n || "").replace(/\.safetensors$/i, "");

class Panel {
  constructor(node) {
    this.node = node; this.ckpt = null; this.front = ""; this.mode = "words";
    this.armed = false; this.lastGood = ""; this.countSeq = 0;
    this.el = document.createElement("div"); this.el.className = "cfp";
    this.el.innerHTML = `
      <div class="t">STEP 7b SUMMARY SIGNAL - page 1 of the prompt</div>
      <div class="ex">The art model sums up page 1 (the first 75 places of the prompt) and keeps that
        summary in mind for the whole picture. This box is page 1: the model's own text first (locked),
        then your most important words.</div>
      <div>Model picked in STEP 1:</div><div class="ck">-</div>
      <textarea class="box"></textarea>
      <div class="count">-</div>
      <div class="wt"></div>
      <div class="row"><button class="edit">Edit model text</button><button class="save">Save model text</button>
        <button class="cancel">Cancel</button><button class="del danger">Delete model text</button></div>
      <div class="row"><select class="other" title="Save the model text as another model's entry"></select>
        <button class="saveas">Save as</button></div>
      <div class="msg"></div>
      <div class="w"><div class="t">PROMPT WATCHER - finished prompt from the last run</div>
        <div class="st">(nothing run yet)</div>
        <textarea class="watch" readonly placeholder="Run a picture to see the finished prompt here."></textarea></div>`;
    this.q = (s) => this.el.querySelector(s);
    this.q(".edit").onclick = () => this.edit();
    this.q(".save").onclick = () => this.save();
    this.q(".cancel").onclick = () => this.cancel();
    this.q(".del").onclick = () => this.del();
    this.q(".saveas").onclick = () => this.saveAs();
    this.q(".box").addEventListener("input", () => this.typed());
    this.fillModels();
    for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"])
      this.el.addEventListener(ev, (e) => e.stopPropagation());
    this.buttons();
  }
  w(name) { return (this.node.widgets || []).find((x) => x.name === name); }
  words() { return String(this.w("signal")?.value ?? ""); }
  setWords(v) { const w = this.w("signal"); if (w) w.value = v; }
  enabled() { return this.w("enabled")?.value !== false; }
  prefix() { return this.enabled() && this.front ? this.front + SEP : ""; }
  say(t, err) { const m = this.q(".msg"); m.textContent = t || ""; m.classList.toggle("err", !!err); }
  watcher(t, err) { const m = this.q(".wt"); m.textContent = t ? "WATCHER: " + t : ""; m.classList.toggle("err", !!err); }
  buttons() {
    const model = this.mode === "model";
    this.q(".edit").disabled = model;
    this.q(".save").disabled = !model;
    this.q(".cancel").disabled = !model;
  }

  // ---- the words box -------------------------------------------------------
  render() {                                        // words mode: model text + your words
    if (this.mode !== "words") return;
    const b = this.q(".box");
    b.readOnly = false; b.classList.remove("modeltext");
    b.value = this.prefix() + this.words().replace(/^\s+/, "");
    this.lastGood = b.value;
    this.recount();
  }
  typed() {
    if (this.mode !== "words") return;
    const b = this.q(".box"), p = this.prefix();
    if (!b.value.startsWith(p)) {                   // the model's part is locked in this box
      b.value = this.lastGood;
      return this.say("The start of the box is this model's own text. To change it, press Edit model text.", true);
    }
    this.setWords(b.value.slice(p.length));
    this.recount(true);
  }
  async recount(fromTyping) {
    const b = this.q(".box"), seq = ++this.countSeq;
    const text = this.mode === "words" ? (this.prefix() + this.words()).replace(/[,\s]+$/, "") : b.value.trim();
    let r;
    try { r = await countText(text); } catch (e) { r = { ok: false, error: String(e) }; }
    if (seq !== this.countSeq) return;              // a newer count is on its way
    const c = this.q(".count");
    if (!r.ok) { c.textContent = "Could not count: " + (r.error || "no answer"); c.classList.add("over"); return; }
    if (r.fits) {
      c.textContent = `Page 1: ${r.used} of ${r.limit} places used - ${r.limit - r.used} left`;
      c.classList.remove("over");
      if (this.mode === "words") { this.lastGood = b.value; if (fromTyping) this.say(""); }
      return;
    }
    if (fromTyping && this.mode === "words") {      // refuse the words that would spill over
      b.value = this.lastGood;
      this.setWords(b.value.slice(this.prefix().length));
      this.say("That would not fit on page 1, so it was not added. Shorten your words to add more.", true);
      return this.recount();
    }
    c.textContent = `Page 1 is full: about ${r.used - r.limit} places over. The end of this text lands on page 2 - shorten it.`;
    c.classList.add("over");
  }

  // ---- following STEP 1 (the watcher) --------------------------------------
  async follow() {
    const m = stepOneModel();
    const key = m.problem ? "!" + m.problem : m.name;
    if (key === this.ckpt || this.mode === "model") return;
    const first = this.ckpt === null;
    const oldFront = this.front, oldName = this.ckpt;
    this.ckpt = key; this.armed = false; this.q(".del").textContent = "Delete model text";
    this.q(".ck").textContent = m.problem ? "WARNING: " + m.problem : m.name;
    if (m.problem) { this.front = ""; this.render(); return this.watcher(m.problem + " - no model text used", true); }
    const d = await jget(`/freedom/ckptfront/entry?ckpt=${encodeURIComponent(m.name)}`);
    if (this.ckpt !== key) return;                  // the model changed again meanwhile
    this.front = d.exists && d.front ? String(d.front).trim() : "";
    this.render();
    this.check(first ? null : oldName, oldFront, m.name);
  }
  check(oldName, oldFront, name) {                  // confirm both actions actually happened
    const v = this.q(".box").value;
    const problems = [];
    if (!v.startsWith(this.prefix())) problems.push("the box does not start with " + shortName(name) + "'s text");
    if (oldFront && oldFront !== this.front && v.startsWith(oldFront))
      problems.push("the box still starts with the old model's text");
    if (problems.length) return this.watcher("PROBLEM - " + problems.join("; ") + ".", true);
    const now = this.front
      ? (this.enabled() ? `'${this.front}' is at the start` : `its text '${this.front}' is saved but switched OFF`)
      : "it has no model text (n/a)";
    const gone = oldName && oldFront && oldFront !== this.front ? ` Taken out: '${oldFront}'.` : "";
    this.watcher(`${shortName(name)} - ${now}.${gone} Checked.`);
  }

  // ---- the model-text package ----------------------------------------------
  edit() {
    const m = stepOneModel(); if (m.problem) return this.say("Can't edit: " + m.problem, true);
    this.mode = "model"; this.buttons();
    const b = this.q(".box"); b.classList.add("modeltext"); b.value = this.front; b.focus();
    this.recount();
    this.say(`Editing ${shortName(m.name)}'s own text (your words are set aside meanwhile). Save model text, or Cancel.`);
  }
  cancel() {
    this.mode = "words"; this.buttons(); this.render();
    this.say("Nothing changed.");
  }
  async save() {
    const m = stepOneModel(); if (m.problem) return this.say("Can't save: " + m.problem, true);
    const text = this.q(".box").value.trim();
    const r = await countText(text);
    if (r.ok && !r.fits) return this.say("The model text alone does not fit on page 1. Shorten it.", true);
    const d = await jpost("/freedom/ckptfront/save", { ckpt: m.name, front: text });
    if (!d.ok) return this.say(d.error || "Could not save.", true);
    const oldFront = this.front;
    this.mode = "words"; this.buttons(); this.front = String(d.front || "").trim(); this.render();
    this.check(m.name, oldFront, m.name);
    this.say(d.front ? "Saved as " + shortName(m.name) + "'s text." : "Saved as empty - n/a for " + shortName(m.name) + ".");
  }
  async del() {
    const m = stepOneModel(); if (m.problem) return this.say("Can't delete: " + m.problem, true);
    if (!this.armed) { this.armed = true; this.q(".del").textContent = "Press again to delete";
      return this.say("Press Delete again to remove " + shortName(m.name) + "'s model text."); }
    this.armed = false; this.q(".del").textContent = "Delete model text";
    const d = await jpost("/freedom/ckptfront/delete", { ckpt: m.name });
    if (!d.ok) return this.say(d.error || "Could not delete.", true);
    const oldFront = this.front;
    this.mode = "words"; this.buttons(); this.front = ""; this.render();
    this.check(m.name, oldFront, m.name);
    this.say("Deleted " + shortName(m.name) + "'s model text. Your words are kept.");
  }
  async fillModels() {                            // every checkpoint ComfyUI knows, for "Save as"
    try {
      const d = await jget("/object_info/CheckpointLoaderSimple");
      const list = d.CheckpointLoaderSimple.input.required.ckpt_name[0] || [];
      const sel = this.q(".other");
      sel.innerHTML = `<option value="">-- save model text as which model? --</option>` +
        list.map((n) => `<option value="${n.replace(/"/g, "&quot;")}">${n}</option>`).join("");
    } catch (e) { this.say("Could not list the models for Save as.", true); }
  }
  async saveAs() {
    const target = this.q(".other").value;
    if (!target) return this.say("Pick the model to save this model text for, then press Save as.", true);
    const text = this.mode === "model" ? this.q(".box").value.trim() : this.front;
    const had = (await jget(`/freedom/ckptfront/entry?ckpt=${encodeURIComponent(target)}`)).exists;
    if (had && this.armedSaveAs !== target) {
      this.armedSaveAs = target;
      return this.say(shortName(target) + " already has model text. Press Save as again to replace it.");
    }
    this.armedSaveAs = null;
    const d = await jpost("/freedom/ckptfront/save", { ckpt: target, front: text });
    if (!d.ok) return this.say(d.error || "Could not save.", true);
    this.say("Saved this model text as " + shortName(target) + "'s entry.");
    if (target === stepOneModel().name) { this.mode = "words"; this.buttons(); this.ckpt = null; this.follow(); }
  }
  watch(finished) { this.q(".watch").value = finished; }
  status(s) { this.q(".st").textContent = "This node, at the run: " + s; }
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
  async afterConfigureGraph() {                     // a loaded workflow brings its own words
    for (const p of panels()) { p.ckpt = null; p.mode = "words"; p.buttons(); p.follow(); }
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
    // Your words are kept in the hidden "signal" field (saved with the workflow); the
    // panel's box is where you see and type them.
    const sw = (node.widgets || []).find((x) => x.name === "signal");
    if (sw) {
      // A multiline STRING widget draws its own textarea, so the element is hidden too
      // (same way as STEP 4a's hidden "state" field in freedom_portrait_control).
      sw.type = "hidden"; sw.computeSize = () => [0, -4];
      const hideEl = () => {
        const el = sw.element || sw.inputEl || sw.domElement;
        if (el) { el.style.display = "none"; return true; }
        return false;
      };
      if (!hideEl()) {
        let tries = 0;
        const t = setInterval(() => { if (hideEl() || ++tries > 20) clearInterval(t); }, 100);
      }
    }
    const ew = (node.widgets || []).find((x) => x.name === "enabled");
    if (ew) {
      const orig = ew.callback;
      ew.callback = function (...args) { const r = orig?.apply(this, args); p.render(); return r; };
    }
    const w = node.addDOMWidget(PANEL, "FREEDOM_CKPT_FRONT", p.el, { serialize: false, hideOnZoom: false, getMinHeight: () => 560 });
    w.serialize = false;
    node.widgets.splice(node.widgets.indexOf(w), 1); node.widgets.unshift(w);
    p.follow();
  },
});
