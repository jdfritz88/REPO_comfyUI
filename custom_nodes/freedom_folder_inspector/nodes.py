# ==========================================
# FREEDOM SYSTEM - ComfyUI Folder Inspector
# nodes.py  (the ComfyUI nodes + the little web API the panel talks to)
# ==========================================
#
# What you get on the canvas:
#   * "Freedom: Folder Inspector"      - one per model folder. Folder name on top,
#                                        file list on the left, description on the
#                                        right with a green / amber / red banner.
#                                        Drag a file onto another inspector to MOVE
#                                        it there on disk (sidecar notes travel too).
#   * "Freedom: Load Checkpoint (wired)" - takes the inspector's selected file name.
#   * "Freedom: Load LoRA (wired)"       - same idea for LoRAs.
#
# Web API (localhost only, used by web/folder_inspector.js):
#   GET  /freedom/inspector/types
#   GET  /freedom/inspector/list?type=loras
#   GET  /freedom/inspector/describe?type=loras&file=name.safetensors
#   POST /freedom/inspector/move   {"src_type":..., "file":..., "dst_type":...}
#   POST /freedom/inspector/undo

import json
import os
import shutil
import threading
import time

import folder_paths
import nodes as comfy_nodes
from aiohttp import web
from server import PromptServer

from . import model_inspect as MI

FOLDER_TYPES = ["checkpoints", "loras", "vae", "embeddings", "controlnet",
                "upscale_models", "clip", "clip_vision", "diffusion_models", "hypernetworks"]

_cache = {}            # (path, mtime, size) -> report
_cache_lock = threading.Lock()
_last_move = {"src": None, "dst": None, "extras": [], "when": 0}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _dirs_for(folder_type):
    try:
        return [d for d in folder_paths.get_folder_paths(folder_type) if os.path.isdir(d)]
    except Exception:
        return []


def _primary_dir(folder_type):
    dirs = _dirs_for(folder_type)
    # Prefer the Freedom SDXL library (extra_model_paths) over ComfyUI's own empty folder.
    for d in dirs:
        if "freedom_system" in d.replace("\\", "/").lower() and "comfyui" not in d.replace("\\", "/").lower():
            return d
    return dirs[0] if dirs else None


def _inspect_cached(path):
    try:
        st = os.stat(path)
    except OSError as exc:
        return {"file": os.path.basename(path), "kind": "unknown", "error": str(exc), "notes": [],
                "base": "unknown", "size": 0, "size_h": "", "triggers": [], "meta": {}, "sidecars": []}
    key = (path, int(st.st_mtime), st.st_size)
    with _cache_lock:
        hit = _cache.get(key)
    if hit is not None:
        return hit
    rep = MI.inspect_file(path)
    with _cache_lock:
        _cache[key] = rep
    return rep


def _list_folder(folder_type):
    """All model files (with relative sub-paths) across every directory for this type."""
    items = []
    seen = set()
    for base_dir in _dirs_for(folder_type):
        for root, _dirs, files in os.walk(base_dir):
            stems = set(os.path.splitext(f)[0] for f in files if f.lower().endswith(MI.MODEL_EXTS))
            for fn in sorted(files, key=str.lower):
                low = fn.lower()
                stem = os.path.splitext(fn)[0]
                # hide notes/previews that belong to a model, and the "Put X here" placeholders
                if not low.endswith(MI.MODEL_EXTS):
                    if stem in stems or low.startswith("put ") or low.startswith("put_") or low in ("desktop.ini", "thumbs.db"):
                        continue
                    if low.endswith(".civitai.info") and low[:-13] in stems:
                        continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, base_dir).replace("\\", "/")
                if rel in seen:
                    continue
                seen.add(rel)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = 0
                items.append({"rel": rel, "name": fn, "size": size, "size_h": MI.human_size(size),
                              "dir": base_dir, "path": full})
    return items


def _find(folder_type, rel):
    rel = rel.replace("\\", "/")
    for base_dir in _dirs_for(folder_type):
        cand = os.path.normpath(os.path.join(base_dir, rel))
        if os.path.commonpath([os.path.normpath(base_dir), cand]) != os.path.normpath(base_dir):
            continue
        if os.path.isfile(cand):
            return cand
    return None


def _installed_bases():
    """Which base models the user actually has, from checkpoints + diffusion_models."""
    found = {}
    for ft in ("checkpoints", "diffusion_models"):
        for it in _list_folder(ft):
            if not it["name"].lower().endswith(MI.MODEL_EXTS):
                continue
            rep = _inspect_cached(it["path"])
            if rep.get("kind") in ("checkpoints", "diffusion_models"):
                found.setdefault(rep.get("base", "unknown"), []).append(it["name"])
    return found


def _chosen_video_family():
    """The video model the Freedom Video workflow is set to (shared settings
    file owned by the freedom_video_queue node). Falls back to Wan 2.2."""
    cand = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "freedom_video_queue", "freedom_video_settings.json")
    try:
        with open(os.path.abspath(cand), "r", encoding="utf-8") as fh:
            fam = json.load(fh).get("video_family")
            if fam:
                return fam
    except Exception:
        pass
    return "Wan 2.2"


def _video_compat(base):
    """(colour, text) for a video-model LoRA vs the chosen video model, or None
    if `base` is not a video family."""
    if base not in MI.VIDEO_FAMILIES:
        return None
    chosen = _chosen_video_family()
    if base == chosen:
        return "green", "Video LoRA for " + base + " - matches your video model. Good to use."
    wan = base.startswith("Wan") and chosen.startswith("Wan")
    if wan:
        return ("amber",
                "Video LoRA for " + base + ", but your video model is " + chosen
                + ". Wan LoRAs often cross over between 2.1 / 2.2, but not always - "
                "if the motion looks broken, that's why.")
    return ("red",
            "Video LoRA for " + base + " - INCOMPATIBLE with your video model (" + chosen
            + "). Different video engine. It will not load, or will corrupt the clip.")


def _verdict(report, folder_type):
    """Banner colour + text.  green = right folder, red = wrong folder, amber = right folder but caution."""
    kind = report.get("kind", "unknown")
    base = report.get("base", "unknown")
    fit = MI.belongs(kind, folder_type)
    if kind == "not_a_model":
        return "red", "Not a model file. It does not belong in any model folder.", None
    if fit == "unsure":
        return "amber", "Could not identify this file. Leave it here until you know what it is.", None
    if fit == "no":
        target = _primary_dir(kind) or "(no folder set up for " + kind + ")"
        return ("red",
                "WRONG FOLDER - this is a " + _nice_kind(kind) + ". It belongs in '" + kind + "' -> " + target
                + ". Drag it onto the '" + kind + "' inspector to move it.",
                kind)
    # right folder - now check it will actually work with what is installed
    if kind in ("loras", "controlnet", "embeddings", "hypernetworks") and base not in ("unknown", "any", ""):
        vc = _video_compat(base)
        if vc:
            return vc[0], vc[1], None
        bases = _installed_bases()
        if base in bases:
            return ("green",
                    "Correct folder. " + _nice_kind(kind) + " for " + base + " - works with: "
                    + ", ".join(sorted(bases[base])[:4]) + ".",
                    None)
        have = ", ".join(sorted(bases.keys())) or "none"
        return ("amber",
                "Right folder, WRONG BASE MODEL. This " + _nice_kind(kind) + " is made for " + base
                + " and will not work with your " + have + " checkpoints. Get a " + base
                + " model, or find the " + have + " version of this LoRA.",
                None)
    return "green", "Correct folder. " + _nice_kind(kind) + (" for " + base if base not in ("unknown", "any", "") else "") + ".", None


def _nice_kind(kind):
    return {"checkpoints": "full checkpoint", "loras": "LoRA", "vae": "VAE", "embeddings": "embedding",
            "controlnet": "ControlNet", "upscale_models": "upscaler", "clip": "text encoder",
            "clip_vision": "vision encoder", "diffusion_models": "bare diffusion model (painter only)",
            "hypernetworks": "hypernetwork"}.get(kind, kind)


# --------------------------------------------------------------------------
# web API
# --------------------------------------------------------------------------
routes = PromptServer.instance.routes


@routes.get("/freedom/inspector/types")
async def api_types(request):
    out = []
    for ft in FOLDER_TYPES:
        out.append({"type": ft, "dir": _primary_dir(ft), "dirs": _dirs_for(ft), "about": MI.FOLDER_INFO.get(ft, "")})
    return web.json_response(out)


@routes.get("/freedom/inspector/list")
async def api_list(request):
    ft = request.query.get("type", "")
    if ft not in FOLDER_TYPES:
        return web.json_response({"error": "unknown folder type"}, status=400)
    items = _list_folder(ft)
    for it in items:
        if it["name"].lower().endswith(MI.MODEL_EXTS) or it["name"].lower().endswith((".crdownload", ".part", ".tmp")):
            rep = _inspect_cached(it["path"])
            colour, _text, _target = _verdict(rep, ft)
            it["kind"] = rep.get("kind")
            it["base"] = rep.get("base")
            it["colour"] = colour
        else:
            it["kind"] = "other"
            it["base"] = ""
            it["colour"] = "grey"
        it.pop("path", None)
    return web.json_response({"type": ft, "dir": _primary_dir(ft), "about": MI.FOLDER_INFO.get(ft, ""), "items": items})


@routes.get("/freedom/inspector/describe")
async def api_describe(request):
    ft = request.query.get("type", "")
    rel = request.query.get("file", "")
    path = _find(ft, rel) if ft in FOLDER_TYPES else None
    if not path:
        return web.json_response({"error": "file not found"}, status=404)
    rep = dict(_inspect_cached(path))
    colour, text, target = _verdict(rep, ft)
    rep["banner"] = {"colour": colour, "text": text, "move_to": target}
    rep["folder_type"] = ft
    rep["rel"] = rel
    rep["about_folder"] = MI.FOLDER_INFO.get(ft, "")
    if rep.get("kind") in MI.FOLDER_INFO:
        rep["about_kind"] = MI.FOLDER_INFO[rep["kind"]]
    return web.json_response(rep)


@routes.post("/freedom/inspector/move")
async def api_move(request):
    body = await request.json()
    src_type = body.get("src_type", "")
    dst_type = body.get("dst_type", "")
    rel = body.get("file", "")
    if src_type not in FOLDER_TYPES or dst_type not in FOLDER_TYPES:
        return web.json_response({"ok": False, "error": "unknown folder type"}, status=400)
    if src_type == dst_type:
        return web.json_response({"ok": False, "error": "already in that folder"})
    src = _find(src_type, rel)
    if not src:
        return web.json_response({"ok": False, "error": "source file not found"}, status=404)
    dst_dir = _primary_dir(dst_type)
    if not dst_dir:
        return web.json_response({"ok": False, "error": "no folder exists for '" + dst_type + "'"}, status=400)
    dst = os.path.join(dst_dir, os.path.basename(src))
    if os.path.exists(dst):
        return web.json_response({"ok": False, "error": "a file with that name already exists in " + dst_dir})
    extras = MI.sidecar_paths(src)
    moved_extras = []
    try:
        shutil.move(src, dst)
        for p in extras:
            target = os.path.join(dst_dir, os.path.basename(p))
            if not os.path.exists(target):
                shutil.move(p, target)
                moved_extras.append((p, target))
    except Exception as exc:
        return web.json_response({"ok": False, "error": "move failed: " + str(exc)}, status=500)
    _last_move.update({"src": src, "dst": dst, "extras": moved_extras, "when": time.time()})
    with _cache_lock:
        _cache.clear()
    _refresh_comfy_lists()
    return web.json_response({"ok": True, "moved_to": dst, "extras": len(moved_extras)})


@routes.post("/freedom/inspector/undo")
async def api_undo(request):
    if not _last_move.get("dst") or not os.path.isfile(_last_move["dst"]):
        return web.json_response({"ok": False, "error": "nothing to undo"})
    try:
        shutil.move(_last_move["dst"], _last_move["src"])
        for orig, moved in _last_move.get("extras", []):
            if os.path.isfile(moved) and not os.path.exists(orig):
                shutil.move(moved, orig)
    except Exception as exc:
        return web.json_response({"ok": False, "error": "undo failed: " + str(exc)}, status=500)
    back = _last_move["src"]
    _last_move.update({"src": None, "dst": None, "extras": [], "when": 0})
    with _cache_lock:
        _cache.clear()
    _refresh_comfy_lists()
    return web.json_response({"ok": True, "restored": back})


def _refresh_comfy_lists():
    """Make ComfyUI's own dropdowns (Load Checkpoint etc.) notice the move."""
    try:
        folder_paths.filename_list_cache.clear()
    except Exception:
        pass


# --------------------------------------------------------------------------
# nodes
# --------------------------------------------------------------------------
class FreedomFolderInspector:
    """Shows one model folder. Pick a file to read about it; drag files between inspectors to move them."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder_type": (FOLDER_TYPES, {"default": "loras"}),
                "selected_file": ("STRING", {"default": "", "multiline": False}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("selected_file",)
    FUNCTION = "run"
    CATEGORY = "Freedom"
    OUTPUT_NODE = False

    def run(self, folder_type, selected_file):
        return (selected_file,)


class FreedomLoadCheckpointWired:
    """Load Checkpoint, but the file name comes in on a wire (from a Folder Inspector)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"ckpt_name": ("STRING", {"default": "", "forceInput": True})}}

    RETURN_TYPES = ("MODEL", "CLIP", "VAE")
    FUNCTION = "load"
    CATEGORY = "Freedom"

    def load(self, ckpt_name):
        name = (ckpt_name or "").strip().replace("\\", "/")
        if not name:
            raise ValueError("No checkpoint selected - click a file in the checkpoints inspector.")
        path = folder_paths.get_full_path("checkpoints", name)
        if not path:
            raise ValueError("Checkpoint not found in the checkpoints folder: " + name)
        return comfy_nodes.CheckpointLoaderSimple().load_checkpoint(name)


class FreedomLoadLoraWired:
    """LoRA Loader, but the file name comes in on a wire (from a Folder Inspector)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",),
            "clip": ("CLIP",),
            "lora_name": ("STRING", {"default": "", "forceInput": True}),
            "strength_model": ("FLOAT", {"default": 1.0, "min": -20.0, "max": 20.0, "step": 0.01}),
            "strength_clip": ("FLOAT", {"default": 1.0, "min": -20.0, "max": 20.0, "step": 0.01}),
        }}

    RETURN_TYPES = ("MODEL", "CLIP")
    FUNCTION = "load"
    CATEGORY = "Freedom"

    def load(self, model, clip, lora_name, strength_model, strength_clip):
        name = (lora_name or "").strip().replace("\\", "/")
        if not name:
            raise ValueError("No LoRA selected - click a file in the loras inspector.")
        if not folder_paths.get_full_path("loras", name):
            raise ValueError("LoRA not found in the loras folder: " + name)
        return comfy_nodes.LoraLoader().load_lora(model, clip, name, strength_model, strength_clip)


NODE_CLASS_MAPPINGS = {
    "FreedomFolderInspector": FreedomFolderInspector,
    "FreedomLoadCheckpointWired": FreedomLoadCheckpointWired,
    "FreedomLoadLoraWired": FreedomLoadLoraWired,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FreedomFolderInspector": "Freedom: Folder Inspector",
    "FreedomLoadCheckpointWired": "Freedom: Load Checkpoint (wired)",
    "FreedomLoadLoraWired": "Freedom: Load LoRA (wired)",
}
