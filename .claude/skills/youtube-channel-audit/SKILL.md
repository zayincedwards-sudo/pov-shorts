---
name: youtube-channel-audit
description: Analyze a YouTube channel (via the YouTube Data API) plus the user's top-performing videos and screenshots of the thumbnails + titles of both best and worst videos, then produce a content playbook (what works, what to avoid, hooks, titles, thumbnail style). Use when reverse-engineering a channel's success or planning a new channel's strategy before producing videos.
---

# YouTube Channel Audit

Reverse-engineer a YouTube channel: pull hard data (views, likes, comments, titles, upload cadence, thumbnails) and combine it with qualitative analysis of provided videos/screenshots to produce a reusable **content playbook**.

## Prerequisites

- YouTube Data API key in `~/.deepcode-plus/settings.json` under `env.YOUTUBE_API_KEY`.

## Inputs (ask if missing)

- Channel: `@handle`, channel ID, or URL.
- A local folder with the **top-performing videos** (actual video files — losing videos are NOT provided).
- Screenshots of the **thumbnails and titles** of **both** the best- and worst-performing videos.
- A screenshot of the channel's **branding** — channel name, profile picture, banner, and description.

## Instructions

1. **Run the audit script:**
   ```bash
   node scripts/audit.mjs --channel "@handle" --max 50 --out ./audit
   ```
2. **Read `audit.md`** (and `audit.json`) to see top vs bottom videos by engagement.
3. **Analyze the provided materials** with the built-in image tool:
   - **Top videos**: extract hook patterns, structure, pacing, and editing cadence.
   - **Thumbnail + title screenshots** (best vs worst): identify what separates winners from losers — composition, colors, on-screen text, faces/expressions, and title phrasing.
   - **Branding screenshot** (name, profile picture, banner, description): extract the channel's brand identity — color palette, banner composition/layout, profile-picture style, and description tone/structure — so a *similar* (but original) brand can be created.
4. **Synthesize a `playbook.md`** covering:
   - audience and content pillars
   - hook formulas (first 30 seconds)
   - title patterns and thumbnail style
   - video structure and ideal length
   - upload cadence
   - brand identity (colors, banner layout, profile-pic style, description structure)
   - pitfalls to avoid (from the worst videos' thumbnails/titles)
5. **Save the playbook** where the `youtube-channel-produce` and `youtube-channel-brand` skills can read it (the "brand identity" section feeds the brand skill).

## Best practices

- Ground every conclusion in the data (views/likes/comments) or the provided visuals — do not guess.
- Distinguish correlation from causation; flag what needs A/B testing.
- The output is a strategy playbook, not a single video plan.
