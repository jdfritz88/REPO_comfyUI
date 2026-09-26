# The user's face-tool rules written down — 2026-09-26

- The user named the root cause of the scanner contradictions: rules they set were never
  written where the next Claude session reads first. Offered (a) a section in this repo's
  CLAUDE.md, (b) its own file with a line in CLAUDE.md, (c) no. User: **(b)**, and also
  show it on the review page's yellow-framed box as section (b); "Photos and frames …"
  becomes (a) without "your choice … date"; "Training settings" without "— text-encoder
  training is your choice (c)".
- `face_training/FACE_TOOL_RULES.md`: 35 standing rules in 5 steps, plain words, dates;
  replaced rules left out (history in `logs/face_rules_audit_2026-09-25/`); instructions
  for every session at the top (add new rules the same session, never quietly make code
  and rule match).
- `CLAUDE.md` (this repo): "Face tool: read the user's rules first" section.
- `review_server.py`: `face_tool_rules()` reads the file on every request; GET `/api/rules`.
- `review_page.html`: headings changed as asked; section (b) "YOUR FACE TOOL RULES" fills
  from `/api/rules`; a review program started before today shows a note instead.
- Tested in Chrome on a throwaway person: headings as asked; (b) lists 35 rules numbered
  1-35 under 5 step headings. Throwaway person removed.
