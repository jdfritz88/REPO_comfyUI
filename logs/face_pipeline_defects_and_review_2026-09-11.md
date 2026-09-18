# Face pipeline: silent defects, and giving the person a say — 2026-09-11

An overnight session. Started as "unzip these archives and run the face search",
became four pipeline defects and five app changes. Every defect had the same
character: **it failed silently and produced unusable training data with no
error.** Nothing crashed. Folders looked full. The files in them were wrong.

Branch: `branch09-comfyui-repo-migration`.

---

## 1. The archives

Twelve zips, 85.5 GB, on `\\PERSONALCLOUD\Public\Photos & Videos\Temp as of
2026-09-11`.

All twelve carry the same top-level `iCloud Photos/` folder, so they merge.
Extracted with `unzip -n` per instruction — existing files win, duplicates are
not written.

**Verified**: 13,497 archive entries checked against the filesystem, **0
missing**. 9,829 unique files on disk, the gap being deduplication working.

Two findings worth keeping:

- **`iCloud Photos01.zip` and `02.zip` are byte-identical** — same size, same
  1,363-entry list, nothing unique to either. 5.68 GB of redundant archive.
- **The 38.67 GB archive holds only 228 files**, ~170 MB each. Almost entirely
  video.

**One mistake, reversed.** `iCloud Photos 2017.zip` had already been extracted
years ago into `iCloud Photos 2017/`. Re-extracting it into `iCloud Photos/`
added 621 duplicates — `unzip -n` could not prevent it, because it compares
target *paths* and the path differed. All 621 verified byte-identical to their
originals by SHA-256, then removed. Originals untouched.

---

## 2. Two run-level failures before any code was wrong

**Git Bash mangled the UNC path.** `\\PERSONALCLOUD\...` reached Python as
`\PERSONALCLOUD\...` — one backslash, not a valid UNC path. Seek registered a
folder that did not resolve and silently rescanned the old 2000–2025 cache
instead, reporting **0 new files**. Fixed by using the forward-slash form
(`//PERSONALCLOUD/...`), which Python resolves and the shell does not touch.

**Two seek runs ran concurrently for six hours.** A launch I had declared dead
was alive the whole time — it was buffering, so its log sat at 21 bytes while it
worked. Both were writing the same SQLite cache and the same `profile.json`.
Killed the older one; database verified `integrity_check: ok` afterwards, 33,527
file rows and 73,992 face rows intact. Throughput roughly doubled once they
stopped competing.

Lesson recorded: `ps` in Git Bash does not see native Windows processes. Use
`Get-CimInstance Win32_Process`, and check the log's mtime — a file being
written this second is alive whatever `ps` says.

---

## 3. Four silent defects

### 3.1 The detector could not see tall frames

InsightFace letterboxes an image into its square 640×640 input. A 1:3 body strip
is therefore scaled to fit by height, and the face shrinks with it — a face 300
px across arrives at 100 and is simply not found. No error; the photo just never
counts.

Not a rare path: the body strip crop produces tall narrow frames **by design**.

`_detect()` gained a third fallback, after the existing whole-frame padding
retry: past 1.6:1, detect again at an input shaped like the frame.

| crop | before | after |
| --- | --- | --- |
| 541×1980 | none | face 611×768 |
| 850×2210 | none | face 599×766 |
| 499×1536 | none | face 338×400 |

**Measured over the real cache: 388 files that had zero faces now have one.**
Those were invisible to every previous run, in every folder, for every person.

### 3.2 The head crop sliced through faces

`_tight_head_crop` pulls its edges inward to exclude a neighbour, with no guard
against crossing her own face box. The sanity check afterwards compared the crop
to the face's **size**, never its **position** — so a crop sitting beside her
face passed as long as it was wide enough. One real crop kept a single eye and
half a nose.

Her box is now the floor for all four edges. A neighbour may end up in frame;
she is always whole.

### 3.3 The strip cap could only trim from the top

`_body_strip_crop` trimmed from the top and stopped at her face. A subject
already near the top of the frame had nothing to give, so the cap was abandoned
**without a word** and the strip kept its full height. One crop came out
312×3174 — 1:10.2, roughly 85% pavement.

Whatever the top cannot give up now comes off the bottom.

### 3.4 `_loose_crop` had no cap at all

Only visible **because 3.3 was fixed**: 190 bad crops fell to 48, and the
remainder came from a path the fix never touched. When the strip collapses,
`_body_strip_crop` falls back to `_loose_crop`, which breaches the cap by
construction — ten face-heights over 4.2 face-widths is about 3:1 before
clamping starts.

Evidence: a 317×1630 crop at 1:5.1 whose face was 190 px tall where the cap
allowed 824. Nothing to do with her face being large; it was simply never
capped.

Both paths now share one `_cap_height` helper.

**Result: over-cap crops 190 → 0.**

---

## 4. What the dataset actually contained

| finding | count |
| --- | --- |
| body crops exceeding the 2.6 aspect cap | **190 of 293 (64%)** |
| of those, 4:1 or worse | 67 |
| worst | 1:10.2, 85% pavement |
| head crops that were AI-generated | **11 of 27 (41%)** |
| total AI-generated crops removed | 40 |

The AI crops all traced to `F:/Chest/Stable Diffusion/My Stuff` with no
surviving original. **33 more were left alone deliberately**: their filename
stems match a Stable Diffusion path *and* surviving real photos (`IMG_0949` has
eleven cache entries across 2006, 2012 and the SD folder). Crop filenames carry
only the stem, so provenance is genuinely ambiguous and deleting would be a
guess.

---

## 5. Five app changes

**`processed/` instead of deletion.** `found/` emptied by deletion, so the
moment a crop was written the only local copy of the original went in the bin —
fine until the crop turns out to be wrong, and 190 of them were. Photos now move
to `processed/<outcome>/`: `cropped`, `not_her`, `no_face`, `unreadable`. That
also preserves what deletion destroyed: which photos were considered and turned
**down**, and why.

**Needs review, with a screen.** `facebank.decide()` has always returned a
`borderline` flag; Seek logged it and guessed anyway. A wrong guess either lost a
good photo or trained on a stranger, and the original was deleted immediately so
there was no way to tell which. Borderline photos now go to `needs_review/`, and
the Face Tool shows each one as a thumbnail with **Yes, it's her** (queues it) or
**Not her** (removes it, and teaches the judge). **Process N approved** then
crops the queue through `seek.process_one` — the same path the clean stage uses,
so the review screen decides *which* photos are hers, never how they are cut.

Only possible because originals are kept now. The old Review button could show a
filename and a score, because the photo it asked about was already destroyed.

**Two anchor photos.** One anchor is one lighting, one angle, one day. Add person
now asks for two and averages them — and checks them against each other: below
0.45 cosine they are probably different people, which is almost always the wrong
file in the chooser, and is now said out loud.

**Every folder built at creation.** `create()` makes all of them, including
tonight's additions. A run should never be the thing that discovers a directory
is missing.

**Videos travel the path.** Frame extraction is untouched — scene changes,
sharpest frame, dedup. But each `video_frames/<hash>/` now carries a
`_source.json` naming its clip, because frame folders are named by content hash
alone and there was no way back. Search pulls a matched video into `found/`;
clean files it to `processed/cropped/`. Nothing is re-cut; the frames were
already cropped as stills.

---

## 6. Where Susana's dataset ended up

```
clean/head               23   captions 23, 10 distinct, 0 over cap
clean/body              255   captions 255, 49 distinct, 0 over cap
processed                26   originals kept
recrop_pending          178   superseded crops
removed_ai_generated     40
```

**The ceiling has not moved, and no pipeline fix touches it.** Head median short
side is **498 px** against the 1024 training resolution, and **1 of 23** head
crops meets it. That is decided by the source photography — candid shots where
the face is small in frame — not by anything in the code.

10,289 newly scanned files produced 11 more head crops. More data did not help.
A deliberate photo session would.

---

## 7. Outstanding

- **None of section 5 has run end-to-end.** All unit-verified, none exercised by
  a real seek. Annia's run is the test.
- `recrop_pending/` holds 178 superseded crops; replacements are already in the
  clean set.
- Portrait Master's preset-precedence and seed fixes are on disk but **not live**
  — ComfyUI needs restarting (`c` in the launcher).
- The 33 ambiguous AI-provenance crops remain in the training set.
- Whether to retrain Susana on the current set, given the resolution ceiling.
