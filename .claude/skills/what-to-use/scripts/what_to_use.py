#!/usr/bin/env python
"""what-to-use: how much plan usage is left, how fast it is going, and what this window runs on.

    python what_to_use.py          prints the budget summary the what-to-use skill decides from

Data comes from the status line (scripts/statusline.py), which records the plan's 5-hour and weekly
usage on every redraw of every window. Reads local files only; spends nothing.
"""
import collections
import glob
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(SKILL, "data")
LOG = os.path.join(DATA, "usage_log.jsonl")
SESSIONS = os.path.join(os.path.expanduser("~"), ".claude", "sessions")
NOW = time.time()
SPAN = {"five_hour": 5 * 3600, "seven_day": 7 * 86400}
NAME = {"five_hour": "5-hour", "seven_day": "weekly"}


def fdur(s):
    s = max(0, int(s))
    if s < 3600:
        return "%dm" % (s // 60)
    if s < 48 * 3600:
        return "%dh%02dm" % (s // 3600, s % 3600 // 60)
    return "%dd%dh" % (s // 86400, s % 86400 // 3600)


def fclock(t):
    lt = time.localtime(t)
    s = time.strftime("%I:%M %p", lt).lstrip("0")
    return (time.strftime("%a ", lt) + s) if t - NOW > 18 * 3600 else s


def readings():
    out = []
    try:
        with open(LOG, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def current(rows, win):
    """Latest reading of a window: the highest from the last 15 min (a stale window can report low)."""
    recent = [r for r in rows if win in r.get("used", {}) and NOW - r["at"] < 900]
    if not recent:
        older = [r for r in rows if win in r.get("used", {})]
        recent = older[-1:]
    if not recent:
        return None
    best = max(recent, key=lambda r: r["used"][win])
    return best["used"][win], best["resets"].get(win), best["at"]


def recent_rate(rows, win, resets, hours=6):
    """% per hour over the last few hours of this same window (same reset time), from the log."""
    pts = [(r["at"], r["used"][win]) for r in rows if win in r.get("used", {})
           and abs((r["resets"].get(win) or 0) - (resets or 0)) < 120 and NOW - r["at"] < hours * 3600]
    if len(pts) < 2:
        return None
    pts.sort()
    by_hour = collections.OrderedDict()                    # top reading per 10 min, so a stale low one can't pull it down
    for t, u in pts:
        k = int(t // 600)
        by_hour[k] = max(by_hour.get(k, 0), u)
    ks = list(by_hour)
    if len(ks) < 2 or (ks[-1] - ks[0]) * 600 < 3600:
        return None
    return max(0.0, (by_hour[ks[-1]] - by_hour[ks[0]]) / ((ks[-1] - ks[0]) * 600 / 3600))


def level(used, projected):
    if used >= 90 or projected >= 120:
        return "critical"
    if projected >= 95:
        return "tight"
    if projected >= 70:
        return "ok"
    return "plenty"


def my_window():
    """This window's model and effort, as its own status line last reported them."""
    try:
        import psutil
        p = psutil.Process(os.getpid())
        for a in p.parents():
            f = os.path.join(SESSIONS, "%d.json" % a.pid)
            if os.path.exists(f):
                sid = (json.load(open(f, encoding="utf-8")).get("sessionId") or "")[:8]
                w = os.path.join(DATA, "windows", sid + ".json")
                if os.path.exists(w):
                    return json.load(open(w, encoding="utf-8"))
                return {"session_id": sid}
    except Exception:
        pass
    return None


def daily(rows):
    """Weekly-window usage added per calendar day, from the log."""
    days = collections.OrderedDict()
    for r in rows:
        if "seven_day" in r.get("used", {}):
            d = time.strftime("%a %d %b", time.localtime(r["at"]))
            lo, hi, res = days.get(d, (None, None, None))
            u = r["used"]["seven_day"]
            days[d] = (u if lo is None else min(lo, u), u if hi is None else max(hi, u), r["resets"].get("seven_day"))
    return days


def main():
    rows = readings()
    if not rows:
        print("NO USAGE DATA YET: the status line records it on each window redraw. Open or click into any "
              "Claude window, then run this again. Decide from the task alone and say the budget is unknown.")
        return
    worst = "plenty"
    order = ["plenty", "ok", "tight", "critical"]
    print("USAGE (plan limits, from the status line log)")
    for win in ("five_hour", "seven_day"):
        cur = current(rows, win)
        if not cur:
            print("  %s: no reading" % NAME[win])
            continue
        used, resets, at = cur
        span = SPAN[win]
        left = max(0, (resets or NOW) - NOW)
        elapsed = max(60, span - left)
        pace = used / elapsed * 3600                       # % per hour since this window opened
        rate = recent_rate(rows, win, resets)
        use_rate = max(pace, rate) if rate is not None else pace
        projected = used + use_rate * left / 3600
        lv = level(used, projected)
        if win == "five_hour" and used < 50:
            lv = "plenty" if lv in ("ok", "tight") and used < 30 else lv
        worst = max(worst, lv, key=order.index)
        runout = ""
        if use_rate > 0 and used < 100:
            t_out = (100 - used) / use_rate * 3600
            if t_out < left:
                runout = ", runs out about %s, %s before it resets" % (fclock(NOW + t_out), fdur(left - t_out))
        print("  %s: %d%% used, resets %s (in %s); %d%% of the window gone. Pace %.1f%%/h%s -> about %d%% at reset%s. [%s]"
              % (NAME[win], round(used), fclock(resets) if resets else "?", fdur(left), round(100 * elapsed / span),
                 pace, "" if rate is None else ", last few hours %.1f%%/h" % rate, round(projected), runout, lv.upper()))
        if NOW - at > 1800:
            print("    (reading is %s old)" % fdur(NOW - at))
    days = daily(rows)
    if len(days) > 1:
        print("  weekly usage added per day: " + ", ".join(
            "%s +%d%%" % (d, round(hi - lo)) for d, (lo, hi, _) in list(days.items())[-7:]))
    else:
        print("  (day-by-day trend builds up as the log grows; it started %s)" % fclock(rows[0]["at"]))
    print("BUDGET: %s" % worst.upper())
    me = my_window()
    if me and me.get("model"):
        print("THIS WINDOW: %s, effort %s" % (me.get("model"), me.get("effort") or "?"))
    else:
        print("THIS WINDOW: unknown (use the model named in your system prompt)")


if __name__ == "__main__":
    main()
