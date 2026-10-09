# Runbook: the commands, in order

`YT` below means `python ~/.claude/skills/winning-video-replicator/scripts/ytown.py`. Run in the Bash tool with full
paths (`C:/Users/admin/Downloads/GEMS`, never `/c/...` inside a Python argument). Each command prints what it wrote.

## First run in a project (one sitting, free)
1. **Setup**
   ```
   YT init --project C:/Users/admin/Downloads/GEMS --channel-id UCUjn4qZNKnp7xMFAIUJGw6Q --name "Vault of Stones" --handle @VaultofStones --adapter gems --content long --key gems
   YT auth --project C:/Users/admin/Downloads/GEMS
   ```
   `init` writes `analytics/channel.json`, the folders and the `.gitignore` lines (tokens, exports and other people's
   thumbnails stay out of git). `auth` opens the Google consent page in the user's browser once: they sign in, pick the
   channel in the chooser, and the command prints which channel the token points at. A mismatch with `channel.json`
   stops everything. `--manual` prints the URL instead of opening a browser.
2. **Pull** (Bash `timeout: 600000`; a channel of 12 videos is about 80 API calls)
   ```
   YT pull --project C:/Users/admin/Downloads/GEMS
   ```
   Snapshot under `analytics/pull/<today>/`; `analytics/latest.txt` names it. `errors.json` lists any report YouTube
   refused (say so in the report). `--dry-run` prints the plan without a token.
3. **Studio numbers** (impressions, click-through, key moments, Test & Compare)
   - Through Claude in Chrome: load the extension tools, open `studio.youtube.com`, switch to the channel (avatar →
     Switch account), READ THE CHANNEL NAME on the page, Analytics → Advanced mode → the Content table with
     Impressions, Impressions click-through rate, Views, Average view duration, Watch time, lifetime window → Export →
     CSV (a zip downloads). Move it into `analytics/studio_exports/<date>/`. For retention curves per video, the
     video's Engagement tab → Advanced mode → Export.
   - Or the user drops the files there.
   ```
   YT studio --project C:/Users/admin/Downloads/GEMS "C:/Users/admin/Downloads/GEMS/analytics/studio_exports/2026-10-07/Content lifetime.zip"
   YT studio --project ... --video <id> "<retention export>.csv"
   ```
4. **Reference heatmaps** (public winners of the reference channel, free)
   ```
   YT heatmap --project C:/Users/admin/Downloads/GEMS https://www.youtube.com/watch?v=<id> ...
   ```
5. **Map and join**
   ```
   YT map --project C:/Users/admin/Downloads/GEMS
   ```
   Read the output: unmapped videos, episodes without a video, duration disagreements. Fix a mapping by editing
   `analytics/videos.json` (`episode` = the folder path). Then fill the hand fields from CLAUDE.md for every video:
   `hook_type`, `voice`, `model`, `template`, `topic_class`, plus `title_history` / `thumb_history` entries for anything
   the user changed in Studio, and `"exclude": true` for a video that should not be compared (a test upload).
   ```
   YT join --project C:/Users/admin/Downloads/GEMS
   YT retention --project C:/Users/admin/Downloads/GEMS --charts
   ```
   Open two or three charts and read them: a dip on a card, a recording that holds, a boundary that loses.
6. **Analyse**
   ```
   YT analyse --project C:/Users/admin/Downloads/GEMS --min-age 7 --noise-floor 300 --hit-ratio 2.0
   ```
   Writes `analytics/analysis.json`, `candidates.json`, `REPORT_TABLES.txt`, `ANALYTICS.tables.md` and a snapshot.
   Read `REPORT_TABLES.txt` whole before writing a word.
7. **Walk the rules** (SKILL.md Phase 4): `YT rules propose`, curate, AskUserQuestion in batches of four, then one
   `YT rules decide ...` per answer, then the gates in code.
8. **Write** `analytics/ANALYTICS.md` by hand, then `analytics/findings.json` and `YT report --project ...` for
   `WHAT WORKS.txt`. Commit the project (the gitify hook also checkpoints).

## A re-run (after an upload turns 7 days old, or every two weeks)
```
YT pull --project <folder>              # fetches only new days and new videos
YT studio --project <folder> <new exports>
YT run --project <folder>               # map -> join -> retention --charts -> analyse
YT rules retest --project <folder>      # holds / weakened / contradicted, with the numbers
YT rules propose --project <folder>     # new candidates only
```
Then the walk for the new candidates and for anything weakened or contradicted, and the report's "what moved" section.

## Shorts and clipping channels
- `init ... --adapter clips --content shorts` for a publisher project (`publish/uploaded_manifest.json` carries the
  video ids, so `map` needs no catalogue match). Shorts are ranked among Shorts only. Their view percentage can pass
  100 (loops). The Shorts feed is a traffic source of its own (`traffic_shorts_feed_pct`).
- A clip's words come from a transcript JSON beside the clip (`<stem>.words.json`); its shots from
  `YT cuts <mp4> --video <id>`. Without either, the clip still has its scoreboard, title traits, publish time and
  thumbnail pixels.
- A channel with no pipeline at all: `--adapter generic`, and per video a folder `analytics/generic/<video id>/` with
  `transcript.json` (channel-pipeline's `teardown.py transcribe` on the delivered mp4), `cuts.json` and an optional
  hand-written `sections.json`.

## findings.json (what `report` formats)
```json
{"lead": "One paragraph: the single biggest thing the numbers say.",
 "findings": [{"rule": "Open on the sound, name the planet after.", "numbers": "30 s survival 71% vs 58% on the other six",
               "videos": "007, 003 against 001-006", "action": "accepted; script_check now warns when item one is named before its sound"}],
 "tests": ["Test & Compare the ring-round-every-circle thumbnail on 012"],
 "limits": ["No click-through for 001-004: Studio export covered 30 days only"]}
```

## Reading the retention tables
- `excess pts/min` is the loss over that video's own average body second, so a negative number means that thing held
  viewers better than the rest of its video. The hook is excluded from candidates (every hook loses faster); its figures
  are the survival columns.
- `agree` is the share of videos where the sign was the same. Three videos agreeing at a point a minute is CONFIRMED;
  two is PLAUSIBLE; one is a HINT. All three tiers are proposed; the tier travels with the rule.
- A dip's `beats` are the shots on screen in the three seconds around its steepest second; `sentence` is what was being
  said. Read the chart before believing a dip.
