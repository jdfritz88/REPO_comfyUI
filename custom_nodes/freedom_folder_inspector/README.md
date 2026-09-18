# Freedom: Folder Inspector (ComfyUI custom node)

Boxes on the ComfyUI canvas that look inside your model folders.

- **Folder name on top** of each box (the real path is in the footer).
- **Left side**: every file in that folder, with a colour bar
  (green = fine, amber = caution, red = wrong folder / not a model).
- **Right side**: click a file once to see what it is, what base model it was made for,
  its trigger words, notes stored inside it, and any notes file saved next to it.
- **Banner** across the top of the description says plainly whether the file belongs in
  this folder. If it doesn't, a **Move it** button appears - or just **drag** the file onto
  the correct folder's box. The file (and its notes) are moved on disk, with an **Undo**.
- **Wiring**: each box outputs the selected file name. Plug it into
  *Freedom: Load Checkpoint (wired)* or *Freedom: Load LoRA (wired)* to use it in a recipe.

Nothing here ever loads a model into memory - only the small header at the start of the
file is read, so even a 12 GB file is inspected instantly.

## Install
Already in place at `REPO_comfyUI/custom_nodes/freedom_folder_inspector/`.
Restart ComfyUI once so it picks up the new nodes.

## Use
1. In ComfyUI: **Workflow -> Open** -> `custom_nodes/freedom_folder_inspector/workflows/Freedom_Model_Folders.json`
   (six inspectors laid out: checkpoints, diffusion_models, loras, vae, upscale_models, embeddings).
2. Or add one by hand: double-click the canvas, search **Freedom**, pick **Folder Inspector**,
   choose the folder in the dropdown.

## Files
- `model_inspect.py` - reads headers and works out what a file is (no ComfyUI needed; run it alone to test)
- `nodes.py` - the nodes and the tiny local web API (`/freedom/inspector/...`)
- `web/folder_inspector.js` - the panel drawn inside the node
- `workflows/Freedom_Model_Folders.json` - starter layout
