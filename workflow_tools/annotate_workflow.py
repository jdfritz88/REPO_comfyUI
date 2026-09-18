"""Add plain-language titles + hint notes to Freedom_bigLust_SDXL.json."""
import json, copy

P = "F:/Apps/freedom_system/REPO_comfyUI/user/default/workflows/Freedom_bigLust_SDXL.json"
w = json.load(open(P, encoding="utf-8"))
nodes = {n["id"]: n for n in w["nodes"]}

# ---- 1. titles + positions + fix stale widgets_values_named ----
layout = {
    15: ("STEP 1  -  Pick the art model",      [40, 140],  [360, 110]),
    10: ("STEP 2  -  What you WANT  (type here)", [480, 140], [430, 230]),
    11: ("STEP 3  -  What you DON'T want  (leave this)", [480, 590], [430, 200]),
    13: ("STEP 4  -  Picture size",             [480, 1000], [430, 130]),
    12: ("STEP 5  -  Make the picture",         [1010, 140], [300, 290]),
    14: ("STEP 6  -  Develop the picture  (don't touch)", [1400, 140], [260, 90]),
    7:  ("STEP 7  -  See it & save it",         [1720, 140], [520, 660]),
}
for nid, (title, pos, size) in layout.items():
    n = nodes[nid]
    n["title"] = title
    n["pos"] = pos
    n["size"] = size
    n.pop("widgets_values_named", None)  # stale template values; ComfyUI rebuilds it

# make sure the checkpoint + sampler actually carry our values
nodes[15]["widgets_values"] = ["bigLust_v16.safetensors"]
nodes[12]["widgets_values"] = [0, "randomize", 26, 6, "dpmpp_2m", "karras", 1]

# ---- 2. rewrite the big overview note (id 16) ----
nodes[16]["title"] = "READ ME FIRST"
nodes[16]["pos"] = [-470, 60]
nodes[16]["size"] = [440, 430]
nodes[16]["widgets_values"] = ["""## How to make a picture

1. In the **green box (STEP 2)** type what you want to see. Plain sentences are fine.
2. Press the blue **Run** button, top right.
3. Wait 15-60 seconds. The picture shows up in **STEP 7** and is also saved to
   `comfyui/output/freedom/`.

That's it. Everything else is already set up.

### If you want to change something
- **Different look / model:** click the file name in STEP 1.
- **Wider or taller:** change the numbers in STEP 4.
- **New random picture, same idea:** just press Run again.
- **Keep the same picture, tweak wording:** in STEP 5 set *control_after_generate*
  to `fixed`, change a few words, Run.

### Your add-ons (LoRAs)
Emotions, expression_helper, Hands zib all work here. To use one, right-click the
canvas -> Add Node -> loaders -> **Load LoRA**, and wire it between STEP 1 and
STEP 5. (Optional - the recipe works fine without.)
"""]
nodes[16]["color"] = "#322"
nodes[16]["bgcolor"] = "#533"

# ---- 3. one hint note per functional node ----
HINTS = {
    17: (nodes[15], "STEP 1 - the art model",
         "This opens the 'brain' that knows how to paint - **bigLust**, a "
         "photo-real model made for adult images.\n\n"
         "It feeds three things to the rest of the recipe: the painter, the "
         "part that reads your words, and the part that turns the result into "
         "a normal picture.\n\n"
         "**You touch this only** to switch models - click the file name to "
         "pick lustify, CyberRealistic Pony, etc."),
    18: (nodes[10], "STEP 2 - what you want",
         "**This is the main box - type here.**\n\n"
         "Describe the picture in plain sentences: who, where, the lighting, "
         "the mood. Example: *a red-haired woman by a rainy window, soft light, "
         "sharp photo*.\n\n"
         "More detail = closer to what you pictured."),
    19: (nodes[11], "STEP 3 - what you don't want",
         "A list of stuff to avoid: blur, extra fingers, watermarks, a cartoon "
         "look.\n\n"
         "It's already filled in with good defaults. **Leave it alone** unless "
         "the same problem keeps showing up in your pictures - then add a word "
         "for it here."),
    20: (nodes[13], "STEP 4 - size & how many",
         "Sets the shape of the picture and how many to make at once.\n\n"
         "- **832 x 1216** = tall (portrait) - the current setting\n"
         "- **1216 x 832** = wide (landscape)\n"
         "- **1024 x 1024** = square\n\n"
         "Keep batch size at 1 unless you want several at once (uses more "
         "graphics memory)."),
    21: (nodes[12], "STEP 5 - the actual painting",
         "This is where the picture gets made. It takes the painter (STEP 1), "
         "your want / don't-want (STEPS 2-3) and the blank canvas (STEP 4), "
         "and cleans up random noise into an image over **26 passes**.\n\n"
         "- **seed** = the random starting point. Same seed + same words = same "
         "picture.\n"
         "- **control_after_generate**: `randomize` = new picture each Run; "
         "`fixed` = keep tweaking the same one.\n"
         "- Leave steps / cfg / sampler as they are - they're tuned for "
         "bigLust."),
    22: (nodes[14], "STEP 6 - develop it",
         "STEP 5's result is still in a coded form the computer uses. This box "
         "'develops' it into a normal picture you can see.\n\n"
         "**Never touch this.** It just works."),
    23: (nodes[7], "STEP 7 - see it & save it",
         "Shows the finished picture and saves a copy to "
         "`comfyui/output/freedom/`.\n\n"
         "Right-click the picture to save it somewhere else, copy it, or send "
         "it back in as the starting point for another round."),
}
note_pos = {
    17: [40, 290],   18: [480, 400],  19: [480, 820],
    20: [480, 1160], 21: [1010, 460], 22: [1400, 260], 23: [1720, 830],
}
note_size = {
    17: [360, 230], 18: [430, 210], 19: [430, 210],
    20: [430, 250], 21: [300, 320], 22: [260, 180], 23: [520, 200],
}
base_note = copy.deepcopy(nodes[16])
order = max(n.get("order", 0) for n in w["nodes"]) + 1
for nid, (target, title, body) in HINTS.items():
    nn = copy.deepcopy(base_note)
    nn["id"] = nid
    nn["title"] = title
    nn["pos"] = note_pos[nid]
    nn["size"] = note_size[nid]
    nn["order"] = order; order += 1
    nn["widgets_values"] = ["**" + title + "**\n\n" + body]
    nn["color"] = "#233"
    nn["bgcolor"] = "#355"
    nn.pop("widgets_values_named", None)
    w["nodes"].append(nn)

w["last_node_id"] = max(w["last_node_id"], max(HINTS))

# ---- 4. visual group boxes ----
w["groups"] = [
    {"title": "SET IT UP", "bounding": [10, 90, 920, 1330], "color": "#3f789e", "font_size": 24, "flags": {}},
    {"title": "MAKE IT",   "bounding": [980, 90, 340, 700], "color": "#8e7b3f", "font_size": 24, "flags": {}},
    {"title": "GET IT",    "bounding": [1360, 90, 900, 950], "color": "#3f8e5c", "font_size": 24, "flags": {}},
]

json.dump(w, open(P, "w", encoding="utf-8"), indent=2)
print("annotated:", len(w["nodes"]), "nodes,", len(w["groups"]), "groups")
for n in sorted(w["nodes"], key=lambda x: x["id"]):
    print(f"  {n['id']:3} {n['type']:16} {n.get('title','')}")
