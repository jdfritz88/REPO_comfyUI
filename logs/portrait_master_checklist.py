"""Portrait Master setup checklist, built from logs/portrait_master_exhaustive.md.

Run BEFORE and AFTER the ComfyUI folder move; the two JSON result files are compared item by item.
Usage:  python pm_checklist.py <comfyui_root> <result_json_path>
Every check records PASS / FAIL and the evidence it saw. Nothing here changes any file, except that
the duplicate-name check and the picture tests leave their normal output (picture files) and the
preset tests clean up after themselves.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = sys.argv[1]
OUT = sys.argv[2]
BASE = "http://127.0.0.1:8188"
results = []


def rec(section, name, ok, evidence):
    results.append({"section": section, "check": name, "result": "PASS" if ok else "FAIL",
                    "evidence": evidence})


def get(path, timeout=180):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.load(r)


def post(path, body, timeout=180):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True).stdout.strip()


PM = os.path.join(ROOT, "custom_nodes", "comfyui-portrait-master")
WF = os.path.join(ROOT, "user", "default", "workflows", "Freedom_bigLust_SDXL v04.json")

# ---------------------------------------------------------------------------------------------
# 1. Portrait Master itself
# ---------------------------------------------------------------------------------------------
head = git(PM, "rev-parse", "HEAD")
rec("1 Portrait Master", "commit is dbf65b8 (3.6.0)", head.startswith("dbf65b8"), head)
status = git(PM, "status", "--short")
rec("1 Portrait Master", "git status clean (developer's code untouched)", status == "", status or "(clean)")
hdr = open(os.path.join(PM, "__init__.py"), encoding="utf-8").read(400)
rec("1 Portrait Master", "__init__.py header says Version 3.6.0", "Version: 3.6.0" in hdr,
    re.search(r"Version: [\d.]+", hdr).group(0) if re.search(r"Version: [\d.]+", hdr) else "no version line")
src = open(os.path.join(PM, "__init__.py"), encoding="utf-8").read()
rec("1 Portrait Master", "none of our old edits (FREEDOM CHANGE / seed max)",
    "FREEDOM CHANGE" not in src and "0xffffffffffffffff" not in src, "searched __init__.py")

OI = get("/object_info")
pm_types = sorted(k for k, v in OI.items() if str(v.get("category", "")).startswith("AI WizArt/Portrait Master"))
expected_types = sorted(["PortraitMaster", "PortraitMasterBaseCharacter", "PortraitMasterFaceGenerator",
                         "PortraitMasterMakeup", "PortraitMasterPromptStyler", "PortraitMasterSkinDetails",
                         "PortraitMasterStylePose"])
rec("1 Portrait Master", "all 7 node types load", pm_types == expected_types, pm_types)
rec("1 Portrait Master", "seed declared the developer's way (no default)",
    OI["PortraitMasterBaseCharacter"]["input"]["optional"]["seed"] == ["INT", {"forceInput": False}],
    OI["PortraitMasterBaseCharacter"]["input"]["optional"]["seed"])
rec("1 Portrait Master", "Legacy 2.9.2 hidden (deprecated: true)", OI["PortraitMaster"].get("deprecated") is True,
    OI["PortraitMaster"].get("deprecated"))
bc_presets = OI["PortraitMasterBaseCharacter"]["input"]["required"]["load_preset"][0]
fg_presets = OI["PortraitMasterFaceGenerator"]["input"]["required"]["load_preset"][0]
rec("1 Portrait Master", "restored preset 'Preset basic' in Base Character's list", "Preset basic" in bc_presets, bc_presets)
rec("1 Portrait Master", "restored preset 'test_verify_face' in Face Generator's list", "test_verify_face" in fg_presets, fg_presets)

# ---------------------------------------------------------------------------------------------
# 2. Our add-ons and Prompt Control
# ---------------------------------------------------------------------------------------------
for folder in ("freedom_portrait_control", "freedom_face_router", "freedom_prompt_fixups", "comfyui-prompt-control"):
    rec("2 Add-ons", f"folder present: custom_nodes/{folder}", os.path.isdir(os.path.join(ROOT, "custom_nodes", folder)), folder)
ctl = OI.get("FreedomPortraitUserPreset")
rec("2 Add-ons", "4a node type loads with mode / preset / state",
    bool(ctl) and list(ctl["input"]["required"]) == ["mode", "preset", "state"],
    list(ctl["input"]["required"]) if ctl else "missing")
rout = OI.get("FreedomFaceRouter", {}).get("input", {})
rec("2 Add-ons", "router: required [mode], optional [trained_trigger, random_appearance]",
    list(rout.get("required", {})) == ["mode"] and list(rout.get("optional", {})) == ["trained_trigger", "random_appearance"],
    {"required": list(rout.get("required", {})), "optional": list(rout.get("optional", {}))})
rec("2 Add-ons", "Prompt Control's PCLazyTextEncode loads", "PCLazyTextEncode" in OI, "PCLazyTextEncode" in OI)
web = urllib.request.urlopen(BASE + "/extensions/freedom_portrait_control/portrait_control.js", timeout=60)
js = web.read().decode("utf-8")
rec("2 Add-ons", "4a web panel served, with the redraw fix (queueRedraw)", web.status == 200 and "queueRedraw" in js,
    f"HTTP {web.status}, queueRedraw present: {'queueRedraw' in js}")

# ---------------------------------------------------------------------------------------------
# 3. The workflow v04
# ---------------------------------------------------------------------------------------------
wf = json.load(open(WF, encoding="utf-8"))
nodes = {n["id"]: n for n in wf["nodes"]}
L = {l[0]: l for l in wf["links"]}
rec("3 Workflow", "32 nodes, 26 links", len(wf["nodes"]) == 32 and len(wf["links"]) == 26,
    f"{len(wf['nodes'])} nodes, {len(wf['links'])} links")

expected_row = [
    ("FreedomPortraitUserPreset", "STEP 4a  -  Random (Portrait Master) user preset"),
    ("PortraitMasterBaseCharacter", "STEP 4b  -  Base Character"),
    ("PortraitMasterFaceGenerator", "STEP 4c  -  Face Generator  (cannot be used with 4b)"),
    ("PortraitMasterSkinDetails", "STEP 4d  -  Skin Details"),
    ("PortraitMasterStylePose", "STEP 4e  -  Style & Pose"),
    ("PortraitMasterMakeup", "STEP 4f  -  Make-up"),
    ("PortraitMasterPromptStyler", "STEP 4g  -  Prompt Styler  (off by default)"),
]
row = sorted([n for n in wf["nodes"] if n["type"] in dict(expected_row)], key=lambda n: (n["pos"][0], n["pos"][1]))
got_row = [(n["type"], n["title"]) for n in row]
rec("3 Workflow", "4a..4g left to right with the logged titles", got_row == expected_row, got_row)
rec("3 Workflow", "all seven Step 4 nodes collapsed", all(n.get("flags", {}).get("collapsed") for n in row),
    [n.get("flags") for n in row])
g = [x for x in wf.get("groups", []) if x.get("title") == "STEP 4 PORTRAIT MASTER"]
rec("3 Workflow", "STEP 4 group moved to y ~ 1470 row", bool(g) and abs(g[0]["bounding"][1] - 1380) < 1,
    g[0]["bounding"] if g else "group missing")

by_type = {n["type"]: n for n in wf["nodes"]}
def src_of(node, inp):
    i = next((x for x in node["inputs"] if x["name"] == inp), None)
    return nodes[L[i["link"]][1]]["type"] if i and i.get("link") in L else None
chain = [("PortraitMasterBaseCharacter", "PortraitMasterFaceGenerator"),
         ("PortraitMasterSkinDetails", "PortraitMasterBaseCharacter"),
         ("PortraitMasterStylePose", "PortraitMasterSkinDetails"),
         ("PortraitMasterMakeup", "PortraitMasterStylePose"),
         ("PortraitMasterPromptStyler", "PortraitMasterMakeup")]
chain_ok = all(src_of(by_type[dst], "text_in") == s for dst, s in chain)
router = by_type["FreedomFaceRouter"]
rec("3 Workflow", "chain FaceGen->BaseChar->Skin->Style&Pose->Make-up->Prompt Styler->STEP 5",
    chain_ok and src_of(router, "random_appearance") == "PortraitMasterPromptStyler",
    {dst: src_of(by_type[dst], "text_in") for dst, _ in chain} | {"router.random_appearance": src_of(router, "random_appearance")})

WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN"}
def dial_fields(cls):
    info = OI[cls]["input"]
    out = []
    for f in OI[cls]["input_order"].get("required", []):
        spec = info["required"][f]
        opts = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
        if not opts.get("forceInput") and (isinstance(spec[0], list) or spec[0] in WIDGET_TYPES):
            out.append(f)
    return out
DEF = get("/freedom/pm/defaults")
diffs, seeds_saved = {}, {}
for cls in ["PortraitMasterBaseCharacter", "PortraitMasterFaceGenerator", "PortraitMasterSkinDetails",
            "PortraitMasterStylePose", "PortraitMasterMakeup", "PortraitMasterPromptStyler"]:
    n = by_type[cls]
    fields = dial_fields(cls)
    vals = n.get("widgets_values") or []
    seeds_saved[cls] = len(vals) > len(fields)
    d = {f: v for f, v in zip(fields, vals) if v != DEF[cls].get(f)}
    if d:
        diffs[cls] = d
rec("3 Workflow", "every Portrait Master dial at the developer's starting value", not diffs, diffs or "no differences")
rec("3 Workflow", "no seed value saved on any Portrait Master node", not any(seeds_saved.values()), seeds_saved)
rec("3 Workflow", "positive encode (node 10) is PCLazyTextEncode", nodes[10]["type"] == "PCLazyTextEncode", nodes[10]["type"])
rin = [(i["name"], i.get("link")) for i in router["inputs"]]
l58 = L.get(58)
rec("3 Workflow", "router inputs trained_trigger(59), random_appearance(66), mode(58); wire 58 slot 2",
    rin == [("trained_trigger", 59), ("random_appearance", 66), ("mode", 58)] and l58 and l58[4] == 2
    and 58 in (nodes[24]["outputs"][0].get("links") or []),
    {"inputs": rin, "link58": l58[:5] if l58 else None, "source outputs": nodes[24]["outputs"][0].get("links")})

# ---------------------------------------------------------------------------------------------
# 4. Presets
# ---------------------------------------------------------------------------------------------
pr = get("/freedom/pm/preset?scope=user&name=" + urllib.parse.quote("User Preset 01"))
bcv = pr.get("data", {}).get("nodes", {}).get("PortraitMasterBaseCharacter", {})
spv = pr.get("data", {}).get("nodes", {}).get("PortraitMasterStylePose", {})
want = {"gender": "Woman", "body_type": "Curvy", "facial_expression": "-", "breast_size": "medium",
        "butt_size": "athletic", "face_shape": "-", "hair_color": "-", "hair_length": "-"}
got = {k: bcv.get(k) for k in want}
others = {k: v for k, v in bcv.items() if k not in want and k in DEF["PortraitMasterBaseCharacter"] and v != DEF["PortraitMasterBaseCharacter"][k]}
rec("4 Presets", "User Preset 01 holds exactly the logged values", got == want and spv.get("photorealism_improvement") is True and not others,
    {"named": got, "photorealism": spv.get("photorealism_improvement"), "other non-default dials": others})
rec("4 Presets", "User Preset 01 switches: start base, Prompt Styler off",
    pr.get("data", {}).get("switches") == {"start": "base", "prompt_styler": False}, pr.get("data", {}).get("switches"))
rec("4 Presets", "stored under user/default/portrait_presets/user/",
    os.path.isfile(os.path.join(ROOT, "user", "default", "portrait_presets", "user", "User Preset 01.json")), "file check")
combined = get("/freedom/pm/presets?scope=PortraitMasterBaseCharacter")["presets"]
rec("4 Presets", "Base Character's combined list shows the developer's 'Preset basic' first",
    bool(combined) and combined[0] == {"name": "Preset basic", "source": "developer"}, combined)
st, res = post("/freedom/pm/preset/save", {"scope": "user", "name": "User Preset 01", "data": {}, "overwrite": False})
rec("4 Presets", "duplicate name refused", st == 400 and "already exists" in str(res.get("error", "")), f"HTTP {st}: {res.get('error')}")

# ---------------------------------------------------------------------------------------------
# 5. Server-side rules (the six logged tests)
# ---------------------------------------------------------------------------------------------
def dials(cls):
    return {k: v for k, v in DEF[cls].items() if k != "seed"}
def rule_graph(mode, preset, state):
    return {
        "1": {"class_type": "FreedomPortraitUserPreset", "inputs": {"mode": mode, "preset": preset, "state": json.dumps(state)}},
        "2": {"class_type": "PortraitMasterFaceGenerator", "inputs": dials("PortraitMasterFaceGenerator")},
        "3": {"class_type": "PortraitMasterBaseCharacter", "inputs": dict(dials("PortraitMasterBaseCharacter"), text_in=["2", 0])},
        "4": {"class_type": "PortraitMasterSkinDetails", "inputs": dict(dials("PortraitMasterSkinDetails"), text_in=["3", 0])},
        "5": {"class_type": "PortraitMasterStylePose", "inputs": dict(dials("PortraitMasterStylePose"), text_in=["4", 0])},
        "6": {"class_type": "PortraitMasterMakeup", "inputs": dict(dials("PortraitMasterMakeup"), text_in=["5", 0])},
        "7": {"class_type": "PortraitMasterPromptStyler", "inputs": {"text_in": ["6", 0], "style": "descriptive", "add_extra_instructions": True}},
        "8": {"class_type": "FreedomShowText", "inputs": {"text": ["7", 0]}},
    }
def run_rule(mode, preset, state):
    st, res = post("/prompt", {"prompt": rule_graph(mode, preset, state), "client_id": "pm-checklist"})
    if st != 200:
        return f"REJECTED {json.dumps(res)[:200]}"
    pid = res["prompt_id"]
    for _ in range(90):
        h = get(f"/history/{pid}")
        if h.get(pid, {}).get("status", {}).get("completed"):
            return (h[pid]["outputs"].get("8", {}).get("text") or [""])[0]
        time.sleep(1)
    return "TIMED OUT"

IGN, WINS = "ignore presets - use the dials", "preset wins - dials locked"
PHOTO = "(professional photo, balanced photo, balanced exposure:1.2)"
t = run_rule(IGN, "-- none --", {"nodes": {}, "switches": {"start": "base", "prompt_styler": False}})
rec("5 Server rules", "defaults only -> just the photorealism phrase", t == PHOTO, t)
t = run_rule(WINS, "User Preset 01", {"nodes": {}, "switches": {"start": "base", "prompt_styler": False}})
rec("5 Server rules", "4a preset wins -> woman, curvy, medium breasts, athletic butt",
    t == "(woman :1.15), curvy body, medium breasts, athletic butt, " + PHOTO, t)
t = run_rule(IGN, "-- none --", {"nodes": {}, "switches": {"start": "facegen", "prompt_styler": False}})
rec("5 Server rules", "Face Generator active -> its five fixed phrases",
    t.startswith("front view portrait, symmetrical face, neutral expression, white background, soft diffused lighting"), t)
t = run_rule(IGN, "-- none --", {"nodes": {}, "switches": {"start": "facegen", "prompt_styler": True}})
rec("5 Server rules", "Prompt Styler ON -> rewritten as a sentence", t.startswith("A detailed photo of"), t[:120])
t = run_rule(IGN, "-- none --", {"nodes": {"PortraitMasterBaseCharacter": {"mode": "node preset", "preset": "Preset basic"}},
                                 "switches": {"start": "base", "prompt_styler": False}})
rec("5 Server rules", "Base Character on the developer's 'Preset basic' -> full preset incl. a nationality blend",
    t.startswith("full body, ([") and re.search(r"\[[\w ]+:[\w ]+:0\.5\] woman 18-years-old", t) is not None and "slim body" in t, t[:160])
t = run_rule(WINS, "User Preset 01", {"nodes": {}, "switches": {"start": "facegen", "prompt_styler": True}})
rec("5 Server rules", "preset wins + node switches changed -> preset's switches win",
    t == "(woman :1.15), curvy body, medium breasts, athletic butt, " + PHOTO, t)

# ---------------------------------------------------------------------------------------------
# 6. Prompt Control's parser (the blend proof)
# ---------------------------------------------------------------------------------------------
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "custom_nodes", "comfyui-prompt-control"))
try:
    from prompt_control.parser import parse_prompt_schedules
    p1 = [list(x) for x in parse_prompt_schedules("[italian:japanese:0.5] woman")]
    ok = p1 == [[0.5, {"prompt": "italian woman", "loras": {}}], [1.0, {"prompt": "japanese woman", "loras": {}}]]
    p2 = [list(x) for x in parse_prompt_schedules("plain woman with no blend")]
    rec("6 Blend", "[italian:japanese:0.5] woman -> two scheduled prompts; plain text -> one",
        ok and len(p2) == 1, {"blend": p1, "plain": p2})
except Exception as e:
    rec("6 Blend", "Prompt Control parser importable and correct", False, repr(e))

# ---------------------------------------------------------------------------------------------
# 7. End to end from the saved v04 file, and ComfyUI's default workflow
# ---------------------------------------------------------------------------------------------
CONTROL_WORDS = {"fixed", "increment", "decrement", "randomize"}
def all_dial_names(cls):
    info = OI[cls]["input"]
    names = []
    for section in ("required", "optional"):
        for f in OI[cls]["input_order"].get(section, []):
            spec = info[section][f]
            opts = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
            if opts.get("forceInput"):
                continue
            if isinstance(spec[0], list) or spec[0] in WIDGET_TYPES:
                names.append(f)
    return names
def map_values(cls, values):
    out, i = {}, 0
    for name in all_dial_names(cls):
        if i >= len(values):
            break
        out[name] = values[i]; i += 1
        if name in ("seed", "noise_seed") and i < len(values) and isinstance(values[i], str) and values[i] in CONTROL_WORDS:
            i += 1
    return out
def run_graph(prompt, label, out_key):
    st, res = post("/prompt", {"prompt": prompt, "client_id": "pm-checklist"})
    if st != 200:
        return False, f"REJECTED {json.dumps(res)[:300]}"
    pid = res["prompt_id"]
    for _ in range(300):
        h = get(f"/history/{pid}")
        if h.get(pid, {}).get("status", {}).get("completed"):
            imgs = [i["filename"] for o in h[pid]["outputs"].values() for i in (o.get("images") or [])]
            return h[pid]["status"]["status_str"] == "success" and bool(imgs), f"{h[pid]['status']['status_str']} {imgs}"
        time.sleep(2)
    return False, "TIMED OUT"

prompt = {}
for n in wf["nodes"]:
    if n["type"] in {"Note", "MarkdownNote"} or n.get("mode") in (2, 4) or n["type"] not in OI:
        continue
    inputs = map_values(n["type"], list(n.get("widgets_values") or []))
    for i in n.get("inputs") or []:
        if i.get("link") is not None:
            s = L[i["link"]]
            inputs[i["name"]] = [str(s[1]), s[2]]
    prompt[str(n["id"])] = {"class_type": n["type"], "inputs": inputs}
for n in prompt.values():
    if n["class_type"] == "KSampler":
        n["inputs"]["steps"] = 6; n["inputs"]["seed"] = 4242
    if n["class_type"] == "EmptyLatentImage":
        n["inputs"].update(width=512, height=512, batch_size=1)
    if n["class_type"] == "SaveImage":
        n["inputs"]["filename_prefix"] = "pm_checklist/v04"
    if n["class_type"] == "FreedomPortraitUserPreset":
        n["inputs"]["mode"] = WINS; n["inputs"]["preset"] = "User Preset 01"
ok, ev = run_graph(prompt, "v04", "SaveImage")
rec("7 End to end", "saved v04 workflow makes a picture (4a preset wins)", ok, ev)

ckpt = OI["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0][0]
default = {
    "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
    "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "a photo of a red apple on a table"}},
    "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "blurry, low quality"}},
    "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
    "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
          "seed": 1, "steps": 6, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
    "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
    "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "pm_checklist/default"}},
}
ok, ev = run_graph(default, "default", "SaveImage")
rec("7 End to end", f"ComfyUI's classic default workflow makes a picture ({ckpt})", ok, ev)

# ---------------------------------------------------------------------------------------------
# 8. Addresses
# ---------------------------------------------------------------------------------------------
# The phone address is this machine's private Tailscale IP. It is not written
# down here because this repo is public; set FREEDOM_TAILSCALE_IP before running
# if you want the two phone checks to run. Without it they are skipped, and the
# local check still runs.
_phone_ip = os.environ.get("FREEDOM_TAILSCALE_IP", "").strip()
_checks = [("http://127.0.0.1:8188/", (200,))]
if _phone_ip:
    _checks += [(f"http://{_phone_ip}:8188/", (200,)),
                (f"http://{_phone_ip}:8188/mobile", (200, 302))]

for url, expect in _checks:
    try:
        req = urllib.request.Request(url, method="GET")
        opener = urllib.request.build_opener(type("NoRedirect", (urllib.request.HTTPRedirectHandler,),
                                                  {"redirect_request": lambda *a, **k: None}))
        try:
            code = opener.open(req, timeout=30).status
        except urllib.error.HTTPError as e:
            code = e.code
    except Exception as e:
        code = repr(e)
    rec("8 Addresses", f"{url} answers", code in expect, code)

summary = {"root": ROOT, "ran_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "pass": sum(r["result"] == "PASS" for r in results), "fail": sum(r["result"] == "FAIL" for r in results),
           "results": results}
json.dump(summary, open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(f"PASS {summary['pass']}  FAIL {summary['fail']}  -> {OUT}")
for r in results:
    mark = "ok  " if r["result"] == "PASS" else "FAIL"
    ev = r["evidence"] if isinstance(r["evidence"], str) else json.dumps(r["evidence"], ensure_ascii=False)
    print(f"  [{mark}] {r['section']:18s} {r['check']}" + ("" if r["result"] == "PASS" else f"\n           evidence: {ev[:300]}"))
