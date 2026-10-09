---
name: channel-pipeline
description: This skill should be used when the user wants to build or extend a faceless YouTube video pipeline by reverse-engineering a reference channel. That covers the teardown and measurement, the format rules and script register, voice, footage and image sourcing, assembly, thumbnails and branding, and delivery, followed by producing episodes with the pipeline. Use it for "make a channel like X", "reverse-engineer this channel", "build a pipeline for these videos", "start a new channel", or making or re-cutting an episode in one of the user's existing video projects (GEMS, Astro, Otto, Ancestral Stories, SAM, Movie Theory).
argument-hint: "[reference channel URL or @handle | existing project folder] [what to do]"
---

<!-- Editors: never put a digit straight after a dollar sign in this file. The skill loader treats dollar-number as an
argument slot and replaces it. Write "USD 5" here; the reference files are read normally and may use dollar amounts. -->

# Channel pipeline: from a reference channel to finished episodes

The user builds faceless YouTube channels by tearing down a channel that already works, measuring exactly what it does,
and rebuilding the format as a reproducible pipeline: script → voice → picture → assembly → thumbnail → upload text.
This skill is that process, distilled from their projects. The guides in `references/` hold the detail. Read the one
for the phase you are in, not all of them up front. Run every pipeline command in the **Bash tool** (Git Bash): the
commands here are bash, PowerShell's `timeout` is a different program, and its `>` writes UTF-16, which breaks the
tools' JSON reads.

Arguments: `$ARGUMENTS`

## Always, before anything else
1. Read `references/house-rules.md`. These are the user's standing orders, and most of them came as corrections.
   Breaking one costs their trust. The five that bite most often:
   - **Warn and get a yes before ANY Gemini or ElevenLabs spend.** The credit-guard hook enforces it; never add
     `CREDITS_OK=1` before the yes.
   - **Claude first, then the cheapest Gemini, and Gemini never looks at images** (7 Oct 2026). Do any job you can
     do yourself (reading, looking at frames and sheets, picking footage by eye, judging) instead of calling Gemini;
     in GEMS Gemini only makes the thumbnail. Anything else uses the cheapest model for the job with thinking off
     (house rule 2). The guard refuses pricier models.
   - **Never edit the ElevenLabs audio.** No music unless the user asked for it on that channel.
   - **Everything lives in the project folder.** Deliverables go at its top, and user-facing documents are plain
     Notepad `.txt`.
   - **Measure against the reference, never against our own episodes.**
   - **No review gates.** Verify facts yourself and keep building. Stop only for spend, publishing, deleting, or a
     creative pick the user asked to make, such as topics, hooks and the voice.
2. Work out the situation:
   - **New channel or format from a reference** → run the phases below in order.
   - **An existing project** (the folder has a CLAUDE.md and tools/) → that project's CLAUDE.md governs; read it first.
     Use this skill's guides only for what the project lacks, and the house rules always. The known projects are in
     `references/other-channels.md`.
   - **Fixing or extending one part** → go straight to that phase's guide.
3. Tell the user, in one line, which situation you read and what happens next. Then work. Keep them posted in a few
   words during long stretches.

## Phases for a new channel
| # | Phase | Guide | Done when |
|---|---|---|---|
| 0 | Setup | below | folder, git, `.gitignore`, `.env` key names, CLAUDE.md skeleton |
| 1 | Teardown and measurement | `references/analysis.md` + `scripts/` | `ANALYSIS.md` with measured numbers, hits vs flops, and a rules list with evidence |
| 2 | Format spec, base toolkit, scripts | `references/format-and-scripts.md`, `references/toolkit.md` | CLAUDE.md standing rules; base toolkit chosen and copied; `script_check.py` gates; first script passes |
| 3 | Voice | `references/voice.md` | the user picked a voice (free previews first, then a paid A/B if needed); settings, pace and hook-take profile recorded |
| 4 | Sourcing the picture | `references/sourcing.md` | visual approach decided; sources curated; stills credited |
| 5 | Assembly, review and gates | `references/assembly.md` | every shot reviewed by eye; GATE sync and GATE black frames pass |
| 6 | Branding and metadata | `references/branding.md` | thumbnail template plus its gate; title pattern; `upload info.txt`; channel page |
| 7 | Delivery and iteration | below | `upload/<Title>/` delivered; the user's notes turned into dated CLAUDE.md rules |
Other channels' components and decisions (generated images, drawn animation, white cards, Shorts, publishers) are in
`references/other-channels.md`. Traps already paid for are in `references/gotchas.md`.

**How it usually runs for a new channel:**
1. **First sitting, free.** Phases 0-2: setup, the teardown with `scripts/`, the rules written into CLAUDE.md, the
   base toolkit copied and its gates rewritten. Close with a short summary of what wins and why, and offer a topic
   list.
2. **The user picks a topic.** Research FACTS.md (subagents can split the topic areas), write the script, pass the
   gates, then show 3-4 hook options. For the first episode, propose voices from free previews; quote a paid A/B only
   if the user wants to hear real lines.
3. **After the yes (and the voice pick):** voice, sources, picture, assembly, thumbnail and metadata in one approved
   build. Check by eye wherever the guides say so. Deliver.
4. **The user watches and gives notes.** Apply exactly what they asked, turn each note into a rule, and keep the
   template steady from episode to episode.

## Running commands
- **Use the Bash tool,** with the full path to every script; shell variables do not survive between calls.
- **Timeouts:** the Bash tool stops a command after 2 minutes unless told otherwise. For transcription, cuts, segment
  batches and fetch slices, pass `timeout: 600000` and keep each slice under about 9 minutes (`timeout 590`).
- **Paid renders** (voice, images) run with `run_in_background: true` and a log file, then are waited on. A request
  killed mid-flight can still be billed, and the rerun buys it again.
- Every stage caches its results, so a rerun after a crash never repeats finished work.

## Phase 0: Setup
1. Folder: `C:\Users\admin\Downloads\<NAME>`, or wherever the user says. Never temp or a scratchpad.
2. `git init` (the gitify hook may already have). Copy `assets/gitignore.template` to `.gitignore` before the first
   download.
3. Write `.env` with key names only (`ELEVENLABS_API_KEY=`, `GEMINI_API_KEY=`), and ask the user to paste the values.
   Never read, echo or copy another project's keys.
4. Write `CLAUDE.md` from `assets/CLAUDE.template.md`. Fill it as the phases settle each rule, with the evidence and
   date beside each.
5. Check the tools: `yt-dlp --version`, `ffmpeg -version`,
   `python -c "import PIL, numpy, faster_whisper"`, and Chrome at
   `C:/Program Files/Google/Chrome/Application/chrome.exe` for cards.
The toolkit is copied in Phase 2, once the teardown has settled the format and the visual approach. Copying the GEMS
tools before then hardcodes the wrong voice, thumbnail and format.

## Phase 7: Delivery and iteration
- Deliver to `upload/<Title>/` (`<Title>.mp4`, `thumbnail.jpg`, `upload info.txt`). `cmp` the video against the render.
  The user uploads it themselves.
- Report: one bold lead, then a few short sentences covering what was made, the runtime, the gates, what was spent
  against the quote, anything missing and why, and the one next step. No bullet rundowns.
- Every note the user gives becomes a dated rule in the project's CLAUDE.md, quoting their words, with the tool or gate
  that now enforces it. If the note is about every project, it also goes into `references/house-rules.md` in this
  skill (a local git repo; commit it), so other windows get it.
- Record what each finished episode taught in CLAUDE.md "Build lessons": what broke, the fix, and what prevents it now.
- Commit logical units with descriptive messages. Never push.
- Pitch the next topics from the measured topic gate, with the user's standing preferences first. Show hook options
  before voicing anything.
- **Once an upload has had a week of data, the channel's own numbers come in through `/winning-video-replicator`**
  (`~/.claude/skills/winning-video-replicator`): it pulls the owner's analytics, lays the retention curve on the build
  timeline, and walks every candidate rule past the user before anything is written into CLAUDE.md.

## Spending, quoted before every paid step
- **ElevenLabs** (Creator, eleven_v3): the rate drifts, so quote at the last measured one and re-measure with the
  subscription call before and after each render: ~0.55 credits per character in September, 0.44 on 2 Oct 2026,
  0.65 on 6 Oct 2026 (15,285 credits for 23,688 characters). A 13-minute episode of ~10,400 characters plus two
  extra hook takes is ~4,900-6,800 credits; a 28-minute one ~15,000. Check the balance covers it: a render that runs
  out stops between takes (HTTP 401 quota_exceeded) and keeps what it bought.
- **Gemini, measured on the bill (7 Oct 2026):** a GEMS-style Gemini build cost 6-13 USD, not the 1 USD we used to
  quote: `gemini-3.5-flash` bills 1.50 USD per 1M input and 9.00 USD per 1M output tokens with thinking counted as output,
  and with no `thinkingConfig` every call thought ~1,550 tokens (about 70 percent of the bill, even on yes/no frame
  checks). Read real spend at aistudio.google.com/spend before quoting, and count `thoughtsTokenCount` in any meter.
  **Since 7 Oct 2026 Claude picks footage by eye and Gemini never looks at images** (house rule 2): in GEMS the only
  Gemini cost is the thumbnail, one image on `gemini-3.1-flash-lite-image` at about 3.4 US cents. Anything else
  Claude can't do runs on `gemini-2.5-flash-lite` with thinking off (0.10 / 0.40 USD per 1M tokens). Generated-image
  channels ran about 1.75 USD an episode on the older image model.
- **Free:** downloads, scene detection, Whisper, ffmpeg, Commons, review sheets, by-eye pinning, voice-library previews.
- When a balance runs out (Gemini HTTP 402), say so, keep building what is free (by-eye pinning works for a whole
  episode), and list exactly what waits for the top-up.
