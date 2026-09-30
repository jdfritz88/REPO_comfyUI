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
                      list_presets, read_preset, rename_preset, user_root, write_preset)

log = logging.getLogger("freedom_portrait_control")

MODE_PRESET_WINS = "preset wins - dials locked"
MODE_PRESET_UNLOCKED = "preset loaded - dials unlocked"
MODE_IGNORE_PRESETS = "ignore presets - use the dials"
MODES = [MODE_PRESET_WINS, MODE_PRESET_UNLOCKED, MODE_IGNORE_PRESETS]

NO_PRESET = "-- none --"

# Built-in choices at the BOTTOM of 4a's top preset dropdown (user, 2026-09-29, Q60/Q62).
# They are not files. They decide Portrait Master's on/off outright, so the pair dropdown
# ("which one starts the chain") can never fight a switch:
#   z_block      - every Portrait Master node OFF, greyed and locked on screen.
#   z_open_base  - every node ON and unlocked, Base Character ON, Face Generator OFF.
#   z_open_face  - every node ON and unlocked, Face Generator ON, Base Character OFF.
# "Open" means the dials are used as they are: no 4a preset values and no node
# presets are written over them.
Z_BLOCK = "z_block all nodes"
Z_OPEN_BASE = "z_unblock and open all nodes WITH Base Character (Face Generator must be OFF)"
Z_OPEN_FACE = "z_unblock and open all nodes WITH Face Generator (Base Character must be OFF)"
Z_PRESETS = [Z_BLOCK, Z_OPEN_BASE, Z_OPEN_FACE]
# The "In charge" dropdown is gone from the screen (user, 2026-09-29, Q64 = 4, Q65 = 3).
# The mode is worked out from the ONE preset menu instead, so there is nothing to conflict:
#   "-- none --" (shown as "Use the dials (no 4a preset)") -> ignore presets, use the dials
#   a saved preset                                         -> loads UNLOCKED (fills only
#                                                             the dials you have not changed)
#   a z_ choice                                            -> on/off outright (below)
# The old "mode" input stays on the node only so older workflows still open.
def effective_mode(preset_name):
    if not preset_name or preset_name == NO_PRESET:
        return MODE_IGNORE_PRESETS
    return MODE_PRESET_UNLOCKED


# The same for 4b-4g (user, 2026-09-29, Q66 = 1, Q73 = 1): each node's own preset menu
# decides; its "In charge" dropdown (<step>_mode on 4a) is hidden and not read any more.
#   "-- none --" -> ignore presets, use the dials;  a preset -> loads UNLOCKED.
def effective_node_mode(preset_name):
    if not preset_name or preset_name == NO_PRESET:
        return NODE_MODE_IGNORE
    return NODE_MODE_PRESET_UNLOCKED

# Descriptions of the built-in menu entries, editable with the description package.
# Saved presets keep their description inside their own file ("description").
NEEDS_DESCRIPTION = "needs description"
BUILTIN_DESCRIPTIONS_FILE = "builtin_descriptions.json"

Z_ON_OFF_NODES = ["PortraitMasterBaseCharacter", "PortraitMasterFaceGenerator",
                  "PortraitMasterSkinDetails", "PortraitMasterStylePose", "PortraitMasterMakeup"]

# Per-node radio choices, stored in 4a's "state" field by the web code.
NODE_MODE_PRESET = "node preset"           # dials locked, no buttons
NODE_MODE_PRESET_UNLOCKED = "node preset + unlocked"
NODE_MODE_IGNORE = "ignore presets"


# --------------------------------------------------------------------------- #
# The per-node choices as REAL node dropdowns on 4a.
#
# They replace the radio buttons our web code used to draw on each Portrait Master
# node. Radios were page elements, so only the PC had them; a dropdown is part of
# the node, so the PC, the phone and a raw API call all send it.
#
# Named by STEP letter (n4b ... n4g) so the phone shows something recognisable.
# Appended AFTER mode/preset/state, because saved workflows store values by
# position and inserting among them would misread every older workflow.
# --------------------------------------------------------------------------- #
STEP_OF = {
    "PortraitMasterBaseCharacter": "n4b",
    "PortraitMasterFaceGenerator": "n4c",
    "PortraitMasterSkinDetails":   "n4d",
    "PortraitMasterStylePose":     "n4e",
    "PortraitMasterMakeup":        "n4f",
    "PortraitMasterPromptStyler":  "n4g",
}
NODE_MODES = [NODE_MODE_PRESET, NODE_MODE_PRESET_UNLOCKED, NODE_MODE_IGNORE]
PAIR_CHOICES = ["4b Base Character", "4c Face Generator"]
STYLER_CHOICES = ["off", "on"]


def _node_preset_names(class_name):
    try:
        return [NO_PRESET] + [p["name"] for p in list_presets(class_name)]
    except Exception:
        return [NO_PRESET]


def _dropdown_inputs():
    out = {}
    for cls, step in STEP_OF.items():
        out["%s_mode" % step] = (NODE_MODES, {"default": NODE_MODE_PRESET})
        out["%s_preset" % step] = (_node_preset_names(cls), {"default": NO_PRESET})
    out["active_of_pair"] = (PAIR_CHOICES, {"default": "4b Base Character"})
    out["prompt_styler_switch"] = (STYLER_CHOICES, {"default": "off"})
    return out


def _user_preset_names():
    saved = [p["name"] for p in list_presets("user") if p["name"] not in Z_PRESETS]
    return [NO_PRESET] + saved + Z_PRESETS          # the built-in z_ choices always last


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
            },
            "optional": _dropdown_inputs(),
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("in_charge",)
    FUNCTION = "run"
    CATEGORY = "Freedom"

    @classmethod
    def IS_CHANGED(cls, mode, preset, state, **kw):
        return f"{mode}|{preset}|{state}|" + "|".join(f"{k}={v}" for k, v in sorted(kw.items()))

    def run(self, mode, preset, state, **kw):
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


def _activate(node):
    """Switch one Portrait Master node ON: active = True.

    The page code used to do this as you clicked a radio, so the server only ever had
    to switch the OTHER one off. A client with no page code - the phone, or a raw API
    call - sends whatever the workflow was saved with, and the workflow saves the
    non-default one as active = False. Without this the pair dropdown could switch one
    off and leave BOTH off, which produced an empty prompt from the pair. Found by a
    live run, not by reasoning.
    """
    inputs = node.setdefault("inputs", {})
    if "active" not in inputs or isinstance(inputs.get("active"), list):
        return False
    if inputs["active"] is not True:
        inputs["active"] = True
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
    preset_name = cin.get("preset", NO_PRESET)
    mode = effective_mode(preset_name)          # the old "mode" input is not read any more
    try:
        state = json.loads(cin.get("state") or "{}")
    except Exception:
        state = {}
    if not isinstance(state, dict):
        state = {}

    # ----------------------------------------------------------------------- #
    # The dropdowns are the source of truth when the node carries them. A workflow
    # saved before they existed has none, and falls back to the old hidden field,
    # so older workflows keep behaving exactly as they did.
    # ----------------------------------------------------------------------- #
    nodes_state = state.setdefault("nodes", {})
    sw = state.setdefault("switches", {})
    chosen = []
    for _cls, _step in STEP_OF.items():
        # "<step>_mode" is no longer read (Q66 = 1): the node's preset decides its mode.
        _p = cin.get("%s_preset" % _step)
        if _p:
            nodes_state.setdefault(_cls, {})["preset"] = _p
        _pn = nodes_state.get(_cls, {}).get("preset")
        if _pn and _pn != NO_PRESET:
            chosen.append("%s=%s" % (_step, _pn))
    _pair = cin.get("active_of_pair")
    if _pair:
        sw["start"] = "base" if _pair.startswith("4b") else "facegen"
        chosen.append("pair=%s" % sw["start"])
    _styler = cin.get("prompt_styler_switch")
    if _styler:
        sw["prompt_styler"] = (_styler == "on")
        chosen.append("styler=%s" % _styler)

    touched = 0
    notes = []
    if chosen:
        notes.append("dropdowns: " + ", ".join(chosen))

    # Portrait Master's OWN "save preset" switch saves its dials as a node preset on every
    # run - a save nobody pressed. Only a Save button may change a stored preset (user,
    # 2026-09-29), so it is switched off in every job, from every client.
    for class_name in NODE_CLASSES:
        for _nid, node in by_class.get(class_name, []):
            inputs = node.get("inputs") or {}
            if inputs.get("save_preset") is True:
                inputs["save_preset"] = False
                touched += 1
                notes.append("%s: Portrait Master's own auto-save switched off" % class_name)
    switches = state.get("switches") or {}

    # Built-in z_ choices: they decide on/off outright and skip everything else below
    # (no preset values, no node presets, no pair forcing). Obeyed in every mode except
    # "ignore presets", where the preset dropdown itself is out of use.
    if preset_name in Z_PRESETS:
        want_on = {c: (preset_name != Z_BLOCK) for c in Z_ON_OFF_NODES}
        if preset_name == Z_OPEN_BASE:
            want_on["PortraitMasterFaceGenerator"] = False
        elif preset_name == Z_OPEN_FACE:
            want_on["PortraitMasterBaseCharacter"] = False
        for class_name, on in want_on.items():
            for _nid, node in by_class.get(class_name, []):
                if (_activate(node) if on else _deactivate(node)):
                    touched += 1
        styler_ids = [nid for nid, _ in by_class.get("PortraitMasterPromptStyler", [])]
        if preset_name == Z_BLOCK or not switches.get("prompt_styler", False):
            if _bypass_prompt_styler(prompt, styler_ids):
                notes.append("Prompt Styler bypassed")
        notes.append("4a built-in '%s': %s" % (preset_name, ", ".join(
            "%s %s" % (c.replace("PortraitMaster", ""), "ON" if on else "OFF") for c, on in want_on.items())))
        log.info("[freedom_portrait_control] applied: %s (%d value(s) set)", "; ".join(notes), touched)
        return json_data

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
            pname = nstate.get("preset")
            nmode = effective_node_mode(pname)          # the old per-node mode is not read
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
    on_class = "PortraitMasterBaseCharacter" if start == "base" else "PortraitMasterFaceGenerator"
    for _nid, node in by_class.get(off_class, []):
        if _deactivate(node):
            touched += 1
            notes.append("%s switched off (start = %s)" % (off_class, start))
    for _nid, node in by_class.get(on_class, []):
        if _activate(node):
            touched += 1
            notes.append("%s switched on (start = %s)" % (on_class, start))

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

    def _builtin_refusal(body, key="name"):
        if body.get("scope", "user") == "user" and (body.get(key) in Z_PRESETS or body.get("new_name") in Z_PRESETS):
            return web.json_response({"ok": False, "error": "The z_ choices are built in - they cannot be saved over, renamed or deleted."}, status=400)
        return None

    @routes.post("/freedom/pm/preset/save")
    async def _save(request):
        body = await request.json()
        refused = _builtin_refusal(body)
        if refused:
            return refused
        result = write_preset(body.get("scope", "user"), body.get("name", ""),
                              body.get("data") or {}, bool(body.get("overwrite")))
        return web.json_response(result, status=200 if result.get("ok") else 400)

    @routes.post("/freedom/pm/preset/delete")
    async def _delete(request):
        body = await request.json()
        refused = _builtin_refusal(body)
        if refused:
            return refused
        # Portrait Master's own preset files are the developer's: never deleted from here.
        found = read_preset(body.get("scope", "user"), body.get("name", ""))
        if found and found.get("source") == "developer":
            return web.json_response({"ok": False, "error": "That is one of Portrait Master's own presets - it cannot be deleted from here."}, status=400)
        result = delete_preset(body.get("scope", "user"), body.get("name", ""))
        return web.json_response(result, status=200 if result.get("ok") else 404)

    @routes.post("/freedom/pm/preset/rename")
    async def _rename(request):
        body = await request.json()
        refused = _builtin_refusal(body)
        if refused:
            return refused
        result = rename_preset(body.get("scope", "user"), body.get("name", ""),
                               body.get("new_name", ""))
        return web.json_response(result, status=200 if result.get("ok") else 400)

    def _builtin_desc_path():
        import os
        return os.path.join(user_root(), BUILTIN_DESCRIPTIONS_FILE)

    def _read_builtin_descs():
        import os
        p = _builtin_desc_path()
        if not os.path.isfile(p):
            return {}
        try:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
            return d if isinstance(d, dict) else {}
        except Exception as e:
            log.warning("[freedom_portrait_control] cannot read %s (%s)", p, e)
            return {}

    # Built-in entries: 4a's "-- none --" and z_ choices (stored by name, as before), and on
    # 4b-4g the node's "-- none --" and Portrait Master's own presets (stored as
    # "<NodeClass>::<name>", in OUR file - the developer's preset files are never written).
    def _builtin_key(scope, name):
        if scope == "user":
            return name if (name == NO_PRESET or name in Z_PRESETS) else None
        if scope not in NODE_CLASSES:
            return None
        if name == NO_PRESET:
            return "%s::%s" % (scope, name)
        found = read_preset(scope, name)
        if found and found.get("source") == "developer":
            return "%s::%s" % (scope, name)
        return None

    @routes.get("/freedom/pm/description")
    async def _desc_get(request):
        scope = request.query.get("scope", "user")
        name = request.query.get("name", NO_PRESET)
        key = _builtin_key(scope, name)
        if key:
            text = _read_builtin_descs().get(key) or NEEDS_DESCRIPTION
            return web.json_response({"ok": True, "name": name, "builtin": True, "description": text})
        found = read_preset(scope, name)
        if not found:
            return web.json_response({"ok": False, "error": "No preset called '%s'." % name}, status=404)
        text = (found.get("data") or {}).get("description") or NEEDS_DESCRIPTION
        return web.json_response({"ok": True, "name": name, "builtin": False, "description": text})

    @routes.post("/freedom/pm/description")
    async def _desc_save_builtin(request):
        """Save the description of a BUILT-IN entry only. A saved preset's description is
        saved together with the preset, by its own Save / Save as buttons."""
        import os
        body = await request.json()
        name = body.get("name", "")
        key = _builtin_key(body.get("scope", "user"), name)
        if not key:
            return web.json_response({"ok": False, "error": "Only built-in entries are saved here."}, status=400)
        descs = _read_builtin_descs()
        descs[key] = str(body.get("description") or "").strip() or NEEDS_DESCRIPTION
        os.makedirs(user_root(), exist_ok=True)
        tmp = _builtin_desc_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(descs, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, _builtin_desc_path())
        return web.json_response({"ok": True, "name": name, "description": descs[key]})

    @routes.get("/freedom/pm/defaults")
    async def _defaults(request):
        node = request.query.get("node")
        if node:
            return web.json_response({node: factory_defaults(node)})
        return web.json_response(all_factory_defaults())
