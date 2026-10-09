# The user's other pipelines: what each decided, and what to borrow

Every project measured a winning reference before building, and none uses its own episodes as the template. When
working inside one of these, its CLAUDE.md governs (MOVIE THEORY has none: use ANALYSIS.md and PRODUCTION.md).

## The projects
| Project | Folder | Visuals | Voice | Thumbnail | Status |
|---|---|---|---|---|---|
| GEMS (Rio Rogan price ladders) | `Downloads\GEMS` | real footage + Commons, Python/ffmpeg | Brad, eleven_v3, stored settings, hook ×3 | ruby template + `thumb_like.py` | 5 episodes delivered |
| Astro / SPACE RANKED (white cards) | `Downloads\Astro` (Node) | sourced only, from the NASA library and Commons with a licence manifest; white card + picture box; real recordings spliced into the voice | Adam (pro clone) on eleven_v3, stored settings, 150-450-char paragraphs, hook ×3, DeepFilterNet + pause ducker (Astro only, user-asked) | white 4×2 grid, `lib/thumbgate.js`, user picks from 3 | running |
| Otto Explained (mascot) | `Downloads\Patrick\v2` (Python) | drawn in code: SVG → headless Chrome → PNG → x264; "hero" style hooks (`hero.py`, `hooklib.py`) | Liam, eleven_multilingual_v2 with continuity text | 5×3 flat icons on black, `tools/thumb_build.py` | 3 uploads got 2-7 views ("crowded subject"); a niche study followed |
| Ancestral Stories (stick figures) | `C:\Users\admin\zayin` (Node) | generated panels (flash-lite image, batch, style lock, 30-pose library) + SVG cards | Adam (Engaging, Friendly and Bright), eleven_v3 | never names the answer; 2-3 words ending "?"; `episodes\_engine\check_thumb_fit.js` | running |
| SAM (Sam O'Nella style) | `Downloads\SAM` (Node) | one accumulating canvas, a fixed generated host with SVG arms and mouth | undecided (auditions) | inverse of Ancestral: the thumbnail delivers the hook | scaffold only |
| MOVIE THEORY (Plot Anomaly) | `Downloads\MOVIE THEORY` | muted film clips the user supplies, in an inset over a loop | user picks from free previews | white plate, rembg cut-out, two lines of Anton | analysis only; blocked on films, voice, credits |
| CLIPPING / TALARICO (speed clips) | `Downloads\CLIPPING`, `Downloads\TALARICO` | real footage, face-tracked crops, ASS captions | none | — | automated publisher, owner-reviewed |
| Ollie (AI baby reels) | `Downloads\Ollie` | Veo 3.1 at ~$1.60 a reel | — | — | teardown + recipe |
| ANIME (Animize1 moments lists) | `Downloads\ANIME` (Python, GEMS base) | official anime clips (Crunchyroll / Toei YouTube uploads) played whole with their own audio; ~300 narrated words placed as bursts; Shorts = a lore question over fast cuts with one-word yellow captions (`tools/shorts/`) | Brad, eleven_v3 | one official frame, no text (`thumb_frame.py`) | episode 001 delivered 2 Oct 2026; Shorts format measured 3 Oct |

## Decisions every new channel settles (and what the user chose)
1. **Visual source.** Sourced (GEMS, Astro, Movie Theory, clips) is free but costs sourcing time and credits. Astro,
   4 Sep: "Pull from anywhere you can. Don't generate." Visibly real assets are that format's credibility.
   - Generated images (Ancestral) cost ~$1.75 an episode after batching.
   - Drawn in code (Otto) is $0, but frames come out empty without a fill gate.
   - Generated video (Ollie) is ~$1.60 a reel.
2. **Host:** none (GEMS, Astro), a reacting mascot in ≥ 30% of shots (Otto), a composed avatar (SAM), or stick figures
   (Ancestral).
3. **Voice choice:**
   - The user picks: Otto, SAM, Movie Theory. Never send samples unprompted.
   - An in-context A/B: Ancestral against real cuts; GEMS v3 vs v2.
   - Match the reference narrator from free previews: Astro (`lib/voiceprint.js`, `match_reference_voice.js`).
   Rendering a library voice adds it to the account. Premade voices expire 31 Dec 2026.
4. **Model:** v3 is expressive with audio tags, but fuzzes and refuses continuity text (Astro, GEMS, Ancestral).
   multilingual_v2 is cleaner and supports continuity (Otto).
5. **Chunking:** Astro measured 150-450-character paragraphs, one take each, as the cure for v3 fuzz. GEMS still renders
   the fewest takes up to 4,900 characters. A new channel should start with short paragraphs.
6. **Processing:** the narration is untouched everywhere since 17 Sep. Astro's denoise and ducking are the user's
   explicit exception. Otto's gap trims and LUFS and Ancestral's de-breathing predate the rule; don't copy them.
7. **Music:** none by default. Astro and Otto run without it. GEMS has the quiet jazz bed on every video again
   ("music on every video from now on", 2 Oct 2026, reversing the 30 Sep "remove music from all future videos";
   `assemble.py` now refuses a GEMS render without `bed.json`). Clips use a beat and a boom. Sfx are summed at unity.
   GEMS also ends every video on "If you made it this far, be sure to like and subscribe for more. And let me know
   your favorite type of <material> in the comments." (the user's wording of 5 Oct 2026, replacing the 2 Oct lines),
   in its own `## END` section voiced as its own short take, so the wording can change cheaply and the line can be
   added to a delivered episode by buying one ~127-character take.
8. **Runtime:** "runtime follows the voice" by default. Explicit gates where the user set them: Astro and GEMS 11-15
   min, Ancestral 7-10. Re-measure wpm per voice, model and settings, and reach a target by adding paragraphs.
9. **Hook:**
   - Astro: title + tease + transition, picked from 3-4 options.
   - Otto: "From X, to Y, to Z, here's every type of … explained in N minutes".
   - GEMS: one type, then "one of N types".
   It is always shown to the user before voicing.
10. **Thumbnail:** a template taken from the niche's winners, gated at 210 px. The user picks from 3 options at the
    start, then the template holds.
11. **Cut rate:** measured per reference. About 6-8/min (Astro), 18-20 (Otto, GEMS, Ancestral), 6.25 s holds (SAM).
12. **Topic and niche:** offer topics as a choice first (Astro, 13 Sep: "Make a new video starts with a CHOICE"). Keep
    `IDEAS.md`; "Ideas they do not pick are not dead." Measure how crowded a subject is before committing: Otto's craft
    could not save a crowded subject.

## Borrow these
- **Voice engine, Astro `lib\vo.js`:**
  - stored settings
  - takes keyed by model, text and settings; fuzzy takes re-rolled
  - `HOOK_TAKES`, `VO_DRY=1` dry run with cost, `VO_BUY=missing`
  - refuses to buy a chunk whose letters differ from its paragraph
- **Audio and voice checks:**
  - `Astro\lib\audiocheck.js`: post-mux check of speech residual, pause level and true peak.
  - `Astro\lib\align_local.py`: free word timings from takes already on disk.
  - `Astro\lib\metrics.js` (`wordBudget()`) and `lib\dryrun.js`: runtime gate before buying.
- **Thumbnail gates:** `Astro\lib\thumbgate.js` (210 px: caption cap height, contrast, distinctness),
  `Patrick\v2\tools\thumb_build.py --measure`, `GEMS\tools\thumb_like.py`.
- **Sourcing with a licence manifest:** `Astro\assets.js`, `asset_sheet.js`, `lib\clip.js` (clip windows without
  slates). Commons range reads 429, so archive.org mirrors help. Never run asset downloads in parallel.
- **Drawn animation:** `Patrick\v2\tools\hero.py`, `herolib.py`, `hooklib.py`, `scenes.py`, `host.py`, `prerender.py`
  (frame-exact to the voice). Also `shorts.py` (9:16 trailers) and `sfx.py` (synthesised whoosh, tick and pop).
- **Upload and branding:**
  - `Patrick\v2\tools\upload_docs.py`, `brand.py` (avatar 800 px, banner with safe-area preview, watermark).
    ⚠ These hardcode Otto's output folder (`OUT = "C:/Users/admin/Downloads/otto"`). Change it to the new project
    folder before running.
  - `Astro\brand\build_upload.js` (chapters from `words.json`, credits, a stay-to-the-end line).
  - `zayin\brand\`.
  - `CLIPPING\BRANDING\make_branding.py`.
- **Generated images:** `zayin\episodes\_engine\ep_assets_batch.js` (batch and style lock) and
  `zayin\library\build_library.js` (pose library).
- **Script lint:** `zayin\lint_speakable.js` (PILE-UP / TWO CLOCKS / BREATHLESS), plus `audit_text.js` and
  `timing_probe.js`.
- **Niche scans:** `Patrick\v2\niches\tools\` (`yt_search.py`, `lane.py`, `score.py`) and `COMPILATIONS\tools\`.
- **Publishing:** `CLIPPING\publish\`.
  - Drop a file at the root to queue it; posting runs at a randomised cadence with quiet hours, deduped per page.
  - It refuses to post from the wrong signed-in account.
  - Uploads go through the YouTube Data API, and Playwright for TikTok and Instagram.
  - The owner installs the scheduled task themselves (`scheduler\install_task.ps1`). Prove it live after any fix.
- **Clip gates:** `CLIPPING\shorts\deliver.py` (true peak, 10-60 s, music stops at the boom) and
  `TALARICO\shorts\verify_words.py` (re-transcribes every finished clip).
- **A NEW clipping project** (reference channel + source material + rules document) is not this skill's job: use the
  `clipping-pipeline` agent (`~/.claude/agents/clipping-pipeline.md`, or `claude --agent clipping-pipeline`). Its
  playbook, the owner's clipping rules, the traps and the bootstrap script live in `~/.claude/clipping-kit/`
  (3 Oct 2026). A rule the owner gives for every clipping project goes into that kit's `OWNER_RULES.md`.
- **Instagram scrape:** `Ollie\reference\download_reels.py`, `fetch_info.py` (GraphQL intercept in the logged-in
  Chrome tab).
- **Picking a niche before a teardown:** `COMPILATIONS\tools\yt_search.py` (YouTube search with the filter blob built
  in code, cached per call, date-window check on every row), `relevance.py` (title filters with a `--check` mode that
  lists what each rule drops), `yt_channels.py` (subscribers and recent uploads of the winners) and `score.py` (a
  niche score weighted by the share of winners from channels under 100K subscribers). Findings in
  `COMPILATIONS\REPORT.txt` (2 Oct 2026): for a new no-narration channel, rain and sleep sounds, cozy rooms, study
  sessions and sleep music, where 60-80% of winners are small channels.

## Rules learned in these projects that apply anywhere
- **Asked for one fix, make one fix** (Astro, 18 Sep: "just pick better pictures DONT CHANGE ANYTHING ELSE"). Attach no
  extras to a requested change.
- **Cost before and after** (Astro rule 41). State the cost before a purchase, and after it report the characters bought,
  mistakes included. Try the free route first and say that it exists.
- **Stay to the end** (Astro rule 45). The description and the pinned comment tell the viewer to stay to the end, and
  why.
- **Upload kit** (Otto, 24 Sep):
  - the hook line opens the description
  - a pinned question in the host's voice
  - end screens and a series playlist
  - one video every ~5 days, with a Short the day after
- **Never kill chrome.exe globally.** It is the user's browser too.
- **YouTube Studio may be on the wrong channel.** The account holds several channels and Studio defaults to one of
  them; switch first.
- **A YouTube delete is permanent.** Set a video private and let the owner delete it (29 Sep).
- **The owner enables scheduled tasks themselves.** During sign-ins, raise decisions in the reply, not in popups.
- **Never invent a citation in a description.** Simplifying narration is editorial; fabricating a source is not.
- **Shell patches eat backslashes.** Edit files with the Edit tool.
