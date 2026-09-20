"""
Make a finished crop contain only the person - or say plainly that it could not.

Why this exists (logs/face_seek_review_rotation_and_dataset_audit_2026-09-13.md
section 7): since 09-03 the README promised Seek "crops everyone else out", but
the croppers only trim sideways around faces the detector found, fall back to a
loose crop that may keep a neighbour, and keep the whole photo when no other face
was detected - and nothing ever looked at the finished crop. 73 of Susana's 237
body crops still held other people's faces.

This looks at the finished crop itself:
  1. detect every face in the crop and find her (closest to her own face's
     embedding from the source photo)
  2. no other face -> the crop is fine
  3. other faces -> shrink the crop rectangle, one edge at a time, until no other
     face box (plus a small clearance) is inside it, never cutting into her face
  4. check the shrunken crop again with the detector
  5. if that fails - an other face overlaps hers, the result would be too small,
     or the detector still sees someone - keep the original crop and report how
     many other faces remain, so the review page frames it in yellow

What it cannot do: see people whose faces are not visible (turned away, cut off,
out of focus). A face detector finds faces, not bodies. Those can only be caught
by the person reviewing.

Runs in the OneTrainer venv.
"""

from __future__ import annotations

import math

import numpy as np

from face_training.sort_photos import MIN_CROP_PX, _detect, _get_app

HER_MIN_SIM = 0.40     # a face in the crop this similar to her source face is her
CLEARANCE = 0.10       # other face boxes are pushed out with 10% of their size to spare


def faces_in(img):
    return _detect(_get_app(), img)


def split_her(faces, her_emb):
    """-> (her face or None, [other faces])"""
    if not faces:
        return None, []
    sims = [float(np.dot(f.normed_embedding, her_emb)) for f in faces]
    i = int(np.argmax(sims))
    if sims[i] < HER_MIN_SIM:
        return None, list(faces)
    return faces[i], [f for j, f in enumerate(faces) if j != i]


def _overlaps(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def exclude_others(crop, her_box, other_boxes):
    """Shrink the crop until no other face box is inside it, never cutting her box.
    -> the smaller image, or None if that is not possible."""
    h, w = crop.shape[:2]
    x1, y1, x2, y2 = 0, 0, w, h
    hx1, hy1, hx2, hy2 = (float(v) for v in her_box)
    boxes = []
    for ob in other_boxes:
        ox1, oy1, ox2, oy2 = (float(v) for v in ob)
        mx, my = (ox2 - ox1) * CLEARANCE, (oy2 - oy1) * CLEARANCE
        boxes.append((ox1 - mx, oy1 - my, ox2 + mx, oy2 + my))

    for _ in range(4 * len(boxes) + 1):
        inside = [b for b in boxes if _overlaps((x1, y1, x2, y2), b)]
        if not inside:
            break
        ox1, oy1, ox2, oy2 = inside[0]
        options = []
        if ox2 <= hx1:                      # that face is left of hers: move the left edge
            options.append((max(x1, math.ceil(ox2)), y1, x2, y2))
        if ox1 >= hx2:                      # right of hers
            options.append((x1, y1, min(x2, math.floor(ox1)), y2))
        if oy2 <= hy1:                      # above hers
            options.append((x1, max(y1, math.ceil(oy2)), x2, y2))
        if oy1 >= hy2:                      # below hers
            options.append((x1, y1, x2, min(y2, math.floor(oy1))))
        options = [r for r in options if r[2] > r[0] and r[3] > r[1]]
        if not options:
            return None                     # it overlaps her face in both directions
        x1, y1, x2, y2 = max(options, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
    else:
        return None

    if min(x2 - x1, y2 - y1) < MIN_CROP_PX:
        return None
    return crop[int(y1):int(y2), int(x1):int(x2)]


def only_her(crop, her_emb) -> dict:
    """-> {"img": final crop, "others": other faces still in it, "her": her face in
    the final crop or None, "refined": True if the crop was shrunk}"""
    faces = faces_in(crop)
    her, others = split_her(faces, her_emb)
    if not others:
        return {"img": crop, "others": 0, "her": her, "refined": False}
    if her is None:
        # cannot tell which face is hers, so nothing can be trimmed safely
        return {"img": crop, "others": len(others), "her": None, "refined": False}
    smaller = exclude_others(crop, her.bbox, [o.bbox for o in others])
    if smaller is not None:
        her2, others2 = split_her(faces_in(smaller), her_emb)
        if her2 is not None and not others2:
            return {"img": smaller, "others": 0, "her": her2, "refined": True}
    return {"img": crop, "others": len(others), "her": her, "refined": False}
