"""
The job table: which (architecture family x crop) LoRAs get trained for each
person, and in what order.

Every enabled row produces one LoRA file and one shelf thumbnail. Adding a
future architecture is one new entry here plus one entry in
face_training/otrain.py FAMILIES - the rest of the pipeline is model-agnostic.

Order matters: jobs run one at a time, top to bottom, so the whole graphics
card is free for each.
"""

# family key (see otrain.FAMILIES) -> enabled?, with a reason when disabled
FAMILY_ENABLED = {
    "sdxl": (True, ""),
    "sdxl_pony": (True, ""),
    "krea2": (
        False,
        "Krea 2 is its own architecture (Qwen3-VL text encoder, Qwen-image VAE). "
        "Training it needs the gated krea/Krea-2-Raw diffusers repo (license + HF "
        "token) and ~20 GB of extra downloads, OneTrainer's smallest Krea 2 LoRA "
        "preset is 16 GB so a 12 GB card needs heavy offloading, and there is no "
        "Krea 2 image workflow in ComfyUI yet to actually use the result. "
        "Enable once those are sorted.",
    ),
}

CROPS = ("head", "head_body")


def job_specs(person: str):
    """Return the ordered list of (family, crop) pairs to train for `person`."""
    out = []
    for family, (enabled, _reason) in FAMILY_ENABLED.items():
        if not enabled:
            continue
        for crop in CROPS:
            out.append((family, crop))
    return out


def disabled_families():
    return {k: reason for k, (enabled, reason) in FAMILY_ENABLED.items() if not enabled}
