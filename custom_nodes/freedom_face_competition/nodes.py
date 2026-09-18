# =============================================================================
# FREEDOM SYSTEM - Face Competition controller
# One workflow that runs the same "put her face on this picture" job through
# five methods, one at a time, each with its own save file and a skip checkbox.
#
# This node only holds the SHARED inputs and the skip state. The five method
# groups in the workflow read from it. The web panel (web/face_competition.js)
# draws the five checkboxes and the Run button, and turns a ticked checkbox
# into "bypass that whole group" so the chain skips it.
# =============================================================================
import json
import os
import time

import numpy as np
import torch
from PIL import Image, ImageOps

try:
    from server import PromptServer
    from aiohttp import web
    _HAS_SERVER = True
except Exception:                       # pragma: no cover
    _HAS_SERVER = False

import folder_paths

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, "freedom_face_competition_state.json")

METHODS = [
    ("1_faceswap",    "Face swap (least hands-on)"),
    ("2_instruct",    "Instruction edit (Qwen)"),
    ("3_fingerprint", "Identity fingerprint (IPAdapter FaceID)"),
    ("4_expression",  "Expression copy (LivePortrait)"),
    ("5_shapetracer", "Shape tracer (face mesh + your LoRA)"),
]

DEFAULT_STATE = {
    "prompt": "",                       # scene DESCRIPTION - Methods 3 and 5 only
    "negative": "lowres, blurry, distorted face, extra fingers, watermark, text, deformed",
    "instruction": "",                  # edit INSTRUCTION - Method 2 only
    "expression_mode": "auto",          # auto | photo | sliders
    "pose_image": "",                   # filename in ComfyUI/input
    "expression_image": "",             # filename in ComfyUI/input (used when mode == photo)
    "driving_image": "",                # filename in ComfyUI/input - Method 4 expression source
    "hair_reference_image": "",         # filename in ComfyUI/input - her real hair, for the hair fixes on Methods 1 and 4
    "photo_folder": "",                 # folder of the person's reference photos
    # skip flags - True means "skip this method until unticked"
    **{f"skip_{k}": False for k, _ in METHODS},
}


def load_state():
    s = dict(DEFAULT_STATE)
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as fh:
            s.update(json.load(fh))
    except (OSError, ValueError):
        pass
    return s


def save_state(s):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as fh:
            json.dump(s, fh, indent=2)
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# image helpers
# --------------------------------------------------------------------------- #
def _pil_to_tensor(img):
    img = ImageOps.exif_transpose(img).convert("RGB")
    arr = np.asarray(img).astype(np.float32) / 255.0
    return torch.from_numpy(arr)[None, ]          # (1, H, W, 3)


def _blank(h=512, w=512):
    return torch.zeros((1, h, w, 3), dtype=torch.float32)


def _load_input_image(name):
    if not name:
        return _blank()
    path = name
    if not os.path.isabs(path):
        path = os.path.join(folder_paths.get_input_directory(), name)
    if not os.path.isfile(path):
        return _blank()
    return _pil_to_tensor(Image.open(path))


def _fit_square(pil, side=768, fill=(127, 127, 127)):
    """Resize keeping aspect ratio so the longer side == `side`, then pad to a
    square. No stretching - faces keep their shape (a stretch here breaks the
    face detectors that Methods 1, 3 and 4 rely on)."""
    pil = ImageOps.exif_transpose(pil).convert("RGB")
    w, h = pil.size
    scale = side / max(w, h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    pil = pil.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (side, side), fill)
    canvas.paste(pil, ((side - nw) // 2, (side - nh) // 2))
    return canvas


def _load_folder_batch(folder, limit=12):
    if not folder or not os.path.isdir(folder):
        return _blank()
    exts = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
    files = sorted(f for f in os.listdir(folder) if f.lower().endswith(exts))[:limit]
    if not files:
        return _blank()
    tensors = []
    for f in files:
        try:
            tensors.append(_pil_to_tensor(_fit_square(Image.open(os.path.join(folder, f)))))
        except Exception:
            continue
    return torch.cat(tensors, dim=0) if tensors else _blank()


# --------------------------------------------------------------------------- #
# the node
# --------------------------------------------------------------------------- #
class FreedomFaceComp:
    """Shared inputs + skip state for the five-method face competition."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"state": ("STRING", {"multiline": True, "default": "{}"})}}

    RETURN_TYPES = ("IMAGE", "IMAGE", "IMAGE", "STRING", "STRING", "STRING", "IMAGE", "IMAGE")
    RETURN_NAMES = ("pose_image", "face_photos", "expression_image", "prompt",
                    "negative", "instruction", "driving_image", "hair_reference")
    FUNCTION = "run"
    CATEGORY = "Freedom"

    @classmethod
    def IS_CHANGED(cls, state):
        return time.time()

    def run(self, state):
        s = load_state()
        try:
            live = json.loads(state) if state and state.strip().startswith("{") else {}
            s.update({k: v for k, v in live.items() if k in DEFAULT_STATE})
        except ValueError:
            pass
        save_state(s)

        pose = _load_input_image(s["pose_image"])
        photos = _load_folder_batch(s["photo_folder"])

        if s["expression_mode"] == "photo" and s["expression_image"]:
            expr = _load_input_image(s["expression_image"])
        else:
            expr = pose                                   # "auto" = read it off the pose picture

        # Method 4's expression driver - a separate photo, or fall back to `expr`
        driving = _load_input_image(s["driving_image"]) if s.get("driving_image") else expr

        # her real hair, for the hair-repaint and hair-transfer branches on Methods 1 and 4
        hair_ref = _load_input_image(s["hair_reference_image"])

        return (pose, photos, expr, s["prompt"], s["negative"],
                s.get("instruction", ""), driving, hair_ref)


class FreedomChainLink:
    """Ordering glue. Passes `image` straight through; the optional `after`
    input just forces this method to run after the previous one finished.
    In bypass mode ComfyUI routes `image` (the first IMAGE input) to the
    output, so a skipped method still hands the chain to the next one."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",)},
                "optional": {"after": ("IMAGE",)}}

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "run"
    CATEGORY = "Freedom"

    def run(self, image, after=None):
        return (image,)


class FreedomPresetsMethod1:
    """UI-only control panel - save/load a named snapshot of every widget
    value across every Method 1 node (the face swap + both hair fixes).
    Does nothing at graph-execution time; the panel applies values directly
    to live node widgets via the same JS pattern FreedomFaceComp's skip
    checkboxes use. Not wired to anything else in the workflow."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ()
    FUNCTION = "noop"
    CATEGORY = "Freedom"
    OUTPUT_NODE = True

    def noop(self):
        return ()


NODE_CLASS_MAPPINGS = {
    "FreedomFaceComp": FreedomFaceComp,
    "FreedomChainLink": FreedomChainLink,
    "FreedomPresetsMethod1": FreedomPresetsMethod1,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "FreedomFaceComp": "Freedom Face Competition - inputs",
    "FreedomChainLink": "Freedom Chain Link (ordering)",
    "FreedomPresetsMethod1": "Freedom Presets - Method 1",
}


# --------------------------------------------------------------------------- #
# web API for the panel
# --------------------------------------------------------------------------- #
if _HAS_SERVER:
    routes = PromptServer.instance.routes

    @routes.get("/freedom/facecomp/state")
    async def _get_state(request):
        s = load_state()
        s["_methods"] = METHODS
        return web.json_response(s)

    @routes.post("/freedom/facecomp/state")
    async def _set_state(request):
        body = await request.json()
        s = load_state()
        for k, v in body.items():
            if k in DEFAULT_STATE:
                s[k] = v
        save_state(s)
        return web.json_response({"ok": True, "state": s})

    @routes.post("/freedom/facecomp/browse_folder")
    async def _browse_folder(request):
        import asyncio
        import subprocess
        import sys
        picker = (
            "import tkinter as tk\n"
            "from tkinter import filedialog\n"
            "r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True); r.update()\n"
            "print(filedialog.askdirectory(title='Choose the folder of Britany reference photos') or '')\n"
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", picker,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out, _ = await proc.communicate()
            folder = out.decode().strip()
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)})
        if not folder:
            return web.json_response({"ok": False, "cancelled": True})
        s = load_state()
        s["photo_folder"] = folder
        save_state(s)
        n = len([f for f in os.listdir(folder)
                 if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]) if os.path.isdir(folder) else 0
        return web.json_response({"ok": True, "folder": folder, "count": n})

    @routes.post("/freedom/facecomp/upload")
    async def _upload(request):
        """Save a pasted/loaded pose or expression image into ComfyUI/input."""
        reader = await request.multipart()
        field = await reader.next()
        which = "pose_image"
        data = b""
        while field is not None:
            if field.name in ("which",):
                which = (await field.read()).decode()
            elif field.name in ("file", "image"):
                data = await field.read()
                fname = field.filename or "freedom_facecomp.png"
            field = await reader.next()
        if not data:
            return web.json_response({"ok": False, "error": "no file"})
        safe = "".join(c for c in fname if c.isalnum() or c in "._- ") or "freedom_facecomp.png"
        dest = os.path.join(folder_paths.get_input_directory(), "freedom_" + safe)
        with open(dest, "wb") as fh:
            fh.write(data)
        s = load_state()
        s[which if which in ("pose_image", "expression_image") else "pose_image"] = os.path.basename(dest)
        save_state(s)
        return web.json_response({"ok": True, "name": os.path.basename(dest)})


# --------------------------------------------------------------------------- #
# Method 1 presets - a named snapshot of every widget value across every
# Method 1 node (build_face_competition.py tags each one
# properties.freedom_method == "1"). The panel (web/presets_method1.js) reads
# and writes live node widgets directly; this file only persists the named
# snapshots and which one is currently marked "loaded".
# --------------------------------------------------------------------------- #
PRESETS_M1_PATH = os.path.join(HERE, "freedom_face_competition_presets_method1.json")


def _load_presets_m1():
    if os.path.isfile(PRESETS_M1_PATH):
        try:
            with open(PRESETS_M1_PATH, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and isinstance(data.get("presets"), list):
                data.setdefault("loaded", None)
                return data
        except (OSError, ValueError):
            pass
    return {"loaded": None, "presets": []}


def _save_presets_m1(data):
    os.makedirs(os.path.dirname(PRESETS_M1_PATH), exist_ok=True)
    tmp = PRESETS_M1_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, PRESETS_M1_PATH)


def _unique_preset_name(presets, base):
    names = {p["name"] for p in presets}
    if base not in names:
        return base
    n = 2
    while f"{base} {n}" in names:
        n += 1
    return f"{base} {n}"


if _HAS_SERVER:
    @routes.get("/freedom/presets1/list")
    async def _presets1_list(request):
        return web.json_response(_load_presets_m1())

    @routes.post("/freedom/presets1/save")
    async def _presets1_save(request):
        """Overwrite an existing preset's values (Save Loaded Preset)."""
        body = await request.json()
        name = (body.get("name") or "").strip()
        values = body.get("values") or {}
        if not name:
            return web.json_response({"ok": False, "error": "no name"})
        data = _load_presets_m1()
        for p in data["presets"]:
            if p["name"] == name:
                p["values"] = values
                break
        else:
            data["presets"].append({"name": name, "values": values})
        data["loaded"] = name
        _save_presets_m1(data)
        return web.json_response({"ok": True, **data})

    @routes.post("/freedom/presets1/new")
    async def _presets1_new(request):
        """Create a preset from CURRENT live values under a fresh name."""
        body = await request.json()
        values = body.get("values") or {}
        data = _load_presets_m1()
        name = _unique_preset_name(data["presets"], (body.get("base_name") or "New Preset").strip() or "New Preset")
        data["presets"].append({"name": name, "values": values})
        data["loaded"] = name
        _save_presets_m1(data)
        return web.json_response({"ok": True, "new_name": name, **data})

    @routes.post("/freedom/presets1/duplicate")
    async def _presets1_duplicate(request):
        """Copy a SAVED preset's values under a new "<name> copy" name."""
        body = await request.json()
        name = (body.get("name") or "").strip()
        data = _load_presets_m1()
        src = next((p for p in data["presets"] if p["name"] == name), None)
        if not src:
            return web.json_response({"ok": False, "error": f"no preset named {name!r}"})
        new_name = _unique_preset_name(data["presets"], f"{name} copy")
        data["presets"].append({"name": new_name, "values": json.loads(json.dumps(src["values"]))})
        data["loaded"] = new_name
        _save_presets_m1(data)
        return web.json_response({"ok": True, "new_name": new_name, **data})

    @routes.post("/freedom/presets1/rename")
    async def _presets1_rename(request):
        body = await request.json()
        old_name = (body.get("old_name") or "").strip()
        new_name = (body.get("new_name") or "").strip()
        data = _load_presets_m1()
        if not new_name:
            return web.json_response({"ok": False, "error": "no new name", **data})
        if new_name != old_name and any(p["name"] == new_name for p in data["presets"]):
            return web.json_response({"ok": False, "error": f"{new_name!r} already exists", **data})
        for p in data["presets"]:
            if p["name"] == old_name:
                p["name"] = new_name
                break
        else:
            return web.json_response({"ok": False, "error": f"no preset named {old_name!r}", **data})
        if data["loaded"] == old_name:
            data["loaded"] = new_name
        _save_presets_m1(data)
        return web.json_response({"ok": True, **data})

    @routes.post("/freedom/presets1/load")
    async def _presets1_load(request):
        """Bookkeeping only - marks `name` as loaded. The panel applies the
        preset's values to the live widgets itself; this just persists which
        one to show the green dot next to next time the panel opens."""
        body = await request.json()
        name = (body.get("name") or "").strip()
        data = _load_presets_m1()
        if not any(p["name"] == name for p in data["presets"]):
            return web.json_response({"ok": False, "error": f"no preset named {name!r}", **data})
        data["loaded"] = name
        _save_presets_m1(data)
        return web.json_response({"ok": True, **data})
