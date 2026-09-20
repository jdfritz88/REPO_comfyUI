"""
The mandatory review page: every crop Seek produced, before anything trains.

Seek (a window run) or a whole background library run ends by marking the person
"review pending". Nothing trains until someone looks at the crops here and clicks
Proceed (user, 2026-09-13):

  - tick crops, click Delete        the crop and its caption go to the Recycle Bin;
                                     the search history records that its original
                                     is not this person, so no later search copies it
                                     again. Other crops cut from the same original
                                     are left alone. The face judge is NOT taught.
  - tick crops, click Rotate Left /  the crop is turned a quarter, its caption tags
    Rotate Right                     are measured again on her face, and the turn is
                                     written to the search history
  - crops framed in yellow           other people's faces are still in them - the
                                     cropper could not remove them without cutting
                                     into her
  - Proceed                          clears "review pending" and starts training

A local page on 127.0.0.1 only. Nothing leaves the machine.

  python -m face_training.review_server --profile susana [--no-browser] [--port N]

Runs in the OneTrainer venv.
"""

from __future__ import annotations

import argparse
import ctypes
import glob
import json
import logging
import os
import subprocess
import sys
import threading
import time
import re
import urllib.parse
import urllib.request
import uuid
import webbrowser
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(_HERE) not in sys.path:
    sys.path.insert(0, os.path.dirname(_HERE))

import cv2
import numpy as np

from face_training import crop_guard as CG
from face_training import dedupe as DD
from face_training import face_groups as FG
from face_training import profiles as P
from face_training.recycle import recycle
from face_training.scan_cache import content_hash as _content_hash
from face_training import search_history as SH
from face_training.identity import Identity
from face_training.seek import approved_waiting as SK_pending
from face_training.seek import standing_marks as SK_marks
from face_training.sort_photos import build_caption
from face_training.video_frames import VIDEO_EXTS

log = logging.getLogger("face_training.review_server")

REPO = os.path.dirname(_HERE)
PAGE = os.path.join(_HERE, "review_page.html")
TRAIN_LOG_DIR = os.path.join(REPO, "logs", "face_training")
CROP_EXTS = (".jpg", ".jpeg", ".png")
# The server stays up while the training it started runs, so the page can keep
# showing how it is going, then closes this long after the run ends.
SHUTDOWN_AFTER_TRAINING_S = 120

# The same port every time, so a link to this page keeps working. The page is
# read from another device over Tailscale (user, 2026-09-17), which forwards to
# one fixed port; a random port would break that link on every restart. If
# something else already holds it, any free port is used instead and the log
# says so - the page opening matters more than the number.
DEFAULT_PORT = 50086

# Undo (user, 2026-09-17): no confirmation before an answer, a way back after it.
# An answer about an uncertain photo or video is written down at once, but what
# it DOES - deleting a copy, moving one to _approved, teaching the judge - waits
# until the answer is UNDO_DEPTH answers old, so nothing is gone while the button
# can still take it back. The file waits in needs_review/_undo, and _undo/pending
# .json survives a crash so the waiting answers are carried out on the next start.
# How far round a face to blur, in turn, as a fraction of the face box. The
# first pass is the cropper's own clearance; the wider ones are for faces the
# detector still finds afterwards.
BLUR_PADS = (0.10, 0.35, 0.60)

# The review page's slider lives in face_groups.py now: whole notches, 1 to 10,
# 4 being the frame-pruning step's own settings (user, 2026-09-17).

UNDO_DEPTH = 10
UNDO_DIR = "_undo"
UNDO_PENDING = "pending.json"


_TRAIN_WHICH = re.compile(r"\[(\d+)/(\d+)\] training (\S+)")
_TRAIN_EPOCH = re.compile(r"epoch:\s+(\d+)%\|[^|]*\|\s*(\d+)/(\d+)\s*\[([^<]+)<([^,\]]+)")


def training_progress(log_path: str) -> dict | None:
    """How far a training run has got, read from the log it is writing.

    OneTrainer prints an epoch counter as it goes and the pipeline prints which
    LoRA of the set it is on, so between them the page can show a real bar
    instead of "it is running" (user, 2026-09-17). Only the tail of the file is
    read, so this costs nothing to ask for often.
    """
    try:
        with open(log_path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            back = min(fh.tell(), 16384)
            fh.seek(-back, os.SEEK_END)
            tail = fh.read().decode("utf-8", "replace")
    except OSError:
        return None
    which = None
    for m in _TRAIN_WHICH.finditer(tail):
        which = m
    epoch = None
    for m in _TRAIN_EPOCH.finditer(tail):
        epoch = m
    if not which and not epoch:
        return None
    out = {}
    if which:
        out["lora_at"], out["lora_of"] = int(which.group(1)), int(which.group(2))
        out["lora"] = which.group(3)
    if epoch:
        out["epoch_at"], out["epoch_of"] = int(epoch.group(2)), int(epoch.group(3))
        out["elapsed"], out["left"] = epoch.group(4).strip(), epoch.group(5).strip()
    # one number for the bar: whole LoRAs done, plus how far through this one
    if "lora_at" in out and "epoch_of" in out and out["epoch_of"]:
        share = out["epoch_at"] / out["epoch_of"]
        out["pct"] = round(100 * ((out["lora_at"] - 1) + share) / out["lora_of"])
    elif "epoch_of" in out and out["epoch_of"]:
        out["pct"] = round(100 * out["epoch_at"] / out["epoch_of"])
    bits = []
    if "lora_at" in out:
        bits.append(f"LoRA {out['lora_at']} of {out['lora_of']} — {out['lora']}")
    if "epoch_of" in out:
        left = out.get("left", "")
        bits.append(f"epoch {out['epoch_at']} of {out['epoch_of']}"
                    + (f", about {left} left on this one" if left and left != "?" else ""))
    out["line"] = " · ".join(bits)
    return out


def _apply_blur(img, faces, pad_frac: float):
    """Blur each face away in place, with pad_frac of its size to spare.

    Blurred through a soft oval, not a square: a hard-edged rectangle is itself
    a shape, and the whole point of blurring rather than blacking out is to
    leave the training nothing to learn but a smudge.
    """
    h, w = img.shape[:2]
    for f in faces:
        x1, y1, x2, y2 = [int(v) for v in f.bbox]
        pad = int(pad_frac * max(x2 - x1, y2 - y1))
        x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
        x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
        if x2 <= x1 or y2 <= y1:
            continue
        region = img[y1:y2, x1:x2]
        rh, rw = region.shape[:2]
        k = max(31, min(rw, rh) | 1)                  # odd, and wide
        blurred = cv2.GaussianBlur(region, (k, k), 0)
        mask = np.zeros((rh, rw), np.float32)
        cv2.ellipse(mask, (rw // 2, rh // 2), (int(rw * 0.52), int(rh * 0.52)),
                    0, 0, 360, 1.0, -1)
        feather = max(9, (min(rw, rh) // 4) | 1)
        mask = cv2.GaussianBlur(mask, (feather, feather), 0)[..., None]
        img[y1:y2, x1:x2] = (blurred * mask + region * (1.0 - mask)).astype(np.uint8)


# Deleting to the Recycle Bin lives in recycle.py, so the Face Tool's Delete
# button and this page's Delete use exactly the same code.
_recycle = recycle


def _pid_alive(pid: int) -> bool:
    try:
        import psutil
        return psutil.pid_exists(int(pid))
    except Exception:                                          # noqa: BLE001
        return False


def find_running(prof: P.Profile) -> dict | None:
    """The review page already open for this person, if its server is alive."""
    try:
        with open(prof.review_server_file, encoding="utf-8") as fh:
            info = json.load(fh)
        if not _pid_alive(info["pid"]):
            return None
        with urllib.request.urlopen(info["url"] + "api/ping", timeout=2) as r:
            return info if r.status == 200 else None
    except Exception:                                          # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
# the review itself
# --------------------------------------------------------------------------- #
class Review:
    def __init__(self, slug: str):
        prof = P.Profile(slug)
        if not prof.data:
            raise ValueError(f"no profile '{slug}'")
        self.slug = slug
        self.lock = threading.Lock()
        self.sub = {"head": prof.clean_head, "body": prof.clean_body}
        # uncertain work, both kinds, on this one page (user, 2026-09-15): the
        # videos Seek could not call, and the photos it could not call
        self.unsure = {"video": prof.uncertain_dir, "photo": prof.needs_review_dir}
        self.undo_dir = os.path.join(prof.needs_review_dir, UNDO_DIR)
        self.undo_file = os.path.join(self.undo_dir, UNDO_PENDING)
        self.pending: list[dict] = []
        self._load_pending()
        self.training: dict | None = None
        self.on_training_end = None
        # cutting the approved photos and pulling the marked videos, when the
        # page asks for it (user, 2026-09-17): {"running", "line", "done"}
        self.finishing: dict | None = None
        # finding her face in each crop, for the review page's grouping
        self.measuring: dict | None = None

    # always re-read from disk: never write back a stale copy of profile.json
    def _prof(self) -> P.Profile:
        return P.Profile(self.slug)

    def _history(self) -> SH.History:
        return SH.History(self._prof().history_path)

    def _path(self, kind: str, name: str) -> str:
        if kind not in self.sub:
            raise ValueError(f"unknown crop kind {kind!r}")
        if os.path.basename(name) != name or not name.lower().endswith(CROP_EXTS):
            raise ValueError(f"bad crop name {name!r}")
        p = os.path.join(self.sub[kind], name)
        if not os.path.isfile(p):
            raise FileNotFoundError(f"{kind}/{name} is not there any more")
        return p

    def _unsure_path(self, kind: str, name: str) -> str:
        d = self.unsure.get(kind)
        if not d:
            raise ValueError(f"unknown kind {kind!r}")
        if os.path.basename(name) != name:
            raise ValueError(f"bad name {name!r}")
        p = os.path.join(d, name)
        if not os.path.isfile(p):
            raise FileNotFoundError(f"{name} is not there any more")
        return p

    def _marked_videos(self, hist) -> set:
        """Videos already answered "she appears here", and still standing.

        The copy has to stay in uncertain/ - the search pulls her frames out of
        it - but a video you have answered must leave the page, the way an
        answered photo does. It used to sit there looking unanswered, and the
        same video was marked again and again (user, 2026-09-17), each mark
        replacing the one before it. A mark that was tried and found nothing of
        her stops standing, so the video comes back here to be answered again.
        """
        return set(SK_marks(hist))

    def _video_notes(self, hist) -> dict:
        """{video name: what happened last time it was marked}."""
        out = {}
        for e in hist.data.get("events", []):
            if e.get("kind") == "marked_video_no_match" and e.get("video"):
                out[e["video"]] = (f"you marked frame {e.get('start_frame', 0)}, but no face in "
                                   f"this video looked like her - nothing was pulled")
            elif (e.get("kind") == "uncertain_video_answered" and e.get("video")
                  and e.get("answer") == "in it" and not e.get("undone")):
                out.pop(e["video"], None)
        return out

    def _unsure_items(self, prof) -> dict:
        """The videos and photos waiting for a yes or no."""
        out = {"video": [], "photo": []}
        hist = SH.History(prof.history_path)
        marked, notes = self._marked_videos(hist), self._video_notes(hist)
        for kind, d in self.unsure.items():
            exts = VIDEO_EXTS if kind == "video" else CROP_EXTS
            for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
                p = os.path.join(d, name)
                if not os.path.isfile(p) or not name.lower().endswith(exts):
                    continue
                if kind == "video" and name in marked:
                    continue
                out[kind].append({"kind": kind, "name": name,
                                  "mb": round(os.path.getsize(p) / 1e6, 1),
                                  "note": notes.get(name, "") if kind == "video" else "",
                                  "v": int(os.path.getmtime(p) * 1000)})
        return out

    def state(self) -> dict:
        prof = self._prof()
        hist = SH.History(prof.history_path)
        items = {}
        for kind, d in self.sub.items():
            rows = []
            for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
                if not name.lower().endswith(CROP_EXTS):
                    continue
                p = os.path.join(d, name)
                c = hist.crop(f"{kind}/{name}") or {}
                rows.append({"kind": kind, "name": name,
                             "v": int(os.path.getmtime(p) * 1000),
                             "others": int(c.get("others_remain", 0)),
                             "source": c.get("source", "")})
            items[kind] = rows
        tr = self.training or self._recover_training(prof)
        if tr:
            # running until the watcher has recorded how it ended, so the page
            # never sees "ended" without the outcome that goes with it
            tr = dict(tr, running="ended" not in tr)
            if tr["running"] and tr.get("log"):
                p = training_progress(tr["log"])
                if p:
                    tr = dict(tr, progress=p)
        from face_training.otrain import training_settings_summary
        return {"person": prof.data.get("display_name", self.slug),
                "review_pending": prof.review_pending(), "items": items, "training": tr,
                "unsure": self._unsure_items(prof), "undo": self.undo_state(),
                "notches": {"min": FG.NOTCH_MIN, "max": FG.NOTCH_MAX,
                            "default": FG.NOTCH_DEFAULT},
                "pending": SK_pending(prof), "finishing": self.finishing,
                "measuring": self.measuring, "settled": self._settled_counts(),
                "settings": training_settings_summary()}

    # --- answers that can still be taken back ---------------------------
    def _load_pending(self):
        """Carry out answers left waiting by an earlier review before this one
        starts: the page they belonged to is gone, so they cannot be undone."""
        try:
            with open(self.undo_file, encoding="utf-8") as fh:
                left = json.load(fh)
        except (OSError, ValueError):
            left = []
        if left:
            log.info("%d answer(s) were still waiting from an earlier review "
                     "- carrying them out now", len(left))
            for e in left:
                try:
                    self._finalise(e)
                except Exception:                              # noqa: BLE001
                    log.exception("could not finish answer %s", e.get("name"))
        self.pending = []
        self._save_pending()

    def _save_pending(self):
        os.makedirs(self.undo_dir, exist_ok=True)
        tmp = self.undo_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.pending, fh, indent=1)
        os.replace(tmp, self.undo_file)

    def _stage(self, entry: dict, src: str | None) -> dict:
        """Put one answered file out of sight but not out of reach."""
        if src:
            folder = os.path.join(self.undo_dir, entry["ref"])
            os.makedirs(folder, exist_ok=True)
            staged = os.path.join(folder, os.path.basename(src))
            os.replace(src, staged)
            entry["staged"], entry["back_to"] = staged, src
        self.pending.append(entry)
        while len(self.pending) > UNDO_DEPTH:
            self._finalise(self.pending.pop(0))
        self._save_pending()
        return entry

    def _finalise(self, e: dict):
        """An answer no Undo can reach any more: do what it said.

        Everything that cannot be taken back happens here and nowhere else -
        deleting the copy, moving a kept photo to _approved, teaching the judge
        from a yes or a no, and writing "her, not used" into the search history.
        """
        staged, kind, answer = e.get("staged"), e.get("kind"), e.get("answer")
        name = e.get("name", "")
        if not staged or not os.path.isfile(staged):
            self._drop_ref_dir(e)
            return
        prof = self._prof()
        hist = SH.History(prof.history_path)
        if kind == "photo" and answer in ("yes", "not_her"):
            from face_training import facebank as FB
            from face_training import seek as SK
            sc = FB.scores_for(self.slug, staged)
            if answer == "yes":
                os.makedirs(prof.review_approved_dir, exist_ok=True)
                SK._move_into(staged, prof.review_approved_dir)
            else:
                recycle([staged])
            FB.apply_review(self.slug, staged, answer == "yes",
                            sc[0] if sc else None, sc[1] if sc else None,
                            sc[2] if sc else False)
        elif kind == "photo" and answer in ("her_unused", "duplicate"):
            # Recorded, never learned from (user, 2026-09-17): the judge is not
            # told anything, and the picture is not offered again.
            cap = hist.capture(name) or {}
            hsh = cap.get("hash") or _content_hash(staged)
            hist.mark_not_used(hsh, reason=answer, name=name, source=cap.get("source", ""))
            hist.set_outcome(name, answer)
            hist.save()
            recycle([staged])
        elif kind == "video" and answer == "not_her":
            recycle([staged])
        else:
            # nothing was staged for this answer (a video mark): nothing to do
            pass
        self._drop_ref_dir(e)

    def _drop_ref_dir(self, e: dict):
        folder = os.path.join(self.undo_dir, e.get("ref", ""))
        if e.get("ref") and os.path.isdir(folder) and not os.listdir(folder):
            try:
                os.rmdir(folder)
            except OSError:
                pass

    def undo_last(self) -> dict:
        """Take back the most recent answer: the file comes back, the page shows
        it again, and the entry in her search history is marked as taken back."""
        with self.lock:
            if not self.pending:
                return {"ok": False, "error": "there is nothing left to undo"}
            e = self.pending.pop()
            self._save_pending()
            staged, back = e.get("staged"), e.get("back_to")
            if staged and back and os.path.isfile(staged):
                os.makedirs(os.path.dirname(back), exist_ok=True)
                os.replace(staged, back)
            self._drop_ref_dir(e)
            hist = self._history()
            hist.mark_event_undone(e["ref"])
            hist.log("review_answer_undone", ref=e["ref"], name=e.get("name"),
                     about=e.get("kind"), answer=e.get("answer"),
                     meaning="the person took this answer back")
            hist.save()
            return {"ok": True, "name": e.get("name"), "answer": e.get("answer"),
                    "said": e.get("said", ""), "left": len(self.pending)}

    def finish_approved(self) -> dict:
        """Cut the approved photos and pull the marked videos, then let the page
        try Proceed again."""
        with self.lock:
            if self.finishing and self.finishing.get("running"):
                return {"error": "that work is already running", "finishing": self.finishing}
            prof = self._prof()
            pending = SK_pending(prof)
            if not (pending["photos"] or pending["videos"]):
                return {"error": "there is nothing waiting to be processed"}
            self.finishing = {"running": True, "line": "starting …", "done": None,
                              "pending": pending, "phase": "", "at": 0, "of": 0,
                              "started": time.time(), "eta": None}

        def work():
            from face_training import seek as SK
            try:
                r = SK.finish_approved(prof, say=self._finish_line, on_step=self._finish_step)
                line = (f"{r['photos']}/{r['photo_files']} approved photo(s) cut"
                        + (f", {r['frames_kept']} frame(s) kept from "
                           f"{r['videos']} marked video(s)" if r["videos"] else ""))
                with self.lock:
                    self.finishing = {"running": False, "line": line, "done": r}
            except Exception as e:                             # noqa: BLE001
                log.exception("finishing the approved work failed")
                with self.lock:
                    self.finishing = {"running": False, "line": f"it failed: {e}",
                                      "done": {"errors": [str(e)]}}

        threading.Thread(target=work, daemon=True).start()
        return {"started": True, "finishing": self.finishing}

    def _finish_step(self, phase: str, at: int, of: int, name: str = ""):
        """How far the processing has got, with a guess at the time left.

        The guess is simply how long the ones done so far took, spread over the
        ones that are left - the only honest way to do it without knowing what
        is in each video (user asked for a progress bar, 2026-09-17).
        """
        with self.lock:
            f = self.finishing or {}
            started = f.get("started") or time.time()
            eta = None
            if at > 0 and of > at:
                eta = int((time.time() - started) / at * (of - at))
            self.finishing = dict(f, running=True, phase=phase, at=at, of=of,
                                  now=name, eta=eta,
                                  line=f"{phase}: {at} of {of}" + (f" — {name}" if name else ""))

    def _finish_line(self, line: str):
        with self.lock:
            if self.finishing:
                self.finishing = dict(self.finishing, line=line)
        log.info("finishing: %s", line)

    def finish_all(self):
        """Carry out every answer still waiting - the page is going away, so
        there is nothing left that could take them back."""
        with self.lock:
            while self.pending:
                e = self.pending.pop(0)
                try:
                    self._finalise(e)
                except Exception:                              # noqa: BLE001
                    log.exception("could not finish answer %s", e.get("name"))
            self._save_pending()

    def undo_state(self) -> dict:
        last = self.pending[-1] if self.pending else None
        return {"n": len(self.pending),
                "last": (last or {}).get("said", ""),
                "name": (last or {}).get("name", "")}

    # --- uncertain videos and photos -----------------------------------
    def unsure_answer(self, kind: str, name: str, answer: str, seconds=None,
                      fps=None) -> dict:
        """One answer about an uncertain video or photo.

        The answer is written into her search history straight away. What it
        DOES waits until it is out of Undo's reach (_finalise), so no picture is
        deleted while the button can still bring it back (user, 2026-09-17).

        video + "appears": the moment showing in the player is written down as
        where the next search should start that video, instead of the beginning
        - the user marks the first frame she is on, so the search has her face
          and place to work from and does not re-read what came before.
        video + "not_her": the copy goes, and both facts go into her search
        history - that she said it is not her, and that the copy was removed.
        photo + "yes"/"not_her": the answer teaches the judge (facebank.apply_review).
        photo + "her_unused": it IS her, and she is not to be used. Recorded and
        nothing else - the judge is not told, and a later search does not offer
        the picture again (user, 2026-09-17).
        photo + "duplicate": the same picture again. Recorded, deleted, and not
        offered again; the judge is not told.
        """
        with self.lock:
            prof = self._prof()
            hist = SH.History(prof.history_path)
            path = self._unsure_path(kind, name)
            ref = uuid.uuid4().hex[:12]
            if kind == "video":
                if answer == "appears":
                    frame = None
                    if seconds is not None:
                        # the page knows the moment showing; the frame rate comes
                        # from the video itself, so the frame number is the one
                        # the search counts in
                        if not fps:
                            cap = cv2.VideoCapture(path)
                            fps = cap.get(cv2.CAP_PROP_FPS) or 0
                            cap.release()
                        if fps:
                            frame = max(0, int(round(float(seconds) * float(fps))))
                    said = (f"{name}: the next search starts at "
                            f"{float(seconds or 0):.2f}s"
                            + (f" (frame {frame})" if frame is not None else ""))
                    hist.log("uncertain_video_answered", video=name, answer="in it",
                             seconds=(None if seconds is None else round(float(seconds), 3)),
                             start_frame=frame, fps=(round(float(fps), 3) if fps else None),
                             ref=ref,
                             meaning="the next search starts this video here")
                    hist.save()
                    self._stage({"ref": ref, "kind": kind, "name": name,
                                 "answer": answer, "said": said}, None)
                    return {"ok": True, "name": name, "start_frame": frame,
                            "seconds": seconds, "said": said, "undo": self.undo_state()}
                if answer == "not_her":
                    said = f"{name}: not her - the copy is being deleted"
                    hist.log("uncertain_video_answered", video=name, answer="not her",
                             ref=ref,
                             meaning="not this person; the copy is deleted")
                    hist.save()
                    self._stage({"ref": ref, "kind": kind, "name": name,
                                 "answer": answer, "said": said}, path)
                    return {"ok": True, "name": name, "said": said,
                            "undo": self.undo_state()}
                raise ValueError(f"unknown answer {answer!r}")

            if kind == "photo":
                meanings = {
                    "yes": ("it is her", "kept for cropping"),
                    "not_her": ("not her", "deleted"),
                    "her_unused": ("her, not used",
                                   "recorded only: the copy is deleted, the app's "
                                   "idea of her face is unchanged, and it is not "
                                   "offered again"),
                    "duplicate": ("duplicate",
                                  "the same picture again: the copy is deleted and "
                                  "it is not offered again"),
                }
                if answer not in meanings:
                    raise ValueError(f"unknown answer {answer!r}")
                verdict, meaning = meanings[answer]
                said = {"yes": f"{name}: kept as her",
                        "not_her": f"{name}: not her - the copy is being deleted",
                        "her_unused": f"{name}: her, but not used - recorded only, "
                                      f"nothing learned from it",
                        "duplicate": f"{name}: duplicate - the copy is being deleted",
                        }[answer]
                hist.log("uncertain_photo_answered", photo=name, answer=verdict,
                         ref=ref, meaning=meaning)
                hist.save()
                self._stage({"ref": ref, "kind": kind, "name": name,
                             "answer": answer, "said": said}, path)
                return {"ok": True, "name": name, "is_her": answer in ("yes", "her_unused"),
                        "said": said, "undo": self.undo_state()}
            raise ValueError(f"unknown kind {kind!r}")

    def delete(self, items: list[dict]) -> dict:
        done, errors = [], []
        with self.lock:
            hist = self._history()
            for it in items:
                rel = f"{it.get('kind')}/{it.get('name')}"
                try:
                    p = self._path(it.get("kind"), it.get("name"))
                except (ValueError, FileNotFoundError) as e:
                    errors.append(str(e))
                    continue
                txt = os.path.splitext(p)[0] + ".txt"
                if not _recycle([p] + ([txt] if os.path.isfile(txt) else [])):
                    errors.append(f"{rel}: could not be moved to the Recycle Bin")
                    continue
                c = hist.crop(rel) or {}
                hsh = hist.mark_not_person(rel)
                hist.log("deleted_in_review", crop=rel, source=c.get("source", ""),
                         hash=hsh or "", meaning="not this person")
                hist.forget_crop(rel)
                done.append(rel)
            hist.save()
            if done:
                # Take the names off the crop snapshot too: otherwise the Face Tool
                # reads review deletions as complaints about crop margins and widens
                # every future crop (profiles.clean_deletions / nudge_crop_prefs).
                prof = self._prof()
                snap = prof.data.get("clean_snapshot")
                if snap:
                    for rel in done:
                        kind, name = rel.split("/", 1)
                        snap[kind] = [n for n in snap.get(kind, []) if n != name]
                prof.refresh_counts()
                prof.save()
        log.info("delete: %d done, %d errors %s", len(done), len(errors), errors)
        return {"deleted": done, "errors": errors}

    def duplicate_groups(self, kind: str, threshold: int) -> dict:
        """Group the crops in one section by HER FACE (user, 2026-09-17).

        The whole-picture check that used to do this is blind to her: on a body
        crop her face is 1.5-2% of the dots, so the room decided the answer.
        This uses the frame-pruning test instead - her face aligned, her head
        angle, and the look of face, eyes and mouth. It never deletes: it
        reports the groups and which copy of each holds the best view of her
        face, and the page ticks the rest for you to agree with or change.

        Finding her face costs about 0.4s a crop, so the first scan of a section
        measures them in the background and the page waits; afterwards it is
        instant. Groups already settled are left out.
        """
        if kind not in self.sub:
            raise ValueError(f"unknown crop kind {kind!r}")
        n = max(FG.NOTCH_MIN, min(FG.NOTCH_MAX, int(threshold)))
        prof = self._prof()
        points = FG.load_points(prof)
        todo = FG.missing(prof, kind, self.sub[kind], points)
        if todo:
            self._start_measuring(prof, kind, todo, points)
            return {"kind": kind, "threshold": n, "measuring": self.measuring}
        settled = self._settled_groups()
        groups = []
        for g in FG.groups(self.sub[kind], kind, points, n):
            if frozenset(f"{kind}/{m}" for m in g["members"]) in settled:
                continue
            groups.append(g)
        return {"kind": kind, "threshold": n, "groups": groups,
                "means": FG.describe(n)}

    def _start_measuring(self, prof, kind: str, todo: list, points: dict):
        """Find her face in the crops that have not been looked at yet."""
        with self.lock:
            if self.measuring and self.measuring.get("running"):
                return
            self.measuring = {"running": True, "kind": kind, "done": 0,
                              "total": len(todo)}

        def work():
            try:
                ident = Identity.load(prof.identity_dir)
                def step(done, total):
                    with self.lock:
                        self.measuring = {"running": True, "kind": kind,
                                          "done": done, "total": total}
                FG.measure(prof, todo, points, ident, on_step=step)
                FG.save_points(prof, points)
                with self.lock:
                    self.measuring = {"running": False, "kind": kind,
                                      "done": len(todo), "total": len(todo)}
                log.info("measured her face in %d %s crop(s)", len(todo), kind)
            except Exception as e:                             # noqa: BLE001
                log.exception("measuring her face failed")
                with self.lock:
                    self.measuring = {"running": False, "kind": kind, "error": str(e),
                                      "done": 0, "total": len(todo)}

        threading.Thread(target=work, daemon=True).start()

    def _settled_counts(self) -> dict:
        """How many groups in each section you have already dealt with.

        The page shows this so the work done is visible: a section that has been
        worked through looks the same as one that was never scanned otherwise
        (user, 2026-09-17).
        """
        out = {"head": 0, "body": 0}
        for members in self._settled_groups():
            for m in members:
                kind = m.split("/", 1)[0]
                if kind in out:
                    out[kind] += 1
                break
        return out

    def _settled_groups(self) -> set:
        """The groups already dealt with, as sets of "kind/name"."""
        hist = self._history()
        out = set()
        for e in hist.data.get("events", []):
            if (e.get("kind") == "duplicate_group_settled" and e.get("members")
                    and not e.get("undone")):
                out.add(frozenset(e["members"]))
        return out

    def settle_group(self, members: list[str], outcome: str, kept: str = "") -> dict:
        """Take one group off the queue and write down what happened to it."""
        with self.lock:
            hist = self._history()
            hist.log("duplicate_group_settled", members=sorted(members), outcome=outcome,
                     kept=kept, size=len(members),
                     meaning={"kept_all": "looked at and every picture kept",
                              "acted": "the ones ticked were dealt with; the rest kept",
                              }.get(outcome, outcome))
            hist.save()
        return {"settled": sorted(members), "outcome": outcome}

    def blur_others(self, items: list[dict]) -> dict:
        """Blur the other people's faces out of ticked crops (user, 2026-09-17).

        A yellow crop is one the cropper could not trim clean: the other face
        overlaps hers, or trimming it out would leave too little picture. The
        crop is her, so rather than lose it, every face that is not hers is
        blurred away where it stands. Blur, not a black box - a hard black
        rectangle is a shape the training would learn.
        """
        done, errors, still = [], [], 0
        with self.lock:
            prof = self._prof()
            ident = Identity.load(prof.identity_dir)
            hist = SH.History(prof.history_path)
            for it in items:
                rel = f"{it.get('kind')}/{it.get('name')}"
                try:
                    p = self._path(it.get("kind"), it.get("name"))
                except (ValueError, FileNotFoundError) as e:
                    errors.append(str(e))
                    continue
                img = cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)
                if img is None:
                    errors.append(f"{rel}: could not be read")
                    continue
                her, others = CG.split_her(CG.faces_in(img), ident.mean)
                if her is None:
                    errors.append(f"{rel}: her face could not be found in it")
                    continue
                if not others:
                    errors.append(f"{rel}: there is nobody else in it")
                    continue
                # Blurring the face box alone is not enough: on a real crop of
                # Susana's the detector still found the neighbour at 0.72
                # afterwards, because a face runs past the box the detector
                # draws round it. So it blurs, looks again, and blurs wider
                # until nobody is found (measured 2026-09-17).
                left = others
                for pad_frac in BLUR_PADS:
                    _apply_blur(img, left, pad_frac)
                    _her2, left = CG.split_her(CG.faces_in(img), ident.mean)
                    if not left:
                        break
                ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
                if not ok:
                    errors.append(f"{rel}: could not be saved")
                    continue
                buf.tofile(p)
                still += len(left)
                c = hist.crop(rel)
                if c is not None:
                    c["others_remain"] = len(left)
                    c["others_blurred"] = c.get("others_blurred", 0) + len(others)
                hist.log("others_blurred_in_review", crop=rel, blurred=len(others),
                         others_remain=len(left), source=(c or {}).get("source", ""),
                         meaning="other people's faces blurred out; the crop is kept")
                done.append(rel)
            hist.save()
        log.info("blur others: %d done, %d faces still found, %d errors %s",
                 len(done), still, len(errors), errors)
        return {"blurred": done, "others_remain": still, "errors": errors}

    def crops_not_used(self, items: list[dict]) -> dict:
        """"Yes - but don't use it", for finished crops (user, 2026-09-17).

        The same meaning it has on a photo: it IS her, it is not to be trained
        on, and nothing is learned from it. The crop goes to the Recycle Bin and
        the original is written into not_used, NOT into not_person - saying "do
        not use this picture" must never be recorded as "this is not her".
        """
        done, errors = [], []
        with self.lock:
            prof = self._prof()
            hist = SH.History(prof.history_path)
            for it in items:
                rel = f"{it.get('kind')}/{it.get('name')}"
                try:
                    p = self._path(it.get("kind"), it.get("name"))
                except (ValueError, FileNotFoundError) as e:
                    errors.append(str(e))
                    continue
                txt = os.path.splitext(p)[0] + ".txt"
                if not _recycle([p] + ([txt] if os.path.isfile(txt) else [])):
                    errors.append(f"{rel}: could not be moved to the Recycle Bin")
                    continue
                c = hist.crop(rel) or {}
                hist.mark_not_used(c.get("hash", ""), reason="crop_not_used",
                                   name=os.path.basename(p), source=c.get("source", ""))
                hist.log("crop_not_used_in_review", crop=rel, source=c.get("source", ""),
                         hash=c.get("hash", ""),
                         meaning="her, but not to be used: the crop is deleted, nothing is "
                                 "learned from it, and the photo is not marked as someone else")
                hist.forget_crop(rel)
                done.append(rel)
            hist.save()
            if done:
                snap = prof.data.get("clean_snapshot")
                if snap:
                    for rel in done:
                        kind, name = rel.split("/", 1)
                        snap[kind] = [n for n in snap.get(kind, []) if n != name]
                prof.refresh_counts()
                prof.save()
        log.info("crops not used: %d done, %d errors %s", len(done), len(errors), errors)
        return {"not_used": done, "errors": errors}

    def rotate(self, items: list[dict], direction: str) -> dict:
        if direction not in ("left", "right"):
            raise ValueError("direction must be left or right")
        code = cv2.ROTATE_90_COUNTERCLOCKWISE if direction == "left" else cv2.ROTATE_90_CLOCKWISE
        done, errors = [], []
        with self.lock:
            prof = self._prof()
            ident = Identity.load(prof.identity_dir)
            base = prof.caption_base()
            hist = SH.History(prof.history_path)
            for it in items:
                rel = f"{it.get('kind')}/{it.get('name')}"
                try:
                    p = self._path(it.get("kind"), it.get("name"))
                except (ValueError, FileNotFoundError) as e:
                    errors.append(str(e))
                    continue
                img = cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)
                if img is None:
                    errors.append(f"{rel}: could not be read")
                    continue
                rot = cv2.rotate(img, code)
                ok, buf = cv2.imencode(".jpg", rot, [cv2.IMWRITE_JPEG_QUALITY, 95])
                if not ok:
                    errors.append(f"{rel}: could not be saved")
                    continue
                buf.tofile(p)
                txt = os.path.splitext(p)[0] + ".txt"
                old = open(txt, encoding="utf-8").read().strip() if os.path.isfile(txt) else ""
                her, others = CG.split_her(CG.faces_in(rot), ident.mean)
                caption = old
                if her is not None:
                    keep_base = old.split(",")[0].strip() if old else base
                    caption = build_caption(keep_base, rot, her.bbox,
                                            getattr(her, "kps", None), rot.shape[0])
                    with open(txt, "w", encoding="utf-8") as fh:
                        fh.write(caption.strip() + "\n")
                c = hist.crop(rel)
                if c is not None:
                    c["turns_clockwise"] = (c.get("turns_clockwise", 0) + (1 if direction == "right" else -1)) % 4
                    if her is not None:
                        c["others_remain"] = len(others)
                hist.log(f"rotated_{direction}_in_review", crop=rel,
                         source=(c or {}).get("source", ""),
                         caption_remeasured=her is not None, caption=caption)
                done.append({"crop": rel, "caption_remeasured": her is not None})
            hist.save()
        log.info("rotate %s: %d done, %d errors %s", direction, len(done), len(errors), errors)
        return {"rotated": done, "errors": errors}

    def proceed(self) -> dict:
        # Training is the end of the review: every answer still waiting for Undo
        # stands (user, 2026-09-17). finish_all takes the same lock, so it runs
        # before this one is held.
        self.finish_all()
        with self.lock:
            if self.training and _pid_alive(self.training["pid"]):
                return {"error": "training is already running", "training": self.training}
            prof = self._prof()
            if prof.training_running():
                return {"error": "a training run for this person is already active"}
            pending = SK_pending(prof)
            if pending["photos"] or pending["videos"]:
                # Training would quietly leave out everything answered "yes"
                # (user, 2026-09-17). The page offers to do that work first.
                return {"needs_finishing": pending}
            prof.refresh_counts()
            head, body = prof.data["counts"]["clean_head"], prof.data["counts"]["clean_body"]
            if not (head or body):
                return {"error": "there are no crops to train on"}

            from face_training.pipeline import load_registry
            finished = [e for e in load_registry().get("people", {}).get(prof.slug, {})
                        .get("loras", {}).values() if not e.get("partial")]
            cmd = [sys.executable, "-m", "face_training.pipeline",
                   "--person", prof.data["display_name"],
                   "--folder", os.path.join(prof.dir, "clean"),
                   "--presorted", "--stop-file", prof._stop_flag]
            if finished:
                cmd.append("--retrain")      # replace the existing LoRAs as each new one finishes

            os.makedirs(TRAIN_LOG_DIR, exist_ok=True)
            log_path = os.path.join(TRAIN_LOG_DIR,
                                    f"train_{prof.slug}_{time.strftime('%Y%m%d_%H%M%S')}.log")
            fh = open(log_path, "w", encoding="utf-8")
            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = subprocess.Popen(cmd, cwd=REPO, stdout=fh, stderr=subprocess.STDOUT,
                                    creationflags=flags)

            prof.set_review_pending(False)
            prof.save()
            hist = SH.History(prof.history_path)
            hist.log("review_proceed", head=head, body=body, retrain=bool(finished),
                     training_pid=proc.pid, training_log=log_path)
            hist.save()
            self.training = {"pid": proc.pid, "log": log_path, "started": time.strftime("%H:%M:%S"),
                             "head": head, "body": body, "retrain": bool(finished)}
            log.info("proceed: training started pid %s log %s cmd %s", proc.pid, log_path, cmd)
            threading.Thread(target=self._watch_training, args=(proc, fh, time.time()),
                             daemon=True).start()
        return {"started": True, "training": self.training}

    def _recover_training(self, prof) -> dict | None:
        """Pick up a training run that was already going when this page started.

        The page used to lose sight of a run whenever its little server was
        restarted - the run itself carries on, since it is its own program, but
        the page showed nothing (user, 2026-09-17: the bar was added mid-run).
        The pipeline lock names the process, and the newest train log for this
        person is the one it is writing.
        """
        if not prof.training_running():
            return None
        try:
            from face_training.pipeline import WORK_ROOT, _lock_path
            with open(_lock_path(os.path.join(WORK_ROOT, self.slug)), encoding="utf-8") as fh:
                pid = int(fh.read().strip())
        except Exception:                                      # noqa: BLE001
            return None
        logs = sorted(glob.glob(os.path.join(TRAIN_LOG_DIR, f"train_{self.slug}_*.log")))
        if not logs:
            return None
        newest = logs[-1]
        started = os.path.basename(newest).rsplit("_", 1)[-1][:6]
        found = {"pid": pid, "log": newest, "crops": None, "recovered": True,
                 "started": f"{started[:2]}:{started[2:4]}:{started[4:6]}"}
        with self.lock:
            if self.training is None:
                self.training = found
                threading.Thread(target=self._watch_pid, args=(pid, time.time()),
                                 daemon=True).start()
                log.info("picked up the training run already going (pid %s, %s)", pid, newest)
        return self.training

    def _watch_pid(self, pid: int, started_at: float):
        """Wait for a recovered run to end, then record it like any other."""
        from face_training.pipeline import _pid_alive
        while _pid_alive(pid):
            time.sleep(5)
        self._record_training_end(None, started_at)

    def _watch_training(self, proc: subprocess.Popen, log_fh, started_at: float):
        """Wait for the run Proceed started, then record how it ended.

        The page asks /api/state every few seconds while training runs, so it
        shows the real ending - finished, stopped, or ended with errors -
        without a reload. It kept saying "Training is running" after a stop
        until someone reloaded it (window test, 2026-09-14), and this server
        used to shut down 2 minutes after Proceed, leaving nobody to ask.
        """
        rc = proc.wait()
        try:
            log_fh.close()
        except OSError:
            pass
        self._record_training_end(rc, started_at)

    def _record_training_end(self, rc, started_at: float):
        """Write down how a run ended - one path for runs this page started and
        runs it picked up afterwards."""
        outcome = None
        try:
            from face_training.pipeline import WORK_ROOT
            path = os.path.join(WORK_ROOT, self.slug, "last_run_summary.json")
            if os.path.isfile(path) and os.path.getmtime(path) >= started_at:
                with open(path, encoding="utf-8") as fh:
                    s = json.load(fh)
                loras = s.get("loras", [])
                outcome = {"stopped": bool(s.get("stopped")), "loras": len(loras),
                           "partial": sum(1 for e in loras if e.get("partial")),
                           "errors": list(s.get("errors", []))}
        except Exception:                                      # noqa: BLE001
            log.exception("could not read the run summary for %s", self.slug)
        # A stop request is spent once the run is over. The Face Tool clears it
        # the same way after the runs it starts itself.
        try:
            self._prof().clear_stop()
        except Exception:                                      # noqa: BLE001
            log.exception("could not clear the stop flag for %s", self.slug)
        with self.lock:
            self.training = dict(self.training, ended=time.strftime("%H:%M:%S"),
                                 exit=rc, outcome=outcome)
        try:
            hist = self._history()
            hist.log("training_ended", exit=rc, outcome=outcome,
                     training_log=self.training["log"])
            hist.save()
        except Exception:                                      # noqa: BLE001
            log.exception("could not write training_ended to the search history")
        log.info("training for %s ended: exit %s outcome %s", self.slug, rc, outcome)
        if self.on_training_end:
            self.on_training_end()


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def _handler(rv: Review):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj).encode("utf-8"), "application/json")

        def _send_file(self, path: str, ctype: str):
            """Send a file, or the piece of it the browser asked for.

            A video player asks for pieces as you drag its scrubber (a Range
            header). Sending the whole file every time, as this server used to,
            leaves the scrubber dead and re-sends a gigabyte to move a second."""
            size = os.path.getsize(path)
            rng = self.headers.get("Range", "")
            start, end = 0, size - 1
            partial = False
            if rng.startswith("bytes="):
                first, _, last = rng[6:].partition("-")
                try:
                    if first:
                        start = int(first)
                        end = int(last) if last else min(size - 1, start + 4 * 1024 * 1024 - 1)
                    elif last:                       # bytes=-N : the last N bytes
                        start = max(0, size - int(last))
                    partial = 0 <= start <= end < size
                except ValueError:
                    partial = False
            if not partial:
                start, end = 0, size - 1
            length = end - start + 1
            self.send_response(206 if partial else 200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(length))
            if partial:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            with open(path, "rb") as fh:
                fh.seek(start)
                left = length
                while left > 0:
                    chunk = fh.read(min(262144, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            try:
                if path in ("/", "/index.html"):
                    with open(PAGE, "rb") as fh:
                        return self._send(200, fh.read(), "text/html; charset=utf-8")
                if path == "/api/ping":
                    return self._json(200, {"ok": True})
                if path == "/api/state":
                    return self._json(200, rv.state())
                if path.startswith("/img/"):
                    parts = path.split("/", 3)
                    if len(parts) == 4:
                        p = rv._path(parts[2], urllib.parse.unquote(parts[3]))
                        with open(p, "rb") as fh:
                            ctype = "image/png" if p.lower().endswith(".png") else "image/jpeg"
                            return self._send(200, fh.read(), ctype)
                if path.startswith("/unsure/"):
                    parts = path.split("/", 3)
                    if len(parts) == 4:
                        p = rv._unsure_path(parts[2], urllib.parse.unquote(parts[3]))
                        low = p.lower()
                        ctype = ("video/mp4" if low.endswith((".mp4", ".m4v")) else
                                 "video/quicktime" if low.endswith(".mov") else
                                 "video/x-msvideo" if low.endswith(".avi") else
                                 "video/webm" if low.endswith(".webm") else
                                 "video/x-matroska" if low.endswith(".mkv") else
                                 "image/png" if low.endswith(".png") else "image/jpeg")
                        return self._send_file(p, ctype)
            except (ValueError, FileNotFoundError) as e:
                return self._json(404, {"error": str(e)})
            except ConnectionError:
                raise                   # the browser went away - nothing to answer
            except Exception as e:                             # noqa: BLE001
                # e.g. profile.json still refused after safe_replace's wait. This
                # used to drop the connection with the traceback on stderr only,
                # which nothing captures when the Face Tool starts this server.
                log.exception("GET %s failed", path)
                return self._json(500, {"error": str(e)})
            self._json(404, {"error": "not found"})

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path
            try:
                n = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(n) or b"{}")
                if path == "/api/delete":
                    return self._json(200, rv.delete(body.get("items", [])))
                if path == "/api/duplicate_scan":
                    return self._json(200, rv.duplicate_groups(
                        body.get("kind"), body.get("threshold", FG.NOTCH_DEFAULT)))
                if path == "/api/settle_group":
                    return self._json(200, rv.settle_group(
                        body.get("members", []), body.get("outcome", "acted"),
                        body.get("kept", "")))
                if path == "/api/blur_others":
                    return self._json(200, rv.blur_others(body.get("items", [])))
                if path == "/api/not_used":
                    return self._json(200, rv.crops_not_used(body.get("items", [])))
                if path == "/api/rotate":
                    return self._json(200, rv.rotate(body.get("items", []), body.get("direction")))
                if path == "/api/proceed":
                    return self._json(200, rv.proceed())
                if path == "/api/finish_approved":
                    return self._json(200, rv.finish_approved())
                if path == "/api/undo":
                    return self._json(200, rv.undo_last())
                if path == "/api/unsure":
                    return self._json(200, rv.unsure_answer(
                        body.get("kind"), body.get("name"), body.get("answer"),
                        seconds=body.get("seconds"), fps=body.get("fps")))
            except Exception as e:                             # noqa: BLE001
                log.exception("POST %s failed", path)
                return self._json(400, {"error": str(e)})
            self._json(404, {"error": "not found"})

        def log_message(self, fmt, *args):
            log.debug("http " + fmt, *args)

    return H


class _Server(ThreadingHTTPServer):
    # Windows hands the SAME port to a second server when the address may be
    # reused, and then splits requests between them at random - two review pages
    # for two people both answering on DEFAULT_PORT, each seeing half the
    # clicks (found while testing the fixed port, 2026-09-17). Refusing the
    # reuse is what makes the "port is taken" fallback below actually happen.
    allow_reuse_address = False


def main():
    ap = argparse.ArgumentParser(description="Review a person's crops before training")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help=f"the port to listen on (default {DEFAULT_PORT}); 0 = any free port")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()

    from face_training.logconsole import start_logging_console
    start_logging_console(f"review_{a.profile}")

    prof = P.Profile(a.profile)
    running = find_running(prof)
    if running:
        log.info("review page already open at %s", running["url"])
        if not a.no_browser:
            webbrowser.open(running["url"])
        return

    rv = Review(a.profile)
    try:
        server = _Server(("127.0.0.1", a.port), _handler(rv))
    except OSError as e:
        if not a.port:
            raise
        log.warning("port %s is taken (%s) - using any free port instead", a.port, e)
        server = _Server(("127.0.0.1", 0), _handler(rv))
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    with open(prof.review_server_file, "w", encoding="utf-8") as fh:
        json.dump({"pid": os.getpid(), "url": url, "started": time.strftime("%Y-%m-%dT%H:%M:%S")}, fh)
    rv.on_training_end = lambda: threading.Timer(SHUTDOWN_AFTER_TRAINING_S, server.shutdown).start()
    log.info("review page for %s: %s", a.profile, url)
    print(f"review page: {url}", flush=True) if sys.stdout else None
    if not a.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    finally:
        # Read, close, THEN remove. The remove used to run inside the `with`,
        # while the file was still open - Windows refuses that, and the error
        # was swallowed, so review_server.json outlived every clean shutdown
        # (test 2026-09-14). find_running's pid + ping check kept the stale file
        # harmless, but it is supposed to go.
        log.info("review server for %s shutting down", a.profile)
        try:
            rv.finish_all()      # the page is gone: answers waiting for Undo stand
        except Exception:                                      # noqa: BLE001
            log.exception("could not finish the answers that were waiting")
        try:
            with open(prof.review_server_file, encoding="utf-8") as fh:
                mine = json.load(fh).get("pid") == os.getpid()
            if mine:
                os.remove(prof.review_server_file)
                log.info("removed %s", prof.review_server_file)
            else:
                log.info("left %s alone - another review server wrote it",
                         prof.review_server_file)
        except (OSError, ValueError):
            log.exception("could not remove %s", prof.review_server_file)


if __name__ == "__main__":
    main()
