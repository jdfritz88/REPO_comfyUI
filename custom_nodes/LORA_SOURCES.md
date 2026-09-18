# Where to get more LoRAs / checkpoints (SDXL images + Wan video)

## Civitai  -  civitai.com  (the main hub)
1. Make a free account and log in.
2. Account -> **Settings -> Browsing Data** -> turn ON "Show mature content"
   and set the content filter to include **X / NSFW** (otherwise adult models
   are hidden).
3. Browse by:
   - Images (SDXL / Pony):  civitai.com/models  -> filter **Base model = SDXL 1.0 / Pony**, sort by Most Downloaded
   - Video motion (Wan):     civitai.com/models  -> filter **Base model = Wan Video**, type **LORA**
   - Tags:  civitai.com/tag/nsfw  ,  civitai.com/tag/wan  ,  civitai.com/tag/motion
4. Download the `.safetensors`. Drop SDXL LoRAs into
   `Stable_Diffusion_SDXL/models/Lora/`, Wan motion LoRAs into
   `Stable_Diffusion_SDXL/models/Lora/wan/` (or wherever the video workflow's
   LoRA folder points). The Folder Inspector will flag anything misfiled.

## Hugging Face  -  huggingface.co
- Search e.g. "wan 2.2 lora nsfw", "sdxl lora", "pony lora".
- Less curated than Civitai; check the model card for the trigger word and
  which base model it needs.

## Trigger words
Almost every LoRA has a **trigger word** (or several) you must put in the
prompt for it to fire. It's on the Civitai / HF page. The Folder Inspector
reads it out of the file when it can.

---

# Video motion LoRAs (for the Freedom Video / Wan workflow)

## The situation (honest)
- **Wan 2.2 has 2,500+ LoRAs, but most are for the 14-billion T2V model**, not
  the **5-billion TI2V** model your video workflow runs (chosen because it fits
  12 GB). The 5B image-to-video LoRA scene is smaller and newer.
- Many "expression" LoRAs (ahegao / eyes-rolling / o-face) are **image** LoRAs
  for SDXL / Pony / Illustrious - put those on the **bigLust image step**, not
  the video step. Wan then animates whatever expression is already in the
  picture.
- For subtle facial motion, a good **motion prompt** + a strong starting image
  often gets you there with **no LoRA at all** - try that first.

## Where to look
- Civitai -> `civitai.com/models` -> filter **Base model = Wan Video 2.2** ,
  type **LORA** . Sort by Most Downloaded.
- Direct: `civitai.com/tag/wan` , `civitai.com/tag/motion` ,
  `civitai.com/tag/expressions`
- For the actions you named, search: "ahegao", "eye roll", "o-face",
  "fingering", "hand motion" - and check the **Base model** on each result:
  - `Wan Video 2.2` or `Wan Video 14B i2v` -> works in the video workflow
  - `SDXL 1.0` / `Pony` / `Illustrious` -> works on the bigLust IMAGE step

## If motion LoRAs really matter
Switching the video model to **Wan 2.2 14B** (heavier, uses the KoboldCpp
auto-swap) unlocks the full, mature LoRA library. Ask and we can add it as a
second option in the workflow.
