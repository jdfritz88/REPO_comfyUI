# REPO_comfyUI - Monitor Log

Every monitoring check gets one entry here, whether or not it found anything.

Started 2026-09-18. Before this file existed, ComfyUI-side monitoring was written
into `REPO_koboldccp_sst_tts_media_Monitor_LOG.md`; that file continues for
kobold / launcher / face_training checks.

Times are LOCAL and approximate where marked `~`.

---

## 2026-09-18 ~19:40 - LoRA verification - files on disk
- **Checked:** `ls -la models/loras/faces/`; `find app_cabinet/OneTrainer/_face_runs -name "*.safetensors"`.
- **Result:** Four LoRAs present here, each exactly 128,263,990 bytes, all written 2026-09-18: susana_head_sdxl 01:19, susana_head_body_sdxl 04:53, susana_head_sdxl_pony 06:10, susana_head_body_sdxl_pony 11:55. OneTrainer's run folder holds the same four and no others - no trained LoRA failed to publish.

## 2026-09-18 ~19:41 - LoRA verification - registry cross-check
- **Checked:** `models/loras/faces/_registry.json` against the files.
- **Result:** All four listed, every one `partial: false`, each entry's `trained` stamp matching its file's mtime to the minute. Steps: 3,280 for both head crops, 9,080 for both head_body.

## 2026-09-18 ~19:42 - LoRA verification - byte identity
- **Checked:** sha256 of all 8 files (4 published here, 4 in OneTrainer's run folder).
- **Result:** Each published copy byte-identical to its run-folder original. The publish step is a faithful copy, not a stale one.

## 2026-09-18 ~19:43 - Developer's app cleanliness
- **Checked:** `git -C ../app_cabinet/comfyui status --short --ignored`; find for `*.safetensors` / `*.ckpt` / `*.pt` under it excluding venv; listing of its `models/loras`.
- **Result:** 110 lines, all `__pycache__` (109) plus `venv`. Zero tracked-file changes. No model file of any kind outside venv. Its `models/loras` holds only the developer's empty `put_loras_here` placeholder. Nothing of ours is in the developer's app.

## 2026-09-18 ~19:45 - Path resolution, offline, using ComfyUI's own code
- **Checked:** ComfyUI venv python with `comfy.options.enable_args_parsing()`, `--base-directory`, `--extra-model-paths-config`, then `folder_paths.get_filename_list('loras')` and `get_folder_paths('loras')`.
- **Result:** 11 entries; all four faces LoRAs present under `faces\`. base_path = REPO_comfyUI. Lora search dirs = `REPO_comfyUI\models\loras` and `app_cabinet\Stable_Diffusion_SDXL\models\Lora`. The developer's comfyui folder is not among them.

## 2026-09-18 ~19:47 - Server state before any work
- **Checked:** `Get-NetTCPConnection -LocalPort 8188 -State Listen`; process scan for kobold / comfy / face_tool / ot_train.
- **Result:** Port 8188 NOT listening - ComfyUI down. No launcher process. Face tool interface running as two pythonw processes (PIDs 31160, 16064) - the same blocker the move handoff names for face_training.

## 2026-09-18 ~19:48 - Desktop state
- **Checked:** windows-mcp Screenshot; `Get-Process LogonUI`.
- **Result:** Windows lock screen, "No windows found". LogonUI PID 44980 running - session LOCKED, confirmed rather than inferred.

## 2026-09-18 ~19:58 - Running server sees the LoRAs
- **Checked:** `GET /object_info/LoraLoader` on the live server.
- **Result:** 11 `lora_name` options, four of them the faces entries. Matches the offline resolution entry for entry.

## 2026-09-18 ~20:05-20:15 - Chrome cannot load 127.0.0.1:8188
- **Checked:** claude-in-chrome navigate / get_page_text / read_page against `127.0.0.1:8188`, `localhost:8188`, `/system_stats` and `example.com`; `read_network_requests` on the failed navigation; Chrome policy registry keys (HKLM and HKCU `Software\Policies\Google\Chrome`); Profile 1 content settings for 8188; extension Local Extension Settings, Extension Rules, Extension State; Service Worker database origins.
- **Result:** example.com loads and extracts. Both ComfyUI URLs return an error page, whole-origin, while PowerShell gets HTTP 200 and 20,059 bytes from the same address. The network capture shows only the three `data:` images Chrome's own error page embeds - no document request was dispatched. No Chrome policy keys exist. No content setting blocks that origin; Profile 1 holds ordinary engagement history for it. No blocking rule in extension storage - the single "8188" hit in Extension State is a timestamp inside a keepalive alarm. Service workers registered only for claude.ai, Google, GitHub, Reddit, iCloud.

## 2026-09-18 ~20:20 - Isolating the Chrome failure
- **Checked:** throwaway `python -m http.server` on 127.0.0.1:8899 opened in the extension tab; a proxy on 8891 serving ComfyUI's own bytes; then a clean Chrome launched with its own `--user-data-dir` pointed at `127.0.0.1:8188`, with its History database read and TCP connections inspected.
- **Result:** 8899 loads. 8891 serving ComfyUI's identical bytes loads and the real frontend renders. The clean Chrome profile loads ComfyUI successfully - History records the visit titled "*Unsaved Workflow - ComfyUI" - and held an established TCP connection to 8188. The user's own Chrome (PID 6212) simultaneously held three established connections to 8188. **Conclusion: the block is confined to the Claude-in-Chrome extension's own tabs.** Chrome, the profile, the port, the server and the locked screen are all fine. Remaining cause is a per-site permission inside the extension, which could not be read from its storage.

## 2026-09-18 ~20:30 - Frontend's own node definitions
- **Checked:** through the proxy, `javascript_tool` running the page's `api.getNodeDefs()`.
- **Result:** 1,353 node types; `LoraLoader.lora_name` holds 11 options including all four faces LoRAs. Third independent confirmation, this one from inside the browser.

## 2026-09-18 ~21:05 - Run history, structural
- **Checked:** `GET /history`; per-run submitted graph, node inputs, status.
- **Result:** 7 runs, all `success`. Every one: switch = `trained_face`; shelf `susana_head_sdxl_pony`, `enabled` true, strength 0.9 (1.0 in the newest); `face_mode` and router `mode` both live wires from node 24; zero extra LoRA slots on. Node 4's text reaches the encoder via node 12. Submitted graphs carry 21 nodes, not 32 - the eleven MarkdownNotes are not executable. The strength of 2 seen on screen was never submitted.

## 2026-09-18 ~21:10 - Server log stream
- **Checked:** `GET /internal/logs/raw`; greps of `logs/comfyui.log`.
- **Result:** Endpoint works, 300 entries, carries model loads, sampler step progress and "Prompt executed in 36.89 seconds". No per-node names. 444 `ConnectionResetError [WinError 10054]` entries in comfyui.log - a client dropping sockets abruptly. Noisy, harmless, not cleanly attributable: both a force-closed probe browser and a phone on 5G are candidates.

## 2026-09-18 ~21:40 - Passive WebSocket watcher - FAILED APPROACH
- **Checked:** aiohttp client connected to `ws://127.0.0.1:8188/ws?clientId=...` as a separate client, left listening.
- **Result:** FAILED. Three runs finished while it was connected (21:56, 21:57, 21:59) and it logged zero events. **ComfyUI sends execution events only to the client that submitted the prompt.** Watcher stopped. Nothing was installed into the repo - the script lived in the session scratchpad only. Note for future sessions: a watcher built in an earlier session also caused a real defect (Fix_LOG line 346, a 0.2 s profile.json poller). Check that precedent before adding another.

## 2026-09-18 ~21:20 - Likeness A/B, controlled
- **Checked:** Two runs through the API, identical except the framing words: same checkpoint `cyberrealisticPony_v110`, same LoRA `susana_head_sdxl_pony` at 0.9, seed 777000111, 26 steps, cfg 6, dpmpp_2m / karras, 832x1216, plain negative, plain `LoraLoader` and no custom nodes. Then face bounding boxes measured with `models/ultralytics/bbox/face_yolov8m.pt`.
- **Result:** A headshot: face 484x648 px = **31.03%** of frame. B full body: 104x141 px = **1.46%**. The user's own latest picture: 116x194 px = **2.25%**, and the detector found **2** faces in it. The LoRA was trained on head crops at 1024, so the real frames give it roughly a fivefold linear shortfall. Outputs at `output/likeness_test/`.

## 2026-09-18 ~21:50 - Workflow inspections
- **Checked:** `Freedom_bigLust_SDXL v04.json` and `v05.json` node and link dumps; `Freedom_Face_Competition.json` structure; mtimes of every workflow file.
- **Result:** v05 saved 21:40, 47,502 bytes, 32 nodes, 26 links, wiring byte-for-byte equivalent to v04, switch `trained_face`, shelf `susana_head_sdxl_pony`. v04 last written 2026-09-16 15:16, matching the Portrait Master rebuild window. Competition workflow: 121 nodes, 191 links, 11 labelled SaveImage outputs, all five methods, and a FaceDetailer (node 79) **already wired into Method 5** with image from VAEDecode and model/clip from the Face Shelf - that method still scored 0.044 in the 2026-09-04 competition.

## 2026-09-18 ~22:00 - Capability scan
- **Checked:** full `GET /object_info` scan for face-detail and workflow-execution nodes.
- **Result:** 1,353 node types. FaceDetailer present, `sam_model_opt` confirmed optional, `face_yolov8m.pt` on disk, no `sams` folder. **No node can execute another workflow file as part of a graph** - the only near-match is `ExecuteAllControlNetPreprocessors`, unrelated.

## 2026-09-18 ~22:45 - Lazy evaluation, after restart
- **Checked:** `GET /object_info/FreedomFaceRouter` on the live server after the launcher restarted ComfyUI.
- **Result:** Both `trained_trigger` and `random_appearance` report `lazy=True, forceInput=True`; required is `mode` only. Change is live.

## 2026-09-18 ~22:50 - Lazy evaluation, proven by execution
- **Checked:** Three real runs of a five-node graph (switch -> two string branches -> router -> show text), submitted as our own client so ComfyUI reports per-node `executing` messages.
- **Result:** PROVEN. `trained_face`: switch, router, TRAINED branch, router, show text - RANDOM branch never executed. `random_face`: the mirror image, TRAINED branch never executed. `off`: neither branch executed. The router appearing twice is `check_lazy_status` being asked what it needs before the branch is built. Corollary worth recording: the WebSocket **does** deliver per-node events when we are the submitting client, which is why the 21:40 watcher failed and this did not.

## 2026-09-19 ~23:05 - FaceDetailer research, from source not memory
- **Checked:** ltdrdata's shipped `example_workflows/1-FaceDetailer.json` (node and link dump); his `detailers.md` tutorial page; Impact Pack README; `modules/impact/core.py` `enhance_detail`; `modules/impact/wildcards.py` `process_with_loras`; installed version in `pyproject.toml`; docs.comfy.org for a core FaceDetailer page.
- **Result:** Installed version 8.28.3. The author's written FaceDetailer tutorial is an empty "WIP" heading - his real documentation is the example workflow and the code. That example puts FaceDetailer **after VAEDecode**, fed by the same model / clip / vae / positive / negative as the main KSampler. `enhance_detail` computes `upscale = guide_size / min(bbox_w, bbox_h)`, then clamps by `max_size` against the whole crop, so **max_size, not guide_size, is usually the binding constraint**. The node's `clip` input is used ONLY by `process_with_loras` (core.py:268, 441) - with the wildcard box empty it does nothing. No official ComfyUI documentation exists; it is a third-party node.

## 2026-09-19 ~23:10 - clip-L / clip-G / pivotal, established from code and files
- **Checked:** `comfy_extras/nodes_clip_sdxl.py`; `comfy/sdxl_clip.py` and `comfy/sd1_clip.py` embedding key handling; safetensors headers of `susana_head_sdxl` and `susana_head_sdxl_pony`; `models/embeddings/`.
- **Result:** clip-L uses `embedding_size=768, embedding_key='clip_l'`; clip-G uses `1280 / 'clip_g'` - a pivotal token is two vectors, resolved at tokenize time, entirely upstream of any CONDITIONING. Both LoRAs already train both encoders: **te1 (CLIP-L) 216 tensors, te2 (CLIP-G) 579, unet 2382, embeddings 0**. `models/embeddings/` holds only ComfyUI's placeholder, so **no pivotal tuning exists in this pipeline today**. FaceDetailer's wildcard box re-encodes with plain `CLIPTextEncode`, so it cannot carry a split clip-G/clip-L prompt.

## 2026-09-19 ~23:30 - FaceDetailer installed into v05, validated
- **Checked:** backup of v05 to the session scratchpad; a 292-assertion validator run against the live server's `/object_info` - node types known, every link endpoint consistent both ways, every link type accepted by the target input, the intended wiring, the switch default, detailer sampler settings matched to STEP 10, `face_yolov8m.pt` offered by the server, and `ImpactConditionalBranch` inputs reported lazy.
- **Result:** 292/292 passed. Added #33 UltralyticsDetectorProvider, #34 FaceDetailer, #35 PrimitiveBoolean (default true), #36 ImpactConditionalBranch and #37 MarkdownNote. VAEDecode now feeds the detailer and the branch's OFF side; the branch feeds both the preview and the auto-save. One real defect was found and fixed during conversion, not in the workflow but in my own graph-to-API converter: the frontend adds a `control_after_generate` widget for any INT named `seed` even though the server spec does not advertise it, which had shifted every FaceDetailer value after the seed.

## 2026-09-19 ~23:40 - Switch proven by execution, not by inspection
- **Checked:** two real runs of the edited v05 graph submitted as our own client so per-node `executing` events are delivered; then a pixel comparison of the two outputs and a YOLO face measurement of each.
- **Result:** PROVEN. Switch ON: detector and FaceDetailer both executed, 48.9 s. Switch OFF: **neither executed**, 17.8 s - the lazy branch genuinely skips the work rather than discarding it. Outputs differ in 5.36% of pixels against a face box occupying 4.67% of the frame; mean change inside the face box 23.7, outside it 0.1, so the repaint is confined to the face. NOT verified: that the repaint improves likeness - a crude mean-gradient measure of the face went 6.77 (off) to 6.29 (on), i.e. slightly smoother rather than sharper, and likeness was not measured.

## 2026-09-24 07:48:06 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[10928, 23188]

## 2026-09-24 ~07:47 - CP1 baseline sweep - STEP 0B tool verification
- **Checked:** `tabs_context_mcp` (read-only, no tab created) and windows-mcp `Screenshot`.
- **Result:** Both respond. Chrome MCP group holds one tab, id 1273371540, `http://localhost:8188/`, title "localhost" (the known extension error page). Screenshot shows the desktop: File Explorer on REPO_comfyUI and two terminal windows (main Claude session, launcher). No ComfyUI window visible.

## 2026-09-24 ~07:47 - CP1 baseline sweep - ComfyUI log buffer (full)
- **Checked:** `GET /internal/logs/raw`, all 111 entries, 07:39:48 to 07:45:51.
- **Result:** No ERROR lines, no tracebacks, no "IMPORT FAILED"; all 26 custom nodes listed in the import-times block. WARNINGs: (1) Impact Pack SAM2-unavailable warning, emitted TWICE at 07:40:09.450 and 07:40:09.471; (2) three [DEPRECATION WARNING] lines at 07:45:51.319/.325/.325 for `/scripts/ui.js`, `/extensions/core/clipspace.js`, `/extensions/core/widgetInputs.js`. INFO-level only: triton unavailable, `OpenGL_accelerate` missing.

## 2026-09-24 ~07:48 - CP1 baseline sweep - launcher stdout log
- **Checked:** `REPO_koboldccp_sst_tts_media/logs/comfyui.log` from the `===== ComfyUI started 2026-09-24 07:39:47 =====` marker (line 14220) to end; `launcher_20260924_073927.log`. Launcher sends ComfyUI stdout+stderr to that file (launcher.py:521-529, Service.start).
- **Result:** Identical content to the log buffer, nothing extra, no stderr-only output. Launcher log: option 4 chosen 07:39:45, "ComfyUI: starting ........ healthy" 07:39:47-07:40:13, no errors.

## 2026-09-24 ~07:48 - CP1 baseline sweep - deprecated-import trace
- **Checked:** grep of every custom_nodes `*.js/*.mjs/*.ts/*.html` for the three paths; `server.py:82-99` deprecation middleware; `GET /extensions` (58 files served).
- **Result:** Importers: `ComfyUI-Impact-Pack/js/impact-pack.js:2`, `impact-sam-editor.js:3`, `impact-segs-picker.js:2` (`../../scripts/ui.js`); `impact-sam-editor.js:5` (`../../extensions/core/clipspace.js`); `ComfyUI-VideoHelperSuite/web/js/VHS.core.js:3` (`../../../extensions/core/widgetInputs.js`). All four files are in the served `/extensions` list. Middleware warns once per path per server run, so the 07:45:51 lines mark the first frontend load after start.

## 2026-09-24 ~07:48 - CP1 baseline sweep - SAM2 double warning trace
- **Checked:** `Impact-Pack/modules/impact/core.py:31-37`, `__init__.py:17-60`, relative imports in modules/impact; `find_spec('sam2')` in the ComfyUI venv.
- **Result:** sam2 not installed (spec None). Warning is module-level in core.py:37. core.py is loaded under two module names: `impact.core` (absolute, via `sys.path.append(modules_path)`) and the package-relative name via `impact_pack.py:28 from . import hooks` -> `hooks.py:5 from . import segs_nodes` -> `segs_nodes.py:7 from . import core`. Upstream author's own note at `bridge_nodes.py:11-13` confirms 'from .' and 'from impact' give different core modules. Traced from source; not confirmed by inspecting live sys.modules.

## 2026-09-24 ~07:49 - CP1 baseline sweep - queue / history / system_stats / GPU
- **Checked:** `/queue`, `/history?max_items=200`, `/system_stats`, `nvidia-smi`.
- **Result:** Queue empty, history empty (no prompts run this server session, so no failed prompts). Package versions all match required. VRAM free 11.6 of 12.3 GB; nvidia-smi: 45C, P8, 0% util, PID 23188 the only compute process. Nothing unusual.

## 2026-09-24 ~07:49 - CP1 baseline sweep - Windows Application event log (24 h, IDs 1000/1001/1002)
- **Checked:** Get-WinEvent Application, since 2026-09-23 ~07:49.
- **Result:** No python.exe crash. No chrome.exe APPCRASH; one chrome.exe `RADAR_PRE_LEAK_64` (WER memory-leak pre-detection report, not a crash) 2026-09-23 23:26:01 (dwm.exe 23:21, explorer.exe 23:16 same type). Unrelated crashes: RtkAudUService64.exe c0000005 21:46; OVRServer_x64.exe c0000409 21:42; Dell ServiceShell.exe c0000005 18:04; WindowsWcpOtherFailure3 x5 11:43. No ID 1002 (hang).

## 2026-09-24 ~07:49 - CP1 baseline sweep - connections to port 8188
- **Checked:** `netstat -ano` for :8188; process lookup of the client PID.
- **Result:** Six ESTABLISHED connections to `100.65.32.118:8188` from PID 26776 = chrome.exe NetworkService utility process (created 07:38:12). So some Chrome tab has ComfyUI open on the Tailscale address. Five ESTABLISHED on 127.0.0.1:8188 plus a run of TIME_WAIT (client PIDs not resolved on the server side lines).

## 2026-09-24 ~07:49 - CP1 baseline sweep - other passive logs / backup
- **Checked:** `REPO_comfyUI/_freedom_comfy.log` mtime; `REPO_comfyUI_Fix_LOG.md`; `F:/Apps/freedom_system/REPO_comfyUI BACKUP`.
- **Result:** `_freedom_comfy.log` last written 2026-09-04 02:10 - not from this session, not read further. No Fix log exists. **REPO_comfyUI BACKUP folder does not exist** - per the run's hard limit, CP1 stopped here without copying; Technique 2, Technique 3 and Monitoring Check C were NOT run.

## 2026-09-24 08:15:22 - live watch - comfyui
- **Checked:** live stream
- **Result:** server not answering: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>

## 2026-09-24 08:15:34 - live watch - process
- **Checked:** live stream
- **Result:** pid 10928 GONE

## 2026-09-24 08:15:34 - live watch - process
- **Checked:** live stream
- **Result:** pid 23188 GONE

## 2026-09-24 08:17:03 - live watch - comfyui
- **Checked:** live stream
- **Result:** server answering again

## 2026-09-24 08:17:03 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [INFO] Found comfy_kitchen backend triton: {'available': False, 'disabled': True, 'unavailable_reason': "ImportError: No module named 'triton'", 'capabilities': []}

## 2026-09-24 08:17:03 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [WARNING] 
----------------------------------------------------------------------------
[Impact Pack] The SAM2 functionality is unavailable because the `facebook/sam2` dependency is not installed.

Installation command:
F:\Apps\freedom_system\app_cabinet\comfyui\venv\Scripts\python.exe -m pip install git+https://github.com/facebookresearch/sam2
----------------------------------------------------------------------------

## 2026-09-24 08:17:03 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [WARNING] 
----------------------------------------------------------------------------
[Impact Pack] The SAM2 functionality is unavailable because the `facebook/sam2` dependency is not installed.

Installation command:
F:\Apps\freedom_system\app_cabinet\comfyui\venv\Scripts\python.exe -m pip install git+https://github.com/facebookresearch/sam2
----------------------------------------------------------------------------

## 2026-09-24 08:17:30 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 08:30:33 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:30:33 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:31:18 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:31:18 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:31:18 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:32:25 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:32:56 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:34:38 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:34:38 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:34:38 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:36:36 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:36:36 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:37:51 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:37:51 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:45:58 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:45:58 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:47:34 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 08:48:00 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:49:23 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 08:49:23 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 09:17:39 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 09:28:39 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()
handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
Traceback (most recent call last):
  File "F:\Apps\Python\Lib\asyncio\events.py", line 89, in _run
    self._context.run(self._callback, *self._args)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\Apps\Python\Lib\asyncio\proactor_events.py", line 165, in _call_connection_lost
    self._sock.shutdown(socket.SHUT_RDWR)
    ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
ConnectionResetError: [WinError 10054] An existing connection was forcibly 

## 2026-09-24 09:47:43 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 10:02:12 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [WARNING] [DEPRECATION WARNING] Detected import of deprecated legacy API: /scripts/ui.js. This is likely caused by a custom node extension using outdated APIs. Please update your extensions or contact the extension author for an updated version.

## 2026-09-24 10:02:12 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [WARNING] [DEPRECATION WARNING] Detected import of deprecated legacy API: /extensions/core/clipspace.js. This is likely caused by a custom node extension using outdated APIs. Please update your extensions or contact the extension author for an updated version.

## 2026-09-24 10:02:12 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [WARNING] [DEPRECATION WARNING] Detected import of deprecated legacy API: /extensions/core/widgetInputs.js. This is likely caused by a custom node extension using outdated APIs. Please update your extensions or contact the extension author for an updated version.

## 2026-09-24 10:17:47 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 10:47:52 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 11:17:56 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 11:48:00 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 12:18:04 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 12:48:08 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 13:18:12 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 13:48:16 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 14:18:20 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 14:48:25 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 15:18:29 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 15:48:33 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 16:18:37 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 16:48:41 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 17:18:46 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[22216, 31676]

## 2026-09-24 17:35:21 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[37908, 33780]

## 2026-09-24 17:39:58 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [WARNING] [DEPRECATION WARNING] Detected import of deprecated legacy API: /scripts/ui.js. This is likely caused by a custom node extension using outdated APIs. Please update your extensions or contact the extension author for an updated version.

## 2026-09-24 17:39:58 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [WARNING] [DEPRECATION WARNING] Detected import of deprecated legacy API: /extensions/core/clipspace.js. This is likely caused by a custom node extension using outdated APIs. Please update your extensions or contact the extension author for an updated version.

## 2026-09-24 17:39:58 - live watch - comfyui-log
- **Checked:** live stream
- **Result:** [WARNING] [DEPRECATION WARNING] Detected import of deprecated legacy API: /extensions/core/widgetInputs.js. This is likely caused by a custom node extension using outdated APIs. Please update your extensions or contact the extension author for an updated version.

## 2026-09-24 18:05:26 - live watch - watcher
- **Checked:** live stream
- **Result:** started; pids=[37908, 33780]
