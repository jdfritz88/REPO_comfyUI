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
