# STEP 7b Summary Signal built (2026-09-29)

## What the user decided
- Q55 = 1: the Summary Signal words go right after the model's own text (Pony's score tags), so both
  are on page 1 of the prompt.
- Q70 = 1 (go ahead), with a change: "because the score tags come from pony, they need to auto populate
  at the beginning of the 7[x] summary signal when pony is selected in node 2 AND UNPOPULATE, when
  unselected from node2 a watcher will need to activite and make sure both actions happen."
- Q71 = 1: "node 2" meant node 1, STEP 1, the model picker.
- Q72 = 1: merge. The "Checkpoint front text" node became the Summary Signal node; there is no
  separate front-text node any more.

## What "page 1" means, in plain words
ComfyUI reads the prompt in pieces of 75 places (a place is a word or part of a word; "score_9," alone
takes several). The first piece is also boiled down into a short summary the art model keeps in mind for
the whole picture. Words on page 1 are in that summary; words later are still read, but are not in it.
The count here is made by ComfyUI's own word-splitter for SDXL, so it is the real count.

## What you see on the node (STEP 7b)
- The model picked in STEP 1.
- One box. It starts with the model's own text (CyberRealistic Pony: "score_9, score_8_up, score_7_up";
  bigLust, Krea and the rest: nothing), then your words.
- The model's part is locked in the box: deleting or changing it is undone, with the message "The start of
  the box is this model's own text. To change it, press Edit model text."
- Counter: "Page 1: 24 of 75 places used - 51 left". Typing that would spill past page 1 is refused
  ("That would not fit on page 1, so it was not added.").
- If a model switch pushes your words past page 1 (fit with bigLust, too long once Pony's tags are added),
  your words are kept and the counter turns red: "Page 1 is full: about 14 places over..."
- WATCHER line: after every model switch it checks the box - the new model's text is at the start, the
  old model's text is gone - and says so ("bigLust_v16 - it has no model text (n/a). Taken out:
  'score_9, score_8_up, score_7_up'. Checked."), or shows "PROBLEM" in red.
- Model-text package: Edit model text, Save model text, Cancel, Delete model text (press twice), and Save
  as (for another model). Only Save / Save as / Delete change a stored entry.
- PROMPT WATCHER: the finished prompt from the last run, and this node's own check from that run.
- The "enabled" switch still works: OFF leaves the model's text out; your words still go in.

## Where things live
- `custom_nodes/freedom_checkpoint_prefix/__init__.py`: class name kept (FreedomCheckpointFrontText) so the
  v09 wiring stays; new "signal" field (your words, saved with the workflow, hidden on the node); output is
  model text + ", " + your words; each run logs "[Freedom] STEP 7b Summary Signal: ... N of 75 places used -
  all on page 1" (or a WARNING if over); new route `/freedom/summary/count`.
- `custom_nodes/freedom_checkpoint_prefix/web/checkpoint_prefix.js`: the panel above.
- Stored model texts: unchanged, `user/default/checkpoint_prefix/<model>.json`.
- `custom_nodes/freedom_prompt_slots/nodes.py`: wording only (tooltips, description, log line now "STEP 7c").
- Backups: `_backups/summary_signal_2026-09-29/`.

## v09 changes (STEP 7 re-lettered in reading order, per the guidelines)
- 7a description note (node 15): text now explains the Summary Signal and the new order.
- 7b Summary Signal (node 47): new title, taller (720).
- 7c prompt boxes (node 45, was 7b): moved down 300.
- 7d phrase note (node 43, was 7c): mentions of "STEP 7b" changed to "STEP 7c".
- 7e phrases (node 44, was 7d).
- STEP 4 hints note (48): "STEP 7b" -> "STEP 7c". STEP 7 group 300 taller.
- Only those nodes changed; links identical (checked against the backup).
- When the red checkpoint-hints node is built it goes in as 7c and the letters after it move down again.

## Tests
- ComfyUI restarted through the launcher (console "c"), no import errors; the node shows its new name and
  the "signal" field.
- Count route matches the word-splitter run directly: score tags 15; tags + "(eyes rolled back:1.3),
  ahegao" 22; 40 dummy words 149 (2 pieces, does not fit).
- In the browser (v09 loaded fresh, launch-page hop): box opened as "score_9, score_8_up, score_7_up, ",
  60 left; typed words -> 53 left; tried to wipe the model text -> undone with the message; tried to add
  60 more words -> refused; bigLust -> tags taken out, watcher "Checked", 69 left; Krea -> none, "Checked";
  back to Pony -> tags back, "Checked"; long words on bigLust (73 of 75) then Pony -> red "about 14 places
  over", words kept. Real keyboard typing (", drool") and Ctrl+Home Delete Delete on the tags: same results.
  Looked at on screen.
- 6 jobs from v09 (words "(eyes rolled back:1.3), ahegao, drool"), seeds 111111 / 222222 / 333333, on
  cyberrealisticPony_v110 and bigLust_v16: all succeeded. Pony finished prompts start
  "score_9, score_8_up, score_7_up, (eyes rolled back:1.3), ahegao, drool, (lorasusana:1.1), ...";
  bigLust ones start "(eyes rolled back:1.3), ahegao, drool, (lorasusana:1.1), ...". Tokenizing each whole
  finished prompt: the model text + your words are exactly the first 24 (Pony) / 8 (bigLust) places of
  page 1. The node's log line and its on-screen line matched. Raw results:
  `logs/summary_signal_2026-09-29/run_check.json` (untracked).
- The pictures themselves were not compared or judged; this test checked where the words land.
- The test tab: the workflow was closed in ComfyUI without saving; the v09 file on disk was unchanged
  afterwards (same fingerprint, same time). The Chrome tab itself would not close from automation.

## Decision after the build: STEP 8 stays as it is (Q58 = 2)
- Asked: should each model's entry also hold "don't want" text for STEP 8 (for CyberRealistic Pony
  "score_6, score_5, score_4"), added and removed automatically?
- Research first (user asked; read from the sources, not memory): CyberRealistic Pony's maker gives
  "score_6, score_5, score_4" as a negative example and says the Pony tags can also be removed; the Pony
  Diffusion maker says the model "is designed to not need negative prompts in most cases" and that score tags
  work less well in negatives because ratings only go down to 4; community guides call them common but weak;
  no side-by-side test was found anywhere.
- User answered 2: no automatic "don't want" text. STEP 8 is unchanged; the user adds those words by hand
  when wanted. Nothing was built for this.
