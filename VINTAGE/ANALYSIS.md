# VINTAGE: teardown of one video (reference: Vintage Ambience Cafe)

Scope (user, 9 Oct 2026): replicate ONLY "Rainy 1950s Jazz & Cozy Window | Cat, Candles & Relaxing Ambience"
(youtu.be/tg2cNKIuCuo) and very close variations of it, plus the channel's identity. The channel's other nine
uploads are used only as controls here, never as models.

Data actually measured (cloud IP is bot-walled; the user supplied the media):
- `analysis/yt/tg2_1080_30s.mp4`: 30 s of the video at 1920x1074, 30 fps (user upload)
- `analysis/yt/tg2_audio_32min.m4a`: the first 32 min 10 s of the soundtrack, AAC 128k (user upload)
- 1,593 storyboard frames covering the full 4:25:16 (321x180, one every 9.99 s), info JSON, heatmap, thumbnail
- the channel's About page, avatar and banner (`channel/`)

## 1. Channel snapshot (9 Oct 2026)
- Joined **16 May 2026, the same day this video went up: it was the channel's first upload.**
- 3.37K subscribers, 626K total views, 11 videos. This video: 435,780 views (70% of the channel), 7,166 likes
  (1.6%), 46 comments, ~2,985 views/day lifetime.
- Next best: 70K (Witch Cat's Kitchen), 57K (Vintage Library). Median upload 8.6K. Outlier ratio 50.6x.
- Every upload is a 3-4.5 h single-scene ambience in the same ink-outline illustration style, every thumbnail a
  frame of its video with no text.

## 2. Controls (the other uploads, for what separates the hit; never copied)
| views | scene | rain | indoor window | cat | jazz |
|---|---|---|---|---|---|
| 435,780 | **this video**: windowsill, cat, candles, cup | yes | yes | yes, back to viewer | 1950s |
| 57,497 | vintage library, fireplace, cat at window | yes | yes | yes | slow jazz |
| 69,988 | witch cat's kitchen (Halloween, seasonal) | no | kitchen | yes | lo-fi/autumn jazz |
| 28,426 | cat on porch steps, autumn | no | outdoor | yes | lo-fi |
| 9,036 | 1950s noir, cat on coastal balcony at sunset | no | outdoor | yes | 1950s noir jazz |
| 8,116 / 8,191 | balcony at dusk / backyard pumpkins | no | outdoor | yes / tiny | lo-fi |
| 4,786 / 2,957 / 1,587 | lighthouse / magical porch rain / moon | mixed | no | tiny or none | ambient / 1930s |
Read: the two **rain + indoor window + cat looking out + jazz** videos are the hit and the third best. "1950s jazz"
without rain or a window (the noir video, 9K) did nothing, so the window-in-the-rain is the core, not the era.
Caveats: n = 10, no CTR, and the hit also had first-upload timing in May; treat as direction, not proof.

## 3. The video measured
### Picture
- **One continuous scene for all 4:25:16.** Storyboards: no cuts, no fades, mean luminance 54.3-55.2 of 255 from
  first frame to last. 30 s clip: largest frame-to-frame change 0.94/255, so zero cuts.
- **Composition** (1920x1074 frame, `analysis/frames/v_01.png`): interior windowsill at dusk in the rain. Black cat
  sitting with its back to the viewer, looking out, right of centre (body x 1300-1650, ears at y 400, tail on the
  sill to x 1750). Steaming cup on a saucer just left of the cat (x 1080-1270). Glass jar lantern with three lit
  pillar candles (x 900-1075). Terracotta pots with dried orange autumn leaves along the sill; a hanging plant top
  right; a candle lantern cut by the left edge; small framed pictures on the wall top left; scattered leaves on the
  sill; a patterned cushion bottom left. Through the panes: rain on the glass, a neighbouring brick house with a
  warm lit window behind the cat's head.
- **Style:** inked outlines over flat-shaded colour, vintage storybook/comic. Warm palette: amber, rust, olive,
  brown; the cat is a pure black silhouette with a thin light rim. Thumbnail stats: 0% white, 22% near-black,
  saturation 142.
- **Motion (9.2% of pixels move, 5.1% strongly):** candle flames (lantern and jar), steam curling off the cup,
  faint rain on the glass, and the cat: the tail sweeps back and forth across the sill continuously, and the head
  and body sway slightly (`analysis/cat_motion_sheet.jpg`, `analysis/motion_1080_30s.png`). Nothing else moves.
  The cat never leaves its spot.
- **Frame rate:** the motion steps every 2-3 frames, so the animation was made at roughly 12-15 fps and
  delivered at 30.
- **Defect, not to copy:** two thin flickering vertical seams at x ≈ 320 and x ≈ 965, visible in the motion map,
  the thumbnail and the storyboards. Odd height 1074 too. Both point to an AI-animate-then-upscale pipeline.
- **Picture loop: longer than 30 s, exact length NOT yet measured.** The clip never repeats inside its 30 s.
  Storyboards say the loop length divides ~419.6 s (strongest repeat at 42 storyboard frames), which leaves
  35.0 / 38.1 / 69.9 / 83.9 / 209.8 s and others; 10 s sampling cannot separate them. Needs a 4-5 minute clip at
  any resolution (see NEEDS.txt).

### Sound (`analysis/audio_bed_tg2.json`, `analysis/tools/audio_loop.py`, `rain_loop.py`)
- **Two independent loops, mixed together:**
  - **Music bed: 602.665 s (10:02.7)** loop, proven on the waveform: correlation 0.98 at every start tested, and at
    2x (1,205.331 s) and 3x (1,807.996 s). About five pieces per loop, split by gaps 15-17 dB deep at 80, 130, 290,
    448 and 582 s (pieces of ~50, 160, 158, 134 and 102 s). Tempos read 64-129 BPM: slow to mid swing.
  - **Rain bed: 354.0 s (5:54)** loop, on the >5 kHz band (correlation 0.85-0.95 at the next repeat), with a
    2.73 s slip somewhere between 1,254 s and 1,610 s. Its join shows as a vertical line on the spectrogram at
    ~353 s. Because 354 and 602.7 don't line up, the mix never repeats exactly within the 32 minutes.
- **"Jazz from another room":** the music is heavily low-passed. 99% of its energy sits below 1,184 Hz, 90% below
  462 Hz, half below 96 Hz. It is warm and muffled, with no air on top.
- **Rain level:** in the song gaps the mix drops to -29 dB against -11.7 dB under music, so the rain sits about
  17 dB below the music. It is broadband (99% of gap energy below 9 kHz). The rain is a quiet bed under the jazz,
  not the main sound.
- **Loudness:** -13.9 LUFS integrated, LRA 4.9 LU, true peak **+0.9 dBTP** (over full scale; a defect, not to
  copy). Narrow stereo (side 11 dB under mid).
- **No voice, no sound effects, no thunder** are visible in the spectrogram. Auto-captions read only "[music]"
  and ASR noise ("Heat. Heat.").
- The About page promises "the gentle crackle of vinyl". It is not separable at this resolution of analysis;
  confirm by ear.

### Retention (heatmap, 100 segments of 159 s)
The opening segment is 1.0, everything after is flat at 0.24-0.34 (median 0.24). Small bumps at 53 min, 2:10 and
40 min are noise-level. Nothing marks 11:25. Viewers start it and leave it running.

## 4. Title, description, tags
- Title: `Rainy 1950s Jazz & Cozy Window | Cat, Candles & Relaxing Ambience`
  Pattern: `{Weather} {Era} Jazz & Cozy {Place} | {Subject}, {Prop} & Relaxing Ambience`. No emoji (the channel's
  later titles added emoji and did worse, but that is not isolated).
- Description: two paragraphs, present tense, sensory: the 1950s rainy day, raindrops tapping the window,
  candlelight, the black cat gazing out, plants, "vintage jazz melodies play—just like old records spinning in
  another room", for "relaxation, sleep, or study"; the second paragraph is "safe at home" comfort. No timestamps,
  links or credits.
- Tags: seven hashtag strings (#vintagejazz #rainyambience #cozywindow, #relaxingmusic, #candlelight, #oldies
  #studymusic, #chilljazz, #coffeejazz, #oldvinyl).

## 5. Channel identity (`channel/`)
- Name "Vintage Ambience Cafe", handle @VintageAmbienceCafe.
- Avatar (`ref_avatar.jpg`): a flat retro screen-print poster in a different style from the videos. A cat from
  behind on a sill at an arched rainy window, a vinyl record filling the arch, a lit candle, steam curling up into
  music notes, fern and monstera in terracotta pots, on a mustard background with a cream border.
- Banner (`ref_banner.jpg`): a 2048x339 crop of a sibling scene in the video ink style (cat silhouette, candle in a
  glass, rain-streaked window, autumn plants).
- About text: "your cozy corner for vintage jazz, rain ambience, and nostalgic relaxation… 1950s jazz, soothing
  rain sounds, candlelight glow, and peaceful home vibes… sleep, study, or unwinding… the mellow tones of jazz from
  another room, rainy windows, quiet cats, and the gentle crackle of vinyl".

## 6. Build rules distilled (for this video and its close variations)
1. One static illustration in the ink-outline vintage style, warm amber/rust/olive, animated in place. No cuts,
   text, intro or outro. Deliver clean 1920x1080, with no tile seams.
2. The scene keeps: indoor windowsill, rain on the glass, a black cat from behind looking out on the right third,
   a steaming cup, lit candles in glass, potted autumn plants, a lit window across the street.
3. Motion only in flame, steam, rain on glass, and the cat's tail and sway: about 9% of the frame. Seamless picture
   loop (length to match the reference once measured).
4. Sound: a ~10-minute bed of about five slow-to-mid instrumental jazz pieces, low-passed to about 1.2 kHz,
   looped; under it an independent ~6-minute rain loop about 17 dB down; no voice or effects. Master to about
   -14 LUFS with true peak at or under -1 dBTP (the reference clips; we won't).
5. Runtime about 4.5 hours. The thumbnail is a frame of the video with no text.
6. Title in the measured pattern; a two-paragraph sensory description; hashtag tags.
7. Close variations change ONE element at a time and keep the rest: the view (a different street, a garden),
   the hour (blue night instead of dusk), the cup (tea, cocoa), the cat's pose (curled up, lying down), the season's
   plants. The controls say never to drop the rain, the indoor window or the cat.

## 7. Caveats
- One hit, ten uploads, public data only (no CTR or impressions). First-upload luck can't be separated out.
- Audio measured on the first 32 min only. The loops were proven three and five times over inside it, but a
  change later in the 4.5 h can't be ruled out.
- Picture measured on 30 s at full res plus 10 s-sampled storyboards. The loop length is still open.

## 8. Evidence index
`analysis/storyboard_tg2.json` (+ `_motion.png`, `_median.png`), `analysis/motion_1080_30s.png`,
`analysis/cat_motion_sheet.jpg`, `analysis/audio_bed_tg2.json`, `analysis/spectrogram_loop1.png`,
`analysis/channel_table.csv`, `analysis/thumb_stats.json`, `channel/`. Tools: `analysis/tools/`.
