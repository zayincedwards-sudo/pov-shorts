"""Public "most replayed" heatmaps of reference videos, for shape comparison (free, yt-dlp)."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .util import TODAY, jsave, winpath

ID_RE = re.compile(r"(?:v=|youtu\.be/|shorts/|^)([A-Za-z0-9_-]{11})(?:[&?/]|$)")


def fetch_heatmap(url_or_id: str) -> dict | None:
    target = url_or_id if url_or_id.startswith("http") else f"https://www.youtube.com/watch?v={url_or_id}"
    r = subprocess.run(["yt-dlp", "--dump-single-json", "--skip-download", "--no-warnings", target],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    j = json.loads(r.stdout)
    hm = j.get("heatmap") or []
    return {
        "id": j.get("id"), "title": j.get("title"), "channel": j.get("channel") or j.get("uploader"),
        "channel_id": j.get("channel_id"), "duration": j.get("duration"), "views": j.get("view_count"),
        "upload_date": j.get("upload_date"), "fetched": TODAY,
        "heatmap": [{"start": h.get("start_time"), "end": h.get("end_time"), "value": h.get("value")} for h in hm],
    }


def heat_summary(h: dict) -> str:
    pts = h.get("heatmap") or []
    if not pts or not h.get("duration"):
        return "no heatmap (YouTube shows one only above a view threshold)"
    top = sorted(pts, key=lambda p: -(p["value"] or 0))[:3]
    d = h["duration"]
    return "peaks at " + ", ".join(f"{int(p['start'] // 60)}:{int(p['start'] % 60):02d} ({100 * p['start'] / d:.0f}%)" for p in top)


def cmd_heatmap(args) -> None:
    from .config import load_channel
    project = winpath(args.project).resolve()
    cfg = load_channel(project, args.out)
    root = Path(cfg["root"]) / "reference"
    root.mkdir(parents=True, exist_ok=True)
    for u in args.urls:
        h = fetch_heatmap(u)
        if not h:
            print(f"  {u}: yt-dlp returned nothing")
            continue
        jsave(root / f"{h['id']}.heatmap.json", h)
        print(f"  {h['id']} {str(h['title'])[:60]} ({h.get('views')} views): {heat_summary(h)}")
