# =============================================================================
# FREEDOM SYSTEM - Prompt Shelf
# A working prompt box (positive + negative) with a drawer of clickable saved
# prompts underneath. Click a saved prompt and its text drops into the boxes;
# edit from there. Ships with the two "put her on a pose" templates.
#
# {trigger} anywhere in a box is replaced at run time by the `trigger` input -
# wire the Face Shelf's trigger output into it and the selected person fills in.
#
# Saved prompts live in  comfyui/models/loras/faces/_prompts.json .
# =============================================================================
import json
import os

import folder_paths

try:
    from server import PromptServer
    from aiohttp import web
    _HAS_SERVER = True
except Exception:                       # pragma: no cover
    _HAS_SERVER = False

PROMPTS_FILE = os.path.join(folder_paths.models_dir, "loras", "faces", "_prompts.json")

# The face is held at 100% (trigger first, "same face / same person"); the
# negative fights face-swap look and identity blending. Pose, setting, clothing
# and expression are left for you to type so the base model stays free to place
# them - per current SDXL LoRA guidance, the trigger should carry identity only.
DEFAULT_PROMPTS = [
    {
        "name": "Put her head onto a pose",
        "note": "uses the FACE-ONLY LoRA. Type the pose, setting and the "
                "expression you want. For an img2img/ControlNet setup the "
                "expression is carried by the source pose instead - keep the "
                "denoise low so it survives.",
        "positive": "{trigger} woman, head and shoulders, "
                    "<describe the pose, setting and lighting>, "
                    "<describe her expression>, "
                    "same face, same person, her own eyes and mouth, "
                    "sharp facial features, natural skin texture, detailed",
        "negative": "different person, another face, face swap, blended face, "
                    "changed features, changed ethnicity, deformed face, "
                    "extra face, plastic skin, lowres, blurry, watermark, text",
    },
    {
        "name": "Put her head and body onto a pose",
        "note": "uses the FACE+BODY LoRA. Same idea, plus her build. Type the "
                "full-body pose and setting.",
        "positive": "{trigger} woman, full body, "
                    "<describe the full-body pose, setting and lighting>, "
                    "<describe her expression>, "
                    "same face, same person, her own eyes and mouth, "
                    "consistent body proportions, sharp facial features, "
                    "natural skin texture, detailed",
        "negative": "different person, another face, face swap, blended face, "
                    "changed features, changed body, wrong proportions, "
                    "deformed face, extra face, plastic skin, lowres, blurry, "
                    "watermark, text",
    },
]


def _load() -> list[dict]:
    if os.path.isfile(PROMPTS_FILE):
        try:
            with open(PROMPTS_FILE, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and isinstance(data.get("prompts"), list):
                return data["prompts"]
        except (OSError, ValueError):
            pass
    _save(DEFAULT_PROMPTS)
    return list(DEFAULT_PROMPTS)


def _save(prompts: list[dict]):
    os.makedirs(os.path.dirname(PROMPTS_FILE), exist_ok=True)
    tmp = PROMPTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"version": 1, "prompts": prompts}, fh, indent=2)
    os.replace(tmp, PROMPTS_FILE)


class FreedomPromptShelf:
    """Editable positive + negative prompt, with a drawer of saved prompts."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "positive": ("STRING", {"multiline": True, "default": DEFAULT_PROMPTS[0]["positive"]}),
                "negative": ("STRING", {"multiline": True, "default": DEFAULT_PROMPTS[0]["negative"]}),
            },
            "optional": {
                "trigger": ("STRING", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("positive", "negative")
    FUNCTION = "run"
    CATEGORY = "Freedom"

    def run(self, positive, negative, trigger=""):
        trig = (trigger or "").strip()
        pos = positive.replace("{trigger}", trig) if trig else positive.replace("{trigger}", "").replace("  ", " ")
        neg = negative.replace("{trigger}", trig) if trig else negative.replace("{trigger}", "")
        return (pos.strip(), neg.strip())


NODE_CLASS_MAPPINGS = {"FreedomPromptShelf": FreedomPromptShelf}
NODE_DISPLAY_NAME_MAPPINGS = {"FreedomPromptShelf": "Freedom Prompt Shelf"}


# --------------------------------------------------------------------------- #
# web API
# --------------------------------------------------------------------------- #
if _HAS_SERVER:
    routes = PromptServer.instance.routes

    @routes.get("/freedom/promptshelf/list")
    async def _list(request):
        return web.json_response({"prompts": _load()})

    @routes.post("/freedom/promptshelf/save")
    async def _save_one(request):
        body = await request.json()
        name = (body.get("name") or "").strip()
        if not name:
            return web.json_response({"ok": False, "error": "no name"})
        prompts = _load()
        entry = {"name": name,
                 "note": body.get("note", ""),
                 "positive": body.get("positive", ""),
                 "negative": body.get("negative", "")}
        for i, p in enumerate(prompts):
            if p["name"] == name:
                prompts[i] = entry
                break
        else:
            prompts.append(entry)
        _save(prompts)
        return web.json_response({"ok": True, "prompts": prompts})

    @routes.post("/freedom/promptshelf/delete")
    async def _delete(request):
        body = await request.json()
        name = body.get("name", "")
        prompts = [p for p in _load() if p["name"] != name]
        _save(prompts)
        return web.json_response({"ok": True, "prompts": prompts})
