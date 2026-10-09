"""Import YouTube Studio exports (the numbers the API does not have).

Studio -> Analytics -> Advanced mode -> Export gives a zip with "Table data.csv" (one row per
video) and "Chart data.csv". The Content table carries Impressions and Impressions
click-through rate, which the Analytics API cannot return. A single video's retention chart
exports a CSV with the video position and the absolute / relative retention.

Column names vary by Studio version and locale, so columns are matched by lowercase
substrings, never by exact names. The window is read from the file name
(e.g. "Content 2026-09-01_2026-10-06 Astro Ranked.zip") or from --from/--to.
"""
from __future__ import annotations

import csv
import io
import re
import sys
import zipfile
from pathlib import Path

from .util import TODAY, jload, jsave, winpath

ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _hms_to_s(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    parts = s.split(":")
    try:
        parts = [float(p) for p in parts]
    except ValueError:
        return None
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0]


def _num(s: str) -> float | None:
    s = (s or "").strip().replace(",", "").replace("%", "")
    if s in ("", "-", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _find(headers: list[str], *needles: str, exclude: tuple[str, ...] = ()) -> int | None:
    for i, h in enumerate(headers):
        hl = h.lower()
        if all(n in hl for n in needles) and not any(x in hl for x in exclude):
            return i
    return None


def read_csv_text(text: str) -> list[list[str]]:
    return [row for row in csv.reader(io.StringIO(text.lstrip("﻿")))]


def parse_content_table(rows: list[list[str]], source: str, window: dict) -> dict:
    """Rows of the Content table -> {video_id: {...}}. Skips the Total row."""
    if not rows:
        return {}
    headers = rows[0]
    c_id = None
    for i, h in enumerate(headers):
        if h.strip().lower() in ("content", "video", "video id"):
            c_id = i
            break
    if c_id is None:
        # fall back to the first column whose values look like ids
        for i in range(len(headers)):
            if sum(1 for r in rows[1:] if len(r) > i and ID_RE.match(r[i].strip())) >= max(1, (len(rows) - 1) // 2):
                c_id = i
                break
    if c_id is None:
        return {}
    c_title = _find(headers, "title")
    c_imp = _find(headers, "impressions", exclude=("click", "rate"))
    c_ctr = _find(headers, "click-through") or _find(headers, "ctr")
    c_views = _find(headers, "views", exclude=("engaged",))
    c_eng = _find(headers, "engaged views")
    c_avd = _find(headers, "average view duration")
    c_avp = _find(headers, "average percentage") or _find(headers, "average view percentage")
    c_wt = _find(headers, "watch time")
    c_pub = _find(headers, "publish")
    c_subs = _find(headers, "subscribers")
    out = {}
    for r in rows[1:]:
        if len(r) <= c_id:
            continue
        vid = r[c_id].strip()
        if not ID_RE.match(vid):
            continue
        rec = {"source": source, "window": window, "imported": TODAY}
        if c_title is not None and len(r) > c_title:
            rec["title"] = r[c_title]
        if c_pub is not None and len(r) > c_pub:
            rec["published"] = r[c_pub]
        for key, col, conv in (("impressions", c_imp, _num), ("ctr_pct", c_ctr, _num), ("views", c_views, _num),
                               ("engaged_views", c_eng, _num), ("avd_s", c_avd, _hms_to_s), ("avp_pct", c_avp, _num),
                               ("watch_hours", c_wt, _num), ("subscribers", c_subs, _num)):
            if col is not None and len(r) > col:
                rec[key] = conv(r[col])
        out[vid] = rec
    return out


def parse_retention_csv(rows: list[list[str]]) -> list[dict]:
    """Studio's per-video retention export -> [{ratio, abs, rel}] with ratio in 0..1."""
    if not rows:
        return []
    headers = rows[0]
    c_pos = _find(headers, "position")
    c_abs = _find(headers, "absolute")
    c_rel = _find(headers, "relative")
    if c_pos is None or (c_abs is None and c_rel is None):
        return []
    out = []
    for r in rows[1:]:
        pos = _num(r[c_pos]) if len(r) > c_pos else None
        if pos is None:
            continue
        ratio = pos / 100.0 if pos > 1.0 else pos
        rec = {"ratio": round(ratio, 4)}
        if c_abs is not None and len(r) > c_abs:
            a = _num(r[c_abs])
            rec["abs"] = (a / 100.0 if a is not None and a > 1.5 else a)
        if c_rel is not None and len(r) > c_rel:
            rec["rel"] = _num(r[c_rel])
        out.append(rec)
    return out


def window_from_name(name: str, args) -> dict:
    dates = DATE_RE.findall(name)
    w = {"from": getattr(args, "date_from", None), "to": getattr(args, "date_to", None)}
    if len(dates) >= 2 and not (w["from"] and w["to"]):
        w = {"from": dates[0], "to": dates[1]}
    return w


def cmd_studio(args) -> None:
    from .config import load_channel
    project = winpath(args.project).resolve()
    cfg = load_channel(project, args.out)
    root = Path(cfg["root"])
    latest = (root / "latest.txt").read_text(encoding="utf-8").strip() if (root / "latest.txt").exists() else TODAY
    snap = root / "pull" / latest
    sdir = snap / "studio"
    sdir.mkdir(parents=True, exist_ok=True)
    content = jload(sdir / "content.json", {}) or {}
    n_content = n_ret = 0
    for path in args.files:
        p = winpath(path)
        if not p.exists():
            print(f"  missing: {p}")
            continue
        texts = []
        if p.suffix.lower() == ".zip":
            with zipfile.ZipFile(p) as z:
                for m in z.namelist():
                    if m.lower().endswith(".csv"):
                        texts.append((f"{p.name}/{m}", z.read(m).decode("utf-8-sig", errors="replace")))
        else:
            texts.append((p.name, p.read_text(encoding="utf-8-sig", errors="replace")))
        for name, text in texts:
            rows = read_csv_text(text)
            if not rows:
                continue
            hdr = " ".join(rows[0]).lower()
            if "position" in hdr and ("retention" in hdr or "absolute" in hdr or "relative" in hdr):
                vid = args.video
                if not vid:
                    m = re.search(r"([A-Za-z0-9_-]{11})", name)
                    vid = m.group(1) if m else None
                if not vid:
                    print(f"  {name}: a retention curve but no video id; pass --video <id>")
                    continue
                curve = parse_retention_csv(rows)
                jsave(sdir / f"retention_{vid}.json", {"video": vid, "source": name, "imported": TODAY, "points": curve})
                n_ret += 1
                print(f"  {name}: retention curve for {vid}, {len(curve)} points")
            else:
                got = parse_content_table(rows, name, window_from_name(name, args))
                if got:
                    content.update(got)
                    n_content += len(got)
                    print(f"  {name}: {len(got)} videos "
                          f"({sum(1 for g in got.values() if g.get('impressions') is not None)} with impressions)")
                else:
                    print(f"  {name}: no video rows recognised (headers: {rows[0][:6]})")
    if n_content:
        jsave(sdir / "content.json", content)
    print(f"studio import into {sdir}: {n_content} content rows, {n_ret} retention curves")
    if not (n_content or n_ret):
        sys.exit(1)
