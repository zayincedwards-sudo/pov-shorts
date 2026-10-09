"""Map YouTube videos to episode folders (analytics/videos.json), and build the join files.

Match order: the publisher's own video id (clips, generic) > the uploaded file name against the
delivered mp4 > the title > a unique duration within 2.5 s. Durations are always compared and a
disagreement is written down, never hidden. Hand-kept fields in videos.json (hook_type, voice,
model, template, notes, title_history, thumb_history) survive every re-run.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .adapters import get as get_adapter, norm_title
from .config import load_channel
from .timeline import make_join
from .util import TODAY, jload, jsave, winpath

HAND_FIELDS = ("hook_type", "voice", "model", "template", "topic_class", "notes", "title_history", "thumb_history", "exclude")


def latest_snapshot(root: Path) -> Path | None:
    lt = root / "latest.txt"
    if not lt.exists():
        return None
    p = root / "pull" / lt.read_text(encoding="utf-8").strip()
    return p if p.exists() else None


def _stem(p: str | None) -> str:
    return norm_title(Path(p).stem) if p else ""


def match_videos(catalogue: list[dict], episodes: list[dict]) -> list[dict]:
    by_vid = {e["video_id"]: e for e in episodes if e.get("video_id")}
    by_file = {}
    for e in episodes:
        for m in e.get("mp4", []):
            by_file.setdefault(_stem(m), e)
    by_title = {norm_title(e.get("title")): e for e in episodes if e.get("title")}
    out = []
    for v in catalogue:
        ep, how, note = None, None, None
        if v["id"] in by_vid:
            ep, how = by_vid[v["id"]], "manifest"
        if ep is None and v.get("fileName"):
            fs = _stem(v["fileName"])
            if fs in by_file:
                ep, how = by_file[fs], "file"
            else:
                part = [e for k, e in by_file.items() if k and (fs.endswith(k) or k.endswith(fs))]
                if len(part) == 1:
                    ep, how = part[0], "file-partial"
        if ep is None:
            nt = norm_title(v.get("title"))
            if nt in by_title:
                ep, how = by_title[nt], "title"
            else:
                part = [e for k, e in by_title.items() if k and (nt.endswith(k) or k.endswith(nt) or k in nt)]
                if len(part) == 1:
                    ep, how = part[0], "title-partial"
        if ep is None and v.get("duration_s"):
            close = [e for e in episodes if e.get("duration") and abs(e["duration"] - v["duration_s"]) <= 2.5]
            if len(close) == 1:
                ep, how = close[0], "duration"
        if ep and ep.get("duration") and v.get("duration_s"):
            diff = abs(ep["duration"] - v["duration_s"])
            if diff > 2.5:
                note = f"duration differs by {diff:.1f} s (episode {ep['duration']:.1f}, YouTube {v['duration_s']:.1f})"
        out.append({"id": v["id"], "title": v.get("title"), "published": v.get("publishedAt"), "duration_s": v.get("duration_s"),
                    "is_short": v.get("is_short"), "privacy": v.get("privacy"), "fileName": v.get("fileName"),
                    "episode": ep["folder"] if ep else None, "slug": ep["slug"] if ep else None, "match": how, "note": note})
    return out


def cmd_map(args) -> None:
    project = winpath(args.project).resolve()
    cfg = load_channel(project, args.out)
    root = Path(cfg["root"])
    adapter = get_adapter(cfg["adapter"])
    eps = adapter.episodes(project)
    snap = latest_snapshot(root)
    catalogue = (jload(snap / "catalogue.json", []) if snap else []) or []
    if not catalogue:
        # no pull yet: episodes that carry their own video id can still be mapped
        catalogue = [{"id": e["video_id"], "title": e.get("title"), "publishedAt": e.get("uploaded_at"), "duration_s": e.get("duration"),
                      "is_short": None, "privacy": None, "fileName": None} for e in eps if e.get("video_id")]
        if not catalogue:
            print("no catalogue yet (run `pull` first); nothing to map")
    rows = match_videos(catalogue, eps)
    old = {r["id"]: r for r in (jload(root / "videos.json", []) or [])}
    for r in rows:
        prev = old.get(r["id"], {})
        for k in HAND_FIELDS:
            if k in prev:
                r[k] = prev[k]
        if prev.get("title") and prev["title"] != r["title"]:
            hist = list(prev.get("title_history", []))
            hist.append({"title": prev["title"], "until": TODAY})
            r["title_history"] = hist
    jsave(root / "videos.json", rows)
    matched = [r for r in rows if r["episode"]]
    print(f"videos.json: {len(rows)} videos, {len(matched)} mapped "
          f"({', '.join(f'{h}: {sum(1 for r in matched if r['match'] == h)}' for h in sorted(set(r['match'] for r in matched)))})")
    for r in rows:
        if not r["episode"]:
            print(f"  unmapped video: {r['id']} {str(r['title'])[:60]} ({r.get('fileName')})")
        elif r["note"]:
            print(f"  check: {r['id']} {str(r['title'])[:50]}: {r['note']}")
    used = {r["episode"] for r in matched}
    for e in eps:
        if e["folder"] not in used:
            print(f"  episode without a video: {e['slug']} ({e.get('title')})")


def build_join(project: Path, cfg: dict, ep: dict, video: dict | None, cache: Path) -> dict:
    adapter = get_adapter(cfg["adapter"])
    sections, sentences, beats, spans, words, attrs = adapter.timeline(project, ep, cache)
    duration = (video or {}).get("duration_s") or ep.get("duration")
    j = make_join((video or {}).get("id") or ep.get("video_id"), ep["folder"], duration, sections, sentences, beats, spans, words,
                  {**attrs, "episode_title": ep.get("title"), "episode_duration": ep.get("duration")}, cfg["adapter"])
    j["built"] = TODAY
    return j


def cmd_join(args) -> None:
    project = winpath(args.project).resolve()
    cfg = load_channel(project, args.out)
    root = Path(cfg["root"])
    cache = root / "join" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    adapter = get_adapter(cfg["adapter"])
    if args.episode:
        folder = winpath(args.episode).resolve()
        eps = [e for e in adapter.episodes(project) if Path(e["folder"]).resolve() == folder]
        if not eps:
            sys.exit(f"episode not found by the {cfg['adapter']} adapter: {folder}")
        j = build_join(project, cfg, eps[0], None, cache)
        p = jsave(root / "join" / f"{eps[0]['slug']}.json", j)
        print(f"{eps[0]['slug']}: {len(j['sections'])} sections, {len(j['sentences'])} sentences, {len(j['beats'])} beats, "
              f"{len(j['spans'])} spans, {len(j['words'])} words -> {p}")
        return
    rows = jload(root / "videos.json", []) or []
    all_eps = adapter.episodes(project)
    eps = {e["folder"]: e for e in all_eps}
    # Clip channels keep every clip in ONE folder (the project root), so a folder cannot tell
    # their episodes apart: match on the video id the adapter knows (the publisher's manifest)
    # first. Found on the first CLIPPING run (6 Oct 2026): all 80 clips joined to the last one.
    by_vid = {e["video_id"]: e for e in all_eps if e.get("video_id")}
    n = 0
    for r in rows:
        if args.video and r["id"] != args.video:
            continue
        ep = by_vid.get(r["id"]) or (eps.get(r["episode"]) if r.get("episode") else None)
        if not ep or r.get("exclude"):
            continue
        j = build_join(project, cfg, ep, r, cache)
        for k in HAND_FIELDS:
            if k in r:
                j["attrs"][k] = r[k]
        jsave(root / "join" / f"{r['id']}.json", j)
        n += 1
        print(f"  {r['id']} {r['slug']}: {len(j['sections'])} sections, {len(j['sentences'])} sentences, {len(j['beats'])} beats, "
              f"{len(j['spans'])} spans, {len(j['words'])} words")
    print(f"join: {n} videos written under {root / 'join'}")
