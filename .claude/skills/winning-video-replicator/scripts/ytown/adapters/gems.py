"""GEMS (Vault of Stones): price-ladder gem explainers, Python + ffmpeg.

Reads episodes/NNN-slug/: vo/words.json (absolute word times with section index), vo/sections.json,
vo/takes.json, shots/shots.json (shots, overlays, sfx), bed.json, upload info.txt. The ANIME
project copies this layout for everything but the picture, so anime.py imports from here.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..timeline import classify_section
from ..util import jload, norm_words
from . import duration_of, mp4s_in, upload_info_title


def episodes(project: Path) -> list[dict]:
    out = []
    for d in sorted((project / "episodes").glob("[0-9]*")):
        if not d.is_dir():
            continue
        title = upload_info_title(d / "upload info.txt")
        mp4 = []
        if title:
            mp4 += mp4s_in(project / "upload" / title)
        mp4 += mp4s_in(d / "render")
        out.append({"folder": str(d), "slug": d.name, "title": title or d.name, "mp4": mp4, "duration": duration_of(mp4)})
    return out


def timeline(project: Path, ep: dict, cache: Path):
    d = Path(ep["folder"])
    words = norm_words(jload(d / "vo" / "words.json", []) or [])
    secs = jload(d / "vo" / "sections.json", []) or []
    sections = [{"name": s["name"], "kind": classify_section(s["name"], s.get("i")), "t0": float(s["t0"]), "t1": float(s["t1"])} for s in secs]
    shots = jload(d / "shots" / "shots.json", {}) or {}
    beats, spans = [], []
    for i, s in enumerate(shots.get("shots", [])):
        kind = s.get("kind", "clip")
        moving = True if kind == "clip" else (str(s.get("motion", "none")).lower() not in ("none", "", "static"))
        beats.append({"t0": float(s["t0"]), "t1": float(s["t1"]), "kind": kind if kind in ("clip", "still", "grid", "card") else "beat",
                      "label": (s.get("want") or s.get("src") or f"shot {i}")[:80], "moving": moving, "text": kind == "card"})
    for o in shots.get("overlays", []):
        card = o.get("card", {}) or {}
        ck = str(card.get("kind", "card"))
        spans.append({"t0": float(o["t0"]), "t1": float(o["t1"]), "type": "price_flash" if ck == "price" else "card",
                      "label": f"{ck}: {card.get('text') or card.get('num') or ''}"[:80]})
    for s in shots.get("sfx", []):
        spans.append({"t0": float(s["t"]), "t1": float(s["t"]) + 0.6, "type": "sfx", "label": Path(str(s.get("src", "sfx"))).stem})
    takes = jload(d / "vo" / "takes.json", []) or []
    for ti, sec_ids in enumerate(takes):
        if sec_ids and sections and sec_ids[0] < len(sections):
            t0 = sections[sec_ids[0]]["t0"]
            t1 = sections[sec_ids[-1]]["t1"] if sec_ids[-1] < len(sections) else t0
            spans.append({"t0": t0, "t1": t1, "type": "take", "label": f"take {ti}"})
    bed = jload(d / "bed.json")
    if bed:
        grid = next((b for b in beats if b["kind"] == "grid"), None)
        start = grid["t0"] if (grid and bed.get("fade_across") == "grid") else 0.0
        end = max([b["t1"] for b in beats] + [s["t1"] for s in sections] + [0.0])
        spans.append({"t0": start, "t1": end, "type": "music", "label": f"{bed.get('track', 'bed')} {bed.get('under_db', '')} dB under"})
    attrs = {
        "takes": len(takes) or None,
        "bed": bool(bed), "bed_under_db": (bed or {}).get("under_db"),
        "price_flashes": sum(1 for s in spans if s["type"] == "price_flash"),
        "cards": sum(1 for s in spans if s["type"] == "card"),
        "sections": len(sections),
        "script_words": _script_words(d / "script.md"),
        "thumbnail": _thumb(project, d, ep.get("title")),
    }
    return sections, [], beats, spans, words, attrs


def _script_words(p: Path) -> int | None:
    if not p.exists():
        return None
    txt = p.read_text(encoding="utf-8", errors="replace")
    txt = re.sub(r"\[shot:[^\]]*\]|\{[^}]*\}|^#.*$", " ", txt, flags=re.M)
    return len(txt.split())


def _thumb(project: Path, d: Path, title: str | None) -> str | None:
    cands = []
    if title:
        cands += list((project / "upload" / title).glob("thumbnail.*"))
    cands += sorted((d / "thumb").glob("thumb_v*.jpg")) if (d / "thumb").exists() else []
    return str(cands[0]) if cands else None
