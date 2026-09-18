# Face Seek: rotation bug, dataset audit, originals check, and the new review plan — 2026-09-12/13

A long session, mostly driven by what the user saw on Susana's crop picker page.
It began with "how do I start OneTrainer" and ended with a decision to wipe
Susana and rebuild the Face Seek pipeline around a mandatory human review.

Branch: `branch09-comfyui-repo-migration`. Commits from this session:
`63899ff` (rotation fix + logging console), `59e6209` (Face Tool Seek button verified).

---

## 1. Starting OneTrainer and finding the Face Seek app

- OneTrainer's own window: `app_cabinet\OneTrainer\start-ui.bat` (activates its
  venv, runs `scripts\train_ui_qt.py`).
- The launcher menu had changed since the saved memory: option **5** is
  "Train a NEW face LoRA", option **6** is "Face Seek" (the Face Tool window,
  `face_training\face_tool_ui.py`). The memory said 3 and 4; it was corrected.

## 2. The Review window showed "(photo not found)" for 22 photos

- All 224 borderline rows in `_global\feedback.jsonl` were written 09-08..09-11,
  before rows carried a full path (added 09-12, `e04730d`). They carry only a
  file name.
- The photo library was reorganised on 09-12 (`_organize_logs\FINAL_REPORT.txt`:
  28,427 moves), so every path in Seek's scan cache is stale.
- The user asked the review to focus on Seek's copies, not originals. Only 12 of
  the 22 had any copy (crops in `clean`, or video frames); 10 had none, because
  before 09-11 16:32 (`a73d40f`) the clean stage deleted `found\` copies after
  cropping, and search never copies rejected photos.

## 3. How many photos/frames were captured

- 09-08/09 library run: 47 group + 8 solo photos; crops 21 face / 167 body;
  7,428 video frames pulled.
- 09-11 run (after group progress was reset): 163 group + 26 solo; crops
  27 / 293; 4,873 more frames. The two runs overlap and cannot be added.
- Total video frames on disk: 12,301 from 4,274 videos (all people, not just her).
- Correction made during the session: I first said the 09-11 run left no log.
  It did — `logs\seek_susana_20260911-050153.log` and
  `logs\seek_susana_recrop_20260911-164426.log`; my search had truncated output.

## 4. Crop picker page (scratchpad, local only)

- A local server + page (`scratchpad\crop_picker\`) on `127.0.0.1:8765` showed all
  crops with tick boxes; ticks saved to `selections.json`. Nothing uploaded.
- Deleting a crop normally makes the Face Tool think the user dislikes crop
  margins: `profiles.clean_deletions()` vs `clean_snapshot`, and 5+ deletions call
  `facebank.nudge_crop_prefs()` on next open. To avoid that, each deletion sent
  the image + caption to the Recycle Bin **and** removed only those names from
  `clean_snapshot`. Verified each time with the app's own `clean_deletions()`
  = (kept, 0, 0) and no `crop_prefs.json`.
- The Face Tool keeps profile.json in memory and `save()` writes it whole, so it
  was closed before every deletion.
- Deleted by the user's ticks: 6 + 9 + 7 = 22 crops (with captions), all in the
  Recycle Bin. Crops went from 278 to 256 (19 face, 237 body).

## 5. Sideways photos: a real bug, now fixed

**Cause (reproduced, not inferred).** Phones store portrait video as landscape
pixels plus a display-matrix rotation tag. `video_frames.extract_frames()` opened
videos with `cv2.VideoCapture` and never enabled orientation handling:
`CAP_PROP_ORIENTATION_AUTO` read 0 and frames came out 1280x720 sideways; with it
set to 1 the same frame was 720x1280. ffprobe showed `rotation=-90` on every
source checked. No log or note ever intended rotation; training has rotation
augmentation off.

**Fix** (`63899ff`): `extract_frames` sets `CAP_PROP_ORIENTATION_AUTO` before
reading, logs each video's tag, and refuses to write frames if a tagged video's
backend will not rotate them. It is the only `VideoCapture` in the app, so the
background runner, the Face Tool Seek button and the CLI all get it. The same
commit added `face_training\logconsole.py` (per-run log files in
`logs\face_training\`) required by the debugging pipeline.

**Verification.**
- CP4: extractor on -90, +90, 180 and untagged videos (untagged byte-identical to
  before); background runner on a throwaway profile; `_global` restored by hash.
- The Face Tool button was verified by the main session (`59e6209`): real
  SendInput clicks on Seek → folder dialog → Select Folder → Subfolders OK, on a
  throwaway profile `zztestui`; 7 frames byte-identical to the direct extractor,
  all viewed upright (the 180 golfer right side up); `_global` restored, Susana's
  profile and all 512 crop/caption files hash-identical afterwards.
- Old videos are still skipped ("already extracted"), so pre-fix frames stay
  sideways until re-extracted.

**Crops rotated in place.** The user ticked 55 sideways crops, then 3 more face
crops were found by a full orientation scan. Each was backed up, turned 90°
clockwise (InsightFace landmarks decided the direction; every result viewed),
and its caption re-measured on her face picked by identity. None of the 256 crops
carries an EXIF orientation tag, so OneTrainer (which applies EXIF) will not
rotate them again.

**Desktop automation notes.** The screen locked mid-test. Mouse/keyboard input
and posted window messages did not reach the Tk button while locked; PrintWindow
could still render windows. After unlock, a Windows-MCP Type landed in the
user's Claude prompt because the terminal took focus between calls. The fix was
one script doing SendInput clicks plus WM_SETTEXT into the dialog's Folder box.

## 6. Duplicates

68 renamed files (`name__<8 hex>.jpg`) were compared with their partners:
- 47 byte-identical, 15 the same picture 1 px shorter, 4 the same photo cropped
  differently, 2 different photos sharing a name.
- Cause in code: `seek._dest_name` appends a source-content-hash suffix when the
  name is taken instead of overwriting. The renamed copies were written 09-11
  17:57–18:07, during/just after the re-crop. Logs record the re-crop
  (`retrain_and_review_gate_2026-09-12.md` §4: "125 replaced under the same name,
  33 re-cut under a new one, 19 with no replacement") but never why old copies
  stayed; the parked crops were cleared 09-12 and no re-crop script is in the repo.
- Some duplicate pairs carry different captions (older 09-10 recaption had head
  angle; Seek's cached path has no landmarks).
- The user chose **not** to remove them then.

## 7. Other people in the crops — the contradiction

- Measured: 0 of 19 face crops, **73 of 237 body crops** contain another face
  (55 distinct pictures); in 53 another face is ≥80% of hers, in 42 it is larger.
  All 73 were in the folder trained on 09-12 (checked against `clean_snapshot`).
- **The claim and the code were written together** in `a69d5e1` (09-03): README
  "crops everyone else out" and commit "crops the other people out … single-
  subject crops", while the same code trims only sideways around detected faces,
  falls back to `_loose_crop` ("maybe a sliver of a neighbour"), and Seek
  (`0da2c3a`) keeps the whole photo when no other face was detected. Nothing ever
  re-checks a finished crop. Seek logs record only counts.
- `2dbb993` (09-11) made the head crop allow neighbours to stop it slicing her
  face; only the defects log was updated, not the README.
- `recaption_folder` assumes "the largest face, others having already been
  cropped away". In 42 crops another face is larger; 2 captions last written by
  the 09-10 recaption were measured on the other person, 12 were re-measured
  today on her face, 28 have unknown provenance (22 rewritten by an undocumented
  trim pass 09-11 18:06–18:07 that first backed up 48 crops to `pre_trim_backup`).
- OneTrainer 09-12 runs: head concept 23 images, body 255 images, no warnings.
  **Correction:** the actual run config was rank 32 / alpha 32, random flip on,
  text encoders not trained — not the "rank 16 / alpha 16" I first stated (that
  was only the decision recorded in the master reference).

## 8. Research: OneTrainer docs, community, and Google AI Mode

Reddit (blocked), the OneTrainer Discord (login) and most Civitai articles could
not be read. Google AI Mode was given the technical situation with no names or photos.

- **Other people:** remove or crop them out. OneTrainer collaborator (pinned
  discussion #347): "You're treating masks like crops, but they aren't crops."
  Hugging Face SDXL guide: "no other faces appear in the training set."
- **Masking** is a partial measure (phantom bodies, extra people reported). Real
  settings: Masked Training, Unmasked Probability 0.1, Unmasked Weight 0.1,
  Normalize Masked Area Loss; masks named `<image>-masklabel.png`, white = focus.
  Masked Prior Preservation is the closest official feature for unwanted items.
- **Random flip:** off for faces; OneTrainer changed its default to off (#1045).
- **Duplicates:** community says remove; official sources are silent.
- **Quality over quantity;** drop blurry/low-res frames; no hard 1024 minimum.
- Google AI Mode got the mask setting names wrong, advised zero weight (warned
  against by maintainers) and claimed a 1024 minimum.

## 9. "Did I lose originals?" — checked

- **Face Seek never deletes, moves or edits library files.** Every delete/move in
  `face_training\*.py` targets the app's own copies, crops, backups or locks.
  Group photos are read (`_load_bgr`) and a new crop file is written; solo photos
  are copied with `shutil.copy2`; `_move_into` is only used on those copies.
- **The 09-12 library cleanup** permanently deleted 1,404 "exact duplicates":
  every kept copy still exists at the logged size (byte identity was checked by the
  cleanup at deletion time). It deleted 12 iCloud zips only after all 13,497
  entries were verified present on disk.
- **20 damaged library files:** 17 zero-filled JPGs in `2006\Uncertain` were
  already damaged when Seek fingerprinted them on 09-08 (content hash identical
  today); `2014\Uncertain\IMG_1673.JPG` was already 0 bytes then; `IMG_1652` and
  `IMG_1680` (0 bytes) have no earlier record. Same-named files elsewhere are not
  proven to be the same photos. Only a backup can restore them.
- Seek was not running; nothing Seek-related was scheduled.

## 10. Decisions for the rebuild (user, 2026-09-13)

1. **Wipe Susana completely** inside the app: crops, copies, processed, video
   frames, identity, scan records, her 5 backup snapshots, and the shared learning
   files in `_global` (other-faces bank, feedback log, judge). Leave the user's own
   folders alone (e.g. `F:\Chest`). Keep her 4 LoRAs until new ones overwrite them.
   **Do not start a Face Search** — the user starts it manually.
2. **Training:** rank 16, alpha 1, random flip off, OneTrainer text-encoder
   training on with OneTrainer's own preset values.
3. **Add person** must force the user to pick **two** starter photos, then ask
   where to search and whether to include subfolders.
4. **Copy everything first:** all found photos and videos, group photos included,
   are copied into `found\` before processing.
5. **Crops must contain only her.** If the others cannot be removed without
   cutting into her, the crop still goes to review, framed in **yellow**.
6. **Duplicates:** keep the four existing checks where they are (video frame
   near-dupes, identical-content scan, search-stage skip, other-faces bank) and add
   one check at the end of processing, before review, removing exact **and**
   near-identical copies and keeping the larger/sharper one.
7. **Mandatory browser review** after processing and before training, for both
   background and window runs: a legend pinned at the top; tick → **Delete**
   (removes the crop, records in the search history that the source is not her,
   **without teaching the judge**); tick → **Rotate Left / Rotate Right**
   (updates caption tags and the log); **Proceed** starts training.
8. Correct the README and notes so they describe what the app really does.

## 11. Open at the time of writing

- Whether choosing the search folder in Add person should start the search at
  once or only save the choice (asked).
- Library videos extracted before `63899ff` keep sideways frames (moot for Susana
  after the wipe; relevant for anyone else).
- The 20 damaged library photos need a backup to recover.
