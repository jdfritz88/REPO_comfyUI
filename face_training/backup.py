"""
Rotating backup of a person's TRACKING state only:
  profile.json, identity/ (mean.npy, refs.npy, refs.json), scan_cache/faces.db

NOT the cropped photos and NOT the trained LoRA files - those are handled
separately.

Five rotating snapshots per person, at <profile>/backup/1/ (newest) through
<profile>/backup/5/ (oldest). Each new backup first writes fresh copies into
<profile>/backup/_incoming/, and only when every copy succeeded shifts every
slot up by one (5 is dropped, 4->5, ... 1->2) and renames _incoming/ to 1/.

Called automatically:
  - at the end of every Seek run (seek.py), whether it finished or was
    stopped - both paths go through the same cleanup
  - at the end of every Train run (pipeline.py), whether it finished or was
    stopped
  - when the Face Tool window closes (its X button or its Close button)
  - when the launcher console closes (its X button, or logoff/shutdown)

Also callable by hand (the Face Tool's "Backup" button -> backup_profile),
and restore_backup() to roll one profile back to an earlier snapshot.

stdlib only - safe to import from the launcher's own Python, not just the
OneTrainer venv.
"""

from __future__ import annotations

import os
import shutil
import time

from face_training.safe_replace import copy_file

N_SLOTS = 5
# where a new snapshot is assembled before it becomes slot 1
STAGING = "_incoming"
# paths relative to a profile's own folder
TRACKED = ("profile.json", "identity", os.path.join("scan_cache", "faces.db"),
           # captures, crops and "not this person" decisions - restoring
           # profile.json without it would forget what review decided
           "search_history.json")


def _slot_dir(profile_dir: str, n: int) -> str:
    return os.path.join(profile_dir, "backup", str(n))


def backup_profile(profile_dir: str) -> str | None:
    """Rotate and write a fresh backup for one profile folder.
    Returns the new slot's path, or None if this isn't a real profile folder
    yet (no profile.json) - nothing to back up."""
    if not os.path.isfile(os.path.join(profile_dir, "profile.json")):
        return None

    root = os.path.join(profile_dir, "backup")
    os.makedirs(root, exist_ok=True)

    # Copy first, rotate after. Rotating first meant a copy that failed (a Seek
    # swapping profile.json in at that moment) had already dropped slot 5 and
    # left slot 1 empty - one backup generation lost per failure (Fix log,
    # 2026-09-13).
    staging = os.path.join(root, STAGING)
    if os.path.isdir(staging):
        shutil.rmtree(staging)              # left by an earlier backup that failed
    os.makedirs(staging)
    try:
        for rel in TRACKED:
            src = os.path.join(profile_dir, rel)
            if not os.path.exists(src):
                continue
            dst = os.path.join(staging, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                copy_file(src, dst)         # waits out a swap in progress - safe_replace.py
        with open(os.path.join(staging, "_backed_up_at.txt"), "w", encoding="utf-8") as fh:
            fh.write(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n")
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    oldest = _slot_dir(profile_dir, N_SLOTS)
    if os.path.isdir(oldest):
        shutil.rmtree(oldest, ignore_errors=True)
    for n in range(N_SLOTS - 1, 0, -1):
        src, dst = _slot_dir(profile_dir, n), _slot_dir(profile_dir, n + 1)
        if os.path.isdir(src):
            os.replace(src, dst)

    dest = _slot_dir(profile_dir, 1)
    os.replace(staging, dest)
    return dest


def backup_profile_by_slug(slug: str) -> str | None:
    """Same as backup_profile(), looked up by profile slug - lets callers
    (like pipeline.py) back up without importing profiles.py themselves."""
    from face_training import profiles as P
    return backup_profile(os.path.join(P.PROFILES_ROOT, slug))


def backup_all_profiles() -> list[str]:
    from face_training import profiles as P
    out = []
    if not os.path.isdir(P.PROFILES_ROOT):
        return out
    for name in os.listdir(P.PROFILES_ROOT):
        pdir = os.path.join(P.PROFILES_ROOT, name)
        if os.path.isdir(pdir):
            r = backup_profile(pdir)
            if r:
                out.append(r)
    return out


def list_backups(profile_dir: str) -> list[dict]:
    """-> [{"slot": 1, "at": "2026-09-08T10:15:00"}, ...] newest first,
    only slots that actually have a backup in them."""
    out = []
    for n in range(1, N_SLOTS + 1):
        stamp_f = os.path.join(_slot_dir(profile_dir, n), "_backed_up_at.txt")
        if os.path.isfile(stamp_f):
            with open(stamp_f, encoding="utf-8") as fh:
                stamp = fh.read().strip()
            out.append({"slot": n, "at": stamp})
    return out


def restore_backup(profile_dir: str, slot: int) -> bool:
    """Copy one backup slot's tracking files back over the live profile.
    Returns False if that slot is empty."""
    src = _slot_dir(profile_dir, slot)
    if not os.path.isdir(src):
        return False
    for rel in TRACKED:
        s = os.path.join(src, rel)
        if not os.path.exists(s):
            continue
        d = os.path.join(profile_dir, rel)
        if os.path.isdir(s):
            if os.path.isdir(d):
                shutil.rmtree(d)
            shutil.copytree(s, d)
        else:
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
    return True


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Back up / restore a face profile's tracking state")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backup")
    b.add_argument("--profile", help="one profile's folder (default: all profiles)")

    l = sub.add_parser("list")
    l.add_argument("--profile", required=True)

    r = sub.add_parser("restore")
    r.add_argument("--profile", required=True)
    r.add_argument("--slot", type=int, required=True)

    a = ap.parse_args()
    if a.cmd == "backup":
        if a.profile:
            print(backup_profile(a.profile))
        else:
            for p in backup_all_profiles():
                print(p)
    elif a.cmd == "list":
        for row in list_backups(a.profile):
            print(row)
    elif a.cmd == "restore":
        print("restored" if restore_backup(a.profile, a.slot) else "that slot is empty")
