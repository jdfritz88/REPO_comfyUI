# Session record, 29-30 September 2026: Summary Signal, Portrait Master menus, the eye repaint, and MediaPipe

This is the full record of everything done after commit `e4e6a82` (29 Sep, 12:41), up to the commit that
adds this file. It is written so someone who was not there can follow every step, every decision, every
mistake and every loose end. Where a shorter log already exists for one part, it is named; this file still
repeats the important details, because the working notes in `logs/<folder>/` sub-folders are not saved to
git (the `.gitignore` keeps only files directly in `logs/`).

Contents
1. Where things stood at the start
2. Carried over from before: work done after the last commit but not yet committed
3. STEP 7b Summary Signal (Q55, Q70, Q71, Q72)
4. "Don't want" score tags for Pony (Q58)
5. Portrait Master 4b-4g: one menu per node (Q66, Q73)
6. The eye repaint: choosing it, researching it, testing it on her trained face (Q8, Q74)
7. MediaPipe: a misreading of "uninstall", and putting everything back (Q76-Q81, Q78)
8. What went wrong, and what was learned
9. Every file changed, and what is NOT in this commit
10. Loose ends
11. The questions, in order, with their answers

---

## 1. Where things stood at the start

- Working workflow: `user/default/workflows/Freedom_bigLust_SDXL v09.json`. ComfyUI 0.37.0 with page
  (frontend) 1.53.6, started only by the kobold launcher; restarts are done by typing "c" into the
  launcher's console (process 41352) and answering "y" to "Stop anyway?".
- The last commit was `e4e6a82` "Checkpoint front text, action-before-physical prompt order, one STEP 4a
  menu, and no more auto-save", pushed.
- The live question was Q55: where the planned "7b Summary Signal" words should go in the finished prompt.
  Parked: Q66 (per-node "In charge" menus on 4b-4g), Q58 (negative score tags per model), Q8 (the Portrait
  Master sharpening tool).

## 2. Carried over from before: work done after the last commit but not yet committed

These were already done on 29 Sep and have their own logs; they are committed now together with the rest.

- **Prompt Control removed.** The add-on `custom_nodes/comfyui-prompt-control` was deleted with no backup,
  as the user asked. v09's STEP 7 encoder (node 10) became ComfyUI's own `CLIPTextEncode`. Full record:
  `logs/prompt_control_removed_2026-09-29.md`.
- **Nationality mix in plain words.** Without Prompt Control, Portrait Master's two-nationality mix
  "[a:b:0.5]" would be read as odd literal text. `freedom_prompt_slots/nodes.py` now rewrites it as
  "a and b" on Portrait Master's text only; Base Character's `nationality_mix` slider is hidden (it did
  nothing any more). A note, node 48 "STEP 4 hints - the two nationality settings", explains the user's
  decision to keep it simple. Same log.
- **CLAUDE.md**: the node-lettering section was turned into guidelines, not fixed rules (user, 29 Sep):
  groups are lettered in natural reading order, hints come right after the description, and a group is
  re-lettered whenever it changes.
- `logs/session_2026-09-26_to_29_full_record.md` got a short addendum pointing at the Prompt Control log.

## 3. STEP 7b Summary Signal (Q55, Q70, Q71, Q72)

### 3.1 The explanation the user needed first
The user said an earlier, code-heavy explanation "made no sense" ("I do not program image generation
files"). It was explained again without code: the prompt is read in pages of about 75 places (a place is a
word or part of a word); every page is read, but only page 1 is also boiled down into a short "sticky note"
summary the painter keeps in mind for the whole picture. Pony's score tags sit at the top of page 1 and use
15 of its 75 places. Making a word stronger, like "(eyes rolled back:1.3)", does not put it on the sticky
note - only being on page 1 does. Research had said the sticky note matters less than the words themselves.
(Checked in ComfyUI's code: `comfy/sd1_clip.py` keeps only the first piece's summary; the count of 15 was
measured with ComfyUI's own SDXL word-splitter.)

### 3.2 Decisions
- **Q55 = 1**: the Summary Signal words go right after the score tags, both on page 1.
- **Q70** (go-ahead for the plan) = 1, with a change: "because the score tags come from pony, they need to
  auto populate at the beginning of the 7[x] summary signal when pony is selected in node 2 AND UNPOPULATE,
  when unselected from node2 a watcher will need to activite and make sure both actions happen."
- Node 2 in v09 is the Face Shelf (STEP 3b), not the model picker, so that was asked, not guessed.
  **Q71 = 1**: "node 2" meant node 1, STEP 1, the model picker.
- The existing "Checkpoint front text" node already put the score tags at the start of the prompt; keeping
  both would have added the tags twice. **Q72 = 1**: merge them into one node.

### 3.3 What was built
- `custom_nodes/freedom_checkpoint_prefix/__init__.py`: the node keeps its class name
  (`FreedomCheckpointFrontText`) so v09's wires stay connected, but is now shown as "Freedom Summary Signal
  (model's front text + your words, page 1)". New hidden field `signal` (your words, saved with the
  workflow). Output = the model's saved text, then ", ", then your words. Every run writes one log line:
  "[Freedom] STEP 7b Summary Signal: added '...'; your words: '...'; N of 75 places used - all on page 1",
  or a WARNING when it spills past page 1. New route `/freedom/summary/count` counts with ComfyUI's own
  SDXL word-splitter (the CLIP-G half, which makes the summary). The stored per-model texts are unchanged
  (`user/default/checkpoint_prefix/<model>.json`).
- `custom_nodes/freedom_checkpoint_prefix/web/checkpoint_prefix.js`: one box. It starts with the model's
  text (locked - editing or deleting it is undone with a message), then your words. A counter ("Page 1:
  24 of 75 places used - 51 left"); typing that would spill past page 1 is refused. If a model switch pushes
  your words over, they are kept and the counter turns red ("about 14 places over"). A WATCHER line checks,
  after every switch, that the new model's text is at the start and the old one is gone ("... Checked." or a
  red "PROBLEM"). A model-text package: Edit model text / Save model text / Cancel / Delete model text
  (press twice) / Save as for another model. The PROMPT WATCHER still shows the finished prompt after a run.
- `custom_nodes/freedom_prompt_slots/nodes.py`: wording only (tooltips, description, its log line now says
  "STEP 7c").
- v09: STEP 7 re-lettered in reading order: 7a description note (text rewritten to explain the Summary
  Signal), 7b Summary Signal (node 47, made taller), 7c prompt boxes (node 45, moved down 300), 7d phrase
  note (node 43), 7e phrases (node 44). The STEP 4 hints note (48) now says "STEP 7c". The STEP 7 group was
  made 300 taller. Wires identical to before (checked against the backup). The file was written back in
  its original one-line form so the change stays small.
- `CLAUDE.md` records the new STEP 7 lettering. Backups: `_backups/summary_signal_2026-09-29/`.

### 3.4 Tests
- Launcher restart: no import errors; the node showed its new name and field.
- Counts from the new route matched the word-splitter run directly: tags 15; tags + "(eyes rolled
  back:1.3), ahegao" 22; forty dummy words 149 (two pages).
- In a fresh tab (launch-page hop): the box opened as the tags plus ", " with 60 left; typed words, 53 left;
  wiping the tags was undone with the message; adding 60 more words was refused; bigLust took the tags out
  ("Checked", 69 left); Krea had none; Pony put them back; 73-of-75 words on bigLust then Pony gave the red
  "about 14 over" with the words kept. Real keyboard typing (", drool") and Ctrl+Home, Delete on the tags gave
  the same results. Looked at on screen.
- Six pictures with the words "(eyes rolled back:1.3), ahegao, drool", seeds 111111 / 222222 / 333333, on
  CyberRealistic Pony and on bigLust: all succeeded. Pony prompts started "score_9, score_8_up,
  score_7_up, (eyes rolled back:1.3), ahegao, drool, (lorasusana:1.1), ..."; bigLust ones started with the
  words. Tokenizing each whole finished prompt: tags + words were exactly the first 24 (Pony) / 8 (bigLust)
  places of page 1. The pictures themselves were not judged; this test checked where the words land.
- The v09 file on disk was checked unchanged after the test tab was closed.
- Record: `logs/summary_signal_2026-09-29.md`.

## 4. "Don't want" score tags for Pony (Q58)

- Question: should each model's entry also hold "don't want" text for STEP 8 (for Pony "score_6, score_5,
  score_4"), added and removed automatically?
- The user asked for research first ("Do not assume, guess or rely on memory"). Found, read directly:
  - CyberRealistic Pony's maker (civitai model 443821, read through civitai's own data feed because two
    page summaries contradicted each other): negative example starts "score_6, score_5, score_4", and "it's
    also possible to remove the normal pony tags". The user's file `cyberrealisticPony_v110` is their v11.0.
  - The maker's linked "Pony Prompting: Master Guide" uses those three tags in every negative example and
    says they push away from mediocre, not truly bad, pictures.
  - Pony Diffusion's maker: the model "is designed to not need negative prompts in most cases"; score tags
    work less well in negatives because ratings only go down to 4 (article by PurpleSmartAI).
  - Community guides: common, but weak. No side-by-side test found anywhere.
- **Q58 = 2**: no automatic "don't want" text; STEP 8 unchanged; the user adds those words by hand when
  wanted. Nothing built.

## 5. Portrait Master 4b-4g: one menu per node (Q66, Q73)

- **Q66 = 1**: merge each node's "In charge" dropdown into its own preset menu, like 4a, with descriptions.
  **Q73 = 1**: go ahead with the plan.
- Built (`custom_nodes/freedom_portrait_control/__init__.py` and `web/portrait_control.js`):
  - Each of 4b Base Character, 4c Face Generator, 4d Skin Details, 4e Style & Pose, 4f Make-up, 4g Prompt
    Styler: no "In charge" row. "Use the dials (no preset)" = only your dials (Factory reset works); a saved
    preset = loads unlocked (fills dials still at the developer's starting value, keeps the ones you
    changed). The old locked choice is gone.
  - A description box under every node's menu (Edit description / Save / Save as). Everything starts as
    "needs description". Your presets keep their description in their own file; "Use the dials" and
    Portrait Master's own presets keep theirs in our `user/default/portrait_presets/builtin_descriptions.json`
    as "<NodeClass>::<name>". Portrait Master's own presets cannot be renamed or deleted.
  - Found while reading: the server route could delete one of Portrait Master's own preset files (only the
    buttons stopped it). The server now refuses too.
  - 4a's six hidden per-node dropdowns (n4b_mode ... n4g_mode) are hidden and not read. 4a still takes
    charge with a saved preset or a z_ choice. The explanation text on every node was rewritten (it still
    described both old dropdowns).
- Tests (restart, v09 fresh): all six nodes laid out right; Save as A then B on each node wrote both files
  with their own descriptions; picking A showed its description, mode "node preset + unlocked", no dial
  locked; back to "Use the dials" gave "ignore presets". A first run overlapped a second one because Chrome
  slows timers in a tab that is not on screen - 4e and 4g showed mixed-up results and were re-run alone, and
  passed. Save changed only the chosen preset. Built-in descriptions saved to our file and came back after a
  reload. Portrait Master's preset folder was byte-identical to a backup afterwards; a server delete of
  "Preset basic" was refused. 4a "z_block" and "User Preset 01" greyed the node menus; "-- none --" freed
  them. Three pictures (Pony, seeds 111111 / 222222 / 333333) with a 4d test preset (pores 0.5, freckles
  0.4), freckles then set to 1.0 and pores back to 0 by hand: every job ran with pores 0.5 (filled from the
  preset) and freckles 1.0 (your change kept); the log named the preset each time. An old-style job with the
  old locked choice kept freckles at 1.0 - the old choice is ignored. Cleanup: all 13 test presets deleted,
  `builtin_descriptions.json` restored from backup, v09 unchanged.
- Noticed, not changed: Portrait Master's own preset folder holds "Random02" (BaseCharacter, 25 Sep) - the
  one its own save switch kept writing while v09 had that switch on - and "test_verify_face".
- Record: `logs/pm_node_menus_merged_2026-09-29.md`; CLAUDE.md updated.

## 6. The eye repaint: choosing it, researching it, testing it on her trained face (Q8, Q74)

### 6.1 Choosing
- Q8 (how the Portrait Master path, STEP 2 on random face, gets sharper eyes at 1216x832) had six options;
  options 4 (Civitai eye finders "Full Eyes" and "Eyeful") and 6 (ComfyUI's own MediaPipe eye mask) were
  tested on 28 Sep (`logs/session_2026-09-26_to_29_full_record.md` section 11). Q8 was rewritten with those
  results before it was asked again.
- **Q8 = 6**, with: "put media pipe needs an on and off switch on the node."
- Q74 asked when it should run: whenever switched on (both face modes), or only on the Portrait Master path.

### 6.2 Research the user asked for ("you tell me! ... Do not assume, guess or recall from memory")
- ComfyUI's MediaPipe nodes (pull request 14009 by kijai; ComfyUI docs): they find a face, mark 478 points,
  and draw masks; nothing about when to repaint eyes, trained faces or likeness.
- Impact Pack's developer (ltdrdata tutorial): only that a tiny eye/pupil mask needs "dilation" to be big
  enough to repaint.
- Users/guides: an ADetailer discussion answer on repainting with a person's LoRA; MyAIForce (Wei Mao)
  lists an "eyes only" finder with no settings. A search summary claimed 0.4-0.5 strength keeps identity;
  its page could not be opened, so it was not counted.
- From v09's own wiring: on trained face the eye repaint's model already carries her face LoRA (STEP 3b ->
  3c -> 6) and the prompt carries her trigger word; the face repaint there uses 0.15, the eye tests 0.5.
- Claude did not choose for the user (the rule: once a question is asked, the choice is the user's) and said
  so. Q74 gained option 3, "test first". **Q74 = 3.**

### 6.3 The test on her trained face
- Base: current v09 exported from a fresh tab (it could not be read back through the browser tool, so the
  page saved it through ComfyUI's user-data store and it was moved straight into the test's logs folder).
  STEP 2 trained_face, face shelf susana_head_sdxl_pony 0.4 + STEP 3c passes 0.3/0.2/0.1, CyberRealistic
  Pony v11.0, face repaint ON at 0.15, Summary Signal empty. Test-only change: one picture per job.
- Each job saved BEFORE (STEP 11's output) and AFTER (the eye repaint) from the same picture.
- Eye repaint = the 28 Sep MediaPipe row exactly: short-range detector, 1 face, confidence 0.5; mask =
  both eyes + irises; MaskToSEGS (crop 3.0); Detailer (SEGS) with v09's FaceDetailer dials at strength 0.5,
  full scene prompt, model from STEP 6.
- Log: her face LoRA applied ("applied faces\susana_head_sdxl_pony.safetensors 3 more time(s)") and
  "CLIP: [(lorasusana:1.1)]" in every job. Free memory before: 8.2 GB.

| seed | eyes found | changed area (pixels) | pixels changed |
|---|---|---|---|
| 111111 | 2 (enlarged x7.1, x6.2) | x 789-965, y 202-282 | 4,030 |
| 222222 | 0 - face at the top edge, partly cut off and tipped back | none | 0 |
| 333333 | 2 (enlarged x9.8, x9.0) | x 170-303, y 101-191 | 2,761 |

- Everything outside the eyes was identical (measured). Looked at: 111111 irises and lashes darker and a
  little crisper; 333333 lashes slightly crisper. Likeness was left to the user. No base picture had
  rolled-back eyes, so that case is still untested.
- Sheet (captions beneath each picture) sent in the conversation and served on this computer only at
  http://127.0.0.1:8193/sheet_eye_repaint_trained_face.jpg (folder `logs/eye_repaint_trained_face_2026-09-29/`,
  not in git). Pictures: `output/eye_repaint_trained_face_2026-09-29/` (not in git).

## 7. MediaPipe: a misreading of "uninstall", and putting everything back (Q76-Q81, Q78)

### 7.1 What the user said
"Thats multiple tests with media pipe, in cases against fuller eyes and the other eyes, media pipe was the
least desctructive, but its still descructive. Lets completely uninstall media pipe and whatever comfyui
systems that drive it thate are are not being used by anything else." The eye repaint idea was dropped, so
Q74 and Q75 (the switch's starting position) were removed as their topic was closed.

### 7.2 What Claude checked (read-only)
- The Python package `mediapipe` 1.0.1 in ComfyUI's software folder (`app_cabinet/comfyui/venv`); nothing
  lists it as needed except the ControlNet add-on (`comfyui_controlnet_aux`, "mediapipe>=0.8.0"). Its helper
  packages: absl-py and sounddevice (used by nothing else); flatbuffers (also needed by onnxruntime);
  opencv-contrib-python (needed: `comfyui_face_parsing`'s guided filter uses its `cv2.ximgproc`);
  matplotlib, certifi, numpy (needed by many others).
- The ControlNet add-on's MediaPipe nodes re-install `mediapipe` by themselves if it is missing
  (`node_wrappers/mediapipe_face.py`, `mesh_graphormer.py`).
- **The Face Competition workflow uses it**: Method 5's "STEP 2b - dense face mesh" is the ControlNet
  add-on's `MediaPipe-FaceMeshPreprocessor` (`user/default/workflows/Freedom_Face_Competition.json`, built
  by `custom_nodes/freedom_face_competition/build_face_competition.py`).
- ComfyUI's own built-in MediaPipe nodes (`comfy_extras/nodes_mediapipe.py`) are part of ComfyUI and cannot
  be removed without editing ComfyUI's files. The model file downloaded for the tests,
  `models/detection/mediapipe_face_fp32.safetensors`, was used only by the tests.

### 7.3 The steps, in order
1. **Q76 = 1, "keep bur remove from v09"**: keep the package. v09 was searched: it contains no MediaPipe at
   all (0 matches) - the tests were separate jobs - so nothing was removed from v09. As option 1 said, the
   model file was deleted (5,423,900 bytes, sha256 a98c4806...).
2. **Q77** asked whether to hide ComfyUI's built-in MediaPipe nodes from the node menu. The user asked how
   Face Competition "decided" between the two MediaPipes. Answer from the records: ComfyUI (cloned 1 Sep)
   already had the built-in nodes; Face Competition was rebuilt on 4 Sep from a method list ("MediaPipe
   FaceMesh / DWPose + ControlNet"), and a Claude session used the ControlNet add-on's node without ever
   comparing the built-in one. No user choice was recorded.
3. The user: "This second media pipe needs to be added to the competition as method six. But do it later."
   Saved as a reminder in Claude's project memory (`face-competition-method-6-mediapipe`) and the log.
4. **Q77 = 1**: a new add-on `custom_nodes/freedom_hide_nodes/` marked the four built-in nodes as outdated
   in memory (they are newer-style nodes, so it wrapped each node's `define_schema` to set
   `is_deprecated = True`). Restart; ComfyUI reported all four as outdated; the Node Library search no longer
   listed them. The search then showed two ComfyUI blueprints built from them: "Image Face Detection
   (Mediapipe)" and "Video Face Detection (Mediapipe)" (`app_cabinet/comfyui/blueprints/`).
5. **Q79 = 1**: "hide in v09 and future versions but add to the competition reminder that these need to be
   added somehow if they are not already." The same add-on filtered them out of ComfyUI's blueprint list in
   memory (SubgraphManager). Restart; the list had 114 entries, none MediaPipe; the search showed only the
   ControlNet add-on's "MediaPipe Face Mesh" and Impact Pack's "MediaPipe FaceMesh to SEGS". The reminder
   got the blueprints.
6. The user asked whether hiding is ComfyUI's feature or Claude's. Answer: hiding happens only in the "add a
   node" list, never on a workflow's canvas; ComfyUI has a built-in "deprecated" label its page hides unless
   Settings > "Show deprecated nodes in search" is on (ComfyUI's own text: deprecated nodes "remain
   functional in existing workflows that use them" - not tested here); applying it to these nodes was ours;
   hiding blueprints is not a ComfyUI feature at all (no setting found in the page's code).
7. The user objected: "why hide any of them if they are not installed and invisible. This is like my saying
   'I don't like this person, keep him away from me.' so you find him and kill him. I simply met, warn me
   when he is around but you made a choice to for an action that comfyui nor the user intended." Claude
   agreed the practical effect was small, named the cost (extra code changing ComfyUI's behaviour, a
   surprise later for Method 6), and owned that it had not said plainly that "leave them visible" was an
   equal choice. Q80 (undo?) was swapped in as the live question; Q78 parked.
8. **The user's clarification: "I meante remove it from the work flow. Every time I said uninstall, I meant
   remove from the work flow."** Saved in Claude's project memory (`uninstall-means-remove-from-workflow`).
9. **Q80 = 1**: `custom_nodes/freedom_hide_nodes/` deleted; restart; the four nodes report not outdated, and
   both blueprints are listed again (116 entries). The old Portrait Master 2.9.2 node stays hidden (older,
   separate work).
10. **Q81 = 1**: the deleted model file was downloaded again from
    https://huggingface.co/Comfy-Org/mediapipe/resolve/main/detection/mediapipe_face_fp32.safetensors -
    5,423,900 bytes, sha256 a98c4806081d40eba35102a0f6dc0000c2e1388b72cf24e691703d0605bd888a, identical to
    the original; ComfyUI's loader lists it again.
11. **Q78 = 4**: the Full Eyes (`models/ultralytics/bbox/full_eyes_detect_v1.pt`, Civitai 330727 v1.0) and
    Eyeful (`models/ultralytics/bbox/Eyeful_v2-Paired.pt`, Civitai 178518 v2 Paired) files are KEPT, to be
    included in the Face Competition. The user thought a reminder already existed; it did not (the reminder
    covered only the built-in MediaPipe and its blueprints) - it was added. How they join (inside Method 6 or
    as their own methods) is to be asked when it is built.

### 7.4 End state
Everything MediaPipe is exactly as before: package installed, model file present, nodes and blueprints
visible. None of the user's picture workflows ever contained MediaPipe. The only lasting results are the
reminders (Method 6 = built-in MediaPipe, plus the two blueprints if Method 6 does not cover them, plus Full
Eyes and Eyeful) and the note about what "uninstall" means.

## 8. What went wrong, and what was learned

- **"Uninstall" was read as "remove from the computer."** It meant "take it out of the workflow". That led
  to deleting a model file and building, then removing, an add-on that hid nodes. Everything was put back.
  From now on: "uninstall" = remove from the workflow; if it is not in the workflow, say so and stop; ask
  before removing anything from the computer.
- **A stand-in was offered without saying how little it did.** Hiding was offered as the nearest thing to
  uninstalling, without saying plainly that it only changes the "add a node" list.
- **A claim was stated before it was tested**: that a hidden node still runs inside a workflow. That is
  ComfyUI's own statement; it was corrected to "not tested here".
- **Two test runs overlapped** (section 5): the first run kept going after the tool timed out, because
  Chrome slows a tab that is not on screen. Results that mixed the two runs were thrown out and re-run alone.
  Lesson: keep a test tab on screen, and never start a second run until the first has reported done.
- **Browser tabs**: the first test tab ("*Freedom_bigLust_SDXL v09") would not close from automation even
  after its workflow was closed in ComfyUI with nothing saved; Chrome's "Close tab and delete group?" box was
  answered, which removed only the tab group. While looking for the right Chrome window, one of the user's
  other Chrome windows (a Google search) was brought up and then put back down with Win+Down, which may have
  changed its size. The v09 file was checked unchanged after every browser test.

## 9. Every file changed, and what is NOT in this commit

In this commit:
- `CLAUDE.md` - lettering guidelines; STEP 7's new letters; 4b-4g menus.
- `custom_nodes/freedom_checkpoint_prefix/__init__.py`, `web/checkpoint_prefix.js` - the Summary Signal.
- `custom_nodes/freedom_prompt_slots/nodes.py` - nationality mix in plain words; STEP 7c wording.
- `custom_nodes/freedom_portrait_control/__init__.py`, `web/portrait_control.js` - 4b-4g menus and
  descriptions; the delete guard; the hidden nationality slider; the rewritten explanation text.
- `user/default/workflows/Freedom_bigLust_SDXL v09.json` - Prompt Control swap (node 10), note 48, STEP 7
  re-lettering and layout, node 47 taller.
- `logs/prompt_control_removed_2026-09-29.md`, `logs/summary_signal_2026-09-29.md`,
  `logs/pm_node_menus_merged_2026-09-29.md`, `logs/session_2026-09-26_to_29_full_record.md` (addendum), and
  this file.

Not in this commit (by the repo's `.gitignore`, or outside the repo):
- Working folders under `logs/`: `checkpoint_front_text_2026-09-29/`, `eye_sharpen_test_2026-09-28/`,
  `group7_tests_2026-09-29/`, `remove_prompt_control_2026-09-29/`, `summary_signal_2026-09-29/`
  (`run_check.json`), `eye_repaint_trained_face_2026-09-29/` (LOG.md, results.json, the sheet, the v09
  export). Everything important from them is repeated in this file.
- Pictures in `output/`, models in `models/`, backups in `_backups/` (`summary_signal_2026-09-29/`,
  `pm_node_menus_2026-09-29/` including a copy of Portrait Master's preset folder).
- Claude's project memory (outside the repo): the Face Competition reminder and the "uninstall" note.
- Nothing in ComfyUI's own folder (`app_cabinet/comfyui`) or Portrait Master's files was changed.

## 10. Loose ends

- Face Competition, later (not started): Method 6 = ComfyUI's built-in MediaPipe; the two MediaPipe
  blueprints if Method 6 does not already cover them; Full Eyes and Eyeful in the competition. Running a
  built-in MediaPipe node inside a workflow has not been tested here. Present a plan and get a go-ahead first.
- Still not built from earlier requests: the STEP 1 checkpoint description box (the model maker's own
  description, swapping with the model), and the red STEP 7 checkpoint-hints node (it will go in as 7c; the
  Danbooru text for it is in `logs/checkpoint_hints_build_plan_2026-09-29.md`).
- A Chrome tab titled "*Freedom_bigLust_SDXL v09" is still open with no workflow in it; safe to close ("leave
  without saving" if asked).
- Three small local servers are still running, reachable only from this computer (127.0.0.1): port 8191
  (`logs/eye_sharpen_test_2026-09-28`), 8192 (`logs/group7_tests_2026-09-29`), 8193
  (`logs/eye_repaint_trained_face_2026-09-29`).
- Portrait Master's own preset folder still holds "Random02" and "test_verify_face" (not ours to delete
  without asking).

## 11. The questions, in order, with their answers

| Q | Asked | Answer |
|---|---|---|
| Q55 | Where the Summary Signal words go | 1 - right after the score tags |
| Q70 | Go-ahead for the Summary Signal plan | 1, with the score tags to fill and empty by themselves, watched |
| Q71 | What "node 2" meant | 1 - node 1, STEP 1, the model picker |
| Q72 | The existing front-text node once the tags are in the box | 1 - merge into one node |
| Q58 | Automatic "don't want" text per model | (research first) 2 - no; add by hand |
| Q66 | Merge 4b-4g "In charge" into their menus | 1 - yes, like 4a |
| Q73 | Go-ahead for the 4b-4g plan | 1 - yes |
| Q8 | How the Portrait Master path gets sharper eyes | 6 - ComfyUI's MediaPipe, with an on/off switch |
| Q74 | When the eye repaint runs | (research first) 3 - test first on trained face; then removed (topic closed) |
| Q75 | Switch starts on or off | removed (topic closed) |
| Q76 | The MediaPipe package that Face Competition uses | 1 - keep; "remove from v09" (nothing there) |
| Q77 | Hide the built-in MediaPipe nodes | 1 - hide (undone by Q80) |
| Q79 | The two MediaPipe blueprints | 1 - hide, and add to the competition reminder (hiding undone by Q80) |
| Q80 | Undo the hiding | 1 - undo it all |
| Q81 | The deleted MediaPipe model file | 1 - download again (done, identical) |
| Q78 | Delete Full Eyes and Eyeful | 4 - keep them; include them in the Face Competition (reminder added) |

No questions are open at the end of this session.
