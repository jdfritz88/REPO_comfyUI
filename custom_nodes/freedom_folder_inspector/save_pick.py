# ==========================================
# FREEDOM SYSTEM - ComfyUI "Preview & Pick" (no auto-save)
# save_pick.py
# ==========================================
#
# Replaces the Save Image box. Pictures are NOT saved automatically.
#   * They are held in ComfyUI's temp folder (cleared when ComfyUI restarts).
#   * The panel shows every picture in the batch with a tick box.
#   * One picture      -> a single "Save Image" button.
#   * Two or more      -> tick the ones you want, "Save Selected Images".
#   * "Set User Save Folder" (button under Save Image) -> real Windows folder
#     picker. The chosen folder is written into this node's `save_folder`
#     widget, so it is remembered *inside the workflow* when you save it.
#   * "Open Folder" -> opens the current save folder in Explorer.
# Saved files are full-quality PNGs with the recipe embedded (same as Save Image).
#
# Web API (used by web/preview_pick.js):
#   GET  /freedom/save/settings            -> {"folder": <default>}
#   POST /freedom/save/browse              -> native folder picker -> {"folder"} or {"cancelled": true}
#   POST /freedom/save/open   {folder}     -> open that folder in Explorer
#   POST /freedom/save/pick   {files, prefix, folder} -> copy held pictures into <folder>

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

import folder_paths
from aiohttp import web
from comfy.cli_args import args
from server import PromptServer

HOLD_SUB = "freedom_hold"
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "freedom_save_settings.json")


# --------------------------------------------------------------------------
# default save folder (used only when the node's widget is empty)
# --------------------------------------------------------------------------
def _default_folder():
    return os.path.join(folder_paths.get_output_directory(), "freedom")


def load_settings():
    s = {"folder": _default_folder()}
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


# --------------------------------------------------------------------------
# every copy of a picture (user, 2026-10-01: the viewer's DELETE removes them all)
# --------------------------------------------------------------------------
# The 12b copy is named in the hold folder; its archive copy and any Save Image
# copies are noted here, so DELETE can find them again later - even after a page
# reload. Only the pictures this node made are listed.
_LINKS_LOCK = threading.Lock()


def _links_path():
    return os.path.join(hold_dir(), "_links.json")


def _links_update(fn, **add):
    with _LINKS_LOCK:
        try:
            with open(_links_path(), "r", encoding="utf-8") as fh:
                links = json.load(fh)
        except Exception:
            links = {}
        e = links.setdefault(fn, {"archive": "", "saved": []})
        if add.get("archive"):
            e["archive"] = add["archive"]
        for p in add.get("saved", []):
            if p not in e["saved"]:
                e["saved"].append(p)
        if add.get("forget"):
            links.pop(fn, None)
        tmp = _links_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(links, fh, indent=1)
        os.replace(tmp, _links_path())
        return links.get(fn)


def _links_get(fn):
    with _LINKS_LOCK:
        try:
            with open(_links_path(), "r", encoding="utf-8") as fh:
                return json.load(fh).get(fn)
        except Exception:
            return None


def _inside(path, folder):
    path, folder = os.path.abspath(path), os.path.abspath(folder)
    return os.path.commonpath([path, folder]) == folder


def _recycle(path):
    """Send one file to the Windows Recycle Bin (it can be restored from there)."""
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                    ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]
    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = 3, 0x4, 0x10, 0x40, 0x400
    op = SHFILEOPSTRUCTW(None, FO_DELETE, os.path.abspath(path) + "\0", None,
                         FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI,
                         False, None, None)
    code = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if code != 0 or op.fAnyOperationsAborted or os.path.exists(path):
        raise OSError("the Recycle Bin did not take it (code %s)" % code)


def _clean_prefix(prefix):
    prefix = (prefix or "freedom").strip().replace("\\", "/")
    prefix = re.sub(r"[^A-Za-z0-9 _./-]", "", prefix).strip("/") or "freedom"
    return prefix


def _resolve_folder(folder):
    """The node widget value wins; fall back to the remembered default."""
    folder = (folder or "").strip().strip('"')
    if not folder:
        folder = load_settings().get("folder") or _default_folder()
    return os.path.abspath(folder.replace("/", os.sep))


def _next_name(folder, base):
    """freedom_00001_.png style, continuing from whatever is already there."""
    pat = re.compile("^" + re.escape(base) + r"_(\d{5})_\.png$", re.IGNORECASE)
    n = 0
    try:
        for fn in os.listdir(folder):
            m = pat.match(fn)
            if m:
                n = max(n, int(m.group(1)))
    except OSError:
        pass
    return "{0}_{1:05d}_.png".format(base, n + 1)


# --------------------------------------------------------------------------
# the archive ("auto-save")
# --------------------------------------------------------------------------
# Exactly what ComfyUI's own SaveImage did in the old AUTO-SAVE box with
# filename_prefix "freedom_archive/img" (nodes.py SaveImage.save_images): same
# folder, same img_NNNNN_.png counter, same metadata, compress level 4.
ARCHIVE_PREFIX = "freedom_archive/img"


def _archive(images, prompt=None, extra_pnginfo=None, prefix=ARCHIVE_PREFIX):
    out_dir = folder_paths.get_output_directory()
    # get_save_image_path refuses a prefix that climbs out of the output folder,
    # exactly as it did for the old SaveImage box.
    full_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
        prefix, out_dir, images[0].shape[1], images[0].shape[0])
    saved = []
    for batch_number, image in enumerate(images):
        arr = 255.0 * image.cpu().numpy()
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        meta = None
        if not args.disable_metadata:
            meta = PngInfo()
            if prompt is not None:
                meta.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for k, v in extra_pnginfo.items():
                    meta.add_text(k, json.dumps(v))
        name = filename.replace("%batch_num%", str(batch_number))
        fn = f"{name}_{counter:05}_.png"
        img.save(os.path.join(full_folder, fn), pnginfo=meta, compress_level=4)
        saved.append({"filename": fn, "subfolder": subfolder, "type": "output"})
        counter += 1
    return saved


# --------------------------------------------------------------------------
# the node
# --------------------------------------------------------------------------
class FreedomPreviewPick:
    """Shows the batch, lets you pick which pictures to save. Nothing is saved
    until you click. The save folder is stored in this node, so it travels
    with the workflow."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "filename_prefix": ("STRING", {"default": "freedom"}),
                "save_folder": ("STRING", {
                    "default": _default_folder(),
                    "multiline": False,
                    "tooltip": "Where 'Save Image' writes to. Use the "
                               "'Set User Save Folder' button, or type a path. "
                               "Saved inside the workflow.",
                }),
            },
            # Folded in from the separate AUTO-SAVE (SaveImage) box, 2026-09-24:
            # one picture display instead of three. Optional and last, so older
            # workflows that never had it simply get the default (on).
            "optional": {
                "auto_save": ("BOOLEAN", {
                    "default": True,
                    "label_on": "on - keep every picture",
                    "label_off": "off",
                    "tooltip": "Also save EVERY picture to output/" + ARCHIVE_PREFIX
                               + "_NNNNN_.png, the moment it is made - the "
                               "'never lose anything' pile. Same names the old "
                               "AUTO-SAVE box used.",
                }),
                # The old AUTO-SAVE box's own filename_prefix box, carried over.
                "archive_prefix": ("STRING", {
                    "default": ARCHIVE_PREFIX,
                    "tooltip": "Where auto-save writes, inside ComfyUI's output "
                               "folder. 'freedom_archive/img' = output/freedom_archive/"
                               "img_NNNNN_.png (the old AUTO-SAVE box's setting).",
                }),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    # The old AUTO-SAVE box passed the pictures on through an "images" output;
    # this node now does too, so anything that hung off it still can.
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "hold"
    OUTPUT_NODE = True
    CATEGORY = "Freedom"

    def hold(self, images, filename_prefix="freedom", save_folder="",
             prompt=None, extra_pnginfo=None, auto_save=True,
             archive_prefix=None):
        archived = (_archive(images, prompt, extra_pnginfo,
                             (archive_prefix or "").strip() or ARCHIVE_PREFIX)
                    if auto_save else [])
        batch = uuid.uuid4().hex[:8]
        d = hold_dir()
        files = []
        for i, image in enumerate(images):
            arr = 255.0 * image.cpu().numpy()
            img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
            meta = None
            if not args.disable_metadata:
                meta = PngInfo()
                if prompt is not None:
                    meta.add_text("prompt", json.dumps(prompt))
                if extra_pnginfo is not None:
                    for k, v in extra_pnginfo.items():
                        meta.add_text(k, json.dumps(v))
            fn = "{0}_{1:02d}.png".format(batch, i)
            img.save(os.path.join(d, fn), pnginfo=meta, compress_level=4)
            files.append({"filename": fn, "subfolder": HOLD_SUB, "type": "temp", "index": i,
                          "batch": batch, "width": img.width, "height": img.height})
            if i < len(archived):                      # archive copy i is picture i
                a = archived[i]
                _links_update(fn, archive=os.path.join(folder_paths.get_output_directory(),
                                                       a["subfolder"], a["filename"]))
        folder = _resolve_folder(save_folder)
        # keep the last-used folder as the default for brand-new nodes
        save_settings({"folder": folder})
        # "images" is ComfyUI's OWN key for preview pictures, and every client
        # understands it: the desktop page, the phone, and a raw API call reading
        # /history. "freedom_files" is ours, and only this package's JavaScript can
        # draw it - which runs on the desktop and nowhere else.
        #
        # Returning ONLY the custom key meant the phone saw a node that produced
        # nothing, and /history recorded zero images for this node, even though the
        # pictures existed. Emitting both fixes that without changing the desktop
        # picker, which keeps reading "freedom_files" exactly as before.
        return {"ui": {"images": files,
                       "freedom_files": files,
                       "freedom_folder": [folder],
                       "freedom_prefix": [_clean_prefix(filename_prefix)],
                       "freedom_archived": archived},
                "result": (images,)}


# --------------------------------------------------------------------------
# web API
# --------------------------------------------------------------------------
routes = PromptServer.instance.routes


@routes.get("/freedom/save/settings")
async def api_settings_get(request):
    s = load_settings()
    return web.json_response({"folder": s["folder"], "exists": os.path.isdir(s["folder"])})


_PICKER = (
    "import sys, tkinter as tk\n"
    "from tkinter import filedialog\n"
    "r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True); r.update()\n"
    "p = filedialog.askdirectory(initialdir=sys.argv[1] if len(sys.argv) > 1 else None, "
    "title='Freedom - choose where Save Image writes pictures', mustexist=False)\n"
    "print(p or '')\n"
)


def _run_picker(initial):
    try:
        out = subprocess.run([sys.executable, "-c", _PICKER, initial],
                             capture_output=True, text=True, timeout=600)
        return out.stdout.strip(), out.stderr.strip()
    except subprocess.TimeoutExpired:
        return "", "picker timed out"
    except Exception as exc:
        return "", str(exc)


@routes.post("/freedom/save/browse")
async def api_browse(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    initial = _resolve_folder(body.get("folder", ""))
    loop = asyncio.get_event_loop()
    chosen, err = await loop.run_in_executor(None, _run_picker, initial)
    if not chosen:
        return web.json_response({"ok": False, "cancelled": True, "error": err})
    chosen = os.path.abspath(chosen.replace("/", os.sep))
    try:
        os.makedirs(chosen, exist_ok=True)
    except Exception as exc:
        return web.json_response({"ok": False, "error": "cannot create folder: " + str(exc)})
    save_settings({"folder": chosen})
    return web.json_response({"ok": True, "folder": chosen})


@routes.post("/freedom/save/open")
async def api_open(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    folder = _resolve_folder(body.get("folder", ""))
    try:
        os.makedirs(folder, exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", folder])
    except Exception as exc:
        return web.json_response({"ok": False, "error": str(exc)})
    return web.json_response({"ok": True, "folder": folder})


@routes.get("/freedom/save/open_folder")
async def api_open_folder_get(request):
    """Open an output subfolder in Explorer, from a plain link.

    The POST route above is driven by a button on the Pick panel. A note has no
    button to give it - and a file:// link cannot be used either, because the
    browser blocks those from an http page. A GET route is the one thing a
    markdown link can actually reach, so the AUTO-SAVE note can offer its
    archive folder the same way the Pick panel offers its own.

    `sub` is resolved inside ComfyUI's output directory and refused if it tries
    to climb out of it - this opens a window on the host machine, so it must
    not be steerable to anywhere on disk.
    """
    sub = (request.query.get("sub") or "freedom_archive").strip().strip('"')
    out_root = os.path.abspath(folder_paths.get_output_directory())
    folder = os.path.abspath(os.path.join(out_root, sub.replace("/", os.sep)))
    if os.path.commonpath([out_root, folder]) != out_root:
        return web.Response(status=400, content_type="text/html",
                            text="<p>Refused: that is outside the output folder.</p>")
    try:
        os.makedirs(folder, exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", folder])
    except Exception as exc:
        return web.Response(content_type="text/html",
                            text=f"<p>Could not open it: {exc}</p><p>{folder}</p>")
    n = sum(len(f) for _, _, f in os.walk(folder))
    return web.Response(content_type="text/html", text=(
        "<body style='font:14px system-ui;background:#1c1c1c;color:#ddd;padding:24px'>"
        f"<p>Opened on the ComfyUI machine:</p><p><code>{folder}</code></p>"
        f"<p style='color:#9cc4ff'>{n} file(s) in there.</p>"
        "<p style='color:#888'>You can close this tab.</p></body>"))


@routes.post("/freedom/save/pick")
async def api_pick(request):
    body = await request.json()
    wanted = body.get("files", []) or []
    prefix = _clean_prefix(body.get("prefix", "freedom"))
    folder = _resolve_folder(body.get("folder", ""))
    if "/" in prefix:
        sub, base = prefix.rsplit("/", 1)
        folder = os.path.join(folder, sub.replace("/", os.sep))
    else:
        base = prefix
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception as exc:
        return web.json_response({"ok": False, "error": "cannot create folder: " + str(exc)}, status=400)
    d = hold_dir()
    saved, errors = [], []
    for fn in wanted:
        fn = os.path.basename(str(fn))
        src = os.path.join(d, fn)
        if not os.path.isfile(src):
            errors.append(fn + ": no longer held (ComfyUI restarted?)")
            continue
        dst = os.path.join(folder, _next_name(folder, base))
        try:
            shutil.copy2(src, dst)
            saved.append(dst)
            _links_update(fn, saved=[dst])
        except Exception as exc:
            errors.append(fn + ": " + str(exc))
    save_settings({"folder": _resolve_folder(body.get("folder", ""))})
    return web.json_response({"ok": not errors, "saved": saved, "errors": errors, "folder": folder})


@routes.post("/freedom/save/delete")
async def api_delete(request):
    """The viewer's DELETE (user, 2026-10-01, choice 3): every copy of one picture - the
    12b copy, its archive copy and any Save Image copies - goes to the Recycle Bin.
    A copy that is already gone is skipped, never an error."""
    body = await request.json()
    fn = os.path.basename(str(body.get("file", "")))
    if not fn or fn.startswith("_"):
        return web.json_response({"ok": False, "error": "no picture named"}, status=400)
    link = _links_get(fn) or {}
    paths = [("12b", os.path.join(hold_dir(), fn))]
    arch = link.get("archive") or ""
    a = body.get("archive") or {}                     # the page's own record, if the note is missing
    if not arch and a.get("filename"):
        arch = os.path.join(folder_paths.get_output_directory(), str(a.get("subfolder", "")),
                            os.path.basename(str(a["filename"])))
    if arch:
        paths.append(("archive", arch))
    for p in link.get("saved", []):
        paths.append(("your save folder", p))
    removed, missing, errors = [], [], []
    for where, p in paths:
        if where == "12b" and not _inside(p, hold_dir()):
            errors.append(where + ": not in the 12b folder"); continue
        if where == "archive" and not _inside(p, folder_paths.get_output_directory()):
            errors.append(where + ": not in the output folder"); continue
        if not os.path.isfile(p):
            missing.append(where); continue
        try:
            await asyncio.to_thread(_recycle, p)
            removed.append(where)
        except Exception as exc:
            errors.append(where + ": " + str(exc))
    if not errors:
        _links_update(fn, forget=True)
    logging.getLogger("freedom_save").info("[Freedom] 12b DELETE %s: removed %s; already gone %s; problems %s",
                                           fn, removed, missing, errors)
    return web.json_response({"ok": not errors, "removed": removed, "missing": missing, "errors": errors})


NODE_CLASS_MAPPINGS = {"FreedomPreviewPick": FreedomPreviewPick}
NODE_DISPLAY_NAME_MAPPINGS = {"FreedomPreviewPick": "Freedom: Preview & Pick (no auto-save)"}
