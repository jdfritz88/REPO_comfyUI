# Unsure copies no longer teach her face profile — 2026-09-26

## The decision
- 2026-09-14 the user decided the search learns only from the user's answers, never
  from its own unsure guesses ("Yes that seems 100% aligned with what i have already
  requested throughout this chat"). That was put into the judge (`facebank.train_judge`).
- 2026-09-26, walking through the steps, it was found that the reteach stage still
  rebuilt her face profile from every capture, including photos copied on a close
  call (unsure, leaning "her") before the user had seen them.
- The user chose **(b)**: unsure photos and frames teach nothing until the user
  answers, but an unsure video frame still gets its video the closer look (the
  stretch pass keeps only clear frames of her; only-maybes sends the video to review).
  Rejected: (a) leave it; (c) send the video straight to review with no closer look.
- The user asked for a short combined explanation of (b) and (c) in the review page's
  orange settings box.

## What changed
- `search_history.add_capture(..., unsure=False)`: a close-call capture is marked
  `"unsure": true`.
- `seek.py`: group and search pass the judge's borderline flag to `_take` →
  `_capture`. Video frames: unchanged (an unsure frame still queues the video).
- `seek._stage_reteach`: leaves out captures marked unsure unless their outcome is
  "cropped" (the user said yes and the photo was cut); says how many were left out.
  Captures written before this change carry no mark and still count.
- `review_page.html`: new block in the orange box — both options, (b) marked chosen.
- `README.md`: reteach line says so.

## Tested (`logs/unsure_reteach_test_2026-09-26/test_output.txt`)
- A throwaway history with three captures (sure; unsure, not answered; unsure,
  answered and cropped), saved and re-read from disk, run through the real
  `_stage_reteach`: the rebuild used faces 1 and 3 only; message "1 unsure copies
  left out until you answer". PASS.
- Not tested: a full search run. The review page block was not looked at in a browser.
