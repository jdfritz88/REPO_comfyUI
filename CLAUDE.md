# REPO_comfyUI — working notes for Claude

## Speak in elementary school language for adults — always (user, 2026-09-26)

SPEAK IN ELEMENTARY SCHOOL LANGUAGE FOR ADULTS. ALWAYS. THIS RULE APPLIES TO
EVERY REPLY, EVERY QUESTION, EVERY OPTION, EVERY SUMMARY, EVERY LOG ENTRY
WRITTEN FOR ME, AND EVERY PAGE OR DOCUMENT MADE FOR ME.

a) Use short, plain words and short sentences. Say what a thing DOES, in terms
   of the app and what I see on screen, not how the code is built.
b) TECHNICAL TERMS AND COLLEGE-LEVEL WORDS: avoid them when a plain word does
   the job. When one is truly needed, say it, then explain it right there in
   everyday words ("threshold - the score a face must reach to count as her").
   File paths and code names may be given so I can find things, but only after
   the plain explanation, never instead of it.
c) GIVE CONTEXT, NOT JUST INSTRUCTIONS. Say what a thing is for, why it
   matters, and what happens if there is too much or too little of it.
   Not: "use this water on the plant."
   But: "giving the plant water and sunlight helps it grow, but too much of
   either can harm it."
d) Explain every new idea the first time it comes up, with an everyday example
   ("this works like...").
e) Numbers get their meaning next to them ("0.44 - the score a face needs to
   count as her").
f) Adults, not children: plain does not mean babyish. No talking down, no
   cheerleading, no filler.
g) Before sending, re-read the reply as someone who knows nothing about code.
   If any sentence would make them ask "what does that mean?" or "why does
   that matter?", rewrite it.
h) If I say I don't understand, the next reply explains it again in simpler
   words with more context. It does not repeat the same wording, and it does
   not pile on more technical detail.

## Face tool: read the user's rules first (user, 2026-09-26)

Before changing anything in the face tool (`face_training/` — the search, the review
page, the Face Tool window), read **`face_training/FACE_TOOL_RULES.md`**. It is the
user's standing rule list. Any new face-tool rule the user gives goes into that file in
the same session, with its date. If the code disagrees with a rule, tell the user; never
quietly change either to make them match.

## Node-group layout: description, then packages, then the panel (user, 2026-09-26/27)

**These are GUIDELINES, not fixed rules (user, 2026-09-29).** They give the usual
order, but Claude adjusts each node group as needed so its nodes read in natural
order - a group with extra nodes (hints, notes, a second panel) simply gets the
next letters in the order a person reads them. Do not force a group into the
pattern below, and do not skip or reserve letters to make it fit. When a group
changes, re-letter it top to bottom in natural order. This file is not static:
update these guidelines whenever the user refines them.

**Hints count as description-type notes.** Anything that explains or advises
(a description, a hint box, the checkpoint hints, the "7b Summary Signal" box)
goes right after the group's description, in reading order. Example the user
gave for STEP 7: 7a description, 7b Summary Signal, 7c the next hint (the
checkpoint hints), then the rest of the group follows on.

The usual order, as a starting point:

Every workflow step (node group) where the user clicks, types or picks something
follows this order, going forward. Think of it like a form: first the
instructions, then the buttons that fill or reset the form, then the form itself.

- **Column 1, top to bottom:**
  - **#a — the description note.** What this step does and why it matters.
  - **#b — switches, or the preset / reset / save packages.** The on/off
    switches and the buttons that load, save or reset settings.
  - **#c — the control panel itself.** The shelf, the dials, the prompt boxes —
    whatever the user actually works with. (The user wrote "#v"; they confirmed
    on 2026-09-27 that they meant #c.)
- **The next column repeats the same order with the next letters:** #d
  description, #e switches or packages, #f panel — then #g, #h, #i, and so on.
- **The prompt saver/loader and the phrase saver/loader are separate** — not one
  shared package. In STEP 7 they already were separate nodes; the user chose
  (2026-09-27) to keep them as they are and only re-letter them (see below).
- Node titles carry the step and letter, e.g. `STEP 3a`, `STEP 3b`, `STEP 3c`.
  STEP 3 in `Freedom_bigLust_SDXL v09.json` was the first step laid out this way
  (3a note, 3b face shelf with its recipes package kept inside, 3c face LoRA
  stack — the user chose to keep recipes inside the shelf node).
- STEP 7 (v09, user 2026-09-27): its save/load buttons live inside its panels,
  so each column is only a note and a panel. The user chose plain lettering with
  no gaps: 7a description note, 7b prompt boxes, 7c phrase note, 7d phrase node.
  The prompt and phrase nodes themselves were kept as they are (already
  separate). This is STEP 7's choice, not a rule for every step.
  Since 2026-09-29 (Q72 = 1) the checkpoint front-text node IS "7b Summary Signal"
  (one node: the model's own text, then the user's words, all on page 1). STEP 7
  now reads 7a description, 7b Summary Signal, 7c prompt boxes, 7d phrase note,
  7e phrases. When the checkpoint hints are built they go in as 7c and the
  letters after them move down. Record: `logs/summary_signal_2026-09-29.md`.
- Layout changes go into a new workflow version, not the one the user is working
  in (v09 was made for STEP 3 because the user was working in v08).

## Save packages: nothing saves by itself, and every package has "Save as" (user, 2026-09-29)

- **Only a Save button may change a stored preset or entry.** Changing a dial, a box or a
  dropdown must never save anything by itself. Portrait Master's own "save preset" switch is
  kept off for this reason (`freedom_portrait_control` switches it off in every job and shows
  it off and locked).
- **Every save / edit / delete package in the workflow has a "Save as"** as well as Save, so a
  changed version can be kept without replacing the old one. A new package gets one from the start.
- STEP 4a has one menu (no "In charge" dropdown): "Use the dials (no 4a preset)", saved presets
  (they load unlocked - they only fill dials you have not changed), then the three built-in z_
  choices. Every entry has a description beneath the menu; an entry without one says
  "needs description". Record: `logs/checkpoint_front_text_2026-09-29/LOG.md`.
- 4b-4g the same way (Q66 = 1): no "In charge" row; each node's own menu decides - "Use the
  dials (no preset)", or a saved preset that loads unlocked - with a description beneath every
  entry. Portrait Master's own presets are read-only (their descriptions live in our
  `builtin_descriptions.json`). Record: `logs/pm_node_menus_merged_2026-09-29.md`.

## Every ComfyUI log lives in `logs/` — write it there, never route it later

Standing rule from the user (decided 2026-09-18, repeated 2026-09-24): anything
produced by improving a developer's app — new files, logs, outputs — lives in
our repo, never in theirs. For logs that means **`REPO_comfyUI\logs\`** — the
kobold launcher's ComfyUI log included: since 2026-09-24 `launcher.py` writes it to
`REPO_comfyUI\logs\comfyui.log` (the user starts ComfyUI from the launcher; all its
data lands here). One decided exception: the mobile frontend's `user\default\mobile-debug.log`
stays where it is (user, 2026-09-24) — it can only be moved by exposing `logs\` over
ComfyUI's HTTP API. Do not move it or ask again.

- **Do** point every writer at `logs\` at the source. Fix the code or the
  command that writes the log; do not write it elsewhere and move it afterwards.
- **When Claude starts ComfyUI directly**, redirect its output there:
  `-RedirectStandardOutput "F:\Apps\freedom_system\REPO_comfyUI\logs\comfyui_<yyyy-mm-dd>_<hhmm>_stdout.log"`
  and the same for stderr. Never to the session scratchpad.
- **Session records, monitor captures, test captures, rollback records** go in
  `logs\` (a dated subfolder for a session's raw files is fine).
- **Do not** leave ComfyUI logs at the repo root, in `user\`, or in a temp folder.
- **CP1/CP2/CP4 Monitor log for this repo** is `logs\REPO_comfyUI_Monitor_LOG.md`,
  not the repo root the standards files name. Append there.
- **Exception — the face tool's runtime logs live with the person** (user,
  2026-09-26): logs written while the face tool is *used* — search, review page,
  training (whole-run and per-job), big library runs — go in that person's own
  `_face_profiles\<person>\logs\` folder, as they would for a customer who bought
  and installed the app. `logs\` is for *developing* the app (session records,
  tests, audits). Nothing about one person is shared with another
  (`face_training\FACE_TOOL_RULES.md`).
- AvatarAI's ComfyUI stderr goes to
  `logs\avatarai_comfyui_server_stderr.log` (`REPO_avatarAI\...\expression_editor.py`).

## A ComfyUI browser tab whose title starts with an asterisk

**Recognise it:** a Chrome tab titled `*<workflow name> - ComfyUI`. The leading
asterisk means the frontend has that workflow flagged as modified. Trying to
navigate or close it is refused with Chrome's native "Leave site? Changes you
made may not be saved." dialog, which browser automation cannot dismiss.

**Do not work around this by opening a fresh tab and carrying on.** That was the
habit before 2026-09-23, it was repeated across sessions, and a stale tab had
already overwritten `Freedom_bigLust_SDXL v06.json` with an older version once.
Deal with the tab.

**Background, in short:** the dialog cannot be dismissed from outside the page.
Chrome DevTools could do it (`Page.handleJavaScriptDialog`), but since Chrome
136 `--remote-debugging-port` only works with a non-default `--user-data-dir`,
so it cannot attach to the John Doe profile. That is why the procedure below
works inside ComfyUI instead.

### Why it happens — read from the shipped source, frontend 1.51.9

`src/components/dialog/UnloadWindowConfirmDialog.vue` registers the only
`beforeunload` handler that blocks unload:

```js
if (settingStore.get('Comfy.Window.UnloadConfirmation') &&
    workflowStore.modifiedWorkflows.length > 0) {
  event.preventDefault()
  return true
}
```

- `Comfy.Window.UnloadConfirmation` defaults to `true` (default flipped to true
  in frontend 1.7.12) and is **not** present in
  `user/default/comfy.settings.json` here, so it is running on that default.
- `modifiedWorkflows` is `computed(() => workflows.value.filter(w => w.isModified))`
  in `workflowStore.ts`, over **every known workflow, not just the open ones**.

### The real danger is a save, not a close

A save from a stale tab is a blind overwrite. `comfyWorkflow.ts` calls
`super.save({ force: true })`, and the backend `post_userdata` in
`app/user_manager.py` only checks whether the file exists — it never compares
modification times. So a stale tab clobbers a newer file the moment anything in
it triggers a save.

What currently prevents that happening on its own: `Comfy.Workflow.AutoSave`
defaults to `off` and is not set here, and `Comfy.Workflow.Persist` is set to
`false` here. It takes a human pressing Save, or clicking "Save" in the dialog
below. **Never click Save in a stale tab.**

### Tested response — do this

1. Inspect the tab first, read-only. This is allowed and does not trip the
   dialog:

   ```js
   const ws = window.app.extensionManager.workflow
   ws.modifiedWorkflows.map(w => w.path)   // what is flagged
   ws.openWorkflows.map(w => w.path)       // what is actually open
   ws.activeWorkflow.path
   window.app.graph._nodes.length          // 0 means nothing on the canvas
   ```

2. Hover the workflow tab in ComfyUI's own top bar so its close button appears,
   then click that X.

3. ComfyUI shows its **own** dialog — "Save Changes?", listing the file, with
   buttons **Close anyway** and **Save**. This is an ordinary page element, so
   automation can click it, unlike Chrome's native dialog. **Click "Close
   anyway". Never "Save".**

Verified on 2026-09-23: this writes nothing to disk. Afterwards the workflow
file was byte-identical to the committed version with an unchanged timestamp.
Once the workflow is closed in that tab, that tab can no longer overwrite it,
which is the outcome that matters.

### Standing authorisation: close and force-reload tabs without asking

Granted by the user on 2026-09-23, in these words: Claude needs "detailed
instructions to force close tabs when you (claude) need or want to close them
without asking my permission."

**You do not ask permission to close, reload or force-navigate a ComfyUI tab.**
Not for a stale tab, not for a tab behind the "Leave site?" dialog, not for one
you opened yourself. Asking was the old failure: it stalled the work and put a
decision on the user that they have now handed over for good. Use
`navigate` with `force: true` when the ordinary navigation is refused, and
`tabs_close_mcp` for tabs you are finished with.

Do this in order every time, so the authorisation is used well rather than
blindly:

1. **Look first, read-only** (the check in "Tested response" above). It costs one
   call and cannot trip any dialog. This is not asking — never turn it into a
   question.
2. **If a workflow is open and flagged modified, close it in-app first** with
   the X and **"Close anyway"**. This writes nothing to disk and it is what
   makes the force safe: after it, the tab holds nothing that can overwrite a
   file. Never click "Save".
3. **Then force.** `navigate` with `force: true`, or close the tab.
4. **Say what was discarded afterwards** — which workflow, how many nodes were
   on the canvas, and that the file on disk was left alone. A one-line report,
   not a request.

Do not turn the confirmation setting off — see "Keep the unsaved-changes
warning on" below.

### Two tested limits — do not write these up as working

- **The Shift shortcut does not work from automation.** The app's own hint reads
  "Hold Shift to close without prompt", and the source gates it on
  `warnIfUnsaved: !workspaceStore.shiftDown`. But a synthetic click carrying a
  shift modifier does not set that state — the dialog appeared anyway. Use
  "Close anyway". Shift works for a human pressing a real key.
- **Closing the workflow does NOT free the browser tab.** Because
  `modifiedWorkflows` spans all known workflows, the closed workflow keeps its
  `isModified` flag and Chrome's "Leave site?" dialog still fires. Tested
  directly: after "Close anyway", navigation was still refused. Freeing the tab
  needs a forced navigation — see the standing authorisation above. Do not ask
  for it.

### Keep the unsaved-changes warning on

- **Do not** set `Comfy.Window.UnloadConfirmation` to `false` in
  `user/default/comfy.settings.json`. The user decided on 2026-09-23 to keep it
  on, as a guard against losing real unsaved work.
- **Do not** ask the user about turning it off.
- **Handle** the dialog with the procedure above, every time.

### Do not trust the asterisk

- **Do not** assume an asterisk tab holds real edits. ComfyUI marks workflows
  as modified even when nobody touched them (ComfyUI#7475).
- **Check** what is flagged with step 1 of "Tested response", then close it with
  "Close anyway". **Never** click "Save".

## Opening ComfyUI on 127.0.0.1 from Claude in Chrome — the launch-page hop

**Proven 2026-09-24. Use this every time. Do not use the Tailscale address —
the user has ruled it out.** Full record:
`logs/comfyui_403_cross_site_guard_and_launchpad_hop_2026-09-24.md`.

### Recognise the problem

Any of these, in a Claude in Chrome tab pointed at `http://127.0.0.1:8188/`
(or `localhost:8188`):

- `get_page_text` / `screenshot` fail with "Frame with ID 0 is showing error page"
- `document.title` is just `127.0.0.1`, and `window.app` is undefined
- a Windows-MCP screenshot of the real Chrome window shows
  **"Access to 127.0.0.1 was denied — HTTP ERROR 403"**

### Why it happens — do not re-derive this

1. Every page load the extension starts (`navigate`, which uses
   `chrome.tabs.update`) carries `Sec-Fetch-Site: cross-site`. Measured with a
   header-echo server, from new and existing tabs.
2. ComfyUI's own anti-CSRF guard, `app_cabinet/comfyui/server.py:162-165`,
   returns an empty **403** for `Sec-Fetch-Site: cross-site` and logs nothing.
   `curl -H "Sec-Fetch-Site: cross-site" http://127.0.0.1:8188/` → 403, 0 bytes.
3. Chrome only sends `Sec-Fetch-*` headers to loopback/HTTPS addresses, which
   is why Tailscale and LAN addresses were never blocked.

It is **not** the Windows firewall, **not** the extension's site permissions,
and **not** Chrome's "Insecure content" setting. All three were checked.

### The procedure

1. **Start a launch page** on another loopback port, serving an empty folder,
   in the background:

   ```bash
   mkdir -p "<scratchpad>/launchpad_empty"
   python -m http.server 8190 --bind 127.0.0.1 --directory "<scratchpad>/launchpad_empty"
   ```

   Check first that 8190 is free (`netstat -ano | grep ":8190 "`); pick
   another port if not. Always bind to `127.0.0.1`, never to a network address.
2. **Open it with the extension:** `navigate` to `http://127.0.0.1:8190/`.
3. **Hop from inside the page** with `javascript_tool` on that tab:

   ```js
   location.href = 'http://127.0.0.1:8188/'
   ```

   A load started by a page on 127.0.0.1 is not tagged `cross-site`, so the
   guard lets it through.
4. **Confirm it loaded:** after a few seconds, `javascript_tool`:
   `({title: document.title, hasApp: !!window.app})`, which should give the
   ComfyUI title and `hasApp: true`.
5. **Stop the launch-page server.** It is only needed for the hop.
6. Before loading a workflow, follow the caching rule in the root `CLAUDE.md`
   and the asterisk-tab procedure above.

### Rules that go with it

- **Never use the extension's `navigate` on `127.0.0.1:8188` again inside that
  tab**, and never reload it with the extension. That load is `cross-site` and
  gets the 403 again. To reload, repeat the hop.
- **Do not weaken ComfyUI's guard.** Starting with `--enable-cors-header` or
  editing `server.py` were offered and **rejected by the user on 2026-09-24**.
  The hop needs neither.
- **Similar problem on another local app** (any `127.0.0.1` page that works
  when typed by hand but fails in a Claude in Chrome tab): first
  `curl -s -o /dev/null -w "%{http_code}" -H "Sec-Fetch-Site: cross-site" -H "Sec-Fetch-Mode: navigate" http://127.0.0.1:<port>/`.
  If that returns 403 and the same request without the header returns 200, it
  is this same guard pattern, and the same hop works with that app's port in
  place of 8188.
