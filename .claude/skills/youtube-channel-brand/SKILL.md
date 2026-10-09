---
name: youtube-channel-brand
description: Generate a YouTube channel's profile picture, banner, and channel description in a chosen niche/style using Gemini, optionally matching a reference channel's branding (from the audit). Use when setting up branding for a new channel or rebranding an existing one.
---

# YouTube Channel Brand

Generate the three core branding assets for a YouTube channel: profile picture, banner, and description.

## Prerequisites

- Gemini API key in `~/.deepcode-plus/settings.json` under `env.GEMINI_API_KEY`.

## Inputs (ask if missing)

- Channel name
- Niche / topic
- Optional style notes
- Optional reference branding (from the `youtube-channel-audit` playbook's "brand identity" section) to generate *similar* elements

## Instructions

1. Run:
   ```bash
   node scripts/brand.mjs --name "<Name>" --niche "<topic>" --style "<optional>" --style-ref "<reference brand style>" --out ./brand
   ```
   `--style-ref` is optional; pass the audit playbook's "brand identity" text to generate similar (but original) branding.
2. Outputs: `profile.png` (1:1), `banner.png` (16:9), `description.txt`.
3. Give the user the exact manual upload steps below.

## Manual upload steps (YouTube Studio)

1. Go to **studio.youtube.com → Customization → Branding**.
2. Upload `profile.png` as the profile picture.
3. Upload `banner.png` as the banner (YouTube recommends 2560×1440; the image is 16:9, so keep important content centered and crop if needed).
4. Paste `description.txt` into **Customization → Basic info → Description**.

## Notes

- Text/logos are omitted from generated images by default (YouTube overlays UI elements); add text manually if desired, or pass a more specific `--style`.
- To bake text into the banner, edit the prompt in `brand.mjs` or pass a detailed `--style`.
