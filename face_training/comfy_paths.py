"""The one place that says where a trained LoRA gets published.

Everything of ours lives in REPO_comfyUI; the developer's ComfyUI lives in
app_cabinet\comfyui and is kept pristine so it can be updated (see
REPO_comfyUI/logs/move_to_app_cabinet_HANDOFF_2026-09-17.md). A training run
must never write into the developer's folder.

Before 2026-09-18 the repo path was spelled out by hand in three files -
pipeline.py, thumbs.py and face_tool_ui.py. All three agreed, so nothing was
broken, but nothing stopped them drifting apart either, and nothing checked
the destination before a run wrote to it. This module holds the path once and
provides the check.
"""

import os

# The invariant. Our ComfyUI repo, and the only place published LoRAs belong.
COMFY_REPO = r"F:\Apps\freedom_system\REPO_comfyUI"
COMFY_LORAS = os.path.join(COMFY_REPO, "models", "loras")
FACES_DIR = os.path.join(COMFY_LORAS, "faces")
THUMBS_DIR = os.path.join(FACES_DIR, "_thumbs")
REGISTRY = os.path.join(FACES_DIR, "_registry.json")

# The developer's app. Named here only so the guard can say plainly when a
# destination has landed in it.
APP_CABINET_COMFY = r"F:\Apps\freedom_system\app_cabinet\comfyui"

# Proof that COMFY_REPO is really our repo and not an empty folder that some
# makedirs call created at a stale path. custom_nodes is ours and always there.
REPO_MARKER = "custom_nodes"


class PublishDestinationError(RuntimeError):
    """The place a LoRA was about to be written to is not our repo."""


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _is_within(child: str, parent: str) -> bool:
    c, p = _norm(child), _norm(parent)
    return c == p or c.startswith(p + os.sep)


def check_publish_root() -> str:
    """Refuse to go on unless the publish root really is our repo.

    Called before a training run starts, so a wrong path stops the run instead
    of being discovered after OneTrainer has spent hours on a LoRA.
    """
    if _is_within(COMFY_LORAS, APP_CABINET_COMFY):
        raise PublishDestinationError(
            "the publish root is inside the developer's ComfyUI (%s). Nothing "
            "of ours may be written there; it belongs in %s."
            % (APP_CABINET_COMFY, COMFY_REPO))

    if not os.path.isdir(COMFY_REPO):
        raise PublishDestinationError(
            "our ComfyUI repo is not at %s. Refusing to run, because creating "
            "that folder would publish LoRAs somewhere nothing reads."
            % COMFY_REPO)

    marker = os.path.join(COMFY_REPO, REPO_MARKER)
    if not os.path.isdir(marker):
        raise PublishDestinationError(
            "%s exists but does not look like our ComfyUI repo - %s is missing. "
            "Refusing to run rather than write LoRAs into the wrong folder."
            % (COMFY_REPO, marker))

    return COMFY_LORAS


def check_publish_path(path: str) -> str:
    """Refuse to write a specific file anywhere but the faces folder.

    The root check above catches a wrong constant; this catches a caller that
    computed its own destination. Returns the path so it can wrap a write.
    """
    check_publish_root()
    if not _is_within(path, FACES_DIR):
        raise PublishDestinationError(
            "refusing to publish %s: it is not inside %s." % (path, FACES_DIR))
    return path


# ---------------------------------------------------------------------------
# OneTrainer's data, moved out of the developer's app on 2026-09-19
# ---------------------------------------------------------------------------
# Until then, _face_profiles (2681 files) and _face_runs (3276 files) sat inside
# app_cabinet\OneTrainer - the developer's own checkout. Nothing of ours belongs
# in there: it makes their folder dirty, it puts her photographs inside a
# third-party app, and an update or a reinstall of OneTrainer would sit on top
# of it. Both folders now live in our repo, and OneTrainer is pointed at them.
#
# Future folders land here too. That is the whole point of naming them once.

PROFILES_ROOT = os.path.join(COMFY_REPO, "_face_profiles")
WORK_ROOT = os.path.join(COMFY_REPO, "_face_runs")

# The developer's OneTrainer. Named only so the guard can say plainly when a
# path has landed back inside it.
APP_CABINET_ONETRAINER = r"F:\Apps\freedom_system\app_cabinet\OneTrainer"


class DataRootError(RuntimeError):
    """A profile or training folder resolved somewhere it does not belong."""


def check_data_root(path: str, what: str = "data") -> str:
    """Refuse to use a profile or work folder outside our repo.

    Called before anything is written, so a wrong path stops the work instead of
    being discovered after hours of training. Returns the path, so it can wrap a
    destination inline.
    """
    if _is_within(path, APP_CABINET_ONETRAINER):
        raise DataRootError(
            "the %s folder resolved to %s, which is inside the developer's "
            "OneTrainer. Nothing of ours may be written there; it belongs in %s."
            % (what, path, COMFY_REPO))

    if not _is_within(path, COMFY_REPO):
        raise DataRootError(
            "the %s folder resolved to %s, which is outside our repo (%s). "
            "Refusing to use it." % (what, path, COMFY_REPO))

    if not os.path.isdir(os.path.join(COMFY_REPO, REPO_MARKER)):
        raise DataRootError(
            "%s does not look like our ComfyUI repo - %s is missing. Refusing "
            "to use it rather than create folders nothing reads."
            % (COMFY_REPO, os.path.join(COMFY_REPO, REPO_MARKER)))

    return path


def profiles_root() -> str:
    """Where face profiles live. Checked every time it is asked for."""
    return check_data_root(PROFILES_ROOT, "profiles")


def work_root() -> str:
    """Where training runs live. Checked every time it is asked for."""
    return check_data_root(WORK_ROOT, "training work")
