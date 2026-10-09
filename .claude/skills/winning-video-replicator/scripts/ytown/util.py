"""Shared helpers: paths, JSON, plain-text output, durations, sentences, ffprobe.

Everything in this kit uses C:/ style paths on Windows (Git Bash /c/ paths break Python's
open()), writes JSON as UTF-8 with indent 1, and writes user-facing text as CRLF plain text
with no markdown (house rule 5).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import statistics as st
import subprocess
from pathlib import Path

TODAY = _dt.date.today().isoformat()


# ------------------------------------------------------------------ paths
def winpath(p: str | os.PathLike) -> Path:
    """Accept /c/Users/... (Git Bash) or C:\\Users\\... and return a Path Python can open."""
    s = str(p)
    m = re.match(r"^/([a-zA-Z])/(.*)$", s)
    if m:
        s = f"{m.group(1).upper()}:/{m.group(2)}"
    return Path(s)


def analytics_root(project: Path, out: str | None = None) -> Path:
    """Where this project's analytics live: <project>/analytics unless --out overrides it."""
    root = winpath(out) if out else project / "analytics"
    root.mkdir(parents=True, exist_ok=True)
    return root


# ------------------------------------------------------------------ json
def jload(p: str | os.PathLike, default=None):
    p = winpath(p)
    if not p.exists():
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def jsave(p: str | os.PathLike, data) -> Path:
    p = winpath(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    return p


# ------------------------------------------------------------------ plain text for the user
def plain(s: str) -> str:
    """Strip markdown marks so a line opens cleanly in Notepad."""
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"^#+\s*", "", s, flags=re.M)
    return s


def write_txt(p: str | os.PathLike, text: str) -> Path:
    """UTF-8, CRLF, no markdown. Never edit these with sed -i (it turns CRLF into LF)."""
    p = winpath(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = plain(text).replace("\r\n", "\n").replace("\n", "\r\n")
    if not body.endswith("\r\n"):
        body += "\r\n"
    with open(p, "wb") as f:
        f.write(body.encode("utf-8"))
    return p


def heading(title: str, char: str = "=") -> str:
    return f"{title}\n{char * len(title)}"


def table(rows: list[list], headers: list[str]) -> str:
    """Fixed-width text table (plain text, no pipes needed by Notepad)."""
    cells = [[str(h) for h in headers]] + [[fmt(c) for c in r] for r in rows]
    widths = [max(len(r[i]) for r in cells) for i in range(len(headers))]
    out = []
    for k, r in enumerate(cells):
        out.append("  ".join(r[i].ljust(widths[i]) for i in range(len(headers))).rstrip())
        if k == 0:
            out.append("  ".join("-" * widths[i] for i in range(len(headers))))
    return "\n".join(out)


def fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        if abs(v) >= 100:
            return f"{v:,.0f}"
        if abs(v) >= 10:
            return f"{v:.1f}"
        return f"{v:.2f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


# ------------------------------------------------------------------ durations and dates
def iso_duration_s(s: str | None) -> float | None:
    """PT13M24S -> 804.0"""
    if not s:
        return None
    m = re.match(r"^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$", s)
    if not m:
        return None
    d, h, mi, se = m.groups()
    return (int(d or 0) * 86400 + int(h or 0) * 3600 + int(mi or 0) * 60 + float(se or 0))


def mmss(t: float | None) -> str:
    if t is None:
        return "-"
    t = int(round(t))
    return f"{t // 60}:{t % 60:02d}"


def parse_date(s: str) -> _dt.date:
    return _dt.date.fromisoformat(s[:10])


def days_between(a: str, b: str) -> int:
    return (parse_date(b) - parse_date(a)).days


def ffprobe_duration(p: str | os.PathLike) -> float | None:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(winpath(p))],
                           capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip()) if r.stdout.strip() else None
    except Exception:
        return None


# ------------------------------------------------------------------ words and sentences
_TERMINAL = re.compile(r'[.!?]["\')\]]*$')


def words_to_sentences(words: list[dict], section_of=None) -> list[dict]:
    """Group timed words into sentences on terminal punctuation.

    words: [{"w": str, "s": float, "e": float, ...}] (also accepts t0/t1 or start/end keys).
    Returns [{"i", "text", "t0", "t1", "section"}].
    """
    sents, cur = [], []
    for w in words:
        cur.append(w)
        if _TERMINAL.search(wtext(w)):
            sents.append(cur)
            cur = []
    if cur:
        sents.append(cur)
    out = []
    for i, ws in enumerate(sents):
        t0, t1 = wstart(ws[0]), wend(ws[-1])
        out.append({"i": i, "text": " ".join(wtext(w) for w in ws), "t0": t0, "t1": t1,
                    "words": len(ws), "section": section_of(t0) if section_of else None})
    return out


def wtext(w: dict) -> str:
    return str(w.get("w", w.get("word", w.get("text", "")))).strip()


def wstart(w: dict) -> float:
    for k in ("s", "t0", "start"):
        if k in w:
            return float(w[k])
    raise KeyError("word has no start time")


def wend(w: dict) -> float:
    for k in ("e", "t1", "end"):
        if k in w:
            return float(w[k])
    raise KeyError("word has no end time")


def norm_words(words: list[dict], offset: float = 0.0, extra: dict | None = None) -> list[dict]:
    out = []
    for w in words:
        d = {"w": wtext(w), "s": round(wstart(w) + offset, 3), "e": round(wend(w) + offset, 3)}
        if extra:
            d.update(extra)
        for k in ("sent", "sec", "item"):
            if k in w:
                d[k] = w[k]
        out.append(d)
    return out


def chars_to_words(align: dict, offset: float = 0.0) -> list[dict]:
    """ElevenLabs character alignment -> timed words."""
    chars = align.get("characters", [])
    s0 = align.get("character_start_times_seconds", [])
    e0 = align.get("character_end_times_seconds", [])
    words, cur, t_start, t_end = [], [], None, None
    for c, s, e in zip(chars, s0, e0):
        if c.isspace():
            if cur:
                words.append({"w": "".join(cur), "s": round(t_start + offset, 3), "e": round(t_end + offset, 3)})
                cur = []
            continue
        if not cur:
            t_start = s
        cur.append(c)
        t_end = e
    if cur:
        words.append({"w": "".join(cur), "s": round(t_start + offset, 3), "e": round(t_end + offset, 3)})
    return words


# ------------------------------------------------------------------ small stats
def median(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return st.mean(xs) if xs else None


def pct(a, b):
    return (100.0 * a / b) if b else None


def spearman(xs, ys):
    """Spearman rank correlation without scipy; None when under 3 pairs."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return None, n

    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks([p[0] for p in pairs]), ranks([p[1] for p in pairs])
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return (num / den if den else None), n


def log10(x):
    import math
    return math.log10(x) if x and x > 0 else None
