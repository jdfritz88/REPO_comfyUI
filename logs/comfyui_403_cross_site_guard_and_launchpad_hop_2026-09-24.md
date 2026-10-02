# Chrome extension gets HTTP 403 from ComfyUI on 127.0.0.1 — cause found, and the launch-page hop

**Date:** 2026-09-24, 07:39 → ~11:30
**Branch:** main (nothing committed this session)
**Started as:** a CP1 watch-mode run — "watch all the backend detail while you work with Chrome and ComfyUI, do not ignore any errors."

---

## 1. Summary

The Claude in Chrome extension could not open ComfyUI at `http://127.0.0.1:8188`. Earlier sessions (2026-09-20
and 2026-09-23) blamed "the extension's own site permission" and fell back to the Tailscale address. **That
diagnosis was wrong.** The real cause, proven this session:

1. Every page load the extension starts (`navigate` → `chrome.tabs.update`) goes out with the header
   `Sec-Fetch-Site: cross-site`.
2. ComfyUI's own anti-CSRF guard, `create_origin_only_middleware()` in
   `app_cabinet/comfyui/server.py:159-197`, returns **HTTP 403 with an empty body** for any request carrying
   `Sec-Fetch-Site: cross-site` (lines 162-165). It logs nothing when it does this.
3. Chrome only sends `Sec-Fetch-*` headers to "potentially trustworthy" addresses: HTTPS, or loopback
   (`127.0.0.1`, `localhost`, `::1`). Plain-http network addresses (Tailscale `100.65.32.118`, LAN
   `192.168.50.14`) get **no** `Sec-Fetch-Site` header at all, so the guard never fires there. That is why
   Tailscale always "worked".

**Fix used (guard left fully on, no ComfyUI code changed):** the *launch-page hop*. Open a tiny local page on
another loopback port, then have that page itself send the tab to ComfyUI. A load started by a page on
127.0.0.1 is tagged `same-origin`/`same-site`, never `cross-site`, so ComfyUI lets it in. Tested twice, works.
The user chose this over turning the guard off or editing `server.py`.

---

## 2. Timeline

| Time | What happened |
|---|---|
| 07:39:47 | ComfyUI started by the kobold launcher (`REPO_koboldccp_sst_tts_media\launcher.py`, PID 31228 → 10928 → 23188). |
| 07:45 | Claude opened ComfyUI once on the Tailscale address before the user said "do not use tailscale". The page loaded (the three deprecation warnings at 07:45:51 are that load). |
| 07:46–07:47 | `http://127.0.0.1:8188/` and `http://localhost:8188/` both showed Chrome's error page in the extension's tab. `get_page_text` and screenshots failed: "Frame with ID 0 is showing error page". |
| 07:48 | Live backend watcher started (see §5). CP1 baseline sweep launched in the background. |
| ~07:55 | CP1 sweep finished: no errors, 4 traced warnings (see §6). It stopped at Technique 1 (backup) because it had been told not to copy without the user. |
| ~08:00 | Extension code read: its "site permission" system (Options → Permissions → "Your approved sites") only lists sites with a Revoke button, has no Add button, and the stored list was empty. It governs whether Claude may *act* on a site, not whether a page loads. The 2026-09-20/23 conclusion was therefore not supported by the code. |
| ~08:04 | User set **Insecure content → Allow** in `chrome://settings/content/siteDetails?site=chrome-extension://fcoeoabgfenejglbffodgkkbkcdhcgfn`. No change (that setting is for the extension's own pages). User then changed other extension settings and closed Chrome. |
| 08:11 | Claude launched Chrome in the John Doe profile (`--profile-directory="Profile 1"`, profile name "John"). Windows-MCP screenshot of the real window finally showed the error text: **"Access to 127.0.0.1 was denied — HTTP ERROR 403"**. This was the first time anyone saw it was a 403 and not a network block. |
| 08:15:22 | User shut ComfyUI down. Watcher reported "server not answering", then both PIDs gone. |
| 08:17 | Claude restarted ComfyUI directly (not via the launcher) — see §7. Still 403. |
| ~08:20 | Research: Windows Firewall ruled out (see §4). ComfyUI's `server.py:162-165` identified. `curl` proved the server returns 403/0 bytes only for `Sec-Fetch-Site: cross-site`. |
| 08:26 | Header-echo test on `127.0.0.1:8190`: the extension's navigations carry `Sec-Fetch-Site: cross-site` from both an existing and a brand-new tab. **Cause confirmed.** |
| 08:30–09:28 | Repeated `ConnectionResetError [WinError 10054]` errors in the ComfyUI log — traced to the iPhone (see §6.3). |
| 08:44 | User ran a generation from ComfyUI Mobile on the iPhone: success, 35.6 s, 8 images. |
| 09:31 | Header-echo test on the LAN address `192.168.50.14:8190`: **no `Sec-Fetch-*` headers sent at all.** Explains why Tailscale got through. |
| 10:01–10:02 | Launch-page hop tested: ComfyUI loaded on 127.0.0.1 in the extension's tab. Guard untouched. |
| ~11:25 | Hop re-tested with a stock `python -m http.server` (no custom script) — works. This is the procedure now written into `REPO_comfyUI/CLAUDE.md`. |

---

## 3. Evidence, in the order it was gathered

### 3.1 What ComfyUI does with each header value

Run against the live server:

```
curl -s -o /dev/null -w "%{http_code} bytes=%{size_download}" [-H "<header>"] http://127.0.0.1:8188/

(no header)                  -> 200 bytes=20059
Sec-Fetch-Site: none         -> 200 bytes=20059
Sec-Fetch-Site: same-origin  -> 200 bytes=20059
Sec-Fetch-Site: cross-site   -> 403 bytes=0
```

The code that does it, `app_cabinet/comfyui/server.py`:

```python
162        if 'Sec-Fetch-Site' in request.headers:
163            sec_fetch_site = request.headers['Sec-Fetch-Site']
164            if sec_fetch_site == 'cross-site':
165                return web.Response(status=403)
```

The middleware is installed at `server.py:236-239` unless ComfyUI is started with `--enable-cors-header`.
It does **not** check the host, so it would block Tailscale too if Chrome sent the header there. It does not
log. The second check in the same function (host vs. origin mismatch, lines 169-188) only applies to loopback
hosts and does log "request with non matching host and origin"; it was never seen this session.

### 3.2 What Chrome actually sends from the extension's tab

A header-echo server (records every request's headers) was run on `127.0.0.1:8190` and on
`192.168.50.14:8190`:

| Navigation | `Sec-Fetch-Site` |
|---|---|
| extension `navigate`, existing tab → `127.0.0.1:8190` | `cross-site` |
| extension `navigate`, brand-new tab → `127.0.0.1:8190` | `cross-site` |
| extension `navigate`, new tab → `192.168.50.14:8190` | *(header not sent)* |
| extension `navigate`, existing tab → `192.168.50.14:8190` | *(header not sent)* |
| page's own script, `127.0.0.1:8190` → `127.0.0.1:8190/page-started-hop` | `same-origin` (with `Referer`) |

The extension's navigate tool (`assets/mcpPermissions-*.js` in extension 1.0.94) always loads pages with
`chrome.tabs.update(tabId, {url})`, whatever the address.

### 3.3 Why the network addresses get no header

W3C Fetch Metadata spec: for every `Sec-Fetch-*` header, "Assert: r's current URL is a potentially
trustworthy URL", and "If r's current URL is not an potentially trustworthy URL, return."
Loopback counts as potentially trustworthy; plain http on a network IP does not.
Source: https://www.w3.org/TR/fetch-metadata/

Chromium's tracker records that requests sent by extensions are labelled `cross-site`:
https://issues.chromium.org/issues/40641061 (see also https://github.com/w3c/webappsec-fetch-metadata/issues/47).

### 3.4 Things ruled out along the way

- **Windows Firewall.** It does not filter loopback by default, and a firewall block shows as a timeout or
  "connection refused", never an HTTP 403 reply.
- **The extension's site permissions.** Its permission store had no entry for 127.0.0.1, localhost or 8188,
  and the permission system has no bearing on page loads. Chrome's own site access for the extension is
  `<all_urls>` with `withholding_permissions=false`.
- **Chrome's HTTP cache serving the Tailscale page.** ComfyUI sends `Cache-Control: no-store, must-revalidate`,
  and there is no cached root document for either address in `Profile 1\Cache\Cache_Data`.
- **"Insecure content" setting.** Applies to the extension's own `chrome-extension://` pages, not to
  `http://127.0.0.1`. Changing it did nothing.

---

## 4. Research on the firewall question (user asked: "might it be a windows firewall?")

- Loopback traffic never leaves the PC and Windows Firewall does not filter it by default:
  https://www.tenforums.com/network-sharing/193311-question-about-loopback-traffic.html ,
  https://pinggy.io/amp/blog/what_is_127_0_0_1_and_loopback/
- Firewall blocks show as timeouts (drop) or instant refusal (reject), not HTTP replies:
  https://www.softwaretestinghelp.com/err-connection-timed-out-error/
- ComfyUI's origin/cross-site guard and the 403 it produces:
  https://github.com/Comfy-Org/ComfyUI/issues/4854 , https://github.com/comfyanonymous/ComfyUI/blob/master/server.py

---

## 5. The monitoring that ran all session

- **Live backend watcher** — `scratchpad/watch_backend.py`, re-armed every 30 minutes. Polls
  `GET http://127.0.0.1:8188/internal/logs/raw` every 2 s and reports any new line matching
  WARN/ERROR/CRITICAL/Traceback/Exception/failed/OOM/Killed; checks the ComfyUI PIDs every ~10 s; polls the
  Windows Application event log (IDs 1000/1001/1002) for chrome/python crashes every ~30 s. Every event is
  appended to `REPO_comfyUI_Monitor_LOG.md`.
- **Connection recorder** — `scratchpad/conn_tracker.py`, from 08:33. Writes a timestamped OPEN/CLOSE line
  every time a TCP connection to port 8188 appears or disappears (sampled 4×/s) to
  `logs/comfyui_session_2026-09-24/comfyui_connections_0833-1831.log`. The short `127.0.0.1` OPEN/CLOSE pairs in it are the watcher's own polls.
- **CP1 baseline sweep** — one read-only background run of the CP1 agent
  (`F:\Apps\freedom_system\.claude\agents\cp1-bug-search.md`), appended nine entries to the Monitor log.

`scratchpad` = `C:\Users\jespe\AppData\Local\Temp\claude\F--Apps-freedom-system-REPO-comfyUI\182039c5-2248-4b68-8efc-58199e967a50\scratchpad`
(session temp folder — these scripts are not in the repo).

---

## 6. Every error and warning seen this session

### 6.1 Server startup (both starts, 07:40 and 08:17)
- **Impact Pack SAM2 warning, printed twice.** `sam2` is not installed in the venv. Printed twice because
  `modules/impact/core.py` gets loaded under two module names (`impact.core` via `__init__.py:17`
  `sys.path.append`, and a relative import via `impact_pack.py:28 → hooks.py:5 → segs_nodes.py:7`).
  Traced from source only; not confirmed on the live process.
- **triton not available** (`comfy_kitchen backend triton … No module named 'triton'`) — INFO level.

### 6.2 Every page load of the full ComfyUI UI
- **Three `[DEPRECATION WARNING]` lines** (server log). Imports of removed legacy frontend APIs:
  - `/scripts/ui.js` ← `custom_nodes/ComfyUI-Impact-Pack/js/impact-pack.js:2`, `impact-sam-editor.js:3`,
    `impact-segs-picker.js:2`
  - `/extensions/core/clipspace.js` ← `ComfyUI-Impact-Pack/js/impact-sam-editor.js:5`
  - `/extensions/core/widgetInputs.js` ← `ComfyUI-VideoHelperSuite/web/js/VHS.core.js:3`
- **Browser console errors at 10:02:11** (first time the browser side could be read):
  - `ComfyApp graph accessed before initialization` — `assets/settingStore-KkBYyEnh.js:223`
  - `[vite:preloadError] Object` — `assets/main-DgYhGLKp.js:1`
- **404s on page load** (from `performance.getEntriesByType('resource')`): `/user.css`,
  `/api/userdata/user.css`, `/api/userdata/comfy.templates.json`, `/extensions/core/clipspace.js`, and one
  fetch whose URL the tool redacted.
- **Traced ~12:00 (read-only), all of them:**

  | Error | Cause | Evidence |
  |---|---|---|
  | `[vite:preloadError]` + 404 `/extensions/core/clipspace.js` | Impact Pack's `js/impact-sam-editor.js:5` imports `ClipspaceDialog` from `/extensions/core/clipspace.js`. Frontend 1.51.9 no longer ships that file (its `static/extensions/core/` has editAttention, groupNode, load3d, maskeditor, textPreviewWidgets, widgetInputs, widgetValuePropagation — no clipspace). The import fails, so the whole SAM editor module fails. | Every other Impact extension registered (`Comfy.Impact.img`, `Comfy.Impack`, `Comfy.Impack.Picker`, `drltdata.MaskRectArea*`); `Comfy.Impact.SAMEditor` is **missing** from `app.extensions`. Re-importing the file in the page: "Failed to fetch dynamically imported module: …/impact-sam-editor.js". The frontend's `vite:preloadError` handler (`main-DgYhGLKp.js`) logs exactly that kind of failure. |
  | `ComfyApp graph accessed before initialization` | Frontend-internal: the `app.rootGraph` getter logs this when something reads it before `setup()` creates the graph. No custom node reads `rootGraph` (grep of all `custom_nodes/**/*.js`: 0 hits). | Upstream fixes: PR #18059 (merged 2026-09-22, `executionErrorStore` read it unguarded; "the only user-visible symptom was a console.error") and PR #17886 (canvasStore/executionIdMap path). Which of those paths fired here was not pinned down. Both are newer than the installed 1.51.9, and #18059 is newer than the latest release 1.54.7 (2026-09-21). |
  | 404 `/user.css`, `/api/userdata/user.css` | The frontend's `index.html` always links both optional stylesheets; neither file exists. | `<link rel="stylesheet" href="user.css">` and `href="api/userdata/user.css"` in `static/index.html`. |
  | 404 `/api/userdata/comfy.templates.json` | No saved node templates yet. The frontend expects this. | `nodeTemplates-BvbGRDKm.js`: `t.status!==404&&console.error(...)`, so a 404 is silently treated as "no templates". |
  | 404 `/api/userdata?dir=subgraphs&recurse=true&split=false&full_info=true` (the redacted one) | `user/default/subgraphs/` doesn't exist. | `app/user_manager.py:183-184` returns 404 "Directory not found" for a missing folder; `user/default` has no `subgraphs` folder. |

- **Behind on updates (confirmed):** ComfyUI core is at `3216c62` (2026-08-31, v0.34.0), **167 commits
  behind** upstream master, which now requires `comfyui-frontend-package==1.53.6`. Installed frontend is
  1.51.9 (released 2026-08-26); latest is 1.54.7 (2026-09-21). Impact Pack (`429d015`) and VideoHelperSuite
  (`4d907be`) are both **at their latest upstream commit**. The SAM editor break is Impact Pack's own code not
  having caught up with the frontend, and an update of Impact Pack would not change it today.

### 6.3 `ConnectionResetError: [WinError 10054]` — traced to the iPhone
Logged as `[ERROR] Exception in callback _ProactorBasePipeTransport._call_connection_lost()` at
`asyncio/proactor_events.py:165`. Every burst was matched against the connection recorder:

| Errors logged | iPhone (`100.119.119.70`, Tailscale) connections closed |
|---|---|
| 08:34:37.433 / .475 / .477 | 08:34:37.497 — ports 53559, 53562, 53563 |
| 08:36:34.031 / 08:36:34.936 | 08:36:34.076 (53565), 08:36:35.142 (53566) |
| 08:37:51.453 / .499 | 08:37:51.464 (53567), 08:37:51.727 (53568) |
| 08:45:56.538 / .702 | 08:45:56.712 — ports 64969, 64970, 64971 |
| 08:47:58.990 | 08:47:59.153 (64974) |
| 08:49:22.880 / .882 | 08:49:23.092 (64972, 64973) |
| 09:28:39.258 | 09:28:39.465 (60595) |

Some iPhone closes caused no error (e.g. 53564 at 08:36:19, 60593/60594 at 09:28:42) — only abrupt drops
trigger it. Chrome's single 127.0.0.1 connection stayed open through every burst. No job was affected. This is
a known Windows asyncio cleanup error: https://github.com/comfyanonymous/ComfyUI/issues/2815 ,
https://github.com/Comfy-Org/ComfyUI/issues/15163 .

### 6.4 Clean results
- Queue/history empty at the start; GPU idle 45 °C, 11.6 of 12.3 GB VRAM free; all package versions match.
- Generations from the phone at 08:29, 08:38 and 08:44 all succeeded (~36 s each, 8 images each — 4 from
  node 9, 4 from node 11).
- No chrome.exe or python.exe crash in the Windows event log over the last 24 h (one Chrome
  "RADAR_PRE_LEAK_64" memory pre-detection report on 2026-09-23 23:26, not a crash).

---

## 7. ComfyUI updated 0.34.0 → 0.37.0 (17:30–17:45, at the user's request: "Update and test")

**Rollback points recorded first:** core commit `3216c62` (clean working tree, 0 local commits), full
`pip freeze` (149 packages) and the 1,355-node-type list, saved in `logs\comfyui_session_2026-09-24\update_0.37_rollback_records\`.

**What changed:**
- Core: `git merge --ff-only upstream/master` → `78368ea` (2026-09-24), version **0.37.0**, 170 commits.
  The git remote here is named `upstream`, not `origin`.
- Packages (`pip install -r requirements.txt`, dry-run first; exactly these 9 changed, `pip check` clean):
  frontend 1.51.9 → **1.53.6**, workflow-templates 0.11.50 → 0.11.69 (+ its core/json/media-assets
  sub-packages, new media-assets-02), embedded-docs 0.5.10 → 0.5.12, comfy-kitchen 0.2.31 → 0.2.35,
  comfy-aimdo 0.4.15 → 0.5.5. Torch and everything else unchanged. `torchaudio` dropped out of
  ComfyUI's requirements but stays installed.
- Node types 1,355 → 1,413 (+65, −7). The 7 removed are paid cloud-API nodes (ByteDanceImageNode,
  ByteDanceImageReferenceNode, KlingVideoExtendNode, LtxvApiImageToVideo, LtxvApiTextToVideo,
  OpenAIDalle2, OpenAIDalle3); none is used in any saved workflow.
- **Asset catalog rebuilt** by migration `0007_record_content_split` (startup warning). Old DB kept at
  `user\comfyui.db.bkp`. Checked read-only: the old DB had 0 assets, 0 metadata, 0 tagged items, and only
  ComfyUI's 24 built-in folder tags. Nothing user-made was lost.
- New startup warning: "On windows we are currently forcing single GPU mode". This machine has one GPU.

**Tests run:**
- Server up in ~12 s; all 26 custom nodes imported; no IMPORT FAILED, no tracebacks.
- `/system_stats`: every ComfyUI package installed == required.
- Frontend 1.53.6 loaded via the launch-page hop: 60 extensions (was 59), VideoHelperSuite OK.
- `Freedom_bigLust_SDXL v06.json`: all 31 node types present, loaded with 44 nodes and no error dialogs.
- Two real generations: **both success, 8 images each**. Sampling speed unchanged (1.12 s/step vs
  1.09–1.12 before). Warm run total **40.3 s vs 35.7–36.1 s** on 0.34: about 4 s slower, all of it in
  model preparation before and at the start of sampling, not in the sampling steps. Cause not traced.
- `/mobile/` → 200; Comfy Portal `/cpe/health` → 200, success.

**Unchanged by the update (still present):** the Impact Pack SAM editor still fails to load (1.53.6 still
doesn't ship `clipspace.js`); "ComfyApp graph accessed before initialization" still logged (its upstream
fix is newer than 1.53.6); the three deprecation warnings; SAM2 not installed.
**Newly visible in the console (warnings, not errors):** "the legacy queue/history menu is deprecated",
printed twice on every page load. Traced: it's in the constructor of the frontend's own legacy `ComfyList`
class (`settingStore-DDHzGrHr.js`), which the frontend builds itself. `comfy.settings.json` has no menu
setting at all, so it isn't caused by a user setting; Impact Pack's `ImpactSchedulerAdapter` uses a
deprecated `defaultInput`; `ComfyApp.open_maskeditor` deprecated; some extension reads the deprecated
`input.link`.

**During the update:** an extension tab still on the old frontend had `Freedom_bigLust_SDXL v06.json`
loaded and flagged modified (loaded while the update ran; not by Claude). Closed in-app with
"Close anyway". The file on disk was not written (still 2026-09-24 01:10:07, 101,208 bytes). Separately,
that on-disk v06 already differs from its last commit (`f312dcd`, 2026-09-22) across all 44 nodes
(values, positions, links). That change dates from 01:10 this morning, before this session.

**Running now:** ComfyUI 0.37.0, PIDs 37908 → 33780, same arguments as before, output in
`logs\comfyui_session_2026-09-24\comfyui_0.37_claude-start_1735-1830_stdout.log` / `_stderr.log`.

## 8. State left behind (as of ~18:30 - superseded by section 12.9)

- **ComfyUI is running outside the launcher.** Since 17:35 it is the updated 0.37.0 (see §7, PIDs
  37908 → 33780). From 08:17 to 17:30 it was 0.34.0, started by Claude with exactly the launcher's
  arguments:

  ```
  F:\Apps\freedom_system\app_cabinet\comfyui\venv\Scripts\python.exe main.py --port 8188
    --disable-auto-launch --base-directory F:\Apps\freedom_system\REPO_comfyUI
    --extra-model-paths-config F:\Apps\freedom_system\REPO_comfyUI\extra_model_paths.yaml
    --disable-pinned-memory --listen 127.0.0.1,100.65.32.118 --cache-none
  ```
  (working directory `app_cabinet\comfyui`, PIDs 22216 → 31676). Its stdout/stderr go to
  `logs\comfyui_session_2026-09-24\comfyui_0.34_claude-start_0817-1730_stdout.log` / `_stderr.log`, **not** to the launcher's
  `REPO_koboldccp_sst_tts_media\logs\comfyui.log`.
- ComfyUI's guard is unchanged. No ComfyUI file was edited.
- One extension tab left open on `http://127.0.0.1:8188/` with an empty "Unsaved Workflow" (0 nodes,
  nothing flagged as modified).
- `F:\Apps\freedom_system\.claude\agents\cp1-bug-search.md` Technique 1 reworded at the user's request: the
  backup now means the repo folder of the project being troubleshot *and* the app's folder (e.g.
  `REPO_comfyUI` → `REPO_comfyUI BACKUP`, `app_cabinet\comfyui` → `app_cabinet\comfyui BACKUP`). No backup
  was made this session.
- `REPO_comfyUI/CLAUDE.md` gained the launch-page hop procedure. The older section "Chrome cannot open
  ComfyUI on 127.0.0.1 — use the Tailscale address", which blamed the extension's site permission, was
  **removed on the user's instruction** ("All of that needs to be removed. The only thing that should
  remain is, if this thing or similar happens, then try this hopping technique."). Its three asterisk-tab
  subsections were kept, reworded as instructions and moved back under the asterisk-tab topic.

## 9. Where this session's raw files are

All moved on 2026-09-24 ~18:40 from the session temp folder into
`logs/comfyui_session_2026-09-24/`: both ComfyUI runs' stdout/stderr (0.34 and 0.37), the 07:48 log-buffer
capture, the connection record, the two Sec-Fetch header captures, the pip install log, and
`update_0.37_rollback_records/` (pip freeze before/after, system stats, node lists, requirements).
`_freedom_comfy.log` (2026-09-04) moved from the repo root to `logs/`.

## 10. Every ComfyUI log now written into `logs/` at the source (18:40–19:05)

User's instruction: every new and old log about ComfyUI goes to `REPO_comfyUI\logs`, except the kobold
launcher's own `comfyui.log`. The user's standing rule from 2026-09-18 said the same and had been left as
"still to do: write into every CLAUDE.md" in the 09-17 handoff — it never was, so no session saw it.

Writers changed at the source (not routed afterwards):
- **Claude-started ComfyUI** — rule at the top of `CLAUDE.md`: stdout/stderr redirected into `logs\`.
> Moved to `REPO_face\logs\comfyui_403_cross_site_guard_and_launchpad_hop_2026-09-24__face_parts.md` on 2026-09-30, when Face N the Crowd moved out of REPO_comfyUI: "**`face_training/otrain.py`** — `TRAIN_LOG_DIR` added; per-job log is now"
- **`REPO_avatarAIackendpp\services\expression_editor.py`** — `_COMFYUI_LOG_DIR` added; its ComfyUI
  server stderr now goes to `logsvatarai_comfyui_server_stderr.log`. Two old files moved in as
  `avatarai_comfyui_server_2026-08-16.log` and `avatarai_comfyui_server_stderr_2026-08-23.log`.
- **`REPO_comfyUI_Monitor_LOG.md`** — moved from the repo root to `logs\`; CLAUDE.md tells the CP agents
  to append there for this repo (the standards files still say "project root" for other projects).
- **`mobile-debug.log`** — old file moved to `logs\mobile-debug_2026-09-12_to_09-24.log`. The writer is the
  third-party `comfyui-mobile-frontend` (`src/utils/debugLog.ts`, always on, used by one hook), writing
  through ComfyUI's userdata API, which only allows paths under `user\` (`user_manager.py:94`) and writes via
  temp file + `os.replace` (`:406-408`), so a hard link would not survive a write. Landing it in `logs\` at
  the source needs: the path in `debugLog.ts` changed, the dist rebuilt (`npm install` + `npm run build`;
  no `node_modules` present), and a junction `user\default\logs` → `REPO_comfyUI\logs` — which exposes the
  whole logs folder read/write over ComfyUI's HTTP API to anything that reaches port 8188. **User decided 19:10: leave it** — new entries keep landing in `user\default\`.

## 11. v07 clean-up, launcher logging, and the test (evening, 2026-09-24)

**Built** (all in our own add-ons or v07; v06 untouched):
- `Freedom_bigLust_SDXL v07.json`, copied from the on-disk v06 (01:10 save). Groups: one straight line, step
  order, same top edge, every node fitted inside its group, 50 px grid; titles "STEP n - what it does";
  STEP 2 and STEP 5 got groups; a grey "BEHIND THE SCENES - plumbing, don't touch" group holds the encoder,
  face finder, three gates, on/off branch and decoder; the three gates numbered 1-3 of 3 in wire order;
  all nodes start collapsed (user's choice; phone unaffected). READ ME FIRST, STEP 7 and STEP 7b notes
  rewritten to match.
- STEP 12: the three picture displays are one node (`freedom_folder_inspector/save_pick.py`,
  `web/preview_pick.js`): auto_save + archive_prefix + images output + Open Archive Folder; the desktop no
  longer draws the duplicate strip (`hideOutputImages`). AUTO-SAVE box removed from v07.
- STEP 7a `FreedomPromptParts` (`freedom_prompt_slots`): physical + everything-else boxes, trigger wired in,
  each box with its own shelf. Saved prompts moved: Doggy01 / Cowgirl01 on the everything-else shelf,
  "Doggy01 look" / "Cowgirl01 look" on the physical shelf (Cowgirl01's age changed sixteen -> eighteen at
  the user's instruction; Claude declined to move it before that change). Old shelf emptied; backup
  `user/default/freedom_prompt_slots.json.bak_2026-09-24_before_move`.
- Rename on every shelf: 7a (both), 7b phrases, whole-prompt shelf, 4a, 4b-4g, STEP 3 recipes, Method 1.
- 4a and 4b-4g: "In charge", presets and save/load controls on top; labelled gaps between 4a's sections.
- `REPO_koboldccp_sst_tts_media/launcher.py`: ComfyUI's log now goes to `REPO_comfyUI/logs/comfyui.log`
  (Service gained `log_dir`). Old launcher copy moved to `logs/comfyui_launcher_2026-08-to-09-24.log`.
  Confirmed live: the relaunch at 19:51:33 wrote its header there.
- Snap grid 50 px (`Comfy.SnapToGrid.GridSize`), settings backed up first.

**Errors found in testing, and fixed:**
1. *4g Prompt Styler lost its values.* The on-disk v06 (01:10) had `style` and `add_extra_instructions`
   blank; v04, v05 and committed v06 all hold `descriptive`, `true`. Restored in v07 only.
2. *Reordered widgets loaded into the wrong boxes.* Frontend 1.53.6 restores by name when a file has
   `widgets_values_named`, otherwise by position against the NEW screen order (settingStore
   `createWidgetRestorationState`). Fix: after ComfyUI's own restore, every value is put back by name
   (named copy, else the original declared order, including shorter older saves). Verified: v07 162
   settings match by name; v05 138 match (2 are `null` in v05 and keep defaults, as before).
3. *Loading a second workflow failed: DataCloneError.* Cause: wire 58 (STEP 2 -> STEP 5) stored its type
   as the option list; 1.53.6 wraps it in a Vue proxy that `structuredClone` rejects. Both ends are
   `"COMBO"`. Upstream (issue #18165, PR #18252 / backport #18517, merged 2026-09-23, unreleased) only
   covers node extension fields, not links. Fixed in v07 by setting the wire's type to `COMBO`; v07 then
   loaded 3 times in a row cleanly. **v02-v06 still carry the list type** - user decided 22:2x: leave them as they are. Only v07 is fixed.
4. *Console: "Unknown message type mobile_latent_shape".* Sent by comfyui-mobile-frontend
   (`mobile_latent_shape.py`, identical to upstream latest) to the queuing window; the desktop logs any
   unregistered type. Fixed by registering and ignoring it on the desktop
   (`freedom_folder_inspector/web/mobile_messages.js`); the phone is unaffected. Gone after the fix.

**Test runs (launcher-started ComfyUI 0.37.0):** 20:06 and ~20:09, both success, 4 pictures each,
archived img_01491-01494 and img_01495-01498 by the one STEP 12 node; one picture display on the desktop;
all Rename routes tested (renamed and restored; a throwaway 4a preset created, renamed, deleted).
Remaining console errors are the two known ones (graph-init upstream bug; SAM editor, left by choice).

## 12. The evening in detail, in order (18:30 → 22:35)

Times are LOCAL, taken from file modification times, ComfyUI's log and process start times wherever
possible. Section 11 is the summary; this is the full record.

### 12.1 "Every new and old log about comfy goes to the REPO_comfyUI log folder" (~18:30-19:10)

- User: *"every NEW AND OLD log about comfy (exept when it comes to the kobald launcher) needs to
  automatically go to the repo_comfyi log folder."* Then: *"why would you need to auto route? if they are
  landing somewhere else first, why not change that source code?"* - so every writer was changed at the
  source, not routed afterwards.
- User asked for a count of how often they had said this. **4 times, in 2 files:**
  `move_to_app_cabinet_HANDOFF_2026-09-17.md` lines 16-17 and 31-32, and
  `onetrainer_data_moved_out_2026-09-19.md` lines 28-29 and 32-34. The 09-17 handoff listed "write the
  standing rule into every CLAUDE.md" as still to do; it never was, so no session saw it.
- User asked who wrote the processes that logged elsewhere. From git: `otrain.py` (2026-09-19, co-authored
  by Claude), the CP agent/standards files (2026-08-24, 09-01), AvatarAI `expression_editor.py`
  (2026-08-16, 08-21) - all Claude sessions; `mobile-debug.log` is the third-party mobile frontend.
- Claude then asked the user which writers to change - a question the user had already answered ("every
  new and old log"). Claude acknowledged that and did all of them:
  - Moved to `REPO_face\logs\comfyui_403_cross_site_guard_and_launchpad_hop_2026-09-24__face_parts.md` on 2026-09-30, when Face N the Crowd moved out of REPO_comfyUI: "`face_training/otrain.py` (18:46:23): `TRAIN_LOG_DIR` = `logs/face_training`, per-job"
  - `REPO_avatarAI/.../expression_editor.py` (18:46:36): stderr to
    `REPO_comfyUI/logs/avatarai_comfyui_server_stderr.log`; two old AvatarAI ComfyUI logs moved in.
  - `REPO_comfyUI_Monitor_LOG.md` moved from the repo root into `logs/`; CLAUDE.md tells the CP agents
    to use it there.
  - `user/default/mobile-debug.log`: old file moved into `logs/`. New entries can only reach `logs/` by
    exposing the folder over ComfyUI's HTTP API (junction), so the user was asked; **user chose "3" -
    leave it** (~19:10). Recorded in CLAUDE.md as a decided exception.
- The "diary to a file" question: the user answered *"I would rather start it via the launcher. But all
  data should go to a log in the repo_comfy log foldre."* -> `launcher.py` changed (19:38:57): the
  `Service` class gained `log_dir`; ComfyUI's log now goes to `REPO_comfyUI/logs/comfyui.log`. Verified
  by building the launcher's own ComfyUI service object from the edited code. CLAUDE.md updated
  (19:39:16) - no launcher exception any more.

### 12.2 The v07 clean-up requests and the user's decisions

User's list: STEP 2 and STEP 5 need their own groups; groups in one straight line; stronger snapping; the
three "STEP 11 GATE" nodes can't be told apart; all nodes start collapsed; "we do not need three different
image groups... ALL OF THE FEATURES can be combined into one"; every node must fit its group; 4a's
"in charge" and buttons at the top; split the positive prompt into a physical box and an everything-else
box, three inputs making the final prompt, with the same save/preset/load package; save/preset/load at the
top of node 4; a space between 4a's sections; review the node titles; where do non-user nodes go.

Decisions, in the user's words or choices:

| Question | User's answer |
|---|---|
| Which file | "1" - a new **v07**, copied from v06 |
| The "three image groups" | a screenshot and *"i mean only this. just this"* - the three picture displays around STEP 12; then *"all features and mechanics of these must go into one node of possible"* |
| Go-ahead on the one-node plan | "1" (twice) |
| Collapsed on the desktop too? | "1" - yes (the 09-22 "desktop stays expanded" memory was updated at 19:19:54) |
| What goes in "physical" | "1" - how she looks: body, face, hair, skin, clothing |
| Shelves for the two boxes | "1" - each box its own shelf |
| The old saved prompts | *"Move the saved prompts to the everything shelf. extract the body parts and create two new presets from them for the body shelf."* |
| Rename | *"make sure all shelves on all nodes with button (save, etc...) shelves include a 'rename' button."* |
| Plumbing nodes | "2" - one "behind the scenes" group |
| Snap strength | "2" - 50 px |
| Cut the hop section in CLAUDE.md? | "2" - keep all four parts |
| Update ComfyUI | *"Update and test."* (earlier, 17:30) |
| SAM editor | "3" - leave it |
| The ~4 s slower runs after the update | "3" - leave it |
| Menu question | "1" - close it (it was moot: already on the new menu) |
| 28 log-only rules into CLAUDE.md | "park" (twice) - still open |
| Fix the old-format wire in v02-v06 | "3" - leave them (~22:25) |

The STEP 12 chart (Came from / Feature / Now in the one node) was put into the STEP 12 note at the
user's request.

### 12.3 The saved prompts

- `freedom_prompt_slots.json` backed up as `freedom_prompt_slots.json.bak_2026-09-24_before_move`.
- **Doggy01** split (bracket-aware check: all 18 phrases accounted for, none added or lost):
  physical shelf "Doggy01 look"; everything-else shelf "Doggy01".
- **Cowgirl01** described a sixteen-year-old in a sexual scene. Claude would not move, split or copy it
  and left it untouched. The user then said *"change cowgirl to eighteen year old girl"*; with that one
  change it was split the same way ("Cowgirl01 look" / "Cowgirl01"), 18 phrases accounted for. The
  backup file still holds the original wording.
- The old whole-prompt shelf is now empty; STEP 7a (whole-prompt shelf) and its note were removed from v07.

### 12.4 What was built, with file times

- `freedom_folder_inspector/save_pick.py` (19:19:07) + `web/preview_pick.js`: auto_save (default on),
  archive_prefix (default `freedom_archive/img`), `images` output, Open Archive Folder button, archive
  status line, `hideOutputImages` so the desktop draws one picture display.
- `freedom_prompt_slots/nodes.py` (19:32:54) + `web/prompt_slots.js`: `FreedomPromptParts` (STEP 7a),
  `/freedom/partslots/{physical|scene}/...` routes, shelf files `freedom_physical_slots.json` and
  `freedom_scene_slots.json`; Rename on the parts sections, the whole-prompt shelf and the phrase shelf
  (a phrase's words are its name - first press unlocks, second saves).
- `freedom_portrait_control` (`presets.py`, `__init__.py`, `web/portrait_control.js`, last 20:01:06):
  Rename on 4a, 4b-4g and STEP 3's "Her recipes"; `/freedom/pm/preset/rename`; top-first layout for 4a and
  4b-4g with labelled section gaps on 4a; values put back by name after every load.
- `freedom_face_competition/web/presets_method1.js` (19:33:20): a visible Rename button.
- `freedom_folder_inspector/web/mobile_messages.js` (20:08:06): registers `mobile_latent_shape`.
- `user/default/comfy.settings.json`: `Comfy.SnapToGrid.GridSize` = 50 (backup
  `comfy.settings.json.bak_2026-09-24_before_grid50`).
- v07 layout (copy before it: `logs/comfyui_session_2026-09-24/v07_before_layout.json`, 19:33:40) and
  titles/notes (copy before: `v07_before_titles.json`, 19:35:17). Last v07 write 20:04:03 (the wire fix).

### 12.5 The restart through the launcher (19:43-19:52)

- The user said to restart. The screen was **locked** (Windows lock screen had focus), and keystrokes do not
  reach the launcher while locked; Claude stopped rather than kill processes (logged rule: never kill the
  launcher's processes). The user unlocked it.
- Claude pressed **9** in the old launcher (PID 31228, started 07:39:27) - it exited cleanly. Its hold on
  the old `logs/comfyui.log` was released, and that file was moved to
  `REPO_comfyUI/logs/comfyui_launcher_2026-08-to-09-24.log`. No ComfyUI log is left in the launcher folder.
- A fresh launcher was started from `start_koboldcpp_media.bat` (PID 548, 19:46:09).
- **Claude's mistake:** the "4" meant for the launcher went into the Claude Code window instead and was sent
  as a user message (both windows belong to Windows Terminal; Windows-MCP could not report keyboard focus).
  The same mistake is recorded in the logs from 2026-09-13. Claude stopped typing and asked the user to press
  4. The user did; ComfyUI came up at **19:51:33**, and its header landed in `REPO_comfyUI/logs/comfyui.log`
  - the launcher change works. Server PIDs 13740 -> 35536.
- Startup: no errors, no import failures, all 26 custom nodes, every package version matches;
  `FreedomPromptParts` registered; the pick node shows `auto_save`, `archive_prefix` and its output.

### 12.6 The old Chrome tabs

Two earlier test tabs (still on the pre-change code) held v06 and an empty workflow. Following the
asterisk-tab procedure: v06 closed in-app with "Close anyway" (v06 on disk unchanged, 01:10:07); closing the
tabs timed out on Chrome's "Leave site?" box; both were then force-navigated to the launch page (discarding
two empty "Unsaved Workflow" canvases). The `navigate` tool accepted `force: true` even though its schema
does not list it.

### 12.7 Testing, and the four faults found and fixed (19:52-20:12)

1. **4g lost its values in the 01:10 save of v06.** Compared every v07 value against the committed v06:
   only 4g's `style` and `add_extra_instructions` were blanked. Restored `descriptive`, `true` in v07 only.
2. **Values landing in the wrong boxes after the top-first reorder.** Found by comparing each node's saved
   values before and after a load. Frontend 1.53.6 (settingStore `serialiseWidgetValues`,
   `createWidgetRestorationState`) writes a named copy and restores by name when it can, otherwise by
   position against the new screen order. An earlier attempt (inserting blank slots before loading) did not
   work - tested and replaced. Final fix: after ComfyUI's own restore, every value is put back by name (named
   copy, else the original declared order, including shorter pre-change saves). Verified: v07 all 162
   Portrait Master/4a settings match by name; v05 138 checked, the only two differences are 4a `mode`/`preset`
   stored as `null` in v05, which keep defaults exactly as before.
3. **DataCloneError when loading a second workflow.** Traced to wire 58 (STEP 2 -> STEP 5), whose type was
   saved as the option list; the new frontend wraps it in a Vue proxy that `structuredClone` rejects. Both
   slot ends are `"COMBO"`. Researched: ComfyUI_frontend issue #18165, PR #18252, backport PR #18517 (merged
   2026-09-23 into core/1.53, not released) - covers node extension fields only, not wires. Fixed in v07 by
   setting the wire type to `COMBO`: v07 then loaded 3 times in a row. v02-v06 all still carry the list;
   **user chose to leave them.**
4. **Console: "Unknown message type mobile_latent_shape"** during every desktop run. Sent by
   comfyui-mobile-frontend (`mobile_latent_shape.py` lines 123-132; identical to the author's latest copy,
   line endings aside); the desktop page logs any unregistered type once. Fixed by registering and ignoring
   it on the desktop (`mobile_messages.js`); gone after the fix; the phone is unaffected.

Also confirmed on screen: STEP 12 shows one picture display (4 cards, no extra strip); Open Archive Folder
present; all six shelf panels carry Rename (4a, 4b, STEP 3 recipes, 7b phrases, both 7a sections); Rename
routes tested for real (7a physical slot 1 renamed and restored, text unchanged; a throwaway 4a preset
`pm_zz_renametest` saved, renamed, deleted - nothing left behind).

**Runs:** ~20:06 success, 39.08 s, img_01491-01494 archived; ~20:10 success, 37.41 s, img_01495-01498
archived. No server errors. Remaining console errors: the two known ones (graph accessed before
initialization - upstream fix unreleased; SAM editor - left by the user's choice).

### 12.8 Watching after the tests (20:12 → 22:35)

- The log watcher was re-armed every 30 minutes on PIDs 13740/35536; quiet until 22:30.
- **22:30:01-22:30:03, five connection-reset errors; 22:32:02.7, 03.9, 05.9, three more**
  (`ConnectionResetError [WinError 10054]` in `_call_connection_lost`). At 22:30 the iPhone had two
  connections open and two just closed; Chrome's one connection stayed open. Same pattern as the morning,
  when every burst was matched to the iPhone - but the connection recorder was not running, so these were
  **not** matched.
- The recorder was restarted at 22:32:13, now writing into
  `logs/comfyui_session_2026-09-24/comfyui_connections_from_2232.log` (per the logs rule). It started just
  after the last burst; its first reading shows two iPhone connections open.

### 12.9 State right now

- ComfyUI 0.37.0 running **from the launcher** (launcher PID 548; server 13740 -> 35536); its log is
  `REPO_comfyUI/logs/comfyui.log`.
- Log watcher and connection recorder running (both session-temporary scripts in the scratchpad; the
  recorder's output is in `logs/`).
- Chrome: tab 1273372023 on ComfyUI with an empty "Unsaved Workflow" (v07 closed in-app, never saved from
  the page); an old tab left outside the extension's group showing the launch page's directory listing.
  Launch-page server stopped.
- Files: v07 is the working version; v06 untouched since 01:10:07; nothing committed in any repo.
- Open question (parked by the user): whether to write the 28 log-only rules into `REPO_comfyUI/CLAUDE.md`.
