"""
Walk a big photo library through Seek, one folder at a time, unattended.

Why this exists: a 27,000-photo network library is about eight hours of CPU
face detection. That is far too long to sit in front of, and far too long to
lose to a dropped network share or a reboot. This runs the folders in order,
oldest first, as separate processes, and writes down exactly where it got to
after every one.

What survives an interruption, in three layers:

  * every image      - scan_cache commits to SQLite after each file
  * every folder     - scan_cache.folders_done skips a finished folder without
                       opening a single file in it
  * every year       - progress.json here records which folders are done, so a
                       restart begins at the first one that is not

Each folder runs as its own child process. A crash on one bad file takes that
folder down, not the whole run - the loop notes the failure and carries on.

Note on `resume`: Seek's own --resume flag skips completed *stages*, and a
profile that has ever finished a run has them all marked done - so passing it
would skip everything. Each folder therefore runs as a fresh pipeline, and the
scan cache is what actually makes it resumable.

  python -m face_training.seek_library --profile susana \
      --root "\\\\PersonalCloud\\Public\\Photos & Videos"

Stop it cleanly by creating a file called STOP next to progress.json - it
finishes the folder it is on, then halts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import traceback

from face_training.safe_replace import read_text, replace_file

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(REPO, "logs", "seek")


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _folders(root: str, years_only: bool) -> list[str]:
    """Sub-folders in the order they should be worked: numbered years ascending
    first (2000, 2001, ...), then anything else alphabetically."""
    try:
        entries = [e for e in os.listdir(root) if os.path.isdir(os.path.join(root, e))]
    except OSError as e:
        sys.exit(f"cannot read {root}: {e}")
    years, others = [], []
    for e in entries:
        (years if re.fullmatch(r"(19|20)\d{2}", e.strip()) else others).append(e)
    years.sort(key=lambda s: int(s.strip()))
    others.sort(key=str.lower)
    ordered = years if years_only else years + others
    return [os.path.join(root, e) for e in ordered]


class Progress:
    """The run's own memory, rewritten after every folder."""

    def __init__(self, path: str):
        self.path = path
        self.data = {"folders": {}, "started_at": _now()}
        if os.path.isfile(path):
            # A progress file that exists but cannot be read is raised, not
            # replaced by a fresh one: the next set() would overwrite this run's
            # record of every folder already done. A brief lock while something
            # else has it is waited out by read_text (safe_replace.py).
            try:
                self.data = json.loads(read_text(path))
            except ValueError:
                pass
        self.data.setdefault("folders", {})

    def state(self, folder: str) -> str:
        return self.data["folders"].get(folder, {}).get("state", "pending")

    def set(self, folder: str, **kv):
        self.data["folders"].setdefault(folder, {}).update(kv)
        self.data["updated_at"] = _now()
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=1)
        replace_file(tmp, self.path)    # atomic - never a half-written file (safe_replace.py)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--years-only", action="store_true",
                    help="only 4-digit year folders, skipping iCloud dumps etc")
    ap.add_argument("--redo", action="store_true",
                    help="run folders already marked done in progress.json")
    ap.add_argument("--no-review-page", action="store_true",
                    help="mark the review pending at the end but do not open the page")
    a = ap.parse_args()
    from face_training import profiles as P
    from face_training.seek import EXIT_STOPPED

    os.makedirs(LOG_DIR, exist_ok=True)
    stop_file = os.path.join(LOG_DIR, "STOP")
    main_log = os.path.join(LOG_DIR, f"{a.profile}_run.log")

    def say(msg: str):
        line = f"{_now()}  {msg}"
        print(line, flush=True)
        with open(main_log, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def log_crash(exc_type, exc, tb):
        # Each folder's child already logs its own traceback to its folder
        # log; this is for the runner itself dying, which used to reach only
        # the console.
        say("RUNNER STOPPED BY AN UNHANDLED EXCEPTION - traceback follows")
        for tl in "".join(traceback.format_exception(exc_type, exc, tb)).rstrip().splitlines():
            say("    " + tl)

    sys.excepthook = log_crash

    # after the crash hook, so a progress file that cannot be read is reported
    # in the run log instead of only on the console
    prog = Progress(os.path.join(LOG_DIR, f"{a.profile}_progress.json"))

    folders = _folders(a.root, a.years_only)
    say(f"=== library run: {len(folders)} folders under {a.root}")
    todo = [f for f in folders if a.redo or prog.state(f) != "done"]
    say(f"    {len(folders) - len(todo)} already done, {len(todo)} to go")

    for i, folder in enumerate(todo, 1):
        if os.path.exists(stop_file):
            say("STOP file found - halting cleanly. Delete it and re-run to continue.")
            break
        if P.Profile(a.profile).stop_requested():
            say("Stop requested from the Face Tool - halting before the next folder. "
                "Re-run to continue.")
            break
        name = os.path.basename(folder)
        say(f"[{i}/{len(todo)}] {name} - starting")
        prog.set(folder, state="running", started_at=_now())
        t0 = time.time()
        folder_log = os.path.join(LOG_DIR, f"{a.profile}_{name}.log")
        try:
            with open(folder_log, "w", encoding="utf-8") as lf:
                r = subprocess.run(
                    [sys.executable, "-m", "face_training.seek",
                     "--profile", a.profile, "--seek-folder", folder,
                     # one review for the whole library, at the end - not one per folder
                     "--defer-review"],
                    cwd=REPO, stdout=lf, stderr=subprocess.STDOUT, text=True)
            code = r.returncode
        except Exception as e:                       # noqa: BLE001 - keep going
            code, e_msg = -1, str(e)
            say(f"    launch failed: {e_msg}")
        mins = (time.time() - t0) / 60
        if code == EXIT_STOPPED:
            # A stopped folder is NOT done: it used to exit 0 and be marked done,
            # so a re-run skipped the rest of it for ever.
            prog.set(folder, state="stopped", finished_at=_now(), minutes=round(mins, 1))
            say(f"    {name} STOPPED after {mins:.1f} min - progress saved; re-run to continue")
            break
        if code == 0:
            prog.set(folder, state="done", finished_at=_now(), minutes=round(mins, 1))
            say(f"    {name} done in {mins:.1f} min")
        else:
            prog.set(folder, state="failed", finished_at=_now(),
                     minutes=round(mins, 1), exit_code=code)
            say(f"    {name} FAILED (exit {code}) after {mins:.1f} min - see {folder_log}")

    done = sum(1 for f in folders if prog.state(f) == "done")
    say(f"=== finished this pass: {done}/{len(folders)} folders done overall")

    if folders and done == len(folders):
        prof = P.Profile(a.profile)
        prof.refresh_counts()
        c = prof.data["counts"]
        if c["clean_head"] or c["clean_body"]:
            prof.set_review_pending(True)
            prof.save()
            say(f"=== every folder processed: {c['clean_head']} face + {c['clean_body']} body "
                f"crops. Review them before training (nothing trains until Proceed).")
            if not a.no_review_page:
                subprocess.Popen([sys.executable, "-m", "face_training.review_server",
                                  "--profile", a.profile], cwd=REPO,
                                 creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))


if __name__ == "__main__":
    main()
