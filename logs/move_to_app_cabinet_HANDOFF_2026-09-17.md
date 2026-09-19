# ComfyUI: moved to app_cabinet, our work split into its own repo

Started as a handoff written 2026-09-17, before anything had been moved.
Rewritten 2026-09-18 as the record of the move actually being carried out.

- Times are LOCAL.
- Every claim below was checked at the time and the check is named beside it.
- The original 2026-09-17 plan is kept at the bottom, unchanged, as PART 5.

---

# PART 1 — THE SHAPE THAT WAS AGREED

The user answered eleven questions before any work began. The answers, in order:

1. **The split.** ComfyUI the app goes to `app_cabinet\comfyui`. Everything of ours goes
   to `REPO_comfyUI`, which keeps that exact name.
2. **Clean room.** The app cabinet copy stays a pristine checkout of the developer's
   project, with nothing of ours inside it. The launcher points it at our repo instead.
   Chosen over junctions, a copy script, or an extra-paths entry, because it is the only
   arrangement where a developer update cannot collide with our work.
3. **The developer's git travels with the app**, so updates can be pulled where the app
   lives. `REPO_comfyUI` starts a brand-new repository of its own.
4. **Git tracks only what we make** — nodes, workflows, presets. Models, output, input,
   temp, backups and the environment are ignored.
5. **Public repo, scrubbed first.** Every tracked file read for personal details, the list
   shown, the user decides, and only then does it go online.
6. **The live node copies win** over the `comfyui_ext` mirror in the kobold repo. Settled
   by checking the Portrait Master exhaustive log, which names only live `custom_nodes`
   paths and never mentions the mirror.
7. **Everything ComfyUI leaves the kobold repo.** The launcher and the launcher's own logs
   stay there.
8. **face_training moves too**, but still launches from the kobold launcher.
9. **Kobold is committed first**, as a restore point.
10. **The scrub script reports first, replaces on the user's say-so**, and is re-runnable
    before every push, because the name list grows as the work does.
11. **ComfyUI is the proving ground.** The standing rule and the launcher's new duties get
    built after this move is proven, not before.

A twelfth decision came later: **her first name stays** (the user confirmed it is not her
real name); **all Tailscale details come out**; **the product name "Tailscale" stays**.

---

# PART 2 — WHAT WAS DONE, IN ORDER

## 2.1 Safety (08:0x)
- ComfyUI confirmed not running: port 8188 free, no `main.py` or comfy process anywhere.
- Kobold's fifteen outstanding changes committed as **`a1c1300`** — the edited
  `comfyui_ext/README.md`, the `freedom_face_router` and `freedom_prompt_fixups` node
  folders (which existed in no git at all until then), a stray restart PID file, and the
  `face_training`, `seek` and `train` log folders.

## 2.2 The move
- `Move-Item REPO_comfyUI -> app_cabinet\comfyui` completed in **0.003 seconds** — a
  same-volume rename, so none of the 87 GB was copied.
- The 2026-09-17 attempt had failed with "the item is in use". The difference this time:
  the session's working folder was the parent, not the folder being moved. Nothing else
  was holding it.
- The developer's `.git` travelled with the app, as intended. Remote still `upstream`
  pointing at `comfyanonymous/ComfyUI`, HEAD still `3216c62`.

## 2.3 The split
Moved out of the app folder into a new `REPO_comfyUI`:
`custom_nodes`, `input`, `models`, `output`, `user`, `temp`, `logs`, `_backups`,
`_freedom_comfy.log`, `extra_model_paths.yaml`.

Then `git checkout -- .` inside the app folder restored the developer's own files that had
travelled with those directories — their two example nodes, `input/example.png`, the
thirty-six `put_..._here` model placeholders and the output placeholder.

Result, verified:
- `app_cabinet\comfyui`: **git status completely clean**. 4.9 GB, which is the app code
  plus its virtual environment. The only untracked things left are `__pycache__` folders
  and `venv`, both of which upstream already ignores.
- `REPO_comfyUI`: 82 GB — 79 GB models, 1.4 GB output, 1.3 GB custom_nodes, 60 MB input,
  21 MB temp, 6.4 MB backups, 1.5 MB user, 420 KB logs.

## 2.4 The launcher
`REPO_koboldccp_sst_tts_media/launcher.py`:
- `COMFYUI_DIR` now `app_cabinet/comfyui` — the developer's app, with the comment fixed.
- New `COMFYUI_DATA_DIR` pointing at `REPO_comfyUI`.
- The ComfyUI command gained `--base-directory` and `--extra-model-paths-config`, and lost
  the explicit `--output-directory`, which `--base-directory` now covers.
- Why one flag is enough: `folder_paths.py` lines 15-47 derive models, custom_nodes,
  input, output, user and temp from the base path. The yaml no longer sits beside
  `main.py`, so it has to be named explicitly — `main.py` lines 141-147.

## 2.5 The path sweep — nothing needed repointing
Because our folder kept the name `REPO_comfyUI`, every reference to it still resolves. All
hits point at `output/`, `models/`, `custom_nodes/`, `input/` or `user/default/workflows/`,
all of which are still exactly there. Checked specifically: **nothing anywhere points at
`REPO_comfyUI/venv` or `REPO_comfyUI/main.py`**, which are the only things that moved.

## 2.6 The tear-away from the kobold repo
The mirror was compared against the live copies file by file first, not assumed:

| | count |
|---|---|
| identical to the live copy | 24 |
| differed (live copy won, per decision 6) | 5 |
| existed **only** in the mirror | 8 |

The eight were rescued before anything was deleted: the three `build_*.py` scripts, the
three `Freedom_Video*.json` workflows, and the two readmes (`README.md` became
`FREEDOM_NODES_README.md`, plus `LORA_SOURCES.md`).

The ten `comfyui_workflows` files were compared the same way: 3 identical, 4 differed
(live won), 3 unique. The three unique ones — `annotate_workflow.py`,
`biglust_sdxl_api.json`, `wan_i2v_phaseA_api.json` — moved to `REPO_comfyUI/workflow_tools/`.

Also moved: `bigLust_ComfyUI_Recipe.pdf`, and thirty-two ComfyUI and face log files.
Then `comfyui_ext/` and `comfyui_workflows/` were removed from the kobold repo. Their
contents remain in that repo's git history, including in the restore point `a1c1300`.

Committed in kobold as **`7d68e5a`**.

## 2.7 The new repository
- `git init -b main` in `REPO_comfyUI`, with a `.gitignore` written for decision 4.
- First commit **`5be5a7b`**: 81 files, 1.3 MB, largest file well under GitHub's limit.
- **No remote is configured**, so nothing can be pushed by accident.
- Tracked: nine `freedom_*` node folders, the workflows, the portrait presets, the workflow
  tooling, eighteen written logs, the bigLust recipe, the extra paths config.

## 2.8 The wiring, verified without starting the server
Ran ComfyUI's own `folder_paths` with the launcher's flags, the way `main.py` does it
(`comfy.options.enable_args_parsing()` first — without that the flags are ignored, which
caught out the first attempt):

```
base         F:\Apps\freedom_system\REPO_comfyUI
models       F:\Apps\freedom_system\REPO_comfyUI\models
custom_nodes F:\Apps\freedom_system\REPO_comfyUI\custom_nodes
input        F:\Apps\freedom_system\REPO_comfyUI\input
output       F:\Apps\freedom_system\REPO_comfyUI\output
user         F:\Apps\freedom_system\REPO_comfyUI\user
freedom nodes found: 9      workflows found: 11      portrait_presets: present
checkpoint dirs on disk: 2  (ours + the shared Stable_Diffusion_SDXL library)
```

This proves the flags resolve. It is **not** proof the app runs — see PART 4.

## 2.9 The scrub
Built `tools/scrub_names.py` and `tools/scrub_names.json` in the parent repo. Three modes:
`discover` sweeps for emails, IP addresses, Windows user folders, drive paths and watched
words; `report` lists every hit and exits non-zero so it can gate a push; `replace` writes.
It only ever looks at files git tracks, because those are the only files a push sends.

What discovery found in the 81 published files: her first name 107 times (96 in logs, 11
in code across 7 files), the user's own name, username, handle and two email addresses,
the two Tailscale addresses, the tailnet hostname, the PC's machine name, the phone's
device name, and drive paths throughout. **Zero images, videos or model files are tracked**
— her reference photographs, the trained face models and the face training logs are all
ignored by git and never leave this machine.

Applied: **16 lines rewritten across 6 files**, removing both Tailscale addresses, the
tailnet hostname, the PC name and the phone name. Verified afterwards that no identifier
survives. Committed as **`4d70c24`**.

`portrait_master_checklist.py` had the phone address hardcoded into two live checks. It now
reads `FREEDOM_TAILSCALE_IP` from the environment and skips those two checks when it is not
set, so the script still runs without carrying a private address into a public repo.

Left alone by decision: her first name, the user's own name and email (ordinary
attribution, and git writes them into every commit anyway), and the word "Tailscale".

---

# PART 3 — TWO THINGS THAT WENT WRONG, AND WHAT WAS DONE

## 3.1 A live training run was disturbed
`face_training/` was moved out of the kobold repo while an OneTrainer run was **actively
using it**. Four processes were running and unknown to this session: the face tool
interface, the Susana retrain pipeline from the previous night, the review server, and an
`ot_train_entry.py` training job started that morning at 06:10. The running job loads its
code from that exact path.

It was caught because three log files refused to move and the reason was investigated
instead of worked around. `face_training/`, `logs/seek/` and `logs/train/` were put back
immediately and the entry script confirmed in place. The training job survived.

**Lesson for next time: check for running processes belonging to the folder being moved,
not just for the app being moved.**

## 3.2 The failed move split a log folder
That same failed move was not atomic. Four `face_tool_*.log` files had already landed in
`REPO_comfyUI/logs/face_training/` and existed **nowhere else**, while the other forty-seven
stayed in kobold. Found by comparing both sides file by file. All four were returned and
the stray folder removed. Count verified back at fifty-one, matching the original.

---

# PART 4 — STILL TO DO

1. **Verification.** Nothing has been proven to actually run yet.
   - Start ComfyUI through the launcher — never directly; that rule has not changed.
   - Run `venv\Scripts\python.exe logs\portrait_master_checklist.py` against the new
     location and compare against `logs/portrait_master_checklist_BEFORE_2026-09-16.json`
     check by check. Every one must pass: 43 of 43.
   - Repeat the on-screen rows in `portrait_master_exhaustive.md` PART 6.4 by clicking the
     real controls, Chrome in the foreground, workflow loaded fresh from disk.
   - **Known risk not yet tested:** the virtual environment was built while the app sat at
     the old path. If Python inside it fails after the move, report the exact error. Do not
     patch around it.
   - **Open question:** how ComfyUI gets started for this — by the user from the launcher
     menu, by this session driving the launcher menu, or by running the launcher's command
     directly (which would break the launcher-only rule).

2. **face_training still has not moved.** Blocked: the face tool interface window is still
   open (two processes) and holds three of its log files. The training run itself finished
   at 11:55.

3. **The public repository.** Not created, not named, nothing pushed. The scrub gate has
   been passed, so this is only waiting on a name.

4. **The logging step.** A dated entry in each repo this touched, including the parent, and
   the standing rule written into every CLAUDE.md: anything produced by improving a
   developer's app — new files, logs, outputs — lives in our repo, never in theirs.

5. **The launcher's seven new duties**, to be built after this move is proven: check the
   developer's app for updates; tell the user and let them choose; after updating, hunt for
   links into the repo that the update broke; keep the app seeing our files; check for
   version conflicts across our apps, their apps and Python, each inside its own
   environment and never against global versions; try to resolve those conflicts; and log
   the changeover in every repo.

6. **Undecided: the mixed logs still in the kobold repo.** Nothing purely ComfyUI is left
   there, but several logs cover the whole media stack and mention ComfyUI heavily —
   `media_stack_build_log.md`, `work_log_2026-09-01/02/02_continued.md`,
   `ram_fix_and_remote_access_2026-09-05.md`, `research_lora_training_tools_2026-09-03.md`,
   `onetrainer_master_reference.md`, `lora_training.md`. They are not ComfyUI-specific, so
   they were left where they are. Also left: the five `seek_susana_*.log` files and the
   `step6`/`step7` Willow files, which belong to the chat-to-image pipeline rather than to
   ComfyUI.

---

# PART 5 — THE ORIGINAL 2026-09-17 PLAN, UNCHANGED

Written before anything was moved, by the session that started inside `REPO_comfyUI`.

## Why a new session was needed

On 2026-09-17 the move was tried from inside REPO_comfyUI, and Windows refused it:
`Cannot move item because the item at 'F:\Apps\freedom_system\REPO_comfyUI' is in use.`
At that moment no running program had REPO_comfyUI in its command line, port 8188 was free,
and the only thing known to be inside the folder was the Claude session's own working
folder. A session cannot leave the folder it started in. It was NOT proven that nothing
else held the folder, because the Sysinternals Handle tool is not installed.

*(2026-09-18 note: the session's own working folder was indeed the cause. Run from the
parent, the move took three thousandths of a second.)*

## The user's rules for this job

- Do not guess or assume. Report exact results, including failures.
- Start the work only after the user gives a go-ahead (CLAUDE.md rule 3).
- Do NOT commit or push anything without asking.
- REPO_koboldccp_sst_tts_media is NOT a backup of ComfyUI.
- Restart and stop ComfyUI only through the koboldccp launcher. Never kill its processes.
- Chrome: use the "John Doe" profile, never "Jacob". Close old ComfyUI tabs and workflows
  before loading the workflow again. Chrome must be the foreground window, or the ComfyUI
  page stalls.
- The launcher is `REPO_koboldccp_sst_tts_media\start_koboldcpp_media.bat`. Main menu:
  `4` start ComfyUI, `8` stop apps, `9` quit. Control console: `c` restart, `q` quit back
  to the menu, `e` quit and close. Keystrokes do not reach it while the screen is locked.
