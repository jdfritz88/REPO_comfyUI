# Frames clean-up: duplicate look line 90% → 85% — 2026-09-26

- User, walking through step 7: "Change to 85%" (the frames stage's "same look" line —
  aligned face, eyes band and mouth band each this alike, with the same head angle).
- video_frames.py: DUP_LOOK_MIN 0.90 → 0.85. More frame pairs now count as twins, so fewer
  frames are kept. On the 147 pairs measured 2026-09-15, a pair at 0.87 was a smile opening:
  with the same head angle it now counts as a duplicate (the sharper one is kept).
- Checked with the real twins test: a look of 0.87 → duplicate; 0.84 → kept as different.
- Not changed: the review page's look-alike grouping slider (face_groups.py) has its own
  numbers — notch 4 is still look 0.90; its comment now says so.
- README and FACE_TOOL_RULES.md (rule 22) updated. Affects frames pulled from now on; frames
  already pruned are not re-pruned.
