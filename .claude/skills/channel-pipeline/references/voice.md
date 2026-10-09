# Phase 3: Voice

The narration is the spine: the picture is timed to it and the audio is never edited after it arrives. House rules 7-10
govern everything here. This file covers how to apply them.

## Choosing the voice (once per channel)
1. Measure the reference delivery first. Get words per minute from the transcript timings, the pitch range, and the
   pause lengths between sections. Write the numbers into ANALYSIS.md.
2. **Free route first.**
   - Shortlist 3-4 ElevenLabs voices whose description fits (age, accent, energy). Listing voices, their free
     `preview_url` clips, and a voice's settings cost nothing.
   - `Astro\lib\voiceprint.js` with `match_reference_voice.js` ranks library voices against the reference narrator
     using previews only, with no text-to-speech.
   - Hand the user the preview links, or the files saved into the project. Never render samples unprompted.
   - ⚠ Rendering with a shared-library `voice_id` ADDS that voice to the account, and there is no way to audition a
     library voice through the API without acquiring it. Premade voices expire 31 Dec 2026.
3. **A paid A/B only if the user wants to hear real lines.** Render the same ~300-character paragraph from a real draft
   with 2-3 finalists, after quoting the characters.
4. **The user picks.** On Otto the user picked Liam. On GEMS they picked "Hey Its Brad - Clear Narrator for
   Documentary" (`Dslrhjl3ZpzrctukrQSN`) on `eleven_v3`, after an A/B showed v3 "talking to you" where v2 was "reading at
   you", at the same cost (~0.55 credits a character on Creator) and 165 wpm against 155. Record the choice and the
   date in the channel's CLAUDE.md.
5. A professional voice clone has trained weights only for the models its record lists, often none for `eleven_v3`. On
   v3 such a voice renders with a noise floor ~18 dB higher and fuzzes unpredictably. ElevenLabs' advice is an instant
   clone or a designed voice for v3.

## Settings
- Fetch the voice's own stored settings (`GET /v1/voices/<id>/settings`) and send them with every render. GEMS:
  `tools/el.py` `stored_settings()`, with a hardcoded fallback. Brad's stored settings equal the global defaults (0.5 /
  0.75 / 0.0 / speaker boost / speed 1.0). Adam's on Astro are 0.75 stability, 0.4 style, 0.95 speed. That is why
  defaults read flat for some voices.
- On v3 a stability of 0.5 means "Natural", style is ignored, and speed is not a setting. Never atempo.
- Pace moves with the settings, so re-measure wpm on the first real render before sizing the next script.

## Rendering
- **Chunking:** a chunk is one generation. Write paragraphs of 150-450 characters, split at sentence boundaries. Measured
  across 98 Astro chunks: over 900 characters, 70% came back fuzzy; under 300, 27%; 300-450, 15%. GEMS renders whole
  sections as takes up to ~4,900 characters and accepts the result. A new channel should prefer short chunks.
- **Takes and caching:** `GEMS/tools/vo.py` plans the fewest takes that fit the request limit and splits at section
  boundaries (after the CTA when two takes fit). It caches each take by a hash of voice, model and text.
  - `takes.json` pins the take boundaries once voiced, so editing one section re-voices only that take.
  - A respelling is tested with a ≤ 100-character throwaway before a section is re-rendered.
- **Hook:** the OPEN is its own take, bought `HOOK_TAKES = 3` times. `tools/takescore.py` keeps the take closest to the
  voice's profile. The others stay as `take_00_alt1/2.mp3` with scores in `take_00_hook.json`. A failed later take
  never wastes the ones already paid for.
  - The profile must be THIS voice's. `vo.py` voices the body before the hook. If `assets/voice_profile.json` was not
    built for this voice id, it scores the hook against a provisional profile built from those body takes.
  - After the first approved episode, build the real profile:
    `python tools/takescore.py --profile episodes/<ep>/vo/take_01.mp3 … --voice "<name> <voice_id>"` (from the
    project root).
- **Pronunciation:** `assets/tts_map.json` holds respellings sent to the voice only. The script, cards and word timings
  keep the real spelling. The map is one token to one token so the alignment stays word-aligned, and uses plain
  respellings, because a hyphen puts an audible break in the word. Typical entries are names, foreign places and
  diacritics ("Māori." → "Mowree.").
- **Output:** `with-timestamps` gives character alignment, which becomes `vo/words.json` (word, start, end, section) and
  `vo/sections.json`. Request `mp3_44100_192` (Creator), with a fallback to 128.
- **Joining:** frame-copy concat only (`-f concat -c copy`); a single take is a byte copy. Never trim lead or tail
  silence.

## QA (free, then cheap)
- `GEMS/tools/vo_qa.py <ep>` transcribes with faster-whisper (`small.en`), diffs against the script and lists every
  window carrying a number or a name. Homophones and US/UK spellings ("colour" → "color") are not errors.
  - Look for real slips: a mangled name ("Koh-i-Noor" → "Koinor" can be fine audibly; check by ear when in doubt), a
    skipped line, a doubled phrase.
  - `--ear` adds a Gemini listen per doubtful window. It is a spend, so ask first.
- Report the measured pace per take beside the reference wpm. A hook running much faster than the body is normal (the
  diamond hook ran 171 wpm against 138).

## Cost (Creator plan, eleven_v3)
About 0.44 credits per character (ElevenLabs' quote on 2 Oct 2026; ~0.55 in September). A 13-minute GEMS episode is
~10,400 narration characters plus two extra hook takes (~640), about 4,900 credits. Quote characters and credits
before rendering, and say if the balance won't cover it: an empty balance stops the render between takes (HTTP 401
quota_exceeded), keeping the takes already bought.
