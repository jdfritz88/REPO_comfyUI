# Comfy Portal sync bug, LoRA-app research, and installing a second mobile client

**Date:** 2026-09-06 → 2026-09-07
**Branch:** branch08-remote-access (created at the end of this session, off Branch07)

---

## 1. Comfy Portal (the iOS app) showed "Sync Error" / server offline

User's phone app (Comfy Portal, installed 2026-09-05 per `ram_fix_and_remote_access_2026-09-05.md`) started
showing "An error occurred while syncing workflows. Please check your connection and server status" and
"No Synced Server Workflows," with the server row reading "Offline."

**Investigated methodically, ruling things out one at a time rather than guessing:**

1. Confirmed ComfyUI itself was up and listening on both `127.0.0.1:8188` and the Tailscale IP
   `<TAILSCALE_IP>:8188` (`netstat`).
2. Confirmed the `comfy-portal-endpoint` plugin was actually installed on disk
   (`app_cabinet/comfyui/custom_nodes/comfy-portal-endpoint`) and loaded cleanly in `comfyui.log`
   — nothing needed reinstalling, correcting an earlier wrong assumption.
3. Hit the plugin's own routes directly with `curl` against the exact Tailscale address the phone uses:
   `/cpe/health`, `/cpe/workflow/list`, and `/cpe/workflow/get-and-convert` all returned success, including a
   real workflow conversion. The headless-Chromium browser the plugin uses for UI→API conversion lazily
   initializes on first request (`/cpe/health` showed `not_initialized` until the first real call, then
   flipped to `ready`) — not a bug, just how the plugin starts.
4. Checked Windows Firewall: no explicit rule blocking it, and there's a pre-existing "Python" inbound-allow
   rule covering the Private profile (which the Tailscale interface is categorized under) for both TCP and
   UDP, any port — so the firewall was never the problem either.
5. Confirmed on the phone that Tailscale itself was connected, and both this PC (`<THIS_PC>`,
   `<TAILSCALE_IP>`) and the phone (`<PHONE>`, `<PHONE_TAILSCALE_IP>`) showed green/online in the
   tailnet.

Every server-side and network-level check passed. The actual fix was on the phone: after the user tapped
refresh in the app, the server came back "online," but then showed "24 models · 0 workflows" until a **model
was selected** in the app — once a model was picked, the sync fully completed and the workflows list
populated. Root cause on the app's own side was never fully pinned down beyond that; noting it here in case
it recurs. (`ram_fix_and_remote_access_2026-09-05.md` §5 also flags "Use SSL: Never" as the fix for a
similar-looking earlier "Offline" state — worth checking that setting first if this happens again.)

---

## 2. Research: does anything else on the market expose LoRAs from a ComfyUI server through a mobile client?

User asked to deep-dive competitors to Comfy Portal specifically for live LoRA access read from the server
(not bundled/static). Findings, verified via WebFetch against each project's own docs/README, not assumed
from search snippets:

| App | Confirmed live LoRA picker from server? | Notes |
|---|---|---|
| **ComfyChair** (Android, native, GPL-3.0) | **Yes** | Explicitly loads samplers/schedulers/LoRAs dynamically from the server; hierarchical folder-tree LoRA dropdown; stack up to 5 LoRAs with individual strengths. Open source: `github.com/legal-hkr/comfychair`. |
| **ComfyUI Mobile Frontend** (cosmicbuffalo) | **Yes** | Not a native app — a ComfyUI *custom node* served by the same ComfyUI process over the same HTTP/WebSocket API; integrates with the separate `ComfyUI-Lora-Manager` node for a richer picker (thumbnails, version/base-model badges). |
| **Mobile Lens** | **Yes (claimed)** | No-install static-HTML web UI, connects directly to the ComfyUI server over LAN; LoRA picker with weight sliders. Couldn't find an official site URL, only a Civitai writeup and a Japanese X post. |
| **ComfyLink** | Unclear | Has live workflow sync/remote triggering; no documentation found specifically describing a live LoRA picker. |
| **Comfy Remote**, **ComfyUInator** (iOS) | Unclear | App Store pages didn't have enough detail either way. |

Conclusion given to the user: ComfyChair looked like the closest match to what they actually wanted (open
source, dynamic LoRA folder tree, multi-LoRA stacking) — but the path actually taken was installing
`comfyui-mobile-frontend` instead, since it runs as a custom node inside the existing ComfyUI install rather
than a separate native app, and Comfy Portal's underlying limitation (no LoRA endpoint in its
`comfy-portal-endpoint` companion plugin) was independently confirmed by reading that plugin's own README —
it only exposes `/cpe/health` and workflow list/get/save/convert routes, nothing model- or LoRA-related.

---

## 3. Researched `--enable-compress-response-body` before deciding whether to add it

Read ComfyUI's actual `server.py` (not just docs) to confirm the real behavior before recommending it:
- Only compresses `application/json` and `text/plain` responses — binary responses (including `/view`,
  which streams generated images) are explicitly excluded, so it has zero effect on image transfer.
- No size threshold; compresses every matching response when the client sends `Accept-Encoding: gzip`.
- Runs in the request-handling path, not anywhere near GPU sampling — no interaction with generation speed.

Net effect for this setup: real speedup for a mobile frontend's `/object_info` calls (large, since this
install has many custom nodes) and workflow-JSON loads, at effectively no cost. **Not yet added to the
launcher** — this was researched but the user moved on to the interface-editing question before deciding
whether to add the flag to `_make_comfyui_service()`. Still open.

---

## 4. Researched the actual security model before answering "can anyone with the address get in?"

User's worry: since ComfyUI is listening on `<TAILSCALE_IP>:8188`, "anyone with the web address" could
access it. Checked rather than assumed:

- Tailscale addresses (the `100.x.x.x` CGNAT range) are only routable between devices in the same tailnet —
  not reachable from the public internet at all. Confirmed against Tailscale's own device-visibility docs.
  Today the tailnet has exactly two devices: this PC and the user's iPhone, both under `jdfritz88@gmail.com`.
- ComfyUI's own official `SECURITY.md` states its trust model is "trusted operator on a trusted network" —
  no login, and anyone who can reach the port can run arbitrary Python via custom nodes.
- Checked this specific install for the known **CVE-2025-67303** (ComfyUI-Manager RCE, no auth needed) —
  confirmed `custom_nodes/` does **not** have ComfyUI-Manager installed, so that specific hole doesn't apply
  here.
- Real exposure boundary for this setup is therefore Tailscale account security, not ComfyUI itself: the
  risk is (a) ever adding another person's device to the tailnet, or (b) the Google account tied to
  Tailscale (`jdfritz88@gmail.com`) being compromised.
- Noted that hardening ComfyUI itself with a login page (e.g. `ComfyUI-Login`) is a bad option here — the
  `comfy-portal-endpoint` plugin's own README states it's explicitly incompatible with any extension that
  blocks/intercepts the ComfyUI frontend, since its headless-browser conversion step needs unrestricted page
  access.

---

## 5. Licensing question: can the mobile frontend be repackaged and sold on Patreon?

Checked both relevant licenses directly rather than assuming "open source = free to resell":
- `comfyui-mobile-frontend` itself: **MIT** (confirmed via the actual LICENSE file) — permits commercial use,
  modification, distribution, and selling copies; the only requirement is keeping the copyright/permission
  notice included.
- ComfyUI core, which the frontend depends on to run at all: **GPLv3** (confirmed via
  `comfyanonymous/ComfyUI`'s LICENSE) — selling is technically allowed under GPL, but any distributed,
  working product built on it must ship full source and can't restrict a paying customer from freely
  redistributing what they received. This effectively rules out an "exclusive paid access" Patreon model for
  anything that bundles ComfyUI itself, even though the frontend piece alone is unrestricted.

---

## 6. Installed `comfyui-mobile-frontend` as a second mobile client, alongside Comfy Portal

- Cloned `github.com/cosmicbuffalo/comfyui-mobile-frontend` into
  `app_cabinet/comfyui/custom_nodes/comfyui-mobile-frontend` (same "not tracked in this repo" pattern as
  every other third-party custom node here).
- ComfyUI was already running (in "Server + phone access" mode, left up from the prior session) — stopped it
  (`taskkill /T` needed `/F` to actually kill the full process tree; some child processes resisted the
  graceful signal) and relaunched it with the same `--listen 127.0.0.1,<TAILSCALE_IP>` flags so the new
  custom node would load.
- Confirmed in `comfyui.log`: `[Mobile Frontend] Mobile UI enabled at: /mobile` — loaded clean.

### Browser automation troubleshooting (Claude-in-Chrome)
- Chrome wasn't running on the machine at all at first — `tasklist` showed zero Chrome processes, which is
  why the extension reported "not connected." Not a permissions issue.
- Found the correct Chrome profile directory for "John Doe" by reading Chrome's own `Local State` file
  rather than guessing (`Default` = `jesperanto1@gmail.com` = Jacob's profile; `Profile 1` = `John` /
  `jdfritz88@gmail.com` = the John Doe profile) — launched with
  `chrome.exe --profile-directory="Profile 1"`.
- Once Chrome was up, the extension connected fine on real sites (verified against `example.com`), but
  screenshot/page-read calls specifically failed against `http://127.0.0.1:8188/...` with "Frame with ID 0 is
  showing error page" — even though `curl` against the identical URL worked perfectly and returned real
  HTML. Confirmed this is a loopback-specific block: the exact same page loaded and rendered correctly over
  the Tailscale address `http://<TAILSCALE_IP>:8188/mobile/` instead. Not a ComfyUI or mobile-frontend
  problem — an extension-side restriction on `127.0.0.1`.

### Verified the actual interface, live, for editing/rearranging capability
User specifically wanted to know whether a wrongly-arranged mobile layout could be fixed. Confirmed live
(not from docs):
- **Preferences** (Server → Preferences) are behavior toggles only — fast/latent previews, restore lost
  queue, alias filepaths, credit-in-workflow, infinite mode, hide-bottom-bar-when-idle, subgraph following,
  and generation notifications. No layout/panel rearrangement here, matching what the docs implied but didn't
  state outright.
- **Every node card's `...` menu** has real editing power beyond what the README/USER_GUIDE described: Edit
  label, Change color, Select, Bypass, Hide, Duplicate, Copy, **Move**, Delete.
- **"Move" opens a "Reposition Nodes" screen** — a drag-handle (☰) list of every card, grouped by the
  workflow's own group boxes (e.g. "SET IT UP"), letting the user drag-and-drop reorder the entire mobile
  card list. This is the actual answer to "what if things are arranged wrong" — confirmed by opening it
  against the real `Freedom_bigLust_SDXL` workflow, then canceling out without saving so the production
  workflow wasn't altered.
- All saved workflows (`Freedom_Face_Competition`, `Freedom_Face_Image`, `Freedom_Face_Shelf`, both video
  workflows, `Freedom_bigLust_SDXL`) showed up correctly in "My Workflows," and the custom `READ ME FIRST`
  markdown note rendered exactly as authored on the desktop version.

---

## 7. Current state at end of session

- ComfyUI: UP, phone-access mode, `--listen 127.0.0.1,<TAILSCALE_IP>`, port 8188.
- `comfyui-mobile-frontend` installed and loading clean; reachable at `http://<TAILSCALE_IP>:8188/mobile` from
  Safari on the phone (not `127.0.0.1` — that address is specifically blocked for the Claude-in-Chrome
  extension, though it works fine from an actual phone browser since the extension isn't involved there).
- Comfy Portal (the original native app) is still installed and working — this is a second, alternative
  client, not a replacement.
- Chrome (John Doe profile) is open on the desktop from this session's testing.

## 8. Open items

1. `--enable-compress-response-body` researched and recommended but **not added** to `launcher.py`'s
   `_make_comfyui_service()` — still needs the user's go-ahead.
2. The model-deletion review from `work_log_2026-09-02_continued.md` §7 is still unanswered (three
   yes/no questions, nothing deleted yet) — unrelated to this session but still outstanding.
3. Root cause of the original Comfy Portal "0 workflows until a model is selected" behavior was never fully
   identified past "picking a model unblocked the sync" — worth watching for a recurrence.

---

## 9. Follow-up: new branch, and a proper description for option 4  [2026-09-07]

- Created `branch08-remote-access` off Branch07 and committed this log (plus the previously-uncommitted
  2026-09-05 log) there — commit `9cf8514`.
- User asked for the launcher's "server choice" (option 4, "Start ComfyUI Server and phone access") to have
  a proper description covering both phone interfaces. Clarified first which of two possible asks this was
  (a Settings on/off toggle for the mobile-frontend node, vs. just a better description of option 4) — user
  meant the description.
- Added `SERVER_HELP`, a new plain-language help block in `launcher.py` (same style/placement as the
  existing `MODE_HELP` for options 1/2), printed on the main menu screen above the numbered choices. Explains
  that option 4 is Tailscale-only (not internet-reachable), and that Comfy Portal and the
  `comfyui-mobile-frontend` browser page (`/mobile`) both work at the same time once it's up — including the
  drag-reorder capability found in §6, since that's the actual answer to "what if the layout looks wrong."
- Updated the post-start "Stack summary" printed after choosing option 4 to list both URLs explicitly (the
  bare phone URL for Comfy Portal, and the same address with `/mobile` appended for the browser page)
  instead of just the one bare address it printed before.
- Verified: `ast.parse` on the edited file, and a live `printf "8\n" | python launcher.py` smoke test
  confirming the new block renders correctly and the launcher still exits cleanly.
- Committed as `ad41618` on `branch08-remote-access`.
