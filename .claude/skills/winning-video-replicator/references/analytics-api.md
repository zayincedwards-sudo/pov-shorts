# YouTube's owner data: what we can pull, how, and what is missing

Everything here is free within quota. Read it before the first pull in a project. Dates are 2026 unless written.

## Authorisation (one read-only token per channel)
- **OAuth client:** the Google Cloud project the clipping publishers already use. Its Desktop-app client secret sits at
  `C:/Users/admin/Downloads/client_secret_430398441095-j68cac3eitbui4sp83tna6tv8ael3r3d.apps.googleusercontent.com.json`
  (copies in `CLIPPING/publish/`, `TALARICO/publish/`, `SOFTCHAOS CLIPPING/publish/`). The YouTube Analytics API is
  already enabled on it: `pov-pipeline-handover/meme_scanner/channel_stats.py` queried it for SoftChaos. Never copy
  the file into a tracked folder; reference it by path or copy it into the project's gitignored `analytics/`.
- **Scopes for this skill, and nothing wider:**
  `https://www.googleapis.com/auth/youtube.readonly` and `https://www.googleapis.com/auth/yt-analytics.readonly`.
  Add `yt-analytics-monetary.readonly` only if the user wants revenue on a monetised channel (QUESTIONS.txt, 7).
- **One token per channel.** A Google token authorises exactly one channel (Brand Accounts show a chooser at consent).
  Store it as `analytics/token_<channel key>.json`, gitignored. Refreshing a token cannot widen its scopes; a new scope
  means a fresh consent in the browser.
- **Flow:** `google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(path, SCOPES).run_local_server(port=0)`
  opens the consent page in the user's browser. The user signs in and picks the channel. Save `creds.to_json()`.
  `CLIPPING/publish/authorize.py` and `youtube_api.py` (`get_youtube_client`, `whoami`, `token_path_for`) are the
  worked example, including the manual-URL fallback.
- **Verify before reading a number:** `youtube.channels().list(part="id,snippet", mine=True)` returns the channel the
  token points at. Compare with `analytics/channel.json`. On a mismatch, stop and say which channel it is.
- Libraries present on this machine (the handover venv proves them): `google-api-python-client`,
  `google-auth-oauthlib`. In a project without a venv: `pip install google-api-python-client google-auth-oauthlib`.

## The Data API (youtube v3): the catalogue and public stats
Quota 10,000 units a day by default; every call below costs 1 unit, so a whole channel is a few dozen units.
- `channels().list(part="contentDetails,statistics,snippet", mine=True)` → `contentDetails.relatedPlaylists.uploads`.
- `playlistItems().list(part="contentDetails", playlistId=<uploads>, maxResults=50)` paged → every video id, public,
  unlisted and private. (`search().list` costs 100 units and misses videos; never use it for this.)
- `videos().list(part="snippet,contentDetails,statistics,status,fileDetails,topicDetails", id=<50 ids>)`:
  - `snippet`: title, description, tags, publishedAt, categoryId, `thumbnails.maxres.url` (the LIVE thumbnail; save it).
  - `contentDetails.duration` (ISO 8601, e.g. `PT13M24S`), `definition`, `caption`.
  - `statistics`: viewCount, likeCount, commentCount (public counters, lifetime).
  - `status`: privacyStatus, madeForKids, publishAt.
  - `fileDetails` (owner only): `fileName` and `durationMs` of the uploaded file. The file name is the first key for
    mapping a video to its episode folder.
- `commentThreads().list(part="snippet", videoId=<id>, order="relevance", maxResults=50)` → top comments with like
  counts. Classify them (praise, complaint, request, correction, "where is X") as a qualitative signal.
- `captions().list` and `.download` exist for our own videos but cost 200 units a download and we already hold the
  scripts and word timings; do not use them.

## The Analytics API (youtubeAnalytics v2): the owner's numbers
One method, `reports().query(ids="channel==MINE", startDate, endDate, metrics, dimensions, filters, sort, maxResults)`.
Dates are `YYYY-MM-DD`. The data is complete about 3 days back; the newest 2-3 days are partial. Say the data date.
Reports used by this skill, with the dimensions and filters they need:

| report | dimensions | filters | metrics | notes |
|---|---|---|---|---|
| per-video totals | `video` | none, or `video==id1,id2,...` | `views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,dislikes,comments,shares,subscribersGained,subscribersLost` | with `dimensions=video` and no filter, `sort=-views` and `maxResults<=200` are required (the `channel_stats.py` pattern) |
| per-day series | `day` | `video==<id>` | `views,estimatedMinutesWatched,averageViewDuration,subscribersGained` | one video per query; gives views per day at day 7 and day 28 |
| retention curve | `elapsedVideoTimeRatio` | `video==<id>` (one video); optional `audienceType==ORGANIC` | `audienceWatchRatio,relativeRetentionPerformance` | 100 rows, 0.00 to 0.99 of the runtime; absent on videos below YouTube's view threshold |
| traffic types | `insightTrafficSourceType` | `video==<id>` | `views,estimatedMinutesWatched` | types include `SUBSCRIBER` (home and subscriptions feed, Studio's "Browse"), `RELATED_VIDEO` (Suggested), `YT_SEARCH`, `SHORTS`, `EXT_URL`, `NOTIFICATION`, `PLAYLIST`, `YT_CHANNEL`, `END_SCREEN` |
| traffic details | `insightTrafficSourceDetail` | `video==<id>;insightTrafficSourceType==YT_SEARCH` (search terms) or `==RELATED_VIDEO` (the videos that suggested us) | `views` | `sort=-views`, `maxResults<=25`; details exist only for some types |
| channel tide | `day` | none | `views,estimatedMinutesWatched,subscribersGained,subscribersLost` | the whole channel per day |
| content type | `creatorContentType` | none | `views` | SHORTS / VIDEO_ON_DEMAND / LIVE_STREAM; if the query is refused, split Shorts by duration under 61 s and a vertical frame instead |

Not pulled on purpose (the user, 6 Oct 2026: "don't worry about who the viewers are"): `subscribedStatus`,
`deviceType`, `country`, `ageGroup,gender`. Traffic sources stay, because they say whether a video was shown.
`scripts/ytown/pull.py` issues exactly the reports in the table above; `pull --dry-run` prints them.

Reading the curve: `audienceWatchRatio` at ratio r is the share of views still playing at r of the runtime (it can
exceed 1 near the start when viewers rewind). `relativeRetentionPerformance` compares the video with YouTube videos of
similar length, not with our own uploads. Studio's "Intro" figure is the watch ratio at 30 seconds, so read it at
`r = 30 / duration`.

Two measures that look alike and are not: `averageViewPercentage` is over engaged views, `estimatedMinutesWatched`
over all views. Store both; never divide one by the other. In 2025 YouTube split Shorts `views` from `engagedViews`;
when a Shorts channel is analysed, pull `engagedViews` too if the API accepts it.

## Not in the API (Studio only)
- **Impressions and impressions click-through rate.** Try `metrics=impressions` once per run and record the refusal
  in `ANALYTICS.md`, so a future API change is noticed. Until then they come from Studio.
- **Key-moments labels** (Intro, Top moments, Spikes, Dips): compute them from the curve instead.
- **Test & Compare** results and the thumbnail history.
- **New vs returning viewers**, title and thumbnail change history, real-time counts.

### Getting the Studio numbers
Two routes; QUESTIONS.txt question 8 picks the default.
1. **Claude in Chrome**, in the user's signed-in browser. Load the extension's tools, open YouTube Studio, switch to
   the right channel (avatar → Switch account), and READ THE CHANNEL NAME on the page before anything else. Analytics
   → Advanced mode → the Content table with Impressions, Impressions click-through rate, Views, Average view duration
   and Watch time over the chosen window → Export (CSV). For one video, its Engagement tab holds the retention chart
   and Advanced mode exports the curve too. Downloads land in `Downloads/`; move them into
   `analytics/studio_exports/<date>/` at once. Never click anything that changes the channel.
2. **The user exports** the same tables and drops the CSVs into that folder when the report says which are missing.
Record in the report which videos have click-through figures and from which date, and compare click-through only
among videos with a similar impression count and source mix.

## Caching and snapshots
- Every response is written as JSON under `analytics/pull/<date>/` before anything reads it, one file per report and
  video (`<video id>.retention.json`, `.days.json`, `.traffic.json`...). A re-run reads the cache and fetches only
  what is new: new videos, and days after the last cached day.
- `analytics/latest.txt` names the newest snapshot. The join and the report read from there.
- Tokens, Studio exports and the live thumbnails (other people's images may appear in them) are gitignored. The pulled
  JSON is our own data and is tracked, so trends survive and diffs are plain `git diff`.

## Errors seen before and what they mean
- `403 insufficientPermissions` or `quotaExceeded` on Analytics: the token lacks `yt-analytics.readonly` (fresh
  consent) or the API is not enabled on the Cloud project (it is on the clipping client; check which secret was used).
- `400` on a `video` dimension query without `sort`/`maxResults` or with too many ids: use the pattern in the table.
- An empty `rows` for the retention report: the video is under YouTube's threshold or younger than the lag. Say so.
- `invalid_grant` on refresh: the token was revoked or the consent screen is in Testing and the token expired after 7
  days. Re-run the consent; publishing the consent screen removes the 7-day expiry.
