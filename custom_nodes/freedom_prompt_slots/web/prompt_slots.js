// =============================================================================
// FREEDOM SYSTEM - Prompt Slots and Phrase Slots (screen side)
//
// Draws, wherever ComfyUI's own page is open - this PC, or a phone at the plain
// address (NOT the CueForge mobile app at /mobile, which loads no custom node
// JavaScript at all):
//   - the buttons under the PROMPT SLOTS node   (Load, Save overwrite, Save as,
//     Create new, Save phrase, Delete)
//   - the buttons under the PHRASE SLOTS node   (Copy phrase, Save phrase, Delete)
//   - a single "Save phrase" button under your STEP 7 prompt box
//
// WHAT IS A WIDGET AND WHAT IS A BUTTON, AND WHY IT MATTERS
// --------------------------------------------------------
// The dial, the name and the two read-only windows are REAL widgets, declared in
// nodes.py. Real widgets travel with the workflow and are drawn by every client,
// including the CueForge mobile app - its number field is literally a minus
// button, the value, and a plus button. The buttons below are page elements, so
// they exist only where this file is loaded. That is why nothing the shelves need
// to REMEMBER is ever stored in a button.
//
// FINDING YOUR PROMPT BOX
// -----------------------
// Never by node id. Ids were handed out in the order the nodes were created and
// do not match the STEP numbers on screen - the box labelled STEP 7 is id 4. We
// follow the wire instead: your prompt box is whatever feeds `string_b` on the
// StringConcatenate that glues her trigger word onto the front of your text. So
// renaming, renumbering or moving nodes cannot break this.
//
// REMEMBERING WHAT YOU HIGHLIGHTED
// --------------------------------
// The Save phrase buttons do not read the highlight at the moment you click,
// because clicking a button can take the highlight away first. Every text box we
// care about gets a listener that remembers the last stretch of words you
// highlighted in it. The button saves that.
// =============================================================================
import { app } from "../../scripts/app.js";

const PROMPT_NODE = "FreedomPromptSlots";
const PHRASE_NODE = "FreedomPhraseSlots";
const PARTS_NODE = "FreedomPromptParts";

// STEP 7 in two boxes: each box has its own shelf (see nodes.py).
const PART_SPECS = [
  { kind: "physical", slot: "physical_slot", name: "physical_name",
    saved: "physical_saved", box: "physical",
    title: "PHYSICAL - how she looks (body, face, hair, skin, clothing)",
    boxLabel: "the physical box" },
  { kind: "scene", slot: "scene_slot", name: "scene_name",
    saved: "scene_saved", box: "everything_else",
    title: "EVERYTHING ELSE - pose, action, scene, camera, light, style",
    boxLabel: "the everything-else box" },
];

// --------------------------------------------------------------------------- //
// small helpers
// --------------------------------------------------------------------------- //
const el = (tag, props = {}, children = []) => {
  const e = Object.assign(document.createElement(tag), props);
  for (const c of children) e.append(c);
  return e;
};

const graphNodes = (type) => (app.graph?._nodes || []).filter((n) => n.type === type);
const widget = (node, name) => (node?.widgets || []).find((w) => w.name === name) || null;

// A multiline widget draws a real <textarea> on the page. Depending on the
// front-end version the widget hands us the textarea itself or a box containing
// it, so check both.
function textareaOf(w) {
  const root = w?.element || w?.inputEl || w?.domElement;
  if (!root) return null;
  if (root.tagName === "TEXTAREA" || root.tagName === "INPUT") return root;
  return root.querySelector("textarea, input") || null;
}

// The textarea does not always exist the instant the node does. Keep looking for
// a couple of seconds, then give up quietly.
function whenTextarea(w, fn) {
  const found = textareaOf(w);
  if (found) { fn(found); return; }
  let tries = 0;
  const timer = setInterval(() => {
    const ta = textareaOf(w);
    if (ta) { clearInterval(timer); fn(ta); }
    else if (++tries > 40) clearInterval(timer);
  }, 100);
}

async function getJson(route) {
  const r = await fetch(route);
  return await r.json();
}

async function postJson(route, body) {
  const r = await fetch(route, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return await r.json();
}

// Write a value into a real widget and make sure the page shows it.
function setWidget(node, name, value) {
  const w = widget(node, name);
  if (!w) return false;
  w.__freedomQuiet = true;
  w.value = value;
  const ta = textareaOf(w);
  if (ta) ta.value = value;
  try { w.callback?.(value); } catch (e) { /* a widget without a callback is fine */ }
  w.__freedomQuiet = false;
  node.setDirtyCanvas?.(true, true);
  return true;
}

const widgetValue = (node, name) => widget(node, name)?.value ?? "";

// Copy to the clipboard. The modern call only works on localhost or https; the
// older one works over plain http too, which is how the phone reaches this PC.
async function copyToClipboard(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (e) { /* fall through to the old way */ }
  const scratch = el("textarea", { value: text });
  scratch.style.cssText = "position:fixed;top:-1000px;left:-1000px;opacity:0;";
  document.body.append(scratch);
  scratch.focus();
  scratch.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
  scratch.remove();
  return ok;
}

// --------------------------------------------------------------------------- //
// buttons that throw something away ask twice
// --------------------------------------------------------------------------- //
// Create new empties your prompt box; Delete takes a slot off the shelf. Neither
// should happen on one stray tap. The first press only changes the label on the
// button itself - no pop-up box, because a pop-up freezes the whole page until
// it is answered. Pressing any other button in the panel calms them down again.
function twoStep(button, calmLabel, armedLabel, warning, act, say) {
  let armed = false;
  const calm = () => { armed = false; button.textContent = calmLabel; };
  button.__calm = calm;
  button.onclick = async () => {
    if (!armed) { armed = true; button.textContent = armedLabel; say(warning); return; }
    calm();
    await act();
  };
  return calm;
}

// Put every two-click button in a panel back to its resting label.
function calmAll(root) {
  for (const b of root.querySelectorAll(".fpsl-btn")) b.__calm?.();
}

// --------------------------------------------------------------------------- //
// what you last highlighted, and where
// --------------------------------------------------------------------------- //
const lastSelection = { text: "", from: "" };

function rememberSelections(textarea, label) {
  if (textarea.__freedomWatched) return;
  textarea.__freedomWatched = true;
  const remember = () => {
    const picked = String(textarea.value || "")
      .substring(textarea.selectionStart, textarea.selectionEnd);
    if (picked && picked.trim()) {
      lastSelection.text = picked.trim();
      lastSelection.from = label;
    }
  };
  for (const ev of ["mouseup", "keyup", "select", "touchend"]) {
    textarea.addEventListener(ev, remember);
  }
}

// --------------------------------------------------------------------------- //
// the two shelves, held in memory so the dial feels instant
// --------------------------------------------------------------------------- //
const shelf = { prompts: [], phrases: [], parts: { physical: [], scene: [] } };
const panels = [];                       // every panel refreshes when anything changes

async function reloadPrompts() {
  try { shelf.prompts = (await getJson("/freedom/promptslots/list")).prompts || []; }
  catch (e) { shelf.prompts = []; }
}

async function reloadPhrases() {
  try { shelf.phrases = (await getJson("/freedom/phrases/list")).phrases || []; }
  catch (e) { shelf.phrases = []; }
}

async function reloadParts() {
  for (const spec of PART_SPECS) {
    try { shelf.parts[spec.kind] = (await getJson(`/freedom/partslots/${spec.kind}/list`)).items || []; }
    catch (e) { shelf.parts[spec.kind] = []; }
  }
}

function refreshAll() {
  for (const p of panels) { try { p.refresh(); } catch (e) { /* node gone */ } }
}

// --------------------------------------------------------------------------- //
// finding your STEP 7 prompt box by following the wire
// --------------------------------------------------------------------------- //
function promptBoxNode() {
  const graph = app.graph;
  if (!graph) return null;
  for (const node of graph._nodes || []) {
    if (node.type !== "StringConcatenate") continue;
    const slot = (node.inputs || []).findIndex((i) => i.name === "string_b");
    if (slot < 0) continue;
    let origin = null;
    try { origin = node.getInputNode?.(slot); } catch (e) { origin = null; }
    if (!origin) {
      const link = graph.links?.[node.inputs[slot].link];
      if (link) origin = graph.getNodeById?.(link.origin_id);
    }
    if (origin) return origin;
  }
  // Nothing wired yet - fall back to the only plain multiline text node there is.
  return (graph._nodes || []).find((n) => n.type === "PrimitiveStringMultiline") || null;
}

function promptBoxText() {
  const node = promptBoxNode();
  if (!node) return null;
  const w = widget(node, "value");
  if (!w) return null;
  const ta = textareaOf(w);
  return ta ? String(ta.value || "") : String(w.value || "");
}

function setPromptBoxText(text) {
  const node = promptBoxNode();
  if (!node) return false;
  return setWidget(node, "value", text);
}

// --------------------------------------------------------------------------- //
// styling
// --------------------------------------------------------------------------- //
const CSS = `
.fpsl-root{display:flex;flex-direction:column;gap:6px;
  font:11px/1.35 system-ui,Segoe UI,sans-serif;color:#ddd;background:#1c1c1c;
  border:1px solid #444;border-radius:6px;padding:8px}
.fpsl-row{display:flex;flex-wrap:wrap;gap:5px}
.fpsl-btn{background:#2b2b2b;color:#ddd;border:1px solid #555;border-radius:4px;
  padding:4px 9px;cursor:pointer;font-size:10.5px;white-space:nowrap}
.fpsl-btn:hover{background:#3a3a3a;border-color:#6a8cb8}
.fpsl-btn:disabled{opacity:.4;cursor:default}
.fpsl-btn.warn{border-color:#a66;color:#fbb}
.fpsl-where{color:#cde3ff;font-size:10px;font-weight:600;letter-spacing:.3px}
.fpsl-status{color:#9cc4ff;font-size:10px;min-height:13px}
.fpsl-status.bad{color:#f2a0a0}
`;

function installCss() {
  if (document.getElementById("fpsl-css")) return;
  document.head.append(el("style", { id: "fpsl-css", textContent: CSS }));
}

// --------------------------------------------------------------------------- //
// PROMPT SLOTS panel
// --------------------------------------------------------------------------- //
function buildPromptPanel(node) {
  const root = el("div", { className: "fpsl-root" });
  const where = el("div", { className: "fpsl-where" });
  const status = el("div", { className: "fpsl-status" });

  const btnLoad = el("button", { className: "fpsl-btn", textContent: "Load" });
  const btnSave = el("button", { className: "fpsl-btn", textContent: "Save (overwrite)" });
  const btnSaveAs = el("button", { className: "fpsl-btn", textContent: "Save as" });
  const btnNew = el("button", { className: "fpsl-btn warn", textContent: "Create new" });
  const btnDelete = el("button", { className: "fpsl-btn warn", textContent: "Delete" });
  const btnPhrase = el("button", { className: "fpsl-btn", textContent: "Save phrase" });
  const btnRename = el("button", { className: "fpsl-btn", textContent: "Rename" });

  root.append(where,
    el("div", { className: "fpsl-row" }, [btnLoad, btnSave, btnSaveAs, btnNew]),
    el("div", { className: "fpsl-row" }, [btnRename, btnPhrase, btnDelete]),
    status);

  // The canvas swallows clicks and scrolls unless we stop them here.
  for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"]) {
    root.addEventListener(ev, (e) => e.stopPropagation());
  }

  const say = (message, bad) => {
    status.textContent = message || "";
    status.className = "fpsl-status" + (bad ? " bad" : "");
  };

  const slotNow = () => Math.max(1, parseInt(widgetValue(node, "slot"), 10) || 1);

  const disarm = () => calmAll(root);

  function refresh() {
    const slot = slotNow();
    const entry = shelf.prompts[slot - 1];
    setWidget(node, "name", entry ? entry.name : "");
    setWidget(node, "saved_prompt", entry ? entry.positive : "");
    where.textContent = entry
      ? `slot ${slot} of ${shelf.prompts.length} saved`
      : (shelf.prompts.length
        ? `slot ${slot} is empty - ${shelf.prompts.length} saved, dial down to see them`
        : "nothing saved yet - type a name and press Save as");
    btnLoad.disabled = !entry;
    btnSave.disabled = !entry;
    btnRename.disabled = !entry;
    btnDelete.disabled = !entry;
  }

  btnRename.onclick = async () => {
    disarm();
    const slot = slotNow();
    const result = await postJson("/freedom/promptslots/rename", {
      slot, name: widgetValue(node, "name"),
    });
    if (!result.ok) { say(result.error || "rename failed", true); return; }
    shelf.prompts = result.prompts;
    refreshAll();
    say(`renamed "${result.old}" to "${shelf.prompts[slot - 1].name}" - its text is unchanged`);
  };

  btnLoad.onclick = () => {
    disarm();
    const entry = shelf.prompts[slotNow() - 1];
    if (!entry) { say("that slot is empty", true); return; }
    if (!setPromptBoxText(entry.positive)) { say("could not find your STEP 7 box", true); return; }
    say(`loaded "${entry.name}" into your STEP 7 box - edit it there`);
  };

  btnSave.onclick = async () => {
    disarm();
    const text = promptBoxText();
    if (text === null) { say("could not find your STEP 7 box", true); return; }
    const slot = slotNow();
    const result = await postJson("/freedom/promptslots/save", {
      slot, name: widgetValue(node, "name"), positive: text,
    });
    if (!result.ok) { say(result.error || "save failed", true); return; }
    shelf.prompts = result.prompts;
    refreshAll();
    say(`slot ${slot} written over with what is in your STEP 7 box`);
  };

  btnSaveAs.onclick = async () => {
    disarm();
    const text = promptBoxText();
    if (text === null) { say("could not find your STEP 7 box", true); return; }
    const result = await postJson("/freedom/promptslots/saveas", {
      name: widgetValue(node, "name"), positive: text,
    });
    if (!result.ok) { say(result.error || "save failed", true); return; }
    shelf.prompts = result.prompts;
    setWidget(node, "slot", result.slot);
    refreshAll();
    say(`saved as slot ${result.slot}`);
  };

  twoStep(btnNew, "Create new", "Clear the box - click again",
    "this empties your STEP 7 box. Click again to go ahead, or click anything else.",
    () => {
      setPromptBoxText("");
      const fresh = Math.min(shelf.prompts.length + 1, 99);
      setWidget(node, "slot", fresh);
      setWidget(node, "name", "");
      setWidget(node, "saved_prompt", "");
      refresh();
      say(`box emptied. You are on slot ${fresh}, which is free. Type your prompt, ` +
          "then a name here, then press Save as.");
    }, say);

  twoStep(btnDelete, "Delete", "Delete this one - click again",
    "this takes the prompt you are dialled to off the shelf for good. Click again " +
    "to go ahead, or click anything else.",
    async () => {
      const slot = slotNow();
      const result = await postJson("/freedom/promptslots/delete", { slot });
      if (!result.ok) { say(result.error || "could not delete that one", true); return; }
      shelf.prompts = result.prompts;
      // Everything after the deleted one moved up a slot, so stay in range.
      setWidget(node, "slot", Math.min(slot, Math.max(1, shelf.prompts.length)));
      refreshAll();
      say(`"${result.deleted}" is gone. ${shelf.prompts.length} left, and anything ` +
          "that was below it has moved up a slot.");
    }, say);

  btnPhrase.onclick = async () => {
    disarm();
    await savePhrase(say);
  };

  node.addDOMWidget("freedom_prompt_slots_buttons", "div", root,
    { serialize: false, hideOnZoom: false });

  // The window onto the shelf is a window, not a notepad - you read it here and
  // edit in the STEP 7 box. It still allows highlighting, which Save phrase needs.
  whenTextarea(widget(node, "saved_prompt"), (ta) => {
    ta.readOnly = true;
    ta.title = "Read-only. Press Load to edit this in your STEP 7 box.";
    rememberSelections(ta, "the saved-prompt window");
  });

  // Turning the dial re-reads the shelf entry under it.
  const dial = widget(node, "slot");
  if (dial) {
    const original = dial.callback;
    dial.callback = function (value) {
      const r = original ? original.apply(this, arguments) : undefined;
      if (!dial.__freedomQuiet) setTimeout(refresh, 0);
      return r;
    };
  }

  const panel = { node, refresh };
  panels.push(panel);
  return panel;
}

// --------------------------------------------------------------------------- //
// PHRASE SLOTS panel
// --------------------------------------------------------------------------- //
function buildPhrasePanel(node) {
  const root = el("div", { className: "fpsl-root" });
  const where = el("div", { className: "fpsl-where" });
  const status = el("div", { className: "fpsl-status" });

  const btnCopy = el("button", { className: "fpsl-btn", textContent: "Copy phrase" });
  const btnSave = el("button", { className: "fpsl-btn", textContent: "Save phrase" });
  const btnRename = el("button", { className: "fpsl-btn", textContent: "Rename" });
  const btnSaveAs = el("button", { className: "fpsl-btn", textContent: "Save as" });
  const btnDelete = el("button", { className: "fpsl-btn warn", textContent: "Delete" });

  root.append(where,
    el("div", { className: "fpsl-row" }, [btnCopy, btnSave, btnRename, btnSaveAs, btnDelete]),
    status);
  for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"]) {
    root.addEventListener(ev, (e) => e.stopPropagation());
  }

  const say = (message, bad) => {
    status.textContent = message || "";
    status.className = "fpsl-status" + (bad ? " bad" : "");
  };

  const slotNow = () => Math.max(1, parseInt(widgetValue(node, "slot"), 10) || 1);

  function refresh() {
    const slot = slotNow();
    const phrase = shelf.phrases[slot - 1];
    setWidget(node, "phrase", phrase || "");
    where.textContent = phrase
      ? `slot ${slot} of ${shelf.phrases.length} saved`
      : (shelf.phrases.length
        ? `slot ${slot} is empty - ${shelf.phrases.length} saved, dial down to see them`
        : "no phrases yet - highlight some words in STEP 7 and press Save phrase");
    btnCopy.disabled = !phrase;
    btnRename.disabled = !phrase;
    btnSaveAs.disabled = !phrase;
    btnDelete.disabled = !phrase;
  }

  // A phrase has no separate name - its words are its name. So Rename works in
  // two presses: the first unlocks the window above so you can change the
  // words; the second saves them back to the same slot.
  let editing = false;
  const phraseArea = () => textareaOf(widget(node, "phrase"));
  const stopEditing = () => {
    editing = false;
    btnRename.textContent = "Rename";
    const ta = phraseArea();
    if (ta) ta.readOnly = true;
  };
  btnRename.onclick = async () => {
    calmAll(root);
    const ta = phraseArea();
    if (!editing) {
      if (!ta) { say("could not find the phrase window", true); return; }
      editing = true;
      ta.readOnly = false;
      ta.focus();
      btnRename.textContent = "Save new words";
      say("change the words in the window above, then press Save new words");
      return;
    }
    const slot = slotNow();
    const text = ta ? String(ta.value || "") : String(widgetValue(node, "phrase"));
    stopEditing();
    const result = await postJson("/freedom/phrases/rename", { slot, text });
    if (!result.ok) { say(result.error || "rename failed", true); refresh(); return; }
    shelf.phrases = result.phrases;
    refreshAll();
    say(`phrase in slot ${slot} renamed`);
  };

  // Save as (user, 2026-09-29): the words in the window - changed or not - go on the
  // shelf as a NEW phrase; the phrase you are dialled to stays as it was. Use Rename,
  // then change the words, then Save as, to keep both.
  btnSaveAs.onclick = async () => {
    calmAll(root);
    const ta = phraseArea();
    const text = ta ? String(ta.value || "").trim() : String(widgetValue(node, "phrase") || "").trim();
    if (!text) { say("the window is empty - nothing to save", true); return; }
    stopEditing();
    const result = await postJson("/freedom/phrases/add", { text });
    if (!result.ok) { say(result.error || "could not save that phrase", true); refresh(); return; }
    shelf.phrases = result.phrases;
    setWidget(node, "slot", result.slot);
    refreshAll();
    say(result.already ? `those words are already on the shelf, at slot ${result.slot}`
                       : `saved as a new phrase in slot ${result.slot}; the old one is unchanged`);
  };

  btnCopy.onclick = async () => {
    calmAll(root);
    const phrase = shelf.phrases[slotNow() - 1];
    if (!phrase) { say("that slot is empty", true); return; }
    const ok = await copyToClipboard(phrase);
    say(ok
      ? "copied. Click into your STEP 7 box and paste it where you want it."
      : "the browser would not let me copy - highlight it in the window above " +
        "and press Ctrl+C instead", !ok);
  };

  btnSave.onclick = () => { calmAll(root); return savePhrase(say); };

  twoStep(btnDelete, "Delete", "Delete this one - click again",
    "this takes the phrase you are dialled to off the shelf for good. Click again " +
    "to go ahead, or click anything else.",
    async () => {
      const slot = slotNow();
      const result = await postJson("/freedom/phrases/delete", { slot });
      if (!result.ok) { say(result.error || "could not delete that one", true); return; }
      shelf.phrases = result.phrases;
      setWidget(node, "slot", Math.min(slot, Math.max(1, shelf.phrases.length)));
      refreshAll();
      const short = String(result.deleted).length > 40
        ? String(result.deleted).slice(0, 40) + "..." : result.deleted;
      say(`"${short}" is gone. ${shelf.phrases.length} left, and anything below it ` +
          "has moved up a slot.");
    }, say);

  node.addDOMWidget("freedom_phrase_slots_buttons", "div", root,
    { serialize: false, hideOnZoom: false });

  whenTextarea(widget(node, "phrase"), (ta) => {
    ta.readOnly = true;
    ta.title = "Read-only. Press Copy phrase, then paste into your STEP 7 box.";
    rememberSelections(ta, "the phrase window");
  });

  const dial = widget(node, "slot");
  if (dial) {
    const original = dial.callback;
    dial.callback = function (value) {
      const r = original ? original.apply(this, arguments) : undefined;
      if (!dial.__freedomQuiet) setTimeout(refresh, 0);
      return r;
    };
  }

  const panel = { node, refresh };
  panels.push(panel);
  return panel;
}

// --------------------------------------------------------------------------- //
// STEP 7 in two boxes - one shelf section per box
// --------------------------------------------------------------------------- //
// Same package as the prompt shelf, but Load / Save read and write the node's
// OWN box, so no wire-following is needed. The buttons are slotted in directly
// under each section's read-only window, above its typing box, so every save,
// load and preset control sits at the top of its section.
function buildPartsSection(node, spec) {
  const root = el("div", { className: "fpsl-root" });
  const head = el("div", { className: "fpsl-where", textContent: spec.title });
  const where = el("div", { className: "fpsl-status" });
  const status = el("div", { className: "fpsl-status" });

  const btnLoad = el("button", { className: "fpsl-btn", textContent: "Load" });
  const btnSave = el("button", { className: "fpsl-btn", textContent: "Save (overwrite)" });
  const btnSaveAs = el("button", { className: "fpsl-btn", textContent: "Save as" });
  const btnNew = el("button", { className: "fpsl-btn warn", textContent: "Create new" });
  const btnDelete = el("button", { className: "fpsl-btn warn", textContent: "Delete" });
  const btnPhrase = el("button", { className: "fpsl-btn", textContent: "Save phrase" });
  const btnRename = el("button", { className: "fpsl-btn", textContent: "Rename" });

  root.append(head, where,
    el("div", { className: "fpsl-row" }, [btnLoad, btnSave, btnSaveAs, btnNew]),
    el("div", { className: "fpsl-row" }, [btnRename, btnPhrase, btnDelete]),
    status);
  for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"]) {
    root.addEventListener(ev, (e) => e.stopPropagation());
  }

  const say = (message, bad) => {
    status.textContent = message || "";
    status.className = "fpsl-status" + (bad ? " bad" : "");
  };
  const items = () => shelf.parts[spec.kind] || [];
  const slotNow = () => Math.max(1, parseInt(widgetValue(node, spec.slot), 10) || 1);
  const boxText = () => {
    const w = widget(node, spec.box);
    if (!w) return null;
    const ta = textareaOf(w);
    return ta ? String(ta.value || "") : String(w.value || "");
  };
  const disarm = () => calmAll(root);

  function refresh() {
    const slot = slotNow();
    const entry = items()[slot - 1];
    setWidget(node, spec.name, entry ? entry.name : "");
    setWidget(node, spec.saved, entry ? entry.text : "");
    where.textContent = entry
      ? `slot ${slot} of ${items().length} saved`
      : (items().length
        ? `slot ${slot} is empty - ${items().length} saved, dial down to see them`
        : "nothing saved yet - type in the box below, a name above, then Save as");
    btnLoad.disabled = !entry;
    btnSave.disabled = !entry;
    btnRename.disabled = !entry;
    btnDelete.disabled = !entry;
  }

  const post = async (action, body) => {
    const result = await postJson(`/freedom/partslots/${spec.kind}/${action}`, body);
    if (result.ok && result.items) shelf.parts[spec.kind] = result.items;
    return result;
  };

  btnLoad.onclick = () => {
    disarm();
    const entry = items()[slotNow() - 1];
    if (!entry) { say("that slot is empty", true); return; }
    setWidget(node, spec.box, entry.text);
    say(`loaded "${entry.name}" into ${spec.boxLabel} - edit it there`);
  };

  btnSave.onclick = async () => {
    disarm();
    const text = boxText();
    if (text === null) { say(`could not find ${spec.boxLabel}`, true); return; }
    const slot = slotNow();
    const r = await post("save", { slot, name: widgetValue(node, spec.name), text });
    if (!r.ok) { say(r.error || "save failed", true); return; }
    refreshAll();
    say(`slot ${slot} written over with what is in ${spec.boxLabel}`);
  };

  btnSaveAs.onclick = async () => {
    disarm();
    const text = boxText();
    if (text === null) { say(`could not find ${spec.boxLabel}`, true); return; }
    const r = await post("saveas", { name: widgetValue(node, spec.name), text });
    if (!r.ok) { say(r.error || "save failed", true); return; }
    setWidget(node, spec.slot, r.slot);
    refreshAll();
    say(`saved as slot ${r.slot}`);
  };

  twoStep(btnNew, "Create new", "Clear the box - click again",
    `this empties ${spec.boxLabel}. Click again to go ahead, or click anything else.`,
    () => {
      setWidget(node, spec.box, "");
      const fresh = Math.min(items().length + 1, 99);
      setWidget(node, spec.slot, fresh);
      setWidget(node, spec.name, "");
      setWidget(node, spec.saved, "");
      refresh();
      say(`box emptied. You are on slot ${fresh}, which is free. Type, name it, ` +
          "then press Save as.");
    }, say);

  twoStep(btnDelete, "Delete", "Delete this one - click again",
    "this takes the one you are dialled to off the shelf for good. Click again " +
    "to go ahead, or click anything else.",
    async () => {
      const slot = slotNow();
      const r = await post("delete", { slot });
      if (!r.ok) { say(r.error || "could not delete that one", true); return; }
      setWidget(node, spec.slot, Math.min(slot, Math.max(1, items().length)));
      refreshAll();
      say(`"${r.deleted}" is gone. ${items().length} left, and anything below it ` +
          "has moved up a slot.");
    }, say);

  btnPhrase.onclick = async () => { disarm(); await savePhrase(say); };

  btnRename.onclick = async () => {
    disarm();
    const slot = slotNow();
    const r = await post("rename", { slot, name: widgetValue(node, spec.name) });
    if (!r.ok) { say(r.error || "rename failed", true); return; }
    refreshAll();
    say(`renamed "${r.old}" to "${items()[slot - 1].name}" - its text is unchanged`);
  };

  // Add the buttons, then move them to sit right under this section's window.
  const domName = `freedom_parts_${spec.kind}_buttons`;
  node.addDOMWidget(domName, "div", root, { serialize: false, hideOnZoom: false });
  const ws = node.widgets || [];
  const from = ws.findIndex((w) => w.name === domName);
  const after = ws.findIndex((w) => w.name === spec.saved);
  if (from !== -1 && after !== -1 && from !== after + 1) {
    const [moved] = ws.splice(from, 1);
    ws.splice(ws.findIndex((w) => w.name === spec.saved) + 1, 0, moved);
  }

  whenTextarea(widget(node, spec.saved), (ta) => {
    ta.readOnly = true;
    ta.title = `Read-only. Press Load to edit this in ${spec.boxLabel}.`;
    rememberSelections(ta, `the saved ${spec.kind} window`);
  });
  whenTextarea(widget(node, spec.box), (ta) => rememberSelections(ta, spec.boxLabel));

  const dial = widget(node, spec.slot);
  if (dial) {
    const original = dial.callback;
    dial.callback = function (value) {
      const r = original ? original.apply(this, arguments) : undefined;
      if (!dial.__freedomQuiet) setTimeout(refresh, 0);
      return r;
    };
  }

  const panel = { node, refresh };
  panels.push(panel);
  return panel;
}

// The saved workflow holds ONLY the node's real values, in the order nodes.py
// declares them. The phone (CueForge) draws no button panels and reads values
// in that order, so a panel's empty slot in the middle would shift every value
// after it. Strip the panel slots when saving; put them back when loading.
function keepPanelsOutOfSavedValues(node) {
  const isPanel = (w) => String(w?.name || "").startsWith("freedom_parts_");
  const realCount = () => (node.widgets || []).filter((w) => !isPanel(w)).length;

  const onSerialize = node.onSerialize;
  node.onSerialize = function (o) {
    const r = onSerialize ? onSerialize.apply(this, arguments) : undefined;
    if (o && Array.isArray(o.widgets_values)) {
      o.widgets_values = (this.widgets || [])
        .map((w, i) => (isPanel(w) ? undefined : o.widgets_values[i]))
        .filter((_, i) => !isPanel(this.widgets[i]));
    }
    return r;
  };

  // Load: let ComfyUI restore however it does, then put every value back BY NAME -
  // from the file's named copy if it has one, else from the plain list in
  // nodes.py order. (Frontend 1.53.6 sometimes restores by position against the
  // screen order, which would shift values past the panels.)
  const realOrder = (node.widgets || []).filter((w) => !isPanel(w)).map((w) => w.name);
  const configure = node.configure;
  node.configure = function (info) {
    const r = configure.call(this, info);
    if (info) {
      const named = info.widgets_values_named;
      const vals = info.widgets_values;
      let want = null;
      if (named && typeof named === "object" && !Array.isArray(named)) want = named;
      else if (Array.isArray(vals) && vals.length === realCount()) {
        want = Object.fromEntries(realOrder.map((n, i) => [n, vals[i]]));
      } else if (Array.isArray(vals) && vals.length === (this.widgets || []).length) {
        want = Object.fromEntries((this.widgets || []).map((w, i) => [w.name, vals[i]]));
      }
      if (want) {
        for (const w of this.widgets || []) {
          if (isPanel(w) || !(w.name in want) || want[w.name] === undefined) continue;
          w.value = want[w.name];
          const ta = textareaOf(w);
          if (ta) ta.value = want[w.name];
        }
      }
    }
    return r;
  };
}

// --------------------------------------------------------------------------- //
// saving whatever you last highlighted, from wherever you highlighted it
// --------------------------------------------------------------------------- //
async function savePhrase(say) {
  if (!lastSelection.text) {
    say("highlight some words first - in your STEP 7 box or in either window here", true);
    return;
  }
  const result = await postJson("/freedom/phrases/add", { text: lastSelection.text });
  if (!result.ok) { say(result.error || "could not save that phrase", true); return; }
  shelf.phrases = result.phrases;
  // Park every phrase dial on the phrase that just landed, so you can see it did.
  for (const p of panels) {
    if (p.node?.type === PHRASE_NODE) setWidget(p.node, "slot", result.slot);
  }
  refreshAll();
  const short = lastSelection.text.length > 40
    ? lastSelection.text.slice(0, 40) + "..."
    : lastSelection.text;
  say(result.already
    ? `already on the shelf at slot ${result.slot}: "${short}"`
    : `saved to phrase slot ${result.slot}: "${short}"`);
}

// --------------------------------------------------------------------------- //
// the Save phrase button that sits under your STEP 7 prompt box
// --------------------------------------------------------------------------- //
function attachToPromptBox() {
  // Only bother if one of the shelves is actually on the canvas. A workflow
  // without them should not grow a button it has no use for.
  if (!graphNodes(PROMPT_NODE).length && !graphNodes(PHRASE_NODE).length) return;

  const node = promptBoxNode();
  if (!node || node.__freedomPhraseButton) return;
  node.__freedomPhraseButton = true;

  const root = el("div", { className: "fpsl-root" });
  const status = el("div", { className: "fpsl-status" });
  const btn = el("button", { className: "fpsl-btn", textContent: "Save phrase" });
  root.append(
    el("div", { className: "fpsl-where", textContent: "HIGHLIGHT WORDS ABOVE, THEN:" }),
    el("div", { className: "fpsl-row" }, [btn]),
    status);
  for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"]) {
    root.addEventListener(ev, (e) => e.stopPropagation());
  }

  const say = (message, bad) => {
    status.textContent = message || "";
    status.className = "fpsl-status" + (bad ? " bad" : "");
  };
  btn.onclick = () => savePhrase(say);

  node.addDOMWidget("freedom_save_phrase", "div", root,
    { serialize: false, hideOnZoom: false });
  whenTextarea(widget(node, "value"), (ta) => rememberSelections(ta, "your STEP 7 box"));
}

// --------------------------------------------------------------------------- //
// registration
// --------------------------------------------------------------------------- //
async function refreshEverything() {
  await Promise.all([reloadPrompts(), reloadPhrases(), reloadParts()]);
  attachToPromptBox();
  refreshAll();
}

app.registerExtension({
  name: "freedom.prompt_slots",

  async nodeCreated(node) {
    const cls = node.comfyClass || node.type;
    if (cls !== PROMPT_NODE && cls !== PHRASE_NODE && cls !== PARTS_NODE) return;
    installCss();
    if (cls === PARTS_NODE) {
      // Built at once, not later: the button panels sit in the MIDDLE of the
      // widget list (under each window), and they must be in place before a
      // saved workflow's values are poured back in.
      PART_SPECS.forEach((s) => buildPartsSection(node, s));
      keepPanelsOutOfSavedValues(node);
      setTimeout(refreshEverything, 0);
      return;
    }
    setTimeout(() => {
      if (cls === PROMPT_NODE) buildPromptPanel(node);
      else buildPhrasePanel(node);
      refreshEverything();
    }, 0);
  },

  // Runs once the whole workflow is on the canvas and the wires are joined up,
  // which is the earliest moment we can follow a wire to find your prompt box.
  async afterConfigureGraph() {
    setTimeout(refreshEverything, 100);
  },
});
