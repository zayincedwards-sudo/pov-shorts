"""Lay the audience-retention curve on the join timeline and read where viewers leave.

Inputs: the Analytics API retention report (elapsedVideoTimeRatio, audienceWatchRatio,
relativeRetentionPerformance) or a Studio export curve; the join file. Output per video:
  survival at 30 s / 60 s / midpoint / 90% / end, the intro profile (5..30 s)
  loss rate per second r(t) = (f(t) - f(t+1)) / f(t); baseline = the median body rate
  dips (10-second windows losing >= twice the median window loss, >= 2 points) with the
    section, the sentence being spoken and the beats on screen; spikes (replays)
  per section, per beat kind, per span type and per item boundary: seconds and excess loss
    over the baseline, in points per minute of that thing
"""
from __future__ import annotations

import statistics as st
from pathlib import Path

from .timeline import beats_in, section_at, sentence_at
from .util import jload, jsave, median, mmss, winpath

WINDOW = 10
MIN_DIP = 0.02
BOUNDARY_S = 3.0


def curve_from_api(rep: dict) -> list[dict]:
    cols = rep.get("columns", [])
    out = []
    for row in rep.get("rows", []):
        d = dict(zip(cols, row))
        if "elapsedVideoTimeRatio" in d:
            out.append({"ratio": float(d["elapsedVideoTimeRatio"]), "abs": float(d.get("audienceWatchRatio") or 0),
                        "rel": d.get("relativeRetentionPerformance")})
    return sorted(out, key=lambda p: p["ratio"])


def interpolate(points: list[dict], duration: float, key: str = "abs") -> list[float]:
    """Values on a 1-second grid 0..floor(duration), linear between points, flat past the ends."""
    pts = [(p["ratio"] * duration, p[key]) for p in points if p.get(key) is not None]
    if not pts:
        return []
    n = int(duration) + 1
    out, k = [], 0
    for t in range(n):
        while k + 1 < len(pts) and pts[k + 1][0] <= t:
            k += 1
        x0, y0 = pts[k]
        if k + 1 < len(pts) and pts[k + 1][0] > x0:
            x1, y1 = pts[k + 1]
            y = y0 + (y1 - y0) * (t - x0) / (x1 - x0) if t >= x0 else y0
        else:
            y = y0
        out.append(float(y))
    return out


def analyse(join: dict, points: list[dict]) -> dict | None:
    dur = join.get("duration")
    if not dur or not points:
        return None
    f = interpolate(points, dur, "abs")
    rel = interpolate(points, dur, "rel")
    n = len(f)
    if n < 10:
        return None

    def at(t):
        t = max(0, min(n - 1, int(round(t))))
        return f[t]

    r = [((f[t] - f[t + 1]) / f[t]) if f[t] > 0.02 else 0.0 for t in range(n - 1)]
    body = r[30:] if n > 90 else r
    # the baseline is the video's own AVERAGE body loss rate (after the intro), so a beat type's excess reads as
    # "faster than this video's average second" (+) or "slower" (-); the median is kept for the record
    baseline = st.mean(body) if body else 0.0
    baseline_median = median(body) or 0.0
    # windows
    wl = [f[t] - f[min(n - 1, t + WINDOW)] for t in range(0, n - 1, 1)]
    med_w = median([x for x in wl[30:]] if n > 90 else wl) or 0.0
    thr = max(MIN_DIP, 2.0 * med_w)
    flagged = [t for t, x in enumerate(wl) if x >= thr]
    dips, cur = [], []
    for t in flagged:
        if cur and t - cur[-1] > 1:
            dips.append(cur)
            cur = []
        cur.append(t)
    if cur:
        dips.append(cur)
    sections, sentences, beats, spans = join["sections"], join["sentences"], join["beats"], join["spans"]
    dip_rows = []
    for grp in dips:
        t_start, t_end = grp[0], min(n - 1, grp[-1] + WINDOW)
        peak = max(range(t_start, t_end), key=lambda t: r[t] if t < len(r) else 0)
        sec = section_at(sections, peak)
        sen = sentence_at(sentences, peak)
        bs = beats_in(beats, peak - BOUNDARY_S, peak + BOUNDARY_S)
        sp = [s for s in spans if s["t0"] <= peak < s["t1"]]
        dip_rows.append({
            "t": peak, "at": mmss(peak), "from": t_start, "to": t_end,
            "loss_points": round(100.0 * (f[t_start] - f[t_end]), 1),
            "share_lost": round(100.0 * (1 - f[t_end] / f[t_start]), 1) if f[t_start] > 0 else None,
            "in_intro": peak < 30,
            "section": (sec or {}).get("name"), "section_kind": (sec or {}).get("kind"),
            "sentence": (sen or {}).get("text"),
            "beats": [f"{b['kind']}: {b['label']}" for b in bs][:6],
            "beat_kinds": sorted({b["kind"] for b in bs}),
            "spans": [f"{s['type']}: {s['label']}" for s in sp][:4],
        })
    dip_rows.sort(key=lambda d: -d["loss_points"])
    spikes = []
    for t in range(0, n - WINDOW - 1):
        rise = f[t + WINDOW] - f[t]
        if rise >= MIN_DIP and (not spikes or t - spikes[-1]["t"] > WINDOW):
            sen = sentence_at(sentences, t + WINDOW // 2)
            spikes.append({"t": t, "at": mmss(t), "rise_points": round(100 * rise, 1), "sentence": (sen or {}).get("text"),
                           "beats": [f"{b['kind']}: {b['label']}" for b in beats_in(beats, t, t + WINDOW)][:4]})
    spikes.sort(key=lambda s: -s["rise_points"])

    def excess_over(sel):
        """sel(t) -> bool over the second grid; returns seconds, mean rate, excess per minute in points."""
        ts = [t for t in range(len(r)) if sel(t)]
        if not ts:
            return None
        rates = [r[t] for t in ts]
        return {"seconds": len(ts), "rate_pct_per_min": round(100 * 60 * st.mean(rates), 2),
                "excess_pct_per_min": round(100 * 60 * (st.mean(rates) - baseline), 2)}

    per_section = []
    for s in sections:
        t0, t1 = int(s["t0"]), int(min(n - 1, s["t1"]))
        if t1 <= t0:
            continue
        ex = excess_over(lambda t, a=t0, b=t1: a <= t < b)
        rel_s = rel[t0:t1] if rel else []
        per_section.append({"name": s["name"], "kind": s["kind"], "t0": s["t0"], "t1": s["t1"], "seconds": t1 - t0,
                            "survival_in": round(f[t0], 3), "survival_out": round(f[t1], 3),
                            "share_lost_pct": round(100 * (1 - f[t1] / f[t0]), 1) if f[t0] > 0 else None,
                            "excess_pct_per_min": ex["excess_pct_per_min"] if ex else None,
                            "rel_mean": round(st.mean(rel_s), 3) if rel_s else None})
    kinds = sorted({b["kind"] for b in beats})
    per_kind = {}
    for k in kinds:
        cover = [False] * len(r)
        for b in beats:
            if b["kind"] == k:
                for t in range(max(0, int(b["t0"])), min(len(r), int(b["t1"]) + 1)):
                    cover[t] = True
        ex = excess_over(lambda t, c=cover: c[t])
        if ex:
            per_kind[k] = ex
    moving = {"moving": [False] * len(r), "still": [False] * len(r)}
    for b in beats:
        if b.get("moving") is None:
            continue
        key = "moving" if b["moving"] else "still"
        for t in range(max(0, int(b["t0"])), min(len(r), int(b["t1"]) + 1)):
            moving[key][t] = True
    for key, cov in moving.items():
        ex = excess_over(lambda t, c=cov: c[t])
        if ex:
            per_kind[f"motion:{key}"] = ex
    per_span = {}
    for typ in sorted({s["type"] for s in spans}):
        cover = [False] * len(r)
        for s in spans:
            if s["type"] == typ:
                for t in range(max(0, int(s["t0"])), min(len(r), int(s["t1"]) + 1)):
                    cover[t] = True
        ex = excess_over(lambda t, c=cover: c[t])
        if ex:
            per_span[typ] = ex
    sec_kind = {}
    for sk in sorted({s["kind"] for s in sections}):
        cover = [False] * len(r)
        for s in sections:
            if s["kind"] == sk:
                for t in range(max(0, int(s["t0"])), min(len(r), int(s["t1"]) + 1)):
                    cover[t] = True
        ex = excess_over(lambda t, c=cover: c[t])
        if ex:
            sec_kind[sk] = ex
    bounds = [s["t0"] for s in sections if s["kind"] == "item"][1:]
    boundary = None
    if bounds:
        cover = [False] * len(r)
        for tb in bounds:
            for t in range(max(0, int(tb)), min(len(r), int(tb + BOUNDARY_S))):
                cover[t] = True
        boundary = excess_over(lambda t, c=cover: c[t])
    hook = next((s for s in sections if s["kind"] == "hook"), None)
    out = {
        "video_id": join.get("video_id"), "episode": join.get("episode"), "duration": dur, "points": len(points),
        "survival": {"5s": round(at(5), 3), "10s": round(at(10), 3), "15s": round(at(15), 3), "20s": round(at(20), 3),
                     "30s": round(at(30), 3), "60s": round(at(60), 3), "mid": round(at(dur / 2), 3), "p90": round(at(0.9 * dur), 3),
                     "end": round(f[-1], 3), "start": round(f[0], 3)},
        "hook": {"seconds": round(hook["t1"] - hook["t0"], 1) if hook else None,
                 "survival_at_item1": round(at(hook["t1"]), 3) if hook else None},
        "baseline_pct_per_min": round(100 * 60 * baseline, 2),
        "baseline_median_pct_per_min": round(100 * 60 * baseline_median, 2),
        "rel_mean": round(st.mean([x for x in rel if x is not None]), 3) if rel else None,
        "dips": dip_rows, "spikes": spikes[:10],
        "per_section": per_section, "per_section_kind": sec_kind, "per_beat_kind": per_kind, "per_span_type": per_span,
        "item_boundary": boundary,
        "curve": [round(x, 4) for x in f],
    }
    return out


def cmd_retention(args) -> None:
    from .config import load_channel
    from .mapping import latest_snapshot
    project = winpath(args.project).resolve()
    cfg = load_channel(project, args.out)
    root = Path(cfg["root"])
    snap = latest_snapshot(root)
    outdir = root / "retention"
    outdir.mkdir(parents=True, exist_ok=True)
    joins = sorted((root / "join").glob("*.json"))
    n = 0
    for jp in joins:
        if jp.parent.name == "cache":
            continue
        join = jload(jp)
        vid = join.get("video_id")
        if args.video and vid != args.video:
            continue
        points = []
        if snap and vid:
            rep = jload(snap / "videos" / vid / "retention.json")
            if rep:
                points = curve_from_api(rep)
            if not points:
                sc = jload(snap / "studio" / f"retention_{vid}.json")
                if sc:
                    points = sc.get("points", [])
        if args.curve:  # a curve file for tests or a Studio export: [{ratio, abs, rel}]
            points = jload(args.curve) or points
        if not points:
            continue
        res = analyse(join, points)
        if not res:
            continue
        key = vid or jp.stem
        jsave(outdir / f"{key}.json", res)
        n += 1
        s = res["survival"]
        print(f"  {key}: 30 s {s['30s']:.0%}, mid {s['mid']:.0%}, end {s['end']:.0%}; {len(res['dips'])} dips, "
              f"baseline {res['baseline_pct_per_min']:.1f}%/min")
        if args.charts:
            from .charts import chart_video
            png = outdir / f"{key}.png"
            chart_video(res, join, png, join.get("attrs", {}).get("episode_title") or key)
    print(f"retention: {n} videos -> {outdir}")
