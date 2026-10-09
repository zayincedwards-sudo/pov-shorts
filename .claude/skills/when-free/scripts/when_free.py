#!/usr/bin/env python
"""when-free: when will this PC be free again?

  scan   snapshot every Claude window, background job, child process and detached job; gather the
         evidence for how long each piece of work has left; print it; save data/last_snapshot.json
  plan   turn remaining-time estimates into the clock time the machine has room again
           plan --eta 1=35m-55m --eta 2=10m          (best-late; also: done, never)
  index  build or refresh the history index on its own (scan refreshes it within a time budget)

Reads local files and the process table only: spends nothing, changes nothing, kills nothing.
Never reads ~/.claude/sessions/*.key (peer tokens).
"""
import argparse
import base64
import collections
import datetime as dt
import glob
import json
import os
import re
import statistics
import subprocess
import sys
import time

try:
    import psutil
except ImportError:
    sys.exit("when-free needs psutil:  python -m pip install psutil")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HOME = os.path.expanduser("~")
CLAUDE = os.path.join(HOME, ".claude")
SESSIONS = os.path.join(CLAUDE, "sessions")
JOBS = os.path.join(CLAUDE, "jobs")
PROJECTS = os.path.join(CLAUDE, "projects")
PROMPTS = os.path.join(CLAUDE, "history.jsonl")
SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(SKILL, "data")
INDEX = os.path.join(DATA, "history_index.json")
SNAP = os.path.join(DATA, "last_snapshot.json")


def _temp_claude():
    for base in (os.environ.get("TEMP"), os.environ.get("TMP"), os.path.join(HOME, "AppData", "Local", "Temp")):
        if base and os.path.isdir(os.path.join(base, "claude")):
            return os.path.join(base, "claude")
    return os.path.join(HOME, "AppData", "Local", "Temp", "claude")


TEMP_CLAUDE = _temp_claude()
NOW = time.time()

SHELLS = {"bash.exe", "sh.exe", "cmd.exe", "powershell.exe", "pwsh.exe", "conhost.exe", "openconsole.exe",
          "winpty-agent.exe"}
UTILS = {"grep.exe", "tail.exe", "sleep.exe", "timeout.exe", "cat.exe", "head.exe", "sed.exe", "awk.exe",
         "gawk.exe", "find.exe", "tee.exe", "wc.exe", "sort.exe", "uniq.exe", "xargs.exe", "ls.exe", "date.exe",
         "git.exe", "rg.exe", "less.exe", "cut.exe", "tr.exe", "env.exe", "nohup.exe", "ping.exe", "choice.exe"}
WORK = {"python.exe", "pythonw.exe", "py.exe", "ffmpeg.exe", "ffprobe.exe", "ffplay.exe", "node.exe", "yt-dlp.exe",
        "whisper.exe", "whisper-cli.exe", "magick.exe", "sox.exe", "java.exe", "deno.exe", "bun.exe", "uv.exe",
        "npx.exe", "aria2c.exe", "curl.exe", "wget.exe", "7z.exe", "handbrakecli.exe", "blender.exe",
        "rclone.exe", "gallery-dl.exe", "tesseract.exe"}
BROWSERS = {"chrome.exe", "msedge.exe", "chromium.exe", "headless_shell.exe", "firefox.exe"}
TEXT_EXT = (".log", ".txt", ".out", ".output", ".err", ".csv", ".jsonl", ".progress")
MEDIA_EXT = (".mp4", ".mkv", ".mov", ".webm", ".wav", ".mp3", ".m4a", ".aac", ".flac", ".png", ".jpg", ".ts",
             ".part", ".opus", ".avi")
SKIP_FILE = re.compile(r"\\windows\\|\\program files|\.(dll|mui|sdb|clb|exe|pyd|nls|ttf|ttc|otf|ico|cur|db|"
                       r"db-wal|db-shm|ldb|lock|pak|bin|dat)$", re.I)
RX_SNAP = re.compile(r"snapshot-(?:bash|zsh|sh)-(\d{12,14})-")
RX_SID = re.compile(r"--session-id\s+([0-9a-f-]{36})")
RX_SCRIPT = re.compile(r"([\w.-]+\.(?:py|pyw|sh|ps1|js|mjs|cjs|ts|cmd|bat))\b", re.I)


# ---------------------------------------------------------------- small helpers

def fdur(s):
    if s is None:
        return "?"
    s = max(0, int(round(s)))
    if s < 90:
        return "%ds" % s
    m = (s + 30) // 60
    if m < 100:
        return "%dm" % m
    h, m = divmod(m, 60)
    if h < 48:
        return "%dh%02dm" % (h, m)
    return "%dd%dh" % divmod(h, 24)


def fclock(t):
    lt = time.localtime(t)
    s = time.strftime("%I:%M %p", lt).lstrip("0")
    if time.strftime("%Y%j", lt) != time.strftime("%Y%j", time.localtime(NOW)):
        s = time.strftime("%a ", lt) + s
    return s


def iso2t(s):
    if not s or not isinstance(s, str):
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def gb(b):
    return "%.1f GB" % (b / 2 ** 30)


def mem(b):
    return "%d MB" % (b / 2 ** 20) if b < 2 ** 30 else gb(b)


def short(s, n):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def nice(p):
    if not p:
        return ""
    return "~" + p[len(HOME):] if p.lower().startswith(HOME.lower()) else p


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, separators=(",", ":"))
    os.replace(tmp, path)


def mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def tail_bytes(path, n):
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            fh.seek(max(0, size - n))
            return fh.read(), size > n
    except OSError:
        return b"", False


def tail_lines(path, n=8192):
    data, cut = tail_bytes(path, n)
    lines = data.decode("utf-8", "replace").splitlines()
    return lines[1:] if cut and lines else lines


ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def log_tail(path, n=6, nbytes=6000):
    """Last n readable lines of a log; progress bars that rewrite a line with \\r keep their last state."""
    data, cut = tail_bytes(path, nbytes)
    text = ANSI.sub("", data.decode("utf-8", "replace"))
    out = []
    for ln in text.split("\n")[1 if cut else 0:]:
        segs = [x for x in ln.split("\r") if x.strip()]
        if segs:
            out.append(segs[-1].rstrip())
    return [short(x, 170) for x in out[-n:]]


def median(xs):
    return statistics.median(xs) if xs else None


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def remaining_from(durs, elapsed, min_n=4):
    """Median and 80th-percentile time left, from past durations longer than what has already run."""
    longer = [d - elapsed for d in durs if d > elapsed]
    if len(longer) < min_n:
        return None
    return {"mid": median(longer), "late": pct(longer, 0.8), "n": len(longer), "of": len(durs)}


def parse_dur(s):
    """35m, 1h20m, 90s, 1:20 (h:mm), 0/done -> seconds; never/open -> None."""
    s = (s or "").strip().lower()
    if s in ("never", "open", "inf", "unknown", "?"):
        return None
    if s in ("0", "done", "now", "finished"):
        return 0.0
    m = re.fullmatch(r"(\d+):(\d\d)", s)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60.0
    m = re.fullmatch(r"(?:(\d+(?:\.\d+)?)h)?\s*(?:(\d+(?:\.\d+)?)m(?:in)?)?\s*(?:(\d+)s)?", s)
    if m and any(m.groups()):
        h, mi, se = (float(x or 0) for x in m.groups())
        return h * 3600 + mi * 60 + se
    raise ValueError("cannot read duration %r" % s)


def hms(s):
    parts = [float(x) for x in s.split(":")]
    t = 0.0
    for x in parts:
        t = t * 60 + x
    return t


def iso_interval(s):
    m = re.match(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$", s or "")
    if not m:
        return None
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return (d * 86400 + h * 3600 + mi * 60 + se) or None


# ---------------------------------------------------------------- processes

def begin_sample():
    procs = {}
    for p in psutil.process_iter(["pid", "ppid", "name", "create_time"]):
        i = p.info
        if not i["pid"]:
            continue                                    # System Idle Process would add ~100%
        procs[i["pid"]] = {"pid": i["pid"], "ppid": i["ppid"] or 0, "name": (i["name"] or "").lower(),
                           "create": i["create_time"] or 0.0, "p": p, "cpu": 0.0, "cpu_total": 0.0,
                           "ws": 0, "priv": 0}
    t0 = {}
    for pid, d in procs.items():
        try:
            c = d["p"].cpu_times()
            t0[pid] = c.user + c.system
        except Exception:
            pass
    psutil.cpu_percent(None)
    return procs, t0, time.time()


def finish_sample(procs, t0, w0):
    machine = psutil.cpu_percent(None)
    wall = max(0.5, time.time() - w0)
    n = psutil.cpu_count() or 1
    for p in psutil.process_iter(["pid", "ppid", "name", "create_time"]):   # born during the sample:
        i = p.info                                                            # all their CPU is in it
        if i["pid"] and i["pid"] not in procs and (i["create_time"] or 0) >= w0 - 1:
            procs[i["pid"]] = {"pid": i["pid"], "ppid": i["ppid"] or 0, "name": (i["name"] or "").lower(),
                               "create": i["create_time"] or 0.0, "p": p, "cpu": 0.0, "cpu_total": 0.0,
                               "ws": 0, "priv": 0}
            t0[i["pid"]] = 0.0
    for pid, d in procs.items():
        try:
            c = d["p"].cpu_times()
            tot = c.user + c.system
            d["cpu_total"] = tot
            if pid in t0:
                d["cpu"] = max(0.0, (tot - t0[pid]) / wall / n * 100)
            m = d["p"].memory_info()
            d["ws"] = m.rss
            d["priv"] = getattr(m, "private", 0) or 0
        except Exception:
            d["gone"] = True
    return machine, n


def link_tree(procs):
    """Children map. Windows recycles PIDs, so a parent only counts if it started before the child."""
    kids = collections.defaultdict(list)
    for pid, d in procs.items():
        pp = d["ppid"]
        if pp and pp != pid and pp in procs and procs[pp]["create"] <= d["create"] + 1:
            d["parent"] = pp
            kids[pp].append(pid)
        else:
            d["parent"] = None
    return kids


def descendants(kids, pid):
    out, stack, seen = [], [pid], {pid}
    while stack:
        x = stack.pop()
        for k in kids.get(x, ()):
            if k not in seen:
                seen.add(k)
                out.append(k)
                stack.append(k)
    return out


def ancestors(procs, pid):
    out, d = [], procs.get(pid)
    while d and d.get("parent") and len(out) < 60:
        out.append(d["parent"])
        d = procs.get(d["parent"])
    return out


def cmdline(d):
    if "cmd" not in d:
        try:
            d["cmd"] = d["p"].cmdline() or []
        except Exception:
            d["cmd"] = []
    return d["cmd"]


def cmdtext(d):
    return " ".join(cmdline(d))


def cwd_of(d):
    if "cwd" not in d:
        try:
            d["cwd"] = d["p"].cwd() or ""
        except Exception:
            d["cwd"] = ""
    return d["cwd"]


def open_files(d):
    if "files" not in d:
        files = []
        try:
            for f in d["p"].open_files():
                if not SKIP_FILE.search(f.path):
                    files.append(f.path)
        except Exception:
            pass
        d["files"] = files
    return d["files"]


def automation_browser(d):
    if d["name"] not in BROWSERS:
        return False
    c = cmdtext(d)
    return "--remote-debugging" in c or "ms-playwright" in c or "--headless" in c


def proc_label(d):
    c = cmdline(d)
    name = d["name"][:-4] if d["name"].endswith(".exe") else d["name"]
    if name in ("python", "pythonw", "py"):
        for i, a in enumerate(c[1:], 1):
            if a == "-m" and i + 1 < len(c):
                return short("python -m " + " ".join(c[i + 1:i + 4]), 110)
            if a.lower().endswith((".py", ".pyw")) or (a.lower().endswith(".exe") and "scripts" in a.lower()):
                return short("python " + os.path.basename(a) + " " + " ".join(c[i + 1:i + 5]), 110)
        return "python (inline script)"
    if automation_browser(d):
        return name + " (automation browser)"
    args = [os.path.basename(x) if ("\\" in x or "/" in x) and len(x) > 40 else x for x in c[1:7]]
    return short(name + " " + " ".join(args), 110)


def shell_command(d):
    """The command a Claude Bash-tool shell was started for (the text inside eval '...')."""
    t = cmdtext(d)
    i = t.find("eval '")
    if i < 0:
        return None
    s = t[i + 6:]
    j = s.rfind("' < /dev/null")
    if j < 0:
        j = s.rfind("'")
    return (s[:j] if j > 0 else s).replace("'\\''", "'")


# ---------------------------------------------------------------- sessions, jobs, prompts

def load_sessions(procs):
    out = {}
    for f in glob.glob(os.path.join(SESSIONS, "*.json")):        # *.json only: the .key files hold tokens
        s = read_json(f)
        if not isinstance(s, dict):
            continue
        pid = s.get("pid")
        d = procs.get(pid)
        if not d or "claude" not in d["name"]:
            continue
        ps = s.get("procStart")
        if ps:
            try:
                if abs(int(ps) / 1e7 - 11644473600 - d["create"]) > 30:
                    continue                                       # recycled pid: a different process now
            except (TypeError, ValueError):
                pass
        out[pid] = s
    return out


def load_job(job_id):
    if not job_id:
        return None
    st = read_json(os.path.join(JOBS, job_id, "state.json"))
    if not isinstance(st, dict):
        return None
    tl = []
    for ln in tail_lines(os.path.join(JOBS, job_id, "timeline.jsonl"), 60000):
        try:
            tl.append(json.loads(ln))
        except ValueError:
            pass
    st["_timeline"] = tl
    return st


def job_working_since(job):
    since = None
    for ev in job.get("_timeline") or []:
        if ev.get("state") == "working":
            since = since or iso2t(ev.get("at"))
        else:
            since = None
    return since


def load_prompts():
    """Latest typed prompt per session id, from ~/.claude/history.jsonl."""
    last = {}
    for ln in tail_lines(PROMPTS, 3 << 20):
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        sid = e.get("sessionId")
        if sid and e.get("display"):
            try:
                ts = float(e.get("timestamp") or 0) / 1000
            except (TypeError, ValueError):
                ts = 0
            last[sid] = (ts, e["display"])
    return last


def transcript_path(sid):
    hits = glob.glob(os.path.join(PROJECTS, "*", sid + ".jsonl"))
    return max(hits, key=mtime) if hits else None


# ---------------------------------------------------------------- transcript tails

RX_BG = re.compile(r"running in background with ID: ([A-Za-z0-9_-]+)\. Output is being written to: (.+?\.output)")
RX_NOTE = re.compile(r"<task-id>([^<]+)</task-id>(.*?)</task-notification>", re.S)
RX_STATUS = re.compile(r"<status>(\w+)</status>")
END_STATES = {"completed", "failed", "killed", "stopped", "cancelled", "canceled", "error", "timeout"}


def tail_entries(path, want=150, start=1 << 20, cap=16 << 20):
    n = start
    while True:
        data, cut = tail_bytes(path, n)
        lines = data.split(b"\n")
        if cut:
            lines = lines[1:]
        ents = []
        for ln in lines:
            if ln.strip():
                try:
                    ents.append(json.loads(ln))
                except ValueError:
                    pass
        if len(ents) >= want or not cut or n >= cap:
            return ents
        n *= 4


def content_blocks(e):
    m = e.get("message")
    if not isinstance(m, dict):
        return []
    c = m.get("content")
    if isinstance(c, str):
        return [{"type": "text", "text": c}]
    return [b for b in (c or []) if isinstance(b, dict)]


def result_text(b):
    c = b.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text")
    return ""


def note_finished(text, finished):
    if "<task-notification>" not in text:
        return
    for m in RX_NOTE.finditer(text):
        s = RX_STATUS.search(m.group(2))
        if s and s.group(1).lower() in END_STATES:
            finished[m.group(1).strip()] = s.group(1).lower()


def is_prompt(text):
    t = text.lstrip()
    return bool(t) and not t.startswith(("<", "[Request interrupted", "Caveat:", "This session is being continued"))


def analyze(ents):
    """What a transcript tail says: last words, tool still running, background tasks not yet finished."""
    a = {"last_ts": None, "cwd": None, "texts": [], "pending": [], "bg": [], "todos": None, "prompt": None,
         "ended": False, "loop": False}
    uses, answered, bg, finished = {}, set(), {}, {}
    for e in ents:
        ts = iso2t(e.get("timestamp"))
        if ts:
            a["last_ts"] = ts
        if e.get("cwd"):
            a["cwd"] = e["cwd"]
        t = e.get("type")
        if t == "assistant":
            for b in content_blocks(e):
                bt = b.get("type")
                if bt == "text" and b.get("text", "").strip():
                    a["texts"].append((ts, b["text"].strip()))
                elif bt == "tool_use":
                    inp = b.get("input") or {}
                    uses[b.get("id")] = (ts, b.get("name") or "", inp)
                    if b.get("name") == "TodoWrite" and isinstance(inp.get("todos"), list):
                        a["todos"] = inp["todos"]
                    elif b.get("name") == "ScheduleWakeup":
                        a["loop"] = not inp.get("stop")
            a["ended"] = (e.get("message") or {}).get("stop_reason") == "end_turn"
        elif t == "user":
            for b in content_blocks(e):
                bt = b.get("type")
                if bt == "tool_result":
                    answered.add(b.get("tool_use_id"))
                    m = RX_BG.search(result_text(b))
                    if m:
                        u = uses.get(b.get("tool_use_id")) or (ts, "", {})
                        bg[m.group(1)] = {"id": m.group(1), "out": m.group(2), "ts": u[0] or ts, "tool": u[1],
                                          "desc": (u[2] or {}).get("description") or "",
                                          "cmd": (u[2] or {}).get("command") or ""}
                elif bt == "text":
                    txt = b.get("text", "")
                    note_finished(txt, finished)
                    if is_prompt(txt) and not e.get("isMeta"):
                        a["prompt"] = (ts, txt.strip())
            a["ended"] = False
        elif t == "queue-operation":
            note_finished(e.get("content") or "", finished)
    since = a["prompt"][0] if a["prompt"] else 0
    if not a["ended"]:
        a["pending"] = [u for k, u in uses.items() if k not in answered and (u[0] or 0) >= (since or 0)]
    a["bg"] = [v for k, v in bg.items() if k not in finished]
    return a


LIMIT_RX = re.compile(r"\b(usage|session|rate) limit\b|hit your limit|limit (?:was|has been) reached", re.I)


def hit_limit(a):
    """The last thing it said is a usage-limit stop: it will not go on until someone says continue."""
    return bool(a and a["texts"] and LIMIT_RX.search(a["texts"][-1][1][:600]))


def active_subagents(sid):
    out = []
    for f in glob.glob(os.path.join(PROJECTS, "*", sid, "subagents", "agent-*.jsonl")):
        mt = mtime(f)
        if NOW - mt > 30 * 60:
            continue
        a = analyze(tail_entries(f, want=80, start=512 << 10, cap=8 << 20))
        if a["ended"] or hit_limit(a):
            continue                                   # finished its run, stopped to ask, or died at the limit
        if NOW - mt > 10 * 60 and not a["pending"]:
            continue                                   # silent for 10 min with no tool running: not working
        meta = read_json(f[:-6] + ".meta.json") or {}
        out.append({"file": f, "id": os.path.basename(f)[6:-6], "type": meta.get("agentType") or "agent",
                    "desc": meta.get("description") or "", "mtime": mt, "a": a})
    return out


# ---------------------------------------------------------------- history index

RX_TS_B = re.compile(rb'"timestamp":"(\d{4}-\d\d-\d\dT[0-9:.]+Z)"')
RX_NOTE_B = re.compile(rb"<task-id>([^<]+)</task-id>(.*?)</task-notification>", re.S)
RX_STATUS_B = re.compile(rb"<status>(\w+)</status>")


def new_index():
    return {"v": 1, "files": {}, "turns": [], "bg": {}, "uses": {}, "agents": {}}


def load_index():
    idx = read_json(INDEX)
    return idx if isinstance(idx, dict) and idx.get("v") == 1 else new_index()


def index_line(idx, sid, ln, ag):
    if ag is not None:
        tsm = RX_TS_B.findall(ln)
        if tsm:
            ts = iso2t(tsm[-1].decode())
            if ts:
                if ag["first"] is None:
                    ag["first"] = ts
                if ag["last"] is not None:
                    gap = ts - ag["last"]
                    # silence after end_turn is waiting for the owner; silence over 20 min is a stop (a
                    # working agent writes at least every ~10 min, the foreground tool cap)
                    if 0 < gap <= 1200 and not (ag["ended"] and gap > 300):
                        ag["active"] += gap
                ag["last"] = max(ag["last"] or 0, ts)
        if b'"type":"assistant"' in ln:
            ag["ended"] = b'"stop_reason":"end_turn"' in ln
        elif b'"type":"user"' in ln:
            ag["ended"] = False
        return
    if b'"turn_duration"' in ln:
        try:
            e = json.loads(ln)
        except ValueError:
            return
        if e.get("subtype") == "turn_duration" and e.get("durationMs"):
            idx["turns"].append([sid, e.get("timestamp"), round(e["durationMs"] / 1000)])
        return
    if b'"run_in_background":true' in ln and b'"tool_use"' in ln:
        try:
            e = json.loads(ln)
        except ValueError:
            return
        for b in content_blocks(e):
            inp = b.get("input") or {}
            if b.get("type") == "tool_use" and inp.get("run_in_background"):
                idx["uses"][b.get("id")] = [e.get("timestamp"), (inp.get("command") or "")[:500],
                                            (inp.get("description") or "")[:140], sid]
        return
    if b"running in background with ID: " in ln:
        try:
            e = json.loads(ln)
        except ValueError:
            return
        for b in content_blocks(e):
            if b.get("type") == "tool_result":
                m = RX_BG.search(result_text(b))
                u = idx["uses"].pop(b.get("tool_use_id"), None)
                if m and u:
                    idx["bg"][m.group(1)] = {"launch": u[0], "cmd": u[1], "desc": u[2], "sid": u[3],
                                             "end": None, "status": None}
        return
    if b"<task-notification>" in ln:
        tsm = RX_TS_B.findall(ln)
        ts = tsm[-1].decode() if tsm else None
        for m in RX_NOTE_B.finditer(ln):
            r = idx["bg"].get(m.group(1).decode("utf-8", "replace").strip())
            s = RX_STATUS_B.search(m.group(2))
            if r and s and not r.get("end") and s.group(1).decode().lower() in END_STATES:
                r["end"] = ts
                r["status"] = s.group(1).decode().lower()


def index_file(idx, path, start, deadline):
    parts = os.path.normpath(path).split(os.sep)
    ag = None
    if "subagents" in parts:
        sid = parts[parts.index("subagents") - 1]
        ag = idx["agents"].get(path)
        if ag is None or start == 0:
            meta = read_json(path[:-6] + ".meta.json") or {}
            ag = idx["agents"][path] = {"type": meta.get("agentType") or "agent",
                                        "desc": (meta.get("description") or "")[:120], "sid": sid,
                                        "first": None, "last": None, "active": 0.0, "ended": False}
    else:
        sid = os.path.basename(path)[:-6]
    pos, partial = start, False
    with open(path, "rb") as fh:
        fh.seek(start)
        buf = b""
        while True:
            chunk = fh.read(16 << 20)
            if not chunk:
                break
            buf += chunk
            cut = buf.rfind(b"\n")
            if cut < 0:
                continue
            block, buf = buf[:cut + 1], buf[cut + 1:]
            for ln in block.split(b"\n"):
                if ln:
                    index_line(idx, sid, ln, ag)
            pos += len(block)
            if time.time() > deadline:
                partial = True
                break
    return pos, partial


def update_index(idx, budget_s):
    """Incremental: each transcript is read once, from where the last run stopped. Newest first."""
    deadline = time.time() + budget_s
    files = glob.glob(os.path.join(PROJECTS, "*", "*.jsonl")) + \
        glob.glob(os.path.join(PROJECTS, "*", "*", "subagents", "agent-*.jsonl"))
    stats = []
    for f in files:
        try:
            st = os.stat(f)
            stats.append((st.st_mtime, st.st_size, f))
        except OSError:
            pass
    stats.sort(reverse=True)
    left = 0
    for mt, size, f in stats:
        rec = idx["files"].get(f)
        if rec and rec.get("size") == size and not rec.get("partial"):
            continue
        if time.time() > deadline:
            left += 1
            continue
        start = rec.get("off", 0) if rec and size >= rec.get("size", 0) else 0
        if start == 0 and rec:
            sid = os.path.basename(f)[:-6]
            idx["turns"] = [t for t in idx["turns"] if t[0] != sid]
        try:
            off, partial = index_file(idx, f, start, deadline)
        except OSError:
            continue
        idx["files"][f] = {"size": size, "off": off, "partial": partial, "mtime": mt}
        if partial:
            left += 1
    cutoff = time.time() - 2 * 86400
    idx["uses"] = {k: v for k, v in idx["uses"].items() if (iso2t(v[0]) or 0) > cutoff}
    save_json(INDEX, idx)
    return left, len(stats)


def agent_history(idx, agent_type, exclude):
    durs = []
    for f, ag in idx["agents"].items():
        if ag.get("type") != agent_type or f == exclude or not ag.get("first"):
            continue
        if NOW - (idx["files"].get(f, {}).get("mtime") or 0) < 30 * 60:
            continue                                   # still running somewhere
        if ag.get("active", 0) >= 60:
            durs.append(ag["active"])
    return durs


def script_history(idx, script):
    durs = []
    key = script.lower()
    for r in idx["bg"].values():
        if r.get("status") == "completed" and key in (r.get("cmd") or "").lower():
            a, b = iso2t(r.get("launch")), iso2t(r.get("end"))
            if a and b and b > a:
                durs.append(b - a)
    return durs


def turn_history(idx):
    return [t[2] for t in idx["turns"] if t[2] and t[2] >= 30]


# ---------------------------------------------------------------- progress in a log

RX_TQDM = re.compile(r"\[(\d+:\d\d(?::\d\d)?)<(\d+:\d\d(?::\d\d)?)")
RX_ETA = re.compile(r"\bETA[:\s]+(\d+:\d\d(?::\d\d)?)", re.I)
RX_FRAC = re.compile(r"(?<![\w/.:-])(\d{1,6})\s*(?:/|\bof\b)\s*(\d{1,6})(?![\w/.:-])")
RX_PCT = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s?%")
RX_FF_TIME = re.compile(r"time=\s*(\d+:\d\d:\d\d(?:\.\d+)?)")
RX_FF_DUR = re.compile(r"Duration:\s*(\d+:\d\d:\d\d(?:\.\d+)?)")
# a bare N/M or N% only counts on a line that reads like progress (encoder stats are full of percentages)
RX_PROG_WORDS = re.compile(r"progress|complet|done|download|upload|render|encod|transcrib|process|frame|clip|file|"
                           r"item|episode|video|chunk|batch|part\b|step|segment|window|recipe|card|page|\[|\(|█|#{3}|={3}",
                           re.I)


def parse_progress(lines, elapsed):
    def extrap(frac, how, ln):
        left = elapsed * (1 - frac) / frac if elapsed and 0.02 < frac < 1 else (0 if frac >= 1 else None)
        return {"how": how, "frac": frac, "left": left, "line": ln}

    for ln in reversed(lines):
        m = RX_TQDM.search(ln)
        if m:
            return {"how": "progress bar", "left": hms(m.group(2)), "line": ln}
        m = RX_ETA.search(ln)
        if m:
            return {"how": "ETA in log", "left": hms(m.group(1)), "line": ln}
    dur = RX_FF_DUR.search("\n".join(lines))
    for ln in reversed(lines):
        m = RX_FF_TIME.search(ln)
        if m and dur and hms(dur.group(1)) > 0:
            return extrap(min(1.0, hms(m.group(1)) / hms(dur.group(1))), "ffmpeg time", ln)
        if not RX_PROG_WORDS.search(ln):
            continue
        m = RX_FRAC.search(ln)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if 0 < a <= b and b >= 2:
                return extrap(a / b, "%d/%d" % (a, b), ln)
        m = RX_PCT.search(ln)
        if m and 0 < float(m.group(1)) <= 100:
            return extrap(float(m.group(1)) / 100, m.group(1) + "%", ln)
    return None


def live_logs(d, since):
    """Text files a process has open that were written since it started (old error logs stay quiet)."""
    return [f for f in open_files(d) if f.lower().endswith(TEXT_EXT) and mtime(f) >= since - 60]


# ---------------------------------------------------------------- scheduled tasks

PS_TASKS = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ErrorActionPreference = 'SilentlyContinue'
$h = $env:USERPROFILE
$r = @(Get-ScheduledTask | Where-Object { $_.State -ne 'Disabled' -and $_.TaskPath -notlike '\Microsoft\*' } | ForEach-Object {
  $a = ($_.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join ' ; '
  if ($a -like "*$h*" -and $a -notlike '*\AppData\Local\Microsoft\*') {
    $i = $_ | Get-ScheduledTaskInfo
    [pscustomobject]@{
      name   = $_.TaskName
      state  = "$($_.State)"
      next   = $(if ($i.NextRunTime) { $i.NextRunTime.ToString('s') } else { '' })
      last   = $(if ($i.LastRunTime) { $i.LastRunTime.ToString('s') } else { '' })
      every  = ((@($_.Triggers | ForEach-Object { $_.Repetition.Interval }) | Where-Object { $_ }) -join ',')
      action = $a
    }
  }
})
ConvertTo-Json -InputObject $r -Compress
"""


def start_task_query():
    try:
        enc = base64.b64encode(PS_TASKS.encode("utf-16-le")).decode()
        return subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError:
        return None


TASKS_CACHE = os.path.join(DATA, "scheduled_tasks.json")


def finish_task_query(proc):
    """Scheduled tasks; under heavy paging PowerShell can take a minute, so fall back to the last good list."""
    data = None
    if proc:
        try:
            out, _ = proc.communicate(timeout=60)
            data = json.loads(out.decode("utf-8-sig", "replace").strip() or "[]")
            data = data if isinstance(data, list) else [data]
            save_json(TASKS_CACHE, {"at": time.time(), "tasks": data})
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            data = None
    stale = False
    if data is None:
        cache = read_json(TASKS_CACHE) or {}
        data, stale = cache.get("tasks") or [], True
    tasks = []
    for t in data:
        if not isinstance(t, dict):
            continue
        ivs = [iso_interval(x) for x in (t.get("every") or "").split(",") if x]
        ivs = [x for x in ivs if x]
        every = min(ivs) if ivs else None
        nxt = iso2t(t.get("next"))
        if stale and nxt and nxt < NOW:                    # roll a cached next-run forward
            nxt = nxt + -(-(NOW - nxt) // every) * every if every else (nxt + 86400 if nxt > NOW - 86400 else None)
        tasks.append({"name": t.get("name"), "state": "?" if stale else t.get("state"), "next": nxt,
                      "last": iso2t(t.get("last")), "every": every, "action": t.get("action") or "",
                      "cached": stale})
    return tasks


# ---------------------------------------------------------------- scan

def cmd_scan(args):
    procs, t0, w0 = begin_sample()
    time.sleep(max(0.5, args.sample))
    machine_cpu, ncpu = finish_sample(procs, t0, w0)
    task_q = start_task_query()                            # after the sample, so PowerShell isn't counted as load
    kids = link_tree(procs)
    vm, sw = psutil.virtual_memory(), psutil.swap_memory()

    sessions = load_sessions(procs)
    by_sid = {s.get("sessionId"): pid for pid, s in sessions.items()}
    me = next((a for a in ancestors(procs, os.getpid()) if a in sessions), None)

    trees = {pid: {pid, *descendants(kids, pid)} for pid in sessions}
    infra = {}
    for pid, d in procs.items():
        if pid in sessions or "claude" not in d["name"]:
            continue
        c = cmdtext(d)
        m = RX_SID.search(c) if "--bg-pty-host" in c else None
        if m and m.group(1) in by_sid:
            trees[by_sid[m.group(1)]].add(pid)            # daemon pty host of a background session
        elif not any(pid in t for t in trees.values()):
            infra[pid] = ("daemon" if " daemon " in c + " " else "Chrome bridge" if "chrome-native-host" in c
                          else "pty host" if "--bg-pty-host" in c else "claude helper")
    claimed = set().union(*trees.values()) if trees else set()
    claimed |= set(infra)
    my_tree = trees.get(me) or {os.getpid(), *descendants(kids, os.getpid())}
    own_cpu = sum(procs[x]["cpu"] for x in my_tree if x in procs)
    machine_cpu = max(0.0, machine_cpu - own_cpu)          # this window's scan is not load

    # shells carry their session's shell-snapshot id: it ties detached jobs back to their window
    snap_owner = {}
    for spid, tree in trees.items():
        for x in tree:
            if procs[x]["name"] in ("bash.exe", "sh.exe"):
                m = RX_SNAP.search(cmdtext(procs[x]))
                if m:
                    snap_owner[m.group(1)] = spid

    # CPU no listed process accounts for: processes born and gone inside the sample (tool bursts)
    seen_cpu = sum(d["cpu"] for pid, d in procs.items() if pid not in my_tree)
    bursts = max(0.0, machine_cpu - seen_cpu)

    left, nfiles = (0, 0)
    idx = load_index()
    try:
        left, nfiles = update_index(idx, args.budget)
    except Exception as exc:                                  # history is a bonus, never a blocker
        print("note: history index update failed: %s" % exc)
    prompts = load_prompts()
    tasks = finish_task_query(task_q)

    groups = orphan_groups(procs, kids, claimed)
    for g in groups:
        attribute_group(g, procs, sessions, snap_owner, tasks)

    items, waiting, idle, stale = [], [], [], []
    for pid, s in sorted(sessions.items(), key=lambda kv: -(kv[1].get("updatedAt") or 0)):
        if pid == me:
            continue
        ev = session_evidence(pid, s, procs, kids, trees[pid], groups, idx, prompts)
        if ev["state"] == "active":
            items.append(ev)
        elif ev["state"] == "waiting":
            waiting.append(ev)
        elif ev["state"] == "stale":
            stale.append(ev)
        else:
            idle.append(ev)
        if ev["state"] != "active" and ev.get("needs"):
            waiting.append(ev) if ev not in waiting else None

    loose = [g for g in groups if g["kind"] == "active" and g.get("owner") not in sessions]
    for g in loose:                                         # active detached work with no live window
        items.append(group_item(g, idx))
    stuck = [g for g in groups if g["kind"] == "stuck"]

    for n, it in enumerate(items, 1):
        it["n"] = n
    report(args, machine_cpu, ncpu, vm, sw, items, waiting, idle, stale, stuck, tasks, procs, claimed, groups,
           infra, me, left, nfiles, bursts)
    save_json(SNAP, {
        "at": NOW, "ncpu": ncpu, "cpu": machine_cpu, "ram_total": vm.total, "ram_free": vm.available,
        "cpu_th": args.cpu, "ram_th": args.ram,
        "items": [{"n": it["n"], "label": it["label"], "cpu": it["cpu"], "ram": it["ram"],
                   "hint": it.get("hint")} for it in items],
        "idle_ws": sum(e["ws"] for e in idle + stale), "idle_n": len(idle) + len(stale),
        "stuck_ws": sum(g["ws"] for g in stuck), "stuck_n": len(stuck),
    })


def orphan_groups(procs, kids, claimed):
    """Work processes no live window owns (detached jobs, scheduled tasks), grouped by their top ancestor."""
    groups, seen = [], set()
    for pid, d in procs.items():
        if pid in claimed or pid in seen or d.get("gone"):
            continue
        if d["name"] not in WORK and not automation_browser(d):
            continue
        root = pid
        while True:
            par = procs[root].get("parent")
            if not par or par in claimed:
                break
            pd = procs[par]
            if pd["name"] in WORK or pd["name"] in SHELLS or pd["name"] in UTILS or automation_browser(pd):
                root = par
            else:
                break
        if root in seen:
            continue
        members = [root] + descendants(kids, root)
        seen.update(members)
        work = [m for m in members if procs[m]["name"] in WORK or automation_browser(procs[m])]
        main = max(work or members, key=lambda m: (procs[m]["cpu_total"], procs[m]["ws"]))
        g = {"root": root, "members": members, "main": main,
             "cpu": sum(procs[m]["cpu"] for m in members), "ws": sum(procs[m]["ws"] for m in members),
             "priv": sum(procs[m]["priv"] for m in members),
             "start": min(procs[m]["create"] for m in members), "label": proc_label(procs[main]),
             "cwd": cwd_of(procs[main]), "parent_dead": procs[root].get("parent") is None}
        age = NOW - g["start"]
        g["kind"] = "stuck" if age > 6 * 3600 and g["cpu"] < 0.5 else "active"
        groups.append(g)
    return groups


def attribute_group(g, procs, sessions, snap_owner, tasks):
    texts = [cmdtext(procs[m]) for m in g["members"]]
    root = procs[g["root"]]
    texts.append(cmdtext(root))
    for t in texts:                                         # 1. the shell snapshot of the launching window
        m = RX_SNAP.search(t)
        if m:
            owner = snap_owner.get(m.group(1))
            if owner is None:
                ms = int(m.group(1)) / 1000.0
                near = [(ms - (s.get("startedAt") or 0) / 1000.0, pid) for pid, s in sessions.items()
                        if 0 <= ms - (s.get("startedAt") or 0) / 1000.0 < 900]
                owner = min(near)[1] if near else None
            if owner:
                g["owner"], g["how"] = owner, "launched by its shell"
                return
    blob = " ".join(texts + [g["cwd"]]).lower()
    for t in tasks:                                         # 2. a scheduled task's folder
        folder = os.path.dirname(re.split(r"\s+(?=[-/])", t["action"].strip('"'))[0].strip('"')).lower()
        if folder and len(folder) > 12 and folder in blob:
            g["owner"], g["how"], g["task"] = None, "scheduled task", t["name"]
            return
    parts = [x.lower() for x in re.split(r"[\\/]", g["cwd"]) if x]   # 3. folder named like a window
    for pid, s in sessions.items():
        name = (s.get("name") or "").lower()
        if name and name in parts:
            g["owner"], g["how"] = pid, "folder matches the window name"
            return


def tree_work(procs, tree, spid):
    """Work processes inside a window's tree, minus helpers that started with the window (MCP servers)."""
    born = procs[spid]["create"]
    out = []
    for x in tree:
        d = procs[x]
        if x == spid or "claude" in d["name"]:
            continue
        if d.get("parent") == spid and d["create"] - born < 120:
            continue
        out.append(x)
    return out


def session_evidence(pid, s, procs, kids, tree, groups, idx, prompts):
    sid = s.get("sessionId") or ""
    job = load_job(s.get("jobId")) if s.get("jobId") else None
    parked = load_job(s.get("parkedJobId")) if s.get("parkedJobId") else None
    tpath = transcript_path(sid)
    t_mt = mtime(tpath) if tpath else 0
    status = s.get("status") or "?"
    status_at = (s.get("statusUpdatedAt") or s.get("updatedAt") or 0) / 1000.0
    work = tree_work(procs, tree, pid)
    mine = [g for g in groups if g.get("owner") == pid]
    tree_cpu = sum(procs[x]["cpu"] for x in tree)
    work_cpu = sum(procs[x]["cpu"] for x in work) + sum(g["cpu"] for g in mine if g["kind"] == "active")
    ev = {"pid": pid, "sid": sid, "label": s.get("name") or sid[:8], "kind": s.get("kind") or "?",
          "status": status, "status_at": status_at, "job": job, "parked": parked, "t_mt": t_mt,
          "ws": sum(procs[x]["ws"] for x in tree), "priv": sum(procs[x]["priv"] for x in tree),
          "cpu": tree_cpu + sum(g["cpu"] for g in mine if g["kind"] == "active"),
          "ram": sum(procs[x]["ws"] for x in work) + sum(g["ws"] for g in mine if g["kind"] == "active"),
          "work": work, "groups": mine, "prompt": prompts.get(sid), "needs": None}

    # Status labels and file times go stale (parked windows say 'busy' for days, usage-limit stops leave jobs
    # 'working', metadata lines touch every transcript), so 'active' needs live evidence.
    task_outs = [f for f in glob.glob(os.path.join(TEMP_CLAUDE, "*", sid, "tasks", "*.output"))
                 if NOW - mtime(f) < 15 * 60]
    live_work = [x for x in work if (procs[x]["name"] in WORK or automation_browser(procs[x]))
                 and (procs[x]["cpu"] >= 1 or NOW - procs[x]["create"] < 30 * 60)]
    active_groups = [g for g in mine if g["kind"] == "active"]
    look = status in ("busy", "shell", "waiting") or (job and job.get("state") in ("working", "blocked")) \
        or NOW - t_mt < 30 * 60 or task_outs or work_cpu > 1 or live_work or active_groups
    a, subs = None, []
    if look and tpath:
        a = analyze(tail_entries(tpath))
        subs = active_subagents(sid)
        if a["prompt"] and (not ev["prompt"] or a["prompt"][0] > ev["prompt"][0]):
            ev["prompt"] = a["prompt"]
        fresh = bool(a["last_ts"]) and NOW - a["last_ts"] < 15 * 60
        if not fresh:
            a["pending"] = []                          # a tool can't still be running after 15 silent minutes
        a["bg"] = [b for b in a["bg"] if NOW - mtime(b["out"]) < 30 * 60]
    else:
        fresh = False
    ev["a"], ev["subs"], ev["task_outs"], ev["fresh"] = a, subs, task_outs, fresh
    ev["last_act"] = (a or {}).get("last_ts") if a else None
    limit = hit_limit(a) and not (fresh and a["last_ts"] - (a["texts"][-1][0] or 0) > 60)   # resumed since?

    running = bool(subs) or bool(a and (a["bg"] or a["pending"])) or work_cpu > 1.5 or bool(live_work) \
        or bool(active_groups)
    talking = fresh and a and not a["ended"] and not limit
    needs = []
    if job and job.get("needs") and job.get("state") in ("blocked", "working"):
        needs.append(job["needs"])
    if status == "waiting":
        needs.append(s.get("waitingFor") or "input")
    if limit and not running:
        needs.append("stopped at the usage limit; say continue in it to resume")
    ev["needs"] = "; ".join(needs) or None
    if running or talking:
        ev["state"] = "active"
    elif ev["needs"]:
        ev["state"] = "waiting"
    elif status == "busy" or (job and job.get("state") == "working"):
        ev["state"] = "stale"
    else:
        ev["state"] = "idle"

    if job and job.get("state") == "working" and ev["state"] == "active":
        ev["since"] = job_working_since(job) or status_at
    elif status in ("busy", "shell"):
        ev["since"] = status_at
    else:
        ev["since"] = ev["prompt"][0] if ev["prompt"] else status_at
    ev["hint"] = None
    if ev["state"] == "active":
        ev["hint"] = estimate_hint(ev, procs, idx)
    return ev


def estimate_hint(ev, procs, idx):
    """A first remaining-time guess the script can defend; Claude refines it from the evidence."""
    hints = []
    runs = [(procs[x], procs[x]["create"]) for x in ev["work"]] + \
        [(procs[g["main"]], g["start"]) for g in ev["groups"] if g["kind"] == "active"]
    for d, start in runs:                                  # progress printed by the work itself
        for f in live_logs(d, start):
            p = parse_progress(log_tail(f, 12), NOW - start)
            if p and p.get("left") is not None:
                hints.append((p["left"], p["left"] * 1.3, "log %s says %s" % (os.path.basename(f), p["how"])))
    for sub in ev["subs"]:
        active = (idx["agents"].get(sub["file"]) or {}).get("active") or 0
        last = (idx["agents"].get(sub["file"]) or {}).get("last") or sub["a"]["last_ts"] or NOW
        sub["active"] = active + min(1200, max(0, NOW - last))
        past = agent_history(idx, sub["type"], sub["file"])
        sub["past"] = (median(past), len(past)) if past else None
        r = remaining_from(past, sub["active"], 2)
        if r:
            hints.append((r["mid"], r["late"], "%s agents that ran past this one's %s of work (n=%d of %d)"
                          % (sub["type"], fdur(sub["active"]), r["n"], r["of"])))
    if not hints and ev.get("since") and ev["status"] == "busy":
        r = remaining_from(turn_history(idx), NOW - ev["since"], 8)
        if r:
            hints.append((r["mid"], r["late"], "past turns that ran %s+ (n=%d)" % (fdur(NOW - ev["since"]), r["n"])))
    if not hints:
        return None
    mid, late, why = max(hints, key=lambda h: h[0])
    return {"mid": mid, "late": max(mid, late), "why": why}


def group_item(g, idx):
    script = (RX_SCRIPT.search(g["label"]) or [None])[0] if RX_SCRIPT.search(g["label"]) else None
    if g.get("task"):
        label = "%s (scheduled task)" % g["task"]
    else:
        label = "%s (detached, %s)" % (g["label"].split(" ")[0] if not script else script,
                                       os.path.basename(g["cwd"]) if g["cwd"] else "?")
    it = {"label": label, "cpu": g["cpu"], "ram": g["ws"], "groups": [g], "work": [], "subs": [],
          "a": None, "pid": None, "kind": "process", "status": "running", "since": g["start"], "job": None,
          "prompt": None, "task_outs": [], "hint": None, "detached": True}
    if script:
        r = remaining_from(script_history(idx, script), NOW - g["start"], 3)
        if r:
            it["hint"] = {"mid": r["mid"], "late": r["late"], "why": "past runs of %s (n=%d)" % (script, r["n"])}
    return it


# ---------------------------------------------------------------- report

def report(args, cpu, ncpu, vm, sw, items, waiting, idle, stale, stuck, tasks, procs, claimed, groups, infra, me,
           left, nfiles, bursts):
    out = []
    w = out.append
    busy_cpu = cpu > args.cpu
    short_ram = vm.available / 2 ** 30 < args.ram
    w("WHEN-FREE scan %s (CPU sampled %gs)" % (time.strftime("%a %d %b %I:%M %p", time.localtime(NOW)).replace(" 0", " "),
                                               args.sample))
    w("Machine: CPU %d%% of %d threads | RAM %.1f of %.1f GB used, %.1f GB free | pagefile %.1f GB in use"
      % (cpu, ncpu, (vm.total - vm.available) / 2 ** 30, vm.total / 2 ** 30, vm.available / 2 ** 30, sw.used / 2 ** 30))
    if bursts >= 5:
        w("   %d%% of that CPU came from processes that started and ended inside the sample (tool bursts from "
          "active windows; not in any item's load below)" % bursts)
    state = []
    if busy_cpu:
        state.append("CPU %d pts over" % (cpu - args.cpu))
    if short_ram:
        state.append("RAM %.1f GB short" % (args.ram - vm.available / 2 ** 30))
    w("Free means CPU <= %g%% and >= %g GB RAM free. Now: %s" % (args.cpu, args.ram,
                                                                "BUSY (" + ", ".join(state) + ")" if state else "FREE"))
    if left:
        w("History index: %d of %d transcripts still to index (continues next scan; or run: when_free.py index)"
          % (left, nfiles))
    w("")
    w("== ACTIVE WORK (ends on its own). Estimate each, then: when_free.py plan --eta N=best[-late][@cpu%] ...")
    if not items:
        w("   none")
    for it in items:
        print_item(w, it, procs)
    w("")
    w("== WAITING ON YOU (won't move until you act)")
    if not waiting:
        w("   none")
    for ev in waiting:
        detail = (ev.get("job") or {}).get("detail") or ""
        if len(re.sub(r"[`\s]", "", detail)) < 8:
            detail = ""                                   # a stray code fence is not a status line
        w("   - %s (%s, idle %s): %s%s" % (ev["label"], "background job" if ev["kind"] == "bg" else "window",
                                          fdur(NOW - max(ev["status_at"], ev.get("last_act") or 0)),
                                          short(ev["needs"] or "", 200),
                                          "; job says: " + short(detail, 130) if detail else ""))
    w("")
    hold = idle + stale
    w("== IDLE WINDOWS (finished; hold memory until closed): %d windows, %s in RAM now, %s committed"
      % (len(hold), gb(sum(e["ws"] for e in hold)), gb(sum(e["priv"] for e in hold))))
    rows = []
    for ev in hold:                                       # idle since the status flipped or the last real entry
        ev["idle_for"] = NOW - max(ev["status_at"] if ev["status"] != "busy" else 0, ev.get("last_act") or 0) \
            if (ev["status"] != "busy" or ev.get("last_act")) else NOW - ev["status_at"]
    for ev in sorted(hold, key=lambda e: -e["idle_for"]):
        tag = ""
        if ev in stale:
            tag = " [says busy, nothing running%s]" % (", parked into a background job" if ev.get("parked") else "")
        rows.append("%s %s, %s%s" % (ev["label"], fdur(ev["idle_for"]), mem(ev["ws"]), tag))
    for i in range(0, len(rows), 4):
        w("   " + " | ".join(rows[i:i + 4]))
    w("")
    w("== STUCK PROCESSES (alive, no CPU for hours; they never finish by themselves)")
    if not stuck:
        w("   none")
    for g in stuck:
        owner = g.get("owner")
        w("   - %s  in %s  %s old, %s in RAM, %s committed, pids %s%s"
          % (g["label"], nice(g["cwd"]) or "?", fdur(NOW - g["start"]), mem(g["ws"]), mem(g["priv"]),
             ",".join(str(m) for m in g["members"] if procs[m]["name"] not in SHELLS)[:40],
             "" if not g.get("task") else ", scheduled task " + g["task"]))
    w("")
    w("== SCHEDULED JOBS (start on their own)%s" % (" - from the last good lookup, this one timed out"
                                                    if tasks and tasks[0].get("cached") else ""))
    soon = [t for t in tasks if t["next"] and t["next"] - NOW < 12 * 3600 or t["state"] == "Running"]
    if not soon:
        w("   none in the next 12 hours")
    for t in sorted(soon, key=lambda t: t["next"] or 0):
        w("   - %s: %s%s, next %s%s" % (t["name"], "RUNNING NOW, " if t["state"] == "Running" else "",
                                     "every " + fdur(t["every"]) if t["every"] else "once/daily",
                                     fclock(t["next"]) if t["next"] else "?",
                                     "  (" + nice(t["action"].split(" ;")[0].strip('"'))[:70] + ")"))
    w("")
    other = collections.defaultdict(lambda: [0.0, 0, 0])
    gmem = {m for g in groups for m in g["members"]}
    helpers = [p for p, d in procs.items() if p not in claimed and p not in gmem and d["name"] in UTILS | SHELLS
               and d.get("parent") is None and NOW - d["create"] > 3600 and d["name"] not in ("conhost.exe",)]
    for pid, d in procs.items():
        if pid in claimed or pid in gmem or pid in helpers:
            continue
        o = other[d["name"]]
        o[0] += d["cpu"]
        o[1] += d["ws"]
        o[2] += 1
    top = sorted(other.items(), key=lambda kv: -(kv[1][1] + kv[1][0] * 50 * 2 ** 20))[:9]
    w("== OTHER LOAD (not Claude work): " + ", ".join(
        "%s %s%s%s" % (n.replace(".exe", ""), mem(v[1]), " %d%% CPU" % v[0] if v[0] >= 1 else "",
                       " x%d" % v[2] if v[2] > 1 else "") for n, v in top))
    if infra:
        w("   Claude infrastructure: " + ", ".join("%s %s" % (k, mem(procs[p]["ws"])) for p, k in infra.items()))
    if len(helpers) >= 5:
        names = collections.Counter(procs[p]["name"].replace(".exe", "") for p in helpers)
        w("   %d leftover shell helpers from finished commands (%s), %s"
          % (len(helpers), ", ".join("%s x%d" % kv for kv in names.most_common(4)),
             mem(sum(procs[p]["ws"] for p in helpers))))
    print("\n".join(out))


def print_item(w, it, procs):
    since = it.get("since")
    head = "[%d] %s" % (it["n"], it["label"])
    if it.get("pid"):
        head += "  %s pid %d" % ("background job" if it["kind"] == "bg" else "window", it["pid"])
    if since:
        head += " | working %s (since %s)" % (fdur(NOW - since), fclock(since))
    cwd = (it.get("a") or {}).get("cwd") if it.get("a") else None
    if cwd:
        head += " | " + nice(cwd)
    w(head)
    if it.get("prompt"):
        w("    asked %s: \"%s\"" % (fclock(it["prompt"][0]) if it["prompt"][0] else "?", short(it["prompt"][1], 230)))
    job = it.get("job")
    if job:
        w("    job: %s - %s%s" % (job.get("state"), short(job.get("detail") or "", 160),
                                ("; intent: " + short(job.get("intent"), 120)) if job.get("intent") else ""))
        fan = job.get("fan")
        if isinstance(fan, list) and fan:
            w("    job in flight: " + "; ".join("%s %s (%s)" % (f.get("kind"), short(f.get("label") or "", 80),
                                                              fdur(NOW - (f.get("startedAt") or NOW * 1000) / 1000))
                                            for f in fan[:4]))
    w("    load now: CPU %d%% (~%.1f threads), work RAM %s" % (it["cpu"], it["cpu"] / 100 * psutil.cpu_count(),
                                                             mem(it["ram"])))
    a = it.get("a")
    if a:
        for ts, txt in a["texts"][-2:][::-1]:
            w("    said %s ago: \"%s\"" % (fdur(NOW - ts) if ts else "?", short(txt, 260)))
        for ts, name, inp in a["pending"][:3]:
            w("    running now: %s \"%s\" for %s" % (name, short(inp.get("description") or inp.get("command") or
                                                             inp.get("prompt") or json.dumps(inp)[:120], 150),
                                                  fdur(NOW - ts) if ts else "?"))
        if a["todos"]:
            st = collections.Counter(t.get("status") for t in a["todos"] if isinstance(t, dict))
            cur = [t.get("activeForm") or t.get("content") for t in a["todos"]
                   if isinstance(t, dict) and t.get("status") == "in_progress"]
            w("    to-do list: %d done, %d in progress, %d pending%s" % (st["completed"], st["in_progress"],
                                                                         st["pending"],
                                                                         " - now: " + short(cur[0], 90) if cur else ""))
        for b in a["bg"][:4]:
            w("    background task %s \"%s\" running %s" % (b["id"], short(b["desc"] or b["cmd"], 120),
                                                         fdur(NOW - b["ts"]) if b["ts"] else "?"))
            print_log(w, b["out"], NOW - (b["ts"] or NOW), "      ")
    for sub in it.get("subs") or []:
        sa = sub["a"]
        past = sub.get("past")
        w("    agent %s \"%s\": %s of work so far%s, last wrote %s ago"
          % (sub["type"], short(sub["desc"], 80), fdur(sub.get("active")),
             " (past %s agents: median %s, n=%d)" % (sub["type"], fdur(past[0]), past[1]) if past else "",
             fdur(NOW - sub["mtime"])))
        for ts, txt in sa["texts"][-2:][::-1]:
            w("      said %s ago: \"%s\"" % (fdur(NOW - ts) if ts else "?", short(txt, 240)))
        for ts, name, inp in sa["pending"][:2]:
            w("      running now: %s \"%s\" for %s" % (name, short(inp.get("description") or inp.get("command") or
                                                               json.dumps(inp)[:120], 150),
                                                    fdur(NOW - ts) if ts else "?"))
        for b in sa["bg"][:3]:
            w("      background task %s \"%s\" running %s" % (b["id"], short(b["desc"] or b["cmd"], 110),
                                                           fdur(NOW - b["ts"]) if b["ts"] else "?"))
    shown = set()
    for x in sorted(it.get("work") or [], key=lambda x: -procs[x]["cpu"]):
        d = procs[x]
        if d["name"] not in WORK and not automation_browser(d):
            continue
        if d["cpu"] < 0.5 and d["ws"] < 150 * 2 ** 20 and NOW - d["create"] > 1800:
            continue
        w("    process %s  pid %d  CPU %d%%  %s  up %s" % (proc_label(d), x, d["cpu"], mem(d["ws"]),
                                                          fdur(NOW - d["create"])))
        print_files(w, d, "      ")
        for f in live_logs(d, d["create"])[:3]:
            if f not in shown:
                shown.add(f)
                print_log(w, f, NOW - d["create"], "      ")
    for g in it.get("groups") or []:
        if g["kind"] != "active":
            continue
        d = procs[g["main"]]
        w("    detached %s  pid %d  CPU %d%%  %s  up %s  in %s (%s)"
          % (g["label"], g["main"], g["cpu"], mem(g["ws"]), fdur(NOW - g["start"]), nice(g["cwd"]),
             g.get("how") or "owner unknown"))
        print_files(w, d, "      ")
        for x in g["members"]:
            for f in live_logs(procs[x], g["start"])[:3]:
                if f not in shown:
                    shown.add(f)
                    print_log(w, f, NOW - g["start"], "      ")
        sc = shell_command(procs[g["root"]]) if procs[g["root"]]["name"] in ("bash.exe", "sh.exe") else None
        if sc:
            w("      launched with: " + short(sc, 200))
    if it.get("hint"):
        h = it["hint"]
        w("    script guess: %s left (late %s) - %s" % (fdur(h["mid"]), fdur(h["late"]), h["why"]))
    else:
        w("    script guess: none - read the evidence above")


def print_files(w, d, pad):
    """Media files a work process is writing right now: their size is the progress of a copy or render."""
    if d["name"] == "ffmpeg.exe":
        w("%scommand: %s" % (pad, short(" ".join(os.path.basename(x) if ("\\" in x or "/" in x) else x
                                                 for x in cmdline(d)[1:]), 230)))
    for f in open_files(d):
        if f.lower().endswith(MEDIA_EXT) and NOW - mtime(f) < 120:
            try:
                size = os.path.getsize(f)
            except OSError:
                continue
            w("%swriting %s  %s so far" % (pad, nice(f), mem(size)))


def print_log(w, path, elapsed, pad):
    if not path or not os.path.exists(path):
        return
    lines = log_tail(path, 6)
    w("%slog %s (written %s ago)%s" % (pad, nice(path), fdur(NOW - mtime(path)), "" if lines else ": empty"))
    for ln in lines:
        w("%s| %s" % (pad, ln))
    p = parse_progress(log_tail(path, 12), elapsed)
    if p:
        w("%sprogress: %s%s" % (pad, p["how"], ", naive time left " + fdur(p["left"]) if p.get("left") is not None
                                else ""))


# ---------------------------------------------------------------- plan

def cmd_plan(args):
    snap = read_json(SNAP)
    if not snap:
        sys.exit("no snapshot yet: run  when_free.py scan  first")
    cpu_th = args.cpu if args.cpu is not None else snap.get("cpu_th", 50)
    ram_th = (args.ram if args.ram is not None else snap.get("ram_th", 3.0)) * 2 ** 30
    at = snap["at"]
    items = {it["n"]: dict(it) for it in snap["items"]}
    for it in items.values():
        it["load"] = it["cpu"]
    for spec in args.eta:
        key, _, val = spec.partition("=")
        key = key.strip()
        n = int(key) if key.isdigit() else next((k for k, it in items.items() if it["label"].lower() == key.lower()),
                                                None)
        if n not in items:
            sys.exit("no item %r in the snapshot (items: %s)" % (key, ", ".join(str(k) for k in items)))
        val, _, load = val.partition("@")                  # @40 = it will hold ~40% CPU until it ends
        best, _, late = val.partition("-")
        b = parse_dur(best)
        items[n]["best"] = b
        items[n]["late"] = parse_dur(late) if late else (None if b is None else b * 1.4)
        items[n]["src"] = "Claude's estimate"
        if load:
            items[n]["load"] = float(load.strip().rstrip("%"))
            items[n]["src"] += ", holding ~%g%% CPU until then" % items[n]["load"]
    for n, it in items.items():
        if "best" not in it:
            h = it.get("hint")
            if h:
                it["best"], it["late"], it["src"] = h["mid"], h["late"], "script guess (%s)" % h["why"]
            else:
                it["best"] = it["late"] = None
                it["src"] = "NO ESTIMATE - counted as never ending; pass --eta %d=..." % n

    age = time.time() - at
    print("FREE-AT PLAN from the scan at %s%s; free = CPU <= %g%% and >= %.1f GB RAM free"
          % (fclock(at), " (%s ago)" % fdur(age) if age > 120 else "", cpu_th, ram_th / 2 ** 30))
    base = max(0.0, snap["cpu"] - sum(it["cpu"] for it in items.values()))   # load that is not listed work
    for case in ("best", "late"):
        cpu = base + sum(it["load"] for it in items.values())
        free = snap["ram_free"]
        ends = sorted(((at + it[case], it) for it in items.values() if it[case] is not None), key=lambda e: e[0])
        room = at if cpu <= cpu_th and free >= ram_th else None
        cpu_room = at if cpu <= cpu_th else None
        start_cpu = cpu
        rows = []
        for t, it in ends:
            cpu = max(0.0, cpu - it["load"])
            free += it["ram"]
            rows.append("  %-9s [%d] %s ends -> CPU %d%%, RAM free %.1f GB"
                        % (fclock(t), it["n"], it["label"], cpu, free / 2 ** 30))
            if cpu_room is None and cpu <= cpu_th:
                cpu_room = t
            if room is None and cpu <= cpu_th and free >= ram_th:
                room = t
        if case == "best":
            print("  now       CPU %d%% measured%s, RAM free %.1f GB"
                  % (snap["cpu"], ", %d%% with the loads expected" % start_cpu if abs(start_cpu - snap["cpu"]) >= 1
                     else "", snap["ram_free"] / 2 ** 30))
            print("\n".join(rows))
            for it in items.values():
                print("  [%d] %s: %s" % (it["n"], it["label"], it["src"]))
        never = [it for it in items.values() if it[case] is None]
        all_done = max((t for t, _ in ends), default=at)
        if room is not None:
            line = "room for new work at %s (in %s)" % (fclock(room), fdur(room - time.time()) if room > time.time()
                                                         else "now")
        elif cpu_room is not None:
            line = "CPU has room at %s, but RAM stays under %.1f GB free" % (fclock(cpu_room), ram_th / 2 ** 30)
        else:
            line = "no room while the listed work runs"
        line += "; all listed work done %s" % (fclock(all_done) if not never else "never (%d open-ended)" % len(never))
        print("%s case: %s" % (case.upper(), line))
    if snap.get("idle_n"):
        print("Closing the %d idle windows would free about %s of RAM now%s."
              % (snap["idle_n"], gb(snap["idle_ws"]), " (stuck processes: %s more)" % gb(snap["stuck_ws"])
                 if snap.get("stuck_ws", 0) >= 0.1 * 2 ** 30 else ""))


def cmd_index(args):
    t = time.time()
    idx = load_index()
    left, n = update_index(idx, args.budget)
    print("history index: %d transcripts, %d still to read, %d turns, %d background tasks, %d agents (%.0fs)"
          % (n, left, len(idx["turns"]), len(idx["bg"]), len(idx["agents"]), time.time() - t))


EASE_NAMES = {"claude.exe", "python.exe", "pythonw.exe", "ffmpeg.exe", "ffprobe.exe", "node.exe", "bun.exe"}


def boost():
    """Run this scan ahead of everything else without stopping anything (user, 7 Oct 2026): raise our own
    priority and drop the other work processes to below-normal for the few seconds the scan takes.
    Returns what to restore."""
    if os.name != "nt":
        return []
    eased = []
    try:
        me = psutil.Process()
        me.nice(psutil.HIGH_PRIORITY_CLASS)
        keep = {me.pid} | {p.pid for p in me.parents()}
    except Exception:
        return []
    for p in psutil.process_iter(["name"]):
        try:
            if p.pid in keep or (p.info["name"] or "").lower() not in EASE_NAMES:
                continue
            was = p.nice()
            if was in (psutil.NORMAL_PRIORITY_CLASS, psutil.ABOVE_NORMAL_PRIORITY_CLASS, psutil.HIGH_PRIORITY_CLASS):
                p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                eased.append((p, was))
        except Exception:
            pass
    return eased


def unboost(eased):
    for p, was in eased:
        try:
            p.nice(was)
        except Exception:
            pass


def main():
    eased = boost()
    try:
        run()
    finally:
        unboost(eased)


def run():
    ap = argparse.ArgumentParser(description="When will this PC be free again?")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("scan", help="measure everything and print the evidence")
    s.add_argument("--sample", type=float, default=5.0, help="seconds of CPU sampling (default 5)")
    s.add_argument("--budget", type=float, default=25.0, help="seconds allowed for the history index (default 25)")
    s.add_argument("--cpu", type=float, default=50.0, help="free = CPU at or under this %% (default 50)")
    s.add_argument("--ram", type=float, default=3.0, help="free = at least this many GB of RAM free (default 3)")
    p = sub.add_parser("plan", help="turn estimates into a free-at time")
    p.add_argument("--eta", action="append", default=[], help="N=best[-late][@cpu], e.g. 1=35m-55m, 2=done, 3=never, 4=2h-3h@40")
    p.add_argument("--cpu", type=float, default=None)
    p.add_argument("--ram", type=float, default=None)
    i = sub.add_parser("index", help="build the history index")
    i.add_argument("--budget", type=float, default=900.0)
    args = ap.parse_args()
    if args.cmd == "plan":
        cmd_plan(args)
    elif args.cmd == "index":
        cmd_index(args)
    else:
        cmd_scan(args if args.cmd == "scan" else s.parse_args([]))


if __name__ == "__main__":
    main()
