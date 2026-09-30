# =============================================================================
# FREEDOM SYSTEM - STEP 7b Summary Signal (user, 2026-09-29: Q55 = 1, Q71 = 1, Q72 = 1)
#
# Since Q72 = 1 this ONE node does two jobs (it was "Checkpoint front text" before):
#  1. the model's own front text (e.g. Pony's score tags), loaded for the model STEP 1
#     has picked and taken out again when another model is picked;
#  2. the user's "summary signal" words, which go right after it.
# Both must fit on "page 1" of the prompt - the first 75 places (tokens) ComfyUI reads
# as one piece. SDXL builds its one-line summary of the whole prompt from that first
# piece only (comfy/sd1_clip.py, first_pooled). The count uses ComfyUI's own SDXL
# word-splitter, so it is the real count, not an estimate.
#
# The class name is kept (FreedomCheckpointFrontText) so v09's wiring stays intact.
#
# --- what the front-text part does (Q56 = B made general, Q59 = 1) ---
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


LIMIT = 75                                        # places on page 1 (77 minus start and end marks)
_TOKENIZER = None


def join_signal(front, words):
    # Same joiner as STEP 7c (FreedomPromptParts.combine), so the count matches the real prompt.
    return ", ".join(p for p in (str(front or "").strip(), str(words or "").strip()) if p)


def page_one(text):
    """Count text with ComfyUI's own SDXL word-splitter (the CLIP-G half, which gives SDXL's
    summary). Returns used = places the text fills, fits = it all stays in the first piece."""
    global _TOKENIZER
    if _TOKENIZER is None:
        from comfy import sdxl_clip
        _TOKENIZER = sdxl_clip.SDXLTokenizer(embedding_directory=folder_paths.get_folder_paths("embeddings"))
    if not text:
        return {"used": 0, "pieces": 1, "fits": True}
    batches = _TOKENIZER.tokenize_with_weights(text, return_word_ids=True)["g"]
    used = sum(1 for b in batches for t in b if t[2] != 0)
    return {"used": used, "pieces": len(batches), "fits": len(batches) == 1}


class FreedomCheckpointFrontText:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "enabled": ("BOOLEAN", {"default": True,
                            "tooltip": "ON = add the saved front text for the model STEP 1 has picked. "
                                       "OFF = leave the model's text out (your own words still go in)."}),
                "signal": ("STRING", {"default": "", "multiline": True,
                           "tooltip": "Your summary-signal words. They go right after the model's "
                                      "front text, on page 1 of the prompt."}),
            },
            "hidden": {"prompt": "PROMPT", "unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("front",)
    FUNCTION = "run"
    CATEGORY = "Freedom"
    DESCRIPTION = ("STEP 7b Summary Signal. Starts with the text saved for the model picked in "
                   "STEP 1 (for example CyberRealistic Pony's score tags; nothing for a model with "
                   "nothing saved), then your most important words. Both must fit on page 1 - the "
                   "first 75 places of the prompt, the part SDXL sums up for the whole picture.")

    @classmethod
    def IS_CHANGED(cls, **kw):
        return float("nan")                      # always run - the model choice lives outside this node

    def run(self, enabled=True, signal="", prompt=None, unique_id=None):
        ckpt, problem = picked_checkpoint(prompt)
        front = ""
        if not enabled:
            status = "model text switched OFF - not added"
        elif problem:
            status = "WARNING: " + problem + " - model text not added"
        else:
            entry = read_entry(ckpt)
            front = str((entry or {}).get("front") or "").strip()
            status = ("added '%s'" % front) if front else (NA + " - nothing saved for this checkpoint")
        words = str(signal or "").strip()
        text = join_signal(front, words)
        page = page_one(text)
        if page["fits"]:
            fit = "%d of %d places used - all on page 1" % (page["used"], LIMIT)
        else:
            fit = ("WARNING: about %d places over page 1 - the end of your summary words lands on page 2"
                   % (page["used"] - LIMIT))
        status = "%s; your words: %s; %s" % (status, ("'%s'" % words) if words else "none", fit)
        log.info("[Freedom] STEP 7b Summary Signal: %s for %s", status, ckpt or "(unknown)")
        return {"ui": {"checkpoint": [ckpt or ""], "front": [front], "status": [status]}, "result": (text,)}


NODE_CLASS_MAPPINGS = {"FreedomCheckpointFrontText": FreedomCheckpointFrontText}
NODE_DISPLAY_NAME_MAPPINGS = {"FreedomCheckpointFrontText": "Freedom Summary Signal (model's front text + your words, page 1)"}
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

    @routes.post("/freedom/summary/count")
    async def _count(request):
        body = await request.json()
        text = str(body.get("text") or "")
        try:
            r = page_one(text)
        except Exception as e:                   # reported to the box, never guessed around
            log.warning("[Freedom] STEP 7b Summary Signal: could not count (%s)", e)
            return web.json_response({"ok": False, "error": "Could not count: %s" % e})
        return web.json_response({"ok": True, "text": text, "limit": LIMIT, **r})

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
