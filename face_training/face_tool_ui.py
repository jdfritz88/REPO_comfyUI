"""
Freedom Face Tool - the window.

A small tkinter window listing every face profile with its status
(Updated / Resume / Review / Start / Working) and its trained LoRAs, plus:
  +  add a person   - pick TWO clear photos of the face (no folder), then the
                      folder to search and whether to include subfolders; the
                      search starts at once
  Seek / Resume seek- mine a folder for photos of that person; Resume continues
                      a stopped search from where it saved
  Review crops      - the mandatory browser review (face_training/review_server.py);
                      training starts only from its Proceed button
  Train             - opens the review while one is pending
  Stop              - ask a running Seek/Train to stop and save its work

Launched by the stack launcher (option 4) with OneTrainer's pythonw.exe so it
runs in the environment that has insightface / torch / OneTrainer.

Runs in the OneTrainer venv.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

_HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(_HERE) not in sys.path:
    sys.path.insert(0, os.path.dirname(_HERE))


from face_training import backup as BK
from face_training import profiles as P
from face_training import seek as SK
from face_training.safe_replace import read_text
from face_training.video_frames import VIDEO_EXTS
from face_training.comfy_paths import REGISTRY

PY = sys.executable                       # OneTrainer venv python
REPO = os.path.dirname(_HERE)

log = logging.getLogger("face_training.face_tool_ui")

BADGE = {
    "Updated": "#2e7d3a",
    "Resume": "#b5872b",
    "Review":  "#8a6d00",
    "Start":   "#5a5a5a",
    "Working": "#26608b",
    "Error":   "#a33",
}

# how often the window checks whether a row's status has changed under it
REFRESH_MS = 3000


class FaceTool(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Freedom Face Tool")
        self.geometry("760x600")
        self.configure(bg="#1c1c1c")
        self.msgq: queue.Queue = queue.Queue()
        self._procs: dict[str, subprocess.Popen] = {}

        self.protocol("WM_DELETE_WINDOW", self.close)

        top = tk.Frame(self, bg="#1c1c1c")
        top.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(top, text="Face profiles", bg="#1c1c1c", fg="#cde3ff",
                 font=("Segoe UI", 12, "bold")).pack(side="left")
        tk.Button(top, text="Close", command=self.close).pack(side="right")
        tk.Button(top, text="Refresh", command=self.reload).pack(side="right", padx=6)
        tk.Button(top, text="+  Add person", command=self.add_person).pack(side="right", padx=6)

        self.listwrap = tk.Frame(self, bg="#141414")
        self.listwrap.pack(fill="both", expand=True, padx=10, pady=4)

        self.log = tk.Text(self, height=7, bg="#0f0f0f", fg="#bbb",
                           font=("Consolas", 9), wrap="word")
        self.log.pack(fill="x", padx=10, pady=(4, 10))
        self._logline("Face tool ready.")

        self.reload()
        self.after(200, self._drain)
        self._row_state = self._state_now()
        self.after(REFRESH_MS, self._tick)

    # --- logging / thread plumbing --------------------------------------
    def _logline(self, s: str):
        log.info(s.rstrip())
        self.log.insert("end", s.rstrip() + "\n")
        self.log.see("end")

    def report_callback_exception(self, exc, val, tb):
        # pythonw has no stderr, so Tk's own report of a failed button handler
        # went nowhere; put it in the log file with its traceback.
        log.error("unhandled error in a window callback", exc_info=(exc, val, tb))
        super().report_callback_exception(exc, val, tb)

    def _drain(self):
        # Re-armed in `finally`. It used to be re-armed after the try, so one
        # exception here (a profile.json that could not be read) stopped every
        # later log line, reload and review page for the life of the window
        # (Fix log, 2026-09-13). The error itself still reaches
        # report_callback_exception, which logs its traceback.
        try:
            while True:
                kind, payload = self.msgq.get_nowait()
                if kind == "log":
                    self._logline(payload)
                elif kind == "reload":
                    self.reload()
                elif kind == "open_review":
                    # Nothing trains straight after a Seek any more: the crops
                    # are reviewed first, and Proceed on that page starts training.
                    self.open_review(P.Profile(payload))
                elif kind == "start_seek":
                    slug, folder, recursive = payload
                    self.reload()
                    self._start_seek(P.Profile(slug), folder, recursive, resume=False)
        except queue.Empty:
            pass
        finally:
            self.after(200, self._drain)

    def _state_now(self):
        """What the rows are showing, in one comparable lump.

        A search or a training run is started by another process (and stopped
        from here), so the rows went stale the moment anything changed: a row
        drawn before a search started kept saying "Updated" with Stop greyed
        out until someone pressed Refresh, which is exactly how the user found
        Stop unusable while a search was running (2026-09-15)."""
        out = []
        for prof in P.all_profiles():
            try:
                st = prof.status()
                out.append((prof.slug, st["label"], st["detail"], len(st["loras"]),
                            st.get("has_partial", False), prof.review_pending()))
            except Exception:                                  # noqa: BLE001
                out.append((prof.slug, "?", "", 0, False, False))
        return out

    def _tick(self):
        """Redraw the rows when what they show has changed - never otherwise,
        so nothing flickers and a scrolled list stays put."""
        try:
            now = self._state_now()
            if now != self._row_state:
                self._row_state = now
                self.reload()
        except Exception:                                      # noqa: BLE001
            log.exception("row refresh failed")
        finally:
            self.after(REFRESH_MS, self._tick)

    def bg(self, fn, *a, **kw):
        threading.Thread(target=fn, args=a, kwargs=kw, daemon=True).start()

    # --- close -----------------------------------------------------------
    def close(self):
        try:
            done = BK.backup_all_profiles()
            self._logline(f"Backed up {len(done)} profile(s) before closing.")
        except Exception as e:
            self._logline(f"backup on close failed: {e}")
        self.destroy()

    # --- the list ------------------------------------------------------
    def reload(self):
        for w in self.listwrap.winfo_children():
            w.destroy()
        profs = P.all_profiles()
        if not profs:
            tk.Label(self.listwrap, text="No profiles yet. Click  +  Add person.",
                     bg="#141414", fg="#888", pady=20).pack()
            return
        canvas = tk.Canvas(self.listwrap, bg="#141414", highlightthickness=0)
        sb = ttk.Scrollbar(self.listwrap, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#141414")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        # The rows used to be pinned to 590px whatever the window was doing, so
        # widening the window did not give them a single extra pixel and the
        # last button stayed cut in half. Let them follow the canvas instead.
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw", width=590)
        canvas.bind("<Configure>",
                    lambda e, i=inner_id, c=canvas: c.itemconfigure(i, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # learn crop margins from any crops the user deleted since the last seek
        try:
            from face_training import facebank as FB
            for prof in profs:
                k, dh, db = prof.clean_deletions()
                if dh + db >= 5:
                    FB.nudge_crop_prefs(k, dh, db)
                    prof.snapshot_clean()
        except Exception:
            pass

        for prof in profs:
            self._row(inner, prof)

    def _row(self, parent, prof: P.Profile):
        # The registry next to the LoRA files is the truth about what has been
        # trained - it is what the pipeline reads to decide what to skip, and
        # what the face shelf reads to list a person. The profile only carried
        # a copy, refreshed after a training run in this window; anything that
        # rewrote profile.json afterwards (a Seek run does, constantly) wiped
        # it. Susana ended up showing "not trained" with four finished LoRAs on
        # the shelf. Re-read it here so the row can never disagree with disk.
        _sync_loras_from_registry(prof)
        st = prof.status()
        row = tk.Frame(parent, bg="#1e1e1e", bd=1, relief="solid")
        row.pack(fill="x", pady=4, padx=2)

        head = tk.Frame(row, bg="#1e1e1e")
        head.pack(fill="x", padx=8, pady=6)
        tk.Label(head, text=prof.data["display_name"], bg="#1e1e1e", fg="#eee",
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        tk.Label(head, text=f"  {st['label']}  ", bg=BADGE.get(st["label"], "#555"),
                 fg="#fff", font=("Segoe UI", 8, "bold")).pack(side="left", padx=8)
        tk.Label(head, text=st["detail"], bg="#1e1e1e", fg="#999",
                 font=("Segoe UI", 8)).pack(side="left")

        # The buttons get their own line under the name. Sharing the name's
        # line, a long status ("2 face + 8 body crops waiting for your review
        # before training") left them 300 px: Restore was squeezed to "esto"
        # and "Review crops" got no room at all, so it never appeared (window
        # test, 2026-09-14).
        btns = tk.Frame(row, bg="#1e1e1e")
        btns.pack(fill="x", padx=8, pady=(0, 6))
        working = st["label"] == "Working"
        resume_stage = prof.seek_resume_stage()
        seek_label = "Resume seek" if (resume_stage and not working) else "Seek"
        tk.Button(btns, text=seek_label, state=("disabled" if working else "normal"),
                  command=lambda p=prof, rs=bool(resume_stage): self.seek(p, rs)
                  ).pack(side="left", padx=2)
        # Three different things, so three different words on the button:
        # something is paused -> carry on from its checkpoint; everything is
        # finished -> do it all again with the photos as they are now; nothing
        # yet -> a first run.
        train_label = ("Resume training" if st.get("has_partial")
                       else "Retrain" if _finished_loras(st) else "Train")
        tk.Button(btns, text=train_label, state=("disabled" if working else "normal"),
                  command=lambda: self.train(prof)).pack(side="left", padx=2)
        tk.Button(btns, text="Stop", state=("normal" if working else "disabled"),
                  command=lambda: self.stop(prof)).pack(side="left", padx=2)
        tk.Button(btns, text="Backup", command=lambda p=prof: self.backup_now(p)
                  ).pack(side="left", padx=2)
        tk.Button(btns, text="Restore", command=lambda p=prof: self.restore_ui(p)
                  ).pack(side="left", padx=2)
        tk.Button(btns, text="Delete", state=("disabled" if working else "normal"),
                  command=lambda p=prof: self.delete_ui(p)).pack(side="left", padx=2)
        # One page in the browser now holds everything waiting on a person: the
        # crops before training, and the photos and videos the search could not
        # call (user, 2026-09-15 - the old Needs review window is gone). So the
        # button appears whenever any of those are waiting, not only for crops.
        waiting = _waiting_for_review(prof)
        if waiting and not working:
            tk.Button(btns, text="Review", command=lambda p=prof: self.open_review(p)
                      ).pack(side="left", padx=2)
            tk.Label(btns, text="  " + waiting, bg="#1e1e1e", fg="#9cc4ff",
                     font=("Segoe UI", 8)).pack(side="left")

        # Photos the search could not call used to have their own "Needs review"
        # button and window here. Both are gone: they are answered on the review
        # page beside the uncertain videos (user, 2026-09-15).
        n_ap = len([f for f in glob.glob(os.path.join(prof.review_approved_dir, "*.*"))
                    if os.path.isfile(f)])
        if n_ap:
            revbar = tk.Frame(row, bg="#1e1e1e")
            revbar.pack(fill="x", padx=8, pady=(0, 6))
            tk.Button(revbar, text=f"Process {n_ap} approved photo(s)",
                      command=lambda p=prof: self.process_approved(p)).pack(side="right", padx=2)

        if st["loras"]:
            body = tk.Frame(row, bg="#1e1e1e")
            body.pack(fill="x", padx=22, pady=(0, 6))
            for e in st["loras"]:
                tk.Label(body, text=f"- {e['name']}   ({e.get('family_label','')}, "
                                    f"{e.get('crop','')})   {e.get('trained','')}",
                         bg="#1e1e1e", fg="#9cc4ff", font=("Consolas", 8)
                         ).pack(anchor="w")

    # --- add a person -------------------------------------------------
    def add_person(self):
        name = _ask_text(self, "New person", "Person's name (e.g. Susana):")
        if not name:
            return
        if os.path.isdir(os.path.join(P.PROFILES_ROOT, P.slugify(name))):
            messagebox.showerror("Exists", f"A profile named '{P.slugify(name)}' already exists.")
            return
        # Exactly two clear photos of the face, and no starter folder (user,
        # 2026-09-13). Two, not one: a single photo is one lighting, one angle,
        # one day - if it is unflattering, every face gets judged against a
        # slightly wrong idea of the person, and nothing ever says so. Two also
        # let the app check them against each other and warn when they are not
        # the same person. There is no "carry on with one" any more.
        picked: list[str] = []
        while len(picked) < 2:
            n = len(picked) + 1
            label = "FIRST" if n == 1 else "SECOND (a different day / angle)"
            f = filedialog.askopenfilename(
                title=f"Choose the {label} clear photo of {name}'s face  ({n} of 2)",
                filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp"), ("All", "*.*")])
            if not f:
                if messagebox.askretrycancel(
                        "Two photos needed",
                        f"Adding {name} needs two clear photos of their face.\n\n"
                        f"Choose photo {n} of 2 again?"):
                    continue
                return
            if picked and os.path.normcase(os.path.abspath(f)) == \
                    os.path.normcase(os.path.abspath(picked[0])):
                messagebox.showwarning("Same photo", "That is the same file as the first "
                                       "photo. Choose a different photo of the same person.")
                continue
            picked.append(f)

        # Then where to search - and the search starts straight away.
        while True:
            folder = filedialog.askdirectory(title=f"Choose the folder to search for {name}")
            if folder:
                break
            if not messagebox.askretrycancel("Search folder needed",
                                             f"Choose the folder to search for {name}?"):
                return
        recursive = _ask_checkbox(self, "Subfolders",
                                  "Search all subfolders of that folder too?", default=True)

        self._logline(f"Creating profile '{name}' from the two photos ...")
        self.bg(self._do_add, name, picked, folder, recursive)

    def _do_add(self, name, photos, folder, recursive):
        try:
            from face_training.identity import build_identity
            # identity first: if neither photo shows a readable face this raises,
            # and no half-made profile is left behind
            ident = build_identity("", photos)
            prof = P.Profile.create(name, "", photos)
            ident.save(prof.identity_dir)
            prof.data["identity"] = {"n_refs": ident.n_refs, "built_at": P._now()}
            prof.save()
            self.msgq.put(("log", f"'{name}': identity built from {ident.n_refs} face(s)."))
            for w in ident.warnings:
                self.msgq.put(("log", "  ! " + w))
            self.msgq.put(("start_seek", (prof.slug, folder, recursive)))
        except Exception as e:
            self.msgq.put(("log", f"add person failed: {e}"))

    # --- review the photos Seek could not call ---------------------------
    def process_approved(self, prof: P.Profile):
        """Cut the photos answered "Yes, it's her" into the Clean set.

        The judging itself moved to the review page in the browser, beside the
        uncertain videos (user, 2026-09-15); the old Needs review window here is
        gone. A photo answered yes waits in needs_review/_approved until this
        turns it into crops, through the same path a search uses."""
        files = sorted(f for f in glob.glob(os.path.join(prof.review_approved_dir, "*.*"))
                       if os.path.isfile(f))
        if not files:
            messagebox.showinfo("Approved photos", "Nothing waiting to be processed.")
            return
        self._logline(f"'{prof.data['display_name']}': processing {len(files)} approved photo(s) ...")

        def work():
            made = 0
            for f in files:
                try:
                    h, b = SK.process_one(prof, f)
                    if h or b:
                        made += 1
                except Exception as exc:                       # noqa: BLE001
                    self.msgq.put(("log", f"approved: {os.path.basename(f)} failed: {exc}"))
            self.msgq.put(("log", f"approved: {made}/{len(files)} photo(s) cropped into the Clean set"))
            self.msgq.put(("reload", None))

        self.bg(work)

    # --- seek ------------------------------------------------------
    def seek(self, prof: P.Profile, resume: bool):
        if resume:
            sf = prof.data.get("seek_folders", [])
            if not sf:
                messagebox.showerror("Resume", "No recorded seek folder to resume.")
                return
            folder, recursive = sf[-1]["path"], sf[-1].get("all_subdirs", True)
            if not messagebox.askyesno(
                    "Resume seek",
                    f"Resume from stage '{prof.seek_resume_stage()}'\nfolder: {folder}?"):
                return
        else:
            folder = filedialog.askdirectory(
                title=f"Choose a folder to seek {prof.data['display_name']} in")
            if not folder:
                return
            recursive = _ask_checkbox(
                self, "Subfolders",
                "Search all subfolders of that folder too?", default=True)
        self._start_seek(prof, folder, recursive, resume)

    def _start_seek(self, prof: P.Profile, folder: str, recursive: bool, resume: bool):
        cmd = [PY, "-m", "face_training.seek", "--profile", prof.slug,
               "--seek-folder", folder]
        if not recursive:
            cmd.append("--flat")
        if resume:
            cmd.append("--resume")
        self._logline(("Resuming" if resume else "Starting") + " seek: " + " ".join(cmd))
        self.bg(self._run_stream, prof.slug, cmd, "seek")

    def open_review(self, prof: P.Profile):
        """Open the review page, or bring back the one already open."""
        from face_training import review_server as RS
        running = RS.find_running(prof)
        if running:
            import webbrowser
            webbrowser.open(running["url"])
            self._logline(f"'{prof.data['display_name']}': review page {running['url']}")
            return
        try:
            subprocess.Popen([PY, "-m", "face_training.review_server", "--profile", prof.slug],
                             cwd=REPO, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            self._logline(f"'{prof.data['display_name']}': opening the review page in the "
                          f"browser. Training starts from its Proceed button.")
        except Exception as e:
            log.exception("could not start the review page")
            self._logline(f"could not open the review page: {e}")

    # --- train ------------------------------------------------------
    def _review_gate(self, prof: P.Profile) -> bool:
        """Ask about unreviewed photos before training. True = go on training.

        A photo or video sitting in the uncertain piles is one the search could
        not call, and a photo sitting in _approved is one already judged to be
        her that has not been cut into the training set yet. Either way it is
        something that SHOULD be in the set and is not, and training does not
        mention them - it just quietly trains on what happens to be there. The
        whole point of keeping the originals was so that call gets made by
        someone who can see the face, and that only works if the app asks
        before the moment it stops mattering.

        The answering itself happens on the review page in the browser now
        (user, 2026-09-15), so "Yes" opens that page.
        """
        uncertain = _waiting_for_review(prof)
        approved = [f for f in glob.glob(os.path.join(prof.review_approved_dir, "*.*"))
                    if os.path.isfile(f)]
        if not uncertain and not approved:
            return True
        bits = []
        if uncertain:
            bits.append(uncertain + " waiting for your answer on the review page")
        if approved:
            bits.append(f"{len(approved)} photo(s) you already approved, not yet cut "
                        f"into the training set")
        msg = (f"{prof.data['display_name']} has:\n\n  - " + "\n  - ".join(bits) +
               "\n\nTraining now trains without them.\n\n"
               "Deal with them first?\n"
               "    Yes  -  open the review page (and cut any approved photos)\n"
               "    No   -  carry on and start training")
        if messagebox.askyesno("Review first?", msg, icon="question"):
            if approved:
                self.process_approved(prof)
            if uncertain:
                self.open_review(prof)
            return False
        return True

    def train(self, prof: P.Profile):
        if prof.review_pending():
            self._logline(f"'{prof.data['display_name']}': the crops have not been reviewed "
                          f"yet - training starts from the review page's Proceed button.")
            self.open_review(prof)
            return
        if not self._review_gate(prof):
            return
        head = prof.data["counts"]["clean_head"]
        body = prof.data["counts"]["clean_body"]
        st = prof.status()
        if head or body:
            folder = os.path.join(prof.dir, "clean")
            note = f"Train from the gathered Clean set ({head} face, {body} body photos)?"
            extra = ["--presorted"]
        else:
            messagebox.showinfo("Nothing to train",
                                f"{prof.data['display_name']} has no crops yet. Run Seek first.")
            return
        done = _finished_loras(st)
        retrain = bool(done) and not st.get("has_partial")
        if st.get("has_partial"):
            title = "Resume training"
            note = ("Resume: finished LoRAs are kept, the paused one continues "
                    "from its checkpoint, the rest train.\n\n" + note)
        elif retrain:
            title = "Retrain"
            note = (f"{prof.data['display_name']} already has {len(done)} finished "
                    f"LoRA(s):\n  " + "\n  ".join(sorted(e.get("name", "?") for e in done)) +
                    "\n\nRetrain replaces each of those files as its new version "
                    "finishes. The old file is gone once that happens.\n\n" + note)
        else:
            title = "Train"
        if not messagebox.askyesno(title, note):
            return
        cmd = [PY, "-m", "face_training.pipeline",
               "--person", prof.data["display_name"], "--folder", folder,
               "--stop-file", prof._stop_flag] + extra
        if retrain:
            cmd.append("--retrain")
        self._logline("Training: " + " ".join(cmd))
        self.bg(self._run_stream, prof.slug, cmd, "train")

    def _run_stream(self, slug, cmd, kind="job"):
        rc = -1
        try:
            proc = subprocess.Popen(cmd, cwd=REPO, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, bufsize=1)
            self._procs[slug] = proc
            for line in proc.stdout:
                s = line.strip()
                if s and not s.startswith(("step:", "epoch:")):
                    self.msgq.put(("log", s))
            proc.wait()
            rc = proc.returncode
            self.msgq.put(("log", f"[{slug}] {kind} finished (exit {rc})"))
        except Exception as e:
            log.exception("[%s] %s run failed: %s", slug, kind, cmd)
            self.msgq.put(("log", f"[{slug}] error: {e}"))
        finally:
            self._procs.pop(slug, None)
            try:
                P.Profile(slug).clear_stop()
            except Exception:
                pass
            if kind == "train" and rc in (0, 1):
                _sync_loras_from_registry(P.Profile(slug))
            self.msgq.put(("reload", None))
            if kind == "seek" and rc == 0 and P.Profile(slug).review_pending():
                self.msgq.put(("open_review", slug))
            elif kind == "seek" and rc == SK.EXIT_STOPPED:
                self.msgq.put(("log", f"[{slug}] seek stopped - progress saved. "
                                      f"Click 'Resume seek' to carry on from there."))

    def stop(self, prof: P.Profile):
        # Ask what is actually running for this person, not only what this
        # window started. Training started from the review page's Proceed is
        # the review server's child, so it was never in self._procs: Stop
        # stopped it and still said "Nothing running for that person" (window
        # test, 2026-09-14). Same tests the row uses to show "Working".
        fresh = P.Profile(prof.slug)
        pr = self._procs.get(prof.slug)
        mine = bool(pr and pr.poll() is None)
        seeking = bool(fresh.data.get("seek", {}).get("active"))
        training = fresh.training_running()
        name = prof.data["display_name"]
        if not (mine or seeking or training):
            self._logline("Nothing running for that person.")
            return
        prof.request_stop()
        if training:
            self._logline(f"Stopping '{name}'s training. The LoRA being trained keeps "
                          f"what it has learned so far (if it got past its first "
                          f"steps), then the run ends. Give it a moment.")
        elif seeking:
            self._logline(f"Stopping '{name}'s seek. It saves its place, then ends. "
                          f"Give it a moment.")
        else:
            self._logline(f"Stopping '{name}'. Give it a moment.")

    # --- manual backup / restore ------------------------------------------
    def backup_now(self, prof: P.Profile):
        dest = BK.backup_profile(prof.dir)
        if dest:
            self._logline(f"'{prof.data['display_name']}': backed up to {dest}")
        else:
            self._logline(f"'{prof.data['display_name']}': nothing to back up yet.")

    def delete_ui(self, prof: P.Profile):
        """Delete a person - all of them, or only the parts ticked.

        The user asked for a working Delete with a question about its assets:
        a radio button for all, or check boxes to pick (2026-09-15). Everything
        goes to the Recycle Bin, so a wrong click can be undone; the only thing
        that cannot is the person's line in the ComfyUI face-shelf registry,
        which is rewritten without them."""
        from face_training import delete_profile as DP
        fresh = P.Profile(prof.slug)
        if fresh.data.get("seek", {}).get("active") or fresh.training_running():
            messagebox.showerror(
                "Still running",
                f"A search or training is running for {prof.data['display_name']}.\n\n"
                "Stop it first, then delete.")
            return
        parts = DP.parts(prof.slug)
        have = [p for p in parts if p["files"]]
        if not have:
            if messagebox.askyesno("Delete", f"{prof.data['display_name']} has no files left. "
                                             f"Remove the profile?"):
                DP.delete(prof.slug, ["profile"])
                self._logline(f"'{prof.data['display_name']}': profile deleted.")
                self.reload()
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Delete - {prof.data['display_name']}")
        dlg.configure(bg="#1c1c1c")
        dlg.transient(self)
        dlg.grab_set()
        tk.Label(dlg, text=f"Delete {prof.data['display_name']}", bg="#1c1c1c", fg="#fff",
                 font=("Segoe UI", 11, "bold")).pack(padx=16, pady=(14, 2), anchor="w")
        tk.Label(dlg, text="Everything deleted here goes to the Recycle Bin and can be put "
                           "back from there. The person's entry in the ComfyUI face shelf is "
                           "rewritten without them, which cannot be undone.",
                 bg="#1c1c1c", fg="#ccc", wraplength=520, justify="left"
                 ).pack(padx=16, pady=(0, 10), anchor="w")

        mode = tk.StringVar(value="all")
        picks = {p["key"]: tk.BooleanVar(value=True) for p in parts}
        boxes = {}

        def refresh():
            pick_mode = mode.get() == "pick"
            for key, cb in boxes.items():
                cb.config(state=("normal" if pick_mode else "disabled"))
                if not pick_mode:
                    picks[key].set(True)
            n = sum(1 for p in have if picks[p["key"]].get())
            go.config(text=f"Delete {n} part(s)" if pick_mode else "Delete everything",
                      state=("normal" if (not pick_mode or n) else "disabled"))

        tk.Radiobutton(dlg, text="Everything - the whole person and all their files",
                       variable=mode, value="all", command=refresh, bg="#1c1c1c", fg="#ddd",
                       selectcolor="#333", activebackground="#1c1c1c", activeforeground="#fff"
                       ).pack(padx=16, anchor="w")
        tk.Radiobutton(dlg, text="Choose what to delete", variable=mode, value="pick",
                       command=refresh, bg="#1c1c1c", fg="#ddd", selectcolor="#333",
                       activebackground="#1c1c1c", activeforeground="#fff"
                       ).pack(padx=16, anchor="w", pady=(0, 6))

        box = tk.Frame(dlg, bg="#141414")
        box.pack(fill="both", padx=16, pady=(0, 10))
        for p in parts:
            text = p["label"] + (f"   ({p['files']} files, {p['bytes'] / 1e6:.1f} MB)"
                                 if p["files"] else "   (nothing)")
            cb = tk.Checkbutton(box, text=text, variable=picks[p["key"]], command=refresh,
                                bg="#141414", fg=("#ddd" if p["files"] else "#777"),
                                selectcolor="#333", activebackground="#141414",
                                activeforeground="#fff", anchor="w")
            cb.pack(fill="x", padx=8, pady=1)
            if not p["files"]:
                picks[p["key"]].set(False)
            boxes[p["key"]] = cb

        bar = tk.Frame(dlg, bg="#1c1c1c")
        bar.pack(fill="x", padx=16, pady=(0, 14))

        def do_delete():
            keys = ([p["key"] for p in parts] if mode.get() == "all"
                    else [k for k, v in picks.items() if v.get()])
            chosen = [p for p in parts if p["key"] in keys and p["files"]]
            mb = sum(p["bytes"] for p in chosen) / 1e6
            lines = "\n".join(f"  - {p['label']}  ({p['files']} files)" for p in chosen)
            if not messagebox.askyesno(
                    "Confirm delete",
                    f"Send to the Recycle Bin for {prof.data['display_name']}:\n\n{lines}\n\n"
                    f"{mb:.1f} MB in total. Go ahead?", icon="warning", parent=dlg):
                return
            r = DP.delete(prof.slug, keys)
            dlg.destroy()
            self._logline(f"'{prof.data['display_name']}': deleted "
                          + ", ".join(p["label"].lower() for p in chosen)
                          + f" - {len(r['recycled'])} path(s) to the Recycle Bin"
                          + ("; face-shelf entry removed" if r["registry_entry_removed"] else "")
                          + (f"; {len(r['failed'])} could NOT be deleted" if r["failed"] else ""))
            for p in r["failed"]:
                self._logline(f"   could not delete: {p}")
            self.reload()

        go = tk.Button(bar, text="Delete everything", command=do_delete)
        go.pack(side="right", padx=4)
        tk.Button(bar, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
        refresh()

    def restore_ui(self, prof: P.Profile):
        rows = BK.list_backups(prof.dir)
        if not rows:
            messagebox.showinfo("Restore", "No backups yet for this person.")
            return
        dlg = tk.Toplevel(self)
        dlg.title(f"Restore - {prof.data['display_name']}")
        dlg.configure(bg="#1c1c1c")
        dlg.transient(self)
        dlg.grab_set()
        tk.Label(dlg, text="Restoring replaces the live profile.json, identity, "
                           "and scan cache with the chosen snapshot. Cropped "
                           "photos and LoRA files are not affected.",
                 bg="#1c1c1c", fg="#ccc", wraplength=380, justify="left"
                 ).pack(padx=14, pady=(14, 8))
        for r in sorted(rows, key=lambda r: r["slot"]):
            rw = tk.Frame(dlg, bg="#1c1c1c")
            rw.pack(fill="x", padx=14, pady=2)
            tk.Label(rw, text=f"slot {r['slot']}   {r['at']}", bg="#1c1c1c",
                     fg="#ddd", font=("Consolas", 9)).pack(side="left")

            def do_restore(slot=r["slot"]):
                if messagebox.askyesno(
                        "Confirm restore",
                        f"Restore '{prof.data['display_name']}' to the slot {slot} "
                        f"snapshot? This overwrites the current tracking state."):
                    ok = BK.restore_backup(prof.dir, slot)
                    self._logline(f"'{prof.data['display_name']}': "
                                  + ("restored from slot " + str(slot) if ok
                                     else "restore failed - slot was empty"))
                    dlg.destroy()
                    self.reload()

            tk.Button(rw, text="Restore this", command=do_restore).pack(side="right")
        tk.Button(dlg, text="Cancel", command=dlg.destroy).pack(pady=(6, 14))


def _waiting_for_review(prof: P.Profile) -> str:
    """What is waiting for this person on the review page, in a few words.

    Everything uncertain moved onto that page (user, 2026-09-15): the crops
    before training, the videos the search could not call, and the photos it
    could not call. Empty string when nothing is waiting."""
    bits = []
    if prof.review_pending():
        c = prof.data.get("counts", {})
        bits.append(f"{c.get('clean_head', 0)} face + {c.get('clean_body', 0)} body crops")
    for label, d, exts in (("video", prof.uncertain_dir, VIDEO_EXTS),
                           ("photo", prof.needs_review_dir, (".jpg", ".jpeg", ".png"))):
        n = len([f for f in os.listdir(d)
                 if f.lower().endswith(exts) and os.path.isfile(os.path.join(d, f))]
                ) if os.path.isdir(d) else 0
        if n:
            bits.append(f"{n} uncertain {label}{'s' if n > 1 else ''}")
    return ", ".join(bits)


def _finished_loras(st: dict):
    """The LoRAs in this person's status that actually completed."""
    return [e for e in st.get("loras", []) if not e.get("partial")]


def _sync_loras_from_registry(prof: P.Profile):
    """Copy this person's entries from the training registry into the profile."""
    # comfy_paths owns this path; see the note at the top of that module.
    reg_path = REGISTRY
    try:
        # training may be swapping the registry in - read_text waits (safe_replace.py)
        reg = json.loads(read_text(reg_path))
    except (FileNotFoundError, ValueError):
        return
    except OSError as e:
        # Still refused after that wait: say so instead of skipping silently.
        # The row shows the LoRAs the profile already holds, this time.
        log.warning("could not read the LoRA registry to refresh %s: %s", prof.slug, e)
        return
    person = reg.get("people", {}).get(prof.slug)
    if not person:
        return
    loras = person.get("loras", {})
    if prof.data.get("loras") == loras:
        return                      # nothing changed - don't rewrite profile.json
    prof.data["loras"] = loras
    prof.save()


def _ask_checkbox(parent, title, prompt, default=True) -> bool:
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg="#1c1c1c")
    dlg.transient(parent)
    dlg.grab_set()
    var = tk.BooleanVar(value=default)
    tk.Checkbutton(dlg, text=prompt, variable=var, bg="#1c1c1c", fg="#ddd",
                   selectcolor="#333", activebackground="#1c1c1c",
                   activeforeground="#fff").pack(padx=18, pady=(16, 6))
    out = {"v": default}
    def ok():
        out["v"] = bool(var.get())
        dlg.destroy()
    tk.Button(dlg, text="OK", command=ok).pack(pady=(4, 14))
    parent.wait_window(dlg)
    return out["v"]


def _ask_text(parent, title, prompt) -> str:
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg="#1c1c1c")
    dlg.transient(parent)
    dlg.grab_set()
    tk.Label(dlg, text=prompt, bg="#1c1c1c", fg="#ddd").pack(padx=16, pady=(14, 4))
    var = tk.StringVar()
    ent = tk.Entry(dlg, textvariable=var, width=32)
    ent.pack(padx=16, pady=4)
    ent.focus_set()
    out = {"v": ""}
    def ok():
        out["v"] = var.get().strip()
        dlg.destroy()
    tk.Button(dlg, text="OK", command=ok).pack(pady=(6, 14))
    ent.bind("<Return>", lambda e: ok())
    parent.wait_window(dlg)
    return out["v"]


if __name__ == "__main__":
    from face_training.logconsole import start_logging_console
    start_logging_console("face_tool")
    FaceTool().mainloop()
