# ComfyUI LoRA Stack, Face-Training video/backup, and ComfyUI repo migration — 2026-09-07

Session continued from an earlier compaction. Covers three separate pieces of work,
in the order they happened: (1) face-training video ingestion + rotating backup,
(2) a new general-purpose LoRA node plus wiring the existing Face Shelf and a
trigger-word auto-fill into the beginner SDXL workflow, (3) relocating the entire
ComfyUI installation into its own git repository and auditing/testing everything
that touches it.

Branch at the time: `branch08-remote-access`. All work in this log was committed
there; a new branch is cut at the end of this session (see bottom).

---

## 1. Face-training: video ingestion + rotating backup

### 1.1 Discussion

User asked for a full walkthrough of how the Face Seek / Face Training pipeline
avoids double-processing photos, handles head vs head+body crops, protects
originals, tracks progress, and resumes after a stop — all explained in plain,
teaching language (per standing preference), and explicitly "do not assume or
guess." Verified everything against the actual code before answering:

- **Duplicate protection**: `scan_cache.py`'s `content_hash()` (first 256 KB +
  file size, blake2b) keyed in a per-profile SQLite DB — confirmed exact-duplicate
  protection across folders/reruns.
- **Head vs head+body**: confirmed two separate folders (`clean/head/`,
  `clean/body/`) via `sort_photos.py`, never mixed.
- **Originals**: confirmed never moved/deleted — `seek.py` only copies into a
  staging `found/` folder, crops from the copy, deletes the staged copy.
- **Progress tracking**: `profile.json`'s `seek.progress` dict + `SEEK_STAGES`
  tuple in `profiles.py`, checkpointed per stage (scan/learn/group/reteach/
  search/clean).
- **Stop-safety**: a `STOP` flag file (`Profile.request_stop/_stop_flag`),
  polled between photos.
- **Model tracking**: `profile.json`'s `loras` dict, `jobs.py`'s job table.

Found and reported the one real gap: **no video support at all** — `IMAGE_EXTS`
in `sort_photos.py` only covered still-image extensions; no `cv2.VideoCapture`,
no ffmpeg, nothing, anywhere in `face_training/`. Researched two real options via
web search (frame-extraction/dedup community practice + a pHash-vs-embedding
paper-backed comparison) and presented two ideas. User picked **idea two only,
for video**: a fuzzy/near-duplicate check (perceptual hash + face-embedding
reuse), paired with the smarter "scene-cut + sharpest frame" extraction method
once asked directly which extraction approach to use.

Also asked for a **5-slot rotating backup** of "everything used to track the
process" (clarified down to: `profile.json`, `identity/`, `scan_cache/faces.db`
only — not cropped photos, not LoRA files), living inside each person's own
profile folder, triggered automatically on Seek/Train stop **and** on closing
either the Face Tool window or the launcher console (including their actual
Windows X buttons — confirmed via code read that neither currently had a real
close handler), plus a manual backup/restore path.

### 1.2 Built

**New file `face_training/video_frames.py`** — scene-cut + sharpest-frame video
extraction, then a fuzzy-duplicate pass:
- Samples a video at `SAMPLE_FPS = 2.0`, detects scene cuts via histogram
  correlation drop (`SCENE_CUT_DROP = 0.45`), keeps only the sharpest frame
  (Laplacian variance) per scene.
- Fuzzy-dup pass on the kept frames: a DCT-based perceptual hash
  (`PHASH_HAMMING_MAX = 8`) first, then — if a face is present — an ArcFace
  embedding comparison reusing `sort_photos._detect` (`EMBED_SIM_MAX = 0.93`).
  Either match drops the frame.
- Output: plain `.jpg` stills, so nothing downstream needs to know they came
  from video.

**New file `face_training/backup.py`** — 5-slot rotating backup/restore:
- `backup_profile()` rotates `<profile>/backup/1/` (newest) through `.../5/`
  (oldest), copying only `profile.json`, `identity/`, `scan_cache/faces.db`.
- `backup_profile_by_slug()`, `backup_all_profiles()`, `list_backups()`,
  `restore_backup()`.
- stdlib only, importable from the launcher's own Python or the OneTrainer venv.

**Wired in:**
- `scan_cache.py`: added `list_videos()`, `extract_videos()`, and a
  `video_frames_dir` parameter on `scan_folder()` so Seek's scan stage also
  extracts and scans any videos in the seek folder.
- `seek.py`: scan stage passes `self.prof.video_frames_dir`; `Seek.run()`'s
  `finally` block now calls `BK.backup_profile(self.prof.dir)` on every run end
  (finished or stopped).
- `pipeline.py`: `run()` now calls `BK.backup_profile_by_slug(person_slug)` at
  the end.
- `profiles.py`: added `video_frames_dir` property and `backup/` to the folder
  layout doc; both created by `Profile.create()`.
- `face_tool_ui.py`: added a **Close** button, `self.protocol("WM_DELETE_WINDOW",
  self.close)` handler (backs up all profiles before destroying the window), and
  per-profile **Backup**/**Restore** buttons with a slot-picker dialog.
- `launcher.py`: added `_install_close_backup_handler()` using
  `ctypes.WINFUNCTYPE` + `SetConsoleCtrlHandler`, handling
  `CTRL_CLOSE_EVENT`/`CTRL_LOGOFF_EVENT`/`CTRL_SHUTDOWN_EVENT` — backs up every
  profile when the console's own X button is clicked (previously only Ctrl+C
  was handled, and only to protect the shutdown sequence, not to back anything
  up).

### 1.3 Verified (not just written)

- Backup rotation tested end-to-end against a throwaway fake profile: 7 cycles
  through 5 slots, confirmed slot 1 = newest / slot 5 = oldest-kept, confirmed
  restoring from a specific slot rolls back to exactly that snapshot.
- Video extraction tested against a real synthetic OpenCV-generated test video
  (two distinct color scenes, 30 total frames): correctly found 2 scenes,
  correctly collapsed to exactly 2 kept frames.
- The perceptual-hash duplicate math itself was directly unit-tested: an
  initial test using a flat solid-color synthetic image gave a misleading
  result (flagged as a real finding, investigated) — root cause was the test
  image being degenerate (no texture for the DCT hash to key on), not a bug in
  the hash logic. Re-tested with realistic textured synthetic images (gradient
  + shapes) and got correct results: near-duplicate correctly caught (Hamming
  distance 0), genuinely different scene correctly left alone (Hamming distance
  30, threshold 8).
- All 8 touched/new files passed `ast.parse` syntax checks; all imported
  cleanly inside the real OneTrainer venv (with insightface etc. actually
  available), not just the system Python.

### 1.4 Committed

- `3f8a939` — "Face training: video ingestion (scene-cut + fuzzy dedup) and
  rotating backup" (9 files, +527/−8).

---

## 2. LoRA Stack node, Face Shelf wiring, trigger word

### 2.1 What prompted it

User pointed out the `Freedom_bigLust_SDXL` workflow was missing a LoRA step
entirely (7 steps instead of the intended 8/9) and that the shelf of trained
faces (already built and working in three other workflows) didn't show up in
this one. Asked for: a general-purpose LoRA node with 3 starter rows, a "+" to
add more, a "✕" to delete any row, and — critically — this node must **never**
offer the trained face LoRAs (those live under `models/loras/faces/` and are
picked from the existing Face Shelf node instead, so a trained identity can
never be loaded from the wrong picker by mistake).

### 2.2 Research done before building

- Checked `custom_nodes/` for any existing multi-LoRA node (e.g. rgthree's
  Power Lora Loader) — none installed; confirmed this needed building from
  scratch.
- Read the proven pattern already used in this codebase
  (`freedom_face_shelf/web/face_shelf.js`'s hidden-widget technique: real data
  lives in native ComfyUI widgets, marked `type = "hidden"` so they serialize
  with the workflow but aren't drawn; a DOM panel is the visible front end)
  and reused it rather than inventing a new approach.
- Asked the user directly which order — identity LoRA before or after general
  LoRAs — rather than guessing (user explicitly said "do not assume or guess,
  research it"). Web-searched real LoRA-stacking guidance: character/identity
  LoRA should load first/closer to the checkpoint at higher relative strength;
  style/general LoRAs layered on top afterward at lower strength, since a
  strong style LoRA applied first can wash out identity applied after it.
  Confirmed via a second search that this is consistent with how LoRA merges
  work mathematically (near-additive weight deltas). Order chosen:
  checkpoint → Face Shelf → LoRA Stack.

### 2.3 Built

**New package `comfyui_ext/freedom_lora_stack/`** (mirrored into
`custom_nodes/freedom_lora_stack/` — see note in §3 about this mirroring
becoming moot after the relocation):
- `nodes.py` — `FreedomLoraStack`: `MAX_ROWS = 12` optional
  `(enabled_i, lora_i, strength_i)` triples, applied in row order via
  `comfy.sd.load_lora_for_models`. `_is_face_lora()` filters out anything
  under `faces/` both in the dropdown list (`/freedom/lorastack/list` route)
  and defensively again at execution time.
- `web/lora_stack.js` — 3 starter rows, "+ Add LoRA" (up to 12), a "✕" per row;
  real values live in hidden native widgets so the workflow serializes
  correctly; `onConfigure` rebuilds the visible rows from whatever a loaded
  workflow's widgets already hold (not just the 3-row default).
- `__init__.py` — standard `WEB_DIRECTORY` export.

### 2.4 Wiring `Freedom_bigLust_SDXL.json` (direct JSON surgery, not click-drag)

User had unsaved changes open in the browser tab; had them press Ctrl+S first,
then edited the saved workflow file on disk directly (more reliable than
UI automation for inserting/rewiring nodes), reasoning: `git status`-style
consistency check afterward, not just visual inspection.

Changes made via a scratch Python script (`_scratch_edit_workflow.py`, deleted
after use):
- Removed a stray, unwired `LoraLoader` node (id 26) the user had dropped on
  the canvas.
- Renumbered STEP 2→4, 3→5, 4→6, 5→7, 6→8, 7→9 in every node title **and**
  inside every MarkdownNote's body text (including internal cross-references
  like "STEPS 2-3" → "STEPS 4-5") via a regex mapping, not manual string
  replacement.
- Inserted `FreedomFaceShelf` as new **STEP 2** (id 27) and `FreedomLoraStack`
  as new **STEP 3** (id 29), each with its own explanatory MarkdownNote
  (ids 28, 30) written in the same plain-language style as the rest of the
  workflow.
- Rewired: checkpoint (15) → Face Shelf (27) → LoRA Stack (29) → KSampler
  model input + both CLIPTextEncode nodes' clip input.
- Verified with an automated consistency check: every link ID referenced by a
  node input/output exists in the `links` array and vice versa (no dangling
  links either direction) — confirmed clean before touching the live server.
- ComfyUI restarted (custom nodes only load at startup) — `freedom_lora_stack`
  loaded with zero errors; confirmed live via direct DOM inspection through
  the (now-disconnected) Chrome extension: 3 rows present with
  select/strength/delete controls each, "+ Add LoRA" grows to 4, "✕" shrinks
  back to 3, dropdown correctly listed 7 real LoRAs with **zero** face LoRAs
  leaking in.

### 2.5 Trigger word — discussion, near-miss, correction

User asked for clarification on how the trigger word (`ohwxsusana`) relates to
head vs head+body — confirmed via the live `/freedom/faceshelf/list` endpoint
that **both** of Susana's LoRAs share the identical trigger word; the
head/body distinction is entirely which file gets loaded (which card is
clicked), not the word itself, because each file was trained on a different
crop style.

User then asked to **remove the trigger feature from the whole plan**. Before
doing anything, researched whether a LoRA's trained identity actually requires
its trigger word to be present in the prompt (not assumed) — confirmed via web
search that yes, generally both the LoRA-load step *and* the trigger word in
the prompt are needed together; loading alone patches the model's capability,
the trigger word is the learned key that was baked into every training
caption. Recommended keeping it; user confirmed ("1 of course... I thought you
read all the logs?").

**Wired the trigger word in** — added to `Freedom_bigLust_SDXL.json`:
- New node 31, `PrimitiveStringMultiline` — becomes the new "STEP 4 — type
  here" box (the user's original prompt text preserved exactly).
- New node 32, `StringConcatenate` — glues Face Shelf's `trigger` output
  (comma-delimited) onto whatever's typed.
- Original node 10 (`CLIPTextEncode`) retitled "combine + encode (don't
  touch)", now fed by node 32's output instead of being typed into directly.
- STEP 4's MarkdownNote text updated to explain the auto-fill in plain
  language.
- Verified via link-graph consistency check (no dangling links) and live via
  the Chrome extension's JS execution tool: read the live graph object
  directly (`window.app.graph.getNodeById(...)`), confirmed
  `n27_trigger_output_links: [50]` (wired) and the full chain resolved
  correctly.

### 2.6 Full live test, done discreetly

User's real STEP 4 prompt is explicit content; user asked for discretion since
people were near the laptop. Test procedure:
1. Read and saved the exact current state of Face Shelf selection, LoRA Stack
   rows, and prompt text via JS (`window.__preTestState`).
2. Set safe placeholder values in memory only (not saved to the workflow file
   on disk): Face Shelf → `susana_head_sdxl` @ 0.9, LoRA Stack row 1 →
   `Emotions V1.safetensors` @ 0.6, prompt → a plain, safe sentence.
3. Called `window.app.queuePrompt(0)` directly — real submission through
   ComfyUI's actual API, not a simulated check.
4. Polled `/history` via curl until `status: success`.
5. Read the resulting PNG directly with the Read tool myself (never displayed
   on the user's screen) — confirmed a real, correctly-composed, safely-clothed
   image came back.
6. Restored every value to the exact pre-test state via JS, verified the
   restoration matched byte-for-byte (`restored_ok: true`).

### 2.7 Committed

- `1014a41` — "ComfyUI: add Freedom LoRA Stack node (general LoRAs, excludes
  trained faces)" (3 files, +315).
- The workflow JSON itself (`Freedom_bigLust_SDXL.json`) lives in the
  *separate* `app_cabinet/comfyui` git repo (at the time), not this one — not
  committed here as a result; only later folded into this repo's
  `comfyui_workflows/` mirror during the relocation work (§3).

---

## 3. ComfyUI relocated into its own repository

### 3.1 How this came up

A long back-and-forth about where ComfyUI's custom nodes, workflows, and
face-training output "live" relative to git — established that:
- `app_cabinet/comfyui`'s own `.git` was pointed at the **real, official**
  upstream project (`github.com/comfyanonymous/ComfyUI`), a single-commit
  shallow copy, not something the user authored.
- Everything genuinely built by/for the user (the six `freedom_*` custom node
  folders, the workflow files, the face-training registry/thumbnails/prompts)
  sat *inside* that same folder but was **not** tracked by the author's repo
  at all (`custom_nodes/` and `models/` and `user/` are all in the author's
  own `.gitignore`).
- Explored several options (junctions, a filesystem-watcher service, "can git
  just watch arbitrary folders like Google Drive" — confirmed git fundamentally
  cannot do that, for any repo) before landing on the standard, correct git
  answer: **fork it**. A real fork keeps a link back to the original author
  (`upstream` remote) for pulling future updates, while everything the user
  adds becomes normal commits in their own copy — no watcher, no junctions,
  no manual mirroring step.
- User confirmed: keep ComfyUI connected to the author's git for future
  updates; move **everything**, including the 79 GB of models and 5.1 GB venv
  (not just the small app-code slice) — "any future models will go into the
  future location too."

### 3.2 Pre-flight checks (all done before touching anything)

- Confirmed ComfyUI was live on port 8188 (PID 31628).
- Sized the folder: 85 GB total — 79 GB `models/`, 5.1 GB `venv`,
  1.2 GB `custom_nodes/`, 345 MB `output/`, rest small.
- Checked `venv/pyvenv.cfg` — confirmed it has the old absolute path baked
  into its `command` field (informational only, not used by the interpreter
  at runtime — later proven harmless since the venv ran ComfyUI successfully
  immediately after the move without modification).
- Grepped this repo for every hardcoded reference to
  `app_cabinet[/\\]comfyui` — found 10 Python files plus one workflow JSON
  with an absolute path baked into a widget value.
- Confirmed F: drive had 398 GB free — plenty for a same-volume move (and a
  same-volume move on NTFS is a near-instant directory-entry change, not a
  byte-for-byte copy, which is exactly what happened: the `mv` returned
  immediately for the full 85 GB).

### 3.3 Execution, in order

1. **Stopped ComfyUI** — graceful `taskkill //PID //T` failed ("can only be
   terminated forcefully"), followed with `//F`; confirmed port 8188 freed.
2. **Moved the whole folder**: `app_cabinet/comfyui` →
   `F:\Apps\freedom_system\REPO_comfyUI` (an empty placeholder folder had
   already been created there; removed first). Confirmed old location gone,
   new location's size matched (85 GB), top-level listing sane.
3. **Fixed the git remote**: `git remote rename origin upstream` inside
   `REPO_comfyUI` — the author's project is fetch/push-able as `upstream` now;
   no new `origin` was created (not asked for; would need a real decision
   about a destination repo, left for a future request).
4. **Repointed every hardcoded path**:
   - `launcher.py`: single-point fix — `COMFYUI_DIR` (line ~75) changed from
     `f"{CABINET}/comfyui"` to `f"{BASE_DIR}/REPO_comfyUI"`; everything else in
     the launcher already routed through this one constant. Also fixed one
     informational print string (line ~902).
   - `face_training/otrain.py`, `pipeline.py`, `thumbs.py`, `face_tool_ui.py`,
     `sort_photos.py` — each had its own separate hardcoded literal
     (insightface root, LoRA output dir, registry path) — fixed individually.
   - `comfyui_ext/freedom_face_competition/build_face_competition.py`,
     `freedom_face_shelf/build_face_shelf.py`,
     `freedom_prompt_shelf/build_face_image.py` — each writes its generated
     workflow JSON to an absolute output path — fixed.
   - `comfyui_workflows/annotate_workflow.py` — fixed.
   - `Freedom_bigLust_SDXL.json`'s `save_folder` widget value (both the copy
     now living at `REPO_comfyUI/user/default/workflows/` and a separate,
     already-stale mirror copy sitting in this repo's own
     `comfyui_workflows/` folder, confirmed unreferenced by any code but
     fixed anyway for consistency) — fixed.
   - Three README files (`comfyui_ext/README.md`,
     `comfyui_ext/freedom_folder_inspector/README.md`,
     `face_training/README.md`) — fixed for documentation accuracy.
   - **Inside `REPO_comfyUI` itself** (none tracked by the author's repo, so
     none needed committing there, but all needed fixing for the app to
     actually work): `custom_nodes/freedom_face_competition/
     freedom_face_competition_state.json` had two *real, functional* absolute
     paths (`hair_reference_image`, `photo_folder`) pointing at the old
     `input/susana_ref/` location — confirmed the referenced files existed at
     the new path, fixed both. Five `models/diffusion_models/*.metadata.json`
     files had a stale `file_path` field (cosmetic — ComfyUI resolves models
     by directory scan, not this field, but fixed via `sed` for accuracy).
     `venv/pyvenv.cfg`'s `command` line fixed for cleanliness (already proven
     non-functional/cosmetic).
   - **Final sweep** caught one more the first pass missed: the *live* copy
     of `custom_nodes/freedom_folder_inspector/README.md` (as opposed to the
     already-fixed version-controlled mirror in this repo's `comfyui_ext/`)
     still had the old path — fixed.
   - Confirmed via repo-wide grep that the only remaining hits anywhere are
     dated historical log files and past commit messages, correctly left
     untouched.
5. **Verified `launcher.py` resolves correctly** before restarting anything:
   imported the module directly, checked `COMFYUI_DIR` value, confirmed
   `main.py` and the venv's `python.exe` both exist at the resolved path.
6. **Restarted ComfyUI** from the new location with its original launch flags
   (`--port 8188 --disable-auto-launch --output-directory ... --listen
   127.0.0.1,<TAILSCALE_IP>`). Startup log showed all 20 custom node packages
   (the six `freedom_*` ones plus every third-party one) importing with zero
   errors; server reachable on both addresses (HTTP 200 confirmed via curl on
   both `127.0.0.1:8188` and the Tailscale IP).

### 3.4 Audit

- Hit the Face Shelf and LoRA Stack HTTP endpoints directly post-move —
  registry and LoRA scan both returned identical, correct data to before the
  move (Susana's two cards; 7 non-face LoRAs).
- Confirmed the **shared model library** trick (a separate app,
  `app_cabinet/Stable_Diffusion_SDXL`, shares its checkpoints/LoRAs with
  ComfyUI via `extra_model_paths.yaml`) survived the move correctly — that
  file's `base_path` still correctly points at the *other*, unmoved app
  folder; confirmed via ComfyUI's live `/object_info/CheckpointLoaderSimple`
  that all 7 checkpoints resolve, including two that an early structural-audit
  script had (incorrectly) flagged as "missing" before the shared library was
  accounted for.
- Wrote a structural audit script (`audit_workflows.py`) that loads every
  saved workflow JSON, checks every node's `type` against ComfyUI's live
  `/object_info` (1,324 registered node types), and checks every
  checkpoint/LoRA/VAE/etc. file reference against ComfyUI's own live model
  lists (not a raw folder scan, which would have missed the shared library).
  First pass flagged 6 false positives (all from not knowing about the shared
  library); corrected the script to query `/object_info` per node type
  instead of scanning `models/` directly, re-ran — all 7 workflows passed
  clean.

### 3.5 Real end-to-end testing of all 7 workflows (not just structural checks)

No browser automation tool was available this session (the Chrome MCP
connection had dropped), so wrote a generic graph-to-API-prompt converter
(`graph_to_prompt.py`) — the same conversion ComfyUI's own frontend normally
does — using the server's live `/object_info` as ground truth for each node
type's parameter order, rather than guessing at widget-array positions.
Caught and fixed a real correctness risk before trusting it: ComfyUI's
frontend silently injects an extra "control_after_generate" slot into
`widgets_values` right after any seed-like INT widget, which has no
corresponding backend parameter — confirmed this is a real, detectable flag
(`"control_after_generate": true`) in the live object_info spec, and taught
the converter to skip that slot rather than let it silently misalign every
value after it. Verified the converter's correctness by hand before trusting
it: converted `Freedom_bigLust_SDXL.json` and cross-checked every KSampler/
EmptyLatentImage value against the raw file — seed, steps, cfg, sampler,
scheduler, denoise, width, height, batch_size all matched exactly, with the
"randomize" control string correctly consumed and dropped.

Tests run, each a genuine submission through ComfyUI's real `/prompt` API,
polled via `/history` to actual completion:

| workflow | result |
|---|---|
| `Freedom_bigLust_SDXL.json` | **success** — real render (with safe placeholder prompt text, Face Shelf + LoRA Stack both exercised), output confirmed 1216×832, batch of 2, correct file size |
| `Freedom_Face_Shelf.json` | **success** — real render |
| `Freedom_Face_Image.json` | **success** — real render |
| `Freedom_Face_Competition.json` | **success** — full 5-method run (faceswap, instruct, fingerprint, expression, plus hair-mask debug outputs), ~10+ minutes, confirmed via live GPU check mid-run (RTX 4080 Laptop at 96% utilization, 10.8/12.3 GB VRAM) that it was genuinely computing, not stalled |
| `Freedom_Video_5B_fast.json` | correctly stopped at its own intentional safety check (`FreedomVideoQueue`: "Video queue slot 1 is empty — send an image to it first") — proves every model/node/path upstream resolved correctly; nothing was ever queued into it this session, so this is expected, not a bug |
| `Freedom_Video.json` | same, same expected result |
| `Freedom_Video_14B_quality.json` | same, same expected result |

### 3.6 Aside: Windows "best performance" / GPU question

User asked where Claude Code itself is installed
(`C:\Users\jespe\.local\bin\claude.exe`) intending to set Windows' per-app
graphics preference on it. Flagged before they acted on it: Claude Code does
no GPU work itself; the actual GPU-heavy process is ComfyUI's own Python
interpreter (`REPO_comfyUI\venv\Scripts\python.exe`). Also confirmed, live,
that no manual Windows graphics assignment was needed at all — `nvidia-smi`
during the Face Competition run showed the RTX 4080 Laptop GPU at 96%
utilization and the ComfyUI log explicitly showed it auto-detected and bound
to `cuda:0` on that GPU by itself.

### 3.7 Committed

- `721816e` — "ComfyUI relocated to its own repo (REPO_comfyUI) - repoint
  every path" (14 files, +16/−16, in `REPO_koboldccp_sst_tts_media`).
- Nothing to commit inside `REPO_comfyUI` itself — every file fixed there
  (the node state JSON, model metadata, venv config) lives in paths the
  upstream author's own `.gitignore` already excludes, so there was nothing
  for that repo to track differently before or after.

---

## Final state at the end of this session

- ComfyUI: healthy, idle (queue empty), serving on both `127.0.0.1:8188` and
  the Tailscale address, running from `F:\Apps\freedom_system\REPO_comfyUI`.
- `REPO_comfyUI`: a real git repo, `upstream` remote pointed at
  `comfyanonymous/ComfyUI`, no `origin` configured yet (not requested).
- `REPO_koboldccp_sst_tts_media`: branch `branch08-remote-access`, all work in
  this log committed and pushed (commits `3f8a939`, `1014a41`, `721816e`, plus
  this log's own commit — see below).
- No open bugs. Every workflow that could be meaningfully tested this session
  was tested for real and passed; the three video workflows are structurally
  and functionally proven correct up to their own intentional "nothing queued"
  stop, which requires a separate, deliberate "send an image to the queue"
  step by design, not something this session's changes affected.
