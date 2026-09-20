"""
Delete to the Recycle Bin, not for ever.

Face Seek deletes things a person cannot get back any other way - crops, whole
profiles, trained LoRAs - so every delete the app makes on the user's behalf
goes through here and can be undone from the Recycle Bin. (The one exception is
frames Seek pulled from a video itself: those are its own working files and are
removed outright by the frames stage.)

stdlib only (ctypes), so the launcher, the Face Tool window and the review
server can all import it.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

FO_DELETE = 3
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040          # this is what makes it the Recycle Bin
FOF_NOERRORUI = 0x0400


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT),
                ("pFrom", ctypes.c_wchar_p), ("pTo", ctypes.c_wchar_p),
                ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", ctypes.c_wchar_p)]


def recycle(paths: list[str]) -> bool:
    """Move these files/folders to the Recycle Bin. True only if all are gone.

    Paths that do not exist are ignored. Error dialogs are off, so this never
    blocks behind a message box on a locked screen."""
    real = [os.path.abspath(p) for p in paths if os.path.exists(p)]
    if not real:
        return True
    buf = ctypes.create_unicode_buffer("\0".join(real) + "\0")
    op = _SHFILEOPSTRUCTW(None, FO_DELETE, ctypes.cast(buf, ctypes.c_wchar_p), None,
                          FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI,
                          False, None, None)
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    return rc == 0 and not op.fAnyOperationsAborted and not any(os.path.exists(p) for p in real)
