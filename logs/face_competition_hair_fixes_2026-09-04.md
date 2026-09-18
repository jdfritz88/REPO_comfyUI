# Face Competition — hair fixes for Methods 1 and 4 (repaint + transfer)

**Date:** 2026-09-04
**Branch:** Branch04_improvement
**Trigger:** Methods 1 and 4 are face-only swaps — they keep whatever hair was
already in the pose picture, not Susana's. This session builds the two
competing fixes discussed earlier (repaint, and StableHair transfer), wires
them into the workflow, and tests them for real.

---

## 1. What was built

Two new outputs per method (1 and 4), four total:

- `britany_1_faceswap_hairrepaint` / `britany_1_faceswap_hairtransfer`
- `britany_4_expression_hairrepaint` / `britany_4_expression_hairtransfer`

**New panel field:** `FreedomFaceComp` gains a `hair_reference` output (8th
output, index 7) fed by a new `hair_reference_image` state field. The web
panel gets a "HER REAL HAIR" box for it. Both fixes need this — a clear photo
of Susana's real hair — to work from.

### REPAINT branch (nodes 100-121, 130-141)
Finds the hair region and redraws it guided by the hair reference photo.
- `BBoxDetectorLoader` + `BBoxDetect` + `BBoxListItemSelect` (face_parsing) —
  find her face in the swapped picture using the same `face_yolov8m.pt`
  Method 5 already uses.
- `ImageCropWithBBox` → `FaceParse` (SegFormer face-parsing model,
  `jonathandinu/face-parsing`) → `FaceParsingResultsParser` with every class
  except `hair` set to False — isolates a hair-only mask.
- `MaskInsertWithBBox` puts that mask back at full picture size.
- `IPAdapterAdvanced` (SDXL, `ip-adapter_sdxl_vit-h.safetensors`) guides the
  repaint using the hair reference photo, masked to the hair region only via
  `attn_mask`.
- `VAEEncodeForInpaint` (masked to hair, grow_mask_by 6) → `KSampler`
  (28 steps, denoise 0.85, using bigLust) → `VAEDecode` → `SaveImage`.

### TRANSFER branch (nodes 104-105, 122-125, 142-143, 150-153)
Uses `ComfyUI_StableHair_ll`: makes the swap bald, then transplants her real
hairstyle from the reference photo onto the bald result.
- `LoadStableHairRemoverModel` / `LoadStableHairTransferModel` (shared
  loaders) — SD1.5 base (`v1-5-pruned-emaonly.safetensors`) + StableHair's
  four `.bin` files.
- `ImageScale` (×2 per method) resizes both the swapped image and the hair
  reference photo to a fixed 832×1216 (center crop, not stretch) before they
  reach StableHair — see §3.3 for why this is fixed-size rather than
  dynamically read.
- `ApplyHairRemover` → `ApplyHairTransfer` → `SaveImage`.

### Ordering
Both fixes run **after** all five competition methods finish (chained off
Method 5's `FreedomChainLink`), then M1 repaint → M1 transfer → M4 repaint →
M4 transfer, one at a time — same "never together" discipline as the rest of
the workflow. See §4 for how "one at a time" was actually verified this
session, not just assumed.

---

## 2. New installs (all verified working, none skipped)

| Item | Where | Size |
|---|---|---|
| `ComfyUI_StableHair_ll` | `custom_nodes/` | node package |
| `comfyui_face_parsing` | `custom_nodes/` | node package |
| `diffusers` (pip) | ComfyUI venv | additive only — dry-run confirmed zero version changes to any existing package |
| StableHair models (4 files) | `models/diffusers/StableHair/` | ~6.4 GB |
| `jonathandinu/face-parsing` model | `models/face_parsing/` | ~339 MB |
| `ip-adapter_sdxl_vit-h.safetensors` | `models/ipadapter/` | ~666 MB |

`face_yolov8m.pt` and the SD1.5 checkpoint were already on disk and reused.

**One fix made outside this repo** (in the vendored `comfyui_face_parsing`
clone, not tracked here): its `__init__.py` used `pkg_resources` to
auto-install its own requirements, which no longer exists in the installed
setuptools (84.0.0 dropped it) and crashed the node's import entirely. Since
every real dependency (`opencv-contrib-python`, `torchvision`, `ultralytics`,
`matplotlib`) was already confirmed installed, and the auto-installer's
exact-name check would have additionally tried to pip-install
`opencv-contrib-python-headless` on top of the non-headless version already
in use (a real conflict risk for every other node using `cv2`), that block
was removed rather than patched to use `importlib.metadata`.

---

## 3. Bugs found and fixed, in the order they were hit

### 3.1 `comfyui_face_parsing` failed to import
`ModuleNotFoundError: No module named 'pkg_resources'` at ComfyUI startup —
see the installs section above. Fixed by removing the dead auto-installer
block; confirmed clean import on restart.

### 3.2 Wrong node type names (`BBoxDetectorLoader` etc.)
First headless validation attempt returned
`missing_node_type: class_type null` for node 100. ComfyUI's frontend had
registered every `comfyui_face_parsing` node with a `(FaceParsing)` suffix
(e.g. `BBoxDetectorLoader(FaceParsing)`) to avoid a name collision — verified
directly via `LiteGraph.registered_node_types` in the browser, not guessed.
All nine face-parsing node type strings in the builder were corrected to
include the suffix.

### 3.3 StableHair crash: `tensor a (64) must match tensor b (96)`
First real execution attempt crashed inside StableHair's ControlNet forward
pass. Cause: the hair reference photo (768×768) was being force-stretched
~58% taller to match the pose picture's 768×1216 with `ImageScale`'s
`crop="disabled"`. Fixed by switching to `crop="center"` (verified against
`comfy/utils.py`'s actual crop-then-scale implementation, not assumed) so the
reference gets cropped instead of stretched.

That fix didn't fully hold once a *different* pose picture was used later
(see §3.7) — the real, permanent fix was switching both StableHair inputs to
a fixed, always-8-divisible 832×1216 target instead of trying to dynamically
match whatever the pose picture's native size was.

### 3.4 `IndexError: mask shape [0] does not match tensor [1, 14592, 320]`
Second crash, inside `reference_control.py`'s reference-attention hook.
Traced to the exact line: `hidden_states.shape[0] // 2` floors to 0 when the
running batch is 1, producing an empty mask. Researched properly before
touching anything — confirmed via the **original, published**
`Xiaojiu-z/Stable-Hair` repo that this exact code (including the `//2` bug)
is unmodified from upstream, and that the official demo runs with
`guidance_scale=1.5` (same default used here), which is supposed to make
`do_classifier_free_guidance=True` and double the batch before this code
runs — meaning the crash meant something else was overriding that.

Added temporary diagnostic prints (removed again once the cause was found —
not left in the vendored package) and got a direct answer: `do_cfg=False`,
`steps=1` at runtime, despite `cfg=1.5, steps=20` being set. Root cause,
verified against a fresh `LiteGraph.createNode()` instance: ComfyUI
auto-injects a `control_after_generate` widget after any `seed`-named INT
widget (same convention already used correctly for every KSampler in this
file). The builder's `widgets_values` array for `ApplyHairRemover` /
`ApplyHairTransfer` didn't include a slot for it, so every value after `seed`
shifted down one position — `cfg` landed as `1.0`, which is `≤1.0` and
disables classifier-free guidance, which is what put a batch of 1 into the
buggy code path. Not a StableHair bug in practice — a wiring bug here. Fixed
by adding `"randomize"` in the correct slot, and removing the redundant
socket-style `inputs=[]` declarations for those fields (this file's own
working convention elsewhere is to leave seed/steps/cfg-type fields as pure
widgets, not also declare them as unlinked input sockets).

### 3.5 Stale browser cache during testing (not a real bug)
Several rounds of "the fix isn't working" turned out to be `fetch()` serving
a cached copy of the workflow JSON while iterating in the same tab. Confirmed
by inspecting the actually-loaded node's `properties`/`widgets_values` and
finding them still matching the *pre-fix* file. Fixed by cache-busting every
subsequent fetch (`cache: 'no-store'` + a `?_=timestamp` query param) — no
code in the workflow itself was at fault.

### 3.6 OOM crash running all 5 methods + 4 hair fixes in one queued prompt
The full run (pose = `FanJan.jpg`) crashed the whole ComfyUI process — killed
by the OS for low memory, confirmed via `Get-CimInstance` showing the process
gone and `system_stats` unreachable, not a Python exception (no traceback in
the log). Methods 1-4 had actually completed and saved real files before the
crash; Method 5 (the heaviest combination — FaceDetailer + mesh + LoRA) was
mid-execution when it died. Fixed operationally by restarting ComfyUI fresh
and running Method 5 alone, then the hair fixes alone, in separate queued
prompts instead of one giant combined run.

### 3.7 `height and width have to be divisible by 8 but are 1200 and 1010`
Once pose picture `FanJan.jpg` (1010×1200) was used, the transfer branch
crashed again — 1010 isn't divisible by 8 (`comp_pose_body.png`, used
earlier, happened to be 768×1216, both divisible by 8, which is why this
wasn't caught sooner). The REPAINT branch handled this fine on its own
(ComfyUI's native `VAEEncodeForInpaint` tolerates it); only StableHair's
diffusers pipeline enforces the strict assertion. Permanent fix: both the
swapped image and the hair reference now always get resized to a fixed
832×1216 (`ImageScale`, center crop) before reaching StableHair, regardless
of the pose picture's native size — replacing the earlier dynamic
`ImageGenResolutionFromImage`-based sizing from §3.3, which only fixed the
aspect-ratio mismatch, not the divisibility requirement.

---

## 4. "One at a time" — verified, not assumed

Checked directly against the installed `execution.py`: none of the nodes
involved (`ApplyHairRemover`, `ApplyHairTransfer`, `KSampler`,
`FaceDetailer`, etc.) are `async def` functions, so ComfyUI's executor runs
every one of them fully synchronously — true concurrent execution of two of
them is structurally impossible.

The real risk was memory *residency* overlap (one branch's models still
loaded when the next branch's models get requested), which likely caused the
§3.6 crash. Fixed by running Method 1's hair fixes and Method 4's hair fixes
as two **separate** queued prompts instead of one, with a verification step
between them:
1. Submit Method 1's branches, poll `/history/<id>` until
   `status_str: success, completed: true`.
2. `POST /free {"unload_models": true, "free_memory": true}`.
3. Check `/system_stats` VRAM before and after the free call.
4. Only then submit Method 4's branches.

Result: VRAM was already back to the 2166 MB baseline both times, before and
after the explicit free call — confirming ComfyUI's own cleanup already
releases everything correctly between separate submissions. The `/free` +
verify step is now a confirmed extra safety net on top of that, not a
speculative fix.

---

## 5. Results — compared against Susana's real reference photo, not just "did it run"

Tested on `FanJan.jpg` (a real, identifiable person's photo — used with the
user's explicit confirmation it's cleared for this use).

| Branch | Verdict | Notes |
|---|---|---|
| Method 1 repaint | **Pass** | Black hair matches Susana; a faint blend-seam is visible around the mask edge |
| Method 4 repaint | **Pass** | Same profile as Method 1 |
| Method 1 transfer | **Fail** | Wrong hair color (auburn/brown, not black) and degraded, over-sharpened image quality |
| Method 4 transfer | **Fail** | Same failure pattern |

**Tuning attempt on transfer:** raised `control_strength` 1.0 → 2.5 and
lowered `adapter_strength` 1.0 → 0.8, on the theory that it would anchor the
output more tightly to the original swap's color/lighting. Re-ran and
compared again: the result was visibly *worse* (harsher texture, still wrong
hair color), not better. Reported as a failed tweak rather than claimed as a
fix — repaint is the branch that actually works; transfer needs real rework
(different reference-photo cropping, a different guidance mechanism, or
patching the underlying batch-handling bug) before it's usable, not another
parameter nudge.

**Also confirmed while comparing:** Method 5 (shape tracer) produces a
visible woven-fabric texture artifact across the whole face. This is not new
— it's the previously-documented undertrained-LoRA limitation
(`face_competition_rebuild_2026-09-04.md` §3, Method 5) reappearing, not a
regression from this session's changes.

---

## 6. Files changed this session

- `comfyui_ext/freedom_face_competition/build_face_competition.py` — all new
  node wiring described above.
- `comfyui_ext/freedom_face_competition/nodes.py` — `hair_reference_image`
  state field + `hair_reference` output on `FreedomFaceComp`.
- `comfyui_ext/freedom_face_competition/web/face_competition.js` — "HER REAL
  HAIR" panel box.
- `comfyui_workflows/Freedom_Face_Competition.json` — regenerated from the
  builder script (also written to
  `app_cabinet/comfyui/user/default/workflows/`, outside this repo, which is
  what ComfyUI actually loads at runtime).

---

## 7. Open items (see §8 for what got fixed)

1. **Transfer branch is not usable as-is.** Needs real investigation beyond
   parameter tuning — the wrong-hair-color + degraded-quality pattern held
   across two different settings.
2. **Method 5's texture artifact** — pre-existing, needs a properly-trained
   LoRA (more training photos / more steps), not a workflow change.
3. ~~The repaint branch's visible blend-seam...~~ — fixed, see §8.

---

## 8. Repaint branch failed completely on a new pose photo - root-caused and fixed

**Trigger:** a new pose photo (`stock_laugh_blonde.jpg`, head tilted back,
long hair flowing well past the shoulders) made the repaint branch fail
outright — the result still showed almost entirely the stranger's blonde
hair, the exact complaint that started this whole hair-fix effort.

### 8.1 Diagnosis - looked at the actual mask instead of guessing at sliders

Added a temporary debug tap (`MaskToImage` + `SaveImage` on the hair mask,
nodes 160/161 for Method 1, 162/163 for Method 4) to see what the mask
detection step was actually producing. It showed a thin crescent around only
the very crown of the head — none of the long hair down the sides or past
the shoulders. Confirmed why: `BBoxDetect` finds a **tight face-only** box,
`ImageCropWithBBox` crops to just that box, and `FaceParse` only ever looks
for hair *inside that crop* — any hair below/beside the face box structurally
cannot be found, no matter how good the parsing model is or how the repaint's
own denoise/weight sliders are set.

**Ruled out an alternative hypothesis empirically, not just by reasoning:**
tested running the hair-fix *before* the face swap instead of after (same
mask-finding steps on the raw pose picture, then swap on top of the result) —
the mask came back visually identical (same thin crescent), proving order
doesn't matter; the same tight crop produces the same miss regardless of
which image it runs on. That experimental branch (nodes 170-184) was removed
again after the test — this log is the only remaining record of it.

### 8.2 The real fix - widen the crop, then widen the mask

Two changes to `BBoxDetect`'s widget values (nodes 110 and 130, both
methods) and `VAEEncodeForInpaint`'s (nodes 117 and 137):

- `dilation_ratio`: `0.2` → the node's actual max, `1.0`, with `by_ratio`
  switched `False` → `True` (padding by a ratio of the box's size instead of
  a flat 8px). Verified against the node's real schema (`min: 0, max: 1`) via
  ComfyUI's own `/object_info` after an initial attempt at `1.2` was rejected
  by the server, not guessed from the source alone.
- `grow_mask_by` (VAEEncodeForInpaint): `6` → the node's actual max, `64`
  (an attempt at `100` was likewise rejected by the server: `max: 64`).

Iterated three times, checking the actual output image against Susana's
reference photo after each change rather than trusting the parameter alone:
first pass (crop only) fixed most of the hair but left a visible band of
blonde at the very bottom of the frame; `grow_mask_by` 6→50 shrank that band
substantially; 50→64 (the hard cap) shrank it to a thin sliver. Both limits
are now maxed out — closing the remaining sliver needs a structural change
(e.g. skipping the face-crop step and parsing hair on the whole image
directly), not a parameter, and is left as an open item below.

### 8.3 Testing without a working browser tab

Partway through this, the Chrome tab lost the ability to reach ComfyUI
entirely (showed a real connection-error page; `curl` from the terminal
reached the same server instantly and reliably throughout - isolated to the
browser/extension, not ComfyUI). Rather than keep guessing at browser fixes,
built a small standalone converter
(`scratchpad/workflow_to_prompt.py`, not part of this repo) that reads the
saved workflow JSON and produces the exact API-format prompt dict `/prompt`
expects, using ComfyUI's own `/object_info` for each node's true parameter
order - keyed by name, so it sidesteps the `control_after_generate` /
positional-`widgets_values` trap entirely (the API format needs a value per
parameter *name*, not a position; that frontend-only widget doesn't exist in
the schema at all). Caught and fixed two real bugs in the converter itself
via ComfyUI's own validation errors before trusting its output: `STRING`
inputs were wrongly treated as always-a-link (skipped real widget text
fields like the panel's `state` field and the hair-repaint prompt text), and
an optional "after"-ordering link whose source node was excluded needs to be
dropped rather than left dangling. Verified correct against known-good values
(node 118's `steps`/`cfg`/`denoise`) before using it for real submissions.

### 8.4 Open items (added)

4. **Closing the last sliver of unfixed hair** needs a structural change -
   skip `ImageCropWithBBox` and run `FaceParse` on the whole swapped image
   directly, since both `dilation_ratio` and `grow_mask_by` are now at their
   hard caps.
5. **This fix was applied to both Methods 1 and 4** (same nodes changed in
   both) but only empirically verified on Method 1 so far - Method 4 uses
   the identical mask-finding code path, so it's expected to behave the same,
   but hasn't been separately confirmed against Susana's reference photo.
