"""
Face Seek's search history for one person.

What it records, in <profile>/search_history.json:

  captures    every photo or video frame Seek copied into found/ - the copy's
              name, the original it was copied from, that original's content
              hash, and which stage found it (group or search)
  crops       every finished crop in clean/head and clean/body - which capture it
              was cut from, and whether other people's faces were still in it
              after the crop was trimmed (shown framed in yellow on review)
  not_person  originals the person reviewing said are not this person, keyed by
              content hash, so a later search never captures them again
  not_used    originals the person reviewing said ARE this person but chose not
              to use - "Yes, but don't use it" and "Duplicate" (user,
              2026-09-17), keyed by content hash, so a later search does not
              offer them again. Nothing here changes what the app believes her
              face looks like: the decision is recorded, not learned from
  events      what happened during review and processing, in order: deletions,
              rotations, duplicates removed

Why its own file and not profile.json: Seek rewrites profile.json constantly
while it runs, and the review page writes here while Seek is not running.
Nothing in this file teaches the face judge - review decisions are recorded,
not learned from (user, 2026-09-13).

stdlib only.
"""

from __future__ import annotations

import json
import os
import time

from face_training.safe_replace import read_text, replace_file

EMPTY = {"captures": {}, "crops": {}, "not_person": {}, "not_used": {}, "events": []}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class History:
    def __init__(self, path: str):
        self.path = path
        self.data = json.loads(json.dumps(EMPTY))
        if os.path.isfile(path):
            # A damaged history is not silently replaced with an empty one:
            # that would forget every "not this person" decision. A Seek may be
            # swapping it in right now - read_text waits that out (safe_replace.py).
            loaded = json.loads(read_text(path))
            for k in EMPTY:
                if k in loaded:
                    self.data[k] = loaded[k]
        self._captured = {c["hash"] for c in self.data["captures"].values() if c.get("hash")}

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=1)
        replace_file(tmp, self.path)        # a backup copy may be reading it - safe_replace.py

    # --- captures ------------------------------------------------------
    def add_capture(self, name: str, source: str, hsh: str, stage: str, video: str = ""):
        self.data["captures"][name] = {"source": source, "hash": hsh, "stage": stage,
                                       "video": video, "at": _now()}
        if hsh:
            self._captured.add(hsh)

    def is_captured(self, hsh: str) -> bool:
        return hsh in self._captured

    def captured_hashes(self) -> set[str]:
        return set(self._captured)

    def capture(self, name: str) -> dict | None:
        return self.data["captures"].get(name)

    def set_outcome(self, name: str, outcome: str):
        c = self.data["captures"].get(name)
        if c is not None:
            c["outcome"] = outcome

    # --- crops ---------------------------------------------------------
    def add_crop(self, rel: str, capture: str | None, source: str, hsh: str,
                 others_remain: int, refined: bool):
        self.data["crops"][rel] = {"capture": capture, "source": source, "hash": hsh,
                                   "others_remain": int(others_remain),
                                   "refined": bool(refined), "at": _now()}

    def crop(self, rel: str) -> dict | None:
        return self.data["crops"].get(rel)

    def forget_crop(self, rel: str):
        self.data["crops"].pop(rel, None)

    # --- review decisions ----------------------------------------------
    def excluded(self, hsh: str) -> bool:
        return hsh in self.data["not_person"]

    def not_used_hash(self, hsh: str) -> bool:
        return hsh in self.data["not_used"]

    def skipped(self, hsh: str) -> bool:
        """Leave this original alone on a later search: the person reviewing
        said it is not her, or said it is her but is not to be used."""
        return self.excluded(hsh) or self.not_used_hash(hsh)

    def mark_not_used(self, hsh: str, reason: str, name: str = "", source: str = ""):
        """"Yes, but don't use it" or "Duplicate" (user, 2026-09-17): her, kept
        out of the training set, and not offered again."""
        if hsh:
            self.data["not_used"][hsh] = {"source": source, "photo": name,
                                          "reason": reason, "at": _now()}

    def forget_not_used(self, hsh: str):
        """Undo of the answer that put it there."""
        self.data["not_used"].pop(hsh, None)

    def mark_event_undone(self, ref: str) -> bool:
        """Mark the answer carrying this ref as taken back, in place."""
        for e in reversed(self.data["events"]):
            if e.get("ref") == ref and not e.get("undone"):
                e["undone"] = True
                return True
        return False

    def mark_not_person(self, rel: str):
        """The reviewer deleted this crop: its original is not this person."""
        c = self.data["crops"].get(rel) or {}
        hsh = c.get("hash")
        if hsh:
            self.data["not_person"][hsh] = {"source": c.get("source", ""), "crop": rel,
                                            "at": _now()}
        return hsh

    def log(self, kind: str, **kv):
        self.data["events"].append({"at": _now(), "kind": kind, **kv})
