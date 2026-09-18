# Forcing a generated image to look like a specific person — research — 2026-09-10

A research session, no code changed. The question: what is the best way to make
a generated image actually look like Susana. Starting complaint was that the
finished face and face+body LoRAs don't look like her.

The session ended somewhere unexpected — the answer was already in this repo,
measured, a week earlier. Section 6 is the one that matters if you read nothing
else.

Branch: `branch09-comfyui-repo-migration`.

---

## 1. The premise that started it

User's argument: training works by averaging, and averaging is the wrong tool
for likeness. "We use averages in math to find a middle, not to model art;
eventually if you average enough your curve flattens to near zero. In character
art we use character models to reference."

Verdict after research: **the observation is real and documented, the stated
mechanism is only part of it, and the user was more right than the first
pushback allowed.** See section 3 — averaging turned out to be happening
literally, in three separate places, one of which nobody had looked at.

---

## 2. What the pipeline actually does (verified from disk, not inferred)

Read out of `face_training/` and the live OneTrainer install rather than
assumed:

**Captions — every image carries an identical string.**

| set | images | caption | steps |
| --- | --- | --- | --- |
| head | 21 | `ohwxsusana woman, face portrait` | 1,995 (95 epochs) |
| body | 167 | `ohwxsusana woman, full body` | 3,340 (20 epochs) |

Confirmed by reading the `.txt` files directly: 21 of 21 identical, 167 of 167
identical. Step counts match the registry, confirming the pipeline does what it
says.

**Other verified settings** (`face_training/otrain.py`): rank 32, alpha 32,
learning rate 3e-4 CONSTANT, AdamW with weight decay 0.01, batch size 1 with
4-step gradient accumulation, aspect-ratio bucketing on, random horizontal flip
on. **Both text encoders frozen** (`text_encoder.train = False`,
`text_encoder_2.train = False`).

**Masked training: not enabled.** Notable because `otrain.py:165` already
excludes `-masklabel.png` from image counts — the code knows OneTrainer's mask
convention, it just never produces masks.

**Regularization images: none.** A single concept is configured. This rules out
the most commonly-blamed cause of drift toward a class average — worth recording
because the first research thread ranked it suspect #1 before knowing the config.

**Checkpoint mismatch, both families.** The `sdxl` family trains against
`stabilityai/stable-diffusion-xl-base-1.0` but the LoRA is used on
`bigLust_v16`. The `sdxl_pony` family trains against `cyberrealisticPony_v110`
but is used on `lustifyNSFWCheckpoint_v10Krea2`. A LoRA is a set of adjustments
relative to the model they were measured against; applying them to a different
checkpoint loses some likeness in translation.

---

## 3. Where averaging actually happens — three places

This is the part that vindicated the opening premise.

**(a) Photo selection — literal averaging of 512-dimensional points.**
`face_training/identity.py`. Its own docstring: "An identity is an averaged
ArcFace embedding." Line 162 computes `mean = _unit(embeds.mean(axis=0))` over
512-dimensional face embeddings. Line 163's comment: *"refine: drop refs that
pull away from the consensus, re-average."* It averages, discards references
sitting too far from that average, and re-averages — tightening inward.

That centroid then gates the dataset: `identity.py:45` scores every candidate as
a dot product against the mean, and `near_miss.py:281` admits photos by that
score. **Photos where she looks typical pass; photos where she looks distinctive
score lower and are rejected first.** The training set is centralised before
training begins.

Not quantified — the cutoff (~0.30 cosine) is fairly permissive, so the
mechanism is confirmed present but its magnitude was never measured. Open item.

**(b) Training — identical captions force it.**
With every caption identical, the model cannot attribute anything. What is
constant across the set fuses to the trigger token; what varies has to be
explained by the same words and can only be learned as its middle.

**(c) Face swap — `compute_method = Mean`.**
From `logs/face_competition_rebuild_2026-09-04.md`: `ReActorBuildFaceModel`
is run with **compute_method = Mean** over the whole folder of her photos,
producing "one averaged FACE_MODEL."

**(d) And the yardstick itself is an average.** The competition scored outputs
by cosine similarity against the profile's *average*. A genuine, unedited
photograph of her scores **0.75** against it. A real photo of her is only 75%
similar to her own average — which is the user's original point, measured.

---

## 4. What the research found

Four parallel research threads. Evidence grades preserved: (a) paper/controlled,
(b) reproduced community practice, (c) unverified folklore.

**On the averaging theory (a).** Diffusion personalization papers do describe
drift toward "an average facial appearance," but attribute it to the training
objective having *no identity term at all* — it is pure noise reconstruction, and
identity lives in high-frequency detail that barely moves the loss. It is
insensitivity, not arithmetic. Fix by adding identity pressure, not by reducing
variety.

**Corollary that matters (b):** more angle/lighting variety produces a *better*
likeness. The documented failure mode is too many *similar* images. The intuitive
response to the averaging theory — feed it fewer, more uniform photos — would
make things worse.

**Captions — largest measured effect (a).** A 14-configuration controlled SDXL
experiment: captioned sets produced a recognizable subject by epoch 4–5;
uncaptioned needed 9–10 or failed. Rule: caption everything that *varies* so it
factors out, leaving the token carrying identity only. Token position matters —
"photo of skw woman wearing a suit" binds to the woman, "wearing an skw suit"
binds to the suit.

**Masked training (b, and the shipped default is wrong).** Masks are
`<image>-masklabel.png`. **Unmasked Weight defaults to 0.1**; a nine-config sweep
found **0.6–0.7 best**, with low values including the default producing
"anatomically disproportional body." Leave ~64px gap between mask and subject;
caption only what's inside the mask.

**Dataset size (b).** 8–12 closely-cropped face images with varied lighting and
angles, plus a few full-body. HuggingFace used 6–10. Current sets are 21 and 167.

**Rank — counterintuitive (a).** Rank 32 beat rank 64; 64 produced an
"air-brushed appearance with less realistic skin texture." More capacity made it
*more* generic. Current setting is already 32, so capacity is likely not the
bottleneck.

**Steps (a).** images × 120 beat 100× and 75×.

**Optimizer (b).** Prodigy is the consensus pick for SDXL faces. Hard
requirement: **learning rate exactly 1.0** for UNet and text encoders — it is a
multiplier on Prodigy's own estimate, not a step size.

**Loss weighting (b).** min-SNR gamma **5** for SD1.5/SDXL. One head-to-head put
min-SNR first, constant second, debiased estimation worst.

**Architectures.** LyCORIS's own guidelines: **LoHa sacrifices fidelity for
generalization — avoid for character detail**, despite forums recommending it for
characters. **LoKr at low factor (4–8), full dimension** is prescribed for the
exact symptom "does not learn well enough." Full/native training is called
"best" for quality. (IA)³, DyLoRA, GLoRA: explicitly unstudied, no
recommendation.

**Installed OneTrainer (commit `23df383`, 2026-08-19)** — verified against source:
LoKr present with `lokr_decompose_factor` (**default -1**, the
maximum-compression, *lowest*-capacity setting), `lokr_full_matrix` (default
False), `lokr_weight_decompose` (default False — this is DoRA, available **only**
on LoKr, not plain LoRA), `lokr_decompose_both` (default False). Switching to
LoKr without changing these gives the opposite of what the guidelines prescribe.

**Pivotal tuning** — supported via the Additional Embeddings tab plus
`embedding_learning_rate`. Trains a real embedding for the trigger word instead
of leaving it meaningless fragments. Wiki advises training the embedding first so
the LoRA has a stationary target. Mechanism sound; **no primary-source likeness
benchmark found.**

**Runtime methods.** InstantID is SDXL-only, Apache-2.0; drop CFG to 4–5; the
plastic look is largely a base-checkpoint artifact; `image_kps` overrides
keypoints to break repeated poses. IP-Adapter FaceID Plus v2 works on
SDXL/Pony/Illustrious; the main model and its companion LoRA **must** load
together. Stacking a LoRA with FaceID is reported multiplicative, not
conflicting — LoRA 0.7–0.8, FaceID 0.7–0.75, CFG 6.5–7.5.

**Face swap has a hard ceiling.** `inswapper_128` outputs **128×128 pixels** and
the model is frozen and unmaintained. Detail seen afterwards is invented by the
restoration pass. No alternative swapper avoids this — they all share the model.

**Not usable on SDXL:** Arc2Face (SD1.5-only), InfiniteYou (Flux). ConsistentID
has an SDXL variant but no ComfyUI integration.

**Sources contradict each other in three places**, recorded rather than
resolved: regularization images real-photo vs model-generated; alpha = rank vs
rank/2; LoHa-for-characters (forums vs official docs). **And two of the research
threads flatly disagreed on whether a full SDXL fine-tune fits 12GB** — one cited
a documented 10.3GB figure, the other said it will not fit. Unresolved.

---

## 5. Transparent PNG — asked, tested, settled

Question raised: does exporting training images as transparent PNGs remove the
background entirely, leaving "no data to capture"?

**No.** Tested directly in OneTrainer's own venv (PIL 12.3.0) with genuinely
transparent pixels over three different underlying colours:

| file | what the model receives |
| --- | --- |
| transparent over black | **black** |
| transparent over white | **white** |
| transparent over green | **green** |

PIL and torchvision behaved identically — **the alpha channel is discarded and
the hidden RGB values pass straight through as visible colour.** Confirmed in
source: OneTrainer's loader (`mgds/pipelineModules/LoadImage.py`) hard-sets mode
to `RGB` and calls `.convert('RGB')`; there is no alpha branch in that path.

Structural reason: the VAE takes three channels. LayerDiffuse had to build
*separate* encoder/decoder models alongside the frozen VAE precisely because the
latent distribution cannot absorb a fourth channel.

Practical consequence: most background removers zero the hidden pixels, so
transparent regions sit over **black** — meaning you would train on a solid black
background, the most constant thing possible, while your eyes see only a
checkerboard. Worse than a deliberate white background, not better.

Note: [the same question was asked on kohya_ss](https://github.com/bmaltais/kohya_ss/discussions/2367)
in April 2024 and received **zero replies**. It is genuinely undocumented.

---

## 6. The decisive finding — this was already answered and measured

From `logs/face_competition_full_rebuild_and_hair_2026-09-04.md`, the five-method
competition, scored as cosine similarity against the profile average:

**Reference point: a genuine, unedited photograph of her scores ~0.75.**

| # | method | score | note from that log |
| --- | --- | --- | --- |
| 1 | ReActor full stack | **0.753** | "looks like her; face only, full body/clothes kept" |
| 3 | LoRA + FaceID + InstantID | **0.742** | "up from 0.25 before the stack — now clearly her" |
| 4 | LivePortrait + swap | 0.695 | "looks like her; face only" |
| 2 | Qwen, own instruction | -0.002 | "does not look like her" — Q4 identity ceiling |
| 5 | mesh + pose + **trained file** | **0.044** | "does not look like her yet" |

**The conclusion that reframes the whole session:**

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
almost certainly nowhere near 0.75. And method 3's known unfixed defect is
recorded in that log: "framing collapsed to a face close-up (InstantID pulls
toward the face) instead of the intended full body — the body-pose ControlNet
strength needs raising to hold it."

---

## 7. Where this leaves it

The highest-value change is **not** a training change. It is connecting the Face
Shelf pick to a method that already measures at 0.75, rather than to the one that
measures 0.044. Nothing was built this session — this is research only, and that
change was offered but not authorised.

Training improvements remain worth doing for the LoRA's own sake, ranked by
measured effect: vary the captions (largest measured effect, and the current
state is the worst case — 100% identical), cut the dataset toward 8–12 curated
face images, enable masked training at unmasked weight 0.6–0.7, train against the
checkpoint actually used for generation, and consider pivotal tuning to give the
trigger word a real embedding. Architecture changes (LoKr, DoRA) are lower
priority because the rank-32-beats-64 result argues capacity is not the
bottleneck.

---

## 8. Open items

- **Never measured:** how hard the identity centroid filter is actually biting.
  Scoring her 188 kept photos against her own centroid would settle it.
- **Unresolved:** whether a full SDXL fine-tune fits 12GB — two research threads
  disagreed outright.
- **Unretested:** method 5 with the current 1,995/3,340-step files instead of the
  440-step file it was scored with.
- **Known defect, unfixed:** method 3's framing collapses to a face close-up;
  body-pose ControlNet strength needs raising.
- **Unquantified:** whether the checkpoint mismatch (train on base SDXL, generate
  on bigLust) costs meaningful likeness.
