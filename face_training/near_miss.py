"""
The middle drawer: faces that were nearly her, and the photos around them.

The pipeline makes a hard call on every face - above the cutoff she is
gathered, below it the face is dropped and no trace is kept. Two things are
lost that way. Photos that sit just under the line vanish silently, so a miss
looks exactly like an absence. And every face is judged alone, as if it were
the only photograph in the world, which throws away the strongest evidence a
human uses: that the picture was taken at the same moment as one already known
to be her.

This tool adds both back, working entirely from the scan cache, so it costs
minutes rather than the hours the scanning took.

  1. Score every cached face against her current identity.
  2. Keep the near-misses - below the cutoff but not by much.
  3. Group photos into sessions by folder and time, and mark the near-misses
     that sit in a session containing a confident match. Those are the ones a
     person would recognise on sight: the same afternoon, the same room, the
     same clothes, her face half-turned away.
  4. Write a contact sheet of cropped faces with their scores, so the call can
     be made by eye instead of by threshold.

Session time comes from the file modification time already stored in the cache,
which is free. On a copied library that can be the copy date rather than the
day the photo was taken - use --exif to read real capture times for the
candidates only, which costs a few seconds per hundred photos.

  python -m face_training.near_miss --profile susana --report
  python -m face_training.near_miss --profile susana --report --exif
  python -m face_training.near_miss --profile susana --promote 0.28

Nothing here writes to the scan cache or to the gathered folders unless
--promote is given, so it is safe to run while a scan is going.
"""

from __future__ import annotations

import argparse
import html
import os
import shutil
import sqlite3
import sys
import time

import numpy as np

from face_training.identity import Identity
from face_training.scan_cache import parse_frame_ref
from face_training.sort_photos import MIN_DET_SCORE, _load_bgr

from face_training.comfy_paths import PROFILES_ROOT  # our repo, never the app folder

FLOOR = 0.20            # below this it is somebody else, not a near miss
SESSION_GAP_S = 30 * 60  # photos within half an hour are the same occasion
CONTEXT_BONUS = 0.06     # how much a confident neighbour is worth


class Face:
    __slots__ = ("hash", "path", "idx", "sim", "box", "img_h", "img_w",
                 "mtime", "session", "context")

    def __init__(self, hsh, path, idx, sim, box, img_h, img_w, mtime):
        self.hash, self.path, self.idx = hsh, path, idx
        self.sim, self.box = sim, box
        self.img_h, self.img_w, self.mtime = img_h, img_w, mtime
        self.session = None
        self.context = False

    @property
    def face_px(self) -> float:
        return self.box[3] - self.box[1]


def _profile_dir(slug: str) -> str:
    d = os.path.join(PROFILES_ROOT, slug)
    if not os.path.isdir(d):
        sys.exit(f"no profile at {d}")
    return d


def _cutoff(prof_dir: str, override: float | None) -> float:
    if override is not None:
        return override
    import json
    from face_training.safe_replace import read_text
    try:
        # a running Seek may be swapping profile.json in - read_text waits
        return float(json.loads(read_text(os.path.join(prof_dir, "profile.json")))
                     .get("thresholds", {}).get("match", 0.32))
    except (OSError, ValueError, KeyError):
        return 0.32


def score_all(prof_dir: str) -> list[Face]:
    """Every cached face, scored against her identity. Read-only."""
    db_path = os.path.join(prof_dir, "scan_cache", "faces.db")
    ident = Identity.load(os.path.join(prof_dir, "identity"))
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = db.execute(
        "SELECT a.hash, f.path, a.idx, a.x1, a.y1, a.x2, a.y2, a.det, a.emb, "
        "a.img_h, a.img_w, f.mtime FROM faces a JOIN files f ON f.hash = a.hash"
    ).fetchall()
    db.close()

    out = []
    for hsh, path, idx, x1, y1, x2, y2, det, emb, ih, iw, mtime in rows:
        if det < MIN_DET_SCORE:
            continue
        e = np.frombuffer(emb, dtype=np.float16).astype(np.float32)
        out.append(Face(hsh, path, idx, float(np.dot(e, ident.mean)),
                        (x1, y1, x2, y2), ih, iw, mtime))
    return out, ident


def build_sessions(faces: list[Face]) -> dict:
    """Group photos into occasions: same folder, taken close together in time.

    This is the piece the pipeline has no notion of. A face judged alone has
    only its own 512 numbers to argue with; a face judged in company can borrow
    the certainty of the photo taken forty seconds earlier."""
    by_photo = {}
    for f in faces:
        by_photo.setdefault(f.path, f)          # one entry per photo is enough
    items = [(os.path.dirname(p), f.mtime or 0, p) for p, f in by_photo.items()]
    items.sort()

    sessions, sid, last_dir, last_t = {}, 0, None, None
    for d, t, p in items:
        if d != last_dir or last_t is None or (t - last_t) > SESSION_GAP_S:
            sid += 1
        sessions[p] = sid
        last_dir, last_t = d, t
    for f in faces:
        f.session = sessions.get(f.path)
    return sessions


def mark_context(faces: list[Face], cutoff: float) -> int:
    """Flag near-misses sitting in a session that already contains a sure hit."""
    confident = {f.session for f in faces if f.sim >= cutoff and f.session}
    n = 0
    for f in faces:
        if f.sim < cutoff and f.session in confident:
            f.context = True
            n += 1
    return n


def read_exif_times(faces: list[Face]) -> int:
    """Real capture times for these photos only - a copied library often has
    file dates from the day it was copied, which would fuse unrelated years
    into one 'session'."""
    from PIL import Image
    fixed = 0
    for path in {f.path for f in faces}:
        try:
            with Image.open(path) as im:
                ex = im.getexif()
            raw = ex.get(36867) or ex.get(306)      # DateTimeOriginal, DateTime
            if not raw:
                continue
            t = time.mktime(time.strptime(str(raw), "%Y:%m:%d %H:%M:%S"))
        except Exception:                            # noqa: BLE001
            continue
        for f in faces:
            if f.path == path:
                f.mtime = t
        fixed += 1
    return fixed


_RELOCATED: dict[str, str] = {}


def build_relocation_index(prof_dir: str):
    """Filename -> current location, for photos that have moved since scanning.

    The cache stores the path a photo had when it was scanned. Content hashing
    means a moved photo is never rescanned, which is right - but a crop still
    needs somewhere to read the pixels from, and a reorganised folder leaves
    those paths pointing at nothing. This re-finds them by name."""
    import json
    from face_training.safe_replace import read_text
    roots = []
    try:
        # a running Seek may be swapping profile.json in - read_text waits
        d = json.loads(read_text(os.path.join(prof_dir, "profile.json")))
        if d.get("seed_folder"):
            roots.append(d["seed_folder"])
        roots += [e["path"] for e in d.get("seek_folders", []) if e.get("path")]
    except (OSError, ValueError):
        pass
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                _RELOCATED.setdefault(f.lower(), os.path.join(dirpath, f))


def resolve(path: str) -> str | None:
    """Where this photo actually is now, or None if it is truly gone."""
    if os.path.isfile(path):
        return path
    return _RELOCATED.get(os.path.basename(path).lower())


def load_images(faces: list[Face]) -> dict:
    """{cache path: image} for these faces - photos from their file, video
    frames read back out of their video (one pass per video). Video frames are
    not files (scan_cache.frame_ref)."""
    from face_training.video_frames import read_frames
    out, by_video = {}, {}
    for f in faces:
        ref = parse_frame_ref(f.path)
        if ref:
            by_video.setdefault(ref[0], {})[f.path] = ref[1]
        elif f.path not in out:
            live = resolve(f.path)
            out[f.path] = _load_bgr(live) if live else None
    for video, paths in by_video.items():
        live = resolve(video)
        frames = read_frames(live, paths.values()) if live else {}
        for path, i in paths.items():
            out[path] = frames.get(i)
    return out


def contact_sheet(cands: list[Face], out_dir: str, cutoff: float, title: str) -> str:
    """Crop each near-miss face and lay them out with their scores."""
    crops = os.path.join(out_dir, "crops")
    os.makedirs(crops, exist_ok=True)
    import cv2

    cards = []
    missing = 0
    images = load_images(cands)
    for i, f in enumerate(sorted(cands, key=lambda x: -x.sim)):
        img = images.get(f.path)
        if img is None:
            missing += 1
            continue
        x1, y1, x2, y2 = (int(v) for v in f.box)
        bw, bh = x2 - x1, y2 - y1
        cx1 = max(0, int(x1 - bw * 0.5)); cx2 = min(img.shape[1], int(x2 + bw * 0.5))
        cy1 = max(0, int(y1 - bh * 0.6)); cy2 = min(img.shape[0], int(y2 + bh * 0.7))
        crop = img[cy1:cy2, cx1:cx2]
        if crop.size == 0:
            continue
        name = f"{i:04d}_{f.sim:.3f}_{f.hash[:8]}.jpg"
        cv2.imwrite(os.path.join(crops, name), crop,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        cards.append((name, f))

    rows = "\n".join(
        f'<figure><img src="crops/{html.escape(n)}" loading="lazy">'
        f'<figcaption><b>{f.sim:.3f}</b>{" &middot; same session" if f.context else ""}'
        f'<br><span>{html.escape(os.path.basename(f.path))}</span>'
        f'<br><span>{int(f.face_px)}px face</span></figcaption></figure>'
        for n, f in cards)
    page = f"""<meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body{{background:#151515;color:#ddd;font:13px system-ui,Segoe UI,sans-serif;margin:16px}}
h1{{font-size:16px}} .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px}}
figure{{margin:0;background:#1e1e1e;border:1px solid #333;border-radius:6px;overflow:hidden}}
img{{width:100%;display:block;aspect-ratio:1/1;object-fit:cover}}
figcaption{{padding:5px 6px;font-size:11px;line-height:1.3}}
figcaption span{{color:#888;font-size:10px;word-break:break-all}}
b{{color:#ffd479}}
</style>
<h1>{html.escape(title)}</h1>
<p>{len(cards)} faces below the {cutoff:.2f} cutoff. "same session" means the
photo was taken alongside one that IS confidently her.</p>
<div class="grid">
{rows}
</div>"""
    if missing:
        print(f"  {missing} could not be read even after re-finding them")
    page_path = os.path.join(out_dir, "near_miss.html")
    with open(page_path, "w", encoding="utf-8") as fh:
        fh.write(page)
    return page_path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--cutoff", type=float, default=None)
    ap.add_argument("--floor", type=float, default=FLOOR)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--exif", action="store_true",
                    help="read real capture times for the candidates")
    ap.add_argument("--max-crops", type=int, default=400)
    ap.add_argument("--promote", type=float, default=None, metavar="SIM",
                    help="copy near-misses at or above SIM into found/ for review")
    a = ap.parse_args()

    prof_dir = _profile_dir(a.profile)
    cutoff = _cutoff(prof_dir, a.cutoff)
    faces, ident = score_all(prof_dir)
    print(f"identity built from {ident.n_refs} faces | cutoff {cutoff:.2f}")
    print(f"{len(faces)} faces in the cache")

    sure = [f for f in faces if f.sim >= cutoff]
    near = [f for f in faces if a.floor <= f.sim < cutoff]
    print(f"  confident matches : {len(sure)}")
    print(f"  near misses       : {len(near)}  (between {a.floor:.2f} and {cutoff:.2f})")

    if a.exif:
        n = read_exif_times(near + sure)
        print(f"  capture times read from {n} photos")
    build_sessions(faces)
    ctx = mark_context(faces, cutoff)
    near = [f for f in faces if a.floor <= f.sim < cutoff]
    in_ctx = [f for f in near if f.context]
    print(f"  sessions           : {len({f.session for f in faces})}")
    print(f"  near misses beside a sure match : {len(in_ctx)}"
          f"  <- most likely to be her")

    for lo in (0.30, 0.28, 0.26, 0.24, 0.22):
        n = sum(1 for f in near if f.sim >= lo)
        c = sum(1 for f in in_ctx if f.sim >= lo)
        print(f"    at {lo:.2f} or better: {n:5d} near misses ({c} of them beside a sure match)")

    if a.report:
        build_relocation_index(prof_dir)
        out = os.path.join(prof_dir, "near_miss")
        os.makedirs(out, exist_ok=True)
        cands = sorted(near, key=lambda f: (-f.context, -f.sim))[:a.max_crops]
        page = contact_sheet(cands, out, cutoff, f"{a.profile}: the middle drawer")
        print(f"\n  contact sheet: {page}")

    if a.promote is not None:
        found = os.path.join(prof_dir, "found")
        os.makedirs(found, exist_ok=True)
        n = 0
        promote = [f for f in near if f.sim >= a.promote]
        frames = [f for f in promote if parse_frame_ref(f.path)]
        if frames:
            # video frames are not files: read each back out of its video and
            # save it as a still, the same way Seek saves a matched frame
            import cv2
            build_relocation_index(prof_dir)
            images = load_images(frames)
            for f in frames:
                video, idx = parse_frame_ref(f.path)
                stem = os.path.splitext(os.path.basename(video))[0]
                dst = os.path.join(found, f"{stem}_frame{idx:06d}__{f.hash[:8]}.jpg")
                img = images.get(f.path)
                if img is not None and not os.path.exists(dst) and \
                        cv2.imwrite(dst, img, [cv2.IMWRITE_JPEG_QUALITY, 95]):
                    n += 1
        for f in sorted(promote, key=lambda x: -x.sim):
            if parse_frame_ref(f.path):
                continue
            stem, ext = os.path.splitext(os.path.basename(f.path))
            dst = os.path.join(found, f"{stem}__{f.hash[:8]}{ext}")
            if not os.path.exists(dst) and os.path.isfile(f.path):
                try:
                    shutil.copy2(f.path, dst)
                    n += 1
                except OSError:
                    pass
        print(f"  promoted {n} photos into found/ for review")


if __name__ == "__main__":
    main()
