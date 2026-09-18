# =============================================================================
# FREEDOM SYSTEM - Portrait Control  (STEP 4a)
#
# Our own add-on, in our own folder, so a Portrait Master re-install or update can
# never erase it. It does three things:
#
#   1. Declares the 4a node: which mode is in charge, which user preset is selected,
#      and a hidden field holding each node group's own radio choice.
#   2. Serves the buttons: list / save / save-as / delete presets, and the developer's
#      factory values, read live from their code.
#   3. Applies the chosen preset AT QUEUE TIME, on the server, by rewriting the other
#      nodes' values in the submitted prompt. The screen also shows the values (our web
#      code fills the dials in), but the server does not depend on the screen - so a
#      phone, Comfy Portal or a raw API call obey the same rules.
#
# Why a hidden field for the per-node radios: ComfyUI sends a node's INPUT values to the
# server and nothing else - not its properties. A radio drawn by our web code on one of
# the developer's nodes is therefore invisible to the server unless its state travels in
# something the server receives. It travels in 4a's "state" input.
# =============================================================================
import json
import logging

from .presets import (NODE_CLASSES, all_factory_defaults, delete_preset, factory_defaults,
                      list_presets, read_preset, user_root, write_preset)

log = logging.getLogger("freedom_portrait_control")

MODE_PRESET_WINS = "preset wins - dials locked"
MODE_PRESET_UNLOCKED = "preset loaded - dials unlocked"
MODE_IGNORE_PRESETS = "ignore presets - use the dials"
MODES = [MODE_PRESET_WINS, MODE_PRESET_UNLOCKED, MODE_IGNORE_PRESETS]

NO_PRESET = "-- none --"

# Per-node radio choices, stored in 4a's "state" field by the web code.
NODE_MODE_PRESET = "node preset"           # dials locked, no buttons
NODE_MODE_PRESET_UNLOCKED = "node preset + unlocked"
NODE_MODE_IGNORE = "ignore presets"


def _user_preset_names():
    return [NO_PRESET] + [p["name"] for p in list_presets("user")]


class FreedomPortraitUserPreset:
    """STEP 4a - Random (Portrait Master) user preset."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (MODES, {"default": MODE_PRESET_WINS}),
                "preset": (_user_preset_names(), {"default": NO_PRESET}),
                # Hidden on screen by our web code; it carries each node group's radio
                # choice, its chosen preset, and the two switches, to the server.
                "state": ("STRING", {"multiline": True, "default": "{}"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("in_charge",)
    FUNCTION = "run"
    CATEGORY = "Freedom"

    @classmethod
    def IS_CHANGED(cls, mode, preset, state):
        return f"{mode}|{preset}|{state}"

    def run(self, mode, preset, state):
        if mode == MODE_IGNORE_PRESETS:
            return (mode,)
        return (f"{mode}: {preset}",)


# --------------------------------------------------------------------------- #
# Hide Portrait Master 2.9.2 (Legacy) from ComfyUI's node menu.
#
# It is deliberately left out of the workflow: it is the pre-July-2024 all-in-one node,
# kept by the developer only so old workflows still open, it duplicates the newer nodes'
# dials, is missing everything added since, and its dials do not start at "-".
#
# ComfyUI's server marks a node as deprecated when its class sets DEPRECATED (server.py),
# and the page hides deprecated nodes unless the user asks to see them. We set that flag on
# the class AT RUNTIME, in memory - the developer's files are never edited, so a re-install
# of Portrait Master is unaffected and nothing is lost. Removing these lines brings the node
# straight back.
try:
    import nodes as _comfy_nodes
    _legacy = _comfy_nodes.NODE_CLASS_MAPPINGS.get("PortraitMaster")
    if _legacy is not None and not getattr(_legacy, "DEPRECATED", False):
        _legacy.DEPRECATED = True
        log.info("[freedom_portrait_control] Portrait Master 2.9.2 (Legacy) hidden from the node menu")
except Exception as _exc:                # never let this stop the add-on loading
    log.warning("[freedom_portrait_control] could not hide the legacy node: %s", _exc)


NODE_CLASS_MAPPINGS = {"FreedomPortraitUserPreset": FreedomPortraitUserPreset}
NODE_DISPLAY_NAME_MAPPINGS = {
    "FreedomPortraitUserPreset": "Random (Portrait Master) user preset",
}
WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]


# --------------------------------------------------------------------------- #
# Applying a preset to the submitted prompt
# --------------------------------------------------------------------------- #
def _nodes_by_class(prompt):
    out = {}
    for nid, node in prompt.items():
        if isinstance(node, dict):
            out.setdefault(node.get("class_type"), []).append((nid, node))
    return out


def _apply_values(node, values, class_name):
    """Write dial values into one node's inputs, skipping anything wired to another node
    (a linked input arrives as a list and must never be overwritten by a value)."""
    changed = 0
    inputs = node.setdefault("inputs", {})
    allowed = set(factory_defaults(class_name))
    for field, value in (values or {}).items():
        if field not in allowed:
            continue
        if field in ("seed", "load_preset", "save_preset", "save_preset_as"):
            continue
        if isinstance(inputs.get(field), list):
            continue
        if inputs.get(field) != value:
            inputs[field] = value
            changed += 1
    return changed


def _deactivate(node):
    """Switch one Portrait Master node off the developer's own way: active = False.
    Their code then emits nothing of its own and passes text_in straight through."""
    inputs = node.setdefault("inputs", {})
    if "active" not in inputs or isinstance(inputs.get("active"), list):
        return False
    if inputs["active"] is not False:
        inputs["active"] = False
        return True
    return False


def _bypass_prompt_styler(prompt, styler_ids):
    """Take Prompt Styler out of the line: whoever reads its output reads its input source
    instead. Used when its radio is off, which is the default."""
    fixed = 0
    for sid in styler_ids:
        src = (prompt.get(sid, {}).get("inputs") or {}).get("text_in")
        if not isinstance(src, list):
            continue
        for nid, node in prompt.items():
            if nid == sid or not isinstance(node, dict):
                continue
            for field, value in list((node.get("inputs") or {}).items()):
                if isinstance(value, list) and len(value) == 2 and str(value[0]) == str(sid):
                    node["inputs"][field] = src
                    fixed += 1
    return fixed


def _fill_untouched(node, values, class_name):
    """Preset fills only the dials still sitting at the developer's own starting value,
    so a deliberate tweak survives."""
    defaults = factory_defaults(class_name)
    inputs = node.get("inputs") or {}
    return {f: v for f, v in (values or {}).items() if inputs.get(f) == defaults.get(f)}


def _apply(json_data):
    prompt = json_data.get("prompt") if isinstance(json_data, dict) else None
    if not isinstance(prompt, dict):
        return json_data
    by_class = _nodes_by_class(prompt)
    controls = by_class.get("FreedomPortraitUserPreset") or []
    if not controls:
        return json_data

    control = controls[0][1]
    cin = control.get("inputs") or {}
    mode = cin.get("mode", MODE_PRESET_WINS)
    preset_name = cin.get("preset", NO_PRESET)
    try:
        state = json.loads(cin.get("state") or "{}")
    except Exception:
        state = {}
    if not isinstance(state, dict):
        state = {}

    touched = 0
    notes = []
    switches = state.get("switches") or {}

    if mode in (MODE_PRESET_WINS, MODE_PRESET_UNLOCKED) and preset_name and preset_name != NO_PRESET:
        found = read_preset("user", preset_name)
        if not found:
            log.warning("[freedom_portrait_control] preset %r not found - nothing applied", preset_name)
            return json_data
        data = found.get("data") or {}
        switches = data.get("switches") or switches
        for class_name in NODE_CLASSES:
            values = (data.get("nodes") or {}).get(class_name)
            if not values:
                continue
            for _nid, node in by_class.get(class_name, []):
                if mode == MODE_PRESET_WINS:
                    touched += _apply_values(node, values, class_name)
                else:
                    touched += _apply_values(node, _fill_untouched(node, values, class_name), class_name)
        notes.append("4a preset '%s' (%s)" % (preset_name, mode))
    else:
        for class_name in NODE_CLASSES:
            nstate = (state.get("nodes") or {}).get(class_name) or {}
            nmode = nstate.get("mode", NODE_MODE_PRESET)
            pname = nstate.get("preset")
            if nmode == NODE_MODE_IGNORE or not pname or pname == NO_PRESET:
                continue
            found = read_preset(class_name, pname)
            if not found:
                continue
            values = found.get("data") or {}
            for _nid, node in by_class.get(class_name, []):
                if nmode == NODE_MODE_PRESET:
                    touched += _apply_values(node, values, class_name)
                else:
                    touched += _apply_values(node, _fill_untouched(node, values, class_name), class_name)
            notes.append("%s: preset '%s' (%s)" % (class_name, pname, nmode))

    start = switches.get("start", "base")
    off_class = "PortraitMasterFaceGenerator" if start == "base" else "PortraitMasterBaseCharacter"
    for _nid, node in by_class.get(off_class, []):
        if _deactivate(node):
            touched += 1
            notes.append("%s switched off (start = %s)" % (off_class, start))

    if not switches.get("prompt_styler", False):
        styler_ids = [nid for nid, _ in by_class.get("PortraitMasterPromptStyler", [])]
        if _bypass_prompt_styler(prompt, styler_ids):
            notes.append("Prompt Styler bypassed")

    if touched or notes:
        log.info("[freedom_portrait_control] applied: %s (%d value(s) set)",
                 "; ".join(notes) or "switches only", touched)
    return json_data


# --------------------------------------------------------------------------- #
# server: prompt hook + routes for the buttons
# --------------------------------------------------------------------------- #
try:
    from server import PromptServer
    from aiohttp import web
    _HAS_SERVER = True
except Exception:                       # pragma: no cover
    _HAS_SERVER = False

if _HAS_SERVER and PromptServer.instance is not None:
    PromptServer.instance.add_on_prompt_handler(_apply)
    routes = PromptServer.instance.routes

    @routes.get("/freedom/pm/presets")
    async def _list(request):
        scope = request.query.get("scope", "user")
        return web.json_response({"scope": scope, "presets": list_presets(scope),
                                  "folder": user_root()})

    @routes.get("/freedom/pm/preset")
    async def _read(request):
        scope = request.query.get("scope", "user")
        name = request.query.get("name", "")
        found = read_preset(scope, name)
        if not found:
            return web.json_response({"ok": False, "error": "No preset called '%s'." % name},
                                     status=404)
        payload = {"ok": True}
        payload.update(found)
        return web.json_response(payload)

    @routes.post("/freedom/pm/preset/save")
    async def _save(request):
        body = await request.json()
        result = write_preset(body.get("scope", "user"), body.get("name", ""),
                              body.get("data") or {}, bool(body.get("overwrite")))
        return web.json_response(result, status=200 if result.get("ok") else 400)

    @routes.post("/freedom/pm/preset/delete")
    async def _delete(request):
        body = await request.json()
        result = delete_preset(body.get("scope", "user"), body.get("name", ""))
        return web.json_response(result, status=200 if result.get("ok") else 404)

    @routes.get("/freedom/pm/defaults")
    async def _defaults(request):
        node = request.query.get("node")
        if node:
            return web.json_response({node: factory_defaults(node)})
        return web.json_response(all_factory_defaults())
