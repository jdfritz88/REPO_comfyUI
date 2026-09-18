# ==========================================
# FREEDOM SYSTEM - ComfyUI nodes (Folder Inspector + Preview & Pick)
# __init__.py  (tells ComfyUI where the nodes and the web panels live)
# ==========================================
from .nodes import NODE_CLASS_MAPPINGS as _A, NODE_DISPLAY_NAME_MAPPINGS as _AN
from .save_pick import NODE_CLASS_MAPPINGS as _B, NODE_DISPLAY_NAME_MAPPINGS as _BN

NODE_CLASS_MAPPINGS = {}
NODE_CLASS_MAPPINGS.update(_A)
NODE_CLASS_MAPPINGS.update(_B)

NODE_DISPLAY_NAME_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS.update(_AN)
NODE_DISPLAY_NAME_MAPPINGS.update(_BN)

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
