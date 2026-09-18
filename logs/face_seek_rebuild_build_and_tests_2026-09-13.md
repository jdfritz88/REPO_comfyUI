# Face Seek rebuild: build, tests, fixes, and the OneTrainer settings questions — 2026-09-13

Continues `face_seek_review_rotation_and_dataset_audit_2026-09-13.md` (the audit,
the originals check and the decisions, §10 there). This log covers everything
after that: the user's answers, the wipe, the build, every test and its result,
the bugs found on the way, the text-encoder choice, and the OneTrainer
"headless" discussion.

Branch `branch09-comfyui-repo-migration`. Commits in this part:
`96ae87e` (first log), `35c9cf8` (rank 16 / alpha 1 / flip off + dedupe.py),
`018f0dd` (the Face Seek rebuild + save-crash fix), `36b5ece` (text-encoder
choice (c) + banners).

---

## 1. The user's answers (numbered questions)

| # | question | answer |
|---|---|---|
| 1 | After the two photos + folder, start searching at once? | **Yes** — and Stop/Save and Resume must actually work |
| 2 | Still ask for a starter folder? | **No — two photos only** |
| 3 | Delete one crop → remove the other crops from the same original? | **No** |
| 4 | Removed duplicates: delete or move aside? | **Remove completely** |
| 5 | Background library run: review once at the end? | **Yes, once after the whole run** |
| 6 | Test on a throwaway profile with copied photos? | **Yes** |
| 7 | Text-encoder values? | "Do not assume or guess — what does the research say?" → research (§6) → chose **(c)** |
| — | Wipe shared learning files + Susana's 5 backups too? | **Yes** |
| — | Duplicates definition / which copy stays? | **Exact and near-identical; keep the larger, sharper** |
| — | `F:\Chest` | "Leave my stuff alone." Chest is not in the app's code; it was Susana's saved starter folder |

Where duplicates were already handled (answered before building): video
near-identical frames (within one video), identical file content scanned once,
the search stage skipping photos already handled, the other-faces bank. None sees
finished crops, so the four stay where they are and one new check runs at the
end of processing.

**"Did I lose originals?"** asked twice. Answered from code: Face Seek never
deletes, moves or edits a library file; "cut straight from your library" meant
*cropped* (read the photo, write a new crop file), not cut-and-paste. Detail in
the first log §9.

## 2. The wipe (09-13 ~17:00)

To the Recycle Bin: `_face_profiles\susana` (13,142 files, 4.1 GB) and the four
`_global` files (feedback.jsonl, judge.json, other_faces.npy,
other_faces_meta.jsonl). Kept: Susana's 4 LoRAs in `REPO_comfyUI\models\loras\faces`.
`F:\Chest\...\Susana` untouched. The crop-picker page server was stopped.

## 3. What was built

- **Training** (`otrain.py`, `pipeline.py`): rank 16, alpha 1 (`LORA_ALPHA`),
  concept `enable_random_flip: False`.
- **`dedupe.py`**: finished-crop duplicates — identical SHA-256, or same aspect
  (±3%) and mean grey difference ≤ 6 at 96×96; keeps the larger, then sharper
  (Laplacian variance). Threshold from Susana's measured pairs (1-px re-cuts
  0.9–4.3; different crops ≥ 50).
- **`identity.py`**: builds from the two chosen photos when there is no folder
  (each photo one reference).
- **`search_history.py`**: `<profile>/search_history.json` — captures, crops,
  not_person, events.
- **`crop_guard.py`**: detects faces in the finished crop, finds her by her
  source-face embedding, shrinks the crop one edge at a time to push other face
  boxes out (10% clearance, never into her box), re-detects; otherwise keeps the
  crop and records how many other faces remain.
- **`seek.py`**: group photos and videos are copied into `found/` (never cropped
  from the library); reteach uses her cached embeddings from captures; search
  skips captured and not-person originals; clean runs every crop through the
  guard and captions on her face in the final crop; new **dedupe** stage;
  `EXIT_STOPPED = 3`; review marked pending at the end (or deferred with
  `--defer-review`); the stage is recorded when it starts.
- **`review_server.py` + `review_page.html`**: local page on 127.0.0.1, pinned
  legend, yellow frames, tick → Delete (Recycle Bin; original marked not-person;
  siblings kept; snapshot names removed so crop margins are not nudged; judge not
  taught) / Rotate Left / Rotate Right (caption re-measured by identity) /
  Proceed (clears pending, starts `pipeline --presorted`, `--retrain` if LoRAs
  exist, log in `logs\face_training\train_<slug>_*.log`).
- **`face_tool_ui.py`**: Add person = exactly two photos (no carry-on with one,
  same file refused) → search folder → subfolders → Seek starts; Review crops
  button; Train opens review while pending; stopped Seek message; no seed-folder
  training fallback.
- **`seek_library.py`**: passes `--defer-review`; exit 3 → folder "stopped" (not
  done) and halt; honours the profile STOP flag; when every folder is done, marks
  review pending once and opens the review page.
- **`profiles.py`**: `dedupe` stage, `history_path`, review pending,
  `training_running()` (pipeline lock), **Review** status.
- **`backup.py`**: backs up `search_history.json` too.
- **`sort_photos.recaption_folder` / `pipeline._ensure_captions`**: pick her face
  by identity, not the largest face.
- **README** corrected (it had said Seek "crops everyone else out").

## 4. Tests on throwaway profiles (copied photos only)

Test library (scratchpad `rebuild_test\library`): 5 library group photos that
contain the anchor person plus others, 2 solo screenshots, an exact duplicate in
a subfolder, and a -90-tagged phone video. Anchors: two screenshots of the same
woman from `F:\Chest\...\Susana\Found` (copied; viewed first). Originals
hash-checked before and after every run: unchanged.

A test-script mistake on the way: the first copy of library photos reported all
8 "unreadable". Diagnosed, not assumed: the files open fine (JPEG, both UNC path
forms); the heredoc had turned `\\PersonalCloud` into `\PersonalCloud`. Recopied
with forward slashes.

| test | result |
|---|---|
| profile from two photos, no folder | identity from 2 refs; warning "only 2 faces" |
| Seek run 1 (`zztestrebuild`) | all 7 stages; 5 group photos + frame + video copied to `found/`; 2 face + 8 body crops |
| crop guard vs independent detector recheck | all 10 agree; 1 trimmed clean (IMG_3188), 4 flagged (1/5/5/4 other faces) |
| why the 4 could not be trimmed | every other face was clearly left/right/above/below her, but trimming left < 256 px (MIN_CROP_PX) — kept + yellow |
| dedupe at end | 0 removed — the exact duplicate was never captured (identical content scanned once upstream) |
| review page (Chrome) | pinned legend (bar top 0 after 978 px scroll); 4 yellow frames |
| Delete (page) | IMG_3644 crop+txt in Recycle Bin; source hash in not_person; IMG_3643 kept; snapshot updated; clean_deletions (9,0,0); `_global` feedback/judge untouched |
| Rotate Right / Left (page) | 294×764 → 764×294 → 294×764; caption re-measured; turn logged |
| Proceed (page) | confirm panel; training started; config showed rank 16, alpha 1, flip False |
| Stop during training | pipeline stopped in 18 s before a step; no LoRA, no registry entry |
| Stop/Resume test 1 | invalid: stage was only written at stage END, so Stop arrived during dedupe → fixed (stage recorded at start) |
| Stop/Resume test 2 (`zzteststop`) | **crashed**, exit 1 — see §5 |
| Resume after that | exit 0; all stages; 2/8 crops (same as run 1); no double captures; review pending |

## 5. Bug: Seek crashed saving profile.json (CP3 → CP4, Fix_LOG)

Traceback: `profiles.py save → os.replace(profile.json.tmp, profile.json)` →
`PermissionError [WinError 5] Access is denied`. Trigger in the test: a watcher
reading profile.json every 0.2 s with an unclosed `open()`. Real in the app too:
the Face Tool reads profile.json while a Seek child rewrites it; backups copy
it; ComfyUI reads the registry while training writes it.

Fix (`safe_replace.py`, CP3; PASS by CP4 20:52–20:57): retry the swap only for
WinError 5/32, 1 ms doubling to 10 ms, up to 5 s; after that log ERROR and raise
(never silent). Used by `Profile.save`, `History.save`, the library runner's
progress file, and `save_registry`. CP4 evidence: old code failed in 0.001 s;
new code saved after ~1 s with a 1 s holder; an 8 s holder still raised after
5 s; six real Seek runs with a reader exited 0 (37 real collisions all completed,
longest 157 ms). Reviewed and committed in `018f0dd`.

Left open by CP4: a READER can itself fail to open the file at the instant of a
swap (errno 13). A CP1 bug search was started on that (running at the time of
writing); the Face Tool window tests wait for it.

## 6. Text-encoder training

Research (OneTrainer code/wiki/issues, Kohya, diffusers, HF blogs, experts,
community; Reddit blocked, Discord login-gated): no authoritative values for a
real-person SDXL LoRA. OneTrainer's SDXL LoRA preset: off (since Nerogar's 2023
preset). Kohya SDXL docs: `--network_train_unet_only` "highly recommended". HF
SD1.x DreamBooth blog: TE training best for faces (not SDXL). Where trained: TE
LR lower than the UNet (commonly half), overfits faster. Installed OneTrainer
23df383 includes the fix for the TE resume crash (#1661/#1671).

The options put to the user:
- **(a)** Leave it off, like OneTrainer's preset.
- **(b)** Turn it on with OneTrainer's base defaults: same learning rate as the rest of the model, stop after 30 epochs.
- **(c)** Turn it on at half the learning rate, the common community practice. Nobody has tested that at our settings.

**Chosen: (c)**, with a big banner explaining the options and the settings.
Set in `otrain.py`: TE1 + TE2 trained at 0.00015 (half of 0.0003), stop after 30
epochs (OneTrainer base default — (c) named no stop point; the banner says so),
weights FLOAT_16, LoRA FLOAT_32; rank 16, alpha 1, flip off. Banner in
`otrain.py`, every training log, the review page (+ Proceed confirmation),
README, master reference. Verified from a real built config and viewed on the
page (Cancel, no training). Not observed: a run with TE on (12 GB VRAM untested).

## 7. The OneTrainer settings questions

- **Why the banner is on a Face Seek page:** Face Seek does not train. Proceed
  starts OneTrainer with a settings file our code writes for each run
  (`_face_runs\<person>\<job>\config.json`, `concepts.json`); the banner shows
  what OneTrainer is about to be given.
- **Can OneTrainer's window save settings?** Yes — named presets in
  `training_presets\<name>.json`, and the last session in `training_presets\#.json`
  (TopBarController.save_to_file / save_default). My earlier wording ("its window
  won't show these settings") made it sound otherwise; corrected. Face Seek's
  runs read neither: they layer OneTrainer's base defaults + the built-in
  `#sdxl 1.0 LoRA.json` + our values, and our values always win.
- **Why headless:** a design constraint recorded 2026-09-03
  (`onetrainer_master_reference.md` §2.2: "Must run headless, driven by our own
  code, not clicked through by hand"; commit `dc7e0dd` "driven headless from the
  stack launcher"), serving §1.3's goal that a person picks a face in ComfyUI and
  never types a filename or knows what a rank is. The records do not show
  whether the user asked for "no window" in those words. Recorded side effect:
  `layer_filter_preset` only applies in the GUI.
- **User's decision:** leave it headless for now. OneTrainer settings are being
  handled in another Claude session; **this work focuses on Face Search only.**

## 7b. After the first push (`9e88597`)

**Reader-side bug (CP1 → CP3 → CP4, commit `ad39ea4`).** Reproduced in every
reader with the app's own code: the Face Tool's message loop died after one
failed refresh; the review server crashed at startup / dropped requests; a
failed backup copy lost a backup generation; `load_registry` returned an EMPTY
registry that `register_lora` wrote back (wiped susana in a test copy); the
ComfyUI Face Shelf node silently found no face. Fix: `safe_replace.read_text` /
`copy_file` retry lock refusals up to 2 s then raise; unreadable registry /
progress raise instead of reading empty; `_drain` re-arms in `finally`; backups
built in `backup/_incoming` before rotating; review server answers 500 and
logs. Both Face Shelf node copies identical. CP4: 0 errors in 13,937–198,634
operations per reader (657–12,183 before). Open: shared `.tmp` name when two
processes save the same file; corrupt JSON still reads as empty; one
unreproduced FileNotFoundError in a backup copy.

**Library runner test (throwaway `zztestlibrary`, root with folders 2001 and
2002, `--no-review-page`).** Run 1: Stop requested during 2001's clean stage →
runner log "2001 STOPPED … re-run to continue", 2001 state `stopped`, 2002 not
started, review not pending, resume stage `clean`. Run 2: 2001 `done`, 2002
`done`; review pending set once by the runner ("every folder processed: 2 face +
8 body crops"); neither folder's Seek log marked it; 2 face + 8 body crops, 8
captures, no double captures. The review page opening at the end was not
exercised (the flag was used so no browser opened in an unverified Chrome
profile).

**Cleanup so far:** removed profiles `zztestrebuild`, `zzteststop`,
`zztestlibrary`, `_face_runs\zztestrebuild`, and their test logs. `_global`
test files are left until the Face Tool window test is done.

## 7c. Face Tool window test and the fixes it led to (2026-09-14, 00:24–01:37)

Throwaway profile `zztestwindow` (the two anchor photos, the small test library).

**Run 1 — real clicks (screen unlocked).**
- Add person PASSED (two photos → folder → subfolders → "Starting seek").
  Stop during clean PASSED ("seek stopped - progress saved"). Resume seek
  PASSED (seek finished, review pending, review server started).
- **Review crops button missing.** The row's buttons shared the name's line;
  the long status ("2 face + 8 body crops waiting for your review before
  training") left them 300 px. Restore was squeezed to "esto" and "Review crops"
  got no room, so Tk never showed it; the test clicked Restore instead (dialog
  cancelled, nothing restored). User approved moving the buttons to their own
  line. Fix `964d097`; re-test: six buttons at full width, "Review crops"
  reused the open review page (log line 6 s after the click), no second server.
- Proceed on the review page (Chrome, John Doe) started training; Stop in the
  Face Tool ended it ~9 s later; training lock released; no LoRA; registry
  byte-identical to the baseline.
- **Measurement error found:** Win32 `IsWindowEnabled` reports Tk buttons as
  enabled even when Tk draws them disabled, so the driver's "Stop enabled"
  readings meant nothing. What does show Stop was enabled: Tk ignores clicks
  on disabled buttons, and both Stop clicks reached `stop()` and stopped the run.
- **Four problems found:** (1) Stop said "Nothing running for that person"
  although it stopped the training (`stop()` only looked at runs the window
  started; Proceed's training is the review server's child). (2) The training
  log called the stop "FAILED … train exit 3; no LoRA produced" and also said
  "checkpoint kept, will continue next time" — the workspace held only config
  and tensorboard, no checkpoint. (3) The review page kept saying "Training is
  running" with Proceed disabled until reloaded (it only loaded state after its
  own button actions). (4) "Resume?" badge on a person with crops and no
  training. Also noted: the old "Review" button (borderline-call queue that
  re-teaches the judge) appears under the row.

**User's answers:** 1 fix them yourself until resolved; 2 "resume"; 3 did not
understand the old-Review-button question; 4 remove the test person.
Checked and ruled out a suspected stale-STOP problem for Proceed: the pipeline
deletes a leftover stop file when it starts. It is real for background library
runs (`seek_library` checks the profile STOP before each folder and never
clears it).

**Fixes, commit `5074c69`:**
- `face_tool_ui.stop()` asks what is really running (own run, `seek.active`,
  or `training_running()` from the pipeline lock); says "Stopping '<name>'s
  training/seek…"; with nothing running it says so and writes no STOP flag.
- `pipeline`: a stop before the first LoRA file breaks the loop without an
  error ("stopped by request after Ns, before a LoRA file was written; no
  checkpoint was saved - the next run starts this LoRA over" — or "its
  checkpoint is kept" when `has_checkpoint()` is true); "Registry unchanged"
  when no LoRA was made; SUMMARY prints `stopped  : yes`.
- `review_server`: a watcher thread waits for the training it started, reads
  `last_run_summary.json` (only if newer than Proceed) into
  `training.outcome`, clears the spent STOP flag, logs `training_ended` to the
  search history, and shuts the server down 120 s after training ENDS (was
  120 s after Proceed — the page would have lost its server mid-training).
- `review_page.html`: while training runs, polls `/api/state` every 5 s and
  updates only the training line and buttons (crops are not redrawn); shows
  finished / stopped (with LoRA counts) / ended with errors / ended without a
  summary; says plainly if it loses the server.

**Run 2 — screen locked (user: "you have permission to continue even while the
screen is locked").** SendInput clicks and a posted BM_CLICK both failed to
reach Tk (foreground window = "Windows Default Lock Screen"); the driver's
typing of "Zztest Window" went to no app window — most likely the lock screen's
password box; Enter was never sent. So the Face Tool was run in-process
(`scratchpad\wintest\nocl.py`) calling the same methods its buttons call
(`_do_add`, `reload`, `stop`), reading button text/state from Tk itself. Chrome
clicks on the review page did work while locked (the page's click listener
recorded trusted clicks). Results:
- Seek finished; row: Seek, Train, Stop[disabled], Backup, Restore,
  Review crops, Review; status Review.
- Stop with nothing running → "Nothing running for that person.", no STOP file.
- Proceed (Chrome) → training lock; row while training: Seek[disabled],
  Train[disabled], Stop[normal]; status Working/training. `stop()` → "Stopping
  'Zztest Window's training. …"; STOP file present.
- Train log: "stopped by request after 21s, before a LoRA file was written; no
  checkpoint was saved …", "stop requested - not starting the rest of the set",
  "Registry unchanged …", SUMMARY `stopped  : yes`, no errors, exit 0. Workspace
  confirmed no checkpoint.
- Review page, never reloaded: "Training is running (started 01:19:53)" →
  17 s later "Training stopped by request at 01:20:18. No LoRA file was saved.",
  Proceed enabled again.
- STOP flag gone after the run; row back to Seek/Train enabled, Stop disabled.
- Registry byte-identical to the baseline.

**Server shutdown.** In run 2 the server's process was gone before its timer
and `review_server.json` was left behind — the background shell task that ran
the driver ended at 01:21:09 and most likely took the server with it (not
proven). A foreground test (real server, POST Proceed, STOP) then showed the
server exiting cleanly 120 s after training ended — but `review_server.json`
still left behind. Cause: `os.remove` ran inside the `with open(...)` block;
Windows refuses to delete an open file and the error was swallowed. Fix
`b9fd891` (read, close, then remove; log failures). Re-test: exit 121 s after
training ended, log "shutting down" + "removed …review_server.json", file gone,
STOP cleared.

**Not exercised:** the "partial LoRA is kept" wording (a stop after OneTrainer
has written a LoRA) — it would put a partial test LoRA into the shared registry.
In run 2, Add person / Stop / Refresh were method calls, not physical clicks
(run 1 covered the physical clicks for all of them except the new row layout,
which run 1's re-test clicked).

**Cleanup (all to the Recycle Bin, copies of the logs in scratchpad
`wintest\run1_logs`, `run2_logs`):** profile and `_face_runs\zztestwindow`
(twice), 15 test logs across both runs, and the three `_global` files — every
row in them belonged to `zztestrebuild`, `zzteststop`, `zztestlibrary` or
`zztestwindow`. `_global` is empty again; `_face_profiles` holds only `_global`;
registry hash unchanged.

## 8. Still to do (Face Search)

1. **Done 2026-09-14:** old "Review" button removed (user: "remove") with its
   dialog and helpers; badge now reads **Resume** (user: "no question mark").
   Verified on throwaway `zztestrow` (one old-queue item, one Needs-review
   photo, one crop): row = badge Resume; Seek, Train, Stop[disabled], Backup,
   Restore; Needs review; no Review button. Test profile and its one
   `_global/feedback.jsonl` row recycled; registry hash unchanged.
2. **Done 2026-09-14 — face search learns only from the user's answers.** When
   Seek cannot tell whether a face is her it moves the copy into `needs_review`
   and logs a guess. `train_judge` used to fit those guesses as if they were
   answers (both unsure "her" and unsure "not her", once per rescan). The user:
   a false positive taught as truth is not acceptable in an app built for
   accuracy, and matches what they asked for throughout. Now only `by="user"`
   rows (Needs review answers) are fitted; guess rows are still written because
   an answer takes its scores from them. Old Review-list helpers removed.
   Scratch-file test: 300 wrong guesses alone → no judge; + 200 answers → judge
   from exactly 200 rows; weights identical with and without the guesses;
   `scores_for` still pairs an answer with its scores; real `_global` untouched.
   (My explanation of this took several tries; the user had to state the
   problem plainly themselves.)
3. Open from earlier: two processes saving the same file share one `.tmp`
   name; corrupt JSON still reads as empty; one unreproduced FileNotFoundError
   in a backup copy; review page Delete reads the profile after the Recycle Bin
   move; the app's `webbrowser` opens the default browser, not necessarily the
   John Doe profile; the review page opening automatically at the end of a
   library run was not exercised; no training run with text encoders on has
   been observed (VRAM untested); whether the review page keeps the
   training-settings banner.
