# face_training — face LoRAs, and the Face Tool

Two ways in from the launcher:

- **5. Train a NEW face LoRA** — quick path. Point it at ONE folder of one
  person; it sorts + crops the photos, trains a LoRA per picture-model family per
  crop, renders a thumbnail for each, and records them on the shelf. (This path
  does not go through the review page.)
- **6. Face Seek** — a small window. Keeps a **profile** per person, can **Seek**
  a person through a big photo library into a training set, makes you **review
  every crop in the browser** before anything trains, Stop/Resume any run, and
  gets sharper at identity matching the more people it processes.

**What the cropper can and cannot do.** Every crop is checked for other
people's faces after it is cut, and trimmed until none remain. When that is not
possible — another face overlaps hers, or trimming would leave a crop under
256 px — the crop is kept and **framed yellow** on the review page. It cannot see
people whose faces are not visible (turned away, cut off, out of focus): a face
detector finds faces, not bodies. Those are for the person reviewing to catch.
(Until 2026-09-13 this README said Seek "crops everyone else out"; it never did.
See `logs/face_seek_review_rotation_and_dataset_audit_2026-09-13.md` §7.)

## The Face Tool

`face_tool_ui.py` (tkinter, runs in OneTrainer's venv). Profile list with a
status per person — **Updated** (all LoRAs current), **Resume** (a run stopped
partway, or a Clean set not yet trained), **Review** (crops waiting for your
review), **Start** (seeded only), **Working** (a Seek or a training run).

- **+ Add person** — pick exactly **two** clear photos of the face (no folder;
  the same file twice is refused). `identity.py` builds the identity from those
  two faces and warns if they look like different people. Then choose the folder
  to search and whether to include subfolders — **the search starts at once**.
- **Seek / Resume seek** — `seek.py` runs eight checkpointed stages:
  **scan** (cache face detection over the folder; read every frame of every
  video in memory with the original sharpest-per-scene method and record those
  frames' faces — no frame is saved to disk),
  **learn** (fold confident solo matches into the identity), **group** (find her
  in multi-person photos and **copy** each original into `found/`), **reteach**
  (rebuild the identity from the two photos + her face in every capture),
  **search** (copy every other original she's in into `found/`; for each video
  she's matched in, pull **every** frame of the stretches she's on screen into
  `video_frames/<video>/`), **frames** (prune those pulled frames: delete every
  blurred, unfocused, duplicate and near-duplicate one, keep the sharpest of
  each angle and expression), **clean** (crop
  each `found/` copy into `clean/head` + `clean/body`, check each crop for other
  people's faces, trim or flag it, caption it on her face), **dedupe** (remove
  exact and near-identical crops, keeping the larger, sharper one).
  Nothing is cut from a library photo directly and no original is moved or
  edited. **Stop** saves progress (Seek exits with code 3, never "done");
  **Resume seek** re-enters the first unfinished stage.
- **Review crops** — the mandatory review page (`review_server.py`, opens in the
  browser when a Seek finishes, or once at the end of a whole library run).
  Legend pinned at the top. Tick crops and **Delete** (to the Recycle Bin; the
  original is recorded as *not this person* so no later search copies it again;
  other crops from the same original stay; the judge is **not** taught), or
  **Rotate Left / Rotate Right** (caption re-measured, turn logged). **Proceed**
  starts training. **Train** opens the review page while a review is pending.
- **Delete** — removes a person. A radio button chooses **everything**, or
  **choose what to delete** with a check box per part: copied photos/videos and
  pulled frames, cropped training photos, what it learned (identity, scan cache,
  search history), backup snapshots, training work folders, trained LoRAs with
  their thumbnails and face-shelf entry, and the profile itself. Each part shows
  how many files and how much disk it holds. Everything goes to the **Recycle
  Bin**; only the face-shelf registry line is rewritten and cannot be undone.
  Disabled while a search or training is running for that person.
- **Uncertain photos and videos** — everything Seek could not call is answered on
  the same review page (user, 2026-09-15; the Face Tool's old **Needs review**
  window is gone, and so is the **Review N** button removed on 2026-09-14):
  - a **video** plays in the page. Watch it, and when she first appears press
    **She appears here**: the moment showing is written down, and the next search
    starts that video at that frame instead of the beginning — including videos
    the search never matched her in at all, which it then pulls frames from.
    **Not her** deletes the copy and records both the answer and the deletion in
    the search history.
  - a **photo** shows with **Yes, it's her** (kept in `needs_review/_approved`
    until the Face Tool's *Process approved photos* button cuts it into the Clean
    set) and **Not her** (deleted). Those answers train the judge (below).
  - the person's row shows one **Review** button whenever crops, uncertain photos
    or uncertain videos are waiting, with a note of what is waiting.

Every capture, crop, deletion, rotation and removed duplicate is written to
`<profile>/search_history.json`.

### How it improves over time (`facebank.py`, shared across all profiles)

1. **Other-people bank** — every face Seek rules out is saved. The per-person
   match cutoff is set from how close the nearest *other* face is: loose with a
   small bank, tight with a large one. Automatic.
2. **Feedback log** — when Seek cannot tell whether a face is her, it sets the
   copy aside in `needs_review` and logs its scores. An answer in **Needs
   review** is paired with those scores and becomes a labeled example. Seek's
   own unsure guesses are **never** used as examples (changed 2026-09-14: they
   used to be, as if a guess were the answer).
3. **The judge** — once there are 200+ of your answers (some "her", some "not
   her"), a small logistic model (hand-rolled, no sklearn) trained on similarity
   features replaces the fixed cutoff. Retrains after every Seek and every
   answer.
4. **Crop margins** — if you delete many crops from a Clean set by hand (in
   Explorer), the head/body crop margins widen a little next time. Deletions made
   on the review page are not counted: they mean "not this person", not "bad
   margins".

Storage: `_face_profiles/<slug>/` per person; `_face_profiles/_global/` for the
bank, feedback log, judge, and crop prefs.

### Video (`video_frames.py`)

No video frame is saved to disk unless Seek has matched her in it (changed
2026-09-14: Seek used to save every kept frame of every video as a .jpg in
`<profile>/video_frames/`, whether or not the person was in it — 14,526 files,
2.67 GB, for one library). The user's rules (2026-09-15): look at **every**
frame of a video, seek the best frame, accept no duplicates or near-duplicates,
but seek every different angle and expression if the picture is sharp; and a
face that does not look like her is not her. Two passes:

**1. Scan — every video** (the user's original method, chosen 2026-09-07):
- every frame is looked at: a histogram jump from the frame before is a scene
  cut, and the sharpest frame of each scene is kept (both measured on a copy
  shrunk to 480 px wide; it used to look only 2 times a second)
- near-duplicates across the video's kept frames are dropped: a perceptual hash
  first, then face-fingerprint similarity ≥ 0.93 — the video near-duplicate
  check the user said to keep where it is (2026-09-13)
- each kept frame's faces go into the scan cache as a row named
  `<video path>::frame=<n>`; nothing is written; the video is marked done so a
  resume skips it

**2. Pull her frames — only a video she has been matched in.** When group or
search matches her in one of its frames, the video is copied into `found/` and
read again:
- faces are looked for twice a second and her face is picked with Seek's own
  match rule; an unsure call is **not** her. A run of checks that all found her
  is one stretch she is on screen for (finding faces costs ~2 s a frame, so it
  cannot run on every frame — and this only runs on videos she is in at all)
- **every** frame of those stretches is written into
  `<profile>/video_and_frames/<video>__<hash>/`, blurry and duplicate alike
  (user, 2026-09-15), together with **a copy of the video itself**, which stays
  there — the user wants those videos for other projects. (Profiles made before
  2026-09-15 have this folder as `video_frames/` and keep using it.) A manifest
  beside them holds her landmarks for each frame, worked out from the checks
  either side, so the next stage never has to look for a face again
- if she is never clearly there but a check was **unsure**, a copy of the video
  goes to `<profile>/uncertain/` for a person to look at, and nothing is pulled

**3. The frames stage — after the search.** Every pulled frame that is blurred,
unfocused, a duplicate or a near-duplicate is deleted; the sharpest of each
angle and expression is kept:
- **blurred or unfocused**: her face aligned to 112 px scores < 200 on Laplacian
  variance (measured on 33 frames of her side by side: 257+ crisp, 202 slightly
  soft but detailed, 137 and below visibly blurred)
- **duplicate**: her face has a twin among the frames already kept — the same
  head angle (turn and nod change < 0.08, lean change < 5°, from the five face
  landmarks) and the same look (the aligned face, its eyes band and its mouth
  band each correlate ≥ 0.90, set by measuring 147 same-face pairs of
  consecutive frames side by side). The sharper of the two is the one kept
- the survivors are cropped by the **clean** stage like any other photo

Near-identical crops coming from different videos or photos are still removed
by the **dedupe** stage at the end.

### Backup (`backup.py`)

Each profile's *tracking* state - `profile.json`, `identity/`,
`scan_cache/faces.db` and `search_history.json` (not the cropped photos, not the
LoRA files) - is kept
in 5 rotating snapshots at `<profile>/backup/1/` (newest) through `.../5/`
(oldest). A fresh backup runs automatically whenever a Seek or Train run ends
(finished or stopped) and whenever the Face Tool window or the launcher
console closes (its X button included, via a Windows console-control
handler). The Face Tool also has manual "Backup" and "Restore" buttons per
person.

## ⚠ Training settings — text-encoder training is the user's choice (c)

Decided 2026-09-13. The three options were:

- **(a)** Leave it off, like OneTrainer's preset.
- **(b)** Turn it on with OneTrainer's base defaults: same learning rate as the rest of the model, stop after 30 epochs.
- **(c)** Turn it on at half the learning rate, the common community practice. Nobody has tested that at our settings.

**Chosen: (c).** Every training job uses:

| setting | value |
|---|---|
| text encoders 1 + 2 | trained |
| their learning rate | 0.00015 (half of the model's 0.0003) |
| stop training them | after 30 epochs — OneTrainer's base default; option (c) did not name a stop point |
| rank / alpha | 16 / 1 |
| random flip | off |

No authoritative source gives tested text-encoder values for a real-person SDXL
LoRA (OneTrainer's SDXL LoRA preset has it off; Kohya's SDXL docs recommend
training the UNet only). The values live in `otrain.py`; the same banner is
printed at the top of every training log and shown on the review page.

## What comes out

For each person, per `jobs.py`:

| file | trained on | pairs with the prompt |
|---|---|---|
| `<name>_head_sdxl.safetensors` | base SDXL 1.0 | put her head on a pose |
| `<name>_head_body_sdxl.safetensors` | base SDXL 1.0 | put her head and body on a pose |
| `<name>_head_sdxl_pony.safetensors` | cyberrealisticPony_v110 | (same, on Pony checkpoints) |
| `<name>_head_body_sdxl_pony.safetensors` | cyberrealisticPony_v110 | (same, on Pony checkpoints) |

Files land in `REPO_comfyUI/models/loras/faces/`.
Thumbnails in `.../faces/_thumbs/`. Shelf registry: `.../faces/_registry.json`.

A LoRA is trained for an **architecture family**, not one checkpoint. The SDXL
files work on every SDXL checkpoint; the Pony files work on Pony-style ones.

`krea2` (the family for the Flux-architecture `lustifyNSFWCheckpoint_v10Krea2`
checkpoint) is defined but **disabled** — see the reason string in `jobs.py`.

## The pieces

| file | role | runs in |
|---|---|---|
| `sort_photos.py` | identity-locked sort: learns the person from the clean solo close-ups, then finds *her* face in every photo (including couple/group shots) and writes a `head/` set (tight face crops of close-ups) and a `head_body/` set (a vertical strip keeping her body, trimmed sideways around other detected faces where it can — it does **not** guarantee other people are gone). Handles EXIF rotation and detector misses on frame-filling faces. Drops photos where she is not confidently found or the crop is too low-res. | OneTrainer venv |
| `crop_guard.py` | checks a finished crop for other people's faces; trims them out without cutting into her, or reports how many remain (yellow frame on review) | OneTrainer venv |
| `dedupe.py` | finds exact and near-identical finished crops and picks the larger, sharper copy to keep | OneTrainer venv |
| `search_history.py` | per-person record of captures, crops, "not this person" decisions and review events | stdlib |
| `review_server.py` + `review_page.html` | the mandatory local review page (127.0.0.1): tick, Delete, Rotate Left/Right, Proceed → training | OneTrainer venv |
| `otrain.py` | builds one OneTrainer config = its default + its built-in preset + this job's values; runs `scripts/train.py --config-path` headless | OneTrainer venv |
| `jobs.py` | the job table: which (family × crop) LoRAs to train, in order; which families are enabled | — |
| `thumbs.py` | renders one thumbnail per LoRA through the running ComfyUI HTTP API (also proves the LoRA loads) | stdlib (launcher or OneTrainer venv) |
| `video_frames.py` | chooses a video's frames in memory (sharpest per second, scene cuts, face-based near-duplicate filtering) and reads chosen frames back out; saves nothing | OneTrainer venv |
| `backup.py` | 5-slot rotating backup/restore of a profile's tracking state | stdlib (launcher, Face Tool, or OneTrainer venv) |
| `pipeline.py` | ties it together: sort → train each job → copy to ComfyUI → thumbnail → registry | OneTrainer venv |

## Requirements

- OneTrainer installed at `app_cabinet/OneTrainer/` with its venv
  (Python 3.10, torch cu130). `pip install insightface onnxruntime` added to
  that venv for the sorter.
- InsightFace `buffalo_l` models — reused from
  `REPO_comfyUI/models/insightface/`.
- ComfyUI running for the thumbnail step (the launcher starts a low-memory one).
- First SDXL run downloads `stabilityai/stable-diffusion-xl-base-1.0` (~7 GB fp16
  / ~16 GB with fp32) to the Hugging Face cache on `C:`.

## Numbers seen on the RTX 4080 Laptop (12 GB)

- SDXL LoRA, 1024 px, batch 1, rank 8–32: **VRAM peak ~7.4 GB** (measured before
  2026-09-13; the defaults are now rank 16, alpha 1, random flip off).
- ~20 epochs on a small set: a few minutes. A real ~2000-step run: 20–45 min per
  file, so ~2–3 hours for a full 4-file person.

## Run it by hand

```
app_cabinet/OneTrainer/venv/Scripts/python.exe -m face_training.pipeline \
    --person Britany --folder "D:/photos/britany" [--steps 2000] [--rank 16] \
    [--family sdxl] [--no-thumbnails]
```

## Adding a future model family

1. add an entry to `FAMILIES` in `otrain.py` (model_type, built-in preset path,
   base model, resolution)
2. add it to `FAMILY_ENABLED` in `jobs.py` with `(True, "")`
3. add its thumbnail checkpoint to `FAMILY_CKPT` in `thumbs.py`

Everything else is model-agnostic.
