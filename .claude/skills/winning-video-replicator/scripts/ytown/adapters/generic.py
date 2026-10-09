"""Any channel without a pipeline: a timeline from files the user or the session drops in.

analytics/generic/<video id>/
  transcript.json   teardown.py transcribe format: {"words": [{"w","s","e"}]}  (or a bare list)
  cuts.json         {"cuts": [t, t, ...]} from `ytown.py cuts <mp4> --video <id>` (or a bare list)
  sections.json     hand-written [{"name", "t0", "t1"}]
  episode.mp4       optional, for the duration
The channel-pipeline teardown kit makes the transcript (free, local Whisper).
"""
from __future__ import annotations

from pathlib import Path

from ..timeline import classify_section
from ..util import ffprobe_duration, jload, norm_words


def episodes(project: Path) -> list[dict]:
    root = project / "analytics" / "generic"
    out = []
    if not root.exists():
        return out
    for d in sorted(root.iterdir()):
        if d.is_dir() and len(d.name) == 11:
            mp4 = [str(p) for p in d.glob("*.mp4")]
            out.append({"folder": str(d), "slug": d.name, "title": d.name, "mp4": mp4, "video_id": d.name,
                        "duration": ffprobe_duration(mp4[0]) if mp4 else None})
    return out


def timeline(project: Path, ep: dict, cache: Path):
    d = Path(ep["folder"])
    tj = jload(d / "transcript.json", []) or []
    words = norm_words(tj.get("words", []) if isinstance(tj, dict) else tj)
    cuts = jload(d / "cuts.json")
    beats = []
    if cuts:
        times = cuts.get("cuts") if isinstance(cuts, dict) else cuts
        dur = ep.get("duration") or (cuts.get("duration") if isinstance(cuts, dict) else None) or (words[-1]["e"] if words else (times[-1] if times else 0))
        edges = [0.0] + [float(t) for t in times] + [float(dur)]
        beats = [{"t0": a, "t1": b, "kind": "beat", "label": f"shot {i}", "moving": None, "text": None} for i, (a, b) in enumerate(zip(edges, edges[1:])) if b > a]
    secs = jload(d / "sections.json", []) or []
    sections = [{"name": s["name"], "kind": s.get("kind") or classify_section(s["name"], i), "t0": float(s["t0"]), "t1": float(s["t1"])} for i, s in enumerate(secs)]
    return sections, [], beats, [], words, {"has_transcript": bool(words), "has_cuts": bool(beats)}
