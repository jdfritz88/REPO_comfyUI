# Face tool notes checked against the code — 2026-09-26

User's choice (b): rewrite the out-of-date opening note in video_frames.py, and check all
the face tool's notes (README + every program file's opening note) against the code, fix
any that are wrong, and list each. Three read-only helpers audited the 28 files and the
README; every finding was re-checked against the code before it was fixed.

## Fixed (notes only — no behaviour changed)
- video_frames.py — opening note rewritten: three passes (1 in 24, no look-alike check;
  closer look 1 in 12 with the boxed face; frames stage), blur line "not settled".
- seek.py — stages note (scan 1-in-24; videos to video_and_frames/, not found/; reteach
  leaves out unsure copies; clean re-judges, sends close calls to needs_review/); copies
  paragraph (videos not in found/); stop flag is the STOP file, not profile.json; stage
  comment 6→8 stages; _flush_frames note ("twice a second", "found/"); clean-stage comment
  about videos in found/ (leftovers from before 09-15); two messages (a video-copy warning
  said "found/"; the search summary said "photos and video frames copied into found/").
- scan_cache.py — a finished folder is skipped whole (new files in it are not picked up);
  a video stopped halfway is read again from its start.
- seek_library.py — progress file is logs/seek/<profile>_progress.json; STOP in logs/seek/;
  the Face Tool's Stop also halts it.
- profiles.py — scan cache is one faces.db per person; backups include search_history.json;
  status labels include Working/Review; "stdlib only" true at import time only.
- search_history.py — captures include kept video frames and stages frames/approved_video,
  "unsure"/"outcome"; reteach does read captures now (not "nothing here is learned from").
- facebank.py — which faces are banked; only the clean stage moves close calls to
  needs_review/; answers come from the review page.
- near_miss.py — close calls within the margin ARE logged now.
- identity.py — match() returns -1..1, not 0..1.
- otrain.py — runs this repo's ot_train_entry.py, not OneTrainer's scripts/train.py.
- jobs.py — a new family also needs thumbs.py FAMILY_CKPT.
- recycle.py — the dedupe stage also deletes outright (duplicate crops, needs_review dupes).
- safe_replace.py — a few saves still call os.replace directly.
- backup.py — the tracked list includes search_history.json.
- mark_reviewed.py — --forget only unmarks crops now in clean/.
- face_tool_ui.py — the button is "Review", not "Review crops"; launcher option 6, not 4;
  Close also closes the review programs.
- README.md — video_and_frames/<video>__<hash8>/ (not video_frames/<video>/); "Three
  passes"; videos copied to their own folder, not found/; feedback answers come from the
  review page; banner is near the top of the whole-run log, not the per-job logs; krea2 is
  its own architecture; otrain runs ot_train_entry.py; thumbs.py is run by pipeline.py;
  added the new video buttons (don't use it, Find the face), the photo buttons, and Close.

## Real problems found — NOT fixed (the user decides)
1. Reteach still learns from photos the user marked "not her" on the review page: Delete
   records not_person and forgets the crop, but the capture stays, and reteach does not
   check not_person (seek._stage_reteach). Found by reading the code; not run.
2. A folder that finished scanning is skipped whole on later runs, so a photo added to it
   afterwards is never scanned (scan_cache.scan_folder skip_finished=True, called by seek).
3. thumbs.py run by hand (its own command line) calls render_thumb without the required
   subject argument and would fail. The pipeline's own call is not affected.
