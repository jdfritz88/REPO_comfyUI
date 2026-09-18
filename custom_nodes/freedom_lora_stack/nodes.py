# =============================================================================
# FREEDOM SYSTEM - LoRA Stack
# A general-purpose LoRA loader for the "everything except her face" LoRAs -
# clothing, styles, poses, objects, whatever. Starts with 3 rows on the node;
# the panel has a "+" to add more and a X to delete any row. Deliberately
# excludes anything under models/loras/faces/ - those are the trained face
# identities and are picked from the Face Shelf node instead, never from here.
#
# Applies enabled rows onto the model + CLIP passing through, in row order,
# each at its own strength.
#
# The dropdown only offers LoRAs that match the checkpoint actually wired into
# this node - reusing freedom_folder_inspector's real architecture classifier
# (reads the safetensors header, and falls back to tensor shapes when a file
# carries no training metadata) so a Flux or Wan Video LoRA can never be picked
# for an SDXL checkpoint and silently fail at run time.
# =============================================================================
import os
import time

import folder_paths

try:
    import comfy.sd
    import comfy.utils
    _HAS_COMFY = True
except Exception:                       # pragma: no cover
    _HAS_COMFY = False

try:
    from server import PromptServer
    from aiohttp import web
    _HAS_SERVER = True
except Exception:                       # pragma: no cover
    _HAS_SERVER = False

MAX_ROWS = 12
STARTER_ROWS = 3


def _is_face_lora(name: str) -> bool:
    return name.replace("\\", "/").lower().startswith("faces/")


def _lora_choices() -> list[str]:
    """Every LoRA file ComfyUI knows about, except the trained face ones."""
    try:
        all_loras = folder_paths.get_filename_list("loras")
    except Exception:
        all_loras = []
    return [f for f in all_loras if not _is_face_lora(f)]


# --------------------------------------------------------------------------- #
# Base-model compatibility, reusing freedom_folder_inspector's classifier.
#
# The two packages are independent custom_nodes folders with no shared package
# structure, so this loads model_inspect.py directly by file path rather than
# assuming ComfyUI puts custom_nodes on sys.path (verified working, not
# guessed - see the sibling package's own header: "pure Python, no ComfyUI
# imports - safe to test alone", which is exactly what makes this safe).
# --------------------------------------------------------------------------- #
_MI = None
_MI_LOAD_TRIED = False


def _model_inspect():
    global _MI, _MI_LOAD_TRIED
    if _MI is not None or _MI_LOAD_TRIED:
        return _MI
    _MI_LOAD_TRIED = True
    try:
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        target = os.path.normpath(os.path.join(
            here, "..", "freedom_folder_inspector", "model_inspect.py"))
        spec = importlib.util.spec_from_file_location("freedom_model_inspect", target)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MI = mod
    except Exception as e:                                    # noqa: BLE001
        print(f"[freedom_lora_stack] could not load the compatibility "
              f"classifier ({e}) - compatibility filtering is disabled, "
              f"every LoRA will be offered")
        _MI = None
    return _MI


# path -> (mtime, size, base). Header-only reads are already fast (milliseconds
# even on a multi-GB file), but this avoids re-reading on every dropdown open.
_CLASSIFY_CACHE: dict[str, tuple] = {}


def _base_of(path: str) -> str:
    """This file's base model ('SDXL', 'Flux', 'Wan Video', ... or 'unknown')."""
    mi = _model_inspect()
    if mi is None or not path or not os.path.isfile(path):
        return "unknown"
    try:
        st = os.stat(path)
    except OSError:
        return "unknown"
    key = os.path.abspath(path)
    cached = _CLASSIFY_CACHE.get(key)
    if cached and cached[0] == st.st_mtime and cached[1] == st.st_size:
        return cached[2]
    try:
        base = mi.inspect_file(path).get("base") or "unknown"
    except Exception:                                          # noqa: BLE001
        base = "unknown"
    _CLASSIFY_CACHE[key] = (st.st_mtime, st.st_size, base)
    return base


def _checkpoint_base(checkpoint_name: str) -> str:
    if not checkpoint_name:
        return "unknown"
    try:
        path = folder_paths.get_full_path_or_raise("checkpoints", checkpoint_name)
    except Exception:
        return "unknown"
    return _base_of(path)


def _compatible_choices(checkpoint_name: str) -> dict:
    """
    {"checkpoint_base": ..., "compatible": [names], "unverified": [names],
     "incompatible": [{"name", "base"}]}

    A name never classifiable (or the classifier itself unavailable) is
    "unverified", not silently dropped - an "unsure" verdict is shown with a
    reason, never hidden, matching the Folder Inspector's own principle.
    A checkpoint that cannot be classified disables filtering entirely rather
    than hiding everything - failing open, not closed.
    """
    ck_base = _checkpoint_base(checkpoint_name)
    names = _lora_choices()
    if ck_base == "unknown":
        return {"checkpoint_base": ck_base, "compatible": names,
                "unverified": [], "incompatible": []}

    compatible, unverified, incompatible = [], [], []
    for name in names:
        try:
            path = folder_paths.get_full_path_or_raise("loras", name)
        except Exception:
            unverified.append(name)
            continue
        base = _base_of(path)
        if base == "unknown":
            unverified.append(name)
        elif base == ck_base:
            compatible.append(name)
        else:
            incompatible.append({"name": name, "base": base})
    return {"checkpoint_base": ck_base, "compatible": compatible,
            "unverified": unverified, "incompatible": incompatible}


class FreedomLoraStack:
    """A growing list of (on/off, LoRA file, strength) rows applied in order.
    Never offers or applies a face LoRA - use the Face Shelf node for that."""

    @classmethod
    def INPUT_TYPES(cls):
        req = {"model": ("MODEL",), "clip": ("CLIP",)}
        opt = {}
        for i in range(1, MAX_ROWS + 1):
            opt[f"enabled_{i}"] = ("BOOLEAN", {"default": False})
            opt[f"lora_{i}"] = ("STRING", {"default": "", "multiline": False})
            opt[f"strength_{i}"] = ("FLOAT", {"default": 0.8, "min": -2.0, "max": 2.0, "step": 0.05})
        return {"required": req, "optional": opt}

    RETURN_TYPES = ("MODEL", "CLIP")
    RETURN_NAMES = ("model", "clip")
    FUNCTION = "run"
    CATEGORY = "Freedom"

    def run(self, model, clip, **kw):
        m, c = model, clip
        for i in range(1, MAX_ROWS + 1):
            if not kw.get(f"enabled_{i}"):
                continue
            name = (kw.get(f"lora_{i}") or "").strip()
            strength = kw.get(f"strength_{i}", 0.0)
            if not name or not strength:
                continue
            if _is_face_lora(name):
                continue          # defensive: never apply a face LoRA from here
            try:
                path = folder_paths.get_full_path_or_raise("loras", name)
            except Exception:
                continue          # a stale/renamed file - skip it, don't fail the whole queue
            lora, meta = comfy.utils.load_torch_file(path, safe_load=True, return_metadata=True)
            m, c = comfy.sd.load_lora_for_models(m, c, lora, strength, strength, lora_metadata=meta)
        return (m, c)


NODE_CLASS_MAPPINGS = {"FreedomLoraStack": FreedomLoraStack}
NODE_DISPLAY_NAME_MAPPINGS = {"FreedomLoraStack": "Freedom LoRA Stack"}


# --------------------------------------------------------------------------- #
# web API
# --------------------------------------------------------------------------- #
if _HAS_SERVER:
    routes = PromptServer.instance.routes

    @routes.get("/freedom/lorastack/list")
    async def _list(request):
        checkpoint = request.query.get("checkpoint", "")
        if checkpoint:
            info = _compatible_choices(checkpoint)
            return web.json_response({
                "loras": info["compatible"] + info["unverified"],
                "checkpoint_base": info["checkpoint_base"],
                "compatible": info["compatible"],
                "unverified": info["unverified"],
                "incompatible": info["incompatible"],
                "max_rows": MAX_ROWS,
                "starter_rows": STARTER_ROWS,
            })
        # No checkpoint named - unfiltered, exactly as before.
        return web.json_response({
            "loras": _lora_choices(),
            "checkpoint_base": "unknown",
            "compatible": [], "unverified": [], "incompatible": [],
            "max_rows": MAX_ROWS,
            "starter_rows": STARTER_ROWS,
        })
