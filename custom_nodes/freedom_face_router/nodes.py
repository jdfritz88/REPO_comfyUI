# =============================================================================
# FREEDOM SYSTEM - Face Router
# One switch, not two. Before this existed, Face Shelf had its own on/off and
# Portrait Master had none at all, which meant nothing actually stopped both
# from contributing to the same prompt at once. Now there is exactly one
# control - FreedomFaceSource's "mode" - and everything downstream reads it
# instead of deciding for itself.
#
# FreedomFaceSource   - the switch. A single dropdown: off / trained_face /
#                       random_face. Its own selected value IS the readable
#                       state - no separate banner is needed, because Comfy
#                       Portal already renders a combo's current choice on a
#                       phone exactly as plainly as the desktop does.
#
# FreedomFaceRouter    - reads that switch and picks exactly one source of
#                       face text: Face Shelf's trigger, or Portrait Master's
#                       text, or nothing. A plain function of its current
#                       inputs, no memory of any previous run - so switching
#                       back and forth between modes is always clean; there is
#                       nothing left over to clear, because nothing is ever
#                       held onto between generations.
#
# 2026-09-16: Style & Pose is now IN the Portrait Master chain, the way the developer
# wires it (Base Character -> Skin Details -> Style & Pose -> Make-up). The router's
# second text input and its "include_style" switch were therefore removed: there is one
# Portrait Master text now, not two, so there is nothing left to splice in.
# =============================================================================

MODES = ["off", "trained_face", "random_face"]


class FreedomFaceSource:
    """The single switch. Everything else reads this instead of deciding
    on its own, so trained face and random face can never both be active."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # random_face is the default per current design intent: a
                # random face when nothing else says otherwise.
                "mode": (MODES, {"default": "random_face"}),
            }
        }

    RETURN_TYPES = (MODES, "STRING")
    RETURN_NAMES = ("mode", "mode_text")
    FUNCTION = "run"
    CATEGORY = "Freedom"

    def run(self, mode):
        return (mode, mode)


class FreedomFaceRouter:
    """Picks exactly one face text source, per the shared switch.

    A plain function of its current inputs only - it holds nothing from one
    run to the next, so there is nothing that needs to be "cleared" when the
    switch changes. Whatever mode is selected right now is what gets used
    right now, every time."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (MODES, {"default": "random_face"}),
            },
            "optional": {
                "trained_trigger": ("STRING", {"forceInput": True}),
                "random_appearance": ("STRING", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("face_text",)
    FUNCTION = "run"
    CATEGORY = "Freedom"

    @classmethod
    def IS_CHANGED(cls, mode, trained_trigger="", random_appearance=""):
        return f"{mode}|{trained_trigger}|{random_appearance}"

    def run(self, mode, trained_trigger="", random_appearance=""):
        if mode == "trained_face":
            return ((trained_trigger or "").strip(),)
        if mode == "random_face":
            return ((random_appearance or "").strip(),)
        return ("",)          # off


class FreedomShowText:
    """Displays whatever string reaches it - a debugging/verification tap,
    not a workflow-facing control. Echoes the value back through the same
    'ui' mechanism the other Freedom nodes already use for their own status
    reporting, so it shows up in the history API without needing a render."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"text": ("STRING", {"forceInput": True})}}

    RETURN_TYPES = ()
    FUNCTION = "run"
    OUTPUT_NODE = True
    CATEGORY = "Freedom"

    def run(self, text):
        return {"ui": {"text": [text]}}


NODE_CLASS_MAPPINGS = {
    "FreedomFaceSource": FreedomFaceSource,
    "FreedomFaceRouter": FreedomFaceRouter,
    "FreedomShowText": FreedomShowText,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "FreedomFaceSource": "Freedom Face Source (the switch)",
    "FreedomFaceRouter": "Freedom Face Router",
    "FreedomShowText": "Freedom Show Text (debug)",
}
