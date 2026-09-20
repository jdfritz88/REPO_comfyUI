"""
Render one thumbnail per trained LoRA through the running ComfyUI, using the
ComfyUI HTTP API. This doubles as a real check that the finished LoRA loads and
works in the tool that will actually use it.

stdlib only, so the launcher (system Python) can call it directly.

The LoRA must already be copied into ComfyUI/models/loras/ (pipeline.py does
that) and ComfyUI must be running.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from face_training.comfy_paths import COMFY_LORAS

COMFY = "http://127.0.0.1:8188"

# which checkpoint to render each family's thumbnail on (the LoRA's natural home)
FAMILY_CKPT = {
    "sdxl": "bigLust_v16.safetensors",
    "sdxl_pony": "cyberrealisticPony_v110.safetensors",
    "krea2": "bigLust_v16.safetensors",   # placeholder; krea2 not enabled
}

NEG = "lowres, blurry, deformed, extra fingers, watermark, text, bad anatomy"


def comfy_up(timeout=3) -> bool:
    try:
        urllib.request.urlopen(COMFY + "/system_stats", timeout=timeout)
        return True
    except Exception:
        return False


def _post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(COMFY + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _get(path: str) -> dict:
    with urllib.request.urlopen(COMFY + path, timeout=30) as r:
        return json.load(r)


def _object_info_has(node: str) -> bool:
    try:
        info = _get("/object_info/" + node)
        return bool(info)
    except Exception:
        return False


def _graph(ckpt: str, lora_rel: str, prompt: str, w: int, h: int, seed: int) -> dict:
    return {
        "4": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": ckpt}},
        "10": {"class_type": "LoraLoader",
               "inputs": {"lora_name": lora_rel, "strength_model": 0.9,
                          "strength_clip": 0.9,
                          "model": ["4", 0], "clip": ["4", 1]}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"text": prompt, "clip": ["10", 1]}},
        "7": {"class_type": "CLIPTextEncode",
              "inputs": {"text": NEG, "clip": ["10", 1]}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": w, "height": h, "batch_size": 1}},
        "3": {"class_type": "KSampler",
              "inputs": {"seed": seed, "steps": 28, "cfg": 6.0,
                         "sampler_name": "dpmpp_2m", "scheduler": "karras",
                         "denoise": 1.0, "model": ["10", 0],
                         "positive": ["6", 0], "negative": ["7", 0],
                         "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode",
              "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": "facethumb", "images": ["8", 0]}},
    }


def render_thumb(lora_abs_path: str, family: str, crop: str, dest_png: str,
                 subject: str, timeout_s: int = 300) -> str:
    """
    lora_abs_path  the LoRA file, already sitting under ComfyUI/models/loras/
    subject        the person's own trigger and class word, e.g. "lorasusana woman".
                   This used to be the literal "ohwx woman", which is nobody's
                   trigger - so the sample was rendered without ever naming the
                   person the LoRA was trained on.
    returns dest_png on success, raises on failure
    """
    if not comfy_up():
        raise RuntimeError("ComfyUI is not responding on " + COMFY)

    # comfy_paths owns this path; see the note at the top of that module.
    comfy_loras = COMFY_LORAS
    lora_rel = os.path.relpath(lora_abs_path, comfy_loras).replace("/", "\\")

    ckpt = FAMILY_CKPT.get(family, "bigLust_v16.safetensors")
    if crop == "head":
        prompt = f"{subject}, face portrait, headshot, sharp focus, natural light, detailed skin"
        w, h = 832, 1024
    else:
        prompt = f"{subject}, full body, standing, plain studio background, sharp focus"
        w, h = 768, 1152

    graph = _graph(ckpt, lora_rel, prompt, w, h, seed=42)
    resp = _post("/prompt", {"prompt": graph})
    pid = resp["prompt_id"]

    deadline = time.time() + timeout_s
    hist = {}
    while time.time() < deadline:
        time.sleep(2)
        h_all = _get("/history/" + pid)
        if pid in h_all:
            hist = h_all[pid]
            break
    if not hist:
        raise RuntimeError("thumbnail render timed out")

    status = hist.get("status", {})
    if status.get("status_str") == "error" or not status.get("completed", True):
        raise RuntimeError("ComfyUI reported an error rendering the thumbnail: "
                           + json.dumps(status)[:400])

    images = []
    for _node, out in hist.get("outputs", {}).items():
        images += out.get("images", [])
    if not images:
        raise RuntimeError("no image in ComfyUI history for the thumbnail")

    img = images[0]
    q = urllib.parse.urlencode({"filename": img["filename"],
                                "subfolder": img.get("subfolder", ""),
                                "type": img.get("type", "output")})
    os.makedirs(os.path.dirname(dest_png), exist_ok=True)
    with urllib.request.urlopen(COMFY + "/view?" + q, timeout=30) as r, \
            open(dest_png, "wb") as fh:
        fh.write(r.read())
    return dest_png


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("lora")
    ap.add_argument("dest")
    ap.add_argument("--family", default="sdxl")
    ap.add_argument("--crop", default="head")
    a = ap.parse_args()
    print(render_thumb(a.lora, a.family, a.crop, a.dest))
