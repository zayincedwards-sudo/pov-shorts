---
name: when-free
description: Tells the user when this PC will be free again. Measures every Claude Code window, background job, subagent, child process, detached job and scheduled task on the machine, works out how long each piece of running work has left (from its own progress logs, the window's stated plan, and how long similar work took before), and turns that into the clock time there is room to start something new, plus what is waiting on the user and what could be closed to free memory. Use whenever the user asks when the computer, PC, laptop or machine will be free, how long the running windows, projects, tasks or jobs will take, what is eating CPU or RAM, why the computer is slow, whether they can start a new project now, or types /when-free.
---

# When will this PC be free?

All of the user's work runs locally in Claude Code terminal windows (interactive windows and daemon
background jobs) and in what those windows start: subagents, background shells, detached Python and ffmpeg
processes, and the Windows scheduled publishers. This skill measures all of it, estimates the time each
piece has left, and answers with a clock time.

It reads the process table and local files only. It spends nothing, changes nothing, and never kills a
process or closes a window. If something should be closed, say so and leave it to the user (or ask first).

## Steps

1. **Scan** (about 20 s):
   `python ~/.claude/skills/when-free/scripts/when_free.py scan`
   It samples CPU for 5 s and prints the machine line (CPU, RAM, pagefile), then ACTIVE WORK (numbered
   items with their evidence), WAITING ON YOU, IDLE WINDOWS, STUCK PROCESSES, SCHEDULED JOBS and OTHER
   LOAD. It saves `data/last_snapshot.json` for step 3. The window running the skill is left out.

2. **Estimate each ACTIVE item's time left**, a best case and a late case, using the evidence in this order:
   - Progress the work prints itself: a log tail with N of M, a percentage, a progress bar or an ETA. When
     the log counts finished units but not the total, find the total with at most two small reads (the
     script's own list, the command's arguments, the head of the log, or what the window said it would
     do). Time left = units left x average time per finished unit.
   - The window's plan: the "said ... ago" lines, the request and the job intent. Add the heavy steps that
     come after the current one (renders after a transcription, uploads after renders).
   - History as a cross-check: the "script guess" line and the "past ... agents: median" figures come from
     the user's own transcripts (finished turns, background tasks and subagent runs).
   - Future load: if the next steps are heavy (ffmpeg renders, Whisper, big downloads), give the CPU the
     item will hold until it ends with `@` (e.g. `@40`); otherwise its current CPU is used.
   Never open whole transcripts. Make the late case genuinely late; these runs overrun more than they
   underrun.

3. **Plan**:
   `python ~/.claude/skills/when-free/scripts/when_free.py plan --eta 1=25m-45m --eta 2=10m-20m@35 --eta 3=done`
   Each item is `N=best[-late][@cpu%]`, or `done` / `never`. Free means CPU at or under 50% and at least
   3 GB of RAM free (`--cpu`, `--ram` to change; use what the user says they need, e.g. Whisper wants most
   of the CPU and ~3 GB). It prints the timeline, the best and late "room for new work" times, and how much
   RAM closing the idle windows would free.

4. **Answer** in the user's recap format: one bold lead with the clock time and how long from now ("Room
   for new work at about 1:40 PM, in 35 minutes"), then a few short sentences, no bullet rundown:
   - what is holding the machine and when each big piece ends;
   - what is waiting on the user (sign-ins, questions, windows stopped at the usage limit): these never
     finish by waiting;
   - when RAM is the limit, the biggest idle windows and stuck processes they could close and roughly how
     much that frees (name a few, not all of them).
   Times are local clock times. Don't paste the scan; the user wants the answer.

## Priority (user, 7 Oct 2026: "this task to finish quickly" without the other tasks stopping)

Every run of `when_free.py` raises its own process to High priority and drops the other claude, python,
ffmpeg, node and bun processes to Below Normal, then puts each back to its original priority when it exits
(`boost()` / `unboost()` in the script). Nothing is paused or killed; the other work just yields the CPU
for the ~20 s of the scan. Run the steps straight through with no detours, so the answer arrives fast.

## How the scan knows (for fixing it later)

- Windows: `~/.claude/sessions/<pid>.json` (status busy/idle/waiting/shell, busy-since, jobId, parkedJobId).
  PIDs are checked against `procStart` so a recycled PID is never mistaken for a window. The `*.key` files
  there hold peer tokens: never read them.
- Background jobs: `~/.claude/jobs/<jobId>/state.json` and `timeline.jsonl` (state, detail, needs, intent).
- Labels go stale: parked windows say busy for days, jobs stopped by the usage limit still say working,
  and something touches every transcript's modified time. So "active" needs live evidence: a conversation
  entry in the last 15 min, a background task output written in the last 30 min, a subagent that wrote in
  the last 10 min (30 with a tool still open), or a work process using CPU or started in the last 30 min.
- A window whose last words are a usage-limit message is listed as waiting on the user.
- Detached jobs (`(python x.py > log 2>&1 &)`) outlive their shell's parent. Each Claude shell's command
  line names the session's shell snapshot (`snapshot-bash-<ms>-...`), which ties the job back to its
  window; failing that, a scheduled task's folder, then a folder named like the window.
- Logs: a process's open files (`psutil.open_files`) name the log it writes; only logs written since it
  started are shown.
- History: `data/history_index.json`, built incrementally from every transcript (the first build takes
  10-30 s): finished turn lengths, background-task run times by script name, and subagent work time by
  agent type (silence after end_turn or over 20 min is not counted as work).
- CPU percentages are of the whole machine (16 threads = 100%). The System Idle Process is excluded and
  the scan's own window is subtracted.
