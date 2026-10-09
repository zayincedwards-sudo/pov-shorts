# {{CHANNEL}}: {{one-line format}} (reference: {{reference channel}})

Project root is this folder. Everything produced lives here, never in temp or the scratchpad. The evidence for every
rule below is in `ANALYSIS.md` (the measured teardown) and `analysis/`. The build recipe is `PRODUCTION.md`.

**Cross-project rules:** read `~/.claude/skills/channel-pipeline/references/house-rules.md` at the start of every
session. It covers credit spend, the untouched voice, git, Notepad docs and the script register. This file records only
what is specific to {{CHANNEL}}, and any user decision here that differs from the house rules wins for this channel.

## Standing rules
- **Topic gate:** {{what a topic must have, measured from the reference's hits vs flops}}.
- **Title:** {{exact pattern, e.g. "Every {X} Type Explained"}}.
- **Thumbnail:** {{template: set, objects, text or none, colours, the reference image it is built on}}. The gate is
  {{tool}}.
- **Script:** `episodes/<ep>/script.md` uses the `## SECTION` + `[shot: …]` + `{card: …}` format
  (`~/.claude/skills/channel-pipeline/references/format-and-scripts.md`, "Script file format"). Target {{words}}
  words. The skeleton is
  {{cold open / roadmap / items / CTA at N% / payoff / outro}}. `tools/script_check.py` must pass before any voice is
  rendered.
- **Hook:** {{the measured hook mechanics}}. Show options to the user before voicing.
- **Facts:** verify every number into `FACTS.md`. Never make the user review it.
- **Voice:** {{voice name and id}} on {{model}}, using the voice's own stored settings. The user picked it from an A/B
  on {{date}}.
- **Visuals:** {{sourced footage / Commons stills / generated images / animation}}. Sources per topic live in
  `episodes/<ep>/footage/sources.json`.
- **Audio:** the narration file, untouched. {{sfx or bed: only if the user asked, summed at the mux}}.
- **Cards:** text on screen only while its exact words are spoken. {{card kinds used by this channel}}.
- **Video:** {{cuts/min}}, median shot {{s}}, {{motion rules}}, {{intro / end screen or none}}.
- **Spending:** ask before any paid call. Images ≤ {{$}} an episode.
- **Docs:** every document for the user is a plain `.txt` (`tools/textdoc.py`).

## Build
`tools/build_episode.py <ep>` runs {{stages}}. Each stage is idempotent and resumable (`--from` / `--to`). It runs as
`CREDITS_OK=1 …` only after the user's yes, with the cost stated.

## Episode order
{{001 …: date delivered, runtime, hook, notes}}

## Build lessons
{{dated, one paragraph each: what went wrong, the fix, the tool that now prevents it}}
