# =============================================================================
# FREEDOM SYSTEM - Portrait Control: preset storage
#
# Two folders are read, in this order, and the two lists are combined:
#   1. the developer's own folder, custom_nodes/comfyui-portrait-master/presets/<NodeClass>/
#      - written by Portrait Master itself when a run happens with save_preset on;
#        a re-install of Portrait Master DELETES it.
#   2. ours, user/default/portrait_presets/<NodeClass>/  (and /user/ for 4a's own presets)
#      - found through ComfyUI's own folder_paths.get_user_directory(), so it sits with
#        the workflows and settings and survives a Portrait Master re-install.
#
# A save refuses a name that already exists in EITHER folder, so the combined list can
# never hold the same name twice.
# =============================================================================
import json
import os
import re
import time

import folder_paths

PM_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "comfyui-portrait-master")
DEV_PRESETS = os.path.join(PM_DIR, "presets")

# The six node groups that live in the workflow. Legacy 2.9.2 is deliberately absent:
# it is not in the workflow, is hidden from the node menu, and is not covered by
# presets or factory reset.
NODE_CLASSES = [
    "PortraitMasterBaseCharacter",
    "PortraitMasterFaceGenerator",
    "PortraitMasterSkinDetails",
    "PortraitMasterStylePose",
    "PortraitMasterMakeup",
    "PortraitMasterPromptStyler",
]

# Portrait Master names its own preset folders after the class's preset_class attribute,
# not the class name. Read that from the class itself rather than hard-coding it.
def dev_folder_for(class_name: str) -> str | None:
    cls = _node_class(class_name)
    pc = getattr(cls, "preset_class", None) if cls else None
    return os.path.join(DEV_PRESETS, pc) if pc else None


def user_root() -> str:
    return os.path.join(folder_paths.get_user_directory(), "default", "portrait_presets")


def user_folder_for(scope: str) -> str:
    return os.path.join(user_root(), scope)


def _node_class(class_name: str):
    try:
        import nodes
        return nodes.NODE_CLASS_MAPPINGS.get(class_name)
    except Exception:
        return None


SAFE_NAME = re.compile(r"^[A-Za-z0-9 _.\-()]{1,64}$")


def valid_name(name: str) -> bool:
    return bool(name) and bool(SAFE_NAME.match(name.strip()))


def _list_dir(path: str) -> list[str]:
    if not path or not os.path.isdir(path):
        return []
    return sorted(os.path.splitext(f)[0] for f in os.listdir(path) if f.endswith(".json"))


def list_presets(scope: str) -> list[dict]:
    """Developer folder first, then ours - the order the combined dropdown shows."""
    out = []
    if scope != "user":
        for n in _list_dir(dev_folder_for(scope)):
            out.append({"name": n, "source": "developer"})
    for n in _list_dir(user_folder_for(scope)):
        out.append({"name": n, "source": "user"})
    return out


def find_preset(scope: str, name: str) -> tuple[str, str] | None:
    """Where a preset lives: (path, source). Developer folder wins the lookup order."""
    dev = dev_folder_for(scope)
    if dev:
        p = os.path.join(dev, f"{name}.json")
        if os.path.isfile(p):
            return p, "developer"
    p = os.path.join(user_folder_for(scope), f"{name}.json")
    if os.path.isfile(p):
        return p, "user"
    return None


def name_taken(scope: str, name: str) -> str | None:
    hit = find_preset(scope, name)
    return hit[1] if hit else None


def read_preset(scope: str, name: str) -> dict | None:
    hit = find_preset(scope, name)
    if not hit:
        return None
    with open(hit[0], "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return {"name": name, "source": hit[1], "data": data}


def write_preset(scope: str, name: str, data: dict, overwrite: bool) -> dict:
    """Write into OUR folder only; the developer's folder is never written by us."""
    if not valid_name(name):
        return {"ok": False, "error": f"'{name}' is not a usable preset name."}
    name = name.strip()
    taken = name_taken(scope, name)
    if taken and not overwrite:
        where = "Portrait Master's own folder" if taken == "developer" else "your preset folder"
        return {"ok": False, "error": f"A preset called '{name}' already exists in {where}."}
    if taken == "developer":
        return {"ok": False, "error":
                f"'{name}' belongs to Portrait Master's own folder and is not overwritten from here."}
    folder = user_folder_for(scope)
    os.makedirs(folder, exist_ok=True)
    payload = dict(data)
    payload["_saved"] = time.strftime("%Y-%m-%d %H:%M:%S")
    path = os.path.join(folder, f"{name}.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
    return {"ok": True, "name": name, "path": path}


def delete_preset(scope: str, name: str) -> dict:
    hit = find_preset(scope, name)
    if not hit:
        return {"ok": False, "error": f"No preset called '{name}'."}
    os.remove(hit[0])
    return {"ok": True, "name": name, "source": hit[1], "path": hit[0]}


def factory_defaults(class_name: str) -> dict:
    """The developer's own starting value for every dial on one node.

    Read live from their class, never copied into our code, so a Portrait Master update
    changes these automatically. Dropdowns with no declared default take their first
    option, which is how ComfyUI itself treats them.
    """
    cls = _node_class(class_name)
    if cls is None:
        return {}
    spec = cls.INPUT_TYPES()
    out = {}
    for section in ("required", "optional"):
        for field, entry in (spec.get(section) or {}).items():
            if field == "text_in":
                continue
            kind = entry[0]
            opts = entry[1] if len(entry) > 1 else {}
            if isinstance(opts, dict) and "default" in opts:
                out[field] = opts["default"]
            elif isinstance(kind, (list, tuple)):
                out[field] = kind[0]
            elif kind == "INT":
                out[field] = 0
            elif kind == "FLOAT":
                out[field] = 0.0
            elif kind == "STRING":
                out[field] = ""
            elif kind == "BOOLEAN":
                out[field] = False
    return out


def all_factory_defaults() -> dict:
    return {c: factory_defaults(c) for c in NODE_CLASSES}
