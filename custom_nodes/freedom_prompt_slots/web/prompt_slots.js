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

// Every box font one bigger (user, 2026-09-30). This Chrome profile has a MINIMUM
// FONT SIZE of 18 px (measured: anything asked for below 18 shows at 18), so every
// box text - ComfyUI's own fields, menus, labels, notes, and our own panels - was
// showing at 18. One bigger is therefore 19 for all of it. (Our panels' own sizes
// were also raised by 1, which only shows if that Chrome minimum is ever lowered.)
// !important because some of our panels set their size inline.
(() => {
  if (document.getElementById("freedom-fonts-plus-one")) return;
  const s = document.createElement("style");
  s.id = "freedom-fonts-plus-one";
  s.textContent =
    `.lg-node .lg-node-widgets, .lg-node .lg-node-widgets * { font-size: 19px !important; }\n` +
    `.lg-node .comfy-markdown-content, .lg-node .comfy-markdown-content * { font-size: 19px !important; }`;
  document.head.appendChild(s);
})();

// Two-choice switches (e.g. auto_save "off | on - keep every picture", "face OFF |
// face ON"): the chosen side is always green, the other side gray (user, 2026-09-30).
// ComfyUI draws them as a role=group with one button per choice; the chosen one
// carries data-state="on".
(() => {
  if (document.getElementById("freedom-toggle-colors")) return;
  const s = document.createElement("style");
  s.id = "freedom-toggle-colors";
  s.textContent =
    `.lg-node [role=group] > button[data-state="on"] { background: #2e8b3e !important; color: #fff !important; }\n` +
    // inactive lettering: a mid gray, darker than before but apart from the button gray (user, 2026-10-01: #c8c8c8 -> #e2e2e2 too bright -> #a0a0a0)
    `.lg-node [role=group] > button[data-state="off"] { background: #55575c !important; color: #a0a0a0 !important; }\n` +
    `.lg-node [role=group] > button[data-state="off"]:hover { background: #6a6c72 !important; }`;
  document.head.appendChild(s);
})();

const PROMPT_NODE = "FreedomPromptSlots";
const PHRASE_NODE = "FreedomPhraseSlots";
const PARTS_NODE = "FreedomPromptParts";
// STEP 7 split (user, 2026-09-30): each prompt box is its own node, and the
// FINAL COMBINED PROMPT is a read-only node filled by green buttons.
const SCENE_NODE = "FreedomScenePrompt";
const PHYSICAL_NODE = "FreedomPhysicalPrompt";
const FINAL_NODE = "FreedomFinalPrompt";
const PM_MARKER = "[Portrait Master's words - written at Run]";   // same as nodes.py
const SCENE_SPEC = { kind: "scene", slot: "scene_slot", name: "scene_name",
  saved: "scene_saved", box: "scene",
  title: "SCENE - pose, action, scene, camera, light, style",
  boxLabel: "the scene box", finalKey: "scene", phrase: false, shelfTitle: "Scene Shelf - pose, action, scene, camera, light, style",
  boxTitle: "Scene Prompt", boxGapPx: 36 };   // two line spaces above the typing field (user, 2026-09-30)
const PHYSICAL_SPEC = { kind: "physical", slot: "physical_slot", name: "physical_name",
  saved: "physical_saved", box: "physical",
  title: "PHYSICAL DESCRIPTION - how she looks (body, face, hair, skin, clothing)",
  boxLabel: "the physical box", finalKey: "physical", phrase: false,
  shelfTitle: "Physical Shelf - how she looks (body, face, hair, skin, clothing)",
  boxTitle: "Physical Description Prompt", boxGapPx: 36 };   // same as Scene (user, 2026-09-30)

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
  font:12px/1.35 system-ui,Segoe UI,sans-serif;color:#ddd;background:#1c1c1c;
  border:1px solid #444;border-radius:6px;padding:8px}
.fpsl-row{display:flex;flex-wrap:wrap;gap:5px}
.fpsl-btn{background:#2b2b2b;color:#ddd;border:1px solid #555;border-radius:4px;
  padding:4px 9px;cursor:pointer;font-size:11.5px;white-space:nowrap}
.fpsl-btn:hover{background:#3a3a3a;border-color:#6a8cb8}
.fpsl-btn:disabled{opacity:.4;cursor:default}
.fpsl-btn.warn{border-color:#a66;color:#fbb}
.fpsl-ask{display:flex;flex-direction:column;gap:5px;border:1px solid #c66;background:#2a1c1c;
  border-radius:5px;padding:6px}
.fpsl-ask-text{color:#fbb;font-size:12px;font-weight:600}
.fpsl-where{color:#cde3ff;font-size:11px;font-weight:600;letter-spacing:.3px}
.fpsl-status{color:#9cc4ff;font-size:11px;min-height:13px}
.fpsl-status.bad{color:#f2a0a0}
.fpsl-shelf-title{flex:none;font:700 15px system-ui,sans-serif;color:#cde3ff;padding:2px 2px 4px;
  border-bottom:1px solid #444;letter-spacing:.3px}
.fpsl-text{flex:1;width:100%;box-sizing:border-box;min-height:40px;background:#111;color:#eee;
  border:1px solid #666;border-radius:3px;font:13px/1.4 sans-serif;padding:4px;resize:none}
.fpsl-text.ro{color:#bbb;background:#181818}
/* the prompt boxes you type in get a light green frame (user, 2026-09-30) */
.fpsl-text:not(.ro){border:2px solid #90ee90}
.fpsl-green{background:#1f7a33;color:#fff;border:1px solid #39b35a;border-radius:6px;
  padding:10px 14px;cursor:pointer;font-size:14px;font-weight:700;width:100%}
.fpsl-green:hover{background:#26933e}
.fpsl-blue{background:#2b5f9e;color:#fff;border:1px solid #4a86c8;border-radius:6px;
  padding:10px 14px;cursor:pointer;font-size:14px;font-weight:700;width:100%}
.fpsl-blue:hover{background:#3a74ba}
.ffinal-text{flex:1;background:#141414;border:1px solid #3a3a3a;border-radius:4px;padding:6px;
  color:#eee;font:13px/1.45 system-ui,sans-serif;white-space:pre-wrap;word-break:break-word;
  user-select:none;-webkit-user-select:none;cursor:default;outline:none}
.ffinal-text.empty{color:#777;font-style:italic}
.ffinal-watch{font-size:12px;font-weight:600}
.ffinal-watch.ok{color:#8fd19e}
.ffinal-watch.bad{color:#f0b060}
.ffinal-last{flex:1;width:100%;box-sizing:border-box;min-height:50px;background:#181818;color:#aaa;
  border:1px solid #555;border-radius:3px;font:13px sans-serif;padding:4px;resize:none}
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

  const renamer = makeRenamer({
    button: btnRename, say,
    field: () => nativeField(node, "name"),
    current: () => shelf.prompts[slotNow() - 1]?.name || "",
    apply: async (newName) => {
      const slot = slotNow();
      setWidget(node, "name", newName);
      const result = await postJson("/freedom/promptslots/rename", { slot, name: newName });
      if (!result.ok) { say(result.error || "rename failed", true); refresh(); return; }
      shelf.prompts = result.prompts;
      refreshAll();
      say(`renamed "${result.old}" to "${shelf.prompts[slot - 1].name}" - its text is unchanged`);
    },
  });
  btnRename.onclick = () => { disarm(); renamer.click(); };

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

  const saveAser = makeRenamer({
    button: btnSaveAs, say, armedLabel: "Save as new", allowEmpty: true, requireChange: false,
    field: () => nativeField(node, "name"),
    current: () => shelf.prompts[slotNow() - 1]?.name || "",
    apply: async (newName) => {
      const text = promptBoxText();
      if (text === null) { say("could not find your STEP 7 box", true); return; }
      setWidget(node, "name", newName);
      const result = await postJson("/freedom/promptslots/saveas", { name: newName, positive: text });
      if (!result.ok) { say(result.error || "save failed", true); refresh(); return; }
      shelf.prompts = result.prompts;
      setWidget(node, "slot", result.slot);
      refreshAll();
      say(`saved as "${newName}" in slot ${result.slot}`);
    },
  });
  btnSaveAs.onclick = () => { disarm(); saveAser.click(); };

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

  // A phrase has no separate name - its words are its name. So Rename opens the
  // window above with the words selected and blinking (user, 2026-09-30); change
  // them, then Enter or "Save new name" saves them back to the same slot.
  const phraseArea = () => nativeField(node, "phrase");
  const renamer = makeRenamer({
    button: btnRename, say,
    field: phraseArea,
    current: () => shelf.phrases[slotNow() - 1] || "",
    apply: async (text) => {
      const slot = slotNow();
      const result = await postJson("/freedom/phrases/rename", { slot, text });
      if (!result.ok) { say(result.error || "rename failed", true); refresh(); return; }
      shelf.phrases = result.phrases;
      refreshAll();
      say(`phrase in slot ${slot} renamed`);
    },
  });
  const stopEditing = () => renamer.release();
  btnRename.onclick = () => { calmAll(root); renamer.click(); };

  // Save as (user, 2026-09-29): the words in the window - changed or not - go on the
  // shelf as a NEW phrase; the phrase you are dialled to stays as it was. Use Rename,
  // then change the words, then Save as, to keep both.
  const saveAser = makeRenamer({
    button: btnSaveAs, say, armedLabel: "Save as new", allowEmpty: true, requireChange: false,
    field: phraseArea,
    current: () => shelf.phrases[slotNow() - 1] || "",
    apply: async (text) => { await savePhraseAs(text); },
  });
  btnSaveAs.onclick = () => { calmAll(root); stopEditing(); saveAser.click(); };
  const savePhraseAs = async (text) => {
    if (!text) { say("the window is empty - nothing to save", true); return; }
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

  // The split boxes (Scene, Physical) have no Save phrase: the phrase shelf was
  // taken out of the workflow (user, 2026-09-30).
  // A box with a shelf title at its top has no second heading on the buttons (user, 2026-09-30).
  // Delete and Create new ask first, in a small box (user, 2026-10-01): one click
  // opens it, and nothing happens until Confirm. It sits BELOW the buttons and
  // ignores Confirm for half a second, so a double-click can never get through.
  // An in-page box, not a browser pop-up - a pop-up freezes the whole page.
  const ask = el("div", { className: "fpsl-ask" });
  const askText = el("div", { className: "fpsl-ask-text" });
  const btnYes = el("button", { className: "fpsl-btn warn", textContent: "Confirm" });
  const btnNo = el("button", { className: "fpsl-btn", textContent: "Cancel" });
  ask.append(askText, el("div", { className: "fpsl-row" }, [btnYes, btnNo]));
  ask.style.display = "none";

  root.append(...(spec.shelfTitle ? [] : [head]), where,
    el("div", { className: "fpsl-row" }, [btnLoad, btnSave, btnSaveAs, btnNew]),
    el("div", { className: "fpsl-row" },
      spec.phrase === false ? [btnRename, btnDelete] : [btnRename, btnPhrase, btnDelete]),
    ask, status);
  for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"]) {
    root.addEventListener(ev, (e) => e.stopPropagation());
  }

  const say = (message, bad) => {
    status.textContent = message || "";
    status.className = "fpsl-status" + (bad ? " bad" : "");
  };

  let pending = null;                        // what Confirm will do, and when the box opened
  const closeAsk = () => { pending = null; ask.style.display = "none"; };
  const openAsk = (message, act) => {
    askText.textContent = message;
    ask.style.display = "";
    pending = { act, at: performance.now() };
    say("");
  };
  btnYes.onclick = async () => {
    if (!pending || performance.now() - pending.at < 500) return;   // the 2nd half of a double-click
    const act = pending.act;
    closeAsk();
    await act();
  };
  btnNo.onclick = () => { closeAsk(); say("cancelled - nothing was changed"); };
  const items = () => shelf.parts[spec.kind] || [];
  const slotNow = () => Math.max(1, parseInt(widgetValue(node, spec.slot), 10) || 1);
  const boxText = () => {
    const w = widget(node, spec.box);
    if (!w) return null;
    const ta = textareaOf(w);
    return ta ? String(ta.value || "") : String(w.value || "");
  };
  // Any other shelf button closes the confirm box and stops a half-done rename.
  // (renamer and saveAser are made further down; this only runs on a click.)
  const disarm = (keep) => {
    closeAsk();
    if (keep !== renamer) renamer.cancel();
    if (keep !== saveAser) saveAser.cancel();
  };

  function refresh() {
    const slot = slotNow();
    const entry = items()[slot - 1];
    setWidget(node, spec.name, entry ? entry.name : "");
    setWidget(node, spec.saved, entry ? entry.text : "");
    // Scene and Physical: no "slot 1 of 2 saved" line (user, 2026-09-30); the
    // empty-slot and nothing-saved messages stay.
    where.textContent = entry
      ? (spec.finalKey ? "" : `slot ${slot} of ${items().length} saved`)
      : (items().length
        ? `slot ${slot} is empty - ${items().length} saved, dial down to see them`
        : "nothing saved yet - type in the box below, a name above, then Save as");
    where.style.display = where.textContent ? "" : "none";     // no empty gap
    // never switched off - on an empty slot a click makes the dial blink (user, 2026-09-30)
    btnLoad.disabled = false;
    btnSave.disabled = false;
    btnRename.disabled = false;
    btnDelete.disabled = false;
    if (waiting && entry) {                  // the dial reached a saved one: say what to press
      const f = dialField(); if (f) f.style.outline = "";
      const then = waiting; waiting = null; setTimeout(then, 0);
    }
  }

  // These buttons work on the slot the DIAL points at, so on an empty slot the dial is
  // the field that blinks 3 times and stays highlighted until it reaches a saved one.
  // Reaching it only shows a message - no button ever acts by itself later on
  // (user, 2026-10-01: a forgotten Load used to fill the box on its own).
  let waiting = null;
  const dialField = () => {
    const root = document.querySelector(`[data-node-id="${node.id}"]`);
    const row = [...(root?.querySelectorAll(".lg-node-widgets > *") || [])]
      .find((r) => (r.textContent || "").trim().startsWith(spec.slot));
    return row?.querySelector("input") || null;
  };
  const needSlot = (message, then) => {
    say(message);
    const f = dialField();
    if (f) { blinkThree(f); f.style.outline = "3px solid #ffd479"; f.style.outlineOffset = "1px"; }
    waiting = then;
  };
  const hasEntry = () => !!items()[slotNow() - 1];

  // No answer, or a garbled one, from ComfyUI is reported - never silent (user, 2026-10-01).
  let busy = false;                          // one shelf change at a time
  const post = async (action, body) => {
    let result = null;
    try { result = await postJson(`/freedom/partslots/${spec.kind}/${action}`, body); }
    catch (e) { result = null; }
    if (!result || typeof result !== "object") {
      return { ok: false, error: "ComfyUI gave no proper answer, so this may not have happened. " +
                                 "Turn the dial away and back to check." };
    }
    if (result.ok && result.items) shelf.parts[spec.kind] = result.items;
    return result;
  };
  const once = async (job) => {
    if (busy) { say("still working on the last click - wait a moment"); return; }
    busy = true;
    try { await job(); } finally { busy = false; }
  };

  btnLoad.onclick = () => {
    disarm();
    const entry = items()[slotNow() - 1];
    if (!entry) {
      needSlot("turn the dial to the saved one to load",
        () => say(`now press Load to load "${items()[slotNow() - 1].name}"`));
      return;
    }
    setWidget(node, spec.box, entry.text);
    say(`loaded "${entry.name}" into ${spec.boxLabel} - edit it there`);
  };

  btnSave.onclick = async () => {
    disarm();
    if (!hasEntry()) {
      needSlot("turn the dial to the saved one to save over",
        () => say(`now press Save (overwrite) to save over "${items()[slotNow() - 1].name}"`));
      return;
    }
    const text = boxText();
    if (text === null) { say(`could not find ${spec.boxLabel}`, true); return; }
    const slot = slotNow();
    await once(async () => {
      const r = await post("save", { slot, name: widgetValue(node, spec.name), text });
      if (!r.ok) { say(r.error || "save failed", true); return; }
      refreshAll();
      say(`slot ${slot} written over with what is in ${spec.boxLabel}`);
    });
  };

  const saveAser = makeRenamer({
    button: btnSaveAs, say, armedLabel: "Save as new", allowEmpty: true, requireChange: false,
    field: () => nativeField(node, spec.name),
    current: () => items()[slotNow() - 1]?.name || "",
    apply: async (newName) => {
      const text = boxText();
      if (text === null) { say(`could not find ${spec.boxLabel}`, true); return; }
      await once(async () => {
        setWidget(node, spec.name, newName);
        const r = await post("saveas", { name: newName, text });
        if (!r.ok) { say(r.error || "save failed", true); refresh(); return; }
        setWidget(node, spec.slot, r.slot);
        refreshAll();
        say(`saved as "${newName}" in slot ${r.slot}`);
      });
    },
  });
  btnSaveAs.onclick = () => { disarm(saveAser); saveAser.click(); };

  btnNew.onclick = () => {
    disarm();
    openAsk(`Empty ${spec.boxLabel}? What is typed there now will be lost. ` +
            "Your saved ones on the shelf stay as they are.", () => {
      setWidget(node, spec.box, "");
      const fresh = Math.min(items().length + 1, 99);
      setWidget(node, spec.slot, fresh);
      setWidget(node, spec.name, "");
      setWidget(node, spec.saved, "");
      refresh();
      say(`box emptied. You are on slot ${fresh}, which is free. Type, name it, ` +
          "then press Save as.");
    });
  };

  btnDelete.onclick = () => {
    disarm();
    if (!hasEntry()) {
      needSlot("turn the dial to the saved one to delete",
        () => say(`now press Delete to delete "${items()[slotNow() - 1].name}"`));
      return;
    }
    const slot = slotNow();
    const name = items()[slot - 1].name;
    openAsk(`Delete "${name}" (slot ${slot}) from the shelf for good? The ones below it move up a slot.`,
      () => once(async () => {
        if (items()[slot - 1]?.name !== name) {        // the shelf changed meanwhile
          say("the shelf changed before Confirm - nothing was deleted", true); return;
        }
        const r = await post("delete", { slot });
        if (!r.ok) { say(r.error || "could not delete that one", true); return; }
        setWidget(node, spec.slot, Math.min(slot, Math.max(1, items().length)));
        refreshAll();
        say(`"${r.deleted}" is gone. ${items().length} left, and anything below it ` +
            "has moved up a slot.");
      }));
  };

  btnPhrase.onclick = async () => { disarm(); await savePhrase(say); };

  const renamer = makeRenamer({
    button: btnRename, say,
    field: () => nativeField(node, spec.name),
    current: () => items()[slotNow() - 1]?.name || "",
    apply: async (newName) => {
      const slot = slotNow();
      await once(async () => {
        setWidget(node, spec.name, newName);
        const r = await post("rename", { slot, name: newName });
        if (!r.ok) { say(r.error || "rename failed", true); refresh(); return; }
        refreshAll();
        say(`renamed "${r.old}" to "${items()[slot - 1].name}" - its text is unchanged`);
      });
    },
  });
  btnRename.onclick = () => {
    disarm(renamer);
    if (!hasEntry()) {
      needSlot("turn the dial to the saved one to rename",
        () => say(`now press Rename to rename "${items()[slotNow() - 1].name}"`));
      return;
    }
    renamer.click();
  };

  // Add the buttons, then move them to sit right under this section's window.
  const domName = `freedom_parts_${spec.kind}_buttons`;
  if (spec.finalKey) makeAdjustable(node, domName, root);
  node.addDOMWidget(domName, "div", root, { serialize: false, hideOnZoom: false });
  const ws = node.widgets || [];
  const from = ws.findIndex((w) => w.name === domName);
  const after = ws.findIndex((w) => w.name === spec.saved);
  if (from !== -1 && after !== -1 && from !== after + 1) {
    const [moved] = ws.splice(from, 1);
    ws.splice(ws.findIndex((w) => w.name === spec.saved) + 1, 0, moved);
  }

  if (spec.finalKey) {
    // Split boxes (Scene, Physical): ComfyUI's own two text fields are hidden and
    // drawn by us instead, each in its own adjustable field (user, 2026-09-30).
    // Their values stay in the real widgets, so saving and the server are unchanged.
    ownTextField(node, spec.saved, `freedom_parts_${spec.kind}_window`, true,
      `Read-only. Press Load to edit this in ${spec.boxLabel}.`, "the saved one you are dialled to");
    ownTextField(node, spec.box, `freedom_parts_${spec.kind}_box`, false,
      spec.boxTitle || spec.title, `type here, then press the green button`, spec.boxGapPx);
  } else {
    whenTextarea(widget(node, spec.saved), (ta) => {
      ta.readOnly = true;
      ta.title = `Read-only. Press Load to edit this in ${spec.boxLabel}.`;
      rememberSelections(ta, `the saved ${spec.kind} window`);
    });
    whenTextarea(widget(node, spec.box), (ta) => rememberSelections(ta, spec.boxLabel));
  }

  const dial = widget(node, spec.slot);
  if (dial) {
    const original = dial.callback;
    dial.callback = function (value) {
      const r = original ? original.apply(this, arguments) : undefined;
      if (!dial.__freedomQuiet) {
        // A new slot is a different saved one: a waiting Confirm or a half-typed
        // name was meant for the old one, so both are called off (user, 2026-10-01).
        const was = pending || renamer.isArmed() || saveAser.isArmed();
        disarm();
        if (was) say("the dial moved, so that was cancelled - nothing was changed");
        setTimeout(refresh, 0);
      }
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
// STEP 7 split: adjustable fields, green buttons, FINAL COMBINED PROMPT
// (user, 2026-09-30)
// --------------------------------------------------------------------------- //

// "Adjustable": the field has its own drag handle on its bottom edge, so it can be
// made taller or shorter on its own. The height is kept in the node's properties,
// so it is saved with the workflow.
function makeAdjustable(node, name, elem, minH = 40) {
  elem.style.resize = "vertical";
  elem.style.overflow = "auto";
  // ComfyUI stretches every add-on field to share the free space evenly, which
  // overrides its own height; switching that off lets each field keep its height.
  elem.style.flex = "none";
  elem.style.minHeight = minH + "px";
  elem.style.boxSizing = "border-box";
  // A node's fields are built BEFORE its saved settings arrive, so the saved
  // heights are put back once they have (onConfigure), not here.
  rememberAdjustable(node, name, elem);
  // A height is stored only when YOU drag the handle - never because code or a
  // load changed it (that once overwrote a saved height with the starting one).
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
      setTimeout(() => { window.__freedomNoOverlap?.(node); markChanged(); }, 50);
    }, 300);
  }).observe(elem);
  return elem;
}

function markChanged() {
  // Tell ComfyUI at once, so the tab shows unsaved changes and Save keeps the change.
  app.extensionManager?.workflow?.activeWorkflow?.changeTracker?.checkState?.();
}

// Remember each adjustable field; once the node's saved settings are in, give every
// field its saved height.
function rememberAdjustable(node, name, elem) {
  (node.__adjustables = node.__adjustables || []).push([name, elem]);
  const now = node.properties?.freedom_heights?.[name];
  if (now) { elem.style.height = now + "px"; elem.__applied = Math.round(parseFloat(now)); }
  if (node.__adjHooked) return;
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

// --------------------------------------------------------------------------- //
// No overlap, ever (user, 2026-09-30). When a box grows, every box below it that
// shares its column moves down by the same amount (on the 50 grid, keeping a 50
// gap), and any frame holding them grows to fit. Boxes never move up by themselves.
// --------------------------------------------------------------------------- //
const GRID = 50, GAP = 50;
function nodeBox(n) {
  const ds = app.canvas.ds;
  const title = LiteGraph.NODE_TITLE_HEIGHT || 30;
  const el = document.querySelector(`[data-node-id="${n.id}"]`);
  const h = el ? el.getBoundingClientRect().height / ds.scale : n.size[1] + title;
  return { x0: n.pos[0], x1: n.pos[0] + n.size[0], y0: n.pos[1] - title, y1: n.pos[1] - title + h };
}
window.__freedomNoOverlap = function (grown) {
  const g = app.graph; if (!g) return;
  const a = nodeBox(grown);
  const below = g._nodes.filter((n) => n !== grown).map((n) => [n, nodeBox(n)])
    .filter(([, b]) => b.x0 < a.x1 && a.x0 < b.x1 && b.y0 >= a.y0)
    .sort((p, q) => p[1].y0 - q[1].y0);
  if (!below.length) return;
  const need = a.y1 + GAP - below[0][1].y0;          // how far the nearest one is too high
  if (need <= 0) return;
  const shift = Math.ceil(need / GRID) * GRID;
  for (const [n] of below) n.pos[1] += shift;
  // frames: any frame that held the grown box or a moved box grows to fit them all
  for (const fr of g._groups || []) {
    const [fx, fy, fw, fh] = fr._bounding;
    const inside = [grown, ...below.map(([n]) => n)].filter((n) => n.pos[0] >= fx && n.pos[0] < fx + fw);
    if (!inside.length) continue;
    const want = Math.ceil((Math.max(...inside.map((n) => nodeBox(n).y1)) + GAP - fy) / GRID) * GRID;
    if (want > fh) fr._bounding[3] = want;
  }
  g.setDirtyCanvas(true, true);
};

// ComfyUI draws its own multiline fields in this front-end and redraws them when
// the node scrolls into view, so they cannot be given a drag handle from here.
// Instead the real widget is hidden (it still holds the value that is saved and
// sent) and we draw our own text field for it, in its own adjustable box.
function ownTextField(node, widgetName, domName, readOnly, label, placeholder, gapPx = 0) {
  const w = widget(node, widgetName);
  if (!w) return;
  w.type = "hidden"; w.computeSize = () => [0, -4];
  w.options = w.options || {}; w.options.hidden = true;
  const hideNative = () => { const r = w.element || w.inputEl; if (r) { r.style.display = "none"; return true; } return false; };
  if (!hideNative()) { let n = 0; const t = setInterval(() => { if (hideNative() || ++n > 20) clearInterval(t); }, 100); }

  const root = el("div", { className: "fpsl-root" });
  const ta = el("textarea", { className: "fpsl-text", readOnly, placeholder, title: label });
  if (readOnly) ta.classList.add("ro");
  root.append(el("div", { className: "fpsl-where", textContent: readOnly ? "SAVED - " + placeholder : label }), ta);
  for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"]) root.addEventListener(ev, (e) => e.stopPropagation());
  ta.value = String(w.value ?? "");
  if (!readOnly) ta.addEventListener("input", () => { w.value = ta.value; try { w.callback?.(ta.value); } catch (e) {} node.setDirtyCanvas?.(true, true); });
  // Load, Create new and a saved workflow change the real value; show it here.
  const sync = setInterval(() => {
    if (!node.graph) { clearInterval(sync); return; }            // node was removed
    if (document.activeElement !== ta && ta.value !== String(w.value ?? "")) ta.value = String(w.value ?? "");
  }, 300);
  makeAdjustable(node, domName, root, 80);
  if (gapPx) root.style.marginTop = gapPx + "px";        // space above this field
  if (!node.properties?.freedom_heights?.[domName]) { root.style.height = (readOnly ? 130 : 200) + "px"; root.__applied = Math.round(parseFloat((readOnly ? 130 : 200))); }
  node.addDOMWidget(domName, "div", root, { serialize: false, hideOnZoom: false });
}

// --------------------------------------------------------------------------- //
// Rename in two steps (user, 2026-09-30) - every Rename button:
//   1st click: the name field gets the current name, selected, and blinks 3 times,
//   and the confirm/cancel box opens under the buttons (user, 2026-10-01).
//   Then type the new name; Enter or Confirm renames. A 2nd click does nothing.
//   Esc puts the field back and renames nothing.
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
function makeRenamer({ button, field, current, apply, say, armedLabel = "Save new name",
                       allowEmpty = false, requireChange = true }) {
  let armed = null;
  const label = button.textContent;
  const ask = askBox(button);
  const end = (restore) => {
    if (!armed) return;
    const { el: f, before, onKey } = armed;
    f.removeEventListener("keydown", onKey, true);
    if (restore) { f.value = before; f.dispatchEvent(new Event("input", { bubbles: true })); }
    armed = null;
    ask.close();
    button.textContent = label;
  };
  const confirm = async () => {
    if (!armed) return;
    const v = String(armed.el.value || "").trim();
    const cur = String(current() || "").trim();
    const after = armed.after; end(false); after?.();
    if (!v) { say?.("type a name first"); return; }
    if (requireChange && v === cur) { say?.("the name was not changed"); return; }
    await apply(v);
  };
  const cancel = () => { const after = armed?.after; end(true); after?.(); say?.("rename cancelled - the name is unchanged"); };
  const click = async () => {
    if (armed) { armed.el.focus(); return; }   // a 2nd press does nothing - the box's Confirm does it
    const f = field(); const cur = current();
    if (!f) { say?.("could not find the name field", true); return; }
    if (!cur && !allowEmpty) { say?.("there is nothing here to rename", true); return; }
    const before = f.value;
    const after = f.readOnly ? (() => { f.readOnly = true; }) : null;   // a read-only window opens for typing
    f.readOnly = false;
    if (cur) { f.value = cur; f.dispatchEvent(new Event("input", { bubbles: true })); }
    f.focus(); f.select?.(); blinkThree(f);
    const onKey = (e) => {
      if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); confirm(); }
      else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); cancel(); }
    };
    f.addEventListener("keydown", onKey, true);
    armed = { el: f, before, onKey, after, at: performance.now() };
    ask.open(`${label}: type the name in the name box, then press Confirm.`, confirm, () => cancel());
    say?.("type the name, then press Confirm (or Enter). Cancel or Esc stops.");
  };
  // release: stop waiting without renaming and without putting the old text back
  const release = () => { const after = armed?.after; end(false); after?.(); };
  return { click, release, isArmed: () => !!armed, cancel: () => armed && cancel() };
}

// A text field ComfyUI draws itself (Vue): found on the page by its widget name.
function nativeField(node, widgetName) {
  const w = widget(node, widgetName);
  const own = w && (w.element || w.inputEl);
  if (own && /INPUT|TEXTAREA/.test(own.tagName)) return own;
  const root = document.querySelector(`[data-node-id="${node.id}"]`);
  return root?.querySelector(`input[placeholder="${widgetName}"], input[aria-label="${widgetName}"], `
    + `textarea[placeholder="${widgetName}"], textarea[aria-label="${widgetName}"]`) || textareaOf(w);
}

const firstNode = (type) => graphNodes(type)[0] || null;
const cleanPart = (s) => String(s ?? "").trim();

// What each part of the final prompt would be RIGHT NOW, read from the page.
// Her trigger word, e.g. "(lorasusana:1.1)" - only in trained-face mode, and not when the Face
// Shelf's strength is 0. Its weight comes from the Face Shelf's trigger_weight dial.
function liveTrigger() {
  if (widgetValue(firstNode("FreedomFaceSource"), "mode") !== "trained_face") return "";
  const shelfNode = firstNode("FreedomFaceShelf");
  if (Number(widgetValue(shelfNode, "strength")) === 0) return "";
  return cleanPart(shelfNode?.__ffs?.trigEl?.dataset?.text);
}

// Her trigger word lives in the Summary Signal part, right after the model's text (user,
// 2026-10-01, choice 2: shown locked in 7c; the weight is still set on the Face Shelf). So the
// Summary Signal part is: model text, trigger word, your words. Random-face mode is unchanged:
// Portrait Master's words go in the face part, written at Run.
function liveParts() {
  const live = { front: "", face: "", physical: "", scene: "", model: "", trig: "" };
  const sig = firstNode("FreedomCheckpointFrontText")?.__cfp;
  const mode = widgetValue(firstNode("FreedomFaceSource"), "mode");
  const trig = liveTrigger();
  if (sig) {
    live.model = sig.enabled() && sig.front ? cleanPart(sig.front) : "";
    live.trig = trig;
    live.front = [live.model, trig, cleanPart(sig.words())].filter(Boolean).join(", ");
  }
  if (mode === "trained_face") {
    live.face = sig ? "" : trig;                // no Summary Signal box: as before
  } else if (mode === "random_face") {
    live.face = PM_MARKER;
  }
  const boxOf = (type, name) => {
    const n = firstNode(type); const w = widget(n, name);
    if (!w) return "";
    const ta = textareaOf(w);
    return cleanPart(ta ? ta.value : w.value);
  };
  live.physical = boxOf(PHYSICAL_NODE, "physical");
  live.scene = boxOf(SCENE_NODE, "scene");
  return live;
}

const FINAL_KEYS = ["front", "face", "physical", "scene"];      // the user's order
const PART_NAMES = { front: "Summary Signal", face: "trigger word / Portrait Master",
                     physical: "Physical Description", scene: "Scene" };

function finalParts(node) {
  try { const p = JSON.parse(widgetValue(node, "final_parts") || "{}"); return p && typeof p === "object" ? p : {}; }
  catch (e) { return {}; }
}
// The blue button under the final box swaps Physical and Scene (user, 2026-10-02); the choice
// is kept in the saved parts as "order", which the server reads too (nodes.py join_final).
const sceneFirst = (p) => (p && p.order) === "scene_first";
const orderOf = (p) => sceneFirst(p) ? ["front", "face", "scene", "physical"] : FINAL_KEYS;
const joinParts = (p) => orderOf(p).map((k) => cleanPart(p[k])).filter(Boolean).join(", ");

// Pressing a green button: that box's text goes into the final box. The face
// part (trigger word / Portrait Master marker) has no box of its own, so every
// green button refreshes it too.
function updateFinal(key) {
  const node = firstNode(FINAL_NODE);
  if (!node) return "There is no FINAL COMBINED PROMPT box in this workflow.";
  const live = liveParts();
  const parts = finalParts(node);
  parts[key] = live[key];
  if (key === "front") { parts.model = live.model; parts.trig = live.trig; }
  parts.face = live.face;
  // Every green button keeps her trigger word current (as it always kept the face part current),
  // without taking in Summary Signal words that its own green button has not been pressed for.
  if (key !== "front") refreshTrigger(parts, live);
  setWidget(node, "final_parts", JSON.stringify(parts));
  node.__final?.render();
  return null;
}

// Put the live trigger word into the saved Summary Signal part, in place of the one stored
// there (or after the model's text when none was stored), leaving the rest of it alone.
function refreshTrigger(parts, live) {
  if (!firstNode("FreedomCheckpointFrontText")) return;
  const old = cleanPart(parts.trig), now = cleanPart(live.trig);
  if (old === now && parts.trig !== undefined) return;
  let front = cleanPart(parts.front);
  if (old && front.includes(old)) {
    front = front.replace(old, now);
  } else if (now) {
    const model = cleanPart(parts.model !== undefined ? parts.model : live.model);
    front = model && front.startsWith(model)
      ? model + ", " + now + front.slice(model.length)
      : (front ? now + ", " + front : now);
  }
  parts.front = front.replace(/(\s*,\s*){2,}/g, ", ").replace(/^\s*,\s*|\s*,\s*$/g, "");
  parts.trig = now;
}
window.__freedomFinal = { update: updateFinal, liveParts, liveTrigger };

// The big green button under a prompt box.
function greenButton(node, name, key) {
  const root = el("div", { className: "fpsl-root" });
  const btn = el("button", { className: "fpsl-green", textContent: "Update the FINAL COMBINED PROMPT" });
  const msg = el("div", { className: "fpsl-status" });
  root.append(btn, msg);
  for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"]) root.addEventListener(ev, (e) => e.stopPropagation());
  btn.onclick = () => {
    const err = updateFinal(key);
    msg.textContent = err || `done - the FINAL COMBINED PROMPT now has this box's text (${new Date().toLocaleTimeString()})`;
    msg.className = "fpsl-status" + (err ? " bad" : "");
  };
  makeAdjustable(node, name, root);
  node.addDOMWidget(name, "div", root, { serialize: false, hideOnZoom: false });
}

// STEP 7f - the final box, its watcher line, and the Prompt Watcher field.
function buildFinal(node) {
  const pw = widget(node, "final_parts");
  if (pw) {                                   // the saved parts field stays, hidden
    pw.type = "hidden"; pw.computeSize = () => [0, -4];
    whenTextarea(pw, (ta) => { const box = ta.closest(".dom-widget, .comfy-multiline-input") || ta; box.style.display = "none"; ta.style.display = "none"; });
  }
  const top = el("div", { className: "fpsl-root" });
  top.innerHTML = `<div class="fpsl-where">FINAL COMBINED PROMPT - what goes to the engine at Run</div>
    <div class="fpsl-status">Read-only. Only the green buttons change it. Order: Summary Signal (the model's text, her trigger word in trained-face mode, your words), Portrait Master's words in random-face mode, Physical Description, Scene (the blue button below swaps those two).</div>
    <div class="ffinal-text"></div>`;
  const text = top.querySelector(".ffinal-text");
  // Closed to the mouse and keyboard: no clicking in, no selecting, no typing. A
  // plain block with no tabindex can never take the cursor.
  for (const ev of ["mousedown", "pointerdown", "keydown", "focus", "selectstart", "copy", "cut", "paste", "contextmenu", "dblclick"])
    text.addEventListener(ev, (e) => { e.preventDefault(); e.stopPropagation(); }, true);
  makeAdjustable(node, "freedom_parts_final_text", top, 120);
  node.addDOMWidget("freedom_parts_final_text", "div", top, { serialize: false, hideOnZoom: false });

  // Blue button right under the final box (user, 2026-10-02, choice 1): each click swaps
  // Physical Description and Scene at once; the line under it says which order is in use.
  // Saved with the workflow (it lives in the final box's own saved parts).
  const swap = el("div", { className: "fpsl-root" });
  const swapBtn = el("button", { className: "fpsl-blue", textContent: "Switch the order of the Scene Prompt and the Physical Prompt" });
  const swapLine = el("div", { className: "fpsl-status" });
  swap.append(swapBtn, swapLine);
  for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"]) swap.addEventListener(ev, (e) => e.stopPropagation());
  const showOrder = () => {
    swapLine.textContent = sceneFirst(finalParts(node))
      ? "Order now: ... Scene Prompt, then Physical Description."
      : "Order now: ... Physical Description, then Scene Prompt.";
  };
  swapBtn.onclick = () => {
    const parts = finalParts(node);
    if (sceneFirst(parts)) delete parts.order; else parts.order = "scene_first";
    setWidget(node, "final_parts", JSON.stringify(parts));
    markChanged();
    node.__final?.render();
    showOrder();
  };
  makeAdjustable(node, "freedom_parts_final_order", swap, 60);
  node.addDOMWidget("freedom_parts_final_order", "div", swap, { serialize: false, hideOnZoom: false });

  const watch = el("div", { className: "fpsl-root" });
  const line = el("div", { className: "ffinal-watch" });
  watch.append(el("div", { className: "fpsl-where", textContent: "WATCHER - is every box in the final prompt?" }), line);
  makeAdjustable(node, "freedom_parts_final_watch", watch, 50);
  node.addDOMWidget("freedom_parts_final_watch", "div", watch, { serialize: false, hideOnZoom: false });

  const pwBox = el("div", { className: "fpsl-root" });
  pwBox.innerHTML = `<div class="fpsl-where">PROMPT WATCHER - what the engine got on the last run</div>
    <textarea class="ffinal-last" readonly placeholder="Run a picture to see here exactly what the engine got."></textarea>`;
  for (const ev of ["pointerdown", "wheel", "contextmenu", "keydown"]) pwBox.addEventListener(ev, (e) => e.stopPropagation());
  makeAdjustable(node, "freedom_parts_final_last", pwBox, 90);
  if (!node.properties?.freedom_heights?.freedom_parts_final_last) { pwBox.style.height = "160px"; pwBox.__applied = 160; }
  node.addDOMWidget("freedom_parts_final_last", "div", pwBox, { serialize: false, hideOnZoom: false });

  const render = () => {
    const parts = finalParts(node);
    const joined = joinParts(parts);
    text.textContent = joined || "(empty - press a green button on a prompt box)";
    text.classList.toggle("empty", !joined);
    showOrder();
  };
  const check = () => {
    const parts = finalParts(node), live = liveParts();
    const stale = FINAL_KEYS.filter((k) => cleanPart(parts[k]) !== cleanPart(live[k]));
    if (!stale.length) { line.textContent = "Up to date - the final prompt matches every box."; line.className = "ffinal-watch ok"; return; }
    // Only her trigger word changed inside the Summary Signal part? Any green button fixes that.
    const t = { ...parts }; refreshTrigger(t, live);
    const onlyTrigger = cleanPart(t.front) === cleanPart(live.front);
    // one note for everything any green button fixes (her trigger word / Portrait Master's slot)
    const anyBtn = stale.filter((k) => k === "face" || (k === "front" && onlyTrigger));
    const tips = (anyBtn.length ? ["her trigger word / Portrait Master changed - press any green button"] : [])
      .concat(stale.filter((k) => !anyBtn.includes(k)).map((k) => `${PART_NAMES[k]} changed - press its green button`));
    line.textContent = "Out of date: " + tips.join("; ") + ".";
    line.className = "ffinal-watch bad";
  };
  node.__final = { render, check, last: pwBox.querySelector(".ffinal-last") };
  render(); check();
  const timer = setInterval(() => { if (!node.graph) { clearInterval(timer); return; } render(); check(); }, 500);
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

  async setup() {
    // The Prompt Watcher field in STEP 7f: what the engine got on the last run.
    const { api } = await import("../../scripts/api.js");
    api.addEventListener("executed", ({ detail }) => {
      const out = detail?.output || {};
      const n = app.graph?.getNodeById?.(Number(detail?.node));
      if (out.finished_prompt && n?.comfyClass === FINAL_NODE && n.__final)
        n.__final.last.value = out.finished_prompt[0] ?? "";
    });
  },

  async nodeCreated(node) {
    const cls = node.comfyClass || node.type;
    if (cls === SCENE_NODE || cls === PHYSICAL_NODE) {
      installCss();
      const spec = cls === SCENE_NODE ? SCENE_SPEC : PHYSICAL_SPEC;
      if (spec.shelfTitle) {
        // The shelf's title, at the very top, above the slot dial (user, 2026-09-30).
        const head = el("div", { className: "fpsl-shelf-title", textContent: spec.shelfTitle });
        node.addDOMWidget(`freedom_parts_${spec.kind}_heading`, "div", head, { serialize: false, hideOnZoom: false });
      }
      buildPartsSection(node, spec);
      greenButton(node, `freedom_parts_${spec.kind}_update`, spec.finalKey);
      // Reading order: dial, name, saved window, shelf buttons, the box, green button.
      // (The two hidden real fields keep their nodes.py order, which is what is saved.)
      const want = [`freedom_parts_${spec.kind}_heading`, spec.slot, spec.name, spec.saved, `freedom_parts_${spec.kind}_window`,
        `freedom_parts_${spec.kind}_buttons`, spec.box, `freedom_parts_${spec.kind}_box`,
        `freedom_parts_${spec.kind}_update`];
      node.widgets.sort((a, b) => {
        const ia = want.indexOf(a.name), ib = want.indexOf(b.name);
        return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
      });
      keepPanelsOutOfSavedValues(node);
      setTimeout(refreshEverything, 0);
      return;
    }
    if (cls === FINAL_NODE) {
      installCss();
      buildFinal(node);
      keepPanelsOutOfSavedValues(node);
      return;
    }
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
