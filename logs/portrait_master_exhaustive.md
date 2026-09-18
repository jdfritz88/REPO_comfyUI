# Portrait Master — EXHAUSTIVE log

One file for everything about Portrait Master on this machine: what was installed, every change ever made and
by whom, every design decision the user made, everything that was built, every test and its result, every
defect found (including mine), and what is still open.

- Created 2026-09-16 by combining `portrait_master_updates.md` (history) and
  `portrait_master_user_preset_PLAN.md` (vision, decisions, plan). Both originals were deleted afterwards;
  nothing from them was dropped.
- Times are LOCAL. Claude session transcripts record UTC, which is 7 hours ahead.
- Every claim here has evidence named next to it: git records, file dates, workflow files, ComfyUI's own logs,
  the developer's documents, or the Claude session transcripts.

---

# PART 1 — WHERE THINGS STAND (2026-09-16, end of session)

## 1.1 Portrait Master itself
- Version 3.6.0, commit `dbf65b8`, re-installed fresh from the developer's GitHub today. Identical to their
  newest commit (0 behind).
- `git status --short --ignored` in that folder: CLEAN. None of our code is in it any more.
- Author: Stefano Flore (GitHub `florestefano1975`, also `stefanoflore`); project "AI Wiz Art".
- Its seven node types load: Base Character, Skin Details, Style & Pose, Make-up, Face Generator,
  Prompt Styler, Portrait Master 2.9.2 (Legacy).
- Legacy 2.9.2 is hidden from ComfyUI's node menu — see 6.4. The developer's files are untouched.

## 1.2 Our own add-ons (our folders; a Portrait Master re-install cannot erase them)
| Folder | What it is |
|---|---|
| `custom_nodes/freedom_portrait_control/` | NEW today. The 4a node, its web panel, preset storage, the queue-time rule-applier, and the runtime flag that hides the Legacy node. |
| `custom_nodes/freedom_face_router/` | STEP 2 switch + STEP 5 router. Changed today: the router lost its second text input and its `include_style` switch. |
| `custom_nodes/freedom_prompt_fixups/` | Created 2026-09-10. Turns a seed holding the word "randomize" into a real number at the server, before validation. |
| `custom_nodes/comfyui-prompt-control/` | NEW today. The developer's listed optional dependency (asagi4), v3.0.0-beta.10, for the nationality-blend syntax. |

## 1.3 The workflow
`user/default/workflows/Freedom_bigLust_SDXL v04.json` — 32 nodes, 26 links. STEP 4 is now:

```
4a Random (Portrait Master) user preset   (ours)
4b Base Character      \  the two that cannot be used together, side by side
4c Face Generator      /
4d Skin Details
4e Style & Pose
4f Make-up
4g Prompt Styler       (off by default)

chain:  4c -> 4b -> 4d -> 4e -> 4f -> 4g -> STEP 5 router -> your typed words -> encode -> picture
```
- All seven nodes open COLLAPSED.
- Every Portrait Master dial sits at the developer's own starting value; no seed value is saved anywhere.
- The STEP 4 group was moved to clear canvas space below (y = 1470) because seven nodes in one row no longer
  fitted beside STEP 7. The single left-to-right row is what the phone's card order depends on.
- The positive prompt's encode node is now `PCLazyTextEncode` ("PC: Schedule prompt"). The negative prompt's
  encode is untouched.

## 1.4 Addresses
- This computer: `http://127.0.0.1:8188`
- Phone, Comfy Portal app: `http://<TAILSCALE_IP>:8188`
- Phone, Safari, no app: `http://<TAILSCALE_IP>:8188/mobile`
- The server listens on both 127.0.0.1 and the Tailscale address.

## 1.5 Where things are kept
| What | Where |
|---|---|
| Our 4a presets | `user/default/portrait_presets/user/*.json` |
| Our per-node presets | `user/default/portrait_presets/<NodeClassName>/*.json` |
| The developer's presets | `custom_nodes/comfyui-portrait-master/presets/<PresetClass>/*.json` (deleted by a re-install) |
| Today's full backup | `_backups/portrait_master_20260916-115527/` (whole folder, both preset files, the workflow, the git state) |
| Workflow backups | `user/default/workflow_backups/` |

---

# PART 2 — COMPLETE HISTORY

## 2.1 Changes made INSIDE the developer's folder
| # | When | Who | What | Evidence |
|---|---|---|---|---|
| 1 | 2026-09-08 22:49 | Claude session db0790b4 | Installed it: `git clone --depth 1` into `custom_nodes`. | `git reflog`; transcript 2026-09-09T05:49:32Z |
| 2 | 2026-09-08 22:51-52 | Claude test run | Created `presets/FaceGenerator/test_verify_face.json` by running Face Generator with `save_preset` on. | file date; transcript; ComfyUI log "Saved preset to …" |
| 3 | 2026-09-11 00:48 | Claude session db0790b4 | Backed up their file as `__init__.py.orig-before-freedom-20260911-004848`. Byte-identical to their code apart from line endings. | transcript 07:48:48Z; byte comparison |
| 4 | 2026-09-11 00:49 | Claude, at the user's request ("lets try this first") | CODE EDIT 1 — preset loading: `params.update(preset_data)` replaced so a preset fills only dials still at the developer's default. | transcript 07:49:03Z; `git diff` |
| 5 | 2026-09-11 12:41 | Claude, after the user's "wrong type … seed" error | Backup `__init__.py.bak-seedfix-20260911-124119`, then CODE EDIT 2 — `seed` given default 0, min 0, max 0xffffffffffffffff in all five classes. | transcript 19:41:18Z; `git diff` |
| 6 | 2026-09-16 11:55 | this session | BOTH EDITS REMOVED by a full re-install (Part 5). | `git status` clean; 0 matches for either edit |

Not ours: `presets/BaseCharacter/Preset basic.json` (dated 2026-09-11 02:13). No Claude action created it;
Portrait Master writes such a file when a run happens with `save_preset` on.

## 2.2 Changes made OUTSIDE their folder
| # | When | Who | What | Evidence |
|---|---|---|---|---|
| 7 | 2026-09-09 ~11:58 | Claude script | Added the four Portrait Master nodes to `v02`, wired to FreedomFaceSource / FreedomFaceRouter. Set gender = Woman and 18 dials to "random". No seed value saved. | transcript 18:58:57Z; v02 file |
| 8 | 2026-09-10 00:51 | Claude | In v03, replaced the word "randomize" in all four seed slots with numbers (25→1727880776, 28→988065021, 26→976253013, 27→2108882107). | transcript 07:51:56Z |
| 9 | 2026-09-10 ~01:17 | Claude browser script | Loaded v03 into the open ComfyUI page (`loadGraphData`). Changed no file, but replaced what the page held. | transcript 08:17:49Z |
| 10 | 2026-09-10 ~01:52 | Claude | Created `freedom_prompt_fixups`. | file dates; transcript |
| 11 | 2026-09-10 23:40 | Claude | Backed up v03, then stored nodes in STEP order (list order only). Backup `.bak-20260910-234025`. | transcript 06:40Z |
| 12 | 2026-09-11 00:21 | Claude | Moved STEP 5 left of STEP 6; re-sorted storage order. Backup `.bak-20260911-002125`. | transcript 07:21Z |
| 13 | 2026-09-11 01:02 | Claude | Ran a script meant to switch nine more 4a dials to "random". Later copies do NOT show them on random, so it was either not applied or overwritten by a later save. UNRESOLVED. | transcript 08:02:58Z; later backups |
| 14 | 2026-09-11 12:41 | Claude | Set all four seed values in v03 to 0. Backup moved to the Windows temp folder. | transcript 19:41:54Z |
| 15 | 2026-09-14 ~18:35-21:32 | Claude | Moved 4b/4c/4d on the canvas so their left edges run a→b→c→d, for the phone's card order. Positions only. Backup `v03.json.bak_before_step4_order`. | workflow backups |
| 16 | 2026-09-15 18:22 | this session | Wrote the planning log and a memory note. No Portrait Master or workflow change. | file dates |
| 17 | 2026-09-16 | this session | The rebuild — Part 5 below. | this log |

## 2.3 Changes NOT made by any Claude action
| When | What | Evidence |
|---|---|---|
| 2026-09-09 23:22 | `v03` first saved, ALREADY holding "randomize" in all four seed slots. | file listing; first session mention 8 minutes later |
| 2026-09-11 00:06 | `v03` saved again; seeds back to "randomize". | backup `.bak-20260911-002125`; session note |
| 2026-09-11 02:13 | `presets/BaseCharacter/Preset basic.json` written. | file date |
| 2026-09-11 → 09-12 | Dials changed: facial_expression → Fearful, its weight → 1.1, hair_style → Wavy, hair_length → Long, nationality_mix → 1, jawline_weight → 0.15, face_balance_weight → 0.25. | backup comparison |
| 2026-09-12 → 09-14 | breast_size → medium, hair_style → Shoulder Length with Bangs, hair_color → Dirty. | backup comparison |
| 2026-09-14/15 | Seeds became large numbers again; `v04.json` created 2026-09-15 00:49, same content as v03. | workflow files |

## 2.4 The seed story, start to finish
1. The developer declares `seed` with NO default: `"seed": ("INT", {"forceInput": False})`.
2. ComfyUI's page (frontend v1.51.9) gives a seed with no default the value 0, and adds a "control after
   generate" dropdown (default "randomize") to any input named `seed` — `useIntWidget.ts` lines 54, 61-62, 70-78.
3. A save from the page wrote the WORD "randomize" into the seed slot (first seen 2026-09-09 23:22).
4. ComfyUI rejects a word where a number belongs. `comfyui.log` holds **44** such error lines across nodes 25,
   26, 27, 28: `invalid literal for int() with base 10: 'randomize'`.
5. Fixes attempted, in order: numbers written into the file (09-10), the `freedom_prompt_fixups` server hook
   (09-10), the seed code edit (09-11), seeds set to 0 (09-11).
6. Today: the code edit was removed with the re-install, and no seed value is saved in the workflow at all —
   the developer's own shipping state. The `freedom_prompt_fixups` hook remains as the safety net.

## 2.5 Corrections to earlier reporting
1. **2026-09-11:** a session claimed a preset was silently replacing the user's "Confused" expression. Its own
   checks that night showed every node's `load_preset` was "-- disabled --" and no "Loaded preset" line existed
   in ComfyUI's log. No preset was in use. The code edit was made anyway, at the user's request.
2. **2026-09-15:** this session said issue #55 had no reply and that no user recommendations existed for Face
   Generator. Wrong: the developer HAD replied (quoted in 3.3).
3. **2026-09-16:** this session first blamed the browser freeze on the locked screen and said "not our code".
   Wrong: it WAS our code (Defect 1 in Part 7). The locked screen was a separate, real effect.

## 2.6 Evidence sweeps (how completely this was searched)
**Second pass:** every Claude transcript in every project, browser-script actions, ComfyUI run logs, other
projects' Fix/Monitor logs, and the disk for a second copy. Ruled out: no "Loaded preset from …" line exists in
any ComfyUI log (no preset has ever been loaded by a run); the other projects' logs mention "portrait" only
about portrait-ORIENTATION video; only one copy of Portrait Master exists under freedom_system.

**Third pass (all logs, as asked):** the earlier sweep used a search that skips git-ignored files, which is
where log folders live. Redone across every `.log`, `.txt`, `.md`, `.out`, `.err`, `.jsonl`, `.csv` under
`F:\Apps\freedom_system`, hidden and ignored included. Fourteen files mention Portrait Master:
1. `REPO_koboldccp_sst_tts_media/logs/comfyui.log` — the 44 seed errors above.
2. `…/logs/comfyui_20260908_225043.out.log` line 8 — `Saved preset to …\presets\FaceGenerator\test_verify_face.json`.
3. `…/logs/face_pipeline_defects_and_review_2026-09-11.md` — noted the two fixes were "on disk but not live"
   pending a restart. RESOLVED: the server that ran until today started 2026-09-16 00:00:47, after the
   2026-09-11 12:41 file, so they were live.
4. `…/logs/onetrainer_master_reference.md` — two rules the user stated 2026-09-13: "Portrait Master never
   combines… it is only ever its own ending — button 8 — and every 'run all' button (2, 9) excludes it and says
   so in its description." Button 8 = Portrait Master; buttons 2 and 9 exclude it.
5. `F:\Apps\freedom_system\log\claude_code_voice_mode.log` — spoken summaries only.
6. Four `comfyui_*.err.log` — only the start-up line for the folder.
7. README / CHANGELOG / PORTRAIT_MASTER_2.9.2.md inside the folder — the developer's own, unmodified.

Also confirmed: no second copy of Portrait Master anywhere (`app_cabinet\comfyui` holds AdvancedLivePortrait,
an unrelated pack).

---

# PART 3 — WHAT THE DEVELOPER'S OWN DOCUMENTS SAY

## 3.1 Install
README "Method 2": `git clone https://github.com/florestefano1975/comfyui-portrait-master` into `custom_nodes`,
restart ComfyUI. Optional dependencies: ComfyUI Manager; ComfyUI Prompt Control "For nationality mixing syntax".

## 3.2 How the nodes connect
- README "Basic Workflow": add Base Character, then chain the others.
- `screenshot/overview.png`: Base Character → Skin Details → Style & Pose → Make-up → Prompt Styler, with the
  normal prompt and the styled prompt shown side by side. (That picture predates 3.5.0 — no breast/butt dials.)
- `workflow/Portrait Master SDXL.json`: the same four-node chain, ending in Prompt Composer (a separate pack of
  theirs). It contains NO Face Generator and NO Prompt Styler.
- Issue #3 (developer): to use their text, right-click CLIP Text Encode and "convert text to input", then
  connect; same for the negative prompt.
- Issue #11 (developer): the legacy node "generates two output strings: positive and negative… use them however
  you like".

## 3.3 The only documented conflict
Issue #55, developer reply (stefanoflore, 2025-10-23):
> "Face Generator is a simplified node of Base Character. You can cascade both of them with Skin Details, but
> don't use Face Generator with Base Character."
Their attached picture shows two separate chains side by side, never joined.

## 3.4 Defaults, as declared in their code
Every dropdown starts on "-"; "random 🎲" is only ever the second entry in a list, never a default; sliders
start at 0, weight sliders at 1, nationality_mix at 0.5; make-up toggles start off; `photorealism_improvement`
is the ONE thing shipped ON; seeds have no starting value.

## 3.5 Other facts worth keeping
- Prompt Styler (added 30.04.2025) strips SD1.5/SDXL weight numbers and rewrites the prompt as a sentence, aimed
  at Flux, Sana, HiDream.
- Face Generator (added 14.09.2025) always adds five fixed phrases: "front view portrait", "symmetrical face",
  "neutral expression", "white background", "soft diffused lighting".
- Legacy 2.9.2 is the pre-July-2024 all-in-one node, kept so old workflows open. Its dials do NOT start at "-"
  (shot = first list entry, age = 30). Its own example workflows need Prompt Control's old `PromptControlSimple`,
  which that author removed in V2 (issues #43, #44, #46).
- Their "practical advice": high skin/eye detail values may override the chosen shot; use ControlNet with
  `shot` set to "-" for full pose control; disable ControlNet when using the pose library.
- Project activity: last code change 2026-02-09 (3.6.0). Last reply to a user 2026-05-04. No releases or tags.
  Not archived. 1,239 stars, 217 forks. The developer's other ComfyUI projects saw changes as late as June 2026.

---

# PART 4 — THE DESIGN THE USER CHOSE

## 4.1 Principles
- Portrait Master stays exactly as the developer ships it; customising their files is pointless because an
  update or re-install erases it.
- Everything ours lives in our own folders.
- Real code, wired and tested. No assumptions, guesses, shortcuts, placeholders, stubs.
- The computer matters more than the phone; the phone will not show our on-screen controls.
- The word "checkbox" in earlier conversation always meant RADIO BUTTON — one choice only.

## 4.2 The four-a node (4a)
Three radio buttons, one choice only:
1. **Use the preset (dials locked)** — the preset wins. DEFAULT when the workflow opens. Everything on the
   other six nodes is greyed out and unusable: their radios, dropdowns, buttons and dials.
2. **Use the preset, unlock the dials** — the preset loads, dials can be tweaked. Each node's own preset
   controls are greyed; saving happens ONLY on 4a, whose Save / Save as / Delete write the tweaks back.
3. **Ignore the presets** — each node's own three radios take over.

4a also holds: the preset dropdown, a name box, Save, Save as, Delete, and "Factory reset ALL" (which resets the
dials of all six in-workflow nodes; available only in mode 3).

## 4.3 Each node group
Shows, in this order: the shared explanation banner, an indicator of who is in charge, a down arrow, its own
three radios, a preset dropdown, a name box, Save, Save as, Delete, Factory reset.
- **Its radio 1 (default): use this node's preset** — dials locked, no buttons work.
- **Its radio 2: load the preset, unlock the dials** — Save, Save as and Delete all work.
- **Its radio 3: ignore presets, unlock the dials** — Save as and Delete work; Save does not.
- **Factory reset** works only in radio 3, i.e. when no preset is in use for that node.

## 4.4 The conflicting pair
Base Character and Face Generator each carry one radio, wired as a pair: exactly one is filled. An empty radio
means the OTHER node is active. Clicking an empty radio makes that node active and greys the other immediately.
Base Character is the default. Both carry the conflict banner quoting the developer.

## 4.5 Prompt Styler
Wired at the end of the chain, with its own ON/OFF radio on that node, default OFF. Off means the words pass
through untouched.

## 4.6 Presets
- A 4a preset covers the six in-workflow nodes AND the two switches (which of the pair is active, Prompt Styler
  on/off), so loading one can flip them.
- A 4a preset takes effect by WRITING its values into the six nodes' dials; the developer's own chain then
  builds the prompt. The dials stay visible but greyed, so the screen always shows what is being used.
- Each node's dropdown shows the developer's folder first, then ours, combined; the list rebuilds at start-up
  and after save / save as / delete.
- A save is refused if the name exists in EITHER folder.
- Our presets live in `user/default/portrait_presets`.
- Legacy 2.9.2 is excluded from presets and from factory reset.

## 4.7 "User Preset 01" (created today)
| Dial | Value |
|---|---|
| gender | Woman |
| body_type | Curvy |
| facial_expression | - |
| breast_size | medium |
| butt_size | athletic |
| face_shape | - |
| hair_color | - |
| hair_length | - |
| photorealism_improvement | on |

Everything else at the developer's starting value. Switches: start = Base Character, Prompt Styler off.

## 4.8 Banner wording (approved "for now")
On Base Character and Face Generator:
```
These two cannot be used together. The developer: "Face Generator is a
simplified node of Base Character. You can cascade both of them with Skin
Details, but don't use Face Generator with Base Character."
The filled radio is the one in use. Click the empty one to switch.
```
On all six nodes, identical:
```
Radio buttons on 4a decide who is in charge:
  Use preset            - the preset wins, these dials are locked.
  Use preset, unlocked  - the preset loads, you can tweak; saving happens on 4a.
  Ignore presets        - this node's own three radios take over:
      Use this node's preset (default) - dials locked, no buttons.
      Load preset, unlock dials        - save, save as, delete available.
      Ignore presets, unlock dials     - save as and delete available.
Factory reset works only in the last one.
```

## 4.9 Other decisions
- Follow the developer's chain; Step 5's second text input and its `include_style` switch were removed.
- Install ComfyUI Prompt Control and actually wire it.
- Edit `v04` in place, after backing it up.
- All nodes open collapsed, 4a included.
- The two old preset files go back into the developer's own per-node folders, not into 4a's list.
- Legacy 2.9.2: out of the workflow, hidden from the menu, not deleted.

---

# PART 5 — WHAT WAS BUILT AND DONE (2026-09-16)

## 5.1 Backups (11:55)
`_backups/portrait_master_20260916-115527/` holds: the whole folder (109 files, matching the original's 109),
both preset files separately, `Freedom_bigLust_SDXL v04.json.bak`, and the git state before the work.

## 5.2 Re-install (11:55)
Deleted the folder; re-cloned from the developer's GitHub (their Method 2). New copy at commit `dbf65b8`,
"Version 3.6.0". `git status --short --ignored` clean; zero matches for either of our old edits; all five seed
declarations read exactly as they wrote them. Both preset files restored. `py_compile` passes.

## 5.3 Restart (12:11-12:13)
ComfyUI is not standalone here: `REPO_koboldccp_sst_tts_media/launcher.py` starts it, in a cmd window from
`start_koboldcpp_media.bat`. Its own control console offers `c = restart ComfyUI`. Used the launcher's menu
(option 8 "Stop running apps", answered "y", confirmed the port was free, then option 4 "Start ComfyUI Server
and phone access", which is how it had been launched). Back up in ~15 seconds. Later restarts used `c`.
**Never kill the python processes directly** — the launcher owns them.

Verified live afterwards: seven Portrait Master node types; seed declared the developer's way; Base Character's
preset list shows "Preset basic"; Face Generator's shows "test_verify_face"; no errors in the log.

## 5.4 Our add-on (12:20-12:30, refined later)
`custom_nodes/freedom_portrait_control/`
- `presets.py` — storage. Reads the developer's folder first, ours second; refuses a duplicate name in either;
  never writes into the developer's folder; reads factory values LIVE from their classes (so their updates
  change ours automatically).
- `__init__.py` — the 4a node (`mode`, `preset`, and a hidden `state` field), the web routes, the queue-time
  rule-applier, and the runtime flag that hides Legacy 2.9.2.
- `web/portrait_control.js` — the on-screen panel: banners, indicator, arrow, radios, dropdown, name box and
  the four buttons, drawn as real page elements because ComfyUI has no radio widget and Portrait Master ships
  no page code.

**Why a hidden field:** ComfyUI sends a node's INPUT values to the server and nothing else. A radio drawn on one
of the developer's nodes is invisible to the server unless its state travels in something the server receives,
so all per-node choices and the two switches travel in 4a's `state` field.

**Why the server applies the rules too:** the screen is not trusted to be present. A phone, Comfy Portal or a raw
API call obeys the same rules because the applier runs at queue time on the server.

Routes: `GET /freedom/pm/presets`, `GET /freedom/pm/preset`, `POST /freedom/pm/preset/save`,
`POST /freedom/pm/preset/delete`, `GET /freedom/pm/defaults`.

Preset file shape: `{ "nodes": { "<NodeClass>": { dial: value, … } }, "switches": { "start": "base"|"facegen",
"prompt_styler": true|false }, "_saved": "<timestamp>" }`.

## 5.5 The workflow rebuild (12:31)
Backup `workflow_backups/Freedom_bigLust_SDXL v04.json.bak-before-rebuild-20260916-123107`. Added 4a (id 30),
Face Generator (31), Prompt Styler (32). Titles and order set as in 1.3. Every dial reset to the developer's
value, verified field by field with no differences. No seed values saved. Router inputs trimmed. Group moved.

## 5.6 Prompt Control (12:45)
Cloned `asagi4/comfyui-prompt-control` v3.0.0-beta.10 (vendors its own parser; needs ComfyUI ≥ 0.8.0, this is
0.34.0). The positive prompt's encode node is now `PCLazyTextEncode`.
**First attempt was wrong:** `PCTextEncode` handles advanced but NON-scheduling syntax, so the blend was not
applied; a picture test caught it.

## 5.7 Hiding Legacy 2.9.2 (15:45)
Our add-on sets `DEPRECATED = True` on the developer's class at runtime, in memory. ComfyUI's server then
reports `deprecated: true`, and the page hides deprecated nodes unless asked. Their files are untouched.
A page-side filter was tried first and did not take; it was removed rather than left half-working.

---

# PART 6 — EVERY TEST AND ITS RESULT

## 6.1 The rules, on the server (12:40) — real runs, words read back
| Test | Result |
|---|---|
| all dials at the developer's defaults | only "(professional photo, balanced photo, balanced exposure:1.2)" |
| 4a preset wins, "User Preset 01" | "(woman :1.15), curvy body, medium breasts, athletic butt, (professional photo…)" |
| ignore presets + Face Generator active | Base Character switched off; its five fixed phrases appear |
| ignore presets + Prompt Styler ON | whole prompt rewritten as a sentence |
| ignore presets + Base Character on the developer's "Preset basic" | full preset applied, including `[surinamer:cuban:0.5]` |
| 4a preset wins + node switches changed | the preset's own switches win; node radios ignored — as specified |

## 6.2 The nationality blend (12:45)
Prompt Control's own parser: `[italian:japanese:0.5] woman` → `[[0.5, 'italian woman'], [1.0, 'japanese woman']]`;
`(italian woman:1.15), [surinamer:cuban:0.5] woman 18-years-old` splits the same way; plain text stays one entry.
Picture tests: the two blend settings give different images, and ComfyUI's plain encoder treats the brackets as
literal text.

## 6.3 End to end (12:51)
The saved file, converted to a runnable prompt and submitted: `success`,
`output/pm_rebuild_test/run_00001_.png`. Log for that run:
`[freedom_portrait_control] applied: 4a preset 'User Preset 01' (preset wins - dials locked);
PortraitMasterFaceGenerator switched off (start = base); Prompt Styler bypassed (5 value(s) set)`.

## 6.4 On screen (15:00-15:40) — each by clicking the real control
| Test | Result |
|---|---|
| workflow loads with all seven panels | 32 nodes, 7 panels, ~0.5 s |
| 4a radios, default | "Use the preset (dials locked)"; indicator "In charge: preset wins - dials locked" |
| 4a buttons in preset mode | Save / Save as / Delete active, "Factory reset ALL" greyed |
| 4a set to "ignore presets" | its three buttons grey out, "Factory reset ALL" becomes active, node radios come alive |
| node radios (Base Character) | radio 1 = dials locked, no buttons; radio 3 = Save greyed, Save as + Delete + Factory reset active |
| conflict pair | clicking Face Generator's radio sets start=facegen and greys Base Character |
| Prompt Styler radio | ON and OFF both register in the hidden state the server reads |
| factory reset (one node) | freckles set to 1.5, pressed reset, back to 0 |
| Save as (node scope) | wrote `user/default/portrait_presets/PortraitMasterBaseCharacter/TEST DELETE ME.json`; list then showed the developer's "Preset basic" AND ours together |
| duplicate name | refused: "A preset called 'TEST DELETE ME' already exists in your preset folder." |
| Delete | removed only our test file; the developer's two presets untouched |
| Save as + Save (4a scope) | preset covering all six nodes plus switches; pressing Save again updated its stamp (15:08:30 → 15:08:50) |
| Delete (4a scope) | test preset gone; "User Preset 01" remains |
| Legacy 2.9.2 | server reports `deprecated: true`; the page's visible node list does not contain it |

## 6.5 ComfyUI's own default workflow (15:50)
This ComfyUI has no core template pack and its built-in default graph is empty, so the classic default was
built in the page: Checkpoint → two CLIP Text Encodes → Empty Latent → KSampler → VAE Decode → Save Image,
checkpoint `bigLust_v16.safetensors`, 512×512, 6 steps. Queued from the page's own Run path.
**Result:** success in 21.7 s, `output/default_test/run_00001_.png` (a red apple on a table), ZERO console
errors, ZERO warning toasts. Our add-on does not interfere with ordinary ComfyUI use.

## 6.6 The "58 is funky" warning — resolved
On a clean page, loading the rebuilt workflow produced NO toast, and the wiring reads correctly: router inputs
trained_trigger(59), random_appearance(66), mode(58); the switch's "mode" output holds [58]. The earlier warning
came from ComfyUI restoring the pre-rebuild draft it still held in memory.

---

# PART 7 — DEFECTS FOUND IN MY OWN WORK, AND THE FIXES

1. **Redraw loop (severe).** Our panel refresh called `node.setDirtyCanvas()` once per node. With seven panels
   that re-entered the draw path and the page never finished loading the workflow. Found by staged bisect:
   registration only 457 ms, panels attached 455 ms, refresh without that call 480 ms, with it never.
   **Fix:** one redraw per frame, queued and coalesced. Load now 452-505 ms.
2. **Broken wire number.** Removing two inputs from STEP 5 left link 58 pointing at slot 3.
   **Fix:** corrected to slot 2; the file's links are self-consistent.
3. **Hidden field not hidden.** 4a showed raw JSON, because a multiline text widget draws its own element.
   **Fix:** the element is hidden as well as the widget.
4. **Wrong Prompt Control node** (`PCTextEncode` instead of `PCLazyTextEncode`) — caught by a picture test.
5. **Two workflow-conversion defects** in my test harness: model/clip connections must not be read as dials, and
   ComfyUI stores an extra control word after a seed widget which shifts every later value.
6. **Wrong diagnosis, twice**: blaming the locked screen for a freeze that was my code; and the page-side
   legacy filter that silently did nothing until I checked.

---

# PART 8 — THINGS TO KNOW WHEN WORKING ON THIS AGAIN

- **Chrome must be the FOREGROUND window** on this machine or the ComfyUI page is throttled and every check
  times out. A locked screen does the same.
- **The page restores its last unsaved draft** at start-up and validates it, which can produce warnings about
  the OLD graph. Load the workflow from disk before judging anything.
- **Restart ComfyUI only through the launcher** (`c` in its control console).
- **The phone keeps its own copy** of the workflow. After a rebuild, re-open it from the menu under Recent.
- **The developer's preset folder is deleted by any re-install.** Ours, in `user/default/portrait_presets`, is not.
- **Test leftovers** on disk: `output/pctest/`, `output/pctest2/`, `output/pm_rebuild_test/`, `output/default_test/`.

# PART 9 — STILL OPEN
- Nothing from the agreed plan is outstanding. The items below are optional or unresolved history:
  - Item 13 in 2.2 (the 2026-09-11 "make everything random" script) was never confirmed applied. It no longer
    matters: every dial was reset to the developer's value today.
  - Banner wording was approved "for now" and can be revised.
  - The phone page will not show the radios, banners or buttons; the server still obeys them.
