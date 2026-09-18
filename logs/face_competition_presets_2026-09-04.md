# Face Competition — Method 1 presets

**Date:** 2026-09-04
**Branch:** Branch04_improvement

## What was built

A new node, `FreedomPresetsMethod1`, placed at the top of Method 1's group
in the workflow. It saves and loads a named snapshot of **every widget
value** across **every node** tagged `freedom_method == "1"` — the face
swap, both hair fixes (repaint + transfer), and their shared setting nodes.
It does nothing at graph-execution time; the panel reads and writes other
nodes' live widgets directly, the same way `FreedomFaceComp`'s skip
checkboxes already do.

Panel (`web/presets_method1.js`):
- A dropdown of saved presets, an editable name box, and four buttons:
  **Load Selected Preset**, **Save Loaded Preset**, **Duplicate Loaded
  Preset**, **New Preset**.
- The currently-loaded preset shows a green circle (🟢) next to its name,
  both in the dropdown and in a "Loaded: X 🟢" readout above it.
- **Duplicate** and **New** both end by auto-focusing and auto-selecting the
  name box, so typing immediately overwrites the auto-generated name
  ("X copy", "New Preset") with whatever the user wants.
- On first load ever (no presets saved yet), the panel automatically
  snapshots whatever Method 1's nodes are currently set to and saves it as
  a preset named **"Susana"**, marked as loaded.

Backend (`nodes.py`, `comfyui/presets1` routes): a plain JSON file
(`freedom_face_competition_presets_method1.json`, alongside the existing
`freedom_face_competition_state.json` - not tracked in this repo, same as
that file) holding `{"loaded": name, "presets": [{"name", "values"}]}`,
where `values` is `{node_id: {widget_name: value}}`. Five endpoints:
`list`, `save` (overwrite by name), `new` (fresh name from given values),
`duplicate` (copy a named preset's values under an auto-generated new
name), `rename`, and `load` (bookkeeping only - marks which one is
"loaded" for the green dot; the panel applies the actual values itself).

No delete endpoint - not asked for, left out rather than added speculatively.

## Verified, not just built

Tested every button directly against the live node graph (not just the
REST API) via the browser: tweaked a live widget value, confirmed **New
Preset** captured that exact changed value under an auto-generated name
with the name box focused and selected; **Duplicate Loaded Preset** copied
the *saved* values of the loaded preset under `"<name> copy"`, same
focus-and-select behavior; typing a new name and blurring correctly
renamed the preset server-side; switching the dropdown and clicking **Load
Selected Preset** genuinely wrote the saved values back onto the live
node widgets (checked one specific widget's value before and after);
**Save Loaded Preset** overwrote the currently-loaded preset with a
freshly tweaked live value. Also confirmed the "Susana" auto-seed
captured all ~20 Method 1 nodes' real settings, including the crop-widening
fix from the same session (`dilation_ratio: 1`, `grow_mask_by: 64`).

One fix made after first testing: the initial version also captured the two
`MarkdownNote` explanation nodes' text as if they were settings (harmless,
but not a "dial or slider" as asked for) - excluded `MarkdownNote` from
`method1Nodes()` before finalizing.

## Files

- `comfyui_ext/freedom_face_competition/build_face_competition.py` - new
  node 190, placed at the top of Method 1's (now taller) group box.
- `comfyui_ext/freedom_face_competition/nodes.py` - `FreedomPresetsMethod1`
  class + the five `/freedom/presets1/*` routes.
- `comfyui_ext/freedom_face_competition/web/presets_method1.js` - the panel.
- `comfyui_workflows/Freedom_Face_Competition.json` - regenerated.
