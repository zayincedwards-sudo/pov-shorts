"""Astro (Astro Ranked): white-card list explainers with real recordings, Node.

Reads episodes/eNNN_slug/: plan.js (title comment, ITEMS names), ep/words.json ({w, t0, t1}),
ep/gaps.json (recording windows), ep/seg/list.txt + the segment mp4s (the beat timeline comes
from their durations in concat order; cached under analytics/join/cache/), thumb_spec.json.
Items start where the item's name is first spoken after the previous item (Astro's own rule:
the first picture cues AFTER the name). Everything before item one is the hook.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..util import ffprobe_duration, jload, jsave, norm_words, wtext
from . import duration_of, mp4s_in, norm_title

DELIVERABLES = Path("C:/Users/admin/Downloads/ASTRO VIDS")


def episodes(project: Path) -> list[dict]:
    out = []
    for d in sorted((project / "episodes").glob("e[0-9]*")):
        if not d.is_dir() or not (d / "plan.js").exists():
            continue
        title = _title(d / "plan.js") or d.name
        mp4 = mp4s_in(d / "ep", "episode.mp4")
        if DELIVERABLES.exists():
            nt = norm_title(title)
            mp4 += [str(p) for p in DELIVERABLES.glob("*.mp4") if norm_title(p.stem) == nt]
        out.append({"folder": str(d), "slug": d.name, "title": title, "mp4": mp4, "duration": duration_of(mp4)})
    return out


def _title(plan: Path) -> str | None:
    head = "\n".join(plan.read_text(encoding="utf-8", errors="replace").splitlines()[:6])
    m = re.search(r'//\s*Episode\s+\d+\s*[—:-]+\s*["“](.+?)["”]', head)
    return m.group(1).strip() if m else None


def _items(plan: Path) -> list[dict]:
    txt = plan.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"\bITEMS\s*=\s*\[(.*?)\n\];", txt, re.S)
    if not m:
        return []
    items = []
    for line in m.group(1).splitlines():
        s = line.strip()
        if s.startswith("//") or not s.startswith("{"):
            continue
        nm = re.search(r"name:\s*['\"]([^'\"]+)['\"]", s)
        if nm:
            items.append({"name": nm.group(1), "thumb": "thumb:" in s})
    return items


def _segment_timeline(d: Path, cache: Path) -> list[dict]:
    seg = d / "ep" / "seg"
    lst = seg / "list.txt"
    if not lst.exists():
        return []
    files = [ln.split("'")[1] for ln in lst.read_text(encoding="utf-8").splitlines() if ln.startswith("file ")]
    cp = cache / f"{d.name}_segments.json"
    known = jload(cp, {}) or {}
    changed = False
    beats, t = [], 0.0
    for f in files:
        p = seg / f
        key = f"{f}:{p.stat().st_mtime_ns if p.exists() else 0}"
        dur = known.get(key)
        if dur is None:
            dur = ffprobe_duration(p) if p.exists() else None
            if dur is None:
                continue
            known[key] = dur
            changed = True
        beats.append({"t0": round(t, 3), "t1": round(t + dur, 3), "kind": "beat", "label": f, "moving": None, "text": None})
        t += dur
    if changed:
        jsave(cp, known)
    return beats


def _find_phrase(words: list[dict], phrase: str, start_idx: int) -> int | None:
    toks = [re.sub(r"[^a-z0-9]", "", w.lower()) for w in phrase.split()]
    toks = [t for t in toks if t and t not in ("the", "a", "an")]
    if not toks:
        return None
    norm = [re.sub(r"[^a-z0-9]", "", wtext(w).lower()) for w in words]
    for i in range(start_idx, len(norm) - len(toks) + 1):
        if all(norm[i + k].startswith(toks[k]) for k in range(len(toks))):
            return i
    return None


def timeline(project: Path, ep: dict, cache: Path):
    d = Path(ep["folder"])
    words = norm_words(jload(d / "ep" / "words.json", []) or [])
    gaps = jload(d / "ep" / "gaps.json", []) or []
    spans = [{"t0": float(g["start"]), "t1": float(g["end"]), "type": "recording", "label": (g.get("caption") or g.get("slug") or "recording")[:80]} for g in gaps]
    beats = _segment_timeline(d, cache)
    items = _items(d / "plan.js")
    sections, idx = [], 0
    bounds = []
    for it in items:
        k = _find_phrase(words, it["name"], idx)
        if k is None:
            continue
        bounds.append((it["name"], words[k]["s"]))
        idx = k + 1
    end = max([w["e"] for w in words] + [s["t1"] for s in spans] + [b["t1"] for b in beats] + [0.0])
    if bounds:
        sections.append({"name": "HOOK", "kind": "hook", "t0": 0.0, "t1": bounds[0][1]})
        for i, (name, t0) in enumerate(bounds):
            t1 = bounds[i + 1][1] if i + 1 < len(bounds) else end
            sections.append({"name": name, "kind": "item", "t0": t0, "t1": t1})
    chunks = d / "ep" / "chunks"
    attrs = {
        "items_planned": len(items), "items_found": len(bounds),
        "thumb_cells": sum(1 for it in items if it["thumb"]),
        "recordings": len(gaps), "recording_seconds": round(sum(s["t1"] - s["t0"] for s in spans), 1),
        "voice_chunks": len(list(chunks.glob("*.wav")) + list(chunks.glob("*.mp3"))) if chunks.exists() else None,
        "segments": len(beats),
        "thumbnail": str(d / "ep" / "thumbnail.png") if (d / "ep" / "thumbnail.png").exists() else None,
    }
    return sections, [], beats, spans, words, attrs
