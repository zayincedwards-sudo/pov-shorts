#!/usr/bin/env python
"""Status line for every Claude Code window, and the usage recorder behind /what-to-use.

Claude Code pipes a JSON blob to this script on every redraw; its `rate_limits` field carries the plan's
5-hour and 7-day usage (used_percentage, resets_at). This script saves the latest reading to
data/usage.json, appends changes to data/usage_log.jsonl (the trend), and prints one short line:
    Opus 5.5 · 5h 42% → 3:10 PM · week 61% → Mon 9 AM
It must be fast and must never fail: any error still prints the model name.
"""
import datetime as dt
import json
import os
import sys
import time

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def reset_time(v):
    """resets_at may be epoch seconds, epoch ms or ISO text."""
    if v is None:
        return None
    try:
        x = float(v)
        return x / 1000 if x > 1e11 else x
    except (TypeError, ValueError):
        try:
            return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None


def windows(rl):
    """Every rate-limit window in the blob: name -> (used %, reset epoch)."""
    out = {}
    if not isinstance(rl, dict):
        return out
    for name, w in rl.items():
        if isinstance(w, dict) and "used_percentage" in w:
            try:
                out[name] = (float(w.get("used_percentage") or 0), reset_time(w.get("resets_at")))
            except (TypeError, ValueError):
                pass
    return out


def clock(t, now):
    lt = time.localtime(t)
    s = time.strftime("%I:%M %p", lt).lstrip("0").replace(":00 ", " ")
    if t - now > 20 * 3600:
        s = time.strftime("%a ", lt) + s
    return s


def effort_of(blob):
    e = blob.get("effort")
    return e.get("level") if isinstance(e, dict) else e


def record(blob, wins, now):
    os.makedirs(DATA, exist_ok=True)
    snap = {"at": now, "model": (blob.get("model") or {}).get("display_name"),
            "effort": effort_of(blob),
            "windows": {k: {"used": u, "resets": r} for k, (u, r) in wins.items()},
            "raw_rate_limits": blob.get("rate_limits")}
    tmp = os.path.join(DATA, "usage.json.%d.tmp" % os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(snap, fh)
    os.replace(tmp, os.path.join(DATA, "usage.json"))
    sid = (blob.get("session_id") or "")[:8]
    if sid:                                                 # each window's own model and effort
        os.makedirs(os.path.join(DATA, "windows"), exist_ok=True)
        tmp = os.path.join(DATA, "windows", "%s.%d.tmp" % (sid, os.getpid()))
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"at": now, "model_id": (blob.get("model") or {}).get("id"), "model": snap["model"],
                       "effort": snap["effort"], "session_id": blob.get("session_id")}, fh)
        os.replace(tmp, os.path.join(DATA, "windows", sid + ".json"))
    sample = os.path.join(DATA, "statusline_sample.json")       # one raw blob, to see the schema
    if not os.path.exists(sample) or now - os.path.getmtime(sample) > 86400:
        with open(sample, "w", encoding="utf-8") as fh:
            json.dump(blob, fh, indent=1)
    log = os.path.join(DATA, "usage_log.jsonl")
    last = None
    try:
        with open(log, "rb") as fh:
            fh.seek(max(0, os.path.getsize(log) - 4000))
            tail = fh.read().decode("utf-8", "replace").strip().splitlines()
            last = json.loads(tail[-1]) if tail else None
    except (OSError, ValueError):
        pass
    cur = {k: round(u, 1) for k, (u, r) in wins.items()}
    sid = (blob.get("session_id") or "")[:8]
    if last is None or last.get("used") != cur or now - last.get("at", 0) > 600 \
            or (last.get("sid") != sid and now - last.get("at", 0) > 60):
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": round(now), "used": cur,
                                 "resets": {k: r for k, (u, r) in wins.items()},
                                 "sid": sid, "v": blob.get("version")}) + "\n")


def main():
    now = time.time()
    try:
        blob = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except ValueError:
        blob = {}
    model = (blob.get("model") or {}).get("display_name") or "Claude"
    parts = [model]
    try:
        wins = windows(blob.get("rate_limits"))
        if wins:
            record(blob, wins, now)
        names = {"five_hour": "5h", "seven_day": "week"}
        for k in ("five_hour", "seven_day"):
            if k in wins:
                u, r = wins[k]
                parts.append("%s %d%%%s" % (names[k], round(u), " → " + clock(r, now) if r else ""))
        for k, (u, r) in wins.items():                         # extra windows (e.g. a model's weekly cap)
            if k not in names and u >= 1:
                parts.append("%s %d%%" % (k.replace("seven_day_", "week ").replace("_", " "), round(u)))
    except Exception:
        pass
    sys.stdout.buffer.write(" · ".join(parts).encode("utf-8"))    # Windows' default codepage has no →


if __name__ == "__main__":
    main()
