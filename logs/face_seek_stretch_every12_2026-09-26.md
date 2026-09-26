# Stretch pass: one frame in every 12 — 2026-09-26

## The decision
The stretch pass (in a video the search matched her in, find the stretches she is on
screen) looked for her every 0.5 s — about 1 frame in 15 at 30 fps — set 2026-09-15 on
a Claude claim that face finding "can't run on every frame" (~2 s a frame). The
user's own rule that day was "look at every frame". Offered (a) keep ~1 in 15,
(b) 1 in 24, (c) every frame, (d) another rate, the user chose **(d) every 12 frames**.

## What changed
- `video_frames.py`: `SEGMENT_STEP_S = 0.5` → `SEGMENT_STEP_FRAMES = 12`;
  `her_segments` uses it directly; its description and `_kps_at` updated. The stale
  pass-2 paragraph at the top of the file was left alone (a separate open question).
- `otrain.py`: the training-settings banner's VIDEO SCAN RULE block gains a line
  for it, and `training_settings_summary()` gains `stretch_face_check_every`.
- `review_page.html`: settings table row "Videos she is in", shown only when the
  server sends the value (a server started before this change does not).
- `README.md`: pass 2 describes the new rate.

## Tested (`logs/stretch_every12_test_2026-09-26/test_output.txt`)
With her real profile and the app's own rule (unsure = not her), cutoff 0.441:
- IMG_3768: 8 checks (was 7), 0 clearly her, 3 unsure → no stretch; the video still
  goes to review, as before. Scores: frame 0 0.163, 12 0.404, **24 0.458 (unsure)**,
  **36 0.434 (unsure)**, 48 0.371, 60 0.355, 72 0.339, 84 0.318. Her clearest frames,
  25 (0.509) and 35 (0.513), are one frame from the checks at 24 and 36.
- IMG_3763: 8 checks (was 6), 0 clearly her, 3 unsure → no stretch.
- The rate works as coded. For these two clips it does not change the outcome.
