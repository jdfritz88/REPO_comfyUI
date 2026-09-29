# Checkpoint prompt-hints build - plan and saved hint text (2026-09-29)

The node that will show checkpoint prompt hints (the red "IMPORTANT: prompt hints for this checkpoint"
node in STEP 7, and/or the Pony hints box under STEP 1 - open questions Q52 / Q53 / Q54) is NOT built
yet. Until it is, hint text the user asks to keep is saved here, word for word, and will be moved into
the node's own storage when the node is built.

## CyberRealistic Pony (cyberrealisticPony_v110.safetensors)

### Saved on the user's request, 2026-09-29 ("save this in the cyberealistic prompt hints we're building")

What Danbooru is: a public picture website (danbooru.donmai.us) where every picture is labelled with short
tags, like "rolling_eyes" or "all_fours". Its tag list has become a kind of dictionary for these models.
- The developer research helper quoted CyberRealistic's Pony guide saying "Pony uses Danbooru tags".
- The Pony author's own page, which I read myself today, only says the model is "trained on combination of
  natural language prompts and tags". It doesn't name Danbooru in the part I read.

Sources behind it:
- Danbooru tag page: https://danbooru.donmai.us/wiki_pages/rolling_eyes ("Eyes that are rotated upward.
  Usually associated with fucked silly or ahegao expressions") - read by the community research helper
  through a page-reading tool.
- CyberRealistic "Pony Prompting: Master Guide" (https://civitai.red/articles/31052/pony-prompting-master-guide),
  "Pony uses Danbooru tags" - quoted by the developer research helper; not re-read by Claude.
- Pony Diffusion V6 XL page (https://civitai.com/models/257749), "trained on combination of natural language
  prompts and tags" - read by Claude on 2026-09-29 through Civitai's public data feed.
- Test evidence: `logs/group7_tests_2026-09-29/` Extra 4 - the Danbooru-style tags "rolling eyes, ahegao"
  gave rolled-back eyes in all 6 pictures (with and without Portrait Master); the plain-English
  "eyes rolled back" did not in any other test.
