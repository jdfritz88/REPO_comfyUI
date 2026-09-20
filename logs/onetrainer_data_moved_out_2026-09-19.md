# OneTrainer's data moved out of the developer's app, and proven to stay out

2026-09-19. Follows the ComfyUI split recorded in
`move_to_app_cabinet_HANDOFF_2026-09-17.md`, and applies the same rule to the
second third-party app.

---

# PART 1 — WHY

OneTrainer at `app_cabinet\OneTrainer` is Nerogar's project, cloned from
`github.com/Nerogar/OneTrainer`. Its checkout was clean apart from two folders
that were not theirs:

| folder | size | files |
|---|---|---|
| `_face_profiles` | 4.6 GB | 2,681 |
| `_face_runs` | 1.1 GB | 3,276 |

Three problems with that, in order of seriousness:

1. **Her photographs were sitting inside a third-party application's folder.**
2. **An update or reinstall of OneTrainer would land on top of them.** The same
   failure that wiped two Portrait Master edits in September.
3. **Their git status showed our work as untracked clutter**, so "is this
   checkout clean?" could never be answered at a glance.

The user's standing rule, decided 2026-09-18: anything produced by improving a
developer's app — new files, logs, outputs — lives in our repo, never in theirs.
This is that rule applied to OneTrainer.

The user's instruction, 2026-09-19: move them into `REPO_comfyUI`, make sure
OneTrainer can always see them, and make future folders land in the repo and not
in the app folder.

---

# PART 2 — THE MOVE

Checked first, because of what went wrong on 2026-09-18 (a folder was moved out
from under a live training run): `Get-CimInstance Win32_Process` for anything
matching `face_tool_ui|face_training|OneTrainer`. **None running.** The face tool
window, open for most of the previous day, had been closed.

Both folders moved with `Move-Item` — an atomic same-volume rename, not the
copy-style move that silently split a log folder the day before.

```
_face_profiles   moved in 0.005 s
_face_runs       moved in 0.003 s
```

Verified afterwards:

- `_face_profiles`: **2,681 files** in the repo, gone from OneTrainer.
- `_face_runs`: **3,276 files** in the repo, gone from OneTrainer.
- `git -C app_cabinet\OneTrainer status --porcelain` → **empty**. Their checkout
  is clean for the first time.

Both folders are git-ignored in `REPO_comfyUI/.gitignore`: 5.7 GB, and the
profiles hold her photographs. Neither is ever published.

---

# PART 3 — MAKING IT STICK

## 3.1 One place owns the paths

A session earlier the same day had created
`REPO_koboldccp_sst_tts_media/face_training/comfy_paths.py` to own the LoRA
publish path, after finding it hand-copied into three files that happened to
agree but nothing kept in step. That module was extended rather than competed
with:

```python
PROFILES_ROOT = os.path.join(COMFY_REPO, "_face_profiles")
WORK_ROOT     = os.path.join(COMFY_REPO, "_face_runs")
APP_CABINET_ONETRAINER = r"F:\Apps\freedom_system\app_cabinet\OneTrainer"
```

plus `check_data_root()`, which raises `DataRootError` when a path resolves
inside the developer's OneTrainer, or outside our repo, or when our repo does not
carry its `custom_nodes` marker (so a stale path cannot be silently created by a
`makedirs` and quietly used).

## 3.2 Three files stopped spelling the paths out

| file | line | was | now |
|---|---|---|---|
| `near_miss.py` | 53 | `PROFILES_ROOT = r"...app_cabinet\OneTrainer\_face_profiles"` | imports it from `comfy_paths` |
| `profiles.py` | 39 | same literal | imports it from `comfy_paths` |
| `pipeline.py` | 45 | `WORK_ROOT = r"...app_cabinet\OneTrainer\_face_runs"` | imports it from `comfy_paths` |

A future folder cannot land in the app folder by being typed there, because there
is nowhere left to type it.

---

# PART 4 — THE TEST

The user asked for proof that no new LoRA or data file would land in OneTrainer.
Four separate checks, because a path trace alone is not proof.

## 4.1 Every write destination of a real training job

A real `otrain.Job` was constructed the way `pipeline.py` constructs one, and
every destination `otrain.py` feeds to OneTrainer was read off it:

```
the LoRA itself      REPO_comfyUI\models\loras\faces\<name>.safetensors
workspace_dir        REPO_comfyUI\_face_runs\<person>\<job>\workspace
cache_dir            REPO_comfyUI\_face_runs\<person>\<job>\cache
concepts.json        REPO_comfyUI\_face_runs\<person>\<job>\concepts.json
checkpoint backups   REPO_comfyUI\_face_runs\<person>\<job>\workspace\backup
source images        REPO_comfyUI\_face_profiles\<person>\clean\head
```

**Write destinations landing in OneTrainer: 0.**

## 4.2 A real write, against a file-level snapshot

A trace proves what we compute, not what their code does. `_default_config()` runs
OneTrainer's own `scripts/create_train_files.py` **with its working directory set
to the app root**, which is exactly where a stray relative write would land.

- Snapshot before: **783 files** under `app_cabinet\OneTrainer` (excluding `venv`,
  `.git`, `.pyc`).
- The generator was actually run. It produced `ot_default_config.json`,
  `ot_default_concepts.json` and `ot_default_samples.json` — all three in
  `REPO_comfyUI\_face_runs\zz_pathtest\cache`.
- Snapshot after: **783 files. File list byte-identical. Their git status empty.**
- The throwaway test folder was removed afterwards; confirmed gone.

## 4.3 The guards were fed the forbidden path

Each was handed a path inside OneTrainer and had to refuse:

| attempt | result |
|---|---|
| publish a LoRA into `OneTrainer\_face_runs\x.safetensors` | refused, `PublishDestinationError` |
| use `OneTrainer\_face_profiles` as the profiles root | refused, `DataRootError` |
| use `OneTrainer\_face_runs` as the work root | refused, `DataRootError` |

## 4.4 Every absolute path constant in the package

All modules in `face_training` were imported and every upper-case string constant
holding an absolute path was checked — around thirty. Six point into OneTrainer.
The first pass reported them as failures; that was **wrong**, and the rule was too
crude: it flagged anything *pointing* at the app rather than anything *writing* to
it. Classified properly:

| constant | what it is | writes? |
|---|---|---|
| `otrain.OT_ROOT`, `ot_train_entry._OT` | the app root, for imports and cwd | no |
| `otrain.OT_PY`, `face_tool_ui.PY` | their Python interpreter | no |
| `otrain.OT_MKFILES` | their config-generation script | no — outputs are passed explicitly (4.2) |
| `comfy_paths.APP_CABINET_ONETRAINER` | exists only so the guard can name the forbidden folder | no |

Every other constant resolves into `REPO_comfyUI` or the kobold repo.

## 4.5 What was NOT proven

Stated plainly rather than papered over:

- **No full training run was executed.** This proves the destinations and one real
  write, not eight hours of OneTrainer behaving.
- **The guards check paths we compute, not paths their code invents.** If
  OneTrainer ever writes somewhere it never declared, nothing here would catch it.
  4.2 is the closest thing to a defence, and it is a single sample.
- **Twenty files inside the moved `_face_runs` still hold the old absolute path** —
  OneTrainer's own image cache (`aggregate.pt`), past run configs under
  `workspace/config/`, and old `train.log` files. All historical records of runs
  that already happened, none of them live configuration. They were deliberately
  left alone rather than rewritten to make a scan look clean. Worst case: one
  re-cache on the next run.

---

# PART 5 — WHAT CHANGED, FILE BY FILE

**Moved:** `app_cabinet\OneTrainer\_face_profiles` → `REPO_comfyUI\_face_profiles`;
`app_cabinet\OneTrainer\_face_runs` → `REPO_comfyUI\_face_runs`.

**`REPO_comfyUI/.gitignore`** — both folders ignored.

**`REPO_koboldccp_sst_tts_media/face_training/comfy_paths.py`** — gained
`PROFILES_ROOT`, `WORK_ROOT`, `APP_CABINET_ONETRAINER`, `DataRootError`,
`check_data_root()`, `profiles_root()`, `work_root()`.

**`near_miss.py`, `profiles.py`, `pipeline.py`** — one literal each replaced by an
import.

**Left uncommitted on purpose:** another session's in-progress changes to
`face_tool_ui.py`, `otrain.py`, `sort_photos.py` and `thumbs.py`. Not mine to
commit.

---

# PART 6 — STILL OPEN AFTER THIS

1. The ComfyUI verification run — the 43-check list and the on-screen checks. The
   app has still not been started since the move.
2. `face_training` itself has still not moved out of the kobold repo. The blocker
   (the open face tool window) is gone now, so this is simply outstanding.
3. The launcher's seven duties, to be built once ComfyUI is proven.
4. The same clean-room treatment for the remaining third-party apps:
   text-generation-webui, SillyTavern, and the avatarAI upstream.
