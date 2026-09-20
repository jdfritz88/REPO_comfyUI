"""
Seek: mine a folder for more photos of one person.

Stages, run in order, each one checkpointed so a Stop is always safe and a
Resume picks up at the first unfinished stage:

  scan     detect faces in every photo under the seek folder -> the cache; read
           every video in memory (the original sharpest-per-scene method) and
           record its frames' faces - no frame is saved. When group or search
           matches her in a video, that video is read again closely and every
           distinct angle and expression of her is saved into found/
           (video_frames.her_segments + pull_her_frames), and the frames stage
           prunes them
  learn    fold the confident solo matches into the identity model
  group    find her in multi-person photos, COPY each original into  found/
  reteach  rebuild the identity from the two chosen photos + her face in every capture
  search   copy every other original photo she appears in into  found/
  frames   prune the frames pulled from her videos: every blurred, unfocused,
           duplicate and near-duplicate frame is deleted, the sharpest of each
           angle and expression is kept
  clean    crop each  found/  photo (head + body) into the Clean set; every crop
           is checked for other people's faces and trimmed, or flagged
  dedupe   remove exact and near-identical crops, keeping the larger, sharper one

Nothing is cut from a library photo directly and no original is ever moved or
edited: every photo and video Seek finds is copied into found/ first (user,
2026-09-13). Every capture and crop is written to search_history.json.

When a run finishes processing, the profile is marked "review pending": nothing
trains until the person reviews the crops in the browser and clicks Proceed
(face_training/review_server.py). A background library run defers that to the
end of the whole run (--defer-review).

Progress and the stop flag live in the profile's profile.json, so the window
(a separate process) can ask a running Seek to stop, and a later run knows
exactly where to resume.

Runs in the OneTrainer venv.
"""

from __future__ import annotations

import glob
import logging
import os
import shutil
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(_HERE) not in sys.path:
    sys.path.insert(0, os.path.dirname(_HERE))

from face_training import backup as BK
from face_training import crop_guard as CG
from face_training import dedupe as DD
from face_training import facebank as FB
from face_training import profiles as P
from face_training import search_history as SH
from face_training.identity import Identity, build_identity
from face_training.recycle import recycle
from face_training.scan_cache import (ScanCache, content_hash, frame_key,
                                      frame_ref, parse_frame_ref, scan_folder)
from face_training.sort_photos import (
    HEAD_RATIO, MIN_CROP_PX, _body_strip_crop, _detect, _get_app, _load_bgr,
    build_caption, is_close_up,
    _loose_crop, _save_jpeg, _tight_head_crop,
)

from face_training.video_frames import (VIDEO_EXTS, her_segments, prune_her_frames,
                                        pull_her_frames)

log = logging.getLogger("face_training.seek")

LEARN_SIM = 0.45           # only very confident solo matches feed the identity

STAGES = P.SEEK_STAGES     # ("scan","learn","group","reteach","search","clean")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _pick_her(face_embs: list[np.ndarray], ident: Identity):
    """-> (index, best_sim, second_sim)"""
    sims = sorted(((i, ident.match_emb(e)) for i, e in enumerate(face_embs)),
                  key=lambda t: t[1], reverse=True)
    if not sims:
        return -1, 0.0, 0.0
    bi, best = sims[0]
    second = sims[1][1] if len(sims) > 1 else 0.0
    return bi, best, second


def _dest_name(clean_sub: str, src_path: str, hsh: str) -> str:
    stem = os.path.splitext(os.path.basename(src_path))[0]
    cand = os.path.join(clean_sub, stem + ".jpg")
    if os.path.exists(cand):
        cand = os.path.join(clean_sub, f"{stem}__{hsh[:8]}.jpg")
    return cand


def _move_into(src, dest_dir):
    """Move a file into a folder, never overwriting a different file there."""
    os.makedirs(dest_dir, exist_ok=True)
    name = os.path.basename(src)
    dest = os.path.join(dest_dir, name)
    if os.path.exists(dest):
        stem, ext = os.path.splitext(name)
        try:
            tag = content_hash(src)[:8]
        except OSError:
            tag = f"{int(time.time() * 1000) % 100000000:08d}"
        dest = os.path.join(dest_dir, f"{stem}__{tag}{ext}")
    try:
        shutil.move(src, dest)
        return dest
    except OSError:
        return None


def process_one(prof, src):
    """Crop one original into the Clean set exactly as the clean stage does,
    then retire it to processed/. Returns (made_head, made_body).

    Lives here rather than in the window so a photo a person approved goes
    through the identical path as one the run accepted on its own - the review
    screen decides WHICH photos are hers, never how they are cut.
    """
    img = _load_bgr(src)
    if img is None:
        _retire(prof, src, "unreadable")
        return (False, False)
    app = _get_app()
    faces = _detect(app, img)
    if not faces:
        _retire(prof, src, "no_face")
        return (False, False)

    ident = Identity.load(prof.identity_dir)
    embs = [f.normed_embedding for f in faces]
    idx, _best, _second = _pick_her(embs, ident)
    if idx < 0:
        _retire(prof, src, "no_face")
        return (False, False)

    her = faces[idx].bbox
    her_kps = getattr(faces[idx], "kps", None)
    others = [faces[j].bbox for j in range(len(faces)) if j != idx]
    ratio = (her[3] - her[1]) / img.shape[0]
    history = SH.History(prof.history_path)
    cap = history.capture(os.path.basename(src)) or {}
    made = _crop_into_clean(img, her, others, ratio,
                            prof.clean_head, prof.clean_body,
                            src, cap.get("hash") or content_hash(src),
                            prof.caption_base(), her_kps,
                            her_emb=faces[idx].normed_embedding, history=history,
                            capture=os.path.basename(src), source=cap.get("source"))
    _retire(prof, src, "cropped")
    history.set_outcome(os.path.basename(src), "cropped")
    history.save()
    return made


def _retire(prof, src, outcome):
    """Move a finished photo out of found/, filed by what happened to it.

    found/ used to empty by deletion: the moment a crop was written, the only
    local copy of the original went in the bin. That is fine until the crop
    turns out to be wrong - a strip that kept more pavement than person, a face
    the detector could not see - and then there is nothing left to re-cut from.
    The original has to be hunted down again out on the share, if it is even
    still there; one of ours was not.

    Keeping them costs disk and saves exactly that. Filing them by outcome also
    answers the question deletion destroyed: not just which photos were used,
    but which were looked at and turned down, and why.
    """
    _move_into(src, os.path.join(prof.processed_dir, outcome))


def _crop_into_clean(img, her_bbox, others, ratio, clean_head, clean_body,
                     src_path, hsh, base, her_kps=None, her_emb=None,
                     history=None, capture=None, source=None) -> tuple[bool, bool]:
    """close-ups feed both sets; wider shots feed only the body set.

    `ratio` is kept for the caller's logging; the close-up decision itself uses
    is_close_up(), which also lets through a face that is big in real pixels
    even when the shot is framed wide.

    Every crop then goes through crop_guard.only_her(): the finished crop is
    searched for other people's faces and trimmed until none are left, or kept
    and flagged when that is impossible (framed yellow on review). `her_emb` is
    her face in the source photo, which is how her face is told apart from the
    others inside the crop.

    `base` names the person; each crop's caption is measured on her face in the
    final crop, so the tags describe her and the framing matches what is saved."""
    made_head = made_body = False

    if is_close_up(her_bbox[3] - her_bbox[1], img.shape[0]):
        hc = _tight_head_crop(img, her_bbox, others)
        if hc is not None and hc.size and min(hc.shape[:2]) >= MIN_CROP_PX:
            made_head = _write_crop(hc, clean_head, "head", img, her_bbox, her_kps,
                                    src_path, hsh, base, her_emb, history, capture, source)

    if others:
        bc = _body_strip_crop(img, her_bbox, others)
    else:
        bc = img
    if bc is None or not bc.size or min(bc.shape[:2]) < MIN_CROP_PX:
        bc = _loose_crop(img, her_bbox)
    if bc is not None and bc.size and min(bc.shape[:2]) >= MIN_CROP_PX:
        made_body = _write_crop(bc, clean_body, "body", img, her_bbox, her_kps,
                                src_path, hsh, base, her_emb, history, capture, source)

    return made_head, made_body


def _write_crop(crop, sub, kind, img, her_bbox, her_kps, src_path, hsh, base,
                her_emb, history, capture, source) -> bool:
    guard = (CG.only_her(crop, her_emb) if her_emb is not None
             else {"img": crop, "others": 0, "her": None, "refined": False})
    out = guard["img"]
    her = guard["her"]
    if her is not None:
        caption = build_caption(base, out, her.bbox, getattr(her, "kps", None), out.shape[0])
    else:
        # her face could not be re-found inside the crop (too small for the
        # detector); measure from the source photo as before
        caption = build_caption(base, img, her_bbox, her_kps, crop.shape[0])
    dst = _dest_name(sub, src_path, hsh)
    _save_jpeg(out, dst, caption)
    if history is not None:
        history.add_crop(f"{kind}/{os.path.basename(dst)}", capture=capture,
                         source=source or src_path, hsh=hsh,
                         others_remain=guard["others"], refined=guard["refined"])
    return True


# --------------------------------------------------------------------------- #
# the orchestrator
# --------------------------------------------------------------------------- #
class Seek:
    def __init__(self, prof: P.Profile, seek_folder: str, recursive: bool,
                 on_event=None, defer_review: bool = False):
        self.prof = prof
        self.folder = seek_folder
        self.recursive = recursive
        self.on_event = on_event or (lambda s: None)
        self.defer_review = defer_review
        self.cache = ScanCache(os.path.join(prof.scan_cache_dir, "faces.db"))
        self.ident = Identity.load(prof.identity_dir)
        self.caption_base = prof.caption_base()
        self.history = SH.History(prof.history_path)
        # matched video frames waiting to be read out of their video, one video
        # at a time: (video path, [(decode index, cache key, stage), ...])
        self._fq_video: str | None = None
        self._fq_items: list[tuple[int, str, str]] = []
        # videos her frames were already taken from (by content hash), this run
        # or an earlier one - read closely once, not once per matching frame
        self._her_videos: set[str] = {
            c["hash"].rsplit(":f", 1)[0] for c in self.history.data["captures"].values()
            if ":f" in (c.get("hash") or "")}
        self._refresh_cutoff()
        # apply any learned crop-margin preferences
        cp = FB.load_crop_prefs()
        if cp:
            import face_training.sort_photos as _S
            if "head_expand" in cp:
                _S.HEAD_EXPAND.update(cp["head_expand"])
            if "body_side_pad" in cp:
                _S.BODY_SIDE_PAD = cp["body_side_pad"]

    def _refresh_cutoff(self):
        self_sims = (self.ident.ref_embeds @ self.ident.mean
                     if self.ident.ref_embeds is not None else None)
        self.cutoff = FB.adaptive_threshold(self.ident.mean, self_sims)

    def _judge(self, embs, source, multi_override=None):
        """-> (idx, is_her, borderline). Logs borderline calls, banks other faces."""
        idx, best, second = _pick_her(embs, self.ident)
        if idx < 0:
            return -1, False, False
        multi = (len(embs) > 1) if multi_override is None else multi_override
        is_her, borderline = FB.decide(best, second, multi, self.cutoff)
        if borderline:
            FB.log_decision(self.prof.slug, best, second, multi,
                            kept=is_her, source=source, borderline=True)
        if is_her:
            # the other faces in this frame are, by construction, other people
            others = [e for j, e in enumerate(embs) if j != idx]
            if others:
                FB.add_others(others, self.prof.slug, source)
        elif not multi and best < self.cutoff - 0.10:
            FB.add_others([embs[idx]], self.prof.slug, source)   # a clearly different solo person
        return idx, is_her, borderline

    def say(self, s: str):
        log.info(s)
        self.on_event(s)

    # --- progress / stop -------------------------------------------------
    def _seek_state(self) -> dict:
        return self.prof.data.setdefault("seek", {})

    def _mark(self, stage: str, **kv):
        prog = self._seek_state().setdefault("progress", {})
        prog.setdefault(stage, {}).update(kv)
        self._seek_state()["stage"] = stage
        self.prof.save()

    def _done(self, stage: str):
        self._mark(stage, done_flag=True)

    def _stopping(self) -> bool:
        return self.prof.stop_requested()

    # --- run -------------------------------------------------------------
    def run(self, resume: bool) -> dict:
        self.prof.clear_stop()             # any leftover stop flag
        s = self._seek_state()
        s.update({"active": True, "last_run": time.strftime("%Y-%m-%dT%H:%M:%S")})
        if not resume:
            s["progress"] = {}
        # register the seek folder
        sf = self.prof.data.setdefault("seek_folders", [])
        if not any(e["path"] == self.folder for e in sf):
            sf.append({"path": self.folder, "all_subdirs": self.recursive})
        self.prof.save()

        start_at = 0
        if resume:
            done = {st for st in STAGES
                    if s.get("progress", {}).get(st, {}).get("done_flag")}
            while start_at < len(STAGES) and STAGES[start_at] in done:
                start_at += 1

        result = {"stopped": False, "finished": False}
        try:
            for stage in STAGES[start_at:]:
                if self._stopping():
                    result["stopped"] = True
                    break
                self.say(f"--- stage: {stage} ---")
                # Record the stage as it STARTS. It used to be written only when a
                # stage ended, so the window said "seek: search" all through the
                # clean stage, and anything watching could not tell what was running.
                self._seek_state()["stage"] = stage
                self.prof.save()
                getattr(self, f"_stage_{stage}")()
                if self._stopping() and not self._seek_state()["progress"].get(stage, {}).get("done_flag"):
                    result["stopped"] = True
                    break
        finally:
            prog = self._seek_state().get("progress", {})
            result["finished"] = (not result["stopped"]
                                  and all(prog.get(st, {}).get("done_flag") for st in STAGES))
            self._seek_state()["active"] = False
            self.history.save()
            self.prof.refresh_counts()
            if result["finished"] and not self.defer_review:
                c = self.prof.data["counts"]
                if c["clean_head"] or c["clean_body"]:
                    self.prof.set_review_pending(True)
                    self.say("  processing finished - review the crops before training")
            self.prof.snapshot_clean()
            self.prof.save()
            self.prof.clear_stop()
            self.cache.close()
            if FB.train_judge():
                self.say(f"  judge retrained from {FB.judge_info()['rows']} of your Needs review answers")
            BK.backup_profile(self.prof.dir)
            self.say("  tracking state backed up")

        result["counts"] = self.prof.data["counts"]
        return result

    # --- stages --------------------------------------------------------
    def _stage_scan(self):
        def prog(i, t, sc, sk):
            self._mark("scan", done=i, total=t, scanned=sc, skipped=sk)
            self.say(f"  scan {i}/{t}  (new {sc}, cached {sk})")
        r = scan_folder(self.folder, self.recursive, self.cache,
                        stop_check=self._stopping, on_progress=prog,
                        scan_videos=True)
        vs = r.get("video_stats")
        if vs and vs["videos_found"]:
            self.say(f"  videos: {vs['videos_read']}/{vs['videos_found']} newly read, "
                     f"{vs['frames_recorded']} frames with faces recorded (no frame saved to disk)"
                     + (f", {vs['unreadable']} could not be read" if vs["unreadable"] else ""))
        self.say(f"  scanned {r['scanned']} new, {r['skipped']} cached, "
                 f"{self.cache.count()} total")
        if not r["stopped"]:
            self._done("scan")

    def _stage_learn(self):
        new_embs = []
        for hsh, path, ih, iw, faces in self.cache.iter_scanned():
            if len(faces) != 1:
                continue
            (x1, y1, x2, y2), det, emb = faces[0]
            if ih and (y2 - y1) / ih < HEAD_RATIO * 0.7:
                continue
            if self.ident.match_emb(emb) >= LEARN_SIM:
                new_embs.append(emb)
        if new_embs:
            self.say(f"  {len(new_embs)} confident solo matches -> identity")
            self.ident = build_identity(*self._anchors(), extra_embeds=np.stack(new_embs))
            self.ident.save(self.prof.identity_dir)
            self.prof.data["identity"] = {"n_refs": self.ident.n_refs,
                                          "built_at": P._now()}
        self._refresh_cutoff()
        self._done("learn")

    def _anchors(self):
        """(starter folder or "", [the chosen photos]) for build_identity."""
        d = self.prof.data
        photos = d.get("best_photos") or ([d["best_photo"]] if d.get("best_photo") else [])
        return d.get("seed_folder", "") or "", photos

    def _capture(self, hsh: str, path: str, stage: str) -> bool:
        """Copy one original photo into found/ and write it down.

        A copy, always: the original is never moved, renamed or edited."""
        if not os.path.isfile(path):
            return False
        os.makedirs(self.prof.found_dir, exist_ok=True)
        stem, ext = os.path.splitext(os.path.basename(path))
        dst = os.path.join(self.prof.found_dir, f"{stem}{ext}")
        if os.path.exists(dst):
            dst = os.path.join(self.prof.found_dir, f"{stem}__{hsh[:8]}{ext}")
        try:
            shutil.copy2(path, dst)
        except OSError as e:
            log.warning("could not copy %s into found/: %s", path, e)
            return False
        self.history.add_capture(os.path.basename(dst), source=path, hsh=hsh,
                                 stage=stage, video="")
        self.history.save()          # written at once, so a Stop never loses a capture
        return True

    def _take(self, hsh: str, path: str, stage: str, done: set) -> int:
        """A match: copy the photo now, or queue the video frame. -> photos/frames saved."""
        ref = parse_frame_ref(path)
        if ref is None:
            return 1 if self._capture(hsh, path, stage) else 0
        if hsh.rsplit(":f", 1)[0] in self._her_videos:
            return 0            # this video's frames of her are already taken
        saved = 0
        if self._fq_video is not None and self._fq_video != ref[0]:
            saved = self._flush_frames(done)
        self._fq_video = ref[0]
        self._fq_items.append((ref[1], hsh, stage))
        return saved

    def _video_copy(self, video: str, video_hash: str, dest_dir: str) -> str | None:
        """A copy of the video in dest_dir (made now if needed), or None.

        Videos travel with their frames (user, 2026-09-15): the copy lives in
        the same folder as the frames pulled from it and stays there, because
        the user wants those videos for other projects. Phone videos share names
        across folders (IMG_0001.MOV), so a same-named file already there is
        only reused when its content is this video - a frame must never be read
        out of the wrong one."""
        if not os.path.isfile(video):
            return None
        os.makedirs(dest_dir, exist_ok=True)
        stem, ext = os.path.splitext(os.path.basename(video))
        for name in (f"{stem}{ext}", f"{stem}__{video_hash[:8]}{ext}"):
            dst = os.path.join(dest_dir, name)
            if os.path.isfile(dst):
                try:
                    if content_hash(dst) == video_hash:
                        return dst
                except OSError:
                    pass
                continue
            try:
                shutil.copy2(video, dst)
                return dst
            except OSError as e:
                log.warning("could not copy video %s into found/: %s", video, e)
                return None
        return None

    def _her_index(self, embs):
        """Seek's own match rule for one frame -> (index of her face or -1, unsure).

        An unsure call is not her for the purpose of keeping frames (user,
        2026-09-15), but it is reported, so a video that was never clearly her
        yet left the search unsure is copied into uncertain/ for a person to
        look at. Nothing is logged or banked here - the scan frames already went
        through _judge."""
        i, best, second = _pick_her(embs, self.ident)
        if i < 0:
            return -1, False
        is_her, borderline = FB.decide(best, second, len(embs) > 1, self.cutoff)
        return (i if (is_her and not borderline) else -1), bool(borderline)

    def _frames_dir_for(self, video: str, video_hash: str) -> str:
        stem = os.path.splitext(os.path.basename(video))[0]
        return os.path.join(self.prof.video_frames_dir, f"{stem}__{video_hash[:8]}")

    def _flush_frames(self, done: set) -> int:
        """Pull every frame of the stretches she is in, from the one video
        queued, into its own folder under video_frames/ (user, 2026-09-15).

        The scan matched her in at least one of this video's frames. The video
        is copied into found/, then read again: faces are looked for twice a
        second to find where she is on screen, and EVERY frame of those
        stretches is written out - blurry and duplicate alike. The frames stage
        prunes them after the search. If she is never clearly there, nothing is
        pulled: a face that does not look like her is not her. If the video
        cannot be read, the queued frames are taken out of `done` so a resume
        tries again. -> frames pulled."""
        video, items = self._fq_video, self._fq_items
        self._fq_video, self._fq_items = None, []
        if not items:
            return 0
        video_hash = items[0][1].rsplit(":f", 1)[0]
        if video_hash in self._her_videos:
            return 0
        out_dir = self._frames_dir_for(video, video_hash)
        local = self._video_copy(video, video_hash, out_dir)
        read_from = local or (video if os.path.isfile(video) else None)
        start_at = self._video_marks().get(os.path.basename(video), 0)
        r = (her_segments(read_from, self._her_index, stop_check=self._stopping,
                          start_at=start_at)
             if read_from else {"error": "no readable copy"})
        if r.get("error"):
            log.warning("%s could not be read (%s) - will retry on resume", video, r["error"])
            for _i, key, _s in items:
                done.discard(key)
            return 0
        how = (f"{r['checks']} checks, she is in {r['checks_with_her']}, "
               f"{r.get('checks_unsure', 0)} unsure, {len(r['segments'])} stretch(es)")
        if not r["segments"]:
            # Nothing here is clearly her. If any check was unsure, the video
            # goes to uncertain/ for a person to look at rather than being
            # passed over (user, 2026-09-15); the frames folder, holding only
            # the copy of the video, is cleared away.
            unsure = r.get("checks_unsure", 0) > 0
            where = ""
            if unsure:
                kept = self._video_copy(video, video_hash, self.prof.uncertain_dir)
                where = f"; copied to uncertain/ as {os.path.basename(kept)}" if kept else \
                        "; could not copy it to uncertain/"
            shutil.rmtree(out_dir, ignore_errors=True)
            self._her_videos.add(video_hash)
            self.history.log("video_frames_pulled", video=video, pulled=0,
                             uncertain=unsure,
                             detail=how + "; never clearly her - nothing pulled" + where)
            self.history.save()
            self.say(f"  {os.path.basename(video)}: never clearly her - nothing pulled"
                     + (" (copy kept in uncertain/)" if unsure else ""))
            return 0
        stem = os.path.splitext(os.path.basename(video))[0]
        p = pull_her_frames(read_from, r["segments"], out_dir, stem, video_hash,
                            stop_check=self._stopping)
        if not p.get("stopped"):
            self._her_videos.add(video_hash)   # stopped halfway: pull it again on resume
        self.history.log("video_frames_pulled", video=video, pulled=p["saved"],
                         folder=os.path.basename(out_dir),
                         detail=how + f"; {p['saved']} frames pulled, {p['failed']} unreadable")
        self.history.save()
        self.say(f"  {os.path.basename(video)}: {p['saved']} frames pulled "
                 f"({how}) - blurry and duplicates are pruned after the search")
        return p["saved"]

    def _stage_group(self):
        """Multi-person photos she is in: copy each original into found/.

        This stage used to crop straight out of the library photo. Everything
        Seek finds is now copied into found/ first (user, 2026-09-13), so group
        photos are cut in the clean stage like every other capture, and every
        crop goes through the same other-people check."""
        done = set(self._seek_state()["progress"].get("group", {}).get("hashes", []))
        copied = 0
        for hsh, path, ih, iw, faces in self.cache.iter_scanned():
            if self._stopping():
                copied += self._flush_frames(done)
                self._mark("group", hashes=list(done), copied=copied)
                return
            if len(faces) < 2 or hsh in done:
                continue
            done.add(hsh)
            if self.history.skipped(hsh) or self.history.is_captured(hsh):
                continue        # not this person, or her but not to be used,
                                # or already copied
            embs = [f[2] for f in faces]
            idx, is_her, _borderline = self._judge(embs, path, multi_override=True)
            if not is_her:
                continue
            copied += self._take(hsh, path, "group", done)
        copied += self._flush_frames(done)
        self._mark("group", hashes=list(done), copied=copied)
        self.say(f"  group photos -> {copied} copied into found/ (photos; her videos "
                 f"and the frames pulled from them go to "
                 f"{os.path.basename(self.prof.video_frames_dir)}/)")
        self._done("group")

    def _stage_reteach(self):
        """Rebuild the identity from the chosen photos plus her face in every
        capture so far (her face picked by the current identity from the cached
        faces - the crops do not exist yet at this point)."""
        caps = self.history.captured_hashes()
        embs = []
        for hsh, path, ih, iw, faces in self.cache.iter_scanned():
            if hsh not in caps or not faces:
                continue
            idx, _best, _second = _pick_her([f[2] for f in faces], self.ident)
            if idx >= 0:
                embs.append(faces[idx][2])
        self.ident = build_identity(*self._anchors(),
                                    extra_embeds=np.stack(embs) if embs else None)
        self.ident.save(self.prof.identity_dir)
        self.prof.data["identity"] = {"n_refs": self.ident.n_refs, "built_at": P._now()}
        self._refresh_cutoff()
        self.say(f"  identity rebuilt from {self.ident.n_refs} faces "
                 f"(match cutoff {self.cutoff:.2f}, bank {FB.bank_size()})")
        self._done("reteach")

    def _stage_search(self):
        seen = set(self._seek_state()["progress"].get("search", {}).get("hashes", []))
        copied = 0
        for hsh, path, ih, iw, faces in self.cache.iter_scanned():
            if self._stopping():
                copied += self._flush_frames(seen)
                self._mark("search", hashes=list(seen), copied=copied)
                return
            if hsh in seen or not faces:
                continue
            seen.add(hsh)
            if self.history.skipped(hsh) or self.history.is_captured(hsh):
                continue        # not this person, or her but not to be used,
                                # or already copied
            embs = [f[2] for f in faces]
            idx, is_her, _borderline = self._judge(embs, path)
            if not is_her:
                continue
            copied += self._take(hsh, path, "search", seen)
        copied += self._flush_frames(seen)
        self._mark("search", hashes=list(seen), copied=copied)
        n_videos = len({c.get("video") for c in self.history.data["captures"].values()
                        if c.get("video")})
        self.say(f"  search -> {copied} photos and video frames copied into found/"
                 + (f" (from {n_videos} video(s) so far)" if n_videos else ""))
        self._done("search")

    def _video_marks(self) -> dict:
        """{video file name: frame to start at} from the review page.

        "She appears here" writes the moment into the search history. The user
        marks the first frame she is on, so the search starts the video there
        instead of the beginning (user, 2026-09-15)."""
        out = {}
        for e in self.history.data.get("events", []):
            if e.get("kind") == "uncertain_video_answered" and e.get("answer") == "in it":
                name = e.get("video")
                if name:
                    out[name] = int(e.get("start_frame") or 0)
        return out

    def _pull_marked_videos(self) -> int:
        """Pull frames from the videos a person marked on the review page.

        These are videos the search itself never called hers - they were set
        aside in uncertain/ and someone watched them and said she is there. The
        copy in uncertain/ is the video, so frames are pulled straight from it,
        starting where they said; the copy is then removed, because the video is
        kept beside its frames like any other."""
        marks = self._video_marks()
        if not marks:
            return 0
        pulled = 0
        step = getattr(self, "_on_video", None)
        for i, (name, start_at) in enumerate(sorted(marks.items())):
            if step:
                step(i, len(marks), name)
            src = os.path.join(self.prof.uncertain_dir, name)
            if not os.path.isfile(src) or self._stopping():
                continue
            try:
                vhash = content_hash(src)
            except OSError:
                continue
            if vhash in self._her_videos:
                continue
            out_dir = self._frames_dir_for(src, vhash)
            local = self._video_copy(src, vhash, out_dir)
            read_from = local or src
            r = her_segments(read_from, self._her_index, stop_check=self._stopping,
                             start_at=start_at)
            if r.get("error") or r.get("stopped"):
                continue
            if not r["segments"]:
                self.say(f"  {name}: marked as her at frame {start_at}, but no face there "
                         f"matched her - nothing pulled")
                self.history.log("marked_video_pulled", video=name, start_frame=start_at,
                                 pulled=0, detail="no stretch matched her")
                self.history.save()
                continue
            stem = os.path.splitext(name)[0]
            p = pull_her_frames(read_from, r["segments"], out_dir, stem, vhash,
                                stop_check=self._stopping)
            self._her_videos.add(vhash)
            recycle([src])          # the video now lives beside its frames
            pulled += p["saved"]
            self.say(f"  {name}: {p['saved']} frames pulled from frame {start_at} on "
                     f"(you marked her there)")
            self.history.log("marked_video_pulled", video=name, start_frame=start_at,
                             pulled=p["saved"], folder=os.path.basename(out_dir))
            self.history.save()
        return pulled

    def _stage_frames(self):
        """Prune the frames pulled out of her videos - after the search, as the
        user asked (2026-09-15).

        Every frame of the stretches she is in was pulled, blurry and duplicate
        alike. Here every blurred, unfocused, duplicate and near-duplicate frame
        is deleted and the sharpest of each angle and expression is kept. Her
        landmarks come from the folder's manifest, so no face is looked for
        again. Each survivor is written down as a capture, so the clean stage
        crops it like any other photo."""
        # first, the videos a person marked on the review page: the search never
        # called them hers, but someone watched them and said where she is
        self._pull_marked_videos()
        root = self.prof.video_frames_dir
        done = set(self._seek_state()["progress"].get("frames", {}).get("folders", []))
        pulled = removed = kept = 0
        if os.path.isdir(root):
            for name in sorted(os.listdir(root)):
                folder = os.path.join(root, name)
                if not os.path.isdir(folder) or name in done:
                    continue
                if self._stopping():
                    self._mark("frames", folders=list(done), kept=kept)
                    self.history.save()
                    return
                r = prune_her_frames(folder)
                done.add(name)
                pulled += r["started"]
                removed += r["blurry_removed"] + r["duplicates_removed"]
                kept += r["kept"]
                video = r.get("video") or ""
                vhash = r.get("video_hash") or name.rsplit("__", 1)[-1]
                for idx, path in r["kept_frames"]:
                    self.history.add_capture(os.path.basename(path),
                                             source=frame_ref(video, idx) if video else path,
                                             hsh=frame_key(vhash, idx), stage="frames",
                                             video=os.path.basename(video))
                self.history.log("video_frames_pruned", folder=name, started=r["started"],
                                 blurry_removed=r["blurry_removed"],
                                 duplicates_removed=r["duplicates_removed"], kept=r["kept"])
                self.history.save()
        self._mark("frames", folders=list(done), kept=kept)
        self.say(f"  frames -> {pulled} pulled frames checked, {removed} blurred or duplicate "
                 f"removed, {kept} kept")
        self._done("frames")

    def _pulled_frames(self) -> list[str]:
        """The frames that survived the frames stage, newest folder first."""
        root = self.prof.video_frames_dir
        out = []
        if os.path.isdir(root):
            for name in sorted(os.listdir(root)):
                d = os.path.join(root, name)
                if os.path.isdir(d):
                    out += [os.path.join(d, f) for f in sorted(os.listdir(d))
                            if f.lower().endswith(".jpg")]
        return out

    def _stage_clean(self):
        app = _get_app()
        entries = os.listdir(self.prof.found_dir) if os.path.isdir(self.prof.found_dir) else []
        files = [os.path.join(self.prof.found_dir, f) for f in entries
                 if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp"))]
        # the surviving video frames are cropped here too, from their own folder
        files += self._pulled_frames()
        if not files and not entries:
            self._done("clean")
            return
        # Videos travel the same path, but the frames she was matched in were
        # already read out of them and saved into found/ by the group and search
        # stages, and those frames are cropped as stills like any other photo.
        # So the video itself has nothing left to cut; it just needs to finish
        # its journey and be filed with everything else rather than sitting in
        # found/ for ever.
        vids = [f for f in entries if f.lower().endswith(VIDEO_EXTS)]
        for vf in vids:
            _retire(self.prof, os.path.join(self.prof.found_dir, vf), "cropped")
        if vids:
            self.say(f"  {len(vids)} video(s) filed into processed/ "
                     f"(their frames were cropped as stills)")
        made = 0
        for src in files:
            if self._stopping():
                self._mark("clean", remaining=len(files) - made)
                self.history.save()
                return
            # src is a full path: a copy in found/, or a frame that survived the
            # frames stage in video_frames/<video>/. Both are cropped the same
            # way and retired into processed/ when they are done.
            f = os.path.basename(src)
            img = _load_bgr(src)
            if img is None:
                _retire(self.prof, src, "unreadable")
                self.history.set_outcome(f, "unreadable")
                continue
            faces = _detect(app, img)
            if not faces:
                _retire(self.prof, src, "no_face")
                self.history.set_outcome(f, "no_face")
                continue
            embs = [x.normed_embedding for x in faces]
            idx, is_her, borderline = self._judge(embs, src)
            if borderline:
                # Too close to call. The original is still here, so hand it to a
                # person instead of guessing - guessing is what silently filled
                # the training set with photos of other people.
                os.makedirs(self.prof.needs_review_dir, exist_ok=True)
                _move_into(src, self.prof.needs_review_dir)
                self.history.set_outcome(f, "needs_review")
                continue
            if not is_her:
                _retire(self.prof, src, "not_her")
                self.history.set_outcome(f, "not_her")
                continue
            her = faces[idx].bbox
            her_kps = getattr(faces[idx], "kps", None)
            others = [faces[j].bbox for j in range(len(faces)) if j != idx]
            ratio = (her[3] - her[1]) / img.shape[0]
            cap = self.history.capture(f) or {}
            hsh = cap.get("hash") or content_hash(src)
            _crop_into_clean(img, her, others, ratio,
                             self.prof.clean_head, self.prof.clean_body,
                             src, hsh, self.caption_base, her_kps,
                             her_emb=faces[idx].normed_embedding, history=self.history,
                             capture=f, source=cap.get("source"))
            _retire(self.prof, src, "cropped")   # found/ empties as Clean fills
            self.history.set_outcome(f, "cropped")
            self.history.save()
            made += 1
        flagged = sum(1 for c in self.history.data["crops"].values() if c.get("others_remain"))
        self._mark("clean", made=made)
        self.say(f"  clean -> {made} photos cropped into the Clean set; "
                 f"{flagged} crop(s) still show other people's faces (framed yellow on review)")
        self._done("clean")

    def _stage_dedupe(self):
        """Remove exact and near-identical crops, keeping the larger, sharper one.

        The four earlier duplicate checks stay where they are (near-identical
        frames within one video, identical file content scanned once, the search
        stage skipping photos already handled, the other-faces bank). None of
        them sees the finished crops, which is where Susana's duplicates were.
        Removed copies are deleted outright (user, 2026-09-13)."""
        removed = 0
        for kind, sub in (("head", self.prof.clean_head), ("body", self.prof.clean_body)):
            if self._stopping():
                self.history.save()
                return
            for g in DD.find_duplicates(sub):
                keep_rel = f"{kind}/{os.path.basename(g['keep'])}"
                for p in g["remove"]:
                    rel = f"{kind}/{os.path.basename(p)}"
                    for q in (p, os.path.splitext(p)[0] + ".txt"):
                        try:
                            os.remove(q)
                        except FileNotFoundError:
                            pass
                    self.history.forget_crop(rel)
                    self.history.log("duplicate_removed", crop=rel, kept=keep_rel)
                    removed += 1
        removed_rev = self._dedupe_review_pile()
        self.history.save()
        self.say(f"  duplicates -> {removed} removed (kept the larger, sharper copy of each)")
        if removed_rev:
            self.say(f"  duplicates in the review pile -> {removed_rev} removed "
                     f"before anyone is asked about them")
        self._done("dedupe")

    def _dedupe_review_pile(self) -> int:
        """Clear duplicates out of needs_review/ before the review page opens.

        The pictures held back as too close to call are whole photos and whole
        video frames, not crops, so the crop check above never saw them and a
        person was handed the same picture over and over (user, 2026-09-17).
        Frames of one video are compared on the looser FRAME_DIFF_MAX; anything
        else on the ordinary crop rule. The copies that go are deleted outright,
        the same rule as duplicate crops, and each one is written down."""
        folder = self.prof.needs_review_dir
        if not os.path.isdir(folder):
            return 0
        removed = 0
        for g in DD.find_duplicates(folder):
            keep = os.path.basename(g["keep"])
            for path in g["remove"]:
                name = os.path.basename(path)
                try:
                    os.remove(path)
                except OSError as e:
                    log.warning("could not remove duplicate %s: %s", path, e)
                    continue
                self.history.set_outcome(name, "duplicate_removed")
                self.history.log("duplicate_removed", photo=name, kept=keep,
                                 where="needs_review",
                                 meaning="the same picture was already waiting for review")
                removed += 1
        return removed


def approved_waiting(prof) -> dict:
    """What a person approved on the review page that is not yet crops.

    -> {"photos": n, "videos": [names]}. Training must not start while either is
    waiting (user, 2026-09-17): a photo answered "Yes, it's her" sits in
    needs_review/_approved until it is cut, and a video answered "She appears
    here" keeps its copy in uncertain/ until her frames are pulled out of it, so
    both would simply be left out of the run.
    """
    photos = [f for f in glob.glob(os.path.join(prof.review_approved_dir, "*.*"))
              if os.path.isfile(f)]
    hist = SH.History(prof.history_path)
    videos = [n for n in sorted(standing_marks(hist))
              if os.path.isfile(os.path.join(prof.uncertain_dir, n))]
    # (a video whose frames have been pulled no longer has a copy in uncertain/)
    return {"photos": len(photos), "videos": videos}


def standing_marks(hist) -> dict:
    """{video name: the "she appears here" answer that still stands}.

    A mark stops standing when it is taken back, or when the app has already
    tried it and found nothing of her there: a video someone marked but whose
    faces still do not look like her must not sit in front of the training
    button for ever (found while testing, 2026-09-17). It goes back on the
    review page instead, with what happened written on it.
    """
    out = {}
    for e in hist.data.get("events", []):
        kind, name = e.get("kind"), e.get("video")
        if not name:
            continue
        if kind == "uncertain_video_answered" and e.get("answer") == "in it":
            if e.get("undone"):
                out.pop(name, None)
            else:
                out[name] = e
        elif kind == "marked_video_no_match":
            out.pop(name, None)
    return out


def finish_approved(prof, say=lambda s: None, on_step=lambda *a: None) -> dict:
    """Turn everything a person approved into crops, ready for training.

    Photos answered "Yes, it's her" are cut by process_one - the same cut a
    search makes. Videos answered "She appears here" have her frames pulled from
    the marked moment on, pruned of the blurry and the near-identical, and then
    cut the same way. Nothing here decides WHO is in a picture; the person
    already did that on the review page.
    """
    out = {"photos": 0, "photo_files": 0, "videos": 0, "frames_pulled": 0,
           "frames_kept": 0, "errors": []}
    files = sorted(f for f in glob.glob(os.path.join(prof.review_approved_dir, "*.*"))
                   if os.path.isfile(f))
    out["photo_files"] = len(files)
    for i, f in enumerate(files, 1):
        on_step("photos", i - 1, len(files), os.path.basename(f))
        try:
            h, b = process_one(prof, f)
            if h or b:
                out["photos"] += 1
        except Exception as exc:                               # noqa: BLE001
            log.exception("approved photo %s failed", f)
            out["errors"].append(f"{os.path.basename(f)}: {exc}")
        on_step("photos", i, len(files), os.path.basename(f))
    if files:
        say(f"{out['photos']}/{len(files)} approved photo(s) cut into the Clean set")

    waiting = approved_waiting(prof)["videos"]
    out["no_match"] = []
    if waiting:
        on_step("videos", 0, len(waiting), waiting[0])
        seek = Seek(prof, "", True, on_event=lambda s: say(s.strip()))
        seek._on_video = lambda done, total, name: on_step("videos", done, total, name)
        out["frames_pulled"] = seek._pull_marked_videos()
        on_step("videos", len(waiting), len(waiting), "")
        out["videos"] = len(waiting)
        # Prune and cut what was just pulled. A folder left over from the search
        # holds only its video and manifest - the frames it had were cropped and
        # retired - so a folder with frames in it is one of these.
        root = prof.video_frames_dir
        for name in sorted(os.listdir(root)) if os.path.isdir(root) else []:
            folder = os.path.join(root, name)
            if not os.path.isdir(folder):
                continue
            if not any(f.lower().endswith(".jpg") for f in os.listdir(folder)):
                continue
            r = prune_her_frames(folder)
            out["frames_kept"] += r["kept"]
            video, vhash = r.get("video") or "", r.get("video_hash") or ""
            seek.history.log("video_frames_pruned", folder=name, started=r["started"],
                             blurry_removed=r["blurry_removed"],
                             duplicates_removed=r["duplicates_removed"], kept=r["kept"])
            for k, (idx, path) in enumerate(r["kept_frames"], 1):
                on_step("frames", k, len(r["kept_frames"]), os.path.basename(path))
                seek.history.add_capture(os.path.basename(path),
                                         source=frame_ref(video, idx) if video else path,
                                         hsh=frame_key(vhash, idx), stage="approved_video",
                                         video=os.path.basename(video))
                try:
                    process_one(prof, path)
                except Exception as exc:                       # noqa: BLE001
                    log.exception("approved frame %s failed", path)
                    out["errors"].append(f"{os.path.basename(path)}: {exc}")
            seek.history.save()
        # A successful pull takes the copy out of uncertain/, so whatever is
        # still sitting there had nothing of her at the marked moment. Say so,
        # write it down, and let the video back onto the review page.
        marks = standing_marks(seek.history)
        for name in waiting:
            if not os.path.isfile(os.path.join(prof.uncertain_dir, name)):
                continue
            out["no_match"].append(name)
            seek.history.log("marked_video_no_match", video=name,
                             start_frame=int((marks.get(name) or {}).get("start_frame") or 0),
                             meaning="you marked her here, but no face in this video looked "
                                     "like her - nothing was pulled, and it is back on the "
                                     "review page")
        if out["no_match"]:
            seek.history.save()
        say(f"{out['frames_pulled']} frame(s) pulled from {out['videos']} marked video(s), "
            f"{out['frames_kept']} kept after the blurry and duplicate ones went"
            + (f"; {len(out['no_match'])} video(s) had nothing of her at the mark: "
               f"{', '.join(out['no_match'])}" if out["no_match"] else ""))
    prof.refresh_counts()
    prof.save()
    return out


def run_seek(slug: str, seek_folder: str, recursive: bool, resume: bool,
             on_event=None, defer_review: bool = False) -> dict:
    prof = P.Profile(slug)
    if not prof.data:
        raise ValueError(f"no profile '{slug}'")
    return Seek(prof, seek_folder, recursive, on_event, defer_review).run(resume)


EXIT_STOPPED = 3    # a Stop was honoured: progress is saved, Resume continues it


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Seek: mine a folder for a person's photos")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--seek-folder", required=True)
    ap.add_argument("--flat", action="store_true", help="this folder only")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--defer-review", action="store_true",
                    help="do not mark the review pending (a library run marks it once at the end)")
    a = ap.parse_args()
    from face_training.logconsole import start_logging_console
    start_logging_console(f"seek_{a.profile}")
    log.debug("seek start: profile=%s folder=%s recursive=%s resume=%s defer_review=%s",
              a.profile, a.seek_folder, not a.flat, a.resume, a.defer_review)
    r = run_seek(a.profile, a.seek_folder, not a.flat, a.resume,
                 on_event=lambda s: None, defer_review=a.defer_review)
    log.info("\n==== SEEK STOPPED - progress saved ====" if r.get("stopped")
             else "\n==== SEEK DONE ====")
    log.info("%s", r)
    # A stopped run must not look like a finished one: the library runner and
    # the Face Tool read this to decide between "Resume" and "Review".
    sys.exit(EXIT_STOPPED if r.get("stopped") else 0)
