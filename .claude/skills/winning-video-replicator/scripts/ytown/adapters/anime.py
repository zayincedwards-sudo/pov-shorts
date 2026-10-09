"""ANIME: official clips played whole with sparse narration bursts (GEMS base).

Reads episodes/NNN-slug/render/timeline.json (segments with start/len, voice bursts with
start/dur/text, episode tags) and vo/bursts.json (word times relative to each burst).
"""
from __future__ import annotations

from pathlib import Path

from ..timeline import classify_section
from ..util import jload, norm_words
from . import duration_of, mp4s_in, upload_info_title


def episodes(project: Path) -> list[dict]:
    out = []
    for d in sorted((project / "episodes").glob("[0-9]*")):
        tl = d / "render" / "timeline.json"
        if not d.is_dir() or not tl.exists():
            continue
        t = jload(tl, {}) or {}
        title = t.get("title") or upload_info_title(d / "upload info.txt") or d.name
        mp4 = mp4s_in(d / "render", "episode.mp4")
        if title:
            mp4 += mp4s_in(project / "upload" / title)
        out.append({"folder": str(d), "slug": d.name, "title": title, "mp4": mp4, "duration": duration_of(mp4) or t.get("runtime")})
    return out


def timeline(project: Path, ep: dict, cache: Path):
    d = Path(ep["folder"])
    t = jload(d / "render" / "timeline.json", {}) or {}
    beats, spans, words = [], [], []
    for i, s in enumerate(t.get("segments", [])):
        t0, t1 = float(s.get("start", 0)), float(s.get("start", 0)) + float(s.get("len", 0))
        kind = "montage" if s.get("kind") == "montage" else "clip"
        beats.append({"t0": t0, "t1": t1, "kind": kind, "label": f"{s.get('id', '')} {s.get('t0', '')}-{s.get('t1', '')}"[:80], "moving": True, "text": False})
    bursts = {b.get("section"): b for b in (jload(d / "vo" / "bursts.json", []) or [])}
    sec_names = {}
    for v in t.get("voice", []):
        t0 = float(v.get("start", 0))
        t1 = t0 + float(v.get("dur", 0))
        spans.append({"t0": t0, "t1": t1, "type": "narration", "label": (v.get("name") or "")[:40] + ": " + (v.get("text") or "")[:60]})
        sec_names[v.get("section")] = v.get("name")
        b = bursts.get(v.get("section"))
        if b and b.get("words"):
            words += norm_words(b["words"], offset=t0, extra={"sec": v.get("section")})
    for tg in t.get("tags", []):
        spans.append({"t0": float(tg.get("start", 0)), "t1": float(tg.get("start", 0)) + float(tg.get("len", 0)), "type": "tag", "label": tg.get("text", "")[:60]})
    sections, by = [], {}
    for s in t.get("segments", []):
        k = s.get("section")
        t0, t1 = float(s.get("start", 0)), float(s.get("start", 0)) + float(s.get("len", 0))
        lo, hi = by.get(k, (t0, t1))
        by[k] = (min(lo, t0), max(hi, t1))
    for k in sorted(by, key=lambda x: by[x][0]):
        name = sec_names.get(k) or f"section {k}"
        sections.append({"name": name, "kind": classify_section(name, k), "t0": by[k][0], "t1": by[k][1]})
    words.sort(key=lambda w: w["s"])
    runtime = float(t.get("runtime") or 0)
    narr = sum(s["t1"] - s["t0"] for s in spans if s["type"] == "narration")
    attrs = {"clips": sum(1 for b in beats if b["kind"] == "clip"), "montages": sum(1 for b in beats if b["kind"] == "montage"),
             "narration_seconds": round(narr, 1), "narration_share": round(100.0 * narr / runtime, 1) if runtime else None,
             "warnings": len(t.get("warnings", []) or []),
             "thumbnail": next((str(p) for p in (d / "thumb").glob("*.jpg")), None) if (d / "thumb").exists() else None}
    return sections, [], beats, spans, words, attrs
