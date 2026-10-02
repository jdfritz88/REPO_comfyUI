# Session record, 1-2 October 2026: last night's crash, the STEP 7 shelves, confirm boxes everywhere, bigger resize handles, STEP 6, the on/off pairs, the missing letters, the face likeness hunt, her trigger word in the Summary Signal, the 12b viewer's buttons and the order switch

This is the full record of everything done in the session of 1 October 2026 (about 12:00 on 1 Oct to 00:45 on 2 Oct),
after commit `22d2c8a` (30 Sep, 20:07, "New Freedom_SDXL_v01 workflow, STEP 7 split into its own prompt
boxes, and a picture viewer with arrows"). It was committed and pushed at the end (section 28). It is
written so someone who was not there can follow every step, every decision, every mistake and every
loose end. A shorter log of the button work also exists, `logs/confirm_box_buttons_2026-10-01.md`; this
file repeats its important parts and adds everything else.

**Where things ended (2 Oct, about 00:45):** the current workflow is `user/default/workflows/Freedom_SDXL_v02.json` (the user's own save of 1 Oct 23:47:58; Claude never wrote it after 21:10). New workflow versions are no longer made (section 15). ComfyUI is running, started by Claude at 00:38 on 2 Oct (process 36964, log `logs/comfyui_2026-10-02_0038_*.log`), not by the kobold launcher. Everything here was committed and pushed at the end (section 28).

Contents
1. Where things stood at the start
2. Last night's crash: were there any error logs after 10pm?
3. "Make the shelf preview boxes read-only" - and finding they already were
4. Looking for weak spots in the STEP 7 shelves
5. Fixing the STEP 7 shelves: one click, then a confirm/cancel box
6. Every "press again" button in the workflow gets the same box
7. Portrait Master's Delete buttons: who made them, and adding the box
8. Weak spot 5 became: bigger resize handles on boxes and frames
9. The first version of this record
10. Restarting ComfyUI and closing the extra tabs
11. STEP 6 lettering (6a / 6b / 6c) and the LoRA stack's All OFF | All ON
12. The gray-side lettering, first attempt (too bright), and "which workflow is current?"
13. The 6a note's wording brought up to date
14. Darker gray-side lettering, the FaceDetailer's repaint OFF | ON, and the missing letters
15. "Stop creating new versions": v03 folded into v02 and deleted
16. The plumbing boxes stay without letters
17. What went wrong, and what was learned
18. Every file changed or created, the backups, and what is NOT ours
19. Loose ends
20. The questions, in order, with their answers
21. Is the FaceDetailer out of the picture when switched off? (checked from the run record)
22. "The faces do not resemble either LoRA" - the side-by-side test
23. Likeness scan of every saved picture
24. "Focus on the training" - what the training is now (read-only)
25. Her trigger word shown in the Summary Signal
26. The 12b pop-up viewer: Send to video workflow queue and DELETE
27. The blue "switch the order" button under the FINAL COMBINED PROMPT
28. The end of the session: files, backups, lessons, loose ends and questions since section 20, and the commit

---

## 1. Where things stood at the start

- Working workflow: `user/default/workflows/Freedom_SDXL_v01.json`, last saved by the user on
  30 Sep at 23:42:14. It was never saved during this session (checked again at the end: same time,
  same size, 100,052 bytes).
- ComfyUI was NOT running when the session started (a check of the address 127.0.0.1:8188 got no
  answer). ComfyUI 0.37.0, page (frontend) 1.53.6.
- Already changed but not committed before this session started (NOT this session's work - left
  alone): `CLAUDE.md`; the whole `face_training/` folder deleted (it moved to `REPO_face`, the app
  "Face N the Crowd", on 30 Sep); several older logs deleted for the same move; small edits in
  `logs/REPO_comfyUI_Monitor_LOG.md`, `logs/comfyui_403_cross_site_guard_and_launchpad_hop_2026-09-24.md`,
  `logs/comfyui_lora_stack_and_repo_migration_2026-09-07.md`,
  `logs/move_to_app_cabinet_HANDOFF_2026-09-17.md`, `logs/v06_facedetailer_lora_and_likeness_2026-09-21.md`;
  and a new file `custom_nodes/freedom_prompt_slots/web/fresh_seeds.js`.

## 2. Last night's crash: were there any error logs after 10pm?

### 2.1 What the user said
Late on 30 Sep they clicked or double-clicked the Physical prompt shelf's dropdown and/or its text
window, ComfyUI "crashed", and they had to reload. They asked for any error logs from after 10pm.

### 2.2 What was checked
1. **ComfyUI's own log**, `logs/comfyui.log` (the launcher writes here; 43,830 lines, last written
   1 Oct 00:32). It has no time on each line, only a "ComfyUI started" line at each start:
   - 30 Sep 14:37 start: the last thing it wrote was a finished picture ("Prompt executed in 322.30
     seconds"). No error line, no shutdown line - so the log cannot say when or why that run ended.
   - **30 Sep 22:33 start** (line 42602): loaded normally, said "To see the GUI go to
     http://127.0.0.1:8188", then wrote nothing at all - no pictures, no errors - until the next start.
   - **30 Sep 23:11 start** (line 42721): 16 pictures made, all finished, no errors.
   - Searched everything after line 42602 for error / traceback / exception / crash: nothing.
2. **Other logs changed after 22:00**: none besides `comfyui.log`.
3. **Windows' own crash record** (Application event log, 30 Sep 22:00 to 1 Oct 01:00, errors and
   warnings): only one entry, `OVRServer_x64.exe` (the Oculus VR program) at 00:39:40, exception
   0xc0000409. Nothing for Chrome or Python (ComfyUI).

### 2.3 What was told to the user
No error messages were found. The 22:33 and 23:11 starts are most likely their reloads. A click on a
dropdown or text box happens in the browser page, not in the ComfyUI program behind it, so the likely
place it went wrong is the page - and the page's own message panel (the browser "console") is wiped
when the page reloads. That is a likelihood, not a proven cause; it was said that way.

## 3. "Make the shelf preview boxes read-only" - and finding they already were

### 3.1 The request
"Lets make all of the node group 7 shelf prompt boxes, the box/field that shows whats in the preset,
lets make them as read-only."

### 3.2 What the code showed
- STEP 7 has two shelves: the **Scene Shelf** (node 51, `FreedomScenePrompt`, "STEP 7d") and the
  **Physical Shelf** (node 52, `FreedomPhysicalPrompt`, "STEP 7e"). Code:
  `custom_nodes/freedom_prompt_slots/web/prompt_slots.js` (page side) and `.../nodes.py` (server side).
- Each shelf's "SAVED - the saved one you are dialled to" box is drawn by `ownTextField(...)` with
  `readOnly = true`. So typing was already blocked. You could still click in, see a cursor, select and
  copy.
- By contrast the FINAL COMBINED PROMPT (7f) is "closed to the mouse and keyboard": no clicking in, no
  selecting, no copying.

### 3.3 The question and the answer
Asked: how locked should the SAVED boxes be - (1) fully closed like the final box, (2) leave as is,
(3) you could type in them on screen, so check the live page first. **The user answered "4": "Then
maybe im looking in the wrong area"**, and asked instead for an examination of all the STEP 7 shelf
dropdown menus for weak spots where an accidental click could cause an error. Nothing was changed for
this request.

## 4. Looking for weak spots in the STEP 7 shelves

### 4.1 First finding: there is no real dropdown on the shelves
What picks the preset is a number dial (`scene_slot` / `physical_slot`, a whole-number setting with
- and + arrows, 1 to 99). The name is a one-line text field (`*_name`). The only real dropdown in
STEP 7 is inside the Summary Signal box (7c, "save model text as which model?"), which is not a shelf.

### 4.2 The server side
All shelf routes in `nodes.py` (`/freedom/partslots/<kind>/list|save|saveas|rename|delete`) check every
input (slot number, empty name, slot out of range, shelf full at 99) and answer with a message, and
write their file safely (to a ".tmp" file, then swap it in). The ComfyUI log showed no route errors
last night. Nothing found there that a stray click could break.

### 4.3 The seven weak spots reported (page side, `prompt_slots.js`)
1. A double-click got past the "click twice" safety on **Delete** and **Create new**. Delete removes a
   saved preset for good; Create new empties the typing box, and text cleared by code cannot be
   brought back with Ctrl+Z.
2. That safety stayed "armed" far longer than its message said: only another shelf button calmed it,
   not a click on the canvas, the dial or the green button. So an hour later, a single click on Delete
   would delete.
3. **Load** (and **Rename**) on an empty slot left a hidden job behind: when the dial later reached a
   saved slot, Load ran by itself and replaced the typing box.
4. Turning the dial during a rename threw away the typed name; with Esc and then Save (overwrite), the
   old name could end up on a different preset.
5. Dragging the bottom edge of the SAVED box by accident made it taller, every box below moved down
   (the user's own "no overlap" rule) and never moved back, and the workflow got marked as changed.
6. If ComfyUI answered strangely, Save / Save as / Rename / Delete failed with no message at all.
7. Double-clicking **Save as** saved the same preset twice.

It was said plainly that none of these explains a crash or freeze, and that recreating last night's
crash would need live testing.

## 5. Fixing the STEP 7 shelves: one click, then a confirm/cancel box

### 5.1 The decision
User: "1 but I dont want double click; I want one click and then a confirm/cancel box." So: fix all
seven, and Delete / Create new become one click that opens a confirm/cancel box.

The box is an ordinary part of the page, not a browser pop-up, because a browser pop-up freezes the
whole page until answered (and browser automation cannot click it).

### 5.2 What was built in `prompt_slots.js` (the shelf section, `buildPartsSection`)
- **Backup first:** `_backups/shelf_confirm_box_2026-10-01/prompt_slots.js` (12:01).
- **The red box:** sits under the shelf buttons, text plus **Confirm** and **Cancel**. Confirm ignores
  clicks for the first half second after the box opens, so the second half of a double-click can never
  reach it.
  - Delete: "Delete "<name>" (slot N) from the shelf for good? The ones below it move up a slot." On
    Confirm it first checks the shelf still has that same preset in that slot; if not, "the shelf
    changed before Confirm - nothing was deleted".
  - Create new: "Empty the <scene/physical> box? What is typed there now will be lost. Your saved ones
    on the shelf stay as they are."
  - Cancel: "cancelled - nothing was changed".
- **Calling things off:** pressing any other shelf button closes the box and stops a half-done Rename
  or Save as. Turning the dial does the same and says "the dial moved, so that was cancelled - nothing
  was changed".
- **No hidden jobs:** on an empty slot, Load / Rename / Delete / Save still make the dial blink and
  stay highlighted until it reaches a saved slot (the user's earlier rule), but then only a message
  appears ("now press Load to load ..."). Nothing runs by itself any more.
- **No silent failures:** every shelf change catches a missing or garbled answer and says "ComfyUI gave
  no proper answer, so this may not have happened. Turn the dial away and back to check."
- **One change at a time:** while a save/rename/delete is on its way, another click says "still
  working on the last click - wait a moment".
- **Save as / Rename double-click:** see 5.3 and section 6.
- Weak spot 5 was NOT changed - it touched how resizing works, which the user had set up on 30 Sep, so
  it went to the user as a question (it later became section 8).

### 5.3 How the edit went, step by step (including the slips)
1. The first two edits went in with the editing tool: the box itself, and a change making other
   buttons close the box and stop a half-done rename.
2. The rest was put in a Python script run from the shell. The shell refused the script (a quoting
   problem with the way it was passed in). **At that moment the user interrupted with "?".** The file
   was half-changed, and the half-change on its own broke Rename and Save as: their second click (or
   Enter) cancelled itself, so a new name could never be saved. This was told to the user straight away.
3. The script was saved as a file in the session's scratch folder and run from there. It stopped
   safely before writing (one piece of text it looked for appeared twice). It was made more specific;
   on the next run one block lost its first three lines, which the syntax check caught ("Illegal return
   statement"); the three lines were put back by hand. Syntax check (module mode, as the memory notes
   require) then passed.

### 5.4 Testing in the live page (ComfyUI started by Claude at 13:54)
- ComfyUI was started directly (not by the launcher), with its output going to
  `logs/comfyui_2026-10-01_1354_stdout.log` and `..._stderr.log`, using the same settings the
  launcher uses (`--base-directory REPO_comfyUI`, `--extra-model-paths-config`, `--disable-pinned-memory`,
  port 8188).
- Opened in Chrome by the launch-page hop (a tiny page on 127.0.0.1:8190, then a jump to 8188 - the
  only way past ComfyUI's cross-site guard; see CLAUDE.md). The helper page was stopped after each hop.
- `Freedom_SDXL_v01` was opened from the Workflows panel (not by code - memory note).
- **Before testing, the saved shelves were backed up**: `freedom_scene_slots.json` (md5
  2880fd6147162112ab3b4ad407cb6755) and `freedom_physical_slots.json` (md5
  92f165359fa694ef43a20efcfde5e81d) into the backup folder.
- Results on the Physical shelf (node 52):
  - Double-click **Create new** -> only the box opened; the typing box kept its text. Pass.
  - **Cancel** -> box closed, "cancelled - nothing was changed". Pass.
  - Double-click **Save as** -> no duplicate saved (still 3 presets: woman 30, woman 18, girl 16).
    Pass - but see the bug below.

### 5.5 The bug made during the fix, and how it was found
After the double-click on Save as, typing "zz test delete me" and pressing Enter saved **two extra
copies of "woman 18"** (slots 4 and 5) and never used the typed name. A focus log was attached to the
button to find out why rather than guess. It showed: mousedown on "Save as new" -> focus moved to the
BUTTON. So the second click of the double-click, although ignored, had pulled the keyboard off the
name field onto the button; each typed space then pressed the button, and each press saved. The fix:
an ignored second click hands the keyboard straight back to the name field. (In section 6 this was
replaced by the confirm box, whose buttons never take the keyboard at all.)

Clean-up: the shelf file was restored from the backup (md5 back to 92f165...), the list read back as
woman 30, woman 18, girl 16, and the test workflow was closed with "Close anyway" (writes nothing).

## 6. Every "press again" button in the workflow gets the same box

### 6.1 The request
While the work above was running, the user wrote: "you set some buttons to click for confirmation.
Yes. Please please change those buttons (buttons only) to match the confirm/cancel box." Asked which
ones - (1) only the STEP 7 shelves' Rename and Save as, (2) every one found, (3) a set you name - the
**user answered 2**.

### 6.2 What was found (searched, not recalled)
The "press again" pattern (a function called `makeRenamer`, copied into five files) and two separate
"Press again to delete" buttons:
- `freedom_prompt_slots/web/prompt_slots.js` - STEP 7 shelves: Rename, Save as.
- `freedom_checkpoint_prefix/web/checkpoint_prefix.js` - 7c Summary Signal: Save as (pick a model),
  "Delete model text" ("Press again to delete"), and "Press Save as again to replace it".
- `freedom_portrait_control/web/facedetailer_presets.js` - 11c FaceDetailer presets: Save as, Rename,
  Delete ("Press again to delete").
- `freedom_portrait_control/web/portrait_control.js` - Portrait Master 4b-4h presets and the STEP 3b
  recipes: Save as, Rename.
- `freedom_face_competition/web/presets_method1.js` - Face Competition Method 1: Rename.
  (Listed to the user as "in the workflow"; later found it is NOT in Freedom_SDXL_v01 - see section 9.)

### 6.3 What changed
- Backups first (15:57): the four other files, plus `prompt_slots_before_confirm_box_buttons.js`.
- One shared helper, `askBox(button)`, added to each file: the same red box, placed right under the
  button's row, Confirm ignoring clicks for half a second, and both its buttons set so pressing them
  never moves the keyboard (`mousedown` -> `preventDefault`). Its buttons copy the look of the button
  that opened it.
- `makeRenamer` in all five files: the first press fills the name field, selects it, blinks it, AND
  opens the box ("<Button>: type the name in the name box, then press Confirm."). Pressing the button
  again does nothing but hand the keyboard back. Confirm or Enter saves; Cancel or Esc stops. The
  button keeps its own label (it used to change to "Save new name" / "Save as new").
- 7c Summary Signal: Delete opens "Remove <model>'s model text for good? Your words are kept."; Save as
  over a model that already has text opens "<model> already has model text. Replace it with this one?".
  When the STEP 1 model changes, any open box closes (it was about the old model).
- 11c FaceDetailer: Delete opens "Delete the preset <name> for good?" and checks the menu still shows
  that preset on Confirm.
- The old "click twice" helper (`twoStep`) is still used by two older STEP 7 panels that are not in
  this workflow; left alone.
- Edit route: a Python script (scratch folder `confirm_box_buttons.py`). Summary Signal patched first;
  FaceDetailer then stopped safely (a line appeared twice); the match was narrowed and the remaining
  four were patched. All five passed the module-mode syntax check; a search found no leftover
  "Press again" / old armed-state code.
- A false alarm: a line-ending count first suggested the files used Windows line endings and that
  one had been changed. Re-checked with Python: all five, their backups and the committed versions all
  use plain line endings. The first count was wrong because of how the shell read the command; nothing
  had changed.

### 6.4 Testing (page reloaded by the hop in a fresh tab)
- STEP 7 Physical shelf:
  - Double-click Rename -> box only; typing "zz test name" went into the name field; Cancel -> name
    back to "woman 18", nothing renamed, "rename cancelled - the name is unchanged". Pass.
  - Save as -> type "zz test delete me" -> Confirm -> exactly one new preset, slot 4. Pass.
  - Double-click Delete on it -> box only, nothing deleted. Pass.
  - Turned the dial down one -> box closed, "the dial moved, so that was cancelled". Pass.
  - Dial back, Delete, Confirm -> deleted; back to 3 presets. Pass.
  - Failed-save message: the page's network call was blocked on purpose (only for this test, then
    restored), Save (overwrite) pressed -> "ComfyUI gave no proper answer ...", nothing reached
    ComfyUI. Pass.
- 7c Summary Signal: Delete -> box -> Cancel; the model text for cyberrealisticPony_v110 still saved
  ("score_9, score_8_up, score_7_up"). Save as -> box -> Cancel. Pass.
- 11c FaceDetailer: picked "tl_denoise 0.15" in the menu (choosing only, nothing loaded), Delete -> box
  (fully visible) -> Cancel, preset kept. Rename -> box, keyboard in the name field -> Esc -> box
  closed, "Rename cancelled". Pass.
- 4c Portrait Master: Save as -> box, keyboard in the name field -> Esc -> "Cancelled - nothing was
  changed". Pass. (The first click there missed the button; the second, by screen position, hit it.)
- Not tested live: Face Competition (not in this workflow); the 7c "replace" box (needs a second model
  with saved text); 4b and 4d-4h Save as / Rename (same code as 4c).
- Screenshot timeouts: the browser tool's screenshot timed out about every other time right after
  the canvas changed. Each time the page was checked: it answered at once and ran at about 98 screen
  updates a second, and the console showed no errors from these files (only two from ComfyUI's own
  start-up at 15:59:45: "ComfyApp graph accessed before initialization" and a "vite:preloadError").
  So it was the tool, not the page.
- After testing: both shelf files md5-identical to before; workflow file untouched; test workflow
  closed with "Close anyway". The old browser tab from the first test (Chrome tab 1273375614) could not
  be closed - trying disconnected the browser tool, most likely because Chrome's "Leave site?" pop-up
  is up on it. Left open and reported.

## 7. Portrait Master's Delete buttons: who made them, and adding the box

### 7.1 Found while working
Portrait Master's own preset Delete (4b-4h) and the STEP 3b recipe Delete deleted on ONE click with
no confirm at all. Not part of the request, so it was raised as a question, not changed.

### 7.2 "Who installed the delete buttons? Us or the Portrait Master developers? Do not assume, guess, or recall from memory."
Checked, in this order:
1. Both buttons are in `custom_nodes/freedom_portrait_control/web/portrait_control.js`, whose own
   header reads "FREEDOM SYSTEM - Portrait Control" - our add-on.
2. `git log -S` (finds the commit that first added a piece of text): the preset Delete
   (`mkButton("Delete"`) first appears in `5be5a7b`, 18 Sep, "Our ComfyUI work, in its own repo" (the
   first commit after the move into this repo, so it may have been written slightly earlier
   elsewhere); the recipe Delete (`mk("Delete"`) in `f312dcd`, 22 Sep, "Shelves for your prompts and
   phrases, and presets that carry the whole recipe".
3. The developer's own app, `custom_nodes/comfyui-portrait-master` (its git origin is
   github.com/florestefano1975/comfyui-portrait-master), has no "delete" in any .js or .py file.
Answer: **we made them**. The question was then asked again; **the user answered 1** (add the box).

### 7.3 What changed (`portrait_control.js`)
- Recipe Delete (STEP 3b "Her recipes"): one click -> "Delete the recipe '<name>' for good?";
  Confirm deletes only if the menu still shows that recipe; Cancel lets go of the menu as before.
- Preset Delete (4b-4h): one click -> "Delete the preset '<name>' for good?"; same check.
- Syntax check passed.

### 7.4 Testing
- Backed up the whole `user/default/portrait_presets/` folder (5 files) into the backup folder and
  recorded each file's md5.
- 4b (node 30): "User Preset 01" chosen in the menu without loading it; Delete -> box under the
  buttons -> Cancel -> still 2 presets (User Preset 01, pm_susana closest 02). Pass.
- STEP 3b Her recipes (node 2): Save as "zz test delete me" -> Confirm -> saved as
  "tl_zz test delete me"; double-click Delete -> box only, nothing deleted; Confirm -> only the test
  recipe deleted, "Deleted 'tl_zz test delete me'." Pass.
- All 5 preset files md5-identical to before. Workflow closed (it was not marked changed).

## 8. Weak spot 5 became: bigger resize handles on boxes and frames

### 8.1 The question and the answers
Asked what should happen when a box's bottom edge is dragged by accident: (1) leave it, (2) an "undo
last resize" button, (3) make the drag handle harder to grab, (4) something else. **User: "4. actually
make the node and node group resize handle easier to grab."** ("node" = a box, "node group" = a frame.)

### 8.2 Research before any change (ComfyUI's own shipped page code, frontend 1.53.6)
- Boxes: four invisible grab squares, one per corner - elements with `data-corner` SE / NE / SW / NW
  in `GraphView-*.js`, size class `h-5 w-5` (20 x 20), 4 past the corner, shown only while the mouse
  is over the box (`opacity-0`, `group-hover/node:opacity-100`).
- Frames: resized only from the bottom-right corner, by a small triangle,
  `LGraphGroup.resizeLength = 10` (`settingStore-*.js`, `isInResize`). The same number is used to draw
  the triangle. Exposed to add-ons as `window.LGraphGroup`.
- Older canvas-drawn boxes: `LGraphNode.resizeHandleSize = 15`.
At the user's usual 80% zoom the box corner was about 16 screen dots wide and the frame triangle about 8.

### 8.3 Size choice
Asked: (1) about twice as big, hidden until hover; (2) about twice as big, always faintly showing;
(3) about three times as big, always faintly showing; (4) other. The trade-off was explained: a bigger
grab area also catches clicks meant for things near the corners (wire dots at the top right, the last
field's drag edge). **User: 2.**

### 8.4 What was built
- A new add-on of our own: `custom_nodes/freedom_canvas_handles/` (`__init__.py` with no nodes, and
  `web/canvas_handles.js`). ComfyUI's own files are untouched, so an update cannot undo it; if an update
  renames these settings, the page keeps ComfyUI's sizes and says so in the console.
- Box corners: 40 x 40, centred on the corner (half inside, half outside, so less of the box's own
  buttons and wire dots is covered), always at 35% strength, full strength while the mouse is over the
  box.
- Frame corner triangle: 25 (was 10). Older canvas-box corner: 30 (was 15).
- A new add-on folder only loads when ComfyUI starts, so the ComfyUI Claude had started (process 14460
  and its child 24404, queue empty) was stopped and started again at 19:34, output to
  `logs/comfyui_2026-10-01_1934_stdout.log` / `..._stderr.log`. The log shows
  `freedom_canvas_handles` loaded with no errors. New process: 2532.

### 8.5 Testing
- In the page: the CSS was in place, `LGraphGroup.resizeLength` read 25, `LGraphNode.resizeHandleSize`
  read 30, and each corner measured 40 x 40 at 35% strength. (They first looked small only because the
  view was zoomed out to about 34%.)
- Screenshot at 80%: a faint mark on every corner of every box, and a bigger triangle at the frame's
  corner.
- Real drag from just OUTSIDE the STEP 1c box's (node 1) bottom-right corner: it resized, 550 x 150 ->
  650 x 220. That spot was barely reachable with the old corners.
- **"THERE MUST BE ZERO OVERLAP."** The resized STEP 1c had grown past the edge of its STEP 1 frame and
  over the frame's corner. Claude stopped and asked which overlap was meant; **the user answered 4:
  "when you, claude are resizing nodes, do not let them overlap other nodes."** Saved as a standing
  rule in memory (`claude-resizes-never-overlap.md`). Checked afterwards: no two boxes overlapped, and
  the 650 x 220 test size had not touched any other box (only the frame edge). STEP 1c was put back to
  550 x 150 (page only).
- Frame corner: the page's own test (`isInResize`) confirms a point 8 units in from the corner now
  counts as the grab area (it would not have at 10). But two real drags there (one outward by one
  50-unit step, chosen because the boxes inside had only 50 units of room so shrinking was ruled out,
  and one small inward) did NOT resize the frame; its size stayed -1800, 0, 700 x 2050. The frame was
  not pinned, the page was not read-only, and `document.elementFromPoint` returned nothing at that
  point, which could not be explained. An earlier attempt had also missed because the just-enlarged
  STEP 1c covered the frame's corner. Claude stopped rather than guess. **Unproven - needs a test by
  hand.**
- End: workflow closed (not marked changed, no "Save" anywhere), workflow file untouched.

## 9. The first version of this record

User: "lets create a log of everything done today in painful detail." This file was written then
(sections 1-8 plus a "what went wrong", file list, loose ends and question list), and later the user
asked for it to be brought up to date with everything done after it ("update today's existing log in the
repo logs folder with all the stuff you did so far") - which is this version. The later work was first
added as notes A-G at the end; they are now sections 10-16.

## 10. Restarting ComfyUI and closing the extra tabs
- ComfyUI restarted the same way as before (direct start, not the launcher): processes 2532/11160
  stopped (queue empty), new process 4736 at 19:54, output `logs/comfyui_2026-10-01_1954_*.log`,
  no errors, `freedom_canvas_handles` loaded.
- Tabs: one extra test tab closed. The first test tab (Chrome tab 1273375614) would not close:
  the browser tool timed out twice and a real click on its X (desktop tool) did nothing; no
  "Leave site?" pop-up appeared, so the page itself seemed hung. Stopped after three tries and
  told the user how to close it by hand. Later the whole test tab group was gone (closed by the user).

## 11. STEP 6 lettering (6a / 6b / 6c) and the LoRA stack's All OFF | All ON
- User: group 6 was not lettered - wanted 6a (info), 6b (hints), 6c (LoRA stack); and the LoRA
  stack's on/off button separated, active green, inactive gray.
- Found: group 6 held node 23 (info note) and node 3 (FreedomLoraStack); no hints note. The stack
  had ONE "All OFF / All ON" button whose label flipped (2026-09-25) plus a tick box per row.
- Questions: which control -> user answered "4" with a screenshot of the "All ON" button; asked again
  for that button -> **1** (labels "All OFF" and "All ON"; green = the side every row is on; mixed =
  both gray; each button switches every row). 6b text -> **1** ("n/a" for now, like 7b).
- Code: `custom_nodes/freedom_lora_stack/web/lora_stack.js` (backup
  `_backups/lora_stack_onoff_2026-10-01/lora_stack.js`): two buttons in a joined pair, colours the
  same as "face OFF | face ON" (#2e8b3e green, #55575c gray); a row's tick box updates the pair too.
- Tested live on v01 (not saved): all on -> All ON green; All OFF -> every row off, All OFF green;
  tick row 1 -> both gray; All ON -> every row on, All ON green. No console errors. Rows ended as they
  started (all on). v01 untouched (still 30 Sep 23:42:14, 100,052 bytes).
- New workflow `user/default/workflows/Freedom_SDXL_v02.json` (then: layout changes went into a new version - see 15):
  copied from v01; node 23 -> "STEP 6a - general LoRA stack (both face modes)"; new node 54
  "STEP 6b - Hints" (MarkdownNote, "n/a", 700 x 150 at 4100,600, colours as 7b); node 3 -> "STEP 6c  -
  FreedomLoraStack - ..." moved from y 600 to y 800; frame "STEP 6" height 1200 -> 1400. Same
  workflow id as every earlier version. Written in ComfyUI's compact format (v01 re-saved this way is
  byte-identical, so the format matches).
- Checks: no overlaps between any boxes, in the file and as drawn on screen; all three inside the
  frame; opened unmarked; closed without saving (file still 20:14:40).
- Seen, not changed: the 6a note's text is out of date - it says "Three rows are ready to go" and
  "Click + Add LoRA for more rows, or the X on a row to remove it", but the stack has four fixed rows,
  no Add button, an X that empties a row, and now All OFF | All ON.
- CLAUDE.md: one line added under the node-group layout notes recording STEP 6's lettering.

## 12. The gray-side lettering, first attempt (too bright), and "which workflow is current?"
- User (with a screenshot of All OFF | All ON): the inactive button's lettering should be gray but
  readable, not the same gray as the button. Then: "check similar button packages and make the same
  change."
- Lettering on the gray side changed from #c8c8c8 to #e2e2e2 (button stays #55575c; contrast with the
  button 4.32:1 -> 5.58:1; the green side keeps white #fff).
  - `freedom_lora_stack/web/lora_stack.js` - the All OFF | All ON pair.
  - `freedom_prompt_slots/web/prompt_slots.js` - the one shared rule for every two-choice switch
    ComfyUI draws (`.lg-node [role=group] > button[data-state="off"]`).
- Searched for other green/gray pairs: none (Summary Signal's green is a single update button).
- Checked live in v02 (not saved): the gray side reads rgb(226,226,226) on rgb(85,87,92) on the LoRA
  stack pair, Face Shelf "face OFF | face ON" (node 2), the save switch (node 9) and FaceDetailer's
  switches (node 34); screenshots looked right. v01 and v02 files unchanged by viewing.
- This lettering turned out to be the wrong way (too bright) - corrected in section 14.

**"So which workflow is the current workflow?"** Answered: v02 (made from v01 as the user saved it on
30 Sep 23:42; everything in v01 plus the STEP 6 changes). The button/colour/handle changes are code and
show in both v01 and v02. (After section 15, v02 is still the current workflow - now with the letters.)

## 13. The 6a note's wording brought up to date
- Only the third paragraph of node 23 changed (backup of v02 before: `_backups/lora_stack_onoff_2026-10-01/Freedom_SDXL_v02_before_6a_text.json`).
  Was: "Three rows are ready to go ... Click **+ Add LoRA** for more rows, or the **X** on a row to remove it."
  Now: four rows always there; a ticked row with no LoRA does nothing; the X empties a row and the row
  stays; All OFF / All ON switch every row, the green one shows the setting, both gray when mixed; the
  list only shows LoRAs made for STEP 1's model, click Refresh list after adding a LoRA or changing
  the model. Each point was checked against `lora_stack.js` / `nodes.py` first; the user approved the
  wording before it went in.
- First check on screen: the longer text made the drawn 6a box grow to 647 (with title) and run into
  6b - an overlap on the page only, never saved. Fixed in the file: 6a size 700 x 650, 6b moved to
  y 800, 6c to y 1000, STEP 6 frame height 1600. Re-checked on screen: drawn bottoms 750 / 950 / 1550
  match the file, 20 between boxes, no overlaps between any boxes, no frame overlaps, all inside the
  frame, opened unmarked, closed without saving.

## 14. Darker gray-side lettering, the FaceDetailer's repaint OFF | ON, and the missing letters
- User: inactive lettering "too bright still"; 11c needs its own working on/off pair inside the
  presets box, above the menu / Load / Save; "I keep asking you to fix the other nodes that do not have
  the lettering #x!"
- **Admitted mistake:** the first request ("should be gray ... not the same gray as the button") was
  read the wrong way - the lettering was made BRIGHTER (#c8c8c8 -> #e2e2e2). Now #a0a0a0 (mid gray,
  darker than both earlier values, still apart from the #55575c button) in `lora_stack.js` and the
  shared switch rule in `prompt_slots.js`.
- **repaint OFF | repaint ON** in `freedom_portrait_control/web/facedetailer_presets.js` (backup in
  `_backups/lora_stack_onoff_2026-10-01/facedetailer_presets.js`): a full-width pair at the top of the
  FACEDETAILER PRESETS box, above the preset menu row. It drives the workflow's existing repaint switch
  (node 35 "STEP 11 SWITCH", PrimitiveBoolean), found by following the FaceDetailer's picture to the
  on/off chooser (node 36, ImpactConditionalBranch), its "cond" input back to the gate AND (node 40) and
  that gate's "bool_a" to the switch. The repaint still needs STEP 2 = trained_face (gate nodes 38/39);
  when the switch is ON but STEP 2 is not trained face, a note says no repaint happens. A workflow with
  no such switch shows a note and the buttons do nothing. Same green/gray look as every pair.
- **Letters:** new `Freedom_SDXL_v03.json` copied from v02 AS THE USER SAVED IT at 20:48 (the user had
  been working in v02 after Claude's 20:25 change: new seed, Portrait Master settings, 11b box size; all
  of Claude's v02 changes were still in it). Titles: 2a FreedomFaceSource (24), 5a FreedomFaceRouter (29),
  8a note (16), 8b CLIPTextEncode (5), 9a note (17), 9b EmptyLatentImage (6), 10a note (18), 10b KSampler
  (7). No code finds these boxes by title (searched). Nothing moved.
- Not lettered: the 8 boxes in "BEHIND THE SCENES - plumbing" (titles like "STEP 7 - CLIPTextEncode",
  "STEP 11 GATE 1 of 3") - they sit outside their steps' frames; asked the user (answer: section 16).
- Tested live in v03 (separate tab; the user's own tab with v02 was left alone): pair found node 35;
  repaint OFF -> node 35 false, OFF green; repaint ON -> true, ON green; gray side rgb(160,160,160) on
  rgb(85,87,92); all 8 titles lettered; no overlaps between any boxes on screen. Closed without saving
  (v03 still 20:55). Not tested: an actual picture run with the repaint off.

## 15. "Stop creating new versions": v03 folded into v02 and deleted
- Checked first: v02 not saved since 20:48 (the copy v03 was made from); the user's tab had v02 open
  with no unsaved changes. Backed up that v02 to
  `_backups/lora_stack_onoff_2026-10-01/Freedom_SDXL_v02_user_save_2048.json`, closed v02 in the
  user's tab (nothing lost - it held no changes; done so a stale copy there can't save over the new
  file), copied v03 over v02 (byte-identical check passed), deleted v03. v02 now has the letters
  2a, 5a, 8a/8b, 9a/9b, 10a/10b (21:10:27).
- CLAUDE.md: the old rule "layout changes go into a new workflow version" replaced with the user's
  "do NOT create new workflow versions" plus the safe way to edit the current file.

## 16. The plumbing boxes stay without letters
- Asked how to letter the 8 boxes in "BEHIND THE SCENES - plumbing" (own group / under the step they serve / leave unlettered / other) -> **3: leave them without letters** (the "don't touch" boxes). Recorded in CLAUDE.md. No file changed.

## 17. What went wrong, and what was learned

1. **A half-finished edit was live when the user interrupted** (5.3). The shelf file sat for a while
   with Rename and Save as unable to finish. It was never loaded in a page in that state, and it was
   reported at once. Lesson: put a multi-part change in one step, or check the half state is safe.
2. **The double-click guard created a worse bug** (5.5): ignoring the second click left the keyboard on
   the button, so typed spaces saved extra copies. Found only because the live test typed a name after
   a double-click; diagnosed with a focus log, not guessed.
3. **Shell scripts tripped on quoting** three times (inline Python, an escaped fix-up, a line-ending
   count inside a command). Running scripts from files avoided it.
4. **A false alarm about line endings** (6.3) - a bad count, cleared up by a proper check.
5. **Face Competition was listed as "in the workflow"** when offering the choice in 6.1; it is not in
   Freedom_SDXL_v01/v02. It was changed anyway (the user chose "every one found") and not tested live.
6. **Test drags missed** twice: the first 4c Save as click, and a frame drag that landed on the
   just-enlarged STEP 1c box.
7. **A test resize went past a frame edge** (8.5). It overlapped no box, but it prompted the user's
   rule that Claude's resizes must never overlap other boxes (saved to memory).
8. **The frame-corner drag is unexplained** (8.5). Stopped instead of guessing; still a loose end.
9. **A stuck browser tab** (10) could not be closed after three tries; stopped and handed it to the user
   rather than keep forcing it.
10. **The first gray-lettering change went the wrong way** (12, 14). "Should be gray ... not the same gray
    as the button" was read as "lighter"; the lettering was made brighter (#c8c8c8 -> #e2e2e2) and the
    user had to say "too bright still". Now #a0a0a0. Lesson: when a request names a direction ("gray",
    "darker"), check which way the change goes before making it.
11. **Longer note text overlapped the next box on screen** (13). A note box grows to fit its text when
    drawn, which the file's size does not show. Caught by the on-screen overlap check before anything was
    saved; fixed in the file. Lesson: after changing a note's text, always measure the drawn box.
12. **The STEP lettering was only partly done** until the user said "I keep asking you to fix the other
    nodes that do not have the lettering". Earlier work lettered only the group that was asked about.
    Lesson (now in CLAUDE.md): every box in a STEP frame carries its letter, even a frame with one box.
13. **New workflow versions** (v02 for STEP 6, v03 for the letters) were made because CLAUDE.md said
    "layout changes go into a new version". The user said to stop. v03 was folded into v02 and deleted,
    and the CLAUDE.md rule was replaced (15).

## 18. Every file changed or created, the backups, and what is NOT ours

Changed (this session) - `git diff --stat` for the code and CLAUDE.md: 521 lines added, 114 removed:
- `custom_nodes/freedom_prompt_slots/web/prompt_slots.js` - shelf fixes, confirm box, askBox,
  makeRenamer (5, 6); the shared on/off switch rule's gray-side lettering #c8c8c8 -> #e2e2e2 -> #a0a0a0
  (12, 14).
- `custom_nodes/freedom_checkpoint_prefix/web/checkpoint_prefix.js` - askBox, makeRenamer, Delete and
  replace boxes (6).
- `custom_nodes/freedom_portrait_control/web/facedetailer_presets.js` - askBox, makeRenamer, Delete box
  (6); repaint OFF | repaint ON (14).
- `custom_nodes/freedom_portrait_control/web/portrait_control.js` - askBox, makeRenamer (6); both Delete
  boxes (7).
- `custom_nodes/freedom_face_competition/web/presets_method1.js` - askBox, makeRenamer (6).
- `custom_nodes/freedom_lora_stack/web/lora_stack.js` - All OFF | All ON pair (11) and its gray-side
  lettering (12, 14).
- `CLAUDE.md` - node-group notes: STEP 6 lettering (11); "every box in a STEP frame carries its letter",
  v02's new letters, plumbing boxes stay unlettered (14, 16); the old "layout changes go into a new
  workflow version" rule replaced by "do NOT create new workflow versions" (15).
- `logs/REPO_comfyUI_Monitor_LOG.md` - one entry appended ("2026-10-01 - confirm/cancel box ...").

Created (this session):
- `user/default/workflows/Freedom_SDXL_v02.json` - the current workflow (11, 13, 15).
- `custom_nodes/freedom_canvas_handles/__init__.py` and `.../web/canvas_handles.js` (8).
- `logs/confirm_box_buttons_2026-10-01.md` - the shorter record.
- `logs/session_2026-10-01_full_record.md` - this file.
- `logs/comfyui_2026-10-01_1354_*`, `..._1934_*`, `..._1954_*` (stdout and stderr) - ComfyUI's output
  from the three starts Claude made.
- Memory (outside the repo): `claude-resizes-never-overlap.md` and its line in `MEMORY.md`.
- Scratch folder only (not in the repo): `apply_shelf_fix.py`, `confirm_box_buttons.py`,
  `rebuild_record.py`, the launch page's empty folder, `presets_md5_before.txt`, a copy of this record
  before this rebuild.

Created and deleted (this session): `user/default/workflows/Freedom_SDXL_v03.json` (20:55 - 21:10; its
contents are now v02).

Backups (`_backups/` is kept out of git):
- `_backups/shelf_confirm_box_2026-10-01/`: `prompt_slots.js` (before any change, 12:01),
  `prompt_slots_before_confirm_box_buttons.js` (15:57), `checkpoint_prefix.js`,
  `facedetailer_presets.js`, `portrait_control.js`, `presets_method1.js` (15:57),
  `freedom_scene_slots.json`, `freedom_physical_slots.json` (13:55) and the `portrait_presets/` folder
  (19:10).
- `_backups/lora_stack_onoff_2026-10-01/`: `lora_stack.js` (before the pair), `facedetailer_presets.js`
  (before repaint OFF | ON), `Freedom_SDXL_v02_before_6a_text.json`,
  `Freedom_SDXL_v02_user_save_2048.json` (the user's own 20:48 save of v02, kept before v03 was copied
  over it).

Saved data after all testing: shelf files and all 5 Portrait Master / recipe / FaceDetailer preset files
md5-identical to before. `Freedom_SDXL_v01.json` never written by Claude (still 30 Sep 23:42:14).

NOT this session's work (already there at the start - see section 1): the earlier `CLAUDE.md` edits,
the `face_training/` deletions, the older log edits and deletions, `fresh_seeds.js`, the user's own
30 Sep 23:42 save of `Freedom_SDXL_v01.json` (git shows it changed since the last commit), and two
`_archive_bigLust/... .bak_before_*` files.

Nothing committed.

## 19. Loose ends

1. **Frame corner drag** - prove the bigger frame triangle works by hand (8.5).
2. ~~ComfyUI started by Claude~~ - resolved: at 20:00:06 ComfyUI was started again from the launcher
   (process 12272, log `logs/comfyui.log`); Claude's 19:54 copy is gone.
3. **Reload the ComfyUI page, then open v02** - the user's tab had the older page code loaded; v02 was
   closed in it before the file was replaced (15).
4. ~~Repaint OFF not tried in a real picture run~~ - resolved by the user's own runs (section 21).
5. Not tested live: Face Competition Method 1 Rename; the 7c Save as "replace" box; 4b and 4d-4h Save as
   / Rename; the Delete box on 4c-4h presets (same code as 4b).
6. Last night's crash cause is still unknown; the page's messages were lost on reload. If it happens
   again, open the browser console (F12) before reloading.
7. The two older STEP 7 panels (not in this workflow) still use the old double-click `twoStep` guard.
8. Commit not done.

## 20. The questions, in order, with their answers

1. How locked should the two SAVED preset boxes be? (fully closed / leave as is / you could type in
   them) -> **4**: "maybe im looking in the wrong area" - examine the STEP 7 shelf dropdowns for weak
   spots instead.
2. What to do about the seven weak spots? (fix all / pick by number / test live first / leave) ->
   **1**, "but I dont want double click; I want one click and then a confirm/cancel box."
   - Mid-work message: "?" (status check) - answered with where things stood.
   - Mid-work message: "change those buttons (buttons only) to match the confirm/cancel box."
3. Which "press again" buttons should switch to the box? (STEP 7 shelves only / every one found / a
   set you name) -> **2**.
4. Should Portrait Master's one-click Delete buttons get the box? -> the user first asked "who
   installed the delete buttons? us or portrait master developers? Do no assume, guess, or recall from
   memory." - answered with evidence (ours), question asked again -> **1**.
5. Weak spot 5, an accidental drag of a box's bottom edge (leave / undo button / harder to grab /
   other) -> **4**: "make the node and node group resize handle easier to grab."
6. How big, and always showing? (2x hidden / 2x faintly showing / 3x faintly showing / other) -> **2**.
   - Mid-work message: "THERE MUST BE ZERO OVERLAP".
7. Which overlap must be zero? (boxes and frames / the grab corners / both / other) -> **4**: "when you,
   claude are resizing nodes, do not let them overlap other nodes."
8. "Lets create a log of everything done today in painful detail." -> this file (section 9).
9. "okay restart comfy and close the other tabs" -> done, except one stuck tab (section 10).
10. Which on/off control becomes two buttons? (All OFF/ON at the top / each row's tick box / both /
    other) -> **4** with a screenshot of the "All ON" button.
11. Asked again for that button: (labels "All OFF"/"All ON", green = how the rows are, mixed = both gray
    / labels "OFF"/"ON" / other) -> **1**.
12. What should the 6b hints note say? ("n/a" like 7b / Claude drafts hints / user's own words) -> **1**.
13. Bring the 6a note's wording up to date? (yes, show first / no) -> **1**.
    - Mid-work message: the inactive button's lettering should be gray, readable, not the button's gray
      (screenshot); then "check similar button packages and make the same change."
14. Use the drafted 6a wording? (yes as written / yes with changes / no) -> **1**.
    - "so which workflow is the current workflow." -> v02 (section 12).
    - "the font on all of the inactive buttons ... are too bright still", the FaceDetailer needs its own
      working on/off pair above the dropdown / Load / Save, and "I keep asking you to fix the other nodes
      that do not have the lettering #x!" (section 14).
15. How to letter the 8 plumbing boxes? (own group / under the step they serve / leave unlettered /
    other) -> before answering: "you need to stop creating new versions. save this as v02 and delete
    v03" (section 15); then **3**, leave them without letters (section 16).
16. "update today's existing log in the repo logs folder with alle the stuff you did so far." -> this
    version of the file.
17. "I just turned off facedetailer, can you confirm it is not influencing the stream?" -> section 21.

## 21. Is the FaceDetailer out of the picture when switched off? (checked from the run record)

The user switched the FaceDetailer off and asked for confirmation. The browser tab could not be read (not
one Claude opened), so the check used ComfyUI's own record of the last 3 runs (`/history`) and its log
(`logs/comfyui.log`, the launcher's ComfyUI started 20:00:06):

| Run (prompt id) | Repaint switch (node 35) | STEP 2 | Face found / "Detailer:" lines in log | Time |
|---|---|---|---|---|
| eed55976 | true (ON) | trained_face | yes - "1 face" + "Detailer: segment upscale" for each picture | 113.94 s |
| e2ad8032 | false (OFF) | trained_face | none | 41.07 s |
| bf3a86dd | false (OFF) | trained_face | none | 39.36 s |

So with the switch OFF, the FaceDetailer did no work at all - no face search, no repaint, no extra
model loading - and each run took about a third of the time. The on/off chooser (node 36) passed the
picture straight from the developer step (node 8, VAEDecode) to STEP 12. The FaceDetailer is not touching
the picture.

## 22. "The faces do not resemble either LoRA" - the side-by-side test

User: after recent changes (seeds and others) the faces no longer resemble either face file (face, or
face + body), although "many successful" runs used them in past days. Chose a four-picture test.

- Read the last run's record: Portrait Master's words are NOT in the prompt (trained_face: the face
  router passes her trigger word; it only fetches Portrait Master's text in random_face mode - its input
  is "lazy"). Her face file loaded: shelf 0.4 + passes 0.3/0.2/0.1, patch depth 1 -> 4.
- Test (`logs/face_ab_test_2026-10-01/`, see its README): A reproduced the user's four archived pictures
  pixel-for-pixel; B (Portrait Master removed) pixel-identical to A, so Portrait Master has no effect; C
  (Physical empty) and D (face file at zero) both change the picture; D is plainly a different woman,
  so the face file IS shaping the picture.
- Visible, not judged for likeness: the shots are wide (whole body in a 1216 x 832 frame), so the face is
  small, and the Physical box asks for "head turned away, looking down", "eyes rolled back", drool;
  the face repaint (which used to repaint the face as her) is off.
- Also asked for (parked): her trigger word shown and editable in the Summary Signal after the scores,
  appearing only in trained-face mode; a blue button under the FINAL COMBINED PROMPT to swap the order
  of the Scene and Physical parts.

## 23. Likeness scan of every saved picture (user's choice 1)

The user's reference: four training photos of her (`REPO_face\_face_profiles\susana\clean\head\`), and
eight new unposed pictures (img_01693-01700): 01693 and 01696 "close but not near enough", 01697-01700
"terrible", 01700 "maybe 50%". Their settings were read from each picture's own saved data: the two
batches differ ONLY in their seeds (Portrait Master seeds included, already proven to have no effect).
Then every archived picture (1,584) was scored with Face N the Crowd's likeness check, read-only (its
rules file was read first; nothing in REPO_face changed). Folder: `logs/face_likeness_scan_2026-10-01/`
(scan.py, scores.jsonl, grouped.txt, FINDINGS.md). Main points: same face-file settings since 29 Sep;
the scores fall as the scene changes to cowgirl and the face gets smaller and turned away; unposed head
shots score best (mean 0.40); the "don't want" prompt asks for "looking at viewer, eye contact, facing
camera" NOT to happen. The scorer rates front-facing faces best, so it under-rates turned faces.

## 24. "No more tests. I think we need to focus on the training" - what the training is now (read-only)

Read in REPO_face (nothing changed there):
- Both Pony face files were RETRAINED on 28 Sep (`susana_head_sdxl_pony` 00:07, `susana_head_body_sdxl_pony`
  03:56) and replaced the older files of the same names. No older copy survives (searched REPO_face,
  REPO_comfyUI models and _backups, OneTrainer). So every picture before 28 Sep used older versions.
- Face-only Pony training (`_face_runs/susana/susana_head_sdxl_pony/config.json`): base
  cyberrealisticPony_v110, LoRA rank 16, alpha 1.0, learning rate 0.0003 constant, AdamW, 20 epochs,
  batch 1, gradient accumulation 4, resolution 1024, text encoder trained (0.00015), no random flip.
  3,280 steps (164 pictures x 20).
- Training pictures: `clean/head` 164 pictures, `clean/body` 454. Of the 164 face pictures, about 91 are
  frames of one video (118E0AFD...) and 53 of another (IMG_9845) - about 88% from two videos; the rest are
  a handful of photos.
- Captions are a few fixed patterns, e.g. "lorasusana woman, head and shoulders, facing forward" /
  "... profile view".
- What should "focus on the training" start with? (review and plan / picture set first / retrain now / other) -> **4: "drop this question"**. Dropped; not to be raised again.

## 25. Her trigger word shown in the Summary Signal (user's choice 2)

User: "(lorasusana:1.1)" is in the final prompt but not reachable to change the ":1.1" - show it in the
Summary Signal after the scores, appearing / disappearing with the face mode. Choice 2: shown LOCKED in
7c; the weight is still set with the Face Shelf's trigger_weight dial (3b).
- `freedom_prompt_slots/web/prompt_slots.js`: `liveTrigger()` (trained-face mode only, not when the Face
  Shelf strength is 0); the Summary Signal part of the final prompt is now model text, trigger word,
  your words (keys "model"/"trig" kept beside it); in trained-face mode the separate face part is empty;
  random-face mode unchanged (Portrait Master's slot). Every green button keeps the trigger word
  current inside the Summary Signal part without taking in unpressed Summary Signal words
  (`refreshTrigger`). The watcher shows one note "her trigger word / Portrait Master changed - press any
  green button". The 7f order line updated.
- `freedom_checkpoint_prefix/web/checkpoint_prefix.js`: the box shows model text, trigger word (both
  locked), then your words; re-draws when the trigger appears / changes / disappears; page-1 count
  includes it; explanation text updated.
- `freedom_prompt_slots/nodes.py`: the run-time "changed since its green button" log note ignores the
  trigger word inside the Summary Signal part (takes effect at the next ComfyUI start).
- Backups: `_backups/trigger_in_summary_2026-10-01/` (both .js); nodes.py is in git.
- Tested in v02 (Claude's own tab, not saved): random face -> no trigger; trained face -> box
  "score_9, score_8_up, score_7_up, (lorasusana:1.1), ", count 20 of 75; Scene green button (real click)
  -> final "score_9, ..., (lorasusana:1.1), (eighteen ...", face part empty, watcher up to date; back to
  random face + a green button -> trigger removed, Portrait Master slot back, up to date.

## 26. The 12b pop-up viewer: Send image to video workflow queue (+ Delete pending)

User: the pop-up viewer (the one with the left/right arrows, not the picture area in the 12b box) needs a
working Delete image button and a working "Send image to video workflow queue".
- `freedom_folder_inspector/web/preview_pick.js` (backup `_backups/viewer_buttons_2026-10-01/`): a bar at
  the top of the viewer with "Send image to video workflow queue" - sends the picture on screen by the
  same route as the box's button (`/freedom/video/enqueue`), message shown in the viewer.
- Found and fixed while building it: with the video queue's "auto start" on (it is), the send button
  pressed Run on the workflow on screen - from the picture workflow that starts another round of
  pictures, never a video. Now it presses Run only when the workflow on screen holds the video queue;
  otherwise it says the picture is waiting in the queue and to press Run in the video workflow. This
  applies to the box's button too.
- Tested (Claude's own tab, last run's 4 pictures loaded into 12b from the run record, no new pictures):
  double-click picture 2 -> viewer; Send -> slot 1 of the video queue "pending", message shown, ComfyUI
  queue stayed empty (no picture run started). The test picture was then removed from the video queue
  (queue empty, as before). v02 not saved by Claude (file still the user's 23:47:58 save).
- Delete: not built yet - asked the user which copies "delete" removes.
- User's screenshot of the viewer showed the OLD page (no buttons) - the page had not been reloaded. The
  viewer's send button was renamed "Send to video workflow queue" (the user's wording).
- DELETE (user's choice 3, "make sure that deleting an image in 12b node does not cause an error"):
  - `save_pick.py` (backup `_backups/viewer_buttons_2026-10-01/save_pick.py`): each picture's archive copy
    and every Save Image copy are noted in `temp/freedom_hold/_links.json` (archive copy i = picture i,
    same order as made). New route POST /freedom/save/delete {file, archive}: sends the 12b copy, the
    archive copy and the saved copies to the Windows Recycle Bin (shell SHFileOperationW with undo -
    send2trash is not installed; tested on a throwaway file: it landed in the Recycle Bin). Paths are
    checked to be inside the 12b folder / output folder; a copy already gone is skipped, not an error.
  - `preview_pick.js` (backup `preview_pick_before_delete.js`): red DELETE beside Send in the viewer's top
    bar; one click opens "Delete this picture everywhere ...? Confirm / Cancel" (Confirm ignores the
    first half second; Esc closes it). The box's cards are redrawn from the pictures that remain, the
    viewer shows the next picture (or closes after the last), the Save button and counts follow. If
    anything could not be removed, the picture stays and the viewer says why.
  - A copy saved BEFORE this change is not linked to its picture, so DELETE cannot find it.
  - The route needs a ComfyUI restart to exist; not yet tested end to end.
- Restart (user's choice 1): the launcher's ComfyUI (12272/33720, queue empty) stopped; started directly at
  00:30 on 2 Oct (process 9444), log `logs/comfyui_2026-10-02_0030_*.log`, no errors; the delete route answers.
- DELETE tested with throwaway pictures only (zztest_00-02 in the 12b folder, zztest_archive_00-02 in
  output/freedom_archive, zztest_01 saved through 12b's real Save route into a test folder):
  - double-click DELETE -> only the Confirm/Cancel line, nothing removed;
  - Confirm on test 2 -> 12b, archive and saved copies all in the Recycle Bin (the archive copy found
    from the page's record), viewer moved to the next picture "2 of 2", box 2 cards, no page errors,
    ComfyUI log "12b DELETE zztest_01.png: removed ['12b', 'archive', 'your save folder']";
  - next delete -> "1 of 1", arrows hidden;
  - last picture, its archive copy removed beforehand -> deleted without error ("12b" only), viewer
    closed, box "No pictures here.", Save Image switched off;
  - Cancel -> "Cancelled - nothing was deleted."; browser errors: only ComfyUI's own two start-up ones.
- Side effect found and undone: 12b's Save remembers its folder as the default for NEW 12b boxes, so the
  test save set it to the test folder; restored to `output\freedom` (git copy; also the folder in the
  user's latest run). The user's own 12b box keeps its own folder and was not affected.
- The Confirm/Cancel line was squashed into a narrow column; the viewer's top bar now uses the width
  between the arrows (checked on screen: buttons on one line, question + Confirm + Cancel on the next).
- Test files removed afterwards (12b folder holds only an empty `_links.json`; no zztest files left in
  the archive; the test folder removed). v02 not saved by Claude.

## 27. The blue "switch the order" button under the FINAL COMBINED PROMPT (user's choice 1)

- Choice 1: each click swaps Physical Description and Scene at once; the line under it says which order
  is in use; the choice is saved with the workflow.
- `freedom_prompt_slots/web/prompt_slots.js`: blue button "Switch the order of the Scene Prompt and the
  Physical Prompt" right under the final box, with "Order now: ... Physical Description, then Scene
  Prompt." (or the other way); stored as `"order": "scene_first"` in the final box's own saved parts (so
  it is saved with the workflow and marks it changed); the final box text, the watcher and the 7f order
  line follow it.
- `freedom_prompt_slots/nodes.py` `join_final`: reads the same "order", so what the engine gets matches
  the box. ComfyUI restarted for it (00:38, process 36964, log `logs/comfyui_2026-10-02_0038_*.log`, no
  errors). Backups: `_backups/swap_order_2026-10-02/`.
- Tested: server join both ways ("... PHYS, SCENE" / "... SCENE, PHYS", also with Portrait Master's
  words); in the page (v02 in Claude's own tab, not saved): button shown under the final box; one swap
  -> scene first in the box, line updated, workflow marked changed; a real mouse click swapped it back
  -> physical first, line updated, workflow back to unchanged. v02 file not written by Claude.

## 28. The end of the session: files, backups, lessons, loose ends and questions since section 20, and the commit

The user asked (2 Oct): "Add this activity to yesterday's (October 1) existing log in the REPO logs folder.
Push Committ". This section brings sections 17-20 up to date with everything after them.

### 28.1 More files changed after section 18 was written
- `custom_nodes/freedom_lora_stack/web/lora_stack.js` - All OFF | All ON pair (11), gray-side lettering
  #c8c8c8 -> #e2e2e2 -> #a0a0a0 (12, 14).
- `custom_nodes/freedom_portrait_control/web/facedetailer_presets.js` - repaint OFF | repaint ON (14).
- `custom_nodes/freedom_prompt_slots/web/prompt_slots.js` - shared on/off switch lettering (12, 14), her
  trigger word in the Summary Signal part and the single "any green button" watcher note (25), the blue
  order button (27).
- `custom_nodes/freedom_prompt_slots/nodes.py` - run-time log note ignores the trigger word (25);
  `join_final` follows the saved order (27).
- `custom_nodes/freedom_checkpoint_prefix/web/checkpoint_prefix.js` - trigger word shown locked (25).
- `custom_nodes/freedom_folder_inspector/save_pick.py` - copy notes (`_links.json`) and the
  `/freedom/save/delete` route with the Recycle Bin (26).
- `custom_nodes/freedom_folder_inspector/web/preview_pick.js` - viewer: Send to video workflow queue,
  DELETE with Confirm/Cancel, grid rebuilt after deletes, auto-start only from the video workflow (26).
- `CLAUDE.md` - STEP 6 lettering; every box in a STEP frame carries its letter; plumbing boxes stay
  unlettered; "do NOT create new workflow versions".
- `user/default/workflows/Freedom_SDXL_v02.json` - created (11), 6a text (13), letters (15); later saves are
  the user's own.
- Logs created: `logs/session_2026-10-01_full_record.md` (this file), `logs/confirm_box_buttons_2026-10-01.md`,
  and (folders - not saved to git, which keeps only files directly in logs/) `logs/face_ab_test_2026-10-01/`,
  `logs/face_likeness_scan_2026-10-01/`; ComfyUI output logs `comfyui_2026-10-01_1354/1934/1954_*`,
  `comfyui_2026-10-02_0030/0038_*`.

### 28.2 More backups (`_backups/` is not in git)
`_backups/lora_stack_onoff_2026-10-01/` (lora_stack.js, facedetailer_presets.js, v02 before the 6a text,
the user's 20:48 v02), `_backups/trigger_in_summary_2026-10-01/` (checkpoint_prefix.js, prompt_slots.js),
`_backups/viewer_buttons_2026-10-01/` (preview_pick.js twice, save_pick.py), `_backups/swap_order_2026-10-02/`
(prompt_slots.js, nodes.py).

### 28.3 More lessons
14. **A test save changed a remembered setting** (26): 12b's Save also stores its folder as the default for
    new 12b boxes; the test save set it to a test folder. Found by reading the code afterwards, undone from
    git. Lesson: check what a route writes besides its main job before using it in a test.
15. **A click "missed" because the button was off screen** (27). Checked by triggering the button from
    inside the page first, then clicking it for real once it was in view - not guessed.
16. **The user's tab can hold the workflow I am about to change** (15, 25-27). Done each time: read-only
    check of their tab, close it there only when it held no unsaved changes, back up, then edit; tests ran
    in Claude's own tab and were closed without saving.

### 28.4 Loose ends now
1. Frame corner drag - prove the bigger frame triangle works by hand (8).
2. ComfyUI runs from Claude's 00:38 start, not the launcher (log in `logs/comfyui_2026-10-02_0038_*`).
3. Reload the ComfyUI page to get every change of the evening.
4. Copies saved before 2 Oct 00:30 are not linked to their pictures, so the viewer's DELETE cannot remove
   them.
5. The face likeness question is open: the user dropped the training question (24); nothing was changed.
6. Not tested live: Face Competition Method 1 Rename; the 7c "replace" box; 4d-4h Save as / Rename.
7. Last night's crash cause is still unknown (2).
8. Three old test tabs of Claude's may still be open in Chrome ("*Unsaved Workflow - ComfyUI").

### 28.5 The questions after section 20, in order, with their answers
17. "I just turned off facedetailer, can you confirm it is not influencing the stream?" -> confirmed from
    the run record (21).
18. Side-by-side test (two / four pictures / none) -> **2** (22).
19. Reference picture (you name one / latest with repaint / other) -> **1**, with training photos and
    pictures 01693-01700 (23).
20. What the photos mean ("this is what she looks like" / training set mostly looking left / name a
    picture / other) -> **1** (23).
21. Next test (same-seed test / check the face file / both / other) -> **4: "no more tests. I think we need
    to focus on the training"** (24).
22. What "focus on the training" starts with -> **4: "drop this question"** - dropped.
23. Her trigger word's weight (edit there and sync / locked, set on the Face Shelf / Summary Signal in
    charge / other) -> **2** (25).
24. What DELETE removes (12b + archive / 12b only / every copy / other) -> **3**, "but make sure that
    deleting an image in 12b node does not cause an error somehow" (26).
25. How to restart ComfyUI for DELETE (Claude now / user's launcher / not now) -> **1** (26).
26. The blue order button (swap at once / swap on the next green button / other) -> **1** (27).
27. "Add this activity to yesterday's (October 1) existing log in the REPO logs folder. Push Committ" ->
    this section, then the commit below.

### 28.6 The commit
Everything waiting in the repo was committed in one commit on `main` and pushed, as earlier sessions did
- this session's work together with the changes that were already waiting at its start (section 1: the
earlier CLAUDE.md edits, the `face_training/` move to REPO_face and its log deletions, the older log
edits, `fresh_seeds.js`, the user's own saves of `Freedom_SDXL_v01.json`, and two `_archive_bigLust`
`.bak` workflow files).
