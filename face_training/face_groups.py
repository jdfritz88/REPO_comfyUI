"""
Group the crops in one review section by HER FACE, not by the whole picture.

Why this exists (user, 2026-09-17): the review scanner used the finished-crop
duplicate check, which shrinks each whole picture to 96x96 grey and averages the
difference. On a body crop her face is 1.5-2% of the picture, so the wall, her
clothes and the floor decide the answer: measured on Susana's crops, pairs the
picture test grouped at 6.46 and 6.16 had faces 11.74 and 11.19 apart. It was
grouping frames where the ROOM had not changed, when the user is judging whether
SHE had changed.

So this uses the test the frame pruning already uses, and nothing else:

  1. find her face in the crop (the one closest to her identity)
  2. rotate and scale it onto a standard 112px square, so how she was framed
     stops mattering (insightface's own norm_crop, the same call pruning makes)
  3. read her head angle from the five landmarks - turned, nodded, tilted
  4. compare the aligned face, its eyes band and its mouth band separately, so a
     blink or a half-smile shows instead of being averaged away

Two crops are the same moment when the head angles are close AND all three bands
look alike. The slider moves all four numbers together, notch 4 being exactly
what the pruning step uses.

Nothing here writes to a picture. The aligned face lives in memory for as long as
the comparison takes. Finding her face costs about 0.4s per crop, so every crop's
landmarks are written into clean/_face_points.json and reused; a crop that is
rotated or blurred afterwards has a new size and date, and is measured again.

Runs in the OneTrainer venv (insightface, opencv).
"""

from __future__ import annotations

import json
import logging
import os

import numpy as np

from face_training import crop_guard as CG
from face_training import dedupe as DD
from face_training import video_frames as VF

log = logging.getLogger("face_training.face_groups")

POINTS_FILE = "_face_points.json"

# The slider, in whole notches. Notch 4 is the pruning step's own settings:
# DUP_LOOK_MIN 0.90, DUP_YAW/DUP_PITCH 0.08, DUP_ROLL 5 degrees. Lower is
# stricter (only a face that has barely moved), higher is looser.
NOTCH_MIN, NOTCH_MAX, NOTCH_DEFAULT = 1, 10, 4


def thresholds(notch: int) -> dict:
    """The four numbers this notch means."""
    n = max(NOTCH_MIN, min(NOTCH_MAX, int(notch)))
    scale = n / 4.0
    return {"look_min": round(0.96 - 0.02 * (n - 1), 3),
            "yaw": round(VF.DUP_YAW * scale, 3),
            "pitch": round(VF.DUP_PITCH * scale, 3),
            "roll": round(VF.DUP_ROLL * scale, 2)}


def describe(notch: int) -> str:
    t = thresholds(notch)
    return (f"her face must look at least {t['look_min']:.2f} alike, "
            f"and her head must not have turned more than {t['yaw']:.2f} "
            f"or leaned more than {t['roll']:.1f} degrees")


# --------------------------------------------------------------------------- #
# her face in each crop, measured once
# --------------------------------------------------------------------------- #
def _points_path(prof) -> str:
    return os.path.join(prof.dir, "clean", POINTS_FILE)


def load_points(prof) -> dict:
    try:
        with open(_points_path(prof), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_points(prof, points: dict):
    path = _points_path(prof)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(points, fh)
    os.replace(tmp, path)


def _stamp(path: str) -> str:
    st = os.stat(path)
    return f"{st.st_size}:{int(st.st_mtime)}"


def missing(prof, kind: str, folder: str, points: dict) -> list:
    """The crops in this section whose face has not been measured yet."""
    out = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        p = os.path.join(folder, name)
        row = points.get(f"{kind}/{name}")
        if not row or row.get("stamp") != _stamp(p):
            out.append((f"{kind}/{name}", p))
    return out


def measure(prof, jobs, points: dict, ident, on_step=None) -> dict:
    """Find her face in each crop and write down its five landmarks."""
    done = 0
    for rel, path in jobs:
        img = DD._read(path)
        row = {"stamp": _stamp(path), "kps": None}
        if img is not None:
            her, _others = CG.split_her(CG.faces_in(img), ident.mean)
            if her is not None and getattr(her, "kps", None) is not None:
                row["kps"] = [[float(x), float(y)] for x, y in her.kps]
                row["w"] = float(her.bbox[2] - her.bbox[0])
        points[rel] = row
        done += 1
        if on_step:
            on_step(done, len(jobs))
    return points


# --------------------------------------------------------------------------- #
# the grouping itself
# --------------------------------------------------------------------------- #
def _signature(path: str, kps):
    """Her face in this crop, ready to compare: angle, look, sharpness, size."""
    img = DD._read(path)
    if img is None or kps is None:
        return None
    aligned = VF._aligned(img, np.asarray(kps, np.float32))
    if aligned is None:
        return None
    return {"pose": VF._pose(kps), "look": VF._look(aligned),
            "sharp": VF._sharpness(aligned)}


def _same_face(a: dict, b: dict, t: dict) -> tuple[bool, float]:
    """Same head angle and same look, at this notch. -> (same, look score)"""
    look = VF._look_score(a["look"], b["look"])
    same = (abs(a["pose"][0] - b["pose"][0]) < t["yaw"]
            and abs(a["pose"][1] - b["pose"][1]) < t["pitch"]
            and abs(a["pose"][2] - b["pose"][2]) < t["roll"]
            and look >= t["look_min"])
    return same, look


def groups(folder: str, kind: str, points: dict, notch: int) -> list[dict]:
    """Groups of crops showing her at the same moment, each round its best one.

    Best means the biggest, sharpest view of her FACE - not the biggest picture,
    which is what the old picture-based grouping ranked by. Crops her face could
    not be found in are left out of every group rather than guessed at.
    """
    t = thresholds(notch)
    items = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        row = points.get(f"{kind}/{name}") or {}
        if not row.get("kps"):
            continue
        sig = _signature(os.path.join(folder, name), row["kps"])
        if sig is None:
            continue
        items.append({"name": name, "sig": sig, "rank": (row.get("w", 0.0), sig["sharp"])})
    items.sort(key=lambda i: i["rank"], reverse=True)

    out, used = [], set()
    for i, best in enumerate(items):
        if i in used:
            continue
        members, pairs = [], []
        for j in range(len(items)):
            if j == i or j in used:
                continue
            same, look = _same_face(best["sig"], items[j]["sig"], t)
            if same:
                members.append(j)
                pairs.append([best["name"], items[j]["name"], "same face, same angle",
                              round(look, 3)])
        if not members:
            continue
        used.add(i)
        used.update(members)
        out.append({"keep": best["name"],
                    "members": sorted([best["name"]] + [items[j]["name"] for j in members]),
                    "pairs": pairs})
    log.info("face grouping: %s at notch %d (%s) -> %d group(s) from %d measured crop(s)",
             kind, notch, describe(notch), len(out), len(items))
    return out
