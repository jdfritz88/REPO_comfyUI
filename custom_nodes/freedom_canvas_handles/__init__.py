# ==========================================
# FREEDOM SYSTEM - Canvas Handles
# __init__.py  (no nodes - only page code: web/canvas_handles.js)
#
# Makes the resize handles of boxes (nodes) and frames (node groups) easier to
# grab (user, 2026-10-01, choice 2): about twice as big, always faintly showing.
# Done from our own add-on so ComfyUI's own files stay untouched.
# ==========================================
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
