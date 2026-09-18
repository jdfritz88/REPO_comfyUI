# ==========================================
# FREEDOM SYSTEM - ComfyUI Folder Inspector
# model_inspect.py  (pure Python, no ComfyUI imports - safe to test alone)
# ==========================================
#
# Reads ONLY the header of a model file (never loads weights, never unpickles)
# and works out:
#   * what kind of model it is   -> which ComfyUI folder it belongs in
#   * which base model it is for (SD1.5 / SD2 / SDXL / Pony / Flux / unknown)
#   * a plain-English description (trigger words, resolution, notes, sidecar text)
#
# Safe on huge files: a 12 GB .safetensors is inspected in milliseconds because
# only the JSON header at the start of the file is read.

import json
import os
import struct

# ComfyUI folder types this tool understands, and what each one is for.
FOLDER_INFO = {
    "checkpoints":      "Full art models (the 'brain' that paints). Load Checkpoint box.",
    "loras":            "Small add-on styles / fixes layered on a checkpoint. LoRA Loader box.",
    "vae":              "The 'developer' that turns the coded picture into a real one.",
    "embeddings":       "Tiny text-trick files (textual inversion) used inside prompts.",
    "controlnet":       "Guides the picture with a pose / edge / depth map.",
    "upscale_models":   "Makes finished pictures bigger and sharper (ESRGAN etc).",
    "clip":             "Text encoders (word-readers) shipped separately from a checkpoint.",
    "clip_vision":      "Image encoders used by IP-Adapter / image-prompt tools.",
    "diffusion_models": "Bare painter (UNet / DiT) without its word-reader or developer.",
    "hypernetworks":    "Old-style add-on (pre-LoRA). Rarely used now.",
}

MODEL_EXTS = (".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".sft", ".gguf")
SIDECAR_EXTS = (".txt", ".md", ".json", ".civitai.info", ".preview.png", ".png", ".jpg", ".jpeg", ".webp")


def read_safetensors_header(path, max_bytes=64 * 1024 * 1024):
    """Return (tensors_dict, metadata_dict) from a .safetensors file header only."""
    with open(path, "rb") as fh:
        raw = fh.read(8)
        if len(raw) < 8:
            raise ValueError("file too small to be a safetensors file")
        (hlen,) = struct.unpack("<Q", raw)
        if hlen <= 0 or hlen > max_bytes:
            raise ValueError("bad header length: " + str(hlen))
        header = json.loads(fh.read(hlen).decode("utf-8"))
    meta = header.pop("__metadata__", {}) or {}
    return header, meta


def _any(keys, *needles):
    for k in keys:
        for n in needles:
            if n in k:
                return True
    return False


def _shape_of(tensors, key):
    t = tensors.get(key)
    if isinstance(t, dict):
        return t.get("shape")
    return None


# Video-generation model families. A LoRA / checkpoint tagged with one of these
# is for VIDEO, not for a still-image checkpoint like SDXL.
VIDEO_FAMILIES = {"Wan 2.2", "Wan 2.1", "Wan Video", "HunyuanVideo",
                  "LTX-Video", "CogVideoX", "Mochi"}


def _base_from_meta(meta):
    """Base model named in the training metadata, if any."""
    v = (str(meta.get("ss_base_model_version", "")) + " "
         + str(meta.get("modelspec.architecture", "")) + " "
         + str(meta.get("ss_base_model_name", "")) + " "
         + str(meta.get("modelspec.implementation", ""))).lower()
    # --- video model families first (distinctive keywords) ---
    if "wan" in v:
        if "2.2" in v or "2_2" in v or "a14b" in v or "ti2v" in v:
            return "Wan 2.2"
        if "2.1" in v or "2_1" in v:
            return "Wan 2.1"
        return "Wan Video"
    if "hunyuan" in v and ("video" in v or "hyvideo" in v or "hunyuanvideo" in v):
        return "HunyuanVideo"
    if "ltx" in v or "ltxvideo" in v or "ltx-video" in v:
        return "LTX-Video"
    if "cogvideo" in v:
        return "CogVideoX"
    if "mochi" in v:
        return "Mochi"
    if "krea" in v:
        return "Krea 2"
    if "flux" in v:
        return "Flux"
    if "z-image" in v or "zimage" in v or "z_image" in v:
        return "Z-Image"
    if "qwen" in v:
        return "Qwen-Image"
    if "sd3" in v or "stable-diffusion-v3" in v:
        return "SD3"
    if "sdxl" in v or "stable-diffusion-xl" in v:
        return "SDXL"
    if "sd_v2" in v or "stable-diffusion-v2" in v:
        return "SD2"
    if "sd_v1" in v or "stable-diffusion-v1" in v:
        return "SD1.5"
    return ""


def _base_from_layout(tensors, keys):
    """Base model guessed from the tensor names/shapes (works with no metadata at all)."""
    # --- video transformers (very distinctive block names) ---
    # Wan: blocks.N.{self_attn,cross_attn,ffn} + patch_embedding + text_embedding
    if _any(keys, "blocks.0.cross_attn.", "blocks.0.self_attn.") and \
       _any(keys, "text_embedding.", "patch_embedding.", "time_embedding."):
        return "Wan Video"
    if _any(keys, "diffusion_model.blocks.") and _any(keys, "cross_attn.k.", "cross_attn.v."):
        return "Wan Video"
    # HunyuanVideo: also has double/single_blocks BUT with video-specific vector_in / guidance_in on img
    if _any(keys, "double_blocks.") and _any(keys, "txt_in.", "vector_in.", "guidance_in."):
        return "HunyuanVideo"
    # Newer DiT families - very distinctive block names.
    if _any(keys, "double_blocks.", "single_blocks."):
        return "Flux"
    if _any(keys, "txtfusion.") or (_any(keys, "blocks.") and _any(keys, "attn.gate")):
        return "Krea 2"
    if _any(keys, "adaLN_modulation") and _any(keys, "layers."):
        for k in keys:
            if "attention.to_k" in k and k.endswith("weight"):
                shp = _shape_of(tensors, k)
                if shp and len(shp) == 2 and 3840 in shp:
                    return "Z-Image"
        return "Z-Image"
    if _any(keys, "joint_blocks."):
        return "SD3"
    if _any(keys, "transformer_blocks.") and _any(keys, "img_mod"):
        return "Qwen-Image"
    # UNet families: the cross-attention width tells them apart
    for k in keys:
        if "attn2.to_k" in k or "attn2_to_k" in k:
            shp = _shape_of(tensors, k)
            if shp and len(shp) == 2:
                w = shp[1]
                if w == 768:
                    return "SD1.5"
                if w == 1024:
                    return "SD2"
                if w == 2048:
                    return "SDXL"
    if _any(keys, "lora_te2_", "conditioner.embedders.1"):
        return "SDXL"
    if _any(keys, "lora_te_", "cond_stage_model."):
        return "SD1.5"
    return "unknown"


def classify_safetensors(tensors, meta, size_bytes):
    """Return (folder_type, base_model, notes[])"""
    keys = list(tensors.keys())
    notes = []
    arch = str(meta.get("modelspec.architecture", "")).lower()

    # ---- LoRA / LyCORIS ---------------------------------------------------
    is_lora = (
        _any(keys, "lora_up.", "lora_down.", ".lora_A.", ".lora_B.", "hada_w1", "lokr_w1", "lora_unet_", "lora_te")
        or "ss_network_module" in meta
        or "/lora" in arch
    )
    if is_lora:
        base = _base_from_meta(meta) or _base_from_layout(tensors, keys)
        return "loras", base, notes

    # ---- ControlNet ---------------------------------------------------------
    if _any(keys, "control_model.", "controlnet_cond_embedding", "controlnet_down_blocks"):
        return "controlnet", _base_from_layout(tensors, keys), notes

    # ---- Full checkpoint vs bare painter (diffusion model) ------------------
    has_unet = _any(keys, "model.diffusion_model.")
    has_vae = _any(keys, "first_stage_model.", "vae.decoder", "vae.encoder")
    has_te = _any(keys, "cond_stage_model.", "conditioner.embedders", "text_encoders.")
    layout_base = _base_from_layout(tensors, keys)
    if has_unet and (has_vae or has_te):
        base = _base_from_meta(meta) or layout_base
        if not has_vae:
            notes.append("No VAE baked in - you may need a separate VAE.")
        return "checkpoints", base, notes
    bare_painter = has_unet or layout_base in ("Flux", "Krea 2", "Z-Image", "SD3", "Qwen-Image")
    if bare_painter:
        base = _base_from_meta(meta) or layout_base
        notes.append("Bare painter only - no word-reader or developer inside. Load it with the "
                     "'Load Diffusion Model' box plus separate text encoder and VAE boxes.")
        dtypes = set()
        for k in keys[:50]:
            t = tensors.get(k)
            if isinstance(t, dict):
                dtypes.add(str(t.get("dtype")))
        if any(d.startswith("F8") for d in dtypes):
            notes.append("Stored in FP8 (compact). Fine on RTX 40-series.")
        return "diffusion_models", base, notes

    # ---- VAE ----------------------------------------------------------------
    if has_vae or (_any(keys, "decoder.", "encoder.") and _any(keys, "quant_conv", "post_quant_conv")):
        return "vae", "unknown", notes

    # ---- Embedding (textual inversion) --------------------------------------
    if "emb_params" in keys or ("clip_l" in keys and "clip_g" in keys) or (len(keys) <= 3 and size_bytes < 4 * 1024 * 1024):
        base = "SDXL" if "clip_g" in keys else "SD1.5"
        return "embeddings", base, notes

    # ---- Upscaler -----------------------------------------------------------
    if _any(keys, "model.0.weight", "conv_first", "body.0.rdb1", "upconv1", "conv_last"):
        return "upscale_models", "any", notes

    # ---- CLIP vision / text encoders ----------------------------------------
    if _any(keys, "vision_model.", "visual."):
        return "clip_vision", "any", notes
    if _any(keys, "text_model.", "transformer.resblocks", "encoder.block."):
        return "clip", "any", notes

    return "unknown", "unknown", ["Could not recognise the tensor layout."]


def classify_other(path, size_bytes):
    """Non-safetensors files: we refuse to unpickle, so use name/size hints only."""
    name = os.path.basename(path).lower()
    ext = os.path.splitext(name)[1]
    notes = ["Not a .safetensors file - contents cannot be checked safely (pickle format)."]
    if ext == ".gguf":
        return "diffusion_models", "unknown", ["GGUF quantised model - needs the ComfyUI-GGUF loader."]
    if ext == ".pth" or "esrgan" in name or "upscal" in name or name.startswith("4x") or name.startswith("2x"):
        return "upscale_models", "any", notes
    if ext == ".pt" and size_bytes < 4 * 1024 * 1024:
        return "embeddings", "unknown", notes
    if ext in (".ckpt", ".bin") and size_bytes > 1024 * 1024 * 1024:
        return "checkpoints", "unknown", notes
    if ext in (".pt", ".bin") and size_bytes > 1024 * 1024 * 1024:
        return "checkpoints", "unknown", notes
    return "unknown", "unknown", notes


def human_size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0 or unit == "TB":
            return "{0:.1f} {1}".format(n, unit)
        n = n / 1024.0
    return str(n)


def trigger_words(meta, limit=12):
    """Kohya-trained LoRAs keep a tag-frequency table; the most common tags are the trigger words."""
    raw = meta.get("ss_tag_frequency")
    if not raw:
        return []
    try:
        table = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return []
    counts = {}
    for _folder, tags in table.items():
        if isinstance(tags, dict):
            for tag, n in tags.items():
                tag = str(tag).strip()
                if not tag:
                    continue
                try:
                    counts[tag] = counts.get(tag, 0) + int(n)
                except Exception:
                    pass
    best = sorted(counts.items(), key=lambda kv: -kv[1])[:limit]
    return [t for t, _ in best]


def read_sidecars(path, max_chars=2500):
    """Look for notes saved next to the model (name.txt, name.json, name.civitai.info ...)."""
    stem = os.path.splitext(path)[0]
    out = []
    for ext in (".txt", ".md", ".json", ".civitai.info"):
        p = stem + ext
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read(max_chars)
                if ext in (".json", ".civitai.info"):
                    text = _pretty_json(text, max_chars)
                out.append((os.path.basename(p), text))
            except Exception as exc:
                out.append((os.path.basename(p), "(could not read: " + str(exc) + ")"))
    return out


def _pretty_json(text, max_chars):
    try:
        data = json.loads(text)
    except Exception:
        return text
    keep = {}
    for k in ("activation text", "activation_text", "description", "notes", "sd version", "sd_version",
              "preferred weight", "trainedWords", "baseModel", "name", "type"):
        if isinstance(data, dict) and k in data:
            keep[k] = data[k]
    if isinstance(data, dict) and "model" in data and isinstance(data["model"], dict):
        keep["model.name"] = data["model"].get("name")
        keep["model.type"] = data["model"].get("type")
    if not keep:
        keep = data
    return json.dumps(keep, indent=1, ensure_ascii=True)[:max_chars]


def sidecar_paths(path):
    """All companion files that should travel with a model when it is moved."""
    stem = os.path.splitext(path)[0]
    found = []
    for ext in SIDECAR_EXTS:
        p = stem + ext
        if os.path.isfile(p) and p != path:
            found.append(p)
    return found


def inspect_file(path):
    """Full report for one file. Never raises for a bad file - reports the problem instead."""
    report = {
        "file": os.path.basename(path),
        "size": 0,
        "size_h": "",
        "kind": "unknown",
        "base": "unknown",
        "notes": [],
        "triggers": [],
        "meta": {},
        "sidecars": [],
        "error": "",
    }
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        report["error"] = str(exc)
        return report
    report["size"] = size
    report["size_h"] = human_size(size)
    name = os.path.basename(path).lower()

    if name.endswith(".crdownload") or name.endswith(".part") or name.endswith(".tmp"):
        report["kind"] = "not_a_model"
        report["notes"].append("This is an unfinished browser download, not a model. Delete it or finish the download.")
        return report
    if not name.endswith(MODEL_EXTS):
        report["kind"] = "not_a_model"
        report["notes"].append("Not a model file type (" + os.path.splitext(name)[1] + ").")
        return report

    if name.endswith(".safetensors") or name.endswith(".sft"):
        try:
            tensors, meta = read_safetensors_header(path)
        except Exception as exc:
            report["error"] = "Header could not be read: " + str(exc)
            report["kind"] = "unknown"
            return report
        kind, base, notes = classify_safetensors(tensors, meta, size)
        report["kind"], report["base"], report["notes"] = kind, base, notes
        report["triggers"] = trigger_words(meta)
        show = {}
        for k in ("modelspec.title", "modelspec.description", "modelspec.author", "modelspec.architecture",
                  "modelspec.resolution", "ss_output_name", "ss_base_model_version", "ss_sd_model_name",
                  "ss_resolution", "ss_network_dim", "ss_network_alpha", "ss_num_train_images",
                  "ss_training_comment", "ss_learning_rate", "ss_num_epochs"):
            if k in meta and meta[k] not in ("", None, "None"):
                show[k] = str(meta[k])[:300]
        report["meta"] = show
        report["tensor_count"] = len(tensors)
    else:
        kind, base, notes = classify_other(path, size)
        report["kind"], report["base"], report["notes"] = kind, base, notes

    report["sidecars"] = read_sidecars(path)
    return report


def belongs(kind, folder_type):
    """Does a file of this kind belong in this folder type?  Returns 'yes' / 'no' / 'unsure'."""
    if kind in ("unknown",):
        return "unsure"
    if kind == "not_a_model":
        return "no"
    aliases = {
        "diffusion_models": ("diffusion_models", "unet"),
        "clip": ("clip", "text_encoders"),
    }
    ok = aliases.get(kind, (kind,))
    return "yes" if folder_type in ok else "no"


if __name__ == "__main__":
    # Quick manual test:  python model_inspect.py <folder> <expected_folder_type>
    import sys
    folder = sys.argv[1]
    expect = sys.argv[2] if len(sys.argv) > 2 else "checkpoints"
    for root, _dirs, files in os.walk(folder):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            r = inspect_file(p)
            verdict = belongs(r["kind"], expect)
            print("{0:6} {1:>9}  kind={2:16} base={3:8} {4}".format(verdict, r["size_h"], r["kind"], r["base"], fn))
            if r["triggers"]:
                print("        triggers: " + ", ".join(r["triggers"][:8]))
            for n in r["notes"]:
                print("        note: " + n)
            if r["error"]:
                print("        error: " + r["error"])
