# =============================================================================
# FREEDOM SYSTEM - Prompt Slots and Phrase Slots
#
# Two shelves that live in the STEP 7 group, next to the box you type your
# prompt into.
#
#   FreedomPromptSlots  - whole prompts. A dial walks you through them one at a
#                         time. Load drops the one you are on into the STEP 7
#                         box. Save overwrite, Save as and Create new put things
#                         back on the shelf.
#
#   FreedomPhraseSlots  - single phrases. Highlight a stretch of words in either
#                         text box, click Save phrase, and it lands here. Dial to
#                         it later and click Copy phrase, then paste where you
#                         want it.
#
# WHY THE DIAL IS A REAL NUMBER FIELD, NOT A DROP-DOWN LIST
# ---------------------------------------------------------
# A phone can open this server two ways, and they behave differently.
#
# The CueForge mobile app (served at /mobile) does not load custom node
# JavaScript - it draws whatever /object_info reports, and nothing else. Its
# number field is drawn as a minus button, the value, and a plus button (see
# that app's src/components/InputControls/NumberControl.tsx), so an INT widget
# is literally a dial-up / dial-down control there.
#
# ComfyUI's own page - the plain address, no /mobile - DOES load custom node
# JavaScript, on a phone just as on this PC, so it gives the whole shelf with
# every button.
#
# Everything the shelves need to REMEMBER is therefore an ordinary widget, so it
# survives in either place.
#
# The buttons are drawn by web/prompt_slots.js, so they exist anywhere ComfyUI's
# own page is open - this PC or a phone at the plain address - but not in the
# CueForge mobile app.
#
# Nothing here runs during a generation. Neither node has an output, so the
# picture-making never reaches them; they are worked entirely through the small
# web routes at the bottom of this file.
#
# The shelves themselves are two plain JSON files:
#     user/default/freedom_prompt_slots.json
#     user/default/freedom_phrases.json
# Slot number is just the position in the list - slot 1 is the first entry.
# =============================================================================
import json
import os

import folder_paths

try:
    from server import PromptServer
    from aiohttp import web
    _HAS_SERVER = True
except Exception:                       # pragma: no cover - ComfyUI always has it
    _HAS_SERVER = False


MAX_PROMPT_SLOTS = 99
MAX_PHRASE_SLOTS = 999


def _store(filename):
    """Full path of one of the two shelf files, inside the user folder."""
    return os.path.join(folder_paths.get_user_directory(), "default", filename)


PROMPTS_FILE = _store("freedom_prompt_slots.json")
PHRASES_FILE = _store("freedom_phrases.json")


# --------------------------------------------------------------------------- #
# reading and writing the two shelf files
# --------------------------------------------------------------------------- #
def _read(path, key):
    """Return the shelf, or an empty shelf if the file is missing or damaged."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    items = data.get(key) if isinstance(data, dict) else None
    return items if isinstance(items, list) else []


def _write(path, key, items):
    """Save the shelf. Written beside the real file then swapped into place, so a
    crash half way through can never leave you with half a shelf."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"version": 1, key: items}, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _read_prompts():
    """Every saved prompt, as name plus positive text, in slot order."""
    out = []
    for entry in _read(PROMPTS_FILE, "prompts"):
        if isinstance(entry, dict):
            out.append({"name": str(entry.get("name", "")),
                        "positive": str(entry.get("positive", ""))})
    return out


def _read_phrases():
    """Every saved phrase, as plain strings, in slot order."""
    return [str(p) for p in _read(PHRASES_FILE, "phrases") if isinstance(p, str)]


# --------------------------------------------------------------------------- #
# the two nodes
# --------------------------------------------------------------------------- #
class FreedomPromptSlots:
    """A shelf of whole prompts, walked with a dial."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "slot": ("INT", {
                    "default": 1, "min": 1, "max": MAX_PROMPT_SLOTS, "step": 1,
                    "tooltip": "The dial. Turn it up or down to walk through your "
                               "saved prompts one at a time. Slot 1 is the first "
                               "one you ever saved. The name and the text below "
                               "change to match.",
                }),
                "name": ("STRING", {
                    "default": "", "multiline": False,
                    "tooltip": "What this saved prompt is called. Type a name in "
                               "here first, then press Save as to put the text "
                               "from your STEP 7 box on the shelf under that name.",
                }),
                "saved_prompt": ("STRING", {
                    "default": "", "multiline": True,
                    "tooltip": "A window onto the saved prompt you are dialled to. "
                               "You cannot type in here - it only shows you what is "
                               "on the shelf. Press Load to send it to your STEP 7 "
                               "box, where you CAN edit it. You can still highlight "
                               "words in here and press Save phrase.",
                }),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "noop"
    CATEGORY = "Freedom"
    DESCRIPTION = ("A shelf of whole prompts. Dial through them, load one into the "
                   "STEP 7 box, or put the box's current text back on the shelf.")

    def noop(self, slot, name, saved_prompt):
        # Never called. The node has no output, so a generation never reaches it.
        return ()


class FreedomPhraseSlots:
    """A shelf of single phrases, walked with a dial."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "slot": ("INT", {
                    "default": 1, "min": 1, "max": MAX_PHRASE_SLOTS, "step": 1,
                    "tooltip": "The dial. Turn it up or down to walk through your "
                               "saved phrases one at a time. The phrase below "
                               "changes to match.",
                }),
                "phrase": ("STRING", {
                    "default": "", "multiline": True,
                    "tooltip": "A window onto the phrase you are dialled to. You "
                               "cannot type in here. When the one you want shows "
                               "up, press Copy phrase, then click into your STEP 7 "
                               "box and paste it wherever you like.",
                }),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "noop"
    CATEGORY = "Freedom"
    DESCRIPTION = ("A shelf of single phrases. Highlight words anywhere in STEP 7, "
                   "press Save phrase, and they land here to be copied later.")

    def noop(self, slot, phrase):
        # Never called. The node has no output, so a generation never reaches it.
        return ()


NODE_CLASS_MAPPINGS = {
    "FreedomPromptSlots": FreedomPromptSlots,
    "FreedomPhraseSlots": FreedomPhraseSlots,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "FreedomPromptSlots": "Freedom Prompt Slots",
    "FreedomPhraseSlots": "Freedom Phrase Slots",
}


# --------------------------------------------------------------------------- #
# web routes - everything the buttons do goes through here
# --------------------------------------------------------------------------- #
if _HAS_SERVER:
    routes = PromptServer.instance.routes

    @routes.get("/freedom/promptslots/list")
    async def _prompts_list(request):
        return web.json_response({"prompts": _read_prompts()})

    @routes.post("/freedom/promptslots/save")
    async def _prompts_save(request):
        """Write over the slot the dial is on. Slot numbers arrive 1-based."""
        body = await request.json()
        try:
            slot = int(body.get("slot", 0))
        except (TypeError, ValueError):
            return web.json_response({"ok": False,
                                      "error": "that slot number is not a number"})
        prompts = _read_prompts()
        if slot < 1 or slot > len(prompts):
            return web.json_response({"ok": False,
                                      "error": "slot " + str(slot) +
                                               " is empty - use Save as instead"})
        name = str(body.get("name", "")).strip()
        prompts[slot - 1] = {"name": name or prompts[slot - 1]["name"],
                             "positive": str(body.get("positive", ""))}
        _write(PROMPTS_FILE, "prompts", prompts)
        return web.json_response({"ok": True, "slot": slot, "prompts": prompts})

    @routes.post("/freedom/promptslots/saveas")
    async def _prompts_saveas(request):
        """Add a new prompt at the end of the shelf and report its slot number."""
        body = await request.json()
        name = str(body.get("name", "")).strip()
        if not name:
            return web.json_response({"ok": False,
                                      "error": "type a name in the name box first"})
        prompts = _read_prompts()
        if len(prompts) >= MAX_PROMPT_SLOTS:
            return web.json_response({"ok": False,
                                      "error": "the shelf is full at " +
                                               str(MAX_PROMPT_SLOTS)})
        prompts.append({"name": name, "positive": str(body.get("positive", ""))})
        _write(PROMPTS_FILE, "prompts", prompts)
        return web.json_response({"ok": True, "slot": len(prompts), "prompts": prompts})

    @routes.post("/freedom/promptslots/delete")
    async def _prompts_delete(request):
        """Take one prompt off the shelf. Everything after it moves up a slot."""
        body = await request.json()
        try:
            slot = int(body.get("slot", 0))
        except (TypeError, ValueError):
            return web.json_response({"ok": False,
                                      "error": "that slot number is not a number"})
        prompts = _read_prompts()
        if slot < 1 or slot > len(prompts):
            return web.json_response({"ok": False,
                                      "error": "slot " + str(slot) + " is already empty"})
        gone = prompts.pop(slot - 1)
        _write(PROMPTS_FILE, "prompts", prompts)
        return web.json_response({"ok": True, "deleted": gone["name"], "prompts": prompts})

    @routes.get("/freedom/phrases/list")
    async def _phrases_list(request):
        return web.json_response({"phrases": _read_phrases()})

    @routes.post("/freedom/phrases/add")
    async def _phrases_add(request):
        """Put a highlighted stretch of words on the phrase shelf."""
        body = await request.json()
        text = str(body.get("text", "")).strip()
        if not text:
            return web.json_response({"ok": False,
                                      "error": "highlight some words first"})
        phrases = _read_phrases()
        if text in phrases:
            return web.json_response({"ok": True, "slot": phrases.index(text) + 1,
                                      "phrases": phrases, "already": True})
        if len(phrases) >= MAX_PHRASE_SLOTS:
            return web.json_response({"ok": False,
                                      "error": "the shelf is full at " +
                                               str(MAX_PHRASE_SLOTS)})
        phrases.append(text)
        _write(PHRASES_FILE, "phrases", phrases)
        return web.json_response({"ok": True, "slot": len(phrases), "phrases": phrases})


    @routes.post("/freedom/phrases/delete")
    async def _phrases_delete(request):
        """Take one phrase off the shelf. Everything after it moves up a slot."""
        body = await request.json()
        try:
            slot = int(body.get("slot", 0))
        except (TypeError, ValueError):
            return web.json_response({"ok": False,
                                      "error": "that slot number is not a number"})
        phrases = _read_phrases()
        if slot < 1 or slot > len(phrases):
            return web.json_response({"ok": False,
                                      "error": "slot " + str(slot) + " is already empty"})
        gone = phrases.pop(slot - 1)
        _write(PHRASES_FILE, "phrases", phrases)
        return web.json_response({"ok": True, "deleted": gone, "phrases": phrases})
