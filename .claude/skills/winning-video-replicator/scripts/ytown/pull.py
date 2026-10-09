"""Pull the channel's catalogue and owner analytics into a dated snapshot.

Everything is cached under analytics/pull/<date>/ before anything reads it. A re-run with the
same date fetches only what is missing; --refresh re-fetches. --dry-run prints the queries and
touches no network (no token needed).

Reports, per video (see references/analytics-api.md for the dimension and filter rules):
  totals    dimensions=video, filters=video==<50 ids>, sort=-views
  days      dimensions=day, filters=video==<id>        from the upload date
  retention dimensions=elapsedVideoTimeRatio, filters=video==<id>
  traffic   dimensions=insightTrafficSourceType, filters=video==<id>
  search    dimensions=insightTrafficSourceDetail, filters=video==<id>;insightTrafficSourceType==YT_SEARCH
  suggested dimensions=insightTrafficSourceDetail, filters=video==<id>;insightTrafficSourceType==RELATED_VIDEO
  comments  Data API commentThreads (top 50 by relevance)
Channel-wide: channel_days (dimensions=day), content_type (dimensions=creatorContentType),
capabilities (the impressions probe, recorded so a future API change is noticed).
"""
from __future__ import annotations

import datetime as dt
import sys
import time
import urllib.request
from pathlib import Path

from .util import TODAY, iso_duration_s, jload, jsave, winpath

VIDEO_METRICS = ("views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,"
                 "likes,dislikes,comments,shares,subscribersGained,subscribersLost")
DAY_METRICS = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,likes"
CHANNEL_DAY_METRICS = "views,estimatedMinutesWatched,subscribersGained,subscribersLost"
RETENTION_METRICS = "audienceWatchRatio,relativeRetentionPerformance"
TRAFFIC_METRICS = "views,estimatedMinutesWatched"
SHORTS_MAX_S = 180


class Pull:
    def __init__(self, cfg: dict, yt, ya, snap: Path, refresh: bool, dry: bool, log=print):
        self.cfg, self.yt, self.ya, self.snap, self.refresh, self.dry, self.log = cfg, yt, ya, snap, refresh, dry, log
        self.errors: list[dict] = []
        self.calls = 0

    # ------------------------------------------------------------ plumbing
    def cached(self, rel: str):
        p = self.snap / rel
        if p.exists() and not self.refresh:
            return jload(p)
        return None

    def save(self, rel: str, data):
        jsave(self.snap / rel, data)
        return data

    def query(self, label: str, video: str | None = None, **kw):
        """One Analytics API query with backoff; failures are recorded, never fatal."""
        q = dict(ids="channel==MINE", **kw)
        if self.dry:
            self.log(f"  [dry] {label}: {q}")
            return None
        for attempt in range(4):
            try:
                self.calls += 1
                r = self.ya.reports().query(**q).execute()
                cols = [h["name"] for h in r.get("columnHeaders", [])]
                return {"query": q, "columns": cols, "rows": r.get("rows", []) or [], "fetched": TODAY}
            except Exception as e:  # HttpError or transport
                msg = str(e)
                if any(code in msg for code in ("500", "502", "503", "504", "429", "rateLimit")) and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                self.errors.append({"video": video, "report": label, "error": msg[:400]})
                self.log(f"  ! {label}{' ' + video if video else ''}: {msg[:160]}")
                return None
        return None

    # ------------------------------------------------------------ catalogue
    def catalogue(self, me: dict, only: set[str] | None):
        cat = self.cached("catalogue.json")
        if cat is not None and not only:
            return cat
        if self.dry:
            self.log("  [dry] playlistItems.list over the uploads playlist, then videos.list in chunks of 50 "
                     "(snippet, contentDetails, statistics, status, fileDetails, topicDetails)")
            return []
        ids = []
        token = None
        while True:
            self.calls += 1
            r = self.yt.playlistItems().list(part="contentDetails,status", playlistId=me["uploads"],
                                             maxResults=50, pageToken=token).execute()
            for it in r.get("items", []):
                ids.append(it["contentDetails"]["videoId"])
            token = r.get("nextPageToken")
            if not token:
                break
        if only:
            ids = [i for i in ids if i in only] or sorted(only)
        videos = []
        for i in range(0, len(ids), 50):
            chunk = ids[i:i + 50]
            parts = "snippet,contentDetails,statistics,status,fileDetails,topicDetails"
            try:
                self.calls += 1
                r = self.yt.videos().list(part=parts, id=",".join(chunk), maxResults=50).execute()
            except Exception as e:
                if "fileDetails" in str(e) or "forbidden" in str(e).lower():
                    self.calls += 1
                    r = self.yt.videos().list(part="snippet,contentDetails,statistics,status,topicDetails",
                                              id=",".join(chunk), maxResults=50).execute()
                else:
                    raise
            for it in r.get("items", []):
                videos.append(self._video_record(it))
        videos.sort(key=lambda v: v["publishedAt"] or "")
        for n, v in enumerate(videos, 1):
            v["upload_number"] = n
        self.save("catalogue.json", videos)
        return videos

    @staticmethod
    def _video_record(it: dict) -> dict:
        sn, cd, stt, fd = it.get("snippet", {}), it.get("contentDetails", {}), it.get("status", {}), it.get("fileDetails", {})
        stats = it.get("statistics", {})
        dur = iso_duration_s(cd.get("duration"))
        streams = fd.get("videoStreams") or []
        aspect = None
        if streams:
            w, h = streams[0].get("widthPixels"), streams[0].get("heightPixels")
            if w and h:
                aspect = round(float(w) / float(h), 3)
        thumbs = sn.get("thumbnails", {})
        best = thumbs.get("maxres") or thumbs.get("standard") or thumbs.get("high") or thumbs.get("medium") or {}
        desc = sn.get("description", "") or ""
        return {
            "id": it["id"],
            "title": sn.get("title"),
            "description": desc,
            "tags": sn.get("tags", []),
            "publishedAt": sn.get("publishedAt"),
            "categoryId": sn.get("categoryId"),
            "defaultLanguage": sn.get("defaultLanguage") or sn.get("defaultAudioLanguage"),
            "duration_s": dur,
            "definition": cd.get("definition"),
            "caption": cd.get("caption"),
            "privacy": stt.get("privacyStatus"),
            "madeForKids": stt.get("madeForKids"),
            "fileName": fd.get("fileName"),
            "file_duration_s": (float(fd["durationMs"]) / 1000.0) if fd.get("durationMs") else None,
            "aspect": aspect,
            "is_short": bool(dur is not None and dur <= SHORTS_MAX_S and (aspect is not None and aspect < 1.0)),
            "thumbnail_url": best.get("url"),
            "statistics": {"views": int(stats.get("viewCount", 0) or 0), "likes": int(stats.get("likeCount", 0) or 0),
                           "comments": int(stats.get("commentCount", 0) or 0)},
            "topics": [t.rsplit("/", 1)[-1] for t in it.get("topicDetails", {}).get("topicCategories", [])],
        }

    def thumbnails(self, videos: list[dict]):
        if self.dry:
            return
        d = self.snap / "thumbs"
        d.mkdir(exist_ok=True)
        for v in videos:
            url, p = v.get("thumbnail_url"), d / f"{v['id']}.jpg"
            if not url or p.exists():
                continue
            try:
                urllib.request.urlretrieve(url, p)
            except Exception as e:
                self.errors.append({"video": v["id"], "report": "thumbnail", "error": str(e)[:200]})

    # ------------------------------------------------------------ analytics
    def totals(self, videos: list[dict], end: str):
        got = self.cached("totals.json") or {}
        todo = [v["id"] for v in videos if v["id"] not in got]
        if not todo and not self.dry:
            return got
        start = min((v["publishedAt"] or end)[:10] for v in videos) if videos else "2020-01-01"
        for i in range(0, len(todo or ["dry"]), 50):
            chunk = todo[i:i + 50]
            r = self.query("totals", startDate=start, endDate=end, metrics=VIDEO_METRICS, dimensions="video",
                           filters="video==" + ",".join(chunk or ["<ids>"]), sort="-views", maxResults=50)
            if r:
                for row in r["rows"]:
                    d = dict(zip(r["columns"], row))
                    got[d.pop("video")] = d
                for vid in chunk:
                    got.setdefault(vid, {"views": 0, "note": "no analytics row (0 views in window)"})
        if not self.dry:
            self.save("totals.json", got)
        return got

    def per_video(self, v: dict, end: str):
        vid = v["id"]
        pub = (v.get("publishedAt") or end)[:10]
        base = f"videos/{vid}"
        # days: incremental
        days = self.cached(f"{base}/days.json")
        if days is None or self.refresh or (days.get("rows") and days["rows"][-1][0] < end):
            start = pub if (days is None or self.refresh) else days["rows"][-1][0]
            r = self.query("days", vid, startDate=start, endDate=end, metrics=DAY_METRICS, dimensions="day", filters=f"video=={vid}")
            if r:
                if days and not self.refresh:
                    old = [row for row in days["rows"] if row[0] < start]
                    r["rows"] = old + r["rows"]
                self.save(f"{base}/days.json", r)
        if self.cached(f"{base}/retention.json") is None:
            r = self.query("retention", vid, startDate=pub, endDate=end, metrics=RETENTION_METRICS,
                           dimensions="elapsedVideoTimeRatio", filters=f"video=={vid}")
            if r:
                self.save(f"{base}/retention.json", r)
        if self.cached(f"{base}/traffic.json") is None:
            r = self.query("traffic", vid, startDate=pub, endDate=end, metrics=TRAFFIC_METRICS,
                           dimensions="insightTrafficSourceType", filters=f"video=={vid}", sort="-views")
            if r:
                self.save(f"{base}/traffic.json", r)
        for label, typ in (("search", "YT_SEARCH"), ("suggested", "RELATED_VIDEO"), ("external", "EXT_URL")):
            if self.cached(f"{base}/{label}.json") is None:
                r = self.query(label, vid, startDate=pub, endDate=end, metrics="views",
                               dimensions="insightTrafficSourceDetail",
                               filters=f"video=={vid};insightTrafficSourceType=={typ}", sort="-views", maxResults=25)
                if r:
                    self.save(f"{base}/{label}.json", r)
        if self.cached(f"{base}/comments.json") is None:
            self.comments(vid)

    def comments(self, vid: str):
        if self.dry:
            self.log(f"  [dry] commentThreads.list videoId={vid} order=relevance maxResults=50")
            return
        try:
            self.calls += 1
            r = self.yt.commentThreads().list(part="snippet", videoId=vid, order="relevance", maxResults=50,
                                              textFormat="plainText").execute()
            out = []
            for it in r.get("items", []):
                c = it["snippet"]["topLevelComment"]["snippet"]
                out.append({"text": c.get("textDisplay"), "likes": int(c.get("likeCount", 0) or 0),
                            "at": c.get("publishedAt"), "replies": int(it["snippet"].get("totalReplyCount", 0) or 0)})
            self.save(f"videos/{vid}/comments.json", {"fetched": TODAY, "comments": out})
        except Exception as e:
            self.errors.append({"video": vid, "report": "comments", "error": str(e)[:200]})
            self.save(f"videos/{vid}/comments.json", {"fetched": TODAY, "comments": [], "error": str(e)[:200]})

    def channel_wide(self, start: str, end: str):
        if self.cached("channel_days.json") is None:
            r = self.query("channel_days", startDate=start, endDate=end, metrics=CHANNEL_DAY_METRICS, dimensions="day")
            if r:
                self.save("channel_days.json", r)
        if self.cached("content_type.json") is None:
            r = self.query("content_type", startDate=start, endDate=end, metrics="views,estimatedMinutesWatched",
                           dimensions="creatorContentType")
            if r:
                self.save("content_type.json", r)
        if self.cached("capabilities.json") is None and not self.dry:
            probe = self.query("impressions_probe", startDate=start, endDate=end, metrics="views,impressions", dimensions="video",
                               sort="-views", maxResults=1)
            self.save("capabilities.json", {"impressions_in_api": bool(probe), "checked": TODAY,
                                            "note": "impressions and click-through come from Studio exports while this is false"})


def cmd_pull(args) -> None:
    from .auth import build_clients, check_channel, get_creds, whoami
    from .config import load_channel

    project = winpath(args.project).resolve()
    cfg = load_channel(project, args.out)
    root = Path(cfg["root"])
    snap = root / "pull" / (args.date or TODAY)
    snap.mkdir(parents=True, exist_ok=True)
    end = (dt.date.today() - dt.timedelta(days=args.lag)).isoformat()
    only = set(args.videos.split(",")) if args.videos else None

    if args.dry_run:
        print(f"[dry run] project {project}, channel {cfg.get('name')} ({cfg.get('channel_id')}), snapshot {snap}, data end {end}")
        p = Pull(cfg, None, None, snap, args.refresh, True)
        me = {"uploads": "<uploads playlist>"}
        p.catalogue(me, only)
        p.totals([], end)
        p.per_video({"id": "<video id>", "publishedAt": "<upload date>"}, end)
        p.channel_wide(args.since or "<first upload>", end)
        print("no network calls were made")
        return

    creds = get_creds(root, cfg["key"], interactive=False)
    yt, ya = build_clients(creds)
    me = whoami(yt)
    check_channel(me, cfg)
    print(f"pulling {me['title']} ({me['id']}): {me['videos']} videos, data to {end}, snapshot {snap.name}")
    p = Pull(cfg, yt, ya, snap, args.refresh, False)
    jsave(snap / "channel.json", {**me, "fetched": TODAY, "data_end": end})
    videos = p.catalogue(me, only)
    print(f"  catalogue: {len(videos)} videos ({sum(1 for v in videos if v['is_short'])} Shorts)")
    p.thumbnails(videos)
    compare = [v for v in videos if v.get("privacy") in ("public", "unlisted")]
    if only:
        compare = [v for v in compare if v["id"] in only]
    p.totals(compare, end)
    for n, v in enumerate(compare, 1):
        print(f"  [{n}/{len(compare)}] {v['id']} {v['title'][:60]}")
        p.per_video(v, end)
        time.sleep(0.05)
    first = min((v["publishedAt"] or end)[:10] for v in videos) if videos else end
    p.channel_wide(args.since or first, end)
    jsave(snap / "errors.json", p.errors)
    (root / "latest.txt").write_text(snap.name, encoding="utf-8")
    print(f"done: {p.calls} API calls, {len(p.errors)} errors (errors.json), latest -> {snap.name}")
