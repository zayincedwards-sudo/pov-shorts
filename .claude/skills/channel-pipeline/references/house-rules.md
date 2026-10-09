# House rules: the user's standing orders for every video project

These came from the user directly, most of them as corrections. They apply to every channel unless that channel's own
CLAUDE.md records a different, explicit choice by the user. Sessions started in other folders do not load the memory
these came from, so this file is the copy that travels. Dates are 2026.

## Money and permissions

1. **Warn before ANY Gemini or ElevenLabs spend** (22 Sep: "ALWAYS warn me before you spend ANY gemini or 11labs
   credits"). Say what will run, how many calls, characters, seconds or images, and the expected cost. Then wait for an
   explicit yes. This is the one deliberate exception to rule 11.
   - A PreToolUse hook enforces it: `~/.claude/hooks/credit-guard/credit_guard.py`. In auto mode it denies the command.
     After the user's yes, re-run the SAME command prefixed `CREDITS_OK=1`. In PowerShell that is `$env:CREDITS_OK=1; …`.
   - Never add the marker pre-emptively, never on a "probably fine", and never for a different command than the one
     approved. Never work around the guard by splitting a call into a form it cannot see.
   - How the guard decides:
     - It skips read-only commands entirely: `cat`, `sed`, `grep`, `ls`, `cp`, `mv`, `mkdir`, `git`, `ffmpeg`,
       `ffprobe`, and PowerShell's `Get-Content` and `Copy-Item`, among others. Copying a toolkit or reading a file
       never trips it.
     - For any other command, it scans the command text itself, heredocs and `python -c` included.
     - It also scans every script the command names (`.py`, `.js`) and those scripts' local imports, looking for paid
       endpoints and model ids.
   - So free work gets blocked when:
     - a free tool, or a module it imports, names a model id (review → assemble; pincheck → shots_build; a scorer whose
       comment named the model);
     - a heredoc that patches voice code contains a model id;
     - a shell loop merely names such a file.
   - The fixes:
     - keep model ids out of tools that make no calls;
     - patch code with the Edit or Write tools;
     - test whether files exist with Glob.
     Inside a build the user already approved, a free command it flags may run with the marker.
   - A call refused with HTTP 402 (Gemini prepaid balance empty) or 400 is not charged. Say so, and tell the user to
     top up at ai.studio/projects. A 402 never becomes a reason to cache a failure (see assembly.md).
2. **Gemini: Claude first, then the cheapest model** (7 Oct: "every time anything uses Gemini, I want it to use the
   cheapest version possible. And I also don't want to use Gemini if I can just use Claude tokens to achieve the same
   thing."). This replaces the 17 Sep rule "no flash-lite model except for image generation".
   - **Never use Gemini to look at images** (7 Oct, later: "just use Gemini for the thumbnails from now on. Don't use it
     to look at the images at all."). Captioning, filtering, ranking, matching and checking frames, contact sheets,
     thumbnails or photos is Claude's job. In GEMS Gemini makes the thumbnail and nothing else; its picking, listening
     and music code was deleted. A channel whose picture is generated (zayin panels, SAM, Ollie video) still generates
     on the cheapest model unless the user says otherwise.
   - Order for any other job: a free local tool → Claude doing it in the session (reading, writing, judging) → the
     cheapest Gemini model that can do it → a pricier model only when the user names it.
   - Cheapest models (pricing read 7 Oct): `gemini-3.1-flash-lite-image` for making images (0.034 USD each);
     `gemini-2.5-flash-lite` for reading text or audio when Claude can't (0.10 / 0.40 USD per 1M tokens) with
     `thinkingConfig.thinkingBudget: 0`; Veo 3.1 Lite for video; `lyria-3-clip-preview` for music. Batch mode halves
     any of them.
   - Thinking is billed as output: it was about 70% of GEMS's Gemini bill on 3 and 6 Oct (Gemini 3.5 Flash with default settings,
     ~1,550 thinking tokens on every call). Always send the thinking budget explicitly.
   - If the cheapest model fails the project's gate, ask before stepping up a tier.
   - The credit guard refuses any other Gemini, Veo, Imagen or Lyria model at spend time, even with `CREDITS_OK=1`;
     `MODEL_OK=1` is only for a model the user asked for by name. On 7 Oct it flagged 22 scripts in MOVIE THEORY,
     ANIME, Ollie, SAM, Astro and Patrick: each window switches its own code when the guard stops it.
3. **Never push and never add a git remote unasked.** Never publish, post or upload unasked either. The user uploads the
   videos themselves unless they have set up a publisher for that channel.
   - A YouTube delete is permanent: set a video private and let the owner delete it.
   - Scheduled tasks are installed by the owner.
   - Never kill `chrome.exe` globally; it is the user's browser too.
   - The account holds several YouTube channels: confirm which one Studio is on before any upload work.
3a. **Cost before and after** (Astro rule 41). Before a purchase, quote it and say whether a free route exists. After
    it, report what was actually bought (characters, images, calls), mistakes included.

## Files and delivery

4. **Everything lives in the project folder the user names.** Never temp, never the scratchpad, and never a parallel
   folder. The finished deliverable goes at the TOP of the project folder, never buried in a pipeline subfolder. GEMS
   uses `upload/<Title>/`, which holds the video, the thumbnail and `upload info.txt`.
5. **Every document meant for the user is a plain `.txt`** (22 Sep: "needs to be openable in notepad. all future text
   docs as well"). That covers upload info, descriptions, checklists and reports. Use UTF-8, CRLF line endings, upper-case
   underlined headings and "- " bullets, with no `**`, backticks or fences. Copy `GEMS/tools/textdoc.py` (`write_txt`,
   `plain`). Markdown is only for files Claude reads: CLAUDE.md, ANALYSIS.md, FACTS.md and scripts.
6. **Every project is a git repo, and every conversation's work gets committed** (18 Sep: "gitify EVERY CONVERSATION
   from now on. EVERY NEW PROJECT."). The gitify hook (`~/.claude/hooks/gitify/`) inits repos and makes
   "Checkpoint: <prompt>" commits at each turn end. Still commit logical units yourself, with a sentence subject, an
   explanatory body and the Co-Authored-By trailer.
   - Write `.gitignore` early. The repo tracks the pipeline, not its output: code, specs, docs and small assets that are
     costly to remake.
   - Keep out renders, downloads, frames, other creators' transcripts and `.env` (`assets/gitignore.template`).

## Voice (ElevenLabs)

7. **Never process the narration file ElevenLabs returns.** No trim, pad, loudnorm, compressor, re-encode or EQ. Join
   takes losslessly (`ffmpeg -f concat -c copy`), re-time the picture to the voice, and encode once at the mux.
   - Request the best output format the plan allows (Creator: `mp3_44100_192`).
   - Additions such as a price-flash sfx or a music bed are only ever summed onto the untouched voice at unity, at the
     final mux (`amix normalize=0`), and only when the user asked for them on that channel.
   - The user turned music on (22 Sep) and off again (30 Sep: "remove music from all future videos"). The default is no
     music.
   - ⚠ Astro is the one channel where the user asked for denoising and ducking. Never carry that anywhere else.
8. **Send the voice's own stored settings** (18 Sep, "across every project"). Fetch them with the free
   `GET /v1/voices/<id>/settings`, and keep a hardcoded set only as the fallback.
   - No atempo; the runtime follows the voice.
   - Never re-render an approved take without asking: a re-render is a different performance.
   - The user picks the voice. Start with free library previews, and render a paid A/B of short samples only if they
     want to hear real lines (quote it first). Never render samples unprompted.
9. **v3 behaviour.** Fuzz tracks chunk length: write paragraphs of 150-450 characters, one take each. Over 900
   characters, 70% of takes came back fuzzy.
   - v3 refuses `previous_text`/`next_text` with HTTP 400. Don't offer neighbouring-text context as a v3 fix.
   - **Every hook is bought three times**, and the take closest to the voice's normal sound is kept (30 Sep). Use
     `GEMS/tools/takescore.py`, which scores boxiness, pitch swing, word clarity and air against approved takes. Keep
     the other two as `_alt` files so the user can swap by ear.
   - Never judge a hook by the high-frequency "fizz" metric.
10. **A flat read comes from the script, not the voice.** Few contractions, spelled-out numbers and fragments make TTS
    sound flat. Write spoken English with digits, fold fragments into sentences, and keep continuity on where the model
    allows it.
    - **No commas around a short aside** (1 Oct: "take the comma out of 'you, standing still'. its making the voice
      sound awkward"). The voice stops at every comma. Write the aside into the sentence ("from you standing still to
      a galaxy") or give it its own sentence.

## Process

10a. **Two question rounds per video, then do all the work** (6 Oct: "This is getting ridiculous… Ask me all of the
     questions and then do all of the work."):
     - Round 1 is the topic.
     - Then do everything free: research, script, sourcing, plan, dry run and thumbnail options.
     - Round 2 is ONE AskUserQuestion call holding every remaining choice: the hook parts, the thumbnail and the
       voice purchase with its quote.
     - Then build, review, deliver and commit without asking again.
     - A vague pick ("scary", "whatever you want") means write the best true version and go; never re-ask.
11. **No review gates** (11 Sep: "i trust you. dont make me do that again"). Verify facts yourself into FACTS.md, then keep
    building through voice, visuals and assembly. Stop only for things that are genuinely the user's call: spending,
    publishing, deleting, or a creative pick they asked to make. Hooks are one such pick: show options and wait.
    - **How each object in the hook is described is picked first, every video** (1 Oct: "give me a few options for the
      descriptions of objects in the hook. do this for every future video before making anything."). Before any
      sourcing, planning or voice, ask one AskUserQuestion question per object the hook names, with three or four
      verified descriptions each and today's wording as one of them. Build the hook from the picks word for word.
12. **Measure against the reference, never against your own output.** Transcribe the reference videos and read them
    whole. Print a draft's measurements beside the reference's. When several drafts land at the same length, treat it as
    a warning sign, not a success (user: "why are they all the same length? … DO NOT use the videos you make as a
    framework").
13. **Prove fixes live.** After fixing anything unattended, such as a publisher or scheduler, show an end-to-end run with
    real evidence before resuming other work.
14. **Reports.** End a job with what was done, where it lives and the next command. When asked to recap, cover only the
    latest topic, as one bold lead plus two or three short plain sentences, with no bullets.
14a. **Asked for one fix, make one fix** (Astro, 18 Sep: "just pick better pictures DONT CHANGE ANYTHING ELSE"). Attach
     no extras to a requested change. Offer improvements separately, in one line.
14b. **Offer choices; don't make the user's creative calls.** A new video "starts with a CHOICE": offer topics, keep
     the unpicked ones in `IDEAS.md`, show hook options, and offer 3 thumbnail options when a template is being set.
     When the user rewrites a line, use their wording verbatim.
14c. **Recommend with the evidence; options must be concrete** (6 Oct: "I haven't done the research, so I shouldn't
     really be the one to tell you. You should be telling me that you think it's a good idea, why you think it's a
     good idea, and then I'll decide if you're right"). After a teardown, propose the actual channel: the videos,
     their titles, objects, thumbnails and order, each with its measured reason, then stop for the yes or the
     correction. Never a menu of categories ("shape A", "size", "odds"); every option is a thing they can picture.

## Writing (every script, every channel)

15. **Conversational, never academic.** The register is "a 20 year old college student talking about something they are
    passionate about". Use contractions wherever natural, and spoken connective tissue at the joins ("here's the
    thing", "look", "so", "actually"). Punchlines and reveal lines stay clean.
    - The audience is largely kids and teens: could a fourteen-year-old retell the sentence to a friend?
16. **Payload first.** The wild fact opens the sentence, with at most one piece of scaffolding (place, credential, year)
    before the verb. Never put two clocks in one sentence.
    - Names: roughly five per episode at most, and only when the person is a character. Otherwise "scientists found".
    - Deliver the thumbnail's promise within about a minute of the hook. A tangent that doesn't serve it makes people
      click off.
17. **No telegraphic lines** (24 Sep, "ALL SCRIPTS across ALL PROJECTS"). Keep the small words a person says. "Rain in,
    fountain out." becomes "As the rain falls in, fountains of gas shoot out." Snappy means short sentences, not stripped
    ones. Over a word budget, cut a whole idea, never the grammar words.
17a. **Never "it's not X, it's Y"** (5 Oct: "never use 'its not blank its blank' in a video script. apply to all
     conversations"). It counts in any pronoun, tense or punctuation, in one sentence or two: "That's not a bug, that's a
     feature.", "It wasn't luck. It was physics.", "He was never a king, he was a cook." So do "it's not just X, it's Y",
     "it doesn't just X, it Y" and the fragment form ("Not a rock. A time capsule.").
     - Say what the thing IS. Usually that means dropping the "not X" half: "This wasn't frenzy. This was careful, skilled
       work." becomes "This was careful, skilled work." Where the surprise matters, put it in the claim: "It isn't one
       stone, it's two." becomes "It's actually two different stones."
     - A concession is a different shape and stays ("it's not cheap, but it's worth every penny"), and so does a plain
       negative fact on its own.
     - `script_check.py` fails on it. A new channel that copies the GEMS tools gets `its_not_its`; a checker written from
       scratch copies it from `GEMS/tools/script_check.py`. A scan on 5 Oct found it 42 times in finished scripts and
       descriptions (30 in zayin), so old scripts are not models for this. Future scripts only.
18. **Never every item** (21 Sep: "i NEVER want things to apply to every item"). A device (tie, callback, tease,
    comparison, moving picture, annotation) is used where the material calls for it. Never record it as a per-item
    template slot, a quota or a count. Things the user asked for on every item BY NAME stay, such as a price flash on
    every per-unit price.
19. **Story, not disparate facts, but only real ties.** Where two sections share a mission, place, cause or time, say it
    in a clause. Elsewhere, nothing. Never write a filler bridge ("Next up…", "But that's nothing compared to…").
20. **On-screen text is spoken text.** A card appears the moment its first word is spoken and holds until the next word
    after the phrase begins, both read from forced alignment. If a phrase is never said, it never goes on screen.
21. **Facts are real.** Verify every number against sources in FACTS.md and mark the unverified ones UNVERIFIED, then keep
    them out. Hooks use real, observed facts, never speculation ("Something that might not be real is less exciting than
    something that is").
