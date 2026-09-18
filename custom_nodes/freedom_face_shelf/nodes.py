# =============================================================================
# FREEDOM SYSTEM - Face Shelf
# A node that shows every trained face as a thumbnail card - person name, and
# whether it's the face-only or the face+body LoRA - three to a row, rows
# growing as more are trained. Click a card and this node loads that person's
# LoRA onto the model + CLIP passing through it, and hands out the trigger word.
#
# The shelf has an on/off switch. Off means true pass-through: model and CLIP
# come out exactly as they went in, the trigger comes out empty, and no LoRA is
# read from disk - but the selected face is remembered for when it goes back on.
#
# It reads the shelf registry the training pipeline writes:
#   comfyui/models/loras/faces/_registry.json
#   comfyui/models/loras/faces/_thumbs/<name>.png
# =============================================================================
import hashlib
import json
import logging
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

FACES_DIR = os.path.join(folder_paths.models_dir, "loras", "faces")
REGISTRY = os.path.join(FACES_DIR, "_registry.json")
THUMBS_DIR = os.path.join(FACES_DIR, "_thumbs")


log = logging.getLogger("freedom_face_shelf")

# Training rewrites _registry.json by writing a .tmp and swapping it in. For the
# few milliseconds that swap takes, opening the file here is refused with a
# Windows sharing violation, which Python reports as PermissionError errno 13
# with no winerror (measured 2026-09-13 in this ComfyUI venv, Python 3.13:
# longest unbroken run of refusals 4.8 ms; 11.8 ms at the Win32 level). This
# used to read as "no registry", and the shelf rendered with no face LoRA and
# no trigger, without an error. So wait that out, briefly - the same rule as
# face_training/safe_replace.py read_text, which this package cannot import.
_READ_DEADLINE_SECONDS = 2.0
_LOCK_WINERRORS = (None, 5, 32)     # None = the C runtime's open(); 5, 32 = Win32


def _read_registry_text() -> str:
    start = time.monotonic()
    attempts, wait = 0, 0.001
    while True:
        attempts += 1
        try:
            with open(REGISTRY, encoding="utf-8") as fh:
                text = fh.read()
        except PermissionError as e:
            if getattr(e, "winerror", None) not in _LOCK_WINERRORS:
                raise
            waited = time.monotonic() - start
            if waited >= _READ_DEADLINE_SECONDS:
                msg = (f"could not read {REGISTRY}: still refused after {attempts} attempts "
                       f"over {waited:.1f} s (last error: {e})")
                log.error(msg)
                raise PermissionError(e.errno, msg) from e
            time.sleep(min(wait, _READ_DEADLINE_SECONDS - waited))
            wait = min(wait * 2, 0.010)
            continue
        if attempts > 1:
            log.debug("read %s after %d attempts over %.0f ms (training was swapping it in)",
                      REGISTRY, attempts, (time.monotonic() - start) * 1000)
        return text


def _load_registry() -> dict:
    """The registry, or an empty one when no face has been trained yet.

    A registry that exists but stays refused is raised, not treated as empty:
    empty makes run() hand back the model with no face and no trigger, silently.
    """
    try:
        return json.loads(_read_registry_text())
    except (FileNotFoundError, ValueError):
        return {"version": 1, "people": {}}


def _cards(family_filter: str | None = None) -> list[dict]:
    """Flatten the registry into one card per LoRA, ordered person / crop / family.

    family_filter, when given, drops any card whose family doesn't match -
    used so the shelf only offers faces trained for the checkpoint actually
    wired in (see _checkpoint_family below)."""
    reg = _load_registry()
    out = []
    for pslug, person in sorted(reg.get("people", {}).items()):
        for name, e in person.get("loras", {}).items():
            if family_filter and e.get("family", "") != family_filter:
                continue
            thumb = e.get("thumb", "")
            has_thumb = bool(thumb) and os.path.isfile(os.path.join(FACES_DIR, thumb)) \
                if thumb else os.path.isfile(os.path.join(THUMBS_DIR, name + ".png"))
            out.append({
                "name": name,
                "person": person.get("display_name", pslug),
                "trigger": e.get("trigger", person.get("trigger", "")),
                "family": e.get("family", ""),
                "family_label": e.get("family_label", e.get("family", "")),
                "crop": e.get("crop", ""),
                "crop_label": "face" if e.get("crop") == "head" else "face + body",
                "lora_file": e.get("lora_file", ""),
                "partial": bool(e.get("partial")),
                "trained": e.get("trained", ""),
                "has_thumb": bool(has_thumb),
            })
    order = {"head": 0, "head_body": 1}
    out.sort(key=lambda c: (c["person"].lower(), order.get(c["crop"], 9), c["family"]))
    return out


# --------------------------------------------------------------------------- #
# checkpoint -> family
#
# Face LoRAs are trained per family (see face_training/otrain.py's FAMILIES),
# and a family is NOT the same thing as "architecture" the way Flux vs SDXL
# is: sdxl_pony is tensor-for-tensor identical SDXL, fine-tuned on Pony-style
# data - freedom_lora_stack's safetensors/tensor-shape classifier genuinely
# cannot tell it apart from base SDXL (there is no metadata or layout signal
# to key on). The one signal that reliably does, in practice, is the
# checkpoint's own filename - Pony checkpoints are named that way pretty much
# universally, which is also why face_training/thumbs.py's FAMILY_CKPT table
# keys off "cyberrealisticPony_v110.safetensors" rather than inspecting it.
# This is a name heuristic, not architecture detection - documented as such,
# and it fails OPEN (no filter) rather than guessing wrong when a checkpoint
# name is empty.
# --------------------------------------------------------------------------- #
def _checkpoint_family(checkpoint_name: str) -> str:
    lower = checkpoint_name.lower()
    return "sdxl_pony" if ("pony" in lower or "lustify" in lower or "krea" in lower) else "sdxl"


# The first entry of the face dropdown. It is deliberately a name no LoRA can
# have, so _card() finds nothing for it and run() falls through to its existing
# "no face" path - picking it needs no new code anywhere.
NO_FACE = "(no face)"


def _face_choices() -> list[str]:
    """The dropdown's options: no-face first, then every trained face.

    Read fresh each time ComfyUI asks for the node's inputs, so a face trained
    five minutes ago is in the list after a browser refresh. Unfiltered by
    checkpoint family on purpose - which checkpoint is wired in is a fact about
    the graph, which the server does not know when it is describing the node.
    The desktop shelf still filters, because it can see the wiring.
    """
    return [NO_FACE] + [c["name"] for c in _cards()]


def _card(name: str) -> dict | None:
    for c in _cards():
        if c["name"] == name:
            return c
    return None


def fmt_trigger(trigger: str, weight: float = 1.0) -> str:
    """The exact text this node hands to the prompt.

    A weight of 1 is emitted bare - "(word:1.0)" means the same thing to the
    model but clutters the prompt you have to read. Anything else is wrapped in
    ComfyUI's weighting syntax. The web panel renders this same string so what
    you see in the shelf is character-for-character what the model receives."""
    if not trigger:
        return ""
    if abs(float(weight) - 1.0) < 1e-3:
        return trigger
    return f"({trigger}:{float(weight):g})"


class FreedomFaceShelf:
    """Pick a trained face; this node loads its LoRA onto model + CLIP."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "strength": ("FLOAT", {"default": 0.9, "min": -2.0, "max": 2.0, "step": 0.05}),
                # A LIST, not free text, so every client can draw a picker.
                #
                # The thumbnail shelf is a DOM widget this package's own
                # web/face_shelf.js builds, and that script only runs in
                # ComfyUI's desktop front-end. On the phone - the built-in
                # /mobile page, or Comfy Portal - none of it exists, and a
                # STRING input renders as an empty text box: to choose a face
                # you had to already know a LoRA's exact filename and type it.
                # Declared as a list, ComfyUI publishes the choices in
                # /object_info and both of those apps draw a native dropdown
                # without knowing anything about this node.
                #
                # The desktop is unaffected: face_shelf.js sets this widget's
                # type to "hidden" on creation and drives .value itself, which
                # works the same whether it is a text box or a combo.
                "selected": (_face_choices(), {
                    "default": NO_FACE,
                    "tooltip": "Which trained face to load. On a phone this is "
                               "the picker; on the desktop use the thumbnails.",
                }),
                # LAST on purpose. ComfyUI restores widgets_values by position,
                # so anything added ahead of "selected" would shift the saved
                # strength and face of every workflow already on disk. Appended
                # here, older workflows simply have no value for it - the web
                # side then loads them as ON, which is how they behaved before
                # this switch existed.
                "enabled": ("BOOLEAN", {"default": True,
                                        "label_on": "face ON",
                                        "label_off": "face OFF"}),
                # Also appended last, for the same reason as "enabled".
                "trigger_weight": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 2.0,
                                             "step": 0.05}),
            },
            "optional": {
                # Wired from a Freedom Face Source node when one is on the
                # canvas - one shared switch instead of two independent ones,
                # so a trained face and a random face can never both be
                # active. Left unconnected (every workflow that predates this
                # and has no such switch), "enabled" above still decides on
                # its own exactly as it always has - nothing about existing
                # workflows changes unless you actually add the switch.
                "face_mode": ("STRING", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("MODEL", "CLIP", "STRING", "STRING")
    RETURN_NAMES = ("model", "clip", "trigger", "person")
    FUNCTION = "run"
    CATEGORY = "Freedom"

    def __init__(self):
        self._cache = None

    @classmethod
    def VALIDATE_INPUTS(cls, selected):
        """Accept any face name, including one that no longer exists.

        Naming an input here makes ComfyUI skip its own check that the value is
        one of the list's entries. That check is exactly wrong for this node:
        every workflow saved before the list existed holds "" in this slot, and
        any workflow can outlive the face it names - a person deleted, a LoRA
        retrained under a different name. Today that quietly produces no face.
        Enforcing the list would instead refuse to run the whole graph over a
        face the user may not even have switched on. run() already treats an
        unknown name as no face, which is the behaviour to keep.
        """
        return True

    @classmethod
    def IS_CHANGED(cls, model, clip, strength, selected, enabled=True, trigger_weight=1.0,
                   face_mode=""):
        return hashlib.sha256(
            f"{selected}|{strength}|{bool(enabled)}|{trigger_weight}|{face_mode}"
            .encode()).hexdigest()

    def run(self, model, clip, strength, selected, enabled=True, trigger_weight=1.0,
            face_mode=""):
        # A wired-in shared switch overrides the local one entirely, rather
        # than blending with it - one source of truth, not two votes. With
        # nothing wired in, face_mode arrives as "" and enabled decides alone,
        # exactly as before this switch existed.
        if face_mode:
            enabled = (face_mode == "trained_face")
        # Switched off: hand the model and CLIP straight back untouched and
        # return an empty trigger, so her name never reaches the prompt either.
        # The LoRA is not loaded at all - nothing to unload, no VRAM taken.
        # The chosen face stays in "selected" so switching back on restores it.
        if not enabled:
            return (model, clip, "", "")

        card = _card(selected) if selected else None
        if not card or not card["lora_file"] or strength == 0:
            return (model, clip, "", "")

        lora_path = folder_paths.get_full_path_or_raise("loras", card["lora_file"])
        if self._cache and self._cache[0] == lora_path:
            lora, meta = self._cache[1], self._cache[2]
        else:
            lora, meta = comfy.utils.load_torch_file(
                lora_path, safe_load=True, return_metadata=True)
            self._cache = (lora_path, lora, meta)

        m, c = comfy.sd.load_lora_for_models(
            model, clip, lora, strength, strength, lora_metadata=meta)
        return (m, c, fmt_trigger(card["trigger"], trigger_weight), card["person"])


NODE_CLASS_MAPPINGS = {"FreedomFaceShelf": FreedomFaceShelf}
NODE_DISPLAY_NAME_MAPPINGS = {"FreedomFaceShelf": "Freedom Face Shelf"}


# --------------------------------------------------------------------------- #
# web API
# --------------------------------------------------------------------------- #
if _HAS_SERVER:
    routes = PromptServer.instance.routes

    @routes.get("/freedom/faceshelf/list")
    async def _list(request):
        checkpoint = request.query.get("checkpoint", "")
        if not checkpoint:
            # No checkpoint found upstream - unfiltered, exactly as before.
            return web.json_response({"cards": _cards(), "family": "", "checkpoint": ""})
        family = _checkpoint_family(checkpoint)
        return web.json_response({
            "cards": _cards(family), "all_cards": _cards(),
            "family": family, "checkpoint": checkpoint,
        })

    @routes.get("/freedom/faceshelf/trigger")
    async def _trigger(request):
        """The prompt text for one card at one weight - formatted server-side so
        the panel can never disagree with what the node actually outputs."""
        card = _card(request.query.get("name", ""))
        try:
            w = float(request.query.get("weight", "1"))
        except ValueError:
            w = 1.0
        return web.json_response({"text": fmt_trigger(card["trigger"], w) if card else "",
                                  "trigger": card["trigger"] if card else "",
                                  "person": card["person"] if card else ""})

    @routes.get("/freedom/faceshelf/thumb")
    async def _thumb(request):
        name = request.query.get("name", "")
        safe = "".join(ch for ch in name if ch.isalnum() or ch in "._-")
        for p in (os.path.join(THUMBS_DIR, safe + ".png"),
                  os.path.join(THUMBS_DIR, safe + ".jpg")):
            if os.path.isfile(p):
                return web.FileResponse(p)
        return web.Response(status=404)
