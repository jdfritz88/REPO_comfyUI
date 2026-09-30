# Session record, 26 to 29 September 2026 - every detail

This is the written record of everything done since the last written section (section 15 of
`logs/two_lora_stacks_v08_2026-09-25.md`, late evening 25-26 September). It is long on purpose: the user asked
for "a painfully detailed log". Times are local. Each part says what the user asked, what was found, what was
built, how it was tested, what went wrong, and what is still open.

Why this file repeats so much: the per-test folders under `logs/` (pictures, sheets, `results.json`, each
test's own `LOG.md`) are NOT in git - `.gitignore` keeps only the top-level `.md` / `.py` / `.json` files of
`logs/`. So this file carries the essentials of those untracked records, and names where the full ones are
on disk.

Files named "workflow v08" / "v09" are `user/default/workflows/Freedom_bigLust_SDXL v08.json` / `v09.json`.
"The art model" = the checkpoint picked in STEP 1 (cyberrealisticPony_v110 unless stated).

---

## Contents
1. FaceDetailer: official names, presets, reset, note numbers (26 Sep)
2. Recipes hold every LoRA slot and every FaceDetailer dial; "susana closest 02" cleaned (26 Sep)
3. An add-on built by mistake and removed (26 Sep)
4. The 99-picture FaceDetailer likeness test (26-28 Sep)
5. New node-group layout rule, v09 and STEP 3 (26-27 Sep)
6. STEP 7 letters in v09 (27 Sep)
7. Memory pressure, stopped helper programs, the face training overlap (27-28 Sep)
8. Why each picture loads the art model more than once (Q5, 28 Sep)
9. Reading log types 1 and 13 (28 Sep)
10. v06 log Part 7 corrected (28 Sep)
11. The eye-sharpening tests, runs 1-6 (28-29 Sep)
12. Research: developers and community on prompt order, Pony, Prompt Control (29 Sep)
13. The STEP 7 tests, "seven ways to Sunday" (29 Sep)
14. Score tags, Danbooru, Prompt Control's special words - the answers given (29 Sep)
15. The project: checkpoint front text, new prompt order, Portrait Master on/off, one 4a menu,
    descriptions, Save as everywhere, no auto-save (29 Sep)
16. Rules written into CLAUDE.md during this period
17. Mistakes and near-misses by Claude
18. State left behind, and open questions

---

## 1. FaceDetailer: official names, presets, reset, note numbers (26 Sep)

User asked (paraphrased from the conversation): STEP 11 nodes should show the OFFICIAL node name first and
the nickname in brackets; the description note's default denoise number was wrong; set denoise to the
lowest sensible value (user picked 0.15); a "Reset to Developer's Defaults" button that resets ALL dials to
the Impact Pack developer's values, with a full presets package above it; every preset name gets a prefix
from STEP 2: `tl_` (trained face) or `pl_` (random face / Portrait Master); a preset records EVERY dial;
the first preset holds denoise 0.15.

Built:
- Titles in v08 (and later v09), e.g. "STEP 11b  -  FaceDetailer (face repaint)  -  Repaint the face as her",
  "STEP 11a  -  UltralyticsDetectorProvider (face finder)  -  Find her face".
- FaceDetailer denoise set to 0.15 in the node.
- Note 37 ("STEP 11 - every FaceDetailer dial explained") numbers corrected: max_size 1024, feather 8,
  bbox_crop_factor 3.0, cycle 2, wildcard "wired - gets her code word from STEP 3".
- STEP 3 note strength line rewritten to the 0.4 / 1.0 defaults.
- `custom_nodes/freedom_portrait_control/web/facedetailer_presets.js` (new, page only): a panel at the top of
  the FaceDetailer - "FACEDETAILER PRESETS - every dial, saved by name" - list, Load, Save, prefix label,
  name box, Save as, Rename, Delete (press twice), "Reset to Developer's Defaults", message line.
  Scope "facedetailer" in `user/default/portrait_presets/facedetailer/`. `capture()` takes all 29 values
  (control_after_generate included); loading skips inputs that are wired (the wildcard).
  The developer defaults come live from `/freedom/pm/defaults?node=FaceDetailer` (read from Impact Pack's
  class, so an update changes them automatically). Developer default denoise is 0.5.
- First preset `tl_denoise 0.15.json`: guide_size 1024, guide_size_for true, max_size 1024, seed
  1736114183 fixed, steps 26, cfg 6, dpmpp_2m karras, denoise 0.15, feather 8, noise_mask true,
  force_inpaint false, bbox 0.5 / 10 / 3, cycle 2, and the rest.
- A first field-mapping attempt gave 25 names against 29 values; fixed by including optional inputs.
- User decision (Q3): keep the FaceDetailer ON at 0.15 as the default; tests run at 0.30.

## 2. Recipes hold every LoRA slot and every FaceDetailer dial (26 Sep)

User: a recipe must include all LoRA slots - shelf, face-stack rows and general rows, empty ones included -
and EVERY FaceDetailer dial; delete the dead face slots in "susana closest 02".
Built in `custom_nodes/freedom_portrait_control/web/portrait_control.js`: STACK_SLOTS = 4, the Selected Face
LoRA Stack rows, FreedomPromptParts' two boxes, `allDials(detailer)`; `applyRecipe` applies every
FaceDetailer key except wired ones. Backup `portrait_control_before_recipe_9slots.js`.
"tl_susana closest 02" / "pm_susana closest 02": lora_stack set to 4 empty slots (OFF, "", 0.8); shelf 0.6 kept.

## 3. An add-on built by mistake and removed (26 Sep)

When the user asked for "a preset" holding denoise 0.15, Claude first built an add-on that changed the code
default. The user: "Addon? I meant to say preset". It was removed before it was ever active; the preset in
part 1 was made instead.

## 4. The 99-picture FaceDetailer likeness test (26-28 Sep)

User: at denoise 0.3, test five settings Way A / Way B - #1 an extra LoRA in the wildcard, #3 wildcard with
[CONCAT], #4 max_size 2048, #5 force_inpaint ON, #6 cfg 8 - all 32 combinations (Q28 = 1), three seeds
(111111 / 222222 / 333333 - "drop the 444"), plus 3 repaint-OFF references; every picture labelled with its
row, its dial and its Way B.

Research used: Impact Pack `core.py:267-276` - a filled wildcard REPLACES the positive prompt unless it
starts with `[CONCAT]`; `wildcards.py` can load a LoRA from `<lora:name:strength>`; `resolve_lora_name`
matches with endswith, so the tag is `<lora:susana_head_sdxl_pony:1.0>` (not `faces/...`).

Run 1 (26 Sep night) went wrong:
- A Face Tool training run for Susana started 00:31 (27 Sep) and shared the graphics card. Pictures took 6-8
  minutes instead of ~35 s; the script's 10-minute wait ran out, so records said "TIMEOUT" while ComfyUI was
  still working, and the next job's log text was filed against the wrong picture. Claude stopped the script
  and reported it.
- User chose Q32 = 1: wait for the training to finish, then rerun from the start. Claude wrote a waiting
  script that watched ONE process (35600). The training actually ran four jobs one after another
  (susana_head_sdxl ended 06:40; susana_head_body_sdxl failed "train exit 1; no LoRA produced";
  susana_head_sdxl_pony ended 28 Sep 00:07; susana_head_body_sdxl_pony 03:56). The waiter started the test at
  06:40 while training continued; jobs took 47 min to 3.5 h; all six records TIMEOUT; the script later
  crashed when ComfyUI stopped answering. Claude's mistake: assumed one process = the whole training.
- The training REPLACED `susana_head_sdxl_pony.safetensors` (28 Sep 00:07). No copy of the old file exists
  (searched all of freedom_system). Q35 = 1: run the test with the new file.
Run 2 (28 Sep): 99 / 99 succeeded. At first ~232 s per picture, then back to ~40 s by itself (cause not
found). The wildcard LoRA loaded in all 48 LoRA pictures (log "LOAD LORA"). 8 pictures were not repainted -
all seed 333333 with max_size 1024 and force_inpaint OFF: FaceDetailer skips a face already larger than it
would paint (`core.py`: "segment skip [determined upscale factor=0.98 or less]").
The 9 contact sheets were sent to the user in the conversation (Q37 = 1). Likeness is the user's judgement.
Files: `logs/facedetailer_likeness_grid_2026-09-27/` (untracked).

## 5. New node-group layout rule, v09 and STEP 3 (26-27 Sep)

User rule (memorialised in CLAUDE.md): node #a = description note; #b = switches or preset/reset/save
packages; #c = the control panel (the user wrote "#v"; Q30 = 1 confirmed #c); the next column repeats (#d, #e,
#f ...); the prompt saver/loader and the phrase saver/loader are separate.
User (Q?, "call it v09 because I'm doing work in v08"): v09 = copy of v08 as of 26 Sep 09:52, then STEP 3:
- node 22 "STEP 3a - pick her face" (description)
- node 2 "STEP 3b  -  Freedom_Face_Shelf  -  Pick a face!" - strength and trigger_weight on one row above
  "enabled" (`selected_face_stack.js`, new `freedom_sfs_shelf_row` DOM row; native widgets hidden); two
  thumbnails per row (`face_shelf.js`, grid of 2); the recipes package kept inside the shelf node
- node 46 "STEP 3c  -  FreedomSelectedFaceLoraStack  -  Extra passes of her face (trained face only)"
- notes 13, 15, 22, 23, 37 updated to 3b / 3c; note 22 leftover "STEP 3b" fixed.
Tested three times in a fresh tab: 0 value mismatches, 2 columns, row edits save and update both "Current"
counters and the trigger text ("(lorasusana:1.25)"). v08's screen also changes after a reload (shared page
code); v08's file was not changed.

## 6. STEP 7 letters in v09 (27 Sep)

Q31 = 3 (keep the prompt and phrase nodes as they are, only re-letter); Q33 = 3 (plain order, no gaps);
Q34 = 1 (do it in v09). Titles: node 15 "STEP 7a - what you want", node 45 "STEP 7b  -  FreedomPromptParts
...", node 43 "STEP 7c - your saved phrases", node 44 "STEP 7d  -  FreedomPhraseSlots ...". Note 15 "(STEP 7a)"
-> "(STEP 7b)"; note 43's four "STEP 7a" -> "STEP 7b". Only 6 fields changed (checked against the backup
`_backups/step7_letters_2026-09-27/`). Loaded 3x: 40 nodes, 0 mismatches. Recorded in CLAUDE.md.

## 7. Memory pressure, stopped helper programs, the training overlap (27-28 Sep)

- Claude Code stopped idle background helpers when memory ran low: the launch page (8190) and the picture
  pages (8191, 8192) on 27 Sep; the waiting script on 28 Sep (its process actually survived); the eye test
  on 28 Sep after 4 of 12 pictures.
- Measured 28 Sep: 6.3 of 31.7 GB free; ComfyUI ~10 GB private memory.
- User (Q40 = 3, "you do it safely. Shut down ooga and all talk"): AllTalk was already not running;
  oobabooga was stopped with Ctrl+C sent to its own console (`scratchpad/ctrl_c_console.py`, AttachConsole +
  GenerateConsoleCtrlEvent); its programs closed themselves in ~8 s; its leftover empty cmd window (pid 46704)
  was closed. Free memory 6.3 -> 8.3 GB. Later long runs were done in the foreground, which the memory
  shutdown does not touch.

## 8. Why each picture loads the art model more than once (Q5, 28 Sep)

Q5 = 1 (look into the cause, report before changing anything); Q38 = 3 (skip the second run).
- Watched one picture as our own client (`scratchpad/watch_nodes.py`): CheckpointLoaderSimple ran 3 times,
  the face shelf 3, both LoRA stacks 2, FaceSource 4, router 2, the on/off branch 2; KSampler and FaceDetailer
  once each; 33 node runs for 22 nodes; 39.5 s; the repeats ~2.5 s.
- Cause, read in ComfyUI's code: the launcher starts ComfyUI with `--cache-none` whenever auto-swap or Video
  Mode is on (`REPO_koboldccp_sst_tts_media/launcher.py` 831-832). `--cache-none` -> `CacheType.NONE`
  (`main.py` 330-336, `execution.py` 122-124) -> a null cache whose get / get_local always return None
  (`comfy_execution/caching.py` 411-435). Two v08/v09 nodes ask for inputs lazily (the Face Router and the
  repaint on/off branch); a lazy request finds "not cached" and `add_strong_link` / `add_node`
  (`comfy_execution/graph.py`) re-queue that node and everything before it, back to the model loader.
- Where `--cache-none` came from: the user asked for it for the 14B video model ("this cache none, no whisper,
  all talk launch"); it fixed a ~40x slowdown together with stopping the voice apps.
- NOT proven: that dropping `--cache-none` makes each node run once; its memory cost; whether dropping it
  brings back the video slowdown. Nothing changed. Record: `logs/q5_model_loading_2026-09-28/FINDINGS.md`
  (untracked).

## 9. Reading log types 1 and 13 (28 Sep)

User: read the logs in `logs/` - "Just 1 and 13" (the 42 session records + 2 copies of the user's messages).
Four helper agents read all 44 files to the last line (line numbers reported per file). Findings written to
`logs/log_read_types1_13_model_loading_2026-09-28.md` (tracked): only the v08 log named the repeated
loading; `--cache-none` came from the video work; no log explained the cause.

## 10. v06 log Part 7 corrected (28 Sep)

Q6 = 1: a clearly marked correction at the top of Part 7 and next to defect #5, original text kept. The
"two passes at 0.9" test had really been one pass (the general stack threw the face LoRA out -
`freedom_lora_stack/nodes.py:188` at the time); passes add up (tested 25 Sep: shelf 1.1 = 0.6 + 0.5 within
rounding). Backup `_backups/v06_log_correction_2026-09-28/`.
Also closed on request: Q7 (STEP 6 in random face - STEP 6 never loads face LoRAs), Q16, Q9 = 3 (leave
CLAUDE.md as it is regarding the 28 log-only rules; the list was reconstructed from a 25 Sep helper report
and shown to the user).

## 11. The eye-sharpening tests (28-29 Sep)

Q8 (sharper eyes on the Portrait Master path, 1216x832). User: test options 4 (Civitai eye finders) and 6
(ComfyUI's own MediaPipe) on v09; Q39 = option 3: rows base, Full Eyes, Eyeful, MediaPipe; captions BENEATH
each picture, never on it.

Downloads (user-approved), fingerprints checked against the sites:
- `models/detection/mediapipe_face_fp32.safetensors` - Comfy-Org Hugging Face, 5,423,900 bytes
  (sha256 a98c4806...)
- `models/ultralytics/bbox/full_eyes_detect_v1.pt` - Civitai 330727 v1.0 (zip sha256 1EEF7079...)
- `models/ultralytics/bbox/Eyeful_v2-Paired.pt` - Civitai 178518 v2 Paired (zip sha256 612F6F06...)
- Both .pt files were read WITHOUT loading (pickletools): they refer only to torch / ultralytics model classes,
  collections.OrderedDict and set - nothing that opens programs, files or the internet.
Base: v09 exported from a fresh tab (every input equal to the v08 test job); test-only changes: STEP 2
random face, one picture, seeds, Portrait Master's seven random picks fixed per seed with
`random.Random(seed)`, and Portrait Master's save_preset OFF (v09 had it ON as "Random02" - found here).
Eye repaints used v09's FaceDetailer dials with denoise 0.5 (developer default) and threshold 0.4.
- Run 1 (Portrait Master's random expressions Confused / Peaceful / Calm): 12 / 12. Full Eyes / Eyeful found
  one area per picture, and in seed 111111 a second area = the man's eyes (his face changed). MediaPipe found
  both of her eyes separately (enlarged up to ~15x). No rolled-back eyes in any base picture.
- Run 2 (Q41 = 1, Portrait Master expression "-"): 12 / 12; still no rolled-back eyes; Full Eyes / Eyeful
  turned grey-green / brown irises blue; MediaPipe closest to the base. A first sheet build read run 1's
  results by mistake (folder path not changed) - deleted and rebuilt before sending.
- The user opened Row 1's settings in a temporary tab (Q43 = 2) and changed "orgasm expression" 1.1 -> 1.3 -
  first in the "Doggy01" saved window (never read by the picture), then in the "everything else" box.
  Found: the "physical" box is empty in v09 (the scene box carries most of the looks).
- Run 3 (the user's box at 1.3): 12 / 12; still no rolled-back eyes.
- Wiring check (user: "Its not wired correctly if the prompt is being ignored"): text captured with "Preview
  as Text" - the finished prompt contains "(eyes rolled back, orgasm expression:1.3)"; Prompt Control vs plain
  encoder differ only as expected; `freedom_prompt_fixups` only touches seed words. No wiring fault found.
- Run 4 (Q46 = 2, box first, then Portrait Master): 12 / 12; eyes looked more upward; whole pictures change
  with word order.
- Run 5 (user: 1 Portrait Master, 2 FaceDetailer without MediaPipe, 3 FaceDetailer with MediaPipe; no Portrait
  Master for 2 and 3): 9 / 9; Test 1 pixel-identical to run 3's base.
- Run 6 (user: 1 Portrait Master + FaceDetailer switched OFF, 2 disconnected): our own
  `freedom_portrait_control` hook switched Base Character back ON in all three "off" jobs (log:
  "PortraitMasterBaseCharacter switched on (start = base)") - so "switched off" was not off. "Disconnected"
  worked and matched run 5's no-Portrait-Master pictures exactly.
- Deep check of run 6 Test 2 (user: "dig deep, then dig deeper"): wires traced (13 nodes, none Portrait Master
  / router / 4a / FaceDetailer), hidden inputs (only SaveImage, metadata only), all three job hooks, and a live
  watched rerun (Portrait Master nodes, router and 4a never ran; 0 LoRA patches); pixel-identical. Sheet with
  the difference image sent.
Full records: `logs/eye_sharpen_test_2026-09-28/` (untracked; LOG.md, results, sheets, close-ups).

## 12. Research (29 Sep)

Two read-only helpers (developers; community). Main points, with sources given to the user:
- Portrait Master's author sets no order rule ("simple texts, so you can use them however you like", issue
  #11; options "have no effect if the checkpoint does not 'understand' the requests", issue #39); his example
  puts his text first; his old guide calls the end of a prompt "minor compared to the rest".
- Prompt Control (asagi4): without its special words it works "exactly like ComfyUI's standard text encoding
  node" (issue #104); `[a:b:0.5]` is a halfway switch; special words work only in CAPITALS.
- ComfyUI: long prompts are cut into ~77-token pieces and all reach the model (comfyanonymous, issue #6200).
  Verified in code by Claude: only the FIRST piece feeds SDXL's "summary" (pooled) signal
  (`comfy/sd1_clip.py` first_pooled; `comfy/model_base.py` encode_adm); within a piece each word is read in
  light of the words before it (`comfy/clip_model.py:174`, causal mask); for SDXL ComfyUI already uses the
  penultimate layer ("clip skip 2", `comfy/sdxl_clip.py`).
- Pony author: template "score_9, score_8_up, ..., score_4_up, just describe what you want, tag1, tag2";
  score_9 alone "has a much weaker effect". CyberRealistic Pony page: "score_9, score_8_up, score_7_up,
  (SUBJECT)", CFG 5, 30+ steps, 896x1152 / 832x1216, "it's also possible to remove the normal pony tags".
- Community: the Danbooru tag "rolling_eyes"; a CyberRealistic Pony prompt tool puts pose/act first; eye
  detailers turn eyes blue and can wipe expressions; none makes rolled-back eyes by itself.

## 13. The STEP 7 tests (29 Sep)

User: "something is wrong with the Node group 7. I need you to test the node seven ways to Sunday."
Q49 = 2 (every test twice: A without Portrait Master, B with it first), Q50 = 5 (the seven tests + four
research tests). Base = the user's Row 1 tab, no face repaint.
- Test 1 (text only): STEP 7b's output exactly as expected in 8 / 8 cases.
- 63 / 63 pictures. bigLust really loaded for Test 7.
- Pixel checks: without Portrait Master, STEP 7's encoder = plain CLIPTextEncode fed by STEP 7b = the same
  text typed straight in with NO STEP 7 node - identical in all three seeds. STEP 7 is not the cause.
- Seen (Claude's look): Extra 4, the Danbooru-style tags "(rolling eyes, ahegao:1.3)", "doggy style",
  "all fours", gave rolled-back eyes in all 6 pictures (A and B); nothing else did. Moving the act/pose/eye
  words to the front (Test 5) fixed seed 111111's wrong act. The biggest effect came from the words the model
  learned, not their position (the user was reminded that Extra 4 kept the original order).
- Where the words came from (user asked): Claude's test script, from the research; nothing in ComfyUI,
  Portrait Master, our add-ons or the model file's notes (cyberrealisticPony_v110 has none) supplies them.
Full record: `logs/group7_tests_2026-09-29/` (untracked). Link pages were served on 127.0.0.1:8191 / 8192.

## 14. Answers given about score tags, Danbooru and Prompt Control (29 Sep)

- Score tags (from the Pony author's article "What is score_9 ..." read by Claude): an aesthetic rank of each
  training picture (the author ranked pictures by hand, then trained a ranker; "1 to 5 rank ... now a 0 to 1
  rank"); "score_8_up" = "80% good and up"; the whole string was learned as one ("Clever Hans"); "copy paste
  it into beginning of all your prompts"; a warning that the tags carry bias with style LoRAs. "tag1, tag2"
  are placeholders for short tags after the description. Worked example and a block map given.
- Prompt Control's special words belong to Prompt Control (asagi4), read by the STEP 7 encoder
  (PCLazyTextEncode); not ComfyUI, Portrait Master or CyberRealistic.
- Danbooru explanation saved for the future checkpoint hints: `logs/checkpoint_hints_build_plan_2026-09-29.md`.
- ComfyUI itself has no preferred order for physical vs action (docs silent; the only code fact is the first
  piece's summary signal).

## 15. The project (29 Sep)

Decisions: Q56 = B made general; Q61 = 2 (action and scene before physical, for every model); Q59 = 1 (v09);
Q60 = 4 + Q62 (the z_ choices); Q64 = 4 (move "In charge" into the menu); Q65 = 3 (saved presets load
unlocked, no auto-save, Save as everywhere); Q67 = 1 (go).

15.1 Checkpoint front text - `custom_nodes/freedom_checkpoint_prefix/` (new):
- Node "Freedom Checkpoint Front Text (per model, goes first)". Reads STEP 1's model from the job (hidden
  PROMPT input; exactly one loader, else a warning and nothing added); IS_CHANGED = nan; one log line per run.
- Storage `user/default/checkpoint_prefix/<model>.json`; starting entry cyberrealisticPony_v110 ->
  "score_9, score_8_up, score_7_up" (CyberRealistic's recommendation). bigLust, lustify Krea: none -> n/a.
- Panel: model name, box, Edit / Save / Delete (press twice), Save as (pick another model; asks before
  replacing), PROMPT WATCHER (finished prompt of the last run + status).
- Bug found and fixed: it followed STEP 1 by a timer, which Chrome slows in background tabs (showed the old
  model after 2.5 s); now hooked to the picker's own change, timer as backup.
15.2 New prompt order - `custom_nodes/freedom_prompt_slots/nodes.py` FreedomPromptParts: new optional input
"front"; join order front -> trigger -> EVERYTHING ELSE -> PHYSICAL (was trigger -> physical -> everything
else); returns the finished prompt to the page. Boxes still drawn physical-above.
15.3 v09: node 47 under the STEP 7 note, wired to STEP 7b "front" (link 89; trigger link 60 moved to slot 1);
STEP 7b moved down 460; group taller; note 15 explains the order. Its title has no letter yet (Q52).
15.4 Portrait Master on/off - the z_ choices at the bottom of STEP 4a's top menu: "z_block all nodes",
"z_unblock and open all nodes WITH Base Character (Face Generator must be OFF)", "... WITH Face Generator
(Base Character must be OFF)" (the missing closing bracket in the user's first name was added). Server: on/off
outright, no preset values, no node presets, no pair forcing; refused by save / rename / delete. Page: node
switches shown, z_block greys and locks all, an open choice greys only the node that must be off.
Bug found and fixed: after z_block an open choice left Skin / Style / Makeup grey.
15.5 One STEP 4a menu: "In charge" hidden (row and old widget); the server works the mode out from the menu
(`effective_mode`); entries: "Use the dials (no 4a preset)", saved presets (load unlocked), z_ choices.
Description box + Edit description / Save / Save as / Rename / Delete; built-ins store only their
description (`user/default/portrait_presets/builtin_descriptions.json`); saved presets keep "description"
in their own file. Descriptions written for all six entries (the two presets got only that field).
15.6 No auto-save: Portrait Master's own save_preset (ON in v09 as "Random02") switched off in every job by
our hook, shown off and locked on the page (re-applied after a workflow loads - the first version was
overwritten by the loaded value; fixed); v09's saved value set to false.
15.7 Save as added to the saved phrases (the window's words become a NEW phrase; the old one stays). Every
other package in v09 already had it.
15.8 Tests (all through a launcher restart - "c" typed into the launcher console by process id 41352, then
"y" to "did not start it... Stop anyway?"):
- v09 loads 3x each stage: 0 mismatches.
- Front text: 9 model switches; Edit / Save / Delete 3 rounds; 6 real jobs from the page (score tags only
  for CyberRealistic; log, history and watcher agree); join-order text check; bigLust with/without the node:
  identical prompts and identical pictures BEFORE the face repaint; after it a 3/255 difference that also
  appears between two runs of the identical job without the node (face-repaint run-to-run variation).
- z_ choices: 18 text jobs (from switches ON and OFF); page 3 rounds; refusals; no files created.
- One menu: server 3 rounds (a changed dial kept under an old hidden "locked"; untouched dials filled; z_block
  empty; a job asking Portrait Master to save "zz_autosave_test" created no file; no preset file changed);
  page: menu, descriptions, built-in description edit (restored), Save as from built-in -> "needs
  description" -> edit -> a dial change left the stored preset alone -> delete (3 rounds); front-text and
  phrase Save as 3 rounds each; the phrase shelf restored from its backup afterwards (empty).
Full record: `logs/checkpoint_front_text_2026-09-29/LOG.md` (untracked). Backups:
`_backups/checkpoint_front_text_2026-09-29/`.

## 16. Rules written into CLAUDE.md in this period

- Node-group layout: #a description, #b switches/packages, #c panel; next column #d, #e, #f; prompt and phrase
  savers separate; STEP 7 uses plain lettering 7a-7d; layout changes go into a new version.
- Save packages: only a Save button changes a stored preset; every package has Save as; the STEP 4a menu.
(Pending, not written yet: "hints" as a new #b - Q52.)

## 17. Mistakes and near-misses by Claude

- Asked the user several times about things the rules require asking about, while the user wanted progress
  (e.g. Q43 asked three times before the file / no-file choice was answered).
- The training waiter watched one process and started the 99-picture test during training (part 4).
- The timeout in the first grid run was too short for a shared card, and records were filed against the
  wrong picture (part 4).
- The eye-test sheet builder first read the wrong run's results (part 11) - caught before sending.
- A progress printer cut JSON mid-line and killed the first STEP 7 run after one picture (part 13) - fixed,
  run resumed.
- The front-text panel's timer failed in a background tab (part 15.1); the z_ grey filter was not cleared
  (15.4); the save_preset display was overwritten on load (15.6) - all found by tests, fixed, retested.
- Told the user the bigLust with/without pictures were "almost the same" and then proved the cause instead of
  guessing.

## 18. State left behind, open questions

- ComfyUI running from the launcher (pid 41352's console); picture pages 8191 / 8192 may still be serving
  `logs/eye_sharpen_test_2026-09-28/` and `logs/group7_tests_2026-09-29/` on 127.0.0.1 only.
- v09 holds all project changes; v08 only its earlier changes. Nothing was saved from a test tab.
- Open (parked): Q66 per-node "In charge" (4b-4g) into their own menus with descriptions; Q52 node letters
  with hints as #b; Q58 negative text per checkpoint; Q54 Pony hints box vs red 7c hints node; Q55 BREAK after
  7b Summary Signal; Q51 the new 7b; Q8 the sharpening tool (tests done, no choice made).
- Not built yet (asked for, waiting on the questions above): the Pony hints box under STEP 1, "7b Summary
  Signal", the red checkpoint-hints node.

---

## Addendum (29 Sep, after the commit): Prompt Control removed
The STEP 7 encoder in v09 is now ComfyUI's own CLIPTextEncode and the Prompt Control add-on was deleted (no
backup, as asked). Everything above that says "the STEP 7 encoder is Prompt Control" describes the state
before this change. Full notes: `logs/prompt_control_removed_2026-09-29.md`.
Also after the commit: CLAUDE.md's node-lettering section made into guidelines (natural order, hints right
after the description, re-letter a group when it changes).
