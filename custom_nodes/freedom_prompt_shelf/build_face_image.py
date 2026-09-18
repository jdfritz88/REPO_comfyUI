"""Build Freedom_Face_Image.json - make a still with the Face Shelf + Prompt Shelf."""
import json

nodes, links = [], []
_lid = [0]


def L(a, s, b, t, typ):
    _lid[0] += 1
    links.append([_lid[0], a, s, b, t, typ])
    return _lid[0]


def N(nid, typ, pos, size, inputs=None, outputs=None, wv=None, title=None,
      color=None, bg=None, props=None):
    n = {"id": nid, "type": typ, "pos": list(pos), "size": list(size), "flags": {},
         "order": nid, "mode": 0, "inputs": inputs or [], "outputs": outputs or [],
         "properties": props or {"Node name for S&R": typ}}
    if wv is not None:
        n["widgets_values"] = wv
    if title:
        n["title"] = title
    if color:
        n["color"] = color
    if bg:
        n["bgcolor"] = bg
    nodes.append(n)
    return n


def IN(name, typ, widget=None):
    d = {"name": name, "type": typ, "link": None}
    if widget:
        d["widget"] = {"name": widget}
    return d


def OUT(name, typ):
    return {"name": name, "type": typ, "links": [], "slot_index": 0}


def W(a, s, b, bname):
    na = next(n for n in nodes if n["id"] == a)
    nb = next(n for n in nodes if n["id"] == b)
    typ = na["outputs"][s]["type"]
    bs = next(i for i, inp in enumerate(nb["inputs"]) if inp["name"] == bname)
    lid = L(a, s, b, bs, typ)
    na["outputs"][s]["links"].append(lid)
    nb["inputs"][bs]["link"] = lid


def note(nid, pos, size, title, text):
    N(nid, "MarkdownNote", pos, size, wv=[text], title=title, color="#233", bg="#355")


N(1, "CheckpointLoaderSimple", (40, 160), (360, 100), wv=["bigLust_v16.safetensors"],
  title="STEP 1  -  art model",
  outputs=[OUT("MODEL", "MODEL"), OUT("CLIP", "CLIP"), OUT("VAE", "VAE")])

N(2, "FreedomFaceShelf", (40, 300), (360, 430), wv=[0.9, ""],
  title="STEP 2  -  pick her face",
  inputs=[IN("model", "MODEL"), IN("clip", "CLIP"),
          IN("strength", "FLOAT", "strength"), IN("selected", "STRING", "selected")],
  outputs=[OUT("model", "MODEL"), OUT("clip", "CLIP"),
           OUT("trigger", "STRING"), OUT("person", "STRING")],
  props={"cnr_id": "freedom_face_shelf", "Node name for S&R": "FreedomFaceShelf"})

N(3, "FreedomPromptShelf", (440, 160), (420, 560),
  wv=["{trigger} woman, head and shoulders, <describe the pose, setting and lighting>, "
      "<describe her expression>, same face, same person, her own eyes and mouth, "
      "sharp facial features, natural skin texture, detailed",
      "different person, another face, face swap, blended face, changed features, "
      "deformed face, extra face, plastic skin, lowres, blurry, watermark, text"],
  title="STEP 3  -  the prompt  (click a saved one, then edit)",
  inputs=[IN("positive", "STRING", "positive"), IN("negative", "STRING", "negative"),
          IN("trigger", "STRING")],
  outputs=[OUT("positive", "STRING"), OUT("negative", "STRING")],
  props={"cnr_id": "freedom_prompt_shelf", "Node name for S&R": "FreedomPromptShelf"})

N(4, "CLIPTextEncode", (900, 160), (330, 100), wv=[""], color="#232", bg="#353",
  title="positive (leave wired)",
  inputs=[IN("clip", "CLIP"), IN("text", "STRING", "text")],
  outputs=[OUT("CONDITIONING", "CONDITIONING")])
N(5, "CLIPTextEncode", (900, 290), (330, 90), wv=[""], color="#322", bg="#533",
  title="negative (leave wired)",
  inputs=[IN("clip", "CLIP"), IN("text", "STRING", "text")],
  outputs=[OUT("CONDITIONING", "CONDITIONING")])

N(6, "EmptyLatentImage", (900, 400), (330, 100), wv=[832, 1216, 1],
  title="STEP 4  -  size",
  outputs=[OUT("LATENT", "LATENT")])
N(7, "KSampler", (1270, 160), (300, 260),
  wv=[0, "randomize", 30, 6.0, "dpmpp_2m", "karras", 1.0],
  title="STEP 5  -  make it",
  inputs=[IN("model", "MODEL"), IN("positive", "CONDITIONING"),
          IN("negative", "CONDITIONING"), IN("latent_image", "LATENT")],
  outputs=[OUT("LATENT", "LATENT")])
N(8, "VAEDecode", (1270, 450), (220, 60),
  inputs=[IN("samples", "LATENT"), IN("vae", "VAE")], outputs=[OUT("IMAGE", "IMAGE")])
N(9, "SaveImage", (1270, 540), (300, 300), wv=["face_image"],
  title="STEP 6  -  saved to the output folder",
  inputs=[IN("images", "IMAGE")], outputs=[])

W(1, 0, 2, "model"); W(1, 1, 2, "clip")
W(2, 2, 3, "trigger")
W(2, 1, 4, "clip"); W(3, 0, 4, "text")
W(2, 1, 5, "clip"); W(3, 1, 5, "text")
W(2, 0, 7, "model"); W(4, 0, 7, "positive"); W(5, 0, 7, "negative"); W(6, 0, 7, "latent_image")
W(7, 0, 8, "samples"); W(1, 2, 8, "vae")
W(8, 0, 9, "images")

note(20, (40, -230), (1230, 320), "MAKE A STILL WITH HER FACE",
"""**Step 1.** Pick the art model. Any SDXL model works with the face LoRAs.

**Step 2 - the Face Shelf.** Click the card for the person you want. Use her
**face** card for a portrait, her **face + body** card for a full-body shot.
The strength dial is 0.9 by default - lower toward 0.7 if her face looks stiff,
raise toward 1.0 if it is not enough like her. Click **None** for no face.

**Step 3 - the Prompt Shelf.** Click one of the two saved prompts and it drops
into the box. Fill in the `<...>` parts - the pose, the setting, and the
expression you want her to have. `{trigger}` fills in the picked person for
you. You can save your own prompts with **Save current**.

**Steps 4-6.** Size, render, save. Every picture also auto-saves.

**For video:** a face LoRA can't be loaded onto the Wan video model - it is a
different kind of model. Make the still here first, then send that saved still
into the video queue in the Freedom_Video workflow. The face carries through
because the video is built from your start picture.""")

wf = {"id": "freedom-face-image", "revision": 0, "last_node_id": 60,
      "last_link_id": _lid[0], "nodes": nodes, "links": links, "groups": [],
      "config": {}, "extra": {}, "version": 0.4}
out = r"F:/Apps/freedom_system/REPO_comfyUI/user/default/workflows/Freedom_Face_Image.json"
json.dump(wf, open(out, "w", encoding="utf-8"), indent=2)
print("wrote", out, "| nodes", len(nodes), "| links", _lid[0])

for n in nodes:
    if n["type"] == "MarkdownNote":
        continue
    for inp in n["inputs"]:
        if inp.get("link") is None and "widget" not in inp:
            print("  UNWIRED", n["id"], n["type"], "<-", inp["name"])
