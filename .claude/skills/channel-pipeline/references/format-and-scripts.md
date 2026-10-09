# Phase 2: Format spec and scripts

Turn the measured teardown (`analysis.md`) into rules a script can be checked against. Then write each episode's script
to them. The house rules on writing (15-21) apply on top of whatever the reference does.

## From measurements to rules
1. Every rule in the channel's CLAUDE.md points at evidence in ANALYSIS.md: a measured number, a hit-vs-flop contrast, or
   a direct user decision with its date. No rule from taste alone.
2. Translate measurements into gates in `tools/script_check.py`, the GEMS file being the model.
   **FAILS** block the voice render. Keep them to format facts the reference shows:
   - word range (per runtime)
   - item count and words per item
   - CTA position (percentage of the way through)
   - zero questions, where the reference uses none
   - contractions per 100 words (≥ 2.5 in GEMS)
   - uncontracted forms
   - numbers written as words (TTS reads digits better)
   - every card's `on:` anchor spoken verbatim inside its beat
   - every beat has a shot
   **WARNS** are advisory, for craft signals such as value or picture sentences in an item, price closers and sentence
   length. Never make a writing device a FAIL or a per-item quota (house rule 18).
3. Keep register rules that came from the user above measured ones. In GEMS the 17 Sep sentence-length and number caps
   were suspended after the user called a rewrite to those caps "disjointed and awkward". Flow by ear beats the counts.
4. Length: let the material decide inside the user's range. GEMS long format is ~1,900-2,400 words for 11-15 minutes
   (`script_check.py --words 1900-2400`). Several scripts landing on the same length is a warning sign.

## Script file format (GEMS `script.md`, parsed by `tools/script_check.py`)
```
# Every Diamond Type Explained

## OPEN
[shot: pin: yOO5-RTTAF4#35 | none] There's a kind of diamond that glows red in the dark after UV
[shot: pin: yOO5-RTTAF4#34@1.4 | none] light hits it.
[shot: blue: the Hope Diamond close up | none] {price: $2.44 | POSTAGE | style: black | on: $2.44} {price: $1,000,000 | INSURANCE | on: a million dollars} with $2.44 in postage and a million dollars of insurance.
[shot: grid: vid#n; vid#n@1.0; footage/stills/x.jpg; key: what the tile must show; … | none] That's just one of twelve types of diamond, and it isn't even the most expensive one.

## ITEM 1 | Industrial Diamonds
[shot: industrial: dark, cloudy rough industrial diamonds | none] {lower: Industrial Diamonds} Industrial diamonds are …
```
- One line is one beat. Everything outside `[shot: …]` and `{…}` is narration. The narration is the concatenation of all
  beats, so splitting a line between two shots changes nothing that is voiced.
- Shot tags:
  - `key: what the frame must show` is matched against the captions of the sources under that key in `sources.json`;
    `key+key` searches several keys, `any` searches everything.
  - `pin: vid#n, vid#n@offset` is hand-picked scenes.
  - `still: footage/stills/x.jpg` is a sourced photo, given one continuous push.
  - `grid: …` is the N-type grid; tiles fill in top left to bottom right, 3×3 up to nine and 4×3 beyond.
  - `montage: key: want; key: want` is one quick cut per entry.
  - The motion after `|` is `none`, `push`, `pull`, `pan_l` or `pan_r`.
- Cards:
  - `{lower: Name}` is the item's lower third. Fire it on the item's name, the first time it is spoken.
  - `{price: NUM | UNIT | on: spoken anchor}` is the green price flash plus ka-ching. `style: black` before `on:` gives
    black digits with no sound, for the smaller number of a pair.
  - Also `{big: …}`, `{counter: N | text}`, `{stat: N | text}`, `{timeline: a | b}`, `{callout: …}`.
  - The anchor must be the exact spoken words (plural and possessive endings are accepted).
- Sections: `OPEN`, a framing section (e.g. "WHAT MAKES X VALUABLE"), `ITEM n | Name`, `CTA`, optional `PAYOFF`,
  `OUTRO`.

## The GEMS skeleton (price-ladder "Every X Type Explained", reference Rio Rogan)
1. **Hook:** two or three snappy sentences about ONE type, the coolest true thing about it. It ends on, or opens with,
   the type's name, so "That's just one of N types of X, and …" points back at a type. That line runs over the grid of
   all N types. Show the user hook options before voicing; they pick, and often rewrite, a line. Use their wording
   verbatim.
   Rules the user gave after weak hooks:
   - describe a numbered type, never a one-off specimen
   - never present the category's defining property as news
   - age is not value
   - every clause needs a consequence
   - an event can be evidence inside the hook, never its last word
2. **Frame:** at most three plain mechanism sentences (what sets the price), then "Let's go through all N, starting with
   the cheapest."
3. **Items:** ascending by value. Each is framed by value and prestige: who buys it, the famous stone, the auction house,
   the record per unit. Science gets one plain sentence, and only when it explains the price.
   - Every per-unit price gets a `{price}` flash.
   - Items close on a value line often, not always.
4. **CTA at 50-65%,** welded to a tease of what's coming ("four of the last five have sold for millions a carat").
5. **Payoff:** "And now, back to where we started." That item names the hook's type and adds something new rather than
   repeating the hook.
6. **Outro bookend:** "So from <cheapest, price> to <top, price>, there's a lot more to X than <the everyday one>."

Other channels use other skeletons, measured from their own references:
- Otto: a one-sentence from-to hook.
- Astro: white-card ranked lists.
- Ancestral Stories: a concept-led register with zero named researchers.
Measure; don't import GEMS's.

## Writing checklist (run on every draft)
- Read it aloud. Use contractions and spoken joins, and keep the small words. Nothing telegraphic.
- Never "it's not X, it's Y", in any wording (house rule 17a). Say what the thing IS.
- Payload first, one piece of scaffolding at most before the verb, never two dates in one sentence, few names.
- Digits for numbers. "about $820", not "about eight hundred and twenty dollars". TTS and cards both need digits.
- Ties between sections only where they are real. No device on every item.
- Every card anchor is spoken in its beat. Every price that is per unit has a price card.
- Facts: each number traces to FACTS.md with a source. Unverified claims are out, including a competitor's numbers
  (check theirs; they are often wrong).
- `script_check.py` passes, then show the hook options and quote the voice cost.

## FACTS.md
- One section per topic area. Each claim carries a source name and date, plus a short quote where wording matters.
- Mark doubtful numbers UNVERIFIED and keep them out of the script.
- Note what the reference video got wrong, so we don't repeat it. For example, the diamond reference's "$350 million
  Hope" was an estimate and its "Le Vian is a mining company" was wrong.
- Research can run in parallel subagents, one per topic area. They return sourced claims and you verify them.
- Never make the user review FACTS.md.
