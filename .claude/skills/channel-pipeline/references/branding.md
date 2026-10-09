# Phase 6: Branding: thumbnails, titles, descriptions, channel page

## Thumbnails
1. **Measure the reference's thumbnails before designing.** Look at the hits against the flops: background (white beat
   black 11x on the Astro reference), the number of objects, text or none, colours, where the light falls, and how big
   the subject is at feed size. Labels are unreadable at feed size (Patrick reference), so don't rely on small text.
   - ⚠ **Compare within a channel, and don't credit the picture for the topic** (Astro, 1 Oct 2026). Across 624
     genre videos, each compared with its own channel's neighbours, picture simplicity (empty space, detail,
     regions, colours, file complexity) predicted nothing. Every within-channel correlation was under 0.05.
   - Near-identical thumbnails landed 60–350x apart (Ridddle 2.2M vs 35K; Darkness Beyond 3.0M vs 8.4K), and the
     topic separated the hits. Method and tools: `Astro/reference/thumbs_study/THUMBNAILS.md`.
   - To test a thumbnail, use YouTube Studio's Test & Compare: up to three thumbnails on one video, judged by watch
     time share. Views alone can't isolate the thumbnail.
2. **Build a template, then hold it.** Once a thumbnail performs, the user makes it the template. GEMS, 28 Sep: "the
   ruby thumbnail performed well. make all future thumbnails as much like the ruby thumbnail as possible".
   - The ruby set: rough stone in its host rock → one loose cut stone → the finest stone in a big gold ring standing
     upright. A dark slate table with a visible back edge, a warm glow in the top-right corner, and the same places and
     sizes every time.
   - Pills read white → gold `#F0C355` → glowing green `#12E814`, cheap end $1-100 and top ≥ $500,000. No other words.
3. **Generate from the reference image itself**, so only the objects change.
   `GEMS/tools/thumb.py ruby "<left>" "<centre>" "<right>" raw.png` sends the ruby image as the reference (Gemini flash
   image model, about $0.07 an image, a spend). The objects go in `episodes/<ep>/thumb/objects.json`.
   - Then `thumb.py pills` adds the price pills at the measured object centres.
4. **Gate it with numbers, then eyes.** `tools/thumb_like.py` compares against the template: light map, mean, near-black
   share, corner glow and edge density. It must print LIKE RUBY. Then check by eye that each pill sits under its object.
   - Astro's equivalent gate is `lib/thumbgate.js`.
5. Never regenerate an approved thumbnail unless the user asks for the picture itself to change. Pill and text problems
   are fixed in the overlay pass.
6. Thumbnail generation is a Gemini spend. When the balance is empty (402), deliver the video and say the thumbnail
   follows the top-up. Never fake the template with a different method.

## Titles
- Copy the reference's proven title pattern exactly, e.g. "Every {Material} Type Explained". The title must reflect
  what the video actually contains.
- Topic choice uses the measured topic gate from the reference's hits. GEMS: a one-word precious material with a
  six-figure-plus record price. Patrick: a topic you can name in a word.
- A/B titles and thumbnails start from the same template and change the objects or words, never the set.

## Description, tags, credits: `tools/metadata.py <ep>` → `episodes/<ep>/upload info.txt` (Notepad .txt)
- Input: `episodes/<ep>/description.json` with:
  - `intro`, with `{n}` and `{list}` filled from the script's items
  - `discover`, one paragraph of the episode's best real hooks
  - `keywords`, a sentence of search phrases
  - `hashtags`
  - `tags`, about 30
  It refuses to run without the file: one episode's keywords once leaked into the next upload.
- Credits: every YouTube source actually used appears as "Channel youtu.be/ID", and every photo as "Author, licence,
  commons.wikimedia.org/?curid=N", deduped. The music credit appears only if a bed was used.
- YouTube limits:
  - the description is capped at 5,000 bytes, which metadata.py enforces and shortens credits to meet
  - `<` and `>` are rejected
  - tags total at most 500 characters by YouTube's count (multi-word tags count extra)
- The upload file lists the title, description (paste as is), tags, category and notes. The user pastes from it.

## Channel page (once per channel)
- Banner, avatar, channel name and handle, and the channel description as a plain .txt. Built once from the reference's
  measured style (GEMS keeps these in `channel/`).
- Studio trap from the zayin channel: the account can hold several channels, so confirm which channel Studio is on
  before the user uploads or edits anything.

## Delivery
- `upload/<Title>/` at the top of the project folder holds `<Title>.mp4`, `thumbnail.jpg` and `upload info.txt`.
- Byte-compare the delivered video with the render (`cmp`).
- Variants sit beside the main file, e.g. `<Title> (no music).mp4`.
- The user uploads. Never upload, schedule or publish unless that channel has a publisher the user set up, and then
  prove it live.
