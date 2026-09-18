# Face Competition — full-strength rebuild (technical detail) + the hair discussion

**Date:** 2026-09-04
**Branch:** Branch04_improvement
**Builder:** `comfyui_ext/freedom_face_competition/build_face_competition.py`
**Node package:** `comfyui_ext/freedom_face_competition/nodes.py` (+ `web/face_competition.js`)
**Mirrors:** `app_cabinet/comfyui/custom_nodes/freedom_face_competition/`,
`comfyui_workflows/Freedom_Face_Competition.json`

This log is the technical companion to `face_competition_rebuild_2026-09-04.md`
(which covers the accountability side and the original spec). This one records
exactly what got built, node by node, and the hair-fix discussion that came
after it.

---

## 1. `FreedomFaceComp` node changes

File: `nodes.py`. Two new state fields, two new outputs — additive, so
existing wiring by index (0-4) is untouched:

```python
DEFAULT_STATE = {
    "prompt": "",                       # scene DESCRIPTION - Methods 3 and 5 only
    "negative": "...",
    "instruction": "",                  # edit INSTRUCTION - Method 2 only
    "expression_mode": "auto",
    "pose_image": "",
    "expression_image": "",
    "driving_image": "",                # Method 4's expression source photo
    "photo_folder": "",
    **{f"skip_{k}": False for k, _ in METHODS},
}

RETURN_TYPES = ("IMAGE","IMAGE","IMAGE","STRING","STRING","STRING","IMAGE")
RETURN_NAMES = ("pose_image","face_photos","expression_image","prompt",
                "negative","instruction","driving_image")
```

`run()` now also returns `s.get("instruction","")` and
`_load_input_image(s["driving_image"]) if s.get("driving_image") else expr`
(falls back to the expression photo / pose photo if no driving photo is set).

## 2. Web panel (`face_competition.js`) changes

Removed: the old EXPRESSION mode selector (auto / photo / sliders) and its
`exprimg` input.

Added:
- **DRIVING EXPRESSION PHOTO (Method 4)** — filename input, saves to
  `driving_image`.
- **INSTRUCTION (Method 2 only)** — textarea, saves to `instruction`.
- Renamed the old **WORDS** box to **SCENE DESCRIPTION (Methods 3 and 5)** to
  make the split explicit.
- `USES` dict rewritten to describe each method's real behaviour instead of
  a generic "uses: a PHOTO of her" for all five.

## 3. Per-method build, exact wiring

### Method 1 — ReActor face swap (nodes 6, 7, 8, 10, 11, 12, 13, 14)

Old: one `ReActorFaceSwap` node reading "the first clear face" from the photo
batch, `GFPGANv1.4.pth` restore.

New chain:
```
FreedomFaceComp.face_photos --> ReActorBuildFaceModel(compute_method="Mean")
                                    --> FACE_MODEL
ReActorOptions --> OPTIONS
ReActorFaceBoost(GPEN-BFR-512.onnx, visibility 1.0, restore_with_main_after True) --> FACE_BOOST
FreedomFaceComp.pose_image + FACE_MODEL + OPTIONS + FACE_BOOST
    --> ReActorFaceSwapOpt(swap_model=inswapper_128.onnx,
                            facedetection=retinaface_resnet50,
                            face_restore_model=GPEN-BFR-512.onnx,
                            face_restore_visibility=0.8, codeformer_weight=0.5)
    --> FreedomChainLink --> SaveImage "britany_1_faceswap"
```
`ReActorBuildFaceModel` averages every photo in the folder into one face
model instead of using a single photo, so the swap is anchored on all of her
references, not whichever one happened to load first.

### Method 2 — Qwen-Image-Edit 2511 (nodes 20-37, unchanged infra + rewire)

Kept the official 2511 chain: `UnetLoaderGGUF(qwen-image-edit-2511-Q4_K_M.gguf)`
→ `ModelSamplingAuraFlow(3.1)` → `CFGNorm` → `FluxKontextImageScale` (scales
the pose/scene to Qwen's preferred resolution) → 2×
`FluxKontextMultiReferenceLatentMethod(index_timestep_zero)`.

Changed:
- `TextEncodeQwenImageEditPlus` node 23's `prompt` input is now wired to
  `FreedomFaceComp.instruction` (output slot 5) instead of `.prompt`
  (slot 3, the shared scene description). This was the single most important
  fix for Method 2 — previously it silently received a plain scene
  description instead of an edit instruction.
- Added a second `ImageFromBatch` (node 37, index 1) so the instruction
  encoder gets **two** reference angles of her (`image2`, `image3`) instead
  of one.
- Node 23's default widget instruction (used until the panel Instruction box
  is filled in) was rewritten to explicitly ask for "her face, her hair, and
  her whole head" and to reference both image 2 and image 3.

KSampler unchanged: 40 steps, cfg 3.0, euler, simple.

### Method 3 — Identity stack (nodes 40-56, 90-95 originally, renumbered 51-56 to avoid a clash)

This is the method that changed the most. Old: bare `IPAdapterUnifiedLoaderFaceID`
+ `IPAdapterFaceID` on the plain checkpoint, no trained file, no InstantID.

New chain:
```
CheckpointLoaderSimple.MODEL
  --> LoraLoaderModelOnly(r"faces\susana_head_body_sdxl.safetensors", strength 0.7)   [node 55]
  --> IPAdapterUnifiedLoaderFaceID("FACEID PLUS V2", lora_strength 0.6, "CPU")        [node 40]
        (lora_strength 0.6 auto-loads ip-adapter-faceid-plusv2_sdxl_lora.safetensors,
         the companion LoRA that was downloaded during the original build and
         never used)
  --> IPAdapterFaceID(weight 0.6, weight_faceidv2 1.3, combine_embeds "concat")       [node 41]
        image input = FreedomFaceComp.face_photos (the whole folder)

InstantIDModelLoader("ip-adapter.bin")             --> INSTANTID          [node 51]
InstantIDFaceAnalysis("CPU", antelopev2 pack)      --> FACEANALYSIS       [node 52]
ControlNetLoader("instantid_diffusion_pytorch_model.safetensors")
                                                    --> CONTROL_NET        [node 53]
ImageFromBatch(her photos, index 0)                --> one clear portrait [node 56]

ApplyInstantID(instantid, insightface, control_net, image=portrait,
               model=IPAdapterFaceID.model,
               positive/negative = CLIPTextEncode(scene description)/(negative),
               weight 0.85)                                               [node 54]
  --> MODEL, positive, negative

DWPreprocessor(pose_image)          --> body pose image                   [node 42]
ControlNetLoader(xinsir union)                                            [node 43]
ControlNetApplyAdvanced(ApplyInstantID.positive/negative, xinsir CN,
                         body pose image, strength 0.6)                   [node 44]
  --> positive, negative

EmptyLatentImage(832x1216)          --> latent                            [node 45]
KSampler(ApplyInstantID.model, node44.positive/negative, latent,
         30 steps, cfg 5.0, dpmpp_2m, karras)                             [node 46]
  --> VAEDecode --> FreedomChainLink --> SaveImage "britany_3_fingerprint"
```

Four identity layers stacked: her trained file, FaceID + its companion LoRA,
InstantID + face keypoints, then a body-pose ControlNet on top.

**New assets installed this session for this method:**
| asset | where |
|---|---|
| `ComfyUI_InstantID` (cubiq) | `custom_nodes/ComfyUI_InstantID/` |
| `ip-adapter.bin` (1.7 GB) | `models/instantid/` |
| InstantID ControlNet (2.5 GB) | `models/controlnet/instantid_diffusion_pytorch_model.safetensors` |
| antelopev2 face-analysis pack | `models/insightface/models/antelopev2/*.onnx` (see gotcha below) |
| GPEN-BFR-512.onnx, codeformer-v0.1.0.pth | `models/facerestore_models/` |

**Two build-time bugs found and fixed by headless validation** (loading the
workflow from disk, `app.graphToPrompt()` → `POST /prompt`, reading
`node_errors` — no browser hand-editing):
1. `value_not_in_list` on node 55's `lora_name` — ComfyUI on Windows lists
   loras with backslashes (`faces\susana_head_body_sdxl.safetensors`), the
   builder had a forward slash. Fixed with a raw string
   `r"faces\susana_head_body_sdxl.safetensors"`.
2. `AssertionError: 'detection' in self.models` from `InstantIDFaceAnalysis`
   at runtime — cubiq's node calls
   `FaceAnalysis(name="antelopev2", root=folder_paths.models_dir/"insightface")`,
   so insightface looks in `models/insightface/models/antelopev2/*.onnx`
   (note the doubled `models`). The pack had been downloaded to
   `~/.insightface/models/antelopev2/` (the default insightface cache
   location), which cubiq's node does not read. Copied the 5 `.onnx` files
   (`scrfd_10g_bnkps.onnx` = detection, `glintr100.onnx` = recognition,
   `1k3d68.onnx`, `2d106det.onnx`, `genderage.onnx`) to the correct path and
   verified with a standalone `FaceAnalysis(...).prepare()` call before
   re-running.

### Method 4 — LivePortrait + swap (nodes 60-68, 96)

Old: `ExpressionEditor.sample_image` wired to `FreedomFaceComp.expression_image`,
which in "auto" mode just returned the pose picture itself → the expression
step was a no-op and Method 4 collapsed into a copy of Method 1.

New:
```
ImageFromBatch(her photos, index 0) --> src_image      [node 68]
FreedomFaceComp.driving_image       --> sample_image   (NEW - a real expression photo)
ExpressionEditor --> image (her face wearing the driving expression)      [node 60]
ReActorOptions (own instance, node 96) + ReActorFaceBoost (node 67, GPEN-BFR-512)
ReActorFaceSwapOpt(input_image=pose, source_image=ExpressionEditor.image,
                    options, face_boost)                                  [node 61]
  --> FreedomChainLink --> SaveImage "britany_4_expression"
```
Upgraded from the plain `ReActorFaceSwap` to the same `ReActorFaceSwapOpt` +
`ReActorFaceBoost` + GPEN-BFR-512 stack as Method 1, so its swap quality
matches Method 1's; the only difference left between the two methods is the
expression stage.

Test run used `driving_image = "FanJan.jpg"` (the stranger reference photo).

### Method 5 — Shape tracer + trained file (nodes 70-88)

Old: one `DWPreprocessor` (body + face skeleton) feeding one
`ControlNetApplyAdvanced`, denoise 0.55.

New:
```
DWPreprocessor(pose_image)                    --> body pose image    [node 71]
MediaPipe-FaceMeshPreprocessor(pose_image, max_faces 1, min_confidence 0.5,
                                resolution 512)  --> dense face mesh  [node 87]

ControlNetApplyAdvanced #1: text conditioning + xinsir CN + body pose,
                            strength 0.5                              [node 74]
ControlNetApplyAdvanced #2 (chained after #1): + xinsir CN + face mesh,
                            strength 0.8                              [node 88]
  --> positive, negative --> KSampler
```
`KSampler` (node 76): steps 28→30, denoise 0.55→0.65 (redraw enough of the
person to actually change who she is, per family C's intent - "the most
controllable SDXL route").

The rest (FreedomFaceShelf trained-file pick, FaceDetailer face repaint) is
unchanged.

### Node-id map (for anyone editing the builder later)

| range | method |
|---|---|
| 1-5 | shared (FreedomFaceComp, checkpoint, 2 CLIPTextEncode) |
| 6-8, 10-14 | Method 1 |
| 20-37 | Method 2 |
| 40-56, 90 (unused, removed) | Method 3 core; 51-56 InstantID additions |
| 60-68, 96 | Method 4 |
| 69-88 | Method 5 |
| 200 | top README note |

---

## 4. Validation method used (no hand-operation)

For every check in this rebuild:
1. Rebuild the workflow JSON from `build_face_competition.py` (writes both
   `app_cabinet/comfyui/user/default/workflows/` and the repo's
   `comfyui_workflows/` mirror in one run).
2. Mirror `nodes.py` and `web/face_competition.js` into
   `app_cabinet/comfyui/custom_nodes/freedom_face_competition/`.
3. Restart ComfyUI when a *node type* changed (new custom node installed) -
   not needed for JSON-only or Python-node-logic-only changes.
4. In a **fresh** browser tab (old tabs cache the old JS module - a hard
   reload is not enough, a new tab is): `fetch()` the workflow JSON with a
   cache-busting query string, `app.loadGraphData(wf)`, then
   `app.graphToPrompt()` → `POST /prompt` and read `node_errors`. This is
   ComfyUI's own validator, run against the file exactly as it sits on disk -
   nothing is edited in the console first.
5. Only after that comes back clean does the prompt actually get queued and
   run for real images.

This caught both Method 3 bugs above before a full 20-minute run was wasted
on them.

---

## 5. Results of the first full-strength run (ComfyUI history `8bba9e8d`)

Face-match scores: cosine similarity between each output's face and the new
36-photo clean Susana profile (`F:\Chest\Stable Diffusion\My Stuff\Susana\Clean\`,
built earlier the same session - see the profile-rebuild discussion below).
A genuine, unedited photo of her scores **~0.75** against this profile's
average and **1.00** against its own duplicate in the set (used as ceiling
references, not a literal target).

| # | method | vs profile mean | vs best single clean photo | verdict |
|---|---|---:|---:|---|
| 1 | ReActor full stack | 0.702 | 0.753 | looks like her; face only, full body/clothes kept |
| 2 | Qwen, own instruction | -0.089 | -0.002 | does not look like her - Q4 model's identity ceiling, not a wiring bug; correctly kept the whole scene and full-body framing this time |
| 3 | LoRA + FaceID + InstantID | 0.468 | **0.742** | **up from 0.25 before the stack** - now clearly her; framing collapsed to a face close-up (InstantID pulls toward the face) instead of the intended full body - the body-pose ControlNet strength needs raising to hold it |
| 4 | LivePortrait + swap | 0.501 | 0.695 | looks like her; face only; expression stage now driven by a real photo instead of being a no-op |
| 5 | mesh + pose + trained file | -0.013 | 0.044 | does not look like her yet - the trained file is the quick, undertrained one (440 steps); not a wiring bug |

Three of five (1, 3, 4) now produce a result that reads as Susana. Method 2's
ceiling is the compressed model (a ~20 GB full/fp8 download is the next
lever). Method 5's ceiling is the training data (a properly trained file,
not a quick one, is the next lever).

---

## 6. The hair discussion

### 6.1 What was asked for, and what happened to it

The user asked, after noticing Method 1's swapped face sat inside a
stranger's hairstyle: *"Wire up both swap method 1 and 4 to BOTH hair
methods 2 and 4 first"* - referring to two items from an earlier list of
hair-fix options:

1. Use a pose/stranger photo whose hair already resembles hers (no build
   needed - a free fix by choosing better source material).
2. **Repaint the hair after the swap** - select the hair region, regenerate
   it guided by a photo of her real hair. Uses tools already on the machine
   (a segmentation mask + an SDXL inpaint pass).
3. Use a different method that draws the whole head (Methods 3 or 5).
4. **A dedicated hair-transfer tool** - `ComfyUI_StableHair_ll`
   (<https://github.com/lldacing/ComfyUI_StableHair_ll>), which extracts a
   hairstyle from a reference image via a Hair Extractor + a Latent
   IdentityNet and transplants it onto a target face, keeping identity and
   background intact. Needs its own node install and model downloads - not
   present on the machine.

The user confirmed: build **both #2 (repaint) and #4 (transfer)**, wired to
**both** Method 1 and Method 4, each producing its own competing output
image (so four extra files: M1+repaint, M1+transfer, M4+repaint,
M4+transfer).

**Then the conversation moved to a different, more urgent problem** - the
discovery that prior competition runs had been hand-operated in the browser
console rather than produced by the workflow itself, followed by the
LoRA-stacking demand that became the Section 3 rebuild above. The hair work
was never started: **no hair-repaint nodes, no `ComfyUI_StableHair_ll`
install, and no hair-related model files exist anywhere on the machine as of
this log.** This was confirmed by searching `custom_nodes/` and `models/`
for anything hair-related (nothing found) and grepping the builder for
"hair" (only found in the READ-THIS warning notes, not in any node wiring).

### 6.2 Which of the five methods can already handle hair on their own

Three of the five methods redraw the head (or the whole picture) rather than
pasting a face into an existing one, so they can be told what to do with
hair through their existing text input - no addon required:

- **Method 2 (Qwen instruction edit).** Rewrites the whole picture from the
  Instruction box. Adding a clause such as "give her long, dark, wavy hair"
  to the instruction is enough - it is already wired to redraw the head
  region, hair included.
- **Method 3 (identity stack).** Generates the entire person from scratch
  from the Scene Description box plus the identity embeddings. Describing
  her hair in that prompt is enough.
- **Method 5 (shape tracer + trained file).** Redraws the entire person -
  face, body, and hair - guided by the trained file and the prompt. No addon
  needed, though the *quality* of the hair depends on whether the trained
  file actually learned her real hair from its training photos (the current
  quick files may not have learned it well).

### 6.3 Which of the five need an addon

The two methods built on the ReActor swap engine only ever touch the inner
face region and structurally cannot draw hair, body, or clothing:

- **Method 1 (face swap).**
- **Method 4 (expression + swap).**

For these two, the options remain exactly the four listed in §6.1: pick a
better-haired source photo (free), or build the repaint step and/or the
`ComfyUI_StableHair_ll` transfer tool and wire them on as extra outputs after
the swap.

### 6.4 Status

Not built. Queued as the next piece of work, pending the user's go-ahead.

---

## 7. Assets on disk after this session (face competition only)

```
custom_nodes/
  comfyui_controlnet_aux, ComfyUI-Impact-Pack, ComfyUI-Impact-Subpack,
  ComfyUI_IPAdapter_plus, ComfyUI-AdvancedLivePortrait, comfyui-reactor-node,
  ComfyUI_InstantID                                    <- new this session
  freedom_face_competition, freedom_face_shelf, freedom_prompt_shelf

models/
  insightface/inswapper_128.onnx
  insightface/models/antelopev2/*.onnx                 <- new this session
  facerestore_models/GFPGANv1.4.pth
  facerestore_models/GPEN-BFR-512.onnx                 <- new this session
  facerestore_models/codeformer-v0.1.0.pth             <- new this session
  instantid/ip-adapter.bin                             <- new this session
  controlnet/instantid_diffusion_pytorch_model.safetensors  <- new this session
  controlnet/xinsir_controlnet_union_sdxl_promax.safetensors
  ipadapter/ip-adapter-faceid-plusv2_sdxl.bin
  loras/ip-adapter-faceid-plusv2_sdxl_lora.safetensors
  loras/faces/susana_head_sdxl.safetensors (260 steps, rank 8)
  loras/faces/susana_head_body_sdxl.safetensors (440 steps, rank 32)
  diffusion_models/qwen-image-edit-2511-Q3_K_M.gguf, -Q4_K_M.gguf
  text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors
  vae/qwen_image_vae.safetensors
  ultralytics/bbox/face_yolov8m.pt

Not yet on disk: a hair-repaint pipeline, ComfyUI_StableHair_ll and its
models, the full-size/fp8 Qwen-Image-Edit 2511 model.
```

---

## 8. Open items, in the order they were raised

1. **Hair fixes for Methods 1 and 4** (repaint + `ComfyUI_StableHair_ll`
   transfer) - not started, see §6.
2. **Method 3's framing** - raise the body-pose ControlNet strength (or feed
   a latent seeded from the pose instead of an empty latent) so it holds a
   full-body shot instead of collapsing to a face close-up.
3. **Method 2's identity ceiling** - needs the full-size or fp8
   Qwen-Image-Edit 2511 model (~20 GB) to improve past a plain scene edit.
4. **Method 5's likeness** - needs `susana_head_body_sdxl` retrained properly
   (target ~1500-2000 steps) instead of the quick 440-step version.
5. **The retry/nudge loop** the user asked for earlier (generate, score
   against the profile, adjust one setting, try again, up to 5 attempts,
   keep the best) - discussed at length (target-score math, why nudging a
   seed cannot raise a method's ceiling) but not built.
6. **New Susana profile** - built this session from 36 hand-verified photos
   in `F:\Chest\Stable Diffusion\My Stuff\Susana\Clean\` (`_profile_mean.npy`,
   `_profile_refs.npy`), replacing the old polluted 56-embedding one for
   scoring purposes. Not yet wired to replace the profile Seek/training use.
7. **CP1-CP4 debugging agents** - copied into
   `REPO_koboldccp_sst_tts_media/.claude/agents/` this session; require a
   Claude Code restart from this folder to actually load and become usable.
