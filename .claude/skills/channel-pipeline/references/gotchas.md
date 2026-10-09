# Gotchas: traps already paid for once

## Windows and shells
- **Run pipeline commands in the Bash tool (Git Bash), not PowerShell.** Every command in these guides is bash.
  - In PowerShell 5.1, `timeout` is Windows' pause program, `&&` does not exist, and `>` writes UTF-16 with a BOM, which
    breaks the tools' `json.load(…, encoding='utf-8')`.
  - Git Bash converts `/c/Users/...` arguments and environment variables into `C:/Users/...` for Windows programs, but
    NOT paths written inside a `python -c "…"` string. Write `C:/Users/...` there.
- Run Python with `PYTHONUTF8=1`, and open files with `encoding='utf-8'`. Emoji and CJK in titles crash cp1252 printing.
  A bash `yt-dlp --print > file` writes the console codepage, so metadata comes out empty or mangled.
- Video ids can start with "-". Quote them, and never pass "--" before them to tools that parse `vid#n`.
- `l` and `I` look alike in ids. Use monospace sheets (review.py does), and delete the stray empty
  `cache/yt/<id>.scenes.json` that a typo leaves.
- Heredocs with nested quotes break Python one-liners. Write the script to a file with the Write tool and run that.
- Paths with spaces (`Downloads\MOVIE THEORY`) must be quoted everywhere.
- A `.txt` list written on Windows has CRLF. Strip `\r` before feeding ids to a loop (`tr -d '\r'`); every download in a
  batch once failed on it.

## Long jobs
- Keep foreground commands under 10 minutes (`timeout 590`). Long work runs as resumable slices or background jobs with
  a log file. A watchdog has killed background jobs in some setups, so every stage must survive being killed and rerun:
  cached downloads, captions, matches, voice takes and segments.
- Wait on a background job with an until-loop on its finishing line, and match failure lines as well
  (`Traceback|Error|FAIL`).
- Use `python -u` when piping; buffered output is lost on a timeout.
- Run one heavy ffmpeg job at a time (`-threads 2` in assemble). Killed runs leave truncated segments; assemble
  re-probes them.

## Paid APIs
- The credit guard reads model ids even in comments, and follows imports (review → assemble, pincheck → shots_build,
  vo_qa → listen).
  - Read-only commands (`cp`, `sed`, `cat`, `git`, `ffmpeg`…) pass unscanned.
  - A shell loop that merely names a voice script is scanned. Check whether a file exists with Glob instead.
  - See house-rules.md rule 1.
- Gemini prepaid balance at zero returns HTTP 402. It is not charged and does not fix itself; the user tops up at
  ai.studio/projects. Never cache the failure as an empty result.
- Check `/v1beta/models` before naming a Gemini model. `gemini-3.1-flash` does not exist. Since 7 Oct 2026 every project
  uses the cheapest model for the job (house rule 2): `gemini-2.5-flash-lite` with thinking off for text, images and
  audio, `gemini-3.1-flash-lite-image` for thumbnails.
- eleven_v3 has a ~5,000-character request cap and refuses previous/next text.

## YouTube downloads (ANIME, 2 Oct 2026)
- **"The page needs to be reloaded" on every video, searches still fine:** yt-dlp has no JavaScript challenge solver.
  Verbose shows `JS runtimes: none` and "Signature solving failed / n challenge solving failed". Fix:
  `python -m pip install -U "yt-dlp[default]"` (installs `yt-dlp-ejs`) and run with `--js-runtimes node` (Node 24 is
  on the machine; Deno is not and is the default). `ANIME\tools\clips.py` does both.
- **"Sign in to confirm you're not a bot":** needs the user's cookies. `--cookies-from-browser chrome` fails on this
  Windows with "Failed to decrypt with DPAPI" (Chrome's app-bound encryption, yt-dlp issue 10927). The user exports
  youtube.com cookies with the "Get cookies.txt LOCALLY" extension from the Chrome profile they choose (they picked the
  zayinkoolbob account, Chrome "Profile 2") and the tool passes `--cookies cookies.txt`. Which Chrome profile holds
  which account is in `%LOCALAPPDATA%\Google\Chrome\User Data\Local State` (`profile.info_cache`, `user_name`).
  Keep every `*cookies*.txt` out of git. If exported cookies stop working, YouTube rotated them: re-export from a tab
  with no YouTube page open (yt-dlp wiki, "Exporting YouTube cookies").
- A GEMS-derived fetch tool that carries a Gemini ranker (footage.py) is stopped by the credit guard even for a free
  download; the ANIME copy `clips.py` has no model id and runs freely.
- **HTTP 403 on a media fetch part-way through a batch is usually momentary** (COZY, 5 Oct 2026: 5 of about 45
  fetches, with no cookies). Rerun the failed ones once before anything else; four of the five went straight through.
  A whole audio track comes down in 20 to 40 s; `--download-sections` goes through ffmpeg at about twice real time.
  Never read a section file while it is still being written: the mp4 has no index until it closes.
- **The bot wall hits yt-dlp's watch-page request first** (COZY, 7 Oct 2026, after ~60 media fetches plus searches):
  "Sign in to confirm you're not a bot" on every `--print`, download or `--write-comments`, while flat searches, channel
  pages and the plain watch-page HTML kept answering. `COZY\analysis\tools\comment_dates.py` reads comment dates
  through the page's own comments API (continuation token from `ytInitialData`, POST to `/youtubei/v1/next`, "Newest
  first" token from the sort menu) and worked throughout. Cookies remain the user's call.
- **A signed-out watch page cannot show mid-roll ad breaks** (COZY, 5 Oct 2026). `adPlacements` in the page's player
  response lists one pre-roll placement for every video, three-hour podcasts included, so a "No Ads" title cannot be
  checked that way. Run a control on other channels before trusting any such read; report the claim as unverified.
- **Fetch only what the instruments need, in ranged chunks** (COZY cabin, 6 Oct 2026). `yt-dlp -j -f <format>` only
  resolves the stream; the bytes then come down in 4 MB `Range` requests carrying the format's `http_headers`. About
  17 MB/s, against 0.2 MB/s for a whole-file fetch and 0.04 MB/s for `--download-sections` that day. A WebM cut short
  decodes cleanly up to the cut ("File ended prematurely" is harmless). Tool:
  `COZY\cabin\analysis\tools\fetch_sample.py`.
- **Never measure loudness on a "-drc" format.** Format ids ending in "-drc" are YouTube's stable-volume tracks,
  dynamically compressed, and they flatten the swings being measured. Select `ba[acodec^=opus][format_id!*=drc]`.
- **The bot wall comes signed-out too, after a day's volume** (COZY cabin, 6 Oct 2026). About 260 yt-dlp requests
  (192 info fetches, then about 70 stream look-ups at three workers) and every request got "Sign in to confirm
  you're not a bot". Fetch info first, then only the streams that decide something; cookies are the user's call.
- **yt-dlp writes the cookie jar back into the `--cookies` file after every call** (COZY cabin, 6 Oct 2026). Run
  look-ups that share one cookie file one at a time (`COZY\cabin\analysis\tools\sweep.py` does, with a pause), or
  give each worker its own copy.
- **"Export All Cookies" from a normal Chrome window exports every site's logins** (892 cookies across 149 sites on
  6 Oct 2026). Ask for the export from a fresh Incognito window, and remind the user to delete the file when the run
  is done. Asking YouTube which account a cookie file belongs to is blocked by the auto-mode classifier as credential
  exploration; ask the user instead.

## Video
- Frame-grid sync: snap every shot to 1/30 s and render exact frame counts, or picture drifts behind the voice (1.6 s
  by the end of one master). Ruby and opal were delivered with drift; a free re-render fixes them, and that is the
  user's call.
- Blackdetect trips on small objects on black studio backgrounds as well as on fades. Pin a lighter scene or start
  later.
- A scene can cut or dissolve to something else mid-way (a presenter, an armoury). Peek three frames, and check the
  exact slice the shot uses.
- Captions describe one frame, never the whole scene.
- A re-pick after a timing change can land on a dark or wrong scene. Pin the beat back to the reviewed scene.
- `bars.py` reports dark edges in dark scenes as bars, and a pillarboxed portrait photo as a strip. Look before writing
  crops.
- **Gemini's picks need an eye pass for named things** (GEMS diamond, 3 Oct 2026: ~60 of 305 shots fixed). Captions
  say "a yellow diamond", so a famous stone gets a look-alike: a white diamond under the black Enigma, Christie's Red
  Cross Diamond under the Tiffany lines, a Sotheby's ring under a Christie's sale. Check every named object against
  its own source film; the rest were presenters, chyrons and title cards near scene ends.
- **Pins reserve their scenes for the whole script.** Pinning a scene that the matcher had chosen for another beat
  moves that other beat onto new, unreviewed footage. Snapshot `shots.json` before pinning, diff after every re-pick,
  and pin any beat that moved back to its earlier choice.
- **Review sheets show only each shot's first and last frame.** Burned-in text that appears mid-shot ships unseen (a
  "4.3 MILLION DOLLARS" reached a delivered GEMS video). Dissolve-heavy films also have no detectable cuts, so one
  "scene" can hold a fade, a title card or another subject. `GEMS/tools/strip.py vid#n` draws a frame every 0.5 s;
  strip any scene longer than the shot cut from it.
- **A transparent PNG renders differently in the video and on the check sheets** (Astro 013, 6 Oct 2026). Chrome
  cards composite alpha onto the card's own background, while PIL `convert('RGB')` and ffmpeg sheets drop it to
  black. A chart drawn for a white page looked dark on the contact sheet and would have shipped as grey lines on
  white. Check `im.mode` (RGBA, or P with transparency) and flatten onto the background it was drawn for.
- **White paper on a white card reads as bare text.** Scans of printouts and star charts need a frame or a dark mat
  (the page itself unaltered), and white cells fail a thumbnail contrast gate however they are cropped.
- **A loop finder needs a baseline that is not itself a repeat** (COZY cabin, 6 Oct 2026). `picture_loop.py` judged
  repeats against two moments a fixed 7.3 s apart, and Cozy Cabin's picture loops every 7.300 s, so the true loop
  looked like no match. The baseline now takes the first of several lags that sits clear of every top candidate.
- **Parallel decoders can come back short without an error** (COZY cabin, 6 Oct 2026). With eight measurement jobs
  at once, `audio_loop.py` decoded 19 to 64 of 77 minutes on five soundtracks and still exited 0. Check each
  output's decoded minutes against the file, and rerun short ones alone.

## Text and metadata
- The YouTube description is capped at 5,000 bytes, with no `<` or `>`. Tags total 500 characters by YouTube's count.
- Credits come from metadata, never typed by hand.
- `scout.json`'s channel field is wrong when a title contains "|". `metadata.py` splits meta lines from the right.
- A card anchor that is not spoken verbatim in its beat used to drop the card silently; `script_check` now fails it.
  Plural and possessive endings are accepted.
- **An emoji test of "any character above U+2000" also catches en dashes, bullets and zero-width spaces** (COZY
  cabin, 6 Oct 2026). It put two era-B hits among the "emoji" titles and hid the real split: 1,724 against 121,429.
  Test the emoji blocks only (U+1F300 to U+1FAFF and U+2600 to U+27BF).

## Process
- **The hook's picture is measured per reference, never imported.** ANIME's first build opened on a ten-piece grid
  tease out of GEMS habit; the reference opens on ONE scene for 30-46 s with its own sound (user, 2 Oct 2026: "the
  opening should allways be one scene, or at least look cohesive. check the reference"). Read the reference's first
  minute frame by frame before writing the open, and gate the shape in `script_check.py`.
- Measuring against your own previous episode instead of the reference makes every episode converge on the first.
- **A reference can vanish.** GEMS's reference took all 18 videos private within three weeks of the teardown (5 Oct
  2026). Keep the measured evidence in the project (`ANALYSIS.md`, `analysis/`), never only as links.
- **When a format's topic list looks finite, measure the live niche before guessing.** Search the title pattern across
  candidate topics, pull the full video list of every channel using it, and compare topics INSIDE each channel
  (channels differ 100x). `GEMS/analysis/tools/runway_scan.py` does this for free. For GEMS it showed the subject
  can be cut three ways (by material, by colour, by angle) where the rules allowed only one.
- A device written into the rules as "every item" becomes a tic. Record it as judgement, never a quota.
- Never re-voice or re-render an approved take or thumbnail unasked. A re-render is a different performance or
  picture.
- The gitify hook may commit your files under another session's prompt as "Checkpoint: …". That is harmless; commit
  logical units yourself anyway.

## YouTube search as a measuring tool (COMPILATIONS, 2 Oct 2026)
- **Check every row's own upload date.** yt-dlp gives search rows an approximate timestamp with
  `--extractor-args youtubetab:approximate_date`. The "this month" and "this week" filters let through about 2% of old
  videos when sorting by views, and those are the biggest rows. A first report quoted 4-6-year-old rain videos as
  "uploaded this month" because of it.
- **"Sort by upload date" is ignored.** Results come back in relevance order, and a search returns exactly as many
  rows as requested. The row count is not a supply measure. Judge crowding by outcomes: what fresh uploads get, and the
  share of top videos from small channels.
- **The month pass is relevance-ordered;** year and all-time are close to view order. "This month's top" is a floor.
- **Filter by title before reading a niche's numbers.** Relevance pollution carried whole niches: 88% of pet-TV views
  were Tom and Jerry and funny-pet compilations, rain searches were led by camping vlogs, "night drive" by song
  playlists, "public domain movies" by licensed films. Look at the top titles before trusting any median.
- **Throttling:** HTTP 403 after about 650 searches at 5 workers; 150-row pages fail first while 60-row pages still
  work. After about 4,000 requests in a day everything failed until the scrape went to 1 worker with a 4 s pause.
- **Inline Python in a here-doc loses doubled backslashes** (they arrive as single ones, so a regex word boundary
  becomes a backspace). Patch source files with the Edit tool instead.

## Paid stages that die halfway (GEMS 007 Green, 6-7 Oct 2026)
- **A Gemini HTTP 402 in the middle of a pick leaves the rest of the beats LOCAL-ranked**, and about 60% of those
  were wrong on sight (presenters, burned-in text, a video game under a museum line, the wrong stone). Budget a full
  by-eye pass over every beat (contact pages per topic, peeks, pins, pincheck, `review --changed` after each pass;
  the green needed eight passes), not a touch-up of the flagged ones.
- **The permission classifier can deny a `CREDITS_OK=1` command after the user's yes** ("Safety Bypass Flag" on the
  scene filter) while the same marker passes on captions, voice and the pick. It is not retried by another route;
  say so in the report and let the captions' usable flags and the eye pass cover the stage.
- **ElevenLabs' per-character rate moved three times in a month** (0.55 → 0.44 → 0.65); measure it from the
  subscription counter around every render and quote at the last measured rate, or the quote lands 50% low.
- **Presenter picture-in-picture insets and text overlays arrive mid-scene**, often only in the last second: a shop's
  product scenes carried the host in a corner box from scene 56 on, a gem close-up faded a colour chart in, a studio
  close-up dissolved to the anchor. First/last-frame sheets catch most of it; grab frames of the master at every card
  before delivering (a subtitle line reached a price-flash frame), and strip any scene longer than the shot cut from it.
- **A caption banner survives a 0.8 crop** when it sits at 0.70-0.86 of the height; measure the banner's top edge on a
  full frame (`keep_top 0.66` for the Pakistan peridot film) rather than defaulting to 0.75-0.8.

## Thinking tokens are most of a Gemini bill (GEMS audit, 7 Oct 2026)
- **Default thinking is on and billed as output.** With no `thinkingConfig`, `gemini-3.5-flash` spent ~1,550 thinking
  tokens on every call, a one-word frame check included: 1.47M of the 1.80M output tokens billed for two builds, about
  13 of 18.65 USD at 9 USD per 1M. Set the thinking budget or level explicitly on labelling, captioning and yes/no calls.
- **Meters must add `thoughtsTokenCount`** to `candidatesTokenCount`; ours didn't, so quotes ran 5-13x low.
- **Check the model's price tier before adopting it.** The newest flash was 3-3.6x the price of the previous two
  (1.50/9.00 vs 0.50/3.00 and 0.30/2.50 USD per 1M) and nobody looked when it became the default.
- **The real numbers live in AI Studio:** Spend (per day, per model, per key) and Usage (input and output tokens per
  model per day). Read them before answering any cost question; estimates from our own logs were wrong.
