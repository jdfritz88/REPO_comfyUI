# Freedom: Video Queue (ComfyUI custom node) — Phase B

A 9-slot queue that feeds the Wan image-to-video graph one item at a time.

- **"Send to Video Queue"** button on the Preview & Pick panel drops the ticked
  pictures into the queue.
- **9 slots**, each with its **own** motion prompt, size and length. A slot that
  came from a video (Phase D) gets a **green frame** + "from video" tag.
- **Two prompt panes**: left = the last motion prompt used (persists), right =
  the clicked slot's prompt (editable) with a **"Copy from previous prompt"**
  button.
- **Size / length presets** as buttons. Length is in seconds (5/10/15/20);
  clips over ~5 s are auto-chained (Phase C).
- **Auto-start** (default on): pressing "Send to Video Queue" also presses Run.
  Toggle it off in the panel.
- The **whole queue + settings + last prompt** live in the node's `state`
  string, so they save inside the workflow and survive a ComfyUI restart (#9,
  #9b, #19).

The node outputs `(start_image, motion_prompt, width, height, length_frames)`
— wire those into the Wan I2V graph (Phase C builds the full workflow).

## Phase C / D (not yet)
- auto-advance the queue as each render finishes
- the full Freedom Video workflow + auto-save + "Set User Save Folder" for videos
- "Extend video length" -> re-queue the finished video's last frame
- video metadata (prompt on the file), green-frame indicator, prompt read-back
