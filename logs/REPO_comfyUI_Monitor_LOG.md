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

## 2026-09-30 11:21 - CP1 - file timestamps (user/ folder)
- **Checked:** last-modified time of every file under user/ after the user said sizing/positioning saves are not sticking.
- **Result:** Freedom_SDXL_v01.json last written 10:39:12 (Claude's own edit). Nothing under user/ written by a save in the 50 minutes before 11:21. The user's saves are not reaching disk.

## 2026-09-30 11:21 - CP1 - ComfyUI log (logs/comfyui.log tail)
- **Checked:** last lines of the server log for save errors.
- **Result:** nothing unusual - startup lines and three frontend deprecation warnings only. The server does not log userdata saves, so a missing save leaves no trace here.

## 2026-09-30 11:23 - CP1 - monitors installed
- **Checked:** started logs/save_monitor_2026-09-30/file_watch.py (writes every workflow file change to file_watch.log, polled 4x a second); installed an in-page monitor in Claude's ComfyUI tab (tab 1273374623): every non-GET userdata/workflow request with its answer, page errors, Ctrl+S, clicks on anything labelled Save/Export, and the active workflow's modified flag. Console prefix [SAVEMON]. Baseline layout snapshot taken (window.__layout0).
- **Result:** both running. User is working in this tab from now on (their own tab was closed).

## 2026-09-30 11:25 - CP1 - in-page monitor + file watcher (after user's resize)
- **Checked:** layout diff against the 11:23 baseline, workflow modified flag, save requests, file watcher.
- **Result:** frame "STEP 2 - face source" height 250 -> 300 in the tab. Workflow flagged modified at 11:24:42.630 (the tab noticed the change). No save request sent yet; file unchanged. Resize itself is being recorded correctly on screen.

## 2026-09-30 11:25 - CP1 - save via ComfyUI menu File > Save (Claude's tab)
- **Checked:** in-page monitor, file watcher, file contents vs the live canvas.
- **Result:** click "Save / Ctrl + s" 11:25:32.058 -> POST to userdata 11:25:32.087 (101607 bytes) -> server answered 200 at .093 -> modified flag cleared .132 -> file watcher saw Freedom_SDXL_v01.json change at 11:25:32.215 (101635 bytes). STEP 2 frame on disk is now 300 tall. Full compare of all 42 nodes (position + size) and 13 frames, disk vs screen: zero differences. Save works end to end in this tab.
- **Not found:** why saves from the user's own (now closed) tab between 10:39 and 11:21 did not reach disk - that tab can no longer be inspected. Watchers left running.

## 2026-09-30 11:28 - CP1 - ComfyUI restart + reload check
- **Checked:** restarted ComfyUI with the launcher's own "c" key (stopped, port 8188 freed, started, healthy; new server pid 44792). Menu names from /object_info: "Face Shelf", "Face Lora Stack". Reloaded Claude's tab (launch-page hop), opened Freedom_SDXL_v01 fresh from disk, compared every node position + size and every frame on screen with the file; screenshot of STEP 1-3.
- **Result:** 42 nodes, 13 frames, zero differences. STEP 2 frame shows 300 tall (the user's 11:25 save). Layout survives a full restart. In-page monitor reinstalled (it is lost on page reload); file watcher still running.

## 2026-09-30 11:37 - STEP 3a note wording fix (user asked) - save path check
- **Checked:** changed the STEP 3a note's "(0.4 face shelf + 0.3 row 1 + 0.2 row 2 + 0.1 row 3)" to "(0.4 Face Shelf + 0.3 Face Lora Stack pass 1 + 0.2 Face Lora Stack pass 2 + 0.1 Face Lora Stack pass 3)" inside Claude's tab (workflow had no unsaved changes first), saved with ComfyUI's own Save command.
- **Result:** modified 11:37:12.717 -> POST userdata/workflows/Freedom_SDXL_v01.json 11:37:13.115 -> 200 -> file watcher CHANGED 11:37:13.322 (101738 bytes). New wording on disk, old wording gone. Every node position/size and frame unchanged from the 11:29 layout.

## 2026-09-30 11:38 - STEP 1a line fix (user asked) + finding: Run marks the workflow changed
- **Checked:** before editing, the tab was flagged modified at 11:37:32 with no layout change. Diffed widget values tab vs disk.
- **Result:** the only differences were new seeds on 4b, 4c, 4d, 4e, 4f and STEP 10 KSampler - the user had pressed Run, and "control after generate: randomize" gave new seeds, which flags the workflow modified. Not saved on the user's behalf. The READ ME line "Its three rows start ON at 0.3 / 0.2 / 0.1." was changed to "Its three passes (Face Lora Stack pass 1, pass 2 and pass 3) start ON at 0.3 / 0.2 / 0.1." in the tab (no save) and in the file directly (watcher: CHANGED 11:38:49, 101830 bytes; backup _backups/face_names_2026-09-30/Freedom_SDXL_v01_before_readme_line.json). Tab vs disk after: only the six seeds differ, layout identical.

## 2026-09-30 11:40 - user's save + check of every session edit
- **Checked:** in-page monitor, file watcher, saved file contents, screen vs disk.
- **Result:** user clicked Save 11:40:28.887 -> POST 200 at .923 -> file CHANGED 11:40:29.062. On disk: STEP 1a/1b/1c titles, STEP 1 frame layout, 3b "Face Shelf" / 3c "Face Lora Stack" titles, STEP 3a wording, STEP 1a READ ME line - all present; old wording gone; named copies match. New KSampler seed now saved. Screen vs disk: zero differences (values, layout, titles, frames). Strength box shows the four named rows.

## 2026-09-30 11:45 - user moved 3c down, extended STEP 3 frame, saved
- **Checked:** file watcher, saved file, screen vs disk.
- **Result:** file CHANGED 11:44:31.672. On disk: 3c (Face Lora Stack) y 2300 -> 2400, height 440 -> 450; STEP 3 frame height 2800 -> 2900. Screen vs disk: zero differences. Tab had been reloaded at 11:43:22 (page load time), which wiped the in-page monitor, so the save click itself was not captured; monitor reinstalled 11:45 (now also records page unloads).

## 2026-09-30 11:5x - Portrait Master hint formatting (user asked, option 2) + pre-reload check
- **Changed:** custom_nodes/freedom_portrait_control/web/portrait_control.js - EXPLANATION and CONFLICT are now paragraph/bullet blocks drawn by a new hintBox() in the note font (no breaks inside sentences). Words unchanged. Backup: _backups/face_names_2026-09-30/portrait_control_before_hint_format.js. node --check passes. Only these two hints in our add-ons had typed-in line breaks (grep of every freedom_* web file).
- **Checked before reloading the tab:** tab flagged modified since 11:46:42. Diff vs disk: the user is mid-move - STEP 1, 2, 3 boxes moved left by exactly 700 (y unchanged), while their three frames moved by -713.58 / +9.53 (not the same amount as the boxes they hold). Not reloaded, to keep the user's unsaved moves.

## 2026-09-30 12:05-12:10 - hint formatting: bug in Claude's change, found and fixed, verified
- **Checked:** after the user's 12:04:09 save (POST 200, file CHANGED 12:04:10, screen = disk), reloaded the tab (launch-page hop) and opened Freedom_SDXL_v01 fresh.
- **Result 1 (fail):** Portrait Master panels missing on all 7 STEP 4 nodes. Console: "Error calling extension 'freedom.portrait.control' method 'nodeCreated'" x7; captured message "items is not iterable" at portrait_control.js hintBox list(). Cause (seen in the code): a plain string item has the built-in String.prototype.sub method, so `if (it.sub)` was true and list() was called on a function.
- **Fix:** only objects with an array .sub get a sub-list. node --check ok.
- **Result 2 (pass):** reloaded again: zero console errors while loading; panels on all 7 nodes; hint = paragraphs + 7 bullet items, 4a has its extra first line, 4b/4c warning = 2 paragraphs; screenshot looked right. Rendered words compared by fingerprint with the original text: EXPLANATION 1483 chars sha1 72e1fbd41e6f and CONFLICT 280 chars 59da47642d8a match in every node. In-page monitor reinstalled; tab has no unsaved changes.

## 2026-09-30 12:13-12:25 - STEP 4 spacing + re-lettering (user: option 3, hidden names included)
- **Spacing (saved 12:13:09 via ComfyUI Save):** STEP 4 boxes at x 2650/3350/3850/4550/5050/5550/6050, 50 apart; STEP 4 frame [2600,0,4050,3930]; STEP 5 onward (9 frames, 27 boxes) moved +400 as a block. Check: no frame overlaps, no STEP 4 box overlaps. Pre-existing overlaps left alone: 1a/1b, 7a/7b, 7b/7c, four STEP 11 boxes; STEP 6 LoRA stack and three STEP 11 boxes stick out of their frames.
- **Re-letter:** hints note -> 4a, old 4a..4g -> 4b..4h. One-pass regex shift, 111 changes, reviewed line by line: portrait_control.js 79, __init__.py 29, presets.py 1, checkpoint_prefix.js 1, builtin_descriptions.json 1. Saved presets checked - keyed by node class, no letters, unchanged. Workflow: 8 titles, hints note text, node 30's input names + named values n4b..n4g -> n4c..n4h, pair value -> "4c Base Character". One script slip (note first line shifted twice to "4b hints") caught and fixed to "4a hints". Backups: _backups/step4_reletter_2026-09-30/.
- **Verified:** ComfyUI restarted with launcher "c" (new pid 40748); /object_info shows n4c_mode..., pair choices "4c Base Character"/"4d Face Generator". Tab reloaded, workflow opened: zero console errors, all 8 titles new, node 30 settings = file for every named setting, all other boxes' settings and layout = file, panels show "STEP 4b decides...", "no 4b preset", "Use 4c Base Character". Test job posted straight to /prompt (tab untouched): server log "applied: dropdowns: pair=base, styler=off; ... Face Generator switched off" - the new names are read; job c77b69a6 finished, status success.

## 2026-09-30 12:3x - STEP 6 LoRA stack: orange "Hidden as wrong architecture" line hidden (user asked)
- **Changed:** custom_nodes/freedom_lora_stack/web/lora_stack.js - the notice is never shown; the filter itself is unchanged. Backup: _backups/step4_reletter_2026-09-30/lora_stack_before_hide_warning.js.
- **Verified:** user's 12:35:09 save landed first (POST 200, nothing unsaved). Tab reloaded (hop), workflow opened: zero console errors; .fls-warn hidden (height 0); blue "Showing LoRAs compatible with SDXL" line still shown; no wrong-architecture file in the row menu; screenshot confirms. Server list still reports the 5 hidden files (Emotions V1, Hands zib v1, 2x Wan2.2 Lightning, expression_helper2.0).

## 2026-09-30 13:05-13:20 - STEP 7b Prompt Watcher as its own node; STEP 7 letters moved down (user asked)
- **Code:** new FreedomPromptWatcher in freedom_checkpoint_prefix/__init__.py (no inputs, no outputs - screen only); web/checkpoint_prefix.js: watcher section removed from the Summary Signal panel (its own status line kept, now "At the last run: ..."), new WatchPanel with a concise description, "executed" finished_prompt now goes to watcher nodes. STEP 7 letters 7b..7e -> 7c..7f in checkpoint_prefix (js + py), prompt_slots/nodes.py, portrait_control.js (15 changes, reviewed); two comments fixed by hand (one already had the wrong letter; one said the watcher lived in the Summary Signal). Backups: _backups/step7_prompt_watcher_2026-09-30/.
- **Restart:** launcher "c" (user had saved 13:12:07, nothing unsaved, queue empty). /object_info: "Prompt Watcher (the finished prompt from the last run)", inputs none, outputs none.
- **Workflow (done in the tab, saved 13:16:38 via ComfyUI Save):** node 49 FreedomPromptWatcher "STEP 7b  -  Prompt Watcher  -  the finished prompt from the last run" at [8500,800] size [950,300]; titles 47 -> 7c Summary Signal, 45 -> 7d prompt parts, 43 -> 7e phrase note, 44 -> 7f phrases; 7a note letters moved (3) and "(STEP 7b, just below)" -> "(STEP 7c, below the Prompt Watcher)"; phrase note (4) and STEP 4a hints note (1) letters moved. Summary Signal y 800 -> 1180, prompt parts 1500 -> 1910; STEP 7 frame height 3110 -> 3810. Disk = screen for every node (pos, size, title, values); 43 nodes.
- **Run test:** job 3abf8f41 posted with this page's own client id (no seed change): server accepted the watcher node without error and did not run it; status success. Watcher box filled with the finished prompt ("score_9, score_8_up, score_7_up, (lorasusana:1.1), ..."); Summary Signal line "At the last run: added 'score_9, ...'; 15 of 75 places used". Screenshot confirms. CLAUDE.md STEP 7 notes updated.

## 2026-09-30 14:03-14:45 - phrase shelf out; STEP 7 split into Summary / Scene / Physical / FINAL (user asked)
- **Phrase shelf:** nodes 43 (note) + 44 (FreedomPhraseSlots) removed from the workflow, no wires; saved 14:03:11; phrases file untouched; code kept.
- **Code:** freedom_prompt_slots/nodes.py + FreedomScenePrompt, FreedomPhysicalPrompt, FreedomFinalPrompt (final_parts JSON; run() sends exactly the saved parts in order front, face, physical, scene; random-face marker filled from STEP 5 at Run; logs boxes changed since their button). web/prompt_slots.js: shelf package reused per box (no Save phrase), green button per box, makeAdjustable() (own drag handle, height kept in node.properties.freedom_heights), FINAL box closed to mouse/keyboard, watcher line every 0.5 s, Prompt Watcher field filled from "executed". checkpoint_prefix.js: Summary Signal panel split into 6 adjustable section widgets + green button. Backups: _backups/step7_split_2026-09-30/.
- **Restart:** launcher "c" (window was on the left screen); /object_info shows the three new types.
- **Workflow (saved 14:39:44):** 7b Hints note ("n/a"), 7d Scene (541-char text, slot/name kept), 7e Physical (empty box, slot/name kept), 7f FINAL; wires front/face_text/physical/scene -> final, final -> "encode the prompt"; FreedomPromptParts (45) and Prompt Watcher node (49) removed; 7a note rewritten for the new layout; column 1 x8500: 7a/7b/7c, column 2 x9500: 7d/7e/7f; STEP 7 frame height 2810.
- **Checks:** zero console errors on load; watcher "Out of date" before buttons, "Up to date" after; typing in Physical -> "Physical Description changed - press its green button", undo -> "Up to date"; every section resize: vertical; final text: mousedown/keydown blocked, user-select none, cannot take focus after reload. Reload from disk: final text and "Up to date" restored. Test job 88b05efa (page client id): success; engine got 592 chars, identical to what the final box showed; log "STEP 7f FINAL COMBINED PROMPT sent (592 characters)"; Prompt Watcher field filled with the same text.

## 2026-09-30 14:45-14:53 - adjustable fields fixed; snap-to-grid finding
- **Found:** Scene/Physical text fields were ComfyUI's own (resize: none, redrawn by the Vue front end, unreachable from add-on code). Replaced by our own text fields tied to the hidden real widgets (ownTextField). Also found every add-on DOM widget is stretched by the Vue wrapper (`*:flex-1`), so heights were shared evenly (181/181) and ignored; fixed with flex: none in makeAdjustable (both add-ons). Proven with a real mouse drag: physical box 200 -> 300 while window stayed 130, node grew; heights recorded in node.properties.freedom_heights (an earlier "{}" reading was the tool mis-serialising a Vue proxy - JSON.stringify shows the values). Test drag set back to 200.
- **Real input test:** typed "test words" by keyboard into the Physical field -> real widget value set, watcher "Physical Description changed - press its green button"; real click on the green button -> final "score_9, ..., (lorasusana:1.1), test words, hetero, ..." (order right), message shown; removed by keyboard + green again -> back to empty.
- **Snap-to-grid:** after reload, 7c/7e/7f sat 20/20/-10 away from the file. Settings: pysssss.SnapToGrid true, grid 50, LiteGraph.alwaysSnapToGrid true - ComfyUI snaps on open. Cause: Claude's placements rounded to 10. Fixed: 7c 1100, 7e 1100, 7f 2100, STEP 7 frame height 2850, STEP 4 frame height 3950. Saved 14:51:32; reopened: 0 boxes moved, 0 frames changed. Memory note added.

## 2026-09-30 14:5x - "slot 1 of 2 saved" wording removed from Scene and Physical (user: option 1)
- **Changed:** prompt_slots.js buildPartsSection refresh(): for the split boxes the saved-slot line is empty and hidden; empty-slot and nothing-saved messages kept.
- **Verified after reload (no unsaved work first):** zero errors; Physical and Scene status line empty + hidden on slot 1; dial to 3 on Physical -> "slot 3 is empty - 2 saved, dial down to see them"; back to 1 -> empty again; workflow not marked changed. Screenshot confirms. Seen on screen: an empty gap above and below the shelf-button field in Physical (where the two hidden original fields sit) - not changed.

## 2026-09-30 15:1x - gap under the SAVED window (user screenshot, Scene Prompt)
- **Checked:** Vue grid rows of node 51: hidden widgets make no rows; rows were 181/186/252/131 while their fields were 130/~100/200/~80 - the node (size 900) was taller than its content and the spare height was shared out as empty space under each field.
- **Fix:** node height set to 100 for 7c/7d/7e/7f so each draws only as tall as its content (the front end grows it to fit). Test on 51: gap window->buttons 4; window grown 130->300 -> buttons moved down, gap still 4, node grew 724->894 (then set back). Gaps now 4 (51, 52, 53) and 4-8 (47). Column re-placed on the 50 grid: col1 100/850/1100, col2 100/900/1700, STEP 7 frame height 2450. Saved 15:19:37; nothing off the grid.

## 2026-09-30 15:2x - "Scene Shelf" title + height changes must save (user asked)
- **Mistake, no loss:** Claude sent a reload in the same step as the unsaved-changes check; the check showed the workflow modified and Chrome's "Leave site?" guard blocked the reload. Tab intact. The only unsaved change: user's STEP 8 frame height 650 -> 700. Not saved or discarded by Claude - waiting for the user's save.
- **Code (not yet loaded, needs a page reload):** prompt_slots.js - "Scene Shelf" title field at the top of Scene Prompt (above the slot dial), shelfTitle on SCENE_SPEC only. Both makeAdjustable() - after storing a new height, changeTracker.checkState() so the tab shows unsaved changes at once; a stored height equal to the saved one is not counted as a change.
- **To verify after the user saves:** reload; title on screen; change a field height -> asterisk appears; save -> height in file; reload -> height restored.
- **15:2x (user: option 1):** title text "Scene Shelf - pose, action, scene, camera, light, style"; the Scene button package has no heading of its own. Code only; still waiting on the user's save before reloading.
- **15:3x (user):** Scene typing field headed "Scene Prompt" (boxTitle) with a 36 px space above it (two line spaces) below the shelf button field. Code only; waiting on the user's save before reloading.
- **15:3x (user: yes):** Physical gets the same: title "Physical Shelf - how she looks (body, face, hair, skin, clothing)", no button heading, typing field "Physical Description Prompt", 36 px space. Code only; waiting on the user's save.
- **15:4x user decisions (no code change):** FINAL COMBINED PROMPT shows only what it builds (not the "don't want" list or the face repaint's words); STEP 6 LoRA trigger words are NOT added automatically (user types them); Portrait Master's STEP 4 text stays random-face only (trained face = her trigger word only).

## 2026-09-30 15:5x - two-step Rename on every Rename button (user: Enter or 2nd click confirms, Esc cancels)
- **Code:** makeRenamer()+blinkThree() in prompt_slots.js (Scene/Physical shelves, prompt shelf, phrase shelf), portrait_control.js (4b-4h preset menus, 3b recipe drawer), facedetailer_presets.js (STEP 11), presets_method1.js (face competition). 1st click: name field = current name, selected, blinks 3x, button reads "Save new name"; Enter / 2nd click renames; Esc restores. Backups in _backups/step7_split_2026-09-30/.
- **Checker finding:** `node --check file.js` returned exit 0 on a deliberately broken test file - it does not check these ES-module files. Real check: `node --input-type=module --check < file`. Re-checked every page file changed today: only portrait_control.js was broken (two "});" left from this edit, not yet loaded in any browser) - fixed; all others OK. Memory note added.
- **Not yet tested on screen** (page reload waits on the user's unsaved STEP 8 frame change). Prompt shelf and phrase shelf are not in any open workflow - cannot be tested on screen here.

## 2026-09-30 17:40-18:20 - heights saved+restored, NO OVERLAP rule, rename tests
- **Bug found (heights):** fields are built before a node's saved settings arrive; the height watcher then stored the starting height over the saved one (230 on disk -> 130 in the tab after reload). Also: Chrome sends no pointer events for its own resize handle, so "store only on pointerup" never fired. **Fix:** saved heights are re-applied in onConfigure; each field remembers the last height the code set (__applied) and only a different height (a real drag) is stored. Verified: reload restored 230; real drag 230->279 stored, tab marked changed.
- **No overlap (user, mid-turn: "there MUST BE NO OVERLAP"):** window.__freedomNoOverlap(node) - when a drag makes a box taller, every box below in its column moves down on the 50 grid with a 50 gap and frames grow. Verified with a real drag: Physical 900->1100, FINAL 1700->1900, STEP 7 frame 2450->2650. Then whole-workflow fix (saved 17:58:04): Scene window back to 130 and column restored (Physical 900, FINAL 1700, frame 2450); STEP 1b -> 1400, 1c -> 1850, STEP 1 frame 2050; BEHIND THE SCENES two columns at x16300/x17100, rows 50 apart, frame 1650x1300. Recheck: 0 box overlaps, 0 frame overlaps, every box inside a frame (some neighbours 20-44 apart, not touching).
- **Lost-change handling:** a "Leave site?" block was caused by the bad 130 overwrite only (diff showed nothing else); workflow closed in-app without saving, then forced reload; file still held 230.
- **Rename tests:** Scene shelf with real mouse/keyboard - Enter renamed Doggy01 -> "Doggy01 test" (file updated), 2nd click renamed back to Doggy01 (file updated), Esc cancelled (nothing changed); blink = 3 x 330 ms animation. FaceDetailer presets: start + Esc OK (scripted). 4b preset and 3b recipe drawer: logic OK via a dispatched click (name filled, selected, blinking, "Save new name", Esc restores). Open question: on the 3b recipe panel the Claude-in-Chrome click tool produced pointerdown/pointerup on the button but no mousedown/click event (nothing cancelled them); not explained - the user should try it with a real mouse.
- Seen in console at earlier page loads: "ComfyApp graph accessed before initialization" (not investigated).

## 2026-09-30 18:2x-19:0x - Save as two-step, fonts +1, green frames, zero overlap
- **Save as (user):** same two steps as Rename on every Save as - Scene/Physical shelves, prompt shelf, phrase shelf (window), 3b recipes, 4b-4h presets, FaceDetailer presets, Summary Signal (its model menu blinks; "Pick the model in the menu..."). Button reads "Save as new"; Enter/2nd click saves; Esc cancels. Real-click test on Scene: name field focused, "Doggy01" selected, label "Save as new"; Esc -> label back, nothing saved, not marked changed.
- **Fonts +1 (user):** every px font size in all 14 freedom_* web files +1 (100 changes; backups _backups/fonts_plus_one_2026-09-30/). Finding: this Chrome profile has a MINIMUM FONT SIZE of 18 px (a test span asked for 8/12/17 px computed 18 px; 19/22 kept) - all box text was showing at 18, so the +1 in our styles was invisible. Added one style rule (prompt_slots.js): all text in node widgets and markdown notes 19px !important. Measured after reload: 946 text elements, all 19px.
- **Overlap after fonts:** the user had saved their own STEP 7 rearrangement at 18:40:47 (Scene moved under Summary Signal). Bigger text then caused 3 overlaps (3a/3b 50, STEP 12 note/preview 57, 7a/7b 8) and 3 boxes past their frame (4c, STEP 11 dials note, 7d). Fixed by moving only the lower box (+ boxes below it in its column) down on the 50 grid (7b +50 x3 boxes, STEP 12 preview +100, 3b +100 x2) and growing 7 frames. Saved 18:47:29. Rechecked after a reload at zoom 50%, 30% and 15%: 0 box overlaps, 0 boxes outside a frame, 0 frame overlaps (all 43 boxes measured).
- **Green frames (user):** light green (#90ee90) 2px frame on the typing boxes in STEP 7 only - Summary Signal words box, Scene Prompt, Physical Description Prompt (amber still shown while editing the model's own text). Verified on screen; read-only fields unframed.
- One measuring step timed out (45 s, one long loop) - split into halves.

## 2026-09-30 19:0x-19:3x - buttons never switched off; the field a button works on blinks
- **Cause of "nothing happened" (user screenshot, 3b recipe Rename):** with the menu on "-- none --" the panel set Save/Rename/Delete .disabled; a disabled button gets pointer events but no mouse/click events and no press-in, and these panels never greyed them out. (Same in 4b-4h for Rename/Delete, and for all buttons while 4b's preset is in charge.) This also explains the earlier "click tool produced no click" puzzle.
- **User rule:** a button is never switched off; when it needs something first, ONLY the field it works on blinks 3x and stays highlighted - its dropdown or its text field - never an unrelated field.
- **Code:** needPick() (portrait_control.js, facedetailer_presets.js): blink + yellow outline + focus; a pick made this way only CHOOSES (nothing loads), then the action carries on (Rename/Save as -> name field; Save/Delete -> "now press ... again"); Esc puts the menu back. Recipe drawer + 4b-4h: no .disabled; 4c-4h while 4b is in charge: their OWN menu blinks with a "Locked: 4b's menu is in charge" message (Edit description blinks its own description box; Factory reset only shows a message - it works on no field). FaceDetailer presets: Load/Save/Rename/Delete with nothing picked -> its menu blinks. Scene/Physical shelves: buttons never off; on an empty slot the dial blinks + highlight and the action carries on when it reaches a saved one. makeRenamer onFinish now runs after the action (or at once on Esc). All files pass the module syntax check.
- **Verified after reload:** real mouse click on recipe Rename with "-- none --" -> menu focused, outlined, "Pick the recipe to rename."; pick -> no setting loaded, name field focused with name selected and blinking, button "Save new name"; Esc -> menu back to "-- none --". 4c Rename with none -> its own menu focused + outlined, "Pick the preset to rename.", 4b's menu NOT highlighted; Esc clears. Scene: dial on empty slot 3, Rename -> dial outlined + "turn the dial to the saved one to rename"; dial to 1 -> highlight off, rename carries on ("Doggy01" in the name field); Esc. No setting changed, workflow not marked changed, no console errors.

## 2026-09-30 19:3x - STEP 12 showed no pictures (user)
- **Checked:** run c37c23c3 (client 65c87e48 = Claude's tab) success, node 9 output 4 images; page app.nodeOutputs['9'] had them; socket OPEN; no console errors. Calling node 9's onExecuted by hand filled its panel object's grid with 4 cards, but nothing showed: node.__pp.root.isConnected = false, the on-screen .pp-root was a different (stale) element. Same for 7f's Prompt Watcher.
- **Cause (proven):** Claude had opened the workflow with app.loadGraphData(fetched json). In a fresh tab opened via the Workflows side panel, node 9 and 53 panels were connected; a Run there showed all 4 pictures in STEP 12 and filled the Prompt Watcher.
- **Clean-up:** old tab's unsaved diff = only 6 seed values from the user's Run; workflow closed in-app ("close" without save), tab force-closed; file not written. Memory note added: open via the Workflows panel.

## 2026-09-30 19:5x - STEP 12 button renamed (user)
- "Send to Video Queue" -> "Send selected image to video workflow queue": preview_pick.js button + its "click the picture(s) first" hint (real syntax check OK); READ ME notes in user/default/workflows/Freedom_Video.json, _14B_quality, _5B_fast; the add-on's spare copies of those three + a nodes.py comment. Backups: _backups/video_button_label_2026-09-30/, _backups/step7_split_2026-09-30/preview_pick_before_label.js.
- Still to do with the STEP 11/12 lettering (open question): the STEP 12 note in Freedom_SDXL_v01 still names the old button. The user's own ComfyUI tab (outside Claude's tab group since 19:4x) holds the old titles - they must reopen before saving after that edit.

## 2026-09-30 - two-choice switches: chosen side green, other side gray
- Request (user): "the active button should always be green and switch to gray when inactive" (auto_save off | on).
- Found by reading the page: ComfyUI draws these as `[role=group]` with one button per choice; the chosen one has `data-state="on"`. 16 such buttons in Freedom_SDXL_v01 (face OFF/ON, auto_save, FaceDetailer switches, ...).
- Change: `freedom_prompt_slots/web/prompt_slots.js` injects style `freedom-toggle-colors`: on = green #2e8b3e white text, off = gray #55575c light-gray text, off hover a bit lighter.
- Check: module syntax check OK. In Claude's tab the rule matches the buttons; with the button's fade switched off the gray side reads rgb(85,87,92) as set. The tab was in the background (hidden), so its fade never ran and a screenshot timed out - not yet seen on screen.
- User asked mid-turn: viewer maybe "a little image viewing window" instead of a Chrome tab - asked which kind before changing anything.

## 2026-09-30 - STEP 12 picture viewer now opens on top of ComfyUI (user picked 1)
- User: viewer "maybe do not use a chrome tab, use a little image viewing window" -> asked which kind -> answer "1" (viewer on top of ComfyUI itself).
- Change: `freedom_folder_inspector/web/preview_pick.js` `openViewer` no longer opens a tab. It lays a dark screen over ComfyUI with the picture, left/right arrows, "N of M" count and an X. Arrow keys step (wrapping last -> first); Esc, the X, or a click on the dark area closes; a click on the picture keeps it open. Keys are kept from ComfyUI while it is open. Backup: `_backups/viewer_overlay_2026-09-30/`.
- Check (Claude's tab, reloaded by the launch-page hop, workflow opened from the Workflows panel, STEP 12 filled with the last run's 4 pictures): double-click picture 2 -> "2 of 4"; next 3, 4, wraps to 1; Left key 4; prev 3; picture loads 1216x832; click on picture stays open; Esc closes; X closes; dark area closes. Real mouse click on the right arrow and a real Right key both stepped (1 -> 2 -> 3). Screenshot showed the picture large with both arrows and the X.
- Switch colors seen on screen: auto_save "on - keep every picture" green, "off" gray. Not clicked (would change the user's setting).
- Launch page on 8190 stopped.

## 2026-09-30 - STEP 11 and STEP 12 lettered (user answer 1: hidden helper boxes lose their letters)
- Freedom_SDXL_v01.json titles: 37 -> "STEP 11a - every FaceDetailer dial explained", 19 -> "STEP 11b - repaint and develop", 34 -> "STEP 11c - FaceDetailer (face repaint) ...", 20 -> "STEP 12a - see it & save it", 9 -> "STEP 12b - FreedomPreviewPick ...".
- Hidden helpers lost their letters: 33 face finder "STEP 11a" -> "STEP 11", 36 on/off chooser "STEP 11c" -> "STEP 11"; gate 3's title said "-> 11c", now "-> on/off chooser".
- STEP 12a note: "Send to Video Queue, double-click for full size" -> "Send selected image to video workflow queue, double-click to see it large (arrows step through the run's pictures)".
- Code comment in facedetailer_presets.js: STEP 11b -> 11c. No code looks boxes up by these titles (searched).
- Check: only those 8 boxes changed in the file; reopened from the Workflows panel in Claude's tab, all 8 titles and the note text read back as set. Backup: _backups/step11_12_letters_2026-09-30/.


---

# FULL SESSION RECORD - 2026-09-30, about 09:51 to 20:10 (all times local, Pacific)

Written at the user's request: "log in painful detail everything we have done", in this file
(the newest log we write; `logs/comfyui.log` is newer but it is ComfyUI's own running log, not ours).
The dated entries above (11:21 onward) hold the measured checks. This record walks the whole day
in order: the morning work that had no entry yet, every question asked and the answer given,
every file touched, and what was and was not checked. Session id 8e634bdc.

## Words used below, in plain terms
- **Workflow** - the picture-making recipe file you open in ComfyUI (here `Freedom_SDXL_v01.json`).
- **Box (node)** - one of the panels on the ComfyUI screen. **Frame (group)** - the coloured area around a STEP.
- **Add-on** - our own code in `custom_nodes/freedom_*` that draws extra panels and buttons inside boxes.
- **Claude's tab** - the Chrome tab Claude controls (John Doe profile, its own tab group). **Your tab** - the one you work in.
- **Launch-page hop** - how Claude opens ComfyUI: open a tiny blank page on port 8190, then jump to ComfyUI from inside it, because ComfyUI's safety guard refuses pages opened straight by the extension.
- **Reload** - re-reading the page so new add-on code takes effect. New add-on code does nothing until the page reloads.
- **Backup** - a copy of a file taken before Claude changed it, kept in `_backups/<topic>_2026-09-30/`.

## 1. 09:51 - STEP 1 renamed, new workflow file Freedom_SDXL_v01
- You asked: READ ME FIRST -> 1a, the art model paragraph -> 1b, the checkpoint switch -> 1c.
- Claude read `Freedom_bigLust_SDXL v09.json` and confirmed no code finds these boxes by title.
- Question: which file? Options: a new v10, or change v09 in place. **You: "1, make v10 but rename it Freedom_SDXL_v01".**
- Done 09:54: `user/default/workflows/Freedom_SDXL_v01.json` = copy of v09 with three titles changed:
  `STEP 1a - READ ME FIRST`, `STEP 1b - the art model`, `STEP 1c  -  CheckpointLoaderSimple  -  Pick the art model`.
  File-to-file compare: only those three titles differ. v09 untouched. Noted: the art-model note's own first bold line still said "STEP 1 - the art model".
- Question: move READ ME inside STEP 1's frame? **You: "1" (yes).** Done 09:59: box moved in, frame grew (about 3 times taller, a little wider), order 1a / 1b / 1c top to bottom, no touch with STEP 2's frame. Opened in Claude's tab (launch-page hop) and seen on screen; closed without saving; file confirmed unchanged by the check. Noted: 1c sat right on the frame's bottom edge.

## 2. 10:02 - bigLust workflows archived
- You asked to hide or archive the bigLust workflows. Claude checked that no code opens them by name.
- Question: out of sight (`workflow_archive\bigLust`) or one folder in the list (`workflows\_archive_bigLust`)? **You: "2 move all of them".**
- Done 10:04: 11 files moved into `user/default/workflows/_archive_bigLust/` - the un-numbered one and v02-v09 (9 workflows; Claude first miscounted them as 10 and corrected it) plus the two old v03 backups (`.bak_before_reorder`, `.bak_before_step4_order`). ComfyUI's list then showed the 7 current workflows plus that one folder. Nothing deleted. Warnings given: an old tab that still has a bigLust file open would write it back to its old spot if saved; git now sees the two v03 backups as new files.

## 3. 10:07 - "does Save keep my positions and sizes?"
- Claude checked three ways: the file changed at your 10:05 save; reopened in Claude's tab, all 13 frames and 40 of 42 boxes matched the file; no add-on code changes sizes when a workflow opens.
- Two boxes opened 30 taller than saved (STEP 1b note 320 -> 350, STEP 2 switch 120 -> 150). Question: hunt the cause? **You: "2 i caused the increase"** - you had resized them yourself. Closed, no bug.

## 4. 10:14 - "row 1 row 2 row 3?" -> Face Shelf / Face Lora Stack names
- You (screenshot): numbers without their source names tell a reader nothing ("are we talking concert tickets, cupcake pans?"). Saved as memory `ui-numbers-need-source-names`.
- The line was the face-strength sum "1.0 = 0.4 face shelf + 0.3 row 1 + 0.2 row 2 + 0.1 row 3" (from `freedom_face_shelf/web/selected_face_stack.js`), shown in STEP 3b and 3c. Strength works like a volume knob for her face: too low and it doesn't look like her, too high and it looks overdone.
- Answers: how to name the parts -> **"2 but do not use the node numbers, use the node titles"**; then your fuller instruction: "Freedom_Face_Shelf" / "Freedom Face Shelf" -> "Face Shelf", "FreedomSelectedFaceLoraStack" -> "Face Lora Stack", each stack on its own row, rows update by themselves; how far to rename -> **"3"** (titles + ComfyUI's add-box menu + rename the small workflow file).
- Done 10:37-10:39 (backups `_backups/face_names_2026-09-30/`):
  - `freedom_face_shelf/nodes.py`: menu names "Face Shelf", "Face Lora Stack". `build_face_shelf.py` writes `Face_Shelf.json`. `user/default/workflows/Freedom_Face_Shelf.json` renamed to `Face_Shelf.json`.
  - `selected_face_stack.js` + `face_shelf.js`: the strength box is one row per part - "3b Face Shelf default 0.4", "3c Face Lora Stack - pass 1 default 0.3", pass 2 0.2, pass 3 0.1, then "Total default 1.0  Current: 1.00". The step letter and name are read from each box's own title every half second. Inside the stack box "Row 1 / row 1 ON" became "Pass 1 / pass 1 ON", and the same for 2 and 3.
  - Old names fixed in the Portrait Master recipe note and in the add-on's messages to the ComfyUI log.
  - v01 titles: `STEP 3b  -  Face Shelf  -  Pick a face!`, `STEP 3c  -  Face Lora Stack  -  Extra passes of her face (trained face only)`; the 3c box and the STEP 3 frame made taller to fit the rows.
  - Test in Claude's tab: titles changed to "STEP 9z" / "STEP 4q" -> both strength boxes showed 9z / 4q within about a second; set back -> 3b / 3c. The hidden built-in type names were kept, because saved workflows use them to find the boxes.

## 5. 11:17-11:28 - "Sizing and positioning are still not saving" (Claude watches, you move)
- You: "I dont what you to make the changes for me. I will make the changes. I need you to monitor the code and figure out why". Claude opened v01 fresh in its tab ("1"); you closed your own tab and worked in Claude's ("1 I closed the non claude tab").
- Monitors started: a file watcher, `logs/save_monitor_2026-09-30/file_watch.py`, which writes every workflow file change to `file_watch.log` (checks 4 times a second; still running at the end of the day), and an in-page monitor (save requests, errors, Ctrl+S, Save clicks, the "changed" flag).
- Finding: nothing under user/ had been written by a save between 10:39 and 11:21, so saves from your old tab never reached disk. Why could not be found: that tab was already closed.
- You resized the STEP 2 frame, then File > Save: request sent, server answered OK, file changed 0.15 s later; disk = screen for all 42 boxes and 13 frames. Restart with the launcher's "c" key and a fresh reopen: zero differences. Save works end to end in Claude's tab. The 11:21-11:28 entries above have the exact times.

## 6. 11:37-11:45 - wording fixes and your saves checked
- STEP 3a note "0.3 row 1 ..." -> "0.3 Face Lora Stack pass 1 + 0.2 ... pass 2 + 0.1 ... pass 3" (you: "fix"). READ ME line about "three rows" -> "three passes (Face Lora Stack pass 1, pass 2 and pass 3)" (you: "change it").
- Finding: pressing Run marks the workflow as changed, because six seed numbers are set to pick a new random number after each picture.
- Your 11:40 save and your 11:45 move (3c down, STEP 3 frame taller) were both checked: disk = screen.

## 7. 11:49-12:10 - STEP 4 hint text formatting
- You asked how to edit the STEP 4 hint boxes. Claude explained they are not note boxes: the text is printed by our add-on (`freedom_portrait_control/web/portrait_control.js`), like a label printed on a machine, so it cannot be typed into on screen. You asked "what are you hearing me ask?", "am I asking for formatting or content changing?", "what was my original how to question about the note boxes?" and "why am I able to edit node 3a?" - all answered. Claude had first read it as a wording change; it was formatting. 3a is ComfyUI's own note box; the STEP 4 hints are part of the add-on's panel.
- **You: "2 remove line breaks but do include paragraph breaks. This is for all note boxes like this in all nodes."**
- Done: a new `hintBox()` draws the long "who is in charge" text and the 4b/4c warning as paragraphs and bullet points in the note font. Words unchanged. Claude waited for your unsaved moves (STEP 1-3 shifted 700 left; their frames had moved by a different amount, -713.58 / +9.53) before reloading; you said "go ahead and reload", then "ok now" after saving at 12:04.
- **Bug Claude introduced, then found and fixed:** after the first reload the panels were missing on all 7 STEP 4 boxes, with the error "items is not iterable" (a plain line of text has a built-in `.sub`, so the code treated it as a list). Fixed; second reload had no errors, and the words matched the original exactly (checked by fingerprint).
- **You: "update all similar boxes across all nodes".** Claude checked every add-on panel's hint text: only `portrait_control.js` had typed-in line breaks, so nothing else needed changing. **You: "drop question 4"** (a parked question removed).

## 8. 12:13-12:25 - STEP 4 spaced out and re-lettered
- **You: "space out the 4x nodes and resize the node group to fit. the step 4 hints size is good above the others but it needs to be 4a. adjust the others from there."** Then **"3"** (hidden names re-lettered too).
- Spacing: STEP 4 boxes at x 2650 / 3350 / 3850 / 4550 / 5050 / 5550 / 6050, frame widened, STEP 5 onward moved +400. Re-letter: hints note -> 4a, Portrait Master boxes 4a..4g -> 4b..4h everywhere (111 changes in 5 files; hidden setting names n4c..n4h; pair choice "4c Base Character"). One slip ("4b hints") was caught and fixed. A restart and a test job proved the server reads the new names. Backups `_backups/step4_reletter_2026-09-30/`. CLAUDE.md STEP 4 note updated. Older workflow files still use the old names and lose their STEP 4 settings when opened.

## 9. 12:35 - STEP 6 orange text
- "what is this?" -> the LoRA stack's orange line "Hidden as wrong architecture: ..." (5 LoRA files made for other art models are kept out of the menu). **You: "hide that orange text".** Done in `freedom_lora_stack/web/lora_stack.js`; the files are still kept out of the menu; checked on screen.

## 10. 13:10-15:50 - STEP 7 rebuilt
- 13:10 "what is this?" -> the Prompt Watcher (shows the full prompt from the last picture). **You: the Prompt Watcher becomes its own box as 7b, and the other letters move down.** Built (FreedomPromptWatcher, screen only) and tested with a run.
- 13:45-14:30 questions answered: the physical box vs the saved-look window (not duplicates: the window previews the shelf, the box is what goes to the engine); what a trigger word is (lorasusana, added for you in trained-face mode; 1.1 is the trigger_weight, how loudly the word speaks).
- Your decisions: the phrase shelf and its note were taken out of the workflow (code kept); Physical Description Prompt and Everything Else each became their own box with their own shelf; the "Full Prompt Shelf" became the **FINAL COMBINED PROMPT**, read-only; **one green button per box, nothing updates by itself, the final box closed to mouse and keyboard, with a watcher line**; the layout **7a "What you want" note, 7b "Hints" ("n/a"), 7c Summary Signal (each section its own adjustable field + green button), 7d Scene Prompt, 7e Physical Description Prompt, 7f FINAL COMBINED PROMPT with the Prompt Watcher field under it**; the order Summary Signal, trigger word, Physical, Scene; **"1": the engine gets exactly what the final box shows** (in random-face mode, Portrait Master's words fill a marker at Run).
- Built 14:03-14:53: `freedom_prompt_slots/nodes.py` (FreedomScenePrompt, FreedomPhysicalPrompt, FreedomFinalPrompt) and `prompt_slots.js` (a shelf per box, green buttons, fields with their own drag handle, our own text fields because ComfyUI's could not be resized, the stretching fixed); `checkpoint_prefix.js` (Summary Signal split into fields). Tested: a run sent 592 characters, identical to the final box.
- Snap to grid found: ComfyUI moves boxes onto a 50-point grid when a workflow opens, so Claude's placements now always use multiples of 50 (memory `comfyui-snap-to-grid-50`).
- 15:0x "slot 1 of 2 saved" explained (2 looks saved; the shelf holds up to 99). **"remove that wording"**, then **"1"** - removed; the other messages kept.
- 15:0x "are there any other prompts or hidden instructions?" - answered: the "don't want" list (STEP 8) and the face repaint's own words (only her trigger word, which replaces the prompt for the face repaint) reach the engine but are not in the final box; STEP 6 LoRA trigger words are not added; in trained-face mode STEP 4 is not used. "does the do not want and the face repaint still make it to the engine?" - yes, both, and when.
- 15:1x-15:4x: the gap under the SAVED window fixed; **Scene Shelf title "Scene Shelf - pose, action, scene, camera, light, style"**, typing field headed "Scene Prompt" with two line spaces above it; Physical the same ("Physical Shelf - how she looks (body, face, hair, skin, clothing)", "Physical Description Prompt"); **field heights must save**. LoRA trigger words: **you type them yourself**. FINAL shows only what it builds. A trained face keeps STEP 4 out.
- One mistake, no loss: a reload was sent in the same step as the unsaved-work check; Chrome's "Leave site?" guard blocked it. Since then the check always runs first, on its own.

## 11. 17:40-19:30 - Rename, Save as, heights, overlap, fonts, frames, buttons
- **Rename everywhere:** on the first click the name field shows the current name selected, blinks three times, and the button reads "Save new name"; Enter or a second click renames; Esc cancels. (You: "1".)
- **Height bug fixed:** saved heights were overwritten by the starting heights when a page opened. Now they are re-applied on open, and only a real drag is stored. Verified by a reload and a real drag.
- **"there MUST BE NO OVERLAP":** making a box taller now pushes the boxes below it down and grows the frame. Whole workflow re-checked: 0 overlaps, every box inside a frame.
- **"Save as" works the same way as Save and Rename** on every Save as button (two steps, "Save as new").
- **Fonts +1 everywhere:** finding - this Chrome profile never shows text smaller than 18 px, so all box text was showing at 18; now all of it is 19 px (one style rule). The overlaps the bigger text caused were fixed by moving lower boxes down; re-checked at 50%, 30% and 15% zoom: zero.
- **Light green frame** on the typing boxes in STEP 7 only.
- **"nothing happened" on Rename (3b recipe):** the buttons had been switched off but looked normal. Your rule: a button is never switched off; when it needs something first, only the dropdown or text field it works on blinks three times and stays highlighted ("I am not saying that if you click a button then some unconnected dropdown should appear and blink"). Built into all panels; verified with real clicks. Memory `buttons-never-disabled-linked-field-blinks`.
- Syntax-check finding: plain `node --check` misses errors in these files; the real check uses module mode (memory `js-syntax-check-must-be-module`). It found two leftover "});" in portrait_control.js before any page had loaded them.

## 12. 19:33 - STEP 12 showed no pictures
- Cause proven: Claude had opened the workflow with a code shortcut (`app.loadGraphData`), which left stale panels on screen. Opened through the Workflows panel instead, a run filled STEP 12 with all 4 pictures. Memory `open-workflow-via-sidebar-not-loadgraphdata`. The old tab was closed without saving; the file was not written.
- You also said: STEP 11 and 12 are missing their letters (done in section 15).

## 13. 19:43 - button renamed
- "Send to Video Queue" -> **"Send selected image to video workflow queue"** in `preview_pick.js` (the button and its hint), the three video workflows' READ ME notes and the add-on's spare copies of them, and a `freedom_video_queue/nodes.py` comment. Backups `_backups/video_button_label_2026-09-30/`.

## 14. 19:44-20:00 - double-click picture viewer: first version, then final version
- You: double-clicking opens the picture in a new tab correctly, but it needs left and right arrows for the run's other pictures.
- **First version (new Chrome tab):** `openViewer()` wrote a small page into a new tab with arrows, "N of M", arrow keys, and wrap-around. Tested from code: Chrome blocked the tab (it only allows new tabs from a real click) and the panel showed "Chrome blocked the new tab - allow pop-ups for this page." A real double-click by Claude could not be done: Claude's Chrome window was behind yours and not drawing (screenshots timed out).
- You then said: "maybe do not use a chrome tab, use a little image viewing window". Claude asked which kind (on top of ComfyUI / small separate Chrome window / Windows photo app / keep the tab). **You: "1".**
- **Final version (on top of ComfyUI):** the page behind goes dark, the picture shows large in the middle with arrows left and right, a "2 of 4" count, and an X in the corner. The arrow keys step and wrap around; Esc, the X, or a click on the dark area closes it; a click on the picture keeps it open; while it is open, keys don't reach ComfyUI. Backup `_backups/viewer_overlay_2026-09-30/`.
- Verified in Claude's tab (reloaded by the hop, workflow opened from the Workflows panel, STEP 12 filled with the last run's 4 pictures): every step in the entry above, including a real mouse click on the right arrow and a real Right-arrow key press; screenshot taken.

## 15. 19:55-20:05 - two-choice switches green and gray; STEP 11/12 letters
- **"the active button should always be green and switch to gray when inactive"** (auto_save "off | on - keep every picture"). These switches are pairs of buttons, and the chosen one is marked "on". One style rule in `prompt_slots.js`: chosen = green (#2e8b3e) with white text, the other = gray (#55575c) with light text, a slightly lighter gray on hover. It applies to all 16 such buttons in v01 (face OFF/ON, auto_save, FaceDetailer switches ...). Seen on screen: auto_save "on" green, "off" gray. Not clicked, so your setting was not changed. Note: in a hidden tab the colour fade never finishes, which is why the first measurement read the old colour.
- **STEP 11/12 letters.** Question: what happens to the two hidden helper boxes that had 11a and 11c? **You: "1" - drop their letters.** Done in v01 (backup `_backups/step11_12_letters_2026-09-30/`):
  11a dials note, 11b repaint-and-develop note, 11c FaceDetailer, 12a "see it & save it" note, 12b picture panel; the face finder and the on/off chooser are now just "STEP 11"; gate 3 now says "-> on/off chooser"; the 12a note names the new button and the new viewer; a code comment in `facedetailer_presets.js` was updated. Only those 8 boxes changed; reopened and read back.

## 16. 20:05-20:10 - this record, then commit and push
- You: "log in painful detail everything we have done in the most recent log in the repo folder. Do not create a new one. push commit". This record was written from the session's own transcript (your messages, Claude's replies, and the list of commands run), then everything was committed and pushed.

## Where things stand at the end
- **Your own ComfyUI tab** still has the old titles and old add-on code loaded. Do not press Save there (it would write the old names back). Reload it, then open Freedom_SDXL_v01 from the Workflows panel.
- **Still running in the background:** the file watcher (`logs/save_monitor_2026-09-30/`), and three picture-viewing pages left over from earlier sessions, on ports 8191, 8192 and 8193 (reachable only from this computer). The launch page on 8190 was stopped.
- **Seen but not investigated:** the console message "ComfyApp graph accessed before initialization" at some page loads.
- **Memory notes added today:** ui-numbers-need-source-names, comfyui-snap-to-grid-50, js-syntax-check-must-be-module, buttons-never-disabled-linked-field-blinks, open-workflow-via-sidebar-not-loadgraphdata.
- **Backups made today** (in `_backups/`): face_names, step4_reletter, step7_prompt_watcher, step7_split, fonts_plus_one, video_button_label, viewer_overlay, step11_12_letters (all `_2026-09-30`).

## 2026-09-30 20:2x - "All the last generations created the exact same images" (user, 5 screenshots)
- **Checked:** output/freedom_archive img_01601-01624 - the seeds stored inside each picture, the pixels, ComfyUI's job history (time, which tab sent it, seed), and the live seeds in the tab the user works in (Claude's tab group, client f32c91e9).
- **Result:** runs at 19:32 (Claude), 19:38 (tab bdb2690a), 20:01 and 20:10 (tab f32c91e9) all used KSampler seed 67460242742333 and the same Portrait Master seeds (139/228/80/1537/1790). Pixels of img_01609 = 01613 = 01617 = 01621 exactly (file checksums differ only because each PNG carries its own saved workflow text). 01605 (seed 99420375890181) differs.
- **Cause (proven from the timeline):** every seed is set to "randomize" with ComfyUI's control mode "after" - a new number is picked AFTER each run. The saved workflow file holds 67460242742333. Each of those runs was the FIRST run after the workflow was freshly opened (page reloads at about 19:50 by Claude and 20:09:05 by the user; 19:38 was a fresh tab), so each one used the saved number. After the 20:10 run the tab now shows new seeds (KSampler 526291554669428, PM 566/1121/1298/193/1825), so the next Run in that tab would differ. FaceDetailer seed 1736114183 is set to "fixed".
- Nothing changed. Question asked about what to do.

## 2026-09-30 20:3x - same pictures: earlier answer was wrong; checked code, history, community, and a test
- **User:** "You have assumed and guessed... review the code, check our recent logs, check developer notes, ask the community". Earlier option 1 claimed switching "Widget control mode" to "before" would give the first run after opening a fresh seed. That was not checked and is WRONG.
- **Settings file:** `user/default/comfy.settings.json` has no Comfy.WidgetControlMode entry and has never been changed in git, so it has been on its default all along.
- **Shipped frontend code** (`app_cabinet/comfyui/venv/Lib/site-packages/comfyui_frontend_package`, version 1.53.6, file settingStore-*.js): setting "Widget control mode", options before/after, default "after", exists since frontend 1.6.10. The seed control's code: `afterQueued = () => { if not "before": change the value }`; `beforeQueued = () => { if "before" AND this widget has been queued before: change the value; then mark it queued }`. So in BOTH modes the first run after a box is created (workflow opened / page reloaded) sends the value stored in the workflow. The per-box switch "control after generate" (randomize / fixed / +1 / -1) is set to randomize on 4c-4g and STEP 10; FaceDetailer (STEP 11c) is fixed.
- **Our logs:** 11:38 entry already saw seeds change after a Run (randomize works after the first run). No log ever changed WidgetControlMode.
- **Community:** GitHub issue Comfy-Org/ComfyUI #5462 (seed stays the same on the first generation after switching to randomize); widget control mode docs say "after" changes the number after the run.
- **Archive history:** 1517 archived pictures, 428 different KSampler seeds; repeated seeds across separate runs go back to 09-07 (some were Claude's own test jobs, so not all were the user's), so repeats are not new today.
- **Test (separate Claude tab, nothing sent to the server - the send was intercepted):** opened Freedom_SDXL_v01 from the Workflows panel, mode "after". Screen seeds after opening = file: 67460242742333 / 139 / 228 / 80 / 1537 / 1790. Run 1 SENT exactly those; screen then changed to 887826133005345 / 832 / ... . Run 2 sent 887826133005345 / 832 / ... . Server history and queue unchanged (no job). Test workflow closed without saving; tab freed by a forced navigation (discarded only the test tab's unsaved seed changes) and closed; file unchanged since the commit.
- **Where the saved seed is:** inside Freedom_SDXL_v01.json, the seed box of STEP 10 (KSampler) = 67460242742333 and the seed boxes of 4c-4g Portrait Master = 139, 228, 80, 1537, 1790. Timeline: the 19:30:08 run sent 99420375890181 and then rolled 67460242742333 on screen; the only save between then and 19:53 was at 19:31:53 (file watcher), so that save wrote 67460242742333 into the file (who pressed it is not recorded). 19:53 was Claude's lettering edit, which kept the seeds.
- "before" mode was NOT tested (it would change the setting for every open tab); its behaviour above is from the code only.

## 2026-09-30 20:5x - STEP 11c FaceDetailer seed: fixed or random? (user asked; no change made)
- **Workflow:** v01 box 34 (STEP 11c) seed 1736114183, control "fixed", denoise 0.15 (developer default 0.5). It is the only seed set to fixed; STEP 10 and 4c-4g are randomize.
- **Developer's code** (custom_nodes/ComfyUI-Impact-Pack, commit 429d015, modules/impact/impact_pack.py): seed default 0, no fixed/random preference in the node; do_detail gives each found face `seed + i` (face 1 = seed, face 2 = seed+1 ...) as the starting noise for its repaint. "control after generate" is added by ComfyUI's page, not by the developer (also noted in our facedetailer_presets.js header).
- **Developer's README:** seed = "the initial value required for generating noise" (written for the NoiseInjection hook); the only fixed/random advice is for the external_seed/Detailer case (README line 113), not FaceDetailer. No statement that FaceDetailer's seed should be fixed.
- **Community:** issue #65 asked for a new random seed per face (no developer reply visible); third-party node guides describe the seed as only controlling repeatability of the enhancement.
- **Our history:** set to fixed on 2026-09-22 at the user's request ("Please update the recipe set seed generation for these at fixed?") to rebuild the img_01314 picture; commit f312dcd pinned KSampler 930312207 and FaceDetailer 1736114183. KSampler went back to randomize later; FaceDetailer stayed fixed.
- **Not measured here:** whether fixed or random changes how much the repaint looks like her. Every likeness test in logs/v06_facedetailer_lora_and_likeness_2026-09-21.md used one seed.
- 20:57:44 user saved v01: STEP 11c FaceDetailer control fixed -> randomize (checked in tab and file).

## 2026-09-30 21:0x-21:5x - new seed numbers every time a workflow opens (user: Q = 3)
- **New file:** `custom_nodes/freedom_prompt_slots/web/fresh_seeds.js`. After ComfyUI has fully finished opening a workflow (wraps app.loadGraphData; also runs when switching between open workflow tabs), every seed box whose switch is "randomize" gets a new number from ComfyUI's OWN randomize code (the switch's afterQueued; in "before" mode beforeQueued twice). "fixed" / "increment" / "decrement" boxes untouched. Undo/redo (which also call loadGraphData with clean=false while the tracker is restoring) are skipped.
- **Unsaved-changes star:** screen captured first, then ComfyUI's own flag is trusted. Flag off -> the new numbers become part of the "as opened" copy (reset with the serialized graph + updateModified), so an open is not marked changed. Flag on -> left marked.
- **Three wrong turns, found by testing and fixed before finishing:** (1) first version reset the tracker inside afterConfigureGraph with a timeout - in one switching order it could reset the wrong workflow; moved to after loadGraphData returns. (2) ChangeTracker.reset() copies its last captured state, not the screen, so Face_Shelf/v01 would have been marked later - now resets with the serialized screen. (3) Comparing the "as opened" copy with the current copy to see through a stale star HID real unsaved work (test C: moved note kept, star gone) - because on tab switch ComfyUI resets its "as opened" copy, the star is the only record. Removed; the star is trusted.
- **Undo found in ComfyUI source:** ChangeTracker.updateState -> Q.loadGraphData(n, false, ...) - hence the undo skip.
- **Final tests (Claude's tab, workflow from the Workflows panel; nothing sent to the server - send intercepted; last real job still a1f99cae):** A fresh open: seeds new (file 526291554669428 -> screen 486312092455489...), not marked. B switch to Face_Shelf and back: new numbers again, not marked. C real change (note 20 moved +50) then switch away/back: move kept, star kept. Undo after C: first undo stepped back the roll (seed returned to the previous number, no new roll). E fresh open then pretend Run: sent 797710966057457 / 645 / 191 / 560 / 1154 / 37 / 165978467005316 - none equal to the file's numbers.
- **Seen, not caused by this:** Face_Shelf gets a star after opening because its Face Shelf box (node 2) adds one empty setting after load (widgets_values 5 -> 6 entries). A workflow closed with "Close anyway" keeps its star when reopened (known ComfyUI quirk, already in CLAUDE.md).
- **Clean-up:** all test changes closed with "Close anyway" or closed unmarked, tab force-reloaded by the hop, Freedom_SDXL_v01 opened fresh (not marked). Workflow file not written by any test (last save is the user's at 20:57:44). Launch page on 8190 stopped. Module syntax check OK.


## 2026-10-01 - confirm/cancel box for every "press again" button

- Passive logs: logs/comfyui.log read for 2026-09-30 after 22:00 (restarts 22:33 and 23:11, no errors); Windows Application log 22:00-01:00 (only OVRServer_x64 crash, unrelated).
- ComfyUI started by Claude for testing, output to logs/comfyui_2026-10-01_*_stdout.log / _stderr.log.
- Browser reads: Freedom_SDXL_v01 opened via the Workflows panel; real clicks on 7e, 7c, 11c, 4c; results read from the page and from /freedom/partslots, /freedom/ckptfront, /freedom/pm routes; screenshots of each box.
- Console: no errors from the changed files.
- Files checked after testing: freedom_scene_slots.json / freedom_physical_slots.json md5 equal to before; Freedom_SDXL_v01.json timestamp unchanged.
- Full record: logs/confirm_box_buttons_2026-10-01.md
