# Five-Way Face Competition — Run 1 and Run 2

**Date:** 2026-09-03
**Branch:** Branch04_improvement
**Workflow:** `Freedom_Face_Competition.json`
(built by `comfyui_ext/freedom_face_competition/build_face_competition.py`,
lives at `app_cabinet/comfyui/user/default/workflows/` and mirrored to
`comfyui_workflows/`)
**Controller node package:** `comfyui_ext/freedom_face_competition/`
(mirrored to `app_cabinet/comfyui/custom_nodes/freedom_face_competition/`)

---

## 1. What the competition is

One picture goes in. Five different techniques each try to put a chosen
person's face (Run 1) or face **and** body (Run 2) onto that picture. Five
pictures come out, `britany_1_...` through `britany_5_...`, in the ComfyUI
output folder. You look at the five and pick the winner; the winner becomes
the method the "put her onto a pose" prompt templates use.

The five methods:

| # | Name | Engine | Uses a trained LoRA? | Can it change a body? |
|---|------|--------|----------------------|-----------------------|
| 1 | Face swap | ReActor (inswapper_128 + GFPGAN) | no | **no — face only** |
| 2 | Instruction edit | Qwen-Image-Edit-2511 (GGUF Q4) | no | yes (redraws) |
| 3 | Identity fingerprint | IPAdapter FaceID + pose ControlNet | optional | yes (generates fresh) |
| 4 | Expression copy | LivePortrait (ExpressionEditor) + ReActor | no | **no — face only** |
| 5 | Shape tracer | DWPose + ControlNet + KSampler + FaceDetailer + **your LoRA** | **required** | yes (redraws) |

The workflow runs the un-skipped methods **one at a time, top to bottom**, so
the GPU is never shared. A `FreedomFaceComp` node holds the shared inputs
(pose image, folder of her photos, prompt, negative) and five skip
checkboxes; a small web panel drives them and writes
`freedom_face_competition_state.json`.

---

## 2. Test subject

**Susana.** Source photos: `F:/Chest/Stable Diffusion/My Stuff/Susana`
(her name in the pictures is "Susana Patel").

LoRAs (in `comfyui/models/loras/faces/`, registry `_registry.json`):

| name | crop | family | rank | steps | size | note |
|------|------|--------|------|-------|------|------|
| `susana_head_sdxl` | head | SDXL | 8 | 260 | 49 MB | trained earlier as a smoke test — undertrained |
| `susana_head_body_sdxl` | head_body | SDXL | 32 | 440 | 198 MB | trained for Run 2 (this session) — quick, undertrained |

Both use trigger token `ohwxsusana`.

Reference photo folders (in `comfyui/input/`):

- `susana_ref/` — 10 square 768×768 face crops, InsightFace + identity
  verified. Used by Run 1.
- `susana_body_ref/` — 12 upright real photos, InsightFace + identity
  verified (cosine sim to identity mean 0.47–0.89; the 0.47 one is an
  AI-generated image, kept low in the order). Used by Run 2. A 13th
  candidate — `SusanaFullBody01.JPEG`, a race-day photo shot sideways — was
  rejected; the "rotated and stretched" thumbnail the user saw was a scratch
  file from that rejection, never in the set.

Pose photo for both runs: `comfyui/input/comp_pose_body.png` — a random
full-body studio photo of a fair-skinned brunette, grey t-shirt + dark
jeans, plain grey background, barefoot, neutral expression.

---

## 3. Fixes that had to land before Run 1 worked

1. **Method 3 — "InsightFace: No face detected."**
   `_load_folder_batch` in the controller node was resizing every reference
   photo to the first image's exact dimensions, i.e. **stretching** faces,
   which breaks the detector. Replaced with `_fit_square()` — scale keeping
   aspect ratio so the long side is 768, then letterbox-pad to a square.
   Commit `b898e3e`.

2. **Method 2 — dithered / distorted garbage output.**
   The Qwen chain was missing the official ComfyUI Qwen-Image-Edit-2511
   template nodes. Added: `ModelSamplingAuraFlow` (shift 3.1), `CFGNorm`,
   `FluxKontextImageScale` on the pose input, `ImageFromBatch` to pick one of
   her photos, and two `FluxKontextMultiReferenceLatentMethod`
   (`index_timestep_zero`) on the positive/negative conditioning. KSampler
   set to 40 steps / cfg 3.0 / euler / simple. Swapped the model file from
   `qwen-image-edit-2511-Q3_K_M.gguf` (artifact-prone) to
   `qwen-image-edit-2511-Q4_K_M.gguf` (13.2 GB). Commit `b898e3e`.

3. **Method 5 — silently missing from a "successful" run.**
   FaceDetailer (Impact Pack) widget order/types changed in the installed
   version: `guide_size_for` is now BOOLEAN (was combo `'bbox'`/`'crop_region'`),
   `sam_mask_hint_use_negative` is now COMBO `['False','Small','Outter']`
   (string, not boolean). The old values made ComfyUI print
   "Failed to validate prompt for output 81 / Output will be ignored" and
   **drop Method 5's output while still reporting the run as success.**
   Fixed the node 79 widget values in the builder; also set
   `force_inpaint` True. Commit `5da14ef`.

Gotcha: after rebuilding the workflow JSON, the browser served a **stale
cached copy** via `/api/userdata/workflows%2F...`. Fix: in the browser,
`fetch` the file with a cache-buster query string and call
`app.loadGraphData()` on the fresh copy before queuing.

---

## 4. Run 1 — head-only swap

**Inputs:** `susana_head_sdxl`, `susana_ref/`, `comp_pose_body.png`.
Shared prompt: a plain scene description. All five skip boxes off.
Method 5 redraw denoise 0.55, face-repaint denoise 0.45.

**Clean run:** ComfyUI history `4692816b` — success, all 5 methods produced
output.

| # | result | verdict |
|---|--------|---------|
| 1 ReActor | face swapped to Susana, body/clothes/pose/background 100% kept, strong likeness | **best** for a pure head swap |
| 2 Qwen | clean image, good likeness, but re-framed the picture (FluxKontextImageScale standardises resolution) so the feet/lower legs are cropped and the body is lightly redrawn | works, framing drawback |
| 3 IPAdapter FaceID | generates a brand-new figure in the pose — new outfit, new body, moderate likeness | works as designed (not a head swap) |
| 4 LivePortrait + ReActor | ≈ Method 1 (auto expression mode copies the pose's own neutral expression = near no-op, then ReActor swaps) | works; expression trick only shows with a 2nd photo |
| 5 Shape tracer + LoRA | full redraw on the pose trace, face repainted with the LoRA; clothes/body lightly redrawn; likeness soft (LoRA undertrained) | runs correctly; likeness limited by training |

**Conclusion:** all 5 produce correct, valid output. Remaining imperfections
are inherent method trade-offs, not bugs.

Output files: `britany_1_faceswap_00003_.png` … `britany_5_shapetracer_00002_.png`.
Contact sheet: sent to user.

---

## 5. Run 2 — head + body swap

### 5.1 Blockers surfaced first (user decided)

- **No Susana body LoRA existed.** Options put to the user: proper (~2000
  steps, ~1 hr) / quick (~260 steps, ~10–15 min) / skip and reuse the head
  LoRA. **User chose: quick.**
- **Methods 1 and 4 (ReActor) are face-only** and cannot swap a body. Options:
  let them do face-only with a note / rebuild them as body-capable methods.
  **User chose: "Make a big fat note on these ones that they only do face
  swaps, not body swaps."**

### 5.2 Work done

1. **Trained `susana_head_body_sdxl`.**
   - First attempt: `face_training.pipeline --presorted --family sdxl` on the
     full 58-image `clean/body` set. Ran at **290 s/epoch** (≈90 min ETA) —
     the ~35 ultra-tall full-length strip crops (aspect ~0.2) bloat the
     aspect buckets, and VRAM was tight with ComfyUI still resident. Killed.
   - Second attempt: curated concept dir (`scratchpad/susana_bodyquick/`),
     22 crops with aspect 0.33–1.6 (dropped the extreme strips), **ComfyUI
     stopped** to free the card, stale backup + cache cleared. Ran at
     ~25–60 s/epoch, **finished in 10.4 min**, 20 epochs × 22 = 440 steps,
     rank 32. Registered; both Susana cards now show on the Face Shelf.
   - Note: the pipeline's minimum is 20 epochs (`otrain.py`
     `epochs = max(20, ...)`), so `--steps 260` still yields 440 raw steps
     with 22 images.

2. **Added the face-only warning notes** (nodes 14 and 66, loud red) to
   Methods 1 and 4 in the builder. Widened both method groups. Rebuilt and
   mirrored the workflow. Commit `a1529fb`.

3. **Built `comfyui/input/susana_body_ref/`** — see §2.

4. **Run 2 config — all runtime, no builder change:**
   - shared prompt → a full-body scene description ("full body photo of a
     woman head to toe, standing in the same pose, plain grey studio
     background, … casual grey t-shirt and dark blue jeans, barefoot, …")
   - **Method 2 given its own instruction:** node 23's `prompt` input
     disconnected in the browser, widget text set to an explicit
     head-and-body replacement instruction that also says "show her complete
     body from head to toe, same framing" (this fixed the Run 1 leg-crop).
   - Method 5 redraw denoise (node 76) 0.55 → **0.72**.
   - Face Shelf card = `susana_head_body_sdxl` @ strength 0.9.
   - pose image + folder set via the state file / server API.

### 5.3 Clean run

ComfyUI history `038a66c6` — success, all 5 methods produced output.

| # | result | verdict |
|---|--------|---------|
| 1 ReActor | **face only** (as noted) — Susana's face on the random photo's body | valid image; does not attempt the body by design |
| 2 Qwen | **full head-to-toe framing kept this time** (explicit instruction fixed the Run 1 crop); clean image; face + body likeness **weak** — reads as a generic pale brunette | runs; weak identity |
| 3 IPAdapter FaceID | whole new figure in the pose (head + body inherently); moderate likeness; its own wide-leg outfit | runs; moderate identity |
| 4 LivePortrait + ReActor | **face only** (as noted) — ≈ Method 1 | valid image |
| 5 Shape tracer + body LoRA | full redraw of the whole person on the pose trace, face repainted with the new body LoRA; coherent full-body image; likeness **soft** (LoRA undertrained) | runs; soft identity |

**Conclusion:** all 5 methods completed successfully — valid, coherent,
intended-type output, no crashes, no dropped methods. Head+body **identity is
weak on Methods 2 and 5**. Cause: the deliberately quick 440-step LoRA plus
the inherent difficulty of a full body swap — not a pipeline error.

Output files: `britany_1_faceswap_00004_.png` … `britany_5_shapetracer_00003_.png`.
Contact sheet: sent to user.

---

## 6. Known limitations / next steps

1. **Likeness.** Both Susana LoRAs are undertrained. When likeness matters,
   train `susana_head_body_sdxl` properly (target ~1500–2000 steps, keep
   ComfyUI off, curate out the extreme-aspect strips or fix the aspect
   bucketing). The quick versions prove the pipeline only.
2. **Method 2 re-frames** whenever `FluxKontextImageScale` changes the input
   resolution. The instruction wording ("same framing, head to toe") helps
   but does not fully lock it.
3. **The shared prompt** feeds Methods 3 and 5 as an SDXL prompt and (in Run
   1) Method 2 as an instruction. These want different text. Run 2 worked
   around it by disconnecting Method 2's prompt input in the browser. A
   proper fix: give `FreedomFaceComp` a `swap_mode` (head | head_body) and a
   second `instruction` output wired to Method 2.
4. **Stale READ-ME notes** in the workflow still say "have not been tested
   yet" / "Still to come: the five-way judging itself". Both runs are now
   done — update on the next builder pass.
5. **Method 5's note** tells the user to pick the "face + body" card; for
   Run 1 (head only) the "face" card is the right one. The note could
   mention both cases.

---

## 7. Commit trail (this work)

```
b898e3e  Competition: fix Method 2 (Qwen) to the official 2511 recipe; fix ref-photo batch
5da14ef  Competition: fix Method 5 FaceDetailer widget values for current Impact Pack
276fe71  Work log: Face Competition Run 1 (head-only) results - all 5 methods verified
a1529fb  Competition: big face-only warning notes on Methods 1 and 4
671b012  Work log: Face Competition Run 2 (head + body) results - all 5 complete
```

---

## 8. Run 3 — face-only, LoRA method skipped  [2026-09-03]

User: "another face only run through but without the lora face groups. Which
of the five steps are the lora groups?"

**Answer:** only **Method 5 (Shape Tracer)** uses a trained LoRA — it is the
only method wired to the Face Shelf node. Method 3 (IPAdapter FaceID) *can*
optionally take one but does not by default. Methods 1, 2, 4 never use a LoRA.
(Verified by walking the graph: only node 81 / Method 5 is downstream of
`FreedomFaceShelf`.)

**Run:** same inputs as Run 1 (head-only) — `susana_ref/`, `comp_pose_body.png`,
head-only shared prompt — with `skip_5_shapetracer = true`.
ComfyUI history `46478264` — success, Methods 1-4 produced output, Method 5
correctly absent. Results match Run 1 exactly (M1 best, M2 reframed + weak
likeness, M3 fresh figure, M4 ≈ M1). Output files
`britany_1_faceswap_00005_.png` … `britany_4_expression_00007_.png`.
Contact sheet sent to user.

### 8.1 Bug found and fixed — the skip checkboxes bypassed the wrong nodes

The web panel turned a ticked "skip method N" checkbox into "bypass every node
**inside method N's group box** on the canvas". The five group boxes **overlap**
— Method 5's box (720,1440)–(2220,2200) covered Method 3's `SaveImage#49` and
all of Method 4's save + notes; Method 1's warning note stuck into Method 3's
box. So skipping Method 5 silently switched Methods 3 and 4's outputs off too:
a "successful" run with images quietly missing (same failure signature as the
FaceDetailer bug in §3.3).

Fix (commit `9b8cfe0`):
- `build_face_competition.py` now tags **every** node with
  `properties.freedom_method` = "1".."5" via a module-level `_M[0]` set at each
  method section; shared nodes (FreedomFaceComp, checkpoint, the two shared
  CLIPTextEncodes) and doc notes stay untagged.
- `web/face_competition.js` `applyBypass()` bypasses by that tag. The old
  group-box scan is kept **only** as a fallback for untagged / pre-tag
  workflows.
- Method 5's group box also moved down the canvas (GY 1440 → 2080) so the
  boxes no longer visually overlap.

Verified in a fresh browser tab (the old tab had the pre-fix JS module
cached — ComfyUI extension `.js` is cached hard by the browser; a brand-new
tab or a real cache-clear is needed to pick up an extension code change):
skip 3 → exactly nodes 40–50; skip 4 → exactly 60–66; skip 5 → exactly
69–82, with Methods 1–4 fully runnable; reset → nothing bypassed.

### 8.2 Commit trail (added)

```
9b8cfe0  Competition: tag nodes by method so the skip checkboxes are reliable
```
