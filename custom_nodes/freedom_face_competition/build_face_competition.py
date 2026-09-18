"""Freedom Face Competition workflow - five methods, one at a time, five save files."""
import json

nodes, links, groups = [], [], []
_lid = [0]

# Which method the following N() calls belong to ("1".."5"), or None for
# shared / doc nodes. The web panel bypasses a method by this tag, NOT by which
# group box a node happens to sit inside - group boxes overlap on the canvas.
_M = [None]

def L(a, aslot, b, bslot, typ):
    _lid[0] += 1
    links.append([_lid[0], a, aslot, b, bslot, typ])
    return _lid[0]

def N(nid, typ, pos, size, inputs=None, outputs=None, wv=None, title=None, mode=0, props=None, color=None, bg=None):
    properties = dict(props) if props else {"Node name for S&R": typ}
    if _M[0] is not None:
        properties["freedom_method"] = _M[0]
    n = {"id": nid, "type": typ, "pos": list(pos), "size": list(size), "flags": {}, "order": nid, "mode": mode,
         "inputs": inputs or [], "outputs": outputs or [], "properties": properties}
    if wv is not None: n["widgets_values"] = wv
    if title: n["title"] = title
    if color: n["color"] = color
    if bg: n["bgcolor"] = bg
    nodes.append(n); return n

def note(nid, pos, size, title, text, color="#233", bg="#355"):
    N(nid, "MarkdownNote", pos, size, wv=[text], title=title, color=color, bg=bg)

def IN(name, typ, widget=None):
    d = {"name": name, "type": typ, "link": None}
    if widget: d["widget"] = {"name": widget}
    return d

def OUT(name, typ):
    return {"name": name, "type": typ, "links": [], "slot_index": 0}

def W(a, aslot, b, bname):
    """wire output slot aslot of node a into input named bname of node b"""
    na = next(n for n in nodes if n["id"] == a)
    nb = next(n for n in nodes if n["id"] == b)
    typ = na["outputs"][aslot]["type"]
    bslot = next(i for i, inp in enumerate(nb["inputs"]) if inp["name"] == bname)
    lid = L(a, aslot, b, bslot, typ)
    na["outputs"][aslot]["links"].append(lid)
    nb["inputs"][bslot]["link"] = lid

def group(title, x, y, w, h, color):
    groups.append({"title": title, "bounding": [x, y, w, h], "color": color, "font_size": 22, "flags": {}})

# =========================================================================
# SHARED INPUTS  (left column)
# =========================================================================
group("SHARED - set these once", 20, 40, 640, 1180, "#3f5f9e")

N(1, "FreedomFaceComp", (40, 90), (440, 760),
  inputs=[IN("state", "STRING", "state")],
  outputs=[OUT("pose_image", "IMAGE"), OUT("face_photos", "IMAGE"),
           OUT("expression_image", "IMAGE"), OUT("prompt", "STRING"), OUT("negative", "STRING"),
           OUT("instruction", "STRING"), OUT("driving_image", "IMAGE"), OUT("hair_reference", "IMAGE")],
  wv=["{}"], title="INPUTS + the five skip checkboxes + Run",
  props={"cnr_id": "freedom_face_competition", "Node name for S&R": "FreedomFaceComp"})

N(2, "CheckpointLoaderSimple", (40, 850), (440, 100), wv=["bigLust_v16.safetensors"],
  title="the base picture model (used by Methods 3 and 5)",
  outputs=[OUT("MODEL", "MODEL"), OUT("CLIP", "CLIP"), OUT("VAE", "VAE")])

N(3, "CLIPTextEncode", (40, 990), (440, 110), wv=[""], color="#232", bg="#353",
  title="your words -> picture model  (Methods 3, 5)",
  inputs=[IN("clip", "CLIP"), IN("text", "STRING", "text")],
  outputs=[OUT("CONDITIONING", "CONDITIONING")])
N(4, "CLIPTextEncode", (40, 1120), (440, 90), wv=[""], color="#322", bg="#533",
  title="what to avoid  (Methods 3, 5)",
  inputs=[IN("clip", "CLIP"), IN("text", "STRING", "text")],
  outputs=[OUT("CONDITIONING", "CONDITIONING")])

W(2, 1, 3, "clip"); W(1, 3, 3, "text")
W(2, 1, 4, "clip"); W(1, 4, 4, "text")

# =========================================================================
# METHOD 1 - ReActor face swap
# =========================================================================
_M[0] = "1"
GX = 720
group("METHOD 1  -  FACE SWAP  (highest likeness, face only)", GX-20, -100, 940, 940, "#3f8e5c")

N(190, "FreedomPresetsMethod1", (GX, -80), (400, 300),
  title="PRESETS - save/load every dial and slider in Method 1 at once",
  props={"cnr_id": "freedom_face_competition", "Node name for S&R": "FreedomPresetsMethod1"})

N(6, "ReActorBuildFaceModel", (GX, 120), (380, 150),
  wv=[False, True, "competition_face", "Mean"],
  title="STEP 1  -  average ALL her photos into one face",
  inputs=[IN("images", "IMAGE"), IN("face_models", "FACE_MODEL")],
  outputs=[OUT("FACE_MODEL", "FACE_MODEL")])
N(7, "ReActorOptions", (GX, 290), (380, 210),
  wv=["large-small", "0", "no", "large-small", "0", "no", 1, False],
  title="swap options (leave)", outputs=[OUT("OPTIONS", "OPTIONS")])
N(8, "ReActorFaceBoost", (GX, 520), (380, 210),
  wv=[True, "GPEN-BFR-512.onnx", "Bicubic", 1.0, 0.5, True],
  title="STEP 2  -  restore + upscale the swap crop before paste-back",
  outputs=[OUT("FACE_BOOST", "FACE_BOOST")])
N(10, "ReActorFaceSwapOpt", (GX+420, 120), (400, 340),
  wv=[True, "inswapper_128.onnx", "retinaface_resnet50", "GPEN-BFR-512.onnx", 0.8, 0.5],
  title="STEP 3  -  swap her averaged face onto the pose picture",
  inputs=[IN("input_image", "IMAGE"), IN("source_image", "IMAGE"),
          IN("face_model", "FACE_MODEL"), IN("options", "OPTIONS"),
          IN("face_boost", "FACE_BOOST")],
  outputs=[OUT("SWAPPED_IMAGE", "IMAGE"), OUT("FACE_MODEL", "FACE_MODEL"),
           OUT("ORIGINAL_IMAGE", "IMAGE")])
N(11, "FreedomChainLink", (GX+420, 490), (400, 60),
  title="(ordering - leave it)",
  inputs=[IN("image", "IMAGE"), IN("after", "IMAGE")],
  outputs=[OUT("image", "IMAGE")],
  props={"cnr_id": "freedom_face_competition", "Node name for S&R": "FreedomChainLink"})
N(12, "SaveImage", (GX+420, 570), (400, 60), wv=["britany_1_faceswap"],
  title="SAVE 1",
  inputs=[IN("images", "IMAGE")], outputs=[])

W(1, 1, 6, "images")                                # her photos -> averaged face model
W(1, 0, 10, "input_image")                          # pose picture
W(6, 0, 10, "face_model"); W(7, 0, 10, "options"); W(8, 0, 10, "face_boost")
W(10, 0, 11, "image"); W(11, 0, 12, "images")

note(13, (GX+430, 90), (440, 470), "METHOD 1  -  FACE SWAP",
"""**What it does.** It finds the face already in the pose picture, and molds
her features onto it. It keeps the head angle and the expression that are
already there, because it is reshaping that face, not drawing a new one.

**It works like this:** you have a photo of Britany and a photo of someone
in a pose. It lifts Britany's identity off her photo and presses it onto the
other face, like a mask that follows every crease.

**Step 1.** It reads Britany's face from the folder of photos you chose
(it uses the first clear face it finds).
**Step 2.** It finds the face in the pose picture.
**Step 3.** It swaps them and cleans up the result.

**Nothing to adjust.** This is the hands-off one. If the result looks soft,
that is the method - it works at a small size and then upsizes. The other
methods can look sharper.""", color="#1b3a1b", bg="#20401f")

note(14, (GX, 610), (860, 175), "READ THIS  -  METHOD 1 SWAPS THE FACE ONLY, NEVER THE BODY",
"""This method is a **face swap**. It only changes the face. It cannot change
the body, the hair below the jaw, the clothes, or the figure.

- **Head-only run:** perfect - that is exactly what it does.
- **Head-and-body run:** it will still only swap the face. The body you see
  in the result is the body from the random pose photo, not hers. That is not
  a bug and it cannot be fixed by turning a knob - the tool has no way to
  redraw a body.

For a real head-and-body swap use **Method 2, Method 3, or Method 5**.""",
color="#5a1e1e", bg="#7a2020")

# =========================================================================
# METHOD 2 - Qwen instruction edit
# =========================================================================
_M[0] = "2"
GX = 1620
group("METHOD 2  -  INSTRUCTION EDIT  (type one sentence)", GX-20, 40, 780, 760, "#7a5b2f")

# Follows the official ComfyUI Qwen-Image-Edit-2511 template: AuraFlow model
# sampling (shift 3.1), CFGNorm, FluxKontextImageScale on the input, and
# FluxKontextMultiReferenceLatentMethod on the conditioning. Without these the
# edit collapses into a distorted close-up.
N(20, "UnetLoaderGGUF", (GX, 130), (420, 60), wv=["qwen-image-edit-2511-Q4_K_M.gguf"],
  title="the editing model", outputs=[OUT("MODEL", "MODEL")])
N(21, "CLIPLoader", (GX, 210), (420, 90), wv=["qwen_2.5_vl_7b_fp8_scaled.safetensors", "qwen_image", "default"],
  title="its word-reader", outputs=[OUT("CLIP", "CLIP")])
N(22, "VAELoader", (GX, 330), (420, 60), wv=["qwen_image_vae.safetensors"],
  title="its developer", outputs=[OUT("VAE", "VAE")])
N(31, "ModelSamplingAuraFlow", (GX, 410), (420, 60), wv=[3.1],
  title="Qwen noise schedule (leave it)",
  inputs=[IN("model", "MODEL")], outputs=[OUT("MODEL", "MODEL")])
N(32, "CFGNorm", (GX, 490), (420, 80), wv=[1.0, False],
  title="CFG norm (leave it)",
  inputs=[IN("model", "MODEL"), IN("strength", "FLOAT", "strength"),
          IN("pre_cfg", "BOOLEAN", "pre_cfg")],
  outputs=[OUT("patched_model", "MODEL")])
N(33, "FluxKontextImageScale", (GX, 590), (200, 60),
  title="fit the pose to Qwen",
  inputs=[IN("image", "IMAGE")], outputs=[OUT("IMAGE", "IMAGE")])
N(34, "ImageFromBatch", (GX+220, 590), (200, 90), wv=[0, 1],
  title="one photo of her",
  inputs=[IN("image", "IMAGE"), IN("batch_index", "INT", "batch_index"),
          IN("length", "INT", "length")],
  outputs=[OUT("IMAGE", "IMAGE")])
N(23, "TextEncodeQwenImageEditPlus", (GX, 690), (420, 150), wv=[
  "Replace the woman in image 1 with the person shown in image 2 - her face and "
  "her whole head. Keep image 1's pose, body, clothing, background and lighting "
  "unchanged, and keep the same facial expression. Do not blend the two faces; "
  "the face must be exactly the person in image 2."],
  title="STEP 1  -  the instruction  (image1 = pose, image2 = her)",
  inputs=[IN("clip", "CLIP"), IN("vae", "VAE"), IN("image1", "IMAGE"), IN("image2", "IMAGE"),
          IN("image3", "IMAGE"), IN("prompt", "STRING", "prompt")],
  outputs=[OUT("CONDITIONING", "CONDITIONING")])
N(24, "TextEncodeQwenImageEditPlus", (GX, 850), (420, 90), wv=[""],
  title="what to avoid",
  inputs=[IN("clip", "CLIP"), IN("vae", "VAE"), IN("image1", "IMAGE"), IN("image2", "IMAGE"),
          IN("image3", "IMAGE"), IN("prompt", "STRING", "prompt")],
  outputs=[OUT("CONDITIONING", "CONDITIONING")])
N(35, "FluxKontextMultiReferenceLatentMethod", (GX+440, 690), (300, 60),
  wv=["index_timestep_zero"], title="ref method (leave it)",
  inputs=[IN("conditioning", "CONDITIONING")], outputs=[OUT("CONDITIONING", "CONDITIONING")])
N(36, "FluxKontextMultiReferenceLatentMethod", (GX+440, 770), (300, 60),
  wv=["index_timestep_zero"], title="ref method (leave it)",
  inputs=[IN("conditioning", "CONDITIONING")], outputs=[OUT("CONDITIONING", "CONDITIONING")])
N(25, "VAEEncode", (GX, 950), (200, 60), title="pose -> latent",
  inputs=[IN("pixels", "IMAGE"), IN("vae", "VAE")], outputs=[OUT("LATENT", "LATENT")])
N(26, "KSampler", (GX+220, 950), (300, 260),
  wv=[0, "randomize", 40, 3.0, "euler", "simple", 1.0],
  title="STEP 2  -  do the edit",
  inputs=[IN("model", "MODEL"), IN("positive", "CONDITIONING"), IN("negative", "CONDITIONING"),
          IN("latent_image", "LATENT")],
  outputs=[OUT("LATENT", "LATENT")])
N(27, "VAEDecode", (GX, 1220), (220, 60), title="develop",
  inputs=[IN("samples", "LATENT"), IN("vae", "VAE")], outputs=[OUT("IMAGE", "IMAGE")])
N(28, "FreedomChainLink", (GX+240, 1220), (300, 60), title="(ordering)",
  inputs=[IN("image", "IMAGE"), IN("after", "IMAGE")], outputs=[OUT("image", "IMAGE")],
  props={"cnr_id": "freedom_face_competition", "Node name for S&R": "FreedomChainLink"})
N(29, "SaveImage", (GX, 1300), (400, 60), wv=["britany_2_instruct"], title="SAVE 2",
  inputs=[IN("images", "IMAGE")], outputs=[])

W(20, 0, 31, "model"); W(31, 0, 32, "model")
W(1, 0, 33, "image")                                   # pose -> FluxKontextImageScale
W(1, 1, 34, "image")                                   # her photos -> pick one
W(21, 0, 23, "clip"); W(22, 0, 23, "vae"); W(33, 0, 23, "image1"); W(34, 0, 23, "image2"); W(1, 5, 23, "prompt")   # Method 2 reads its OWN Instruction box, not the shared description
W(21, 0, 24, "clip"); W(22, 0, 24, "vae"); W(33, 0, 24, "image1"); W(34, 0, 24, "image2"); W(1, 4, 24, "prompt")
W(23, 0, 35, "conditioning"); W(24, 0, 36, "conditioning")
W(33, 0, 25, "pixels"); W(22, 0, 25, "vae")
W(32, 0, 26, "model"); W(35, 0, 26, "positive"); W(36, 0, 26, "negative"); W(25, 0, 26, "latent_image")
W(26, 0, 27, "samples"); W(22, 0, 27, "vae")
W(27, 0, 28, "image"); W(11, 0, 28, "after"); W(28, 0, 29, "images")

note(30, (GX+560, 90), (200, 690), "METHOD 2  -  INSTRUCTION EDIT",
"""**What it does.** A newer, larger model that edits a picture from a typed
instruction. You give it the pose picture and a photo of her, and it rebuilds
the face area to be her while keeping the expression and lighting.

**It works like this:** like telling a skilled editor "swap this face for
that one, keep everything else." It re-draws the region rather than pasting.

**Step 1.** Written into STEP 1 already - image1 is the pose, image2 is her.
Change the wording only if you want a different result.
**Step 2.** Press Run. It edits and saves.

**Slow and heavy.** This model is big. In Video/Training mode it fits your
card; in the full stack it will not.""")

# =========================================================================
# METHOD 3 - IPAdapter FaceID
# =========================================================================
_M[0] = "3"
GX, GY = 720, 660
group("METHOD 3  -  IDENTITY FINGERPRINT + HER TRAINED FILE", GX-20, GY, 640, 760, "#5b3f9e")

N(55, "LoraLoaderModelOnly", (GX, GY+70), (400, 110),
  wv=[r"faces\susana_head_body_sdxl.safetensors", 0.7],   # Windows: ComfyUI lists loras with backslashes
  title="STEP 1  -  her trained file  (stacks under the fingerprint; 0 = off)",
  inputs=[IN("model", "MODEL")], outputs=[OUT("MODEL", "MODEL")])
N(40, "IPAdapterUnifiedLoaderFaceID", (GX, GY+200), (400, 120),
  wv=["FACEID PLUS V2", 0.6, "CPU"],
  title="load the FaceID fingerprint tool  (+ its companion LoRA at 0.6)",
  inputs=[IN("model", "MODEL"), IN("ipadapter", "IPADAPTER")],
  outputs=[OUT("MODEL", "MODEL"), OUT("ipadapter", "IPADAPTER")])
N(41, "IPAdapterFaceID", (GX, GY+220), (400, 300),
  wv=[1.0, 1.0, "linear", "average", 0.0, 1.0, "V only"],
  title="STEP 1  -  push her likeness in  (weight slider)",
  inputs=[IN("model", "MODEL"), IN("ipadapter", "IPADAPTER"), IN("image", "IMAGE"),
          IN("image_negative", "IMAGE"), IN("clip_vision", "CLIP_VISION"), IN("insightface", "INSIGHTFACE")],
  outputs=[OUT("MODEL", "MODEL"), OUT("face_image", "IMAGE")])
N(51, "InstantIDModelLoader", (GX+440, GY+320), (300, 60), wv=["ip-adapter.bin"],
  title="InstantID model", outputs=[OUT("INSTANTID", "INSTANTID")])
N(52, "InstantIDFaceAnalysis", (GX+440, GY+400), (300, 60), wv=["CPU"],
  title="InstantID face reader", outputs=[OUT("FACEANALYSIS", "FACEANALYSIS")])
N(53, "ControlNetLoader", (GX+440, GY+480), (300, 60),
  wv=["instantid_diffusion_pytorch_model.safetensors"],
  title="InstantID keypoint guide", outputs=[OUT("CONTROL_NET", "CONTROL_NET")])
N(56, "ImageFromBatch", (GX+440, GY+560), (300, 90), wv=[0, 1],
  title="her - one clear portrait",
  inputs=[IN("image", "IMAGE"), IN("batch_index", "INT", "batch_index"),
          IN("length", "INT", "length")],
  outputs=[OUT("IMAGE", "IMAGE")])
N(54, "ApplyInstantID", (GX+440, GY+660), (300, 200), wv=[0.85, 0.0, 1.0],
  title="STEP 2  -  InstantID identity + keypoints  (weight slider)",
  inputs=[IN("instantid", "INSTANTID"), IN("insightface", "FACEANALYSIS"),
          IN("control_net", "CONTROL_NET"), IN("image", "IMAGE"), IN("model", "MODEL"),
          IN("positive", "CONDITIONING"), IN("negative", "CONDITIONING"),
          IN("image_kps", "IMAGE"), IN("mask", "MASK")],
  outputs=[OUT("MODEL", "MODEL"), OUT("positive", "CONDITIONING"),
           OUT("negative", "CONDITIONING")])
N(42, "OpenposePreprocessor", (GX, GY+530), (400, 90), wv=["disable", "enable", "enable", 1024, "enable"],
  title="read the pose off the pose picture",
  inputs=[IN("image", "IMAGE")], outputs=[OUT("IMAGE", "IMAGE"), OUT("POSE_KEYPOINT", "POSE_KEYPOINT")])
N(43, "ControlNetLoader", (GX, GY+630), (400, 60), wv=["xinsir_controlnet_union_sdxl_promax.safetensors"],
  title="body-pose guide", outputs=[OUT("CONTROL_NET", "CONTROL_NET")])
N(44, "ControlNetApplyAdvanced", (GX+420, GY+70), (300, 180), wv=[0.6, 0.0, 1.0],
  title="STEP 3  -  apply the body pose",
  inputs=[IN("positive", "CONDITIONING"), IN("negative", "CONDITIONING"), IN("control_net", "CONTROL_NET"),
          IN("image", "IMAGE"), IN("vae", "VAE")],
  outputs=[OUT("positive", "CONDITIONING"), OUT("negative", "CONDITIONING")])
N(45, "EmptyLatentImage", (GX+420, GY+270), (300, 100), wv=[832, 1216, 1],
  title="canvas size", outputs=[OUT("LATENT", "LATENT")])
N(46, "KSampler", (GX+420, GY+390), (300, 240), wv=[0, "randomize", 28, 6.5, "dpmpp_2m", "karras", 1.0],
  title="STEP 2  -  make the picture",
  inputs=[IN("model", "MODEL"), IN("positive", "CONDITIONING"), IN("negative", "CONDITIONING"),
          IN("latent_image", "LATENT")],
  outputs=[OUT("LATENT", "LATENT")])
N(47, "VAEDecode", (GX+420, GY+640), (200, 60), title="develop",
  inputs=[IN("samples", "LATENT"), IN("vae", "VAE")], outputs=[OUT("IMAGE", "IMAGE")])
N(48, "FreedomChainLink", (GX, GY+700), (400, 60), title="(ordering)",
  inputs=[IN("image", "IMAGE"), IN("after", "IMAGE")], outputs=[OUT("image", "IMAGE")],
  props={"cnr_id": "freedom_face_competition", "Node name for S&R": "FreedomChainLink"})
N(49, "SaveImage", (GX, GY+770), (400, 60), wv=["britany_3_fingerprint"], title="SAVE 3",
  inputs=[IN("images", "IMAGE")], outputs=[])

W(2, 0, 55, "model"); W(55, 0, 40, "model")        # checkpoint -> her trained file -> FaceID
W(40, 0, 41, "model"); W(40, 1, 41, "ipadapter"); W(1, 1, 41, "image")
W(1, 1, 56, "image")                                # her photos -> portrait pick for InstantID
W(51, 0, 54, "instantid"); W(52, 0, 54, "insightface"); W(53, 0, 54, "control_net")
W(56, 0, 54, "image"); W(41, 0, 54, "model")        # FaceID model -> InstantID
W(3, 0, 54, "positive"); W(4, 0, 54, "negative")    # text -> InstantID conditioning
W(1, 0, 42, "image")
W(54, 1, 44, "positive"); W(54, 2, 44, "negative")  # InstantID conditioning -> body-pose CN
W(43, 0, 44, "control_net"); W(42, 0, 44, "image"); W(2, 2, 44, "vae")
W(54, 0, 46, "model"); W(44, 0, 46, "positive"); W(44, 1, 46, "negative"); W(45, 0, 46, "latent_image")
W(46, 0, 47, "samples"); W(2, 2, 47, "vae")
W(47, 0, 48, "image"); W(28, 0, 48, "after"); W(48, 0, 49, "images")

note(50, (GX+740, GY+70), (300, 700), "METHOD 3  -  IDENTITY FINGERPRINT",
"""**What it does.** It boils several photos of her down to a compact
"fingerprint" of what makes her face hers, then generates a brand-new
picture using that fingerprint plus your words plus the pose.

**It works like this:** instead of copying a face, it teaches the picture
model "this is who to draw" for the length of one job.

**Uses several photos** - the more clear photos of her in the folder, the
stronger the likeness.

**Step 1 - the weight slider.** 1.0 is a firm likeness. If her face looks
stiff or plastic, drop toward 0.7. If it does not look enough like her, raise
toward 1.2.
**Step 2.** Press Run.

**You can also add your trained file** here: load it into the base model box
in the SHARED section - it stacks on top of the fingerprint.""", color="#2a2a3a", bg="#33334a")

# =========================================================================
# METHOD 4 - LivePortrait expression copy
# =========================================================================
_M[0] = "4"
GX, GY = 1620, 860
group("METHOD 4  -  EXPRESSION COPY  (most sliders)", GX-20, GY, 780, 1150, "#7a2f5b")

N(60, "ExpressionEditor", (GX, GY+70), (380, 470),
  wv=[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1.0, 1.0, "All", 1.7],
  title="STEP 1  -  put the expression on her face",
  inputs=[IN("src_image", "IMAGE"), IN("motion_link", "EDITOR_LINK"),
          IN("sample_image", "IMAGE"), IN("add_exp", "EXP_DATA")],
  outputs=[OUT("image", "IMAGE"), OUT("motion_link", "EDITOR_LINK"), OUT("save_exp", "EXP_DATA")])
N(61, "ReActorFaceSwap", (GX+400, GY+70), (360, 340),
  wv=[True, "inswapper_128.onnx", "retinaface_resnet50", "GFPGANv1.4.pth", 1.0, 0.5,
      "no", "no", "0", "0", 1],
  title="STEP 2  -  drop that face onto the pose picture",
  inputs=[IN("input_image", "IMAGE"), IN("source_image", "IMAGE"), IN("face_model", "FACE_MODEL")],
  outputs=[OUT("SWAPPED_IMAGE", "IMAGE"), OUT("FACE_MODEL", "FACE_MODEL"), OUT("ORIGINAL_IMAGE", "IMAGE")])
N(62, "FreedomChainLink", (GX, GY+560), (400, 60), title="(ordering)",
  inputs=[IN("image", "IMAGE"), IN("after", "IMAGE")], outputs=[OUT("image", "IMAGE")],
  props={"cnr_id": "freedom_face_competition", "Node name for S&R": "FreedomChainLink"})
N(63, "SaveImage", (GX, GY+630), (400, 60), wv=["britany_4_expression"], title="SAVE 4",
  inputs=[IN("images", "IMAGE")], outputs=[])

W(1, 1, 60, "src_image")            # her face (first photo)
W(1, 6, 60, "sample_image")         # the DRIVING expression photo (panel) - not the pose picture
W(1, 0, 61, "input_image")          # pose picture
W(60, 0, 61, "source_image")        # her face wearing the expression
W(61, 0, 62, "image"); W(48, 0, 62, "after"); W(62, 0, 63, "images")

note(64, (GX+400, GY+430), (360, 200), "METHOD 4  -  EXPRESSION COPY  (part 1)",
"""**What it does.** It takes a face and physically re-poses its mouth,
eyes, brows and gaze to match another face - without re-drawing it. Then it
places that face on the pose picture.

**It works like this:** imagine gently pushing and pulling the muscles of
her face until they match the expression in another photo.""", color="#3a2a33", bg="#4a3340")

note(65, (GX, GY+700), (760, 260), "METHOD 4  -  the sliders (Step 1)",
"""The **sample_image** on the left is the expression to copy. On "auto" it
is the face in your pose picture. Set the panel to "separate photo" to copy
from a different one, or to "by hand" and use these sliders:

- **aaa / eee / woo** - mouth shapes. `aaa` opens it wide (a yell, an
  o-face). `woo` puckers it. Left = closed, right = extreme.
- **smile** - corners of the mouth. Left = frown, right = big grin.
- **blink / wink** - eyelids. Right = closed. A high `blink` reads as eyes
  rolling back or screwed shut.
- **eyebrow** - left = furrowed/angry, right = raised/surprised.
- **pupil_x / pupil_y** - where the eyes look. 0,0 = straight ahead.
- **rotate_pitch / yaw / roll** - tilt the whole head. Small numbers only;
  big turns break it.
- **sample_ratio** - how hard to copy the sample expression. 1.0 = fully.
  Lower it if her face distorts.

**Known limit:** this method is built for talking-head range. Very extreme
expressions may not fully land - that is why Methods 3 and 5 exist.""",
color="#3a2a33", bg="#4a3340")

note(66, (GX, GY+980), (760, 160), "READ THIS  -  METHOD 4 SWAPS THE FACE ONLY, NEVER THE BODY",
"""Step 2 of this method is the same **face swap** engine as Method 1. It only
changes the face. It cannot change the body, the hair below the jaw, the
clothes, or the figure.

- **Head-only run:** fine - it swaps the face and can also borrow an
  expression from another photo.
- **Head-and-body run:** it will still only swap the face. The body in the
  result is the random pose photo's body, not hers. This cannot be fixed
  with a slider - the tool has no way to redraw a body.

For a real head-and-body swap use **Method 2, Method 3, or Method 5**.""",
color="#5a1e1e", bg="#7a2020")

# =========================================================================
# METHOD 5 - face mesh + controlnet + FaceDetailer + your LoRA
# =========================================================================
# GY sits clear below Method 4's group + notes (which end ~y2010). If this
# group's box overlaps a save/note node of Method 3 or 4, LiteGraph counts
# that node as "inside" and the skip-Method-5 checkbox bypasses it too.
_M[0] = "5"
GX, GY = 720, 2080
group("METHOD 5  -  SHAPE TRACER + YOUR TRAINED FILE  (most hands-on)", GX-20, GY, 1500, 760, "#8e5c3f")

N(70, "FreedomFaceShelf", (GX, GY+40), (400, 300), wv=[0.9, ""],
  title="STEP 1  -  pick her on the Face Shelf  (strength slider)",
  inputs=[IN("model", "MODEL"), IN("clip", "CLIP"),
          IN("strength", "FLOAT", "strength"), IN("selected", "STRING", "selected")],
  outputs=[OUT("model", "MODEL"), OUT("clip", "CLIP"),
           OUT("trigger", "STRING"), OUT("person", "STRING")],
  props={"cnr_id": "freedom_face_shelf", "Node name for S&R": "FreedomFaceShelf"})
N(69, "StringConcatenate", (GX, GY+350), (400, 90), wv=["", "", ", "],
  title="her trigger  +  your words  ->  Method 5 prompt",
  inputs=[IN("string_a", "STRING", "string_a"), IN("string_b", "STRING", "string_b"),
          IN("delimiter", "STRING", "delimiter")],
  outputs=[OUT("STRING", "STRING")])
N(71, "DWPreprocessor", (GX, GY+220), (400, 120), wv=["disable", "enable", "enable", 1024, "yolox_l.onnx", "dw-ll_ucoco_384.onnx", "enable"],
  title="STEP 2  -  trace the pose + face shape",
  inputs=[IN("image", "IMAGE")], outputs=[OUT("IMAGE", "IMAGE"), OUT("POSE_KEYPOINT", "POSE_KEYPOINT")])
N(72, "ControlNetLoader", (GX, GY+360), (400, 60), wv=["xinsir_controlnet_union_sdxl_promax.safetensors"],
  title="the tracer guide", outputs=[OUT("CONTROL_NET", "CONTROL_NET")])
N(73, "CLIPTextEncode", (GX, GY+440), (400, 100), wv=[""], color="#232", bg="#353",
  title="her, in words  (add the LoRA trigger word)",
  inputs=[IN("clip", "CLIP"), IN("text", "STRING", "text")],
  outputs=[OUT("CONDITIONING", "CONDITIONING")])
N(87, "MediaPipe-FaceMeshPreprocessor", (GX, GY+560), (400, 110), wv=[1, 0.5, 512],
  title="STEP 2b  -  dense face mesh",
  inputs=[IN("image", "IMAGE")], outputs=[OUT("IMAGE", "IMAGE")])
N(74, "ControlNetApplyAdvanced", (GX+420, GY+70), (300, 170), wv=[0.5, 0.0, 0.9],
  title="STEP 3a  -  apply the body pose",
  inputs=[IN("positive", "CONDITIONING"), IN("negative", "CONDITIONING"), IN("control_net", "CONTROL_NET"),
          IN("image", "IMAGE"), IN("vae", "VAE")],
  outputs=[OUT("positive", "CONDITIONING"), OUT("negative", "CONDITIONING")])
N(88, "ControlNetApplyAdvanced", (GX+420, GY+250), (300, 170), wv=[0.8, 0.0, 0.9],
  title="STEP 3b  -  apply the dense face mesh",
  inputs=[IN("positive", "CONDITIONING"), IN("negative", "CONDITIONING"), IN("control_net", "CONTROL_NET"),
          IN("image", "IMAGE"), IN("vae", "VAE")],
  outputs=[OUT("positive", "CONDITIONING"), OUT("negative", "CONDITIONING")])
N(75, "VAEEncode", (GX+420, GY+440), (200, 60), title="pose -> latent",
  inputs=[IN("pixels", "IMAGE"), IN("vae", "VAE")], outputs=[OUT("LATENT", "LATENT")])
N(76, "KSampler", (GX+420, GY+520), (300, 240), wv=[0, "randomize", 30, 6.0, "dpmpp_2m", "karras", 0.65],
  title="STEP 4  -  redraw as her  (denoise slider)",
  inputs=[IN("model", "MODEL"), IN("positive", "CONDITIONING"), IN("negative", "CONDITIONING"),
          IN("latent_image", "LATENT")],
  outputs=[OUT("LATENT", "LATENT")])
N(77, "VAEDecode", (GX+420, GY+600), (200, 60), title="develop",
  inputs=[IN("samples", "LATENT"), IN("vae", "VAE")], outputs=[OUT("IMAGE", "IMAGE")])
N(78, "UltralyticsDetectorProvider", (GX+740, GY+70), (300, 90), wv=["bbox/face_yolov8m.pt"],
  title="find the face",
  outputs=[OUT("BBOX_DETECTOR", "BBOX_DETECTOR"), OUT("SEGM_DETECTOR", "SEGM_DETECTOR")])
N(79, "FaceDetailer", (GX+740, GY+180), (380, 520),
  # widget order (Impact Pack): guide_size, guide_size_for(BOOL), max_size, seed,
  # control_after_generate, steps, cfg, sampler, scheduler, denoise, feather,
  # noise_mask(BOOL), force_inpaint(BOOL), bbox_threshold, bbox_dilation,
  # bbox_crop_factor, sam_detection_hint, sam_dilation, sam_threshold,
  # sam_bbox_expansion, sam_mask_hint_threshold,
  # sam_mask_hint_use_negative("False"|"Small"|"Outter"), drop_size, wildcard, cycle
  wv=[512, True, 1024, 0, "randomize", 20, 6.0, "dpmpp_2m", "karras", 0.45, 5, True, True,
      0.5, 10, 3.0, "center-1", 0, 0.93, 0, 0.7, "False", 10, "", 1],
  title="STEP 4  -  repaint the face as her  (denoise slider)",
  inputs=[IN("image", "IMAGE"), IN("model", "MODEL"), IN("clip", "CLIP"), IN("vae", "VAE"),
          IN("positive", "CONDITIONING"), IN("negative", "CONDITIONING"), IN("bbox_detector", "BBOX_DETECTOR")],
  outputs=[OUT("image", "IMAGE"), OUT("cropped_refined", "IMAGE"), OUT("cropped_enhanced_alpha", "IMAGE"),
           OUT("mask", "MASK"), OUT("detailer_pipe", "DETAILER_PIPE"), OUT("cnet_images", "IMAGE")])
N(80, "FreedomChainLink", (GX, GY+620), (400, 60), title="(ordering)",
  inputs=[IN("image", "IMAGE"), IN("after", "IMAGE")], outputs=[OUT("image", "IMAGE")],
  props={"cnr_id": "freedom_face_competition", "Node name for S&R": "FreedomChainLink"})
N(81, "SaveImage", (GX, GY+690), (400, 60), wv=["britany_5_shapetracer"], title="SAVE 5",
  inputs=[IN("images", "IMAGE")], outputs=[])

W(2, 0, 70, "model"); W(2, 1, 70, "clip")
W(70, 2, 69, "string_a"); W(1, 3, 69, "string_b")   # her trigger + the shared prompt
W(1, 0, 71, "image"); W(1, 0, 87, "image")
W(70, 1, 73, "clip"); W(69, 0, 73, "text")
W(73, 0, 74, "positive"); W(4, 0, 74, "negative"); W(72, 0, 74, "control_net"); W(71, 0, 74, "image"); W(2, 2, 74, "vae")
W(74, 0, 88, "positive"); W(74, 1, 88, "negative"); W(72, 0, 88, "control_net"); W(87, 0, 88, "image"); W(2, 2, 88, "vae")
W(1, 0, 75, "pixels"); W(2, 2, 75, "vae")
W(70, 0, 76, "model"); W(88, 0, 76, "positive"); W(88, 1, 76, "negative"); W(75, 0, 76, "latent_image")
W(76, 0, 77, "samples"); W(2, 2, 77, "vae")
W(77, 0, 79, "image"); W(70, 0, 79, "model"); W(70, 1, 79, "clip"); W(2, 2, 79, "vae")
W(73, 0, 79, "positive"); W(4, 0, 79, "negative"); W(78, 0, 79, "bbox_detector")
W(79, 0, 80, "image"); W(62, 0, 80, "after"); W(80, 0, 81, "images")

note(82, (GX+1140, GY+70), (340, 700), "METHOD 5  -  SHAPE TRACER + YOUR FILE",
"""**What it does.** This is the one that uses your trained Britany file.
It traces the pose and the shape of the face off the pose picture as a
guide, redraws the scene following that guide with your trained file making
the person her, then repaints the face patch once more, carefully, as her.

**It works like this:** like tracing paper over the pose, then colouring
inside the lines as Britany.

**Step 1 - the Face Shelf.** The STEP 1 box is the Face Shelf. Click the card
for the person you want - use her **face + body** card here, since this method
redraws the whole scene. Her trigger word is joined to your words
automatically and fed into the "her, in words" box. Strength 0.9 is a good
start; 1.0 if the likeness is weak, 0.75 if her face warps.
**Step 2.** The tracer runs on its own.
**Step 3 - the redraw denoise.** 0.55 keeps the pose and clothing and
redraws enough to change the person. Lower (0.4) keeps more of the original;
higher (0.7) redraws more but can drift from the pose.
**Step 4 - the face repaint denoise.** 0.45 replaces the face with hers
while the expression from the redraw stays. Raise to 0.55 if a trace of the
old face survives; lower to 0.35 if the expression moves.

**Most knobs, most control.** Expect to run this two or three times per
picture, nudging Step 3 and Step 4, before it is clean.""", color="#3a2a1a", bg="#4a3320")

# =========================================================================
# HAIR FIXES for Methods 1 and 4 (both are face-only swaps and keep whatever
# hair was already in the pose picture). Two competing fixes, each applied to
# both methods = four extra outputs. Both need a real photo of her hair -
# the HAIR REFERENCE box on the panel (FreedomFaceComp output 7).
#   REPAINT  - find the hair region (face-parsing), then inpaint it guided by
#              her hair photo (IPAdapter, masked to the hair region only).
#   TRANSFER - StableHair: make the swap bald, then transplant her real
#              hairstyle from the reference photo onto the bald result.
# Runs LAST, after all five methods, chained one-at-a-time like they are.
# =========================================================================
_M[0] = None
GX, GY = 20, 2900
group("HAIR TOOLS - shared loaders (used by both fixes, both methods)", GX-20, GY, 900, 300, "#3f5f9e")

N(100, "BBoxDetectorLoader(FaceParsing)", (GX, GY+40), (380, 60), wv=["bbox/face_yolov8m.pt"],
  title="find her face  (face-parsing's own loader - reuses the file Method 5 uses)",
  outputs=[OUT("BBOX_DETECTOR", "BBOX_DETECTOR")],
  props={"cnr_id": "comfyui_face_parsing", "Node name for S&R": "BBoxDetectorLoader"})
N(101, "FaceParsingModelLoader(FaceParsing)", (GX, GY+120), (380, 60), wv=["cuda"],
  title="the hair/skin/eyes/etc reader",
  outputs=[OUT("FACE_PARSING_MODEL", "FACE_PARSING_MODEL")],
  props={"cnr_id": "comfyui_face_parsing", "Node name for S&R": "FaceParsingModelLoader"})
N(102, "FaceParsingProcessorLoader(FaceParsing)", (GX, GY+200), (380, 60),
  outputs=[OUT("FACE_PARSING_PROCESSOR", "FACE_PARSING_PROCESSOR")],
  props={"cnr_id": "comfyui_face_parsing", "Node name for S&R": "FaceParsingProcessorLoader"})
N(103, "IPAdapterUnifiedLoader", (GX+420, GY+40), (400, 90), wv=["STANDARD (medium strength)"],
  title="load the photo-guidance tool  (for the REPAINT fix)",
  inputs=[IN("model", "MODEL")], outputs=[OUT("model", "MODEL"), OUT("ipadapter", "IPADAPTER")])
N(104, "LoadStableHairRemoverModel", (GX+420, GY+150), (400, 90),
  wv=["v1-5-pruned-emaonly.safetensors", "hair_bald_model.bin", "AUTO"],
  title="StableHair - make the swap bald  (for the TRANSFER fix)",
  outputs=[OUT("BALD_MODEL", "BALD_MODEL")],
  props={"cnr_id": "ComfyUI_StableHair_ll", "Node name for S&R": "LoadStableHairRemoverModel"})
N(105, "LoadStableHairTransferModel", (GX+840, GY+40), (400, 120),
  wv=["v1-5-pruned-emaonly.safetensors", "hair_encoder_model.bin", "hair_adapter_model.bin",
      "hair_controlnet_model.bin", "AUTO"],
  title="StableHair - put her real hair on  (for the TRANSFER fix)",
  outputs=[OUT("HAIR_MODEL", "HAIR_MODEL")],
  props={"cnr_id": "ComfyUI_StableHair_ll", "Node name for S&R": "LoadStableHairTransferModel"})
N(106, "CLIPTextEncode", (GX+840, GY+180), (400, 100),
  wv=["her real natural hair, seamless, matching the lighting and photo style"],
  title="what the repainted hair should look like  (leave it - the mask + photo do the real work)",
  inputs=[IN("clip", "CLIP"), IN("text", "STRING", "text")], outputs=[OUT("CONDITIONING", "CONDITIONING")])
W(2, 0, 103, "model")
W(2, 1, 106, "clip")

note(107, (GX, GY+270), (1220, 90), "READ THIS - the swap picture's size",
"""Both hair fixes need the pose picture's pixel width and height to divide
evenly by 8 (a normal requirement for this kind of model). Most photos
already do. If a fix errors immediately with a shape/size mismatch, re-save
the pose picture at a slightly cropped size that divides by 8 and try again.""",
color="#5a1e1e", bg="#7a2020")

_M[0] = "1"
GX, GY = 20, 3260
group("METHOD 1 HAIR FIXES", GX-20, GY, 1700, 420, "#3f8e5c")
# --- REPAINT ---
N(110, "BBoxDetect(FaceParsing)", (GX, GY+40), (300, 160), wv=[0.3, 8, 1.0, True],
  title="STEP 1 - find her face in the swapped picture",
  inputs=[IN("bbox_detector", "BBOX_DETECTOR"), IN("image", "IMAGE")],
  outputs=[OUT("BBOX_LIST", "BBOX_LIST"), OUT("count", "INT")],
  props={"cnr_id": "comfyui_face_parsing", "Node name for S&R": "BBoxDetect"})
N(111, "BBoxListItemSelect(FaceParsing)", (GX+320, GY+40), (260, 60), wv=[0],
  inputs=[IN("bbox_list", "BBOX_LIST"), IN("index", "INT", "index")], outputs=[OUT("BBOX", "BBOX")],
  props={"cnr_id": "comfyui_face_parsing", "Node name for S&R": "BBoxListItemSelect"})
N(112, "ImageCropWithBBox(FaceParsing)", (GX+600, GY+40), (260, 60),
  inputs=[IN("bbox", "BBOX"), IN("image", "IMAGE")], outputs=[OUT("IMAGE", "IMAGE")],
  props={"cnr_id": "comfyui_face_parsing", "Node name for S&R": "ImageCropWithBBox"})
N(113, "FaceParse(FaceParsing)", (GX+880, GY+40), (260, 90),
  title="STEP 2 - read out every region (skin, eyes, hair, ...)",
  inputs=[IN("model", "FACE_PARSING_MODEL"), IN("processor", "FACE_PARSING_PROCESSOR"), IN("image", "IMAGE")],
  outputs=[OUT("IMAGE", "IMAGE"), OUT("FACE_PARSING_RESULT", "FACE_PARSING_RESULT")],
  props={"cnr_id": "comfyui_face_parsing", "Node name for S&R": "FaceParse"})
N(114, "FaceParsingResultsParser(FaceParsing)", (GX+880, GY+150), (260, 260),
  title="STEP 3 - keep only the hair",
  wv=[False, False, False, False, False, False, False, False, False, False, False, False, False,
      True, False, False, False, False, False],   # background..cloth, hair=True, all else False
  inputs=[IN("result", "FACE_PARSING_RESULT")], outputs=[OUT("MASK", "MASK")],
  props={"cnr_id": "comfyui_face_parsing", "Node name for S&R": "FaceParsingResultsParser"})
N(115, "MaskInsertWithBBox(FaceParsing)", (GX+320, GY+230), (260, 60),
  title="STEP 4 - put the hair mask back at full size",
  inputs=[IN("bbox", "BBOX"), IN("image_src", "IMAGE"), IN("mask", "MASK")], outputs=[OUT("MASK", "MASK")],
  props={"cnr_id": "comfyui_face_parsing", "Node name for S&R": "MaskInsertWithBBox"})
N(160, "MaskToImage", (GX+320, GY+310), (260, 60), title="DEBUG - see the hair mask",
  inputs=[IN("mask", "MASK")], outputs=[OUT("IMAGE", "IMAGE")])
N(161, "SaveImage", (GX+320, GY+380), (260, 60), wv=["debug_hairmask_1"], title="DEBUG SAVE - Method 1 hair mask",
  inputs=[IN("images", "IMAGE")], outputs=[])
W(115, 0, 160, "mask"); W(160, 0, 161, "images")
N(116, "IPAdapterAdvanced", (GX, GY+230), (280, 320),
  title="STEP 5 - guide the repaint with her hair photo  (masked to the hair only)",
  wv=[1.0, "linear", "concat", 0.0, 1.0, "V only"],
  inputs=[IN("model", "MODEL"), IN("ipadapter", "IPADAPTER"), IN("image", "IMAGE"),
          IN("weight", "FLOAT", "weight"), IN("weight_type", "COMBO", "weight_type"),
          IN("combine_embeds", "COMBO", "combine_embeds"), IN("start_at", "FLOAT", "start_at"),
          IN("end_at", "FLOAT", "end_at"), IN("embeds_scaling", "COMBO", "embeds_scaling"),
          IN("image_negative", "IMAGE"), IN("attn_mask", "MASK"), IN("clip_vision", "CLIP_VISION")],
  outputs=[OUT("MODEL", "MODEL")])
N(117, "VAEEncodeForInpaint", (GX+1160, GY+40), (260, 110), wv=[64],
  title="STEP 6 - latent, masked to the hair region",
  inputs=[IN("pixels", "IMAGE"), IN("vae", "VAE"), IN("mask", "MASK"),
          IN("grow_mask_by", "INT", "grow_mask_by")], outputs=[OUT("LATENT", "LATENT")])
N(118, "KSampler", (GX+1160, GY+160), (260, 240), wv=[0, "randomize", 28, 6.0, "dpmpp_2m", "karras", 0.85],
  title="STEP 7 - repaint the hair",
  inputs=[IN("model", "MODEL"), IN("positive", "CONDITIONING"), IN("negative", "CONDITIONING"),
          IN("latent_image", "LATENT")], outputs=[OUT("LATENT", "LATENT")])
N(119, "VAEDecode", (GX+1420, GY+40), (200, 60), title="develop",
  inputs=[IN("samples", "LATENT"), IN("vae", "VAE")], outputs=[OUT("IMAGE", "IMAGE")])
N(120, "FreedomChainLink", (GX+1420, GY+120), (260, 60), title="(ordering)",
  inputs=[IN("image", "IMAGE"), IN("after", "IMAGE")], outputs=[OUT("image", "IMAGE")],
  props={"cnr_id": "freedom_face_competition", "Node name for S&R": "FreedomChainLink"})
N(121, "SaveImage", (GX+1420, GY+200), (260, 60), wv=["britany_1_faceswap_hairrepaint"], title="SAVE 1 - hair repaint",
  inputs=[IN("images", "IMAGE")], outputs=[])

W(100, 0, 110, "bbox_detector"); W(10, 0, 110, "image")
W(110, 0, 111, "bbox_list")
W(111, 0, 112, "bbox"); W(10, 0, 112, "image")
W(101, 0, 113, "model"); W(102, 0, 113, "processor"); W(112, 0, 113, "image")
W(113, 1, 114, "result")
W(111, 0, 115, "bbox"); W(10, 0, 115, "image_src"); W(114, 0, 115, "mask")
W(103, 0, 116, "model"); W(103, 1, 116, "ipadapter"); W(1, 7, 116, "image"); W(115, 0, 116, "attn_mask")
W(10, 0, 117, "pixels"); W(2, 2, 117, "vae"); W(115, 0, 117, "mask")
W(116, 0, 118, "model"); W(106, 0, 118, "positive"); W(4, 0, 118, "negative"); W(117, 0, 118, "latent_image")
W(118, 0, 119, "samples"); W(2, 2, 119, "vae")
W(119, 0, 120, "image"); W(80, 0, 120, "after"); W(120, 0, 121, "images")

# --- TRANSFER ---
N(122, "ApplyHairRemover", (GX+320, GY+270), (280, 130),
  wv=[0, "randomize", 20, 1.5, 1.5],  # seed, control_after_generate, steps, strength, cfg
  title="STEP 1 - make the swap bald",
  inputs=[IN("bald_model", "BALD_MODEL"), IN("images", "IMAGE")],
  outputs=[OUT("IMAGE", "IMAGE")],
  props={"Node name for S&R": "ApplyHairRemover"})
N(123, "ApplyHairTransfer", (GX+620, GY+270), (320, 160),
  wv=[0, "randomize", 20, 1.5, 2.5, 0.8],  # seed, control_after_generate, steps, cfg, control_strength, adapter_strength
  title="STEP 2 - transplant her real hair onto the bald result",
  inputs=[IN("model", "HAIR_MODEL"), IN("images", "IMAGE"), IN("bald_image", "IMAGE")],
  outputs=[OUT("IMAGE", "IMAGE")],
  props={"Node name for S&R": "ApplyHairTransfer"})
N(124, "FreedomChainLink", (GX+960, GY+270), (180, 60), title="(ordering)",
  inputs=[IN("image", "IMAGE"), IN("after", "IMAGE")], outputs=[OUT("image", "IMAGE")],
  props={"cnr_id": "freedom_face_competition", "Node name for S&R": "FreedomChainLink"})
N(125, "SaveImage", (GX+1160, GY+270), (260, 60), wv=["britany_1_faceswap_hairtransfer"], title="SAVE 1 - hair transfer",
  inputs=[IN("images", "IMAGE")], outputs=[])

N(150, "ImageScale", (GX+960, GY+40), (200, 120), wv=["lanczos", 832, 1216, "center"],
  title="StableHair needs 8-divisible, matching-size images - fix the swap picture's size",
  inputs=[IN("image", "IMAGE"), IN("upscale_method", "COMBO", "upscale_method"),
          IN("width", "INT", "width"), IN("height", "INT", "height"), IN("crop", "COMBO", "crop")],
  outputs=[OUT("IMAGE", "IMAGE")])
N(151, "ImageScale", (GX+1160, GY+40), (200, 120), wv=["lanczos", 832, 1216, "center"],
  title="...and her hair photo, to the exact same size",
  inputs=[IN("image", "IMAGE"), IN("upscale_method", "COMBO", "upscale_method"),
          IN("width", "INT", "width"), IN("height", "INT", "height"), IN("crop", "COMBO", "crop")],
  outputs=[OUT("IMAGE", "IMAGE")])
W(10, 0, 150, "image")
W(1, 7, 151, "image")

W(104, 0, 122, "bald_model"); W(150, 0, 122, "images")
W(105, 0, 123, "model"); W(151, 0, 123, "images"); W(122, 0, 123, "bald_image")
W(123, 0, 124, "image"); W(120, 0, 124, "after"); W(124, 0, 125, "images")


_M[0] = "4"
GX, GY = 20, 3720
group("METHOD 4 HAIR FIXES", GX-20, GY, 1700, 420, "#7a2f5b")
N(130, "BBoxDetect(FaceParsing)", (GX, GY+40), (300, 160), wv=[0.3, 8, 1.0, True],
  title="STEP 1 - find her face in the swapped picture",
  inputs=[IN("bbox_detector", "BBOX_DETECTOR"), IN("image", "IMAGE")],
  outputs=[OUT("BBOX_LIST", "BBOX_LIST"), OUT("count", "INT")],
  props={"cnr_id": "comfyui_face_parsing", "Node name for S&R": "BBoxDetect"})
N(131, "BBoxListItemSelect(FaceParsing)", (GX+320, GY+40), (260, 60), wv=[0],
  inputs=[IN("bbox_list", "BBOX_LIST"), IN("index", "INT", "index")], outputs=[OUT("BBOX", "BBOX")],
  props={"cnr_id": "comfyui_face_parsing", "Node name for S&R": "BBoxListItemSelect"})
N(132, "ImageCropWithBBox(FaceParsing)", (GX+600, GY+40), (260, 60),
  inputs=[IN("bbox", "BBOX"), IN("image", "IMAGE")], outputs=[OUT("IMAGE", "IMAGE")],
  props={"cnr_id": "comfyui_face_parsing", "Node name for S&R": "ImageCropWithBBox"})
N(133, "FaceParse(FaceParsing)", (GX+880, GY+40), (260, 90),
  title="STEP 2 - read out every region (skin, eyes, hair, ...)",
  inputs=[IN("model", "FACE_PARSING_MODEL"), IN("processor", "FACE_PARSING_PROCESSOR"), IN("image", "IMAGE")],
  outputs=[OUT("IMAGE", "IMAGE"), OUT("FACE_PARSING_RESULT", "FACE_PARSING_RESULT")],
  props={"cnr_id": "comfyui_face_parsing", "Node name for S&R": "FaceParse"})
N(134, "FaceParsingResultsParser(FaceParsing)", (GX+880, GY+150), (260, 260),
  title="STEP 3 - keep only the hair",
  wv=[False, False, False, False, False, False, False, False, False, False, False, False, False,
      True, False, False, False, False, False],
  inputs=[IN("result", "FACE_PARSING_RESULT")], outputs=[OUT("MASK", "MASK")],
  props={"cnr_id": "comfyui_face_parsing", "Node name for S&R": "FaceParsingResultsParser"})
N(135, "MaskInsertWithBBox(FaceParsing)", (GX+320, GY+230), (260, 60),
  title="STEP 4 - put the hair mask back at full size",
  inputs=[IN("bbox", "BBOX"), IN("image_src", "IMAGE"), IN("mask", "MASK")], outputs=[OUT("MASK", "MASK")],
  props={"cnr_id": "comfyui_face_parsing", "Node name for S&R": "MaskInsertWithBBox"})
N(162, "MaskToImage", (GX+320, GY+310), (260, 60), title="DEBUG - see the hair mask",
  inputs=[IN("mask", "MASK")], outputs=[OUT("IMAGE", "IMAGE")])
N(163, "SaveImage", (GX+320, GY+380), (260, 60), wv=["debug_hairmask_4"], title="DEBUG SAVE - Method 4 hair mask",
  inputs=[IN("images", "IMAGE")], outputs=[])
W(135, 0, 162, "mask"); W(162, 0, 163, "images")
N(136, "IPAdapterAdvanced", (GX, GY+230), (280, 320),
  title="STEP 5 - guide the repaint with her hair photo  (masked to the hair only)",
  wv=[1.0, "linear", "concat", 0.0, 1.0, "V only"],
  inputs=[IN("model", "MODEL"), IN("ipadapter", "IPADAPTER"), IN("image", "IMAGE"),
          IN("weight", "FLOAT", "weight"), IN("weight_type", "COMBO", "weight_type"),
          IN("combine_embeds", "COMBO", "combine_embeds"), IN("start_at", "FLOAT", "start_at"),
          IN("end_at", "FLOAT", "end_at"), IN("embeds_scaling", "COMBO", "embeds_scaling"),
          IN("image_negative", "IMAGE"), IN("attn_mask", "MASK"), IN("clip_vision", "CLIP_VISION")],
  outputs=[OUT("MODEL", "MODEL")])
N(137, "VAEEncodeForInpaint", (GX+1160, GY+40), (260, 110), wv=[64],
  title="STEP 6 - latent, masked to the hair region",
  inputs=[IN("pixels", "IMAGE"), IN("vae", "VAE"), IN("mask", "MASK"),
          IN("grow_mask_by", "INT", "grow_mask_by")], outputs=[OUT("LATENT", "LATENT")])
N(138, "KSampler", (GX+1160, GY+160), (260, 240), wv=[0, "randomize", 28, 6.0, "dpmpp_2m", "karras", 0.85],
  title="STEP 7 - repaint the hair",
  inputs=[IN("model", "MODEL"), IN("positive", "CONDITIONING"), IN("negative", "CONDITIONING"),
          IN("latent_image", "LATENT")], outputs=[OUT("LATENT", "LATENT")])
N(139, "VAEDecode", (GX+1420, GY+40), (200, 60), title="develop",
  inputs=[IN("samples", "LATENT"), IN("vae", "VAE")], outputs=[OUT("IMAGE", "IMAGE")])
N(140, "FreedomChainLink", (GX+1420, GY+120), (260, 60), title="(ordering)",
  inputs=[IN("image", "IMAGE"), IN("after", "IMAGE")], outputs=[OUT("image", "IMAGE")],
  props={"cnr_id": "freedom_face_competition", "Node name for S&R": "FreedomChainLink"})
N(141, "SaveImage", (GX+1420, GY+200), (260, 60), wv=["britany_4_expression_hairrepaint"], title="SAVE 4 - hair repaint",
  inputs=[IN("images", "IMAGE")], outputs=[])

W(100, 0, 130, "bbox_detector"); W(61, 0, 130, "image")
W(130, 0, 131, "bbox_list")
W(131, 0, 132, "bbox"); W(61, 0, 132, "image")
W(101, 0, 133, "model"); W(102, 0, 133, "processor"); W(132, 0, 133, "image")
W(133, 1, 134, "result")
W(131, 0, 135, "bbox"); W(61, 0, 135, "image_src"); W(134, 0, 135, "mask")
W(103, 0, 136, "model"); W(103, 1, 136, "ipadapter"); W(1, 7, 136, "image"); W(135, 0, 136, "attn_mask")
W(61, 0, 137, "pixels"); W(2, 2, 137, "vae"); W(135, 0, 137, "mask")
W(136, 0, 138, "model"); W(106, 0, 138, "positive"); W(4, 0, 138, "negative"); W(137, 0, 138, "latent_image")
W(138, 0, 139, "samples"); W(2, 2, 139, "vae")
W(139, 0, 140, "image"); W(124, 0, 140, "after"); W(140, 0, 141, "images")

N(142, "ApplyHairRemover", (GX+320, GY+270), (280, 130),
  wv=[0, "randomize", 20, 1.5, 1.5],  # seed, control_after_generate, steps, strength, cfg
  title="STEP 1 - make the swap bald",
  inputs=[IN("bald_model", "BALD_MODEL"), IN("images", "IMAGE")],
  outputs=[OUT("IMAGE", "IMAGE")],
  props={"cnr_id": "ComfyUI_StableHair_ll", "Node name for S&R": "ApplyHairRemover"})
N(143, "ApplyHairTransfer", (GX+620, GY+270), (320, 160),
  wv=[0, "randomize", 20, 1.5, 2.5, 0.8],  # seed, control_after_generate, steps, cfg, control_strength, adapter_strength
  title="STEP 2 - transplant her real hair onto the bald result",
  inputs=[IN("model", "HAIR_MODEL"), IN("images", "IMAGE"), IN("bald_image", "IMAGE")],
  outputs=[OUT("IMAGE", "IMAGE")],
  props={"cnr_id": "ComfyUI_StableHair_ll", "Node name for S&R": "ApplyHairTransfer"})
N(144, "FreedomChainLink", (GX+960, GY+270), (180, 60), title="(ordering)",
  inputs=[IN("image", "IMAGE"), IN("after", "IMAGE")], outputs=[OUT("image", "IMAGE")],
  props={"cnr_id": "freedom_face_competition", "Node name for S&R": "FreedomChainLink"})
N(145, "SaveImage", (GX+1160, GY+270), (260, 60), wv=["britany_4_expression_hairtransfer"], title="SAVE 4 - hair transfer",
  inputs=[IN("images", "IMAGE")], outputs=[])

N(152, "ImageScale", (GX+960, GY+40), (200, 120), wv=["lanczos", 832, 1216, "center"],
  title="StableHair needs 8-divisible, matching-size images - fix the swap picture's size",
  inputs=[IN("image", "IMAGE"), IN("upscale_method", "COMBO", "upscale_method"),
          IN("width", "INT", "width"), IN("height", "INT", "height"), IN("crop", "COMBO", "crop")],
  outputs=[OUT("IMAGE", "IMAGE")])
N(153, "ImageScale", (GX+1160, GY+40), (200, 120), wv=["lanczos", 832, 1216, "center"],
  title="...and her hair photo, to the exact same size",
  inputs=[IN("image", "IMAGE"), IN("upscale_method", "COMBO", "upscale_method"),
          IN("width", "INT", "width"), IN("height", "INT", "height"), IN("crop", "COMBO", "crop")],
  outputs=[OUT("IMAGE", "IMAGE")])
W(61, 0, 152, "image")
W(1, 7, 153, "image")

W(104, 0, 142, "bald_model"); W(152, 0, 142, "images")
W(105, 0, 143, "model"); W(153, 0, 143, "images"); W(142, 0, 143, "bald_image")
W(143, 0, 144, "image"); W(140, 0, 144, "after"); W(144, 0, 145, "images")

note(146, (GX, GY-140), (1700, 90), "HAIR FIXES - what they need and when they run",
"""Both fixes need the HAIR REFERENCE photo set on the panel (a clear photo of
her real hair) - without it they run on a blank image and won't look right.
They run last, one at a time, after all five competition methods finish -
same "never together" discipline as the rest of this workflow.""",
color="#1b2a1b", bg="#20331f")

# =========================================================================
# ANNOUNCEMENT  -  the big picture
# =========================================================================
_M[0] = None
note(92, (20, -1240), (1200, 620),
"ANNOUNCEMENT  -  WHAT THIS IS FOR",
"""## The face system

The goal is a shelf of faces that ComfyUI can use. Each face is learned from a
folder of photos of one real person - the **Face Tool** (launcher option 4)
does this. Learning produces small files called LoRAs, **two or more per
person**: one from close-up photos only (sharpest face), one from close-ups
plus full-body shots (also learns her build). You use whichever fits the shot.

What is built and wired now:

1. The **Face Tool** - Seek a person through a photo folder (crops other people
   out, builds a clean training set), then train her LoRAs, with stop/resume.
2. The **Face Shelf** node - every trained LoRA as a thumbnail card (person,
   face vs face + body, model family; three to a row). Click a card and its
   LoRA is loaded onto the model + CLIP and its trigger word comes out.
3. The **Prompt Shelf** node - a working prompt box with a drawer of saved
   prompts. Ships two: put her head on a pose (face-only LoRA), and put her
   head and body on a pose (face + body LoRA). Both hold the face at 100% with
   no blending with the source face; you type the pose and the expression.
   Wire the Face Shelf's trigger into it and `{trigger}` fills in the person.

In **this** workflow, Method 5's STEP 1 box is a live Face Shelf.

## Where THIS workflow fits

This workflow comes **after** the training tool, not before it. Methods 3, 4
and 5 below can each use a trained LoRA, and Method 5 needs one, so this
competition is only worth judging once you have real trained files. Its job is
to answer one question: of the five different ways to put a face plus an
expression onto an existing picture, which one works best on this machine? You
run the same picture through all five, look at the five results, and pick a
winner. That winner becomes the method the "put her onto a pose" prompts will
use.

## What is built now

- **The training tool** - the Face Tool (launcher option 4): Seek a person
  through a photo folder, then train her LoRAs. Method 5's STEP 1 box is a
  live **Face Shelf** - pick a trained face there and its LoRA + trigger are
  wired in for you.
- **The Face Shelf and the Prompt Shelf** nodes, usable in any workflow.

## Still to come

- Krea 2 face training (its own architecture - on hold).
- The five-way judging itself: run a real person through all five, pick the
  winner, make that the default.

## What HAS been tested

All five methods have each been run on their own with stand-in images and they
work. The five of them chained together, and the skip checkboxes in this panel,
have not been tested yet.""",
color="#3a3410", bg="#4a4318")

# =========================================================================
# TOP README
# =========================================================================
note(90, (20, -520), (1200, 520), "READ ME FIRST  -  the five-way face competition",
"""One picture goes in. Five methods each try to put Britany's face on it,
with a chosen expression. Five pictures come out, named `britany_1_...`
through `britany_5_...` in your normal output folder.

## How to run it
1. In the INPUTS box (left): type the **pose image** filename (it must be
   in `ComfyUI/input`), press **Choose folder of her photos**, pick the
   **expression** option, and type your **words**.
2. Method 5 uses the **Face Shelf** in its STEP 1 box - click the person's
   card (her face + body one). Her trigger word is added to your prompt
   automatically.
3. Tick the box on any method you want to **skip**. It stays skipped until
   you untick it.
4. Press **Run the competition**. The un-skipped methods run **one at a
   time, top to bottom** - never together - so your card is never overloaded.
   Watch the five save files appear.

## Which methods use what
- **1 Face swap** - a photo of her. Hands-off.
- **2 Instruction edit** - a photo of her. Type one sentence. Big + slow.
- **3 Identity fingerprint** - several photos of her (+ optionally your
  trained file). Two sliders.
- **4 Expression copy** - a photo of her. The most sliders. Built for
  normal expressions; extreme ones may not fully land.
- **5 Shape tracer** - your trained file. The most hands-on, the most
  control.

## Run this in Training/Video mode
Method 2's model is large. Start the launcher in Video mode (or press `v`)
so the voice apps are off and the card is free. In the full stack this
workflow will crawl.""", color="#1b2a1b", bg="#20331f")

# =========================================================================
wf = {"id": "freedom-face-competition", "revision": 0,
      "last_node_id": 200, "last_link_id": _lid[0],
      "nodes": nodes, "links": links, "groups": groups,
      "config": {}, "extra": {}, "version": 0.4}
for out in ("F:/Apps/freedom_system/REPO_comfyUI/user/default/workflows/Freedom_Face_Competition.json",
            "F:/Apps/freedom_system/REPO_koboldccp_sst_tts_media/comfyui_workflows/Freedom_Face_Competition.json"):
    json.dump(wf, open(out, "w", encoding="utf-8"), indent=2)
    print("wrote", out)
print("nodes", len(nodes), "links", _lid[0], "groups", len(groups))
# unwired required-input check
KNOWN_OPTIONAL = {"after", "face_model", "image_negative", "clip_vision", "insightface", "vae",
                  "motion_link", "add_exp", "sample_image", "image3", "src_image",
                  "sam_model_opt", "segm_detector_opt", "detailer_hook",
                  "options", "face_boost", "face_models", "image_kps", "mask", "ipadapter",
                  "source_image"}
for n in nodes:
    if n["type"] in ("MarkdownNote",):
        continue
    for inp in n["inputs"]:
        if inp.get("link") is None and inp["name"] not in KNOWN_OPTIONAL and "widget" not in inp:
            print("  UNWIRED", n["id"], n["type"], "<-", inp["name"])
