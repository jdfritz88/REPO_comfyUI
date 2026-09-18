"""Build Freedom_Face_Shelf.json - a minimal graph that uses the Face Shelf node."""
import json

nodes, links = [], []
_lid = [0]


def L(a, aslot, b, bslot, typ):
    _lid[0] += 1
    links.append([_lid[0], a, aslot, b, bslot, typ])
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


def W(a, aslot, b, bname):
    na = next(n for n in nodes if n["id"] == a)
    nb = next(n for n in nodes if n["id"] == b)
    typ = na["outputs"][aslot]["type"]
    bslot = next(i for i, inp in enumerate(nb["inputs"]) if inp["name"] == bname)
    lid = L(a, aslot, b, bslot, typ)
    na["outputs"][aslot]["links"].append(lid)
    nb["inputs"][bslot]["link"] = lid


def note(nid, pos, size, title, text):
    N(nid, "MarkdownNote", pos, size, wv=[text], title=title,
      color="#233", bg="#355")


# --- graph -----------------------------------------------------------------
N(1, "CheckpointLoaderSimple", (40, 120), (360, 100), wv=["bigLust_v16.safetensors"],
  title="picture model",
  outputs=[OUT("MODEL", "MODEL"), OUT("CLIP", "CLIP"), OUT("VAE", "VAE")])

N(2, "FreedomFaceShelf", (40, 260), (360, 420), wv=[0.9, ""],
  title="pick a trained face",
  inputs=[IN("model", "MODEL"), IN("clip", "CLIP"),
          IN("strength", "FLOAT", "strength"), IN("selected", "STRING", "selected")],
  outputs=[OUT("model", "MODEL"), OUT("clip", "CLIP"),
           OUT("trigger", "STRING"), OUT("person", "STRING")],
  props={"cnr_id": "freedom_face_shelf", "Node name for S&R": "FreedomFaceShelf"})

N(3, "StringConcatenate", (440, 260), (320, 130), wv=["", "woman standing under a streetlight, armor", ", "],
  title="trigger + your words",
  inputs=[IN("string_a", "STRING", "string_a"), IN("string_b", "STRING", "string_b"),
          IN("delimiter", "STRING", "delimiter")],
  outputs=[OUT("STRING", "STRING")])

N(4, "CLIPTextEncode", (440, 420), (320, 110), wv=[""], color="#232", bg="#353",
  title="positive",
  inputs=[IN("clip", "CLIP"), IN("text", "STRING", "text")],
  outputs=[OUT("CONDITIONING", "CONDITIONING")])
N(5, "CLIPTextEncode", (440, 560), (320, 90), wv=["lowres, blurry, deformed, watermark, text"],
  color="#322", bg="#533", title="negative",
  inputs=[IN("clip", "CLIP")], outputs=[OUT("CONDITIONING", "CONDITIONING")])

N(6, "EmptyLatentImage", (440, 680), (320, 100), wv=[832, 1216, 1],
  title="canvas", outputs=[OUT("LATENT", "LATENT")])
N(7, "KSampler", (800, 260), (300, 260),
  wv=[0, "randomize", 30, 6.0, "dpmpp_2m", "karras", 1.0],
  title="render",
  inputs=[IN("model", "MODEL"), IN("positive", "CONDITIONING"),
          IN("negative", "CONDITIONING"), IN("latent_image", "LATENT")],
  outputs=[OUT("LATENT", "LATENT")])
N(8, "VAEDecode", (800, 540), (220, 60),
  inputs=[IN("samples", "LATENT"), IN("vae", "VAE")], outputs=[OUT("IMAGE", "IMAGE")])
N(9, "SaveImage", (800, 620), (300, 260), wv=["face_shelf"],
  inputs=[IN("images", "IMAGE")], outputs=[])

W(1, 0, 2, "model"); W(1, 1, 2, "clip")
W(2, 0, 7, "model"); W(2, 1, 4, "clip"); W(1, 1, 5, "clip")
W(2, 2, 3, "string_a")
W(3, 0, 4, "text")
W(4, 0, 7, "positive"); W(5, 0, 7, "negative"); W(6, 0, 7, "latent_image")
W(7, 0, 8, "samples"); W(1, 2, 8, "vae")
W(8, 0, 9, "images")

note(20, (40, -220), (1060, 300), "FACE SHELF - how to use",
"""**What this is.** The tile grid on the 'pick a trained face' node is your
face shelf. Every LoRA you train with the Face Tool (launcher option 4) shows
up here as a card: the person, and whether it is the **face** LoRA or the
**face + body** LoRA. Three to a row; the rows grow as you train more.

**Click a card.** That face's LoRA is loaded onto the model and CLIP flowing
through the node, and the person's trigger word comes out of the 'trigger'
output. Here it is joined to your prompt text by the 'trigger + your words'
node. Click **None** to use no face.

**strength** 0.9 is a good start. Lower it toward 0.7 if the face looks stiff,
raise toward 1.0 if it is not enough like her.

**Refresh** re-reads the shelf after you train a new face - no need to reload
the workflow.

**Paused faces** (amber, marked 'paused') are LoRAs whose training was
stopped partway. Finish them in the Face Tool before using them.""")

wf = {"id": "freedom-face-shelf", "revision": 0,
      "last_node_id": 60, "last_link_id": _lid[0],
      "nodes": nodes, "links": links, "groups": [],
      "config": {}, "extra": {}, "version": 0.4}
out = r"F:/Apps/freedom_system/REPO_comfyUI/user/default/workflows/Freedom_Face_Shelf.json"
json.dump(wf, open(out, "w", encoding="utf-8"), indent=2)
print("wrote", out, "| nodes", len(nodes), "| links", _lid[0])

KNOWN_OPTIONAL = {"vae"}
for n in nodes:
    if n["type"] == "MarkdownNote":
        continue
    for inp in n["inputs"]:
        if inp.get("link") is None and inp["name"] not in KNOWN_OPTIONAL and "widget" not in inp:
            print("  UNWIRED", n["id"], n["type"], "<-", inp["name"])
