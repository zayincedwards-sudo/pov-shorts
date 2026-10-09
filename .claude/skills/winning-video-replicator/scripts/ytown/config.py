"""Per-project configuration: analytics/channel.json and the adapter choice."""
from __future__ import annotations

import sys
from pathlib import Path

from .util import analytics_root, jload, jsave, winpath

ADAPTERS = ("gems", "astro", "otto", "ancestral", "anime", "clips", "generic")

GITIGNORE_LINES = [
    "# winning-video-replicator: credentials, exports and other people's images stay out of git",
    "analytics/token_*.json",
    "analytics/client_secret*.json",
    "analytics/pull/*/thumbs/",
    "analytics/studio_exports/",
    "analytics/reference/*.jpg",
]


def detect_adapter(project: Path) -> str:
    """Guess the pipeline from what the folder contains. The user can override with --adapter."""
    if (project / "publish" / "uploaded_manifest.json").exists():
        return "clips"
    if (project / "lib" / "vo.js").exists() and (project / "episodes").exists():
        return "astro"
    if (project / "tools" / "host.py").exists() or (project / "v2" / "tools" / "host.py").exists():
        return "otto"
    if (project / "episodes" / "_engine").exists():
        return "ancestral"
    eps = list((project / "episodes").glob("*/render/timeline.json")) if (project / "episodes").exists() else []
    if eps:
        return "anime"
    if (project / "tools" / "vo.py").exists() and (project / "episodes").exists():
        return "gems"
    return "generic"


def load_channel(project: Path, out: str | None = None) -> dict:
    root = analytics_root(project, out)
    cfg = jload(root / "channel.json")
    if not cfg:
        sys.exit(f"no {root / 'channel.json'}: run `ytown.py init --project {project} --channel-id UC... --name ...` first")
    cfg.setdefault("adapter", detect_adapter(project))
    cfg.setdefault("content", "mixed")
    cfg["project"] = str(project)
    cfg["root"] = str(root)
    return cfg


def cmd_init(args) -> None:
    project = winpath(args.project).resolve()
    if not project.exists():
        sys.exit(f"project folder not found: {project}")
    root = analytics_root(project, args.out)
    existing = jload(root / "channel.json", {}) or {}
    cfg = {
        "key": args.key or existing.get("key") or project.name.lower().replace(" ", "_"),
        "channel_id": args.channel_id or existing.get("channel_id"),
        "name": args.name or existing.get("name"),
        "handle": args.handle or existing.get("handle"),
        "adapter": args.adapter or existing.get("adapter") or detect_adapter(project),
        "content": args.content or existing.get("content") or "mixed",
        "project": str(project),
        "created": existing.get("created") or __import__("datetime").date.today().isoformat(),
    }
    if not cfg["channel_id"]:
        sys.exit("--channel-id is required the first time (the UC... id from the channel's About page or Studio settings)")
    jsave(root / "channel.json", cfg)
    for sub in ("pull", "join", "retention", "studio_exports", "reference", "snapshots"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    gi = project / ".gitignore"
    text = gi.read_text(encoding="utf-8") if gi.exists() else ""
    missing = [ln for ln in GITIGNORE_LINES if ln not in text]
    if missing and not args.out:
        with open(gi, "a", encoding="utf-8", newline="\n") as f:
            if text and not text.endswith("\n"):
                f.write("\n")
            f.write("\n".join(missing) + "\n")
    print(f"channel.json written: {cfg['name']} ({cfg['channel_id']}), adapter {cfg['adapter']}, content {cfg['content']}")
    print(f"analytics root: {root}")
    if missing and not args.out:
        print(f".gitignore: added {len(missing)} lines")
