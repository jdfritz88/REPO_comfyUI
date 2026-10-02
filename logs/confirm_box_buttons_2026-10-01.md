# Confirm/cancel box for every "press again" button - 2026-10-01

## What the user asked
1. Last night (2026-09-30, after 10pm) ComfyUI crashed after a click/double-click on the
   STEP 7 Physical shelf. No error was found in `logs/comfyui.log` or the Windows event log.
   The page is the likely place it went wrong; the browser forgets its messages on reload.
2. Look for weak spots in the STEP 7 shelves where a stray click causes trouble. Seven found.
3. User chose "fix all seven", but Delete and Create new as ONE click then a
   confirm/cancel box, not a double-click.
4. Then: every "press again" button in the workflow gets the same box (answer 2).

## What changed
- `freedom_prompt_slots/web/prompt_slots.js` (STEP 7d/7e shelves):
  - Delete and Create new open a red confirm box under the buttons. Confirm ignores clicks
    for 0.5 s, so a double-click cannot get through. Delete names the preset and slot,
    and checks the shelf did not change before deleting.
  - Turning the dial, or pressing another shelf button, closes the box and stops a
    half-done Rename / Save as ("the dial moved, so that was cancelled").
  - Load / Rename on an empty slot no longer leave a hidden job behind: reaching a saved
    slot only shows "now press Load ..." - nothing runs by itself.
  - Save, Save as, Rename, Delete: no answer from ComfyUI is reported, never silent;
    one shelf change at a time (a 2nd click while one is running is ignored with a message).
  - Rename and Save as: the confirm box (see below).
- The shared "press again" pattern (makeRenamer) in all five files: the 1st press opens
  the name field AND the confirm box; pressing the button again does nothing; Confirm or
  Enter saves; Cancel or Esc stops. Files:
  `freedom_prompt_slots/web/prompt_slots.js`, `freedom_checkpoint_prefix/web/checkpoint_prefix.js`,
  `freedom_portrait_control/web/facedetailer_presets.js`, `freedom_portrait_control/web/portrait_control.js`,
  `freedom_face_competition/web/presets_method1.js`.
- STEP 7c Summary Signal: "Delete model text" and "Save as" over another model's text
  ("Press again") now use the box. Changing the STEP 1 model closes any open box.
- STEP 11c FaceDetailer presets: Delete ("Press again to delete") now uses the box.

Backups of every file before the change: `_backups/shelf_confirm_box_2026-10-01/`.

## Bug made and fixed during the work
First version ignored the 2nd click of a double-click on Save as, but that click's
mousedown had already moved the keyboard onto the button. Typing a name then pressed the
button with each space and saved two extra "woman 18" copies (test only). Proven with a
focus log (mousedown -> focus BUTTON). Now the box's buttons keep the keyboard in the
name field, and a 2nd press of the button hands the keyboard back. The two test copies
were removed by restoring `user/default/freedom_physical_slots.json` from the backup
(md5 92f165359fa694ef43a20efcfde5e81d, same as before testing).

## Tested in the live page (Freedom_SDXL_v01, ComfyUI started by Claude 2026-10-01)
- 7e Physical shelf: double-click Create new -> box only, box text kept; Cancel.
  Double-click Rename -> box only, typing lands in the name field; Cancel restores the name.
  Save as -> type -> Confirm: exactly one new preset. Double-click Delete -> box only,
  nothing deleted; dial turned -> box closed with message; Delete -> Confirm -> deleted.
  Save (overwrite) with the page's network call blocked -> "ComfyUI gave no proper answer".
- 7c Summary Signal: Delete -> box -> Cancel (model text still saved). Save as -> box -> Cancel.
- 11c FaceDetailer: Delete -> box -> Cancel (preset kept). Rename -> box -> Esc.
- 4c Portrait Master: Save as -> box -> Esc.
- NOT tested live: Face Competition Method 1 (not in Freedom_SDXL_v01); the
  "replace another model's text" box in 7c Save as (needs a 2nd model with text);
  4b and 4d-4h (same code as 4c).
- The browser tool's screenshot timed out several times right after a canvas change; the
  page itself was measured running at ~98 frames a second at those moments, and the
  console showed no errors from these files (only two from ComfyUI's own start-up).

## Not done
- Weak spot 5 (dragging the bottom edge of a box by accident pushes boxes below down):
  waiting on the user.
## Later the same day: Portrait Master's Delete buttons (user answered 1)
- Who made them (checked, not recalled): both Delete buttons are in our add-on
  `freedom_portrait_control/web/portrait_control.js` ("FREEDOM SYSTEM - Portrait Control").
  `git log -S` puts the 4b-4h preset Delete in commit 5be5a7b (2026-09-18) and the STEP 3b
  "Her recipes" Delete in f312dcd (2026-09-22). The developer's
  `comfyui-portrait-master` (github.com/florestefano1975) has no "delete" in any .js/.py file.
- Both used to delete on ONE click. Now one click opens the confirm/cancel box; Confirm
  deletes, and only if the menu still shows the same entry.
- Tested live: 4b Delete on "User Preset 01" -> box -> Cancel (kept). STEP 3b Her recipes:
  Save as "zz test delete me" -> Confirm (saved as tl_zz test delete me), double-click
  Delete -> box only, nothing deleted -> Confirm -> deleted. Every file in
  user/default/portrait_presets has the same md5 as before testing (backup:
  `_backups/shelf_confirm_box_2026-10-01/portrait_presets/`).

## Later the same day: easier resize handles on boxes and frames (user answers 4, then 2)
- Read from ComfyUI frontend 1.53.6 first: box corners are `[data-corner]` grab squares,
  20 x 20 (class h-5 w-5), hidden until hover (GraphView-*.js); frames resize only from a
  bottom-right triangle `LGraphGroup.resizeLength = 10` (settingStore-*.js), drawn with the
  same number; old canvas boxes use `LGraphNode.resizeHandleSize = 15`.
- New add-on of our own: `custom_nodes/freedom_canvas_handles/` (web/canvas_handles.js).
  Box corners 40 x 40, centred on the corner, always faintly showing (opacity 0.35, full
  over the box). Frame corner triangle 25. Canvas-box corner 30. ComfyUI files untouched.
  ComfyUI restarted to load it (stderr log `logs/comfyui_2026-10-01_1934_stderr.log`:
  loaded, no errors).
- Tested live: corners measured 40 x 40 with opacity 0.35; screenshot shows the faint
  marks on every corner and the bigger frame triangle. Real drag from just OUTSIDE the
  STEP 1c box's bottom-right corner resized it (550x150 -> 650x220), then put back to
  550x150. No two boxes overlapped before or after (checked on every box).
- Frame corner: the page's own test (`isInResize`) says a point 8 in from the corner now
  counts (it would not have at 10). Two real drags there did NOT resize the frame, and
  `document.elementFromPoint` returned nothing at that point - cause not found; stopped
  rather than guess. Needs a hand test.
- User rule given during this test: when Claude resizes boxes, they must never overlap
  other boxes (saved to memory). The STEP 1c test resize did not overlap any box; it did
  run past the STEP 1 frame's edge and over the frame corner.
