"""Offline test of the kit: no YouTube, no token, nothing written into a project folder.

    python scripts/tests/offline_test.py [--keep]

Builds a fake channel under the scratchpad from one real GEMS join (or a synthetic timeline when
GEMS is not on this machine), then runs retention (+ chart), analyse, report and the rules
bookkeeping end to end, and checks the Studio CSV parser and the retention maths on known curves.
"""
from __future__ import annotations

import json
import math
import os
import random
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ytown import analyse, retention, rules, studio  # noqa: E402
from ytown.cli import main  # noqa: E402
from ytown.timeline import make_join  # noqa: E402
from ytown.util import jload, jsave  # noqa: E402

GEMS = Path("C:/Users/admin/Downloads/GEMS")
PASS = []


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    PASS.append(msg)


def synthetic_join(vid: str, dur: float = 600.0) -> dict:
    words, t = [], 0.0
    sections = [{"name": "OPEN", "kind": "hook", "t0": 0, "t1": 40}, {"name": "ITEM 1", "kind": "item", "t0": 40, "t1": 300},
                {"name": "CTA", "kind": "cta", "t0": 300, "t1": 330}, {"name": "ITEM 2", "kind": "item", "t0": 330, "t1": 560},
                {"name": "OUTRO", "kind": "outro", "t0": 560, "t1": dur}]
    i = 0
    while t < dur - 1:
        w = f"word{i}" + ("." if i % 12 == 11 else "")
        words.append({"w": w, "s": round(t, 2), "e": round(t + 0.3, 2)})
        t += 0.4
        i += 1
    beats, t = [], 0.0
    kinds = ["clip", "clip", "still", "card", "clip", "grid"]
    k = 0
    while t < dur:
        ln = 2.5 + (k % 3)
        beats.append({"t0": t, "t1": min(dur, t + ln), "kind": kinds[k % len(kinds)], "label": f"b{k}", "moving": kinds[k % len(kinds)] == "clip", "text": kinds[k % len(kinds)] == "card"})
        t += ln
        k += 1
    spans = [{"t0": 100, "t1": 103, "type": "price_flash", "label": "$1,000"}, {"t0": 45, "t1": dur, "type": "music", "label": "bed"}]
    return make_join(vid, f"episodes/{vid}", dur, sections, [], beats, spans, words, {"takes": 2, "bed": True}, "gems")


def curve(dur: float, intro_drop: float, body_rate: float, dip_at: float | None = None) -> list[dict]:
    pts = []
    for i in range(100):
        r = i / 100.0
        t = r * dur
        y = 1.0 - intro_drop * (1 - math.exp(-t / 20.0)) - body_rate * t
        if dip_at is not None and t >= dip_at:
            y -= 0.12
        pts.append({"ratio": r, "abs": max(0.05, y), "rel": 0.5})
    return pts


def main_test(keep: bool) -> None:
    root = Path(tempfile.mkdtemp(prefix="wvr_test_", dir=os.environ.get("WVR_TMP") or None))
    proj = root / "project"
    proj.mkdir()
    (proj / "CLAUDE.md").write_text("# Test project\n\n## Standing rules\n- keep it short\n", encoding="utf-8")
    out = root / "analytics"
    main(["init", "--project", str(proj), "--out", str(out), "--channel-id", "UCtest000000000000000000", "--name", "Test Channel", "--adapter", "generic", "--key", "test"])

    # --- retention maths on known curves
    j = synthetic_join("vid000000A1")
    res = retention.analyse(j, curve(600, 0.30, 0.0004, dip_at=150))
    check(res is not None, "retention: analysed a synthetic curve")
    check(0.55 < res["survival"]["30s"] < 0.80, f"retention: 30 s survival plausible ({res['survival']['30s']})")
    check(any(140 <= d["t"] <= 162 for d in res["dips"]), f"retention: the planted dip at 150 s was found ({[d['t'] for d in res['dips']]})")
    planted = min(res["dips"], key=lambda d: abs(d["t"] - 150))
    check(planted["section"] == "ITEM 1" and planted["sentence"] and planted["beats"], "retention: the dip carries its section, sentence and beats")
    check("clip" in res["per_beat_kind"] and "music" in res["per_span_type"], "retention: per-kind and per-span tables exist")
    flat = retention.analyse(j, curve(600, 0.10, 0.0002))
    check(not any(not d["in_intro"] for d in flat["dips"]), "retention: a smooth curve has no body dips")

    # --- fake snapshot: 8 videos, 2 hits, from the synthetic (or a real GEMS) join
    snap = out / "pull" / "2026-10-03"
    (snap / "videos").mkdir(parents=True)
    (out / "latest.txt").write_text("2026-10-03", encoding="utf-8")
    jsave(snap / "channel.json", {"id": "UCtest000000000000000000", "title": "Test Channel", "data_end": "2026-10-03"})
    real = None
    if GEMS.exists():
        try:
            from ytown.adapters import gems
            eps = gems.episodes(GEMS)
            if eps:
                from ytown.mapping import build_join
                real = build_join(GEMS, {"adapter": "gems", "root": str(out)}, eps[0], None, out / "join" / "cache")
        except Exception as e:  # the real join is a bonus, never a requirement
            print("  (real GEMS join skipped:", str(e)[:80], ")")
    random.seed(7)
    cat, totals = [], {}
    rows_videos = []
    for i in range(8):
        vid = f"vid{i:08d}"
        dur = 600.0
        hit = i in (2, 5)
        import datetime as _dt
        pub_date = _dt.date(2026, 8, 10) + _dt.timedelta(days=i * 5)
        pub = f"{pub_date.isoformat()}T15:00:00Z"
        cat.append({"id": vid, "title": f"Every Test Type Explained {i}" + (" BIGGEST" if hit else ""), "description": "0:00 intro\n1:00 item", "tags": ["a", "b"],
                    "publishedAt": pub, "duration_s": dur, "privacy": "public", "fileName": f"test{i}.mp4", "aspect": 1.778, "is_short": False,
                    "thumbnail_url": None, "statistics": {"views": 0, "likes": 0, "comments": 0}, "upload_number": i + 1})
        base = 400 if hit else 60
        totals[vid] = {"views": base * 30, "estimatedMinutesWatched": base * 30 * 4, "averageViewDuration": 240 + (60 if hit else 0),
                       "averageViewPercentage": 40 + (10 if hit else 0), "likes": base, "comments": 5, "shares": 3, "subscribersGained": base // 10, "subscribersLost": 1}
        days = {"columns": ["day", "views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage", "subscribersGained", "likes"], "rows": []}
        for d in range(35):
            day = (pub_date + _dt.timedelta(days=d)).isoformat()
            days["rows"].append([day, int(base * (3 if d < 3 else 1) * random.uniform(0.7, 1.3)), 100, 200, 40, 2, 3])
        jsave(snap / "videos" / vid / "days.json", days)
        jsave(snap / "videos" / vid / "traffic.json", {"columns": ["insightTrafficSourceType", "views", "estimatedMinutesWatched"],
                                                        "rows": [["SUBSCRIBER", base * 10, 1], ["RELATED_VIDEO", base * 15, 1], ["YT_SEARCH", base * 5, 1]]})
        jsave(snap / "videos" / vid / "comments.json", {"comments": [{"text": "love this, do more please", "likes": 3}, {"text": "actually that is wrong", "likes": 1}]})
        pts = curve(dur, 0.25 if hit else 0.40, 0.0004, dip_at=None if hit else 200)
        jsave(snap / "videos" / vid / "retention.json", {"columns": ["elapsedVideoTimeRatio", "audienceWatchRatio", "relativeRetentionPerformance"],
                                                          "rows": [[p["ratio"], p["abs"], p["rel"]] for p in pts]})
        jj = json.loads(json.dumps(real if (real and i % 2 == 0) else synthetic_join(vid, dur)))
        jj["video_id"] = vid
        jj["duration"] = dur if not (real and i % 2 == 0) else jj["duration"]
        jsave(out / "join" / f"{vid}.json", jj)
        rows_videos.append({"id": vid, "title": cat[-1]["title"], "episode": jj["episode"], "slug": vid, "match": "file",
                            "hook_type": "tease" if hit else "cold open", "voice": "Brad", "model": "v3", "template": "ruby"})
    jsave(snap / "catalogue.json", cat)
    jsave(snap / "totals.json", totals)
    jsave(snap / "studio" / "content.json", {f"vid{i:08d}": {"impressions": 20000 if i in (2, 5) else 3000, "ctr_pct": 6.5 if i in (2, 5) else 3.1} for i in range(8)})
    jsave(out / "videos.json", rows_videos)

    main(["retention", "--project", str(proj), "--out", str(out), "--charts"])
    check((out / "retention" / "vid00000002.json").exists(), "retention: per-video result written")
    check((out / "retention" / "vid00000002.png").exists(), "charts: per-video PNG written")
    main(["analyse", "--project", str(proj), "--out", str(out), "--min-age", "7", "--noise-floor", "300", "--hit-ratio", "2.0"])
    an = jload(out / "analysis.json")
    hits = [v["id"] for v in an["videos"] if v.get("hit")]
    check(set(hits) == {"vid00000002", "vid00000005"}, f"analyse: the two planted hits are the hits ({hits})")
    check(any(c["attribute"] == "hand_hook_type" for c in an["candidates"]), "analyse: the hook-type group shows up as a candidate")
    check(any(c["kind"] == "retention" for c in an["candidates"]), "analyse: pooled retention produced candidates")
    check((out / "REPORT_TABLES.txt").read_bytes().count(b"\r\n") > 20, "analyse: REPORT_TABLES.txt is CRLF plain text")
    main(["report", "--project", str(proj), "--out", str(out), "--file", str(root / "WHAT WORKS.txt")])
    check((root / "WHAT WORKS.txt").exists(), "report: WHAT WORKS.txt written")

    # --- rules bookkeeping
    main(["rules", "propose", "--project", str(proj), "--out", str(out)])
    rl = jload(out / "rules.json")
    check(len(rl) >= 2, f"rules: candidates recorded as proposed ({len(rl)})")
    rid = rl[0]["id"]
    main(["rules", "decide", "--project", str(proj), "--out", str(out), "--id", rid, "--decision", "apply", "--wording", "Open every video on a tease", "--edit", "script_check WARN"])
    md = (proj / "CLAUDE.md").read_text(encoding="utf-8")
    check(rules.SECTION in md and "Open every video on a tease" in md, "rules: accepted rule appended to CLAUDE.md under the analytics section")
    main(["rules", "decide", "--project", str(proj), "--out", str(out), "--id", rl[1]["id"], "--decision", "skip"])
    md = (proj / "CLAUDE.md").read_text(encoding="utf-8")
    check(rules.REJECTED in md, "rules: a skipped rule lands under Reviewed and rejected")
    main(["rules", "decide", "--project", str(proj), "--out", str(out), "--id", "none", "--rule", "Never a card in the first 10 seconds", "--decision", "apply", "--evidence", "3 of 3 intro dips sat on a card"])
    md = (proj / "CLAUDE.md").read_text(encoding="utf-8")
    check(md.count(rules.SECTION) == 1 and "Never a card in the first 10 seconds" in md, "rules: a second accepted rule joins the same section once")
    main(["rules", "retest", "--project", str(proj), "--out", str(out)])
    rl = jload(out / "rules.json")
    check(any(r["status"] for r in rl if r["decisions"]), "rules: retest recorded a status on applied rules")

    # --- Studio parser
    content = ("Content,Video title,Video publish time,Impressions,Impressions click-through rate (%),Views,Average view duration,Watch time (hours)\n"
               "Total,,,50000,4.2,9000,0:03:10,470.1\n"
               "abcdefghijk,Every Pearl Type Explained,Oct 1 2026,20000,6.51,2300,0:04:12,160.3\n")
    got = studio.parse_content_table(studio.read_csv_text(content), "test.csv", {"from": "2026-09-01", "to": "2026-10-01"})
    check(got.get("abcdefghijk", {}).get("impressions") == 20000 and abs(got["abcdefghijk"]["avd_s"] - 252) < 0.1 and got["abcdefghijk"]["ctr_pct"] == 6.51,
          "studio: the Content table parses (impressions, click-through, average view duration)")
    ret = ("Video position (%),Absolute audience retention (%),Relative audience retention\n0,100,0.5\n10,71.2,0.5\n50,40,0.4\n")
    pts = studio.parse_retention_csv(studio.read_csv_text(ret))
    check(len(pts) == 3 and abs(pts[1]["abs"] - 0.712) < 1e-6 and pts[2]["ratio"] == 0.5, "studio: a retention export parses to ratios 0..1")

    # --- dry-run pull touches no network
    main(["pull", "--project", str(proj), "--out", str(out), "--dry-run"])
    PASS.append("pull: dry run printed the plan without a token")

    print(f"\n{len(PASS)} checks passed")
    for p in PASS:
        print("  ok", p)
    if keep:
        print("kept:", root)
    else:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main_test("--keep" in sys.argv)
