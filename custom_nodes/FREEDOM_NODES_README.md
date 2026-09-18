# comfyui_ext/ — Freedom custom nodes for ComfyUI

## freedom_folder_inspector
Two things in one package:

1. **Folder Inspector** (`nodes.py`, `model_inspect.py`, `web/folder_inspector.js`)
   — canvas boxes that look inside each model folder: file list with a
   green / amber / red bar, a description panel, a banner saying whether the
   file belongs in that folder, drag-to-move between folders (with Undo), and
   "wired" Load Checkpoint / Load LoRA nodes fed by the selection.

2. **Preview & Pick** (`save_pick.py`, `web/preview_pick.js`) — replaces
   Save Image. Pictures are held in temp, never auto-saved. Panel shows the
   batch with tick boxes:
   - one picture  -> **Save Image**
   - a batch      -> tick -> **Save Selected Images**
   - **Set User Save Folder** (button under Save Image) -> Windows folder
     picker; the choice is stored in the node's `save_folder` widget, so it
     travels inside the workflow.
   - **Open Folder** -> Explorer.
