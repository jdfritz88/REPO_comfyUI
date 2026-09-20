# FaceDetailer — setup log

One file gathering **every FaceDetailer entry found anywhere in our logs**, copied here so the whole
history of this node on this machine is in one place.

- Created 2026-09-19.
- **Nothing was deleted from the source files.** Every entry below is a copy; the originals stay
  where they are, and the source file and line numbers are named above each block.
- Searched: every `.md` in `REPO_comfyUI/logs/`, `REPO_comfyUI/REPO_comfyUI_Monitor_LOG.md`, and
  every `.md` in `REPO_koboldccp_sst_tts_media/logs/`. Search terms: `facedetailer`,
  `face detailer`, `face_detailer`, `detailer`, `impact pack`, `yolov8`, `bbox`, `adetailer`.
- Files that matched: 7. Files with no FaceDetailer content are not listed.
- The full research-and-installation record for 2026-09-19 is its own file and is **not** duplicated
  here: `logs/facedetailer_research_and_install_2026-09-19.md`.

---

# PART 1 — INSTALLATION AND FIRST APPEARANCE (2026-09-02)

**Source: `REPO_koboldccp_sst_tts_media/logs/work_log_2026-09-02_continued.md:441-450`**

```
### Node packs installed (all into `comfyui/venv`, py 3.13.5, all import clean)

comfyui/custom_nodes/
  comfyui_controlnet_aux          (Fannovel16)          - MediaPipe FaceMesh, DWPose
  ComfyUI-Impact-Pack             (ltdrdata)            - FaceDetailer
  ComfyUI-Impact-Subpack          (ltdrdata)            - UltralyticsDetectorProvider
  ComfyUI_IPAdapter_plus          (cubiq)               - IPAdapter FaceID
  ComfyUI-AdvancedLivePortrait    (PowerHouseMan)       - ExpressionEditor
  comfyui-reactor-node            (Gourieff, FROM CODEBERG - github repo is 403)
```

**Source: same file, line 483** — where the detector model came from:

```
| face_yolov8m.pt | models/ultralytics/bbox | 50 MB | Bingsu/adetailer |
```

**Source: same file, line 218** — an `adetailer\` folder already existed in the Stable Diffusion
model tree that was inventoried, alongside `VAE\ VAE-approx\ hypernetworks\ embeddings\ Codeformer\
GFPGAN\ deepbooru\ karlo\`.

---

# PART 2 — FACEDETAILER'S ROLE IN THE FIVE-METHOD COMPETITION

## 2.1 Method 5's definition

**Source: `REPO_comfyUI/logs/face_competition_runs_2026-09-03.md:30`**

```
| 5 | Shape tracer | DWPose + ControlNet + KSampler + FaceDetailer + **your LoRA** | **required** | yes (redraws) |
```

**Source: `REPO_koboldccp_sst_tts_media/logs/work_log_2026-09-02_continued.md:526`**

```
| 5 | shape tracer | `LoraLoader`(PUT_YOUR_BRITANY_LORA_HERE) + `DWPreprocessor` +
`ControlNetLoader`(xinsir) + `ControlNetApplyAdvanced` + `VAEEncode`(pose, img2img) +
`KSampler` denoise 0.55 + `VAEDecode` + `UltralyticsDetectorProvider`(face_yolov8m) +
`FaceDetailer` denoise 0.45 | the trained LoRA (+ optional photo) |
```

**Source: `REPO_comfyUI/logs/face_competition_rebuild_2026-09-04.md:66`**

```
| 5 | **C — Dense face-mesh ControlNet + the trained LoRA** | MediaPipe FaceMesh / DWPose +
ControlNet + KSampler + FaceDetailer, all with the person's LoRA | the most controllable SDXL
route; uses the trained file directly, traces pose + dense face structure. |
```

**Source: same file, lines 154-159** — the intended full-strength shape of the method:

```
    union at ~0.5, then `MediaPipe-FaceMeshPreprocessor` (dense face mesh) via
    xinsir union at ~0.8 — family C is specifically the *dense face-mesh*
    route, which the old build was missing (it only had DWPose).
  - `VAEEncode` the pose picture → KSampler at denoise ~0.7 (redraw the whole
    person as her) → `FaceDetailer` with the trained file (repaint the face).
  - trigger + scene description → CLIPTextEncode.
```

## 2.2 The first FaceDetailer defect — a silently dropped output

**Source: `REPO_comfyUI/logs/face_competition_runs_2026-09-03.md:90-98`**

```
3. **Method 5 — silently missing from a "successful" run.**
   FaceDetailer (Impact Pack) widget order/types changed in the installed
   version: `guide_size_for` is now BOOLEAN (was combo `'bbox'`/`'crop_region'`),
   `sam_mask_hint_use_negative` is now COMBO `['False','Small','Outter']`
   (string, not boolean). The old values made ComfyUI print
   "Failed to validate prompt for output 81 / Output will be ignored" and
   **drop Method 5's output while still reporting the run as success.**
   Fixed the node 79 widget values in the builder; also set
   `force_inpaint` True. Commit `5da14ef`.
```

**Source: same file, line 227** — the commit:

```
5da14ef  Competition: fix Method 5 FaceDetailer widget values for current Impact Pack
```

**Source: same file, lines 258-262** — the same failure signature recurring:

```
— Method 5's box (720,1440)–(2220,2200) covered Method 3's `SaveImage#49` and
all of Method 4's save + notes; Method 1's warning note stuck into Method 3's
box. So skipping Method 5 silently switched Methods 3 and 4's outputs off too:
a "successful" run with images quietly missing (same failure signature as the
FaceDetailer bug in §3.3).
```

**Source: `REPO_koboldccp_sst_tts_media/logs/work_log_2026-09-02_continued.md:662-665`**

```
- Method 5: FaceDetailer widget values stale for current Impact Pack
  (`guide_size_for` now BOOLEAN, `sam_mask_hint_use_negative` now COMBO
  "False"). Old values -> "Failed to validate prompt for output 81" ->
  Method 5 silently missing from a "successful" run. Fixed, commit 5da14ef.
```

## 2.3 Hand-operated settings that never made it into the builder

**Source: `REPO_comfyUI/logs/face_competition_rebuild_2026-09-04.md:12-22`**

```
1. **Hand-operated runs reported as tool output.** Across the three
   competition test runs (Run 1 head-only, Run 2 head+body, Run 3 no-LoRA),
   settings were forced at run time through the browser JavaScript console —
   disconnecting Method 2's prompt wire and typing an instruction into the
   node, setting Method 5's KSampler denoise to 0.72, setting FaceDetailer
   widgets before the real fix was committed, setting the shelf selection and
   skip states. Some of those were later folded into the builder (the
   FaceDetailer fix, the method tags). **Method 2's instruction and Method 5's
   denoise were never put in the builder — they were hand-set every run.**
   Loading the workflow fresh off disk and pressing Run would NOT reproduce
   the Run 2 images that were shown.
```

## 2.4 First isolated test of the method — it ran

**Source: `REPO_koboldccp_sst_tts_media/logs/work_log_2026-09-02_continued.md:545`**

```
| 5 shape tracer (no LoRA — bigLust stand-in) | isolated API prompt | **PASS** —
`m5_struct_test_00001_.png`; DWPose + xinsir CN + img2img + FaceDetailer + yolov8 all ran | ~90 s |
```

**Source: same file, lines 649-653** — the first clean full run:

```
Clean full run: ComfyUI history `4692816b` - success, all 5 methods produced
output, nothing silently dropped. Fresh browser page load + workflow reloaded
from disk so the Method-5 FaceDetailer fix (commit 5da14ef) was actually in
the graph.
```

## 2.5 An OOM crash, with Method 5 as the heaviest branch

**Source: `REPO_comfyUI/logs/face_competition_hair_fixes_2026-09-04.md:151-158`**

```
The full run (pose = `FanJan.jpg`) crashed the whole ComfyUI process — killed
by the OS for low memory, confirmed via `Get-CimInstance` showing the process
gone and `system_stats` unreachable, not a Python exception (no traceback in
the log). Methods 1-4 had actually completed and saved real files before the
crash; Method 5 (the heaviest combination — FaceDetailer + mesh + LoRA) was
mid-execution when it died. Fixed operationally by restarting ComfyUI fresh
and running Method 5 alone, then the hair fixes alone, in separate queued
prompts instead of one giant combined run.
```

## 2.6 FaceDetailer is synchronous — verified, not assumed

**Source: `REPO_comfyUI/logs/face_competition_hair_fixes_2026-09-04.md:175-181`**

```
## 4. "One at a time" — verified, not assumed

Checked directly against the installed `execution.py`: none of the nodes
involved (`ApplyHairRemover`, `ApplyHairTransfer`, `KSampler`,
`FaceDetailer`, etc.) are `async def` functions, so ComfyUI's executor runs
every one of them fully synchronously — true concurrent execution of two of
them is structurally impossible.
```

## 2.7 Method 5 left unchanged in the full rebuild

**Source: `REPO_comfyUI/logs/face_competition_full_rebuild_and_hair_2026-09-04.md:215-220`**

```
`KSampler` (node 76): steps 28→30, denoise 0.55→0.65 (redraw enough of the
person to actually change who she is, per family C's intent - "the most
controllable SDXL route").

The rest (FreedomFaceShelf trained-file pick, FaceDetailer face repaint) is
unchanged.
```

---

# PART 3 — THE SCORE THAT MATTERS: FACEDETAILER DID NOT SAVE METHOD 5

**Source: `REPO_comfyUI/logs/face_competition_full_rebuild_and_hair_2026-09-04.md:262-275`**

```
Face-match scores: cosine similarity between each output's face and the new
36-photo clean Susana profile. A genuine, unedited photo of her scores **~0.75**
against this profile's average and **1.00** against its own duplicate in the set.

| # | method | vs profile mean | vs best single clean photo | verdict |
| 1 | ReActor full stack | 0.702 | 0.753 | looks like her; face only, full body/clothes kept |
| 2 | Qwen, own instruction | -0.089 | -0.002 | does not look like her - Q4 model's identity ceiling |
| 3 | LoRA + FaceID + InstantID | 0.468 | **0.742** | **up from 0.25 before the stack** - now clearly her |
| 4 | LivePortrait + swap | 0.501 | 0.695 | looks like her; face only |
| 5 | mesh + pose + trained file | -0.013 | 0.044 | does not look like her yet - the trained file is the
      quick, undertrained one (440 steps); not a wiring bug |
```

**Source: `REPO_comfyUI/logs/face_likeness_methods_research_2026-09-10.md:244-256`**

```
1. **Two methods already score at photograph level.** 0.753 and 0.742 against a
   0.75 reference. This problem was solved on 2026-09-04.
2. **The pure trained-LoRA route is the worst of the five** at 0.044 — and that
   is exactly what the Face Shelf "pick" drives today. Picking Susana runs
   method 5.
3. Which explains why retraining kept feeling like the answer and kept
   disappointing. Better training improves the weakest method; it cannot reach
   0.75, because **a real photograph of her only reaches 0.75.**

**Caveats, honestly.** Method 5 was tested with an old 440-step file; the current
files are 1,995 and 3,340 steps, so it would score better than 0.044 — but
almost certainly nowhere near 0.75.
```

**Why this entry matters to the setup:** Method 5 already contained a correctly placed FaceDetailer
when it scored 0.044. A FaceDetailer in the right position is therefore **not on its own** enough to
produce likeness. See PART 4 for the 2026-09-19 finding about why.

---

# PART 4 — MONITOR LOG ENTRIES (copied from `REPO_comfyUI/REPO_comfyUI_Monitor_LOG.md`)

**Line 70 — the face-size measurement that motivated all of this (2026-09-18 ~21:20)**

```
- **Checked:** Two runs through the API, identical except the framing words: same checkpoint
  `cyberrealisticPony_v110`, same LoRA `susana_head_sdxl_pony` at 0.9, seed 777000111, 26 steps,
  cfg 6, dpmpp_2m / karras, 832x1216, plain negative, plain `LoraLoader` and no custom nodes.
  Then face bounding boxes measured with `models/ultralytics/bbox/face_yolov8m.pt`.
```

Result recorded there: headshot face 484×648 px = **31.03%** of frame; full body 104×141 px =
**1.46%**; the user's own latest picture 116×194 px = **2.25%**, with **2** faces detected. The LoRA
was trained on head crops at 1024.

**Line 75 — the existing FaceDetailer in the competition (2026-09-18 ~21:50)**

```
Competition workflow: 121 nodes, 191 links, 11 labelled SaveImage outputs, all five methods, and a
FaceDetailer (node 79) **already wired into Method 5** with image from VAEDecode and model/clip
from the Face Shelf - that method still scored 0.044 in the 2026-09-04 competition.
```

**Line 79 — capability scan (2026-09-18 ~22:00)**

```
- **Result:** 1,353 node types. FaceDetailer present, `sam_model_opt` confirmed optional,
  `face_yolov8m.pt` on disk, no `sams` folder. **No node can execute another workflow file as part
  of a graph** - the only near-match is `ExecuteAllControlNetPreprocessors`, unrelated.
```

**2026-09-19 ~23:05 — FaceDetailer research, from source not memory**

```
- **Result:** Installed version 8.28.3. The author's written FaceDetailer tutorial is an empty "WIP"
  heading - his real documentation is the example workflow and the code. That example puts
  FaceDetailer **after VAEDecode**, fed by the same model / clip / vae / positive / negative as the
  main KSampler. `enhance_detail` computes `upscale = guide_size / min(bbox_w, bbox_h)`, then clamps
  by `max_size` against the whole crop, so **max_size, not guide_size, is usually the binding
  constraint**. The node's `clip` input is used ONLY by `process_with_loras` (core.py:268, 441) -
  with the wildcard box empty it does nothing. No official ComfyUI documentation exists; it is a
  third-party node.
```

**2026-09-19 ~23:10 — clip-L / clip-G / pivotal**

```
- **Result:** clip-L uses `embedding_size=768, embedding_key='clip_l'`; clip-G uses
  `1280 / 'clip_g'` - a pivotal token is two vectors, resolved at tokenize time, entirely upstream
  of any CONDITIONING. Both LoRAs already train both encoders: **te1 (CLIP-L) 216 tensors,
  te2 (CLIP-G) 579, unet 2382, embeddings 0**. `models/embeddings/` holds only ComfyUI's
  placeholder, so **no pivotal tuning exists in this pipeline today**. FaceDetailer's wildcard box
  re-encodes with plain `CLIPTextEncode`, so it cannot carry a split clip-G/clip-L prompt.
```

**2026-09-19 ~23:30 — installed into v05, validated**

```
- **Result:** 292/292 passed. Added #33 UltralyticsDetectorProvider, #34 FaceDetailer,
  #35 PrimitiveBoolean (default true), #36 ImpactConditionalBranch and #37 MarkdownNote. VAEDecode
  now feeds the detailer and the branch's OFF side; the branch feeds both the preview and the
  auto-save. One real defect was found and fixed during conversion, not in the workflow but in my
  own graph-to-API converter: the frontend adds a `control_after_generate` widget for any INT named
  `seed` even though the server spec does not advertise it, which had shifted every FaceDetailer
  value after the seed.
```

**2026-09-19 ~23:40 — switch proven by execution**

```
- **Result:** PROVEN. Switch ON: detector and FaceDetailer both executed, 48.9 s. Switch OFF:
  **neither executed**, 17.8 s - the lazy branch genuinely skips the work rather than discarding it.
  Outputs differ in 5.36% of pixels against a face box occupying 4.67% of the frame; mean change
  inside the face box 23.7, outside it 0.1, so the repaint is confined to the face. NOT verified:
  that the repaint improves likeness - a crude mean-gradient measure of the face went 6.77 (off) to
  6.29 (on), i.e. slightly smoother rather than sharper, and likeness was not measured.
```

---

# PART 5 — WHERE THE REST OF IT LIVES

| What | File |
|---|---|
| The 2026-09-19 research, installation and verification, in full | `logs/facedetailer_research_and_install_2026-09-19.md` |
| Every monitoring check, ComfyUI side | `REPO_comfyUI_Monitor_LOG.md` |
| The five-method competition scores in context | `logs/face_competition_full_rebuild_and_hair_2026-09-04.md` |
| Why the trained-LoRA route scores lowest | `logs/face_likeness_methods_research_2026-09-10.md` |
| Node packs and model downloads, original install | `REPO_koboldccp_sst_tts_media/logs/work_log_2026-09-02_continued.md` |

## Files searched that contained no FaceDetailer content
`comfy_portal_debug_and_mobile_frontend_2026-09-07.md`, `comfyui_lora_stack_and_repo_migration_2026-09-07.md`,
`face_competition_presets_2026-09-04.md`, `face_pipeline_defects_and_review_2026-09-11.md`,
`face_seek_*.md` (all four), `face_shelf_checkpoint_filtering_2026-09-10.md`,
`move_to_app_cabinet_HANDOFF_2026-09-17.md`, `next_session_prompt_loras_and_onetrainer.md`,
`portrait_master_exhaustive.md`.

One raw server log, `comfyui_relocated_20260907_183026.log`, matches the search term but contains
only ComfyUI's own import lines for the Impact Pack, not any record of our work. Not copied.
