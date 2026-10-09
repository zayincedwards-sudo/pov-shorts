---
name: winning-video-replicator
description: Pull the owner's own YouTube analytics for any channel the user runs (Vault of Stones / GEMS, Astro Ranked, Otto Explained, Ancestral Stories, ANIME, Movie Theory, the Shorts and clipping channels such as Pull Up The Tape and SoftChaos), join impressions, click-through, views per day, average view duration and the audience-retention curve to each video's own build files (script, word timings, shot list, cards, recordings, takes, thumbnail), measure everything about thumbnail, title, topic, hook, script, narration, visuals and upload metadata against what got shown, clicked and watched, and put every candidate rule in front of the user to accept or skip, then write the accepted ones into that project's CLAUDE.md and the shared house rules with a code gate. Use it whenever the user asks what is working on a channel, why a video did or did not do well, to "learn from the analytics", "replicate the winners", "check retention", "pull the stats", "run the analytics", "what should the next video copy", or after an upload has had a week of data. It runs inside the project's own terminal window, reads YouTube only, spends nothing, and never changes a published video.
argument-hint: "[this project | @handle | channel id] [pull | studio | analyse | walk | replicate]"
---

<!-- Editors: never put a digit straight after a dollar sign in this file; the skill loader treats dollar-number as an
argument slot. Write "USD 5" or avoid money figures. -->

# Winning video replicator: learn from our own channel, then build to it

The teardown kit in `~/.claude/skills/channel-pipeline` measures OTHER people's channels from public data. It cannot
see why a video won. This skill measures OURS from the owner's data, which answers the three questions a view count
hides: was the video shown (impressions, traffic sources), was it clicked (impressions click-through), and was it
watched (average view duration, the retention curve)? The Astro thumbnail study of 1 Oct 2026 hit exactly that wall.

The one thing only we can do: our pipelines know what is on screen and what is being said at every second of every
episode. So the retention curve is laid on the build timeline and read per sentence, per shot kind, per card, per
recording and per section, pooled across every video of the channel. That is where the script, narration and visual
trends come from. Thumbnail, title and topic trends come from click-through and age-matched views per day.

**The user decides every rule** (6 Oct 2026: "put me in charge of committing everything... ask me for each rule... be
pretty lenient"). This skill proposes, with numbers; it never commits a rule on its own. Rules apply to future videos
only; nothing already published is re-cut, re-titled or re-thumbnailed by this skill.

**Status, 6 Oct 2026:** the kit in `scripts/` is built and passes its offline test (`scripts/tests/offline_test.py`,
21 checks: adapters on the real GEMS, Astro, Otto, Ancestral, ANIME and clipping builds, retention maths, charts,
analysis, report, rules, Studio import, dry-run pull). It has not yet been run against a live channel: the user asked
for the skill first. The first live run in any window is `init` → `auth` → `pull`, and the first report will say so.

Arguments: `$ARGUMENTS`

## Always, before anything else
1. Read `~/.claude/skills/channel-pipeline/references/house-rules.md`. The ones that bite here: everything lives in the
   project folder; user documents are plain Notepad `.txt`; never push; measure, do not guess; no review gates except
   spend and the user's own creative picks. This skill's rule walk is the user's explicit choice, not a gate.
2. **Read-only on YouTube.** The token carries `youtube.readonly` and `yt-analytics.readonly`, nothing wider. Never
   upload, edit a title, swap a thumbnail, start a Test & Compare, change privacy or delete. Propose; the user acts.
3. **Spends nothing.** The Data and Analytics APIs are free within quota and the analysis is local. Thumbnail traits
   are read from the specs and by eye; Gemini vision on thumbnails only if the user asks, quoted first (house rule 1).
4. **Which project, which channel.** The working folder has a `CLAUDE.md` and `tools/` or `lib/`: that project governs.
   `analytics/channel.json` names the channel and the adapter (`init` writes it; the table in
   `references/project-artifacts.md` has every known channel id). The account holds several channels and Studio
   defaults to SoftChaos: `whoami` must match `channel.json` before a single number is read.
5. Tell the user, in one line, which project, channel and data date you read and what happens next. Keep them posted
   in a few words during long stretches.

## The kit
`python ~/.claude/skills/winning-video-replicator/scripts/ytown.py <command> --project <folder>` (Bash tool, full paths,
`C:/` style for Python, never `cd`). Commands: `init`, `auth`, `whoami`, `pull` (`--dry-run` touches no network),
`studio`, `heatmap`, `cuts`, `map`, `join`, `retention --charts`, `analyse`, `report`, `rules`, `run`. The exact
sequence for a first run and a re-run, with flags, is `references/runbook.md`. What each API report gives and what only
Studio has is `references/analytics-api.md`. Which files each adapter reads is `references/project-artifacts.md`.

## What a run needs
| input | default (the user's answers of 6 Oct 2026) |
|---|---|
| channel | any channel the user owns, long-form or Shorts, including the clipping channels; one token per channel |
| content types | long-form and Shorts are measured and ranked separately, never pooled; a Short loops, so its view percentage can pass 100 |
| window | everything since the first upload; the API lags about 3 days; name the data date |
| minimum age | 7 days before a video counts for a rule; younger ones are reported as "early" |
| noise floor | 300 views before a retention curve counts |
| hit | views per day in the first 7 days at least 2x the median of the 3 uploads either side (cancels the channel's tide) |
| viewers | everyone; no age, gender, country, device or subscriber splits (the user: "don't worry about who the viewers are") |
| references | the public most-replayed heatmaps of the reference channels' winners are pulled for shape comparison (free) |

## Phase 1: pull (free, cached under `analytics/pull/<date>/`)
1. `init` once per project; `auth` once per channel (the user clicks through one Google consent and picks the channel
   in the chooser; the clipping publishers' OAuth client is reused, read-only scopes only).
2. `pull`: the catalogue (every upload with its uploaded file name, duration, live thumbnail, tags, description), per
   video the lifetime totals, the per-day series, the retention curve, the traffic sources with their details (search
   terms, the videos that suggested us) and the top comments; channel-wide views per day; the content-type split;
   and a once-per-run probe that records whether the API has started returning impressions.
3. **Studio-only numbers**: impressions, impressions click-through, key moments and Test & Compare results. Get them
   through the Claude in Chrome extension in the user's signed-in browser (switch Studio to the right channel, read
   the channel name on the page, Analytics → Advanced mode → Export), with the user watching the first time per
   channel; or the user drops the CSVs into `analytics/studio_exports/`. Then `studio <files>`. Say plainly which
   videos have no click-through figure.
4. `heatmap <reference urls>` for the reference winners still public.

## Phase 2: join (`map`, `join`, `retention --charts`)
- `map` ties each video to its episode folder: the publisher's own video id, else the uploaded file name against the
  delivered mp4, else the title, else a unique duration; a duration disagreement is written down. `analytics/videos.json`
  keeps hand fields that survive re-runs: `hook_type`, `voice`, `model`, `template`, `topic_class`, `title_history`,
  `thumb_history`, `notes`, `exclude`. **Fill them from CLAUDE.md the first time** (hook type per video, the voice and
  model, the thumbnail template), because the API has no title or thumbnail history.
- `join` builds the per-second timeline per video from the project's own files (sections, sentences, shots with their
  kinds, cards, price flashes, recordings, music, takes, narration bursts, tags). A pipeline that keeps no beat timeline
  gets a `--timeline` dump added to its assembler rather than a re-analysis of the mp4; `cuts` is the fallback.
- `retention --charts` lays the curve on the timeline: survival at 5, 10, 15, 20, 30, 60 s, midpoint, 90% and the end;
  dips (10-second windows losing at least twice the median window, at least 2 points) with the section, the sentence
  being spoken and the shots on screen; spikes (replays); and for every section kind, beat kind, span type, motion
  state and item boundary, the loss over that video's average body second, in points per minute. One chart per video
  under `analytics/retention/`, sections as bands, shot kinds as a strip, dips marked and the biggest three labelled.

## Phase 3: analyse (`analyse`)
Three scoreboards per video, never one blended score:
| question | metrics | mostly decided by |
|---|---|---|
| shown | impressions (Studio); views per day at day 7 and day 28; browse, suggested, search, Shorts-feed and external shares; day-1 share | topic, title, the tide |
| clicked | impressions click-through (Studio), compared only among videos with a similar reach and source mix | thumbnail and title |
| watched | survival at 30 s, average view duration and percentage, relative retention, dips by what was on screen | hook, script, narration, visuals |
| converted | subscribers, likes and comments per 1,000 views; shares | payoff, end line, CTA |

**Measured about every video (the user: "measure as much as possible"):** title (length, caps words, number, question,
charged words, "every", "explained", runtime in the title, first word, the emphasised word); publish weekday and hour,
days since the previous upload, upload number; description (length, links, hashtags, chapters, a stay-to-the-end
line), tags; the LIVE thumbnail's pixels (white, black and mid shares, brightness, contrast, saturation, colourfulness,
edge density, bits per pixel, dominant colours) plus the template and the hand-recorded swaps; the script (words,
gross and speech-only wpm, sentence length median, mean, p90, shares over 20 and under 6 words, questions,
contractions, numbers and money words per 100, second person, the its-not-X-its-Y count, pauses per minute, words in
the first 30 s, hook seconds, time to item one, items, words and seconds per item, CTA position, payoff, end line);
the visuals (beats, cuts per minute, shot median, p10 and p90, holds over 8 s, flashes under 1 s, cuts in the first 30 s,
share of each shot kind, moving share, text share, host share, cards per minute, recordings count, seconds, share and
median length, price flashes, sfx, music); the narration facts the build keeps (takes, chunks, bed level); comments
sorted into praise, request, correction, complaint, question; and everything in `videos.json`'s hand fields. Add any
attribute the user names; never drop one to make the list shorter.

**Method, honest about the n:** rank within the channel and within the content type; medians of hits against the
rest with the videos named; age-matched views per day, never lifetime totals across ages; the neighbour median for the
tide, and the suggested-traffic details to see which video carried which; **internal controls first** (the same shell
with one trait changed drove every strong rule so far); pooled retention by what was on screen (hundreds of shots of
evidence); Spearman rank correlations of every attribute against every outcome. Evidence tiers travel with every
candidate: CONFIRMED (an internal control, or at least 6 videos agreeing, or a retention effect in at least 3 videos
with the same sign), PLAUSIBLE (4 or more videos, or 2 with retention), HINT (less). Say what the data cannot show yet.

## Phase 4: the rule walk (the user decides everything)
1. `rules propose` records every candidate. Then curate before asking: merge candidates that say one thing (an
   attribute against several outcomes, a beat kind and its motion state), drop the ones that restate a standing rule
   unless the numbers contradict it, and group the rest by lever: topic, title, thumbnail, hook, script, narration,
   visuals, structure, metadata. Lenient means every tier is proposed, including HINTs; it does not mean 90 questions.
   Aim for the strongest 10 to 20 per run and list the rest in `ANALYTICS.md` under "not proposed this run".
2. Walk them with **AskUserQuestion, at most four per call, strongest first.** For each: header = the lever and a short
   label; question = the proposed rule in plain words, then its evidence in one sentence (metric, numbers, which videos,
   tier); options = Apply / Apply with changes / Skip / Ask again next run. Keep the user's wording verbatim when they
   change a rule. Wait for the answers before the next batch. Nothing else is asked outside these batches.
3. For every answer, `rules decide --id <id> --decision <apply|changes|skip|ask_again> [--wording "..."] [--edit "..."]
   [--videos "..."] [--house]`. An accepted rule lands in the project's CLAUDE.md under
   `## Rules learned from our own channel analytics` (date · videos · rule · why · edit); a skipped one under
   `## Reviewed and rejected` so it is not proposed again; `--house` also writes it into channel-pipeline's
   `house-rules.md` under "From our own analytics" for a rule the user says applies to every channel (commit that repo).
4. **Write the gate the same day** where one can be written: `script_check` thresholds, assembler gates, thumbnail
   gates, plan templates, `IDEAS.md` topic scores. Say exactly what changed. Never touch a narration pipeline the user
   has fenced off (Otto). Never re-cut, re-upload, re-title or re-thumbnail an existing video; a thumbnail-template
   change is proposed with Test & Compare candidates and made only after the user's yes.
5. A rule this skill wrote is re-tested on every later run (`rules retest`): holds, weakened or contradicted, with the
   new numbers. Flag anything weakened or contradicted in the report; the user decides what happens to it.

## Phase 5: write it up
- **`analytics/ANALYTICS.md`** (Claude-facing), in this order: data date and coverage; channel snapshot and tide; every
  video on the scoreboards; what separates the winners by scoreboard and tier; retention by what was on screen with the
  dips mapped to sentences and shots; thumbnail and title findings; traffic and comments; the reference heatmaps against
  our curves; the rules proposed with the user's decision on each; not proposed this run; tests to run; caveats;
  evidence index. `REPORT_TABLES.txt` and `ANALYTICS.tables.md` are generated for it.
- **`WHAT WORKS.txt`** at the project root for the user (house rule 5): write `analytics/findings.json` (lead, at most
  five findings as rule · numbers · videos · what to do, tests to run, what the data cannot tell us yet), then `report`.
  Plain words, no API names.
- Each run keeps its snapshot under `analytics/snapshots/` and the report says what moved since the last one.

## Phase 6, only when asked ("replicate", "build the next one to this")
Options, never a build (house rule 14b): topics scored by our own data (topic class against day-7 views per day, beside
the market gate in `IDEAS.md`); the hook shape with the best 30 s survival; the thumbnail traits with the best
click-through at a similar reach; the structure with the fewest dips. Three or four of each, with the numbers. The
project's own pipeline builds the pick; this skill builds nothing and spends nothing.

## Re-running
When an upload turns 7 days old, and about every two weeks; `run` does map → join → retention → analyse. A `/loop` or a
scheduled routine is possible; the user installs scheduled tasks themselves. Do not message the other project
windows about a cross-channel rule: house-rules.md carries it.

## Traps already paid for, and the new ones
- A token authorises exactly one channel and refreshing cannot widen its scopes; a new scope means a fresh consent.
  Two videos once went to the wrong channel undetected: `whoami` first, always.
- Studio defaults to SoftChaos. Switch accounts before any export and read the channel name on the page.
- Analytics data is complete about 3 days back; the newest days are partial. The first 48 hours are browse-driven and
  noisy; a hit lifts its siblings. Age-match and read the tide.
- `averageViewPercentage` is over engaged views and `estimatedMinutesWatched` over all views; never divide one by the
  other. `relativeRetentionPerformance` compares with YouTube videos of similar length, not with our uploads.
- Impressions and click-through are not in the API, and a video under YouTube's view threshold has no retention curve.
  Click-through falls as reach widens: compare it at a similar impression count or not at all.
- The live thumbnail and title can differ from what was delivered; the API keeps no history. Record swaps by hand in
  `videos.json` when the user makes them.
- The retention baseline is each video's own average body loss; a hook always loses faster than that and is reported
  through the survival figures, never as a "hook loses viewers" rule.
- Eight GEMS review rules once made a script "disjointed and awkward". A rule from this skill changes one measured
  thing and leaves the reference's shape alone.
- Windows Python needs `C:/` paths even from Git Bash; `sed -i` turns a CRLF `.txt` into LF (edit user text with Python).
