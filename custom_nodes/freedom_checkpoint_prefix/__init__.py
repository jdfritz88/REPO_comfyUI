# =============================================================================
# FREEDOM SYSTEM - Checkpoint front text (user, 2026-09-29, Q56 = B made general, Q59 = 1)
#
# Some art models want their own words at the very start of every prompt - for
# CyberRealistic Pony, its maker recommends "score_9, score_8_up, score_7_up"
# (civitai.com/models/443821). This node loads the front text saved for whatever
# model STEP 1 has picked, and gives nothing ("n/a") for a model with nothing saved.
#
# - Which model: read from the job itself (the hidden PROMPT input), so STEP 1 is not
#   changed and needs no extra wire. Exactly one checkpoint loader must be in the job;
#   none or several gives a clear warning and NO front text - it never guesses.
# - Runs every time (IS_CHANGED = nan), so switching models can never leave old text.
# - One small file per model, in OUR folder: user/default/checkpoint_prefix/<model>.json
# - Save / edit / delete from the node (web/checkpoint_prefix.js, routes below).
# - Prompt watcher: one log line per run, and the node shows the finished prompt that
#   STEP 7b built (FreedomPromptParts sends it back to the page).
# =============================================================================
import json
import logging
import os
import re

import folder_paths

log = logging.getLogger("freedom_checkpoint_prefix")

LOADER_CLASSES = ("CheckpointLoaderSimple", "CheckpointLoader", "CheckpointLoaderNF4",
                  "ImageOnlyCheckpointLoader", "unCLIPCheckpointLoader")
STORE = os.path.join(folder_paths.get_user_directory(), "default", "checkpoint_prefix")
NA = "n/a"


def _safe(name):
    return re.sub(r'[\\/:*?"<>|]+', "_", str(name or "")).strip() or "_"


def entry_path(ckpt):
    return os.path.join(STORE, _safe(os.path.basename(str(ckpt).replace("\\", "/"))) + ".json")


def read_entry(ckpt):
    p = entry_path(ckpt)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception as e:                       # a broken file is reported, never guessed around
        log.warning("[Freedom] Checkpoint front text: cannot read %s (%s)", p, e)
        return None


def write_entry(ckpt, front):
    os.makedirs(STORE, exist_ok=True)
    p = entry_path(ckpt)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"checkpoint": ckpt, "front": front}, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)
    return p


def picked_checkpoint(prompt):
    """The model STEP 1 has picked, read from the job. Returns (name, problem)."""
    found = []
    for nid, node in (prompt or {}).items():
        if isinstance(node, dict) and node.get("class_type") in LOADER_CLASSES:
            name = (node.get("inputs") or {}).get("ckpt_name")
            if isinstance(name, str):
                found.append(name)
    if len(found) == 1:
        return found[0], None
    if not found:
        return None, "no checkpoint loader found in the job"
    return None, "more than one checkpoint loader in the job (%s) - not guessing which" % ", ".join(found)


class FreedomCheckpointFrontText:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "enabled": ("BOOLEAN", {"default": True,
                            "tooltip": "ON = add the saved front text for the model STEP 1 has picked. "
                                       "OFF = add nothing."}),
            },
            "hidden": {"prompt": "PROMPT", "unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("front",)
    FUNCTION = "run"
    CATEGORY = "Freedom"
    DESCRIPTION = ("Loads the front text saved for the model picked in STEP 1 (for example "
                   "CyberRealistic Pony's score tags) and puts it at the very start of the prompt. "
                   "n/a when nothing is saved for that model.")

    @classmethod
    def IS_CHANGED(cls, **kw):
        return float("nan")                      # always run - the model choice lives outside this node

    def run(self, enabled=True, prompt=None, unique_id=None):
        ckpt, problem = picked_checkpoint(prompt)
        front = ""
        if not enabled:
            status = "switched OFF - nothing added"
        elif problem:
            status = "WARNING: " + problem + " - nothing added"
        else:
            entry = read_entry(ckpt)
            front = str((entry or {}).get("front") or "").strip()
            status = ("added '%s'" % front) if front else (NA + " - nothing saved for this checkpoint")
        log.info("[Freedom] Checkpoint front text: %s for %s", status, ckpt or "(unknown)")
        return {"ui": {"checkpoint": [ckpt or ""], "front": [front], "status": [status]}, "result": (front,)}


NODE_CLASS_MAPPINGS = {"FreedomCheckpointFrontText": FreedomCheckpointFrontText}
NODE_DISPLAY_NAME_MAPPINGS = {"FreedomCheckpointFrontText": "Freedom Checkpoint Front Text (per model, goes first)"}
WEB_DIRECTORY = "./web"

# --------------------------------------------------------------------------- #
# routes for the node's buttons
# --------------------------------------------------------------------------- #
try:
    from server import PromptServer
    from aiohttp import web

    routes = PromptServer.instance.routes

    @routes.get("/freedom/ckptfront/entry")
    async def _entry(request):
        ckpt = request.query.get("ckpt", "")
        e = read_entry(ckpt) if ckpt else None
        return web.json_response({"ok": True, "checkpoint": ckpt, "exists": e is not None,
                                  "front": (e or {}).get("front", "")})

    @routes.post("/freedom/ckptfront/save")
    async def _save(request):
        body = await request.json()
        ckpt = str(body.get("ckpt") or "").strip()
        if not ckpt:
            return web.json_response({"ok": False, "error": "No checkpoint picked in STEP 1."})
        if ckpt not in folder_paths.get_filename_list("checkpoints"):
            return web.json_response({"ok": False, "error": "'%s' is not a checkpoint ComfyUI knows." % ckpt})
        front = str(body.get("front") or "").strip()
        p = write_entry(ckpt, front)
        log.info("[Freedom] Checkpoint front text: saved for %s -> %s", ckpt, p)
        return web.json_response({"ok": True, "front": front})

    @routes.post("/freedom/ckptfront/delete")
    async def _delete(request):
        body = await request.json()
        ckpt = str(body.get("ckpt") or "").strip()
        p = entry_path(ckpt)
        if not ckpt or not os.path.isfile(p):
            return web.json_response({"ok": False, "error": "Nothing saved for this checkpoint."})
        os.remove(p)
        log.info("[Freedom] Checkpoint front text: deleted entry for %s", ckpt)
        return web.json_response({"ok": True})
except Exception as e:                           # pragma: no cover
    log.warning("[Freedom] Checkpoint front text: routes not added (%s)", e)
