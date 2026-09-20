# FaceDetailer — research, installation into v05, and verification

Everything from the session of 2026-09-19 (evening) about FaceDetailer: what the developer's own
materials actually say, what the code actually does, what clip-L / clip-G / pivotal have to do with
it, exactly what was built into the v05 workflow, how it was verified, every defect found including
my own, and what is still open.

- Times are LOCAL. Claude session transcripts record UTC, which is 7 hours ahead.
- Every claim here has its evidence named next to it: a file and line, a workflow node id, a live
  server response, or a measured number. Where something could **not** be verified it says so in
  those words rather than being rounded up to a pass.
- Companion records: per-check entries for the same work are in
  `REPO_comfyUI/REPO_comfyUI_Monitor_LOG.md` (entries dated 2026-09-19 ~23:05 onward).

---

# PART 1 — WHERE THINGS STAND AT THE END OF THIS SESSION

## 1.1 The workflow
`user/default/workflows/Freedom_bigLust_SDXL v05.json` — was 32 nodes / 26 links, now **37 nodes /
36 links**. `last_node_id` 32 → 37, `last_link_id` 66 → 76. A FaceDetailer now sits between STEP 11
(VAEDecode) and the preview / auto-save, behind an on/off switch that defaults to ON.

## 1.2 What is installed and used
| Thing | Detail | Evidence |
|---|---|---|
| ComfyUI-Impact-Pack | **8.28.3** | `custom_nodes/ComfyUI-Impact-Pack/pyproject.toml:4` |
| ComfyUI-Impact-Subpack | provides `UltralyticsDetectorProvider` | `ComfyUI-Impact-Subpack/__init__.py:5` |
| bbox detector | `models/ultralytics/bbox/face_yolov8m.pt`, 52,026,019 bytes, dated 2026-09-02 | directory listing |
| segm detectors | **none** | `models/ultralytics/segm/` does not exist |
| SAM models | **none** | `models/sams/` does not exist |

Because there is no SAM model on disk, `sam_model_opt` is deliberately left unconnected. The
author's own example connects one; ours cannot, and the input is declared optional.

## 1.3 Repository state at end of session
`git status --short` in `REPO_comfyUI`:

```
 M custom_nodes/freedom_face_router/nodes.py        (lazy evaluation, earlier in this session)
 M "user/default/workflows/Freedom_bigLust_SDXL v05.json"   (this work)
?? REPO_comfyUI_Monitor_LOG.md
```

**Nothing is committed.** The pre-change copy of v05 is in the session scratchpad as
`v05_before_facedetailer.json` (47,523 bytes).

---

# PART 2 — WHAT THE DEVELOPER'S OWN DOCUMENTATION SAYS

The user's instruction was explicit: *"Check comfyUI documentation, face detailer author
documentation, and community recommendations... Do not assume or guess, i do not trust you."* So
each source was opened rather than recalled.

## 2.1 The author's written tutorial: it does not exist
The Impact Pack README links `ComfyUI-extension-tutorials/.../detailers.md` for the Detailer nodes.
That page has a **"FaceDetailer" heading with no body** — the document says "WIP...". ltdrdata has
not written prose documentation for this node.

Consequence: his real documentation is (a) the example workflow he ships, (b) the source code,
(c) two lines in the README.

## 2.2 The README's only substantive lines
- `FaceDetailer` — "Easily detects faces and improves them." (README:125)
- "The face that has been damaged due to low resolution is restored with high resolution by
  generating and synthesizing it, in order to restore the details." (README:424)
- "The FaceDetailer node is a combination of a Detector node for face detection and a Detailer node
  for image enhancement." (README:426)
- A 2-pass configuration is described: a first pass at low settings for rough outline recovery, a
  second for detail. (README:432-438)

## 2.3 The author's shipped example — this is the real answer on placement
`custom_nodes/ComfyUI-Impact-Pack/example_workflows/1-FaceDetailer.json`, dumped node by node:

```
CheckpointLoaderSimple #4
  ├─ CLIP  ─► CLIPTextEncode #5 (Positive) ─► KSampler #28.positive
  ├─ CLIP  ─► CLIPTextEncode #6 (Negative) ─► KSampler #28.negative
  ├─ MODEL ─► KSampler #28.model
  └─ VAE   ─► VAEDecode #30.vae
EmptyLatentImage #29 ─► KSampler #28.latent_image
KSampler #28 ─► VAEDecode #30 ─► FaceDetailer #51.image
UltralyticsDetectorProvider #53 ─► FaceDetailer #51.bbox_detector
SAMLoader #16 ─────────────────► FaceDetailer #51.sam_model_opt
CheckpointLoaderSimple #4 ─► FaceDetailer #51.model / .clip / .vae   (via Reroutes 55/56/57)
CLIPTextEncode #5 ─────────► FaceDetailer #51.positive              (via Reroute 59)
CLIPTextEncode #6 ─────────► FaceDetailer #51.negative              (via Reroutes 60/61)
FaceDetailer #51 ─► PreviewImage #7 / #43 / #52
FaceDetailer #51.MASK ─► MaskToImage #17 ─► PreviewImage #18
```

Two facts the author establishes by construction:

1. **FaceDetailer goes after VAEDecode**, operating on finished pixels. It is a post-process, not a
   stage of the first sampling pass.
2. **It carries its own model, clip, vae, positive and negative**, wired from the *same* sources
   that fed the main KSampler.

## 2.4 What the code actually does
`modules/impact/core.py`, function `enhance_detail` (line 250 onward):

```python
if wildcard_opt is not None and wildcard_opt != "":
    model, _, wildcard_positive = wildcards.process_with_loras(wildcard_opt, model, clip)   # line 268
...
if not force_inpaint and bbox_h >= guide_size and bbox_w >= guide_size:
    logging.info("Detailer: segment skip (enough big)")
    return None, None
if guide_size_for_bbox:                       # "bbox"
    upscale = guide_size / min(bbox_w, bbox_h)
else:                                         # "crop_region"
    upscale = guide_size / min(w, h)
new_w = int(w * upscale); new_h = int(h * upscale)
if new_w > max_size or new_h > max_size:      # line 304
    upscale *= max_size / max(new_w, new_h)
    new_w = int(w * upscale); new_h = int(h * upscale)
upscaled_image = utils.tensor_resize(image, new_w, new_h)
latent_image = utils.to_latent_image(upscaled_image, vae, ...)
# ... a full KSampler pass over that crop, with the model handed to the node ...
```

Three consequences that matter, all derived from the code rather than from a document:

- **`w` and `h` are the crop region, not the face box.** The crop is `bbox_crop_factor` times the
  box. `max_size` is tested against the scaled *crop*. So with the defaults
  (`guide_size` 512, `max_size` 1024, `bbox_crop_factor` 3.0) the clamp on line 304 fires long
  before the face reaches `guide_size`. **`max_size`, not `guide_size`, is usually the binding
  constraint.**
- **Whatever model is handed to the node is the model that repaints the face.** If a face LoRA is
  not on that wire, the detailer repaints the face as a generic person and destroys the likeness the
  first pass produced.
- The author anticipated this: `<lora:name:weight>` syntax is parsed out of the `wildcard` text box
  (`modules/impact/wildcards.py:845`, pattern `r'<lora:([^>]+)>'`) and applied to the model for the
  detailer pass alone (`process_with_loras`, wildcards.py:919).

## 2.5 The `clip` input does not encode anything
Every use of `clip` in the detailer path was traced. It appears **only** at `core.py:268` and
`core.py:441` (the AnimateDiff twin), both times as an argument to `process_with_loras`. With the
`wildcard` box empty, the `clip` input does nothing at all.

When the box is not empty, the text is encoded inside the node by
`nodes.CLIPTextEncode().encode(clip, prompt)` (wildcards.py, in the `pass3` loop) — a **plain,
single-text encode**. This is why the wildcard box cannot carry a split clip-G / clip-L prompt.

## 2.6 Official ComfyUI documentation: there is none
FaceDetailer is a third-party node. `docs.comfy.org` documents core nodes only. The single
first-party mention found is the Comfy Cloud supported-nodes listing, which confirms the pack runs
there and documents nothing about the node. Recorded here as a negative finding rather than padded
out with third-party pages presented as official.

## 2.7 Community consensus
Two points came back consistently across the sources checked:

- **Upscale first, then FaceDetailer.** The detailer inpaints the region at its current pixel size,
  so detailing before upscaling means the refined pixels are then stretched. Set `guide_size` to the
  target face resolution and leave `force_inpaint` off so faces already larger than `guide_size` are
  skipped rather than needlessly repainted.
- **For character work the face LoRA belongs inside FaceDetailer**, so identity is applied to the
  face region without the LoRA distorting body proportions across the whole frame.

Sources consulted: the Impact Pack repo; the empty detailers tutorial; the Comfy Cloud
supported-nodes page; a node-order guide; two LoRA-plus-FaceDetailer guides; the Next Diffusion
detailer workflow; the CLIPTextEncodeSDXL built-in-node docs; ComfyUI discussion #1047; the
OneTrainer "Additional Embeddings" wiki; ComfyUI issue #3659 on bundled LoRA/embedding files.

---

# PART 3 — clip-L, clip-G AND PIVOTAL, AND WHERE FACEDETAILER SITS AMONG THEM

The user asked where FaceDetailer fits among these three. **It does not sit among them.** They are a
different stage.

## 3.1 The stages, established from ComfyUI's own code
| Stage | What happens | Where |
|---|---|---|
| Tokenizing | a pivotal `embedding:` token is looked up and substituted | `comfy/sd1_clip.py:557, 602` |
| Encoding | clip-L and clip-G each produce their part; one CONDITIONING comes out | `comfy_extras/nodes_clip_sdxl.py:29` (`CLIPTextEncodeSDXL`, inputs `text_g`, `text_l`) |
| Sampling | KSampler uses that CONDITIONING | — |
| Decoding | VAEDecode makes pixels | — |
| **Detailing** | **FaceDetailer repaints one region of those pixels** | after all of the above |

FaceDetailer's `positive` and `negative` inputs are **CONDITIONING**. Everything clip-L, clip-G and
pivotal do is already finished and baked in by the time it receives them.

## 3.2 A pivotal token is physically two vectors
- clip-G tokenizer: `embedding_size=1280, embedding_key='clip_g'` — `comfy/sdxl_clip.py:21` and `:77`
- clip-L tokenizer: `embedding_size=768, embedding_key='clip_l'` — `comfy/sd1_clip.py:487`
- The lookup also understands bundled embeddings via the `bundle_emb.` prefix — `comfy/sd1_clip.py:478-480`

So one pivotal token carries a 768-wide vector for clip-L and a 1280-wide vector for clip-G, and
each tokenizer fetches its own key.

## 3.3 What our LoRAs actually contain
safetensors headers read directly. Both files are identical in shape:

| File | te1 (CLIP-L) | te2 (CLIP-G) | unet | embeddings |
|---|---|---|---|---|
| `susana_head_sdxl.safetensors` | 216 | 579 | 2382 | **0** |
| `susana_head_sdxl_pony.safetensors` | 216 | 579 | 2382 | **0** |

Metadata on both: `modelspec.resolution = 1024x1024`, `ss_base_model_version = sdxl_`,
`ot_revision = 23df383`, trained `2026-09-18`.

**Both text encoders are already trained.** That part of the "separate clip-L / clip-G" item is
done — it simply is not separable at prompt time, because a single LoRA patches both encoders.

**There is no pivotal tuning in this pipeline.** Zero embedding tensors in either file, and
`models/embeddings/` contains only ComfyUI's own placeholder file
(`put_embeddings_or_textual_inversion_concepts_here`, 0 bytes). Pivotal remains an item on the list,
not a thing that exists.

## 3.4 The practical rules that follow
1. Whatever is built at the encoding stage must be wired into **both** the KSampler and the
   FaceDetailer, or the body is painted from one description and the face repainted from another.
2. A clip-G / clip-L split **cannot** be done inside FaceDetailer — its wildcard box uses a plain
   single-text encode (2.5).
3. A pivotal `embedding:` token *would* work in that wildcard box, because the box goes through the
   normal tokenizer. So would `<lora:...>`.
4. Official docs describe `text_g` as the overall scene and `text_l` as the detail but say nothing
   about whether they should differ; the common community practice is identical text in both,
   splitting them only as a deliberate experiment.

---

# PART 4 — THE EXISTING FACEDETAILER IN THE COMPETITION WORKFLOW

Before building anything new, the one we already had was examined, because the 2026-09-04
competition recorded Method 5 scoring **0.044** *with* a FaceDetailer in it.

`Freedom_Face_Competition.json`, node **79**, titled "STEP 4 - repaint the face as her (denoise
slider)". Its inputs traced:

```
image         ← #77 VAEDecode
model         ← #70 FreedomFaceShelf   (LoRA-patched)
clip          ← #70 FreedomFaceShelf
vae           ← #2  CheckpointLoaderSimple
positive      ← #73 CLIPTextEncode  "her, in words (add the LoRA trigger word)"
negative      ← #4  CLIPTextEncode  "what to avoid (Methods 3, 5)"
bbox_detector ← #78 UltralyticsDetectorProvider
```

**That is the author's canonical topology, exactly.** The placement was never wrong.

Its settings were: `guide_size` 512, `guide_size_for` bbox, `max_size` 1024, seed 0/randomize,
steps 20, cfg 6.0, dpmpp_2m / karras, `denoise` 0.45, `feather` 5, `noise_mask` on,
`force_inpaint` on, `bbox_threshold` 0.5, `bbox_dilation` 10, `bbox_crop_factor` 3.0, SAM hints at
defaults, `drop_size` 10, **`wildcard` empty**, `cycle` 1.

Running those through the formula in 2.4 against a face the size measured on 2026-09-18
(116 × 194 px):

```
crop region      = 3.0 × bbox          ≈ 348 × 582
upscale wanted   = 512 / 116           ≈ 4.4×     → crop would become ~1531 × 2561
max_size 1024 clamps: 1024 / 2561      ≈ 0.40     → upscale ≈ 1.76×
face actually arrives at the sampler   ≈ 204 × 341 px
```

So the face was repainted at roughly 200 px against a LoRA trained at 1024 — a fivefold linear
shortfall. **This is flagged as arithmetic derived from the author's formula, not as a statement any
document makes, and it has not been separately confirmed by re-running that competition.**

---

# PART 5 — WHAT WAS BUILT INTO v05

## 5.1 The user's decision
Asked how to build it, the user answered **(b) with an on/off switch**, adding *"but the default is
one, make sure there is a decription in middle school language for adults."* So: switch present,
default ON, plain-language note included.

## 5.2 Nodes added
| id | type | title |
|---|---|---|
| 33 | `UltralyticsDetectorProvider` | STEP 11a - Find her face |
| 34 | `FaceDetailer` | STEP 11b - Repaint the face as her |
| 35 | `PrimitiveBoolean` | STEP 11 SWITCH - Repaint her face (true = ON) |
| 36 | `ImpactConditionalBranch` | STEP 11c - ON = repainted / OFF = as painted |
| 37 | `MarkdownNote` | STEP 11 - what the repaint does |

## 5.3 Links added (67-76) and rewired (37, 42)
```
67: #8  VAEDecode.IMAGE          -> #34 FaceDetailer.image
68: #3  FreedomLoraStack.model   -> #34 FaceDetailer.model      (her LoRA is on this wire)
69: #3  FreedomLoraStack.clip    -> #34 FaceDetailer.clip
70: #1  CheckpointLoaderSimple.VAE -> #34 FaceDetailer.vae
71: #10 PCLazyTextEncode.COND    -> #34 FaceDetailer.positive   (same as KSampler positive)
72: #5  CLIPTextEncode.COND      -> #34 FaceDetailer.negative   (same as KSampler negative)
73: #33 UltralyticsDetector      -> #34 FaceDetailer.bbox_detector
74: #34 FaceDetailer.IMAGE       -> #36 branch.tt_value   (the ON side)
75: #8  VAEDecode.IMAGE          -> #36 branch.ff_value   (the OFF side)
76: #35 PrimitiveBoolean.BOOLEAN -> #36 branch.cond

37: was #8 -> #9  FreedomPreviewPick.images   now #36 -> #9
42: was #8 -> #11 SaveImage.images            now #36 -> #11
```

`sam_model_opt`, `segm_detector_opt` and `detailer_hook` are left unconnected (no models on disk).

## 5.4 Why a lazy branch rather than a plain image switch
`ImpactConditionalBranch` declares `"lazy": True` on both `tt_value` and `ff_value` and implements
`check_lazy_status` (`modules/impact/logics.py:63-89`). That means the unselected side is **never
built**, so OFF genuinely skips the detailing rather than computing it and discarding the result.
This is the same mechanism proven on `FreedomFaceRouter` earlier in this session. A switch that
still ran the detailer would have looked like an off switch without being one.

## 5.5 Settings set on node 34, and why
| Widget | Value | Reason |
|---|---|---|
| `guide_size` | 1024 | the resolution the LoRA was trained at (`modelspec.resolution`) |
| `guide_size_for` | bbox | scale is measured against the face box, not the crop |
| `max_size` | 2048 | the author's 1024 clamps before the face reaches guide_size (PART 4) |
| `seed` / control | 0 / randomize | — |
| `steps` | 26 | copied from STEP 10 KSampler |
| `cfg` | 6 | copied from STEP 10 KSampler |
| `sampler_name` / `scheduler` | dpmpp_2m / karras | copied from STEP 10 KSampler |
| `denoise` | 0.45 | how much of the existing face may change |
| `feather` | 5 | blend edge |
| `noise_mask` | on | — |
| `force_inpaint` | **off** | skip faces already larger than guide_size (community recommendation, 2.7) |
| `bbox_threshold` | 0.5 | — |
| `bbox_dilation` | 10 | — |
| `bbox_crop_factor` | 2.0 | smaller than the 3.0 default so max_size clamps less aggressively |
| SAM widgets | defaults | unused; no SAM model installed |
| `drop_size` | 10 | — |
| `wildcard` | empty | — |
| `cycle` | 1 | — |

These are starting values, every one adjustable. They were chosen by me, stated openly, and are not
presented as a recommendation the user approved.

## 5.6 Consequences the user was told about before the edit
- The auto-save safety net now stores the **detailed** picture; the un-detailed version is no longer
  written anywhere.
- STEP 9 produces 4 pictures per run, so this adds four extra face passes to every run.

---

# PART 6 — VERIFICATION

Two stages, because "it loads" is not "it works".

## 6.1 Structural validation against the live server — 292/292
A validator was written that pulls the running server's `/object_info` and checks the saved
workflow against it. All 292 assertions passed:

- every node type in the file is known to the server
- every link id referenced by an input exists, and names that same node and slot as its target
- every link's origin node lists that link id on the correct output slot
- every link's carried type is accepted by the target input's declared type
- the intended wiring specifically (5.3), asserted origin by origin
- the switch defaults to `true`
- the detailer's sampler, scheduler, steps and cfg equal the STEP 10 KSampler's
- `bbox/face_yolov8m.pt` is offered by the server's own detector list
- `ImpactConditionalBranch`'s two value inputs report `lazy` on this server

## 6.2 Real execution, ON and OFF
Two runs of the edited graph were submitted **as our own client**, which is the only way ComfyUI
reports per-node `executing` events (established 2026-09-18). One picture, fixed seed 123456789,
output to `output/facedetailer_test/`.

```
SWITCH ON   (#35 = true)
  ... -> #7 KSampler -> #8 VAEDecode -> #34 FaceDetailer -> #36 branch -> #11 SaveImage -> #9 preview
  detector ran: YES    FaceDetailer ran: YES    48.9 s

SWITCH OFF  (#35 = false)
  ... -> #7 KSampler -> #8 VAEDecode -> #36 branch -> #11 SaveImage -> #9 preview
  detector ran: NO     FaceDetailer ran: NO     17.8 s
```

**The off position genuinely skips the work.** 31 seconds of difference, and neither the detector
nor the detailer appears in the execution list.

## 6.3 Pixel comparison of the two outputs
Same seed, so the two images differ only by the detailing.

| Measure | Value |
|---|---|
| pixels differing at all | **5.36%** |
| face box (YOLO, on the OFF image) | 180 × 263 px at (233, 51) = **4.67%** of the 1216 × 832 frame |
| mean change **inside** the face box | **23.7** |
| mean change **everywhere else** | **0.1** |

The repaint is confined to the face, which is what the design requires.

## 6.4 What was NOT verified
**That the repaint improves likeness.** A crude mean-gradient measure of the face region went from
6.77 (off) to 6.29 (on) — very slightly smoother rather than sharper, which at denoise 0.45 is
unsurprising but is certainly not evidence of improvement. No cosine-similarity likeness measurement
was run. Both images were sent to the user to look at. This is recorded as an open question of fact,
not quietly omitted.

---

# PART 7 — DEFECTS FOUND THIS SESSION, INCLUDING MINE

| # | Defect | Where | Resolution |
|---|---|---|---|
| 1 | Widget values shifted by one on FaceDetailer | **my** graph→API converter | ComfyUI's frontend adds a `control_after_generate` widget for any INT named `seed`, which the server's `/object_info` does **not** advertise (`FaceDetailer.seed` spec has no such flag). The converter now applies the rule by name. The workflow file was correct; my tool was wrong. |
| 2 | Presented dial settings the user had not asked for | my reply about node 79 | The user asked where FaceDetailer belongs, not what to set. Withdrawn; placement answered on its own. |
| 3 | PowerShell session-file scan reported hits from stale data | my Chrome check | On a sharing violation the exception skipped the read but `$txt` retained the *previous* file's contents, so matches were attributed to the wrong file. Redone with `FileShare::ReadWrite`. |
| 4 | Python shared-open of locked Chrome files returned nothing | my Chrome check | `_open_osfhandle` path failed for every file; the run's "no ComfyUI found" line was meaningless and was discarded rather than reported as a pass. |
| 5 | `$pid` is a read-only automatic variable | my PowerShell window enumeration | Rewritten in Python. |
| 6 | Heredoc with embedded quoting failed under the Bash tool | my edit script | Written to a file with the Write tool instead. |

---

# PART 8 — THE CHROME TAB CHECK

Requested because CLAUDE.md requires every old ComfyUI tab to be closed before a workflow is
reloaded, or ComfyUI serves a stale cached version.

## 8.1 What was established
- **No process on this machine holds any connection to port 8188.** `Get-NetTCPConnection -RemotePort
  8188 -State Established` returned nothing. A loaded ComfyUI page keeps a WebSocket open and
  reconnects when it drops, so this means **no live ComfyUI page exists**.
- Exactly **two Chrome windows**, one per profile (`Default` = "Person 1", `Profile 1` = "John").
  Their active tabs were a Google search and the "Smart Wizard" site. Neither is ComfyUI.
- Chrome's saved tab-restore records **do** contain ComfyUI addresses — `127.0.0.1:8188`,
  `localhost:8188`, and the Tailscale address with several workflow anchors — in
  `Profile 1/Tabs_...` files last written **2026-09-19 20:31** and **2026-09-15 23:51**. That is a
  record of tabs that *were* open, not tabs that are open now.
- Screen was **unlocked** (no LogonUI process), unlike the previous session.

## 8.2 What could NOT be established
**The background tabs inside those two windows were never read.** Four approaches were tried and all
failed or were out of scope:
1. the Claude-in-Chrome extension only enumerates tabs in its own MCP tab group, not the user's;
2. Chrome's live session files are locked while Chrome runs, and the shared-read attempts failed;
3. window titles expose only each window's *active* tab;
4. the accessibility snapshot returned page content, not the tab strip, for the Chrome windows.

Recorded as unverified. The mitigating fact is that the caching hazard is a *live* tab holding a
workflow in memory, and the port check rules that out — a frozen or discarded background tab holds
no state and reloads from disk.

## 8.3 Side effects of the check, and what was restored
Both Chrome windows were minimized; they were restored with `ShowWindow(SW_RESTORE)` to read their
tab strips. The "Smart Wizard" window was found displaying a **modal session-expiry dialog**
("Your session will expire in 0:56 minutes. Do you need more time? YES / NO") on the user's military
pay / SF1174 site. It was **not** touched — clicking it would be acting on the user's behalf on
their own government session. That window was left visible so the user could answer it; the other
window was re-minimized to the state it was found in.

---

# PART 9 — DECISIONS THE USER MADE THIS SESSION

1. **Drop the five-method competition wiring.** *"Ok. Lets drop the five method."*
2. **Write the session's monitoring into the Monitor Logs** (answered "B").
3. **Drop the live-monitoring question entirely.** *"Drop the live monitor question"* — so no watcher,
   no live feed, and no standing routine that reads every finished run was built. Server reads
   happen only in service of a specific question the user asks.
4. **Build FaceDetailer with an on/off switch, defaulting to ON, with a plain-language description**
   (answered "b" with that qualification).
5. **Drop question 17** (a clarifier about what "this" referred to in "Who built this and why?").

---

# PART 10 — WHAT IS STILL OPEN

| Item | State |
|---|---|
| Does the repaint actually improve likeness? | **Unmeasured.** See 6.4. |
| Background Chrome tabs | **Unread.** See 8.2. |
| Pivotal tuning | **Does not exist** in the pipeline. See 3.3. |
| Separate clip-L / clip-G prompting | Not built. Both encoders *are* trained (3.3); splitting them at prompt time would need `CLIPTextEncodeSDXL` in place of the current encode, feeding both the KSampler and the FaceDetailer. |
| An output image per method | Not built. |
| Committing any of this | **Nothing is committed.** See 1.3. |
| `face_training` moving out of the kobold repo | Still not done; explicitly out of scope on 2026-09-18. |
| 444 `WinError 10054` entries in `comfyui.log` | Still unattributed; noisy but harmless. |
