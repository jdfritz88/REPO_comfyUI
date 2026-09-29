"""
One-time fill-in: save the faces of video frames that were kept BEFORE 2026-09-27 into
the scan's notes (the scan cache), so the rebuild of her face sketch can learn from them.

Why: frames pulled by the closer look were never noted by the first scan, so they could
never teach her sketch - not even the ones the user answered "Yes, it's her". From
2026-09-27 every kept frame is noted when it is cropped (seek._remember_faces); this does
the same once for the frames kept before that (user chose (a): new AND kept frames).

How: for each kept video frame not yet in the notes and not on her not-her list, it finds
the frame's saved crop in clean/ (face crop first, else face-and-body), looks for faces in
it, and notes those faces under the frame's own key. Nothing else changes: whether a frame
actually teaches is still decided by the rebuild's own rules (not-her list, unsure, ...).

  python -m face_training.backfill_kept_frames --profile susana --dry-run
  python -m face_training.backfill_kept_frames --profile susana

Runs in the OneTrainer venv.
"""
from __future__ import annotations

import argparse
import os

import cv2

from face_training import profiles as P
from face_training import search_history as SH
from face_training.scan_cache import ScanCache
from face_training.sort_photos import _detect, _get_app

NOT_HER = ("not_her", "not_her_user")


def run(slug: str, dry_run: bool) -> dict:
    prof = P.Profile(slug)
    if not prof.data:
        raise ValueError(f"no profile '{slug}'")
    hist = SH.History(prof.history_path)
    not_her = hist.data.get("not_person", {})
    not_used = hist.data.get("not_used", {})      # don't use it / duplicate: never taught
    crops_by_capture: dict[str, list[str]] = {}
    for rel, c in hist.data["crops"].items():
        if c.get("capture"):
            crops_by_capture.setdefault(c["capture"], []).append(rel)
    cache = ScanCache(os.path.join(prof.scan_cache_dir, "faces.db"))
    app = None
    out = {"kept_frames": 0, "already_noted": 0, "not_her": 0, "no_crop": 0,
           "no_face_in_crop": 0, "noted": 0, "would_note": 0}
    try:
        for name, c in hist.data["captures"].items():
            hsh = c.get("hash") or ""
            if ":f" not in hsh:
                continue                                   # photos were noted by the scan
            out["kept_frames"] += 1
            if cache.has(hsh):
                out["already_noted"] += 1
                continue
            base = hsh.rsplit(":f", 1)[0]
            if (hsh in not_her or base in not_her or hsh in not_used or base in not_used
                    or c.get("outcome") in NOT_HER):
                out["not_her"] += 1
                continue
            rels = sorted(crops_by_capture.get(name, []), key=lambda r: not r.startswith("head/"))
            paths = [os.path.join(prof.dir, "clean", *r.split("/", 1)) for r in rels]
            paths = [p for p in paths if os.path.isfile(p)]
            if not paths:
                out["no_crop"] += 1
                continue
            if dry_run:
                out["would_note"] += 1
                continue
            app = app or _get_app()
            for p in paths:
                img = cv2.imdecode(__import__("numpy").fromfile(p, dtype="uint8"), cv2.IMREAD_COLOR)
                faces = _detect(app, img) if img is not None else []
                if faces:
                    cache.record(hsh, p, faces, img.shape)
                    out["noted"] += 1
                    break
            else:
                out["no_face_in_crop"] += 1
    finally:
        cache.close()
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--profile", required=True)
    ap.add_argument("--dry-run", action="store_true", help="count only; write nothing")
    a = ap.parse_args()
    print(run(a.profile, a.dry_run))
