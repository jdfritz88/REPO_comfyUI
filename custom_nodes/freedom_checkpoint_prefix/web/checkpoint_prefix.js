// web/checkpoint_prefix.js
//
// Panel for "STEP 7c Summary Signal" (node class FreedomCheckpointFrontText).
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
//  - "At the last run": this node's own page-1 check from the run.
//  - The finished prompt STEP 7d built shows on its own node, STEP 7b Prompt Watcher
//    (FreedomPromptWatcher, user 2026-09-30) - see WatchPanel below.
// Your words live in the node's hidden "signal" field, so they are saved with the
// workflow. The panel itself is not a setting: serialize = false.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE = "FreedomCheckpointFrontText";
const PANEL = "freedom_ckpt_front_panel";
const LOADERS = ["CheckpointLoaderSimple", "CheckpointLoader", "CheckpointLoaderNF4",
                 "ImageOnlyCheckpointLoader", "unCLIPCheckpointLoader"];
const SEP = ", ";                                   // same joiner as the server and STEP 7d

function css() {
  if (document.getElementById("freedom-cfp-css")) return;
  const s = document.createElement("style");
  s.id = "freedom-cfp-css";
  s.textContent = `
    .cfp { font: 13px/1.5 sans-serif; color: #ccc; padding: 6px 8px; margin: 0 4px;
           border: 1px solid #555; border-radius: 4px; background: #1c1c1c; }
    .cfp .t { font-weight: bold; color: #cde3ff; }
    .cfp .ex { color: #aaa; font-size: 12px; margin-bottom: 4px; }
    .cfp .ck { color: #ffd580; font-weight: bold; word-break: break-all; margin: 2px 0 4px; }
    .cfp textarea { width: 100%; box-sizing: border-box; min-height: 60px; background: #111; color: #eee;
                    border: 1px solid #666; border-radius: 3px; font: 13px sans-serif; padding: 3px; resize: vertical; }
    .cfp textarea[readonly] { color: #aaa; background: #181818; }
    .cfp textarea.box { border: 2px solid #90ee90; }    /* a prompt box you type in: light green frame (user, 2026-09-30) */
    .cfp textarea.modeltext { border-color: #d9a441; }
    .cfp .count { font-weight: bold; color: #9c9; margin: 2px 0; }
    .cfp .count.over { color: #f77; }
    .cfp .row { display: flex; gap: 6px; margin: 5px 0; flex-wrap: wrap; }
    .cfp button { font: 12px sans-serif; padding: 2px 10px; background: #333; color: #eee;
                  border: 1px solid #666; border-radius: 3px; cursor: pointer; }
    .cfp button:hover { background: #444; }
    .cfp button:disabled { opacity: 0.4; cursor: default; }
    .cfp button.danger { border-color: #a55; }
    .cfp .msg { color: #bbb; font-size: 12px; min-height: 14px; }
    .cfp .msg.err { color: #f99; }
    .cfp .wt { font-size: 12px; color: #9c9; min-height: 14px; }
    .cfp .wt.err { color: #f77; font-weight: bold; }
    .cfp .w { margin-top: 6px; border-top: 1px solid #444; padding-top: 5px; }
    .cfp .w .t { color: #b8f0b8; }
    .cfp .st { font-size: 12px; color: #9c9; }
    .cfp-sec { margin: 2px 4px; display: flex; flex-direction: column; }
    .cfp-sec textarea.box { flex: 1; height: 100%; resize: none; }
    .cfp .green { background: #1f7a33; color: #fff; border: 1px solid #39b35a; border-radius: 6px;
                  padding: 10px 14px; font-size: 14px; font-weight: 700; width: 100%; }
    .cfp .green:hover { background: #26933e; }
    .cfp .gmsg { font-size: 12px; color: #9cc4ff; min-height: 14px; }
    .cfp .gmsg.err { color: #f99; }`;
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
function makeRenamer({ button, field, current, apply, say, blocked,
                       armedLabel = "Save new name", allowEmpty = false, requireChange = true }) {
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
    if (!v) { say("Type a name first."); return; }
    if (requireChange && v === cur) { say("The name was not changed."); return; }
    await apply(v);
  };
  const click = async () => {
    if (armed) { armed.el.focus(); return; }   // a 2nd press does nothing - the box's Confirm does it
    const stop = blocked?.();
    if (stop) { say(stop); return; }
    const f = field(); const cur = current();
    if (!f || (!cur && !allowEmpty)) { say("There is nothing here to rename."); return; }
    const before = f.value;
    f.value = cur || (allowEmpty ? f.value : ""); f.focus(); f.select?.(); blinkThree(f);
    const onKey = (e) => {
      if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); confirm(); }
      else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); end(true); say("Rename cancelled - the name is unchanged."); }
    };
    f.addEventListener("keydown", onKey, true);
    armed = { el: f, before, onKey };
    ask.open(`${label}: pick the model in the menu, then press Confirm.`, confirm,
      () => { end(true); say("Cancelled - nothing was changed."); });
    say("Pick the model in the menu, then press Confirm (or Enter). Cancel or Esc stops.");
  };
  return { click };
}

class Panel {
  constructor(node) {
    this.node = node; this.ckpt = null; this.front = ""; this.mode = "words";
    this.lastGood = ""; this.countSeq = 0;
    this.el = document.createElement("div"); this.el.className = "cfp";
    this.el.innerHTML = `
      <div class="t">STEP 7c SUMMARY SIGNAL - page 1 of the prompt</div>
      <div class="ex">The art model sums up page 1 (the first 75 places of the prompt) and keeps that
        summary in mind for the whole picture. This box is page 1: the model's own text first, then her
        trigger word in trained-face mode (both locked - the trigger's weight is set on the STEP 3b Face
        Shelf), then your most important words.</div>
      <div>Model picked in STEP 1:</div><div class="ck">-</div>
      <textarea class="box"></textarea>
      <div class="count">-</div>
      <div class="wt"></div>
      <div class="row"><button class="edit">Edit model text</button><button class="save">Save model text</button>
        <button class="cancel">Cancel</button><button class="del danger">Delete model text</button></div>
      <div class="row"><select class="other" title="Save the model text as another model's entry"></select>
        <button class="saveas">Save as</button></div>
      <div class="msg"></div>
      <div class="st">At the last run: (nothing run yet)</div>`;
    // Each section is its own adjustable field (user, 2026-09-30): the parts built
    // above are moved into separate boxes, each drawn as its own node widget.
    const kids = [...this.el.children];
    const pick = (from, to) => kids.slice(from, to);
    const groups = [["explain", pick(0, 2)], ["model", pick(2, 4)], ["box", pick(4, 5)],
                    ["check", pick(5, 7)], ["buttons", pick(7, 10)], ["status", pick(10, 11)]];
    this.sections = groups.map(([name, els]) => {
      const s = document.createElement("div"); s.className = "cfp cfp-sec";
      s.append(...els);
      for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"])
        s.addEventListener(ev, (e) => e.stopPropagation());
      return [name, s];
    });
    this.q = (s) => { for (const [, sec] of this.sections) { const f = sec.querySelector(s); if (f) return f; } return null; };
    this.q(".edit").onclick = () => this.edit();
    this.q(".save").onclick = () => this.save();
    this.q(".cancel").onclick = () => this.cancel();
    this.q(".del").onclick = () => this.del();
    this.delAsk = askBox(this.q(".del"));          // Delete asks in the box (user, 2026-10-01)
    this.replaceAsk = askBox(this.q(".saveas"));   // so does replacing another model's text
    // Save as (user, 2026-09-30): 1st click points you at the model menu (it blinks
    // and takes the focus); pick the model, then Enter or a 2nd click saves.
    const saveAser = makeRenamer({
      button: this.q(".saveas"), field: () => this.q(".other"),
      armedLabel: "Save as new", allowEmpty: true, requireChange: false,
      current: () => "",
      say: (t) => this.say(t),
      apply: async (model) => { this.q(".other").value = model; await this.saveAs(); },
    });
    this.q(".saveas").onclick = () => saveAser.click();
    this.q(".box").addEventListener("input", () => this.typed());
    this.fillModels();
    this.buttons();
  }
  w(name) { return (this.node.widgets || []).find((x) => x.name === name); }
  words() { return String(this.w("signal")?.value ?? ""); }
  setWords(v) { const w = this.w("signal"); if (w) w.value = v; }
  enabled() { return this.w("enabled")?.value !== false; }
  // Her trigger word, shown locked after the model's text in trained-face mode (user, 2026-10-01,
  // choice 2). Read from the FINAL COMBINED PROMPT code so both always agree; its weight comes from
  // the Face Shelf's trigger_weight dial and cannot be typed here.
  trigger() { try { return window.__freedomFinal?.liveTrigger?.() || ""; } catch (e) { return ""; } }
  prefix() {
    const locked = [this.enabled() && this.front ? this.front : "", this.trigger()].filter(Boolean);
    return locked.length ? locked.join(SEP) + SEP : "";
  }
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
    // her trigger word appears, changes or disappears with STEP 2 and the Face Shelf
    const t = this.trigger();
    if (t !== this.lastTrig) {
      const seen = this.lastTrig !== undefined;
      this.lastTrig = t;
      if (seen && this.mode === "words") this.render();
    }
    const m = stepOneModel();
    const key = m.problem ? "!" + m.problem : m.name;
    if (key === this.ckpt || this.mode === "model") return;
    const first = this.ckpt === null;
    const oldFront = this.front, oldName = this.ckpt;
    this.ckpt = key; this.delAsk.close(); this.replaceAsk.close();   // they were about the old model
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
    this.say("");
    this.delAsk.open("Remove " + shortName(m.name) + "'s model text for good? Your words are kept.",
      () => this.doDel(m), () => this.say("Cancelled - nothing was changed."));
  }
  async doDel(m) {
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
  async saveAs(replace) {
    const target = this.q(".other").value;
    if (!target) return this.say("Pick the model to save this model text for, then press Save as.", true);
    const text = this.mode === "model" ? this.q(".box").value.trim() : this.front;
    const had = (await jget(`/freedom/ckptfront/entry?ckpt=${encodeURIComponent(target)}`)).exists;
    if (had && !replace) {
      this.say("");
      return this.replaceAsk.open(shortName(target) + " already has model text. Replace it with this one?",
        () => this.saveAs(true), () => this.say("Cancelled - nothing was changed."));
    }
    const d = await jpost("/freedom/ckptfront/save", { ckpt: target, front: text });
    if (!d.ok) return this.say(d.error || "Could not save.", true);
    this.say("Saved this model text as " + shortName(target) + "'s entry.");
    if (target === stepOneModel().name) { this.mode = "words"; this.buttons(); this.ckpt = null; this.follow(); }
  }
  status(s) { this.q(".st").textContent = "At the last run: " + s; }
}

const panels = () => (app.graph?._nodes || []).filter((n) => n.__cfp).map((n) => n.__cfp);

// "Adjustable": its own drag handle on the bottom edge; the height is kept in the
// node's properties so it is saved with the workflow (same as prompt_slots.js).
function makeAdjustable(node, name, elem, minH = 24) {
  elem.style.resize = "vertical"; elem.style.overflow = "auto";
  elem.style.flex = "none";          // keep its own height (ComfyUI would share space evenly)
  elem.style.minHeight = minH + "px"; elem.style.boxSizing = "border-box";
  // Saved heights are put back once the node's saved settings have arrived, and a
  // height is stored only on a real drag (same as prompt_slots.js).
  (node.__adjustables = node.__adjustables || []).push([name, elem]);
  const now = node.properties?.freedom_heights?.[name];
  if (now) { elem.style.height = now + "px"; elem.__applied = Math.round(parseFloat(now)); }
  if (!node.__adjHooked) {
    node.__adjHooked = true;
    const orig = node.onConfigure;
    node.onConfigure = function () {
      const r = orig ? orig.apply(this, arguments) : undefined;
      for (const [nm, el] of this.__adjustables || []) {
        const h = this.properties?.freedom_heights?.[nm];
        if (h) { el.style.height = h + "px"; el.__applied = Math.round(parseFloat(h)); }
      }
      return r;
    };
  }
  // A height is stored only when YOU change it. Each field remembers the last
  // height the CODE gave it (__applied); any other height came from a drag. (Chrome
  // sends no pointer events for its own resize handle, so those cannot be used.)
  let t = null;
  new ResizeObserver(() => {
    clearTimeout(t);
    t = setTimeout(() => {
      if (!elem.isConnected || !elem.style.height) return;
      const h = Math.round(parseFloat(elem.style.height));
      if (!h || h === elem.__applied) return;           // the code set it - not a change
      elem.__applied = h;
      if (node.properties?.freedom_heights?.[name] === h) return;
      node.properties = node.properties || {};
      node.properties.freedom_heights = { ...(node.properties.freedom_heights || {}), [name]: h };
      setTimeout(() => { window.__freedomNoOverlap?.(node); app.extensionManager?.workflow?.activeWorkflow?.changeTracker?.checkState?.(); }, 50);
    }, 300);
  }).observe(elem);
}

// ---- STEP 7b Prompt Watcher: its own node (user, 2026-09-30) -------------------
// Split out of the Summary Signal. Screen only: FreedomPromptWatcher has no inputs
// or outputs, so the server never runs it; the page fills it after each run.
const WATCHER = "FreedomPromptWatcher";
const WATCH_PANEL = "freedom_prompt_watcher_panel";

class WatchPanel {
  constructor(node) {
    this.node = node;
    this.el = document.createElement("div"); this.el.className = "cfp";
    this.el.innerHTML = `
      <div class="t">PROMPT WATCHER - the finished prompt from the last run</div>
      <div class="ex">Every word the art model got for the last picture made from this page, in the
        order it got them: the Summary Signal, your physical and everything-else boxes, her trigger
        word, and Portrait Master's words. Use it to spot a word that is missing, doubled or in the
        wrong place. Read-only. It starts empty when the page loads and fills after the next Run.</div>
      <textarea class="watch" readonly placeholder="Run a picture to see the finished prompt here."></textarea>`;
    for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"])
      this.el.addEventListener(ev, (e) => e.stopPropagation());
  }
  watch(finished) { this.el.querySelector(".watch").value = finished; }
}

const watchPanels = () => (app.graph?._nodes || []).filter((n) => n.__cfw).map((n) => n.__cfw);

app.registerExtension({
  name: "freedom.checkpoint_prefix",
  async setup() {
    api.addEventListener("executed", ({ detail }) => {
      const n = app.graph?.getNodeById?.(Number(detail?.node));
      const out = detail?.output || {};
      if (out.finished_prompt && (!n || n.comfyClass === "FreedomPromptParts"))
        for (const p of watchPanels()) p.watch(out.finished_prompt[0] ?? "");
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
    if (node.comfyClass === WATCHER) {
      css();
      const p = new WatchPanel(node); node.__cfw = p;
      const w = node.addDOMWidget(WATCH_PANEL, "FREEDOM_PROMPT_WATCHER", p.el,
        { serialize: false, hideOnZoom: false, getMinHeight: () => 200 });
      w.serialize = false;
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
      // (same way as STEP 4b's hidden "state" field in freedom_portrait_control).
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
    // One adjustable field per section, in reading order, at the top of the node,
    // then the big green button (user, 2026-09-30).
    const added = [];
    for (const [name, sec] of p.sections) {
      makeAdjustable(node, name, sec, name === "box" ? 60 : 24);
      if (name === "box" && !node.properties?.freedom_heights?.box) { sec.style.height = "90px"; sec.__applied = 90; }
      const w = node.addDOMWidget(`${PANEL}_${name}`, "FREEDOM_CKPT_FRONT", sec, { serialize: false, hideOnZoom: false });
      w.serialize = false; added.push(w);
    }
    const g = document.createElement("div"); g.className = "cfp cfp-sec";
    g.innerHTML = `<button class="green">Update the FINAL COMBINED PROMPT</button><div class="gmsg"></div>`;
    for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"]) g.addEventListener(ev, (e) => e.stopPropagation());
    g.querySelector(".green").onclick = () => {
      const err = window.__freedomFinal ? window.__freedomFinal.update("front") : "The FINAL COMBINED PROMPT code is not loaded.";
      const m = g.querySelector(".gmsg");
      m.textContent = err || `done - the FINAL COMBINED PROMPT now has this box's text (${new Date().toLocaleTimeString()})`;
      m.classList.toggle("err", !!err);
    };
    makeAdjustable(node, "green", g, 40);
    const gw = node.addDOMWidget(`${PANEL}_green`, "FREEDOM_CKPT_FRONT", g, { serialize: false, hideOnZoom: false });
    gw.serialize = false; added.push(gw);
    for (const w of added) node.widgets.splice(node.widgets.indexOf(w), 1);
    node.widgets.unshift(...added);
    p.follow();
  },
});
