---
name: youtube-channel-produce
description: Produce a publish-ready YouTube video from a topic + per-channel config. Generates script, titles, description, thumbnail, and an ordered shot list (each classified photo vs drawing); auto-generates drawings via Gemini and makes black placeholders for photos; adds voiceover (11labs); assembles with ffmpeg; then collects the user's real images one at a time and re-renders. Use when producing or publishing videos for a channel.
---

# YouTube Channel Produce

Turn a topic into a publish-ready YouTube video, driven by a per-channel `channel-config.json`.

## Pipeline

1. **Content** (Gemini): script, 3 title options, description, thumbnail, and `shots.txt` — the ordered shot list, one line per shot as `type || description || motion || text` (motion/text applied only when the analysis deems them impactful).
2. **Drawings**: generated automatically via the image-generation agent (Gemini).
3. **Photo placeholders**: black rectangles with white text describing each photo shot.
4. **Voiceover** (ElevenLabs, optional): TTS from the narration.
5. **Draft assembly** (ffmpeg): slideshow (drawings + photo placeholders) + voiceover.
6. **Collect photos**: ask the user for each photo, one at a time, in order.
7. **Re-render** (ffmpeg): replace photo placeholders with the user's real images, preserving original aspect ratio.
8. **Publish** (manual): batch upload via YouTube Studio.

## Config

Copy `channel-config.example.json` to `channel-config.json` and fill in:
`channelName`, `niche`, `style`, `productionMode`, `voice.voiceId` (ElevenLabs), `playbookPath`, `batchSize`. (Ignore `avatar` unless you later add HeyGen.)

## Steps

### 1. Generate content

```bash
node scripts/produce.mjs --topic "<topic>" --config channel-config.json --out ./produce
```

Per topic this writes: `script.md`, `titles.txt`, `description.txt`, `shots.txt`, `thumbnail.png`, `publish.json`.

### 2. Generate drawings (auto) + photo placeholders

Drawings (illustrations, 3D renders, charts, graphics) are generated automatically via the image-generation agent:

```bash
node scripts/generate-drawings.mjs --shots produce/<slug>/shots.txt --out produce/<slug>/shots
```

Photo shots get black-rectangle placeholders with white text:

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/make-placeholders.ps1 -Shots produce/<slug>/shots.txt -Out produce/<slug>/shots
```

Both write `shot-NN.png` using the shot's video order, so the `shots/` folder ends up with the full ordered sequence — drawings generated, photos as placeholders.

### 3. Voiceover (optional)

```bash
node scripts/tts-elevenlabs.mjs --text "<narration>" --voice-id <ID> --out voiceover.mp3
```

### 4. Draft assembly (needs ffmpeg)

```bash
node scripts/assemble.mjs --images produce/<slug>/shots --shots produce/<slug>/shots.txt --audio voiceover.mp3 --out draft.mp4
```

`assemble.mjs` reads `shots.txt` and applies **motion** (zoom/pan) and **on-screen text** only to the shots the analysis flagged; everything else is a static, aspect-ratio-preserved still.

### 5. Collect photos — interactive protocol (IMPORTANT)

Only **photo** shots need your input (drawings were already generated).

1. Count the `photo |` lines in `shots.txt`; tell the user how many photos are needed.
2. Ask: **"Are you ready to provide the photos?"** and wait.
3. When they say yes, ask for **photo 1**, quoting its description. Wait for the user to paste/provide it, save it over the corresponding `shot-NN.png` (replacing that photo slot's placeholder), then ask for photo 2, and so on — **strictly sequential, in video order**.
4. Do not proceed until every photo has been received.

### 6. Re-render final (needs ffmpeg)

```bash
node scripts/assemble.mjs --images produce/<slug>/images --shots produce/<slug>/shots.txt --audio voiceover.mp3 --out final.mp4
```

Static shots are scaled to fit the 1920×1080 frame **without cropping or stretching** (letterboxed). Shots flagged with motion fill the frame (cover + crop) as they zoom/pan, and flagged text is burned in with `drawtext`.

### 7. Publish

1. **studio.youtube.com → Create → Upload videos**.
2. Upload `final.mp4`, paste the title (from `titles.txt`) and description (`description.txt`), upload `thumbnail.png`.
3. Schedule releases in batches (see `batchSize`).

## Secrets (all under `env.*` in `~/.deepcode-plus/settings.json`)

- `GEMINI_API_KEY` — wired & tested
- `ELEVENLABS_API_KEY` — needed for voiceover

## Notes

- **ffmpeg is required** for steps 4 and 6. Install with `winget install Gyan.FFmpeg` (or `choco install ffmpeg`); `assemble.mjs` auto-detects it.
- `tts-elevenlabs.mjs` needs a valid `sk_…` key (verified).
- The thumbnail has no baked-in title text; overlay it with ffmpeg or an editor if desired.
