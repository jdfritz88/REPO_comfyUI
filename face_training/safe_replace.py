"""
The last step of every "write a .tmp, then swap it in" save in face_training -
and, below replace_file(), the reading side: how to read or copy one of those
files while another process may be swapping it in (read_text, copy_file).

Why this exists: on Windows, os.replace() cannot swap a file in while any other
process has the old one open, unless that process opened it with
FILE_SHARE_DELETE - and Python's open() never does. The replace then fails with
PermissionError [WinError 5]. That is not rare here: a Seek child rewrites
profile.json on every progress update while the Face Tool reads every
profile.json on reload, backup copies profile.json and search_history.json when
a window closes, and ComfyUI reads the face registry while training writes it.
One unlucky moment crashed a whole Seek run (2026-09-13, Fix log).

Those readers let go within milliseconds (a 2 MB profile.json read: 9-17 ms,
a backup copy: 3-6 ms, measured 2026-09-13). So replace_file() tries again,
briefly, only for the two lock errors, and only for a bounded time. The .tmp
is written once before this is called, so the target is always either the old
complete file or the new complete file - never half of one.

It never quietly drops a save. If the file is still locked when the time runs
out, it logs an ERROR and raises PermissionError saying how long it waited and
which .tmp still holds the content that did not get saved. The target is left
as the previous complete version.

stdlib only - imported by profiles.py, which the launcher's own Python loads.
"""

from __future__ import annotations

import logging
import os
import shutil
import time

log = logging.getLogger("face_training.safe_replace")

# Windows error codes that mean "another handle has this file open right now".
ERROR_ACCESS_DENIED = 5
ERROR_SHARING_VIOLATION = 32
_LOCK_ERRORS = (ERROR_ACCESS_DENIED, ERROR_SHARING_VIOLATION)

# How long to keep trying: over 250 times the longest read measured above.
DEADLINE_SECONDS = 5.0
# Wait between tries: starts at 1 ms, doubles, never more than 10 ms. Short
# waits matter - a reader that opens the file again and again leaves only
# brief gaps, and each try is a single cheap system call.
FIRST_WAIT = 0.001
MAX_WAIT = 0.010


def replace_file(src: str, dst: str) -> None:
    """os.replace(src, dst), waiting out another process's brief hold on dst.

    Raises at once for any error that is not a Windows lock error. Raises
    PermissionError (same winerror, chained from the last OS error) if the lock
    is still there after DEADLINE_SECONDS.
    """
    start = time.monotonic()
    attempts = 0
    wait = FIRST_WAIT
    while True:
        attempts += 1
        try:
            os.replace(src, dst)
        except PermissionError as e:
            if getattr(e, "winerror", None) not in _LOCK_ERRORS:
                raise
            waited = time.monotonic() - start
            if waited >= DEADLINE_SECONDS:
                msg = (f"could not replace {dst}: still locked by another process after "
                       f"{attempts} attempts over {waited:.1f} s (last error: {e}). "
                       f"Nothing was saved to it; the new content is still in {src}")
                log.error(msg)
                raise PermissionError(e.errno, msg, src, e.winerror, dst) from e
            time.sleep(min(wait, DEADLINE_SECONDS - waited))
            wait = min(wait * 2, MAX_WAIT)
            continue
        if attempts > 1:
            log.debug("replaced %s after %d attempts over %.0f ms (another process had it open)",
                      dst, attempts, (time.monotonic() - start) * 1000)
        return


# --------------------------------------------------------------------------- #
# the reading side
#
# The same swap has a second face. For the few milliseconds os.replace() takes
# to swap the file in, any other process that opens it is refused with a
# sharing violation. Measured 2026-09-13 against a writer saving in a loop:
# every refused open was Win32 ERROR_SHARING_VIOLATION (32), and the longest
# unbroken run of refusals lasted 11.8 ms. Python's open() goes through the C
# runtime, which reports it as PermissionError errno 13 with no winerror - in
# the OneTrainer venv (3.10) and the ComfyUI venv (3.13) alike. Unhandled, one
# of those stopped the Face Tool's message loop for good, cost a backup slot,
# killed the review server at startup, and made the registry read as empty
# (Fix log).
#
# errno 13 cannot tell that apart from a file that is really denied, so a file
# that truly cannot be read costs READ_DEADLINE_SECONDS before its error is
# raised. Shorter than the writer's deadline on purpose: the Face Tool reads
# every profile on its window thread.
# --------------------------------------------------------------------------- #
READ_DEADLINE_SECONDS = 2.0          # 170 times the longest refusal measured
_READ_LOCK_WINERRORS = (None, *_LOCK_ERRORS)   # None = the C runtime's open()


def _retry_while_swapped(what: str, op):
    """Run op(), waiting out a brief sharing refusal. Returns op()'s result.

    Raises at once for any error that is not a lock refusal. Raises
    PermissionError (chained from the last OS error) if the file is still
    refused after READ_DEADLINE_SECONDS.
    """
    start = time.monotonic()
    attempts = 0
    wait = FIRST_WAIT
    while True:
        attempts += 1
        try:
            result = op()
        except PermissionError as e:
            if getattr(e, "winerror", None) not in _READ_LOCK_WINERRORS:
                raise
            waited = time.monotonic() - start
            if waited >= READ_DEADLINE_SECONDS:
                msg = (f"could not {what}: still refused after {attempts} attempts over "
                       f"{waited:.1f} s (last error: {e})")
                log.error(msg)
                raise PermissionError(e.errno, msg) from e
            time.sleep(min(wait, READ_DEADLINE_SECONDS - waited))
            wait = min(wait * 2, MAX_WAIT)
            continue
        if attempts > 1:
            log.debug("%s after %d attempts over %.0f ms (another process was swapping it in)",
                      what, attempts, (time.monotonic() - start) * 1000)
        return result


def read_text(path: str, encoding: str = "utf-8") -> str:
    """The whole text of a file that is saved with replace_file()."""
    def op():
        with open(path, encoding=encoding) as fh:
            return fh.read()
    return _retry_while_swapped(f"read {path}", op)


def copy_file(src: str, dst: str) -> None:
    """shutil.copy2(src, dst) for a file that is saved with replace_file()."""
    _retry_while_swapped(f"copy {src} to {dst}", lambda: shutil.copy2(src, dst))
