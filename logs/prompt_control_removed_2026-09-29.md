# Prompt Control removed (2026-09-29)

## What the user decided
- Q55 = 4: "lets completely remove prompt control" (asked while choosing how the "7b Summary Signal"
  text would reach the first block with Prompt Control's BREAK word).
- Asked "didnt you just say that portrait master needs it to run?" - answered: no; Portrait Master runs
  without it; only its nationality MIX ("[nationality_1:nationality_2:mix_value]") needs it. Its README:
  "Install ComfyUI Prompt Control for full syntax support", "This feature is experimental"; its older guide:
  "not natively recognized by ComfyUI; we therefore recommend the use of comfyui-prompt-control".
- Asked "why is prompt control even installed? Did i make that decision?" - answered from the records:
  installed 2026-09-16 during the Portrait Master rebuild, for the nationality blend
  (`logs/portrait_master_exhaustive.md`: table line "NEW today. The developer's listed optional dependency
  (asagi4)... for the nationality-blend syntax"; section 4.9 "Install ComfyUI Prompt Control and actually
  wire it" under "PART 4 - THE DESIGN THE USER CHOSE"). That log was written by Claude; the user's own words
  asking for it were NOT found in the saved copy of the user's messages
  (`logs/face_rules_audit_2026-09-25/user_messages_face_tool.txt`). The 16 Sep session record was not read.
- Q68 = 2: switch v09 and take the add-on out of ComfyUI; the user added "do not keep a backup".

## What was removed
- `custom_nodes/comfyui-prompt-control/` DELETED (no backup, as asked). It was:
  https://github.com/asagi4/comfyui-prompt-control , commit 88af041dce376c97441d2efe5479e27de4b52cd8
  (2026-09-15), version 3.0.0-beta.10, 1.8 MB. It can be reinstalled from that address and commit.
- Used by: only the STEP 7 encoder node (node 10, "PCLazyTextEncode") in the bigLust workflows v04, v05, v06,
  v07, v08 and v09. None of our own add-ons used it.

## What changed in v09
- Node 10: type PCLazyTextEncode -> CLIPTextEncode (ComfyUI's own); title
  "STEP 7  -  CLIPTextEncode  -  encode the prompt  (ComfyUI's own)  (don't touch)"; same wiring - text from
  STEP 7b (node 45), clip from STEP 6 (node 3), output to the KSampler (7) and FaceDetailer (34). Only node 10
  changed (checked against the backup `_backups/remove_prompt_control_2026-09-29/v09_before_encoder_swap.json`).
- v04 to v08 were NOT changed: they will show a missing node ("PCLazyTextEncode") when opened.

## What it means (read in ComfyUI's code, `comfy/sd1_clip.py`)
- Weights "(words:1.3)" still work: ComfyUI reads round brackets itself (parse_parentheses / token_weights).
- BREAK does not exist any more: ComfyUI's own encoder has no BREAK. "7b Summary Signal" can only land in the
  first ~75-token block by being near the start and short.
- Portrait Master's nationality mix "[a:b:0.5]" is now ordinary words (square brackets are plain characters),
  so both nationalities, the colon and "0.5" are read as text instead of "switch halfway". Only happens when
  Base Character has TWO nationalities set (v09 has both on "random", so it always writes a mix). Open: Q69.
- Without Portrait Master nothing changes.

## Tests
- ComfyUI restarted through the launcher (console "c", pid 41352): the add-on is gone (`/object_info/
  PCLazyTextEncode` returns nothing), no import errors. One "Traceback" in the log around the restart is the
  usual asyncio "connection lost" message from the old server shutting down, not a load error.
- v09 loaded 3x in a fresh tab: 41 nodes, 0 value mismatches, no missing node types, node 10 is CLIPTextEncode
  with the same links, the job contains no PCLazy node. Tab closed, nothing saved from it.
- Pictures (`picture_check.json` and the export in `logs/remove_prompt_control_2026-09-29/`, untracked):
  6 jobs built from the new v09 with the STEP 7 tests' settings (random face, box at 1.3, seeds
  111111 / 222222 / 333333, run-1 Portrait Master picks, no face repaint, front text switched off):
  - without Portrait Master: identical, pixel for pixel, to the STEP 7 tests' Prompt Control AND plain-encoder
    pictures (they were already identical to each other);
  - with Portrait Master first: identical to the STEP 7 tests' plain-encoder pictures, different from the old
    Prompt Control pictures - only because of the nationality mix.

## Questions changed by this
- Q51 (where Prompt Control's special-words hint goes) - no longer applies.
- Q55 (placing "7b Summary Signal" in block 1) - BREAK is gone; only its order next to the front text is left.
- Q69 (new): what to do about Portrait Master's nationality mix now.

## Follow-up: the nationality mix (user, Q69 = 2)
User: "2 lock the slider. Make a descriptive note in the hints portion of this node group about these two
settings. Include my decision to keep it simple since prompt control only really affected this nationality
settings group. Or if your able to make changes to these settings without overwriting developor code, then do
option 2 but hide the slider." - it was possible without touching Portrait Master's code, so option 2 was
built, the slider hidden, and the note added as well (it documents the decision).
- `custom_nodes/freedom_prompt_slots/nodes.py`: `plain_nationality_mix()` - on STEP 7b's TRIGGER input only
  (Portrait Master's text, or her code word), "[a:b:number]" becomes "a and b"; one log line
  "[Freedom] STEP 7b: Portrait Master's nationality mix written in plain words". The user's own boxes are
  never rewritten. Backup `_backups/nationality_mix_2026-09-29/`.
- `custom_nodes/freedom_portrait_control/web/portrait_control.js`: Base Character's `nationality_mix` slider
  hidden on the page (it did nothing without Prompt Control).
- v09: new note node 48 "STEP 4 hints - the two nationality settings" at the top of the STEP 4 group
  (2650,100, 3550x330); the seven STEP 4 nodes moved down 380 and the group made 380 taller. STEP 4's letters
  4a-4g were NOT changed: they are part of 4a's saved choices ("4b Base Character" / "4c Face Generator") and
  of saved presets, so renaming them would break saved settings - the note has no letter.
- Tests: example texts (mix -> "and", single nationality and "(lorasusana:1.1)" unchanged); ComfyUI
  restarted through the launcher, no import errors; 3 random-face jobs: Portrait Master wrote
  "[togolese:south sudanese:0.5] ...", the finished prompt read "(togolese and south sudanese woman ...)"
  (and turkish / liberian, sao tomean / guinean), log line each time; trained face: "(lorasusana:1.1)"
  unchanged; v09 loaded 3x in a fresh tab: 42 nodes, 0 mismatches, nothing flagged modified, note present,
  slider hidden; looked at on screen. Tab closed, nothing saved from it.
