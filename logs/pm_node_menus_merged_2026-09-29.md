# Portrait Master 4b-4g: "In charge" merged into each node's own preset menu (2026-09-29)

## What the user decided
- Q66 = 1: merge the per-node "In charge" dropdowns (4b-4g) into each node's own preset menu, the same
  way 4a's was merged, with a description beneath every entry.
- Q73 = 1: go ahead with the plan.

## What changed, in plain words
- Each Portrait Master node (4b Base Character, 4c Face Generator, 4d Skin Details, 4e Style & Pose,
  4f Make-up, 4g Prompt Styler) no longer has an "In charge" row. Its preset menu decides:
  - "Use the dials (no preset)" - only your dials count. Factory reset works here.
  - a saved preset - it loads UNLOCKED: it fills the dials still at the developer's starting value and
    leaves the dials you changed alone. The old locked choice ("Use this node's preset") is gone.
- A description box under every node's menu, with Edit description / Save / Save as. Every entry starts
  as "needs description". Your own presets keep their description in their own file; "Use the dials" and
  Portrait Master's own presets keep theirs in OUR file
  (`user/default/portrait_presets/builtin_descriptions.json`, as "<NodeClass>::<name>").
- Portrait Master's own presets can't be renamed or deleted from the node (buttons greyed), and the
  server now refuses to delete them too (before, only the buttons stopped it).
- 4a: the six hidden "<step>_mode" dropdowns (n4b_mode ... n4g_mode) are hidden on screen and not read.
  4a still takes charge when it has a saved preset or a z_ choice - the node menus are greyed then.
- The explanation text shown on every node was rewritten (it still described both old dropdowns).
- Older workflows still open; an old saved "node preset" (locked) choice is now treated as unlocked.
- Not changed: Portrait Master's own files, the v09 workflow file.

## Files
- `custom_nodes/freedom_portrait_control/__init__.py`: `effective_node_mode()`; the prompt hook reads
  only each node's preset; description routes take a `scope` (4a = "user", or a node class); delete
  refuses Portrait Master's own presets.
- `custom_nodes/freedom_portrait_control/web/portrait_control.js`: the panels as above.
- Backups: `_backups/pm_node_menus_2026-09-29/` (both files, builtin_descriptions.json, and a copy of
  Portrait Master's own preset folder).

## Tests (ComfyUI restarted through the launcher, v09 opened fresh)
- All six nodes: "In charge" row hidden, menu starts on "Use the dials (no preset)", description box shows
  "needs description", Rename/Delete greyed for built-in entries. 4a's n4b_mode ... n4g_mode hidden.
- Each node: Save as "zz test A" with a description, then Save as "zz test B" with another - both files
  written with their own descriptions (A unchanged by B). Picking A: its description shows, mode
  "node preset + unlocked", no dial locked, Rename/Delete available. Back to "Use the dials": mode
  "ignore presets", Factory reset available. (A first run overlapped a second one because Chrome slowed
  the background tab; 4e and 4g were re-run alone and passed.)
- Save on a user preset (4f) changed only that preset; the other kept its description.
- Built-in descriptions: 4d "Use the dials" and 4b "Preset basic" (Portrait Master's own) saved to our
  file and came back after reloading the workflow. Portrait Master's preset folder byte-identical to the
  backup afterwards. Server delete of "Preset basic" refused; file still there.
- 4a in charge: "z_block all nodes" -> 4d menu and buttons greyed ("4a: z_block all nodes - this node is
  OFF"); "User Preset 01" -> 4d menu greyed ("4a preset, dials unlocked"); "-- none --" -> 4d back.
- Pictures (CyberRealistic Pony, seeds 111111 / 222222 / 333333): 4d preset "zz test C" (pores 0.5,
  freckles 0.4) picked, then freckles set to 1.0 and pores back to 0 on screen. All three jobs ran with
  pores 0.5 (filled from the preset, the dial was at its starting value) and freckles 1.0 (your change
  kept). Log each time: "PortraitMasterSkinDetails: preset 'pm_zz test C' (node preset + unlocked)".
- An old-style job with n4d_mode = "node preset" (locked): freckles stayed 1.0 - the old locked choice is
  ignored.
- Cleanup: all test presets deleted, builtin_descriptions.json restored from the backup, the test
  workflow closed without saving; v09 file unchanged (same fingerprint).

## Noticed, not changed
- Portrait Master's own preset folder holds "Random02" (BaseCharacter, dated 25 Sep) and
  "test_verify_face" (FaceGenerator) besides the developer's "Preset basic". They were there before
  this work. "Random02" is the one Portrait Master's own save switch kept writing while v09 had it on
  (found 28 Sep, session record section 11).
