---
name: gemini-image-gen
description: Generate or edit images with Google Gemini (gemini-3.1-flash-lite-image) via the Gemini API. Use when the user asks to create an image from a prompt, or to make a similar or edited version of a reference image. Reads GEMINI_API_KEY from ~/.deepcode-plus/settings.json.
---

# Gemini Image Generator

Generate or edit images using Google's Gemini image model (`gemini-3.1-flash-lite-image`) through the Gemini API. Supports text-to-image and image-to-image (pass a reference image to keep the result visually close).

## Prerequisites

1. **API key.** Get one from [Google AI Studio](https://aistudio.google.com/apikey).
2. **Store it** in `~/.deepcode-plus/settings.json`:

   ```json
   {
     "env": {
       "GEMINI_API_KEY": "your-key-here"
     }
   }
   ```

   Do not paste the key in chat. The script also accepts a `GEMINI_API_KEY` environment variable or a `--api-key` flag as overrides.

3. **Runtime.** Requires Node.js 18+ (uses the built-in `fetch`). No npm install needed.

## Instructions

1. **Collect the request.**
   - A prompt (required): either written by the user or taken from the `image-analyzer` skill's "Generation prompt:" output.
   - Zero or more reference images (local paths, HTTP(S) URLs, or data URLs). To make a *similar* image, pass the original image as a reference plus a text instruction.
   - An optional aspect ratio.

2. **Run the helper script** from this skill directory:

   ```bash
   node scripts/generate.mjs \
     --prompt "<prompt>" \
     --image "<reference.png>" \
     --aspect-ratio "1:1" \
     --output "<output.png>"
   ```

   - Omit `--image` for pure text-to-image.
   - `--aspect-ratio` is used only when no reference image is given (editing preserves the input dimensions). Supported values include `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`.
   - If `--output` is omitted, the script writes a default file and prints its path.

3. **Report the result.** On success, tell the user the saved file path. If the API returns an error or safety block, relay the safe message verbatim — do not claim success.

## Script reference

Run `node scripts/generate.mjs --help` for all options. Key flags:

- `--prompt <text>` (required)
- `--image <path-or-url>` (repeatable)
- `--aspect-ratio <ratio>`
- `--output <path>`
- `--model <name>` (default `gemini-3.1-flash-lite-image`)
- `--api-key <key>` (override; prefer `~/.deepcode-plus/settings.json`)

## Notes & verification

- The script calls `POST https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent` with `x-goog-api-key`.
- Request fields use `inlineData`/`mimeType` and `generationConfig.responseModalities` (values `TEXT`, `IMAGE`). If the API rejects the request, verify these against the current [Gemini image-generation docs](https://ai.google.dev/gemini-api/docs/image-generation), and confirm the model name is available in your region/plan.
- The model name `gemini-3.1-flash-lite-image` can change; use `--model` to switch if Google renames it.
