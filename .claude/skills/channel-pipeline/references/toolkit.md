# The toolkit: GEMS is the reference implementation

`C:\Users\admin\Downloads\GEMS\tools\` is the most complete pipeline the user has: real footage, ElevenLabs, ffmpeg,
cards, thumbnails and metadata. A real-footage channel starts from a copy of it; other formats pick another base (next
section). Known-good state is the commit tagged `skill-kit` in the GEMS repo (1 Oct 2026). If a later change breaks
something, `git -C /c/Users/admin/Downloads/GEMS show skill-kit:tools/<file>` recovers it. Run every tool from the
project root: several open `cache/yt/...` by relative path.

## Choosing and copying the base toolkit (Phase 2, after the teardown)
1. **Pick the base that matches the measured format,** not GEMS by default:
   | Format | Base |
   |---|---|
   | real footage, long form, price or list explainers | GEMS `tools\` (this file) |
   | white cards plus sourced stills and recordings, Node | Astro `lib\` and its build |
   | drawn or animated scenes, mascot | Otto `Patrick\v2\tools\` |
   | generated-image panels | zayin `episodes\_engine\` |
   | vertical Shorts from footage, unnarrated | `CLIPPING\shorts\`, `TALARICO\shorts\` |
   | narrated vertical Shorts | none exists yet: GEMS with `W, H` in `assemble.py` set to 1080×1920, cards re-laid out, and Otto's `shorts.py` for 9:16 framing |
   Mixed formats borrow parts (`references/other-channels.md`, "Borrow these").
   **Strip any voice processing from the base you copy** (house rule 7):
   - Astro `lib\vo.js`: DeepFilterNet, the pause ducker, the peak-ceiling gain and the limiter. These were Astro's
     user-asked exception and are wrong anywhere else.
   - Otto `vo.py` and `build.py`: loudnorm and sentence-gap trims, which predate the rule.
   - zayin: `debreath.js`, `decut.js`, `retempo.js`.
   - GEMS: `assemble.py` now refuses its legacy mix (anything but `audio: voice_only`), and `vo.py`'s old trim helper is
     gone.
2. **Copy** with `cp -r` (e.g. `cp -r /c/Users/admin/Downloads/GEMS/tools ./tools`). `cp` is on the credit guard's
   read-only list, so it passes and needs no yes. Also copy:
   - `assets/fonts`
   - only the `assets/sfx` the format uses
   - an empty `assets/tts_map.json` (`{}`)
   Do NOT copy `assets/voice_profile.json` (Brad's), `assets/thumb/` (the ruby template), `assets/music/` or any
   `.env`. The user pastes the keys into the new `.env` themselves.
3. **Strip what is GEMS-only before the first build** (the list below). Watch the hardcoded values:
   - `build_episode.py`: the voice id and the price ladder
   - `illustrate.py`: the caption prompt says "gemstones"
   - `vo_qa.py`: the name list
   - `metadata.py`: its title parsing
4. **Chunking:** GEMS `vo.py` makes takes from whole sections (up to 4,900 characters, the hook alone).
   `join_takes` assumes every take holds whole sections. House rule 9's 150-450-character paragraphs need beat-level
   takes: port the chunker from Astro `lib\vo.js`, or extend `plan_takes` and `join_takes` together. Until then, a
   new channel accepts section-sized takes knowingly.
5. **Hook-take profile:** with no profile for the new voice, `vo.py` voices the body first and scores the three hook
   takes against a provisional profile built from those body takes. After the first approved episode, build the real
   one from the project root:
   `python tools/takescore.py --profile episodes/<ep>/vo/take_01.mp3 … --voice "<name> <voice_id>"`. The voice id must
   appear in `--voice`, because that is how `vo.py` recognises the profile as this voice's.

## One episode, end to end (`tools/build_episode.py <ep> [--from S] [--to S] [--words a-b] [--prices '$5,$5,000,$1,000,000']`)
Before the build, the human steps:
- topic through the topic gate
- hook options shown to the user
- `FACTS.md`, `script.md`, `description.json`, `thumb/objects.json`
- `footage/keys.json` → `scout.py` → hand-curated `sources.json`
- the cost quote and the user's yes
| # | stage | does | cost |
|---|---|---|---|
| 1 | check | `script_check.py`; aborts on any FAIL | $0 |
| 2 | fetch | yt-dlp ≤ 720p, meta, scene split, frames and contact sheet for the first ids per key | $0 (guard flags it) |
| 3 | filter | `scene_filter.py` blacklist, one Gemini call per source | Gemini |
| 4 | captions | `illustrate.py captions`, one Gemini call per source | Gemini |
| 5 | voice | `vo.py <ep> <voice_id> eleven_v3`: hook ×3 plus takes, joined losslessly | ElevenLabs |
| 6 | pick | `illustrate.py pick`: alignment beats, pins, Gemini match and verify, layout, cards, sfx, crops | Gemini (per beat) |
| 7 | segments | `assemble.py --stage segments --limit 60`, looped | $0 |
| 8 | master | concat, mux, GATE sync, GATE black frames | $0 |
| 9 | thumb | `thumb.py ruby` → pills → `thumb_like.py` | ~$0.07 an image |
| 10 | metadata | `metadata.py` → `upload info.txt` | $0 |
| 11 | deliver | `upload/<Title>/`: video, thumbnail (if it exists), upload info | $0 |
Between voice and segments, run the QA loop: `vo_qa.py`, `pincheck.py`, `review.py`, then fixes (pins, crops,
blacklist), then re-pick.

## Tools
| tool | purpose | usage | paid? | generic? |
|---|---|---|---|---|
| build_episode.py | driver | above | via stages | GEMS voice id, price ladder and ruby thumb are hardcoded |
| scout.py | yt-dlp search per key | `<ep> <keys.json>` | no | generic |
| footage.py | download, scenes, sheet, clip, rank | `fetch <id>…`, `sheet`, `clip <id> <n> <out>`, `rank` | rank: Gemini | generic |
| fetch_batch.py | time-boxed fetch | `<ep> [--budget 540] [--per-key 3] [--key k=N]` | no | generic |
| scene_filter.py | blacklist title cards, presenters, text, screens | `<ep>` / `--ids …` | Gemini | generic |
| illustrate.py | captions + pick | `captions <ep>`, `pick <ep> [--max-shot 3.0]` | Gemini | caption prompt says "gemstones"; ka-ching path hardcoded |
| shots_build.py | library: `find_phrase`, `beat_windows`, `bad_for` | — | — | generic |
| shots_layout.py | shot ends when its scene ends | library | no | generic |
| pins.py | write pins/splits; refuses any narration or card change; `pins.py <ep>` checks against the voiced words | library + check | no | generic |
| script_check.py | parser + gates | `<script.md> [--words a-b]` | no | parser generic; gates tuned to GEMS |
| vo.py / el.py | narration, stored settings, hook ×3 | `vo.py <ep> <voice> [model]`, `--join-takes` | ElevenLabs | generic (hook needs a section named OPEN) |
| takescore.py | pick the best hook take | `t1.mp3 …`, `--profile [files] [--voice "name id"] [--to path]` | no | profile is per voice |
| vo_qa.py / listen.py | Whisper diff; Gemini ear | `<ep> [--ear]` | `--ear`: Gemini | name list is GEMS-specific; the guard flags vo_qa even without `--ear` (it imports listen.py) |
| cards.py | HTML → PNG cards via headless Chrome | `render spec.json out.png`, `demo` | no | renderer generic, CSS is GEMS's look |
| assemble.py | segments + master + gates | `<ep> [--stage segments --limit N] [--no-bed] [--out]` | no | generic, 1920×1080 at 30 fps |
| review.py | review sheets | `<ep> [--changed snapshot.json]` | no (flagged) | generic |
| peek.py / pages.py / cpages.py | look at scenes | `vid#a-b vid#n@t` / `<id>` / `<name> <id>…` | no | generic |
| pincheck.py | FREEZE / BLACK / REPEAT dry-run | `<ep>` | no (flagged) | generic |
| bars.py | baked-in bars → crop entries | `<ep> [--write]` | no | generic (dark scenes give false hits) |
| commons.py / still.py | Commons search, download, credit; photo → still | see sourcing.md | no | generic |
| thumb.py / thumb_like.py | template thumbnail + gate | `ruby "<l>" "<c>" "<r>" raw.png`, `pills raw out p1 p2 p3` | Gemini image | GEMS template |
| thumb_ideas.py | concept / A-B thumbnails from the template | `<ep> 2,3,4` | Gemini image | written for opal |
| metadata.py | upload text, credits, limits | `<ep>` | no | parses "Every X Type Explained" and "ITEM n \| Name" |
| textdoc.py / env.py | Notepad .txt writer; quiet .env loader | library | no | generic |
| bed.py | Lyria music / ElevenLabs sfx | `music "<p>" out`, `sfx "<p>" out` | yes | generic (no music by default) |
| register.py / delivery.py | script register and voice delivery against the reference | — | no | reference data is GEMS's |
| channel.py | channel avatar and banner | `build` | no | GEMS |

**What to rewrite for a new format:**
- `script_check.py` thresholds and word lists, measured from the new reference
- the section names (OPEN, ITEM, CTA)
- the voice id and voice profile
- the `vo_qa` name list
- the caption prompt's topic
- the card CSS
- the whole thumbnail system: reference image, template, overlay and `thumb_like` limits
- `metadata.py`'s title parsing and layout
- `description.json` content

## Data files (examples in `GEMS/episodes/005-diamond/`)
- `footage/keys.json`: `{"blue": ["Hope Diamond Smithsonian", "Oppenheimer Blue diamond auction"]}`.
- `footage/sources.json`: `{"blue": ["yOO5-RTTAF4", "HW2Us7p1aSU"]}`, in order of priority.
- `footage/scout.json`: `{"key": [{"id","title","dur","views","ch"}]}`.
- `cache/yt/<id>.*` holds the files for one source:
  - `.mp4` and `.meta.txt` (`title|channel|duration|licence`)
  - `.scenes.json` (`[{n,t0,t1,len}]`)
  - `.sheet.jpg` and `_frames/NNN.jpg`
  - `.bad.json` (`{"bad":[…]}`) and `.captions.json`
  - `.crop.json`
- `shots/shots.json`: `{"voice","audio","shots":[{t0,t1,kind:clip|still|card|grid,src,in,motion,crop,crop_x,crop_y,tiles}],"overlays":[{t0,t1,card}],"sfx":[{t,src,db}]}`.
- `vo/`:
  - `words.json` (`[{w,s,e,sec}]`) and `sections.json`
  - `takes.json` (`[[0],[1,2,3,4,5],…]`)
  - `take_NN.mp3` with `.align.json` and `.hash`
  - `take_00_hook.json` and `take_00_alt1/2.mp3`
- `description.json`: `intro` (`{n}`, `{list}`, `{material}`), `discover`, `keywords`, `hashtags`, `tags`, optional
  `ab_tests`.
- `thumb/objects.json`: `{"left": "rough … in host rock", "centre": "one loose cut …", "right": "… in a heavy polished
  gold ring, standing upright"}`.
- `bed.json` (episodes 001-004 only): `{"track":"Lobby Time","under_db":17,"fade_across":"grid"}`.
- Still credit `<still>.jpg.txt`: `file | author | licence | https://commons.wikimedia.org/?curid=N`.

## Dependencies
- **Python 3.13** with urllib only (no SDKs), Pillow, numpy, and faster-whisper (`small.en`, CPU int8).
- **yt-dlp** and **ffmpeg/ffprobe** on PATH.
- **Chrome** at `C:/Program Files/Google/Chrome/Application/chrome.exe`, run headless, for cards.
- **`.env` key names:** `ELEVENLABS_API_KEY`, `GEMINI_API_KEY`, `GEMINI_IMAGE_MODEL` (optional). Never print their
  values.
- The Commons API needs a User-Agent.
- The user-level hooks apply to every project: credit-guard and gitify.
