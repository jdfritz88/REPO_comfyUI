# Prompt for the next session — LoRAs and OneTrainer destinations

Written 2026-09-18. Paste the block below into a session started in `REPO_comfyUI`.

```
Work from F:\Apps\freedom_system\REPO_comfyUI.

Read these two logs first, in full, before touching anything:
  logs\move_to_app_cabinet_HANDOFF_2026-09-17.md
  logs\portrait_master_exhaustive.md

Context you need: on 2026-09-18 ComfyUI was split in two. The developer's app now
lives at F:\Apps\freedom_system\app_cabinet\comfyui and is deliberately kept
pristine so it can be updated. Everything of ours lives here in REPO_comfyUI.
The kobold launcher starts the app and passes --base-directory pointing here, so
ComfyUI reads nodes, models, workflows, presets, input and output from this repo
and writes nothing of ours into the developer's folder. Do not break that.

Three jobs. Report exact findings for each. Do not guess, do not work around a
failure - report it.

1. VERIFY TODAY'S LORAS ARE IN THIS REPO, NOT THE APP CABINET.
   Four were trained on 2026-09-18:
     susana_head_sdxl, susana_head_sdxl_pony,
     susana_head_body_sdxl, susana_head_body_sdxl_pony
   Expected here: models\loras\faces\*.safetensors, ~128 MB each, plus
   _registry.json. OneTrainer also leaves its own copies in
   app_cabinet\OneTrainer\_face_runs\susana\loras\ - that is its working output,
   not the published one.
   Confirm: every trained LoRA that should be usable is present under
   models\loras\faces here; the registry lists them; and nothing of ours has
   appeared inside app_cabinet\comfyui. Check the last one with
   `git -C ..\app_cabinet\comfyui status --short --ignored` - it must stay clean
   apart from venv and __pycache__.

2. VERIFY COMFYUI ACTUALLY SEES THEM.
   Not just that the files exist - that ComfyUI resolves them. Run ComfyUI's own
   path code the way main.py does:
     cd F:\Apps\freedom_system\app_cabinet\comfyui
     .\venv\Scripts\python.exe -c "import sys; sys.argv=['main.py','--base-directory',r'F:\Apps\freedom_system\REPO_comfyUI','--extra-model-paths-config',r'F:\Apps\freedom_system\REPO_comfyUI\extra_model_paths.yaml']; import comfy.options; comfy.options.enable_args_parsing(); import folder_paths, utils.extra_config; utils.extra_config.load_extra_path_config(r'F:\Apps\freedom_system\REPO_comfyUI\extra_model_paths.yaml'); print(folder_paths.get_filename_list('loras'))"
   enable_args_parsing() is not optional - without it the flags are silently
   ignored and everything resolves to the app folder instead.
   All four names must appear in that list, under faces\.
   Then, with ComfyUI running (started ONLY through the kobold launcher, option
   4 - never directly, never killed), confirm the same four appear in a LoraLoader
   node's dropdown in the browser. Use the "John Doe" Chrome profile, close old
   ComfyUI tabs first, and keep Chrome in the foreground or the page stalls.

3. MAKE ONETRAINER ALWAYS SAVE INTO THIS REPO.
   Read REPO_koboldccp_sst_tts_media\face_training\otrain.py (output_model_destination,
   around line 278) and pipeline.py (COMFY_LORAS, around line 38) and establish, as
   fact, where a training run writes and where its result is published.
   Then make it impossible for a run to end up anywhere but here: the published
   destination must resolve to F:\Apps\freedom_system\REPO_comfyUI\models\loras,
   with no path that can silently fall back to app_cabinet\comfyui. If the path is
   hardcoded, say so and say where. Prove the change by running one training job
   end to end, or if that is too slow, by tracing the destination the code computes
   and showing the value.
   Note: face_training itself has NOT yet moved out of the kobold repo - that is
   still outstanding and blocked by an open face tool window. Do not move it as
   part of this task.

Rules that apply: no guessing, no assuming, no shortcuts, no placeholders. If
something cannot be verified, say so plainly instead of presenting a weak check as
a pass. Ask one question at a time and keep an OPEN QUESTIONS ledger.
```

## What was already checked on 2026-09-18, so the next session does not redo it

- All four LoRAs are present in `models\loras\faces\`, ~128 MB each, written today
  between 01:19 and 11:55. `_registry.json` was last written 11:55.
- OneTrainer's own copies sit in `app_cabinet\OneTrainer\_face_runs\susana\loras\`.
  That is its working output; `pipeline.py`'s `COMFY_LORAS` publishes into this repo.
- `app_cabinet\comfyui` was verified clean at the time of the split.

What was NOT checked: whether ComfyUI resolves the LoRA names at runtime, whether the
dropdown shows them, and whether the OneTrainer destination can ever fall back to the
app cabinet. Those are jobs 2 and 3.
