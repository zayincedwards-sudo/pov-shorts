"""Shot boundaries for a video without a build timeline (generic and clipping channels).

Same ffmpeg scene detection as the channel-pipeline teardown kit (soft > 0.10, hard > 0.25),
but the cut TIMES are kept, which the teardown's cuts JSON does not. Writes
analytics/generic/<video id>/cuts.json = {"file", "duration", "cuts": [hard times], "soft": [soft times]}.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .config import load_channel
from .util import TODAY, ffprobe_duration, jsave, winpath


def detect(path: Path, soft: float = 0.10, hard: float = 0.25) -> dict:
    dur = ffprobe_duration(path) or 0.0
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(path), "-an", "-vf", f"scale=320:-2,select='gt(scene,{soft})',metadata=print",
                        "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    times, scores = [], []
    for line in r.stderr.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            times.append(float(m.group(1)))
            continue
        m = re.search(r"lavfi\.scene_score=([\d.]+)", line)
        if m and len(scores) < len(times):
            scores.append(float(m.group(1)))
    pairs = list(zip(times, scores))
    return {"file": str(path), "duration": round(dur, 2), "made": TODAY,
            "cuts": [round(t, 2) for t, s in pairs if s > hard], "soft": [round(t, 2) for t, s in pairs if s > soft]}


def cmd_cuts(args) -> None:
    project = winpath(args.project).resolve()
    cfg = load_channel(project, args.out)
    root = Path(cfg["root"])
    p = winpath(args.file)
    if not p.exists():
        raise SystemExit(f"not found: {p}")
    res = detect(p)
    out = root / "generic" / args.video / "cuts.json"
    jsave(out, res)
    mins = res["duration"] / 60 or 1
    print(f"{p.name}: {len(res['cuts'])} hard cuts ({len(res['cuts']) / mins:.1f}/min), {len(res['soft'])} soft -> {out}")
