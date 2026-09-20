"""
Sort one folder of a person's photos into two training sets, locking onto ONE
person and cropping everyone else out.

  head       - close-up / portrait crops of the target person
  head_body  - the target person with as much of her body as the frame allows

Real phone folders are full of couple shots, group photos, and sideways
pictures. This module handles that:

  1. EXIF orientation is applied, so sideways phone photos are read upright.
  2. The target person is learned from the clean solo close-ups (one face,
     large in frame), as an averaged face embedding.
  3. Every photo - including the ones with other people - is searched for the
     face that matches her. If she is found, the image is cropped to her
     (tight for the head set, a wide vertical strip that excludes other
     people for the head_body set). If she is not confidently found, the photo
     is dropped.

Nothing in the source folder is modified. The two sets are written as folders
of cropped JPEGs plus a matching ``.txt`` caption for each.

Runs inside the OneTrainer venv (insightface, onnxruntime, opencv, numpy, PIL).
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageOps

# A face at least this tall relative to the image counts as a close-up shot.
HEAD_RATIO = 0.22
# A face ALSO qualifies as a close-up if it is simply big enough in real pixels,
# whatever the framing. Face-as-a-fraction-of-the-frame describes how the shot
# was composed, not how much detail there is to train on - so on its own it
# threw out a 500 px face for sitting in a large photo while admitting a 250 px
# face for sitting in a small one. Measured over the first ten years of
# Susana's library: the fraction rule kept 14 of her faces and rejected 58, of
# which 10 were 400 px or taller - sharper than six of the ones it kept.
# 400 px of face becomes roughly a 1000 px head crop once hair and neck are
# added, which is comfortable for training at either size.
HEAD_MIN_PX = 400

# Minimum detector confidence for a face to count.
MIN_DET_SCORE = 0.55

# Detector input. The square default is what insightface ships with; a frame
# further from square than DET_ASPECT_MIN gets a second pass at its own shape,
# because letterboxing into a square shrinks a tall crop until its face is too
# small to find. Measured on a real 499x1536 body strip: nothing at 640x640,
# a clean 304x417 face at 640x1600.
DET_BASE = 640
DET_ASPECT_MIN = 1.6
DET_LONG_SIDE_MAX = 2048

# Cosine similarity (ArcFace normed embeddings) for "this is the same person".
# Same person is typically 0.4-0.8, a different person 0.0-0.25.
MATCH_THRESHOLD = 0.32
# and her face must beat the next-best face in the frame by at least this much
MATCH_MARGIN = 0.10

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff",
              ".heic", ".heif")
INSIGHTFACE_ROOT = r"F:\Apps\freedom_system\REPO_comfyUI\models\insightface"

# tight head crop: how far to expand her face box (fractions of box size)
HEAD_EXPAND = dict(left=0.55, right=0.55, top=0.75, bottom=0.85)
# head_body strip: horizontal padding around her face width, each side
BODY_SIDE_PAD = 1.1
# cap on how tall:wide a body strip may be before it is trimmed from the top
MAX_STRIP_ASPECT = 2.6
# a finished crop whose short side is under this is too low-res to train on
MIN_CROP_PX = 256

# --------------------------------------------------------------------------- #
# caption thresholds
# --------------------------------------------------------------------------- #
# Cut points were read off the measured spread of a real trained subject (21
# head + 167 body crops), so each band actually holds photos rather than being
# a round number that never fires.
#
# Everything here is deliberately LEFT/RIGHT BLIND. Training runs with random
# horizontal flip, which mirrors the pixels but not the caption - so "facing
# left" would be wrong half the time. Turn and tilt are captioned by amount
# only, never direction.
FRAMING_BANDS = (          # face height / crop height -> framing word
    (0.55, "close-up portrait"),
    (0.30, "head and shoulders"),
    (0.17, "upper body"),
    (0.10, "three-quarter length"),
    (0.00, "full body"),
)
YAW_FRONTAL = 0.13         # |nose offset| / inter-ocular distance
YAW_PROFILE = 0.30
YAW_IMPLAUSIBLE = 1.0      # beyond this the landmarks are wrong; say nothing
ROLL_TILTED_DEG = 15.0
ROLL_IMPLAUSIBLE_DEG = 60.0
LUMA_DIM = 70.0            # mean brightness over her face box, 0-255
LUMA_BRIGHT = 125.0
LUMA_CONTRAST_STD = 62.0
SATURATION_MONO = 25.0     # mean HSV saturation below this = a greyscale source


@dataclass
class PhotoResult:
    path: str
    faces: int
    her_sim: float          # best cosine similarity to the reference, 0..1
    face_ratio: float       # her face height / image height (original)
    is_closeup: bool
    used_head: bool
    used_head_body: bool
    cropped_out_others: bool
    note: str = ""


@dataclass
class SortResult:
    head_dir: str
    head_body_dir: str
    head_files: list[str] = field(default_factory=list)
    head_body_files: list[str] = field(default_factory=list)
    per_photo: list[PhotoResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    reference_from: int = 0          # how many photos built the identity reference


_APP = None


def _get_app():
    global _APP
    if _APP is None:
        os.environ.setdefault("INSIGHTFACE_HOME", INSIGHTFACE_ROOT)
        from insightface.app import FaceAnalysis
        app = FaceAnalysis(
            name="buffalo_l",
            root=INSIGHTFACE_ROOT,
            providers=["CPUExecutionProvider"],
            allowed_modules=["detection", "recognition"],
        )
        app.prepare(ctx_id=-1, det_size=(640, 640))
        _APP = app
    return _APP


def _list_images(folder: str) -> list[str]:
    out = []
    for root, _dirs, files in os.walk(folder):
        for f in sorted(files):
            low = f.lower()
            if low.endswith(IMAGE_EXTS) and not low.endswith("-masklabel.png"):
                out.append(os.path.join(root, f))
    return out


# iPhones have written .heic by default since 2017, and PIL cannot open it
# unaided - those photos were being skipped in silence, counted neither as
# scanned nor as missed. Registering the opener teaches PIL the format, so
# they load through exactly the same path as everything else.
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    _HAS_HEIF = True
except Exception:                       # pragma: no cover - optional dependency
    _HAS_HEIF = False


def _load_bgr(path: str):
    """Open with PIL (honours EXIF rotation), return an OpenCV BGR array."""
    try:
        im = Image.open(path)
        im = ImageOps.exif_transpose(im).convert("RGB")
        return cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)
    except Exception:
        return None


def is_close_up(face_h_px: float, img_h: int) -> bool:
    """Worth a head crop? Either it fills a good share of the frame, or it is
    simply big enough in absolute pixels to hold up when cropped."""
    if img_h and (face_h_px / img_h) >= HEAD_RATIO:
        return True
    return face_h_px >= HEAD_MIN_PX


def _face_h(f) -> float:
    return max(0.0, float(f.bbox[3]) - float(f.bbox[1]))


def _cos(a, b) -> float:
    return float(np.dot(a, b))          # both are unit vectors (normed_embedding)


@dataclass
class _Scan:
    path: str
    img: np.ndarray
    faces: list                          # insightface Face objects, det_score-filtered


_ALT_APPS: dict = {}


def _alt_app(det_size):
    """A second detector shaped to a tall or wide frame, built once per size."""
    if det_size not in _ALT_APPS:
        os.environ.setdefault("INSIGHTFACE_HOME", INSIGHTFACE_ROOT)
        from insightface.app import FaceAnalysis
        a = FaceAnalysis(
            name="buffalo_l",
            root=INSIGHTFACE_ROOT,
            providers=["CPUExecutionProvider"],
            allowed_modules=["detection", "recognition"],
        )
        a.prepare(ctx_id=-1, det_size=det_size)
        _ALT_APPS[det_size] = a
    return _ALT_APPS[det_size]


def _aspect_det_size(h: int, w: int):
    """A detector input shaped like this frame, or None if it is near square.

    The detector letterboxes an image into its square input, so a tall strip is
    scaled down until it fits by height and the face shrinks with it - a 1:3
    crop loses two thirds of its scale before detection even starts, and a face
    that was 300 px across arrives at 100. Matching the input to the frame
    keeps the face close to its real size.
    """
    long_side, short_side = max(h, w), max(1, min(h, w))
    ratio = long_side / short_side
    if ratio < DET_ASPECT_MIN:
        return None
    other = min(DET_LONG_SIDE_MAX, int(round(DET_BASE * ratio / 32)) * 32)
    return (DET_BASE, other) if h >= w else (other, DET_BASE)


def _detect(app, img):
    faces = [f for f in app.get(img) if float(f.det_score) >= MIN_DET_SCORE]
    h, w = img.shape[:2]

    if not faces:
        # insightface's detector misses faces that fill the whole frame;
        # pad a border so the face becomes a smaller fraction and retry
        pad = int(max(h, w) * 0.4)
        padded = cv2.copyMakeBorder(img, pad, pad, pad, pad,
                                    cv2.BORDER_REPLICATE)
        for f in app.get(padded):
            if float(f.det_score) >= MIN_DET_SCORE:
                f.bbox = f.bbox - pad          # map back to the original frame
                faces.append(f)

    if not faces:
        # Still nothing, and the frame is far from square - the square input
        # shrank it too far to see. Retry at the frame's own shape. The body
        # strip crop produces exactly these, so this is not a rare path: a
        # photo lost here is silently never counted as hers.
        ds = _aspect_det_size(h, w)
        if ds is not None:
            for f in _alt_app(ds).get(img):
                if float(f.det_score) >= MIN_DET_SCORE:
                    faces.append(f)            # same image, so bbox needs no shift

    faces.sort(key=_face_h, reverse=True)
    return faces


def _scan_all(images: list[str]) -> list[_Scan]:
    app = _get_app()
    out = []
    for p in images:
        img = _load_bgr(p)
        if img is None:
            out.append(_Scan(p, None, []))
            continue
        out.append(_Scan(p, img, _detect(app, img)))
    return out


def _build_reference(scans: list[_Scan]) -> tuple[np.ndarray | None, int]:
    """Average embedding of the clean solo close-ups (1 face, big in frame)."""
    def solo_closeups():
        for s in scans:
            if s.img is None or len(s.faces) != 1:
                continue
            if _face_h(s.faces[0]) / s.img.shape[0] >= HEAD_RATIO:
                yield s.faces[0].normed_embedding

    embs = list(solo_closeups())
    if len(embs) < 3:
        # fall back: any single-face photo
        embs = [s.faces[0].normed_embedding for s in scans
                if s.img is not None and len(s.faces) == 1]
    if not embs:
        return None, 0

    ref = np.mean(embs, axis=0)
    ref = ref / (np.linalg.norm(ref) + 1e-9)

    # refine: keep only embeddings close to the first estimate, re-average
    keep = [e for e in embs if _cos(e, ref) >= 0.30]
    if len(keep) >= 3:
        ref = np.mean(keep, axis=0)
        ref = ref / (np.linalg.norm(ref) + 1e-9)
        return ref, len(keep)
    return ref, len(embs)


def _pick_her(faces, ref) -> tuple[int, float, float]:
    """Return (index of best-matching face, its sim, 2nd-best sim)."""
    sims = sorted(
        ((i, _cos(f.normed_embedding, ref)) for i, f in enumerate(faces)),
        key=lambda t: t[1], reverse=True)
    if not sims:
        return -1, 0.0, 0.0
    best_i, best = sims[0]
    second = sims[1][1] if len(sims) > 1 else 0.0
    return best_i, best, second


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _tight_head_crop(img, bbox, others=()):
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox
    bw, bh = x2 - x1, y2 - y1
    nx1 = int(x1 - bw * HEAD_EXPAND["left"])
    nx2 = int(x2 + bw * HEAD_EXPAND["right"])
    ny1 = int(y1 - bh * HEAD_EXPAND["top"])
    ny2 = int(y2 + bh * HEAD_EXPAND["bottom"])

    # pull the box in so it does not include another person's face
    hcx = (x1 + x2) / 2.0
    for (ox1, oy1, ox2, oy2) in others:
        ocx = (ox1 + ox2) / 2.0
        if ocx < hcx:
            nx1 = max(nx1, int(ox2) + 3)
        else:
            nx2 = min(nx2, int(ox1) - 3)
        # if the other face is above/below and overlaps our x-range, clip vertically
        if ox1 < x2 and ox2 > x1:
            ocy = (oy1 + oy2) / 2.0
            if ocy < (y1 + y2) / 2.0:
                ny1 = max(ny1, int(oy2) + 3)
            else:
                ny2 = min(ny2, int(oy1) - 3)

    # Keeping a neighbour out must never come at the cost of her own face. The
    # trims above pull the edges inward blind, so when another face overlaps
    # her box they can cross it and slice her in half - one eye and half a nose
    # in frame, which no detector will ever recognise as a face again. Her box
    # is the floor: the crop may include a neighbour, but it always holds all
    # of her.
    nx1 = min(nx1, int(x1))
    nx2 = max(nx2, int(x2))
    ny1 = min(ny1, int(y1))
    ny2 = max(ny2, int(y2))

    nx1 = _clamp(nx1, 0, w)
    nx2 = _clamp(nx2, 0, w)
    ny1 = _clamp(ny1, 0, h)
    ny2 = _clamp(ny2, 0, h)
    if nx2 - nx1 < bw * 0.9 or ny2 - ny1 < bh * 0.9:
        return None                       # trimming ate the face - unusable
    return img[ny1:ny2, nx1:nx2]


def _cap_height(ny1, ny2, width, face_y1, face_y2):
    """Bring a crop inside MAX_STRIP_ASPECT, trimming from whichever end can
    spare it and never cutting into her face.

    Two callers need this and both used to tower without it. The strip crop
    could only trim from the top, so a subject high in the frame defeated the
    cap entirely - one crop came out 1:10, of which 85% was pavement. And
    _loose_crop breaches it by construction: ten face-heights over 4.2
    face-widths is roughly 3:1 before clamping even starts.

    Dead space is usually above a standing person, so the top goes first; what
    the top cannot give up comes off the bottom.
    """
    target = int(width * MAX_STRIP_ASPECT)
    if ny2 - ny1 <= target:
        return ny1, ny2
    want = (ny2 - ny1) - target
    cut_top = min(want, max(0, int(face_y1) - ny1))
    ny1 += cut_top
    leftover = want - cut_top
    if leftover > 0:
        ny2 = max(int(face_y2) + 1, ny2 - leftover)
    return ny1, ny2


def _loose_crop(img, bbox, up=3.0, down=6.0, side=1.6):
    """A crop centred on her that always succeeds; may keep a sliver of a
    neighbour rather than lose the photo."""
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox
    bw, bh = x2 - x1, y2 - y1
    nx1 = _clamp(int(x1 - bw * side), 0, w)
    nx2 = _clamp(int(x2 + bw * side), 0, w)
    ny1 = _clamp(int(y1 - bh * up), 0, h)
    ny2 = _clamp(int(y2 + bh * down), 0, h)
    ny1, ny2 = _cap_height(ny1, ny2, nx2 - nx1, y1, y2)
    return img[ny1:ny2, nx1:nx2]


def _body_strip_crop(img, her_bbox, other_bboxes):
    """Vertical strip containing her, trimmed horizontally to keep other people
    out where possible; full image height."""
    h, w = img.shape[:2]
    x1, _y1, x2, _y2 = her_bbox
    bw = x2 - x1
    left = x1 - bw * BODY_SIDE_PAD
    right = x2 + bw * BODY_SIDE_PAD

    for (ox1, _oy1, ox2, _oy2) in other_bboxes:
        ocx = (ox1 + ox2) / 2.0
        hcx = (x1 + x2) / 2.0
        if ocx < hcx:                       # other person to her left
            left = max(left, ox2 + 4)
        else:                               # other person to her right
            right = min(right, ox1 - 4)

    nx1 = _clamp(int(left), 0, w)
    nx2 = _clamp(int(right), 0, w)
    if nx2 - nx1 < bw * 1.2:                # trimming collapsed the strip:
        hc = _tight_head_crop(img, her_bbox, other_bboxes)
        if hc is not None and min(hc.shape[:2]) >= 128:
            return hc
        return _loose_crop(img, her_bbox)   # last resort: keep her, maybe a sliver of a neighbour

    ny1, ny2 = _cap_height(0, h, nx2 - nx1, her_bbox[1], her_bbox[3])
    return img[ny1:ny2, nx1:nx2]


def _framing(face_h: float, crop_h: int) -> str:
    ratio = face_h / max(1, crop_h)
    for floor, word in FRAMING_BANDS:
        if ratio >= floor:
            return word
    return FRAMING_BANDS[-1][1]


def _head_angle_tags(kps) -> list[str]:
    """Turn and tilt, from the five landmarks detection already returned.

    Detection gives eyes, nose and mouth corners but no pose model, so the
    angles are derived: how far the nose sits off the midpoint between the
    eyes (turn), and the slope of the eye line (tilt). Both are approximate,
    so the bands are wide and an implausible reading is dropped rather than
    guessed at.

    Seek re-reads faces from its scan cache, which keeps boxes but not
    landmarks. With no landmarks there is nothing to measure, and the photo is
    captioned on framing and lighting alone rather than on a guess.
    """
    if kps is None or len(kps) < 3:
        return []
    k = np.asarray(kps, dtype=float)
    left_eye, right_eye, nose = k[0], k[1], k[2]
    inter_ocular = float(np.linalg.norm(right_eye - left_eye))
    if inter_ocular <= 0:
        return []

    tags = []
    yaw = abs(float((nose[0] - (left_eye[0] + right_eye[0]) / 2.0) / inter_ocular))
    if yaw <= YAW_IMPLAUSIBLE:
        if yaw < YAW_FRONTAL:
            tags.append("facing forward")
        elif yaw < YAW_PROFILE:
            tags.append("three-quarter view")
        else:
            tags.append("profile view")
    roll = abs(float(np.degrees(np.arctan2(right_eye[1] - left_eye[1],
                                           right_eye[0] - left_eye[0]))))
    if ROLL_TILTED_DEG <= roll < ROLL_IMPLAUSIBLE_DEG:
        tags.append("head tilted")
    return tags


def _light_tags(img, bbox) -> list[str]:
    x1, y1, x2, y2 = (int(v) for v in bbox)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(img.shape[1], x2), min(img.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return []
    region = img[y1:y2, x1:x2]
    grey = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

    tags = []
    mean = float(grey.mean())
    if mean < LUMA_DIM:
        tags.append("dim lighting")
    elif mean > LUMA_BRIGHT:
        tags.append("bright lighting")
    if float(grey.std()) >= LUMA_CONTRAST_STD:
        tags.append("high contrast lighting")
    if float(cv2.cvtColor(region, cv2.COLOR_BGR2HSV)[:, :, 1].mean()) < SATURATION_MONO:
        tags.append("black and white photo")
    return tags


def build_caption(base: str, img, bbox, kps, crop_h: int) -> str:
    """`base` names the person; the tags name everything that varies.

    Writing one fixed caption on every photo leaves the trigger word carrying
    the entire dataset - framing, angle, lighting and all - and the only thing
    the model can learn from a word that means everything is the average of it.
    Naming what differs gives those parts their own words to attach to, so the
    trigger is left holding the person.

    `kps` may be None: callers working from cached boxes have no landmarks, and
    those photos are captioned on framing and lighting alone.
    """
    parts = [base.strip().rstrip(","),
             _framing(float(bbox[3]) - float(bbox[1]), crop_h)]
    parts.extend(_head_angle_tags(kps))
    parts.extend(_light_tags(img, bbox))
    return ", ".join(p for p in parts if p)


def _caption_names(txt_path: str, base: str) -> bool:
    """Does this caption still start with the person-word it should?

    Only the base is compared - the measured part (framing, angle, lighting)
    differs per photo by design and must not trigger a rewrite.
    """
    try:
        with open(txt_path, encoding="utf-8") as fh:
            return fh.read().strip().startswith(base)
    except OSError:
        return False


def recaption_folder(folder: str, base: str,
                     missing_only: bool = False, ident=None) -> tuple[int, int]:
    """Write a measured .txt beside each crop in `folder`.

    For sets written before captions were measured, and as the safety net for
    any crop that reached a clean folder without one. The photo each crop came
    from is long gone, so the subject is re-detected in the crop itself - the
    largest face, others having already been cropped away. A crop with no
    detectable face is left alone and counted, because a face set has no use
    for a photo the detector cannot find a face in.

    `missing_only` still rewrites a caption whose person-word no longer matches
    `base`. A caption naming one trigger while the shelf emits another is the
    worst kind of wrong here: training reads the caption, generation uses the
    shelf, and nothing errors - the word simply never means anything. That is
    exactly what changing the trigger prefix would otherwise have caused for
    every set captioned before the change.
    """
    app = _get_app()
    written = skipped = 0
    for path in sorted(_list_images(folder)):
        txt = os.path.splitext(path)[0] + ".txt"
        if missing_only and os.path.isfile(txt) and _caption_names(txt, base):
            continue
        img = _load_bgr(path)
        if img is None:
            skipped += 1
            continue
        faces = app.get(img)
        if not faces:
            skipped += 1
            continue
        # "The largest face" was only safe while every crop held one person,
        # and 73 of Susana's did not. With the person's identity, measure the
        # face that is actually hers.
        if ident is not None:
            her = max(faces, key=lambda f: ident.match(f))
        else:
            her = max(faces, key=_face_h)
        caption = build_caption(base, img, her.bbox, getattr(her, "kps", None),
                                img.shape[0])
        with open(txt, "w", encoding="utf-8") as fh:
            fh.write(caption + "\n")
        written += 1
    return written, skipped


def _save_jpeg(img, dst, caption):
    ok = cv2.imwrite(dst, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:                              # non-ASCII path
        cv2.imencode(".jpg", img)[1].tofile(dst)
    with open(os.path.splitext(dst)[0] + ".txt", "w", encoding="utf-8") as fh:
        fh.write(caption.strip() + "\n")


def sort_folder(source_folder: str, work_dir: str,
                head_caption: str, head_body_caption: str) -> SortResult:
    if not os.path.isdir(source_folder):
        raise FileNotFoundError(f"source folder not found: {source_folder}")

    head_dir = os.path.join(work_dir, "head")
    head_body_dir = os.path.join(work_dir, "head_body")
    for d in (head_dir, head_body_dir):
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)

    result = SortResult(head_dir=head_dir, head_body_dir=head_body_dir)

    images = _list_images(source_folder)
    if not images:
        raise ValueError(f"no images found in {source_folder}")

    scans = _scan_all(images)
    ref, ref_n = _build_reference(scans)
    result.reference_from = ref_n
    if ref is None:
        raise ValueError(
            "could not find any clear solo face photo to learn the person from. "
            "Add a few tight, single-person face shots to the folder.")
    if ref_n < 3:
        result.warnings.append(
            f"the person was learned from only {ref_n} clean photo(s); identity "
            f"matching on the rest may be shaky.")

    for i, s in enumerate(scans):
        name = os.path.basename(s.path)
        if s.img is None:
            result.per_photo.append(PhotoResult(s.path, 0, 0.0, 0.0, False, False, False, False, "unreadable"))
            result.warnings.append(f"skipped (unreadable): {name}")
            continue
        if not s.faces:
            result.per_photo.append(PhotoResult(s.path, 0, 0.0, 0.0, False, False, False, False, "no face"))
            result.warnings.append(f"no face detected, dropped: {name}")
            continue

        idx, sim, second = _pick_her(s.faces, ref)
        h = s.img.shape[0]
        her = s.faces[idx]
        ratio = _face_h(her) / h
        others = [f.bbox for j, f in enumerate(s.faces) if j != idx]
        multi = len(s.faces) > 1

        pr = PhotoResult(s.path, len(s.faces), round(sim, 3), round(ratio, 3),
                         is_close_up(_face_h(her), h), False, False, False)

        # drop if she is not found, or if the match is marginal AND another
        # face is nearly as good a match (ambiguous who is who)
        ambiguous = multi and sim < 0.45 and (sim - second) < MATCH_MARGIN
        if sim < MATCH_THRESHOLD or ambiguous:
            pr.note = f"not confidently her (sim {sim:.2f})"
            result.per_photo.append(pr)
            result.warnings.append(f"dropped, not confidently the target person: {name}")
            continue

        stem = f"{i:04d}"

        def _big_enough(c):
            return c is not None and c.size and min(c.shape[:2]) >= MIN_CROP_PX

        # head set: a tight crop, only from close-up shots
        if pr.is_closeup:
            crop = _tight_head_crop(s.img, her.bbox, others)
            if _big_enough(crop):
                dst = os.path.join(head_dir, stem + ".jpg")
                _save_jpeg(crop, dst,
                           build_caption(head_caption, s.img, her.bbox,
                                         getattr(her, "kps", None), crop.shape[0]))
                result.head_files.append(dst)
                pr.used_head = True

        # head_body set: whole image if she is alone, else a strip without others
        if multi:
            crop = _body_strip_crop(s.img, her.bbox, others)
            pr.cropped_out_others = True
        else:
            crop = s.img
        if _big_enough(crop):
            dst = os.path.join(head_body_dir, stem + ".jpg")
            _save_jpeg(crop, dst,
                       build_caption(head_body_caption, s.img, her.bbox,
                                     getattr(her, "kps", None), crop.shape[0]))
            result.head_body_files.append(dst)
            pr.used_head_body = True

        if not pr.used_head and not pr.used_head_body:
            pr.note = pr.note or "her crop was too small / low-res to use"
            result.warnings.append(f"dropped, crop too small: {name}")

        result.per_photo.append(pr)

    if len(result.head_files) < 8:
        result.warnings.append(
            f"only {len(result.head_files)} close-up crops - the face-only LoRAs "
            f"may be weak. 15+ tight face shots is a good target.")
    if len(result.head_body_files) < 10:
        result.warnings.append(
            f"only {len(result.head_body_files)} body crops - add more photos.")

    return result


if __name__ == "__main__":
    import argparse
    import json

    # Same convention as the pipeline: profiles.py owns the prefix, so this
    # placeholder cannot go stale the way "ohwx woman" did.
    from face_training.profiles import trigger_for_slug

    _placeholder_caption = trigger_for_slug("person") + " woman"

    ap = argparse.ArgumentParser(description="Identity-locked photo sort")
    ap.add_argument("source", nargs="?")
    ap.add_argument("work_dir", nargs="?")
    # These name the person only. Framing, head angle and lighting are measured
    # per photo and appended, so they must not be spelled out here.
    ap.add_argument("--head-caption", default=_placeholder_caption)
    ap.add_argument("--head-body-caption", default=_placeholder_caption)
    ap.add_argument("--recaption", metavar="FOLDER",
                    help="rewrite captions for crops already sorted into FOLDER, "
                         "then exit")
    a = ap.parse_args()

    if a.recaption:
        written, skipped = recaption_folder(a.recaption, a.head_caption)
        print(json.dumps({"recaptioned": written, "skipped_no_face": skipped},
                         indent=2))
        raise SystemExit(0)

    if not a.source or not a.work_dir:
        ap.error("source and work_dir are required unless --recaption is used")

    r = sort_folder(a.source, a.work_dir, a.head_caption, a.head_body_caption)
    print(json.dumps({
        "reference_from": r.reference_from,
        "head_count": len(r.head_files),
        "head_body_count": len(r.head_body_files),
        "warnings": r.warnings,
        "per_photo": [vars(p) for p in r.per_photo],
    }, indent=2))
