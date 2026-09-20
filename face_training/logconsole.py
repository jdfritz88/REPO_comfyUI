"""
Logging console for the face_training entry points (Seek, the Face Tool
window, the video frame extractor's CLI).

Every run gets its own file  logs/face_training/<name>_<timestamp>_<pid>.log
with a timestamp, level and logger name on every line, and full tracebacks for
anything that goes wrong - including crashes nobody caught, on the main thread
or any other. The Face Tool runs under pythonw.exe with no console at all, so
before this, anything a Seek started from the window said lived only in the
window's text panel and was gone when the window closed.

When the process has a console (sys.stdout is not None), face_training's own
INFO lines are also written there as the bare message - exactly the text the
old print() calls wrote, so the parents that capture a Seek child's stdout
(seek_library.py's per-folder log, the Face Tool's panel) show what they showed
before. WARNING and above, from any library, carry a level prefix and their
traceback.

Runs in the OneTrainer venv. Standard library only.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(REPO, "logs", "face_training")

FILE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
OWN_LOGGERS = "face_training"


class _ConsoleFormatter(logging.Formatter):
    """Bare message for INFO (the old print() text), level-tagged for WARNING+."""

    _plain = logging.Formatter("%(message)s")
    _tagged = logging.Formatter("%(levelname)s: %(name)s - %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        fmt = self._tagged if record.levelno >= logging.WARNING else self._plain
        return fmt.format(record)


def _console_filter(record: logging.LogRecord) -> bool:
    # Third-party INFO chatter never reached the console before; keep it off.
    return record.levelno >= logging.WARNING or record.name.startswith(OWN_LOGGERS)


def start_logging_console(name: str) -> str:
    """Install the file (+ console when there is one) handlers and the crash
    hooks for this process. Returns the log file path."""
    os.makedirs(LOG_DIR, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    path = os.path.join(
        LOG_DIR, f"{safe}_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}.log")

    root = logging.getLogger()
    root.setLevel(logging.INFO)                       # libraries: INFO and up
    logging.getLogger(OWN_LOGGERS).setLevel(logging.DEBUG)  # our own: everything

    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(FILE_FORMAT))
    root.addHandler(fh)

    if sys.stdout is not None:
        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(logging.INFO)
        sh.setFormatter(_ConsoleFormatter())
        sh.addFilter(_console_filter)
        root.addHandler(sh)

    crash_log = logging.getLogger(OWN_LOGGERS + ".unhandled")

    def _excepthook(exc_type, exc, tb):
        crash_log.critical("unhandled exception - the process is exiting",
                           exc_info=(exc_type, exc, tb))

    def _thread_excepthook(args):
        if args.exc_type is SystemExit:
            return
        crash_log.critical("unhandled exception in thread %s",
                           args.thread.name if args.thread else "?",
                           exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook

    logging.getLogger(OWN_LOGGERS + ".logconsole").debug(
        "log file %s  argv=%s  python=%s", path, sys.argv, sys.executable)
    return path
