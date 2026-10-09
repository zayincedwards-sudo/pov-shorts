# when-free: design notes (handoff, 7 Oct 2026)

Goal (user, 7 Oct 2026): a skill that looks at everything running (all work runs locally in Claude Code
terminal windows), estimates how long each task has left, and says when the PC is free enough to start
something new.

Status: BUILT and live-tested 7 Oct 2026 (scripts/when_free.py scan + plan + index, SKILL.md). These notes are the
research it was built from; SKILL.md "How the scan knows" is the maintained summary.

## Machine
i7-11800H 8C/16T, 15.7 GB RAM, Intel UHD only (no GPU counters). Python 3.13; psutil 7.2.2 installed 7 Oct.
Claude Code native at ~/.local/bin/claude.exe. Transcript timestamps are UTC; local is PDT (UTC-7).
Measured 7 Oct ~11:40: 23 claude.exe windows alive (4.5 GB working set), RAM 13.2/15.7 GB used, 2.6 GB
free, pagefile 10.8 GB in use. RAM binds as much as CPU.

## Data sources (all verified on this machine)
- ~/.claude/sessions/<pid>.json: pid, sessionId, cwd, startedAt (ms), procStart (Windows FILETIME:
  epoch = int/1e7 - 11644473600; compare with psutil create_time to reject recycled PIDs), kind
  (interactive|bg), name, status (busy|idle|waiting|shell), statusUpdatedAt (= busy-since), waitingFor
  ('input needed'), jobId (bg), parkedJobId (interactive window parked into a daemon job; its 'busy' is
  stale). NEVER read the *.key files there (peer tokens).
- status alone is not trustworthy: POLITICAL BOY and GEMS (pid 25380) said 'busy' from 8.6 days ago
  (parked). Cross-check CPU, transcript mtime and the job.
- ~/.claude/jobs/<jobId>/state.json (bg sessions): state (working|blocked|done), detail (plain-English
  current step), tempo, inFlight{tasks,kinds}, fan[{id,kind,label,startedAt}], needs (what the user must
  do), intent (the request), output.result. timeline.jsonl: {at,state,detail} per step.
- Daemon pty hosts: `claude.exe --bg-pty-host <pipe> .. -- claude.exe --session-id <uuid> ..` (parent
  dead) host bg sessions: attribute to that session. `claude.exe daemon run` (supervisor) and
  `--chrome-native-host` are infrastructure.
- Transcripts: ~/.claude/projects/<sanitized cwd>/<sessionId>.jsonl (2.7 GB total, GEMS bg 947 MB): read
  tails only. Subagents: <sessionId>/subagents/agent-<id>.jsonl + .meta.json {agentType, description}.
  Every entry carries cwd + timestamp.
  - `system` subtype `turn_duration` {durationMs, messageCount, timestamp, cwd} = finished turn lengths.
  - bg launch: tool_use input.run_in_background:true; tool_result "running in background with ID: X.
    Output is being written to: %TEMP%\claude\<proj>\<sid>\tasks\X.output".
  - completion: `<task-notification><task-id>X</task-id><tool-use-id>..</tool-use-id><output-file>..
    </output-file><status>completed|failed|killed</status><summary>..</summary>`, also inside
    `queue-operation` entries' content. Monitor events carry <event> instead of <status>.
  - `last-prompt` {lastPrompt}; `custom-title` / `agent-name` entries.
- ~/.claude/history.jsonl: every typed prompt {display, timestamp ms, project, sessionId}: the latest
  request per window, cheaply.
- %TEMP%\claude\<proj>\<sessionId>\tasks\*.output: bg task stdout (17-hex ids = subagent transcripts,
  hard-linked).
- psutil Process.open_files() (~0.2 s each) names the log a detached job writes (transcribe_episodes.py ->
  MAN ON\shorts\work\_transcribe.log); Bash-tool shells show their bg .output file.
- Every Bash-tool shell: `bash.exe -c "source ~/.claude/shell-snapshots/snapshot-bash-<ms>-<rand>.sh ..
  && eval '<cd .. && the command>' < /dev/null && pwd -P >| .."`. <ms> is ~1-2 min after the session's
  startedAt (MAN ON 1791350601687 vs snapshot 1791350696219) -> match a live in-tree shell using the same
  snapshot, else the nearest startedAt within ~5 min. The eval'd text is the original command (cd dir,
  redirects).
- Detached jobs lose their Claude parent (`(python x.py > log 2>&1 &)`): MAN ON's python 36620 -> bash
  40600 -> dead. Attribute by snapshot ts -> session; else search transcript tails for the script name;
  else the cwd folder vs session names.
- Windows parent PIDs get recycled: accept a parent only if its create_time <= the child's.
- Exclude pid 0 (System Idle) from CPU sums (it once gave 151%).
- The user's own scheduled tasks (actions under the home dir, not \AppData\Local\Microsoft):
  com.pulluptape.publisher (every 5 min), com.talarico.publisher (5 min), com.memescanner.publisher
  (30 min), CAR DEALS daily (12:00). Get-ScheduledTask + Get-ScheduledTaskInfo + Repetition.Interval via
  powershell takes ~2 s: run it during the CPU sample.
- Stuck processes seen: review_all.py (pov-pipeline-handover\meme_scanner, 22 days, 521 MB committed,
  parent dead); ytown.py auth (CLIPPING, 19 h, waiting on a sign-in). Report them; never kill unasked.

## Design
scripts/when_free.py
- `scan`: sample per-process CPU over ~5 s (cpu_times delta / wall / ncpu) plus working set and private
  bytes; build session trees (+ pty hosts); attribute orphans; skip this window (an ancestor of
  os.getpid()). For each ACTIVE item gather evidence: the request (history.jsonl / job intent),
  busy-since, job detail, the last 2 assistant texts, any pending foreground tool, running bg tasks +
  output tails, active subagents (mtime < 10-30 min and not ended) with type, description and active
  time, work processes (CPU, RAM, age, command) with open-file log tails (last 6 lines, \r-collapsed),
  parsed progress (tqdm `a<b`, `ETA hh:mm`, N/M, N of M, %, ffmpeg time= vs Duration) and history hints.
  Other lists: waiting on you (status waiting, job blocked + needs), idle windows (RAM held, close to
  free it), stale busy / parked, stuck processes (alive, ~0 CPU for hours), scheduled jobs, other load.
  Save data/last_snapshot.json.
- History index data/history_index.json, incremental by file offset, newest files first, with a time
  budget: turn_duration list; bg tasks (launch -> first notification, keyed by task id, command
  signature = script basenames); subagents (active time = sum of gaps, excluding gaps that follow an
  end_turn, i.e. paused for the owner), median by agentType. Hints: agent median - active; same-script
  bg median - elapsed; turn-history median conditional on elapsed.
- `plan --eta N=best[-late]` (35m-55m, 1h20m, done, never) `[--cpu 50 --ram 3]`: a timeline of the CPU
  and RAM freed as each item ends (an item frees its tree CPU and work-process RAM, not the claude.exe,
  which stays open); room for new work = the first time CPU <= 50% and >= 3 GB is free; say plainly when
  RAM frees only by closing idle windows, and by how much.

SKILL.md: run scan; for each active item set best/late from progress first (look up a missing unit
total with at most 1-2 small reads, e.g. the script's list or the log head), add the heavy steps left in
the window's own plan, cross-check the history hints; run plan; answer with a bold lead (clock time +
duration) and a few sentences: what holds the machine, what ends when, what waits on the user, what to
close. No bullet rundown. Spends nothing, changes nothing.

## Live case for the first test (7 Oct ~11:46)
MAN ON transcribe_episodes.py: six masters, one at a time; ep12 490 s, ep6 519 s, ep2 365 s done by
11:46; ~6 cores and 3.1 GB. After it, the clipping-pipeline agent cuts a first batch (more CPU).
