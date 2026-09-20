"""
Delete a person from Face Seek - all of them, or only the parts chosen.

The Face Tool's Delete button asks what should go (user, 2026-09-15): the whole
person, or a picked list. Everything goes to the Recycle Bin (recycle.py), so a
wrong click is undoable - except the registry entry, which is a line inside a
shared file and is rewritten without this person.

  parts(slug)              -> what this person owns right now, with sizes
  delete(slug, keys)       -> send those parts to the Recycle Bin

The parts, by key:

  photos_videos   found/, video_and_frames/ (older profiles: video_frames/),
                  processed/, needs_review/, videos/, uncertain/ - the copies
                  Seek gathered, the videos it kept and the frames it pulled
  crops           clean/head + clean/body - the cropped training photos
  learning        identity/, scan_cache/, search_history.json - what the app
                  learned about this person and where it had got to
  backups         backup/ - the 5 rotating snapshots
  runs            _face_runs/<slug> - OneTrainer's working folders
  loras           the trained LoRA files, their thumbnails, and this person's
                  entry in the ComfyUI face-shelf registry
  profile         profile.json and the profile folder itself (implied by "all")

stdlib only apart from the pipeline constants, so the Face Tool can import it.
"""

from __future__ import annotations

import glob
import os

from face_training import profiles as P
from face_training.recycle import recycle

# key -> (what it is called on screen, how to list its paths)
ORDER = ("photos_videos", "crops", "learning", "backups", "runs", "loras", "profile")
LABELS = {
    "photos_videos": "Copied photos, videos and pulled frames",
    "crops": "Cropped training photos (clean set)",
    "learning": "What it learned: identity, scan cache, search history",
    "backups": "Backup snapshots",
    "runs": "Training work folders (_face_runs)",
    "loras": "Trained LoRA files, thumbnails and the face-shelf entry",
    "profile": "The profile itself (profile.json and its folder)",
}


def _paths(prof: P.Profile, key: str) -> list[str]:
    if key == "photos_videos":
        return [prof.found_dir, prof.video_frames_dir, prof.processed_dir,
                prof.needs_review_dir, prof.videos_dir, prof.uncertain_dir]
    if key == "crops":
        return [os.path.join(prof.dir, "clean")]
    if key == "learning":
        return [prof.identity_dir, prof.scan_cache_dir, prof.history_path]
    if key == "backups":
        return [prof.backup_dir]
    if key == "runs":
        from face_training.pipeline import WORK_ROOT
        return [os.path.join(WORK_ROOT, prof.slug)]
    if key == "loras":
        from face_training.pipeline import FACES_DIR, THUMBS_DIR, load_registry
        out = sorted(glob.glob(os.path.join(FACES_DIR, f"{prof.slug}_*.safetensors")))
        for entry in load_registry().get("people", {}).get(prof.slug, {}).get("loras", {}).values():
            thumb = entry.get("thumb")
            if thumb:
                out.append(os.path.join(FACES_DIR, thumb))
            out.append(os.path.join(THUMBS_DIR, entry["name"] + ".png"))
        return sorted({p for p in out})
    if key == "profile":
        return [prof.dir]
    raise ValueError(f"unknown part {key!r}")


def _size(paths: list[str]) -> tuple[int, int]:
    """(files, bytes) across these paths."""
    files = size = 0
    for p in paths:
        if os.path.isfile(p):
            files += 1
            size += os.path.getsize(p)
        elif os.path.isdir(p):
            for root, _dirs, names in os.walk(p):
                for n in names:
                    try:
                        size += os.path.getsize(os.path.join(root, n))
                        files += 1
                    except OSError:
                        pass
    return files, size


def parts(slug: str) -> list[dict]:
    """What this person owns right now: [{key, label, paths, files, bytes}]."""
    prof = P.Profile(slug)
    out = []
    for key in ORDER:
        paths = [p for p in _paths(prof, key) if os.path.exists(p)]
        files, size = _size(paths)
        out.append({"key": key, "label": LABELS[key], "paths": paths,
                    "files": files, "bytes": size})
    return out


def registry_entry(slug: str) -> dict | None:
    from face_training.pipeline import load_registry
    return load_registry().get("people", {}).get(slug)


def _forget_in_registry(slug: str) -> bool:
    """Take this person out of the ComfyUI face-shelf registry. -> removed?"""
    from face_training.pipeline import load_registry, save_registry
    reg = load_registry()
    if slug not in reg.get("people", {}):
        return False
    reg["people"].pop(slug)
    save_registry(reg)
    return True


def delete(slug: str, keys) -> dict:
    """Send the chosen parts to the Recycle Bin.

    'profile' last, since it is the folder the others live in. Returns
    {"recycled": [paths], "failed": [paths], "registry_entry_removed": bool}.

    A file another program has open cannot go to the Recycle Bin, and the folder
    holding it cannot either: those paths come back in "failed" and the caller
    says so rather than pretending the person is gone (seen 2026-09-15 with a
    test script still holding scan_cache/faces.db open). The Face Tool's Delete
    button is greyed out while that person has a search or training running,
    which is the case that would otherwise hit this.
    """
    keys = [k for k in ORDER if k in set(keys)]
    prof = P.Profile(slug)
    done, failed = [], []
    registry_removed = False
    for key in keys:
        # The paths first, the registry second: the LoRA part reads the thumbnail
        # names out of the registry, so forgetting the person first left their
        # thumbnails behind (tested 2026-09-15).
        paths = [p for p in _paths(prof, key) if os.path.exists(p)]
        if key == "loras":
            registry_removed = _forget_in_registry(slug)
        if not paths:
            continue
        if recycle(paths):
            done += paths
        else:
            failed += [p for p in paths if os.path.exists(p)]
            done += [p for p in paths if not os.path.exists(p)]
    return {"recycled": done, "failed": failed,
            "registry_entry_removed": registry_removed}
