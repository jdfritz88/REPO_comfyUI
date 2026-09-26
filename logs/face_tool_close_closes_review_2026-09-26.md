# Face Tool Close also closes the review pages' program — 2026-09-26

## Why
The "Yes — but don't use it" video button failed on the user's open review page with
"unknown answer 'her_unused'": the review page's program (review_server, started by the
Face Tool on 2026-09-24 18:47, pid 6540, runs windowless as "pythonw") was still running
the code it started with. Closing the browser tab does not stop it, and the Face Tool's
Review button reopens a running one instead of starting a fresh one.
User: "The 'close' button on the face search app should always also - NOT INSTEAD OF - but
also close that server."

## What changed
- `review_server.py`: POST `/api/shutdown` — answers, then stops the server; main()'s
  finally carries out answers still waiting for Undo and removes review_server.json.
  New `stop_running(prof)`: asks it to shut down; if it is still alive after 15 s (a
  program started before this change does not know the request) it is ended with
  taskkill — its waiting answers stay in the undo file and the next review page carries
  them out. A training run is its own program and keeps going; only the "training ended"
  line in the search history is missed if the page is closed mid-run.
- `face_tool_ui.py` `close()` (the Close button and the window X): backs up as before,
  THEN closes every person's review program and logs what happened, then closes.

## Tested (`logs/close_review_test_2026-09-26/test_output.txt`), throwaway person
- A — a review program with today's code: "closed" in 1.0 s; process gone;
  review_server.json removed.
- B — a pretend old program (answers ping, refuses shutdown): "ended (it did not know how
  to close itself)" in 3.8 s; process gone.
- C — the Face Tool's own close(), with only the test person listed and backup stubbed:
  log "Backed up 1 profile(s) before closing." → "'zztestclose': review page closed." →
  window destroyed; process gone.
- Throwaway person sent to the Recycle Bin.

## Limit
The Face Tool window open now runs the code it started with, so its Close does not do
this yet. It works from the next time the Face Tool is opened.
