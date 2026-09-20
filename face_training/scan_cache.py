"""
Content-hashed face-detection cache for Seek.

Detecting faces in a big photo library is the slow part (2-4 s per image on the
CPU). This caches the result of every image by its content, so:

  - a second Seek run only scans files that are new or changed
  - renaming or moving a file does not trigger a rescan
  - a stopped scan resumes exactly where it left off (the DB is the state)

One SQLite database per profile, at <profile>/scan_cache/faces.db.

Runs in the OneTrainer venv (numpy, insightface via sort_photos).
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time

import numpy as np

from face_training.sort_photos import IMAGE_EXTS, _detect, _get_app, _load_bgr
from face_training.video_frames import VIDEO_EXTS, scan_frames

# A video frame is never a file (user, 2026-09-14). In the cache it is a row
# whose path is "<video path>::frame=<decode index>" and whose key is
# "<video content hash>:f<decode index>". seek.py reads the frame back out of
# the video only once it has matched her in it.
FRAME_SEP = "::frame="


def frame_ref(video_path: str, idx: int) -> str:
    return f"{os.path.abspath(video_path)}{FRAME_SEP}{int(idx)}"


def parse_frame_ref(path: str) -> tuple[str, int] | None:
    """-> (video path, decode index) for a video-frame row, None for a photo."""
    if not path or FRAME_SEP not in path:
        return None
    video, _, idx = path.rpartition(FRAME_SEP)
    try:
        return video, int(idx)
    except ValueError:
        return None


def frame_key(video_hash: str, idx: int) -> str:
    return f"{video_hash}:f{int(idx)}"

_HASH_BYTES = 262144        # hash the first 256 KB + size - fast and collision-safe enough


def content_hash(path: str) -> str:
    h = hashlib.blake2b(digest_size=16)
    size = os.path.getsize(path)
    h.update(str(size).encode())
    with open(path, "rb") as fh:
        h.update(fh.read(_HASH_BYTES))
    return h.hexdigest()


_OWN_OUTPUT_DIRS = ("found", "clean", "_thumbs", "video_frames", "backup")

# Whole folders never searched, subfolders included. `_organize_logs` is the
# photo library organizer's working folder (logs, review items, preview
# thumbnails) that sits beside the year folders - previews of library photos,
# not photos (user, 2026-09-14). Pruned from the walk, unlike _OWN_OUTPUT_DIRS,
# which only skip the files directly inside a folder of that name.
_SKIP_TREES = ("_organize_logs",)


def _prune(dirs: list[str]) -> None:
    dirs[:] = [d for d in dirs if d.lower() not in _SKIP_TREES]


def list_images(folder: str, recursive: bool) -> list[str]:
    out = []
    if recursive:
        for root, dirs, files in os.walk(folder):
            _prune(dirs)
            # skip our own output folders
            if os.path.basename(root).lower() in _OWN_OUTPUT_DIRS:
                continue
            for f in files:
                if f.lower().endswith(IMAGE_EXTS):
                    out.append(os.path.join(root, f))
    else:
        for f in sorted(os.listdir(folder)):
            p = os.path.join(folder, f)
            if os.path.isfile(p) and f.lower().endswith(IMAGE_EXTS):
                out.append(p)
    return out


def list_videos(folder: str, recursive: bool) -> list[str]:
    out = []
    if recursive:
        for root, dirs, files in os.walk(folder):
            _prune(dirs)
            if os.path.basename(root).lower() in _OWN_OUTPUT_DIRS:
                continue
            for f in files:
                if f.lower().endswith(VIDEO_EXTS):
                    out.append(os.path.join(root, f))
    else:
        for f in sorted(os.listdir(folder)):
            p = os.path.join(folder, f)
            if os.path.isfile(p) and f.lower().endswith(VIDEO_EXTS):
                out.append(p)
    return out


def scan_video_frames(folder: str, recursive: bool, cache: "ScanCache",
                      stop_check=lambda: False) -> dict:
    """
    For every video under `folder` not already done (by content hash), choose
    its frames in memory (video_frames.scan_frames - the original method) and
    record each one's faces in the cache as a frame row. No frame is written to
    disk.
    A video's frames and its "done" mark are committed together, so a video
    interrupted halfway is simply read again on resume.
    Returns {"videos_found", "videos_read", "frames_recorded", "unreadable"}.
    """
    videos = list_videos(folder, recursive)
    read = recorded = unreadable = 0
    for v in videos:
        if stop_check():
            break
        try:
            vhash = content_hash(v)
            st = os.stat(v)
        except OSError:
            continue
        if cache.video_done(vhash):
            continue          # this exact video content was already read
        r = scan_frames(v, stop_check=stop_check)
        if r.get("stopped"):
            break             # not marked done: it is read again on resume
        for fr in r["frames"]:
            cache.record(frame_key(vhash, fr["idx"]), frame_ref(v, fr["idx"]),
                         fr["faces"], fr["shape"], size=st.st_size, mtime=st.st_mtime,
                         commit=False)
        cache.mark_video_done(vhash, v, r.get("scenes", 0), len(r["frames"]),
                              r.get("error", ""))
        read += 1
        recorded += len(r["frames"])
        unreadable += 1 if r.get("error") else 0
    return {"videos_found": len(videos), "videos_read": read,
            "frames_recorded": recorded, "unreadable": unreadable}


class ScanCache:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db = sqlite3.connect(db_path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS files(
            hash TEXT PRIMARY KEY, path TEXT, size INTEGER, mtime REAL,
            n_faces INTEGER, scanned_at TEXT)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS faces(
            hash TEXT, idx INTEGER, x1 REAL, y1 REAL, x2 REAL, y2 REAL,
            det REAL, emb BLOB, img_h INTEGER, img_w INTEGER,
            PRIMARY KEY(hash, idx))""")
        # Folders finished end to end. The per-file cache already makes a
        # resume correct, but it has to read the first 256 KB of every file to
        # work out that it is already done - half an hour of pure network
        # reading across a 27,000-photo library before it reaches new work.
        # This table lets a finished folder be skipped without opening a
        # single file in it.
        self.db.execute("""CREATE TABLE IF NOT EXISTS folders_done(
            path TEXT, recursive INTEGER, total INTEGER, scanned INTEGER,
            finished_at TEXT, PRIMARY KEY(path, recursive))""")
        # Videos whose frames are recorded (their rows live in files/faces).
        # This used to be "a video_frames/<hash>/ folder exists".
        self.db.execute("""CREATE TABLE IF NOT EXISTS videos_done(
            hash TEXT PRIMARY KEY, path TEXT, candidates INTEGER, kept INTEGER,
            error TEXT, finished_at TEXT)""")
        self.db.commit()

    def close(self):
        self.db.close()

    # --- queries -----------------------------------------------------
    def has(self, hsh: str) -> bool:
        return self.db.execute("SELECT 1 FROM files WHERE hash=?", (hsh,)).fetchone() is not None

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM files").fetchone()[0]

    def video_done(self, video_hash: str) -> bool:
        return self.db.execute("SELECT 1 FROM videos_done WHERE hash=?",
                               (video_hash,)).fetchone() is not None

    def mark_video_done(self, video_hash: str, path: str, candidates: int, kept: int,
                        error: str = ""):
        self.db.execute("INSERT OR REPLACE INTO videos_done VALUES(?,?,?,?,?,?)",
                        (video_hash, path, candidates, kept, error,
                         time.strftime("%Y-%m-%dT%H:%M:%S")))
        self.db.commit()

    def record(self, hsh: str, path: str, faces, img_shape, size=None, mtime=None,
               commit: bool = True):
        """One photo, or one video frame (path from frame_ref, with the video's
        size and mtime passed in - a frame has no file of its own to stat)."""
        h, w = img_shape[:2]
        if size is None or mtime is None:
            st = os.stat(path)
            size, mtime = st.st_size, st.st_mtime
        self.db.execute(
            "INSERT OR REPLACE INTO files VALUES(?,?,?,?,?,?)",
            (hsh, path, size, mtime, len(faces),
             time.strftime("%Y-%m-%dT%H:%M:%S")))
        self.db.execute("DELETE FROM faces WHERE hash=?", (hsh,))
        for i, f in enumerate(faces):
            x1, y1, x2, y2 = (float(v) for v in f.bbox)
            emb = np.asarray(f.normed_embedding, dtype=np.float16).tobytes()
            self.db.execute(
                "INSERT INTO faces VALUES(?,?,?,?,?,?,?,?,?,?)",
                (hsh, i, x1, y1, x2, y2, float(f.det_score), emb, h, w))
        if commit:
            self.db.commit()

    # --- folder-level progress ---------------------------------------
    @staticmethod
    def _folder_key(folder: str) -> str:
        return os.path.normcase(os.path.abspath(folder))

    def folder_done(self, folder: str, recursive: bool) -> dict | None:
        """The record for a folder already scanned end to end, or None."""
        row = self.db.execute(
            "SELECT total, scanned, finished_at FROM folders_done "
            "WHERE path=? AND recursive=?",
            (self._folder_key(folder), 1 if recursive else 0)).fetchone()
        if not row:
            return None
        return {"total": row[0], "scanned": row[1], "finished_at": row[2]}

    def mark_folder_done(self, folder: str, recursive: bool, total: int, scanned: int):
        self.db.execute(
            "INSERT OR REPLACE INTO folders_done VALUES(?,?,?,?,?)",
            (self._folder_key(folder), 1 if recursive else 0, total, scanned,
             time.strftime("%Y-%m-%dT%H:%M:%S")))
        self.db.commit()

    def folders_finished(self) -> list[dict]:
        return [{"path": p, "recursive": bool(r), "total": t, "scanned": sc,
                 "finished_at": f}
                for p, r, t, sc, f in self.db.execute(
                    "SELECT path, recursive, total, scanned, finished_at "
                    "FROM folders_done ORDER BY finished_at")]

    def iter_scanned(self):
        """yield (hash, path, img_h, img_w, [ (bbox, det, emb_f32) ... ]) for every file."""
        rows = self.db.execute(
            "SELECT hash, path, n_faces FROM files").fetchall()
        for hsh, path, _n in rows:
            frows = self.db.execute(
                "SELECT x1,y1,x2,y2,det,emb,img_h,img_w FROM faces WHERE hash=? ORDER BY idx",
                (hsh,)).fetchall()
            faces = []
            ih = iw = 0
            for x1, y1, x2, y2, det, emb, img_h, img_w in frows:
                ih, iw = img_h, img_w
                e = np.frombuffer(emb, dtype=np.float16).astype(np.float32)
                faces.append(((x1, y1, x2, y2), det, e))
            yield hsh, path, ih, iw, faces


def scan_folder(folder: str, recursive: bool, cache: ScanCache,
                stop_check=lambda: False, on_progress=None,
                limit: int | None = None, scan_videos: bool = False,
                skip_finished: bool = True) -> dict:
    """
    Detect faces in every not-yet-cached image under `folder`. If scan_videos,
    the videos under `folder` are read first and their chosen frames' faces
    recorded as frame rows (scan_video_frames) - no frame is saved to disk.
    Returns {"total", "scanned", "skipped", "stopped", "video_stats"?}.

    skip_finished: return straight away if this exact folder was previously
    scanned to completion. Set False to force a re-walk - a folder that has
    gained new photos since needs one, because "finished" is recorded against
    the folder, not its contents.
    """
    if skip_finished and limit is None:
        prev = cache.folder_done(folder, recursive)
        if prev:
            return {"total": prev["total"], "scanned": 0, "skipped": prev["total"],
                    "stopped": False, "already_done": prev["finished_at"]}

    app = _get_app()
    video_stats = None
    if scan_videos:
        video_stats = scan_video_frames(folder, recursive, cache, stop_check=stop_check)

    images = list_images(folder, recursive)
    total = len(images)
    scanned = skipped = 0
    stopped = False

    for i, path in enumerate(images):
        if stop_check():
            stopped = True
            break
        if limit is not None and scanned >= limit:
            break
        try:
            hsh = content_hash(path)
        except OSError:
            continue
        if cache.has(hsh):
            skipped += 1
            continue
        img = _load_bgr(path)
        if img is None:
            cache.record(hsh, path, [], (0, 0))
            scanned += 1
            continue
        faces = _detect(app, img)
        cache.record(hsh, path, faces, img.shape)
        scanned += 1
        if on_progress and scanned % 5 == 0:
            on_progress(i + 1, total, scanned, skipped)

    if on_progress:
        on_progress(total, total, scanned, skipped)
    if not stopped and limit is None:
        # only a complete pass earns the "done" mark - a stopped or limited run
        # must still be re-walked next time
        cache.mark_folder_done(folder, recursive, total, scanned)
    result = {"total": total, "scanned": scanned, "skipped": skipped, "stopped": stopped}
    if video_stats:
        result["video_stats"] = video_stats
    return result


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Scan a folder's faces into a cache")
    ap.add_argument("folder")
    ap.add_argument("db")
    ap.add_argument("--flat", action="store_true", help="this folder only, no subfolders")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    c = ScanCache(a.db)
    t0 = time.time()
    r = scan_folder(a.folder, not a.flat, c, limit=a.limit,
                    on_progress=lambda i, t, s, k: print(f"  {i}/{t}  scanned {s} skipped {k}"))
    print(r, f"in {time.time()-t0:.0f}s ; cache now holds {c.count()} files")
    c.close()
