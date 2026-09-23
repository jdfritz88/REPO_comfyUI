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
const shelf = { prompts: [], phrases: [] };
const panels = [];                       // every panel refreshes when anything changes

async function reloadPrompts() {
  try { shelf.prompts = (await getJson("/freedom/promptslots/list")).prompts || []; }
  catch (e) { shelf.prompts = []; }
}

async function reloadPhrases() {
  try { shelf.phrases = (await getJson("/freedom/phrases/list")).phrases || []; }
  catch (e) { shelf.phrases = []; }
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

  root.append(where,
    el("div", { className: "fpsl-row" }, [btnLoad, btnSave, btnSaveAs, btnNew]),
    el("div", { className: "fpsl-row" }, [btnPhrase, btnDelete]),
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
    btnDelete.disabled = !entry;
  }

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
  const btnDelete = el("button", { className: "fpsl-btn warn", textContent: "Delete" });

  root.append(where,
    el("div", { className: "fpsl-row" }, [btnCopy, btnSave, btnDelete]),
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
    btnDelete.disabled = !phrase;
  }

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
  await Promise.all([reloadPrompts(), reloadPhrases()]);
  attachToPromptBox();
  refreshAll();
}

app.registerExtension({
  name: "freedom.prompt_slots",

  async nodeCreated(node) {
    const cls = node.comfyClass || node.type;
    if (cls !== PROMPT_NODE && cls !== PHRASE_NODE) return;
    installCss();
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
