# Face Seek scan rule: faces looked for on one frame in every 24 — 2026-09-25

## What the user decided, in order

1. "one new scanning rule: one frame per 24 frames. update the code, update the
   readme, update the logs, update the banners." — answering how often the first
   scan should look for faces in each video.
2. Asked whether it replaces or adds to the sharpest-frame-of-each-scene check:
   **1 — replace it.**
3. Asked whether the first scan's near-duplicate check (picture fingerprint, then
   face fingerprint ≥ 0.93; kept "where it is" by the user's 2026-09-13 rule)
   should still drop frames from the one-in-24 checks: **1 — keep it as it is.**

4. Which banners should show it: **3 — add the scan rule to the existing
   training-settings banner** (see "Banner" below).

5. Whether the 4,273 videos already scanned under the old method are scanned
   again: **3 — leave them as they are.** The new rule applies only to videos
   not yet scanned (the scan skips videos marked done; nothing was changed).

6. Whether to restart the running review server (pid 6540) so the banner row
   shows: **2 — leave it running.** The row shows the next time the user starts
   the review page.

Not decided yet, so not touched: whether
the find-her-stretches pass (every 0.5 s) changes; the out-of-date pass-2 paragraph at the
top of `video_frames.py`.

## Why it came up

Read from `logs/face_training/*.log` (every video scanned since 2026-09-15):
4,273 videos, about 48 h of video, 18,928 scenes — faces looked for once per
9.2 s of video; 2,732 videos (64%) were one scene and so judged on one picture.
Full walk-through: `logs/video_find_the_face_and_scan_rate_review_2026-09-25.md`
and `logs/video_face_diag_2026-09-25/FINDINGS.md`.

## What changed in the code

- `face_training/video_frames.py`
  - `FACE_CHECK_EVERY = 24`; `scan_frames` retrieves frames 0, 24, 48, … only
    (every frame is still grabbed, so decode order and indices match
    `read_frames`), and runs the unchanged near-duplicate check and face
    detection on each, streaming, instead of collecting the sharpest frame per
    scene first.
  - Scene-cut code removed from the scan: `SCENE_CUT_DROP`, `CUT_COMPARE_S`,
    `_hist`, the `deque` import. `METRIC_WIDTH` stays (the perceptual hash).
  - Return keys: `frames_read`, `checked` (were `frames_looked_at`, `scenes`).
    Log line: "N frames read, M checked for faces (1 in 24), …".
  - Module description, section 1, rewritten to match. Section 2 (the replaced
    `her_frames`) left as it was — that correction is an open question.
- `face_training/scan_cache.py`: `mark_video_done` now stores `checked` in the
  `candidates` column (it stored `scenes`); description updated.
- `face_training/README.md`: seek-stages line, the "1. Scan" section, the file
  table row, and a pointer from the 2026-09-15 every-frame rule to the new one.

## Tested (output: `logs/scan_rule_1in24_test_2026-09-25/test_output.txt`)

| Video | Frames | Checked (1 in 24) | Dropped as near-duplicate | Recorded (with faces) | Time |
|---|---|---|---|---|---|
| IMG_3763.MOV | 88 | 4 | 3 | 1 (frame 0) | 4.9 s |
| IMG_3768.MOV | 93 | 4 | 2 | 2 (frames 0, 72) | 1.6 s |
| IMG_9845.MP4 | 8,126 | 339 | 222 | 115 | 109.1 s |

- Every recorded frame index is a multiple of 24.
- All near-duplicate drops in the two short clips were the picture fingerprint,
  before any face was looked for (differences of 2–8 of 64 bits; the line is 8).
  So in those clips the new rule adds one face check at most (IMG_3768 frame 72).
- **Bug found by the test and fixed:** a stopped scan returned frames, because
  the working result shared its list with the empty template. Now its own list;
  retested: a stop after 30 frames returns 0 frames, `stopped: True`.
- Through the app's own caller, `scan_cache.scan_video_frames`, into a throwaway
  cache (deleted after): 2 videos read, 3 frames recorded; `videos_done` rows
  hold 4 checked / 1 kept and 4 checked / 2 kept; a second run read 0 videos
  (resume skips videos already done).
- Not tested: a full Seek run over a folder with the new rule.

## Banner (user's answer 4)

- `otrain.py`: `TRAINING_SETTINGS_BANNER` gains a "VIDEO SCAN RULE - the user's
  rule, 2026-09-25" block (faces on one frame in every 24; near-duplicates still
  dropped); `training_settings_summary()` gains `scan_face_check_every`. Both read
  `video_frames.FACE_CHECK_EVERY` - one place for the number.
- `review_page.html`: the settings table gets a "Video scan" row, shown only when
  the server sends the value.
- `README.md`: the banner paragraph says so.
- Checked: the banner prints as intended; `pipeline` and `review_server` import
  cleanly with the OneTrainer venv python; the page's table code, run in node,
  gives the "Video scan" row with the value and leaves it out without it.
- Found: the review server running since 2026-09-24 (pid 6540, port 50086) sends
  the new page from disk but the old settings from memory. Without the guard the
  row would have read "every undefined". It was **not** restarted - it holds the
  Undo history in memory; that is the user's call. The row appears after a restart.
- Not looked at in a browser.

## Look-alike check moved out of the scan (user, 2026-09-26)

- Walking through the steps, the user was shown that the tools found (LoRA-Harvester,
  DeepFaceLab) drop look-alikes after finding the person and cutting out the face,
  and that imagededup's own benchmark says whole-picture hashing does "not perform
  well for finding near duplicates". User: "move my duplicate process after finding
  the person like the community", then chose **(a) take it out of the first scan
  completely** over (b) keeping a face-only twin check in the scan. This replaces
  answer 3 above (keep it as it is) and overrides the 2026-09-13 rule to keep that
  check where it was.
- Code: `scan_frames` records every checked frame that has a face. Removed:
  `_phash`, `_hamming`, `_small_gray`, `METRIC_WIDTH`, `PHASH_HAMMING_MAX`,
  `EMBED_SIM_MAX`, the `duplicates_dropped` count (nothing else used them).
  Look-alikes are still dropped later by the frames stage and the dedupe stage.
- Banner line, review-page row, README and module description updated to say so.
- Tested (`logs/scan_rule_1in24_test_2026-09-25/test_output_no_lookalike_check.txt`):
  IMG_3763 4 checked / 4 recorded (was 1), 14.7 s; IMG_3768 4 / 4 (was 2), 3.8 s;
  IMG_9845 339 checked / 337 recorded (was 115), 271.4 s (was 109.1 s); stop after
  30 frames returns 0 frames; through `scan_video_frames` into a throwaway cache
  (deleted): 8 frames recorded, done rows 4/4 and 4/4.
- Cost: about 2.5 times the scan time on the long video, because every checked
  frame now has its faces found.

## Were the number-only answers survey ratings? (2026-09-26)

Claude Code's feedback survey also uses 1/2/3, so the user was asked whether any
of the number-only replies above were survey ratings. Answer: **(a) — they were
all answers; nothing is undone.** From now on Claude's options use letters, not
numbers (user's choice, same day).
