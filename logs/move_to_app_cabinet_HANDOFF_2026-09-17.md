# HANDOFF — move ComfyUI from REPO_comfyUI to app_cabinet\comfyui

Written 2026-09-17 by the Claude session that started in `F:\Apps\freedom_system\REPO_comfyUI`.
Plan approved by the user. NOTHING has been moved yet.

## Why a new session does this

On 2026-09-17 the move was tried from inside REPO_comfyUI, and Windows refused it:
`Cannot move item because the item at 'F:\Apps\freedom_system\REPO_comfyUI' is in use.`
At that moment:
- no running program had REPO_comfyUI in its command line or program path;
- port 8188 was free, so ComfyUI was not running;
- the Claude session's own working folder was REPO_comfyUI.

A session cannot leave the folder it started in. It was NOT proven that nothing else holds the folder, because the Sysinternals Handle tool is not installed. If the move is refused again, report the exact error to the user. Do not work around it.

## The user's rules for this job

- Do not guess or assume. Report exact results, including failures.
- Start the work only after the user gives a go-ahead (CLAUDE.md rule 3).
- Do NOT commit or push anything. Committing is still an open question for the user.
- Do not touch Waiver, or the koboldccp logs as "merge by date". Those are open questions too.
- REPO_koboldccp_sst_tts_media is NOT a backup of ComfyUI.
- Restart and stop ComfyUI only through the koboldccp launcher. Never kill its processes.
- Chrome: use the "John Doe" profile, never "Jacob". Close old ComfyUI tabs and workflows before loading the workflow again. Chrome must be the foreground window, or the ComfyUI page stalls.

## Steps (approved plan)

1. **Stop.**
   - Confirm ComfyUI is not running: no `main.py` process under REPO_comfyUI, and port 8188 free.
   - If it is running, stop it with launcher key `q`, then quit the launcher with `9`.
   - The launcher is `REPO_koboldccp_sst_tts_media\start_koboldcpp_media.bat`. Its main menu: `4` start ComfyUI, `8` stop apps, `9` quit. Its control console: `c` restart, `q` quit back to the menu, `e` quit and close.
   - Keystrokes don't reach the launcher while the screen is locked.
2. **Before-check.**
   - The approved BEFORE result already exists: `logs\portrait_master_checklist_BEFORE_2026-09-16.json` (43 PASS, 0 FAIL).
3. **Move.**
   - From a working folder OUTSIDE REPO_comfyUI, run:
     `Move-Item -LiteralPath F:\Apps\freedom_system\REPO_comfyUI -Destination F:\Apps\freedom_system\app_cabinet\comfyui`
   - First confirm that `app_cabinet\comfyui` does not already exist.
4. **Repoint the live files** that name REPO_comfyUI.
   - The paths below are as they were BEFORE the move, relative to `F:\Apps\freedom_system`.
   - Read each file before editing it. After editing, search again to confirm no live reference is left.
   - **LIVE — repoint:**
     - REPO_comfyUI/custom_nodes/freedom_face_competition/freedom_face_competition_state.json
     - REPO_comfyUI/custom_nodes/freedom_folder_inspector/README.md
     - REPO_comfyUI/custom_nodes/freedom_folder_inspector/freedom_save_settings.json
     - REPO_comfyUI/user/default/workflows/Freedom_bigLust_SDXL.json
     - REPO_comfyUI/user/default/workflows/Freedom_bigLust_SDXL v02.json
     - REPO_comfyUI/user/default/workflows/Freedom_bigLust_SDXL v03.json
     - REPO_comfyUI/user/default/workflows/Freedom_bigLust_SDXL v04.json
     - REPO_koboldccp_sst_tts_media/comfyui_ext/freedom_face_competition/build_face_competition.py
     - REPO_koboldccp_sst_tts_media/comfyui_ext/freedom_face_shelf/build_face_shelf.py
     - REPO_koboldccp_sst_tts_media/comfyui_ext/freedom_folder_inspector/README.md
     - REPO_koboldccp_sst_tts_media/comfyui_ext/freedom_prompt_shelf/build_face_image.py
     - REPO_koboldccp_sst_tts_media/comfyui_workflows/Freedom_bigLust_SDXL.json
     - REPO_koboldccp_sst_tts_media/comfyui_workflows/annotate_workflow.py
     - REPO_koboldccp_sst_tts_media/face_training/README.md
     - REPO_koboldccp_sst_tts_media/face_training/face_tool_ui.py
     - REPO_koboldccp_sst_tts_media/face_training/otrain.py
     - REPO_koboldccp_sst_tts_media/face_training/pipeline.py
     - REPO_koboldccp_sst_tts_media/face_training/sort_photos.py
     - REPO_koboldccp_sst_tts_media/face_training/thumbs.py
     - REPO_koboldccp_sst_tts_media/launcher.py
       - Line 84 currently reads: `COMFYUI_DIR = f"{BASE_DIR}/REPO_comfyUI"      # its own git repo, forked from upstream - not in app_cabinet`. Fix the comment too.
       - There is also a print statement near line 1073.
   - **HISTORY — leave unchanged** (these record what was true at the time):
     - REPO_comfyUI/user/default/workflow_backups/*
     - REPO_comfyUI/user/default/_workflow_backups_20260908/*
     - REPO_comfyUI/user/default/workflows/*.bak_before_*
     - REPO_koboldccp_sst_tts_media/REPO_koboldccp_sst_tts_media_Fix_LOG.md
     - REPO_koboldccp_sst_tts_media/REPO_koboldccp_sst_tts_media_Monitor_LOG.md
   - **Memory notes** that name REPO_comfyUI (update their paths):
     - C:\Users\jespe\.claude\projects\F--Apps-freedom-system-REPO-koboldccp-sst-tts-media\memory\comfyui-ext-two-copies.md
     - C:\Users\jespe\.claude\projects\F--Apps-freedom-system-REPO-koboldccp-sst-tts-media\memory\face-training-onetrainer.md
     - C:\Users\jespe\.claude\projects\F--Apps-freedom-system-REPO-comfyUI\memory\portrait-master-user-preset-plan.md
       - Update its path, and copy it with its MEMORY.md index line into the memory folder for sessions started in the new location.
5. **Start** ComfyUI with `start_koboldcpp_media.bat`, option `4`.
6. **After-check.**
   - Run: `venv\Scripts\python.exe logs\portrait_master_checklist.py F:\Apps\freedom_system\app_cabinet\comfyui logs\portrait_master_checklist_AFTER_2026-09-17.json`
   - Run it from inside `app_cabinet\comfyui`.
   - Compare with BEFORE, check by check. Every check must PASS (43/43).
   - Search the live files again for "REPO_comfyUI".
   - **Note:** the venv was built inside the old folder path. If Python in the venv fails after the move, report the exact error. Do not patch around it.
7. **On-screen checks.**
   - Repeat the rows in `portrait_master_exhaustive.md` PART 6.4 by clicking the real controls, with Chrome in the foreground. Load the workflow fresh from disk.
   - Delete any test presets made during the checks.
   - Do not save the workflow from the page.
8. **Log it.**
   - In `portrait_master_exhaustive.md`, update PART 1 (1.4 / 1.5 locations) to the new place.
   - Add a dated 2026-09-17 entry for the move with the before and after results.
   - Leave the history sections unchanged.
