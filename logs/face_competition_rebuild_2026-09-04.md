# Face Competition — full rebuild spec + what went wrong

**Date:** 2026-09-04
**Trigger:** user reviewed the five methods and found several were not built to
their real strength, ran near-identically, and that test results had been
produced by hand-operating the workflow rather than by the workflow itself.

---

## 1. What went wrong (stated plainly, for the record)

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

2. **No method map given up front.** The five methods were built and tested
   without ever laying out, for the user, what each method is for, its
   strengths and weaknesses, and its realistic likeness ceiling. The user had
   to extract that over ~15 messages of pointed questions.

3. **Methods wired in basic single-node form, not full strength.** The user
   asked for "no shortcuts, no stubs, no placeholders" (it is in
   `CLAUDE.md`). The competition was built as a bake-off of the plainest form
   of each method. That was never agreed with the user; "test basic first,
   then improve the winner" was an after-the-fact rationalisation.

4. **Several methods ran effectively identically.** Method 4's expression
   control was set to "auto" (copy the pose photo's own expression), which
   made its LivePortrait stage a near no-op, so Method 4 collapsed into a copy
   of Method 1. Methods 2, 3 and 5 share one generic prompt box, so Method 2
   (which needs an *edit instruction*) got fed a *scene description*.

5. **Downloaded assets left unused.** `ip-adapter-faceid-plusv2_sdxl_lora.safetensors`
   (the FaceID companion LoRA) was downloaded during the original build and
   never wired into Method 3. Method 3's low likeness score (0.25) is partly
   that.

6. **Repeated "only Method 5 uses a LoRA" statements** that then needed
   qualifying ("Method 3 can stack one", "an expression-captioned LoRA"),
   which read as contradiction. The accurate statement: **as wired, only
   Method 5 uses a trained file. Methods 2, 3 and 5 are all *capable* of using
   one; 2 and 3 were not wired for it.**

Feedback on all of the above was submitted via `/feedback`.

---

## 2. The five families (from the original deep dive, recovered from
`work_log_2026-09-02_continued.md` §8 — the standalone doc
`scratchpad/face_expression_deep_dive.md` was a one-off and is gone)

| # | Family | Tools | Core idea |
|---|--------|-------|-----------|
| 1 | **E — Face swap** | ReActor (inswapper_128 + face restore) | paste a real face onto an existing photo, change nothing else. Ruled out by the user originally, kept "for completeness" — and it is the likeness winner. |
| 2 | **D — Instruction-edit models** | Qwen-Image-Edit 2511, Flux Kontext, Krea-2 Identity Edit | rewrite parts of a photo from a typed instruction; face + clothes + background + light together. "The third real option," not a paste and not a warp. |
| 3 | **B — Identity adapter + structural guide** | InstantID, PuLID, IP-Adapter FaceID (+ its companion LoRA) | boil the face down to an embedding, inject it into a fresh generation, guide structure with a keypoint/pose ControlNet. |
| 4 | **A — Face reenactment / motion transfer** | LivePortrait, AdvancedLivePortrait ExpressionEditor | physically re-pose a face's mouth/eyes/brows/gaze to match a driving image, without redrawing. Community mostly uses it to GENERATE expression variations / training photos. |
| 5 | **C — Dense face-mesh ControlNet + the trained LoRA** | MediaPipe FaceMesh / DWPose + ControlNet + KSampler + FaceDetailer, all with the person's LoRA | the most controllable SDXL route; uses the trained file directly, traces pose + dense face structure. |

---

## 3. What "correct / full strength" is for each method

Sources at the end. Assumes the launcher is in Video/Training mode so full
VRAM is free.

### Method 1 — ReActor face swap (family E)
- **Distinct job:** paste her real face onto the photo, change nothing else.
  Highest raw likeness of the five (measured 0.86 vs clean headshots).
- **Full build:**
  - `ReActorBuildFaceModel` (compute_method = Mean) over the whole folder of
    her photos → one averaged FACE_MODEL, instead of "first clear face".
  - `ReActorFaceSwapOpt` + `ReActorOptions` (retinaface_resnet50 detection,
    gender detect off).
  - `face_restore_model` = **GPEN-BFR-512** (downloaded) at visibility
    0.7–0.8; CodeFormer as the alternative. inswapper resizes the face to
    128 px, so the restore pass is not optional.
  - `ReActorFaceBoost` (restore + upscale the face crop before it is pasted
    back).
- **Ceiling:** ~0.86 now; the swap model itself is the limit. Better
  reference photos raise it a little.

### Method 2 — Qwen-Image-Edit 2511 (family D)
- **Distinct job:** instruction-driven edit. "Put her in this photo, and also
  make it night, and change her top" — all at once, coherently.
- **Full build:**
  - Keep the official 2511 node chain (ModelSamplingAuraFlow 3.1, CFGNorm,
    FluxKontextImageScale, 2× FluxKontextMultiReferenceLatentMethod).
  - **Its own instruction box**, wired to a new `instruction` output on
    `FreedomFaceComp` — NOT the shared scene-description prompt.
  - **Up to three references:** image1 = the scene to edit, image2 + image3 =
    her from two angles (two `ImageFromBatch` picks).
  - Model: `qwen-image-edit-2511-Q4_K_M.gguf` is on disk and is the practical
    floor; the fp8 / higher-quant is a ~20 GB download and is the next upgrade
    for identity fidelity.
  - 40 steps, cfg 3.0, euler / simple.
- **Ceiling for a pure face match:** ~0.28 with Q4; identity is a lossy
  rebuild. Its value is flexibility, not fidelity.

### Method 3 — Identity adapter, full stack (family B)
- **Distinct job:** generate a brand-new picture of her from an identity
  embedding + a pose. Total freedom of scene / outfit / style.
- **Full build (all installed now):**
  - base model → `LoraLoaderModelOnly` (her trained file, strength ~0.5, can
    be zeroed) →
  - `IPAdapterUnifiedLoaderFaceID` (FACEID PLUS V2, **lora_strength 0.6** —
    this loads the companion LoRA that was downloaded and never used) →
  - `IPAdapterFaceID` (her photo batch, weight 1.0, weight_faceidv2 ~1.5,
    combine_embeds concat) →
  - `ApplyInstantID` (InstantID ip-adapter + its keypoint ControlNet +
    `InstantIDFaceAnalysis` on the antelopev2 pack, weight ~0.8) — a second,
    stronger identity injection stacked on FaceID →
  - `ControlNetApplyAdvanced` (xinsir union, DWPose of the pose picture) for
    the body pose →
  - KSampler → VAEDecode.
- **Installed this session:** `ComfyUI_InstantID` node (cubiq),
  `models/instantid/ip-adapter.bin`,
  `models/controlnet/instantid_diffusion_pytorch_model.safetensors`,
  `~/.insightface/models/antelopev2/`.
- **Ceiling:** FaceID alone plateaus 80–85 % identity match; the InstantID +
  companion-LoRA + person-LoRA stack is meaningfully higher and is the point
  of the rebuild.

### Method 4 — LivePortrait reenactment (family A)
- **Distinct job:** take her face and give it a chosen expression. The ONLY
  method where you dial the expression. Its natural output is "her, with this
  smile / frown / gaze."
- **Full build:**
  - `ExpressionEditor`: src_image = her photo; **sample_image = a real
    driving-expression photo**, wired to a new `driving_image` output on
    `FreedomFaceComp` — not the pose picture's own face.
  - `src_ratio` / `sample_ratio` / `sample_parts` exposed; the 12 manual
    dials (aaa/eee/woo/smile/blink/wink/eyebrow/pupil/rotate) exposed as the
    by-hand fallback.
  - Then `ReActorFaceSwapOpt` to place the expression-adjusted face on the
    pose picture (same restore stack as Method 1).
- **Ceiling:** ~0.72 (it ends in the same swap engine as Method 1). Breaks on
  big head turns; built for talking-head expression range.

### Method 5 — Face-mesh ControlNet + trained file (family C)
- **Distinct job:** the trained-file route with a dense structural guide.
  Does face + body + hair. Most control.
- **Full build:**
  - `FreedomFaceShelf` (her trained file) → model + clip + trigger.
  - **Two ControlNets in series:** `DWPreprocessor` (body pose) via xinsir
    union at ~0.5, then `MediaPipe-FaceMeshPreprocessor` (dense face mesh) via
    xinsir union at ~0.8 — family C is specifically the *dense face-mesh*
    route, which the old build was missing (it only had DWPose).
  - `VAEEncode` the pose picture → KSampler at denoise ~0.7 (redraw the whole
    person as her) → `FaceDetailer` with the trained file (repaint the face).
  - trigger + scene description → CLIPTextEncode.
- **Ceiling:** high with a well-trained file; the two quick Susana files
  (260 and 440 steps) are undertrained.

---

## 4. `FreedomFaceComp` node changes (so nothing is hand-operated)

New state fields + outputs:
- `instruction` (STRING) — Method 2's edit instruction. Its own panel box.
- `driving_image` (IMAGE, from a filename in `ComfyUI/input`) — Method 4's
  expression source. Its own panel box.

The shared `prompt` output stays, but now feeds **only** Methods 3 and 5
(scene description). Method 2 no longer touches it.

Web panel (`face_competition.js`) gets two new controls: an
"INSTRUCTION (Method 2)" textarea and a "DRIVING EXPRESSION PHOTO (Method 4)"
filename box.

---

## 5. Assets downloaded / installed this session

| item | path |
|------|------|
| GPEN-BFR-512.onnx | `models/facerestore_models/` |
| codeformer-v0.1.0.pth | `models/facerestore_models/` |
| InstantID ip-adapter.bin (1.7 GB) | `models/instantid/` |
| InstantID ControlNet (2.5 GB) | `models/controlnet/instantid_diffusion_pytorch_model.safetensors` |
| antelopev2 insightface pack | `~/.insightface/models/antelopev2/` |
| `ComfyUI_InstantID` node (cubiq) | `custom_nodes/` — needs a ComfyUI restart to load |

Still an upgrade, not done: the fp8 / higher-quant Qwen-Image-Edit 2511
model (~20 GB) for Method 2 identity fidelity.

---

## 6. Sources

- ReActor settings: <https://github.com/Gourieff/ComfyUI-ReActor>,
  <https://www.runcomfy.com/tutorials/guide-to-using-comfyui-reactor-workflow-for-video>
- Qwen-Image-Edit 2511: <https://docs.comfy.org/tutorials/image/qwen/qwen-image-edit-2511>,
  <https://blog.comfy.org/p/qwen-image-edit-2511-and-qwen-image>
- InstantID vs FaceID vs PuLID: <https://aiofm.info/en/guides/pulid-vs-instantid-vs-faceid>,
  <https://github.com/cubiq/ComfyUI_InstantID>
- LivePortrait / ExpressionEditor: <https://github.com/PowerHouseMan/ComfyUI-AdvancedLivePortrait>,
  <https://comfyui.org/en/create-emotions-with-expressioneditor>
- Face similarity / FaceAnalysis: <https://github.com/cubiq/ComfyUI_FaceAnalysis>

---

## 7. Rebuild validation + gotchas found

- **Workflow validates headless.** Loading `Freedom_Face_Competition.json`
  straight off disk and doing `app.graphToPrompt()` -> `POST /prompt` returns
  HTTP 200, a prompt_id, and `node_errors: none` for all 71 nodes. No browser
  hand-operation.
- **Method 3 LoRA path:** ComfyUI on Windows lists loras with backslashes.
  `LoraLoaderModelOnly` needs `wv=[r"faces\susana_head_body_sdxl.safetensors", ...]`
  not a forward slash, or you get `value_not_in_list` and Method 3's output is
  silently dropped.
- **InstantID antelopev2 pack location:** cubiq's `InstantIDFaceAnalysis` calls
  `FaceAnalysis(name="antelopev2", root=models_dir/insightface)`, so insightface
  looks in `comfyui/models/insightface/models/antelopev2/*.onnx` (note the
  double `models`). Downloading to `~/.insightface/models/antelopev2/` gives
  `AssertionError: 'detection' in self.models`. The 5 files needed:
  `scrfd_10g_bnkps.onnx` (detection), `glintr100.onnx` (recognition),
  `1k3d68.onnx`, `2d106det.onnx`, `genderage.onnx`.
- **Chain fragility:** the FreedomChainLink `after` ordering means one method
  erroring stops every method below it. When Method 3 errored on antelopev2,
  Methods 4 and 5 never ran. Consider making each method's chain link tolerate
  an upstream failure.
