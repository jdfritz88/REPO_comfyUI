// =============================================================================
// FREEDOM SYSTEM - Portrait Control (screen side)
//
// Draws, on the desktop ComfyUI page:
//   - STEP 4a: an In-charge dropdown, a preset list, and the four preset buttons.
//   - Each Portrait Master node: the shared banner, an indicator of who is in charge
//     of it, its own In-charge dropdown, a preset list, and the preset buttons.
//   - Base Character and Face Generator: the conflict banner and an "Active of the
//     pair" dropdown - exactly one of the two is in use.
//   - Prompt Styler: its own on/off dropdown, off by default.
//
// There are no radio buttons any more. Radios had to be drawn as page elements, which
// meant only this PC had them - a phone or a raw API call could not set any of these
// choices. Every choice is now a REAL dropdown on node 4a, so it travels with the
// workflow to any client. The controls below read and write those widgets.
//
// A preset saved on STEP 4a carries more than Portrait Master dials: it also holds
// the RECIPE - both seeds with their after-generate setting, the face LoRA and its
// strength, the LoRA stack, and the prompt text. See "THE RECIPE" further down.
//
// Everything the server must obey is mirrored into STEP 4a's hidden "state" field,
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

// The per-node choices now live as REAL dropdowns on node 4a, so every client sends
// them. The controls below are ordinary <select> elements that read and write those
// widgets, which is why the phone gets the same choices the PC has.
const STEP_OF = {
  PortraitMasterBaseCharacter: "n4b",
  PortraitMasterFaceGenerator: "n4c",
  PortraitMasterSkinDetails:   "n4d",
  PortraitMasterStylePose:     "n4e",
  PortraitMasterMakeup:        "n4f",
  PortraitMasterPromptStyler:  "n4g",
};
const MIRROR_NAMES = Object.values(STEP_OF)
  .flatMap((st) => [st + "_mode", st + "_preset"])
  .concat(["active_of_pair", "prompt_styler_switch"]);

// read / write a widget on 4a from anywhere
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

const EXPLANATION =
  "The In-charge dropdown on 4a decides who is in charge:\n" +
  "  Use preset            - the preset wins, these dials are locked.\n" +
  "  Use preset, unlocked  - the preset loads, you can tweak; saving happens on 4a.\n" +
  "  Ignore presets        - this node's own In-charge dropdown takes over:\n" +
  "      Use this node's preset (default) - dials locked, no buttons.\n" +
  "      Load preset, unlock dials        - save, save as, delete available.\n" +
  "      Ignore presets, unlock dials     - save as and delete available.\n" +
  "Factory reset works only in the last one.\n" +
  "A preset saved on 4a also carries the RECIPE: both seeds and their\n" +
  "after-generate setting, the face LoRA and its strength, every switched-on\n" +
  "slot of the LoRA stack, and the words in your STEP 7 box. Loading it puts\n" +
  "all of that back, so a saved look can be reproduced exactly.\n" +
  "New presets saved here are named pm_something. STEP 3 - her trained face -\n" +
  "has its own drawer, named tl_something, holding exactly the same things.";

const CONFLICT =
  "These two cannot be used together. The developer: \"Face Generator is a " +
  "simplified node of Base Character. You can cascade both of them with Skin " +
  "Details, but don't use Face Generator with Base Character.\"\n" +
  "Use the \"Active of the pair\" dropdown to choose which of the two is in use.";

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
// shared state, mirrored into 4a's hidden "state" field for the server
// --------------------------------------------------------------------------- //
const state = {
  nodes: {},                                   // class -> {mode, preset}
  switches: { start: "base", prompt_styler: false },
};

for (const c of PM_CLASSES) state.nodes[c] = { mode: NODE_MODE_PRESET, preset: NO_PRESET };

function pushState() {
  const c = controlNode();
  if (!c) return;
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
  if (wpair) wpair.value = state.switches.start === "facegen" ? "4c Face Generator" : "4b Base Character";
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

const controlMode = () => widget(controlNode(), "mode")?.value || MODE_PRESET_WINS;

// Who is in charge of one node group, and therefore what is locked or greyed.
function statusFor(cls) {
  const m = controlMode();
  if (m === MODE_PRESET_WINS) return { inCharge: "4a preset", dialsLocked: true, nodeChoice: false, buttons: "none", reset: false };
  if (m === MODE_PRESET_UNLOCKED) return { inCharge: "4a preset, dials unlocked", dialsLocked: false, nodeChoice: false, buttons: "none", reset: false };
  const nm = state.nodes[cls]?.mode || NODE_MODE_PRESET;
  if (nm === NODE_MODE_PRESET) return { inCharge: "this node's preset", dialsLocked: true, nodeChoice: true, buttons: "none", reset: false };
  if (nm === NODE_MODE_PRESET_UNLOCKED) return { inCharge: "this node's preset, unlocked", dialsLocked: false, nodeChoice: true, buttons: "all", reset: false };
  return { inCharge: "this node's dials", dialsLocked: false, nodeChoice: true, buttons: "saveas_delete", reset: true };
}

const panels = [];                             // every panel refreshes when anything changes
function refreshAll() {
  pushState();
  for (const p of panels) { try { p.refresh(); } catch (e) { console.error("[freedom pm]", e); } }
}

// Applying a 4a preset to what the screen shows, so the dials always show what is used.
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
//   - both seeds, with their after-generate setting. Without the seed pinned you
//     cannot get the same picture back; without the setting you cannot tell
//     whether it will hold still.
//   - the face LoRA: its strength, which face is picked, and the trigger weight.
//     A strength without the file it applies to means nothing.
//   - every switched-on slot of the LoRA stack, with its file and strength. Her
//     likeness currently comes from three passes of the same file, so the stack
//     is part of the recipe, not scenery.
//   - the words in your STEP 7 box.
//
// Presets saved before this existed simply have no recipe in them; they load as
// they always did.
const RECIPE_SAMPLER = "KSampler";
const RECIPE_DETAILER = "FaceDetailer";
const RECIPE_SHELF = "FreedomFaceShelf";
const RECIPE_STACK = "FreedomLoraStack";
const STACK_SLOTS = 12;

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
  const sampler = graphNodes(RECIPE_SAMPLER)[0];
  if (sampler) {
    recipe.ksampler = {
      seed: widget(sampler, "seed")?.value,
      control_after_generate: widget(sampler, "control_after_generate")?.value,
    };
  }
  const detailer = graphNodes(RECIPE_DETAILER)[0];
  if (detailer) {
    recipe.facedetailer = {
      seed: widget(detailer, "seed")?.value,
      control_after_generate: widget(detailer, "control_after_generate")?.value,
    };
  }
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
  const box = recipePromptBox();
  if (box) recipe.prompt = widget(box, "value")?.value;
  return recipe;
}

function applyRecipe(recipe) {
  if (!recipe) return 0;
  let n = 0;
  const sampler = graphNodes(RECIPE_SAMPLER)[0];
  if (sampler && recipe.ksampler) {
    n += setWidgetValue(sampler, "seed", recipe.ksampler.seed);
    n += setWidgetValue(sampler, "control_after_generate", recipe.ksampler.control_after_generate);
  }
  const detailer = graphNodes(RECIPE_DETAILER)[0];
  if (detailer && recipe.facedetailer) {
    n += setWidgetValue(detailer, "seed", recipe.facedetailer.seed);
    n += setWidgetValue(detailer, "control_after_generate", recipe.facedetailer.control_after_generate);
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
  const box = recipePromptBox();
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
// dial, 4a's switches, and the recipe.
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
    "font:12px system-ui,sans-serif;display:flex;flex-direction:column;gap:5px;" +
    "padding:7px;color:#ddd;background:#1c1c1c;border:1px solid #444;border-radius:6px;";
  for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"]) {
    root.addEventListener(ev, (e) => e.stopPropagation());
  }

  const heading = el("div", { textContent: "HER RECIPES - saved settings for this face" });
  heading.style.cssText = "font-weight:700;color:#cde3ff;font-size:10px;letter-spacing:.3px;";
  const note = el("div", {
    textContent: "A recipe here holds both seeds and whether they are fixed, her LoRA " +
                 "and its strength, the trigger weight, every switched-on slot of the " +
                 "LoRA stack, the words in your STEP 7 box, and every Portrait Master " +
                 "dial. Loading one puts all of it back.",
  });
  note.style.cssText = "color:#9a9a9a;font-size:9.5px;line-height:1.35;";

  const select = el("select");
  select.style.cssText = "background:#222;color:#ddd;border:1px solid #555;padding:2px;";
  const nameBox = el("input", { type: "text", placeholder: "new recipe name (tl_ is added for you)" });
  nameBox.style.cssText = "background:#222;color:#ddd;border:1px solid #555;padding:2px;";
  const row = el("div");
  row.style.cssText = "display:flex;flex-wrap:wrap;gap:4px;";
  const say = el("div");
  say.style.cssText = "color:#9cc4ff;min-height:13px;font-size:10px;";

  const mk = (label, fn) => {
    const b = el("button", { textContent: label });
    b.style.cssText = "background:#2b2b2b;color:#ddd;border:1px solid #555;border-radius:4px;" +
                      "padding:3px 9px;cursor:pointer;font-size:10.5px;";
    b.onclick = fn;
    row.append(b);
    return b;
  };

  const btnSave = mk("Save", async () => {
    const name = select.value;
    if (!name || name === NO_PRESET) { say.textContent = "Pick a recipe to save over."; return; }
    const res = await api.save(scope, name, gatherEverything(), true);
    say.textContent = res.ok ? `Saved '${name}'.` : res.error;
    await refreshLists();
  });

  const btnSaveAs = mk("Save as", async () => {
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
  });

  const btnDelete = mk("Delete", async () => {
    const name = select.value;
    if (!name || name === NO_PRESET) { say.textContent = "Pick a recipe to delete."; return; }
    const res = await api.remove(scope, name);
    say.textContent = res.ok ? `Deleted '${name}'.` : res.error;
    await refreshLists();
  });

  select.onchange = async () => {
    const name = select.value;
    refresh();
    if (!name || name === NO_PRESET) { say.textContent = ""; return; }
    const found = await api.read(scope, name);
    if (!found?.data) { say.textContent = `Could not read '${name}'.`; return; }
    const changed = applyEverything(found.data);
    say.textContent = `Loaded '${name}' - ${changed} setting${changed === 1 ? "" : "s"} put back.`;
  };

  function refresh() {
    const chosen = select.value && select.value !== NO_PRESET;
    btnSave.disabled = !chosen;
    btnDelete.disabled = !chosen;
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
  root.style.cssText = "font:12px system-ui,sans-serif;display:flex;flex-direction:column;gap:6px;padding:6px;color:#ddd;";

  const banner = el("pre");
  banner.style.cssText = "margin:0;white-space:pre-wrap;font:11px ui-monospace,monospace;color:#bbb;background:#1c1c1c;border-left:3px solid #666;padding:6px;";
  banner.textContent = isControl
    ? "STEP 4a decides who is in charge. One choice only.\n" + EXPLANATION
    : EXPLANATION;
  root.append(banner);

  let conflictBanner = null, pairSelect = null;
  if (PAIR.includes(cls)) {
    conflictBanner = el("pre");
    conflictBanner.style.cssText = "margin:0;white-space:pre-wrap;font:11px ui-monospace,monospace;color:#f0c674;background:#2a2113;border-left:3px solid #f0c674;padding:6px;";
    conflictBanner.textContent = CONFLICT;
    root.append(conflictBanner);

    const wrap = el("div");
    wrap.style.cssText = "display:flex;gap:6px;align-items:center;";
    pairSelect = makeSelect([["4b Base Character", "Use 4b Base Character"],
                             ["4c Face Generator", "Use 4c Face Generator"]]);
    pairSelect.addEventListener("change", () => {
      state.switches.start = pairSelect.value.startsWith("4b") ? "base" : "facegen";
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
  arrow.style.cssText = "text-align:center;color:#888;font-size:14px;line-height:1;";
  root.append(arrow);

  // who is in charge - a dropdown, not radio buttons. On 4a it drives 4a's own
  // "mode" widget; on a Portrait Master node it drives that node's "<step>_mode"
  // dropdown over on 4a. Either way the value is a real node setting, so the phone
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

  // preset row
  const row = el("div");
  row.style.cssText = "display:flex;gap:6px;align-items:center;flex-wrap:wrap;";
  const select = el("select");
  select.style.cssText = "flex:1;min-width:140px;background:#222;color:#ddd;border:1px solid #555;padding:2px;";
  select.addEventListener("change", async () => {
    if (isControl) {
      const w = widget(node, "preset");
      if (w) { w.value = select.value; w.callback?.(select.value); }
      await applyControlPreset();
    } else {
      state.nodes[cls].preset = select.value;
      const found = select.value !== NO_PRESET ? await api.read(scope, select.value) : null;
      if (found?.data) writeDials(node, found.data);
    }
    refreshAll();
  });
  row.append(select);
  const nameBox = el("input", { type: "text", placeholder: "new preset name" });
  nameBox.style.cssText = "width:150px;background:#222;color:#ddd;border:1px solid #555;padding:2px;";
  row.append(nameBox);
  root.append(row);

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

  const gather = () => (isControl ? gatherEverything() : readDials(node));

  const btnSave = mkButton("Save", async () => {
    const name = select.value;
    if (!name || name === NO_PRESET) { say.textContent = "Pick a preset to save over."; return; }
    const res = await api.save(scope, name, gather(), true);
    say.textContent = res.ok ? `Saved '${name}'.` : res.error;
    await refreshLists();
  });
  const btnSaveAs = mkButton("Save as", async () => {
    if (!nameBox.value.trim()) { say.textContent = "Type a name first."; return; }
    const name = withPrefix(scope, nameBox.value);
    const res = await api.save(scope, name, gather(), false);
    say.textContent = res.ok ? `Saved '${name}'.` : res.error;
    if (res.ok) { nameBox.value = ""; await refreshLists(); select.value = name; select.dispatchEvent(new Event("change")); }
  });
  const btnDelete = mkButton("Delete", async () => {
    const name = select.value;
    if (!name || name === NO_PRESET) { say.textContent = "Pick a preset to delete."; return; }
    const res = await api.remove(scope, name);
    say.textContent = res.ok ? `Deleted '${name}'.` : res.error;
    await refreshLists();
  });
  const btnReset = mkButton(isControl ? "Factory reset ALL" : "Factory reset", async () => {
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
    select.append(el("option", { value: NO_PRESET, textContent: NO_PRESET }));
    for (const p of presets) {
      select.append(el("option", {
        value: p.name,
        textContent: p.source === "developer" ? `${p.name}  (Portrait Master)` : p.name,
      }));
    }
    const wanted = isControl ? widget(node, "preset")?.value : state.nodes[cls]?.preset;
    select.value = [...select.options].some((o) => o.value === wanted) ? wanted
                 : ([...select.options].some((o) => o.value === current) ? current : NO_PRESET);
  }

  function refresh() {
    if (isControl) {
      const m = controlMode();
      modeSelect.value = m;
      indicator.textContent = `In charge: ${m}`;
      const ignoring = m === MODE_IGNORE;
      select.disabled = ignoring;
      btnSave.disabled = ignoring;
      btnSaveAs.disabled = ignoring;
      btnDelete.disabled = ignoring;
      btnReset.disabled = !ignoring;          // reset-all only when presets are ignored
      const w = widget(node, "preset");
      if (w && select.value !== w.value && !ignoring) select.value = w.value;
    } else {
      const s = statusFor(cls);
      modeSelect.value = state.nodes[cls]?.mode || NODE_MODE_PRESET;
      modeSelect.disabled = !s.nodeChoice;
      indicator.textContent = `In charge: ${s.inCharge}`;
      modeWrap.style.opacity = s.nodeChoice ? "1" : "0.45";
      const presetUsable = s.nodeChoice && (state.nodes[cls]?.mode !== NODE_MODE_IGNORE);
      select.disabled = !presetUsable;
      btnSave.disabled = s.buttons !== "all";
      btnSaveAs.disabled = !(s.buttons === "all" || s.buttons === "saveas_delete");
      btnDelete.disabled = !(s.buttons === "all" || s.buttons === "saveas_delete");
      btnReset.disabled = !s.reset;
      lockDials(node, s.dialsLocked);
      root.style.opacity = s.dialsLocked && controlMode() === MODE_PRESET_WINS ? "0.75" : "1";
      if (pairSelect) {
        const active = state.switches.start === (cls === "PortraitMasterBaseCharacter" ? "base" : "facegen");
        pairSelect.value = state.switches.start === "facegen" ? "4c Face Generator" : "4b Base Character";
        root.style.filter = active ? "none" : "grayscale(1)";
        lockDials(node, s.dialsLocked || !active);
      }
      if (stylerSelect) {
        stylerSelect.value = state.switches.prompt_styler ? "on" : "off";
      }
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
      setTimeout(() => { pullState(); refreshAll(); }, 50);
    }
    setTimeout(() => buildPanel(node, cls), 0);
  },
});
