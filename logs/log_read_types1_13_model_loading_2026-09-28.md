# Reading the logs: session records and the user's messages (2026-09-28)

**What was read:** all 44 files of log types 1 and 13 in `logs\`, chosen by the user ("Just 1 and 13"):
the 42 written session records (the dated `.md` files, plus `LOG.md` / `FINDINGS.md` / the rules audit
in sub-folders) and the 2 copies of the user's own messages
(`face_rules_audit_2026-09-25\user_messages_face_tool.txt`, `per_person_learning_2026-09-26\your_messages_this_session.txt`).
Four helper agents each read 11 files start to end and reported the last line read per file; every
file was read to its last line. Nothing was changed.

**What it was read for:** Q5 - why each picture job loads the art model two or more times, and runs the
face shelf and LoRA stacks twice. (Whether the user wants the cause looked into is still open.)

## 1. What the logs say about the repeated loading

- **Only one file names it:** `two_lora_stacks_v08_2026-09-25.md` lines 145-146 - "Each job loads the
  checkpoint two or more times and runs the shelf and both stacks twice. Present before today (older jobs
  in the launcher log show 3-5 loads). Parked." It was never looked into. No other file mentions it.
- **No file explains the cause.** None mentions "Model storage policy", "dynamic VRAM loading" or smart
  memory.

## 2. Where the no-cache setting (`--cache-none`) came from

In plain words: `--cache-none` tells ComfyUI to keep none of the results it already made, so every step
is redone on every job. It saves graphics memory.

- **The user asked for it**, for the big video setup: "Add to launcher ... this cache none, no whisper,
  all talk launch" (`user_messages_face_tool.txt` line 272).
- **Why it was needed then:** the 14B video model ran about 40 times too slowly. The fix was BOTH stopping
  the voice apps (AllTalk + Whisper held about 5.5 GB of the 12 GB card) AND starting ComfyUI with
  `--cache-none`: 148 s end to end instead of ~465 s per step
  (`face_trainer_record_from_kobold.md` lines 3841-3862 and 4018-4019). ComfyUI was version 0.34 then.
- **It was not always on:** the start settings recorded on 2026-09-07 and 2026-09-10 do not include it
  (`comfyui_lora_stack_and_repo_migration_2026-09-07.md` 364-367; `face_shelf_checkpoint_filtering_2026-09-10.md` 33).
  On 2026-09-24 it was on (`comfyui_403_cross_site_guard_and_launchpad_hop_2026-09-24.md` 276-281).
- **Never checked for picture jobs:** no file records whether using it for ordinary picture jobs (the
  launcher adds it whenever auto-swap or Video Mode is on) costs time.

## 3. Other facts that bear on it

- After the ComfyUI update from 0.34 to 0.37 (2026-09-24), each job took about 4 s longer, all in model
  preparation. Cause not traced; the user chose to leave it ("3") (403 log lines 246-248, 438).
- A way to see exactly which nodes run, and how many times: send the job as our own client, which is the
  only way ComfyUI reports each node as it runs (`facedetailer_research_and_install_2026-09-19.md` 360-361).
- The face repaint takes the same model through its wire; it does not load its own copy (same file 68, 286).
- The face repaint's "cycle 2" repaints twice inside one node. That is not the node running twice, but
  it can be mistaken for it (`user_messages_face_tool.txt` 2466).
- Timings recorded: repaint off ~17-20 s, on ~33-40 s per job (v08 log 456, 593); switch on 48.9 s vs off
  17.8 s (facedetailer log 365-372).

## 4. Still unknown after reading

- What actually causes the repeated loading.
- Whether `--cache-none` is involved. The launcher's own note says it does not decide whether a model
  stays loaded (`REPO_koboldccp_sst_tts_media\launcher.py` 805-809); not tested.
- The launcher's log, where the "3-5 loads" were seen, is type 3 and was not read (outside the user's
  choice of types).

## 5. Per-file summaries

The four helpers' plain summaries of every file are in this session's record. The session records cover:
the face competition (09-03/04), Portrait Master (09-16), face shelf filtering (09-10), the move to
`app_cabinet` (09-17), the FaceDetailer install and v06 work (09-19/21), the face search and review tool
(09-11 to 09-27), the 403 fix and the 0.37 update (09-24), and the two LoRA stacks (09-25).
