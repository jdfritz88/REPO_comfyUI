"""
Per-person profile store for the face tool.

One folder per person under PROFILES_ROOT:

    <slug>/
        profile.json          identity meta, seek folders, status, resume state
        identity/             mean.npy, refs.npy, refs.json  (see identity.py)
        clean/head/           final tight face crops + .txt captions
        clean/body/           final face+body crops + .txt captions
        found/               matched photos awaiting crop (staging; empties)
        scan_cache/          content-hashed face-detection cache per seek run
        video_and_frames/     videos she was matched in and their frames, one
                              subfolder per video: every frame of the stretches
                              she appears in (blurry and duplicate alike, pruned
                              by the frames stage after the search) plus a copy
                              of the video itself, which stays
                              (older profiles have this as video_frames/)
        uncertain/            copies of videos the search could not call
        train/               OneTrainer run dirs + LoRA outputs
        backup/               5 rotating snapshots of profile.json, identity/,
                              and scan_cache/faces.db (backup.py)

The launch window reads status() for each profile to show
"Updated" / "Resume" / "Start" and the list of trained LoRAs.

stdlib only (the window and the launcher both import this).
"""

from __future__ import annotations

import json
import os
import re
import time

from face_training.safe_replace import read_text, replace_file

from face_training.comfy_paths import PROFILES_ROOT  # our repo, never the app folder

# stages of a seek run, in order - the resume point is the first incomplete one
SEEK_STAGES = ("scan", "learn", "group", "reteach", "search", "frames", "clean", "dedupe")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower()) or "person"


# The word that names the person inside every caption, and that the Face Shelf
# emits into the prompt.
#
# "ohwx" was the convention borrowed from DreamBooth guides: a deliberately
# meaningless token so the model has no prior idea what it means. "lora" is
# readable instead - "lorasusana" says what it is to anyone reading a caption
# or a prompt, which matters because these captions are read by people here.
#
# Defined once, here. It used to be spelled out separately in profiles.create()
# and in pipeline.trigger_for(), which agreed only by coincidence: captions are
# built from the profile's stored trigger while the registry was written from
# the computed one, so the two could silently drift apart.
TRIGGER_PREFIX = "lora"


def trigger_for_slug(slug: str) -> str:
    return TRIGGER_PREFIX + slug


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class Profile:
    def __init__(self, slug: str):
        self.slug = slug
        self.dir = os.path.join(PROFILES_ROOT, slug)
        self.json_path = os.path.join(self.dir, "profile.json")
        self.data: dict = {}
        if os.path.isfile(self.json_path):
            self._load()

    # --- paths ---------------------------------------------------------
    @property
    def identity_dir(self):  return os.path.join(self.dir, "identity")
    @property
    def clean_head(self):    return os.path.join(self.dir, "clean", "head")
    @property
    def clean_body(self):    return os.path.join(self.dir, "clean", "body")
    @property
    def found_dir(self):     return os.path.join(self.dir, "found")
    @property
    def processed_dir(self): return os.path.join(self.dir, "processed")
    @property
    def videos_dir(self):    return os.path.join(self.dir, "videos")
    @property
    def backup_dir(self):    return os.path.join(self.dir, "backup")
    @property
    def needs_review_dir(self): return os.path.join(self.dir, "needs_review")
    @property
    def review_approved_dir(self):
        return os.path.join(self.dir, "needs_review", "_approved")
    @property
    def scan_cache_dir(self): return os.path.join(self.dir, "scan_cache")
    @property
    def video_frames_dir(self):
        """Videos she was matched in and the frames pulled from them, one folder
        per video.

        Every frame of the stretches she appears in is pulled here, blurry and
        duplicate alike, and a copy of the video itself is kept beside them -
        the user wants those video copies for other projects (2026-09-15). The
        frames stage prunes the frames after the search; the video copy stays.

        Named `video_and_frames` from 2026-09-15. A profile made before that has
        `video_frames`, and keeps using it, so nothing already gathered moves."""
        old = os.path.join(self.dir, "video_frames")
        if os.path.isdir(old):
            return old
        return os.path.join(self.dir, "video_and_frames")

    @property
    def uncertain_dir(self):
        """Videos the search could not call: a copy goes here rather than being
        passed over, so a person can look (user, 2026-09-15)."""
        return os.path.join(self.dir, "uncertain")
    @property
    def train_dir(self):     return os.path.join(self.dir, "train")
    @property
    def history_path(self):  return os.path.join(self.dir, "search_history.json")
    @property
    def review_server_file(self): return os.path.join(self.dir, "review_server.json")

    # --- the mandatory review between processing and training ---------------
    # Set when a Seek (or a whole background library run) finishes processing;
    # cleared only by Proceed on the review page, which then starts training.
    def review_pending(self) -> bool:
        return bool(self.data.get("review", {}).get("pending"))

    def set_review_pending(self, pending: bool):
        r = self.data.setdefault("review", {})
        r["pending"] = bool(pending)
        r["pending_since" if pending else "done_at"] = _now()

    def training_running(self) -> bool:
        """True while a training run for this person holds the pipeline lock."""
        try:
            from face_training.pipeline import WORK_ROOT, _lock_path, _pid_alive
            path = _lock_path(os.path.join(WORK_ROOT, self.slug))
            if not os.path.isfile(path):
                return False
            with open(path, encoding="utf-8") as fh:
                return _pid_alive(int(fh.read().strip()))
        except Exception:                                      # noqa: BLE001
            return False

    # --- io ----------------------------------------------------------
    def _load(self):
        # A Seek, the review page or the Face Tool may be swapping profile.json
        # in at this very moment - read_text waits that out (safe_replace.py).
        self.data = json.loads(read_text(self.json_path))

    def save(self):
        os.makedirs(self.dir, exist_ok=True)
        self.data["updated_at"] = _now()
        tmp = self.json_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2)
        # The Face Tool, backups and anything else may be reading profile.json
        # while a Seek rewrites it - see safe_replace.py.
        replace_file(tmp, self.json_path)

    # --- lifecycle -------------------------------------------------
    @staticmethod
    def create(display_name: str, seed_folder: str, best_photos) -> "Profile":
        if isinstance(best_photos, str):
            best_photos = [best_photos] if best_photos else []
        slug = slugify(display_name)
        p = Profile(slug)
        if os.path.isfile(p.json_path):
            raise FileExistsError(f"a profile named '{slug}' already exists")
        # every folder the app will ever write to, made up front - a run
        # should never be the thing that discovers a directory is missing
        for d in (p.dir, p.identity_dir, p.clean_head, p.clean_body,
                  p.found_dir, p.processed_dir, p.needs_review_dir,
                  p.review_approved_dir, p.videos_dir, p.backup_dir,
                  p.scan_cache_dir, p.video_frames_dir, p.uncertain_dir, p.train_dir,
                  *(os.path.join(p.processed_dir, o)
                    for o in ("cropped", "not_her", "no_face", "unreadable"))):
            os.makedirs(d, exist_ok=True)
        p.data = {
            "slug": slug,
            "display_name": display_name,
            "trigger": trigger_for_slug(slug),
            # The class word every caption and sample prompt is built on. It
            # was "woman" hard-coded in six places, which is silently wrong for
            # anyone who isn't one. Edit it here per person.
            "subject": "woman",
            "created_at": _now(),
            "seed_folder": seed_folder,
            "best_photo": best_photos[0] if best_photos else "",
            "best_photos": list(best_photos or []),
            "seek_folders": [],            # [{path, all_subdirs, last_run}]
            "identity": {"n_refs": 0, "built_at": None},
            "thresholds": {"match": 0.32},
            "seek": {"active": False, "stage": None, "progress": {},
                     "stop_requested": False, "last_run": None},
            "loras": {},                  # name -> {family, crop, file, thumb, trained_at}
            "counts": {"clean_head": 0, "clean_body": 0, "found_pending": 0},
        }
        p.save()
        return p

    def caption_base(self) -> str:
        """The part of every caption that names the person and nothing else.

        Framing, head angle and lighting are measured per photo and appended to
        this, so this must stay free of them - a base that already said "face
        portrait" would fight the framing that was actually measured.
        """
        return f"{self.data['trigger']} {self.data.get('subject', 'woman')}"

    def delete(self):
        import shutil
        if os.path.isdir(self.dir):
            shutil.rmtree(self.dir)

    # --- status for the launch window ---------------------------------
    def refresh_counts(self):
        def _imgs(d):
            return sum(1 for f in os.listdir(d)
                       if f.lower().endswith((".jpg", ".jpeg", ".png"))) if os.path.isdir(d) else 0
        self.data["counts"] = {
            "clean_head": _imgs(self.clean_head),
            "clean_body": _imgs(self.clean_body),
            "found_pending": _imgs(self.found_dir),
        }

    def seek_resume_stage(self) -> str | None:
        s = self.data.get("seek", {})
        if not s.get("stage"):
            return None
        prog = s.get("progress", {})
        for st in SEEK_STAGES:
            if not prog.get(st, {}).get("done_flag"):
                return st
        return None

    def status(self) -> dict:
        """-> {label: 'Updated'|'Resume'|'Start'|'Working', loras: [...], detail: str}"""
        self.refresh_counts()
        loras = sorted(self.data.get("loras", {}).values(),
                       key=lambda e: e.get("crop", "") + e.get("family", ""))
        seek = self.data.get("seek", {})

        if seek.get("active"):
            label, detail = "Working", f"seek: {seek.get('stage') or '...'}"
        elif self.training_running():
            label, detail = "Working", "training"
        elif self.seek_resume_stage():
            label = "Resume"
            detail = f"seek stopped at '{self.seek_resume_stage()}'"
        elif self.review_pending():
            label = "Review"
            detail = (f"{self.data['counts']['clean_head']} face + "
                      f"{self.data['counts']['clean_body']} body crops waiting for "
                      f"your review before training")
        elif not loras and self.data["counts"]["clean_head"] == 0 \
                and self.data["counts"]["clean_body"] == 0:
            label, detail = "Start", "nothing gathered yet"
        else:
            from face_training.jobs import job_specs
            want = len(job_specs(self.data["display_name"]))
            done = [e for e in loras if not e.get("partial")]
            partial = [e for e in loras if e.get("partial")]
            if len(done) >= want and want > 0 and not partial:
                label, detail = "Updated", f"{len(done)} LoRA(s), current"
            elif done or partial:
                label = "Resume"
                bits = [f"{len(done)}/{want} LoRA(s) trained"]
                if partial:
                    bits.append(f"{len(partial)} paused mid-training")
                detail = ", ".join(bits)
            else:
                label = "Resume"
                detail = (f"{self.data['counts']['clean_head']} face + "
                          f"{self.data['counts']['clean_body']} body photos, not trained")
        return {"label": label, "loras": loras, "detail": detail,
                "has_partial": any(e.get("partial") for e in loras)}

    # --- seek run state ------------------------------------------------
    # The stop flag is its own file, NOT a field in profile.json: the running
    # seek process rewrites profile.json constantly (progress), which would
    # clobber a flag the window set in between.
    @property
    def _stop_flag(self):
        return os.path.join(self.dir, "STOP")

    def request_stop(self):
        with open(self._stop_flag, "w", encoding="utf-8") as fh:
            fh.write(_now())

    def clear_stop(self):
        try:
            os.remove(self._stop_flag)
        except OSError:
            pass

    def stop_requested(self) -> bool:
        return os.path.isfile(self._stop_flag)

    # --- crop-preference learning (deletions from the Clean set) ---------
    def snapshot_clean(self):
        def names(d):
            return sorted(f for f in os.listdir(d)
                          if f.lower().endswith((".jpg", ".jpeg", ".png"))) if os.path.isdir(d) else []
        self.data["clean_snapshot"] = {
            "head": names(self.clean_head), "body": names(self.clean_body),
            "at": _now()}
        self.save()

    def clean_deletions(self) -> tuple[int, int, int]:
        """(kept, deleted_from_head, deleted_from_body) since the last snapshot."""
        snap = self.data.get("clean_snapshot")
        if not snap:
            return (0, 0, 0)
        def cur(d):
            return {f for f in os.listdir(d)
                    if f.lower().endswith((".jpg", ".jpeg", ".png"))} if os.path.isdir(d) else set()
        h_now, b_now = cur(self.clean_head), cur(self.clean_body)
        del_h = len(set(snap["head"]) - h_now)
        del_b = len(set(snap["body"]) - b_now)
        kept = len(h_now) + len(b_now)
        return (kept, del_h, del_b)


def all_profiles() -> list[Profile]:
    if not os.path.isdir(PROFILES_ROOT):
        return []
    out = []
    for name in sorted(os.listdir(PROFILES_ROOT)):
        p = Profile(name)
        if p.data:
            out.append(p)
    return out
