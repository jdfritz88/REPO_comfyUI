# Face trainer — the record carried over from the kobold repo

Built 2026-09-19. The face training code, its data and its logs now live in
this repo (see `onetrainer_data_moved_out_2026-09-19.md` and the face_training
move). Its written record was still in `REPO_koboldccp_sst_tts_media/logs`, so
it was carried across to sit beside the code it describes.

How this was built, so it can be checked:

- Six documents in the kobold logs are about nothing but the face trainer and
  were carried in full: the OneTrainer master reference, the one-person LoRA
  reference, the settings inventory, the LoRA-file study, the trainer-tools
  research, and the retrain-and-review-gate session.
- Six more cover the whole media stack; only their face-trainer sections were
  taken.
- Every section was fingerprinted on whitespace-normalised text and checked
  against every section already in this repo's logs. Anything already here was
  skipped rather than copied twice.
- Nothing was deleted from the kobold repo. This is a copy.

Sections carried: 249. Skipped as already present: 0.
Skipped as not about the face trainer: 73.

---

# From `onetrainer_master_reference.md`

## OneTrainer — master reference


**Working reference. Supersedes nothing; gathers everything.**

Combines: `research_lora_training_tools_2026-09-03`, `work_log_2026-09-02_continued`,
the four `face_competition_*` logs, `comfyui_lora_stack_and_repo_migration_2026-09-07`,
`face_likeness_methods_research_2026-09-10`, `face_pipeline_defects_and_review_2026-09-11`,
`retrain_and_review_gate_2026-09-12`, `lora_training`, `onetrainer_person_lora_reference`,
`_ot_settings_inventory`, and everything researched on 2026-09-12.

Deliberately excluded: `ram_fix_and_remote_access_2026-09-05` (mentions the trainer
only in passing).

Last updated 2026-09-12.

---

### 1.1 The goal, in the user's words


> "The goal is to build a comfyUI experience with choices."

Not any one image, not any one model, not any one person. Recorded in
`logs/_my goal.md`. **Susana is the first test subject, not the objective.**
Annia is next, and she is the real test of whether the process works for anyone
rather than for one person who got hand-held through it.

The corollary the user stated, which governs every fix in this document:

> "Fixing the result but not the process is called 'lying' among humans."

Every repair must work for the next person automatically. A result achieved by
hand-editing something is not a repair.

### 1.2 The complaint that drives the training work


The trained face and face+body LoRAs **do not look like Susana**. Stated
repeatedly, across weeks. Everything in Parts 5–9 exists because of that
sentence.

### 1.3 What "a ComfyUI experience with choices" means concretely


A person opens ComfyUI, picks a face from a shelf of thumbnails, types what they
want, and gets that person. The picking, the trigger word, the LoRA loading, the
checkpoint compatibility filtering — all handled. The user should never type a
filename or know what a rank is.

That front end exists (Face Shelf, Face Router, LoRA Stack, Prompt Shelf). What
sits behind the "pick" is the subject of this document.

---

## PART 2 — RESEARCHING THE SOLUTIONS (2026-09-03)



Full log: `research_lora_training_tools_2026-09-03.md`.

### 2.1 The field, as surveyed


| tool | developer | shape | note from the survey |
| --- | --- | --- | --- |
| **kohya_ss GUI** | bmaltais | GUI over kohya sd-scripts | most documented option anywhere for SDXL; maintainer pace slowed, community forks exist |
| **OneTrainer** | Nerogar | single desktop app, GUI **and headless** | 1,600+ commits, actively maintained; community reports especially good results on photographic realistic subjects |
| **ai-toolkit** | Ostris | local web UI | probably the most popular trainer as of early 2026; the reference tool for the newest models |
| **SimpleTuner** | bghira | fine-tuning kit | power-user oriented, leans to bigger cards / rented GPUs; has an 8-bit mode that fits SDXL in 12GB |
| **ComfyUI-FluxTrainer** | — | ComfyUI node pack | steadiest ComfyUI-native choice |
| **comfyUI-Realtime-Lora** | — | ComfyUI node pack | built for SDXL on a modest card, fiddlier setup |
| **ComfyUI built-in trainer node** | — | core node | "undocumented and featureless" |

### 2.2 Constraints that shaped the choice


- **12 GB laptop card** (RTX 4080 Laptop). Rules out anything assuming 24 GB.
- **Repeatable, two-LoRAs-per-person pipeline**, not a one-off experiment.
- Must run **headless**, driven by our own code, not clicked through by hand.
- Must not contaminate ComfyUI's environment — see 4.4.

---

### 3.1 The decision


**OneTrainer (Nerogar).** Chosen 2026-09-03, installed the same day.

Reasons recorded at the time:
- one clean window, and a real headless mode
- actively maintained
- community reports of good results on photoreal subjects specifically
- supports LoRA, full fine-tune and embeddings, so the pipeline can grow without
  changing trainers

### 3.2 Why not the ComfyUI-native route


A ComfyUI path existed and was **deliberately turned down**. The built-in node
was judged *"fine for an experiment, not for a repeatable two-LoRA-per-person
pipeline."* This is why the trainer sits outside ComfyUI and why there is no
trainer node in `custom_nodes`.

### 3.3 What is and is not ours


**Third party, not written here:** OneTrainer itself, at
`app_cabinet/OneTrainer`, revision `23df383` (2026-08-19). That revision string
is stamped into every LoRA we produce as `ot_revision`, so file and checkout can
always be matched.

**Ours:** `face_training/` in this repo — the part that decides *what* gets
trained.

| file | job |
| --- | --- |
| `seek.py` | find her across an archive; the whole search run |
| `facebank.py` | the judge: keep / drop / borderline, and its feedback log |
| `identity.py` | build and hold the identity centroid |
| `sort_photos.py` | crops, detector fallbacks, measured captions |
| `near_miss.py` | second-chance admission for borderline photos |
| `scan_cache.py` | content-hashed detection cache (SQLite) |
| `video_frames.py` | pull stills out of video |
| `jobs.py` | the job table: which family × crop pairs to train |
| `otrain.py` | build one OneTrainer config, run it headless |
| `pipeline.py` | the whole run: sort → train each job → copy → thumbnail → register |
| `thumbs.py` | render each finished LoRA through ComfyUI |
| `profiles.py` | per-person state on disk |
| `backup.py` | rotating snapshots |
| `face_tool_ui.py` | the Face Tool window |
| `ot_train_entry.py` | entry point inside OneTrainer's venv |

`otrain.py` builds a config by layering three things, in order:
1. OneTrainer's own defaults (`scripts/create_train_files.py`, current schema)
2. OneTrainer's shipped preset for that family
3. our per-run values (dataset folder, output path, trigger, step count)

**We reimplement no training.** Every setting we do not set is left at
OneTrainer's default — which is the root cause of most of Part 8.

---

### 4.1 What was installed, where


```
app_cabinet/OneTrainer/          Nerogar/OneTrainer, rev 23df383 (2026-08-19)
app_cabinet/OneTrainer/venv/     own Python 3.10, torch cu130
app_cabinet/OneTrainer/_face_profiles/<slug>/    per-person state
app_cabinet/OneTrainer/_face_runs/<slug>/        per-run workspace + configs
```

### 4.2 Environment isolation


Deliberate and load-bearing. Separate venvs across the whole system:

| app | venv | python |
| --- | --- | --- |
| ComfyUI | `REPO_comfyUI/venv` | 3.13.5 |
| OneTrainer | `app_cabinet/OneTrainer/venv` | 3.10 |
| Whisper | `whisper_stt/venv` | 3.10.11 |
| A1111 | `Stable_Diffusion_SDXL/venv` | 3.10.11 |
| launcher | Windows system Python 3.10 | **stdlib only, installs nothing** |

Consequence: `face_training/` is **stdlib-only where it must be importable from
both** the launcher and OneTrainer's venv (`profiles.py` especially), while the
heavy modules run only inside OneTrainer's venv.

### 4.3 How it is launched


- Launcher option **5**: "Train a NEW face LoRA" — quick, one folder in.
- Launcher option **6**: "Face Seek" — opens the Face Tool window via
  OneTrainer's `pythonw.exe`, so insightface/torch are available.
- The Face Tool's Train button runs:
  `venv/Scripts/python.exe -m face_training.pipeline --person NAME --folder DIR [--presorted] [--retrain] --stop-file ...`

### 4.4 Krea 2 — installed-but-disabled, and why


`jobs.py` has it off with the reason recorded: its own architecture (Qwen3-VL text
encoder, Qwen-image VAE), needs the **gated** `krea/Krea-2-Raw` diffusers repo
(licence + HF token) and ~20 GB of extra downloads, the smallest Krea 2 LoRA preset
is 16 GB so a 12 GB card needs heavy offloading, and there is no Krea 2 image
workflow in ComfyUI to use the result. Enable once those are sorted.

---

## PART 5 — TESTING: THE FIVE-METHOD COMPETITION (2026-09-03/04)



**This is the single most important section in this document.**

Five methods of making a generated image look like a specific person were built
and scored, as cosine similarity against the profile's identity average.

**Reference point: a genuine, unedited photograph of her scores ~0.75.**

| # | method | score | note |
| --- | --- | --- | --- |
| 1 | ReActor full stack | **0.753** | "looks like her; face only, full body/clothes kept" |
| 3 | LoRA + FaceID + InstantID | **0.742** | "up from 0.25 before the stack — now clearly her" |
| 4 | LivePortrait + swap | 0.695 | "looks like her; face only" |
| 2 | Qwen, own instruction | -0.002 | "does not look like her" |
| 5 | mesh + pose + **trained LoRA** | **0.044** | "does not look like her yet" |

### 5.1 What this means and keeps meaning


1. **Two methods already score at photograph level** — 0.753 and 0.742 against a
   0.75 reference. That was 2026-09-04.
2. **The pure trained-LoRA route is the worst of the five**, at 0.044 — and it is
   exactly what the Face Shelf "pick" drives today. Picking Susana runs method 5.
3. This explains why retraining keeps feeling like the answer and keeps
   disappointing. Better training improves the weakest method. **It cannot reach
   0.75, because a real photograph of her only reaches 0.75.**

**Caveats, honestly:** method 5 was tested with an old 440-step file; current files
are 1,995 and 3,340 steps, so it would score better than 0.044 — but almost
certainly nowhere near 0.75. Method 3 has a known unfixed defect: framing collapses
to a face close-up because InstantID pulls toward the face; the body-pose ControlNet
strength needs raising.

### 5.2 Known ceilings from that work


- **Face swap is hard-capped.** `inswapper_128` outputs **128×128 pixels**, and the
  model is frozen and unmaintained. Any detail seen afterwards is invented by the
  restoration pass. Every swapper shares that model.
- **Not usable on SDXL:** Arc2Face (SD1.5 only), InfiniteYou (Flux). ConsistentID
  has an SDXL variant but no ComfyUI integration.

---

### 6.1 The end-to-end path a person takes


1. **Add person** in the Face Tool — name, seed folder, **two** anchor photos
   (forced since 2026-09-11; they are averaged and cross-checked, below 0.45 cosine
   it says they are probably different people). All folders auto-created.
2. **Seek** — scan archives, learn identity, group, re-teach, search, clean.
   Borderline photos go to `needs_review/` as real files.
3. **Needs review** — judge each photo by thumbnail; approved ones queue, then
   "Process approved" crops them through the same path a clean-stage photo takes.
4. **Train / Retrain / Resume** — the button says which of the three it will do.
   Train and Retrain now warn first if anything is waiting for review.
5. The pipeline sorts (or takes the pre-sorted clean set), trains each job in the
   table one at a time, copies each finished LoRA into
   `REPO_comfyUI/models/loras/faces/`, renders a thumbnail through the running
   ComfyUI, and writes the registry the Face Shelf reads.
6. In ComfyUI: the Face Shelf shows a thumbnail per trained face, filtered to the
   wired checkpoint's family; picking one loads the LoRA and emits the trigger.

### 6.2 The job table


`jobs.py`: every enabled family × crop pair. Currently `sdxl` and `sdxl_pony`,
crops `head` and `head_body` → **four LoRAs per person**. Krea 2 disabled (4.4).

### 6.3 Folder layout per person


```
clean/head, clean/body      final crops + .txt captions
processed/<outcome>/        originals kept, filed by what happened
needs_review/ , /_approved  photos the judge could not call
recrop_pending/             superseded crops (cleared for Susana 2026-09-12)
removed_ai_generated/       40 removed
video_frames/<hash>/        + _source.json naming the clip
identity/ , scan_cache/ , backup/ , train/
```

### 6.4 The most recent real run — Susana, 2026-09-12


```
started 02:28   finished 07:01   4h33m   0 errors, 0 warnings
susana_head_sdxl             2001 steps   03:06
susana_head_body_sdxl        5100 steps   04:44
susana_head_sdxl_pony        2001 steps   05:23
susana_head_body_sdxl_pony   5100 steps   07:00
```

Verified rather than taken from the summary: all four files carry that day's
timestamps, all four thumbnails rendered at 07:01, registry lists all four as
finished. Input: 23 head + 255 body crops with the fixed crops and measured
captions.

**Every training setting was identical to the 2026-09-09 run.** The data improved;
the recipe did not.

---

### 7.1 Where averaging actually happens — three places


From `face_likeness_methods_research_2026-09-10`. The user's original argument —
that training works by averaging and averaging is wrong for likeness — turned out
to be literally true in three places:

**(a) Photo selection.** `identity.py` computes `mean = _unit(embeds.mean(axis=0))`
over 512-dimensional face embeddings, then *"drops refs that pull away from the
consensus and re-averages"*, tightening inward. That centroid then gates the
dataset. **Photos where she looks typical pass; photos where she looks distinctive
score lower and are rejected first.** The set is centralised before training begins.
Magnitude never measured — open item.

**(b) Training.** Identical captions force it: with nothing to attribute variation
to, what is constant fuses to the token and what varies can only be learned as its
middle. **Fixed 2026-09-11.**

**(c) Face swap.** `ReActorBuildFaceModel` was run with `compute_method = Mean` over
the whole folder — one averaged face model.

**(d) And the yardstick is an average.** A real photo of her scores 0.75 against her
own average. That *is* the user's point, measured.

**What the papers say the real cause is:** the training objective has **no identity
term at all** — it is pure noise reconstruction, and identity lives in
high-frequency detail that barely moves the loss. Insensitivity, not arithmetic.
**Corollary that matters: more angle and lighting variety produces a *better*
likeness.** The intuitive response to the averaging theory — fewer, more uniform
photos — would make it worse.

### 7.2 Silent pipeline defects found and fixed (2026-09-11)


All four had the same character: nothing crashed, folders looked full, the files in
them were wrong.

| defect | evidence | fix |
| --- | --- | --- |
| detector blind to tall frames | InsightFace letterboxes into 640×640; a 1:3 body strip shrinks the face out of detectability | detect again at a shape matching the frame past 1.6:1 — **388 files that had zero faces now have one** |
| head crop sliced through faces | sanity check compared crop to face *size*, never *position* — one crop kept an eye and half a nose | her box is now the floor for all four edges |
| strip cap trimmed only from the top | a subject near the top had nothing to give, so the cap was abandoned silently — one crop was 312×3174, ~85% pavement | trim from the bottom too |
| `_loose_crop` had no cap at all | only visible after the previous fix; a 317×1630 crop at 1:5.1 | shared `_cap_height` helper — **over-cap crops 190 → 0** |

Also: originals are now kept in `processed/` instead of deleted (190 crops turned
out wrong and there was nothing to re-cut from); 40 AI-generated images removed,
33 left as genuinely ambiguous; 19 photos were found to have dropped out entirely
because their originals were deleted before the keep-originals change.

### 7.3 Settled questions


**Transparent PNG does not remove background.** Tested in OneTrainer's own venv:
the alpha channel is discarded and the hidden RGB passes through as visible colour
(transparent-over-black trains as **black**). OneTrainer's loader hard-sets mode to
RGB. Structural reason: the VAE takes three channels. Most background removers zero
the hidden pixels, so you would train on solid black while seeing a checkerboard —
worse than a deliberate white background. The same question got **zero replies** on
kohya_ss in 2024; genuinely undocumented.

### 7.4 The resolution ceiling


Head crops: **median short side 498 px** against a 1024 training resolution; **1 of
23** meets it. 10,289 newly scanned files produced 11 more head crops. **More data
did not help.** A deliberate photo session would. No setting touches this.

### 7.5 Diagnosing a disappointing result — order to check


1. Is the Face Shelf driving method 5 (0.044) when methods 1 and 3 score 0.75? (5.1)
2. Were the captions varied, or identical? (12)
3. Was the text encoder trained? (6)
4. Did masking actually load — are there `-masklabel.png` files? (8)
5. Is `layer_filter` empty, so everything was trained? (5)
6. Is flip on with `image_variations` 1, so half the set is permanently mirrored? (15)
7. Do the crops meet the training resolution? (7.4)

---

## PART 8 — TODAY'S RESEARCH AND FINDINGS (2026-09-12)


### 8.1 What is inside Susana's LoRA — measured from the file


```
2382 tensors = 794 modules      rank 32 on every one      198 MB
UNet input blocks   271
UNet middle block   108
UNet output blocks  410
UNet other            5
text encoder 1        0     <-- 
text encoder 2        0     <--
```

Metadata: 14 keys, all boilerplate plus `ot_branch`/`ot_revision`. No training
settings. `modelspec.author` says StabilityAI and the title says "Stable Diffusion
XL 1.0 Base LoRA" — inherited boilerplate, not a description of this file.

### 8.2 Five findings from reading source rather than docs


1. **`layer_filter_preset` is GUI-only** — headless runs never filter anything. (5)
2. **`include_train_config` ships NONE** — why no inspector can read our files. (32)
3. **`masked_prior_preservation_weight` pairs with `unmasked_weight` 0**, and is
   LoRA-only. Not in conflict with the 0.6 sweep — two configurations. (9)
4. **`image_variations` defaults to 1**, and augmentation runs before caching — so
   random flip is decided once per photo and frozen. (15)
5. **Text encoders are off because of OneTrainer's shipped preset**, restated in our
   config — not a decision made here, and never questioned. (6)

### 8.3 The uploaded guide — a worked example of why names get checked


A supplied guide described masking and regularisation for OneTrainer. Concepts
sound; mechanics wrong:

- `use_mask`, `mask_dir`, `use_regularization`, `reg_dir`, `reg_weight`,
  `lora_dropout`, `num_epochs`, `lr_scheduler`, `flip_aug`, `color_aug`,
  `image_dir`, `caption_dir` — **all twelve absent from the schema**
- YAML shown; OneTrainer uses JSON
- masks named `image01.png`; OneTrainer needs `image01-masklabel.png`
- linked to the wrong GitHub repository

The filename error is the dangerous one: follow it and no mask loads, no error
appears, training silently proceeds unmasked.

### 8.4 Where sources genuinely conflict — recorded, not resolved


| question | side A | side B |
| --- | --- | --- |
| rank / alpha | 32/16 or 32/32 | 64–256 with alpha 1 |
| learning rate | 2e-6 | 5e-5 · 1e-4 — a fiftyfold spread |
| regularisation images | "really helpful", use FFHQ | LoRAs learn from them; can destroy the class prior |
| flip for faces | enable for symmetry | hurts identity; confuses facial features |
| mask tightness | tight, face only, exclude hair | leave ~64px gap |
| LoHa for characters | forums recommend it | LyCORIS's own docs say avoid for character detail |
| full SDXL fine-tune in 12GB | documented 10.3 GB figure | will not fit |

---

## PART 9 — ALL 50 FEATURES, IN DETAIL


**50 features, of which 36 are confirmed in official documentation and 2 are
documented nowhere — see 9.3. This part is unfinished work, which is why it sits at the end beside the
decisions rather than in the middle as background.** Each entry carries what
the feature is, what the community recommends for a one-person LoRA, and what
our runs actually use. Several entries end in "no face consensus found" —
those are still to be worked through, and they are listed in 10.3.


Two halves of a picture model, needed throughout: the **text encoder** reads
words; the **UNet** paints. SDXL has *two* text encoders.

Every setting name below exists in the installed build. Verify any of them by
searching for the name in quotes in
`app_cabinet/OneTrainer/modules/util/config/TrainConfig.py` (289 settings),
`ConceptConfig.py` (51, per dataset folder) or `SampleConfig.py` (23).
Full generated inventory: `logs/_ot_settings_inventory.md`.

#### 1. Training methods — `training_method`   ✅ DECIDED: LORA

FINE_TUNE, **LORA**, EMBEDDING, FINE_TUNE_VAE. A fine-tune rewrites the whole
model (gigabytes); a LoRA is a small add-on that nudges it (our files are 198 MB);
an embedding teaches one new word without touching the model; the fourth adjusts
only the image/latent converter and is not about likeness.

**OneTrainer's own guidance (F.A.Q.):**
- Embeddings are *"good for persons, because the model has seen a lot of different
  people already. But it can't learn something completely new."*
- LoRAs are *"usually used for persons"*, trainable on *"a small dataset like 20
  images, but for flexibility you'll need more."*
- Their March-2024 guide: LoRA is *"usually the best option for distribution"*, but
  warns *"it is almost impossible to not have a LoRA bleed over to other parts of
  the base model that were not intended"* — which is what masking (8) and prior
  preservation (9) exist to limit.

**Full fine-tune is ruled out, and this settles an old open question.** Two of our
earlier research threads disagreed on whether a full SDXL fine-tune fits 12 GB.
OneTrainer's F.A.Q. answers it: *"For SDXL fine tuning, 24 Gb is not really enough
to do it without compromises."* We have 12.

**Community:** the same, less precisely — LoRA is the default for one person, and
nobody recommends a full fine-tune on a consumer card.

##### The trigger-word finding, and what was done about it


OneTrainer's F.A.Q., on trigger words: *"The trigger word used in prompts for
embeddings is simply the filename, **none exist for LoRA**."*

Their position is that a LoRA has no trigger word at all. It is applied by being
**loaded** — the adjustment numbers are added to the model's own — and it affects
everything painted while loaded, whether or not any word is typed. A word only
steers anything if the **text encoder** was trained, and ours was not (6): her file
has 794 modules and zero text-encoder modules. So `ohwxsusana` reached the encoder
having never been taught anything, and contributed nothing.

Our node does both halves: it patches model *and* CLIP, and separately emits the
trigger into the prompt. The CLIP half is a no-op on a file with no text-encoder
tensors.

**Decision (2026-09-12): keep the trigger word, and rename the convention from
`ohwx<name>` to `lora<name>`.** "ohwx" was a DreamBooth-era convention meaning
"a token the model cannot already know". `lorasusana` says what it is to anyone
reading a caption or a prompt, which matters because people read these here.

**Implemented:**
- `profiles.TRIGGER_PREFIX = "lora"` and `trigger_for_slug()` — **one definition**.
  It had been spelled out separately in `profiles.create()` and
  `pipeline.trigger_for()`, agreeing only by coincidence: captions are built from
  the profile's *stored* trigger while the registry was written from the *computed*
  one, so the two could drift apart silently.
- `pipeline.trigger_for()` now asks the profile first and only computes as a
  fallback (the launcher's quick train-from-a-folder path has no profile).
- `sort_photos.recaption_folder()` gained a safety net: with `missing_only`, a
  caption whose person-word no longer matches the current base **is rewritten**.
  Without this, changing the prefix would have left every existing set captioned
  with one word while the shelf emitted another — training and generation
  disagreeing, with no error anywhere.

*Ours: LORA. New profiles get `lora<slug>`. Susana's profile still stores
`ohwxsusana` — see the action items.*

#### 2. LoRA variants — `peft_type`   ✅ DECIDED: stay on LORA

LORA, LOHA, LOKR, OFT_2. **No BOFT in this build.** All four produce a small file
that modifies the big model; they differ in the mathematics.
- **LoRA** — the change is two small tables multiplied together. Default everywhere.
- **LoHa** — essentially two LoRAs combined by Hadamard product; more nuance per byte.
- **LoKr** — Kronecker product; **very** small files (~2.5 MB reported).
- **OFT_2** — does not add a change at all; it **rotates** the model's existing
  numbers, so what the model already knows is meant to survive intact.

**OneTrainer's own docs.** The LoRA wiki page offers three — LoRA, LoHa, **OFTv2**
— and does **not** mention LoKr, though the code has it. On OFTv2: *"a way to try
to solve some of the challenges a LoRA creates, namely overfitting and loss of
original model knowledge"*, and v2 is a large memory and speed improvement over v1.
**But its output needs [a custom node](https://github.com/Koratahiu/ComfyUI-OFTv2)
before ComfyUI can load it at all.**

**Community / LyCORIS guidelines.** Rule of thumb: *does not learn well enough* →
LoKr, low factor (4–8), full dimension. *Learns too well* → LoHa, or LoKr with a
large factor and lower dimension. On characters: **LoHa sacrifices fidelity for
generalisation — avoid for character detail** (LyCORIS' own docs, against forum
advice), and it degrades as the character gets more complex, up to NaN failures.
**LoKr is tied to the model it was trained from** and loses effect on mixes —
which matters here, given our checkpoint-mismatch history.

**The one with evidence on our exact problem.** The OFT paper reports that after
400 iterations both OFT variants preserved subject identity **while LoRA failed
to**, and at 2000 iterations LoRA was producing wrong attributes while OFT stayed
stable. Cost: more trainable parameters than LoRA. OFTv2 claims a 3× memory
reduction and 3× speedup over OFT v1.

**Caution if LoKr is ever tried:** this build's defaults are the opposite of the
guideline. `lokr_decompose_factor` defaults to **-1**, the maximum-compression,
lowest-capacity setting — switching to LoKr without changing it gives the opposite
of what the guideline prescribes.

**Decision (2026-09-12): stay on LORA.** Three practical reasons, none of them
about quality: LoHa is contraindicated for character detail; LoKr's tie to its
base model conflicts with how we generate; and OFTv2 cannot load in ComfyUI
without a node install plus teaching the Face Shelf and LoRA Stack a new file
type. **OFT is flagged as the experiment worth running later** — it is the only
option whose published evidence is specifically about identity preservation
failing under LoRA.

*Ours: LORA.*

#### 3. Rank and alpha — `lora_rank`, `lora_alpha`   ✅ DECIDED: rank 16, alpha 1 (changed 2026-09-13 from alpha 16)


> ## ⚠ TEXT-ENCODER TRAINING — THE USER'S CHOICE: (c)  (2026-09-13)
> The three options were:
> - **(a)** Leave it off, like OneTrainer's preset.
> - **(b)** Turn it on with OneTrainer's base defaults: same learning rate as the rest of the model, stop after 30 epochs.
> - **(c)** Turn it on at half the learning rate, the common community practice. Nobody has tested that at our settings.
>
> **Chosen: (c).** Settings (set in `face_training/otrain.py`, the only place):
> text encoders 1 + 2 **trained**; learning rate **0.00015** (half of the model's 0.0003);
> stop training them after **30 epochs** (OneTrainer's base default — option (c) did not name a stop point);
> base text-encoder weights 16-bit, LoRA weights 32-bit; rank 16, alpha 1, random flip off.
> Why a choice was needed: no authoritative source gives tested text-encoder values for a
> real-person SDXL LoRA; OneTrainer's SDXL LoRA preset has it off; Kohya's SDXL docs recommend UNet-only.
> The same banner is printed at the top of every training log and shown on the review page.

> **2026-09-13:** the user set **alpha to 1**, matching OneTrainer's shipped SDXL
> LoRA preset (multiplier 1/16 at rank 16). Rank stays 16. Also decided the same
> day: random flip **off**, text-encoder training **on**. The 09-12 LoRAs were
> actually trained at rank 32 / alpha 32, flip on, text encoders frozen.
> See `logs/face_seek_review_rotation_and_dataset_audit_2026-09-13.md` §10.
**Rank** is how much room the add-on gets to write down what it learned — a
sticky note or a notebook. With 23 photos, a notebook has room to write things
that are not her: the wall, that day's lighting, and the softness of a 498px crop
stretched to 1024.

**Alpha is not a second capacity dial. It is a learning-rate multiplier.**
OneTrainer's LoRA wiki page: *"The alpha value divided by the rank will be
multiplied by your learning rate."* Verified in the code — `modules/module/LoRAModule.py`
lines 581 and 795 apply `alpha / rank`. Plain LoRA scaling; **no rank-stabilised
variant**, so the rsLoRA finding below applies here.

##### The finding that reframed this (2026-09-12)


OneTrainer's **shipped SDXL LoRA preset** (`training_presets/SDXL/#sdxl 1.0 LoRA.json`)
sets `learning_rate: 0.0003` and `batch_size: 4`, and leaves rank and alpha at
the schema defaults: **rank 16, alpha 1.0**. Multiplier 1/16. Their real learning
rate is about **1.9e-5**.

Ours took their 3e-4 and set alpha = rank = 32. Multiplier 1.0. **We have been
training at sixteen times the authors' effective learning rate**, with a number
that was calibrated for a multiplier we removed. Their onboarding guide warns of
exactly this: *"Whenever you modify alpha, you must also modify the Learning
Rate."* (Our batch 1 × accumulation 4 ≈ their batch 4, so that part is fine.)

##### What the maintainers say (GitHub; Nerogar himself answers on Discord)


- **O-J1**, collaborator: *"Alpha just multiplies the weights. Leave it at 1 and
  tune around that."* On rank for SDXL: *"great results even as low as 4"*, and
  *"if you're not getting decent results at rank 16, there's a dataset issue."*
  Asked for exact numbers by another user: *"No one can explain or understand the
  exact effects of hyper-parameters, that's why hyperparam sweeps still happen."*
  ([#103](https://github.com/Nerogar/OneTrainer/discussions/103),
  [#942](https://github.com/Nerogar/OneTrainer/discussions/942))
- **madman404**: *"Network alpha is literally just a scalar on the effective
  learning rate"* — real rate = typed rate × alpha/rank — and *"any suggested
  learning rate from anyone else is completely meaningless unless they also
  provide this parameter and the rank."* Larger networks need a lower rate.
  ([#388](https://github.com/Nerogar/OneTrainer/discussions/388))
- **carlo0000**, to someone training on a Pony checkpoint as we do: use the SDXL
  defaults for rank/alpha; *"don't disable text encoder embedding."*
  ([#1069](https://github.com/Nerogar/OneTrainer/discussions/1069))
- **Onboarding guide**: *"for SDXL try 8 or 16, bigger does not equal better,
  larger ranks more easily overtrain."* Leave alpha at 1.0.
- **Their wiki's person guide** (Malessar): *"8/8 seems good for a person, 16/16
  can be better but less flexible unless with very good image captioning. Alpha
  needs to be equal or lower than rank."*

##### What the papers say


- **rsLoRA** ([2312.03732](https://arxiv.org/abs/2312.03732)): alpha/rank scaling
  *stunts* learning at higher ranks, which is why practical use stays low-rank.
  Applies to this build (see code check above). Our alpha = rank sidesteps the
  stunting only by turning the multiplier all the way up.
- **LoRA Learns Less and Forgets Less** ([2405.09673](https://arxiv.org/abs/2405.09673)):
  low rank is itself a regulariser, stronger than weight decay or dropout; higher
  rank learns more of the target and forgets more of the base model.
- **LyCORIS** ([2309.14859](https://arxiv.org/abs/2309.14859)): with the
  alpha-to-rank ratio fixed, raising capacity ≈ raising the learning rate or
  training longer — fidelity up, diversity and prompt-following down. Effects can
  *reverse* when alpha is set to 1.
- **T-LoRA** ([2507.05964](https://arxiv.org/html/2507.05964v2)) — one-to-few
  image personalisation, our situation: overfitting concentrates in the
  high-noise steps and memorises pose and background rather than the person; a
  LoRA's *effective* rank is much smaller than the number set, because many
  columns end up redundant. A big rank on few images is partly waste, partly room
  to memorise.

##### What long-time experts say


- **Gozukara**, 256 vs 32 on SDXL: *"higher rank is yielding better subject
  quality but environment quality looks reduced a lot"* — "cooking the base
  model." His low-VRAM tutorial uses 32/1.
  ([Civitai](https://civitai.com/articles/1647/lora-higher-network-rank-dimension-effect-on-sdxl-training-very-interesting))
- **Civitai ten-model author**: 64–256 with alpha 1. The outlier.
- **Practitioner thread**: 30 images → 32/16; only at 80 images → 64/32. And:
  *"possible to make it look quite similar even with about 10 images using the
  default settings"* — data quality over quantity.
  ([HF discuss](https://discuss.huggingface.co/t/perfect-lora-training-parameters-human-character/147211))
- Small/poor datasets consensus: **rank 8** for truly small sets, 16 as the
  practical first attempt.
- Corleone11's realistic-human guide, which OneTrainer's wiki links: unreachable
  (Reddit blocks fetches on three routes). Not read.

##### The poor-pictures angle


Every source on small or weak data points the same way: lower rank, because less
room means less room to memorise what is wrong. For us "what is wrong" is
concrete — her head crops are a median 498px stretched to 1024, so the softness
*is* an artifact, and a large rank has capacity to learn "her face is blurry" as
a feature of her.

**Our own evidence agrees:** an in-house test found rank 32 beat rank 64 — 64
produced an air-brushed look with less realistic skin. Less was better.

**Decision (2026-09-12): rank 16, alpha 16.** Sixteen is what their person guide
names, what their collaborator calls the floor below which the dataset is the
problem, and what the small-poor-dataset consensus supports; it halves a capacity
our own test showed was more than enough. Alpha equal to rank makes the multiplier
exactly 1, so **the learning rate number means what it says** — no hidden
sixteenfold division for the next person who opens the config, which is exactly
how we got sixteen times too hot without noticing. Their "leave alpha at 1" is the
other honest choice; it was rejected for hiding the arithmetic.

**Consequence:** at alpha = rank, the typed learning rate *is* the real rate, and
ours is currently the unmodified 3e-4 — sixteen times the authors' effective
rate. **That number cannot stay as-is once this is applied. It is feature 17's
decision and cannot be separated from this one.**

*Ours today: 32 / 32. Decided: 16 / 16. Not yet applied — see action items.*

#### 4. DoRA — `lora_decompose` (+ `_norm_epsilon`, `_output_axis`)   ✅ DECIDED: off

Splits each adjustment into "how much" and "in which direction".
[NVIDIA](https://developer.nvidia.com/blog/introducing-dora-a-high-performing-alternative-to-lora-for-fine-tuning/)
reports it beating LoRA on personalisation under identical settings, with the
**advantage largest at low ranks** — DoRA at rank 8 holding against LoRA at 32+.
**But** the reference implementation says diffusion DoRA is **experimental**,
**converges more slowly**, and that LoRA's settings will overfit with it; it wants
a lower learning rate and roughly half the rank
([BootsofLagrangian/DoRA](https://github.com/BootsofLagrangian/DoRA)).
Not a free switch — a different recipe.
**Correction (2026-09-12):** earlier research recorded DoRA as available *only* on
LoKr. Wrong. OneTrainer's LoRA wiki page says **"Only valid with LoRA"**.
**Unresolved conflict:** that same official page says DoRA gives *"much better
learning and **faster** convergence"*, while the reference implementation says it
**converges more slowly**. Both agree it needs different settings; the wiki adds a
specific one — *"you must vastly reduce your dropout probability to as much as
1/10th what you would set for regular LoRA."*

**Decision (2026-09-12): no DoRA.** The two sources that matter disagree on the
one thing that would make it worth trying — whether it converges faster or
slower — and both agree it is not a switch but a different recipe: lower
learning rate, roughly half the rank, dropout cut to a tenth. We have just
decided rank and alpha (3) and have not yet decided the learning rate (17);
adding a variant that changes all three at once would make the next run
impossible to read. Off stays off. Revisit only after a plain-LoRA run with the
decided settings has been judged.

*Ours: off. Decided: off.*

#### 5. Layer targeting — `layer_filter`, `layer_filter_preset`, `layer_filter_regex`   ✅ DECIDED: build the lookup, set attn-mlp

Which layers of the painting half get an adapter. Early layers hold composition
and pose, middle layers the subject, later layers style and fine detail.
SDXL presets: `attn-mlp` → attentions, `attn-only` → attn, `full` → everything.
**TRAP, verified today:** `layer_filter_preset` is referenced **only** in
`modules/ui/*Controller.py`. It is a graphical-interface convenience that expands
into `layer_filter` when clicked. Running headless, nothing expands it —
`layer_filter` stays empty and **every eligible layer is trained**. The shipped
SDXL preset says `attn-mlp`, which reads as attention-only and does nothing.
*Ours: empty → 794 modules, 198 MB. A GUI user picking the same preset gets a far
smaller file.*

##### Plainly (2026-09-13)


The painting half of the model is a machine of about 800 parts. A LoRA clips a
small adjustment onto individual parts; the filter is the list of which parts
get a clip. Blank means every part it is allowed to touch.

OneTrainer is two things bolted together: the **engine** and the **window**. The
preset field is a tick-box that only the window reads — when you tick attn-mlp
in the window, the window writes the real word, "attentions", into
`layer_filter`, the blank line the engine actually reads. We skip the window and
mail the form straight to the engine, so nobody fills in the blank line. Not an
install problem, and not really a bug on their side: a shortcut that only works
in a room we are not standing in. Skipping the window made the window's job
ours; we never knew that job existed.

**Why it was not caught earlier:** the preset was loaded on every run — it is in
Susana's `config.json` as `attn-mlp` — and its output was never checked against
it. Counting the modules in the finished file is a one-line check that would
have caught it on 2026-09-03. It was first run on 2026-09-12.

##### What each choice would have kept, counted from her file


| preset | filter word | modules of 794 | what it is |
| --- | --- | --- | --- |
| `attn-only` | `attn` | **560** | attention — decides *what goes where* |
| `attn-mlp` | `attentions` | **~700–722** | attention + the 140 feed-forward parts beside it (+22 connectors) |
| `full` | (blank) | **794** | + the **72** residual/convolution/time-embed parts and the first layer that reads the image — the parts that handle local texture |

Every run so far was `full`.

##### What OneTrainer's own docs say


Training page, verbatim: *"For LoRA, attn-mlp and attn-only are a safe choice."*
And: *"We recommend to stick to the default value coming with the preset … a blank
value will train all layers."* Matching is plain substring unless regex is on.
Their SDXL preset ticks `attn-mlp` — the setting we have never actually received.

##### What the papers say


- **LyCORIS** ([2309.14859](https://arxiv.org/html/2309.14859)) tested these
  same three presets. Attention-only caused *"a substantial decrease in image
  similarity"* — lost fidelity — while improving diversity; their example:
  leaving out the feed-forward layers *"prevents the model from correctly
  learning the character's uniform."* They recommend the **full** network for
  concept fidelity; attention-only was inferior for characters.
- **B-LoRA** ([2403.14572](https://arxiv.org/html/2403.14572)), SDXL-specific:
  a subject's *content* lives almost entirely in one transformer block (their
  W⁴) and its *style* in the next (W⁵); training only those two from a single
  image captures the subject while avoiding the overfitting full training
  produces.
- **Block-wise LoRA** ([2403.07500](https://arxiv.org/html/2403.07500v1)):
  the upper blocks preserve character detail, the bottom blocks alone lose
  everything — but for *identity* they still recommend all blocks, using block
  selection only when layering a style on top.

##### What the community says


Kohya's two LoRA shapes map onto this. The lighter one — essentially attention
plus feed-forward — is the common recommendation for characters; the heavier
one adds convolution, and the repeated verdict is that in practice there is
*"hardly a difference."*

##### The poor-pictures angle


Same logic as rank: fewer trained parts, less room to memorise what is wrong.
The 72 convolution parts are the ones that handle local texture, and blur from a
stretched 498px crop is exactly a texture.

**Decision (2026-09-13), two parts:**

1. **Build the lookup in `otrain.py`** — read whichever preset name is set, look
   it up in the same table the window uses, write the result into `layer_filter`.
   Then *every* preset works headless: attn-mlp, attn-only, full, or a custom
   list. Nothing hardcoded, nothing locked. Whichever choice is made, now or
   later, actually reaches the engine.
2. **Set `attn-mlp`.** The authors call it safe, their preset already ticks it,
   it keeps the feed-forward layers LyCORIS says a character needs, and it drops
   only the 72 texture parts the community says make hardly a difference. `full`
   stays a valid alternative with LyCORIS behind it — but it is what every
   disappointing run has used. B-LoRA's two-block approach is a later experiment,
   not a first choice.

*Ours today: blank → 794. Decided: attn-mlp → ~700. Not yet applied — see action
items.*

#### 6. Text encoder training — `text_encoder.train`, `text_encoder_2.train`, `.learning_rate`, `.stop_training_after`   ✅ DECIDED: train both, as variants and combined, together with 7

Whether the word-reading halves learn. If they don't, the trigger word never
learns to mean her; the likeness lives entirely in the painting half.
**Community is consistent here, unlike most areas.** Train it — but at a much
lower rate, because it memorises faster and locks the trigger word to one rigid
look. **At least 10× lower** is the most repeated rule (5e-5 UNet / 5e-6 TE is
called the golden ratio, [note.com](https://note.com/honji_nashi_23/n/nc59559367ac0?hl=en));
a more conservative version says half or less ([kohya wiki](https://github.com/bmaltais/kohya_ss/wiki/LoRA-training-parameters)).
Also recommended: **stop it early**, at 60–80% of total steps, and let the
painting half continue alone. OneTrainer's `stop_training_after` does exactly
that and ships at 30 epochs.
*Ours: both **off**. Verified in the file: 794 modules, **zero** text-encoder
modules. Off because OneTrainer's shipped SDXL preset has it off — not a decision
made here.*

##### Plainly (2026-09-13)


The model has two halves. The painter makes the picture. The **reader** turns
your words into something the painter can use — and SDXL has **two** readers, a
small one (CLIP-L) and a large one (OpenCLIP-G), reading the same prompt side by
side. Every run so far trained only the painter; the readers were frozen, so
`ohwxsusana` reached them untaught and the likeness came entirely from the
painter's add-on being loaded.

##### What OneTrainer's own docs say


Training page: *"It has been suggested that TENC1 works better with tags and
TENC2 works better with natural language, but this is not proven and based more
upon testing observation and feeling."* And: *"Trying to determine the best way
to make the text encoders act in concert … is one of the biggest challenges
with SDXL finetuning. Most success stories have had access to commercial grade
hardware, and not consumer grade."* Additional-Embeddings page: *"LR may need to
be adapted to each encoder, but there is not really any general guidance that
can be given."* Their person guide: *"the TE is optional and hard to train for
SDXL, up to you to use it or not, you can try either TE 1 or 2 as they work
differently."* Their F.A.Q.: a LoRA has no trigger word. A collaborator, to a
Pony user: *"don't disable text encoder embedding."* Each reader has its own
learning-rate field overriding the base, and its own `stop_training_after`
(ships 30 epochs).

##### What the community says — no source picks an encoder


Kohya's official SDXL document: *"Because SDXL has two text encoders, the result
of the training will be unexpected,"* and strongly recommends UNet-only. The
Civitai Opinionated Guide: *"finicky on XL and PonyXL, it doesn't always work,
it sometimes works"* — when used, 1e-4 against a base 5e-4. The rentry: *"Better
set much lower than Unet's,"* citing 5e-5. The HuggingFace script offers no
choice: *"SDXL has two text encoders, so both are fine-tuned using LoRA."* The
only stated difference between the two is one user's rationale in a kohya
feature request, not practice: CLIP-L smaller, needs a higher rate; CLIP-G more
capacity, more overfitting risk. **Stop early** at 60–80% of steps is repeated.

##### 6 against 7, and in tandem — what sources say


HuggingFace, the only measured comparison: pivotal tuning *"achieves results
competitive or better than full text encoder training and yet without
optimizing the weights of the text encoder."* Their script treats the two as
either/or flags; the diffusers docs say nothing about combining them. Replicate
shipped pivotal tuning in production with cloneofsimo. OneTrainer, on all three
together: *"very fast learning in the case of subject training"*; on the reader
plus embedding without a trained reader: Prodigy struggles. **Nobody measured
7-plus-6 against 7-alone.**

**Decision (2026-09-13): do both, as separate variants and combined.** Train
each person's LoRA four ways — CLIP-L reader on; CLIP-G reader on; embedding
(7); all three — so each can be scored on its own through 10.6 item 1's radio
buttons 7a–7d. This is the user's decision, made with the sources above in view.
Rates and stop-points are open (feature 17, and 10.6 item 7).

*Ours today: both off. Decided: on, per variant. Not yet applied.*

#### 7. Embedding training and pivotal tuning — `embedding`, `embedding_learning_rate`, `preserve_embedding_norm`, `bundle_additional_embeddings`; per-embedding `placeholder`, `token_count`, `initial_embedding_text`, `stop_training_after`   ✅ DECIDED: on, together with 6


**Plainly.** Feature 6 retrains the reader. Feature 7 leaves the reader alone
and **teaches it one new word.** The reader has a dictionary — every word maps
to a bundle of numbers. An embedding is a brand-new entry: a made-up word whose
numbers are learned from her photos until "this word" reliably means "this
face." "Pivotal tuning" is doing that first, then training the painter's add-on
*around* the word.

**OneTrainer's own docs.** Two techniques on its Additional-Embeddings page:
*"Pivotal Tuning — train an embedding separately … you have a stationary target
to train the unet against"* or *"Combined Training — train an additional
embedding as you are doing your lora … the embedding is a moving target … It is
likely best to stop training the embedding before your unet."* On the three
together: *"Using an additional embedding with LoRA training with both unet and
text encoders will result in very fast learning in the case of subject
training."* F.A.Q.: embeddings *"are good for persons, because the model has seen
a lot of different people already. But it can't learn something completely
new."* Embedding page, on size: *"2 [tokens] can be ok for simple embeddings like
a face … 6 to 10"* for body features; *"the more precise [the initial text] is,
the faster the training will be."* Practical: *"Using your caption trigger word
as the placeholder for the embedding will make things much easier."* Caution:
*"Prodigy struggles if you only train the unet and an additional embedding (and
do not train the Text Encoder(s))."*

**Community and experts.** HuggingFace measured it against reader training:
*"competitive or better … without optimizing the weights of the text encoder"*;
their face experiments used it; tokens are inserted into **both** encoders.
**Replicate built its production SDXL trainer on it** with cloneofsimo — the
person who first brought both LoRA and pivotal tuning to image models. Their
published defaults: **two tokens** for the new word; learning rates **TE 1e-5,
embedding 5e-4, UNet 1e-4**; **500 steps** teaching the word, then **1000**
training the LoRA around it; rank 4 default; a face-segmentation option; and
*"a handful of images, 5–6, is enough to fine-tune SDXL on a single person."*
Older textual-inversion practice: *"3 vectors if there are less than a hundred
training images"* — more vectors need more pictures.

**Feasibility here — checked, not assumed.** OneTrainer's SDXL embedding saver
writes `clip_l` and `clip_g` keys
(`modules/modelSaver/stableDiffusionXL/StableDiffusionXLEmbeddingSaver.py`
lines 29 and 31); ComfyUI's SDXL text handling reads exactly those two keys
(`comfy/sd1_clip.py` line 487, `comfy/sdxl_clip.py` line 21). ComfyUI loads
embeddings from `models/embeddings/` — present here and empty — via
`embedding:name` in the prompt, and warns-and-ignores if the file is missing.
**Two changes on our side:** the pipeline copies the embedding file into that
folder beside the LoRA, and the Face Shelf emits `embedding:<trigger>` instead of
the bare word. OneTrainer packages the embedding *inside* the LoRA by default and
its own LoRA page says ComfyUI will not read that form — so save it separately
(`bundle_additional_embeddings: false`, feature 41).

**Cautions from their wiki.** The word must tokenise sensibly — their
troubleshooting page shows a gibberish word producing noisy, non-converging runs
and a word with existing meaning converging on the wrong thing. Check how
`lorasusana` splits before training. And with the reader *not* trained, Prodigy
needs their workaround.

**What no source answers:** whether 7 alone beats 7 plus 6; any measured face
comparison beyond HuggingFace's one sentence.

**Decision (2026-09-13): on, and together with feature 6** — see 6 for the
combined decision and the per-variant training plan.

*Ours: never tried. Decided: on.*

#### 8. Masking — `masked_training`, `unmasked_weight`, `unmasked_probability`, `normalize_masked_area_loss`   ✅ DECIDED: an AXIS — every recipe trained both masked (option B) and unmasked

Supply a black-and-white image marking her face; the trainer concentrates there,
so hair, clothes, wall and lighting are not learned as part of her.
Mechanically (read from `modules/util/loss/masked_loss.py`): the mask is 1 inside
and 0 outside, clamped to a floor of `unmasked_weight`. So the number is *how much
the outside still counts*. `unmasked_probability` is the chance a step ignores the
mask entirely.
**0.6–0.7 when used alone.** A nine-run sweep discarded 0.1 for producing
"anatomically disproportional body"
([sweep](https://dev.to/furkangozukara/onetrainer-fine-tuning-vs-kohya-ss-dreambooth-huge-research-of-onetrainers-masked-training-4po7)).
Why: a low value means nothing outside is penalised, so the model can invent
content for free — sometimes inventing *lowers* its error
([#347](https://github.com/Nerogar/OneTrainer/discussions/347)).
**Dissent worth keeping:** that same thread advises **cropping rather than
masking** — masks are really an inpainting feature — and a maintainer calls masked
training "not a free lunch", which is why it is off by default
([#700](https://github.com/Nerogar/OneTrainer/discussions/700)).
Masks must be named `<image>-masklabel.png`. Any other name loads nothing **and
training proceeds unmasked with no error.**
*Ours: off. `otrain.py` already excludes `-masklabel.png` from image counts — the
code has always known the convention and never produced masks.*

##### Plainly (2026-09-14)


Next to each training photo goes a second picture, black and white, the same
size. White is her face; black is everything else. The trainer pays full
attention to the white and much less to the black, so her hair-that-day, her
jacket, the wall and the lighting stop being learned as part of "who she is."
**Unmasked weight** is how much the black still counts, 0 to 1. **Unmasked
probability** is what fraction of steps ignore the mask and look at the whole
photo.

##### Is it a kind of LoRA? No — verified, not reasoned


- **OneTrainer's README** lists them on separate lines: line 12, *"Training
  methods: Full fine-tuning, LoRA, embeddings"*; line 13, *"Masked Training: Let
  the training focus on just certain parts of the samples."* A method is what
  you produce; masking is a feature of the producing.
- **Kohya's documentation**, for the other major trainer: *"The masked loss is
  supported in each training script"* — *"a training feature, not a model
  type."*
- **The saved file is unchanged.** OneTrainer's model-saving code
  (`modules/modelSaver/`) contains **zero** mentions of "mask." Masking lives in
  `modules/util/loss/masked_loss.py`, the loss mixin, and the trainer loop —
  never in the LoRA module or the saver. ComfyUI cannot tell a masked-trained
  LoRA from an unmasked one and does not need to.
- **Different stage from the competition methods and Portrait Master.** Those
  run in ComfyUI *after* the file exists. Masking runs in OneTrainer *while* the
  file is being made.
- **Masking and pivot combine in production:** Replicate's pivotal-tuning
  trainer has a face-segmentation option that masks to the face during training.

##### What OneTrainer's own docs say


Training page: mask is `<image>-masklabel.png`, PNG only; *"not all images need
to have a mask"*; both numbers ship at 0.1. `normalize_masked_area_loss`: their
page says use it *"when the masked area is very large (example: jewelry)"* —
self-contradictory, since jewelry is small. The code divides the loss by the
mask's mean, which *boosts* the signal for a **small** mask. For a face filling
a head crop: **off**. Two mask-aware augmentations exist: one randomly shrinks
the mask (factor 0.2–1.0); one **crops the photo to the mask** with 10–30%
padding and up to 20° rotation — an automated "crop instead of mask."

On option B, their Prior-Prediction page, verbatim: *"Unmasked probability and
unmasked weight should be set to low values, 0 is what has been tested. Masked
Prior Preservation Weight should be set high, 1 is what has been tested."*
Concept type stays "normal." *"You should caption the entire image, as both the
normal training and prior prediction need the full caption."* Limits: LoRA only;
*"validation sets do not work"* with it. Their summary: *"results will always
vary."*

##### What the community and experts say


- The nine-run sweep: 0.1 discarded for distorted bodies; 0.6–0.7 when masking
  alone (see above).
- **O-J1**, maintainer, [#703](https://github.com/Nerogar/OneTrainer/discussions/703):
  *"Mask should have 64px gap from the intended object."* *"Do not set the weight
  ridiculously low or you will have whack outcomes."* *"Masks are not a
  replacement for cropping when necessary."* And to the same user: *"crucially get
  more data, all of your pics are pretty much all the same."*
- **Kohya's doc** on why the gap: the mask is applied at 1/8 resolution, so
  *"fine details such as earrings may not be learned well; some dilation of the
  mask may be necessary."*
- **The cheat sheet** recommends masking specifically for **photorealistic people
  with a poor dataset** — probability 0.1, weight 0.6, normalize off — and warns:
  *"Adding masked training will cause anatomy problems but the quality will be
  better when your dataset for training is low quality. So if you have a really
  good dataset do not use masked training."* Both halves describe us.
- ClipSeg prompt examples from their Tools page include *"face and hair of a
  woman."*

**Two conflicts, resolved.** Mask tightness: the uploaded guide said tight and
exclude hair; the maintainer says a 64px gap, and their own prompt example
includes hair — the maintainer wins. Caption scope: plain masking says caption
only inside the mask; option B says caption the entire image — we are on option
B, so the whole crop is captioned, which is what the measured captions already
do.

**Decision (2026-09-14): masking is an AXIS, not a shared setting.** Every one
of the four recipes (7a–7d) is trained twice — once masked with option B, once
unmasked — giving a 4 × 2 table: **eight LoRAs, eight images to score** per
person. The user chose this over "on for all four" so masked and unmasked can be
judged side by side. In item 1's button 7 this becomes **eight individual
choices plus "use all six"** — the user's own phrasing.

**Masked settings (option B):** `masked_training: true`, `unmasked_weight: 0`,
`unmasked_probability: 0`, `masked_prior_preservation_weight: 1`,
`normalize_masked_area_loss: false`. Masks from `generate_masks.py`, CLIPSEG,
prompt "face and hair of a woman", ~64px expansion. Captions unchanged. No
validation set on masked runs. **Unmasked settings:** `masked_training: false`.

*Ours today: off. Decided: both, as an axis. Not yet applied.*

#### 9. Prior preservation — `masked_prior_preservation_weight`   ✅ DECIDED: weight 1 on the masked runs of feature 8

The companion to masking, and **LoRA-only**. Adds a second loss term applying
**outside** the mask that pulls toward what the *untrained* model would have
produced. Plugs the exact hole that makes low unmasked weights dangerous.
**OneTrainer's own tested pairing: weight 1, `unmasked_weight` 0**
([wiki](https://github-wiki-see.page/m/Nerogar/OneTrainer/wiki/Prior-Prediction)).
Not in conflict with the 0.6 figure — they are two different configurations.
Verified in `masked_loss.py`: inside the mask, learn her; outside, zero learning
and full "stay as you were". Verified in `GenericTrainer.py`: when the weight
is above 0 and masking is on, every step runs the batch through the model
twice — once with the LoRA switched off for the prior, once for training — so
the masked runs are slower than the unmasked ones. The setting is **inert when
`masked_training` is off**, so it changes nothing on the unmasked runs.

##### What their docs and the author say

- Prior Prediction wiki, verbatim: *"Unmasked probability and unmasked weight
  should be set to low values, 0 is what has been tested. Masked Prior
  Preservation Weight should be set high, 1 is what has been tested."* Concept
  type "normal"; caption the whole image; validation sets do not work; LoRA only;
  *"results will always vary."*
- dxqb, who built it ([PR #505](https://github.com/Nerogar/OneTrainer/pull/505)):
  needs no regularisation photos and no special captions; on the number, *"in
  none of my experiments did I find it necessary to increase the loss weight...
  1 works well"* — kohya users going to 10–100 *"must have something else wrong."*
- The wiki's warning that adaptive optimizers struggle applies to the
  PRIOR_PREDICTION concept type; our runs use AdamW (`otrain.py`), not adaptive.

##### What the community says

- No published one-person-LoRA report with numbers exists for this setting
  (searched 2026-09-14). The masking threads
  ([#347](https://github.com/Nerogar/OneTrainer/discussions/347),
  [#700](https://github.com/Nerogar/OneTrainer/discussions/700)) are people
  hitting the phantom-body problem it was written to fix — collaborator mx:
  masking with 0 unmasked weight means *"ONLY what appears in this masked section
  matters"*; O-J1: masking is *"very clearly not free lunch."*
- kohya's sister feature, differential output preservation
  ([PR #1710](https://github.com/kohya-ss/sd-scripts/pull/1710)): users found
  weight 1 worked, 10 slowed character learning, 100 nearly stopped it; SDXL
  results inconsistent. Same message: 1, not higher.

*Ours: 0.0 (off). **Decided 2026-09-15: weight 1 on the four masked runs
(with `unmasked_weight` 0, `unmasked_probability` 0, as in feature 8); no
change to the four unmasked runs. Recorded under 10.6 item 7.***

#### 10. Mask generation — `scripts/generate_masks.py`

Built in. Models: **CLIPSEG** (takes a prompt, e.g. "face"), **REMBG**,
**REMBG_HUMAN**, **COLOR**. Options: `--mode` (replace/fill/add/subtract/blend),
`--threshold`, `--smooth-pixels`, `--expand-pixels`, `--alpha`,
`--include-subdirectories`.
**No community recommendation exists.** OneTrainer's documentation on this is two
sentences: some models take a prompt, and *"play around with Threshold, Smooth and
Expand values to find what works best for your dataset"*
([docs](https://github.com/Nerogar/OneTrainer/blob/master/docs/CaptioningAndMasking.md)).
Searched for a CLIPSEG-vs-REMBG face comparison; **none found**. Reasoning (not a
recommendation): CLIPSEG takes the word "face"; the REMBG models cut out whole
people.
Related: earlier research says leave roughly a 64px gap between mask and subject,
which is what `--expand-pixels` is for. This **conflicts** with the uploaded
guide's "tight masks excluding hair". Unresolved.
*Ours: never run.*

#### 11. Regularisation — concept `type`: STANDARD / VALIDATION / **PRIOR_PREDICTION**

Photos of *other* people shown alongside hers, so the class word ("woman") does
not quietly come to mean her.
**Genuinely contested.** "Really helpful", use FFHQ
([Civitai](https://civitai.com/articles/3701/sdxl-photorealistic-lora-tips-reflections-on-training-and-releasing-10-different-models)).
Against: a LoRA **learns from** them, so they are training data and bad ones poison
the run ([kohya #2056](https://github.com/bmaltais/kohya_ss/discussions/2056));
captioned inputs with *no* regularisation scored as well as the best regularised
run ([SDXL experiment](https://blog.aboutme.be/2023/08/10/findings-impact-regularization-captions-sdxl-subject-lora/));
an outside collection can **destroy the class prior** ([arXiv](https://arxiv.org/pdf/2510.20887)).
If used: ~1 per 2–3 training images.
**OneTrainer's own route needs no extra photos.** A PRIOR_PREDICTION concept, in
its own words: *"use the sample to make a prediction using the model as it was
before training; this prediction is then used as the training target."*
*Ours: none. **Decision: skip classic regularisation; use prior preservation (9).***

#### 12. Captions — concept `text.*`, `caps_randomize_*`, `tag_dropout_*`, `enable_tag_shuffling`

The text file beside each photo. Where the trigger word lives and where you say
which things are *her* and which are incidental.
**Largest measured effect of anything in this list.** A 14-configuration
controlled SDXL experiment: captioned sets produced a recognisable subject by
epoch 4–5; uncaptioned needed 9–10 or failed. Rule: **caption everything that
varies**, so it factors out and the token carries identity only. Token position
matters — "photo of skw woman wearing a suit" binds to the woman; "wearing an skw
suit" binds to the suit.
*Ours: **was** one identical string on every image (21/21 and 167/167 identical —
the worst possible case). **Fixed 2026-09-11**: measured per photo. Now 10 distinct
across 23 head crops, 49 across 255 body.*

#### 13. Augmentation — `enable_random_flip`, `_rotate`, `_brightness`, `_contrast`, `_saturation`, `_hue`, each with a `fixed_` variant and max-strength; plus `enable_crop_jitter`, `enable_random_circular_mask_shrink`, `enable_random_mask_rotate_crop`

Automatically varying each photo to stretch a small set.
**Split, and the split matters.** General LoRA advice: enable flip for symmetry,
unless an asymmetry matters ([kohya #2608](https://github.com/bmaltais/kohya_ss/discussions/2608),
[ScottBaker](https://www.scottbaker.ca/AI/LoRA-Training)).
**Research specifically on facial resemblance says flipping hurts**: it "slowed
learning due to face asymmetry, which confused facial features"; rotation produced
unnatural alignments; colour jitter caused erratic results. Their general finding:
when an augmented image carries an artifact, **the model attaches that artifact to
the identity**. They recommend dropping classical augmentation entirely in favour
of generated variants that hold the face consistent
([arXiv 2505.03557](https://arxiv.org/html/2505.03557v2)).
For likeness specifically, the second source governs.
*Ours: flip **on** — and see 15, which makes it worse than it sounds.*

#### 14. Resolution and bucketing — `resolution`, `aspect_ratio_bucketing`

Training size, and sorting mixed shapes into groups rather than squashing
everything square. **1024 for SDXL.**
*Ours: 1024, bucketing on. **This is the ceiling**: her head crops have a median
short side of 498px, and 1 of 23 meets 1024. Set by the source photography, not by
any setting.*

#### 15. Latent caching — `latent_caching`, and concept `image_variations`

Pre-converts pictures into the model's internal form once instead of every pass.
**Not quality-neutral in our setup.** Verified by reading the pipeline
(`DataLoaderText2ImageMixin._create_dataset`): augmentation modules run **before**
cache modules, and the cache stores `image_variations` versions per image —
**default 1**. So each photo is flipped-or-not **once**, and that single version is
used for the whole run. "Random flip" randomises nothing per epoch; roughly half
the dataset is simply permanently mirrored.
OneTrainer's own issue tracker confirms: *if you enable data augmentation you
should increase Image Variations, otherwise only a single augmented version is
cached* ([#211](https://github.com/Nerogar/OneTrainer/issues/211)). Distinct from
Repeats, which exists only to balance uneven datasets. Cost: every variation is
another cached copy.
*Ours: caching on, `image_variations` 1, flip on — the bad combination.*

#### 16. Batch size and accumulation — `batch_size`, `gradient_accumulation_steps`

How many images are seen before the model updates. Accumulation fakes a larger
batch from several small ones. Fit the card; does not change intent.
*Ours: batch 1, accumulation 4.*

#### 17. Optimizers — `optimizer` (43 available)

The rule for how corrections are applied. ADAGRAD, ADAM, **ADAMW**, **ADAMW_8BIT**,
ADAMW_ADV, AdEMAMix, ADOPT, LAMB, LARS, LION, RMSPROP, SGD, SIGNSGD_ADV,
SCHEDULE_FREE_ADAMW/SGD, DADAPT_×5, **PRODIGY**, PRODIGY_PLUS_SCHEDULE_FREE,
PRODIGY_ADV, ADAFACTOR, CAME, MUON, ADAMUON_ADV, ADABELIEF, TIGER, AIDA, YOGI, and
8-bit variants.
**AdamW8Bit most repeated; Prodigy the other common answer** because it estimates
its own step size. **Hard requirement if using Prodigy: learning rate exactly 1.0**
for UNet and text encoders — it is a multiplier on Prodigy's estimate, not a step
size. Getting that wrong silently produces nonsense.
*Ours: ADAMW, weight decay 0.01.*

#### 18. Learning rate schedulers — `learning_rate_scheduler`

CONSTANT, LINEAR, COSINE, COSINE_WITH_RESTARTS, COSINE_WITH_HARD_RESTARTS, REX,
ADAFACTOR, CUSTOM. **Constant — the one point every source agrees on.**
*Ours: CONSTANT.*

#### 19. Warmup, cycles, minimum factor — `learning_rate_warmup_steps`, `learning_rate_cycles`, `learning_rate_min_factor`

Start gently, restart partway, set a floor. **No face-specific consensus found.**
*Ours: 200 warmup steps.*

#### 20. EMA — `ema`, `ema_decay`, `ema_update_step_interval`

Saves a running average of recent states rather than the exact current one,
smoothing flukes. OFF / GPU / CPU. **0.999 for small datasets** (0.9999 for large),
update interval 5 ([OT wiki](https://github.com/Nerogar/OneTrainer/wiki/Training)).
*Ours: OFF.*

#### 21. Loss functions — `mse_strength`, `mae_strength`, `log_cosh_strength`, `huber_strength`, `huber_delta`, `vb_loss_strength`

How mistakes are scored; formulas differ in how harshly they punish large errors.
**No face consensus; MSE is standard.**
*Ours: MSE 1.0.*

#### 22. Loss weighting — `loss_weight_fn`, `loss_weight_strength`

CONSTANT, P2, **MIN_SNR_GAMMA**, DEBIASED_ESTIMATION, SIGMA. Whether all stages of
the noise-to-picture journey are scored equally. **min-SNR gamma 5 for SD1.5/SDXL**
([OT wiki](https://github.com/Nerogar/OneTrainer/wiki/Training)); one head-to-head
put min-SNR first, constant second, debiased estimation worst.
`loss_weight_strength` **is** the gamma and already defaults to 5.0.
**Warning: do not combine with `rescale_noise_scheduler_to_zero_terminal_snr`.**
*Ours: CONSTANT. Rescale is off, so min-SNR is safe to enable.*

#### 23. Noise controls — `offset_noise_weight`, `generalized_offset_noise`, `perturbation_noise_weight`, `rescale_noise_scheduler_to_zero_terminal_snr`, `force_v_prediction`, `force_epsilon_prediction`, `min_noising_strength`, `max_noising_strength`, `timestep_shift`, `dynamic_timestep_shifting`

The model learns by removing added noise; these change how much, what kind, and at
which stages. **No face consensus found.**
*Ours: all default.*

#### 24. Timestep distribution — `timestep_distribution`, `noising_weight`, `noising_bias`

UNIFORM, SIGMOID, LOGIT_NORMAL, HEAVY_TAIL, COS_MAP, INVERTED_PARABOLA, BETA.
Which stages of that journey get practised most. Broad distribution favours coarse
features (shape, pose) before fine ones (facial geometry, eye spacing). Some
OneTrainer users report timestep shift 4. **No agreed face recipe.**
*Ours: UNIFORM.*

#### 25. Gradient checkpointing and offloading — per model part: `gradient_checkpointing`, `offload_fraction`, `activation_offloading`; plus `async_offloading`

Memory savers; recompute or park parts of the model. No effect on the result.
*Ours: checkpointing on (preset default).*

#### 26. Attention mechanism — `attention_mechanism`

SDP, FLASH, CUDNN, FLEX. Speed only.
*Ours: SDP.*

#### 27. Precision and quantization — `train_dtype`, `fallback_train_dtype`, `output_dtype`, `lora_weight_dtype`, per-part `weight_dtype`, `quantization`

fp32 / fp16 / bf16 / fp8 / int8 / NF4 / GGUF variants. Fewer digits means less
memory, with some risk to fine detail. **If using bf16, enable stochastic rounding**
— described as the single setting most people miss, and it affects convergence on
fine facial detail ([neurocanvas](https://neurocanvas.net/blog/ai-toolkit-vs-onetrainer-zimage-guide/)).
*Ours: train fp16, VAE fp32, output fp32.*

#### 28. Multi-GPU and cloud — `multi_gpu`, `device_indexes`, `gradient_reduce_precision`, `cloud`

Not applicable to one laptop card.

#### 29. Live preview sampling — `sample_after`, `sample_after_unit`, `sample_skip_first`, `sample_image_format`, `samples_to_tensorboard`, `non_ema_sampling` + 23 sample settings

The trainer pauses and paints a test image from prompts you choose. **How you catch
a bad run at 40 minutes instead of 4 hours.** Recommended: use 2–4 of your actual
training captions as fixed test prompts and watch for overtraining.
*Ours: `sample_after_unit: NEVER` — deliberately off; thumbnails are rendered
through ComfyUI afterwards instead, which also proves the file loads in the tool
that will use it. **Trade-off: no early warning.***

#### 30. Validation concepts — `validation`, `validate_after`, concept `type: VALIDATION`

A held-out set, scored during training but never trained on. The honest test of
whether the model is learning *her* or memorising these exact pictures.
*Ours: never used.*

#### 31. Backups — `backup_after`, `rolling_backup`, `rolling_backup_count`, `backup_before_save`, `save_every`, `continue_last_backup`, `prevent_overwrites`

Periodic snapshots so a crash does not cost the run.
*Ours: on, and `continue_last_backup: true` — this is what makes "Resume training"
work. Checkpoints are deleted when a LoRA completes, to free disk.*

#### 32. Config embedding — `include_train_config`

NONE / SETTINGS / ALL. Writes an `ot_config` key into the finished file recording
how it was made.
*Ours: **NONE** (the shipped default). This is the entire reason every LoRA
inspector shows nothing about our files — there is nothing in them to show. Our
LoRAs carry 14 metadata keys: format boilerplate plus `ot_branch`/`ot_revision`.*

#### 33. Side tools — `scripts/`

`generate_masks.py`, `generate_captions.py`, `convert_model.py`, `video_tool_ui.py`,
`sample.py`, `calculate_loss.py`, `train_remote.py`, plus TensorBoard
(`tensorboard`, `tensorboard_port`, `tensorboard_expose`).

---

### Added by the documentation sweep of 2026-09-12


Entries 34–38 come from the official README's feature list; 39–50 from the wiki
(43 pages, read in full) and the repo's `docs/` folder. None of these are in the
config schema sections already covered above, or they are and were missed.

#### 34. Model formats — `output_model_format`

The README says "diffusers and ckpt models", which undersells it. Twelve values:
DIFFUSERS, ORIGINAL_SINGLE_FILE, ORIGINAL_TRANSFORMER, COMFY_TRANSFORMER,
LEGACY_SAFETENSORS, **DIFFUSERS_LORA, KOHYA_LORA, ORIGINAL_LORA, COMFY_LORA,
LEGACY_LORA**, SAFETENSORS, INTERNAL. It can write a LoRA in the exact flavour a
given tool expects.
*Ours: SAFETENSORS.*

#### 35. Automatic captioning — `scripts/generate_captions.py`

**BLIP, BLIP2 or WD14_VIT_2**, with `--initial-caption` (BLIP/BLIP2 only — it
continues from that text instead of an empty string), `--caption-prefix`,
`--caption-postfix`. The wiki warns the prefix/postfix add **no spaces or commas**
of their own. Given captions are the largest measured effect on likeness, this
deserved its own entry.
*Ours: never used — we write our own measured captions.*

#### 36. Multiple prompts per image — concept `prompt_source`, `prompt_path`

On the README's feature list. A caption can come from a text file per sample, from
one file containing one prompt per line, or from the filename. The single-file form
is what `docs/EmbeddingTraining.md` recommends for embedding training.
*Ours: "sample" (per-file).*

#### 37. Multi-resolution training

Listed separately from bucketing on the README — train several resolutions at once.
*Ours: single resolution, 1024.*

#### 38. Inpainting model support

A supported model category, listed in the README alongside the architectures.
*Not applicable here.*

#### 39. LoRA base model — `lora_model_name`

**Load an existing LoRA and continue training it.** A resume that is not the
crash-recovery resume of (31) — this is deliberately continuing a finished file.
A backup folder can be used instead, "but you are more limited in what can be
done". Wiki: LoRA page.
*Ours: blank, never used.*

#### 40. Dropout probability — `dropout_probability`

Randomly ignores a percentage of training nodes each step, to fight overfitting.
Wiki cites a guide recommending **0.1 to 0.5**. **Interacts with DoRA (4): if DoRA
is on, cut this to about a tenth.**
*Ours: 0.0.*

#### 41. Bundle embeddings — `bundle_additional_embeddings`

Bundles any trained embeddings into the LoRA file. **Wiki, verbatim: "This option
is only supported in Automatic1111 and SD.Next; ComfyUI does not read these."**
*Ours: **on** (the default) — and useless to us, because ComfyUI is the consumer.*

#### 42. Per-concept resolution override — `enable_resolution_override`, `resolution_override`

Train one folder at its own resolution instead of the global one. With it off,
images are up- or down-scaled to the training resolution.
**Bears directly on 7.4**: her head crops have a median short side of 498px and are
being upscaled to 1024. This is the setting that would stop that.
*Ours: off.*

#### 43. Per-concept loss weight — `loss_weight`

Weight one folder's contribution against another's. Default 1.
**Bears directly on the 23-head / 255-body imbalance** — the body set currently
dominates by count alone.
*Ours: 1.0 (unset).*

#### 44. Balancing (repeats) — `balancing`, `balancing_strategy`

Called "Balancing" in the UI, not Repeats, and the wiki is explicit that it is
**only** for balancing unbalanced concepts and should otherwise be left at 1.
*Ours: 1.0, REPEATS.*

#### 45. Text variations — `text_variations`

The caption-side twin of `image_variations` (15). Default 1.
*Ours: 1.*

#### 46. Tag shuffling — `enable_tag_shuffling`, `keep_tags_count`, `tag_delimiter`

Shuffles caption tags so order is not learned. **Official recommendation, directly
relevant:** *"If training a LoRA on a specific concept, it's a good idea keep that
concept's name (aka the 'trigger word') at the front"* — which is what
`keep_tags_count` protects.
*Ours: off.*

#### 47. Tag / caption dropout — `tag_dropout_enable`, `_probability`, `_mode`, `_special_tags`, `_special_tags_mode`, `_special_tags_regex`

Randomly drops tags from captions. Modes: **Full, Random, Random Weighted**. Special
tags can be **white-listed** (always kept, everything else droppable) or
**black-listed** (only these are droppable). Regex supported — escape special
characters.
*Ours: off.*

#### 48. Randomize capitalisation — `caps_randomize_enable`, `_mode`, `_probability`, `_lowercase`

Modes: capslock, title, first, random.
*Ours: off.*

#### 49. Dataset Tools UI — `caption_ui.py`

The interactive half of 10 and 35: browse the set, caption manually or in batch,
generate masks in batch, and **paint masks by hand with a fill option**.
**Warning from the wiki, in bold there too: you must press Enter after editing a
mask by hand or the change is not saved.**
*Ours: never opened — we drive the CLI scripts.*

#### 50. Video tools — `video_tool_ui.py`

Far more than "a video tool". **Extract Clips** with **PySceneDetect** cut
detection, max length, time ranges, FPS re-encoding (needs ffmpeg), **border
removal** for letterboxed video, and crop variation. **Extract Images** at a chosen
rate with **blur removal** by variance-of-Laplacian, discarding the blurriest of
each batch. **Download** via yt-dlp from a link or a list.
*Ours: none of it — `face_training/video_frames.py` does its own extraction.*

---

### 9.1 Behaviour that is not a setting, and can cost you images


**OneTrainer discards a resolution bucket that cannot fill a batch.** Kohya
duplicates data to fill it instead; OneTrainer throws the bucket away. Symptom:
fewer steps per epoch than expected — at the extreme, 1 or 0. Workaround: raise
balancing, or lower batch size.
Source: wiki, *Common Mistakes Coming From Kohya*.

**Checked against Susana's runs and we are clear:** 23 × 87 epochs = 2,001 steps
and 255 × 20 = 5,100, both exact. Batch size 1 means every bucket fills a batch.

Two other warnings from that page worth keeping: BF16 and F32 can produce *wildly*
different outcomes, so never compare across precisions; and if using Adafactor to
train a LoRA from scratch, **turn Scale Parameter off** — leaving it on can train
for a hundred epochs and get nowhere.

### 9.2 Mask prompts — guidance does exist after all


Earlier this document recorded "no community recommendation exists" for the mask
model. That was wrong; the wiki's Tools page gives worked examples for ClipSeg:
**"a woman"**, **"face of a woman"**, **"face and hair of a woman"**.
The ClipSeg/Rembg/Rembg-human/Hex Color choice is still undocumented as a
comparison.

### 9.3 Documentation coverage — what is confirmed where


Checked 2026-09-12 against: the GitHub README, the repo's `docs/` folder (9 files),
the complete wiki (43 pages, cloned and read), onetrainer.org, and the releases
page.

**36 of the 38 are confirmed in official documentation.** The wiki carries a
dedicated page for most of them — LoRA, Training, Concepts, Prior-Prediction,
Optimizers (three pages), Custom-Scheduler, Aspect-Ratio-Bucketing, Quantization,
Sampling, Backup-and-Save, Cloud-Training, two validation pages, Tools — plus
`docs/RamOffloading.md` (197 lines) and `docs/EmbeddingTraining.md`.

**Two exist in the code and are documented nowhere:**

| | evidence |
| --- | --- |
| **alternative loss functions** (`mse_strength`, `mae_strength`, `log_cosh_strength`, `huber_strength`, `huber_delta`) | zero mentions of MSE, MAE, Huber or log-cosh across README, `docs/` and all 43 wiki pages |
| **`include_train_config`** (32) | zero mentions anywhere. Probably why it was never switched on |

**Conflicts found between the wiki and the code**, code being authoritative for
this build:

| | wiki says | code says |
| --- | --- | --- |
| `enable_random_flip` default | On | **False** |
| LoRA types offered | LoRA, LoHa, OFTv2 | LORA, LOHA, **LOKR**, OFT_2 |
| training methods | full fine-tune, LoRA, embeddings | those plus **FINE_TUNE_VAE** |
| DreamBooth | listed as a method on onetrainer.org | not a `training_method` value; it is fine-tuning with prior preservation |

**Updates:** the releases page has **no published releases at all**. The installed
checkout `23df383` is **exactly upstream HEAD, zero commits behind** (checked via
the GitHub API). Nothing is missing from updates.

**One compatibility note for us:** OFTv2 output needs
[a custom node](https://github.com/Koratahiu/ComfyUI-OFTv2) before ComfyUI can
load it. Not native.

---

## PART 10 — CHOICES: DECIDED, AND STILL OPEN


### 10.1 Decided by the user


| | value |
| --- | --- |
| masking + prior preservation (8, 9) | **an axis**: every recipe trained masked (option B: prior weight **1**, `unmasked_weight` **0**, `unmasked_probability` **0**) *and* unmasked — 4 recipes × 2 = **eight LoRAs per person**. Feature 9 confirmed 2026-09-15: weight 1 on the masked runs only |
| dataset | **all 23** head crops — not cut to 8–12 |
| text encoder (6) | **train both** — CLIP-L and CLIP-G — as separate LoRA variants *and* combined; see 10.6 item 1 |
| embedding / pivotal tuning (7) | **on** — a third variant, and part of the combined one; see 10.6 item 1 |
| where settings live | **the Face Tool**, not a ComfyUI node |
| classic regularisation | not ruled on; prior preservation chosen instead |
| `recrop_pending/` | cleared |

### 10.2 Proposed but NOT agreed — do not switch on unasked


| | proposal | source |
| --- | --- | --- |
| `enable_random_flip` | false | facial-resemblance research (13) |
| `loss_weight_fn` | MIN_SNR_GAMMA @ 5 | OT wiki (22) |
| `include_train_config` | SETTINGS | (32) |
| `text_encoder.learning_rate` | 10× below the UNet | (6) |
| `text_encoder.stop_training_after` | 60–80% of steps | (6) |
| mask model | CLIPSEG, prompt **"face and hair of a woman"** | the wiki's own worked example (9.2) |
| `image_variations` | leave at 1 | only matters if augmentation is used |
| `bundle_additional_embeddings` | **false** | on by default and **ComfyUI cannot read it** (41) |
| `enable_resolution_override` on the head concept | consider | her crops are 498px being upscaled to 1024 (42) |
| `loss_weight` on the head concept | consider raising | 23 head vs 255 body (43) |

### 10.3 Still to work through


- **Features 19, 21, 23, 24** — warmup, loss function, noise controls, timestep
  distribution. No face consensus found for any. Currently defaults.
- **Feature 29, live preview sampling** — deliberately off. Turning it on would give
  early warning on a 4.5-hour run. Not discussed.
- **Feature 30, validation concepts** — never used. The only honest measure of
  whether it is learning her or memorising.
- **Feature 7, pivotal tuning** — the most direct fix for a meaningless trigger word.
  Never tried.
- **Feature 3, rank** — unresolved across sources; our own test says 32 is fine.
- **Feature 3, alpha** — now the sharper question. Alpha/rank multiplies the
  learning rate, and ours is 1.0 against a shipped 0.0625. Either alpha or the
  learning rate is likely too high; which one has not been tested.
- **Feature 17, optimizer** — AdamW vs Prodigy. Prodigy needs LR exactly 1.0.
- **Feature 40, dropout** — 0.1–0.5 recommended, ours is 0. Untried, and it
  interacts with DoRA.
- **Feature 42, per-concept resolution override** — the only setting that speaks to
  the 498px ceiling without new photography.
- **Feature 43, per-concept loss weight** — the only setting that speaks to the
  23-vs-255 imbalance without deleting photos.
- **Features 46 and 47, tag shuffling and dropout** — untried, and the wiki's
  keep-trigger-word-first advice is directly on point.
- **Mask tightness** — 64px gap vs tight-to-face. Unresolved conflict (10).
- **DoRA convergence** — official wiki says faster, reference implementation says
  slower (4). Unresolved.

### 10.4 The thing that outranks all of the above


**Section 5.1.** The Face Shelf pick drives the method that scored 0.044 while two
built methods score 0.75. No training setting in Parts 9 or 10 closes that gap.
Changing what the pick *connects to* was offered on 2026-09-10 and was not
authorised. It remains the highest-value change available.

### 10.5 Build queue, in the user's stated order


1. text encoder training
2. strength sweep
3. block sweep
4. Inspire Pack install

Plus, from the same conversation: training settings exposed in the Face Tool, and
mask generation wired to `generate_masks.py`.

**Nothing in this queue has been built yet.**

### 10.6 Action items


Numbered. **Item 1 is the newest and sits first by the user's instruction**; the
feature-sourced groups follow in the order they were decided, then what was
carried from earlier. A feature number in brackets points at Part 9.

#### 1. Images — the workflow's ending selector, with scoring (added 2026-09-13)


**As stated by the user, replayed.** The main workflow gets a way to choose how
it *ends*: a set of radio buttons, one chosen per run.

| button | what it produces |
| --- | --- |
| **1** | **No add-ons.** No LoRAs, no injections, **and Portrait Master off** — it has its own button (8). The base checkpoint and the prompt, nothing else. |
| **2** | **All five methods** from the five-method competition, in one run — five images. **Portrait Master excluded.** |
| **3** | Competition **Method 1** — face swap (ReActor stack). |
| **4** | Competition **Method 2** — instruction edit. |
| **5** | Competition **Method 3** — identity fingerprint + her trained file (FaceID + InstantID + LoRA). |
| **6** | Competition **Method 4** — expression copy (LivePortrait). |
| **7** | Competition **Method 5** — the trained-LoRA route. **The user's words (2026-09-14): "instead of 4 choices, there are eight, including use all six versions."** Eight individual choices — four recipes × masked/unmasked, **one image each** — plus a ninth, "use all six." Masked = option B; unmasked = `masked_training` off. The recipe letters 7a–7e are the user's; **the `-m` / `-u` suffixes are a proposal, not yet named by the user.** |
| 7a-m · 7a-u | all three training additions **combined** in one LoRA — masked · unmasked |
| 7b-m · 7b-u | LoRA trained with the **CLIP-L** reader on (feature 6) — masked · unmasked |
| 7c-m · 7c-u | LoRA trained with the **CLIP-G** reader on (feature 6) — masked · unmasked |
| 7d-m · 7d-u | LoRA trained with the **embedding / pivot** (feature 7) — masked · unmasked |
| 7e | **"use all six"** — 7b, 7c and 7d in both halves, run **separately** → **six images**. 7a's two are *not* included; they are their own choices. |
| **8** | **Portrait Master.** |
| **9** | **All of the above, de-duplicated** — each distinct method once (2 is not run again on top of 3–7), including every 7 variant. **Portrait Master excluded.** **Ten or more images from one run is expected**: the same picture with different versions of the same face. |

**Two rules that apply to every button, stated by the user (2026-09-13):**

- **Portrait Master never combines.** It invents a woman from dropdowns; every
  other method puts *her* in. Two answers to "who is she" is a conflict, so it
  is only ever its own ending — button 8 — and **every "run all" button (2, 9)
  excludes it and says so in its description.**
- **Each selected method makes its own image.** Methods do not merge into one
  picture. The one exception is where combining is *explicitly specified* —
  7a, the three training additions in one LoRA. Everything else, including 7e
  and buttons 2 and 9, is one image per method or per named combination.

**Scoring, stated as IMPORTANT by the user.** Every image gets a grading scale
at its bottom: **two thumbs down · one thumbs down · one thumbs up · two thumbs
up.** Every score is **recorded and tallied per method.** That much is part of
this item. The **separate AI that nudges each method toward two-thumbs-up is
not** — the user called it "a different animal" and moved it to the very last
action item (item 9), to be attempted only after everything else is installed
and tested.

**Can the competition tab be wired in? Yes — the mechanism already exists.**
`freedom_face_competition` is one shared-inputs node (`FreedomFaceComp`: pose
image, photo folder, expression, prompt, negative, instruction, driving image,
hair reference) plus a web panel with **five checkboxes and a Run button**; a
ticked box *bypasses that method's whole group*. The radio buttons are the same
mechanism with one-of-many instead of any-of. The honest cost: that workflow is
**121 nodes in 9 groups**; the main workflow is 29. Two ways to join them — merge
the five method groups into the main graph (~150 nodes, one file), or keep the
workflows separate and have the selector *dispatch* to the right saved
workflow(s). The second is the smaller first version. **Proposal, not decided.**

**What the training side must produce for button 7.** Four LoRA variants per
person: CLIP-L-on, CLIP-G-on, embedding, and all-three. That is four training
runs where there is now one — roughly four times the wall-clock per person. The
job table (`jobs.py`) grows a "variant" axis beside family × crop.

**Questions asked and answered (2026-09-13):**
1. 7d was written twice — the second is **7e**. Table corrected.
2. 7b and 7c are the **CLIP-L and CLIP-G readers** trained (feature 6); 7d is the
   **pivot embedding** (feature 7). Confirmed as read.
3. Buttons 3–7 are competition Methods 1–5 in order; 7 is Method 5, the trained
   file. Confirmed.
4. Button 1 has **Portrait Master off** as well — which is why Portrait Master
   needs its own button, 8. Table corrected.
5. The overlap between 2 and 3–7 inside 9 was a mistake in the instruction — 9 is
   **de-duplicated**. Ten or more images from one run is intended. **Neither 2 nor
   9 includes Portrait Master** — see the two rules under the table.
6. The nudging AI may change **only settings available at the Run / image
   generation stage** — nothing on the training side. And it is a different
   animal: **moved to the very last action item**, after every other item is
   installed and tested.
7. Where scores live, and tying each score to the settings that produced its
   image, is **part of that final item**, not this one. The user: "not even sure
   we can do it."
8. Four training runs per person: **accepted** — and on 2026-09-14 raised to
   **eight** when masking became a second axis (feature 8). The user chose this
   knowing it doubles the table: *"I want this."*

**Not started.**

#### 2. From feature 1 (decided 2026-09-12)


- [x] **Trigger prefix `ohwx` → `lora`.** One definition in `profiles.py`;
      `pipeline.trigger_for()` defers to the profile; `recaption_folder()` rewrites
      captions whose person-word no longer matches. Done.
- [ ] **Migrate Susana's profile from `ohwxsusana` to `lorasusana`.** Her stored
      trigger is untouched, so she keeps the old word until someone changes it.
      Changing it makes her 278 existing captions stale — which the new safety net
      *will* rewrite on her next training run, but her four current LoRA files were
      trained on the old word and would be orphaned. **So this should happen
      together with her next retrain, not before it.** Needs a decision.
- [x] **Decide whether the trigger word goes in the prompt at all.** Resolved by
      features 6 and 7 on 2026-09-13: it stays, the readers learn it, and once an
      embedding exists the Face Shelf emits `embedding:<trigger>` instead of the
      bare word.

#### 3. From feature 2 (decided 2026-09-12)


- [x] **Stay on `peft_type: LORA`.** No code change — it is already what we use,
      and the decision is now recorded rather than inherited. Done.
- [ ] **Queue OFT_2 as an experiment.** The only alternative whose published
      evidence is about identity preservation failing under LoRA. Blocked on three
      things, none of them training: install
      [ComfyUI-OFTv2](https://github.com/Koratahiu/ComfyUI-OFTv2); teach
      `freedom_face_shelf` and `freedom_lora_stack` to recognise and load an OFT
      file; and decide how the registry distinguishes it from a LoRA. Not started.
- [ ] **If LoKr is ever tried, change `lokr_decompose_factor` first.** It defaults
      to -1, the lowest-capacity setting, which is the opposite of the guideline
      for "does not learn well enough". Recorded so the trap is not walked into.

#### 4. From feature 3 (decided 2026-09-12)


- [x] **Rank 16 applied — with alpha 1, not 16.** Done in commit `35c9cf8`
      (2026-09-13, a second session of the user's): `Job.lora_rank` 16,
      `Job.lora_alpha` 1.0, and `pipeline.LORA_ALPHA = 1.0`. The user changed alpha
      from the 16 recorded here to 1, matching OneTrainer's shipped preset —
      multiplier 1/16 at rank 16, so the effective rate at 3e-4 is now ~1.9e-5.
      Verified there by building a real config. Feature 3's entry carries the
      note. The same commit turned random flip **off** (feature 13).
- [ ] **Feature 17 must follow, not precede, this.** At alpha = rank the typed
      learning rate is the real rate, and 3e-4 is sixteen times what OneTrainer's
      own preset runs at (1/16 × 3e-4 ≈ 1.9e-5). The rate needs its own decision
      before the next training run.
- [ ] **Record the multiplier in the Face Tool's training screen** when that
      screen is built: show `alpha / rank` next to the learning rate, so the next
      person sees the real rate and never inherits a hidden ×16 again.

#### 5. From feature 4 (decided 2026-09-12)


- [x] **`lora_decompose` stays off.** No code change — it is already off and
      `otrain.py` never sets it. Recorded so it is a decision rather than a
      default nobody looked at. Done.
- [ ] **If DoRA is ever revisited, it is a recipe, not a switch.** Change three
      things together — lower learning rate, roughly half the rank, dropout to a
      tenth — and only after a plain-LoRA run with the decided settings has been
      judged, so the comparison is against something known. The faster-vs-slower
      convergence conflict between OneTrainer's wiki and the reference
      implementation is unresolved; a run would settle it for us.

#### 6. From feature 5 (decided 2026-09-13)


- [ ] **Build the preset lookup in `otrain.py`.** When the config is built, read
      `layer_filter_preset` from the merged config, look it up in the same
      `LAYER_PRESETS` table the window uses, and write the result to
      `layer_filter` as a comma-separated string. Verify first whether that table
      (on `BaseStableDiffusionXLSetup`) can be imported from `otrain.py` without
      dragging in the full model stack; if not, read it the way
      `modules/ui/ModelTabController.py` does. Copying the table into our code is
      the kind of duplicate that drifts — avoid it. Not yet built.
- [ ] **Set the preset to `attn-mlp`.** Once the lookup exists, this is one word
      in the config; until then it is inert. Not yet applied.
- [ ] **Add the module count to the pipeline's post-run summary.** Count the
      trained modules in the finished `.safetensors` and print it beside the
      preset that was requested, so a filter that silently did not apply is
      visible in the log of every run — this is the one-line check that would
      have caught the trap on 2026-09-03. Not yet built.
- [ ] **When the Face Tool settings screen is built**, offer attn-only /
      attn-mlp / full / custom as a dropdown, backed by the same lookup.
- [ ] **Later experiment, not queued:** B-LoRA's two-block filter for a single
      subject. Needs custom filter strings naming the specific SDXL blocks.

#### 7. From features 6 and 7 (decided together, 2026-09-13)


- [ ] **Train each person's LoRA in eight variants**, per 10.6 item 1: four
      recipes — CLIP-L reader on; CLIP-G reader on; embedding (pivotal tuning);
      all three combined — **each trained masked (option B) and unmasked**
      (feature 8, 2026-09-14). `jobs.py` gains two axes beside family × crop:
      recipe × masking. At ~1–2.5 h per LoRA on this card, that is a full day or
      more per person per family; the user accepted this. Not built.
- [ ] **Feature 9 (decided 2026-09-15): the four masked runs set
      `masked_prior_preservation_weight: 1`** alongside `unmasked_weight: 0` and
      `unmasked_probability: 0`. The four unmasked runs leave it at 0 — the
      setting does nothing when `masked_training` is off. Each masked step runs
      the model twice, so budget extra time for those four. Not built.
- [ ] **Reader rates.** Community rule is ≥10× below the painter's; Replicate's
      published pairing is TE 1e-5 / embedding 5e-4 / UNet 1e-4. OneTrainer gives
      *"no general guidance"* per encoder. Set per variant in `otrain.py`; use
      `stop_training_after` (ships 30 epochs) at 60–80% of the run. Values not
      yet decided — see feature 17.
- [ ] **Embedding settings.** Two tokens (OneTrainer: "2 can be ok for a face";
      Replicate default: two). Placeholder = the caption trigger word (their
      advice). Initial text = a short description. `bundle_additional_embeddings:
      false` so the file is saved separately. Not built.
- [ ] **Check how `lorasusana` tokenises** before any reader or embedding
      training — their wiki shows a gibberish word producing noisy
      non-convergence. Not done.
- [ ] **Pipeline: copy the embedding into `REPO_comfyUI/models/embeddings/`**
      beside the LoRA, and register it. Not built.
- [ ] **Face Shelf: emit `embedding:<trigger>`** when an embedding exists for
      the picked face; bare word otherwise. Not built.
- [ ] **If Prodigy is chosen (17)** and a variant trains the embedding without the
      readers, apply OneTrainer's workaround (growth limit 2, BF16). Recorded.

#### 8. Carried from earlier


- [ ] Work through features 10–50 and finalise each. Features 1–9 are closed.
- [ ] The 21 uncertain photos still on the archive have never been judged by the
      current app.
- [ ] Whether the 2026-09-12 retrain improved the likeness — the user's call.
- [ ] 33 ambiguous AI-provenance crops remain in the training set.
- [ ] `bundle_additional_embeddings` is on and ComfyUI cannot read it (41).
- [ ] **Section 10.4 still outranks all of the above.**

#### 9. The nudging AI — LAST, only after items 1–8 are installed and tested (added 2026-09-13)


By the user's instruction this is the final item and is not to be started
before everything above it works. The user's own words: *"a different animal"*
and *"not even sure we can do it."*

- What it is: a separate process that reads the thumbs scores from item 1 and
  adjusts a method's settings so its next images move toward two-thumbs-up.
- **Its levers are limited to settings available at the Run / image-generation
  stage** — LoRA strength, block weights, ControlNet strength, CFG, and the like,
  per method. **Never training settings.**
- Includes the design that item 1 deliberately leaves out: where scores live,
  and **tying every score to the exact settings that produced its image**, so
  there is something to learn from. Without that linkage there is nothing to
  nudge.
- Whether it is feasible at all is an open question, stated as such.

**Not started, and not to be started yet.**

---

# From `onetrainer_person_lora_reference.md`

## OneTrainer for a one-person LoRA — what exists, and what the internet says


Written 2026-09-12. Two rules for this document:

1. **Every feature is named exactly as it appears in your installed build**, so
   you can check it exists yourself. Nothing here is "OneTrainer can probably".
2. **Every recommendation carries a link.** Where sources disagree, the
   disagreement is shown rather than averaged away.

**How to check any feature name yourself:**

```
F:\Apps\freedom_system\app_cabinet\OneTrainer\modules\util\config\TrainConfig.py     (289 settings)
F:\Apps\freedom_system\app_cabinet\OneTrainer\modules\util\config\ConceptConfig.py   (51 per-folder)
F:\Apps\freedom_system\app_cabinet\OneTrainer\modules\util\config\SampleConfig.py    (23 preview)
```

Search for the name in quotes. If it isn't there, it doesn't exist. The full
inventory of all 363 is in `logs/_ot_settings_inventory.md`.

A worked example of why this matters is at the end: a guide that looked
authoritative and got twelve names out of twelve wrong.

Installed build: Nerogar/OneTrainer, revision `23df383`.

---

### 1. What OneTrainer can train (verified from its own enums)


| | values |
| --- | --- |
| `training_method` | FINE_TUNE, **LORA**, EMBEDDING, FINE_TUNE_VAE |
| `peft_type` | **LORA**, LOHA, OFT_2, LOKR |
| `model_type` | 29 architectures incl. SDXL, SD 1.5/2.x, SD3, Flux, Flux 2, Chroma, Qwen-Image, Krea 2, HiDream, PixArt, Sana, Hunyuan Video, Wuerstchen |
| `optimizer` | 43, incl. ADAMW, ADAMW_8BIT, PRODIGY, PRODIGY_ADV, LION, CAME, ADAFACTOR, MUON, SCHEDULE_FREE_ADAMW |
| `learning_rate_scheduler` | CONSTANT, LINEAR, COSINE, COSINE_WITH_RESTARTS, COSINE_WITH_HARD_RESTARTS, REX, ADAFACTOR, CUSTOM |
| `loss_weight_fn` | CONSTANT, P2, **MIN_SNR_GAMMA**, DEBIASED_ESTIMATION, SIGMA |
| `timestep_distribution` | UNIFORM, SIGMOID, LOGIT_NORMAL, HEAVY_TAIL, COS_MAP, INVERTED_PARABOLA, BETA |
| `ema` | OFF, GPU, CPU |
| `attention_mechanism` | SDP, FLASH, CUDNN, FLEX |

Note for the record: a widely circulated feature list claims **BOFT**. This
build has no BOFT — the four PEFT types above are the whole set.

---

### 2. The decisions that matter for one person


Each row: the real setting name, what the internet recommends, and what your
last run actually used.

#### 2.1 Dataset


| setting | recommendation | source | Susana's last run |
| --- | --- | --- | --- |
| — | 15–30 images is the usual sweet spot for one subject | [aiofm guide](https://aiofm.info/en/guides/lora-complete-guide) | 23 head / 255 body |
| — | 30 minimum, 50+ preferred, from someone who released ten photoreal LoRAs | [Civitai](https://civitai.com/articles/3701/sdxl-photorealistic-lora-tips-reflections-on-training-and-releasing-10-different-models) | |
| — | vary angle, lighting, distance; repetition is what bakes in background | multiple | |
| `resolution` | 1024 for SDXL, 1024 on the short side | [Civitai](https://civitai.com/articles/3701/sdxl-photorealistic-lora-tips-reflections-on-training-and-releasing-10-different-models) | 1024 (her crops median 498px — under it) |

**Sources conflict on count.** Nobody recommends hundreds. One OneTrainer-specific
warning worth noting: body problems are usually *dataset imbalance* — too many
portrait crops relative to full-body shots, or the reverse
([source](https://neurocanvas.net/blog/ai-toolkit-vs-onetrainer-zimage-guide/)).

#### 2.2 Adapter size


| setting | recommendation | source | last run |
| --- | --- | --- | --- |
| `lora_rank` | 32, alpha 16 | [neura.market](https://www.neura.market/directories/stable-diffusion/guides/sdxl-lora-training-best-settings-and-practical-workflow) | 32 |
| `lora_alpha` | keep alpha = rank for predictable maths | [neurocanvas](https://neurocanvas.net/blog/ai-toolkit-vs-onetrainer-zimage-guide/) | 32 |
| `lora_rank` | 64 / 128 / 256 with alpha 1 for facial likeness | [Civitai](https://civitai.com/articles/3701/sdxl-photorealistic-lora-tips-reflections-on-training-and-releasing-10-different-models) | |
| `lora_decompose` | = DoRA. Available, off by default | — | off |
| `peft_type` | LOHA / LOKR / OFT_2 available as alternatives | — | LORA |

**Unresolved.** 32/16, 32/32 and 256/1 all have advocates. Your own earlier
research found rank 32 beat rank 64 in a direct test, which argues capacity is
not your bottleneck.

#### 2.3 Learning rate and optimizer


| setting | recommendation | source | last run |
| --- | --- | --- | --- |
| `learning_rate` | 5e-5 for identity | [aiofm](https://aiofm.info/en/guides/lora-complete-guide) | 3e-4 |
| `learning_rate` | 1e-4 paired with Prodigy | [aiofm](https://aiofm.info/en/guides/lora-complete-guide) | |
| `learning_rate` | 2e-6, with AdamW8Bit | [Civitai](https://civitai.com/articles/3701/sdxl-photorealistic-lora-tips-reflections-on-training-and-releasing-10-different-models) | |
| `optimizer` | ADAMW_8BIT most repeated; PRODIGY the other common answer | above | ADAMW |
| `learning_rate_scheduler` | CONSTANT | both above | CONSTANT |
| `epochs` / steps | 1500–3000 steps for a face | [neura.market](https://www.neura.market/directories/stable-diffusion/guides/sdxl-lora-training-best-settings-and-practical-workflow) | 2001 |

**A fiftyfold spread on learning rate.** These are recipes tied to their own
rank and optimizer, not universal numbers. This is the single least settled
area in the sources.

#### 2.4 Text encoder


| setting | recommendation | source | last run |
| --- | --- | --- | --- |
| `text_encoder.train` | **yes, train it** for person likeness | [Medium guide](https://medium.com/@guillaume.bieler/a-comprehensive-guide-to-training-a-stable-diffusion-xl-lora-optimal-settings-dataset-building-844113a6d5b3) | **false** |
| `text_encoder_2.train` | SDXL has two, each independently switchable | verified in schema | **false** |
| `text_encoder.learning_rate` | **lower than the UNet** — it overfits faster. 3e-5 cited with rank 32 | [kohya issue](https://github.com/kohya-ss/sd-scripts/issues/1748), [Medium](https://medium.com/@guillaume.bieler/a-comprehensive-guide-to-training-a-stable-diffusion-xl-lora-optimal-settings-dataset-building-844113a6d5b3) | unset |
| `text_encoder.stop_training_after` | stop it early while the UNet continues; ships at 30 epochs | verified in schema | unused |

**This is the largest untouched lever.** Her LoRA contains 794 modules and
**zero** text-encoder modules, so the trigger word never learned to mean her.
Off because OneTrainer's shipped SDXL preset has it off, not by decision.

#### 2.5 Masking


| setting | recommendation | source | last run |
| --- | --- | --- | --- |
| `masked_training` | on, to stop background and clothing being learned | [OT wiki](https://github.com/Nerogar/OneTrainer/wiki/Training) | false |
| `unmasked_weight` | **0.6–0.7** when used *alone*; 0.1 was discarded for producing "anatomically disproportional body" in a nine-run sweep | [nine-run sweep](https://dev.to/furkangozukara/onetrainer-fine-tuning-vs-kohya-ss-dreambooth-huge-research-of-onetrainers-masked-training-4po7) | 0.1 (unused) |
| `masked_prior_preservation_weight` | **1**, and then `unmasked_weight` **0** — OneTrainer's own tested pairing | [OT wiki, Prior Prediction](https://github-wiki-see.page/m/Nerogar/OneTrainer/wiki/Prior-Prediction) | 0.0 |
| `unmasked_probability` | chance a step ignores the mask entirely; ships 0.1 | verified in schema | 0.1 |
| `normalize_masked_area_loss` | available | verified in schema | false |

**The two recommendations are not in conflict — they are two configurations.**
Masking alone leaves everything outside the mask unpenalised, so the model can
invent limbs; 0.6 buys that back. Prior preservation plugs the hole directly by
pinning the outside region to the untrained model, so 0 becomes safe. Confirmed
by reading `modules/util/loss/masked_loss.py`.

**Dissent worth knowing**: in OneTrainer's own discussion, the advice is that if
you only want to train part of an image you should **crop, not mask** — masks
are really an inpainting feature, and a maintainer calls masked training "not a
free lunch" ([#347](https://github.com/Nerogar/OneTrainer/discussions/347),
[#700](https://github.com/Nerogar/OneTrainer/discussions/700)).

**Masks are made by OneTrainer, not by hand**: `scripts/generate_masks.py`,
models CLIPSEG / REMBG / REMBG_HUMAN / COLOR, with `--threshold`,
`--smooth-pixels` and `--expand-pixels`. Files must be named
`<image>-masklabel.png`.

#### 2.6 Regularisation


| setting | recommendation | source |
| --- | --- | --- |
| concept `type: PRIOR_PREDICTION` | the model's own pre-training prediction becomes the target — no class photos to curate | verified in `modules/ui/BaseConceptWindowView.py` |
| classic class images | "really helpful", use FFHQ | [Civitai](https://civitai.com/articles/3701/sdxl-photorealistic-lora-tips-reflections-on-training-and-releasing-10-different-models) |
| classic class images | a LoRA **learns from** them, so they are training data; bad ones poison the run | [kohya discussion](https://github.com/bmaltais/kohya_ss/discussions/2056) |
| classic class images | captioned inputs with *no* regularisation scored as well as the best regularised run | [SDXL experiment](https://blog.aboutme.be/2023/08/10/findings-impact-regularization-captions-sdxl-subject-lora/) |
| classic class images | an outside photo collection can **destroy the class prior** | [arXiv](https://arxiv.org/pdf/2510.20887) |
| ratio, if used | ~1 per 2–3 training images | [kohya discussion](https://github.com/bmaltais/kohya_ss/discussions/2056) |

**Genuinely contested.** It is not "don't use regularisation" — it is that for a
LoRA specifically the evidence is mixed, and OneTrainer offers a mechanism that
needs no extra photos at all.

#### 2.7 Loss, noise, and averaging


| setting | recommendation | source | last run |
| --- | --- | --- | --- |
| `loss_weight_fn` | MIN_SNR_GAMMA for SD1.5/SDXL | [OT wiki](https://github.com/Nerogar/OneTrainer/wiki/Training) | CONSTANT |
| `loss_weight_strength` | that's the gamma — 5 | [OT wiki](https://github.com/Nerogar/OneTrainer/wiki/Training) | 5.0 (unused) |
| `rescale_noise_scheduler_to_zero_terminal_snr` | **do not combine with min-SNR** | [OT wiki](https://github.com/Nerogar/OneTrainer/wiki/Training) | false — clear |
| `ema` | OFF default; 0.999 decay for small sets, `ema_update_step_interval` 5 | [OT wiki](https://github.com/Nerogar/OneTrainer/wiki/Training) | OFF |
| `offset_noise_weight`, `perturbation_noise_weight`, `timestep_distribution`, `min/max_noising_strength` | available; no person-LoRA consensus found | — | defaults |

#### 2.8 Augmentation (per folder, in `concepts.json`)


| setting | recommendation | source | last run |
| --- | --- | --- | --- |
| `enable_random_flip` | **off** for a person — faces are not symmetric | [uploaded guide, and ships false](https://github.com/Nerogar/OneTrainer) | **true** (our code turns it on) |
| `enable_random_rotate` / `brightness` / `contrast` / `saturation` / `hue` | each has an enable, a fixed variant and a max-strength | verified in schema | all off |
| `enable_crop_jitter` | ships **true** | verified in schema | true |
| `enable_random_circular_mask_shrink`, `enable_random_mask_rotate_crop` | mask-aware augmentation | verified in schema | off |

#### 2.9 Captions


| setting | recommendation | source |
| --- | --- | --- |
| concept `text.prompt_source` | captions matter more than any numeric setting; the worst results in a controlled test came from *no* captions | [SDXL experiment](https://blog.aboutme.be/2023/08/10/findings-impact-regularization-captions-sdxl-subject-lora/) |
| `caps_randomize_*` | available | verified in schema |

Already fixed here: captions were one identical string for every photo and are
now measured per photo.

#### 2.10 Layer targeting


| setting | note |
| --- | --- |
| `layer_filter` | comma-separated list of layer names to train. **Empty in every run so far**, so every eligible layer got a LoRA — 794 modules, 198 MB |
| `layer_filter_preset` | SDXL presets: `attn-mlp` → attentions, `attn-only` → attn, `full` → everything. **GUI-only** — it is referenced solely in `modules/ui/*Controller.py` and does nothing headless |
| `layer_filter_regex` | treat the filter as a regex |

**A trap.** The shipped SDXL preset sets `layer_filter_preset: "attn-mlp"`, which
reads as attention-only. Running headless, nothing expands it into
`layer_filter`, so it has no effect. A GUI user picking the same preset gets a
much smaller LoRA than we do.

#### 2.11 Recording what you did


| setting | note |
| --- | --- |
| `include_train_config` | NONE / SETTINGS / ALL. **Ships NONE**, so our LoRAs carry no training settings and every LoRA-inspector tool shows nothing about them. Setting it writes an `ot_config` key into the file |

---

### 3. Features that exist but aren't about likeness


Listed so "is that available?" has an answer: multi-GPU (`multi_gpu`,
`device_indexes`), cloud training (`cloud`), quantization, gradient
checkpointing per model part, `attention_mechanism`, `train_dtype` /
`fallback_train_dtype`, `aspect_ratio_bucketing`, `latent_caching`, validation
concepts (`validation`, `validate_after`), live preview sampling
(`sample_after`, 23 sample settings), rolling backups (`rolling_backup`,
`backup_after`), `prevent_overwrites`, TensorBoard, `clip_grad_norm`,
`loss_scaler`, `learning_rate_scaler`, embedding training with
`embedding_learning_rate` and `preserve_embedding_norm`.

---

### 4. Why the name-checking rule exists


A guide supplied on 2026-09-12 described masking and regularisation for
OneTrainer. Its *concepts* matched what is above. Its mechanics did not:

- `use_mask`, `mask_dir`, `use_regularization`, `reg_dir`, `reg_weight`,
  `lora_dropout`, `num_epochs`, `lr_scheduler`, `flip_aug`, `color_aug`,
  `image_dir`, `caption_dir` — **all twelve absent from the schema**
- config shown as YAML; OneTrainer's is JSON
- masks named `image01.png`; OneTrainer needs `image01-masklabel.png`
- linked to the wrong GitHub repository

The filename error is the dangerous one: follow it and no mask loads, no error
appears, and training silently proceeds unmasked.

---

### 5. Status of each decision


Split deliberately. Nothing in the second table is agreed, and nothing in it
should be switched on without being asked for.

#### Decided by the user


| | value |
| --- | --- |
| `masked_training` + `masked_prior_preservation_weight` | on, weight **1**, `unmasked_weight` **0** — option B |
| dataset | all 23 head crops, not cut to 8–12 |
| `text_encoder.train` | on — from the list of four to install |
| where the settings live | the Face Tool, not a ComfyUI node |

#### Proposed, NOT agreed


| | value | why it is only a proposal |
| --- | --- | --- |
| `enable_random_flip` | false | sourced, but never asked about |
| `loss_weight_fn` | MIN_SNR_GAMMA, strength 5 | recommended by OneTrainer's docs; never asked about |
| `include_train_config` | SETTINGS | housekeeping, not likeness |
| `text_encoder.learning_rate` | lower than the UNet's | the sources say lower, but give no agreed number |
| classic regularisation | skip | researched and recommended; the user has not ruled |

Masks to be generated with `generate_masks.py`, CLIPSEG, prompt "face".

---

# From `_ot_settings_inventory.md`

### Training settings (289)


Everything in OneTrainer's training config, in the order the schema declares it. Anything not marked is left at its default by our pipeline.

#### name, default value, data type, nullable


- `optimizer` — default `Optimizer.ADAMW` **[we set this]**
- `adam_w_mode` — default `False`
- `alpha` — default `None`
- `amsgrad` — default `False`
- `beta1` — default `None`
- `beta2` — default `None`
- `beta3` — default `None`
- `bias_correction` — default `False`
- `block_wise` — default `False`
- `capturable` — default `False`
- `centered` — default `False`
- `clip_threshold` — default `None`
- `d0` — default `None`
- `d_coef` — default `None`
- `dampening` — default `None`
- `decay_rate` — default `None`
- `decouple` — default `False`
- `differentiable` — default `False`
- `eps` — default `None`
- `eps2` — default `None`
- `foreach` — default `False`
- `fsdp_in_use` — default `False`
- `fused` — default `False`
- `fused_back_pass` — default `False`
- `growth_rate` — default `None`
- `initial_accumulator_value` — default `None`
- `initial_accumulator` — default `None`
- `is_paged` — default `False`
- `log_every` — default `None`
- `lr_decay` — default `None`
- `max_unorm` — default `None`
- `maximize` — default `False`
- `min_8bit_size` — default `None`
- `quant_block_size` — default `None`
- `momentum` — default `None`
- `nesterov` — default `False`
- `no_prox` — default `False`
- `optim_bits` — default `None`
- `percentile_clipping` — default `None`
- `r` — default `None`
- `relative_step` — default `False`
- `safeguard_warmup` — default `False`
- `scale_parameter` — default `False`
- `stochastic_rounding` — default `True`
- `use_bias_correction` — default `False`
- `use_triton` — default `False`
- `warmup_init` — default `False`
- `weight_decay` — default `None`
- `weight_lr_power` — default `None`
- `decoupled_decay` — default `False`
- `fixed_decay` — default `False`
- `rectify` — default `False`
- `degenerated_to_sgd` — default `False`
- `k` — default `None`
- `xi` — default `None`
- `n_sma_threshold` — default `None`
- `ams_bound` — default `False`
- `adanorm` — default `False`
- `adam_debias` — default `False`
- `slice_p` — default `None`
- `cautious` — default `False`
- `weight_decay_by_lr` — default `True`
- `prodigy_steps` — default `None`
- `use_speed` — default `False`
- `split_groups` — default `True`
- `split_groups_mean` — default `True`
- `factored` — default `True`
- `factored_fp32` — default `True`
- `use_stableadamw` — default `True`
- `use_cautious` — default `False`
- `use_grams` — default `False`
- `use_adopt` — default `False`
- `d_limiter` — default `True`
- `use_schedulefree` — default `True`
- `use_orthograd` — default `False`
- `nnmf_factor` — default `False`
- `orthogonal_gradient` — default `False`
- `use_atan2` — default `False`
- `use_AdEMAMix` — default `False`
- `beta3_ema` — default `None`
- `alpha_grad` — default `None`
- `beta1_warmup` — default `None`
- `min_beta1` — default `None`
- `Simplified_AdEMAMix` — default `False`
- `kourkoutas_beta` — default `False`
- `schedulefree_c` — default `None`
- `ns_steps` — default `None`
- `MuonWithAuxAdam` — default `False`
- `muon_hidden_layers` — default `None`
- `muon_adam_regex` — default `False`
- `muon_adam_lr` — default `None`
- `muon_te1_adam_lr` — default `None`
- `muon_te2_adam_lr` — default `None`
- `muon_adam_config` — default `{}`
- `rms_rescaling` — default `True`
- `normuon_variant` — default `False`
- `beta2_normuon` — default `None`
- `low_rank_ortho` — default `False`
- `ortho_rank` — default `None`
- `accelerated_ns` — default `False`
- `cautious_wd` — default `False`
- `approx_mars` — default `False`
- `auto_kappa_p` — default `False`
- `compile` — default `False`
- `model_name` — default `""`
- `include` — default `True`
- `train` — default `True`
- `stop_training_after` — default `None`
- `stop_training_after_unit` — default `TimeUnit.NEVER`
- `learning_rate` — default `None` **[we set this]**
- `weight_dtype` — default `DataType.FLOAT_32`
- `dropout_probability` — default `0.0`
- `train_embedding` — default `True`
- `attention_mask` — default `False`
- `guidance_scale` — default `1.0`
- `gradient_checkpointing` — default `True`
- `offload_fraction` — default `0.0`
- `activation_offloading` — default `False`
- `uuid` — default `str(uuid.uuid4())`
- `model_name` — default `""`
- `placeholder` — default `"<embedding>"`
- `train` — default `True`
- `stop_training_after` — default `None`
- `stop_training_after_unit` — default `TimeUnit.NEVER`
- `token_count` — default `1`
- `initial_embedding_text` — default `"*"`
- `is_output_embedding` — default `False`
- `layer_filter` — default `""`
- `layer_filter_preset` — default `"full"`
- `layer_filter_regex` — default `False`
- `svd_dtype` — default `DataType.NONE`
- `svd_rank` — default `16`
- `cache_dir` — default `None` **[we set this]**

#### general settings


- `training_method` — default `TrainingMethod.FINE_TUNE` **[we set this]**
- `model_type` — default `ModelType.STABLE_DIFFUSION_15` **[we set this]**
- `debug_mode` — default `False` **[we set this]**
- `debug_dir` — default `"debug"`
- `workspace_dir` — default `"workspace/run"` **[we set this]**
- `cache_dir` — default `"workspace-cache/run"` **[we set this]**
- `huggingface_cache_dir` — default `""`
- `offline_mode` — default `False`
- `tensorboard` — default `True` **[we set this]**
- `tensorboard_expose` — default `False`
- `tensorboard_always_on` — default `False`
- `tensorboard_port` — default `6006`
- `validation` — default `False`
- `validate_after` — default `1`
- `validate_after_unit` — default `TimeUnit.EPOCH`
- `continue_last_backup` — default `False` **[we set this]**
- `prevent_overwrites` — default `False`
- `include_train_config` — default `ConfigPart.NONE`

#### multi-GPU


- `multi_gpu` — default `False`
- `device_indexes` — default `""`
- `gradient_reduce_precision` — default `GradientReducePrecision.FLOAT_32_STOC...`
- `fused_gradient_reduce` — default `True`
- `async_gradient_reduce` — default `True`
- `async_gradient_reduce_buffer` — default `100`

#### model settings


- `base_model_name` — default `"stable-diffusion-v1-5/stable-diffusi...` **[we set this]**
- `output_dtype` — default `DataType.FLOAT_32` **[we set this]**
- `output_model_format` — default `ModelFormat.SAFETENSORS` **[we set this]**
- `output_model_destination` — default `"models/model.safetensors"` **[we set this]**
- `async_offloading` — default `True`
- `force_circular_padding` — default `False`
- `compile` — default `False`

#### data settings


- `concept_file_name` — default `"training_concepts/concepts.json"` **[we set this]**
- `aspect_ratio_bucketing` — default `True`
- `latent_caching` — default `True`
- `clear_cache_before_training` — default `True` **[we set this]**

#### training settings


- `learning_rate_scheduler` — default `LearningRateScheduler.CONSTANT` **[we set this]**
- `custom_learning_rate_scheduler` — default `None`
- `learning_rate` — default `3e-6` **[we set this]**
- `learning_rate_warmup_steps` — default `200.0` **[we set this]**
- `learning_rate_cycles` — default `1.0`
- `learning_rate_min_factor` — default `0.0`
- `epochs` — default `100` **[we set this]**
- `batch_size` — default `1` **[we set this]**
- `gradient_accumulation_steps` — default `1` **[we set this]**
- `ema` — default `EMAMode.OFF`
- `ema_decay` — default `0.999`
- `ema_update_step_interval` — default `5`
- `dataloader_threads` — default `2`
- `train_device` — default `default_device.type`
- `temp_device` — default `"cpu"`
- `train_dtype` — default `DataType.FLOAT_16` **[we set this]**
- `fallback_train_dtype` — default `DataType.BFLOAT_16`
- `enable_autocast_cache` — default `True`
- `only_cache` — default `False`
- `resolution` — default `"512"` **[we set this]**
- `frames` — default `"25"`
- `attention_mechanism` — default `AttentionMechanism.SDP`
- `mse_strength` — default `1.0`
- `mae_strength` — default `0.0`
- `log_cosh_strength` — default `0.0`
- `huber_strength` — default `0.0`
- `huber_delta` — default `1.0`
- `vb_loss_strength` — default `1.0`
- `loss_weight_fn` — default `LossWeight.CONSTANT`
- `loss_weight_strength` — default `5.0`
- `dropout_probability` — default `0.0`
- `loss_scaler` — default `LossScaler.NONE`
- `learning_rate_scaler` — default `LearningRateScaler.NONE`
- `clip_grad_norm` — default `1.0`

#### noise


- `offset_noise_weight` — default `0.0`
- `generalized_offset_noise` — default `False`
- `perturbation_noise_weight` — default `0.0`
- `rescale_noise_scheduler_to_zero_terminal_snr` — default `False`
- `force_v_prediction` — default `False`
- `force_epsilon_prediction` — default `False`
- `min_noising_strength` — default `0.0`
- `max_noising_strength` — default `1.0`
- `timestep_distribution` — default `TimestepDistribution.UNIFORM`
- `noising_weight` — default `0.0`
- `noising_bias` — default `0.0`
- `timestep_shift` — default `1.0`
- `dynamic_timestep_shifting` — default `False`

#### transformer


- `transformer` — default `transformer`
- `unconditional_transformer` — default `unconditional_transformer`

#### quantization layer filter


- `quantization` — default `quantization`

#### text encoder


- `text_encoder` — default `text_encoder`
- `text_encoder_layer_skip` — default `0`
- `text_encoder_sequence_length` — default `512`

#### text encoder 2


- `text_encoder_2` — default `text_encoder_2`
- `text_encoder_2_layer_skip` — default `0`
- `text_encoder_2_sequence_length` — default `77`

#### text encoder 3


- `text_encoder_3` — default `text_encoder_3`
- `text_encoder_3_layer_skip` — default `0`

#### text encoder 4


- `text_encoder_4` — default `text_encoder_4`
- `text_encoder_4_layer_skip` — default `0`

#### effnet encoder


- `effnet_encoder` — default `effnet_encoder`

#### decoder


- `decoder` — default `decoder`

#### decoder text encoder


- `decoder_text_encoder` — default `decoder_text_encoder`

#### decoder vqgan


- `decoder_vqgan` — default `decoder_vqgan`

#### masked training


- `masked_training` — default `False`
- `unmasked_probability` — default `0.1`
- `unmasked_weight` — default `0.1`
- `normalize_masked_area_loss` — default `False`
- `masked_prior_preservation_weight` — default `0.0`
- `custom_conditioning_image` — default `False`

#### layer filter


- `layer_filter` — default `""`
- `layer_filter_preset` — default `"full"`
- `layer_filter_regex` — default `False`

#### embedding


- `embedding_learning_rate` — default `None`
- `preserve_embedding_norm` — default `False`
- `embedding` — default `TrainEmbeddingConfig.default_values()`
- `embedding_weight_dtype` — default `DataType.FLOAT_32`

#### cloud


- `cloud` — default `CloudConfig.default_values()`

#### lora


- `peft_type` — default `PeftType.LORA`
- `lora_model_name` — default `""`
- `lora_rank` — default `16` **[we set this]**
- `lora_alpha` — default `1.0` **[we set this]**
- `lora_decompose` — default `False`
- `lora_decompose_norm_epsilon` — default `True`
- `lora_decompose_output_axis` — default `False`
- `lora_weight_dtype` — default `DataType.FLOAT_32`
- `bundle_additional_embeddings` — default `True`

#### oft


- `oft_block_size` — default `32`
- `oft_block_share` — default `False`
- `oft_scaled` — default `False`

#### lokr


- `lokr_dim` — default `16`
- `lokr_decompose_both` — default `False`
- `lokr_decompose_factor` — default `-1`
- `lokr_use_tucker` — default `False`
- `lokr_weight_decompose` — default `False`
- `lokr_dora_on_output` — default `True`
- `lokr_full_matrix` — default `False`
- `lokr_vec_trick` — default `True`

#### optimizer


- `optimizer` — default `TrainOptimizerConfig.default_values()` **[we set this]**

#### sample settings


- `sample_definition_file_name` — default `"training_samples/samples.json"` **[we set this]**
- `sample_after` — default `10`
- `sample_after_unit` — default `TimeUnit.MINUTE` **[we set this]**
- `sample_skip_first` — default `0`
- `sample_image_format` — default `ImageFormat.JPG`
- `sample_video_format` — default `VideoFormat.MP4`
- `sample_audio_format` — default `AudioFormat.MP3`
- `samples_to_tensorboard` — default `True` **[we set this]**
- `non_ema_sampling` — default `True`

#### backup settings


- `backup_after` — default `30`
- `backup_after_unit` — default `TimeUnit.MINUTE`
- `rolling_backup` — default `False`
- `rolling_backup_count` — default `3`
- `backup_before_save` — default `True`
- `save_every` — default `0`
- `save_every_unit` — default `TimeUnit.NEVER`
- `save_skip_first` — default `0`
- `save_filename_prefix` — default `""`

#### secrets


- `secrets` — default `secrets`

### Per-concept settings (51)


Set per dataset folder, in `concepts.json`. This is where augmentation, captioning and per-folder behaviour live.

#### concept


- `enable_crop_jitter` — default `True`
- `enable_random_flip` — default `False`
- `enable_fixed_flip` — default `False`
- `enable_random_rotate` — default `False`
- `enable_fixed_rotate` — default `False`
- `random_rotate_max_angle` — default `0.0`
- `enable_random_brightness` — default `False`
- `enable_fixed_brightness` — default `False`
- `random_brightness_max_strength` — default `0.0`
- `enable_random_contrast` — default `False`
- `enable_fixed_contrast` — default `False`
- `random_contrast_max_strength` — default `0.0`
- `enable_random_saturation` — default `False`
- `enable_fixed_saturation` — default `False`
- `random_saturation_max_strength` — default `0.0`
- `enable_random_hue` — default `False`
- `enable_fixed_hue` — default `False`
- `random_hue_max_strength` — default `0.0`
- `enable_resolution_override` — default `False`
- `resolution_override` — default `"512"`
- `enable_random_circular_mask_shrink` — default `False`
- `enable_random_mask_rotate_crop` — default `False`
- `prompt_source` — default `"sample"`
- `prompt_path` — default `""`
- `enable_tag_shuffling` — default `False`
- `tag_delimiter` — default `","`
- `keep_tags_count` — default `1`
- `tag_dropout_enable` — default `False`
- `tag_dropout_mode` — default `"FULL"`
- `tag_dropout_probability` — default `0.0`
- `tag_dropout_special_tags_mode` — default `"NONE"`
- `tag_dropout_special_tags` — default `""`
- `tag_dropout_special_tags_regex` — default `False`
- `caps_randomize_enable` — default `False`
- `caps_randomize_mode` — default `"capslock`
- `caps_randomize_probability` — default `0.0`
- `caps_randomize_lowercase` — default `False`
- `image` — default `ConceptImageConfig.default_values()`
- `text` — default `ConceptTextConfig.default_values()`
- `name` — default `""`
- `path` — default `""`
- `seed` — default `random.randint(-(1 << 30), 1 << 30)`
- `enabled` — default `True`
- `type` — default `ConceptType.STANDARD`
- `include_subdirectories` — default `False`
- `image_variations` — default `1`
- `text_variations` — default `1`
- `balancing` — default `1.0`
- `balancing_strategy` — default `BalancingStrategy.REPEATS`
- `loss_weight` — default `1.0`
- `concept_stats` — default `{}`

### Sampling settings (23)


Preview images generated during a run. Our pipeline disables sampling and renders thumbnails through ComfyUI afterwards instead.

#### sample


- `enabled` — default `True`
- `prompt` — default `""`
- `negative_prompt` — default `defaults["negative_prompt"]`
- `height` — default `defaults["height"]`
- `width` — default `defaults["width"]`
- `frames` — default `1`
- `length` — default `10.0`
- `seed` — default `42`
- `random_seed` — default `False`
- `diffusion_steps` — default `defaults["diffusion_steps"]`
- `cfg_scale` — default `defaults["cfg_scale"]`
- `noise_scheduler` — default `defaults["noise_scheduler"]`
- `text_encoder_1_layer_skip` — default `0`
- `text_encoder_1_sequence_length` — default `None`
- `text_encoder_2_layer_skip` — default `0`
- `text_encoder_2_sequence_length` — default `None`
- `text_encoder_3_layer_skip` — default `0`
- `text_encoder_4_layer_skip` — default `0`
- `transformer_attention_mask` — default `False`
- `force_last_timestep` — default `False`
- `sample_inpainting` — default `False`
- `base_image_path` — default `""`
- `mask_image_path` — default `""`

---

# From `lora_training.md`

## lora training


What is actually inside Susana's LoRA, and what can be done to it without
training again. Written 2026-09-12, after the retrain.

---

### 1. What the file contains


`REPO_comfyUI/models/loras/faces/susana_head_sdxl.safetensors`, read straight
out of the safetensors header rather than from any tool's summary.

```
2382 tensors  =  794 modules (alpha + lora_down + lora_up each)
rank 32 on every single module
198 MB
```

Where those 794 modules sit:

| part of the model | modules |
| --- | --- |
| UNet input blocks | 271 |
| UNet middle block | 108 |
| UNet output blocks | 410 |
| UNet other | 5 |
| **text encoder 1** | **0** |
| **text encoder 2** | **0** |

#### 1.1 It does not touch the text encoders


This is the finding worth keeping. The text encoder is the half of the model
that turns words into something the image half can use — it is what would
learn that `ohwxsusana` means this particular person. Her LoRA does not touch
it at all. Her identity lives entirely in the UNet, and the trigger word is
doing less work than the workflow's wiring implies.

That is not automatically wrong. UNet-only face LoRAs are common, and training
the text encoder is a well-known way to overfit a small set. But it is a real
lead on likeness, and it is a training setting — no viewer or loader can
change it after the fact.

**Where it comes from** (checked 2026-09-12). `face_training/otrain.py` sets

```python
"text_encoder":   {"train": False, "weight_dtype": "FLOAT_16"},
"text_encoder_2": {"train": False, "weight_dtype": "FLOAT_16"},
```

in its per-run block, added in the first face-training commit (`dc7e0dd`,
2026-09-03) with no comment. But OneTrainer's **own** shipped preset,
`training_presets/SDXL/#sdxl 1.0 LoRA.json`, says exactly the same thing. So
this is upstream's stock setting for an SDXL LoRA, restated in our config —
not a choice made here, and not a mistake introduced here. It has simply never
been questioned.

#### 1.2 Its metadata is nearly empty


14 keys, and they are the format spec plus OneTrainer's own git revision:

```
modelspec.architecture   stable-diffusion-xl-v1-base/lora
modelspec.resolution     1024x1024
modelspec.title          Stable Diffusion XL 1.0 Base LoRA
ot_branch / ot_revision  master / 23df383
ss_base_model_version    sdxl_
```

No learning rate, no step count, no optimiser, no dataset size, no captions.
Kohya-trained LoRAs carry all of that in `ss_*` keys, which is what every
"LoRA inspector" on the internet is built to read. **On this file those tools
would show almost nothing.** Worth knowing before installing one.

`modelspec.author` says StabilityAI and `modelspec.title` says "Stable
Diffusion XL 1.0 Base LoRA" — those are inherited boilerplate, not a
description of this LoRA.

---

### 2. Tools, by what they actually do


Three different jobs get called "a LoRA tool". They are not substitutes.

#### 2.1 See what is inside


- [rockerBOO/lora-inspector](https://github.com/rockerBOO/lora-inspector) —
  metadata **and** quantitative analysis of the weights themselves. The weight
  half is the only part that says anything about our files.
- [LoraScope](https://civitai.com/articles/20111/lorascope-your-metadata-explorer-for-lora-testing)
  and [xypher7's browser viewer](https://xypher7.github.io/lora-metadata-viewer/)
  — metadata only. See 1.2: near-useless on an OneTrainer file.
- [safetensors_util](https://github.com/by321/safetensors_util) — raw header
  dump. This is essentially what section 1 above was produced with.

#### 2.2 Adjust how it applies, without retraining


[LoRA Block Weight, in the ComfyUI Inspire Pack](https://github.com/ltdrdata/ComfyUI-extension-tutorials/blob/Main/ComfyUI-Inspire-Pack/tutorial/LoraBlockWeight.md)
(`LoraLoaderBlockWeight //Inspire`).

Instead of one strength for the whole LoRA, a per-block vector: some layers
fire at full strength, others get turned down or switched off. The layers do
different jobs — early/input blocks lean towards composition and pose, middle
blocks carry most of the subject, later/output blocks carry style and fine
detail. The block weights multiply against the usual `strength_model` /
`strength_clip`.

For our problem that is the dial we do not currently have: turn her face up
and the styling baked in from her source photos down, in seconds, instead of
another four-and-a-half-hour run. There is also an XY-plot variant for
sweeping the vector.

**Not installed here.** The only LoRA-related custom node in this ComfyUI is
our own `freedom_lora_stack`.

#### 2.3 Change the file itself


[kohya-ss `networks/resize_lora.py`](https://github.com/kohya-ss/sd-scripts/blob/main/networks/resize_lora.py)
rebuilds a LoRA at a lower rank by singular-value decomposition, writing a new
file. Dynamic methods:

- `sv_ratio` — keep dimensions that are strong relative to the strongest
  dimension in that same layer.
- `sv_fro` — judge each dimension against the base model's total effect in
  that layer, so big layers are penalised more than small ones.
- `sv_cumulative` — keep dimensions up to a cumulative share of the total.

At rank 32 on 794 modules, 198 MB, there is real room here. See also
[elias-gaeros/resize_lora](https://github.com/elias-gaeros/resize_lora).

#### 2.4 Organise and preview


[ComfyUI-Lora-Manager](https://github.com/willmiao/ComfyUI-Lora-Manager) —
previews, trigger-word toggles, sidecar `.metadata.json` files, Civitai
lookups. Housekeeping, not adjustment. Our Face Shelf already covers the part
of this we care about (thumbnail per trained face, trigger handled for you).

---

### 3. Where this leaves the likeness problem


Three levers, cheapest first:

1. **Block weights** — no retraining, minutes. Untried. Needs the Inspire Pack.
2. **Text encoder training** — would need a new run, and is the one setting
   that plausibly explains why the trigger word feels inert.
3. **The source photography** — unchanged and still the ceiling: head crops
   median 498 px short side against a 1024 training resolution, 1 of 23
   meeting it.

Nothing in section 2 touches lever 3.

---

### 4. What the trainer actually is


Asked and checked 2026-09-12, because it is easy to lose track of.

**The trainer is [OneTrainer](https://github.com/Nerogar/OneTrainer), by
Nerogar.** Third-party, open source, not written here. It lives at
`app_cabinet/OneTrainer` at revision `23df383` — the same revision stamped
into Susana's LoRA as `ot_revision`, so the file and the checkout agree.

**It is not part of ComfyUI.** Separate folder, its own virtual environment,
its own Python. There is no trainer node in `REPO_comfyUI/custom_nodes`. The
only link is one-way and after the fact: when a LoRA finishes, our pipeline
copies it into `REPO_comfyUI/models/loras/faces/`, renders one thumbnail
through the running ComfyUI, and writes the registry the Face Shelf reads.

**What is ours** is `face_training/` in this repo — the part that decides
*what* gets trained and turns a pile of photos into a trained face:

| file | what it does |
| --- | --- |
| `seek.py`, `facebank.py`, `identity.py` | find her in an archive, judge, crop |
| `sort_photos.py` | crops and measured captions |
| `jobs.py` | the job table: which family x crop pairs to train |
| `otrain.py` | builds one OneTrainer config, runs it headless |
| `pipeline.py` | the whole run: sort, train each job, copy, thumbnail, register |
| `thumbs.py` | renders each finished LoRA through ComfyUI |
| `face_tool_ui.py` | the Face Tool window |
| `profiles.py`, `backup.py`, `scan_cache.py` | per-person state on disk |

`otrain.py` layers three things to build a config: OneTrainer's own defaults,
then OneTrainer's shipped preset for that family, then our per-run values
(dataset folder, output path, trigger, step count). We do not reimplement any
training.

**Why OneTrainer.** `logs/research_lora_training_tools_2026-09-03.md` compared
kohya_ss, OneTrainer, ai-toolkit, SimpleTuner, ComfyUI-FluxTrainer,
comfyUI-Realtime-Lora and ComfyUI's built-in node. A ComfyUI-native route
existed and was deliberately not taken: the built-in node was "undocumented
and featureless — fine for an experiment, not for a repeatable
two-LoRA-per-person pipeline". OneTrainer was chosen for the standalone path.
It was installed the same day (`dc7e0dd`).

---

### 5. Not done


- Inspire Pack is not installed; block weights have never been tried on her.
- Text-encoder training has never been tried — see 1.1. It is off because
  upstream's preset has it off, not because it was tested and rejected.
- No resize attempted; 198 MB x 4 files stands.

---

# From `research_lora_training_tools_2026-09-03.md`

## Deep dive — LoRA training tools for ComfyUI (2026-09-03)


Research request: list every LoRA training tool a ComfyUI user can use that is
**available and still actively maintained** as of September 2026. Exclude
abandoned tools. Cover both tools that run inside ComfyUI and standalone
trainers that ComfyUI users pair with ComfyUI. Cover SDXL plus the newer model
families (Flux, Wan, Qwen, Z-Image). Written as teaching prose — every term
defined, assume no prior knowledge.

Immediate use: the face-library plan needs a training tool to make two LoRA
files per person (face-only, face+body) for SDXL (bigLust) on a 12 GB laptop
card.

---

### Part 1 — what "training a LoRA" actually is


The picture model in use — bigLust, for example — is called a **checkpoint**.
It is one big frozen file, several gigabytes, holding everything the model
learned about drawing. You cannot easily change what is inside it.

A **LoRA** (Low-Rank Adaptation; the name does not matter) is a small companion
file, usually 10–300 MB. It sits next to the checkpoint and gently bends the
checkpoint's behaviour in one direction — toward a face, a body, an art style,
a piece of clothing. You load it alongside the checkpoint and it does its work.

**Training** is the process of making that small file. You give a program a
folder of example pictures — the **dataset** — and a short text label for each
picture describing what is in it. Those labels are **captions**. The program
shows the model each picture over and over, thousands of times, each time
nudging the numbers in the LoRA a tiny bit so the model's guess about that
picture gets closer to the real picture. Each single nudge is a **step**. One
full pass through every picture is an **epoch**. A typical face LoRA is a few
thousand steps.

Two dials matter most. **Rank** (a.k.a. "network dimension") is how much room
the LoRA has to store what it learns — bigger rank holds more detail but makes
a bigger file and can memorise too hard. **Learning rate** is how big each
nudge is — too big and training thrashes and ruins the result, too small and it
never learns.

Cost of training: **time** (a few minutes to a couple of hours on a laptop
4080 for an SDXL face), **video memory** (SDXL LoRA training needs roughly
8–12 GB, so it wants the whole graphics card to itself, like the big video
model does), and a little **disk**.

---

### Part 2 — the one fact that makes the tool list short


There are only about three real **training engines** in this field. Almost
every "tool" is a friendlier front end — a menu, a set of buttons, or a
ComfyUI node — wrapped around one of those three engines.

- **kohya sd-scripts** — the oldest and most trusted engine, by the developer
  kohya-ss. The standard for SD 1.5 and SDXL; also does Flux. No GUI of its
  own; a set of command-line scripts. Nearly every SDXL trainer runs this
  underneath.
- **Musubi Tuner** — a newer engine by the same kohya-ss developer, built for
  the 2025-and-later models: Wan (video), Qwen-Image, FLUX.2, Z-Image,
  HunyuanVideo. Actively updated (through August 2026).
- **ai-toolkit** — an engine by the developer Ostris. The go-to for Flux, kept
  current with the newest models (FLUX.2, Qwen, Z-Image). Has its own clean web
  interface.

Useful question about any tool: "which engine, and what did they add on top."

---

### Part 3 — tools that run *inside* ComfyUI


#### ComfyUI's built-in "Train LoRA" node

Recent ComfyUI versions ship a training node, no install needed. You build a
small graph: load a checkpoint, load a folder of images, convert them to the
model's internal format, feed them to the Train LoRA node, save the result. It
exposes the real dials — rank, learning rate, steps, batch size, optimizer.
Catch: ComfyUI's team never documented it, and a GitHub question asking which
models it supports was closed without an answer. It is generic enough to work
with whatever model you load it onto (SD 1.5, SDXL, Flux), but it is
bare-bones — no auto-captioning, no sample images during training, no presets.
"There in a pinch," not a finished product.

#### ComfyUI-FluxTrainer (developer: kijai)

Nodes that wrap the kohya sd-scripts engine so you drive it from the ComfyUI
canvas. Despite the name it trains **SDXL and SD3 as well as Flux** —
dedicated SDXL training nodes, handles PonyXL-type SDXL checkpoints. Actively
maintained (160+ commits), widely used. Author labels it "experimental" and
says "do not ask me for training advice," but it works. This is the tool the
earlier face-library plan named; for SDXL on a 12 GB card it is a sound
in-ComfyUI choice.

#### comfyUI-Realtime-Lora (developer: shootthesound)

The most actively developed in-ComfyUI trainer right now. Carries no engine of
its own; you point it at whichever engine you installed (sd-scripts, Musubi
Tuner, or ai-toolkit) and it gives nodes for each. Coverage: **SDXL and
SD 1.5** via sd-scripts; Z-Image, Qwen-Image, Qwen-Image-Edit, FLUX Klein,
Wan 2.2 via the newer engines. Advertises SDXL / SD 1.5 training in a few
minutes on a decent card; adds block-level LoRA editing. Fork
**comfyUI-Realtime-Lora-Plus** (developer: tarkansarim) adds saving an edited
LoRA as a new file. Trade-off: "point it at an engine you installed
separately" means more first-time setup than FluxTrainer.

#### Excluded as abandoned

- **Lora-Training-in-Comfy** (LarryJane491) — the tool most old tutorials point
  at. Last code update January 2024 (~2.5 years ago); author could not even
  test SDXL. Do not build on it.
- **ComfyUI-Lora-Training** (Koschpa fork) — refreshed the bundled kohya
  scripts and added resume-from-checkpoint, but only ~21 commits and reads as a
  personal fix, not a maintained project.

---

### Part 4 — standalone trainers ComfyUI users pair with ComfyUI


Separate programs. Run the training in its own window / command line; when it
produces the LoRA file, drop that file into ComfyUI's `loras` folder and use it
normally.

#### kohya_ss GUI (developer: bmaltais)

A graphical menu wrapped around the kohya sd-scripts engine — same engine,
dropdowns and fields instead of typed commands. Covers SD 1.5, SDXL, SD3,
Flux, plus newer additions (inpainting-model training). Still received updates
through mid-2026. Wrinkle: some users report bmaltais has slowed down and
community forks have appeared, but the official releases page is still moving.
For SDXL it remains the most documented option anywhere — matters when
learning.

#### OneTrainer (developer: Nerogar)

A single desktop application — one window, all settings, no command line
required. Many people moved to it from kohya for the cleaner interface.
Supports SD 1.5–3.5, SDXL, Flux.1, FLUX.2 Dev and Klein, Qwen-Image, Z-Image,
Chroma, PixArt, Sana, Hunyuan Video, and more. Does LoRA, full fine-tuning,
and embeddings; has GUI and headless command-line modes; actively maintained
(1,600+ commits). Community testing described especially good results on
photographic, realistic subjects — relevant to photoreal faces.

#### ai-toolkit (developer: Ostris)

The engine from Part 2, used directly. Modern local web interface at a local
browser address. Described as probably the single most popular LoRA trainer as
of early 2026; the reference tool for the newest models (FLUX.2, Z-Image,
Qwen-Image). Also trains SDXL. If face work ever moves to Flux, this is where
most people are.

#### SimpleTuner (developer: bghira)

A "fine-tuning kit" leaning toward advanced, precise control and toward bigger
cards / rented cloud GPUs. Full SDXL pipeline (including a mode that fits SDXL
training into 12 GB using 8-bit math), plus SD3, Flux, PixArt, HiDream,
Auraflow, others, with ControlNet training across many. Actively maintained
into 2026. More of a power-user tool than kohya_ss or OneTrainer.

#### Musubi Tuner (developer: kohya-ss)

The engine from Part 2, used directly. Reach for it to train on **video models
(Wan 2.1 / 2.2)** or the newest image models (Qwen-Image, FLUX.2, Z-Image).
Command-line. The thing several ComfyUI wrappers call underneath. Changelog
runs through August 2026.

#### diffusion-pipe (developer: tdrussell)

Built for training large text-to-**video** models on consumer cards through
heavy memory tricks. Supports 25+ architectures including SDXL and Flux, but
its reason to exist is HunyuanVideo and Wan video LoRAs. Active into mid-2026.
Relevant only to train motion or a person into the Wan video model rather than
a still-image model.

#### Borderline — FluxGym (developer: cocktailpeanut)

A deliberately stripped-down, beginner-friendly window (Ostris-style front,
kohya engine underneath) aimed at low-VRAM Flux training, with explicit
12/16/20 GB modes. Still works for Flux.1, but falling behind: cannot train any
2026 model, a FLUX.2 request has sat untouched since November 2025, and it
never did SDXL. Usable today, not a safe future bet.

#### Cloud option — Civitai on-site trainer

Not local: upload a dataset to the Civitai website, it trains on their machines
for a token cost ("Buzz" — roughly 500 for SD 1.5 / SDXL on the base model,
~1,000 with a custom checkpoint, more for Flux). Convenient, never touches your
card, but your dataset goes to their servers — a real consideration for this
content.

---

### Part 5 — what this means for the face LoRAs


For SDXL faces on a 12 GB laptop card, the field narrows:

- **In ComfyUI:** ComfyUI-FluxTrainer is the steadiest choice and matches the
  existing plan. comfyUI-Realtime-Lora is more actively developed and built for
  exactly this case (SDXL, modest card, fast runs), at the cost of a fiddlier
  first setup.
- **Standalone:** OneTrainer for one clean window and good results on realistic
  faces; kohya_ss GUI for the deepest pile of tutorials while learning.
- The **built-in ComfyUI node** works but is undocumented and featureless —
  fine for an experiment, not for a repeatable two-LoRA-per-person pipeline.
- **ai-toolkit / Musubi Tuner / diffusion-pipe** only become the answer if
  faces move onto Flux or into the Wan video model.

No tool has been installed or chosen yet. This is research only.

---

### Sources


- comfyUI-Realtime-Lora (shootthesound) — https://github.com/shootthesound/comfyUI-Realtime-Lora
- comfyUI-Realtime-Lora-Plus (tarkansarim) — https://github.com/tarkansarim/comfyUI-Realtime-Lora-Plus
- ComfyUI-FluxTrainer (kijai) — https://github.com/kijai/ComfyUI-FluxTrainer
- Lora-Training-in-Comfy (LarryJane491) — https://github.com/LarryJane491/Lora-Training-in-Comfy
- ComfyUI-Lora-Training (Koschpa fork) — https://github.com/Koschpa/ComfyUI-Lora-Training
- ComfyUI built-in TrainLoraNode docs — https://docs.comfy.org/built-in-nodes/TrainLoraNode
- ComfyUI issue #12575 (how should built-in training be used) — https://github.com/Comfy-Org/ComfyUI/issues/12575
- kohya_ss GUI (bmaltais) — https://github.com/bmaltais/kohya_ss/releases
- OneTrainer (Nerogar) — https://github.com/Nerogar/OneTrainer ; https://onetrainer.org/
- Musubi Tuner (kohya-ss) — https://github.com/kohya-ss/musubi-tuner
- SimpleTuner (bghira) — https://github.com/bghira/SimpleTuner
- diffusion-pipe (tdrussell) — https://github.com/tdrussell/diffusion-pipe
- FluxGym (cocktailpeanut) — https://github.com/cocktailpeanut/fluxgym
- OneTrainer vs Kohya SS vs AI Toolkit (2026) — https://sanj.dev/post/onetrainer-vs-kohya-ss-vs-ai-toolkit/
- Civitai on-site LoRA trainer — https://education.civitai.com/using-civitai-the-on-site-lora-trainer/

---

# From `retrain_and_review_gate_2026-09-12.md`

## Susana retrained, and four defects the retrain exposed — 2026-09-12


Started as "retrain Susana from the app, not behind the scenes". The retrain
ran and finished. Getting there took fixing a wall that made retraining
impossible, and pulling that thread turned up three more defects in the same
area. Every one had the same shape as the ones from 2026-09-11: **nothing
crashed, and the screen said something that was not true.**

Branch: `branch09-comfyui-repo-migration`.
Commits: `b43c4b4`, `e04730d`, `907c181`, `b72972c`, `610685d`.

---

### 1. Training could not be re-run at all


Clicking Train on Susana would have produced nothing. The pipeline asks the
registry which LoRAs are already finished and skips those; all four of hers
were registered finished, and their checkpoints were deleted on completion so
there was nothing to resume from either. Every job would have printed
`already done, skipping` and the run would have ended with zero new files —
while the dialog said "Train from the gathered Clean set (23 face, 255 body
photos)?".

Evidence this had bitten before: `_registry.json.bak_before_retrain_20260909_093525`
sitting in the LoRA folder. Last time, the registry was edited **by hand**.
That fixed one night for one person and left the app exactly as broken.

**Fix.** `pipeline --retrain` ignores the finished list and replaces the files
as each new one completes. Resuming an interrupted run is unchanged — that is
what the skip is for, and it is still right by default.

The button now says which of the three things it will do:

| state | button |
| --- | --- |
| something paused mid-training | Resume training |
| everything finished | Retrain |
| nothing trained yet | Train |

Retrain names the files it is about to replace before asking.

---

### 2. The row claimed she had never been trained


`status()` read the profile's own copy of the LoRA list. The profile was
refreshed from the registry only after a training run **in that window**, and
anything that rewrote `profile.json` afterwards wiped it — a Seek run does,
constantly. So Susana's row read `Resume? — 23 face + 255 body photos, not
trained` while four finished LoRAs sat on the shelf.

**Fix.** The row re-reads the registry next to the LoRA files, which is the
same thing the pipeline reads to decide what to skip and the face shelf reads
to list a person. One source of truth, so the row cannot disagree with disk.

---

### 3. The retrain


Driven from the app, launched from the launcher's option 6. The machine was
locked, so the click went in as keyboard messages — a posted mouse click does
nothing to a Tk window, because Tk works out which widget the pointer is over
by asking Windows where the cursor really is, and while the workstation is
locked the cursor cannot be over the app at all. Keys carry their key in the
message, so they land regardless. Focus was walked with Tab and located after
every press by diffing the window capture against a ring-free baseline, rather
than by counting keystrokes and hoping.

```
started  02:28      finished 07:01      4 h 33 min      0 errors, 0 warnings
  susana_head_sdxl             2001 steps   03:06
  susana_head_body_sdxl        5100 steps   04:44
  susana_head_sdxl_pony        2001 steps   05:23
  susana_head_body_sdxl_pony   5100 steps   07:00
```

Verified rather than taken from the summary: all four `.safetensors` carry
today's timestamps, all four thumbnails rendered at 07:01, and the registry
lists all four as finished with today's dates. The log line that mattered was
the first one — `(retraining - 4 finished file(s) will be replaced)` rather
than `already done, skipping`.

Input was the same 23 head + 255 body crops, with the measured captions and
the fixed crops from 2026-09-11. Whether the likeness improved is the user's
call, not measurable here.

---

### 4. `recrop_pending/` — 178 superseded crops, and 19 photos lost


When the crop bug was fixed, the app re-cut the photos and parked the old
crops rather than deleting them. Measured over the 125 crops present in both
folders:

| | median aspect | worst | over the 2.6 cap |
| --- | --- | --- | --- |
| old | 3.25 | 10.24 | 125 of 125 |
| new | 2.60 | 2.60 | 0 |

Accounting for all 177 body crops: 125 replaced under the same name, 33
re-cut under a new one, and **19 with no replacement anywhere**. Those 19 were
traced through every folder in the profile — clean, processed, needs_review,
near_miss, the AI removals — and appear in none. Their originals had been
deleted by the old behaviour before originals were kept, so there was nothing
left to re-cut from. They dropped out silently: Susana trained on 255 body
crops instead of 274.

Cleared at the user's instruction after the loss was stated: 178 images,
178 captions.

---

### 5. The review queue was wrong in four ways


The button read **Review 40**.

- **40 was a ceiling, not a count.** `pending_reviews()` stops at forty and
  the label printed however many came back.
- **The log held 224 rows.**
- **Those 224 rows were 22 photos.** A photo is logged again every time a scan
  reconsiders it.
- **The screen could not show any of them.** It listed a filename and a match
  score, because the original had been deleted by the time it asked.

And underneath all of it: `log_decision` stored `os.path.basename(source)` and
threw the path away. **17 of the 22 filenames exist in more than one archive
folder** — `IMG_0110.JPG` in eight. So the photo could not be found again, and
searching the archives by name would mean showing a picture the judge never
saw and asking "is this her?".

**Fixes.** The path is recorded beside the filename. `abspath()` is
deliberately not used: on a path with one leading backslash — how a UNC path
arrives when a shell has eaten one, which has happened here — it invents a
drive-letter path that does not exist, and a confidently wrong path is worse
than none. Rows collapse to one per photo, newest kept. `pending_review_count()`
is the true uncapped number. The screen shows the photo.

**The archive is now also the M: drive** (`M:` → `\\PERSONALCLOUD\Public`), so
the same photo can be written two completely different ways depending only on
how the folder was typed when a scan ran. A path stored one way is now looked
up the other way too, tested against a real file on the share in both
directions.

Susana's queue now reads 22 photos, and none is displayable — which is
correct, and says so plainly rather than showing an empty box.

**None of those 22 has ever been judged by the current app.** Every borderline
row predates the identity rebuild at 18:02 and the judge refit at 18:05 on
2026-09-11; the last one was written at 17:58. When they were judged, her
identity came from essentially one reference photo. It now comes from 278.

---

### 6. Training walked past the review folder


A photo in `needs_review/` is one the search could not call. A photo in
`needs_review/_approved/` is one already judged to be her that has not been
cut into the set yet. Both are photos that **should** be in the training set
and are not, and training never mentioned them.

Train and Retrain now check first and offer: **Yes** opens the review screen,
**No** carries on and starts training. Counts decide whether the warning
appears; they are not printed.

This also exposed a layout bug — the buttons carry data-dependent widths, and
`Needs review 2 (+1 queued)` beside the five fixed buttons ran off the right
edge with the last one cut in half. The review buttons moved to their own
line, the window opens wider, and rows now follow the canvas instead of being
pinned to 590px, which had made widening the window pointless.

---

### 7. Confirmations taught the judge nothing


"Not her" was written down. **"Yes, it's her" wrote nothing** — it only moved
the file. So the judge learned from every rejection and from none of the
confirmations: half the lesson, and the half that only ever teaches it to be
more cautious. A confirmed photo was also never marked decided, so the older
queue would go on asking about it for ever.

Worse, the "Not her" call passed `sim=0.0, second=0.0`. `train_judge()` fits
to those numbers. A fabricated zero would be fitted to as though measured, and
one outlier at 0.0 among real readings near 0.35 also drags the mean and
spread that every other row is standardised against.

**Fix.** Both answers are recorded and both refit the judge.
`scores_for()` recovers what the search actually measured for that photo — the
numbers already exist, which is why the photo is in the folder at all — and
pairs it with the person's verdict. Where there is genuinely no measurement,
`sim`/`second` are stored as `null` and `train_judge()` skips the row: still
ground truth for "has this been decided", but it teaches the judge nothing.

Nothing had been damaged. The log contained **zero** user rows, so this had
never had a chance to fire.

---

### 8. How the app was driven


The user's instruction was to use the app, not to work behind it. The
workstation was locked throughout, which blocks pointer input entirely:
`WindowFromPoint` at the button's own coordinates returns the lock screen.

What works instead:

- **Seeing** — `PrintWindow` with `PW_RENDERFULLCONTENT` asks the window to
  paint itself, which does not depend on the desktop being visible.
  `CopyFromScreen` photographs the lock screen.
- **Clicking** — keyboard messages posted to the window. Tab to walk focus,
  Space to press. Native dialogs (`#32770`) are real Win32 controls, so their
  Yes/No buttons take `BM_CLICK` directly.
- **Knowing where focus is** — diff each capture against a ring-free baseline
  and take the changed region's bounding box. Counting Tab presses would be a
  guess about widget order and which disabled buttons get skipped.

---

### 9. Outstanding


- **The 21 uncertain photos still on the archive have not been re-judged.** A
  fresh pass would be the first time the current app looks at them, and the
  survivors would land in `needs_review/` as real files. Minutes of work.
  Awaiting the go-ahead.
- Whether the retrained likeness is better — the user's call.
- The resolution ceiling has not moved: head median short side 498 px against
  a 1024 training resolution, 1 of 23 crops meeting it. Source photography,
  not code.
- **Annia remains the real end-to-end test.** The processed folder, the review
  screen, two anchors, auto-created folders and the video path have still
  never run start to finish on one person.
- A leftover `StopTest` profile sits stuck showing `Working — seek: group`.
- 33 ambiguous AI-provenance crops remain in the training set.

---

# From `_my goal.md`

### What that rules in


The parts that look like side quests are the product:

- The STEP 1-12 workflow, its `READ ME FIRST` note, its "type here" and
  "don't touch" labels — this is written for someone who is not an expert.
- The Face Shelf: pick a face, get that face.
- The face source switch: trained / random / off, one control, no ambiguity.
- The launcher menu and its options.
- Reading in order on a phone.
- Presets that behave predictably.

None of these produce a picture on their own. All of them are the experience.

### What that rules out


Fixing the result instead of the process. Re-captioning one person's photos is
worth nothing if the next person's harvest writes the same broken captions.
Repositioning one node is worth nothing if the numbering can drift again.

The test for any change: **does the next person get this automatically?**

---

### The defect that keeps recurring


Nearly every problem found so far is the same one wearing different clothes —
**a control that says something untrue.**

| what the interface said | what was actually true |
| --- | --- |
| four trained faces available | two were compatible with the loaded checkpoint |
| your preset edits, shown in the panel | the preset silently replaced them at run time |
| STEP 4d sets pose and lighting | computed, then discarded by the router |
| captions describe each photo | all 188 were the same two strings |
| steps numbered 1 to 12 | stored in scrambled order, so list views jumbled them |
| the workflow on screen | a stale copy that overwrote newer work on save |

Six complaints, one failure mode. So when something here is wrong, suspect a
control that lies about what it does before suspecting the model, the settings,
or the training.

This is also the sharper version of the goal, and it is testable in a way that
"make it look like her" never was:

> **Pick something. Verify it took effect. If the screen and the run disagree,
> that is the bug.**

---

---

# From `media_stack_build_log.md`

#### 3.1 KoboldCpp — update


- **Decision:** update prebuilt binary **v1.107 → v1.120** (swap the exe; do
  not build from source).
- **Why:** v1.120 (2026-08-29) is the latest release; v1.107 (Feb 2026) was ~13
  releases behind. It's a self-contained binary with no environment, so the
  update is a drop-in file swap.
- **Compatibility verified:** every launcher flag still exists in v1.120
  (`--config`, `--skiplauncher`, `--ttsmodel/--ttswavtokenizer/--ttsgpu`,
  `--whispermodel`, `--sdmodel`). v1.120 loaded the existing `runtime_config.kcpps`
  with zero errors — it just adds 36 new keys with safe defaults and normalizes
  `sdlora`/`sdloramult` to lists. Only breaking changes in the 1.108–1.120 range
  are to RPC and the removal of `--splitmode row` on CUDA, neither of which this
  stack uses. Ran v1.120 concurrently with live AllTalk + Whisper: no port or
  resource conflict.
- **Backup kept:** `app_cabinet\koboldcpp\koboldcpp_v1.107_backup.exe`
  (sha256 `5485ad78…`).

### Flux — dropped


Flux schnell files deleted (~10 GB reclaimed). Black Forest Labs makes no NSFW models;
community Flux-NSFW is built on Flux **dev** (not schnell) and is still weaker than the
SDXL/Pony ecosystem. **ComfyUI stays**, now running **bigLust (SDXL)**.

- `comfyui/extra_model_paths.yaml` → ComfyUI sees all 7 SDXL checkpoints + 4 LoRAs from
  `app_cabinet/Stable_Diffusion_SDXL/models/` (no copying).
- bigLust image gen through ComfyUI **tested — works**, high-quality photoreal output.
- Canvas recipe: `comfyui/user/default/workflows/Freedom_bigLust_SDXL.json`.
- API recipe (for chat wiring): `comfyui_workflows/biglust_sdxl_api.json` (tested via `/prompt`).
- **Middle-school PDF diagram:** `bigLust_ComfyUI_Recipe.pdf` (repo root, 2 pages).
- In-chat NSFW model = **bigLust**. Alternatives: lustify (bigger/slower), CyberRealistic
  Pony (needs booru-tag prompts).

---

# From `work_log_2026-09-01.md`

### Phase 2 — KoboldCpp v1.107 → v1.120


- Backed up `koboldcpp.exe` → `koboldcpp_v1.107_backup.exe` (sha256 `5485ad78…`).
- Downloaded `koboldcpp.exe` v1.120 from GitHub releases (606 MB), verified
  `--version` → `1.120`, swapped it into place. Removed the duplicate backup.
- Compatibility testing:
  - `--help` cross-checked against every key in `runtime_config.kcpps` — all flags
    present in 1.120.
  - Read release notes v1.108–v1.120: only breaking changes are RPC and the removal
    of `--splitmode row` on CUDA — neither used here.
  - Booted v1.120 with `--nomodel` — API on :5001, `/api/v1/info/version` → HTTP 200.
  - Loaded the existing `runtime_config.kcpps` and re-exported — v1.120 parsed it with
    zero errors; adds 36 new keys with safe defaults, normalizes `sdlora`/`sdloramult`
    to lists.
  - Ran v1.120 concurrently with live AllTalk + Whisper — no port/resource conflict.

### Phase 9 — Flux dropped, ComfyUI → bigLust


- User cut Flux. Deleted the Flux schnell files (~10 GB reclaimed).
- `comfyui/extra_model_paths.yaml` added → ComfyUI now sees all 7 SDXL checkpoints +
  4 LoRAs from `Stable_Diffusion_SDXL/models/` with no copying.
- Built + **tested** a bigLust SDXL text-to-image workflow through ComfyUI's `/prompt`
  API — generated `freedom_test_00001_.png`, high-quality photoreal output.
- Saved:
  - canvas recipe → `comfyui/user/default/workflows/Freedom_bigLust_SDXL.json`
    (built from the shipped `image_sdxl_simple` template),
  - API recipe → `comfyui_workflows/biglust_sdxl_api.json`.
- Made the middle-school PDF walkthrough → `bigLust_ComfyUI_Recipe.pdf` (repo root,
  2 pages, via headless-Chrome HTML→PDF).

---

# From `work_log_2026-09-02_continued.md`

## Work log — 2026-09-02 (continued session)


Continuation of `work_log_2026-09-02.md`. This session ran from ~10:54 to
~22:30 on 2026-09-02. Branch: `Branch04_improvement`.

Covers, in order: model-location inventory, the Wan 2.2 14B video switch, the
lightx2v Lightning speed LoRA, the 14B-video VRAM investigation, the launcher
FULL/VIDEO modes + default video preset, the pending model-deletion review, the
face-training design discussion + deep dive, and the full build + test of the
five-way face competition.

---

#### The goal, in plain words


The user wants to build a shelf of faces that ComfyUI can use. Each face is
learned by the computer from a folder of photos of one real person. This
learning step is called training, and what it produces is a small file called
a LoRA. Once a person has a LoRA, the user can drop that person into any picture
just by adding a tag to the prompt, like `a woman in armor <lora:britany_face:1>`.

The user wants two LoRA files for each person, not one. The first is trained
only on close-up photos of the face, so the face comes out as sharp as
possible. The second is trained on close-ups plus full-body photos, so the
computer also learns the person's build and can draw her whole body correctly.
The user picks whichever file fits the shot.

The faces will be a mix. Some are meant to look like real photographs, some
are meant to look drawn or illustrated, and some sets include full-body poses.

On top of the training, the user wants three tools built around it:

1. A **"Train new face and body" button.** The user clicks it, picks one
   folder of photos, and walks away. The tool sorts the photos on its own —
   close-ups go into both piles, full-body shots go only into the face-plus-body
   pile — and then runs two trainings back to back. It ends with **two LoRA
   files saved, two thumbnail pictures made, and two entries added to the face
   shelf** — one for the face-only LoRA, one for the face-plus-body LoRA.

2. A **face shelf.** This is a panel or node that shows every trained face as a
   small thumbnail with the person's name, three faces to a row. As more faces
   are trained, new rows appear on their own. Clicking a face loads that
   person's LoRA into whatever workflow is open. Each trained person appears on
   the shelf **twice**: a **face** thumbnail that loads the face-only LoRA, and
   a **face + body** thumbnail that loads the face-plus-body LoRA.

3. A **prompt shelf.** This is a list of saved prompts the user can click to
   drop into the working prompt box. It ships with **two** starter prompts: add
   her head to a pose; and add her head and body to a pose. Both are worded to
   force the trained face to be used exactly, with no blending with the source
   face — the one exception is mirroring the expression that is already on that
   picture. (An earlier third prompt, "add her head to a pose but match the
   expression of the original face," turned out to be the same as the first,
   because that mirroring rule already applies to both. The first prompt pairs
   with the face-only LoRA; the second pairs with the face-plus-body LoRA.)

The five-way competition built this session comes **after** the training tool,
not before it. Methods 3, 4 and 5 can each use a trained LoRA, and Method 5
needs one, so the competition is only worth judging once real trained files
exist. Its job is to answer one question: of the five different ways to put a
face plus an expression onto an existing picture, which one gives the best
result on this machine? The user runs the same picture through all five, looks
at the five results, and picks a winner. That winner becomes the method the
"put her on a pose" prompts actually use.

#### What is still needed


1. **The training tool itself.** BUILT (2026-09-03, commit dc7e0dd). Chosen
   standalone trainer: **OneTrainer**, installed at `app_cabinet/OneTrainer/`
   (own Python 3.10 venv, torch cu130). New repo package `face_training/`:
   `sort_photos.py` (InsightFace splits one folder into a close-up "head" set and
   an everything "head_body" set), `otrain.py` (builds a full OneTrainer config
   from its default + built-in preset + per-run values, runs `scripts/train.py`
   headless), `jobs.py` (family x crop job table), `thumbs.py` (renders a
   thumbnail per LoRA through the running ComfyUI - also proves the LoRA loads),
   `pipeline.py` (sort -> train each -> copy to `comfyui/models/loras/faces/` ->
   thumbnail -> update `_registry.json`). Families: `sdxl` (trains on base
   SDXL 1.0, downloaded once), `sdxl_pony` (trains on cyberrealisticPony_v110).
   Verified end to end on the 4080 Laptop: both families train a valid Kohya
   LoRA headless, it loads in ComfyUI and renders, registry updates, VRAM peak
   ~7.4 GB at 1024. Still to do: a real run with real Britany photos (the tests
   used 3 stand-in images), and tune step count / rank / masked-face training
   for quality. See `logs/research_lora_training_tools_2026-09-03.md` for why
   OneTrainer.

   The **`krea2` family is disabled** (`jobs.py`). Finding: the checkpoint
   `lustifyNSFWCheckpoint_v10Krea2.safetensors` is **Krea 2 architecture**
   (Qwen3-VL text encoder, Qwen-image VAE, `Krea2Transformer2DModel` - confirmed
   by its safetensors keys `blocks.N`, `txtfusion`, `mod.lin`, `qknorm`). Not
   SDXL, not Flux. To train it OneTrainer needs the **gated** `krea/Krea-2-Raw`
   diffusers repo (license acceptance + HF token) plus ~20 GB of extra
   downloads; the smallest Krea 2 LoRA preset is 16 GB so a 12 GB card needs
   heavy offloading; and there is no Krea 2 image workflow in ComfyUI yet to
   even use the result. Awaiting the user's call on whether to pursue it.

2. **A "Training" mode in the launcher.** BUILT (commit dc7e0dd). Main menu is
   now `1 FULL / 2 VIDEO / 3 Train a face / 4 Settings / 5 Quit`. Option 3 shows
   plain-language help, asks for a name and a photo folder (native folder
   picker), warns the voice/chat load will be stopped, starts a low-memory
   ComfyUI for the thumbnail step, runs `face_training.pipeline` in OneTrainer's
   venv, then returns to the menu.

3. **The face shelf.** BUILT (commit ddef0e8). ComfyUI node package
   `freedom_face_shelf` (repo `comfyui_ext/`, mirrored to `custom_nodes/`):
   `FreedomFaceShelf` reads `_registry.json`, its `web/face_shelf.js` draws a
   card grid on the node (thumbnail, person, "face" vs "face + body", family
   label; 3 per row, rows grow with the registry; Refresh / None; partial LoRAs
   amber). Clicking a card sets the hidden `selected` widget; `run()` loads that
   LoRA onto the model + CLIP passing through and outputs the trigger word and
   person name. Routes `/freedom/faceshelf/{list,thumb}`. Demo graph
   `Freedom_Face_Shelf.json` (checkpoint → shelf → trigger+prompt concat →
   sampler, with a how-to note).
   Verified end to end (headless + in the browser): node registers, the card
   grid renders on the node with the real thumbnail, a real mouse click on a
   card sets the selection and highlights it, None clears it, Refresh re-reads
   the registry, and picking a face applies its LoRA through to a full render
   (tested with a real `susana_head_sdxl` LoRA).

   **CORS note:** ComfyUI's `origin_only_middleware` 403s the Claude browser
   extension's requests (it sees them as cross-site). To drive ComfyUI from the
   browser, start it with `--enable-cors-header "http://127.0.0.1:8188"`. The
   launcher does NOT pass this - decide whether to add it permanently (it
   slightly weakens CSRF protection; low risk on a local single-user box).

4. **The prompt shelf.** BUILT (commit 742c4d6). Node package
   `freedom_prompt_shelf` - `FreedomPromptShelf`: an editable positive +
   negative prompt with a drawer of clickable saved prompts under it. Ships the
   two templates (trigger first, "same face / same person", negatives vs
   face-swap + blending; pose and expression left as `<...>` to type - per
   current SDXL LoRA guidance the trigger carries identity only). `{trigger}`
   is filled from an optional `trigger` input (wire the Face Shelf into it).
   Add / Save / Delete your own prompts; stored in `.../faces/_prompts.json`.
   Routes `/freedom/promptshelf/{list,save,delete}`.

5. **The wiring.** DONE (commit 742c4d6).
   - `Freedom_Face_Competition`: Method 5's placeholder `LoraLoader` replaced
     with a real `FreedomFaceShelf` + a `StringConcatenate` joining her trigger
     to the shared prompt into Method 5's text encode. Notes rewritten.
   - `Freedom_Face_Image.json` (new): checkpoint -> Face Shelf -> Prompt Shelf
     -> encode -> sampler -> save, with a how-to note. The face-shelf-centric
     image workflow (the beginner `Freedom_bigLust_SDXL.json` is left alone).
   - `Freedom_Video.json`: a note added - a face LoRA is SDXL/Flux and cannot
     load on the Wan video model. The face gets into video by making the still
     in `Freedom_Face_Image` first, then sending that still to the video queue
     as the start frame. There is no direct LoRA wire for video.
   Verified: nodes register + hook their panels, clicking a saved prompt loads
   it, the full chain renders headless, the competition loads with the shelf in
   Method 5 and no placeholder left.

6. **Finish testing the competition.** The five methods have each been proven to
   run on their own. The five of them chained together, and the skip checkboxes
   in the browser panel, have not been tested yet.

7. **The model-deletion review** (section 7) is still waiting on three yes/no
   answers before anything is moved to the Recycle Bin.

---

### 0b. The Face Tool (built 2026-09-03, commits a846ac8 / 0da2c3a / 6eb6b0c)


Launcher **option 4 "Face tool"** opens a small tkinter window (runs in
OneTrainer's venv). It keeps a **profile per person** under
`app_cabinet/OneTrainer/_face_profiles/<slug>/` and adds the "Seek" workflow the
user asked for. New modules in `face_training/`:

- `identity.py` — averaged ArcFace identity from a starter folder + a chosen
  best photo (anchor); rejects folder faces that don't match the anchor.
- `profiles.py` — the profile store + `status()` (Updated / Resume? / Start /
  Working) + the STOP sentinel file (separate from profile.json so a running
  seek can't clobber the window's stop request) + crop-deletion tracking.
- `scan_cache.py` — one SQLite DB per profile; face detection cached by content
  hash so a re-run skips unchanged files and a stopped scan resumes. ~1 s/image.
- `seek.py` — six checkpointed stages: **scan → learn → group → reteach →
  search → clean**. Group photos are cropped to just her (other people removed)
  into `clean/head` + `clean/body`; `found/` is transient staging that empties
  as `clean/` fills. Stop is safe at any point; Resume re-enters the first
  unfinished stage.
- `facebank.py` — the learning layer, shared across all profiles under
  `_face_profiles/_global/`: (1) a growing bank of "other people" faces that
  tightens the per-person match cutoff automatically; (2) a feedback log of
  borderline calls; (3) a small hand-rolled logistic "judge" that replaces the
  fixed cutoff once 200+ labelled rows exist; (4) crop-margin preferences
  nudged by which Clean crops the user deletes.
- `face_tool_ui.py` — the window: profile list, **+ Add person**, **Seek**
  (folder picker + "all subfolders" box), **Resume seek**, **Train**, **Stop**,
  **Review N** (confirm/flip borderline calls → trains the judge), and a
  "train this person now?" prompt after a Seek finishes.
- `pipeline.py --presorted` — trains straight from `clean/head` + `clean/body`.

**Verified end to end** on `F:\Chest\Stable Diffusion\My Stuff\Susana` (77
photos, 46 with another person, name is Susana Patel): identity from 14 refs;
full Seek → 13 face + 58 body single-subject crops (couple/group photos cropped
to just her), bank grew to ~115 other faces, adaptive cutoff 0.32→0.34; a
mid-scan Stop saved state and `--resume` finished the rest; presorted training
ran from the Clean set. Still to do: a real quality training run (the tests used
40 steps / rank 8), the face shelf + prompt shelf nodes, and the workflow
wiring (items 3-5 above).

---

### 1. Model, checkpoint, LoRA and tensor locations (inventory)


Verified on disk. Given to the user verbatim.

#### Image models — SDXL. ComfyUI reads this via `extra_model_paths.yaml`.

```
F:\Apps\freedom_system\app_cabinet\Stable_Diffusion_SDXL\models\
  Stable-diffusion\   bigLust_v16 (default), lustifyNSFWCheckpoint_v10Krea2 (12 GB,
                      actually Flux/Krea-family DiT, NOT SDXL), cyberrealisticPony_v110,
                      realvisxlV50_v50LightningBakedvae, sdxl10ArienmixxlAsian_v45Pruned,
                      "sdxlVanilla_v10Base (asian)", v1-5-pruned-emaonly (SD1.5),
                      "Unconfirmed 516442.crdownload" (aborted download, 6.5 GB)
  Lora\               Emotions V1 (Krea2 arch - matches lustify Krea2),
                      expression_helper2.0 (Flux), japanese_girl_v1.1 (confirmed SDXL,
                      ss_base_model_version = sdxl_base_v0-9), "Hands zib v1" (SD3.5/Qwen-style)
  VAE\ VAE-approx\ hypernetworks\ embeddings\ adetailer\ Codeformer\ GFPGAN\ deepbooru\ karlo\
```

#### Chat / LLM models

```
F:\Apps\freedom_system\app_cabinet\koboldcpp\models\
  Rocinante-X-12B-v1b-Q4_K_M.gguf   (current chat model)
  ggml-base.en.bin                  (Whisper base, English)
F:\Apps\freedom_system\app_cabinet\text-generation-webui\user_data\models\
  Pygmalion-2-7B-GPTQ, Wizard-Vicuna-13B-Uncensored.Q4_K_M.gguf   (the old chat model)
  loras\ and mmproj\ here are empty placeholders
```

#### ComfyUI's own model folders

```
F:\Apps\freedom_system\app_cabinet\comfyui\models\
  diffusion_models\  Wan2.2-TI2V-5B-Q5_K_M.gguf, Wan2.2-I2V-A14B-HighNoise-Q3_K_M.gguf,
                     Wan2.2-I2V-A14B-LowNoise-Q3_K_M.gguf, qwen-image-edit-2511-Q3_K_M.gguf
  text_encoders\     umt5-xxl-encoder-Q5_K_M.gguf, qwen_2.5_vl_7b_fp8_scaled.safetensors
  vae\               wan2.2_vae.safetensors (5B only), wan_2.1_vae.safetensors (14B),
                     qwen_image_vae.safetensors
  loras\             ip-adapter-faceid-plusv2_sdxl_lora.safetensors,
                     Wan2.2-Lightning\Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1\
                       high_noise_model.safetensors, low_noise_model.safetensors
  ipadapter\         ip-adapter-faceid-plusv2_sdxl.bin
  clip_vision\       CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors
  controlnet\        xinsir_controlnet_union_sdxl_promax.safetensors
  insightface\       inswapper_128.onnx, models\buffalo_l\ (auto-downloaded)
  facerestore_models\ GFPGANv1.4.pth
  ultralytics\bbox\  face_yolov8m.pt
  liveportrait\      5 .safetensors (auto-downloaded on first use)
```

Recycle Bin (deleted, not usable): Wizard-Vicuna-13B, SultrySilicon-7B, pygmalion-2-7b.

---

### 2. Wan 2.2 14B I2V switch  (commit 140622e)


- Downloaded both 14B experts via aria2c (`-x16 -s16`, ~44 MB/s):
  `Wan2.2-I2V-A14B-HighNoise-Q3_K_M.gguf` and `LowNoise` (~6.7 GB each).
  NOTE: aria2c with multiple bare URLs treats them as MIRRORS of one file —
  must pass each with its own `-o filename` or separate invocations.
- Built `Freedom_Video.json` as the 14B two-expert graph (script:
  `comfyui_ext/freedom_video_queue/build_video_14b.py` at the time; superseded
  by the Lightning builder). Old 5B graph saved as `Freedom_Video_5B_fast.json`.
- Node graph: 2× `UnetLoaderGGUF` → 2× `LoraLoaderModelOnly` (bypassed) →
  2× `ModelSamplingSD3` (shift 8) → `WanImageToVideo` → two-stage
  `KSamplerAdvanced` (high steps 0-10 `return_with_leftover_noise=enable`;
  low steps 10-end `add_noise=disable`) → `VAEDecode` → `FreedomVideoSave`.
- **VAE bug found in testing:** the 14B I2V model needs the **Wan 2.1 VAE**
  (`wan_2.1_vae.safetensors`, 16-ch latent), NOT `wan2.2_vae.safetensors`
  (48-ch, 5B TI2V only). Wrong VAE → runtime error
  `Given groups=1, weight of size [5120, 36, 1, 2, 2], expected input ... 36
  channels, but got 64`. Downloaded the 2.1 VAE from
  `Comfy-Org/Wan_2.1_ComfyUI_repackaged/split_files/vae/wan_2.1_vae.safetensors`
  (~243 MB) and pointed node 7 at it.
- Verified end to end: 448×640 × 33f, 16 steps, both experts load and hand
  off, decode + auto-save + metadata sidecar all correct. ~10.5 GB peak VRAM.

### 3. Plain-language "why 14B" note  (commit 051e3fe)


Added `MarkdownNote` id 55 beside STEP 1 of the video workflow: why the big
model is the default (motion coherence, LoRA support, two-pass design) and what
it costs (time, VRAM, disk, chained long clips), in middle-school teaching
language. Middle-school = full explanatory prose, not bullet fragments.

### 4. lightx2v Lightning speed LoRA  (commit 29a1a4c)


- Researched: `lightx2v/Wan2.2-Lightning`, folder
  `Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1` → `high_noise_model.safetensors`
  and `low_noise_model.safetensors` (~1.23 GB each). Official Native-Comfy
  recipe from the repo JSON: **ModelSamplingSD3 shift 5**, KSamplerAdvanced
  **4 steps total, split 2/2, cfg 1**, euler/simple.
- Rebuilt `Freedom_Video.json` (script:
  `comfyui_ext/freedom_video_queue/build_video_14b_lightning.py`):
  - nodes 20/21 = speed LoRAs, **active**, strength 1.0, path uses **backslashes**
    (`Wan2.2-Lightning\...\high_noise_model.safetensors`) to match ComfyUI's
    lora listing exactly.
  - nodes 22/23 = a second pair of `LoraLoaderModelOnly`, **bypassed**, for the
    user's motion/expression LoRAs later. Chain: expert → speed LoRA →
    motion LoRA → ModelSamplingSD3 → sampler.
  - ModelSamplingSD3 shift 5; KSamplerAdvanced 4 steps / cfg 1 / split 2/2.
  - The negative CLIPTextEncode is left wired but ignored (cfg 1).
- Kept the prior 20-step graph as `Freedom_Video_14B_quality.json`.
- So there are three video workflows: `Freedom_Video.json` (14B + Lightning,
  default), `Freedom_Video_14B_quality.json`, `Freedom_Video_5B_fast.json`.

### 5. The 14B-video VRAM investigation  (finding recorded in commit 29a1a4c)


Symptom: the 14B video model ran at **~465 seconds per step** — a 3.4 s clip
took 25+ minutes. Investigated three ways (with the Lightning LoRA, without it,
with every ComfyUI memory flag, with the GGUF files pre-warmed into RAM).

Root cause (verified, not guessed): ComfyUI 0.34 uses `comfy_aimdo` 0.4.15
("RAM pressure cache" / DynamicVRAM) which memory-maps the GGUF and streams +
casts weights per step through a 16 GB reservation. It only stays fast when
the mmap'd file is hot in the OS page cache. Two things break that here:
1. **AllTalk + Whisper hold ~5.5 GB of VRAM.** aimdo sees NVML memory pressure
   and refuses to commit the model — streams it every step.
2. **Plain ComfyUI keeps the ~5 GB umt5 text encoder resident** after prompt
   encode, leaving only ~4 GB for a ~7 GB diffusion model → partial load →
   same 465 s/step.

The one time it was fast (~18 s/step at 12:09) was a fluke — the GGUF files
were freshly downloaded and still fully page-cached, and AllTalk had not yet
loaded its model.

**The recipe that works, verified:** BOTH of
1. AllTalk + Whisper stopped, and
2. ComfyUI launched with `--cache-none`
→ 832×480 × 81f (3.4 s), 4-step Lightning → **148 s end to end, ~29 s/step**.

The 5B path (`Freedom_Video_5B_fast.json`) stays the choice when the voice apps
must remain up — the 5B (3.6 GB) fits VRAM alongside them.

### 7. Model-deletion review  —  PENDING, NOT EXECUTED


The user asked for a cleanup of incompatible model files, then said "standby".
**Nothing has been deleted.** Plan is to move to Recycle Bin, not hard-delete.
Three open questions:

1. Is `Stable_Diffusion_SDXL/models/Stable-diffusion/lustifyNSFWCheckpoint_v10Krea2.safetensors`
   (12 GB, Flux/Krea-family, NOT SDXL) the "one more image model" to keep?
   If yes, `Lora/Emotions V1.safetensors` (same Krea2 architecture) is kept too.
2. Delete these five app-cabinet items?
   - `Stable-diffusion/v1-5-pruned-emaonly.safetensors` (SD 1.5, no SD1.5 workflow)
   - `Stable-diffusion/Unconfirmed 516442.crdownload` (aborted download)
   - `Lora/expression_helper2.0.safetensors` (Flux LoRA, no Flux checkpoint)
   - `Lora/Hands zib v1.safetensors` + `.json` (SD3.5/Qwen LoRA, no match)
   - `diffusion_models/Wan2.2-I2V-A14B-HighNoise-Q3_K_M.gguf.part` (stale partial;
     the real .gguf is complete and verified)
3. Delete the two SD 1.5 ControlNets in
   `F:\Chest\Stable Diffusion\My Stuff\ControlNet Models\`?

A 7 pm cron reminder (job 385b6bd2) fired and re-surfaced these; still unanswered.

---

### 8. Face training / library / competition — design discussion


The user wants: (a) train a face LoRA and use it in normal prompts
(`<lora:britany_face:1>`); (b) a face+body LoRA (separate file — the user wants
TWO LoRAs per person, one face-only, one face+body); (c) put her face + a
specific expression onto an existing picture, her own mouth and eyes making
that expression, no blending with the source face.

Update (2026-09-03): (c) is not a third prompt. It is the same as (a) — the
face-only prompt always mirrors the expression already on the picture, so
"put her head on a pose" and "put her head on a pose matching the expression"
are one prompt. The prompt shelf ships two prompts, not three: head-only
(face LoRA) and head+body (face+body LoRA). Ordering: the training tool is
built first; the five-way competition is judged afterward, once real trained
LoRAs exist. Each trained person gets two thumbnails on the shelf.

Ready-made pieces identified:
- Training in ComfyUI: `ComfyUI-FluxTrainer` (`InitSDXLLoRATraining`) or
  `comfyUI-Realtime-Lora`.
- Face/LoRA library: `ComfyUI-Lora-Manager`.
- Prompt library: `ComfyUI-Prompt-Gallery` / `ComfyUI_PromptManager`.

Deep dive delivered as `scratchpad/face_expression_deep_dive.md` (not in repo —
it was a one-off report). Five families for job (c):
- A. Face reenactment / motion transfer (LivePortrait, AdvancedLivePortrait
  ExpressionEditor, Skyreels-A1, HunyuanPortrait). LivePortrait: ~10 control
  dials, breaks on big head turns, identity leak in cross-reenactment. Community
  mostly uses it to GENERATE training photos.
- B. Identity adapter + structural guide (InstantID, PuLID, Face-Adapter).
- C. Dense face-mesh ControlNet + the trained LoRA — the most controllable SDXL
  route; uses the LoRA directly.
- D. Instruction-edit models (Qwen-Image-Edit 2511, Flux Kontext,
  Krea-2 Identity Edit, BFS LoRAs) — the "third real option," not a paint-over
  or warp-swap. Q3/Q4 GGUF fits 12 GB.
- E. Face swap (ReActor) — ruled out by the user, kept for completeness.

Decision: build a **five-way competition** — one workflow that runs the same
job through all five methods.

#### Model downloads (~26 GB — script `scratchpad/dl_face_competition.sh`)

| file | dir | size | source |
|---|---|---|---|
| inswapper_128.onnx | models/insightface | 529 MB | datasets/Gourieff/ReActor |
| GFPGANv1.4.pth | models/facerestore_models | 333 MB | gmk123/GFPGAN |
| ip-adapter-faceid-plusv2_sdxl.bin | models/ipadapter | 1.4 GB | h94/IP-Adapter-FaceID |
| ip-adapter-faceid-plusv2_sdxl_lora.safetensors | models/loras | 355 MB | h94/IP-Adapter-FaceID |
| CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors | models/clip_vision | 2.4 GB | h94/IP-Adapter/models/image_encoder |
| xinsir_controlnet_union_sdxl_promax.safetensors | models/controlnet | 2.4 GB | xinsir/controlnet-union-sdxl-1.0 (promax) |
| face_yolov8m.pt | models/ultralytics/bbox | 50 MB | Bingsu/adetailer |
| qwen-image-edit-2511-Q3_K_M.gguf | models/diffusion_models | 9.3 GB | unsloth/Qwen-Image-Edit-2511-GGUF |
| qwen_2.5_vl_7b_fp8_scaled.safetensors | models/text_encoders | 8.8 GB | Comfy-Org/Qwen-Image_ComfyUI/split_files/text_encoders |
| qwen_image_vae.safetensors | models/vae | 243 MB | Comfy-Org/Qwen-Image_ComfyUI/split_files/vae |

Auto-download-on-first-use (confirmed working during tests): insightface
`buffalo_l` pack, LivePortrait's 5 models, ReActor's `parsing_parsenet.pth`,
DWPose (`yolox_l.onnx`, `dw-ll_ucoco_384.onnx`), openpose preprocessor models.

#### Workflow: `Freedom_Face_Competition.json`  (builder: `build_face_competition.py`)

50 nodes, 6 groups. Shared inputs (FreedomFaceComp + `CheckpointLoaderSimple`
bigLust + 2 shared `CLIPTextEncode`), then five method groups each ending in
its own `FreedomChainLink` → `SaveImage`, chained 1→2→3→4→5 via the `after`
input. Save prefixes `britany_1_faceswap` … `britany_5_shapetracer`.

| # | method | nodes | identity source |
|---|---|---|---|
| 1 | ReActor face swap | `ReActorFaceSwap` (inswapper_128 + GFPGANv1.4) | photo |
| 2 | Qwen-Image-Edit 2511 | `UnetLoaderGGUF` + `CLIPLoader`(qwen_image) + `VAELoader` + 2× `TextEncodeQwenImageEditPlus` (image1=pose, image2=her) + `VAEEncode` + `KSampler` (20 steps, cfg 2.5, euler) + `VAEDecode` | photo |
| 3 | IPAdapter FaceID + pose | `IPAdapterUnifiedLoaderFaceID` (FACEID PLUS V2, provider CPU) + `IPAdapterFaceID` (image = photo batch, combine_embeds average) + `OpenposePreprocessor` + `ControlNetLoader`(xinsir promax) + `ControlNetApplyAdvanced` + `EmptyLatentImage` 832×1216 + `KSampler` | several photos (+ optional LoRA on base) |
| 4 | LivePortrait | `ExpressionEditor` (src_image = photo, sample_image = expression source, sample_ratio 1.0) → `ReActorFaceSwap` to place the finished face on the pose picture | photo |
| 5 | shape tracer | `LoraLoader`(PUT_YOUR_BRITANY_LORA_HERE) + `DWPreprocessor` + `ControlNetLoader`(xinsir) + `ControlNetApplyAdvanced` + `VAEEncode`(pose, img2img) + `KSampler` denoise 0.55 + `VAEDecode` + `UltralyticsDetectorProvider`(face_yolov8m) + `FaceDetailer` denoise 0.45 | the trained LoRA (+ optional photo) |

Plain-language `MarkdownNote` on every method; full "this works like this /
Step 1 / Step 2 …" walkthroughs on methods 4 and 5; a top "READ ME FIRST" note.
Note: `MarkdownNote` is a frontend-only node — it does not appear in
`/object_info`; all 23 real node types resolve.

### 10. Face competition testing


Stand-in inputs used: pose = `input/test_14b_start.png`; "her" photos =
`input/britany_test_photos/{p1,p2,p3}.png` (copies of earlier generated images —
faces are meaningless, this only proves plumbing).

| Method | Test | Result | Time |
|---|---|---|---|
| 1 Face swap | isolated API prompt | **PASS** — `m1_reactor_test_00001_.png` (832×1216) | 24 s |
| 2 Qwen instruction edit | isolated API prompt | **PASS** — `m2_qwen_test_00001_.png`, no OOM, fits 12 GB in cache-none | 208 s |
| 3 IPAdapter FaceID + pose | isolated API prompt | **PASS** — `m3_faceid_test_00001_.png`; helper models auto-downloaded | 41 s |
| 4 LivePortrait | isolated API prompt | **PASS** — `m4_lp_test_00001_.png`; LP models auto-downloaded | 28 s |
| 5 shape tracer (no LoRA — bigLust stand-in) | isolated API prompt | **PASS** — `m5_struct_test_00001_.png`; DWPose + xinsir CN + img2img + FaceDetailer + yolov8 all ran | ~90 s |

Test scripts: `scratchpad/test_m{1..5}_*.py`.

#### NOT tested

- The five chained together through the panel — the "run one, then the next"
  sequencing (`FreedomChainLink` ordering) and the skip-checkbox → group-bypass
  behaviour. Needs the workflow open in a browser, or Chrome automation.
- Method 5 with a real trained Britany LoRA — waits on the training tool.
- Whether any result looks like her — needs real photos + a real pose picture.

---

### 15. Open items / what's next


1. **Model-deletion review** — 3 questions in section 7, unanswered.
2. **Face-training tool** — not built. The competition's method 5 and the whole
   face-library idea depend on it. Plan was: `ComfyUI-FluxTrainer` or
   `comfyUI-Realtime-Lora` + a "Train new face and body" node that takes ONE
   folder and produces TWO LoRAs (face-only from the close-ups, face+body from
   all of them), plus a "Training" launcher mode.
3. **Face competition** — test the full chain + panel in a browser; then a real
   run once real inputs + a trained LoRA exist.
4. **Face library + prompt library** — install `ComfyUI-Lora-Manager` and a
   prompt-gallery pack; pre-load the three face-adherence prompt templates.
5. Carried over from the earlier log: push status is now current; character-card
   asterisk narration; Project 3 multi-API router; Project 4 SillyTavern
   extensions; one clean launcher run from the .bat itself.

### 16. Gotchas worth keeping


- aria2c multiple bare URLs = mirrors of one file. Use `-o` per file.
- ComfyUI 0.34 `comfy_aimdo` streams GGUF weights under VRAM pressure → ~40×
  slowdown. Fix: free the VRAM (stop other GPU apps) AND `--cache-none`.
- 14B Wan I2V needs `wan_2.1_vae.safetensors`, not `wan2.2_vae.safetensors`.
- ComfyUI LoRA widget values on Windows use backslash paths — match the
  `/object_info` listing exactly.
- pip install into `comfyui/venv` fails on `cv2.pyd` if ComfyUI is running.
- `insightface` 1.0.1 is pure-Python now — installs clean on py3.13.
- ReActor's GitHub repo is 403; use the Codeberg mirror.
- `KSamplerAdvanced` serialized widget order includes the seed's
  `control_after_generate` as an extra value: `[add_noise, seed, control,
  steps, cfg, sampler, scheduler, start_at, end_at, return_with_leftover]`.
- A ComfyUI generation keeps running inside ComfyUI even if the external
  monitoring script that queued it is killed — check `/history/<id>` after.

---

### 17. Face Competition - Run 1 (head-only swap) RESULTS  [2026-09-03]


Inputs: Susana LoRA `susana_head_sdxl` (rank 8, ~260 steps, undertrained),
10 InsightFace-verified Susana reference photos in `input/susana_ref/`,
random full-body pose photo `input/comp_pose_body.png` (fair-skinned brunette,
grey tee + dark jeans, plain grey studio, barefoot, neutral face).

Clean full run: ComfyUI history `4692816b` - success, all 5 methods produced
output, nothing silently dropped. Fresh browser page load + workflow reloaded
from disk so the Method-5 FaceDetailer fix (commit 5da14ef) was actually in
the graph.

Fixes that had to land first (all this session):
- Method 3: `_load_folder_batch` was stretching ref photos -> InsightFace
  "no face detected". Fixed with `_fit_square` letterbox pad.
- Method 2: missing the official Qwen-Image-Edit-2511 node chain -> dithered
  garbage. Added ModelSamplingAuraFlow(3.1), CFGNorm, FluxKontextImageScale,
  ImageFromBatch, 2x FluxKontextMultiReferenceLatentMethod; KSampler 40/cfg3.
  Swapped Q3_K_M -> Q4_K_M GGUF.
- Method 5: FaceDetailer widget values stale for current Impact Pack
  (`guide_size_for` now BOOLEAN, `sam_mask_hint_use_negative` now COMBO
  "False"). Old values -> "Failed to validate prompt for output 81" ->
  Method 5 silently missing from a "successful" run. Fixed, commit 5da14ef.

Per-method verdict (Run 1, head-only):
1. ReActor face swap  - WORKS BEST. Body/clothes/pose/background untouched,
   face is convincingly Susana (ReActor reads the ref photos directly, so the
   weak LoRA does not matter here). Output `britany_1_faceswap_00003_.png`.
2. Qwen instruct edit - WORKS. Clean, good Susana likeness. Drawback: it
   re-frames the picture (FluxKontextImageScale standardises resolution) so the
   feet/lower legs get cropped and the body is lightly redrawn.
   `britany_2_instruct_00003_.png`.
3. IPAdapter FaceID   - WORKS AS DESIGNED, i.e. it GENERATES a brand-new person
   in the pose - new clothes, new body. Not a head swap. Moderate likeness.
   `britany_3_fingerprint_00002_.png`.
4. LivePortrait + ReActor - WORKS. Result ~= Method 1 because "auto" expression
   mode copies the pose's own (neutral) expression = near no-op, then ReActor
   swaps. Its unique value (borrow an expression from a 2nd photo) only shows
   when you feed it that 2nd photo. `britany_4_expression_00005_.png`.
5. Shape tracer + LoRA - RUNS CORRECTLY now. Redraws the whole scene on the
   pose trace, then repaints the face with the trained LoRA. Clothes/body
   lightly redrawn. Likeness soft - the Susana LoRA is undertrained, not a
   pipeline bug. `britany_5_shapetracer_00002_.png`.

Conclusion: all 5 methods produce correct, valid output for the head-only run.
Remaining imperfections are inherent method trade-offs, not errors. Run 1 is
DONE. Run 2 (full-body swap) not started yet.

---

### 18. Face Competition - Run 2 (head + body swap) RESULTS  [2026-09-03]


User: "Use Susana's body lora, Susana's body shot, pull a random full body
photo, swap the head AND body. Keep moving forward until all five tests
complete successfully."

Blockers surfaced first (user answered via question tool):
- No Susana body LoRA existed. User picked "train a quick one (~260 steps)".
- Methods 1 and 4 (ReActor) are face-only, cannot swap a body. User:
  "Make a big fat note on these ones that they only do face swaps."

What was done:
1. Trained `susana_head_body_sdxl` (SDXL LoRA, rank 32, 20 epochs x 22 images
   = 440 steps, 10.4 min). Source: 22 curated body/face crops (dropped the
   ~35 ultra-tall strips that made a first 58-image attempt run at 290s/epoch;
   ComfyUI stopped during training to free VRAM). Registered, both Susana
   cards now show on the Face Shelf.
2. Added loud red "face swap only, never a body" notes to Methods 1 and 4 in
   the workflow (commit on 2026-09-03).
3. Built `comfyui/input/susana_body_ref/` - 12 InsightFace + identity
   verified upright real photos of Susana (a rejected 13th was a race photo
   shot sideways - the "rotated and stretched" one the user flagged; it is a
   scratch thumbnail, never in the set).
4. Run 2 config (all runtime, no builder change): shared prompt = full-body
   scene description; Method 2 given its own body-swap instruction (node 23
   prompt input disconnected, widget text set); Method 5 redraw denoise
   0.55 -> 0.72; Face Shelf card = susana_head_body_sdxl @ 0.9.

Clean run: ComfyUI history `038a66c6` - success, all 5 methods produced
output.

Per-method verdict (Run 2, head + body):
1. ReActor          - FACE ONLY (as noted). Susana's face on the random
   photo's body/clothes. `britany_1_faceswap_00004_.png`.
2. Qwen edit        - WORKS. This time the full head-to-toe framing was kept
   (the explicit "show her complete body, same framing" instruction fixed the
   Run 1 crop). Clean image. Face + body likeness WEAK - reads as a generic
   pale brunette. `britany_2_instruct_00004_.png`.
3. IPAdapter FaceID - WORKS. Generates a whole new figure in the pose (head +
   body inherently). Moderate Susana likeness, its own wide-leg outfit.
   `britany_3_fingerprint_00003_.png`.
4. LivePortrait     - FACE ONLY (as noted). ~= Method 1.
   `britany_4_expression_00006_.png`.
5. Shape tracer + body LoRA - WORKS. Full redraw of the whole person on the
   pose trace, face repainted with the new body LoRA. Coherent full-body
   image. Likeness SOFT - the quick 440-step LoRA is undertrained (a
   deliberate "prove the pipeline" choice). `britany_5_shapetracer_00003_.png`.

Conclusion: all 5 methods completed successfully (valid, coherent,
intended-type output; no crashes, no dropped methods). Head+body identity is
weak on Methods 2 and 5 - that is the undertrained quick LoRA plus the
inherent difficulty of a body swap, not a pipeline error. A longer-trained
`susana_head_body_sdxl` is the fix when likeness matters.

---

# From `ram_fix_and_remote_access_2026-09-05.md`

### 4. Remote phone access - research before building anything


User asked for "a separate app, a server to run ComfyUI... remotely from an iPhone,"
explicitly asking to check whether this already exists before building it.

**It does.** Found **Comfy Portal** (open source, native iOS/Android app, actively
maintained - 74 GitHub stars, last updated the same day this was checked). It connects
directly to an existing ComfyUI instance (no custom server needed), supports editing
prompts, picking checkpoints/LoRAs (model pickers read live from the server), combining
images (LoadImage node support), a history gallery, and - the key point - renders any node
it doesn't have a hand-built editor for straight from the server's own `/object_info`
schema, so this project's custom nodes (the whole Face Competition pipeline, Presets node,
etc.) work without any app update. Free for personal use. Two lighter alternatives (Comfy
Remote, ComfyLink) also exist but weren't pursued once Comfy Portal covered the need.

**Decision:** use Comfy Portal + Tailscale rather than build a custom app/server -
confirmed with the user before doing any setup work, since building a worse version of an
existing, maintained tool would have been reward-hacking the request rather than actually
solving it.

### 6. Two workflow-content questions, answered by inspecting the live server (not git log)


- **Is the 5-method competition the same workflow as an "original" pre-competition face
  swap recipe?** No separate one exists. Fetched the actual saved workflow JSON from the
  running server: `Freedom_Face_Image.json` and `Freedom_Face_Shelf.json` are both plain
  10-node text-to-image workflows (no ReActor/IPAdapter/face-swap nodes at all) that just
  pull a saved face *description* into the prompt text. `Freedom_Face_Competition.json`
  (121 nodes) is the only workflow that actually does image-based face-swapping.
- **Is there a fast vs. quality video workflow?** Yes - `Freedom_Video_5B_fast.json` and
  `Freedom_Video_14B_quality.json` already exist as two separate saved files. The
  launcher's "VIDEO MODE" toggle isn't a model switch, though - it only frees VRAM by
  turning off the voice apps; it runs whichever of the two files you open. The menu label
  used to say "fast 14B video," implying the mode itself was fast, when actually the model
  is unaffected by the toggle - fixed in the menu rebuild below.

### 7. Launcher menu rebuild (Branch06)


Realized mid-conversation that exposing ComfyUI on the Tailscale IP by default inside the
existing "ComfyUI only" option would mean *every* use of that mode is remotely reachable,
which the user did not want - remote access needed to be its own explicit, opt-in choice,
not bundled into local-only usage. Rebuilt the main menu to 8 items:

1. Start FULL stack (chat + voice + video)
2. Start VIDEO mode (14B video; voice off) - "fast" dropped from the label
3. Start ComfyUI only (no chat, no voice, no server/phone access) - **local only**,
   `phone_access=False`
4. Start ComfyUI Server and phone access - **new**, `phone_access=True`, adds the
   Tailscale `--listen`
5. Train a NEW face LoRA (renamed from "Train a face")
6. Face Seek (renamed from "Face tool")
7. Settings
8. Quit launcher

Also fixed the actual behavior behind "I need to safely quit whatever app is running
without picking which one, since the launcher only runs one at a time": pressing `q` in the
running-app console now stops the app and returns to this main menu instead of closing the
whole launcher program - a one-line change (the old code did `return` right after the
console call; now falls through to loop again). "Quit launcher" (item 8) is the only thing
that ends the program, and it's only reachable once nothing is running.

**Testing that change surfaced a real bug**, not just cosmetic: returning to the main menu
and then hitting EOF on stdin (e.g. the piped test, but also a real risk if a console window
ever loses its input) crashed with an unhandled `EOFError` traceback, because the
top-level menu prompt had no EOF handling the way the console loop already did. Fixed by
catching `EOFError`/`KeyboardInterrupt` there too and treating it as "quit launcher."

**Tested all 8 options end-to-end**, not just checked they compile:

- Option 3: started healthy: local (`127.0.0.1`) reachable, Tailscale IP genuinely
  unreachable (curl connection refused) - confirmed live, not assumed from reading the code.
- Option 4: started healthy, reachable on **both** `127.0.0.1` and `100.65.32.118` - the
  stack summary correctly printed "COMFYUI SERVER + PHONE ACCESS" with both URLs.
- Options 1 and 2 (FULL, VIDEO): both started every service healthy (AllTalk, Whisper,
  ComfyUI fresh; Resource Monitor/KoboldCpp/SillyTavern already running externally, reused
  correctly), `q` returned to the menu, "Quit launcher" exited cleanly.
- Option 6 (Face Seek): opened the actual OneTrainer "Freedom Face Tool" window, returned
  to the menu without hanging; the test window was closed afterward as cleanup.
- Option 7 (Settings) and option 8 (Quit): both routed and behaved correctly.
- Option 5 (Train a NEW face LoRA) was confirmed to route correctly and start its prompt
  flow; the full interactive flow (name entry, a native Windows folder-picker dialog) was
  not driven end-to-end since it risks leaving a real GUI dialog open with no way to
  dismiss it non-interactively - the underlying function is unchanged from before, only its
  menu label was renamed.

Committed as `acbc75f` "Split ComfyUI-only from remote access; safe app-quit returns to
menu," pushed to `origin/Branch06`.

---
