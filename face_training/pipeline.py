"""
Top-level face-training pipeline: one folder of a person's photos in, a set of
trained LoRAs + thumbnails + a shelf registry entry out.

Steps, in order:
  1. sort the photos into a "head" (close-ups) set and a "head_body" (all) set
  2. for each enabled (architecture family x crop) job, run OneTrainer headless
  3. copy each finished LoRA into ComfyUI/models/loras/faces/
  4. render one thumbnail per LoRA through the running ComfyUI
  5. write/refresh the face-shelf registry the shelf node reads

Runs in the OneTrainer venv. Invoked by the launcher's Training mode as:
  OneTrainer/venv/Scripts/python.exe -m face_training.pipeline --person NAME --folder DIR
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(_HERE) not in sys.path:
    sys.path.insert(0, os.path.dirname(_HERE))

from face_training import backup as BK
from face_training import profiles as P
from face_training import jobs as jobtable
from face_training.otrain import FAMILIES, Job, run_job
from face_training.sort_photos import recaption_folder, sort_folder
from face_training import thumbs
from face_training.safe_replace import read_text, replace_file

# Where a finished LoRA is published. comfy_paths owns this path - it is not
# spelled out here, so this file and thumbs.py and face_tool_ui.py cannot drift.
from face_training.comfy_paths import (COMFY_LORAS, FACES_DIR, THUMBS_DIR,
                                       REGISTRY, check_publish_path,
                                       check_publish_root)

# scratch that survives a run so a failed job can be retried without re-sorting
from face_training.comfy_paths import WORK_ROOT  # our repo, never the app folder

# LoRA alpha for every job (decided 2026-09-13). Rank comes from run()/--rank,
# default 16. See logs/onetrainer_master_reference.md section 3.
LORA_ALPHA = 1.0


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower()) or "person"


def trigger_for(name: str) -> str:
    """The person's trigger word. The profile owns it; this is the fallback.

    A profile stores its trigger when it is created, and captions are built
    from that stored value. If this computed it independently the two could
    disagree - and the failure would be silent, because training would read
    captions saying one word while the shelf emitted another. So: ask the
    profile first, and only compute when there is no profile (the launcher's
    quick "train from one folder" path has none).
    """
    s = slug(name)
    try:
        prof = P.Profile(s)
        if prof.data.get("trigger"):
            return prof.data["trigger"]
    except Exception:                                          # noqa: BLE001
        pass
    return P.trigger_for_slug(s)


class AlreadyRunning(RuntimeError):
    """Raised when a training run for this person is already in progress."""


def _lock_path(work: str) -> str:
    return os.path.join(work, "training.lock")


def _pid_alive(pid: int) -> bool:
    """Is this PID a real, live process right now?

    2026-09-09: two separate crashes each left an orphaned OneTrainer worker
    running unsupervised for hours, because killing a WRAPPER process on
    Windows does not kill its children, and a third launch was started by
    hand without checking whether an earlier one was still alive at all. All
    three shared the GPU with the real run the whole time, which is most of
    why that day's training took so long. This lock exists so that can never
    happen silently again."""
    try:
        import psutil
        return psutil.pid_exists(pid)
    except Exception:                                          # noqa: BLE001
        return False


def acquire_lock(work: str) -> str:
    """Claim the lock for this process, or raise AlreadyRunning if another
    live process already holds it. Returns the lock path to release later."""
    path = _lock_path(work)
    if os.path.isfile(path):
        try:
            held_pid = int(open(path, encoding="utf-8").read().strip())
        except (ValueError, OSError):
            held_pid = None
        if held_pid and held_pid != os.getpid() and _pid_alive(held_pid):
            raise AlreadyRunning(
                f"a training run for this person is already active (pid {held_pid}) - "
                f"not starting a second one. If you are certain nothing is really "
                f"running, delete {path} and try again.")
        # stale lock (process no longer exists, or unreadable) - safe to replace
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(str(os.getpid()))
    return path


def release_lock(path: str):
    """Remove the lock, but only if it is still ours - a lock that changed
    hands since we took it (should not happen, but never assume) is not ours
    to delete."""
    try:
        if os.path.isfile(path) and int(open(path, encoding="utf-8").read().strip()) == os.getpid():
            os.remove(path)
    except (ValueError, OSError):
        pass


def register_lora(person: str, trigger: str, entry: dict):
    """Read-modify-write the shelf registry for ONE finished LoRA, so a hard
    kill mid-run still leaves an accurate record."""
    reg = load_registry()
    slug_ = slug(person)
    reg["people"].setdefault(slug_, {"display_name": person, "loras": {}})
    reg["people"][slug_]["display_name"] = person
    reg["people"][slug_]["trigger"] = trigger
    reg["people"][slug_]["loras"][entry["name"]] = entry
    save_registry(reg)


def _ensure_captions(folder: str, base: str, ident=None):
    """Caption any image that arrived without one.

    A pre-sorted folder holds somebody else's crops, so nothing here knows how
    they were framed - it has to be measured from the crop like any other.
    Stamping one fixed string instead is what put a whole set under a single
    label, which is the thing a model cannot learn a person from.
    """
    if not os.path.isdir(folder):
        return
    recaption_folder(folder, base, missing_only=True, ident=ident)


def load_registry() -> dict:
    """The shelf registry, or an empty one when none has been written yet.

    A registry that exists but cannot be read is an error, not "empty":
    register_lora() writes back whatever this returns, so an empty stand-in
    erased every other person's LoRAs (Fix log, 2026-09-13). Another process
    swapping the file in is waited out by read_text (safe_replace.py).
    """
    if os.path.isfile(REGISTRY):
        try:
            return json.loads(read_text(REGISTRY))
        except (FileNotFoundError, ValueError):
            pass
    return {"version": 1, "people": {}}


def save_registry(reg: dict):
    os.makedirs(FACES_DIR, exist_ok=True)
    tmp = REGISTRY + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(reg, fh, indent=2)
    replace_file(tmp, REGISTRY)             # ComfyUI's Face Shelf may be reading it - safe_replace.py


def run(person: str, source_folder: str, target_steps: int = 2000,
        lora_rank: int = 16, only_family: str | None = None,
        do_thumbnails: bool = True, presorted: bool = False,
        stop_file: str | None = None, on_event=None,
        retrain: bool = False) -> dict:
    def say(msg):
        print(msg, flush=True)
        if on_event:
            on_event(msg)

    def stopping():
        return bool(stop_file) and os.path.isfile(stop_file)

    if stop_file and os.path.isfile(stop_file):
        try:
            os.remove(stop_file)          # clear any stale stop flag before we start
        except OSError:
            pass

    # Before anything is sorted or trained: prove the finished LoRA has a
    # correct place to go. A wrong path stops the run here rather than after
    # hours of training, and it can never fall back to the developer's folder.
    check_publish_root()

    person_slug = slug(person)
    trig = trigger_for(person)
    work = os.path.join(WORK_ROOT, person_slug)
    os.makedirs(work, exist_ok=True)
    lock_path = acquire_lock(work)          # raises AlreadyRunning if one is live
    try:
        return _run_locked(person, source_folder, target_steps, lora_rank,
                           only_family, do_thumbnails, presorted, stop_file,
                           say, stopping, person_slug, trig, work, retrain)
    finally:
        release_lock(lock_path)


def _run_locked(person, source_folder, target_steps, lora_rank, only_family,
                do_thumbnails, presorted, stop_file, say, stopping,
                person_slug, trig, work, retrain=False):
    os.makedirs(FACES_DIR, exist_ok=True)
    os.makedirs(THUMBS_DIR, exist_ok=True)

    # Names the person and nothing else - framing, head angle and lighting are
    # measured per photo and appended. The class word comes from the profile so
    # it is not "woman" for everyone; a person trained without a profile on
    # disk falls back to it.
    _prof = P.Profile(person_slug) if person_slug else None
    caption_base = (_prof.caption_base() if _prof and _prof.data
                    else f"{trig} woman")

    summary = {
        "person": person, "trigger": trig, "started": time.strftime("%Y-%m-%d %H:%M"),
        "source_folder": source_folder, "loras": [], "warnings": [], "errors": [],
        "disabled_families": jobtable.disabled_families(),
        "retrain": bool(retrain),
    }

    # 1. sort (or take a folder that Seek already sorted + cropped) -------
    def _count_jpgs(d):
        return sum(1 for f in os.listdir(d)
                   if f.lower().endswith((".jpg", ".jpeg", ".png"))) if os.path.isdir(d) else 0

    if presorted:
        # source_folder/head and source_folder/body are ready-made concept dirs
        head_dir = os.path.join(source_folder, "head")
        body_dir = os.path.join(source_folder, "body")
        if not os.path.isdir(head_dir) and not os.path.isdir(body_dir):
            raise ValueError(f"--presorted needs {source_folder}\\head and \\body")
        # captions may be missing - measure one for every image that lacks it
        ident = None
        if _prof and _prof.data and os.path.isfile(os.path.join(_prof.identity_dir, "mean.npy")):
            from face_training.identity import Identity
            ident = Identity.load(_prof.identity_dir)
        for d in (head_dir, body_dir):
            _ensure_captions(d, caption_base, ident)
        concept_dirs = {"head": head_dir, "head_body": body_dir}
        hc, bc = _count_jpgs(head_dir), _count_jpgs(body_dir)
        summary["head_count"], summary["head_body_count"] = hc, bc
        say(f"Using pre-sorted set: {hc} face crops, {bc} body crops")
        n_head = hc
    else:
        say(f"Sorting photos from {source_folder} ...")
        sr = sort_folder(
            source_folder=source_folder,
            work_dir=work,
            head_caption=caption_base,
            head_body_caption=caption_base,
        )
        summary["warnings"] += sr.warnings
        summary["head_count"] = len(sr.head_files)
        summary["head_body_count"] = len(sr.head_body_files)
        say(f"  close-ups: {len(sr.head_files)}   all usable: {len(sr.head_body_files)}")
        for w in sr.warnings:
            say("  ! " + w)
        concept_dirs = {"head": sr.head_dir, "head_body": sr.head_body_dir}
        n_head = len(sr.head_files)

    # 2 + 3. train each job --------------------------------------------------
    # The settings banner (text-encoder choice (c) and the rest) goes at the
    # top of every training log, so nobody reads a result without knowing them.
    from face_training.otrain import TRAINING_SETTINGS_BANNER
    for line in TRAINING_SETTINGS_BANNER.splitlines():
        say(line)
    specs = jobtable.job_specs(person)
    if only_family:
        specs = [(f, c) for (f, c) in specs if f == only_family]

    # which LoRAs are already finished (from an earlier run of this set)?
    #
    # Normally a finished LoRA is left alone, so a run that died halfway can be
    # started again without redoing hours of work. A RETRAIN is the opposite
    # request: the photos or the captions changed and the finished files are
    # the thing being replaced, so nothing counts as done. Without this, the
    # only way to retrain anyone was to edit the registry by hand - which is a
    # fix for one person on one night, not a fix for the app.
    already = {
        name for name, e in
        load_registry().get("people", {}).get(person_slug, {}).get("loras", {}).items()
        if not e.get("partial")}
    done_before = set() if retrain else already
    say(f"{len(specs)} LoRA(s) in the set: " +
        ", ".join(f"{c}/{f}" for f, c in specs)
        + (f"   (retraining - {len(already)} finished file(s) will be replaced)"
           if retrain and already else
           f"   ({len(done_before)} already done)" if done_before else ""))

    for i, (family, crop) in enumerate(specs, 1):
        if stopping():
            summary["stopped"] = True
            say(f"  stop requested - not starting {crop}/{family} or anything after it")
            break
        if crop == "head" and n_head == 0:
            summary["errors"].append(f"{crop}/{family}: no close-up photos, skipped")
            say(f"  [{i}/{len(specs)}] {crop}/{family}: SKIPPED - no close-ups")
            continue

        job = Job(
            person=person_slug, family=family, crop=crop,
            concept_dir=concept_dirs[crop], trigger=trig,
            out_dir=os.path.join(work, "loras"),
            work_root=work, target_steps=target_steps,
            subject=(_prof.data.get("subject", "woman") if _prof and _prof.data
                     else "woman"),
            # alpha is a learning-rate multiplier (alpha / rank), not a second
            # capacity dial. 1.0 matches OneTrainer's shipped SDXL LoRA preset;
            # alpha = rank had us training at 16-32x the authors' effective rate.
            lora_rank=lora_rank, lora_alpha=LORA_ALPHA,
        )

        if job.name in done_before and not job.has_checkpoint():
            say(f"  [{i}/{len(specs)}] {job.name}: already done, skipping")
            continue

        verb = "resuming" if job.has_checkpoint() else "training"
        say(f"  [{i}/{len(specs)}] {verb} {job.name}  "
            f"({FAMILIES[family]['label']}, {crop}) ...")
        res = run_job(job, on_line=lambda s: say("      " + s), stop_file=stop_file)
        if res.stopped_early:
            # Say what OneTrainer actually left on disk. This used to print
            # "checkpoint kept, will continue next time" for every stop, and a
            # stop before the first LoRA file was reported as FAILED - window
            # test 2026-09-14 stopped before step 1: no checkpoint, no LoRA,
            # and nothing had failed.
            summary["stopped"] = True
            kept = ("its checkpoint is kept - the next run continues from it"
                    if job.has_checkpoint() else
                    "no checkpoint was saved - the next run starts this LoRA over")
            if not res.ok:
                say(f"      stopped by request after {round(res.seconds)}s, before a "
                    f"LoRA file was written; {kept}")
                if i < len(specs):
                    say("  stop requested - not starting the rest of the set")
                break
            say(f"      stopped by request - the partial LoRA is kept; {kept}")
        elif res.resumed and res.ok:
            say(f"      resumed and finished")
        if not res.ok:
            summary["errors"].append(f"{job.name}: {res.error.splitlines()[0] if res.error else 'failed'}")
            say(f"      FAILED after {round(res.seconds)}s - see {res.log_path}")
            continue

        final = check_publish_path(
            os.path.join(FACES_DIR, job.name + ".safetensors"))
        shutil.copy2(res.out_path, final)
        say(f"      {round(res.seconds/60,1)} min -> {os.path.basename(final)}"
            + ("  (partial)" if res.stopped_early else ""))

        if not res.stopped_early:
            # LoRA finished - drop its checkpoint to free the disk
            if os.path.isdir(job.backup_dir):
                shutil.rmtree(job.backup_dir, ignore_errors=True)

        entry = {
            "name": job.name, "person": person, "family": family, "crop": crop,
            "family_label": FAMILIES[family]["label"],
            "lora_file": os.path.relpath(final, COMFY_LORAS).replace("/", "\\"),
            "trigger": trig, "steps": res.steps_done,
            "trained": time.strftime("%Y-%m-%d %H:%M"),
            "partial": res.stopped_early,
            "thumb": "",
        }
        register_lora(person, trig, entry)      # persist now, not just at the end
        summary["loras"].append(entry)
        if res.stopped_early:
            summary["stopped"] = True
            break

    # 4. thumbnails -------------------------------------------------------
    if do_thumbnails and summary["loras"]:
        if thumbs.comfy_up():
            say("Rendering thumbnails through ComfyUI ...")
            for entry in summary["loras"]:
                if entry.get("partial"):
                    continue          # an unfinished LoRA isn't worth a thumbnail
                dest = os.path.join(THUMBS_DIR, entry["name"] + ".png")
                try:
                    thumbs.render_thumb(
                        os.path.join(COMFY_LORAS, entry["lora_file"]),
                        entry["family"], entry["crop"], dest, caption_base)
                    entry["thumb"] = os.path.relpath(dest, FACES_DIR).replace("/", "\\")
                    say(f"  thumbnail: {os.path.basename(dest)}")
                except Exception as e:
                    summary["warnings"].append(f"thumbnail for {entry['name']}: {e}")
                    say(f"  ! thumbnail failed for {entry['name']}: {e}")
        else:
            summary["warnings"].append(
                "ComfyUI was not running - thumbnails skipped. Re-run with "
                "ComfyUI up, or they will render on first use of the shelf.")
            say("  ! ComfyUI not running - thumbnails skipped")

    # 5. registry - entries were written per-LoRA above; refresh thumbs here
    if summary["loras"]:
        for entry in summary["loras"]:
            register_lora(person, trig, entry)
        say(f"Registry updated: {REGISTRY}")
    else:
        say("Registry unchanged - no LoRA file was made this run")

    summary["finished"] = time.strftime("%Y-%m-%d %H:%M")
    with open(os.path.join(work, "last_run_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    # back up this person's tracking state (no-op if they have no profile -
    # e.g. the launcher's quick "Train a NEW face LoRA" path with no Seek)
    BK.backup_profile_by_slug(person_slug)
    return summary


def main():
    ap = argparse.ArgumentParser(description="Train face LoRAs from one photo folder")
    ap.add_argument("--person", required=True)
    ap.add_argument("--folder", required=True)
    ap.add_argument("--steps", type=int, default=2000)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--family", default=None, help="train only this family")
    ap.add_argument("--no-thumbnails", action="store_true")
    ap.add_argument("--presorted", action="store_true",
                    help="folder already has head/ and body/ subdirs of crops")
    ap.add_argument("--stop-file", default=None,
                    help="training stops (saving the partial LoRA) if this file appears")
    ap.add_argument("--retrain", action="store_true",
                    help="train every LoRA in the set again, replacing finished "
                         "files, instead of skipping the ones already done")
    a = ap.parse_args()

    if not os.path.isdir(a.folder):
        print("folder not found:", a.folder)
        sys.exit(2)

    try:
        s = run(a.person, a.folder, target_steps=a.steps, lora_rank=a.rank,
                only_family=a.family, do_thumbnails=not a.no_thumbnails,
                presorted=a.presorted, stop_file=a.stop_file,
                retrain=a.retrain)
    except AlreadyRunning as e:
        print(f"\nNot starting: {e}")
        sys.exit(3)

    print("\n==== SUMMARY ====")
    print(f"person   : {s['person']}   trigger: {s['trigger']}")
    print(f"photos   : {s.get('head_count', 0)} close-ups, {s.get('head_body_count', 0)} total")
    print(f"LoRAs    : {len(s['loras'])}")
    for e in s["loras"]:
        print(f"   {e['name']:32s} {e['lora_file']}   thumb={'yes' if e['thumb'] else 'no'}")
    if s.get("stopped"):
        print("stopped  : yes - by request (Stop button or stop file)")
    if s["errors"]:
        print("errors:")
        for e in s["errors"]:
            print("   " + e)
    if s["warnings"]:
        print("warnings:")
        for w in s["warnings"]:
            print("   " + w)
    sys.exit(1 if s["errors"] and not s["loras"] else 0)


if __name__ == "__main__":
    main()
