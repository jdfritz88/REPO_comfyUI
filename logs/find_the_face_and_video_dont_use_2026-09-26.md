# Videos: "Yes — but don't use it" and "Find the face" — 2026-09-26

## What the user asked (2026-09-25) and chose
- Videos need the photos' third answer, "Yes — but don't use it".
- "Find the face": greys the frame (still visible), crosshair drag to draw a box around
  her face, a click anywhere clears the box to redraw, Cancel ends it and ungreys,
  Submit sends the face to the scanner to help it.
- The boxed face is the reference for THAT video only (user's option 1, 2026-09-25).
- 2026-09-26: after the diagnostic and the scan-rate review, "(a) Build both".

## What was built
- `review_page.html` video card: four buttons — She appears here · Yes — but don't use it ·
  Find the face · Not her. Find the face pauses, hides the player controls, lays a 38%
  dark layer over the video with a hint line, pointer-drag draws the box (a drag under
  6 px counts as a click and clears it), Submit is greyed until a box exists. The box is
  sent as a share (0-1) of the picture itself, not the black bars. A refused box keeps
  the grey layer so it can be redrawn. "What to do" text updated.
- `review_server.py`:
  - video `her_unused`: logged, staged for Undo; when final: the video's content hash
    goes into not_used, logged, copy to the Recycle Bin.
  - video `face_box` (`_face_box_answer`): reads the frame at that moment, finds the face
    at least half inside the box (whole frame first, then the box with room around it),
    refuses with a plain message if none; logs it as a "She appears here" answer at that
    frame carrying `face_box`, `seed` (the face's 512 numbers), `like_her_profile`.
    Undo, the list and processing treat it like any mark.
- `seek.py`: `SEED_MATCH = 0.40` (InsightFace's documented default); `_seed_picker` — a
  face counts as her if it matches the boxed face at 0.40+ or passes her profile's rule;
  `_pull_marked_videos` uses it when the mark has a seed. `_take` skips a video whose
  hash is in not_used or not_person.
- Her profile is never changed by the boxed face.

## Tested
Server and search, throwaway person "zztestfind" (copies of her identity and the two
videos; `logs/find_the_face_test_2026-09-26/server_and_search_test.txt`):
- a box on empty sky is refused with the message;
- a box at 1.0 s on IMG_3768 → face found at [496,178,555,268], frame 30, 0.498 like
  her profile; the video leaves the list; Undo takes it back; redone;
- IMG_3763 "don't use it" → copy moved out; after finalising, in not_used and skipped
  by the search;
- the pull with the boxed face took **61 frames** of IMG_3768 from frame 30 (0 before).
Browser, throwaway person "zztestfindui", real clicks in Chrome:
- all four buttons on both cards; the orange box shows "Video scan" and "Videos she is
  in" rows;
- Find the face → grey layer + hint, controls hidden, Cancel/Submit; a wrong box drawn,
  a click cleared it (Submit greyed again); a box around her face; Submit → "Recorded —
  IMG_3768.MOV: face saved from frame 30 (1.00s) …", card left the list, Undo (1);
- Cancel on IMG_3763 restored the buttons and controls, no grey layer;
- "Yes — but don't use it" on IMG_3763 → "Recorded — … her, but not used …", Undo (2);
- no console errors. Both throwaway people sent to the Recycle Bin afterwards.

## Known limits
- The review page already open since 2026-09-24 runs the old server code: the new
  buttons will show on reload but the server will not know the new answers until the
  review page is closed and opened again from the Face Tool.
- Clicking a button scrolls the card into view; noticed in the browser test.
- Not tested: a full search run using a boxed face.
