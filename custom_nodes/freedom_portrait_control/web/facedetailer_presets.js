// web/facedetailer_presets.js
//
// FaceDetailer (face repaint, STEP 11b) - our presets package and a
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
//   - Delete needs a second press ("Press again to delete") - no browser dialogs.
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

function css() {
  if (document.getElementById("freedom-fdp-css")) return;
  const s = document.createElement("style");
  s.id = "freedom-fdp-css";
  s.textContent = `
    .fdp { font: 12px/1.5 sans-serif; color: #ccc; padding: 6px 8px; margin: 0 4px;
           border: 1px solid #555; border-radius: 4px; background: #1c1c1c; }
    .fdp .t { font-weight: bold; color: #cde3ff; margin-bottom: 4px; }
    .fdp .row { display: flex; gap: 6px; align-items: center; margin-bottom: 6px; flex-wrap: wrap; }
    .fdp select, .fdp input { background: #111; color: #eee; border: 1px solid #666; border-radius: 3px;
                              font: 12px sans-serif; padding: 2px 4px; }
    .fdp select { flex: 1; min-width: 120px; }
    .fdp input { flex: 1; min-width: 120px; }
    .fdp button { font: 11px sans-serif; padding: 2px 8px; background: #333; color: #eee;
                  border: 1px solid #666; border-radius: 3px; cursor: pointer; }
    .fdp button:hover { background: #444; }
    .fdp button.danger { border-color: #a55; }
    .fdp .reset { width: 100%; margin-top: 2px; }
    .fdp .prefix { color: #9c9; font-weight: bold; }
    .fdp .msg { color: #bbb; font-size: 11px; min-height: 14px; }
    .fdp .msg.err { color: #f99; }`;
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
      <div class="row"><select class="list"></select>
        <button class="load">Load</button><button class="save">Save</button></div>
      <div class="row"><span class="prefix"></span><input class="name" placeholder="new preset name (prefix added for you)">
        <button class="saveas">Save as</button><button class="rename">Rename</button>
        <button class="delete danger">Delete</button></div>
      <div class="row"><button class="reset">Reset to Developer's Defaults</button></div>
      <div class="msg"></div>`;
    this.q = (s) => this.el.querySelector(s);
    this.q(".load").onclick = () => this.load();
    this.q(".save").onclick = () => this.save();
    this.q(".saveas").onclick = () => this.saveAs();
    this.q(".rename").onclick = () => this.rename();
    this.q(".delete").onclick = () => this.del();
    this.q(".reset").onclick = () => this.reset();
    for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"])
      this.el.addEventListener(ev, (e) => e.stopPropagation());
    this.deleteArmed = null;
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
    if (this.deleteArmed !== name) {
      this.deleteArmed = name;
      this.q(".delete").textContent = "Press again to delete";
      return this.say(`Press Delete again to delete ${name}.`);
    }
    this.deleteArmed = null;
    this.q(".delete").textContent = "Delete";
    const d = await jpost("/freedom/pm/preset/delete", { scope: SCOPE, name });
    if (!d.ok) return this.say(d.error || "Could not delete.", true);
    await this.refresh("");
    this.say(`Deleted ${name}.`);
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
