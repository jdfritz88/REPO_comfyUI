// web/facedetailer_presets.js
//
// FaceDetailer (face repaint, STEP 11c) - our presets package and a
// "Reset to Developer's Defaults" button, at the top of the node (user, 2026-09-26).
//
// Presets
//   - A preset records EVERY setting of EVERY dial on the FaceDetailer, by name
//     (seed and its fixed/random control included). A dial that is wired to
//     another node is recorded too, but never overwritten on load - the wire wins.
//   - Names get a prefix from STEP 2 (FreedomFaceSource): "tl_" for trained_face
//     (trained LoRA), "pl_" for random_face (Portrait Master). With STEP 2 off
//     there is no face path, so Save as / Rename explain that instead of guessing.
//   - Stored by freedom_portrait_control's existing routes with scope
//     "facedetailer" -> user/default/portrait_presets/facedetailer/<name>.json
//     (presets.py write_preset: safe names, atomic write, our folder only).
//   - Rename, Save as and Delete ask in a confirm/cancel box under their row
//     (user, 2026-10-01) - no browser dialogs.
//
// Reset to Developer's Defaults
//   - Every dial back to the Impact Pack developer's own value, read live from
//     the running FaceDetailer class (/freedom/pm/defaults -> factory_defaults),
//     so an Impact Pack update changes them automatically. Dials wired to another
//     node are left alone. "control_after_generate" is added by ComfyUI, not by
//     the developer, so it has no developer value and is left as it is.
//
// The panel is a label/control strip, not a setting: its widget is marked
// serialize = false, which frontend 1.53.6 skips when saving and restoring.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE = "FaceDetailer";
const SCOPE = "facedetailer";
const PANEL = "freedom_fd_presets";

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
    ask.open(`${label}: type the name in the name box, then press Confirm.`, confirm,
      () => { end(true); say("Cancelled - nothing was changed."); });
    say("Type the name, then press Confirm (or Enter). Cancel or Esc stops.");
  };
  return { click };
}

// A button never sits switched off (user, 2026-09-30). When it needs something first,
// the field it needs - a dropdown OR a text box - blinks 3 times and stays highlighted
// until you use it. Picking from a dropdown this way only CHOOSES (nothing is loaded,
// unless chooseOnly is false); then the button carries on. Esc lets go of it.
function needPick(field, say, message, onPicked, chooseOnly = true) {
  if (!field) { say?.(message); return; }
  if (field.disabled) field.disabled = false;
  say?.(message);
  blinkThree(field);
  field.style.outline = "3px solid #ffd479";
  field.style.outlineOffset = "1px";
  field.__holdPick = chooseOnly;
  field.__beforePick = field.value;
  field.focus?.();
  const finish = (picked) => {
    field.removeEventListener("change", onChange, true);
    field.removeEventListener("keydown", onKey, true);
    field.style.outline = "";
    if (!picked) { field.value = field.__beforePick; field.__holdPick = false; return; }
    setTimeout(() => onPicked?.(), 0);
  };
  const onChange = () => { if (chooseOnly) field.__pickOnly = true; finish(true); };
  const onKey = (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); finish(false); say?.("Cancelled."); }
  };
  field.addEventListener("change", onChange, true);
  field.addEventListener("keydown", onKey, true);
}


function css() {
  if (document.getElementById("freedom-fdp-css")) return;
  const s = document.createElement("style");
  s.id = "freedom-fdp-css";
  s.textContent = `
    .fdp { font: 13px/1.5 sans-serif; color: #ccc; padding: 6px 8px; margin: 0 4px;
           border: 1px solid #555; border-radius: 4px; background: #1c1c1c; }
    .fdp .t { font-weight: bold; color: #cde3ff; margin-bottom: 4px; }
    .fdp .row { display: flex; gap: 6px; align-items: center; margin-bottom: 6px; flex-wrap: wrap; }
    .fdp select, .fdp input { background: #111; color: #eee; border: 1px solid #666; border-radius: 3px;
                              font: 13px sans-serif; padding: 2px 4px; }
    .fdp select { flex: 1; min-width: 120px; }
    .fdp input { flex: 1; min-width: 120px; }
    .fdp button { font: 12px sans-serif; padding: 2px 8px; background: #333; color: #eee;
                  border: 1px solid #666; border-radius: 3px; cursor: pointer; }
    .fdp button:hover { background: #444; }
    .fdp button.danger { border-color: #a55; }
    .fdp .reset { width: 100%; margin-top: 2px; }
    .fdp .prefix { color: #9c9; font-weight: bold; }
    .fdp .msg { color: #bbb; font-size: 12px; min-height: 14px; }
    .fdp .msg.err { color: #f99; }
    /* repaint OFF | repaint ON (user, 2026-10-01): same look as every on/off pair -
       the side in use green, the other gray with mid-gray lettering */
    .fdp .fdpair { display: flex; flex: 1; }
    .fdp .fdpair button { flex: 1; background: #55575c; color: #a0a0a0; border-color: #55575c;
                          border-radius: 0; padding: 4px 8px; font-size: 13px; }
    .fdp .fdpair button:first-child { border-radius: 3px 0 0 3px; }
    .fdp .fdpair button:last-child { border-radius: 0 3px 3px 0; }
    .fdp .fdpair button:hover { background: #6a6c72; }
    .fdp .fdpair button.on { background: #2e8b3e; color: #fff; border-color: #2e8b3e; }
    .fdp .rpnote { color: #c98a4a; font-size: 12px; margin: -2px 0 6px; }
    .fdp .rpnote:empty { display: none; }`;
  document.head.appendChild(s);
}

function faceMode() {
  const src = (app.graph?.nodes || []).find((n) => n.comfyClass === "FreedomFaceSource");
  return (src?.widgets || []).find((w) => w.name === "mode")?.value || "";
}

function prefixFor(mode) {
  if (mode === "trained_face") return "tl_";
  if (mode === "random_face") return "pl_";
  return "";
}

function withPrefix(raw) {
  const pre = prefixFor(faceMode());
  if (!pre) return { error: "STEP 2 is off - pick trained face (tl_) or random face (pl_) first." };
  let name = (raw || "").trim();
  if (name.startsWith("tl_") || name.startsWith("pl_")) name = name.slice(3);
  if (!name) return { error: "Type a name first." };
  return { name: pre + name };
}

// every real setting on the node, by name (our panel excluded)
function dials(node) {
  return (node.widgets || []).filter((w) => w.name !== PANEL && w.serialize !== false && w.type !== "button");
}

function isWired(node, name) {
  const inp = (node.inputs || []).find((i) => i.name === name || i.widget?.name === name);
  return !!(inp && inp.link != null);
}

function capture(node) {
  const out = {};
  for (const w of dials(node)) out[w.name] = w.value;
  return out;
}

function applyValues(node, values) {
  let changed = 0, skipped = [];
  for (const w of dials(node)) {
    if (!(w.name in values)) continue;
    if (isWired(node, w.name)) { skipped.push(w.name); continue; }
    if (w.value !== values[w.name]) {
      w.value = values[w.name];
      w.callback?.(w.value);           // same path as a hand edit: marks the workflow changed
      changed++;
    }
  }
  node.setDirtyCanvas?.(true, true);
  return { changed, skipped };
}

async function jget(url) {
  const r = await api.fetchApi(url);
  return r.json();
}

async function jpost(url, body) {
  const r = await api.fetchApi(url, { method: "POST", headers: { "Content-Type": "application/json" },
                                      body: JSON.stringify(body) });
  return r.json();
}

class Panel {
  constructor(node) {
    this.node = node;
    this.el = document.createElement("div");
    this.el.className = "fdp";
    this.el.innerHTML = `
      <div class="t">FACEDETAILER PRESETS - every dial, saved by name</div>
      <div class="row"><span class="fdpair">
        <button class="rp-off" title="Switch the face repaint off - the picture is used as painted">repaint OFF</button><button class="rp-on" title="Switch the face repaint on">repaint ON</button>
      </span></div>
      <div class="rpnote"></div>
      <div class="row"><select class="list"></select>
        <button class="load">Load</button><button class="save">Save</button></div>
      <div class="row"><span class="prefix"></span><input class="name" placeholder="new preset name (prefix added for you)">
        <button class="saveas">Save as</button><button class="rename">Rename</button>
        <button class="delete danger">Delete</button></div>
      <div class="row"><button class="reset">Reset to Developer's Defaults</button></div>
      <div class="msg"></div>`;
    this.q = (s) => this.el.querySelector(s);
    // Nothing picked: the preset menu blinks and waits; then the button carries on
    // (Load loads; Save asks you to press it again; Delete opens its confirm box).
    const list = () => this.q(".list");
    const tell = (t) => this.say(t);
    this.q(".load").onclick = () => this.selected() ? this.load()
      : needPick(list(), tell, "Pick the preset to load.", () => this.load());
    this.q(".save").onclick = () => this.selected() ? this.save()
      : needPick(list(), tell, "Pick the preset to save over (or use Save as).",
          () => tell(`Now press Save to save over ${this.selected()}.`));
    const saveAser = makeRenamer({
      button: this.q(".saveas"), field: () => this.q(".name"),
      armedLabel: "Save as new", allowEmpty: true, requireChange: false,
      current: () => this.selected() || "",
      say: (t) => this.say(t),
      apply: async (newText) => { this.q(".name").value = newText; await this.saveAs(); },
    });
    this.q(".saveas").onclick = () => saveAser.click();
    const renamer = makeRenamer({
      button: this.q(".rename"), field: () => this.q(".name"),
      current: () => this.selected() || "",
      say: (t) => this.say(t),
      apply: async (newText) => { this.q(".name").value = newText; await this.rename(); },
    });
    this.q(".rename").onclick = () => this.selected() ? renamer.click()
      : needPick(list(), tell, "Pick the preset to rename.", () => renamer.click());
    this.q(".delete").onclick = () => this.selected() ? this.del()
      : needPick(list(), tell, "Pick the preset to delete.", () => this.del());
    this.q(".reset").onclick = () => this.reset();
    for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"])
      this.el.addEventListener(ev, (e) => e.stopPropagation());
    this.delAsk = askBox(this.q(".delete"));    // Delete asks in the box (user, 2026-10-01)

    // repaint OFF | repaint ON (user, 2026-10-01). It works the workflow's own face
    // repaint switch (in v01/v02: node 35 "STEP 11 SWITCH", in the plumbing frame),
    // found by following this FaceDetailer's picture to the on/off chooser and back
    // through the gate. The repaint still only runs in trained-face mode (STEP 2).
    this.q(".rp-off").onclick = () => this.setRepaint(false);
    this.q(".rp-on").onclick = () => this.setRepaint(true);
    this.showRepaint();
    const t = setInterval(() => {                   // follows changes made elsewhere
      if (!this.node.graph) { clearInterval(t); return; }
      this.showRepaint();
    }, 700);
  }

  // The switch widget this FaceDetailer answers to, or null if the workflow has none.
  repaintSwitch() {
    const g = this.node.graph || app.graph;
    if (!g) return null;
    const link = (id) => (g.links?.get ? g.links.get(id) : g.links?.[id]) || null;
    const from = (n, inputName) => {
      const inp = (n.inputs || []).find((i) => i.name === inputName);
      const l = inp && inp.link != null ? link(inp.link) : null;
      return l ? g.getNodeById(l.origin_id) : null;
    };
    for (const id of this.node.outputs?.[0]?.links || []) {
      const l = link(id);
      const branch = l && g.getNodeById(l.target_id);
      if (!branch || branch.comfyClass !== "ImpactConditionalBranch") continue;
      let src = from(branch, "cond");
      if (src?.comfyClass === "ImpactLogicalOperators") src = from(src, "bool_a");
      const w = (src?.widgets || []).find((x) => x.name === "value");
      if (src?.comfyClass === "PrimitiveBoolean" && w) return { node: src, w };
    }
    return null;
  }

  showRepaint() {
    const sw = this.repaintSwitch();
    const on = !!sw?.w.value;
    this.q(".rp-on").classList.toggle("on", !!sw && on);
    this.q(".rp-off").classList.toggle("on", !!sw && !on);
    const note = !sw ? "This workflow has no face repaint switch, so these buttons do nothing here."
      : (faceMode() !== "trained_face" && on
        ? "STEP 2 is not on trained face, so no repaint happens even with this ON." : "");
    const el = this.q(".rpnote");
    if (el.textContent !== note) el.textContent = note;
  }

  setRepaint(on) {
    const sw = this.repaintSwitch();
    if (!sw) { this.showRepaint(); return; }
    if (sw.w.value !== on) {
      sw.w.value = on;
      try { sw.w.callback?.(on); } catch (e) { /* no callback is fine */ }
      sw.node.setDirtyCanvas?.(true, true);
      app.extensionManager?.workflow?.activeWorkflow?.changeTracker?.checkState?.();
    }
    this.showRepaint();
    this.say(on ? "Face repaint is ON." : "Face repaint is OFF - the picture is used as painted.");
  }

  say(text, err) {
    const m = this.q(".msg");
    m.textContent = text || "";
    m.classList.toggle("err", !!err);
  }

  showPrefix() {
    const pre = prefixFor(faceMode());
    this.q(".prefix").textContent = pre || "(STEP 2 off)";
  }

  selected() { return this.q(".list").value; }

  async refresh(keep) {
    this.showPrefix();
    const sel = this.q(".list");
    const want = keep ?? sel.value;
    const d = await jget(`/freedom/pm/presets?scope=${SCOPE}`);
    const names = (d.presets || []).map((p) => p.name);
    sel.innerHTML = `<option value="">-- none --</option>` +
      names.map((n) => `<option value="${n.replace(/"/g, "&quot;")}">${n}</option>`).join("");
    sel.value = names.includes(want) ? want : "";
  }

  async load() {
    const name = this.selected();
    if (!name) return this.say("Pick a preset to load.", true);
    const d = await jget(`/freedom/pm/preset?scope=${SCOPE}&name=${encodeURIComponent(name)}`);
    if (!d.ok) return this.say(d.error || "Could not read it.", true);
    const r = applyValues(this.node, d.data?.values || {});
    this.say(`Loaded ${name}: ${r.changed} dial(s) changed` +
             (r.skipped.length ? `; left alone (wired): ${r.skipped.join(", ")}` : "") + ".");
  }

  async write(name, overwrite) {
    const d = await jpost("/freedom/pm/preset/save",
      { scope: SCOPE, name, overwrite, data: { node: NODE, face_mode: faceMode(), values: capture(this.node) } });
    if (!d.ok) { this.say(d.error || "Could not save.", true); return false; }
    await this.refresh(d.name);
    this.say(`Saved ${d.name} - ${Object.keys(capture(this.node)).length} dials.`);
    return true;
  }

  async save() {
    const name = this.selected();
    if (!name) return this.say("Pick a preset to overwrite, or use Save as.", true);
    await this.write(name, true);
  }

  async saveAs() {
    const r = withPrefix(this.q(".name").value);
    if (r.error) return this.say(r.error, true);
    if (await this.write(r.name, false)) this.q(".name").value = "";
  }

  async rename() {
    const name = this.selected();
    if (!name) return this.say("Pick the preset to rename.", true);
    const r = withPrefix(this.q(".name").value);
    if (r.error) return this.say(r.error, true);
    const d = await jpost("/freedom/pm/preset/rename", { scope: SCOPE, name, new_name: r.name });
    if (!d.ok) return this.say(d.error || "Could not rename.", true);
    this.q(".name").value = "";
    await this.refresh(d.name);
    this.say(`Renamed ${name} to ${d.name}.`);
  }

  async del() {
    const name = this.selected();
    if (!name) return this.say("Pick the preset to delete.", true);
    this.say("");
    this.delAsk.open(`Delete the preset ${name} for good?`, async () => {
      if (this.selected() !== name) return this.say("The menu changed before Confirm - nothing was deleted.", true);
      const d = await jpost("/freedom/pm/preset/delete", { scope: SCOPE, name });
      if (!d.ok) return this.say(d.error || "Could not delete.", true);
      await this.refresh("");
      this.say(`Deleted ${name}.`);
    }, () => this.say("Cancelled - nothing was changed."));
  }

  async reset() {
    const d = await jget(`/freedom/pm/defaults?node=${NODE}`);
    const values = d[NODE] || {};
    if (!Object.keys(values).length) return this.say("Could not read the developer's defaults.", true);
    const r = applyValues(this.node, values);
    this.say(`Reset to the developer's defaults: ${r.changed} dial(s) changed` +
             (r.skipped.length ? `; left alone (wired): ${r.skipped.join(", ")}` : "") + ".");
  }
}

app.registerExtension({
  name: "freedom.facedetailer_presets",
  async nodeCreated(node) {
    if (node.comfyClass !== NODE) return;
    css();
    const p = new Panel(node);
    node.__fdp = p;
    const w = node.addDOMWidget(PANEL, "FREEDOM_FD_PRESETS", p.el,
      { serialize: false, hideOnZoom: false, getMinHeight: () => 150 });
    w.serialize = false;                            // what 1.53.6 actually checks
    node.widgets.splice(node.widgets.indexOf(w), 1);
    node.widgets.unshift(w);                        // at the top of the node
    p.refresh();
  },
  async afterConfigureGraph() {
    for (const n of app.graph?.nodes || []) if (n.__fdp) n.__fdp.refresh();
  },
});
