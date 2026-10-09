---
name: image-analyzer
description: Analyze an image in detail and produce a structured description plus a ready-to-use text-to-image prompt. Use when the user asks to describe, examine, or understand an image, or wants to recreate a similar image from an existing one.
---

# Image Analyzer

Analyze a source image and turn it into a structured, reusable description that can be handed to an image generator (for example the `gemini-image-gen` skill) to produce a *similar* image.

## When to use

- The user provides an image and asks "what is this?", "describe this", "analyze this image", or similar.
- The user wants to recreate a similar image and needs a prompt first.

## Instructions

1. **Identify the source image(s).**
   - Collect the local image path(s), HTTP(S) image URL(s), or data URL(s) the user provided.
   - If no image is given, ask the user for one.

2. **Analyze each image** using the built-in image understanding tool (`UnderstandImage`).
   - Ask specifically for: subject(s), action/pose, environment/background, composition and framing, art style or medium, lighting, color palette, mood, text or logos, and any notable details.
   - If the image is a local file, make sure the path is absolute and readable.

3. **Produce a structured result** for each image:

   ```text
   ## Subject
   ...
   ## Action / Pose
   ...
   ## Environment / Background
   ...
   ## Composition & Framing
   ...
   ## Style / Medium
   ...
   ## Lighting
   ...
   ## Color Palette
   ...
   ## Mood
   ...
   ## Text / Logos (if any)
   ...
   ```

4. **Write a reusable generation prompt.**
   - Condense the structured notes into one dense, comma-separated prompt that captures subject, action, environment, composition, style, lighting, palette, and mood.
   - Keep any exact wording the user wants to preserve (text, brand names, etc.).
   - End with a short "Generation prompt:" line that can be copied directly into `gemini-image-gen`.

5. **Offer next steps.**
   - If the user wants a similar image, propose running the `gemini-image-gen` skill with the prompt (and, if they want it to stay visually close, the original image as a reference).
   - Do not auto-generate; confirm with the user first.

## Best practices

- Be concrete and specific; avoid vague words like "nice" or "good".
- Preserve the user's intended subject; do not invent major new elements unless asked.
- Distinguish between what is actually in the image and what you infer.
