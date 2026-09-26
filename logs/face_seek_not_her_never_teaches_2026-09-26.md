# "Not her" never teaches her face profile, and every Not her is recorded — 2026-09-26

## Found
- The notes audit found reteach (the rebuild of her face profile, step 4 of every search)
  never read her not-her list. Her records then: 1,386 captures, 167 on the not-her list
  (163 video frames, 4 group photos) — all would be blended into her profile next search.
- Not her on an uncertain PHOTO only wrote the shared facebank feedback + a diary line;
  Not her on an uncertain VIDEO only wrote a diary line. Neither reached her not-her list,
  so a later search could pull that video again.
- Her per-person record exists: <profile>/search_history.json (since 2026-09-13), with a
  not-her list (not_person). There is no single "her" list; yes answers are spread across
  capture outcomes and diary lines.

## User
"a. yes, this should have been fixed a long time ago. This was always the rule. make sure
this is reinforced." Also: every photo/frame picked up and processed as her or not her is
recorded in that person's own logs — one for her, one for not her — not one shared log.

## Changed
- seek._stage_reteach leaves out: anything on her not-her list (photo hash, or a video's
  hash for its frames); captures whose outcome is not_her (clean stage) or not_her_user;
  close calls (unsure, or outcome needs_review from before the unsure mark) until cropped.
  Says how many were left out.
- search_history.mark_not_her(hsh, ...): writes to her not-her list.
- review_server._finalise: Not her on an uncertain photo → her not-her list + outcome
  not_her_user; Not her on an uncertain video → her not-her list (later searches skip it).
- FACE_TOOL_RULES.md: rule 15 reinforced; new rule 35 (every her/not-her decision in the
  person's own file; every Not her into their not-her list).

## Tested (`logs/not_her_test_2026-09-26/test_output.txt`)
- Rebuild with 8 cases → used only: the sure photo, an old close call later approved, an
  unsure copy approved. Left out: deleted crop, frame of a Not-her video, clean-stage not
  her, old unanswered close call, Not-her photo. PASS.
- Throwaway person: Not her on a photo and on a video → both in her not-her list; the video
  is skipped by later searches.
- The photo test also wrote one row to the shared facebank feedback file (_global); that
  row was removed (backup of the file before removal kept in the test folder). No judge
  file exists, so nothing was learned from it. Throwaway person removed.
- Not tested: a full search run.
