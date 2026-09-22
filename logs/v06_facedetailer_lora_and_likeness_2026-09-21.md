# v06 — face repaint, LoRA strength, and the likeness hunt

Everything from the sessions of 2026-09-20 and 2026-09-21: what was measured, what was
built, what was built wrongly and removed, every number behind every setting now in the
workflow, and what is still unanswered.

- Times are LOCAL.
- Every claim here names its evidence: a file and line, a node id, a live server
  response, or a measured number. Where something could **not** be established it says
  so in those words rather than being rounded up to a conclusion.
- Companion records: `logs/facedetailer_research_and_install_2026-09-19.md` (how the
  FaceDetailer got into v05), `logs/portrait_master_exhaustive.md` (STEP 4),
  `logs/OneTrainer_Face_LoRA_Handbook.pdf` (written this session; ignored by git, see §3).

---

# PART 1 — WHERE THINGS STAND

## 1.1 The workflow
`user/default/workflows/Freedom_bigLust_SDXL v06.json` — **40 nodes, 41 links**.
v05 is untouched and still works.

## 1.2 Settings as left
| Where | Setting | Value |
|---|---|---|
| STEP 3 face shelf | selected | `susana_head_sdxl_pony` (HEAD-only) |
| | strength | **0.9** |
| | trigger_weight | **1.1** |
| STEP 6 LoRA stack | slot 1 | `faces/susana_head_sdxl_pony.safetensors` at **0.9**, ON |
| | slots 2-12 | empty |
| STEP 2 face source | mode | `trained_face` |
| STEP 11 SWITCH | value | `true` |
| STEP 11b FaceDetailer | guide_size | 1024 |
| | **max_size** | **1024** (was 2048) |
| | **denoise** | **0.55** (was 0.45) |
| | **feather** | **8** (was 5) |
| | **bbox_crop_factor** | **3.0** (was 2.0) |
| | **cycle** | **2** (was 1) |
| | steps / cfg | 26 / 6 — unchanged, already match community guidance for Pony |
| | wildcard | **wired** from STEP 3's trigger output |

Her total LoRA strength is 1.8, applied as **two separate passes** of 0.9. See §7 for why
that is not the same as one pass at 1.8.

## 1.3 Commits
```
7a8cad0  v06: the STEP 4 radio buttons become real dropdowns, so the phone can set them too
dc66652  v06: the face repaint follows the shelf, switches itself off, and is tuned for likeness
```
The settings in §1.2 from the LoRA-stacking work are **not yet committed** at the time of
writing.

---

# PART 2 — THE LIKENESS HUNT, AND WHAT ACTUALLY CAUSED THE STRONG EXPRESSION

This was the session's most important finding and it overturned three of my own earlier
explanations.

## 2.1 The complaint
The rendered face was an older, wrinkled, crooked-teeth version of her, and the
expression was far too strong — while the prompt's expression group sat at its lowest
setting. The user reported that a few days earlier the expression had been too **weak**.

## 2.2 Three wrong explanations of mine, in order

**Wrong #1 — the FaceDetailer.** I suspected the repaint was amplifying the expression
because it repaints the face conditioned on the whole scene sentence. Ruled out by the
user's own observation that detailer-on and detailer-off images looked identical, and by
measurement: only 7.44 mean change inside the face box.

**Wrong #2 — the drool line outranking the expression line.** In the saved v06 file the
expression group is at 1.1 and `(thick translucent drool dripping from her mouth:1.2)` is
higher, so I concluded the drool line was holding the mouth open. **The saved file is not
what was being run.** The images actually being generated have both at 1.1, and no
FaceDetailer node in the graph at all.

**Wrong #3 — the head_body LoRA switch.** v05 changed the selected face from head-only to
head+body. I checked the body training set: 454 images from 146 sources, mostly neutral or
smiling. That switch should have *weakened* the expression, not strengthened it.

## 2.3 The actual cause, from 979 archived images

Every image in `output/freedom_archive` carries its own graph. Reading the expression
weight and the LoRA out of all of them gives this:

| when | expression weight | what the user was doing |
|---|---|---|
| 7–15 Sep | **1.3 to 1.7** (peaked at 1.7 on 14 Sep) | pushing it UP, too weak |
| 18 Sep 21:31 | 1.2 | starts dropping |
| 18 Sep 21:57 | 1.1 | still dropping |
| 20 Sep | 1.1 | still too strong |

**All four LoRA files were retrained on 2026-09-18** — file mtimes 01:19, 04:53, 06:10 and
11:55 in `models/loras/faces/`. The first run against the new files was that evening, and
the behaviour flips at exactly that point from pushing the dial up to pulling it down.

**Why the new LoRA carries the expression.** The head training set is 164 images:
- **144 of them (88%) are frames from just two videos** — 91 from one, 53 from another
- 17 real photographs contribute one image each
- **zero** images are square; median aspect 0.574, tall strips
- typical width 450–570 px, smallest 256, all trained at 1024 — upscaled 2–4×
- many frames are mid-speech, mouth open
- several carry burnt-in on-screen text reading "Day 15/16"
- **only 6 distinct captions**, all describing head orientation only
  (`lorasusana woman, head and shoulders, facing forward` etc.)

Not one caption mentions expression. The captioning rule (sourced, see §3) is that the
LoRA learns whatever is in the image but *not* in the caption and binds it to the trigger
word. Nobody told the trainer her mouth was open, so an open mouth became part of what
`lorasusana` means.

The old LoRA was undertrained — the repo's own 3 September log says so — which is why
the expression previously had to come entirely from the prompt at 1.4 to 1.7.

**Consequence:** no number in the prompt box fixes this, because the expression no longer
comes from the prompt box. It arrives with her face. It is fixed by retraining.

## 2.4 The training run's own numbers
`_face_runs/susana/susana_head_sdxl_pony/config.json`:
- base model `cyberrealisticPony_v110` — **correct**, matches the generation checkpoint
- lora_rank 16, **lora_alpha 1.0** → alpha/rank multiplier of **0.0625**
- learning_rate 0.0003 → **effective rate 0.0000188**, the very bottom of the 1e-4 to 1e-5
  range the community quotes
- 164 images × 20 epochs ÷ 4 accumulation = **~820 optimiser steps**; the repo's own
  3 Sep log set the target at 1,500–2,000
- loss_weight_fn `CONSTANT` — the recommended `min_snr_gamma` weighting is OFF, while the
  Gamma box sits at 5.0 doing nothing
- masked_training `False`, validation `False`, clear_cache_before_training `False`

---

# PART 3 — THE ONETRAINER HANDBOOK

`logs/OneTrainer_Face_LoRA_Handbook.pdf` — 86 pages, ~22,000 words.

- Covers **all 454 controls** across 10 tabs and 9 sub-windows. Coverage was verified
  programmatically against an extracted inventory, not by eye: 454 assigned, 0 missing.
- 386 carry the developer's own tooltip, rewritten in plain language; 364 have their real
  default resolved from the config modules. Where nothing documents a control, the entry
  says so rather than inventing an explanation.
- 27 boxes carry community commentary, credited to the names contributors post under on
  OneTrainer's own wiki: Caith, Alaiya of OnePawProductions, Malessar, Ejektaflex, efhosci.
- Sourced from the installed source at commit `23df383`, the nine shipped docs, the
  project wiki (developer pages and community pages), discussion #388, and community
  face-training guides.

**It is not in git.** `.gitignore:43` ignores `logs/*` but re-admits `.md`, `.py` and
`.json` — not `.pdf`. The file exists on disk only.

Findings from writing it that bear on this repo:
- alpha ÷ rank multiplies the learning rate (wiki, stated outright)
- min-SNR weighting at gamma 5 is recommended for SDXL by both the wiki and the
  developer's own discussion forum
- the Concepts tab has a **Resolution Override** whose documented purpose is preventing
  image upscaling — exactly our 460px-frames-at-1024 problem
- the **Concept Statistics** tab would have shown the upscaling, the aspect ratios and the
  caption truncation in about ten seconds

---

# PART 4 — v06 STRUCTURAL WORK

## 4.1 Radios → dropdowns (commit 7a8cad0)
The STEP 4 radio buttons were page elements drawn by `portrait_control.js`, so only the
desktop had them. Evidence, from 42 real runs in `/history`: the one desktop-submitted run
carried the hidden `state` field in full (497 chars); **every phone run carried it empty**.
The phone's client id is `mobile-a0ijlixkn`.

Every choice is now a real dropdown on node 4a — `n4b..n4g` mode and preset, plus
`active_of_pair` and `prompt_styler_switch`. Declared **optional** and appended **after**
mode/preset/state, because saved workflows store widget values by position.

**Bug found by the live test that reasoning had missed:** the applier only ever switched
the *other* half of the Base Character / Face Generator pair OFF. The page code used to
switch the chosen one ON as you clicked, so the server never had to. With no page code the
pair dropdown turned one off and left **both** off. `_activate()` added as the missing half.

## 4.2 Titles and collapse
Every node title now reads `STEP n - RealToolName - plain description`, so the name on
screen is the name you would search for or find in the developer's docs. 25 nodes
retitled; the 12 MarkdownNotes left alone. All 40 nodes open collapsed.

## 4.3 The FaceDetailer dial note
Node 37 now documents **all 28 FaceDetailer dials**, grouped by function, each read out of
the Impact Pack's own source — `feather` blurs the paste-back mask at `impact_pack.py:310`;
`drop_size` discards detections smaller than that in either direction; `bbox_threshold` is
the detector's confidence cut-off. The six SAM dials are marked as inert here because
`models/sams/` does not exist.

## 4.4 STEP 12 was invisible to everything but this PC
`FreedomPreviewPick.hold()` returned its pictures under a **private key**,
`freedom_files`, which only `freedom_folder_inspector`'s own JavaScript can read — and
that runs on the desktop only. On the phone, and to anything reading `/history`, the node
appeared to produce **zero images** while the pictures existed the whole time.

Fixed in `save_pick.py` by emitting ComfyUI's own `images` key **as well**. Verified: node
9 went from 0 images to 1 under the standard key, while still emitting `freedom_files` so
the desktop picker is unchanged.

This predated this session. It became visible only when the user ran from the phone.

---

# PART 5 — THE WILDCARD AND THE REPAINT GATE (commit dc66652)

## 5.1 Wildcard follows the shelf
STEP 11b's `wildcard` widget was converted to an input and wired to STEP 3's `trigger`
output (node 2, slot 2). Whichever face the shelf holds is what the repaint is told to
paint; it empties itself when the face is switched off.

Measured, same seed: wildcard carrying the trigger vs an empty box moved the face region
by **3.84** across 6.2% of pixels — the same order as the entire repaint, so not noise.
A fuller face prompt differed from the bare trigger by only **2.33**, so *having something*
in that box matters far more than what it says. Sharpness was unchanged across all three
(5.46 / 5.49 / 5.43) — the wildcard changes what gets painted, not how crisply.

**Note:** with trigger_weight at 1.1 the box receives `(lorasusana:1.1)` and nothing else.
The face is repainted with her name alone — no lighting, no skin texture.

## 5.2 Repaint switches itself off on random face
Three **stock** nodes, no custom code:
- `PrimitiveString` holding `trained_face`
- `ImpactCompare` (`a = b`) against STEP 2's `mode_text`
- `ImpactLogicalOperators` set to `and`, combined with the existing STEP 11 SWITCH

Feeds STEP 11c's `cond`. Both conditions must agree.

Verified by execution time, which is the honest signal because the branch is lazy:

| STEP 2 | switch | time | repaint |
|---|---|---|---|
| trained_face | ON | **40.5s** | ran |
| random_face | ON | **12.1s** | never built |
| trained_face | OFF | **14.1s** | never built |

---

# PART 6 — THE ELEVEN-SETTING SWEEP, AND WHAT IT PROVED

Run 2026-09-20, seed 123456789 throughout, measured as mean change inside the face box
against the detailer-OFF image. A baseline re-run reproduced the original **bit-for-bit**,
so the harness is sound.

| setting | face-box change | time |
|---|---|---|
| baseline (guide 1024, max 2048, denoise 0.45) | 7.44 | 38.3s |
| denoise 0.60 | 11.09 | 40.3s |
| denoise 0.75 | 15.83 | 42.2s |
| denoise 0.90 | 21.16 | 40.3s |
| **guide 768** | **7.44 — bit-for-bit identical to guide 1024** | 42.3s |
| guide 512 | 8.00 | 28.2s |
| guide 384 | 9.56 | 22.1s |
| guide 256 | 11.15 | 20.2s |
| max_size 768 | 10.94 | 20.2s |
| max_size 1024 | 9.43 | 20.1s |
| max_size 3072 | 6.35 | 90.7s |

**The finding that changed the settings:** `guide_size` was doing nothing. 768 and 1024
produced *identical* images because `max_size` clamped both. **max_size is the binding
constraint**, and *lowering* it raises the repaint's effect while costing less time. Hence
max_size 2048 → 1024.

**The uncomfortable finding:** sharpness inside the face was **7.06 with the detailer off**
and **6.56–6.94 across all eleven settings with it on**. Not one tested setting made the
face sharper than not using the detailer at all. The repaint changes the face; it does not
crisp it.

---

# PART 7 — STACKING THE SAME LoRA: THE COMMUNITY WAS RIGHT AND I WAS WRONG

## 7.1 The question
Is two applications at 0.9 the same as one at 1.8?

## 7.2 What I predicted from the source, and got wrong
`ModelPatcher.add_patches` (`comfy/model_patcher.py:842-864`) **appends** each patch to a
list rather than merging. I read that as consistent with pure addition and predicted the
two would be equivalent.

## 7.3 What the test showed
Same seed, same total of 1.8:

- **100% of pixels differ.** Mean difference **60.8**, max 238. Not a rounding wobble — a
  completely different picture.

| arrangement | sharpness | colour spread |
|---|---|---|
| one pass at 1.8 | **1.89** | 31.0 |
| **two passes at 0.9** | **3.47** | **44.7** |
| 1.1 + 0.9 (total 2.0) | 3.21 | 50.9 |

**Two at 0.9 is 84% sharper than the same total in one lump**, with far richer colour. The
single 1.8 shows exactly the flattened, washed-out look that a LoRA gives when overcooked.

This is why §1.2 uses 0.9 + 0.9 rather than a single 1.8.

## 7.4 Shelf strength sweep (seed 777111333)
| shelf strength | sharpness | colour spread |
|---|---|---|
| 1.0 | **2.76** | 30.6 |
| 1.2 | 2.38 | 30.5 |
| 1.4 | 2.35 | **24.3** |

Strength changes the **whole frame**, not just the face — 100% of pixels move, mean 32.9
between 1.0 and 1.2. The colour collapse at 1.4 is the early symptom of overcooking.

---

# PART 8 — DEFECTS FOUND, INCLUDING MINE

| # | Defect | Where | Resolution |
|---|---|---|---|
| 1 | Built a node the user never asked for | **mine** | The user said to wire the shelf LoRA into the FaceDetailer. It was **already wired**. The correct response was to say so and wait. Instead I built `FreedomFaceDetailLora`, added a shelf output, rewired, restarted 4×, ran 7 test generations. Removed entirely on request; shelf restored, package deleted, wiring returned to node 3. |
| 2 | Reinvented an existing node | **mine** | `FreedomLoadLoraWired` already existed in `freedom_folder_inspector` — a LoRA loader taking the filename on a wire, with **separate** model and clip strengths and a -20..20 range. I should have found it. |
| 3 | 86-page PDF shipped dark-on-dark | **mine** | Two page templates were registered but `NextPageTemplate` was never used, so the dark cover ran through all 85 pages. Missed across three separate visual checks. Fixed. |
| 4 | Claimed the clip dial worked | **mine** | Tooltip and note said to use it when the LoRA overrides your words. With an empty wildcard box the result is bit-identical whatever it is set to — FaceDetailer touches its clip input only inside `if wildcard_opt != ""` (`core.py:268`). Both corrected to say so. |
| 5 | Predicted stacking was equivalent | **mine** | See §7.2. Wrong; the test disproved it. |
| 6 | Findings dumped in an appendix | **mine** | Put the handbook's four key findings in Appendix A instead of in the chapters they belong to. Moved into the flow; the appendix is a bare checklist. |
| 7 | Description node did not render | **mine** | Hand-built a MarkdownNote in JSON without `inputs` and `outputs` keys, which every working note has. Anything walking those lists skipped it. Fixed; all nodes then swept for missing standard keys. |
| 8 | Node hidden under another | **mine** | Placed a node at x=3550 with an existing node at x=3580, both collapsed. Invisible. Moved, recoloured; whole canvas swept for overlaps — that was the only one. |
| 9 | Test side effect changed a real setting | **mine** | Test runs repointed `freedom_save_settings.json` at the test folder. Reverted before committing. |
| 10 | Wrong widget order reported | **mine** | Paired FaceDetailer widget names to values without accounting for the frontend's `control_after_generate` and the converted `wildcard` slot. Now derived from `/object_info` and validated against 4 known values before any write. |
| 11 | Saved file did not match what was being run | found | The saved v06 held head+body at 0.9 while the best batch used **head-only at 1.0**, changed in the browser and never saved. Reloading would have silently swapped the LoRA. File corrected to match. |

---

# PART 9 — MECHANISMS ESTABLISHED (so they are not re-derived)

- **The trigger word is not in the LoRA.** It lives in `models/loras/faces/_registry.json`
  as `lorasusana` for all four files. ComfyUI's `load_lora_for_models`
  (`comfy/sd.py:102-127`) only stores metadata as an attachment; it never injects text.
  OneTrainer's FAQ: the trigger word for embeddings is the filename, and **none exists for
  LoRA**. Confirmed against all 164 caption files — every one begins `lorasusana`.
- **A1111's `<lora:...>` syntax does not work here.** Tested: nothing loaded, zero
  LoRA-related log lines, 99.3% of pixels changed because the tag was read as words. The
  installed Prompt Control extension *does* support it, but needs `PCLazyLoraLoader`, which
  is **not in the workflow** — only `PCLazyTextEncode` is. Its README warns about exactly
  this case.
- **Typing the trigger word again does not strengthen it**, it rerolls the picture: 99.8%
  of pixels changed, whole frame.
- **STEP 4a needs no wire.** The add-on registers `add_on_prompt_handler` and finds the
  node by class name at queue time. Server log confirms it applying presets on real runs.
- **The phone has no tooltip support at all** — zero references in its bundle. The only
  text it shows for a setting is the setting's name. Descriptions must live in notes,
  which the phone does render.
- **Generations do not pause when the phone sleeps.** The job runs on the PC regardless.
  What stops is browser-driven infinite mode, because there is no server-side infinite
  mode — the app queues each next run. Push notifications exist in CueForge but cannot
  work here: `pywebpush` is not installed, and the phone reaches ComfyUI over plain HTTP
  while push requires HTTPS.

---

# PART 10 — WHAT IS STILL OPEN

| Item | State |
|---|---|
| Does the current arrangement actually look more like her? | **Unmeasured.** Every strength and stacking test was a single seed. The mechanical questions are settled; likeness is not. |
| The LoRA itself | **Unfixed.** 88% of its training set is two videos. Until retrained, more strength means more of the baked-in open-mouth expression. |
| trigger_weight 1.1 | A deliberate step past the 0.8–1.0 anyone documents. Drop to 1.0 first if the body composition goes strange. |
| Pivotal tuning | Does not exist in this pipeline. |
| The 1,123-image pool | `processed/cropped` holds 1,123 images and `clean/body` 454. The head LoRA used 164 of them. An audit of that pool was offered and declined. |
| Settings from §1.2 | **Not committed** at time of writing. |
