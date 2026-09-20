"""
Build a concrete OneTrainer config for one training job and run it headless.

A "job" is one (architecture family, crop) pair, e.g. SDXL + head, or
SDXL-Pony + head_body. build_config() produces a complete OneTrainer config by
layering three things:

  1. OneTrainer's own default config      (create_train_files.py, current schema)
  2. OneTrainer's built-in preset          (training_presets/<family>/..., upstream-maintained)
  3. this job's per-run values             (dataset folder, output path, trigger, step count)

then run_job() writes the config / concepts / samples files and calls
  venv/Scripts/python.exe scripts/train.py --config-path <config>

Runs inside the OneTrainer venv.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field

OT_ROOT = r"F:\Apps\freedom_system\app_cabinet\OneTrainer"
OT_PY = os.path.join(OT_ROOT, "venv", "Scripts", "python.exe")
OT_MKFILES = os.path.join(OT_ROOT, "scripts", "create_train_files.py")
# our stop-aware entry point (mirrors OneTrainer/scripts/train.py + a STOP watcher)
OT_TRAIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ot_train_entry.py")

# Family key -> (OneTrainer model_type, built-in preset relative path, base-model resolver)
#
# base_model: an absolute path to a single-file checkpoint, a diffusers folder,
# or a Hugging Face repo id. For portability a family trains against a neutral
# base, so one LoRA works on every checkpoint of that family.
FAMILIES = {
    "sdxl": {
        "model_type": "STABLE_DIFFUSION_XL_10_BASE",
        "preset": os.path.join("training_presets", "SDXL", "#sdxl 1.0 LoRA.json"),
        "base_model": "stabilityai/stable-diffusion-xl-base-1.0",
        "resolution": "1024",
        "label": "SDXL",
    },
    "sdxl_pony": {
        "model_type": "STABLE_DIFFUSION_XL_10_BASE",
        "preset": os.path.join("training_presets", "SDXL", "#sdxl 1.0 LoRA.json"),
        # Pony-family checkpoints diverge enough from base SDXL that a Pony LoRA
        # is trained against a Pony checkpoint. This is the only Pony checkpoint
        # on the machine and is a reasonable Pony base.
        "base_model": r"F:\Apps\freedom_system\app_cabinet\Stable_Diffusion_SDXL\models\Stable-diffusion\cyberrealisticPony_v110.safetensors",
        "resolution": "1024",
        "label": "SDXL-Pony",
    },
    # krea2 is defined but not enabled by default - see face_training/jobs.py
    "krea2": {
        "model_type": "KREA_2",
        "preset": os.path.join("training_presets", "Krea 2", "#krea2 LoRA 16GB.json"),
        "base_model": "krea/Krea-2-Raw",
        "resolution": "512",
        "label": "Krea 2",
    },
}

CROPS = ("head", "head_body")


# ============================================================================ #
#  TEXT-ENCODER TRAINING — THE USER'S CHOICE: (c)              (2026-09-13)
# ============================================================================ #
#  The three options put to the user were:
#    (a) Leave it off, like OneTrainer's preset.
#    (b) Turn it on with OneTrainer's base defaults: same learning rate as the
#        rest of the model, stop after 30 epochs.
#    (c) Turn it on at half the learning rate, the common community practice.
#        Nobody has tested that at our settings.
#
#  CHOSEN: (c).
#
#  Why there was a choice at all: no authoritative source gives tested values
#  for text-encoder training in a real-person SDXL LoRA. OneTrainer's own SDXL
#  LoRA preset has it OFF; Kohya's SDXL docs recommend training the UNet only.
#  Sources that do train it agree the text encoder should learn slower than
#  the rest of the model and overfits faster.
#
#  Settings used (the values below are the only place they are set):
#    - text encoders 1 and 2: trained
#    - their learning rate: half of the model's (0.00015 vs 0.0003)
#    - stop training them after: 30 epochs - OneTrainer's base default, kept
#      because option (c) did not name a stop point
#    - base text-encoder weights 16-bit; the LoRA weights being trained stay
#      32-bit (OneTrainer's default lora_weight_dtype)
#    - also decided the same day: rank 16, alpha 1, random flip off
# ============================================================================ #
UNET_LEARNING_RATE = 3e-4                       # OneTrainer's shipped SDXL LoRA preset value
TEXT_ENCODER_LEARNING_RATE = UNET_LEARNING_RATE / 2
TEXT_ENCODER_STOP_AFTER_EPOCHS = 30              # OneTrainer base default (not part of option c)

TRAINING_SETTINGS_BANNER = f"""\
================================================================================
 TRAINING SETTINGS  -  text-encoder training is the user's choice (c), 2026-09-13
--------------------------------------------------------------------------------
 The options were:
   (a) Leave it off, like OneTrainer's preset.
   (b) Turn it on with OneTrainer's base defaults: same learning rate as the
       rest of the model, stop after 30 epochs.
   (c) Turn it on at half the learning rate, the common community practice.
       Nobody has tested that at our settings.
 CHOSEN: (c)
   text encoders 1 + 2 ... trained
   their learning rate ... {TEXT_ENCODER_LEARNING_RATE:g} (half of the model's {UNET_LEARNING_RATE:g})
   stop training them .... after {TEXT_ENCODER_STOP_AFTER_EPOCHS} epochs (OneTrainer's base default - option (c) did not name one)
   rank / alpha .......... 16 / 1
   random flip ........... off
================================================================================"""


def training_settings_summary() -> dict:
    """What every training job is set to - read by the review page's banner."""
    return {
        "choice": "c",
        "options": {
            "a": "Leave it off, like OneTrainer's preset.",
            "b": "Turn it on with OneTrainer's base defaults: same learning rate as the "
                 "rest of the model, stop after 30 epochs.",
            "c": "Turn it on at half the learning rate, the common community practice. "
                 "Nobody has tested that at our settings.",
        },
        "text_encoders_trained": True,
        "text_encoder_learning_rate": TEXT_ENCODER_LEARNING_RATE,
        "model_learning_rate": UNET_LEARNING_RATE,
        "text_encoder_stop_after_epochs": TEXT_ENCODER_STOP_AFTER_EPOCHS,
        "stop_point_note": "OneTrainer's base default - option (c) did not name a stop point",
        "rank": Job.__dataclass_fields__["lora_rank"].default,
        "alpha": Job.__dataclass_fields__["lora_alpha"].default,
        "random_flip": False,
    }


@dataclass
class Job:
    person: str                 # "britany"
    family: str                 # key in FAMILIES
    crop: str                   # "head" | "head_body"
    concept_dir: str            # folder of images + .txt captions
    trigger: str                # LoRA trigger token, e.g. "lorasusana"
    out_dir: str                # where the final .safetensors is written
    work_root: str              # scratch root for workspace + cache + config files
    subject: str = "woman"      # class word from the profile; not always "woman"
    target_steps: int = 2000
    # Decided 2026-09-13 (logs/face_seek_review_rotation_and_dataset_audit_2026-09-13.md
    # section 10): rank 16, alpha 1. The 09-12 LoRAs were trained at 32/32.
    lora_rank: int = 16
    lora_alpha: float = 1.0
    resolution: str | None = None      # overrides family default
    base_model: str | None = None      # overrides family default

    @property
    def name(self) -> str:
        return f"{self.person}_{self.crop}_{self.family}"

    @property
    def out_path(self) -> str:
        return os.path.join(self.out_dir, self.name + ".safetensors")

    @property
    def backup_dir(self) -> str:
        return os.path.join(self.work_root, self.name, "workspace", "backup")

    def has_checkpoint(self) -> bool:
        d = self.backup_dir
        return os.path.isdir(d) and any(
            os.path.isdir(os.path.join(d, x)) for x in os.listdir(d))


@dataclass
class JobResult:
    job: "Job"
    ok: bool
    out_path: str
    steps_done: int
    seconds: float
    log_path: str
    thumb_prompt: str
    sample_image: str = ""      # newest training sample PNG, used as the shelf thumbnail
    stopped_early: bool = False  # user asked to stop; this LoRA is a partial save
    resumed: bool = False        # continued from a checkpoint left by an earlier stop
    error: str = ""


_DEFAULT_CONFIG_CACHE = None


def _default_config(cache_dir: str) -> dict:
    """OneTrainer's current-schema default config, generated once and cached."""
    global _DEFAULT_CONFIG_CACHE
    if _DEFAULT_CONFIG_CACHE is not None:
        return copy.deepcopy(_DEFAULT_CONFIG_CACHE)

    os.makedirs(cache_dir, exist_ok=True)
    cfg_p = os.path.join(cache_dir, "ot_default_config.json")
    con_p = os.path.join(cache_dir, "ot_default_concepts.json")
    smp_p = os.path.join(cache_dir, "ot_default_samples.json")
    if not os.path.isfile(cfg_p):
        subprocess.run(
            [OT_PY, OT_MKFILES,
             "--config-output-destination", cfg_p,
             "--concepts-output-destination", con_p,
             "--samples-output-destination", smp_p],
            cwd=OT_ROOT, check=True, capture_output=True, text=True,
        )
    with open(cfg_p, encoding="utf-8") as fh:
        _DEFAULT_CONFIG_CACHE = json.load(fh)
    return copy.deepcopy(_DEFAULT_CONFIG_CACHE)


def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _builtin_preset(family: str) -> dict:
    rel = FAMILIES[family]["preset"]
    p = os.path.join(OT_ROOT, rel)
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _count_images(folder: str) -> int:
    exts = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
    return sum(
        1 for f in os.listdir(folder)
        if f.lower().endswith(exts) and not f.lower().endswith("-masklabel.png")
    )


def build_config(job: Job) -> dict:
    fam = FAMILIES[job.family]
    n_images = _count_images(job.concept_dir)
    if n_images == 0:
        raise ValueError(f"no images in concept dir: {job.concept_dir}")

    # epochs so that epochs * images ~= target_steps, clamped to a sane band
    epochs = max(20, min(400, round(job.target_steps / max(1, n_images))))
    total_steps = epochs * n_images

    workspace = os.path.join(job.work_root, job.name, "workspace")
    cache = os.path.join(job.work_root, job.name, "cache")
    concepts_file = os.path.join(job.work_root, job.name, "concepts.json")
    samples_file = os.path.join(job.work_root, job.name, "samples.json")
    for d in (workspace, cache):
        os.makedirs(d, exist_ok=True)

    resolution = job.resolution or fam["resolution"]
    base_model = job.base_model or fam["base_model"]

    # Captions are NOT set here - each image carries its own measured .txt,
    # which the concept below reads via prompt_source "sample". Only the sample
    # prompt lives here.
    if job.crop == "head":
        thumb_prompt = (f"{job.trigger} {job.subject}, face portrait, headshot, "
                        f"sharp focus, natural light")
    else:
        thumb_prompt = (f"{job.trigger} {job.subject}, full body, standing, "
                        f"plain background")

    per_run = {
        "training_method": "LORA",
        "model_type": fam["model_type"],
        "base_model_name": base_model,
        "output_model_destination": job.out_path,
        "output_model_format": "KOHYA_LORA" if fam["model_type"].startswith("STABLE_DIFFUSION") else "DIFFUSERS_LORA",
        "output_dtype": "FLOAT_16",
        "workspace_dir": workspace,
        "cache_dir": cache,
        "concept_file_name": concepts_file,
        "sample_definition_file_name": samples_file,
        "resolution": resolution,
        "epochs": epochs,
        "lora_rank": job.lora_rank,
        "lora_alpha": job.lora_alpha,
        "learning_rate": UNET_LEARNING_RATE,
        "learning_rate_scheduler": "CONSTANT",
        "optimizer": {"optimizer": "ADAMW", "weight_decay": 0.01},
        "aspect_ratio_bucketing": True,
        "latent_caching": True,
        # fit a 12 GB card: physical batch 1, accumulate for a stable gradient
        "batch_size": 1,
        "gradient_accumulation_steps": 4,
        # OneTrainer writes output_model_destination when training ends; no
        # periodic saves needed.
        "save_every_unit": "NEVER",
        # Resume support: a rolling checkpoint (weights + optimizer + progress)
        # every few minutes, keeping only the newest, plus one on a clean stop.
        # continue_last_backup makes the next run pick up from it; the pipeline
        # deletes the checkpoint once the LoRA finishes.
        "backup_after": 4,
        "backup_after_unit": "MINUTE",
        "rolling_backup": True,
        "rolling_backup_count": 1,
        "backup_before_save": True,
        "continue_last_backup": True,
        "clear_cache_before_training": False,
        # no in-training sampling; the shelf thumbnail is rendered afterwards
        # through ComfyUI (see face_training/thumbs.py), which also proves the
        # finished LoRA loads and works in the tool that will use it.
        "sample_after_unit": "NEVER",
        "samples_to_tensorboard": False,
        "tensorboard": False,
        "unet": {"train": True, "weight_dtype": "FLOAT_16"},
        "transformer": {"train": True},
        # Text-encoder training: the user's choice (c) - see the banner above
        # CROPS. stop_training_after is set explicitly so it can never silently
        # change if OneTrainer's base default does.
        "text_encoder": {"train": True, "learning_rate": TEXT_ENCODER_LEARNING_RATE,
                         "stop_training_after": TEXT_ENCODER_STOP_AFTER_EPOCHS,
                         "stop_training_after_unit": "EPOCH", "weight_dtype": "FLOAT_16"},
        "text_encoder_2": {"train": True, "learning_rate": TEXT_ENCODER_LEARNING_RATE,
                           "stop_training_after": TEXT_ENCODER_STOP_AFTER_EPOCHS,
                           "stop_training_after_unit": "EPOCH", "weight_dtype": "FLOAT_16"},
        "vae": {"weight_dtype": "FLOAT_32"},
    }

    cfg = _default_config(cache)
    cfg = _deep_merge(cfg, _builtin_preset(job.family))
    cfg = _deep_merge(cfg, per_run)

    # write the concepts file
    concepts = [{
        "name": job.name,
        "path": job.concept_dir,
        "enabled": True,
        "type": "STANDARD",
        "include_subdirectories": False,
        "text": {"prompt_source": "sample", "prompt_path": ""},
        # Off for a person: faces are not symmetric, and a mirrored copy teaches
        # a slightly wrong face. OneTrainer's own default has been off since
        # #1045; every source checked 2026-09-13 agreed.
        "image": {"enable_random_flip": False},
    }]
    with open(concepts_file, "w", encoding="utf-8") as fh:
        json.dump(concepts, fh, indent=2)

    # write the samples file (one prompt, becomes the thumbnail)
    w = h = 1024 if resolution == "1024" else int(resolution.split(",")[0])
    samples = [{
        "enabled": True,
        "prompt": thumb_prompt,
        "negative_prompt": "lowres, blurry, deformed, extra fingers, watermark, text",
        "width": w, "height": h,
        "seed": 42, "random_seed": False,
        "diffusion_steps": 28, "cfg_scale": 6.0,
        "noise_scheduler": "DPMPP",
    }]
    with open(samples_file, "w", encoding="utf-8") as fh:
        json.dump(samples, fh, indent=2)

    return cfg


def _find_output(job: Job) -> str | None:
    if os.path.isfile(job.out_path):
        return job.out_path
    # fall back to any saved LoRA in the workspace
    ws = os.path.join(job.work_root, job.name, "workspace")
    cands = []
    for root, _dirs, files in os.walk(ws):
        for f in files:
            if f.endswith(".safetensors"):
                cands.append(os.path.join(root, f))
    return max(cands, key=os.path.getmtime) if cands else None


def _find_sample_image(job: Job) -> str:
    samples_root = os.path.join(job.work_root, job.name, "workspace", "samples")
    imgs = []
    for root, _dirs, files in os.walk(samples_root):
        for f in files:
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                imgs.append(os.path.join(root, f))
    return max(imgs, key=os.path.getmtime) if imgs else ""


def run_job(job: Job, on_line=None, stop_file: str | None = None) -> JobResult:
    os.makedirs(job.out_dir, exist_ok=True)
    job_dir = os.path.join(job.work_root, job.name)
    os.makedirs(job_dir, exist_ok=True)
    cfg_path = os.path.join(job_dir, "config.json")
    log_path = os.path.join(job_dir, "train.log")
    resumed = job.has_checkpoint()

    cfg = build_config(job)
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)

    with open(os.path.join(job_dir, "samples.json"), encoding="utf-8") as fh:
        thumb_prompt = json.load(fh)[0]["prompt"]

    started = time.time()
    steps_done = 0
    epoch_now = epoch_total = 0
    env = dict(os.environ)
    env["INSIGHTFACE_HOME"] = env.get(
        "INSIGHTFACE_HOME",
        r"F:\Apps\freedom_system\REPO_comfyUI\models\insightface")
    env["ONETRAINER_DIR"] = OT_ROOT
    if stop_file:
        env["OT_STOP_FILE"] = stop_file

    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.Popen(
            [OT_PY, OT_TRAIN, "--config-path", cfg_path],
            cwd=OT_ROOT, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
            # text=True with no explicit encoding decodes with the OS's ANSI
            # codepage (cp1252 on this machine), not UTF-8 - and OneTrainer's
            # own progress-bar output contains bytes cp1252 has no mapping for
            # at all (confirmed: byte 0x8d killed a real run mid-epoch-0 with
            # UnicodeDecodeError, before a single step had been logged).
            # encoding="utf-8" with errors="replace" matches the log file's
            # own handling two lines below.
            encoding="utf-8", errors="replace",
        )
        import re
        frac = re.compile(r"(\d+)\s*/\s*(\d+)")
        for line in proc.stdout:
            log.write(line)
            log.flush()
            s = line.strip()
            low = s.lower()
            m = frac.search(s)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                if low.startswith("epoch"):
                    epoch_now, epoch_total = a, b
                elif low.startswith("step"):
                    steps_done = max(steps_done, epoch_now * b + a)
            if on_line and (low.startswith("epoch") or "saving" in low or "error" in low):
                on_line(s)
        proc.wait()

    seconds = time.time() - started
    out = _find_output(job)
    sample_img = _find_sample_image(job)
    stopped_early = proc.returncode == 3          # our entry's STOPPED_EARLY code
    if (proc.returncode == 0 or stopped_early) and out:
        if out != job.out_path:
            import shutil
            shutil.copy2(out, job.out_path)
        return JobResult(job, True, job.out_path, steps_done, seconds, log_path,
                         thumb_prompt, sample_image=sample_img,
                         stopped_early=stopped_early, resumed=resumed)

    tail = ""
    try:
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            tail = "".join(fh.readlines()[-25:])
    except OSError:
        pass
    return JobResult(job, False, "", steps_done, seconds, log_path, thumb_prompt,
                     sample_image=sample_img, stopped_early=stopped_early,
                     resumed=resumed,
                     error=f"train exit {proc.returncode}; no LoRA produced.\n{tail}")


if __name__ == "__main__":
    # smoke: build a config for a job and print it, do not train
    import argparse
    # Build the token the way the real pipeline does, so this smoke test
    # cannot drift from the convention profiles.py owns.
    from face_training.profiles import trigger_for_slug
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", default="sdxl", choices=list(FAMILIES))
    ap.add_argument("--crop", default="head", choices=CROPS)
    ap.add_argument("--concept-dir", required=True)
    ap.add_argument("--work-root", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    j = Job(person="britany", family=a.family, crop=a.crop, concept_dir=a.concept_dir,
            trigger=trigger_for_slug("britany"), out_dir=a.out_dir,
            work_root=a.work_root)
    cfg = build_config(j)
    print(json.dumps({k: cfg[k] for k in (
        "training_method", "model_type", "base_model_name", "output_model_destination",
        "output_model_format", "resolution", "epochs", "lora_rank", "lora_alpha",
        "batch_size", "gradient_accumulation_steps", "learning_rate")}, indent=2))
    print("concepts + samples written under", os.path.join(a.work_root, j.name))
