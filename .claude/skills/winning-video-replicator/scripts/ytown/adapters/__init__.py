"""Per-project adapters: each turns a pipeline's own build files into the join timeline.

An adapter module exposes:
  episodes(project: Path) -> [ {folder, slug, title, mp4: [paths], duration, video_id?} ]
  timeline(project: Path, ep: dict, cache: Path) -> (sections, sentences, beats, spans, words, attrs)
Nothing here re-analyses an mp4: the timeline comes from the alignments, shot lists and plans
the pipeline already wrote. ffprobe is used only for durations.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path

from ..util import ffprobe_duration, winpath

NAMES = ("gems", "astro", "otto", "ancestral", "anime", "clips", "generic")


def get(name: str):
    if name not in NAMES:
        raise SystemExit(f"unknown adapter {name!r}; one of {NAMES}")
    return importlib.import_module(f"ytown.adapters.{name}")


def norm_title(s: str | None) -> str:
    """Lowercase alphanumerics only, so 'Every Ruby Type Explained' == 'every-ruby-type-explained.mp4'."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def upload_info_title(p: Path) -> str | None:
    """GEMS-style `upload info.txt`: the first non-empty line after the TITLE heading and its dashes."""
    if not p.exists():
        return None
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().upper() == "TITLE":
            for nxt in lines[i + 1:i + 5]:
                t = nxt.strip()
                if t and not set(t) <= {"-", "="}:
                    return t
    return None


def duration_of(paths: list) -> float | None:
    for p in paths:
        p = winpath(p)
        if p.exists():
            d = ffprobe_duration(p)
            if d:
                return round(d, 2)
    return None


def mp4s_in(folder: Path, pattern: str = "*.mp4") -> list[str]:
    folder = winpath(folder)
    if not folder.exists():
        return []
    files = sorted(folder.glob(pattern), key=lambda p: -p.stat().st_size)
    return [str(p) for p in files]


def generic_shot(d: dict, i: int = 0) -> dict | None:
    """Read a shot dict with unknown field names into {t0, t1, kind, label, moving, text}."""
    t0 = next((float(d[k]) for k in ("t0", "start", "t", "s", "in") if k in d and d[k] is not None), None)
    t1 = next((float(d[k]) for k in ("t1", "end", "e", "out") if k in d and d[k] is not None), None)
    if t0 is None:
        return None
    if t1 is None and "dur" in d:
        t1 = t0 + float(d["dur"])
    kind = str(d.get("kind") or d.get("type") or d.get("layer") or "beat").lower()
    if "card" in kind:
        kind = "card"
    elif "panel" in kind or "image" in kind or "still" in kind:
        kind = "still"
    elif "clip" in kind or "video" in kind:
        kind = "clip"
    label = d.get("label") or d.get("src") or d.get("file") or d.get("want") or d.get("id") or f"shot {i}"
    moving = d.get("moving")
    if moving is None and "motion" in d:
        moving = str(d["motion"]).lower() not in ("", "none", "static", "false", "0")
    return {"t0": t0, "t1": t1, "kind": kind, "label": str(label)[:80], "moving": moving, "text": d.get("text") if isinstance(d.get("text"), bool) else None}
