# A "her" list beside the "not her" list, per person — 2026-09-26

User chose (a): each person's own record file (<profile>/search_history.json) gets a
single her list beside the not-her list (not_person), recording every picture decided as
her from now on.

## Changed
- search_history.py: new section "her" (older files start with it empty);
  mark_her(hsh, ...) adds and takes it off not_person; mark_not_person / mark_not_her take
  it off "her" — the latest decision wins, never on both lists.
- review_server.py: when an answer is final (out of Undo's reach) — "Yes, it's her" on a
  photo, "She appears here" and "Find the face" on a video (the video's content hash is
  carried on the staged answer) — it goes on the her list.
- seek.py: every video frame kept of her (frames stage, and processing of marked videos)
  goes on the her list.
- FACE_TOOL_RULES.md rule 35 covers both lists.

## Tested (`logs/her_list_test_2026-09-26/test_output.txt`), throwaway person
- Before the answers were final: her list 0 (Undo could still take them back).
- After: 3 — the photo Yes, the She-appears-here video, the Find-the-face video.
- Processing the approved work: 86 frames pulled, 5 kept → 5 frames on the her list.
- A later Not her on the photo moved it to the not-her list and off the her list.
- The shared learning files in _global were untouched (feedback file compared byte for
  byte; the test blocked the judge's write). Throwaway person removed.
- Also confirmed from her real record: the user's "Yes — but don't use it" on IMG_3763
  (23:14:11) was made final and put on her don't-use list (23:14:22).
- Not added retroactively: pictures decided before today are not on the her list.
