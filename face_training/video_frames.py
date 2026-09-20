"""
Video frames for Face Seek - chosen in memory, saved only when she is in them.

Seek used to save every kept frame of every video as a .jpg in
<profile>/video_frames, whether or not the person was in it: 14,526 files
(2.67 GB) for one library before a single face had been compared. Now no frame
is written during the scan, and a frame is saved only once Seek has matched her
in it (user, 2026-09-14). Two passes, combined (user, 2026-09-15). The user's
rules for both: look at EVERY frame of a video, seek the best frame, accept no
duplicates or near-duplicates, but seek every different angle and expression
if the picture is sharp; and a face that does not look like her is not her.

1. scan_frames - every video, at scan time. The user's original method
   (chosen 2026-09-07), except that nothing is written and every frame is
   looked at (it used to look 2 times a second):
     - every frame: a big grayscale-histogram correlation drop from the frame
       before is a scene cut; the sharpest frame (Laplacian variance) of each
       scene is kept. Both are measured on a copy shrunk to METRIC_WIDTH, which
       keeps looking at every frame affordable.
     - near-duplicate check across the video's kept frames: a DCT perceptual
       hash first (PHASH_HAMMING_MAX), then, if a face is present, ArcFace
       similarity (EMBED_SIM_MAX). Either match drops the frame. This is the
       "video frame near-dupes" check the user said to keep where it is
       (2026-09-13).
   The kept frames' faces go into the scan cache; the search compares them.

2. her_frames - only for a video the search has matched her in. One sharpest
   frame per scene cannot hold every angle and expression, so that video is
   read again, every frame:
     - her face is picked by the caller with Seek's own match rule; an unsure
       call is not her
     - faces are found again when her face changes (looked at where it was
       last found, it no longer looks the same: look score < DUP_LOOK_MIN), at
       a scene cut, and at least every FORCE_DETECT_S seconds (someone walking
       in is caught). Finding faces costs ~2 s per frame on this CPU (measured
       2026-09-15), which is why it is not run on frames where nothing changed
       and why this pass runs only on videos she is in. On an unchanged frame
       her face's sharpness is still measured, so the sharpest frame of each
       angle and expression is the one kept.
     - her face must be sharp: Laplacian variance of her face aligned to 112 px
       >= MIN_HER_SHARPNESS. Measured 2026-09-15 on 33 frames of her in
       IMG_3660.MP4, side by side: faces at 257+ were crisp, 202 slightly soft
       but detailed, 137 and below visibly blurred, 89 and below a smear.
     - a frame is a duplicate only if her face has a twin in a frame already
       kept: same head angle (yaw/pitch change < DUP_YAW/DUP_PITCH, roll change
       < DUP_ROLL degrees, from the five landmarks) and same look (the aligned
       face, its eyes band and its mouth band each correlate >= DUP_LOOK_MIN).
       Anything else is a different angle or expression and is kept; a sharper
       twin replaces the kept one.
   Twin thresholds from measuring 147 same-face pairs of consecutive frames of
   two real videos side by side (2026-09-15): look >= 0.91 was the same pose
   and expression; at 0.87 a smile had opened; at 0.86 and 0.77 the head had
   turned (yaw change 0.24). ArcFace alone cannot make this call: it is built to
   stay the same across angles and expressions.

Frames are identified by their decode index; read_frames returns them later.

Runs in the OneTrainer venv (opencv, numpy, insightface).
"""

from __future__ import annotations

import json
import logging
import math
import os
from collections import deque

import cv2
import numpy as np
from insightface.utils import face_align

from face_training.sort_photos import _detect, _get_app

log = logging.getLogger("face_training.video_frames")

VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm")

# both passes
METRIC_WIDTH = 480              # scene-cut and sharpness measured on a copy this wide
SCENE_CUT_DROP = 0.45           # histogram correlation drop that counts as a cut
CUT_COMPARE_S = 0.5             # a frame is compared with the frame this long before it.
# The original method looked 2 times a second and judged a cut across that gap.
# Looking at every frame, the frame just before is nearly always the same
# picture, so no cut was ever found (tested 2026-09-15: IMG_3567.MOV came out
# as 6 scenes where the committed method keeps 33 frames).

# pass 1 - scan (the original method)
PHASH_HAMMING_MAX = 8           # <=8 of 64 bits different = near-duplicate
EMBED_SIM_MAX = 0.93            # >=0.93 cosine on a face = near-duplicate

# pass 2 - her frames in a video she is in
SEGMENT_STEP_S = 0.5            # how often faces are looked for while finding her stretches
                                # (the original 2-a-second rate; at 2 s she was missed
                                # entirely in IMG_3660.MP4, where she is on screen for
                                # about a second)
MIN_HER_SHARPNESS = 200.0       # her face aligned to 112 px, Laplacian variance
DUP_LOOK_MIN = 0.90             # aligned face, eyes band and mouth band all at least this alike
DUP_YAW = 0.08                  # head turn change (nose offset / eye distance)
DUP_PITCH = 0.08                # nod change (nose height / eye-to-mouth distance)
DUP_ROLL = 5.0                  # sideways lean change, degrees


def _sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _phash(gray: np.ndarray) -> np.ndarray:
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    d = cv2.dct(small)
    block = d[:8, :8]
    med = np.median(block)
    return (block > med).flatten()


def _hamming(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.count_nonzero(a != b))


def _hist(gray: np.ndarray) -> np.ndarray:
    h = cv2.calcHist([gray], [0], None, [64], [0, 256])
    cv2.normalize(h, h)
    return h


def _small_gray(frame: np.ndarray) -> np.ndarray:
    h, w = frame.shape[:2]
    if w > METRIC_WIDTH:
        frame = cv2.resize(frame, (METRIC_WIDTH, max(1, round(h * METRIC_WIDTH / w))),
                           interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def _open(video_path: str):
    """-> (capture, backend, rotation_tag, error). Turns phone video upright.

    Phones film portrait video as landscape pixels plus a rotation tag. OpenCV
    leaves that tag unapplied unless asked (ORIENTATION_AUTO), so every portrait
    phone video used to come out sideways. Every reader here opens through this,
    so a frame read back is the frame that was chosen."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None, "", 0, "could not open video"
    backend = cap.getBackendName()
    cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
    rotation_tag = int(round(cap.get(cv2.CAP_PROP_ORIENTATION_META))) % 360
    if rotation_tag and not bool(cap.get(cv2.CAP_PROP_ORIENTATION_AUTO)):
        cap.release()
        return None, backend, rotation_tag, (
            f"video has a {rotation_tag}-degree rotation tag but the {backend} "
            f"backend would not rotate its frames - not using sideways frames")
    return cap, backend, rotation_tag, ""


# --------------------------------------------------------------------------- #
# pass 1: scan
# --------------------------------------------------------------------------- #
def scan_frames(video_path: str, stop_check=lambda: False) -> dict:
    """
    The original selection, every frame looked at, in memory. Returns
    {"frames": [...], "frames_looked_at", "scenes", "duplicates_dropped",
     "no_face", "stopped", "error"?}.
    Only frames with a face are returned - the cache has no use for the rest.

    stop_check is asked on every frame: a 49-minute video is ~88,000 frames, and
    a Stop used to sit unanswered until the whole video was done (user, when
    Stop looked broken mid-video, 2026-09-15). A stopped video reports
    "stopped": True so the caller does not mark it finished.
    """
    empty = {"frames": [], "frames_looked_at": 0, "scenes": 0,
             "duplicates_dropped": 0, "no_face": 0, "stopped": False}
    cap, backend, rotation_tag, err = _open(video_path)
    if cap is None:
        log.error("%s: %s", video_path, err)
        return dict(empty, error=err)

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    hists = deque(maxlen=max(1, round(fps * CUT_COMPARE_S)))
    scene_best = None             # (sharpness, decode index, frame, small gray)
    scenes_out: list[tuple] = []
    looked = 0
    idx = 0
    stopped = False
    while cap.grab():
        if stop_check():
            stopped = True
            break
        ok, frame = cap.retrieve()
        if ok:
            if looked == 0:
                log.info("video %s: backend=%s fps=%.2f rotation_tag=%d frame=%dx%d",
                         video_path, backend, fps, rotation_tag, frame.shape[1], frame.shape[0])
            looked += 1
            gray = _small_gray(frame)
            hist = _hist(gray)
            cut = (len(hists) == hists.maxlen and
                   cv2.compareHist(hists[0], hist, cv2.HISTCMP_CORREL) < 1.0 - SCENE_CUT_DROP)
            if cut:
                hists.clear()         # the new scene is judged from its own start
                if scene_best is not None:
                    scenes_out.append(scene_best)
                    scene_best = None
            hists.append(hist)
            sharp = _sharpness(gray)
            if scene_best is None or sharp > scene_best[0]:
                scene_best = (sharp, idx, frame.copy(), gray)
        idx += 1
    if scene_best is not None and not stopped:
        scenes_out.append(scene_best)
    cap.release()
    if stopped:
        log.info("video %s: stop requested after %d frames - not recorded, will be "
                 "read again on resume", video_path, looked)
        return dict(empty, frames_looked_at=looked, stopped=True)

    app = _get_app()
    kept_phash: list[np.ndarray] = []
    kept_embed: list[np.ndarray] = []
    out = dict(empty, frames_looked_at=looked, scenes=len(scenes_out))
    for _sharp, fidx, bgr, gray in scenes_out:
        if stop_check():
            return dict(out, stopped=True, frames=[])
        ph = _phash(gray)
        if any(_hamming(ph, k) <= PHASH_HAMMING_MAX for k in kept_phash):
            out["duplicates_dropped"] += 1
            continue
        faces = _detect(app, bgr)
        emb = faces[0].normed_embedding if faces else None
        if emb is not None and any(float(np.dot(emb, k)) >= EMBED_SIM_MAX for k in kept_embed):
            out["duplicates_dropped"] += 1
            continue
        kept_phash.append(ph)
        if emb is None:
            out["no_face"] += 1
            continue
        kept_embed.append(emb)
        out["frames"].append({"idx": fidx, "faces": faces, "shape": bgr.shape})

    log.info("video %s: %d frames looked at, %d scenes, %d frames with faces recorded, "
             "%d near-duplicates dropped, %d without a face - nothing saved to disk",
             video_path, looked, out["scenes"], len(out["frames"]),
             out["duplicates_dropped"], out["no_face"])
    return out


# --------------------------------------------------------------------------- #
# pass 2: her frames
# --------------------------------------------------------------------------- #
def _pose(kps) -> tuple[float, float, float]:
    """(yaw, pitch, roll) from the five landmarks: eyes, nose, mouth corners."""
    le, re, nose, lm, rm = [np.asarray(p, float) for p in kps]
    roll = math.degrees(math.atan2(re[1] - le[1], re[0] - le[0]))
    c, s = math.cos(math.radians(-roll)), math.sin(math.radians(-roll))

    def rot(p):
        return np.array([c * p[0] - s * p[1], s * p[0] + c * p[1]])

    le, re, nose, lm, rm = map(rot, (le, re, nose, lm, rm))
    eye_mid, mouth_mid = (le + re) / 2, (lm + rm) / 2
    yaw = (nose[0] - eye_mid[0]) / max(1e-6, float(np.linalg.norm(re - le)))
    pitch = (nose[1] - eye_mid[1]) / max(1e-6, mouth_mid[1] - eye_mid[1])
    return yaw, pitch, roll


def _z(a: np.ndarray) -> np.ndarray:
    a = a - a.mean()
    sd = a.std()
    return a / sd if sd > 1e-6 else a


def _aligned(frame: np.ndarray, kps) -> np.ndarray | None:
    """Her face aligned by its five landmarks to 112 px grayscale, or None."""
    if kps is None:
        return None
    k = np.asarray(kps, np.float32)
    h, w = frame.shape[:2]
    if k.shape != (5, 2) or (k < 0).any() or (k[:, 0] >= w).any() or (k[:, 1] >= h).any():
        return None
    return cv2.cvtColor(face_align.norm_crop(frame, k, 112), cv2.COLOR_BGR2GRAY)


def _look(aligned: np.ndarray | None) -> dict | None:
    """The aligned face split for comparison: whole face, eyes band, mouth band."""
    if aligned is None:
        return None
    g = aligned.astype(np.float32)
    return {"face": _z(cv2.resize(g, (56, 56))), "eyes": _z(g[30:62, 10:102]),
            "mouth": _z(g[68:108, 24:88])}


def _look_score(a: dict | None, b: dict | None) -> float:
    if a is None or b is None:
        return -1.0
    return min(float((a[k] * b[k]).mean()) for k in ("face", "eyes", "mouth"))


def _twins(a: dict, b: dict) -> bool:
    """Her face at the same angle, with the same look."""
    if a["pose"] is None or b["pose"] is None:
        return False
    return (abs(a["pose"][0] - b["pose"][0]) < DUP_YAW
            and abs(a["pose"][1] - b["pose"][1]) < DUP_PITCH
            and abs(a["pose"][2] - b["pose"][2]) < DUP_ROLL
            and _look_score(a["look"], b["look"]) >= DUP_LOOK_MIN)


MANIFEST = "_frames.json"       # written beside a video's pulled frames


def her_segments(video_path: str, pick_her, stop_check=lambda: False,
                 start_at: int = 0) -> dict:
    """
    Where she is on screen in one video.

    Faces are found every SEGMENT_STEP_S seconds (they cost ~2 s a frame, so
    not on every frame). pick_her(list of face embeddings) -> (index of her
    face or -1, unsure). A run of checks that all found her becomes one stretch,
    reaching half a step past the checks at each end. Checks the caller called
    unsure are counted, so a video that is never clearly her but was unsure
    somewhere can be set aside for a person to look at instead of passed over
    (user, 2026-09-15).

    start_at skips everything before that frame. A person who has watched the
    video and pressed "She appears here" on the review page has said where she
    first shows up, so there is no reason to read what came before it (user,
    2026-09-15) - the rest runs exactly as usual from there.

    Returns {"segments": [{"start", "end", "marks": [(idx, kps), ...]}],
             "checks", "checks_with_her", "checks_unsure", "stopped",
             "started_at", "error"?}; idx are decode indices.
    """
    stats = {"segments": [], "checks": 0, "checks_with_her": 0, "checks_unsure": 0,
             "stopped": False, "started_at": int(max(0, start_at)), "fps": 0.0}
    cap, _backend, _tag, err = _open(video_path)
    if cap is None:
        log.error("%s: %s", video_path, err)
        return dict(stats, error=err)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, round(fps * SEGMENT_STEP_S))
    app = _get_app()
    stats["fps"] = fps

    marks: list[tuple[int, object]] = []    # (idx, kps) for checks that found her
    runs: list[list[tuple[int, object]]] = []
    idx = 0
    while cap.grab():
        if stop_check():
            cap.release()
            log.info("video %s: stop requested while finding her stretches", video_path)
            return dict(stats, stopped=True, segments=[])
        if idx >= start_at and (idx - start_at) % step == 0:
            ok, frame = cap.retrieve()
            if ok:
                stats["checks"] += 1
                faces = _detect(app, frame)
                i, unsure = (pick_her([f.normed_embedding for f in faces]) if faces
                             else (-1, False))
                if unsure:
                    stats["checks_unsure"] += 1
                if i < 0:
                    if marks:
                        runs.append(marks)
                        marks = []
                else:
                    stats["checks_with_her"] += 1
                    marks.append((idx, getattr(faces[i], "kps", None)))
        idx += 1
    if marks:
        runs.append(marks)
    cap.release()

    half = max(1, step // 2)
    last_frame = max(0, idx - 1)
    for run in runs:
        stats["segments"].append({"start": max(0, run[0][0] - half),
                                  "end": min(last_frame, run[-1][0] + half),
                                  "marks": run})
    log.info("video %s: %d checks, she is in %d of them, %d unsure -> %d stretch(es) "
             "covering %d frames", video_path, stats["checks"], stats["checks_with_her"],
             stats["checks_unsure"], len(stats["segments"]),
             sum(s["end"] - s["start"] + 1 for s in stats["segments"]))
    return stats


def _kps_at(marks, idx):
    """Her landmarks at this frame, from the checks either side of it.

    The checks are half a second apart and finding faces costs ~2 s a frame, so
    every frame in between gets its landmarks by moving in a straight line from
    one check to the next. They are what lets the frames stage measure blur and
    spot duplicates later without looking for faces all over again."""
    before = after = None
    for m_idx, kps in marks:
        if kps is None:
            continue
        if m_idx <= idx:
            before = (m_idx, kps)
        if m_idx >= idx and after is None:
            after = (m_idx, kps)
    if before is None and after is None:
        return None
    if before is None:
        return np.asarray(after[1], np.float32)
    if after is None or after[0] == before[0]:
        return np.asarray(before[1], np.float32)
    t = (idx - before[0]) / (after[0] - before[0])
    a = np.asarray(before[1], np.float32)
    b = np.asarray(after[1], np.float32)
    return a + (b - a) * t


def pull_her_frames(video_path: str, segments: list, out_dir: str, prefix: str,
                    video_hash: str = "", stop_check=lambda: False) -> dict:
    """
    Write EVERY frame of the stretches she is in, blurry and duplicate alike
    (user, 2026-09-15), into out_dir as <prefix>_frame<idx>.jpg, with a
    manifest holding her landmarks for each one. The frames stage prunes them
    after the search.
    Returns {"saved", "failed", "error"?}.
    """
    out = {"saved": 0, "failed": 0, "stopped": False}
    if not segments:
        return out
    cap, _backend, _tag, err = _open(video_path)
    if cap is None:
        log.error("%s: %s", video_path, err)
        return dict(out, error=err)
    os.makedirs(out_dir, exist_ok=True)
    last_wanted = max(s["end"] for s in segments)
    manifest = {"video": os.path.abspath(video_path), "video_hash": video_hash, "frames": {}}
    idx = 0
    while idx <= last_wanted and cap.grab():
        if stop_check():
            out["stopped"] = True
            break
        seg = next((s for s in segments if s["start"] <= idx <= s["end"]), None)
        if seg is not None:
            ok, frame = cap.retrieve()
            if not ok:
                out["failed"] += 1
            else:
                dst = os.path.join(out_dir, f"{prefix}_frame{idx:06d}.jpg")
                if cv2.imwrite(dst, frame, [cv2.IMWRITE_JPEG_QUALITY, 95]):
                    kps = _kps_at(seg["marks"], idx)
                    manifest["frames"][str(idx)] = None if kps is None else kps.tolist()
                    out["saved"] += 1
                else:
                    out["failed"] += 1
        idx += 1
    cap.release()
    try:
        with open(os.path.join(out_dir, MANIFEST), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
    except OSError as e:
        log.warning("could not write %s: %s", MANIFEST, e)
    log.info("video %s: %d frames pulled into %s (%d could not be read)",
             video_path, out["saved"], out_dir, out["failed"])
    return out


def prune_her_frames(folder: str) -> dict:
    """
    The after-search pass over one video's pulled frames (user, 2026-09-15):
    delete the blurry ones, then the duplicates and near-duplicates, keeping
    the sharpest of each angle and expression.

    Her landmarks come from the manifest, so no face is looked for again.
    Returns {"started", "blurry_removed", "duplicates_removed", "kept",
             "kept_frames": [(idx, path)], "video", "video_hash"}.
    """
    out = {"started": 0, "blurry_removed": 0, "duplicates_removed": 0, "kept": 0,
           "kept_frames": [], "video": "", "video_hash": ""}
    try:
        with open(os.path.join(folder, MANIFEST), encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError) as e:
        log.warning("%s: no usable %s (%s) - frames left alone", folder, MANIFEST, e)
        return out
    out["video"] = manifest.get("video", "")
    out["video_hash"] = manifest.get("video_hash", "")
    files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".jpg"))
    out["started"] = len(files)

    kept: list[dict] = []
    for name in files:
        path = os.path.join(folder, name)
        idx = int(os.path.splitext(name)[0].rsplit("frame", 1)[-1])
        kps = manifest.get("frames", {}).get(str(idx))
        img = cv2.imread(path)
        if img is None or kps is None:
            _drop(path)
            out["blurry_removed"] += 1
            continue
        aligned = _aligned(img, kps)
        sharp = _sharpness(aligned) if aligned is not None else 0.0
        if sharp < MIN_HER_SHARPNESS:
            _drop(path)
            out["blurry_removed"] += 1
            continue
        sig = {"kps": kps, "pose": _pose(kps), "look": _look(aligned)}
        twin = next((k for k in kept if _twins(sig, k["sig"])), None)
        if twin is None:
            kept.append({"idx": idx, "path": path, "sig": sig, "sharp": sharp})
            continue
        if sharp > twin["sharp"]:
            _drop(twin["path"])
            twin.update(idx=idx, path=path, sig=sig, sharp=sharp)
        else:
            _drop(path)
        out["duplicates_removed"] += 1

    out["kept"] = len(kept)
    out["kept_frames"] = [(k["idx"], k["path"]) for k in sorted(kept, key=lambda k: k["idx"])]
    log.info("%s: %d frames pulled -> %d blurry removed, %d duplicates removed, %d kept",
             folder, out["started"], out["blurry_removed"], out["duplicates_removed"], out["kept"])
    return out


def _drop(path: str):
    try:
        os.remove(path)
    except OSError as e:
        log.warning("could not remove %s: %s", path, e)


def read_frames(video_path: str, indices) -> dict:
    """-> {decode index: frame} for the requested frames of one video.

    Decodes in the same order, with the same orientation handling, as
    scan_frames, so an index returns the frame that was chosen. One pass over
    the video for any number of frames; missing indices are simply absent."""
    wanted = sorted({int(i) for i in indices})
    out: dict[int, np.ndarray] = {}
    if not wanted:
        return out
    cap, _backend, _tag, err = _open(video_path)
    if cap is None:
        log.error("%s: %s", video_path, err)
        return out
    last = wanted[-1]
    want = set(wanted)
    idx = 0
    while idx <= last and cap.grab():
        if idx in want:
            ok, frame = cap.retrieve()
            if ok:
                out[idx] = frame
        idx += 1
    cap.release()
    if len(out) != len(want):
        log.warning("%s: read %d of %d requested frames", video_path, len(out), len(want))
    return out


if __name__ == "__main__":
    import argparse
    import json

    from face_training.logconsole import start_logging_console

    ap = argparse.ArgumentParser(description="List the frames the scan would record (nothing is saved)")
    ap.add_argument("video")
    a = ap.parse_args()
    start_logging_console("video_frames")
    r = scan_frames(a.video)
    print(json.dumps({"recorded": [(f["idx"], len(f["faces"])) for f in r["frames"]],
                      **{k: v for k, v in r.items() if k != "frames"}}, indent=2))
