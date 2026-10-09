---
name: what-to-use
description: Picks the Claude model (Haiku, Sonnet, Opus, Fable) and effort level (Low, Medium, High, Extra) a task should run on, from the task itself and the user's remaining plan usage (5-hour and weekly limits) and how fast it is being used this week, then asks one yes/no question ("Switch to Haiku at Low effort for this task?"). Yes runs the task on that model and effort; No carries on with the current model. Use whenever the user's prompt starts with or contains "what to use", "which model", "what model should I use", "which effort", or they type /what-to-use, with the task in the same prompt.
---

# What to use

The user types `/what-to-use <task>` (or "what to use: <task>"). Answer with ONE yes/no question, then do
the task. Keep the deciding part quick and cheap: one script call, no long deliberation, no other reads.

## 1. Read the budget

`python ~/.claude/skills/what-to-use/scripts/what_to_use.py`

It prints the 5-hour and weekly limits (used %, reset time, pace, where each lands at reset), a day-by-day
trend once the log has history, one BUDGET level (plenty / ok / tight / critical), and THIS WINDOW's
model and effort. If it says there is no data yet, decide from the task alone.

## 2. Pick the model and effort

Size the task first, then let the budget move it:

| Task | Pick |
|---|---|
| Quick: a question, a lookup, a status check, renaming or moving files, a one-line fix, a short summary | Haiku, Low |
| Routine: a script or single-file change, a tidy-up, a document or notes in the user's rules, a simple web lookup | Sonnet, Medium |
| Substantial: multi-file builds and debugging, pipeline or episode work, careful scripts in the user's house rules, research with judgement | Opus, High |
| Hardest: a new channel teardown or pipeline design, deep multi-source research, long agentic builds where a mistake costs hours | Fable, High (Opus, Extra when Fable's budget is tight) |

- plenty: as in the table.
- ok: as in the table.
- tight: one step cheaper, effort first (High -> Medium), then the model; never below what the task needs.
- critical: the cheapest model that can plausibly do it, and say in the question's description that the
  limit is nearly gone.
- Never suggest Max effort unless the user asks for it.

If the pick is the same model and effort the window already runs on, skip the question: say "Your current
<model> at <effort> fits this task" in one line and do the task.

## 3. Ask one question

Use AskUserQuestion with exactly two options, question text in this shape:
"Switch to Haiku at Low effort for this task?"
- "Yes, switch": description = the reason in a few words, e.g. "quick file move; weekly limit 64%, on pace for ~91% by Sat 4 PM".
- "No, keep <current model>": description = "carry on with <model>, <effort>".

## 4. Do the task

- **No:** do the task now, here, on the current model, as if the user had typed it without the prefix.
- **Yes:** start one subagent with the Agent tool: `subagent_type: effort-<low|medium|high|xhigh>`,
  `model: <haiku|sonnet|opus|fable>`, and a prompt holding the user's task word for word plus what it
  needs from this conversation (the working folder, files and decisions already made). It runs in the
  background on that model and effort. Tell the user in one line that it is running there, then end the
  turn. When it reports back, pass its report on briefly; don't redo or re-check its work on this model.
  Follow-up prompts in this window go back to the window's own model unless the user asks again.

Why a subagent: Claude Code does not let a skill switch a window's model mid-conversation (the built-in
`/model` is a UI command only the user can run, and a skill's `model:` frontmatter only applies when the
user types that skill's command). A subagent started with `model` plus an effort agent does run on the
chosen model and effort; this was tested on 7 Oct 2026.

## How it knows (for fixing it later)

- `scripts/statusline.py` is the status line of every window (settings.json `statusLine`). Claude Code
  pipes it `rate_limits.five_hour` / `rate_limits.seven_day` (`used_percentage`, `resets_at` epoch
  seconds), `model` and `effort.level` on each redraw. It writes `data/usage.json`, appends changes to
  `data/usage_log.jsonl` (with the window id), and records each window's model and effort in
  `data/windows/<session8>.json`. One window once reported a stale low weekly figure (21% against 64%),
  so the advisor takes the highest reading of the last 15 minutes.
- The effort agents are `~/.claude/agents/effort-*.md` (copies in `agents/` here). They only set
  `effort:`; the model comes from the Agent call. A `CLAUDE_CODE_EFFORT_LEVEL` environment variable
  overrides every effort setting (the user's was `max`, removed 7 Oct 2026 at their request); if efforts
  stop applying, check that it hasn't come back.
