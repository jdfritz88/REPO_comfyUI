# =============================================================================
# FREEDOM SYSTEM - Prompt fix-ups
# Server-side, client-independent repairs applied to every prompt the moment
# it reaches ComfyUI's /prompt endpoint, before validation - through ComfyUI's
# own PromptServer.add_on_prompt_handler hook (server.py: post_prompt() calls
# trigger_on_prompt(json_data); each handler receives the full request body
# and returns it, possibly modified).
#
# Why this exists - the seed placeholder problem, verified end to end:
#
#   A node whose seed is a plain INT input with no schema-declared
#   control_after_generate (Portrait Master's `seed: ("INT", {"forceInput":
#   False})` is the live example) still gets ComfyUI's generic, frontend-only
#   control widget beside it. When that control is anything but "fixed", the
#   frontend deliberately does not restore the saved number on load - confirmed
#   directly: window.app.loadGraphData() then reading the widget gives the
#   literal string "randomize", with every one of the node's other 55 widgets
#   restored exactly as saved. The number is meant to be minted later, by a
#   pre-queue hook the frontend wires up only for NATIVELY declared seeds
#   (KSampler-style). A generic seed never gets it, so the literal string
#   reaches /prompt and validation rejects the whole graph:
#   "invalid literal for int() with base 10: 'randomize'".
#
#   Every client hits this the same way - the desktop web UI on a fresh load,
#   the mobile page (comfyui-mobile-frontend, which also keeps its own persisted
#   copy of the workflow on the phone), Comfy Portal, and raw API callers.
#   Editing the saved workflow file cannot help: the stored number is exactly
#   what gets discarded. The only place that sees every client is the server,
#   so the repair lives here: any seed-like input still carrying a control-mode
#   word is given a real random number - what a live "randomize" would have
#   produced.
# =============================================================================
import logging
import random

try:
    from server import PromptServer
    _HAS_SERVER = True
except Exception:                       # pragma: no cover
    _HAS_SERVER = False

_SEED_CONTROL_MODES = {"randomize", "increment", "decrement", "fixed"}
_SEED_INPUT_NAMES = ("seed", "noise_seed")


def _resolve_seed_placeholders(json_data):
    prompt = json_data.get("prompt") if isinstance(json_data, dict) else None
    if not isinstance(prompt, dict):
        return json_data
    fixed = []
    for node_id, node in prompt.items():
        inputs = node.get("inputs") if isinstance(node, dict) else None
        if not isinstance(inputs, dict):
            continue
        for key in _SEED_INPUT_NAMES:
            v = inputs.get(key)
            if isinstance(v, str) and v.strip().lower() in _SEED_CONTROL_MODES:
                inputs[key] = random.randint(0, 2**31 - 1)
                fixed.append(f"{node.get('class_type', '?')}#{node_id}.{key}")
    if fixed:
        logging.info("[freedom_prompt_fixups] resolved seed placeholder(s) to real "
                     "numbers before validation: %s", ", ".join(fixed))
    return json_data


if _HAS_SERVER and PromptServer.instance is not None:
    PromptServer.instance.add_on_prompt_handler(_resolve_seed_placeholders)

# No nodes - this package exists only for the hook above. ComfyUI still needs
# the mapping attribute present to treat the folder as a loaded package.
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
