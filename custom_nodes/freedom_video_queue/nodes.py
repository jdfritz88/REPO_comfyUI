# ==========================================
# FREEDOM SYSTEM - ComfyUI Video Queue  (Phase B)
# queue.py
# ==========================================
#
# A 9-slot queue that feeds the Wan image-to-video graph one item at a time.
#
#   * "Send to Video Queue" (button on the Preview & Pick panel) drops picked
#     images into the queue.
#   * Each slot carries its OWN motion prompt, size and length.
#   * The whole queue + settings + last-used prompt live in ONE string on the
#     FreedomVideoQueue node -> saved inside the workflow, survives a restart.
#   * On each run the node outputs the SELECTED slot (or the first pending one)
#     as (start_image, motion_prompt, width, height, length_frames) for the
#     Wan graph.
#   * "auto_start" (default on) makes the panel press Run when a new item is
#     enqueued.
#
# Auto-advance-on-completion, the full Wan workflow, video re-queue / "extend",
# and the green-frame-for-video indicator are Phase C / D.
#
# Web API (localhost only, used by web/video_queue.js + preview_pick.js):
#   GET  /freedom/video/state
#   POST /freedom/video/enqueue   {images:[{filename,subfolder,type}], prompt}
#   POST /freedom/video/select    {index}
#   POST /freedom/video/set_prompt {index, prompt}
#   POST /freedom/video/set_slot   {index, width?, height?, length_s?}
#   POST /freedom/video/clear      {index}            (or {all:true})
#   POST /freedom/video/complete   {index, video?}    (mark done, remember prompt)
#   GET  /freedom/video/settings
#   POST /freedom/video/settings   {auto_start?, width?, height?, length_s?, user_folder?}

import json
import os
import time
import uuid

import numpy as np
import torch
from PIL import Image

import folder_paths
from aiohttp import web
from server import PromptServer

SLOTS = 9
FPS = 24
MAX_SEG_S = 5            # one Wan-5B generation caps here; longer = auto-chained
MAX_SEG_FRAMES = 121
HOLD_SUB = "freedom_video_hold"

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(HERE, "freedom_video_settings.json")

SIZE_PRESETS = [
    {"label": "832x480 wide  (default - fits your card, ~2.5 min)", "w": 832, "h": 480},
    {"label": "1024x512 wide (letterbox, a bit slower)", "w": 1024, "h": 512},
    {"label": "1280x704 wide (Wan native - big, slow, needs video mode)", "w": 1280, "h": 704},
    {"label": "704x1280 tall", "w": 704, "h": 1280},
    {"label": "960x960 square", "w": 960, "h": 960},
]
# seconds. 3.4 s = 81 frames = the Wan 2.2 14B model's native clip length (fastest,
# no stitching). 5+ s are built by auto-chaining, so they take proportionally longer.
LENGTH_PRESETS = [3.4, 5, 10, 15, 20]

DEFAULT_SETTINGS = {
    "auto_start": True,
    "width": 832,
    "height": 480,
    "length_s": 3.4,
    "user_folder": "",          # "Set User Save Folder" for finished videos (Phase C)
    "video_family": "Wan 2.2",   # what the Freedom Video workflow runs - the Folder
                                 # Inspector uses this to flag incompatible video LoRAs
}


# --------------------------------------------------------------------------
# settings (fallback defaults only - the node's `state` widget is the source
# of truth once a workflow is loaded; see #19)
# --------------------------------------------------------------------------
def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
            s.update(json.load(fh))
    except Exception:
        pass
    return s


def save_settings(s):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
            json.dump(s, fh, indent=1)
    except OSError:
        pass


def hold_dir():
    d = os.path.join(folder_paths.get_temp_directory(), HOLD_SUB)
    os.makedirs(d, exist_ok=True)
    return d


def length_frames(seconds):
    """Wan latents are temporally /4, so frame count must be 4n+1."""
    f = int(round(seconds * FPS))
    return max(5, f - ((f - 1) % 4))


# --------------------------------------------------------------------------
# the queue (in-memory; mirrored into the node's `state` widget by the panel)
# --------------------------------------------------------------------------
def _blank_slot():
    return {"id": "", "src": None, "prompt": "", "width": None, "height": None,
            "length_s": None, "want_s": None, "status": "empty", "kind": "image",
            "thumb": None, "extends": None}


_QUEUE = [_blank_slot() for _ in range(SLOTS)]
_SELECTED = 0
_LAST_PROMPT = ""
_RUNNING_IDX = None          # slot the current render belongs to (set by run())
_LAST_VIDEO = {"auto": None, "prompt": "", "when": 0}   # last auto-saved video

VIDEO_FORMATS = {
    # label -> (container ext, ffmpeg codec, pix_fmt)
    "MP4 (H.264) - plays everywhere":      (".mp4",  "libx264",     "yuv420p"),
    "WebM (VP9) - web, open, small":       (".webm", "libvpx-vp9",  "yuv420p"),
    "MOV (H.264) - video editors / Apple": (".mov",  "libx264",     "yuv420p"),
}
DEFAULT_FORMAT = "MP4 (H.264) - plays everywhere"


def _state():
    s = load_settings()
    return {
        "slots": _QUEUE,
        "selected": _SELECTED,
        "last_prompt": _LAST_PROMPT,
        "settings": s,
        "size_presets": SIZE_PRESETS,
        "length_presets": LENGTH_PRESETS,
    }


def _first_pending():
    for i, sl in enumerate(_QUEUE):
        if sl["status"] in ("pending", "ready"):
            return i
    return None


def _copy_hold(image_ref):
    """Copy an image the panel handed us (temp/output) into our own hold dir so
    it survives the source being cleared. Returns a {filename,subfolder,type}."""
    fn = str(image_ref.get("filename", ""))
    sub = str(image_ref.get("subfolder", ""))
    typ = str(image_ref.get("type", "temp"))
    base = folder_paths.get_temp_directory() if typ == "temp" else folder_paths.get_output_directory()
    if typ == "input":
        base = folder_paths.get_input_directory()
    src = os.path.join(base, sub, fn)
    if not os.path.isfile(src):
        return None
    newname = uuid.uuid4().hex[:10] + os.path.splitext(fn)[1]
    dst = os.path.join(hold_dir(), newname)
    try:
        import shutil
        shutil.copy2(src, dst)
    except Exception:
        return None
    return {"filename": newname, "subfolder": HOLD_SUB, "type": "temp"}


def _load_tensor(src_ref):
    """Load a queued image ref -> (1,H,W,3) float tensor for the Wan graph."""
    if not src_ref:
        raise ValueError("This queue slot has no image.")
    base = folder_paths.get_temp_directory()
    path = os.path.join(base, src_ref.get("subfolder", ""), src_ref["filename"])
    if not os.path.isfile(path):
        raise ValueError(f"Queued image is gone (ComfyUI restarted?): {src_ref['filename']}")
    img = Image.open(path).convert("RGB")
    arr = np.asarray(img).astype(np.float32) / 255.0
    return torch.from_numpy(arr)[None, ]


# --------------------------------------------------------------------------
# the node
# --------------------------------------------------------------------------
class FreedomVideoQueue:
    """Feeds the Wan image-to-video graph one queued item at a time.
    All queue + settings state is in the `state` string, saved with the workflow."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "state": ("STRING", {
                    "default": "{}", "multiline": True,
                    "tooltip": "Queue + settings + last prompt. Managed by the panel; "
                               "saved inside the workflow. Don't hand-edit.",
                }),
                "mode": (["selected slot", "next pending"], {"default": "next pending"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "INT", "INT", "INT")
    RETURN_NAMES = ("start_image", "motion_prompt", "width", "height", "length_frames")
    FUNCTION = "run"
    CATEGORY = "Freedom"
    OUTPUT_NODE = False

    @classmethod
    def IS_CHANGED(cls, state, mode="next pending"):
        # the queue advances between runs even though the node inputs look
        # identical - force ComfyUI to re-execute every time so it picks up the
        # next slot instead of replaying the cached one.
        return time.time()

    def run(self, state, mode="next pending"):
        # `state` from the workflow re-hydrates the in-memory queue on first run
        global _QUEUE, _SELECTED, _LAST_PROMPT
        try:
            st = json.loads(state) if state and state.strip().startswith("{") else {}
        except ValueError:
            st = {}
        if st.get("slots") and all(x["status"] == "empty" for x in _QUEUE):
            _QUEUE = (st["slots"] + [_blank_slot()] * SLOTS)[:SLOTS]
            _SELECTED = int(st.get("selected", 0))
            _LAST_PROMPT = str(st.get("last_prompt", ""))

        idx = _SELECTED if mode == "selected slot" else (_first_pending() if _first_pending() is not None else _SELECTED)
        sl = _QUEUE[idx]
        if sl["status"] == "empty" or not sl["src"]:
            raise ValueError(f"Video queue slot {idx + 1} is empty - send an image to it first.")

        s = load_settings()
        w = int(sl["width"] or s["width"])
        h = int(sl["height"] or s["height"])
        want_s = float(sl["length_s"] or s["length_s"])
        # one Wan 5B generation is good to ~5 s (121 frames). Longer requests are
        # built by auto-chaining 5 s segments - FreedomVideoSave re-queues the
        # clip for another pass until the total length is reached.
        seg_s = min(want_s, MAX_SEG_S)
        lf = min(length_frames(seg_s), MAX_SEG_FRAMES)
        sl["want_s"] = want_s          # remember the target so Save can chain
        prompt = sl["prompt"] or _LAST_PROMPT

        global _RUNNING_IDX
        _RUNNING_IDX = idx
        sl["status"] = "running"
        _push_state()
        img = _load_tensor(sl["src"])
        return (img, prompt, w, h, lf)


# --------------------------------------------------------------------------
# video encode + save node
# --------------------------------------------------------------------------
def _auto_dir():
    d = os.path.join(folder_paths.get_output_directory(), "freedom_video")
    os.makedirs(d, exist_ok=True)
    return d


def _next_video_name(folder, base, ext):
    import re
    pat = re.compile("^" + re.escape(base) + r"_(\d{5})" + re.escape(ext) + "$", re.IGNORECASE)
    n = 0
    try:
        for fn in os.listdir(folder):
            m = pat.match(fn)
            if m:
                n = max(n, int(m.group(1)))
    except OSError:
        pass
    return "{0}_{1:05d}{2}".format(base, n + 1, ext)


def _ff():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _encode(frames, path, fps, codec, pix_fmt, meta=None):
    """frames: (N,H,W,3) float 0-1 tensor -> a video file at `path`.
    `meta` (dict) is written into the container AND a sidecar .json (#15)."""
    import json as _json
    import subprocess
    arr = (frames.cpu().numpy().clip(0, 1) * 255).astype("uint8")
    n, h, w, _ = arr.shape
    args = [_ff(), "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
            "-r", str(fps), "-i", "-", "-an", "-c:v", codec, "-pix_fmt", pix_fmt]
    if codec == "libx264":
        args += ["-preset", "medium", "-crf", "18", "-movflags", "+faststart"]
    elif codec == "libvpx-vp9":
        args += ["-b:v", "0", "-crf", "30"]
    if meta:
        args += ["-metadata", "comment=" + str(meta.get("prompt", ""))[:900],
                 "-metadata", "title=Freedom motion clip",
                 "-metadata", "description=" + _json.dumps(meta)[:900]]
    args += [path]
    p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    p.stdin.write(arr.tobytes())
    p.stdin.close()
    err = p.stderr.read().decode(errors="replace")
    if p.wait() != 0:
        raise RuntimeError("ffmpeg failed: " + err[-500:])
    if meta:
        try:
            with open(os.path.splitext(path)[0] + ".freedom.json", "w", encoding="utf-8") as fh:
                _json.dump(meta, fh, indent=1)
        except OSError:
            pass
    return path


def _encode_meta_only(video_path, meta):
    """Write the sidecar .json for an already-encoded file (used after concat)."""
    import json as _json
    try:
        with open(os.path.splitext(video_path)[0] + ".freedom.json", "w", encoding="utf-8") as fh:
            _json.dump(meta, fh, indent=1)
    except OSError:
        pass


def _read_video_meta(video_path):
    """Prompt + settings for a finished video: sidecar .json first, then the
    container 'description' tag."""
    import json as _json
    import subprocess
    side = os.path.splitext(video_path)[0] + ".freedom.json"
    if os.path.isfile(side):
        try:
            return _json.load(open(side, encoding="utf-8"))
        except Exception:
            pass
    try:
        out = subprocess.run([_ff(), "-i", video_path, "-f", "ffmetadata", "-"],
                             capture_output=True, text=True, timeout=20).stdout
        for line in out.splitlines():
            if line.startswith("description="):
                return _json.loads(line[len("description="):])
            if line.startswith("comment="):
                return {"prompt": line[len("comment="):]}
    except Exception:
        pass
    return {}


def _video_seconds(video_path):
    import subprocess
    try:
        out = subprocess.run([_ff(), "-i", video_path], capture_output=True, text=True, timeout=20).stderr
        import re
        m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", out)
        if m:
            hh, mm, ss = m.groups()
            return int(hh) * 3600 + int(mm) * 60 + float(ss)
    except Exception:
        pass
    return 0.0


def _last_frame_png(video_path, dst_png):
    import subprocess
    r = subprocess.run([_ff(), "-y", "-sseof", "-1", "-i", video_path,
                        "-update", "1", "-q:v", "2", dst_png],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0 or not os.path.isfile(dst_png):
        # fallback: just the very first frame
        subprocess.run([_ff(), "-y", "-i", video_path, "-vframes", "1", dst_png],
                       capture_output=True, timeout=60)
    return dst_png if os.path.isfile(dst_png) else None


def _concat(a, b, out_path):
    """Join video `a` then `b` -> out_path (re-encode, same codec as `a`)."""
    import subprocess
    lst = out_path + ".concat.txt"
    with open(lst, "w", encoding="utf-8") as fh:
        fh.write(f"file '{a}'\nfile '{b}'\n")
    r = subprocess.run([_ff(), "-y", "-f", "concat", "-safe", "0", "-i", lst,
                        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path],
                       capture_output=True, text=True, timeout=300)
    try:
        os.remove(lst)
    except OSError:
        pass
    if r.returncode != 0:
        raise RuntimeError("concat failed: " + r.stderr[-400:])
    return out_path


class FreedomVideoSave:
    """Encodes the frames to a video, ALWAYS auto-saves a copy to
    output/freedom_video/, and offers a 'Save to my folder' button in the
    panel (folder stored in the workflow). Also advances the video queue."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "fps": ("INT", {"default": FPS, "min": 1, "max": 60}),
                "format": (list(VIDEO_FORMATS), {"default": DEFAULT_FORMAT}),
                "filename_prefix": ("STRING", {"default": "freedom"}),
                "save_folder": ("STRING", {
                    "default": "",
                    "tooltip": "'Save to my folder' writes here. Use the "
                               "'Set User Save Folder' button. Stored in the workflow.",
                }),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ()
    FUNCTION = "run"
    OUTPUT_NODE = True
    CATEGORY = "Freedom"

    def run(self, images, fps=FPS, format=DEFAULT_FORMAT, filename_prefix="freedom",
            save_folder="", prompt=None, extra_pnginfo=None):
        global _LAST_VIDEO, _LAST_PROMPT
        ext, codec, pix = VIDEO_FORMATS.get(format, VIDEO_FORMATS[DEFAULT_FORMAT])
        base = _clean(filename_prefix)
        auto_dir = _auto_dir()

        motion, extends, want_s = "", None, 0.0
        if _RUNNING_IDX is not None and 0 <= _RUNNING_IDX < SLOTS:
            sl = _QUEUE[_RUNNING_IDX]
            motion = sl.get("prompt", "") or ""
            extends = sl.get("extends")
            want_s = float(sl.get("want_s") or 0)
            sl["status"] = "done"
            if motion:
                _LAST_PROMPT = motion

        n = int(images.shape[0])
        meta = {"prompt": motion, "width": int(images.shape[2]), "height": int(images.shape[1]),
                "frames": n, "fps": fps, "length_s": round(n / max(1, fps), 1),
                "extends_from": extends, "made": time.strftime("%Y-%m-%d %H:%M:%S")}

        seg_path = os.path.join(auto_dir, _next_video_name(auto_dir, base, ext))
        _encode(images, seg_path, fps, codec, pix, meta=meta)

        auto_meta = meta                     # metadata describing whatever we keep
        joined_s = None
        if extends and os.path.isfile(extends):
            # join the original clip + this new segment -> one longer video
            joined = os.path.join(auto_dir, _next_video_name(auto_dir, base + "_extended", ext))
            try:
                _concat(extends, seg_path, joined)
                # The joined file is longer than the segment it was built from,
                # so it needs its OWN numbers. Re-using `meta` here labelled a
                # 9.75 s clip as 4.9 s. The segment's own figures are kept under
                # separate names rather than thrown away.
                joined_s = round(_video_seconds(joined), 2)
                auto_meta = dict(meta)
                auto_meta.update({
                    "extended": True,
                    "segment_frames": n,
                    "segment_length_s": meta["length_s"],
                    "frames": int(round(joined_s * fps)) if joined_s else n,
                    "length_s": round(joined_s, 1) if joined_s else meta["length_s"],
                })
                _encode_meta_only(joined, auto_meta)
                auto_path = joined
            except Exception as e:
                print(f"[freedom_video] extend concat failed ({e}); keeping the new segment only")
                auto_path = seg_path
        else:
            auto_path = seg_path

        # `want_s` on a chained slot = seconds still needed. This pass added
        # `seg_s` of new footage; if there's still >~0.5 s to go, re-queue.
        seg_s = round(n / max(1, fps), 1)
        # already measured above when the clips were joined - don't shell out twice
        total_so_far = round(joined_s if joined_s is not None
                             else _video_seconds(auto_path), 1)
        remaining = round((want_s or 0) - seg_s, 1)
        chained = False
        if remaining > 0.5:
            r = _enqueue_video(auto_path, want_s=remaining, prompt=motion)
            chained = bool(r.get("ok"))

        _LAST_VIDEO = {"auto": auto_path, "prompt": motion, "when": time.time(),
                       "ext": ext, "codec": codec, "pix": pix, "meta": auto_meta,
                       "chaining": chained, "made_total": total_so_far, "want_s": want_s}
        _push_state()

        rel = os.path.relpath(auto_path, folder_paths.get_output_directory()).replace("\\", "/")
        return {"ui": {"freedom_video": [{"path": auto_path,
                                          "url": "/view?filename=" + os.path.basename(auto_path)
                                                 + "&subfolder=freedom_video&type=output",
                                          "rel": rel, "prompt": motion,
                                          "save_folder": save_folder}]}}


def _clean(s):
    import re
    s = (s or "freedom").strip().replace("\\", "/")
    return re.sub(r"[^A-Za-z0-9 _./-]", "", s).strip("/") or "freedom"


# --------------------------------------------------------------------------
# web API
# --------------------------------------------------------------------------
routes = PromptServer.instance.routes


def _push_state():
    try:
        PromptServer.instance.send_sync("freedom.video.state", _state())
    except Exception:
        pass


@routes.get("/freedom/video/state")
async def api_state(request):
    return web.json_response(_state())


@routes.post("/freedom/video/enqueue")
async def api_enqueue(request):
    body = await request.json()
    imgs = body.get("images", []) or []
    prompt = str(body.get("prompt", "") or "")
    added = 0
    for ref in imgs:
        slot = next((sl for sl in _QUEUE if sl["status"] == "empty"), None)
        if slot is None:
            break
        held = _copy_hold(ref)
        if not held:
            continue
        slot.update({"id": uuid.uuid4().hex[:8], "src": held, "prompt": prompt,
                     "width": None, "height": None, "length_s": None,
                     "status": "pending", "kind": "image",
                     "thumb": f"/view?filename={held['filename']}&subfolder={HOLD_SUB}&type=temp"})
        added += 1
    _push_state()
    return web.json_response({"ok": True, "added": added, "full": added < len(imgs),
                              "auto_start": load_settings().get("auto_start", True)})


@routes.post("/freedom/video/select")
async def api_select(request):
    global _SELECTED
    body = await request.json()
    i = int(body.get("index", 0))
    if 0 <= i < SLOTS:
        _SELECTED = i
    _push_state()
    return web.json_response({"ok": True, "selected": _SELECTED, "slot": _QUEUE[_SELECTED]})


@routes.post("/freedom/video/set_prompt")
async def api_set_prompt(request):
    body = await request.json()
    i = int(body.get("index", 0))
    if 0 <= i < SLOTS:
        _QUEUE[i]["prompt"] = str(body.get("prompt", "") or "")
    _push_state()
    return web.json_response({"ok": True})


@routes.post("/freedom/video/set_slot")
async def api_set_slot(request):
    body = await request.json()
    i = int(body.get("index", 0))
    if 0 <= i < SLOTS:
        for k in ("width", "height"):
            if body.get(k) is not None:
                _QUEUE[i][k] = int(body[k])
        if body.get("length_s") is not None:
            _QUEUE[i]["length_s"] = float(body["length_s"])
    _push_state()
    return web.json_response({"ok": True})


@routes.post("/freedom/video/clear")
async def api_clear(request):
    body = await request.json()
    if body.get("all"):
        for i in range(SLOTS):
            _QUEUE[i] = _blank_slot()
    else:
        i = int(body.get("index", 0))
        if 0 <= i < SLOTS:
            _QUEUE[i] = _blank_slot()
    _push_state()
    return web.json_response({"ok": True})


@routes.post("/freedom/video/complete")
async def api_complete(request):
    global _LAST_PROMPT
    body = await request.json()
    i = int(body.get("index", 0))
    if 0 <= i < SLOTS:
        _QUEUE[i]["status"] = "done"
        if _QUEUE[i].get("prompt"):
            _LAST_PROMPT = _QUEUE[i]["prompt"]
    _push_state()
    return web.json_response({"ok": True})


@routes.get("/freedom/video/settings")
async def api_settings_get(request):
    return web.json_response(load_settings())


@routes.post("/freedom/video/settings")
async def api_settings_set(request):
    body = await request.json()
    s = load_settings()
    for k in ("auto_start", "width", "height", "length_s", "user_folder"):
        if k in body and body[k] is not None:
            s[k] = body[k]
    save_settings(s)
    _push_state()
    return web.json_response({"ok": True, "settings": s})


@routes.get("/freedom/video/last_video")
async def api_last_video(request):
    v = dict(_LAST_VIDEO)
    v["exists"] = bool(v.get("auto")) and os.path.isfile(v["auto"])
    v["pending"] = _first_pending() is not None
    v["auto_start"] = load_settings().get("auto_start", True)
    v["chaining"] = bool(_LAST_VIDEO.get("chaining"))
    return web.json_response(v)


_PICKER = (
    "import sys, tkinter as tk\n"
    "from tkinter import filedialog\n"
    "r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True); r.update()\n"
    "p = filedialog.askdirectory(initialdir=sys.argv[1] if len(sys.argv)>1 else None, "
    "title='Freedom - choose where Save to my folder writes videos', mustexist=False)\n"
    "print(p or '')\n"
)


@routes.post("/freedom/video/browse_folder")
async def api_browse_folder(request):
    import asyncio
    import subprocess
    try:
        body = await request.json()
    except Exception:
        body = {}
    initial = (body.get("folder") or "").strip() or folder_paths.get_output_directory()

    def _pick():
        try:
            out = subprocess.run([__import__("sys").executable, "-c", _PICKER, initial],
                                 capture_output=True, text=True, timeout=600)
            return out.stdout.strip()
        except Exception:
            return ""
    chosen = await asyncio.get_event_loop().run_in_executor(None, _pick)
    if not chosen:
        return web.json_response({"ok": False, "cancelled": True})
    chosen = os.path.abspath(chosen.replace("/", os.sep))
    try:
        os.makedirs(chosen, exist_ok=True)
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})
    s = load_settings(); s["user_folder"] = chosen; save_settings(s)
    return web.json_response({"ok": True, "folder": chosen})


@routes.post("/freedom/video/save_user")
async def api_save_user(request):
    import shutil
    body = await request.json()
    folder = (body.get("folder") or load_settings().get("user_folder") or "").strip()
    if not folder:
        return web.json_response({"ok": False, "error": "no user folder set - click 'Set User Save Folder'"}, status=400)
    src = _LAST_VIDEO.get("auto")
    if not src or not os.path.isfile(src):
        return web.json_response({"ok": False, "error": "no finished video to save yet"}, status=400)
    try:
        os.makedirs(folder, exist_ok=True)
        base, ext = os.path.splitext(os.path.basename(src))
        dst = os.path.join(folder, _next_video_name(folder, base.rsplit("_", 1)[0] or "freedom", ext))
        shutil.copy2(src, dst)
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})
    return web.json_response({"ok": True, "saved": dst})


def _enqueue_video(video_path, want_s=None, prompt=None):
    """Drop a finished video into the queue as a green 'from video' slot:
    last frame becomes the start image, the video's saved prompt comes along,
    and `extends` remembers the original so the next render is joined to it.
    `want_s` set = this is an auto-chain step toward a longer total."""
    if not os.path.isfile(video_path):
        return {"ok": False, "error": "video file not found"}
    slot = next((sl for sl in _QUEUE if sl["status"] == "empty"), None)
    if slot is None:
        return {"ok": False, "error": "queue is full - clear a slot first"}
    dst = os.path.join(hold_dir(), uuid.uuid4().hex[:10] + ".png")
    if not _last_frame_png(video_path, dst):
        return {"ok": False, "error": "could not read the last frame"}
    m = _read_video_meta(video_path)
    seg_len = None
    if want_s is not None:
        seg_len = int(min(MAX_SEG_S, max(1, round(want_s))))
    slot.update({
        "id": uuid.uuid4().hex[:8],
        "src": {"filename": os.path.basename(dst), "subfolder": HOLD_SUB, "type": "temp"},
        "prompt": (prompt if prompt is not None else m.get("prompt", "")) or "",
        "width": m.get("width"), "height": m.get("height"),
        "length_s": seg_len,
        "want_s": float(want_s) if want_s is not None else None,
        "status": "pending", "kind": "video",
        "extends": os.path.abspath(video_path),
        "thumb": f"/view?filename={os.path.basename(dst)}&subfolder={HOLD_SUB}&type=temp",
    })
    _push_state()
    return {"ok": True, "prompt": slot["prompt"], "auto_start": load_settings().get("auto_start", True)}


@routes.post("/freedom/video/extend")
async def api_extend(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    path = (body.get("path") or "").strip() or (_LAST_VIDEO.get("auto") or "")
    return web.json_response(_enqueue_video(path))


_VPICKER = (
    "import sys, tkinter as tk\n"
    "from tkinter import filedialog\n"
    "r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True); r.update()\n"
    "p = filedialog.askopenfilename(title='Freedom - pick a video to extend', "
    "filetypes=[('Video','*.mp4 *.mov *.webm *.mkv'),('All','*.*')])\n"
    "print(p or '')\n"
)


@routes.post("/freedom/video/load_to_queue")
async def api_load_to_queue(request):
    import asyncio
    import subprocess
    def _pick():
        try:
            return subprocess.run([__import__("sys").executable, "-c", _VPICKER],
                                  capture_output=True, text=True, timeout=600).stdout.strip()
        except Exception:
            return ""
    chosen = await asyncio.get_event_loop().run_in_executor(None, _pick)
    if not chosen:
        return web.json_response({"ok": False, "cancelled": True})
    return web.json_response(_enqueue_video(os.path.abspath(chosen)))


@routes.post("/freedom/video/open_auto")
async def api_open_auto(request):
    try:
        os.startfile(_auto_dir())
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})
    return web.json_response({"ok": True})


NODE_CLASS_MAPPINGS = {
    "FreedomVideoQueue": FreedomVideoQueue,
    "FreedomVideoSave": FreedomVideoSave,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "FreedomVideoQueue": "Freedom: Video Queue (9 slots)",
    "FreedomVideoSave": "Freedom: Save Video (auto + my folder)",
}
