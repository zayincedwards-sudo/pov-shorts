"""Otto Explained: drawn doodle taxonomy videos, Python (Patrick/v2).

Reads episodes/NNN-slug/: vo/vo_align.json (items with absolute word times and sentence
indices), shots/item_NN.json (shots anchored to a sentence, optionally a word), metadata.md
(title), hook.md. Item 0 is the hook. Shot kinds come from the layer names: grid, hero, text,
host (Otto) is a flag on the beat.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..util import jload, norm_words, wtext
from . import duration_of, mp4s_in, norm_title

DELIVERABLES = Path("C:/Users/admin/Downloads/otto")


def _root(project: Path) -> Path:
    return project / "v2" if (project / "v2" / "episodes").exists() else project


def episodes(project: Path) -> list[dict]:
    out = []
    for d in sorted((_root(project) / "episodes").glob("[0-9]*")):
        if not d.is_dir() or not (d / "vo" / "vo_align.json").exists():
            continue
        title = _title(d / "metadata.md") or d.name
        mp4 = mp4s_in(d, "episode.mp4")
        if DELIVERABLES.exists():
            nt = norm_title(title)
            mp4 += [str(p) for p in DELIVERABLES.glob("*.mp4") if norm_title(p.stem) == nt]
        out.append({"folder": str(d), "slug": d.name, "title": title, "mp4": mp4, "duration": duration_of(mp4)})
    return out


def _title(p: Path) -> str | None:
    if not p.exists():
        return None
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, ln in enumerate(lines[:60]):
        m = re.match(r"^\s*(?:#+\s*)?(?:\*\*)?Title(?:\*\*)?\s*[:：]\s*(.+?)\s*$", ln, re.I)
        if m:
            return m.group(1).strip("* `\"")
        if re.match(r"^\s*#+\s*Title\s*$", ln, re.I):          # "## Title" with the title on the next line
            for nxt in lines[i + 1:i + 4]:
                if nxt.strip():
                    return nxt.strip().strip("* `\"")
    return None


def _kind(layers: list) -> tuple[str, bool, bool, bool]:
    names = [str(l[0]).lower() for l in layers if isinstance(l, (list, tuple)) and l]
    host = any(n.startswith("otto") or "host" in n for n in names)
    text_only = bool(names) and all(("text" in n or "caption" in n or "label" in n) for n in names)
    if any("grid" in n for n in names):
        return "grid", False, host, text_only
    if any("hero" in n or "limb" in n or "nebula" in n for n in names):
        return "hero", True, host, text_only
    if text_only:
        return "text", False, host, True
    return "flat", False, host, text_only


def timeline(project: Path, ep: dict, cache: Path):
    d = Path(ep["folder"])
    al = jload(d / "vo" / "vo_align.json", {}) or {}
    items = al.get("items", [])
    words, sections, beats = [], [], []
    for it in items:
        start, end = float(it.get("start", 0)), float(it.get("end", 0))
        ws = it.get("words", [])
        # word times are absolute in the files seen; guard the relative case
        offset = start if (ws and float(ws[0]["s"]) < start - 0.5) else 0.0
        iw = norm_words(ws, offset=offset, extra={"item": it.get("item")})
        words += iw
        name = str(it.get("title", f"item {it.get('item')}"))
        kind = "hook" if (it.get("item") == 0 or "HOOK" in name.upper()) else "item"
        sections.append({"name": re.sub(r"^\d+\.\s*", "", name), "kind": kind, "t0": start, "t1": end})
        spec = jload(d / "shots" / f"item_{int(it.get('item', 0)):02d}.json", {}) or {}
        shots = spec.get("shots", [])
        times = []
        for sh in shots:
            sent = sh.get("sent", 0)
            sw = [w for w in iw if w.get("sent") == sent]
            t0 = sw[0]["s"] if sw else start
            anchor = sh.get("word")
            if anchor is not None and sw:
                if isinstance(anchor, int) and 0 <= anchor < len(sw):
                    t0 = sw[anchor]["s"]
                elif isinstance(anchor, str):
                    key = re.sub(r"[^a-z0-9]", "", anchor.lower())
                    for w in sw:
                        if re.sub(r"[^a-z0-9]", "", wtext(w).lower()) == key:
                            t0 = w["s"]
                            break
            times.append(t0)
        for k, sh in enumerate(shots):
            t0 = times[k]
            t1 = times[k + 1] if k + 1 < len(times) else end
            if t1 <= t0:
                t1 = t0 + 0.5
            kind, moving, host, text = _kind(sh.get("layers", []))
            beats.append({"t0": round(t0, 3), "t1": round(t1, 3), "kind": kind, "label": ", ".join(str(l[0]) for l in sh.get("layers", [])[:3])[:80],
                          "moving": moving or bool(sh.get("anim")), "text": text, "host": host})
    hook_md = d / "hook.md"
    attrs = {
        "items": max(0, len(items) - 1),
        "host_beats_pct": round(100.0 * sum(1 for b in beats if b.get("host")) / len(beats), 1) if beats else None,
        "hook_words": len(hook_md.read_text(encoding="utf-8", errors="replace").split()) if hook_md.exists() else None,
        "thumbnail": str(d / "thumb_1280.png") if (d / "thumb_1280.png").exists() else None,
        "thumb_metrics": jload(d / "thumb_metrics.json"),
    }
    return sections, [], beats, [], words, attrs
