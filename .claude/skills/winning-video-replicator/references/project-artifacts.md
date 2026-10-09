# Where each project keeps what the join needs, and what each adapter reads

Measured on 6 Oct 2026 by listing the folders and running every adapter (`scripts/tests/offline_test.py` and the
smoke run in the build conversation). Verify a path before relying on it; pipelines move. The timeline comes from the
build artifacts, never from re-analysing the mp4.

## Channels and folders
| project | folder | channel | adapter | episodes found 6 Oct |
|---|---|---|---|---|
| GEMS (price ladders) | `C:/Users/admin/Downloads/GEMS` | Vault of Stones, `@VaultofStones`, `UCUjn4qZNKnp7xMFAIUJGw6Q` | `gems` | 8 (001 ruby … 006 pearl, 005 gemini) |
| Astro (white cards) | `C:/Users/admin/Downloads/Astro` | Astro Ranked, `UChW8do7jHxCFjC6xgBbhlGQ` (001-008 ids in `reference/thumbs_study/ours_dates.tsv`) | `astro` | 12 |
| Otto Explained (drawn) | `C:/Users/admin/Downloads/Patrick/v2` (`--project` may be `Patrick` or `Patrick/v2`) | `@Otto-explained`, `UCuxt0cVjlhmIGiDNCCrh0CQ` | `otto` | 3 |
| Ancestral Stories | `C:/Users/admin/zayin` | `@ZayinEdwards` per zayin/CLAUDE.md (same id as Astro Ranked; the user said not to worry about it) | `ancestral` | 6 |
| ANIME (moments lists) | `C:/Users/admin/Downloads/ANIME` | not recorded; ask when it is live | `anime` | 1 |
| MOVIE THEORY | `C:/Users/admin/Downloads/MOVIE THEORY` | no channel yet | `gems` layout once episodes exist | 0 |
| Pull Up The Tape (clips) | `C:/Users/admin/Downloads/CLIPPING` | `UCvtRqA8UsAK2quiXxjvVwyw`, token in `publish/` is upload-scoped (make a read-only one) | `clips` | 101 uploads |
| SoftChaos (clips) | `C:/Users/admin/Downloads/SOFTCHAOS CLIPPING` | SoftChaos, the account's default Studio channel | `clips` | from its manifest |
| TALARICO (clips) | `C:/Users/admin/Downloads/TALARICO` | the owner's channel | `clips` | from its manifest |

## What each adapter reads (`scripts/ytown/adapters/`)
| adapter | episode folders | title | delivered mp4 | words | sections | beats | spans |
|---|---|---|---|---|---|---|---|
| `gems` | `episodes/NNN-slug/` | `upload info.txt` TITLE | `upload/<Title>/*.mp4`, `render/` | `vo/words.json` {w,s,e,sec} | `vo/sections.json` (OPEN=hook, CTA, PAYOFF, OUTRO, END, else item) | `shots/shots.json` shots (clip / still / grid, motion) | overlays → card or price_flash; sfx; takes (`vo/takes.json`); music from `bed.json` (from the grid shot when `fade_across: grid`) |
| `astro` | `episodes/eNNN_slug/` | `plan.js` first comment | `ep/episode.mp4`, `Downloads/ASTRO VIDS` | `ep/words.json` {w,t0,t1} | HOOK then one per `ITEMS` name, cut where the name is first spoken | `ep/seg/list.txt` + ffprobe of each segment (cached in `analytics/join/cache/`), kind `beat` | recordings from `ep/gaps.json` |
| `otto` | `episodes/NNN-slug/` with `vo/vo_align.json` | `metadata.md` "## Title" | `episode.mp4`, `Downloads/otto` | `vo/vo_align.json` items[].words (absolute, with sentence index) | one per item, item 0 = hook | `shots/item_NN.json` anchored to sentence (and word); kinds grid / hero / text / flat; `host` flag from an Otto layer | none |
| `ancestral` | `episodes/NNN_slug/ep/` | the slug (titles are not stored; the uploaded file name and the duration map it) | `ep/*final*.mp4` | `ep/alignment.json` characters → words, plus the outro alignment offset by the main voice length | OUTRO only | `ep/shots.json` (PANEL / REUSE → still, NEG / TEXT → card) | none |
| `anime` | `episodes/NNN-slug/` with `render/timeline.json` | `timeline.json` title | `render/episode.mp4`, `upload/<Title>/` | `vo/bursts.json` words offset by each burst's start | one per timeline section (OPEN = hook) | timeline segments (clip / montage) | narration bursts, episode tags |
| `clips` | rows of `publish/uploaded_manifest.json` (destination youtube) | the manifest title | `output_path` | `<stem>.words.json` beside the clip if present | none | `analytics/generic/<id>/cuts.json` if present | none |
| `generic` | `analytics/generic/<video id>/` | the id | `episode.mp4` | `transcript.json` (teardown format) | `sections.json` by hand | `cuts.json` | none |

Measured on the real builds on 6 Oct 2026: GEMS 001 ruby 13 sections / 72 sentences / 138 beats / 26 spans / 1,069
words; Astro 007 11 sections / 101 sentences / 166 segments / 10 recordings / 1,816 words; Otto 001 17 sections / 191
sentences / 257 beats / 2,131 words; Ancestral 002 154 sentences / 174 beats / 1,782 words; ANIME 001 10 sections / 12
segments / 20 spans / 343 narrated words; CLIPPING 101 uploads with video ids.

## Known gaps to close on the first live run
- Astro's segments carry no kind (clip / still / card) because the assembler writes none; add a `--timeline` dump to
  `lib/assemble.js` (beat id, t0, t1, kind, caption, moving) when the Astro window first runs this, then teach the
  adapter to read it. Until then Astro's visual metrics are cut counts and recording spans only.
- Ancestral has no hook section marker; the 30-second survival figures carry the hook. zayin's `ep_retime.js` output
  is read generically.
- Clips get a transcript only if one was saved beside the clip; otherwise `cuts` plus the scoreboard.
- Hand fields (`hook_type`, `voice`, `model`, `template`, `topic_class`) are filled from each project's CLAUDE.md by the
  session the first time; nothing reads them automatically.

## Rule destinations
| project | CLAUDE.md section (`rules decide` creates it) | gate code to edit the same day |
|---|---|---|
| GEMS | `## Rules learned from our own channel analytics` | `tools/script_check.py`, `tools/assemble.py`, `tools/thumb.py check`, `tools/thumb_like.py` |
| Astro | same | `lib/metrics.js`, `lib/thumbgate.js`, `lib/card.js`, `lib/dryrun.js` |
| Otto | same, in `Patrick/CLAUDE.md` | `v2/tools/assemble.py`, `script_check.py`, `thumb_build.py --measure` (never the narration pipeline) |
| Ancestral | same, in `zayin/CLAUDE.md` | `lint_speakable.js`, `episodes/_engine/check_thumb_fit.js` |
| ANIME | same | `tools/script_check.py`, `tools/clips.py` gates |
| clipping | same, in the project's CLAUDE.md; a rule for every clipping campaign also goes to `~/.claude/clipping-kit/OWNER_RULES.md` | `shorts/deliver.py`, `shorts/qa_*.py` |
| every channel | `~/.claude/skills/channel-pipeline/references/house-rules.md` → "## From our own analytics" (`--house`) | none |
Skipped proposals go under `## Reviewed and rejected` in the same CLAUDE.md.
