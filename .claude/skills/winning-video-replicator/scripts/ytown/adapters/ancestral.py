"""Ancestral Stories (zayin): stick-figure panels + SVG cards, Node.

Reads episodes/NNN_slug/ep/: alignment.json (ElevenLabs characters -> words), sentences.json
({i, text, start, end}), shots.json ({total, shots:[...]}, read generically), outro_alignment.json
+ outro_vo.mp3 (the outro voice appended after the main track). Titles are not stored in the
folder; the mapper relies on the uploaded file name ("Ancestral Stories - <title>.mp4") and the
duration.
"""
from __future__ import annotations

from pathlib import Path

from ..util import chars_to_words, ffprobe_duration, jload
from . import duration_of, generic_shot, mp4s_in

DELIVERABLES = Path("C:/Users/admin/Downloads/ANCESTRAL VIDS")


def episodes(project: Path) -> list[dict]:
    out = []
    for d in sorted((project / "episodes").glob("[0-9]*")):
        if not d.is_dir() or not (d / "ep" / "sentences.json").exists():
            continue
        mp4 = [p for p in mp4s_in(d / "ep") if "final" in Path(p).name] or mp4s_in(d / "ep")
        out.append({"folder": str(d), "slug": d.name, "title": d.name.split("_", 1)[-1].replace("_", " ").title(), "mp4": mp4,
                    "duration": duration_of(mp4)})
    return out


def timeline(project: Path, ep: dict, cache: Path):
    e = Path(ep["folder"]) / "ep"
    words = chars_to_words(jload(e / "alignment.json", {}) or {})
    sents = jload(e / "sentences.json", []) or []
    sentences = [{"i": s.get("i", i), "text": s.get("text", ""), "t0": float(s["start"]), "t1": float(s["end"]),
                  "words": len(str(s.get("text", "")).split()), "section": None} for i, s in enumerate(sents)]
    shots_j = jload(e / "shots.json", {}) or {}
    raw = shots_j.get("shots", shots_j if isinstance(shots_j, list) else [])
    beats = [b for b in (generic_shot(s, i) for i, s in enumerate(raw)) if b]
    # zayin shot types: PANEL (generated picture), REUSE (a library panel again), NEG (red-X negation card), TEXT (stat card)
    for b, s in zip(beats, raw):
        typ = str(s.get("type", "")).upper()
        if typ in ("NEG", "TEXT", "CARD"):
            b["kind"], b["text"] = "card", True
            b["label"] = f"{typ.lower()} {s.get('id', '')}"[:80]
        elif typ in ("PANEL", "REUSE"):
            b["kind"] = "still"
            b["label"] = f"{typ.lower()} {s.get('id', '')}"[:80]
    for a, b in zip(beats, beats[1:]):
        if a["t1"] is None:
            a["t1"] = b["t0"]
    total = float(shots_j.get("total") or 0) or (words[-1]["e"] if words else 0)
    if beats and beats[-1]["t1"] is None:
        beats[-1]["t1"] = total
    sections = []
    main_len = ffprobe_duration(e / "vo.mp3") if (e / "vo.mp3").exists() else None
    oa = jload(e / "outro_alignment.json")
    if oa and main_len:
        ow = chars_to_words(oa, offset=main_len)
        words += ow
        if ow:
            sections.append({"name": "OUTRO", "kind": "outro", "t0": ow[0]["s"], "t1": ow[-1]["e"]})
    attrs = {
        "panels": sum(1 for b in beats if b["kind"] == "still"),
        "cards": sum(1 for b in beats if b["kind"] == "card"),
        "sentences": len(sentences),
        "thumbnail": next((str(p) for p in (Path(ep["folder"]) / "ep" / "thumb").glob("*.png")), None) if (e / "thumb").exists() else None,
    }
    return sections, sentences, beats, [], words, attrs
