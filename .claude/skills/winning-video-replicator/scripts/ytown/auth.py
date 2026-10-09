"""Read-only YouTube sign-in: one token per channel, never wider than these two scopes.

A Google token authorises exactly one channel. Brand Accounts show a chooser on the consent
page; the user picks the channel there. Refreshing a token cannot widen its scopes, so a
scope change means deleting the token and consenting again.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .util import jload, winpath

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
MONETARY_SCOPE = "https://www.googleapis.com/auth/yt-analytics-monetary.readonly"

# Where a client secret may already live on this machine (the clipping publishers' OAuth app;
# the YouTube Analytics API is enabled on it). The first that exists wins.
CLIENT_SECRET_CANDIDATES = [
    "C:/Users/admin/Downloads/client_secret_430398441095-j68cac3eitbui4sp83tna6tv8ael3r3d.apps.googleusercontent.com.json",
    "C:/Users/admin/Downloads/CLIPPING/publish/client_secret.json",
    "C:/Users/admin/Downloads/TALARICO/publish/client_secret.json",
    "C:/Users/admin/Downloads/SOFTCHAOS CLIPPING/publish/client_secret.json",
]


def client_secret_path(root: Path, override: str | None = None) -> Path:
    cands = ([override] if override else []) + [str(root / "client_secret.json")] + CLIENT_SECRET_CANDIDATES
    for c in cands:
        p = winpath(c)
        if p.exists():
            return p
    sys.exit("no OAuth client secret found; pass --client <client_secret.json> (a Desktop-app client with the "
             "YouTube Data API v3 and YouTube Analytics API enabled)")


def token_path(root: Path, key: str) -> Path:
    return root / f"token_{key}.json"


def get_creds(root: Path, key: str, client: str | None = None, manual: bool = False, monetary: bool = False,
              interactive: bool = True):
    """Load, refresh or create the channel's read-only credentials."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    scopes = SCOPES + ([MONETARY_SCOPE] if monetary else [])
    tp = token_path(root, key)
    creds = None
    if tp.exists():
        creds = Credentials.from_authorized_user_file(str(tp), scopes)
        have = set(creds.scopes or [])
        if not set(scopes) <= have:
            sys.exit(f"{tp} lacks a scope this run needs ({set(scopes) - have}); delete it and run `auth` again")
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        tp.write_text(creds.to_json(), encoding="utf-8")
    if not creds or not creds.valid:
        if not interactive:
            sys.exit(f"no valid token at {tp}: run `ytown.py auth --project ...` (one browser consent per channel)")
        from google_auth_oauthlib.flow import InstalledAppFlow
        secret = client_secret_path(root, client)
        flow = InstalledAppFlow.from_client_secrets_file(str(secret), scopes)
        if manual or os.environ.get("YTOWN_OAUTH_MANUAL"):
            creds = flow.run_console() if hasattr(flow, "run_console") else flow.run_local_server(port=0, open_browser=False)
        else:
            creds = flow.run_local_server(port=0)
        tp.write_text(creds.to_json(), encoding="utf-8")
        print(f"token saved: {tp}")
    return creds


def build_clients(creds):
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    ya = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
    return yt, ya


def whoami(yt) -> dict:
    r = yt.channels().list(part="id,snippet,contentDetails,statistics", mine=True).execute()
    items = r.get("items") or []
    if not items:
        sys.exit("the token points at no channel (channels.list(mine=true) returned nothing)")
    it = items[0]
    return {
        "id": it["id"],
        "title": it["snippet"]["title"],
        "handle": it["snippet"].get("customUrl"),
        "uploads": it.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads"),
        "subscribers": int(it.get("statistics", {}).get("subscriberCount", 0) or 0),
        "views": int(it.get("statistics", {}).get("viewCount", 0) or 0),
        "videos": int(it.get("statistics", {}).get("videoCount", 0) or 0),
    }


def check_channel(me: dict, cfg: dict) -> None:
    """Stop the run when the token's channel is not the configured one. Two videos once went to a wrong channel."""
    if cfg.get("channel_id") and me["id"] != cfg["channel_id"]:
        sys.exit(f"TOKEN MISMATCH: token points at {me['title']} ({me['id']}), channel.json says {cfg.get('name')} "
                 f"({cfg['channel_id']}). Delete analytics/token_{cfg['key']}.json and run `auth` again, picking the right channel.")


def cmd_auth(args) -> None:
    from .config import load_channel
    project = winpath(args.project).resolve()
    cfg = load_channel(project, args.out)
    root = Path(cfg["root"])
    creds = get_creds(root, cfg["key"], args.client, args.manual, args.monetary)
    yt, _ = build_clients(creds)
    me = whoami(yt)
    print(f"token now points at: {me['title']} ({me['handle']}, {me['id']}), {me['videos']} videos, {me['subscribers']} subscribers")
    check_channel(me, cfg)
    print("channel matches channel.json")


def cmd_whoami(args) -> None:
    from .config import load_channel
    project = winpath(args.project).resolve()
    cfg = load_channel(project, args.out)
    root = Path(cfg["root"])
    creds = get_creds(root, cfg["key"], interactive=False)
    yt, _ = build_clients(creds)
    me = whoami(yt)
    print(f"{me['title']} ({me['handle']}, {me['id']}): {me['videos']} videos, {me['subscribers']} subscribers, {me['views']} views")
    check_channel(me, cfg)
