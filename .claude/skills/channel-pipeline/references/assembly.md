# Phase 5: Assembly, review and gates

Order: script passes → voice is rendered → pick the shots → review sheets → render segments → master with gates → look
at the master.

## Picking shots: `tools/illustrate.py pick <ep>` → `shots/shots.json`
- **Claude picks every shot by eye** (house rule 2, 7 Oct 2026: Gemini only for what Claude can't do). Draw contact
  pages per topic (`tools/cpages.py`), look inside candidate scenes (`peek.py`, `tools/strip.py`), pin every beat with
  `tools/pins.py` (`apply`, `split`), dry-run with `pincheck`, then `pick`, which makes no model calls when every beat
  is pinned and refuses unpinned beats. GEMS 005 Diamond, 006 Pearl and 007 Green were picked this way. Grep any old
  `cache/yt/<id>.captions.json` files as a search index when they exist.
- **Beat windows** come from the forced alignment (`vo/words.json`), so a shot starts on the first word of its beat.
- **Matching (history: GEMS deleted this code on 7 Oct 2026, "Don't use it to look at the images at all"):** for `key: want` beats, Gemini ranked captioned scenes against the spoken sentence (the top 120 by
  keyword overlap are listed), and candidate frames are verified against the sentence only until one passes; the rest
  of the beat is taken from the ranked list and logged RANKED (6 Oct 2026, measured: 1.4 checks a beat instead of 3.6).
  Matches and verifications are cached on disk, so an interrupted pick resumes and a re-pick of a delivered episode is
  identical. `pick <ep> --dry` counts the uncached calls first and writes nothing. If the API is down, matching falls
  back to local caption ranking, tagged LOCAL and unverified. Check the log for LOCAL, UNVERIFIED and RANKED lines; the
  eye review of the shot sheets is the quality gate either way.
- **Pins** are reserved up front, so no earlier beat can take them. `@offset` starts inside the scene.
- **Layout** (`tools/shots_layout.py`): about one cut every 3 s, and **a shot ends when its scene runs out**. Equal
  slices used to freeze 39 jade shots on their last frame. The picker keeps adding scenes until the footage covers the
  beat.
- **Cards** are placed from the alignment of their `on:` anchor, never from line boundaries. A lower third holds about
  2.5 s and a price about 1.8 s. Each price card adds the ka-ching to the sfx list unless it has `style: black`.
- **Crops** from `crop.json` are stamped onto every shot and grid tile, so the segment hash changes with them.

## Dry-run the pins: `tools/pincheck.py <ep>` (free; the guard flags it, so use the marker inside an approved build)
For every pinned beat it prints which scene and offset each sub-shot gets. It flags:
- **FREEZE:** the scene runs out before the sub-shot ends. Add a scene.
- **BLACK@t:** blackdetect hits on the exact slice, using the master's thresholds. A stone on a black studio background
  trips it like a fade does, so start after it (`@offset`) or pick another scene.
- **REPEAT:** the pins ran out and a scene starts over. Add a scene.
- **unused:** more pins than the beat needs. This is harmless.
Fix until it reports 0.

## Review sheets: `tools/review.py <ep>` → `shots/review_NN.jpg`
- Twelve shots a sheet, each showing its first and last frame with the crop applied, the words spoken over it, and the
  cards that fire. **Read every sheet before rendering.**
- After a re-cut, use `review.py <ep> --changed <snapshot shots.json>` to draw only the changed shots.
- Things only eyes catch:
  - a presenter appearing 3 s into a scene
  - a scene dissolving to something else
  - another auction house's room
  - burned-in captions and watermarks
  - a pale stone under the words "bright green"
  - a fade to white
  - a counter overlay
- Split a line between two shots when its two halves need different pictures (`pins.split`). The narration stays word
  for word, and the tool refuses otherwise.

## Render: `tools/assemble.py`
- **Segments:** `assemble.py <ep> --stage segments --limit 60`, looped until "remaining 0".
  - Each shot is rendered to an exact frame count on the 1/30 s grid.
  - Segments are cached by content (duration plus shot content, not absolute times), so a timeline shift re-renders
    almost nothing.
  - Grids overlay tiles in reading order.
  - Stills get one continuous push.
- **Master:** `assemble.py <ep>` concatenates the segments and muxes the untouched voice (stream copy into the mix). It
  sums the sfx (and a bed, only if `bed.json` exists) with `amix normalize=0` in one AAC 320k encode. Then the gates
  run:
  - `GATE sync: segments sum to X vs timeline Y`: fails over 0.05 s. Segments rounded one by one once drifted 1.6 s
    behind the voice.
  - `GATE black frames: none`: blackdetect `d=0.06:pix_th=0.08:pic_th=0.97`.
- `--no-bed --out …` builds a music-free version from the same segments in about a minute.
- **Look at the master.** Grab 15-20 frames at the hook, the grid, price flashes, lower thirds, the payoff and the outro
  (`ffmpeg -ss t -frames:v 1`). Confirm cards are on their words.

## Running long jobs
- The safe default for long stages (downloads, segment batches) is foreground slices under 10 minutes (`timeout 590`,
  `fetch_batch --budget 540`, `--stage segments --limit 30-60`). A memory watchdog has killed background jobs in
  earlier sessions.
- Where background jobs survive (they did for 40-minute runs on 30 Sep), run them with a log. Wait with an until-loop on
  the finishing line, and match failure lines too, not just success.
- Every stage is idempotent and resumable: cached downloads, captions, matches, segments and voice takes. A rerun after
  a crash never re-buys or re-renders work already done.
- Use `python -u` when piping, or buffered output is lost on a timeout.

## Re-cuts and edits of a finished episode
1. Snapshot `script.md` and `shots/shots.json` first.
2. Change only shot tags, never narration, using `tools/pins.py` (`apply`, `split`). It refuses any change to the
   narration or cards, and `python tools/pins.py <ep>` confirms the script still matches the voiced words.
3. Run `pincheck`, then `pick` (fully pinned, so no API calls), then diff the shots against the snapshot to prove the
   untouched beats didn't move.
4. Run `review --changed`, render (the segment cache makes this fast), and pass both gates.
5. Re-run metadata if the credits changed, re-deliver and commit.
Text edits that change narration re-voice only the takes whose text changed (`takes.json` pins the boundaries).
