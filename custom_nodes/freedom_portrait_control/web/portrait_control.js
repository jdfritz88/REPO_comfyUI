// =============================================================================
// FREEDOM SYSTEM - Portrait Control (screen side)
//
// Draws, on the desktop ComfyUI page:
//   - STEP 4b: an In-charge dropdown, a preset list, and the four preset buttons.
//   - Each Portrait Master node: the shared banner, an indicator of who is in charge
//     of it, its own In-charge dropdown, a preset list, and the preset buttons.
//   - Base Character and Face Generator: the conflict banner and an "Active of the
//     pair" dropdown - exactly one of the two is in use.
//   - Prompt Styler: its own on/off dropdown, off by default.
//
// There are no radio buttons any more. Radios had to be drawn as page elements, which
// meant only this PC had them - a phone or a raw API call could not set any of these
// choices. Every choice is now a REAL dropdown on node 4b, so it travels with the
// workflow to any client. The controls below read and write those widgets.
//
// A preset saved on STEP 4b carries more than Portrait Master dials: it also holds
// the RECIPE - the FaceDetailer seed with its after-generate setting, the face
// LoRA and its strength, the LoRA stack, and the prompt text. The KSampler is
// left out on purpose. See "THE RECIPE" further down.
//
// Everything the server must obey is mirrored into STEP 4b's hidden "state" field,
// because ComfyUI sends a node's input values to the server and nothing else.
// =============================================================================
import { app } from "../../scripts/app.js";

const CONTROL_NODE = "FreedomPortraitUserPreset";

// STEP 3 on screen - the Face Shelf, the node that loads her trained face. It gets
// its own preset drawer, separate from Portrait Master's, holding the same payload.
const TRAINED_FACE_NODE = "FreedomFaceShelf";
const TRAINED_FACE_SCOPE = "trained_face";

// Every preset saved from here on says where it was born. Portrait Master's are
// named pm_something, the trained face's tl_something. The prefix goes on at
// "Save as" only: a preset that already exists keeps the name it has, because the
// prefixes start from now. Typing the prefix yourself does not double it.
const prefixFor = (scope) => (scope === TRAINED_FACE_SCOPE ? "tl_" : "pm_");
function withPrefix(scope, name) {
  const p = prefixFor(scope);
  const clean = String(name || "").trim();
  return clean.toLowerCase().startsWith(p) ? clean : p + clean;
}

const MODE_PRESET_WINS = "preset wins - dials locked";
const MODE_PRESET_UNLOCKED = "preset loaded - dials unlocked";
const MODE_IGNORE = "ignore presets - use the dials";

const NODE_MODE_PRESET = "node preset";
const NODE_MODE_PRESET_UNLOCKED = "node preset + unlocked";
const NODE_MODE_IGNORE = "ignore presets";

const NO_PRESET = "-- none --";

// Built-in choices at the bottom of 4b's top preset dropdown (user, 2026-09-29).
// Same names and meaning as Z_PRESETS in __init__.py - the server obeys them for every
// client; this page mirrors them so the screen shows what will happen.
const Z_BLOCK = "z_block all nodes";
const Z_OPEN_BASE = "z_unblock and open all nodes WITH Base Character (Face Generator must be OFF)";
const Z_OPEN_FACE = "z_unblock and open all nodes WITH Face Generator (Base Character must be OFF)";
const Z_PRESETS = [Z_BLOCK, Z_OPEN_BASE, Z_OPEN_FACE];
const Z_ON_OFF = ["PortraitMasterBaseCharacter", "PortraitMasterFaceGenerator",
                  "PortraitMasterSkinDetails", "PortraitMasterStylePose", "PortraitMasterMakeup"];
function zChoice() {                        // the built-in z_ choice in use, or null
  const name = widget(controlNode(), "preset")?.value;
  return Z_PRESETS.includes(name) && controlMode() !== MODE_IGNORE ? name : null;
}
function zWantsOn(z, cls) {
  if (z === Z_BLOCK) return false;
  if (z === Z_OPEN_BASE && cls === "PortraitMasterFaceGenerator") return false;
  if (z === Z_OPEN_FACE && cls === "PortraitMasterBaseCharacter") return false;
  return true;
}

// The per-node choices now live as REAL dropdowns on node 4b, so every client sends
// them. The controls below are ordinary <select> elements that read and write those
// widgets, which is why the phone gets the same choices the PC has.
const STEP_OF = {
  PortraitMasterBaseCharacter: "n4c",
  PortraitMasterFaceGenerator: "n4d",
  PortraitMasterSkinDetails:   "n4e",
  PortraitMasterStylePose:     "n4f",
  PortraitMasterMakeup:        "n4g",
  PortraitMasterPromptStyler:  "n4h",
};
const MIRROR_NAMES = Object.values(STEP_OF)
  .flatMap((st) => [st + "_mode", st + "_preset"])
  .concat(["active_of_pair", "prompt_styler_switch"]);

// read / write a widget on 4b from anywhere
function ctrlWidget(name) { return widget(controlNode(), name); }
function setCtrl(name, value) {
  const w = ctrlWidget(name);
  if (w && value !== undefined && value !== null) { w.value = value; w.callback?.(value); }
}
function makeSelect(choices) {
  const sel = el("select");
  sel.style.cssText = "background:#222;color:#ddd;border:1px solid #555;padding:2px;min-width:200px;";
  for (const [value, label] of choices) sel.append(el("option", { value, textContent: label }));
  return sel;
}

// The six node groups in the workflow. Legacy 2.9.2 is not among them: it is left out
// of the workflow, hidden from the node menu, and covered by no preset or reset.
const PM_CLASSES = [
  "PortraitMasterBaseCharacter",
  "PortraitMasterFaceGenerator",
  "PortraitMasterSkinDetails",
  "PortraitMasterStylePose",
  "PortraitMasterMakeup",
  "PortraitMasterPromptStyler",
];
const PAIR = ["PortraitMasterBaseCharacter", "PortraitMasterFaceGenerator"];
const HOUSEKEEPING = new Set(["seed", "control_after_generate", "load_preset",
                              "save_preset", "save_preset_as", "state",
                              ...Object.values(STEP_OF).flatMap((st) => [st + "_mode", st + "_preset"]),
                              "active_of_pair", "prompt_styler_switch"]);

// The two hints, written as paragraphs and bullet lists (user, 2026-09-30:
// no line breaks inside sentences, only between paragraphs), so the text wraps
// to whatever width the node is. A string is a paragraph; { list: [...] } is a
// bullet list, and an item { text, sub: [...] } has its own sub-list.
const EXPLANATION = [
  "Who is in charge is decided by the preset menus - there is no separate " +
    "In-charge dropdown any more:",
  { list: [
    "4b's menu on a saved preset - 4b is in charge of every node; the preset " +
      "fills the dials you have not changed, and every dial stays unlocked.",
    { text: "4b's menu on 'Use the dials (no 4b preset)' - each node's own menu decides:",
      sub: [
        "'Use the dials (no preset)' - only your dials count; Factory reset works.",
        "a saved preset - it loads unlocked: fills the dials you have not changed.",
      ] },
  ] },
  "Every menu entry has a description beneath the menu. Only a Save button " +
    "changes a stored preset; Save as keeps the old one and makes a new one.",
  "At the bottom of 4b's preset list are three built-in choices that switch " +
    "Portrait Master on or off outright (they cannot be saved over or deleted):",
  { list: [
    "z_block all nodes - every node OFF, greyed and locked.",
    "z_unblock ... WITH Base Character - all ON and unlocked, Face Generator OFF.",
    "z_unblock ... WITH Face Generator - all ON and unlocked, Base Character OFF.",
  ] },
  "A preset saved on 4b also carries the RECIPE: the FaceDetailer seed and its " +
    "after-generate setting, the face LoRA and its strength, every switched-on " +
    "slot of the LoRA stack, and the words in your STEP 7 box. Loading it puts " +
    "all of that back. The KSampler is NOT saved and NOT touched: pinning it is " +
    "what made every batch come back the same, so it is left to the canvas.",
  "New presets saved here are named pm_something. STEP 3 - her trained face - " +
    "has its own drawer, named tl_something, holding exactly the same things.",
];

const CONFLICT = [
  "These two cannot be used together. The developer: \"Face Generator is a " +
    "simplified node of Base Character. You can cascade both of them with Skin " +
    "Details, but don't use Face Generator with Base Character.\"",
  "Use the \"Active of the pair\" dropdown to choose which of the two is in use.",
];

// --------------------------------------------------------------------------- //
// small helpers
// --------------------------------------------------------------------------- //
const api = {
  async list(scope) {
    const r = await fetch(`/freedom/pm/presets?scope=${encodeURIComponent(scope)}`);
    return (await r.json()).presets || [];
  },
  async read(scope, name) {
    const r = await fetch(`/freedom/pm/preset?scope=${encodeURIComponent(scope)}&name=${encodeURIComponent(name)}`);
    return r.ok ? await r.json() : null;
  },
  async save(scope, name, data, overwrite) {
    const r = await fetch("/freedom/pm/preset/save", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope, name, data, overwrite }),
    });
    return await r.json();
  },
  async rename(scope, name, new_name) {
    const r = await fetch("/freedom/pm/preset/rename", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope, name, new_name }),
    });
    return await r.json();
  },
  async remove(scope, name) {
    const r = await fetch("/freedom/pm/preset/delete", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope, name }),
    });
    return await r.json();
  },
  async defaults(node) {
    const r = await fetch(`/freedom/pm/defaults${node ? `?node=${encodeURIComponent(node)}` : ""}`);
    return await r.json();
  },
};

const el = (tag, props = {}, children = []) => {
  const e = Object.assign(document.createElement(tag), props);
  for (const c of children) e.append(c);
  return e;
};

// Builds a hint box from blocks like EXPLANATION: paragraphs and bullet lists
// in the same reading font as the workflow's note boxes.
function hintBox(blocks, colours) {
  const box = el("div");
  box.style.cssText = "font:13px/1.45 system-ui,sans-serif;background:" + colours.bg +
    ";color:" + colours.fg + ";border-left:3px solid " + colours.edge + ";padding:4px 8px;";
  const list = (items) => {
    const ul = el("ul");
    ul.style.cssText = "margin:2px 0 6px 0;padding-left:18px;";
    for (const it of items) {
      const li = el("li", { textContent: typeof it === "string" ? it : it.text });
      li.style.cssText = "margin:1px 0;";
      // a plain string has a built-in .sub() method, so only objects carry a sub-list
      if (typeof it !== "string" && Array.isArray(it.sub)) li.append(list(it.sub));
      ul.append(li);
    }
    return ul;
  };
  for (const b of blocks) {
    if (typeof b === "string") {
      const p = el("p", { textContent: b });
      p.style.cssText = "margin:4px 0;";
      box.append(p);
    } else box.append(list(b.list));
  }
  return box;
}

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
function makeRenamer({ button, field, current, apply, say, blocked, onFinish,
                       armedLabel = "Save new name", allowEmpty = false, requireChange = true }) {
  let armed = null;
  const label = button.textContent;
  const end = (restore) => {
    if (!armed) return;
    const { el: f, before, onKey } = armed;
    f.removeEventListener("keydown", onKey, true);
    if (restore) f.value = before;
    armed = null;
    button.textContent = label;
  };
  const confirm = async () => {
    if (!armed) return;
    const v = String(armed.el.value || "").trim();
    const cur = String(current() || "").trim();
    end(false);
    if (!v) { say("Type a name first."); onFinish?.(true); return; }
    if (requireChange && v === cur) { say("The name was not changed."); onFinish?.(true); return; }
    await apply(v);
    onFinish?.(false);
  };
  const click = async () => {
    if (armed) return confirm();
    const stop = blocked?.();
    if (stop) { say(stop); return; }
    const f = field(); const cur = current();
    if (!f || (!cur && !allowEmpty)) { say("There is nothing here to rename."); return; }
    const before = f.value;
    f.value = cur || (allowEmpty ? f.value : ""); f.focus(); f.select?.(); blinkThree(f);
    const onKey = (e) => {
      if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); confirm(); }
      else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); end(true); say("Cancelled - nothing was changed."); onFinish?.(true); }
    };
    f.addEventListener("keydown", onKey, true);
    armed = { el: f, before, onKey };
    button.textContent = armedLabel;
    say(`Type the new name, then press Enter or ${armedLabel} (Esc cancels).`);
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

const graphNodes = (type) => (app.graph?._nodes || []).filter((n) => n.type === type);
const controlNode = () => graphNodes(CONTROL_NODE)[0] || null;
const widget = (node, name) => (node?.widgets || []).find((w) => w.name === name) || null;

function dialWidgets(node) {
  return (node.widgets || []).filter(
    (w) => !HOUSEKEEPING.has(w.name) && w.type !== "button" && !w.__freedom
  );
}

function readDials(node) {
  const out = {};
  for (const w of dialWidgets(node)) out[w.name] = w.value;
  return out;
}

function writeDials(node, values) {
  let n = 0;
  for (const w of dialWidgets(node)) {
    if (values && Object.prototype.hasOwnProperty.call(values, w.name) && w.value !== values[w.name]) {
      w.value = values[w.name];
      w.callback?.(w.value);
      n++;
    }
  }
  queueRedraw();
  return n;
}

// One redraw per frame at most. Calling node.setDirtyCanvas() from inside a panel refresh -
// once per node, on seven nodes that each carry a DOM panel - re-enters the draw path and
// freezes the page. Measured: with the per-node call the workflow never finished loading;
// without it, 0.48 s. So redraws are queued and coalesced instead.
let redrawQueued = false;
function queueRedraw() {
  if (redrawQueued) return;
  redrawQueued = true;
  requestAnimationFrame(() => { redrawQueued = false; app.graph?.setDirtyCanvas(true, true); });
}

function lockDials(node, locked) {
  for (const w of dialWidgets(node)) w.disabled = !!locked;
  queueRedraw();
}

// --------------------------------------------------------------------------- //
// shared state, mirrored into 4b's hidden "state" field for the server
// --------------------------------------------------------------------------- //
const state = {
  nodes: {},                                   // class -> {mode, preset}
  switches: { start: "base", prompt_styler: false },
};

for (const c of PM_CLASSES) state.nodes[c] = { mode: NODE_MODE_PRESET, preset: NO_PRESET };

function pushState() {
  const c = controlNode();
  if (!c) return;
  for (const cls of Object.keys(state.nodes)) state.nodes[cls].mode = nodeModeFor(state.nodes[cls].preset);
  const w = widget(c, "state");
  if (w) w.value = JSON.stringify(state);
  // keep the real dropdowns in step with the panel, so what the server receives is
  // always what the screen shows - on this PC and on any other client.
  for (const [cls, st] of Object.entries(STEP_OF)) {
    const ns = state.nodes[cls] || {};
    const wm = widget(c, st + "_mode");
    if (wm && ns.mode) wm.value = ns.mode;
    const wp = widget(c, st + "_preset");
    if (wp && ns.preset) wp.value = ns.preset;
  }
  const wpair = widget(c, "active_of_pair");
  if (wpair) wpair.value = state.switches.start === "facegen" ? "4d Face Generator" : "4c Base Character";
  const wst = widget(c, "prompt_styler_switch");
  if (wst) wst.value = state.switches.prompt_styler ? "on" : "off";
}

function pullState() {
  const w = widget(controlNode(), "state");
  if (!w?.value) return;
  try {
    const saved = JSON.parse(w.value);
    if (saved && typeof saved === "object") {
      if (saved.nodes) Object.assign(state.nodes, saved.nodes);
      if (saved.switches) Object.assign(state.switches, saved.switches);
    }
  } catch (_) { /* a broken field is replaced by the next push */ }
}

// "In charge" is gone from the screen (user, 2026-09-29): the ONE preset menu decides.
//   "-- none --" (shown as "Use the dials (no 4b preset)") -> ignore presets, use the dials
//   a saved preset -> loads unlocked;  a z_ choice -> on/off outright (see zChoice)
// Same rule as effective_mode() in __init__.py; the old "mode" widget is hidden and unused.
const controlMode = () => {
  const p = widget(controlNode(), "preset")?.value;
  return (!p || p === NO_PRESET) ? MODE_IGNORE : MODE_PRESET_UNLOCKED;
};
const USE_DIALS_LABEL = "Use the dials (no 4b preset)";
const NODE_USE_DIALS_LABEL = "Use the dials (no preset)";
// 4c-4h the same way (user, 2026-09-29, Q66 = 1): each node's own preset menu decides.
//   "-- none --" -> ignore presets;  a preset -> loads unlocked.  Same rule as
//   effective_node_mode() in __init__.py; the "<step>_mode" dropdowns on 4b are hidden.
const nodeModeFor = (preset) => (!preset || preset === NO_PRESET) ? NODE_MODE_IGNORE : NODE_MODE_PRESET_UNLOCKED;
const NEEDS_DESCRIPTION = "needs description";

// Who is in charge of one node group, and therefore what is locked or greyed.
function statusFor(cls) {
  const m = controlMode();
  const z = zChoice();
  if (z === Z_BLOCK) return { inCharge: "4b: z_block all nodes - this node is OFF", dialsLocked: true, nodeChoice: false, buttons: "none", reset: false, blocked: true };
  if (z) return { inCharge: "4b: all nodes open" + (zWantsOn(z, cls) ? " - use the dials" : " - this node is OFF"), dialsLocked: !zWantsOn(z, cls), nodeChoice: false, buttons: "none", reset: false, blocked: !zWantsOn(z, cls) };
  if (m === MODE_PRESET_WINS) return { inCharge: "4b preset", dialsLocked: true, nodeChoice: false, buttons: "none", reset: false };
  if (m === MODE_PRESET_UNLOCKED) return { inCharge: "4b preset, dials unlocked", dialsLocked: false, nodeChoice: false, buttons: "none", reset: false };
  const nm = nodeModeFor(state.nodes[cls]?.preset);
  if (nm === NODE_MODE_PRESET_UNLOCKED) return { inCharge: "this node's preset - it loads unlocked", dialsLocked: false, nodeChoice: true, buttons: "all", reset: false };
  return { inCharge: "this node's dials (no preset)", dialsLocked: false, nodeChoice: true, buttons: "all", reset: true };
}

const panels = [];                             // every panel refreshes when anything changes
function refreshAll() {
  pushState();
  for (const p of panels) { try { p.refresh(); } catch (e) { console.error("[freedom pm]", e); } }
}

// Applying a 4b preset to what the screen shows, so the dials always show what is used.
// --------------------------------------------------------------------------- //
// THE RECIPE
// --------------------------------------------------------------------------- //
// A preset used to hold Portrait Master dials and nothing else. Seeds were
// deliberately left out - `seed` and `control_after_generate` are in HOUSEKEEPING
// above, so writeDials() skips them, and it still does. The recipe below is
// gathered and written SEPARATELY, on purpose, so that turning a dial can never
// quietly move a seed.
//
// What a recipe holds, and why each piece:
//   - EVERY FaceDetailer (face repaint) dial, by name - seed and its
//     after-generate setting included (user, 2026-09-26; before that only the
//     seed was kept). A dial wired to another node (the wildcard, fed from STEP 3)
//     is recorded but never overwritten on load - the wire wins.
//
//     The KSampler is deliberately NOT in here (user, 2026-09-23). It used to be,
//     and it is what made every batch come back the same: one seed makes the
//     noise for a whole batch, so a pinned KSampler gives you the same four
//     pictures in the same order, run after run. Two batches were identical
//     because of it. A preset now leaves the KSampler alone entirely - it keeps
//     whatever seed and after-generate setting the canvas already has, and
//     loading a preset can never re-pin it.
//   - the face LoRA: its strength, which face is picked, and the trigger weight.
//     A strength without the file it applies to means nothing.
//   - the Selected Face LoRA Stack: each of its 3 rows' ON/OFF and
//     strength (user, 2026-09-26). Together with the shelf that is her whole face
//     strength.
//   - the general LoRA stack (STEP 6): all 4 slots, file and strength. (It never
//     applies face LoRAs; the old "three passes" note that stood here was wrong -
//     see logs/two_lora_stacks_v08_2026-09-25.md.)
//   - the words in STEP 7: the physical box and the everything-else box of
//     FreedomPromptParts (v07+). Older workflows with a single prompt box keep
//     using it. Until 2026-09-26 recipes found no prompt in v07/v08 at all,
//     because they only looked for the old prompt nodes.
//
// Presets saved before this existed simply have no recipe in them; they load as
// they always did.
const RECIPE_DETAILER = "FaceDetailer";
const RECIPE_SHELF = "FreedomFaceShelf";
const RECIPE_STACK = "FreedomLoraStack";
const RECIPE_FACE_STACK = "FreedomSelectedFaceLoraStack";
const RECIPE_PARTS = "FreedomPromptParts";
const FACE_STACK_ROWS = 3;
const PARTS_FIELDS = ["physical", "everything_else"];

// A dial whose input is wired to another node: its value comes from the wire.
function recipeWired(node, name) {
  const inp = (node.inputs || []).find((i) => i.name === name || i.widget?.name === name);
  return !!(inp && inp.link != null);
}

// Every real setting on a node, by name - DOM panels and labels excluded.
function allDials(node) {
  const out = {};
  for (const w of node.widgets || []) {
    if (w.serialize === false || w.options?.serialize === false || w.type === "button") continue;
    out[w.name] = w.value;
  }
  return out;
}

// Put a text value into a widget and into its on-screen text box, if it has one.
function setTextValue(node, name, value) {
  const n = setWidgetValue(node, name, value);
  const w = widget(node, name);
  const elx = w && (w.element || w.inputEl || w.domElement);
  const ta = elx && (elx.tagName === "TEXTAREA" ? elx : elx.querySelector?.("textarea"));
  if (ta) ta.value = value;
  return n;
}
// The general LoRA stack has 4 slots since 2026-09-25 (was 12). A recipe saved
// before then may hold 12; applyRecipe skips slots the node no longer has.
const STACK_SLOTS = 4;

// Write one widget directly. writeDials() cannot be used here: it filters to
// Portrait Master dials and skips everything in HOUSEKEEPING, seeds included.
function setWidgetValue(node, name, value) {
  const w = widget(node, name);
  if (!w || value === undefined || value === null || w.value === value) return 0;
  w.value = value;
  w.callback?.(value);
  return 1;
}

// Your prompt box, found by following the wire rather than by node id - ids do
// not match the STEP numbers on screen.
function recipePromptBox() {
  const graph = app.graph;
  if (!graph) return null;
  for (const node of graph._nodes || []) {
    if (node.type !== "StringConcatenate") continue;
    const slot = (node.inputs || []).findIndex((i) => i.name === "string_b");
    if (slot < 0) continue;
    let origin = null;
    try { origin = node.getInputNode?.(slot); } catch (e) { origin = null; }
    if (origin) return origin;
  }
  return (graph._nodes || []).find((n) => n.type === "PrimitiveStringMultiline") || null;
}

function gatherRecipe() {
  const recipe = {};
  // No KSampler here on purpose - see THE RECIPE above.
  const detailer = graphNodes(RECIPE_DETAILER)[0];
  if (detailer) recipe.facedetailer = allDials(detailer);
  const shelf = graphNodes(RECIPE_SHELF)[0];
  if (shelf) {
    recipe.face_shelf = {
      strength: widget(shelf, "strength")?.value,
      selected: widget(shelf, "selected")?.value,
      enabled: widget(shelf, "enabled")?.value,
      trigger_weight: widget(shelf, "trigger_weight")?.value,
    };
  }
  const stack = graphNodes(RECIPE_STACK)[0];
  if (stack) {
    recipe.lora_stack = [];
    for (let i = 1; i <= STACK_SLOTS; i++) {
      recipe.lora_stack.push({
        enabled: widget(stack, `enabled_${i}`)?.value,
        lora: widget(stack, `lora_${i}`)?.value,
        strength: widget(stack, `strength_${i}`)?.value,
      });
    }
  }
  const fstack = graphNodes(RECIPE_FACE_STACK)[0];
  if (fstack) {
    recipe.face_stack = [];
    for (let i = 1; i <= FACE_STACK_ROWS; i++) {
      recipe.face_stack.push({
        enabled: widget(fstack, `enabled_${i}`)?.value,
        strength: widget(fstack, `strength_${i}`)?.value,
      });
    }
  }
  const parts = graphNodes(RECIPE_PARTS)[0];
  if (parts) {
    recipe.prompt_parts = {};
    for (const f of PARTS_FIELDS) recipe.prompt_parts[f] = widget(parts, f)?.value;
  } else {
    const box = recipePromptBox();
    if (box) recipe.prompt = widget(box, "value")?.value;
  }
  return recipe;
}

function applyRecipe(recipe) {
  if (!recipe) return 0;
  let n = 0;
  // recipe.ksampler is ignored even when an older preset still carries one, so a
  // preset saved before 2026-09-23 can never re-pin the KSampler seed.
  const detailer = graphNodes(RECIPE_DETAILER)[0];
  if (detailer && recipe.facedetailer) {
    // older recipes hold only seed + control_after_generate; newer ones every dial
    for (const [k, v] of Object.entries(recipe.facedetailer)) {
      if (recipeWired(detailer, k)) continue;
      n += setWidgetValue(detailer, k, v);
    }
  }
  const shelf = graphNodes(RECIPE_SHELF)[0];
  if (shelf && recipe.face_shelf) {
    for (const k of ["strength", "selected", "enabled", "trigger_weight"]) {
      n += setWidgetValue(shelf, k, recipe.face_shelf[k]);
    }
  }
  const stack = graphNodes(RECIPE_STACK)[0];
  if (stack && Array.isArray(recipe.lora_stack)) {
    recipe.lora_stack.forEach((slot, idx) => {
      const i = idx + 1;
      n += setWidgetValue(stack, `enabled_${i}`, slot?.enabled);
      n += setWidgetValue(stack, `lora_${i}`, slot?.lora);
      n += setWidgetValue(stack, `strength_${i}`, slot?.strength);
    });
  }
  const fstack = graphNodes(RECIPE_FACE_STACK)[0];
  if (fstack && Array.isArray(recipe.face_stack)) {
    recipe.face_stack.forEach((row, idx) => {
      const i = idx + 1;
      n += setWidgetValue(fstack, `enabled_${i}`, row?.enabled);
      n += setWidgetValue(fstack, `strength_${i}`, row?.strength);
    });
  }
  const parts = graphNodes(RECIPE_PARTS)[0];
  if (parts && recipe.prompt_parts) {
    for (const f of PARTS_FIELDS)
      if (typeof recipe.prompt_parts[f] === "string") n += setTextValue(parts, f, recipe.prompt_parts[f]);
  }
  const box = parts ? null : recipePromptBox();
  if (box && typeof recipe.prompt === "string") {
    n += setWidgetValue(box, "value", recipe.prompt);
    const w = widget(box, "value");
    const elx = w && (w.element || w.inputEl || w.domElement);
    const ta = elx && (elx.tagName === "TEXTAREA" ? elx : elx.querySelector?.("textarea"));
    if (ta) ta.value = recipe.prompt;
  }
  queueRedraw();
  return n;
}

// Both drawers store and restore exactly the same thing: every Portrait Master
// dial, 4b's switches, and the recipe.
function gatherEverything() {
  const nodes = {};
  for (const c of PM_CLASSES) {
    const n = graphNodes(c)[0];
    if (n) nodes[c] = readDials(n);
  }
  return { nodes, switches: { ...state.switches }, recipe: gatherRecipe() };
}

function applyEverything(data) {
  if (!data) return 0;
  let n = 0;
  if (data.switches) Object.assign(state.switches, data.switches);
  for (const cls of PM_CLASSES) {
    const values = data.nodes?.[cls];
    if (!values) continue;
    for (const node of graphNodes(cls)) n += writeDials(node, values);
  }
  n += applyRecipe(data.recipe);
  refreshAll();
  return n;
}

// --------------------------------------------------------------------------- //
// STEP 3 - her trained face - its own preset drawer
// --------------------------------------------------------------------------- //
function buildTrainedFacePanel(node) {
  const scope = TRAINED_FACE_SCOPE;
  const root = el("div", { className: "freedom-tf" });
  root.style.cssText =
    "font:13px system-ui,sans-serif;display:flex;flex-direction:column;gap:5px;" +
    "padding:7px;color:#ddd;background:#1c1c1c;border:1px solid #444;border-radius:6px;";
  for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"]) {
    root.addEventListener(ev, (e) => e.stopPropagation());
  }

  const heading = el("div", { textContent: "HER RECIPES - saved settings for this face" });
  heading.style.cssText = "font-weight:700;color:#cde3ff;font-size:11px;letter-spacing:.3px;";
  const note = el("div", {
    textContent: "A recipe here holds every FaceDetailer (face repaint) dial, her Face " +
                 "Shelf (which face, strength, on/off, trigger weight), the 3 passes of " +
                 "the Face Lora Stack, the 4 rows of the general LoRA stack, the words in STEP 7's " +
                 "physical and everything-else boxes, and every Portrait Master dial. " +
                 "Loading one puts all of it back. The KSampler seed is left alone, so " +
                 "loading a recipe never stops your batches varying.",
  });
  note.style.cssText = "color:#9a9a9a;font-size:10.5px;line-height:1.35;";

  const select = el("select");
  select.style.cssText = "background:#222;color:#ddd;border:1px solid #555;padding:2px;";
  const nameBox = el("input", { type: "text", placeholder: "new recipe name (tl_ is added for you)" });
  nameBox.style.cssText = "background:#222;color:#ddd;border:1px solid #555;padding:2px;";
  const row = el("div");
  row.style.cssText = "display:flex;flex-wrap:wrap;gap:4px;";
  const say = el("div");
  say.style.cssText = "color:#9cc4ff;min-height:13px;font-size:11px;";
  const tell = (t) => { say.textContent = t; };
  const nonePicked = () => !select.value || select.value === NO_PRESET;
  const letGo = (cancelled) => {
    if (cancelled && select.__holdPick && select.__beforePick !== undefined) { select.value = select.__beforePick; refresh(); }
    select.__holdPick = false;
  };

  const mk = (label, fn) => {
    const b = el("button", { textContent: label });
    b.style.cssText = "background:#2b2b2b;color:#ddd;border:1px solid #555;border-radius:4px;" +
                      "padding:3px 9px;cursor:pointer;font-size:11.5px;";
    b.onclick = fn;
    row.append(b);
    return b;
  };

  const btnSave = mk("Save", async () => {
    const name = select.value;
    if (!name || name === NO_PRESET) {
      needPick(select, tell, "Pick the recipe to save over.",
        () => tell(`Now press Save to save the current settings over '${select.value}'.`));
      return;
    }
    const res = await api.save(scope, name, gatherEverything(), true);
    say.textContent = res.ok ? `Saved '${name}'.` : res.error;
    letGo();
    await refreshLists();
  });

  const btnSaveAs = mk("Save as", () => recipeSaveAs.click());
  const recipeSaveAs = makeRenamer({
    button: btnSaveAs, field: () => nameBox, armedLabel: "Save as new", allowEmpty: true, requireChange: false,
    current: () => (select.value && select.value !== NO_PRESET) ? select.value : "",
    say: (t) => { say.textContent = t; },
    apply: async (newText) => { nameBox.value = newText; await saveRecipeAs(); },
  });
  const saveRecipeAs = async () => {
    if (!nameBox.value.trim()) { say.textContent = "Type a name first."; return; }
    const name = withPrefix(scope, nameBox.value);
    const res = await api.save(scope, name, gatherEverything(), false);
    say.textContent = res.ok ? `Saved '${name}'.` : res.error;
    if (res.ok) {
      nameBox.value = "";
      await refreshLists();
      select.value = name;
      refresh();
    }
  };

  const btnRename = mk("Rename", () => nonePicked()
    ? needPick(select, tell, "Pick the recipe to rename.", () => recipeRenamer.click())
    : recipeRenamer.click());
  const recipeRenamer = makeRenamer({
    button: btnRename, field: () => nameBox, onFinish: letGo,
    current: () => (select.value && select.value !== NO_PRESET) ? select.value : "",
    say: (t) => { say.textContent = t; },
    apply: async (newText) => { nameBox.value = newText; await renameRecipe(); },
  });
  const renameRecipe = async () => {
    const name = select.value;
    if (!name || name === NO_PRESET) { say.textContent = "Pick a recipe to rename."; return; }
    if (!nameBox.value.trim()) { say.textContent = "Type the new name in the name box first."; return; }
    const newName = withPrefix(scope, nameBox.value);
    const res = await api.rename(scope, name, newName);
    say.textContent = res.ok ? `Renamed '${name}' to '${newName}'.` : res.error;
    if (res.ok) {
      nameBox.value = "";
      await refreshLists();
      select.value = newName;
      refresh();
    }
  };

  const btnDelete = mk("Delete", async () => {
    const name = select.value;
    if (!name || name === NO_PRESET) {
      needPick(select, tell, "Pick the recipe to delete.",
        () => tell(`Now press Delete to delete '${select.value}'.`));
      return;
    }
    const res = await api.remove(scope, name);
    say.textContent = res.ok ? `Deleted '${name}'.` : res.error;
    letGo();
    await refreshLists();
  });

  select.onchange = async () => {
    // picked because a button asked for it: only choose - load nothing
    if (select.__pickOnly) { select.__pickOnly = false; refresh(); return; }
    const name = select.value;
    refresh();
    if (!name || name === NO_PRESET) { say.textContent = ""; return; }
    const found = await api.read(scope, name);
    if (!found?.data) { say.textContent = `Could not read '${name}'.`; return; }
    const changed = applyEverything(found.data);
    say.textContent = `Loaded '${name}' - ${changed} setting${changed === 1 ? "" : "s"} put back.`;
  };

  function refresh() {
    // never switched off - a click shows what it needs first (user, 2026-09-30)
    btnSave.disabled = false;
    btnRename.disabled = false;
    btnDelete.disabled = false;
  }

  async function refreshLists() {
    let presets = [];
    try { presets = await api.list(scope); } catch (e) { presets = []; }
    const chosen = select.value;
    select.replaceChildren(el("option", { value: NO_PRESET, textContent: NO_PRESET }));
    for (const p of presets) select.append(el("option", { value: p.name, textContent: p.name }));
    select.value = presets.some((p) => p.name === chosen) ? chosen : NO_PRESET;
    refresh();
  }

  root.append(heading, note, select, nameBox, row, say);
  node.addDOMWidget("freedom_tf_presets", "div", root, { serialize: false, hideOnZoom: false });

  const panel = { node, cls: TRAINED_FACE_NODE, refresh, refreshLists };
  panels.push(panel);
  refreshLists();
  return panel;
}

async function applyControlPreset() {
  const c = controlNode();
  const name = widget(c, "preset")?.value;
  const m = controlMode();
  if (!c || !name || name === NO_PRESET || m === MODE_IGNORE) return;
  if (Z_PRESETS.includes(name)) {                 // built-in: on/off only, the dials stay as they are
    for (const cls of Z_ON_OFF) for (const node of graphNodes(cls)) {
      const w = widget(node, "active");
      if (w && w.value !== zWantsOn(name, cls)) { w.value = zWantsOn(name, cls); w.callback?.(w.value); }
    }
    if (name === Z_OPEN_BASE) state.switches.start = "base";
    if (name === Z_OPEN_FACE) state.switches.start = "facegen";
    refreshAll();
    return;
  }
  const found = await api.read("user", name);
  if (!found?.data) return;
  if (found.data.switches) Object.assign(state.switches, found.data.switches);
  for (const cls of PM_CLASSES) {
    const values = found.data.nodes?.[cls];
    if (!values) continue;
    for (const node of graphNodes(cls)) {
      if (m === MODE_PRESET_WINS) writeDials(node, values);
      else {
        const defs = (await api.defaults(cls))[cls] || {};
        const fill = {};
        for (const [k, v] of Object.entries(values)) {
          const w = widget(node, k);
          if (w && w.value === defs[k]) fill[k] = v;
        }
        writeDials(node, fill);
      }
    }
  }
  applyRecipe(found.data.recipe);
  refreshAll();
}

// --------------------------------------------------------------------------- //
// the panel drawn on every node
// --------------------------------------------------------------------------- //
function buildPanel(node, cls) {
  const isControl = cls === CONTROL_NODE;
  const scope = isControl ? "user" : cls;
  const root = el("div", { className: "freedom-pm" });
  root.style.cssText = "font:13px system-ui,sans-serif;display:flex;flex-direction:column;gap:6px;padding:6px;color:#ddd;";

  const banner = hintBox(
    isControl ? ["STEP 4b decides who is in charge. One choice only.", ...EXPLANATION] : EXPLANATION,
    { bg: "#1c1c1c", fg: "#bbb", edge: "#666" });
  root.append(banner);

  let conflictBanner = null, pairSelect = null;
  if (PAIR.includes(cls)) {
    conflictBanner = hintBox(CONFLICT, { bg: "#2a2113", fg: "#f0c674", edge: "#f0c674" });
    root.append(conflictBanner);

    const wrap = el("div");
    wrap.style.cssText = "display:flex;gap:6px;align-items:center;";
    pairSelect = makeSelect([["4c Base Character", "Use 4c Base Character"],
                             ["4d Face Generator", "Use 4d Face Generator"]]);
    pairSelect.addEventListener("change", () => {
      state.switches.start = pairSelect.value.startsWith("4c") ? "base" : "facegen";
      setCtrl("active_of_pair", pairSelect.value);
      refreshAll();
    });
    wrap.append(el("span", { textContent: "Active of the pair:" }), pairSelect);
    root.append(wrap);
  }

  let stylerSelect = null;
  if (cls === "PortraitMasterPromptStyler") {
    const wrap = el("div");
    wrap.style.cssText = "display:flex;gap:12px;align-items:center;";
    stylerSelect = makeSelect([["off", "Prompt Styler OFF"], ["on", "Prompt Styler ON"]]);
    stylerSelect.addEventListener("change", () => {
      state.switches.prompt_styler = stylerSelect.value === "on";
      setCtrl("prompt_styler_switch", stylerSelect.value);
      refreshAll();
    });
    wrap.append(el("span", { textContent: "Prompt Styler:" }), stylerSelect);
    root.append(wrap);
  }

  const indicator = el("div");
  indicator.style.cssText = "font-weight:600;color:#9ecbff;";
  root.append(indicator);

  const arrow = el("div", { textContent: "↓" });
  arrow.style.cssText = "text-align:center;color:#888;font-size:15px;line-height:1;";
  root.append(arrow);

  // who is in charge - a dropdown, not radio buttons. On 4b it drives 4b's own
  // "mode" widget; on a Portrait Master node it drives that node's "<step>_mode"
  // dropdown over on 4b. Either way the value is a real node setting, so the phone
  // and a raw API call send it exactly as the PC does.
  const choices = isControl
    ? [[MODE_PRESET_WINS, "Use the preset (dials locked)"],
       [MODE_PRESET_UNLOCKED, "Use the preset, unlock the dials"],
       [MODE_IGNORE, "Ignore the presets, use the dials"]]
    : [[NODE_MODE_PRESET, "Use this node's preset"],
       [NODE_MODE_PRESET_UNLOCKED, "Load the preset, unlock the dials"],
       [NODE_MODE_IGNORE, "Ignore the presets, unlock the dials"]];
  const modeWrap = el("div");
  modeWrap.style.cssText = "display:flex;gap:6px;align-items:center;";
  const modeSelect = makeSelect(choices);
  modeSelect.addEventListener("change", async () => {
    const value = modeSelect.value;
    if (isControl) {
      const w = widget(node, "mode");
      if (w) { w.value = value; w.callback?.(value); }
      await applyControlPreset();
    } else {
      state.nodes[cls].mode = value;
      setCtrl(STEP_OF[cls] + "_mode", value);
    }
    refreshAll();
  });
  modeWrap.append(el("span", { textContent: "In charge:" }), modeSelect);
  root.append(modeWrap);
  modeWrap.style.display = "none";   // 4b and 4c-4h: the preset menu below decides (Q64/Q66)

  // preset row
  const row = el("div");
  row.style.cssText = "display:flex;gap:6px;align-items:center;flex-wrap:wrap;";
  const select = el("select");
  select.style.cssText = "flex:1;min-width:140px;background:#222;color:#ddd;border:1px solid #555;padding:2px;";
  select.addEventListener("change", async () => {
    // picked because a button asked for it: only choose - load nothing
    if (select.__pickOnly) { select.__pickOnly = false; await loadDescription(); return; }
    if (isControl) {
      const w = widget(node, "preset");
      if (w) { w.value = select.value; w.callback?.(select.value); }
      await applyControlPreset();
      await loadDescription();
    } else {
      state.nodes[cls].preset = select.value;
      state.nodes[cls].mode = nodeModeFor(select.value);
      setCtrl(STEP_OF[cls] + "_mode", state.nodes[cls].mode);
      const found = select.value !== NO_PRESET ? await api.read(scope, select.value) : null;
      if (found?.data) writeDials(node, found.data);
      await loadDescription();
    }
    refreshAll();
  });
  row.append(select);
  const nameBox = el("input", { type: "text", placeholder: "new preset name" });
  nameBox.style.cssText = "width:150px;background:#222;color:#ddd;border:1px solid #555;padding:2px;";
  row.append(nameBox);
  root.append(row);

  // A description for every menu entry, beneath the menu (user, 2026-09-29: 4b, then
  // 4c-4h with Q66 = 1).
  let descBox = null, descEdited = false;
  const devNames = new Set();                  // Portrait Master's own presets (read-only)
  {
    const lab = el("div", { textContent: "Description of the chosen entry:" });
    lab.style.cssText = "color:#bbb;";
    descBox = el("textarea");
    descBox.readOnly = true;
    descBox.style.cssText = "width:100%;box-sizing:border-box;min-height:70px;background:#181818;color:#ccc;border:1px solid #555;padding:4px;font:13px system-ui,sans-serif;resize:vertical;";
    root.append(lab, descBox);
  }
  async function loadDescription() {
    if (!descBox) return;
    descEdited = false; descBox.readOnly = true; descBox.style.color = "#ccc";
    try {
      const r = await fetch(`/freedom/pm/description?scope=${encodeURIComponent(scope)}&name=${encodeURIComponent(select.value)}`);
      const d = await r.json();
      descBox.value = d.ok ? d.description : NEEDS_DESCRIPTION;
    } catch (_) { descBox.value = NEEDS_DESCRIPTION; }
  }
  const descValue = () => (descBox && descBox.value.trim()) || NEEDS_DESCRIPTION;

  const buttonRow = el("div");
  buttonRow.style.cssText = "display:flex;gap:6px;flex-wrap:wrap;";
  const mkButton = (label, fn) => {
    const b = el("button", { textContent: label });
    b.style.cssText = "background:#333;color:#ddd;border:1px solid #666;padding:3px 8px;cursor:pointer;";
    b.addEventListener("click", async (e) => { e.preventDefault(); await fn(); });
    buttonRow.append(b);
    return b;
  };

  const say = el("div");
  say.style.cssText = "color:#9c9;min-height:14px;";
  const tell = (t) => { say.textContent = t; };
  const letGo = () => { select.__holdPick = false; refreshAll(); };
  // While 4b's own preset is in charge, this box's presets are locked. Only the field a
  // button works on may blink (user, 2026-09-30): this box's own menu blinks, and the
  // message says why it is locked. Nothing in another box blinks.
  const lockedBy4b = () => !isControl && statusFor(cls).buttons !== "all";
  const pointAt4b = () => {
    blinkThree(select);
    tell("Locked: 4b's menu is in charge of this box right now. Set 4b's menu to " +
         "'Use the dials (no 4b preset)' to use this box's own presets.");
  };

  const gather = () => (isControl ? { ...gatherEverything(), description: descValue() }
                                  : { ...readDials(node), description: descValue() });

  const builtIn = () => isControl && Z_PRESETS.includes(select.value);
  const builtInEntry = () => select.value === NO_PRESET
    || (isControl ? Z_PRESETS.includes(select.value) : devNames.has(select.value));
  const btnDesc = mkButton("Edit description", async () => {
    if (lockedBy4b()) {                      // its own field is the description box
      blinkThree(descBox);
      return tell("Locked: 4b's menu is in charge of this box right now, so its description cannot be edited here.");
    }
    descBox.readOnly = false; descBox.style.color = "#eee"; descEdited = true;
    if (descBox.value === NEEDS_DESCRIPTION) descBox.value = "";
    descBox.focus();
    blinkThree(descBox);                                   // the box to type in blinks
    descBox.style.outline = "3px solid #ffd479"; descBox.style.outlineOffset = "1px";
    say.textContent = "Type the description, then press Save (or Save as for a new preset).";
  });
  const btnSave = mkButton("Save", async () => {
    if (lockedBy4b()) return pointAt4b();
    const name = select.value;
    if (builtInEntry()) {                      // built-in entry: only its description is saved
      const r = await fetch("/freedom/pm/description", { method: "POST", headers: { "Content-Type": "application/json" },
                                                           body: JSON.stringify({ scope, name, description: descValue() }) });
      const d = await r.json();
      say.textContent = d.ok ? "Saved the description. (This entry is built in, so only its description can be saved.)" : d.error;
      await loadDescription();
      return;
    }
    if (!name || name === NO_PRESET) {
      needPick(select, tell, "Pick the preset to save over.",
        () => tell(`Now press Save to save over '${select.value}'.`));
      return;
    }
    const res = await api.save(scope, name, gather(), true);
    select.__holdPick = false;
    say.textContent = res.ok ? `Saved '${name}'.` : res.error;
    await refreshLists();
    await loadDescription();
  });
  const btnSaveAs = mkButton("Save as", () => lockedBy4b() ? pointAt4b() : presetSaveAs.click());
  const presetSaveAs = makeRenamer({
    button: btnSaveAs, field: () => nameBox, armedLabel: "Save as new", allowEmpty: true, requireChange: false,
    current: () => (select.value && select.value !== NO_PRESET) ? select.value : "",
    say: (t) => { say.textContent = t; },
    apply: async (newText) => { nameBox.value = newText; await savePresetAs(); },
  });
  const savePresetAs = async () => {
    if (!nameBox.value.trim()) { say.textContent = "Type a name first."; return; }
    const name = withPrefix(scope, nameBox.value);
    const data = gather();
    // From a built-in entry, its own description is not copied unless you edited it.
    if (builtInEntry() && !descEdited) data.description = NEEDS_DESCRIPTION;
    const res = await api.save(scope, name, data, false);
    say.textContent = res.ok ? `Saved '${name}'.` : res.error;
    if (res.ok) { nameBox.value = ""; await refreshLists(); select.value = name; select.dispatchEvent(new Event("change")); }
  };
  const btnRename = mkButton("Rename", () => lockedBy4b() ? pointAt4b()
    : (builtInEntry()
      ? needPick(select, tell, select.value === NO_PRESET ? "Pick the preset to rename."
          : "That entry is built in and cannot be renamed - pick one of your own presets.",
          () => presetRenamer.click())
      : presetRenamer.click()));
  const presetRenamer = makeRenamer({
    button: btnRename, field: () => nameBox, onFinish: letGo,
    current: () => (select.value && select.value !== NO_PRESET) ? select.value : "",
    blocked: () => builtInEntry() ? "Built-in entries cannot be renamed."
      : ((!select.value || select.value === NO_PRESET) ? "Pick a preset to rename." : null),
    say: (t) => { say.textContent = t; },
    apply: async (newText) => { nameBox.value = newText; await renamePreset(); },
  });
  const renamePreset = async () => {
    const name = select.value;
    if (builtInEntry()) { say.textContent = "Built-in entries cannot be renamed."; return; }
    if (!name || name === NO_PRESET) { say.textContent = "Pick a preset to rename."; return; }
    if (!nameBox.value.trim()) { say.textContent = "Type the new name in the name box first."; return; }
    const newName = withPrefix(scope, nameBox.value);
    const res = await api.rename(scope, name, newName);
    say.textContent = res.ok ? `Renamed '${name}' to '${newName}'.` : res.error;
    if (!res.ok) return;
    nameBox.value = "";
    // Anything that was pointing at the old name follows it to the new one.
    if (isControl) {
      const w = widget(node, "preset");
      if (w && w.value === name) { w.value = newName; w.callback?.(newName); }
    } else if (state.nodes[cls]?.preset === name) {
      state.nodes[cls].preset = newName;
      setCtrl(STEP_OF[cls] + "_preset", newName);
    }
    await refreshLists();
    select.value = newName;
    refreshAll();
  };
  const btnDelete = mkButton("Delete", async () => {
    if (lockedBy4b()) return pointAt4b();
    const name = select.value;
    if (builtInEntry()) {
      needPick(select, tell, name === NO_PRESET ? "Pick the preset to delete."
          : "That entry is built in and cannot be deleted - pick one of your own presets.",
        () => tell(builtInEntry() ? "That one is built in too - pick one of your own presets."
                                  : `Now press Delete to delete '${select.value}'.`));
      return;
    }
    const res = await api.remove(scope, name);
    select.__holdPick = false;
    say.textContent = res.ok ? `Deleted '${name}'.` : res.error;
    await refreshLists();
  });
  const btnReset = mkButton(isControl ? "Factory reset ALL" : "Factory reset", async () => {
    // Factory reset works on dials, not on a menu - so it only says why it cannot run.
    if (isControl && controlMode() !== MODE_IGNORE)
      return tell("Factory reset ALL only works with no 4b preset in use - set this menu to 'Use the dials (no 4b preset)' first.");
    if (!isControl && !statusFor(cls).reset)
      return tell("Factory reset is locked while 4b's menu is in charge of this box.");
    const defs = await api.defaults(isControl ? null : cls);
    let n = 0;
    for (const c of isControl ? PM_CLASSES : [cls]) {
      const values = defs[c];
      if (!values) continue;
      for (const target of graphNodes(c)) n += writeDials(target, values);
    }
    say.textContent = `Factory reset: ${n} dial(s) back to the developer's values.`;
    refreshAll();
  });
  root.append(buttonRow, say);

  async function refreshLists() {
    const presets = await api.list(scope);
    const current = select.value;
    select.replaceChildren();
    select.append(el("option", { value: NO_PRESET, textContent: isControl ? USE_DIALS_LABEL : NODE_USE_DIALS_LABEL }));
    devNames.clear();
    for (const p of presets) {
      if (isControl && Z_PRESETS.includes(p.name)) continue;
      if (p.source === "developer") devNames.add(p.name);
      select.append(el("option", {
        value: p.name,
        textContent: p.source === "developer" ? `${p.name}  (Portrait Master)` : p.name,
      }));
    }
    if (isControl) for (const z of Z_PRESETS) select.append(el("option", { value: z, textContent: z }));
    const wanted = isControl ? widget(node, "preset")?.value : state.nodes[cls]?.preset;
    select.value = [...select.options].some((o) => o.value === wanted) ? wanted
                 : ([...select.options].some((o) => o.value === current) ? current : NO_PRESET);
    await loadDescription();
  }

  function refresh() {
    if (isControl) {
      const m = controlMode();
      const z = zChoice();
      indicator.textContent = z ? `Using: ${z}`
        : (m === MODE_IGNORE ? "Using: your dials (no 4b preset)" : "Using: a saved preset - it loads unlocked");
      const ignoring = m === MODE_IGNORE;
      select.disabled = false;                 // the menu is always usable - it is the only control
      // never switched off - a click shows what it needs first (user, 2026-09-30)
      btnSave.disabled = false; btnSaveAs.disabled = false;
      btnRename.disabled = false; btnDelete.disabled = false; btnReset.disabled = false;
      const w = widget(node, "preset");
      if (w && select.value !== w.value && !select.__holdPick) { select.value = w.value; loadDescription(); }
    } else {
      const s = statusFor(cls);
      modeSelect.value = nodeModeFor(state.nodes[cls]?.preset);
      indicator.textContent = `In charge: ${s.inCharge}`;
      select.disabled = !s.nodeChoice;               // off only while 4b is in charge
      // buttons never switched off - while locked, a click points at 4b's menu (user, 2026-09-30)
      btnSave.disabled = false; btnSaveAs.disabled = false; btnDesc.disabled = false;
      btnDelete.disabled = false; btnRename.disabled = false; btnReset.disabled = false;
      const wanted = state.nodes[cls]?.preset || NO_PRESET;
      if (!select.__holdPick && select.value !== wanted && [...select.options].some((o) => o.value === wanted)) {
        select.value = wanted; loadDescription();
      }
      lockDials(node, s.dialsLocked);
      root.style.opacity = s.dialsLocked && controlMode() === MODE_PRESET_WINS ? "0.75" : "1";
      root.style.filter = "none";               // cleared every time; greyed again below only if still off
      if (pairSelect) {
        const active = state.switches.start === (cls === "PortraitMasterBaseCharacter" ? "base" : "facegen");
        pairSelect.value = state.switches.start === "facegen" ? "4d Face Generator" : "4c Base Character";
        root.style.filter = active ? "none" : "grayscale(1)";
        lockDials(node, s.dialsLocked || !active);
      }
      if (stylerSelect) {
        stylerSelect.value = state.switches.prompt_styler ? "on" : "off";
      }
      if (s.blocked) {                          // switched off by a z_ choice on 4b
        root.style.filter = "grayscale(1)";
        root.style.opacity = "0.5";
        lockDials(node, true);
      }
      if (pairSelect) pairSelect.disabled = !!zChoice();
    }
  }

  node.addDOMWidget("freedom_pm_panel", "div", root, { serialize: false, hideOnZoom: false });
  const panel = { node, cls, refresh, refreshLists };
  panels.push(panel);
  refreshLists().then(refresh);
  return panel;
}

// --------------------------------------------------------------------------- //
// registration
// --------------------------------------------------------------------------- //
app.registerExtension({
  name: "freedom.portrait.control",

  // (The Legacy 2.9.2 node is hidden on the SERVER side - see __init__.py - because the
  // page's node-filter store is not reachable from an extension module here.)

  async nodeCreated(node) {
    const cls = node.comfyClass || node.type;
    if (cls === TRAINED_FACE_NODE) {
      setTimeout(() => buildTrainedFacePanel(node), 0);
      return;
    }
    if (cls !== CONTROL_NODE && !PM_CLASSES.includes(cls)) return;

    if (cls === CONTROL_NODE) {
      const w = widget(node, "state");
      if (w) {
        // The state field exists for the SERVER, not to be read on screen. A multiline
        // STRING widget draws its own textarea element, so marking the widget hidden is not
        // enough - the element has to be hidden too, or the raw JSON shows on the node.
        w.__freedom = true;
        w.type = "hidden";
        w.computeSize = () => [0, -4];
        const hideElement = () => {
          const el = w.element || w.inputEl || w.domElement;
          if (el) { el.style.display = "none"; return true; }
          return false;
        };
        if (!hideElement()) {
          let tries = 0;
          const timer = setInterval(() => { if (hideElement() || ++tries > 20) clearInterval(timer); }, 100);
        }
      }
      // The old "In charge" (mode) widget stays on the node so older workflows open, but it
      // is hidden and unused: the preset menu decides now (user, 2026-09-29).
      const wm = widget(node, "mode");
      if (wm) { wm.type = "hidden"; wm.computeSize = () => [0, -4]; }
      // The six per-node "In charge" dropdowns (n4c_mode ... n4h_mode) are hidden and not
      // read either: each node's own preset menu decides (user, 2026-09-29, Q66 = 1).
      for (const st of Object.values(STEP_OF)) {
        const wn = widget(node, st + "_mode");
        if (wn) { wn.type = "hidden"; wn.computeSize = () => [0, -4]; }
      }
      setTimeout(() => { pullState(); refreshAll(); }, 50);
      // 4b: built at once, then laid out top-first (see layoutTopFirst).
      buildPanel(node, cls);
      layoutTopFirst(node, { gaps: true });
      return;
    }
    // 4c-4h: the same - our panel, then Portrait Master's own preset controls, on top.
    buildPanel(node, cls);
    layoutTopFirst(node, { top: ["load_preset", "save_preset_as", "save_preset"] });
    // Portrait Master's own "save preset" saved its dials on every run - a save nobody
    // pressed. It is shown OFF and locked; the server also switches it off in every job
    // (user, 2026-09-29: only a Save button may change a stored preset).
    const ws = widget(node, "save_preset");
    if (ws) {
      if (ws.value !== false) { ws.value = false; }
      ws.disabled = true;
      ws.label = "save_preset (off - use the Save buttons)";
    }
    // The nationality mix slider only worked through Prompt Control's "[a:b:0.5]" syntax.
    // Prompt Control was removed (2026-09-29); a two-nationality mix is now written in plain
    // words by STEP 7d, so the slider does nothing and is hidden (user, Q69 = 2).
    if (cls === "PortraitMasterBaseCharacter") {
      const wm = widget(node, "nationality_mix");
      if (wm) { wm.type = "hidden"; wm.computeSize = () => [0, -4]; }
    }
  },

  // A loaded workflow restores its saved value AFTER nodeCreated, so the switch is shown
  // off again once every workflow has finished loading (found in testing, 2026-09-29).
  async afterConfigureGraph() {
    for (const cls of PM_CLASSES) for (const node of graphNodes(cls)) {
      const ws = widget(node, "save_preset");
      if (ws) { ws.value = false; ws.disabled = true; ws.label = "save_preset (off - use the Save buttons)"; }
    }
  },
});

// --------------------------------------------------------------------------- //
// 4b layout (user, 2026-09-24): "in charge" and every save / preset / load
// control at the TOP, and a gap between the 4c, 4d ... sections.
//
// The saved workflow keeps the ORIGINAL order - the real values in nodes.py order
// with the panel's empty slot last - because v04-v07 were saved that way and the
// phone reads values in nodes.py order. Only the screen order changes: values are
// put back by NAME when a workflow loads, and written in the original order when
// it saves.
// --------------------------------------------------------------------------- //
function layoutTopFirst(node, { top = [], gaps = false } = {}) {
  const ws = node.widgets || [];
  const isExtra = (w) => w.name === "freedom_pm_panel" || String(w.name).startsWith("freedom_gap_");
  // The original order, as the node was declared (the panel was added last).
  const realOrder = ws.filter((w) => !isExtra(w)).map((w) => w.name);
  node.__freedomRealOrder = realOrder;          // the declared order, kept for checks
  const byName = Object.fromEntries(ws.map((w) => [w.name, w]));
  let order;

  if (gaps) {
    // 4b: gaps between the sections, each with the section's name so you can find it
    const SECTIONS = { n4d: "4d Face Generator", n4e: "4e Skin Details", n4f: "4f Style & Pose",
                       n4g: "4g Make-up", n4h: "4h Prompt Styler" };
    for (const [step, label] of Object.entries(SECTIONS)) {
      const gap = el("div", { textContent: label });
      gap.style.cssText = "margin-top:10px;padding-top:4px;border-top:1px solid #555;" +
                          "color:#9ecbff;font:600 11px system-ui,sans-serif;letter-spacing:.3px;";
      byName["freedom_gap_" + step] =
        node.addDOMWidget("freedom_gap_" + step, "div", gap, { serialize: false, hideOnZoom: false });
    }
    const tail = el("div");
    tail.style.cssText = "margin-top:10px;border-top:1px solid #555;";
    byName.freedom_gap_switches =
      node.addDOMWidget("freedom_gap_switches", "div", tail, { serialize: false, hideOnZoom: false });
    order = ["freedom_pm_panel", "mode", "preset", "state", "n4c_mode", "n4c_preset"];
    for (const step of Object.keys(SECTIONS)) order.push("freedom_gap_" + step, step + "_mode", step + "_preset");
    order.push("freedom_gap_switches", "active_of_pair", "prompt_styler_switch");
  } else {
    // 4c-4h: our panel, then the developer's preset controls, then every dial as before
    order = ["freedom_pm_panel", ...top, ...realOrder.filter((n) => !top.includes(n))];
  }

  const all = node.widgets || [];
  const lookup = Object.fromEntries(all.map((w) => [w.name, w]));
  const placed = order.filter((n) => lookup[n]).map((n) => lookup[n]);
  const rest = all.filter((w) => !placed.includes(w));     // anything new stays, at the end
  all.splice(0, all.length, ...placed, ...rest);

  // save in the original order: real values by name, then the panel's empty slot
  const onSerialize = node.onSerialize;
  node.onSerialize = function (o) {
    const r = onSerialize ? onSerialize.apply(this, arguments) : undefined;
    if (o && Array.isArray(o.widgets_values)) {
      const val = Object.fromEntries((this.widgets || []).map((w, i) => [w.name, o.widgets_values[i]]));
      o.widgets_values = realOrder.map((n) => val[n]).concat([""]);
    }
    return r;
  };

  // load: let ComfyUI restore however it does (by name, or by position against the
  // NEW screen order - frontend 1.53.6 does either, see settingStore
  // createWidgetRestorationState), then put every value back BY NAME. Tested
  // 2026-09-24: without this, 4h's style came back as `true`.
  const configure = node.configure;
  node.configure = function (info) {
    const r = configure.call(this, info);
    restoreByName(this, info, realOrder);
    return r;
  };
}

// The right value for each real widget, whichever way the file was written:
//  - a named copy (widgets_values_named) - written by the current frontend;
//  - otherwise the list in the ORIGINAL order (older frontends, and our own saves).
function restoreByName(node, info, realOrder) {
  if (!info) return;
  const named = info.widgets_values_named;
  const vals = info.widgets_values;
  let want = null;
  if (named && typeof named === "object" && !Array.isArray(named)) want = named;
  else if (Array.isArray(vals) && vals.length) {
    // Older saves can be SHORTER than today's node (Portrait Master and 4b gained
    // settings since). Before the reorder, those values landed on the first
    // widgets in declared order and the rest kept their defaults - do the same.
    want = Object.fromEntries(realOrder.slice(0, vals.length).map((n, i) => [n, vals[i]]));
  }
  if (!want) return;
  for (const w of node.widgets || []) {
    if (!realOrder.includes(w.name) || !(w.name in want) || want[w.name] === undefined) continue;
    w.value = want[w.name];
  }
}
