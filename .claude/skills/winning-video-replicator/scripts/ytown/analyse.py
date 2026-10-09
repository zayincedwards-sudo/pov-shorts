"""Separate the winners, with the right denominators, and list the candidate rules.

Three scoreboards per video (shown / clicked / watched, plus converted), age-matched views per
day, the neighbour-median outlier ratio (cancels the channel's tide), attributes read from the
build, the thumbnail pixels, the title, the publish time and the retention results, then:
  correlations   every numeric attribute against every outcome (Spearman, n)
  groups         categorical attributes: median outcome per group
  controls       pairs of videos that differ in exactly one categorical trait
  retention      beat kinds, span types, section kinds and boundaries pooled across videos
  candidates     everything above that clears a lenient bar, tiered CONFIRMED / PLAUSIBLE / HINT
Nothing here decides a rule; the user does, through the session's AskUserQuestion walk.
"""
from __future__ import annotations

import datetime as dt
import math
import re
import statistics as st
from pathlib import Path

from .mapping import latest_snapshot
from .util import TODAY, heading, jload, jsave, median, mmss, spearman, table, winpath, write_txt

CHARGED = ("biggest", "deadliest", "strangest", "scariest", "weirdest", "rarest", "most", "every", "real", "insane", "secret",
           "never", "worst", "best", "terrifying", "creepiest", "eeriest", "darkest", "mysterious", "fastest", "powerful",
           "expensive", "valuable", "explained", "actually", "really", "truth", "hidden", "banned", "illegal", "dangerous")
OUTCOMES = {
    "vpd_d7": "views per day, first 7 days (log)",
    "vpd_d28": "views per day, first 28 days (log)",
    "ctr_pct": "impressions click-through (Studio)",
    "survival_30": "still watching at 30 s",
    "avp": "average percentage viewed",
    "subs_per_1000": "subscribers per 1,000 views",
    "likes_per_1000": "likes per 1,000 views",
}
LOG_OUTCOMES = ("vpd_d7", "vpd_d28")
CATEGORICAL = ("hand_hook_type", "hand_voice", "hand_model", "hand_template", "hand_topic_class", "m_has_music", "a_bed",
               "pub_weekday", "title_is_question", "title_has_number", "a_takes", "thumb_has_text")
CONTROL_KEYS = ("hand_template", "hand_hook_type", "hand_voice", "hand_model", "m_has_music", "hand_topic_class")
COMMENT_CLASSES = {
    "praise": ("love", "great", "amazing", "awesome", "best", "good", "nice", "perfect", "beautiful", "thank"),
    "request": ("more", "next", "please", "part 2", "do a", "can you", "would love", "make a"),
    "correction": ("actually", "wrong", "incorrect", "not true", "mistake", "false", "misinformation"),
    "complaint": ("boring", "too long", "slow", "ai voice", "robot", "annoying", "clickbait", "unwatchable", "ai generated"),
    "question": ("?",),
}


# ------------------------------------------------------------------ per-video readers
def days_metrics(days: dict | None) -> dict:
    if not days or not days.get("rows"):
        return {}
    cols = days["columns"]
    rows = [dict(zip(cols, r)) for r in days["rows"]]
    rows.sort(key=lambda r: r["day"])
    v = [int(r.get("views") or 0) for r in rows]
    cum = []
    s = 0
    for x in v:
        s += x
        cum.append(s)
    d = {"days_covered": len(v), "views_d7": cum[6] if len(cum) >= 7 else None, "views_d28": cum[27] if len(cum) >= 28 else None,
         "views_latest7": sum(v[-7:]) if v else None, "first_day": rows[0]["day"], "last_day": rows[-1]["day"]}
    d["vpd_d7"] = d["views_d7"] / 7.0 if d["views_d7"] is not None else None
    d["vpd_d28"] = d["views_d28"] / 28.0 if d["views_d28"] is not None else None
    d["vpd_latest7"] = d["views_latest7"] / min(7, len(v)) if v else None
    d["peak_day_index"] = max(range(len(v)), key=lambda i: v[i]) if v else None
    d["day1_share_of_d7"] = (v[0] / cum[6]) if len(cum) >= 7 and cum[6] else None
    return d


def traffic_shares(tr: dict | None) -> dict:
    if not tr or not tr.get("rows"):
        return {}
    cols = tr["columns"]
    by = {}
    for r in tr["rows"]:
        d = dict(zip(cols, r))
        by[d["insightTrafficSourceType"]] = int(d.get("views") or 0)
    tot = sum(by.values()) or 1
    names = {"SUBSCRIBER": "browse", "RELATED_VIDEO": "suggested", "YT_SEARCH": "search", "SHORTS": "shorts_feed", "EXT_URL": "external",
             "NOTIFICATION": "notification", "PLAYLIST": "playlist", "YT_CHANNEL": "channel_page", "END_SCREEN": "end_screen"}
    out = {f"traffic_{names.get(k, k.lower())}_pct": round(100.0 * v / tot, 1) for k, v in by.items()}
    out["traffic_views"] = tot
    return out


def title_traits(title: str | None) -> dict:
    t = title or ""
    words = t.split()
    caps = [w for w in words if len(w) > 2 and w.isupper()]
    return {
        "title_chars": len(t), "title_words": len(words), "title_caps_words": len(caps),
        "title_has_number": bool(re.search(r"\d", t)), "title_is_question": t.strip().endswith("?"),
        "title_has_colon": ":" in t, "title_has_brackets": bool(re.search(r"[\[\(]", t)),
        "title_charged_words": sum(1 for w in words if re.sub(r"[^a-z]", "", w.lower()) in CHARGED),
        "title_has_every": "every" in t.lower(), "title_has_explained": "explained" in t.lower(),
        "title_has_minutes": bool(re.search(r"\bin \d+ minutes\b", t.lower())),
        "title_first_word": words[0].lower() if words else None,
        "title_emphasis": caps[0] if caps else None,
    }


def publish_traits(published: str | None) -> dict:
    if not published:
        return {}
    try:
        d = dt.datetime.fromisoformat(published.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return {}
    return {"pub_weekday": d.strftime("%a"), "pub_weekday_num": d.weekday(), "pub_hour_local": d.hour, "pub_date": d.date().isoformat()}


def description_traits(desc: str | None, tags: list | None) -> dict:
    d = desc or ""
    return {"desc_chars": len(d), "desc_links": len(re.findall(r"https?://", d)), "desc_hashtags": len(re.findall(r"#\w+", d)),
            "desc_chapters": len(re.findall(r"(?m)^\s*\d{1,2}:\d{2}", d)), "desc_stay_to_end": bool(re.search(r"stay (?:until|to) the end", d, re.I)),
            "tags_count": len(tags or [])}


def thumb_stats(path: str | None) -> dict:
    if not path or not Path(path).exists():
        return {}
    try:
        import numpy as np
        from PIL import Image, ImageFilter
    except ImportError:
        return {}
    try:
        im = Image.open(path).convert("RGB")
    except Exception:
        return {}
    w0, h0 = im.size
    bits = Path(path).stat().st_size * 8.0 / max(1, w0 * h0)
    im = im.resize((320, 180))
    a = np.asarray(im).astype("float32")
    luma = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    mx, mn = a.max(axis=2), a.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    gray = np.asarray(im.convert("L").filter(ImageFilter.FIND_EDGES)).astype("float32")
    rg = a[..., 0] - a[..., 1]
    yb = 0.5 * (a[..., 0] + a[..., 1]) - a[..., 2]
    colourfulness = float(math.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * math.sqrt(rg.mean() ** 2 + yb.mean() ** 2))
    q = im.quantize(6, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[:18]
    counts = sorted(q.getcolors(), reverse=True)[:3]
    dom = []
    for cnt, idx in counts:
        r, g, b = pal[idx * 3: idx * 3 + 3]
        dom.append(f"#{r:02x}{g:02x}{b:02x}:{100.0 * cnt / (320 * 180):.0f}%")
    return {
        "thumb_white_pct": round(float(((luma > 235) & (sat < 0.12)).mean() * 100), 1),
        "thumb_black_pct": round(float((luma < 25).mean() * 100), 1),
        "thumb_mid_pct": round(float(((luma >= 25) & (luma <= 235)).mean() * 100), 1),
        "thumb_brightness": round(float(luma.mean()), 1), "thumb_contrast": round(float(luma.std()), 1),
        "thumb_saturation": round(float(sat.mean()), 3), "thumb_colourfulness": round(colourfulness, 1),
        "thumb_edge_density": round(float((gray > 40).mean()), 3), "thumb_bits_per_pixel": round(bits, 2),
        "thumb_dominant": ", ".join(dom), "thumb_size": f"{w0}x{h0}",
    }


def classify_comments(cj: dict | None) -> dict:
    if not cj or not cj.get("comments"):
        return {}
    cs = cj["comments"]
    counts = {k: 0 for k in COMMENT_CLASSES}
    for c in cs:
        t = (c.get("text") or "").lower()
        for k, needles in COMMENT_CLASSES.items():
            if any(nd in t for nd in needles):
                counts[k] += 1
    top = max(cs, key=lambda c: c.get("likes", 0))
    return {**{f"comments_{k}": v for k, v in counts.items()}, "comments_fetched": len(cs), "top_comment": (top.get("text") or "")[:160],
            "top_comment_likes": top.get("likes", 0)}


# ------------------------------------------------------------------ assembling records
def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def build_records(root: Path, snap: Path, cfg: dict, min_age: int, noise_floor: int) -> tuple[list[dict], dict]:
    catalogue = jload(snap / "catalogue.json", []) or []
    totals = jload(snap / "totals.json", {}) or {}
    studio = jload(snap / "studio" / "content.json", {}) or {}
    channel = jload(snap / "channel.json", {}) or {}
    data_end = channel.get("data_end") or TODAY
    vmap = {r["id"]: r for r in (jload(root / "videos.json", []) or [])}
    recs = []
    for v in catalogue:
        vid = v["id"]
        if v.get("privacy") == "private":
            continue
        row = vmap.get(vid, {})
        if row.get("exclude"):
            continue
        tot = totals.get(vid, {})
        days = days_metrics(jload(snap / "videos" / vid / "days.json"))
        tr = traffic_shares(jload(snap / "videos" / vid / "traffic.json"))
        join = jload(root / "join" / f"{vid}.json", {}) or {}
        ret = jload(root / "retention" / f"{vid}.json", {}) or {}
        stu = studio.get(vid, {})
        age = (dt.date.fromisoformat(data_end) - dt.date.fromisoformat(v["publishedAt"][:10])).days if v.get("publishedAt") else None
        views = int(tot.get("views") or v.get("statistics", {}).get("views") or 0)
        rec = {
            "id": vid, "title": v.get("title"), "published": v.get("publishedAt"), "age_days": age, "duration_s": v.get("duration_s"),
            "content": "short" if v.get("is_short") else "long", "privacy": v.get("privacy"), "episode": row.get("slug"),
            "eligible": bool(age is not None and age >= min_age), "retention_ok": views >= noise_floor and bool(ret),
            "views": views, "minutes_watched": tot.get("estimatedMinutesWatched"),
            "avd_s": tot.get("averageViewDuration"), "avp": tot.get("averageViewPercentage"),
            "likes": tot.get("likes"), "comments": tot.get("comments"), "shares": tot.get("shares"),
            "subs_gained": tot.get("subscribersGained"), "subs_lost": tot.get("subscribersLost"),
            "impressions": stu.get("impressions"), "ctr_pct": stu.get("ctr_pct"), "studio_window": stu.get("window"),
            **days, **tr,
            "survival_30": (ret.get("survival") or {}).get("30s"), "survival_60": (ret.get("survival") or {}).get("60s"),
            "survival_mid": (ret.get("survival") or {}).get("mid"), "survival_end": (ret.get("survival") or {}).get("end"),
            "rel_mean": ret.get("rel_mean"), "dips": len(ret.get("dips", [])) if ret else None,
            "biggest_dip_points": (ret.get("dips") or [{}])[0].get("loss_points") if ret.get("dips") else None,
            "hook_survival": (ret.get("hook") or {}).get("survival_at_item1"),
            "upload_number": v.get("upload_number"),
        }
        rec["subs_per_1000"] = (1000.0 * (rec["subs_gained"] or 0) / views) if views else None
        rec["likes_per_1000"] = (1000.0 * (rec["likes"] or 0) / views) if views else None
        rec["comments_per_1000"] = (1000.0 * (rec["comments"] or 0) / views) if views else None
        rec["vpd_lifetime"] = views / age if age else None
        attrs = {}
        attrs.update(title_traits(v.get("title")))
        attrs.update(publish_traits(v.get("publishedAt")))
        attrs.update(description_traits(v.get("description"), v.get("tags")))
        thumb = snap / "thumbs" / f"{vid}.jpg"
        attrs.update(thumb_stats(str(thumb) if thumb.exists() else (join.get("attrs") or {}).get("thumbnail")))
        for k, val in (join.get("metrics") or {}).items():
            attrs[f"m_{k}"] = val
        for k, val in (join.get("attrs") or {}).items():
            if k in ("thumbnail", "thumb_metrics", "episode_title", "episode_duration", "title_history", "thumb_history", "notes"):
                continue
            if isinstance(val, (int, float, bool, str)) or val is None:
                attrs[f"a_{k}"] = val
        for k in ("hook_type", "voice", "model", "template", "topic_class"):
            if row.get(k) is not None:
                attrs[f"hand_{k}"] = row[k]
        attrs.update(classify_comments(jload(snap / "videos" / vid / "comments.json")))
        rec["attrs"] = attrs
        recs.append(rec)
    recs.sort(key=lambda r: r["published"] or "")
    for n, r in enumerate(recs):
        prev = recs[n - 1]["published"][:10] if n and recs[n - 1]["published"] else None
        r["attrs"]["days_since_previous_upload"] = (dt.date.fromisoformat(r["published"][:10]) - dt.date.fromisoformat(prev)).days if (prev and r["published"]) else None
    # neighbour-median outlier ratio, inside each content type, 3 uploads either side
    for content in ("long", "short"):
        grp = [r for r in recs if r["content"] == content]
        for i, r in enumerate(grp):
            neigh = [x["vpd_d7"] for x in grp[max(0, i - 3): i] + grp[i + 1: i + 4] if x.get("vpd_d7")]
            r["neighbour_median_vpd_d7"] = median(neigh) if len(neigh) >= 2 else None
            r["outlier_ratio"] = (r["vpd_d7"] / r["neighbour_median_vpd_d7"]) if (r.get("vpd_d7") and r["neighbour_median_vpd_d7"]) else None
    return recs, {"data_date": data_end, "channel": channel}


# ------------------------------------------------------------------ comparisons
def outcome_value(r: dict, key: str):
    v = r.get(key)
    if v is None:
        return None
    if key in LOG_OUTCOMES:
        return math.log10(v) if v > 0 else None
    return float(v)


def correlations(recs: list[dict]) -> list[dict]:
    keys = sorted({k for r in recs for k, v in r["attrs"].items() if _num(v) is not None})
    out = []
    for key in keys:
        vals = [_num(r["attrs"].get(key)) for r in recs]
        if sum(1 for v in vals if v is not None) < 3 or len({v for v in vals if v is not None}) < 2:
            continue
        for oc in OUTCOMES:
            ys = [outcome_value(r, oc) for r in recs]
            rho, n = spearman(vals, ys)
            if rho is None:
                continue
            hits = [r["attrs"].get(key) for r in recs if r.get("hit") and _num(r["attrs"].get(key)) is not None]
            rest = [r["attrs"].get(key) for r in recs if not r.get("hit") and _num(r["attrs"].get(key)) is not None]
            out.append({"attribute": key, "outcome": oc, "rho": round(rho, 2), "n": n,
                        "hits_median": median(hits), "rest_median": median(rest), "hits_n": len(hits)})
    out.sort(key=lambda c: -abs(c["rho"]))
    return out


def groups(recs: list[dict]) -> list[dict]:
    out = []
    keys = sorted({k for r in recs for k, v in r["attrs"].items() if isinstance(v, (str, bool)) or k in CATEGORICAL})
    for key in keys:
        by = {}
        for r in recs:
            v = r["attrs"].get(key)
            if v is None or (isinstance(v, str) and len(v) > 40):
                continue
            by.setdefault(str(v), []).append(r)
        if len(by) < 2 or sum(1 for g in by.values() if len(g) >= 2) < 1:
            continue
        for oc in OUTCOMES:
            rows = []
            for g, rs in by.items():
                vals = [r.get(oc) for r in rs if r.get(oc) is not None]
                if vals:
                    rows.append({"group": g, "n": len(vals), "median": median(vals), "videos": [r["id"] for r in rs][:6]})
            if len(rows) >= 2 and any(x["median"] for x in rows):
                rows.sort(key=lambda x: -(x["median"] or 0))
                out.append({"attribute": key, "outcome": oc, "groups": rows})
    return out


def controls(recs: list[dict]) -> list[dict]:
    out = []
    el = [r for r in recs if r.get("eligible")]
    for i in range(len(el)):
        for j in range(i + 1, len(el)):
            a, b = el[i], el[j]
            if a["content"] != b["content"]:
                continue
            diffs = [k for k in CONTROL_KEYS if a["attrs"].get(k) != b["attrs"].get(k) and (a["attrs"].get(k) is not None or b["attrs"].get(k) is not None)]
            if len(diffs) != 1:
                continue
            k = diffs[0]
            res = {"attribute": k, "a": {"id": a["id"], "title": a["title"], "value": a["attrs"].get(k)},
                   "b": {"id": b["id"], "title": b["title"], "value": b["attrs"].get(k)}, "outcomes": {}}
            for oc in ("vpd_d7", "ctr_pct", "survival_30", "avp", "subs_per_1000"):
                va, vb = a.get(oc), b.get(oc)
                if va is not None and vb is not None:
                    res["outcomes"][oc] = {"a": va, "b": vb, "ratio": (va / vb) if vb else None}
            strong = any((o.get("ratio") or 1) >= 2 or (o.get("ratio") or 1) <= 0.5 for o in res["outcomes"].values())
            res["strong"] = strong
            out.append(res)
    return out


def pooled_retention(root: Path, recs: list[dict]) -> dict:
    pools = {"beat_kind": {}, "span_type": {}, "section_kind": {}, "boundary": {}}
    n_videos = 0
    for r in recs:
        if not r.get("retention_ok"):
            continue
        ret = jload(root / "retention" / f"{r['id']}.json")
        if not ret:
            continue
        n_videos += 1
        for pool, key in (("beat_kind", "per_beat_kind"), ("span_type", "per_span_type"), ("section_kind", "per_section_kind")):
            for k, ex in (ret.get(key) or {}).items():
                p = pools[pool].setdefault(k, {"seconds": 0, "weighted": 0.0, "videos": 0, "positive": 0, "per_video": []})
                p["seconds"] += ex["seconds"]
                p["weighted"] += ex["excess_pct_per_min"] * ex["seconds"]
                p["videos"] += 1
                p["positive"] += 1 if ex["excess_pct_per_min"] > 0 else 0
                p["per_video"].append({"id": r["id"], "excess": ex["excess_pct_per_min"], "seconds": ex["seconds"]})
        if ret.get("item_boundary"):
            ex = ret["item_boundary"]
            p = pools["boundary"].setdefault("first 3 s of an item", {"seconds": 0, "weighted": 0.0, "videos": 0, "positive": 0, "per_video": []})
            p["seconds"] += ex["seconds"]
            p["weighted"] += ex["excess_pct_per_min"] * ex["seconds"]
            p["videos"] += 1
            p["positive"] += 1 if ex["excess_pct_per_min"] > 0 else 0
            p["per_video"].append({"id": r["id"], "excess": ex["excess_pct_per_min"], "seconds": ex["seconds"]})
    out = {"videos_with_retention": n_videos}
    for pool, d in pools.items():
        rows = []
        for k, p in d.items():
            if not p["seconds"]:
                continue
            mean_ex = p["weighted"] / p["seconds"]
            agree = max(p["positive"], p["videos"] - p["positive"]) / p["videos"]
            tier = "CONFIRMED" if (p["videos"] >= 3 and agree >= 0.75 and abs(mean_ex) >= 1.0) else \
                   "PLAUSIBLE" if (p["videos"] >= 2 and agree >= 0.75 and abs(mean_ex) >= 0.5) else "HINT"
            rows.append({"key": k, "seconds": p["seconds"], "videos": p["videos"], "excess_pct_per_min": round(mean_ex, 2),
                         "agreement": round(agree, 2), "tier": tier, "per_video": p["per_video"]})
        rows.sort(key=lambda x: x["excess_pct_per_min"])
        out[pool] = rows
    return out


def candidates(recs: list[dict], corr: list[dict], grp: list[dict], ctrl: list[dict], pooled: dict) -> list[dict]:
    out = []
    el_n = sum(1 for r in recs if r.get("eligible"))
    for c in corr:
        a = abs(c["rho"])
        if c["n"] < 3 or a < 0.4:
            continue
        tier = "CONFIRMED" if (c["n"] >= 6 and a >= 0.6) else "PLAUSIBLE" if (c["n"] >= 4 and a >= 0.4) else "HINT"
        if c["n"] == 3 and a < 0.8:
            continue
        direction = "higher" if c["rho"] > 0 else "lower"
        out.append({"id": f"corr:{c['attribute']}:{c['outcome']}", "kind": "correlation", "attribute": c["attribute"], "outcome": c["outcome"],
                    "direction": direction, "strength": c["rho"], "n": c["n"], "tier": tier,
                    "evidence": f"Spearman {c['rho']:+.2f} over {c['n']} videos; hits median {c['hits_median']} vs rest {c['rest_median']}",
                    "plain": f"{direction} {c['attribute']} goes with {direction if c['rho'] > 0 else 'higher'} {OUTCOMES[c['outcome']]}"
                             if c["rho"] > 0 else f"lower {c['attribute']} goes with higher {OUTCOMES[c['outcome']]}"})
    for g in grp:
        rows = [x for x in g["groups"] if x["median"] is not None]
        if len(rows) < 2:
            continue
        best, worst = rows[0], rows[-1]
        if not worst["median"]:
            ratio = None
        else:
            ratio = best["median"] / worst["median"] if g["outcome"] in LOG_OUTCOMES or g["outcome"] in ("ctr_pct", "subs_per_1000", "likes_per_1000") else None
        diff = (best["median"] - worst["median"]) if g["outcome"] in ("survival_30", "avp") else None
        strong = (ratio is not None and ratio >= 1.5) or (diff is not None and diff >= (0.08 if g["outcome"] == "survival_30" else 5))
        if not strong:
            continue
        nmin = min(best["n"], worst["n"])
        tier = "CONFIRMED" if (nmin >= 3 and (ratio or 0) >= 2) else "PLAUSIBLE" if nmin >= 2 else "HINT"
        out.append({"id": f"group:{g['attribute']}:{g['outcome']}", "kind": "group", "attribute": g["attribute"], "outcome": g["outcome"],
                    "direction": best["group"], "strength": ratio or diff, "n": sum(x["n"] for x in rows), "tier": tier,
                    "evidence": "; ".join(f"{x['group']}: median {x['median']:.3g} (n={x['n']})" for x in rows),
                    "plain": f"{g['attribute']} = {best['group']} beats {worst['group']} on {OUTCOMES[g['outcome']]}"})
    for c in ctrl:
        if not c["strong"]:
            continue
        oc = ", ".join(f"{k}: {v['a']:.3g} vs {v['b']:.3g}" for k, v in c["outcomes"].items() if v.get("ratio") is not None)
        out.append({"id": f"control:{c['attribute']}:{c['a']['id']}:{c['b']['id']}", "kind": "control", "attribute": c["attribute"], "outcome": "several",
                    "direction": f"{c['a']['value']} vs {c['b']['value']}", "strength": None, "n": 2, "tier": "CONFIRMED",
                    "evidence": f"{c['a']['title']} ({c['a']['value']}) against {c['b']['title']} ({c['b']['value']}): {oc}",
                    "plain": f"internal control on {c['attribute']}: {c['a']['value']} vs {c['b']['value']}"})
    for pool in ("beat_kind", "span_type", "section_kind", "boundary"):
        for row in pooled.get(pool, []):
            if row["tier"] == "HINT" and abs(row["excess_pct_per_min"]) < 0.5:
                continue
            if pool == "section_kind" and row["key"] == "hook":
                continue  # every hook loses viewers; the hook's own numbers live in the per-video survival table
            sign = "loses" if row["excess_pct_per_min"] > 0 else "holds"
            phrase = "loses viewers faster than the video's average second" if sign == "loses" else "holds viewers better than the video's average second"
            out.append({"id": f"retention:{pool}:{row['key']}", "kind": "retention", "attribute": f"{pool}={row['key']}", "outcome": "retention",
                        "direction": sign, "strength": row["excess_pct_per_min"], "n": row["videos"], "tier": row["tier"],
                        "evidence": f"{row['excess_pct_per_min']:+.2f} points per minute against each video's average body loss, over {row['seconds']} s "
                                    f"in {row['videos']} videos, same sign in {row['agreement']:.0%}",
                        "plain": f"{row['key']} ({pool.replace('_', ' ')}) {phrase}: {row['excess_pct_per_min']:+.1f} pts/min"})
    order = {"CONFIRMED": 0, "PLAUSIBLE": 1, "HINT": 2}
    out.sort(key=lambda c: (order[c["tier"]], -(abs(c["strength"]) if isinstance(c["strength"], (int, float)) else 0)))
    for c in out:
        c["eligible_videos"] = el_n
    return out


# ------------------------------------------------------------------ tables
def scoreboard_rows(recs: list[dict]) -> list[list]:
    rows = []
    for r in sorted(recs, key=lambda x: -(x.get("vpd_d7") or x.get("vpd_lifetime") or 0)):
        rows.append([r["id"], (r["title"] or "")[:44], r["content"], r.get("age_days"), r.get("views"),
                     round(r["vpd_d7"], 1) if r.get("vpd_d7") is not None else None,
                     round(r["outlier_ratio"], 2) if r.get("outlier_ratio") is not None else None,
                     "HIT" if r.get("hit") else "", r.get("impressions"), r.get("ctr_pct"),
                     f"{r['survival_30']:.0%}" if r.get("survival_30") is not None else None,
                     round(r["avp"], 1) if r.get("avp") is not None else None,
                     round(r["subs_per_1000"], 2) if r.get("subs_per_1000") is not None else None,
                     "" if r.get("eligible") else "early"])
    return rows


SCORE_HEADERS = ["video", "title", "type", "age", "views", "views/day d7", "x neighbours", "hit", "impr", "ctr %", "30 s", "avp %", "subs/1000", ""]


def write_tables(root: Path, meta: dict, recs, corr, grp, ctrl, pooled, cands, hit_ratio) -> None:
    lines = [heading("ANALYTICS TABLES"), f"Data to {meta['data_date']}. Written {TODAY}. Hit = views per day in the first 7 days at least "
             f"{hit_ratio}x the median of the 3 uploads either side (same content type).", ""]
    lines += [heading("SCOREBOARD", "-"), table(scoreboard_rows(recs), SCORE_HEADERS), ""]
    tr_rows = [[r["id"], (r["title"] or "")[:40], r["attrs"].get("pub_weekday"), r["attrs"].get("pub_hour_local"),
                r.get("traffic_browse_pct"), r.get("traffic_suggested_pct"), r.get("traffic_search_pct"), r.get("traffic_shorts_feed_pct"),
                r.get("traffic_external_pct"), r.get("day1_share_of_d7")] for r in recs]
    lines += [heading("WHERE THE VIEWS CAME FROM (%)", "-"), table(tr_rows, ["video", "title", "day", "hour", "browse", "suggested", "search", "shorts feed", "external", "day-1 share of d7"]), ""]
    if pooled.get("videos_with_retention"):
        lines += [heading(f"RETENTION BY WHAT IS ON SCREEN ({pooled['videos_with_retention']} videos; + loses viewers, - holds them; points per minute over each video's baseline)", "-")]
        for pool in ("section_kind", "beat_kind", "span_type", "boundary"):
            rows = [[row["key"], row["videos"], row["seconds"], row["excess_pct_per_min"], f"{row['agreement']:.0%}", row["tier"]] for row in pooled.get(pool, [])]
            if rows:
                lines += [pool.replace("_", " "), table(rows, ["what", "videos", "seconds", "excess pts/min", "agree", "tier"]), ""]
    if corr:
        rows = [[c["attribute"], c["outcome"], c["rho"], c["n"], c["hits_median"], c["rest_median"]] for c in corr if abs(c["rho"]) >= 0.4][:60]
        lines += [heading("ATTRIBUTES AGAINST OUTCOMES (Spearman rank correlation, |rho| >= 0.4)", "-"), table(rows, ["attribute", "outcome", "rho", "n", "hits median", "rest median"]), ""]
    if ctrl:
        rows = [[c["attribute"], f"{c['a']['value']} / {c['b']['value']}", (c["a"]["title"] or "")[:30], (c["b"]["title"] or "")[:30],
                 "; ".join(f"{k} {v['a']:.3g} vs {v['b']:.3g}" for k, v in c["outcomes"].items() if v.get("ratio") is not None)[:70], "strong" if c["strong"] else ""] for c in ctrl]
        lines += [heading("INTERNAL CONTROLS (pairs that differ in one trait)", "-"), table(rows, ["trait", "values", "video A", "video B", "outcomes", ""]), ""]
    rows = [[c["tier"], c["kind"], c["attribute"][:34], c["outcome"], c["direction"], c["n"], (c["evidence"] or "")[:80]] for c in cands[:80]]
    lines += [heading("CANDIDATE RULES (every one goes to the user; nothing is committed here)", "-"), table(rows, ["tier", "kind", "attribute", "outcome", "direction", "n", "evidence"]), ""]
    write_txt(root / "REPORT_TABLES.txt", "\n".join(lines))
    md = ["# Analytics tables (Claude-facing copy of REPORT_TABLES.txt)", "", "```", "\n".join(lines), "```", ""]
    (root / "ANALYTICS.tables.md").write_text("\n".join(md), encoding="utf-8")


def cmd_analyse(args) -> None:
    from .config import load_channel
    project = winpath(args.project).resolve()
    cfg = load_channel(project, args.out)
    root = Path(cfg["root"])
    snap = latest_snapshot(root)
    if not snap:
        raise SystemExit("no snapshot: run `pull` first")
    recs, meta = build_records(root, snap, cfg, args.min_age, args.noise_floor)
    for r in recs:
        r["hit"] = bool(r.get("eligible") and r.get("outlier_ratio") and r["outlier_ratio"] >= args.hit_ratio)
    el = [r for r in recs if r["eligible"]]
    by_c = {}
    for r in el:
        by_c.setdefault(r["content"], []).append(r)
    for grp_recs in by_c.values():
        ranked = sorted([r for r in grp_recs if r.get("vpd_d7") is not None], key=lambda r: -r["vpd_d7"])
        for i, r in enumerate(ranked):
            r["top_third"] = i < max(1, len(ranked) // 3)
    corr = correlations(el)
    grp = groups(el)
    ctrl = controls(el)
    pooled = pooled_retention(root, recs)
    cands = candidates(el, corr, grp, ctrl, pooled)
    analysis = {"written": TODAY, "data_date": meta["data_date"], "channel": cfg.get("name"), "channel_id": cfg.get("channel_id"),
                "settings": {"min_age": args.min_age, "noise_floor": args.noise_floor, "hit_ratio": args.hit_ratio},
                "videos": recs, "correlations": corr, "groups": grp, "controls": ctrl, "retention": pooled, "candidates": cands}
    jsave(root / "analysis.json", analysis)
    jsave(root / "candidates.json", cands)
    jsave(root / "snapshots" / f"{meta['data_date']}.json", {"data_date": meta["data_date"], "videos": [
        {k: r.get(k) for k in ("id", "title", "views", "vpd_d7", "outlier_ratio", "hit", "ctr_pct", "impressions", "survival_30", "avp", "subs_per_1000")} for r in recs]})
    write_tables(root, {"data_date": meta["data_date"]}, recs, corr, grp, ctrl, pooled, cands, args.hit_ratio)
    hits = [r for r in el if r.get("hit")]
    print(f"analyse: {len(recs)} videos, {len(el)} eligible (>= {args.min_age} days), {len(hits)} hits, "
          f"{pooled.get('videos_with_retention', 0)} with retention; {len(cands)} candidate rules "
          f"({sum(1 for c in cands if c['tier'] == 'CONFIRMED')} confirmed, {sum(1 for c in cands if c['tier'] == 'PLAUSIBLE')} plausible)")
    print(f"  tables: {root / 'REPORT_TABLES.txt'}")
