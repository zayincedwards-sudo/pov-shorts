# Phase 1: Teardown and measurement

A teardown takes one sitting of about 20-40 minutes and spends nothing: yt-dlp, local Whisper, ffmpeg, numpy and
Pillow. When the user asks for a fresh pass ("ignore all previous work"), re-measure everything. Old notes have been
wrong before; a fresh teardown corrected a "measured" sky colour and a claim that labels read at feed size.

**Starting inputs.** Usually the user drops 2-3 of the reference's winning videos (YTDown mp4s) and 2-3 channel
screenshots into a new folder, and that folder becomes the project root. With only a URL, the kit below fetches the
hits itself.
- **Shorts or reels as the reference:** the GEMS long-form 1920×1080 toolkit is the wrong base. For 9:16 work, see
  `CLIPPING\shorts\` and `TALARICO\shorts\` (vertical cuts, captions, gates), Otto's `shorts.py`, and `Ollie\` for
  reels (Instagram is scraped by GraphQL intercept: `references/other-channels.md`).

## The kit: `~/.claude/skills/channel-pipeline/scripts/teardown.py` (tested 1 Oct 2026 on @RioRogan)
- Run it from the project root in the Bash tool. Shell variables don't survive between Bash calls, so write the full
  path every time: `python ~/.claude/skills/channel-pipeline/scripts/teardown.py <command> …` (written `teardown.py`
  below).
- Everything lands under `analysis/`; `--out` changes that.
- For long videos (transcribe, cuts), give the Bash call `timeout: 600000`.
1. `teardown.py scrape @Handle [--limit 40] [--shorts] [--comments 5]`. A full URL works too.
   - Lists EVERY upload, with approximate dates, in `analysis/channel_flat.json`. Metadata goes through Python in
     UTF-8, never a shell redirect.
   - Fetches `analysis/yt/<id>.info.json` (chapters, tags, likes, `heatmap`) and a thumbnail
     (`analysis/thumbs/<views>_<id>.jpg`) for `--limit` videos: **half from the top by views and half from the bottom**,
     so flops are always in the sample.
   - Ids that failed go to `analysis/missing_ids.txt`. Rerun to fill them; channel fetches can silently stop part-way.
   - `--comments K` adds the top comments of the K most-viewed videos.
2. `teardown.py table` writes `analysis/channel_table.json` and `.csv` over every upload: views, views/day, outlier
   ratio, like %, duration, chapters and title traits.
   - Long-form and Shorts each get their own median.
   - It prints each group's top 15 and bottom 8, and the top-1 and top-3 share of views.
3. `teardown.py thumbs` writes thumbnail stats (white, black and mid-tone %, saturation, dominant hex colours) and
   sheets ranked by views at 480 px and at **210 px, the feed size**. Read both sheets by eye.
4. `teardown.py download <id> [--low]` fetches the hits whole, and the flops at 360p with `--low`. Ids starting with "-"
   are safe (the kit passes watch URLs).
5. `teardown.py transcribe analysis/yt/<id>.mp4 …` runs faster-whisper `small.en` on CPU int8, cached model first.
   - Writes word timings to `analysis/transcripts/<id>.json` and timestamped lines to `.txt`.
   - A 6-minute video takes about 90 s. Check every transcript for holes.
6. `teardown.py script analysis/transcripts/<id>.json … [episodes/<ep>/script.md]` prints a side-by-side table of the
   metrics below: words, wpm (gross and speech-only), sentence lengths, contractions, numbers, years cited, openers,
   pauses and so on. Contractions count only real ones (n't, 're, it's, that's…); possessives and curly apostrophes are
   handled. Use the same command on our drafts later, beside the reference.
7. `teardown.py cuts analysis/yt/<id>.mp4` measures cuts and writes contact sheets.
   - Gives hard (scene > 0.25) and soft (> 0.10) cuts per minute, median, p10 and p90 shot length, holds over 8 s,
     flashes under 1 s and cuts in the first 30 s.
   - Writes `analysis/cuts/<id>_cuts.json` (ours, tracked) and labelled contact sheets at one frame per 2 s
     (`analysis/frames/`). Read every sheet.
   - Takes about a minute per 10 minutes of 1080p.
   - An inset or an accumulating canvas needs a different instrument (see Traps).
8. `teardown.py subs --top 10` fetches auto-captions (json3) for pace and openers across many videos.
   - The endpoint 429s easily. The kit stops and says so; then use `transcribe` on downloads instead.
   - Auto-captions are unpunctuated, so sentence statistics always come from Whisper.
The kit's measurements of the GEMS reference pearl video:
- 1,042 words in 5.9 min, 178 wpm gross
- median sentence 18 words, 2.5 contractions per 100 words, 0 years cited
- 19.6 cuts/min, median shot 2.5 s

Our diamond script, measured the same way, cites 28 years. It is worth checking against the payload-first rule on the
next script.

## Deeper instruments in the user's projects (copy and adapt; never run them in place)
These tools expect their own project's folders, some hardcode dates, a topic or a narrator, and several WRITE into
their home project when run there. Patrick's `shots.py` overwrites `Patrick\v2\ref\shots.json`, and
`match_reference_voice.js` writes `episodes\_audio_check\` into whatever folder it runs from. Copy the tool into the new
project, fix its paths and constants, then run it.
- **Script register and delivery:** `Patrick\v2\tools\register.py` and `delivery.py`. Delivery covers F0, pace
  variation and sentence-tail pitch. `zayin\reference\analyze_reference.js` and `zayin\lint_speakable.js`.
- **Shots:** `Patrick\v2\tools\shots.py` (hard, soft and static thresholds). For white-card or canvas formats:
  `Astro\reference\cutrate.js`, `motion.js`, `fill.js` and `text_load.js`.
  - **Anime or any clip-compilation format:** `teardown.py cuts` is useless (speed lines and impact flashes read as
    167-323 cuts a minute). `ANIME\analysis\tools\clipmap.py` debounces cuts to ≥ 0.6 s, reads the creator's own
    edits from an on-screen source tag, and maps the narration bursts (words, share of runtime, first narrated
    second, silent stretches) from a Whisper transcript. Its tag detector is tuned to one overlay's geometry.
  - **One-take zoom or any continuous-camera animation:** `teardown.py cuts` reads almost nothing (0.7 cuts a minute
    on BlenderTimer's 15.7M size comparison). Three tools in `BLENDERTIMER\tools\` take paths as arguments and write
    under `analysis/`:
    - `motion.py` profiles camera moves against holds: moves a minute, hold lengths, share of the runtime still.
    - `itemmap.py` splits a list narration on its repeated opener ("This is ...") and maps the most-replayed
      heatmap onto each item. Number the opener's occurrences first and pass the non-items to `--skip`.
    - `audiobed.py` tests for a music bed by comparing the level in the pauses with the voice, and reads the
      narrator's pitch.
  - **Looped ambience (rain rooms, fireplaces, any hours-long scene with no narration):** `teardown.py cuts` and
    `transcribe` have nothing to read, and three hours of 1080p is not worth fetching. The tools in
    `COZY\analysis\tools\` take paths as arguments and write under `analysis/`:
    - `fetch_parts.py` fetches the first minutes at 480p or 1080p, the whole audio track and a 144p copy.
    - `picture_loop.py` finds the exact loop length, visible joins and the share of the frame that moves;
      `loop_checks.py` checks the loop holds to the end and which part repeats at which length; `cycle.py` reads a
      short cycle inside the loop (a fire, an animal).
    - `audio_loop.py` finds the sound-bed length and proves it on the waveform, with LUFS and fades;
      `audio_match.py` tests whether one recording is reused across videos; `audio_dyn.py` counts loud seconds an
      hour (steadiness). On Cozy Autumn Window the hit was a 120.12 s picture loop over a 10 min 46 s sound bed.
    - **A whole channel in one sitting** (`COZY\cabin\analysis\tools\`, 6 Oct 2026, @Cozycabinrainambient, 192
      uploads): `eras.py` reads the era lines from `analysis/eras.json`; `fetch_sample.py` picks the top and bottom
      of every era and fetches only openings, in ranged chunks (gotchas); `measure_sample.py` runs the instruments
      above in parallel; `lightning.py` counts window flashes (strikes per hour, height, the flash train's repeat)
      and thunder peaks, and whether the two are tied; `table_md.py` prints the tables for `ANALYSIS.md`. On Cozy
      Cabin the hit was a 7.30 s whole-frame loop with a lightning burst in every loop, over a 5 min 8 s bed with
      thunder, and audible thunder sorted hits from flops for three months. Steadiness is not a rule for every rain
      format.
- **Thumbnail gates at feed size:** `Patrick\v2\tools\thumb_build.py --measure`, `Astro\lib\thumbgate.js`,
  `GEMS\tools\thumb_like.py`. Astro also rebuilt the reference thumbnail to within 3.3% pixel difference to prove its
  renderer.
- **Audio:** loudness via `ffmpeg -af ebur128=peak=true`; bed level as RMS in word gaps against speech RMS.
  - To match the reference narrator against library previews (free): `Astro\lib\voiceprint.js` and
    `match_reference_voice.js`. Before running it, replace its hardcoded Astro narrator reference (127 Hz / 442 / −14.2)
    and its male/American filters with the measurements of the new reference. It reads `.env` from the current folder,
    so run it in the new project with that project's keys.
  - A Gemini listening rubric (`GEMS\tools\listen.py`) is a spend, so ask first.
- **Market or niche scan:** `COMPILATIONS\tools\yt_search.py` → `yt_channels.py` → `score.py`, reused in
  `Patrick\v2\niches\`. A web-research subagent can supply RPM, policy and dated hooks.
  - **Seasonal or timing questions** ("is it too late for X", "which season"): `COZY\analysis\tools\season_*.py`
    measures several themes against each other: searches with exact counts split by title into ambience / music /
    franchise / other, a velocity read against an earlier search cache (pace ratio = gain per day now over lifetime
    views per day), channel sizes behind the winners, the upload month of each winner channel's best videos, and the
    month-by-month dates of the newest comments on last season's top videos as the viewing curve
    (`comment_dates.py`). Use last season's winners for the curve; years-old videos have too few comments.
- **Worked teardowns to read for structure:**
  - `GEMS\ANALYSIS.md`
  - `Patrick\v2\ANALYSIS.md`, the most complete
  - `MOVIE THEORY\ANALYSIS.md`
  - `Astro\reference\astro_analysis.md`
  - `zayin\reference\analysis.md`
  - `Ollie\TEARDOWN.md`
  - `BLENDERTIMER\ANALYSIS.md`, a single-video deep dive with the replay heatmap mapped to the script
  - `COZY\ANALYSIS.md`, a no-narration ambience channel: picture and sound loops, every upload compared inside its
    own era, the creator's process read from their behind-the-scenes video
  - `COZY\cabin\ANALYSIS.md`, the same kind of channel at 192 uploads: five eras, a measured sample of each era's
    top and bottom, title traits by era, lightning and thunder

## What to measure (pick what the format needs)
- **Channel:** subs, total views, cadence, views per video, outlier ratio, top-N share of views, subs per 100 views,
  like %, upload resolution.
- **Title:** the exact formula and the emphasised word; runtime in the title or not; hedges; questions vs statements;
  ellipses; series suffixes.
- **Topic:** nameability. A stranger can name a handful of items, with ≥ 3 known and ≥ 5 unknown. The category is one
  people think has a single form. Plus record value, for price-ladder formats.
- **Script:**
  - words and wpm (speech-only vs gross)
  - sentence length median, mean and p90, and the share of sentences ≥ 20 words and ≤ 5 words
  - questions, and use of you/your and I/we
  - contractions and uncontracted phrases per 100 words
  - numbers per 100 words (digits vs words), money words
  - openers; named people and cited years
  - seconds before item one; items, words and seconds per item; the item beat template; bridges
  - CTA position and form; hook type; payoff and bookend
  - AI tells ("not X but Y", tricolons, colon reveals, stock words)
  - sentence classes (picture / fact / abstract / framing)
- **Video:**
  - hard and soft cuts per minute; median, p10 and p90 shot length; holds over 8 s; flashes under 1 s
  - cuts in the first 30 s
  - static vs moving share, Ken Burns share
  - luminance and near-black share
  - text load (header, picture, caption)
  - shot vocabulary, card types, host share, assets per chapter
  - colours as hex; fonts matched by rendering candidates
- **Audio:**
  - LUFS, LRA, peak; bed dB under the voice
  - F0 median and p10-p90, semitone range
  - pauses per minute, median gap, voiced %, sentence-tail pitch, pace standard deviation
  - share of real recordings
- **Thumbnail:**
  - pure white, black and mid-tone %; dominant colours, saturation
  - grid size, icon fill, distinctness at 210 px
  - label size at feed size (27 px at 1280 is 4.4 px at 210)
  - object heights and centres, ground line, light map, glow position, table edge
- **Retention:** heatmap top and bottom segments (in the info JSON) mapped to transcript lines.

## Hits vs flops
- Rank every upload and label it by thumbnail type, format and topic class. Compare medians by attribute.
- Look for **internal controls**: the same creator and shell with one variable changed. These drove the strongest
  rules:
  - **Astro:** an identical grid on black got 75K, on white 907K (11×), so thumbnails are white. A sequel labelled
    objects instead of sounds (19K vs 808K), so every label must be an instance of the title's noun. The winners show 8
    of 10 items: write ten, ship eight. Hedged titles are banned.
  - **Patrick:** nameability sorted all 16 videos, so there is a Stage-0 topic gate. The only flat-icon thumbnail won,
    so the gate is black ≥ 75%, mid-tone ≤ 15%, ≤ 8 colours. A 57-second intro with AI art lost, so no intro and no
    chrome.
  - **GEMS:** the price-ladder thumbnail beat the grid 3-20× per day. AI-cartoon thumbnails flopped, so footage is
    real. Equal-height stones lost, so object heights escalate ≥ 1.5×. Scripts were alike across hits and flops, so
    the script is necessary but not what separates them.
  - **SPACE 1:** the non-grid thumbnails were the bottom three, so never leave the grid. A category re-run lost 90%, so
    no re-runs within about 3 months.
  - **Axen (zayin):** a thumbnail naming the answer (CAFFEINE) got 8.9K against 1.1M for "SURVIVED HOW?", so never name
    the answer.
- Write the gates only the winners pass, and a defect list for each failed variant. State the caveats: n = 1, public
  data only (no CTR), survivorship in search results, noisy outlier ratios on tiny channels.

## Documents
- **`ANALYSIS.md`** (Claude-facing), in this order:
  1. channel snapshot
  2. every video classified
  3. what separates the winners (gates, retention)
  4. title formula
  5. the video measured: side-by-side table, shot vocabulary, script structure with timestamps, item template,
     register
  6. losers' pitfalls
  7. audience comments
  8. the creator's process reverse-engineered
  9. build rules distilled
  10. caveats
  11. evidence index
- **`PRODUCTION.md`** (Claude-facing): the recipe with staged gates.
- **For the user, plain `.txt` only** (house rule 5):
  - the brief, if they want one (e.g. `MOVIE THEORY\BRIEF.txt`);
  - a "What I need from you" list (accounts, keys, films, voice pick) in `NEEDS.txt`.
- **Promotion:** the build rules become CLAUDE.md "Standing rules". Each one is a bold rule, then the measurement behind
  it, then the gate that enforces it, with the date.
- **Later reviews:** when the user runs a review (their slash commands such as `/review-gems`, or the
  `REVIEW_PROMPT.md` files in Patrick\v2 and Astro), re-measure our episode beside the references with the same tools.
  - Walk the suggestions through AskUserQuestion: Apply / Apply with changes / Skip. That is the user's chosen review
    format, never a gate on a build.
  - Accepted ones become rules plus a code gate. Rejected ones go to "Reviewed and rejected" so they are never proposed
    again.

## Traps
- **Rate limits:**
  - Searches 403 after ~650 at 5 workers; use 1-3 workers with pauses.
  - Subtitles 429 after ~30 requests (sometimes at once). Info first, subs later, with sleeps.
  - Downloads hit a sign-in wall after ~30. Cookies are the user's call.
- **Instruments disagree.** Plan-side beats per minute are not comparable to frame-differenced cuts per minute.
  Whole-frame detection read 4.6 cuts/min where the inset crop read 20.9. Scene detection undercounts accumulating
  canvases. Gates do not carry across formats: Astro's fill check fails its own 808K video, and SAM inverts zayin's
  thumbnail rule.
- **Over-fitting register metrics backfires.** Eight GEMS review rules made a script "disjointed and awkward"; the user
  judges flow by ear. Copy the reference's shape, and change only where it measurably loses.
- **Offer topics and hooks, never choose them for the user.**
- Label sheets with PIL. ffmpeg `drawtext` segfaults without fontconfig.
