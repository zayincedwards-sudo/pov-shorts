# VINTAGE: 4.5-hour rainy-window jazz ambience (reference: Vintage Ambience Cafe, youtu.be/tg2cNKIuCuo)

Project root is this folder. Evidence for every rule is in `ANALYSIS.md` and `analysis/`. Scope set by the user on
9 Oct 2026: replicate ONLY the reference's rainy-window video and close variations of it, plus the channel identity.
Never model the reference channel's other uploads.

**Cross-project rules:** read `../.claude/skills/channel-pipeline/references/house-rules.md` at the start of every
session (credit spend, git, Notepad docs). Anything below that differs is a user decision for this channel.

## Standing rules
- **Format:** one illustrated scene, no cuts, no text, no intro or outro, 4h25m (265 min), 1920x1080. Measured:
  the reference is one uncut scene for 4:25:16 with ~9% of the frame moving (ANALYSIS.md section 3).
- **Scene must keep:** an indoor windowsill, rain on the glass, a black cat from behind on the right third looking
  out, a steaming cup, candles in glass, autumn plants, a lit window across the street. Variations change ONE thing
  (view, hour, cup, cat pose, season's plants). Never drop the rain, the indoor window or the cat: the controls
  without them did 2-9K against 436K (ANALYSIS.md section 2).
- **Still:** written prompt in `episodes/<ep>/scene.json`, `gemini-3.1-flash-lite-image` (~USD 0.034), then
  `tools/grade.py` to the reference's look (target luminance ~53, saturation ~155, RGB ~77/51/31). Gemini never
  looks at images; Claude judges the still by eye (house rule 2).
- **Motion:** `tools/veo_clips.py`: 5 clips of 8 s on `veo-3.1-lite-generate-preview` at 720p (USD 0.40 each), each
  with the still as BOTH first and last frame, so the clips chain into one loop. Camera locked; only flames, steam,
  rain and the cat move. Check each clip with `tools/clip_check.py` (start and end distance to the still ~3, wall
  drift under ~5) and read its contact sheet before using it.
- **Loop assembly:** `tools/assemble.py` crossfades every join (8 frames, wrap-around included). GATE joins: every
  join step must be under the clips' own p99 step x1.5 + 0.5.
- **Music:** six instrumental 1950s-style jazz pieces on `lyria-3.5` (USD 0.08 each, `tools/lyria_songs.py`), about
  2.5-3 min each, 64-129 BPM, muffled to ~1.2 kHz in the mix ("jazz from another room"). The user's call on
  10 Oct 2026: "find out what the original channel did". The reference shows no credit anywhere and its pieces are
  tuned within 2 cents of A440, stereo and level-matched, so it reads as AI-generated; Lyria is the match.
- **Rain:** synthesised, free (`tools/rain.py`, a 354 s seamless loop like the reference's), 17 LU under the music.
- **Loudness:** -14 LUFS integrated, true peak -1.5 dBTP (the reference clips at +0.9; we don't).
- **Delivery:** loop re-encoded at CRF 30 (~0.8 Mbps; YouTube serves the reference at ~0.75 Mbps) with 128k AAC, so
  4.5 h is ~1.77 GB and fits a GitHub release. Thumbnail = the graded still, no text. Title pattern
  `{Weather} {Era} Jazz & Cozy {Place} | {Subject}, {Prop} & Relaxing Ambience`.
- **Spending per episode (measured 10 Oct 2026):** USD 2.51 = still 0.03 + 5 clips 2.00 + 6 songs 0.48.

## Build
```
python tools/rain.py build/rain_354.wav                     # once, free
node ../.claude/skills/gemini-image-gen/scripts/generate.mjs --prompt "<still_prompt>" --aspect-ratio 16:9 --output episodes/<ep>/stills/still_a.png   # paid
python tools/grade.py episodes/<ep>/stills/still_a.png episodes/<ep>/still.png --gamma 1.25 --sat 1.0 --warm 1.04
python tools/veo_clips.py episodes/<ep>            # paid, cached; --redo N to re-buy one clip
python tools/lyria_songs.py episodes/<ep>          # paid, cached
python tools/assemble.py episodes/<ep> --minutes 265
```
Key: `GEMINI_API_KEY` in `VINTAGE/.env` (gitignored) or the environment.

## Episode order
- 001 Rainy 1950s Jazz & Cozy Window (10 Oct 2026): 4h25m, 38.3 s picture loop, 16:42 music bed, USD 2.51.
  Delivered as a draft GitHub release `vintage-ep001`.

## Build lessons
- 10 Oct 2026: Veo's `predictLongRunning` rejects `inlineData` images (the docs example is wrong for it); it wants
  `{"bytesBase64Encoded", "mimeType"}`, and `durationSeconds` must be a number. Both 400s are not billed.
  `veo_clips.py` now sends the working form and prints the API's error body.
- 10 Oct 2026: hard-cut joins between clips stepped 1.1-1.5 against a normal 0.33, a faint pop every 8 s. An
  8-frame crossfade at every join (and the wrap) brought them to ~0.6; the join gate enforces it.
- 10 Oct 2026: the CRF 16 master repeated for 4.5 h is ~14 GB, too big to get out of a cloud session; the delivery
  encode (CRF 30) is 1.77 GB.
- 9 Oct 2026: YouTube bot-walls cloud IPs for media (yt-dlp, headless Chrome, mirrors). Channel pages, storyboards
  and comments (via curl, not Python urllib) still answer; the user supplies media from their own machine.
