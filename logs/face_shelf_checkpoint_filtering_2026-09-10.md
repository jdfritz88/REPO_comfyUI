# Face Shelf checkpoint-aware filtering — 2026-09-10

Session continued from an earlier compaction. One feature end to end: making the
Face Shelf panel show **only** the trained faces that match the checkpoint the
workflow is actually using, and keep up when the checkpoint changes. Getting
there took two separate fixes — one backend, one frontend — separated by a long
misdiagnosis that is worth recording in full, because the same trap will come
back otherwise.

Branch: `branch09-comfyui-repo-migration`. Three commits, listed at the bottom.

---

## 1. Getting ComfyUI running again

Two blockers before any feature work, both from the pre-compaction part of the
session:

- **Wrong Python interpreter.** ComfyUI was being launched with the Windows
  Store stub at
  `C:\Users\jespe\AppData\Local\Microsoft\WindowsApps\python.exe`, which has none
  of the ComfyUI dependencies, so the server never came up and the port refused
  connections. Fixed by always launching with the venv interpreter:
  `F:\Apps\freedom_system\REPO_comfyUI\venv\Scripts\python.exe`.
- **Bound to loopback only.** ComfyUI was reachable at `127.0.0.1:8188` on the
  laptop but not from the phone over Tailscale, because it was listening on the
  loopback address only. Fixed by launching with `--listen 0.0.0.0`, after which
  `http://<TAILSCALE_IP>:8188` worked from the phone.

Standing launch line used for the rest of the session:

```
F:/Apps/freedom_system/REPO_comfyUI/venv/Scripts/python.exe main.py --listen 0.0.0.0 --port 8188
```

---

## 2. The requirement

Starting point: the Face Shelf showed **all four** trained-face cards at once.
The registry at `REPO_comfyUI/models/loras/faces/_registry.json` holds four LoRAs
for one person (Susana), two per checkpoint family:

| name | family | crop |
| --- | --- | --- |
| `susana_head_sdxl` | `sdxl` | head |
| `susana_head_body_sdxl` | `sdxl` | head_body |
| `susana_head_sdxl_pony` | `sdxl_pony` | head |
| `susana_head_body_sdxl_pony` | `sdxl_pony` | head_body |

A `sdxl` face LoRA does not work on a Pony-derived checkpoint and vice versa, so
showing all four invites picking a broken combination.

The requirement, after clarification (the first two readings were wrong and got
corrected): the shelf should show **only the two faces — face, and face+body —
belonging to the currently selected checkpoint**, and it should **auto-update
when the checkpoint changes**, not require a manual Refresh. Explicit instruction
to build it and to "test it for both models" (bigLust and lustify).

This mirrors what commit `85025e9` already did for the LoRA Stack node
("only offer LoRAs that match the wired checkpoint's architecture") — same idea,
different node.

---

## 3. Backend fix — family detection missed lustify

Most of the machinery already existed and was correct:

- `nodes.py` route `GET /freedom/faceshelf/list` already accepted a `checkpoint`
  query parameter, resolved it to a family, and returned `cards` (filtered) plus
  `all_cards` (everything) plus `family`.
- `face_shelf.js` already had `findCheckpointWidget()` / `findCheckpointName()` /
  `hookCheckpointWidget()`, and `load()` already appended `?checkpoint=…`.

The gap was the family classifier. Before:

```python
def _checkpoint_family(checkpoint_name: str) -> str:
    return "sdxl_pony" if "pony" in checkpoint_name.lower() else "sdxl"
```

`lustifyNSFWCheckpoint_v10Krea2.safetensors` is Pony-derived but has no "pony"
in its filename, so it fell through to `sdxl` and got shown the wrong two faces.
After:

```python
def _checkpoint_family(checkpoint_name: str) -> str:
    lower = checkpoint_name.lower()
    return "sdxl_pony" if ("pony" in lower or "lustify" in lower or "krea" in lower) else "sdxl"
```

Verified directly against the running server:

```
bigLust_v16.safetensors                    -> 2 cards, family sdxl
lustifyNSFWCheckpoint_v10Krea2.safetensors -> 2 cards, family sdxl_pony
```

---

## 4. The misdiagnosis — a stale server process, not a bytecode cache

Between writing that fix and seeing it work, a long stretch was lost to a wrong
theory. Recording it in detail because the symptoms were extremely convincing.

**Symptom:** the edit was on disk and correct, but the API kept returning the old
answer. Escalating attempts to prove the file was being used all failed:

1. Added `print(...)` to `stderr` inside `_checkpoint_family()` — never appeared.
2. Added `print(...)` inside the route handler — never appeared.
3. Switched to writing to a file instead of stderr — the file was never created.
4. Put `raise Exception("TEST ERROR")` as the first line of the route — the API
   still returned a normal 200 with real data.
5. Replaced the route's return value entirely with a marker JSON object — the
   original payload still came back.

**Wrong theory chased for most of that time:** Python bytecode caching. Deleted
`__pycache__` directories and `*.pyc` files repeatedly, across the whole
`REPO_comfyUI` tree, restarting between each attempt. It never helped, because
that was not the cause.

**Actual cause:** the old ComfyUI process never died. `pkill -9 -f "python.*main.py"`
did **not** match the running processes — their command line is
`/f/Apps/freedom_system/REPO_comfyUI/venv/Scripts/python`, so the pattern missed.
Each "restart" launched a new server that immediately failed with:

```
ERROR Port 8188 is already in use on address 0.0.0.0.
```

…and every subsequent `curl` was answered by the **original, still-running
server executing the original code**. A `ps aux` finally showed two survivors
(PIDs 1917 and 1964); killing them by PID and starting cleanly made the fix take
effect immediately, on the first try.

**Rule for next time:** before concluding a code change "isn't taking effect",
confirm the old process is actually gone (`ps aux | grep -i python`) and that the
port is genuinely free. A "port already in use" line in the startup log means the
server being tested is *not* the one just launched. Kill by PID when a pattern
kill reports success but the process list disagrees.

### 4.1 Related trap — the extension exists twice

Discovered while chasing the above, and real regardless: every `freedom_*`
extension exists as **two divergent copies**.

| copy | path | role |
| --- | --- | --- |
| live | `REPO_comfyUI/custom_nodes/freedom_face_shelf/` | what the running server imports and serves |
| git-tracked | `REPO_koboldccp_sst_tts_media/comfyui_ext/freedom_face_shelf/` | what version control sees |

Confirmed as genuinely separate files (different inodes, not links or symlinks).
Editing only the git copy changes nothing about the running app; editing only the
live copy leaves the change uncommitted. Which one is loaded was settled by
printing `os.path.abspath(__file__)` at import — it reported the `custom_nodes`
path.

Working rule adopted: edit the live copy, test against the running server, mirror
into `comfyui_ext/`, then `diff` both files before committing so what ships is
exactly what was tested.

---

## 5. The real bug — a race between node creation and link restoration

With the backend correct and verified by `curl`, the panel in the browser **still
showed all four cards**. Reproduced it and captured the contradiction that
explains everything:

```json
{
  "trail": ["FreedomFaceShelf", "CheckpointLoaderSimple"],
  "detectedCheckpoint": "cyberrealisticPony_v110.safetensors",
  "cardCount": 4,
  "compatBar": "No checkpoint found upstream - showing every trained face, unfiltered."
}
```

The checkpoint **was** findable at query time — the upstream walk reached the
`CheckpointLoaderSimple` in a single hop — yet the panel had rendered as though
it had found nothing. That is a timing problem, not a wiring or backend problem.

**Mechanism:**

1. Loading a workflow makes ComfyUI construct every node **first**, and restore
   the links between them **afterwards**.
2. `Shelf`'s constructor calls `this.load()` immediately.
3. At that moment `findCheckpointWidget()` walks the shelf's `MODEL` input, finds
   `input.link` is still null, and returns `null`.
4. `load()` therefore requests `/freedom/faceshelf/list` with **no** `checkpoint`
   parameter, and the server correctly answers with every card, unfiltered.
5. `hookCheckpointWidget()` fails for the identical reason — there is no widget
   to hook yet — so the checkpoint-change callback is **never installed**.
6. Nothing ever re-runs the filter. The only existing re-entry points were the
   manual **Refresh** button and that never-installed callback.

Step 5 is why the second half of the requirement failed too: changing the
checkpoint did not update the shelf, because the listener that would have noticed
was never attached. A deadlock — too early to find the checkpoint, and no second
attempt.

There **was** an `onConfigure` hook on the node already, but it only called
`syncEnabled()` and `syncTrigger()`. It never called `load()`, so the filter was
never recomputed after configure.

---

## 6. The fix

Three changes in `web/face_shelf.js`.

**A debounced reload**, because graph configure restores links one at a time and
several triggers can fire in the same tick:

```js
reload(){
  clearTimeout(this.__reloadT);
  this.__reloadT = setTimeout(() => this.load(), 50);
}
```

**Re-filter once the graph is fully wired** — an extension-level hook, sibling to
`beforeRegisterNodeDef`:

```js
afterConfigureGraph(){
  for (const n of (app.graph?._nodes || []))
    if (n.__ffs) n.__ffs.reload();
},
```

**Re-filter when the MODEL input is rewired** — covers a node just dragged in and
wired up, and moving the shelf to a different checkpoint loader:

```js
const onConn = nodeType.prototype.onConnectionsChange;
nodeType.prototype.onConnectionsChange = function(){
  const r = onConn ? onConn.apply(this, arguments) : undefined;
  if (this.__ffs) this.__ffs.reload();
  return r;
};
```

Once `load()` succeeds, the pre-existing `hookCheckpointWidget()` attaches
normally and checkpoint changes flow through on their own — no extra machinery
needed for the auto-update half of the requirement.

Debug `console.log` calls added during the hunt were removed, as were the
leftover `print(...)` statements in `nodes.py`.

---

## 7. Verification

Tested against the real workflow, `Freedom_bigLust_SDXL v03.json` (Face Shelf
node id `2`, wired one hop to a `CheckpointLoaderSimple`), driven in Chrome over
the Tailscale address, from a clean page load each time.

| case | cards | which |
| --- | --- | --- |
| A. on workflow load *(previously broken — showed 4)* | 2 | `susana_head_sdxl_pony`, `susana_head_body_sdxl_pony` |
| B. switched to `bigLust_v16.safetensors` | 2 | `susana_head_sdxl`, `susana_head_body_sdxl` |
| C. switched to `lustifyNSFWCheckpoint_v10Krea2.safetensors` | 2 | `susana_head_sdxl_pony`, `susana_head_body_sdxl_pony` |
| D. switched back to `bigLust_v16.safetensors` | 2 | `susana_head_sdxl`, `susana_head_body_sdxl` |

Compatibility bar text confirmed alongside, e.g.:

```
Showing faces trained for sdxl - from bigLust_v16.safetensors (2 hidden - wrong checkpoint family)
Showing faces trained for sdxl_pony - from lustifyNSFWCheckpoint_v10Krea2.safetensors (2 hidden - wrong checkpoint family)
```

Confirmed **visually** by screenshot as well as by DOM inspection — the
thumbnail images themselves change between the two models, not merely the
captions. Both copies of `nodes.py` and `face_shelf.js` were `diff`ed to be
byte-identical before committing, so the committed code is the tested code. The
saved workflow file was verified untouched (same size and mtime, 07:43).

---

## 8. Commits

| sha | subject |
| --- | --- |
| `416f466` | Face Shelf: detect lustify and krea checkpoints as pony-based |
| `a67e45e` | Face Shelf: add debug logging for checkpoint detection |
| `f5bfd3f` | Face Shelf: re-filter once the graph is wired, not before it exists |

`a67e45e` is a debugging-only commit; its logging was removed again in `f5bfd3f`.

---

## 9. Carry-forward notes

- **Browser cache.** Extension `.js` is served fresh from disk, so no server
  restart is needed for frontend changes — but an already-open browser will keep
  running the old file. A hard refresh (`Ctrl+Shift+R`) is required to pick up
  `face_shelf.js` changes.
- **`_checkpoint_family()` is filename-based.** It matches on `pony`, `lustify`
  and `krea` substrings. Any future Pony-derived checkpoint whose filename
  contains none of those will be misclassified as `sdxl` and shown the wrong
  faces. If that keeps happening, the family belongs in a lookup table or in
  checkpoint metadata rather than in the filename.
- **Stray workflow tabs.** Testing left four "Unsaved Workflow" scratch tabs open
  in ComfyUI. Left in place rather than closed, since unsaved tabs cannot be
  recovered — worth clearing manually given the standing rule about closing old
  workflows before relaunching.
