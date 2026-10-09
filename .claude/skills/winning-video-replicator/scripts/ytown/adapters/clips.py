"""Clipping channels (Pull Up The Tape, SoftChaos, TALARICO): vertical speed clips with a publisher.

The publisher's publish/uploaded_manifest.json already maps each clip file to its YouTube video
id, so no title matching is needed.

The timeline comes from the clip's own RECIPE when the project keeps one (CLIPPING and
TALARICO: shorts/work/recipe_<tag>.json, matched on its "name" = the delivered file's stem). A
recipe is the build: the source pieces (window seconds), the word file, caption fixes, the boom
time, the three narration labels, the flashes, the sound hits, the bed and the frozen tail. From
it this adapter rebuilds, on the clip's own output timeline:
  words     the captioned words (the same mapping build_clip_speed.py does: words inside each
            piece, shifted to output time, then the recipe's caption fixes)
  sections  OPEN (premise label: 0 to the yellow label's end) -> hook; BUILD (to the boom);
            PAYOFF (boom to the end of the dialogue); END (the frozen verdict tail)
  beats     one per source piece (a cut on the output timeline), kind clip, moving
  spans     label (yellow / red / green, with their text), flash, sfx (file), boom, music (bed,
            0 to the boom), freeze (the tail)
  attrs     batch letter, bed, emoji, boom position, body seconds, pieces, cuts per minute,
            flashes, sfx hits, label lengths, our own score, tone word, episode date and the days
            from the episode to the post
Without a recipe: a transcript JSON beside the clip (<stem>.words.json or <stem>.json) and the
shot list from analytics/generic/<video id>/cuts.json (`ytown.py cuts`), as before. Shorts loop,
so their retention and view percentage are read in Shorts mode by the analysis.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from ..util import jload, norm_words, winpath
from . import duration_of

_RECIPES: dict = {}


def episodes(project: Path) -> list[dict]:
    rows = jload(project / "publish" / "uploaded_manifest.json", []) or []
    out, seen = [], set()
    for r in rows:
        if r.get("destination") != "youtube" or not r.get("video_id") or r["video_id"] in seen:
            continue
        seen.add(r["video_id"])
        p = winpath(r.get("output_path") or "")
        out.append({"folder": str(p.parent), "slug": p.stem, "title": r.get("title") or p.stem, "mp4": [str(p)] if p.exists() else [],
                    "duration": duration_of([p]) if p.exists() else None, "video_id": r["video_id"], "uploaded_at": r.get("uploaded_at"),
                    "page": r.get("account") or r.get("channel_name")})
    return out


def _recipes(project: Path) -> dict:
    key = str(project)
    if key not in _RECIPES:
        by = {}
        for p in sorted((project / "shorts" / "work").glob("recipe_*.json")):
            rc = jload(p)
            if isinstance(rc, dict) and rc.get("name") and rc.get("pieces"):
                by[rc["name"]] = (p, rc)
        _RECIPES[key] = by
    return _RECIPES[key]


def _mapped_words(project: Path, rc: dict) -> tuple[list[dict], float]:
    """The captioned words on the clip's output timeline, as build_clip_speed.py maps them."""
    wf = jload(project / "shorts" / rc.get("words", ""), {}) or {}
    wl = [w for s in wf.get("segments", []) for w in s.get("words", [])]
    off = float(rc.get("word_offset", 0.0))
    mapped, t = [], 0.0
    for p in rc["pieces"]:
        s, e = float(p["start"]), float(p["end"])
        for w in wl:
            ws, we = w["s"] + off, w["e"] + off
            if ws >= s and we <= e:
                mapped.append({"w": w["w"], "s": round(t + ws - s, 3), "e": round(t + we - s, 3)})
        t += e - s
    for bad, good in (rc.get("fix") or {}).items():
        bw, gw = bad.split(), good.split()
        i = 0
        while i <= len(mapped) - len(bw):
            if [mapped[i + k]["w"].lower().strip(".,?!") for k in range(len(bw))] == bw:
                s0, e0 = mapped[i]["s"], mapped[i + len(bw) - 1]["e"]
                step = (e0 - s0) / max(len(gw), 1)
                mapped[i:i + len(bw)] = [{"w": gw[k], "s": round(s0 + k * step, 3), "e": round(s0 + (k + 1) * step, 3)}
                                         for k in range(len(gw))]
                i += max(len(gw), 1)
            else:
                i += 1
    return mapped, t


def _episode_date(rc: dict, posted: str | None) -> tuple[str | None, float | None]:
    m = re.search(r"Gil's Arena,\s*(\d{1,2})/(\d{1,2})", rc.get("caption") or "")
    if not m or not posted:
        return None, None
    try:
        when = datetime.fromisoformat(posted)
        ep = datetime(when.year, int(m.group(1)), int(m.group(2)), 12, 0, tzinfo=when.tzinfo)
        return ep.date().isoformat(), round((when - ep).total_seconds() / 86400, 1)
    except ValueError:
        return None, None


# The bed is where the editor's tone decision is recorded (the recipes' free-text "tone" field
# is written differently batch to batch).
TONE_BY_BED = {"scheming": "comedic", "sneaky": "comedic", "volatile": "comedic", "monkeys": "comedic",
               "drill": "heated", "trap": "heated", "bassline": "heated", "investigations": "heated",
               "crash": "heated", "phonk": "heated", "strings": "dramatic", "ticking": "dramatic"}


def _tone_class(bed: str) -> str:
    stem = Path(bed).stem.lower()
    return next((v for k, v in TONE_BY_BED.items() if stem.startswith(k)), "other")


def _from_recipe(project: Path, ep: dict, rc: dict):
    words, body = _mapped_words(project, rc)
    tail = float(rc.get("tail", 1.3))
    total = body + tail
    boom = float(rc.get("boom_at", body / 2))
    lab = {n.get("color"): n for n in rc.get("narration", [])}
    y_end = float(lab.get("yellow", {}).get("e", 1.2))
    sections = [{"name": "OPEN premise label", "kind": "hook", "t0": 0.0, "t1": round(min(y_end, boom), 3)},
                {"name": "BUILD to the boom", "kind": "item", "t0": round(min(y_end, boom), 3), "t1": round(boom, 3)},
                {"name": "PAYOFF after the boom", "kind": "payoff", "t0": round(boom, 3), "t1": round(body, 3)},
                {"name": "END frozen verdict", "kind": "end", "t0": round(body, 3), "t1": round(total, 3)}]
    sections = [s for s in sections if s["t1"] > s["t0"]]
    beats, t = [], 0.0
    for i, p in enumerate(rc["pieces"]):
        d = float(p["end"]) - float(p["start"])
        beats.append({"t0": round(t, 3), "t1": round(t + d, 3), "kind": "clip", "label": "piece %d src %.1f-%.1f" % (i, float(p["start"]), float(p["end"])),
                      "moving": True, "text": None})
        t += d
    beats.append({"t0": round(body, 3), "t1": round(total, 3), "kind": "still", "label": "frozen tail", "moving": False, "text": True})
    spans = []
    for c in ("yellow", "red", "green"):
        n = lab.get(c)
        if n:
            spans.append({"t0": float(n["s"]), "t1": float(n["e"]), "type": "label", "label": "%s: %s" % (c, n.get("text", ""))[:80]})
    for f in rc.get("flashes", []):
        spans.append({"t0": float(f), "t1": float(f) + 0.15, "type": "flash", "label": "flash"})
    for x in rc.get("extra_sfx", []):
        spans.append({"t0": float(x["t"]), "t1": float(x["t"]) + 0.8, "type": "sfx", "label": Path(x.get("file", "")).stem})
    spans.append({"t0": boom, "t1": boom + 0.6, "type": "boom", "label": "boom"})
    bed = (rc.get("bed") or {}).get("file") or "crash_out_bandits"
    spans.append({"t0": 0.0, "t1": boom, "type": "music", "label": Path(bed).stem})
    spans.append({"t0": body, "t1": total, "type": "freeze", "label": "%s + %s" % (lab.get("green", {}).get("text", ""), rc.get("emoji", ""))[:80]})
    ep_date, days = _episode_date(rc, ep.get("uploaded_at"))
    attrs = {"page": ep.get("page"), "uploaded_at": ep.get("uploaded_at"), "title_chars": len(ep.get("title") or ""),
             "has_transcript": bool(words), "has_recipe": True,
             "batch": re.match(r"[A-Z]+", rc["name"]).group(0) if re.match(r"[A-Z]+", rc["name"]) else None,
             "bed": Path(bed).stem.split("_")[0], "emoji": (rc.get("emoji") or "").replace("emoji_", "").replace(".png", ""),
             "body_seconds": round(body, 2), "boom_seconds": round(boom, 2), "boom_pct": round(100.0 * boom / body, 1) if body else None,
             "pieces": len(rc["pieces"]), "cuts_per_min": round(60.0 * max(len(rc["pieces"]) - 1, 0) / body, 1) if body else None,
             "flashes": len(rc.get("flashes", [])), "sfx_hits": len(rc.get("extra_sfx", [])),
             "premise_label_chars": len(lab.get("yellow", {}).get("text", "")), "premise_label_seconds": round(y_end, 2),
             "red_label_chars": len(lab.get("red", {}).get("text", "")), "green_label_chars": len(lab.get("green", {}).get("text", "")),
             "score": rc.get("score"), "tone_class": _tone_class(bed),
             "episode_date": ep_date, "days_episode_to_post": days,
             "words_in_first_3s": sum(1 for w in words if w["s"] < 3.0)}
    return sections, [], beats, spans, norm_words(words), attrs


def timeline(project: Path, ep: dict, cache: Path):
    hit = _recipes(project).get(ep["slug"])
    if hit:
        return _from_recipe(project, ep, hit[1])
    stem = Path(ep["folder"]) / ep["slug"]
    words = []
    for cand in (stem.with_suffix(".words.json"), stem.with_suffix(".json"), project / "shorts" / "out" / f"{ep['slug']}.words.json"):
        j = jload(cand)
        if j:
            ws = j.get("words") if isinstance(j, dict) else j
            if ws:
                words = norm_words(ws)
                break
    beats = []
    gen = project / "analytics" / "generic" / str(ep.get("video_id")) / "cuts.json"
    cuts = jload(gen)
    if cuts:
        times = cuts.get("cuts") if isinstance(cuts, dict) else cuts
        dur = ep.get("duration") or (times[-1] if times else 0)
        edges = [0.0] + [float(t) for t in times] + [float(dur)]
        beats = [{"t0": a, "t1": b, "kind": "clip", "label": f"shot {i}", "moving": True, "text": None} for i, (a, b) in enumerate(zip(edges, edges[1:])) if b > a]
    attrs = {"page": ep.get("page"), "uploaded_at": ep.get("uploaded_at"), "title_chars": len(ep.get("title") or ""),
             "has_transcript": bool(words), "has_recipe": False}
    return [], [], beats, [], words, attrs
