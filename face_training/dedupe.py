"""
Find duplicate training crops in one folder, and choose which copy to keep.

The earlier duplicate checks all run upstream and each only sees its own slice:
near-identical frames inside ONE video, the SAME file content scanned twice, a
photo the search stage already handled. None of them sees the finished crops,
and that is where Susana's 62 duplicates were: the same picture cut twice on two
runs (saved under a second name), or the same photo re-saved as a slightly
different file. This check runs on the finished crops, after processing and
before review.

What counts as a duplicate (user, 2026-09-13): the exact same picture, AND a
near-identical copy - the one-pixel-different re-cuts. A different crop of the
same photo (wider, tighter) is NOT a duplicate; it shows a different framing.

Measured on Susana's set before it was wiped: the one-pixel pairs differed by a
mean of 0.9-4.3 grey levels; different crops of the same photo by 50 or more.
NEAR_DIFF_MAX sits between them.

Which copy stays (user, 2026-09-13): the larger, sharper one - more pixels
first, then a higher Laplacian variance (a standard focus measure).

Runs in the OneTrainer venv (opencv, numpy). Read-only: it reports groups; the
caller decides what happens to the copies that are not kept.
"""

from __future__ import annotations

import hashlib
import os
import re

import cv2
import numpy as np

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

COMPARE_SIZE = 96          # both images resized to this square, greyscale
NEAR_DIFF_MAX = 6.0        # mean absolute grey-level difference at COMPARE_SIZE
ASPECT_TOLERANCE = 0.03    # a different aspect ratio means a different framing

# Two frames out of the SAME video are a looser case than two crops: the camera
# and everyone in shot keep moving, and sensor noise never repeats, so pictures
# that a person calls identical never measure as close as a re-cut of one photo.
# Measured 2026-09-17 on Susana's review pile: a run of frames she calls the same
# picture sat at 3.8-9.0, while the next real change in the same video was 13.2
# and 20.4. FRAME_DIFF_MAX sits between them, and only ever applies to two frames
# pulled from one video (user, 2026-09-17).
FRAME_DIFF_MAX = 10.0
FRAME_RE = re.compile(r"^(?P<video>.+)_frame\d+$")


def _read(path: str):
    data = np.fromfile(path, dtype=np.uint8)      # handles non-ASCII paths
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sharpness(grey: np.ndarray) -> float:
    return float(cv2.Laplacian(grey, cv2.CV_64F).var())


class _Item:
    __slots__ = ("path", "w", "h", "sha", "small", "sharp")

    def __init__(self, path: str, img: np.ndarray):
        self.path = path
        self.h, self.w = img.shape[:2]
        self.sha = _sha256(path)
        grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        self.sharp = sharpness(grey)
        self.small = cv2.resize(grey, (COMPARE_SIZE, COMPARE_SIZE),
                                interpolation=cv2.INTER_AREA).astype(np.int16)

    @property
    def aspect(self) -> float:
        return self.w / max(1, self.h)

    def rank_key(self):
        return (self.w * self.h, self.sharp)


def _read_folder(folder: str) -> list[_Item]:
    """Every picture in one folder, measured once."""
    out: list[_Item] = []
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(IMAGE_EXTS) or name.lower().endswith("-masklabel.png"):
            continue
        p = os.path.join(folder, name)
        img = _read(p)
        if img is None:
            continue
        out.append(_Item(p, img))
    return out


def _video_of(path: str) -> str:
    """The video a pulled frame came from ("IMG_0677" for IMG_0677_frame025065.jpg),
    or "" for anything that is not a pulled frame."""
    m = FRAME_RE.match(os.path.splitext(os.path.basename(path))[0])
    return m.group("video") if m else ""


def _same_picture(a: _Item, b: _Item, near_max=None, frame_max=None) -> tuple[bool, str, float]:
    """Are these the same picture? near_max/frame_max override the usual lines,
    which is what the review page's slider does (user, 2026-09-17)."""
    if a.sha == b.sha:
        return True, "identical file", 0.0
    if abs(a.aspect - b.aspect) > ASPECT_TOLERANCE * max(a.aspect, b.aspect):
        return False, "", -1.0
    diff = float(np.abs(a.small - b.small).mean())
    va, vb = _video_of(a.path), _video_of(b.path)
    if va and va == vb:
        return (diff <= (FRAME_DIFF_MAX if frame_max is None else frame_max),
                "near-identical frames of one video", diff)
    return diff <= (NEAR_DIFF_MAX if near_max is None else near_max), "near-identical", diff


def groups_around_best(folder: str, near_max=None, frame_max=None) -> list[dict]:
    """Small groups for a person to look at, each built round its best picture.

    find_duplicates below groups by chaining: A matches B, B matches C, so all
    three are one picture. That is right for throwing away copies of one photo,
    but it is wrong for a person working through a run of video frames - at a
    loose setting one group swallowed 161 of Susana's crops (2026-09-17), when
    what was wanted was three to five at a time.

    Here the best picture of what is left - most pixels, then sharpest - takes
    the group, and only the pictures that match THAT picture join it. The next
    best of whatever remains starts the next group. Nothing is deleted; this
    reports what it found.
    """
    items = _read_folder(folder)
    items.sort(key=lambda i: i.rank_key(), reverse=True)
    out, used = [], set()
    for i, best in enumerate(items):
        if i in used:
            continue
        members, pairs = [], []
        for j in range(len(items)):
            if j == i or j in used:
                continue
            same, reason, diff = _same_picture(best, items[j], near_max, frame_max)
            if same:
                members.append(items[j])
                pairs.append((best.path, items[j].path, reason, round(diff, 2)))
        if not members:
            continue
        used.add(i)
        used.update(items.index(m) for m in members)
        out.append({"keep": best.path, "remove": sorted(m.path for m in members),
                    "pairs": pairs})
    return out


def find_duplicates(folder: str, near_max=None, frame_max=None) -> list[dict]:
    """-> [{"keep": path, "remove": [paths], "pairs": [(path, path, reason, diff)]}]

    Groups are transitive: if A matches B and B matches C, all three are one
    picture and exactly one of them is kept.
    """
    items = _read_folder(folder)

    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    pairs = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            same, reason, diff = _same_picture(items[i], items[j], near_max, frame_max)
            if same:
                pairs.append((items[i].path, items[j].path, reason, round(diff, 2)))
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[rj] = ri

    groups: dict[int, list[_Item]] = {}
    for i, it in enumerate(items):
        groups.setdefault(find(i), []).append(it)

    out = []
    for members in groups.values():
        if len(members) < 2:
            continue
        keep = max(members, key=lambda m: m.rank_key())
        paths = {m.path for m in members}
        out.append({
            "keep": keep.path,
            "remove": sorted(m.path for m in members if m is not keep),
            "pairs": [p for p in pairs if p[0] in paths],
        })
    return out
