# Phase 4: Sourcing the picture

## Decide the visual approach first (per channel, measured from the reference)
| Approach | Used by | Cost | When |
|---|---|---|---|
| Real documentary footage clipped from YouTube | GEMS | Gemini captions and matching ≈ $1 an episode, or $0 when every beat is pinned by eye | The reference cuts real footage; the subject is physical (stones, places, sales) |
| Wikimedia Commons stills (credited) | GEMS gaps, Astro | free | No footage exists of the exact thing; history; museum objects |
| Generated images | zayin / SAM (stick figures, pose library) | ~$1.75 an episode after batching and flash-lite image | The reference is drawn or animated |
| Programmatic animation and cards | Otto (hooks), Astro (white cards) | free | Diagrams, mascots, ranked cards |
The user decided GEMS may clip YouTube sources (16 Sep). Every clip and photo is credited in the description.

## Footage pipeline (GEMS)
1. **Shot keys.** Write `episodes/<ep>/footage/keys.json` as `{"key": ["search query", …]}`, one key per item or
   subject. Use the same keys in the script's shot tags.
2. **Scout:** `python tools/scout.py <ep> <keys.json>` runs a free yt-dlp search and keeps the top 3-4 per key by views,
   90 s to 60 min. It writes `footage/scout.json` (everything found) and `sources.json` (the picks).
3. **Curate `sources.json` by hand. This is where quality comes from.** Keyword scouting drags in junk: music videos
   ("Shampain", "Disarm"), a YouTuber's red play button, product reviews. Delete it.
   - Then add **subject searches for every named thing in the script**: the exact object, event or place ("Hope Diamond
     phosphorescence", "Millennium Dome heist 2000", "Williamson Pink Star Sotheby's"). Use an auction house's own
     film of its own sale.
   - The best source is the one showing exactly what the line says.
4. **Fetch:** `CREDITS_OK=1 python tools/fetch_batch.py <ep> --per-key 10 --budget 540`, repeated until it prints
   `remaining 0`. It is free, but the guard flags it through its imports, so run it inside the build the user approved.
   Foreground slices of ≤ 9 minutes are the safe default. In a session where background jobs survive (as on 30 Sep),
   the same command with a larger budget can run in the background with a log.
   - `footage.fetch` downloads at ≤ 720p and writes `cache/yt/<id>.meta.txt` (`title|channel|duration|licence`; split
     from the right, since titles contain "|").
   - It also writes `scenes.json` (scene cuts), per-scene frames in `<id>_frames/` and a numbered contact sheet.
5. **Blacklist (Gemini):** `tools/scene_filter.py --ids …`. One call per contact sheet; it flags title cards, presenters
   to camera, text slides, logos, screens, black frames and watermarks.
6. **Captions (Gemini):** `tools/illustrate.py captions <ep>`. One call per sheet gives a caption and a usable flag for
   every scene. Matching and verification use these.
7. A failed API call is NEVER cached as an empty result. Both the captions and the blacklist were fixed after a 402 left
   empty files that silenced every later run.

## Picking by eye (when Gemini is down, or for the beats that matter most)
Every beat can be pinned by hand. The diamond episode was built this way with zero Gemini calls: 298 shots, all looked
at.
- `python tools/cpages.py <name> <vid> <vid> …` gives combined contact pages for a topic (72 labelled frames a page).
- `python tools/pages.py <vid> [min_len]` pages one long source (a 40-minute episode).
- `python tools/peek.py vid#a-b vid#n@2.5` shows three frames per scene (start, middle, end). A scene can cut to a
  presenter, a title card or another subject halfway through. ⚠ Quote ids that start with "-", and never pass "--".
- `ffmpeg -ss <t> -frames:v 1` at full resolution, before planning around any source. Burned-in captions, channel bugs
  and watermarks rule out whole sources (Howcast, a jewellers' channel, CCTV-9) or force crops.
- Write the pins with `tools/pins.py`. `pins.apply(ep, {snippet: "pin: vid#n, vid#n@1.5 | none"})` sets the shot tag of
  the beat whose line contains the snippet, and `pins.split(ep, snippet, [line, line])` gives one beat two shots. Both
  refuse to write if the narration or the cards would change. `python tools/pins.py <ep>` checks the script against the
  voiced words and lists any beats still unpinned.

## Stills (Wikimedia Commons)
- `python tools/commons.py search "query" …` | `cat "Category"` | `get "File:Name.jpg" out.jpg` prints the credit line
  `file | author | licence | https://commons.wikimedia.org/?curid=N`. It has 429 backoff built in; pace the downloads.
- `python tools/still.py <src> <out.jpg> --mode contain|cover [--crop x0,y0,x1,y1] --credit "<line>"` writes a
  1920×1080 still plus `<out>.jpg.txt`.
  - `contain` keeps a portrait photo whole over a blurred copy of itself.
- Never type an author name by hand. The credit comes from Commons' own metadata (a made-up name once reached the
  credits).
- Search terms that fail on Commons: generic ones return scanned books. Use exact object names or categories.

## Cleaning the frame
- `cache/yt/<id>.crop.json`: `{"keep_top": 0.8, "keep_x": [a, b], "keep_y": [a, b], "scenes": {"12": {...}}}` crops
  burned-in subtitles, chyrons, counters, watermarks and baked-in bars before the fit. A scene entry overrides the
  video-wide values.
  - Examples: a Rick Steves watermark (`keep_top 0.86` video-wide); BBC "GROWING TIME" counters (`keep_y [0.13, 1]`
    plus `keep_top 0.8`); a pillarboxed factory clip (`keep_x/keep_y [0.13, 0.87]`).
- `python tools/bars.py <ep> [--write]` measures bars on every used scene. Dark scenes give false positives (a stone in
  a black case is not a bar). Look before writing, and never crop a portrait photo to a strip.

## Rules of thumb the user enforced
- **Literal illustration.** The frame shows what the words say: the stone named, the place named, the house that held
  the sale. "Kings and collectors" gets crowns, not muddy water. A Christie's sale is never shown in a Sotheby's room.
- The N-types grid shows the actual stones, never people, markets or benches.
- No presenters to camera, no title cards, no other channel's on-screen text, no black frames.
- Never let footage repeat within a beat. Across an episode, reuse a scene only on purpose (the hook's shot at the
  payoff).

## YouTube access traps
- After ~30 downloads YouTube can raise a sign-in wall ("Sign in to confirm you're not a bot", HTTP 429) that lasts
  hours. Fill the gaps with Commons stills and re-cut once it lifts (the jade re-cut moved stills from 29% to 14.7%).
  Getting past it needs `yt-dlp --cookies-from-browser` with the user's login: ask first, never do it unasked.
- Single videos can 403. Retry later or swap the source. yt-dlp's "no JS runtime" warning is harmless.
- Write metadata only through Python with UTF-8. A bash `yt-dlp --print > file` on Windows wrote the console codepage,
  and channel names in Chinese or Japanese came out empty.
