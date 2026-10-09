"""Command line for the winning-video-replicator kit.

    python ~/.claude/skills/winning-video-replicator/scripts/ytown.py <command> --project <folder> [...]

init       write analytics/channel.json for a project (channel id, adapter, content type)
auth       one browser consent per channel; read-only scopes; verifies the channel
whoami     which channel the token points at
pull       catalogue + owner analytics into analytics/pull/<date>/  (--dry-run touches no network)
studio     import Studio CSV/zip exports (impressions, click-through, retention curves)
heatmap    public "most replayed" heatmaps of reference videos (yt-dlp)
cuts       shot boundaries for a video without a build timeline
map        videos -> episode folders (analytics/videos.json)
join       build the per-video timeline files from the project's artifacts
retention  lay the retention curves on the timelines (+ --charts)
analyse    scoreboards, attributes, correlations, controls, pooled retention, candidates
report     WHAT WORKS.txt at the project root from analytics/findings.json
rules      list | propose | decide | retest  (the user decides every rule)
run        map -> join -> retention --charts -> analyse
"""
from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ytown.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--project", required=True, help="the project folder (its CLAUDE.md governs)")
        sp.add_argument("--out", help="analytics root override (default <project>/analytics); tests use the scratchpad")
        return sp

    s = common(sub.add_parser("init"))
    s.add_argument("--channel-id")
    s.add_argument("--name")
    s.add_argument("--handle")
    s.add_argument("--key", help="short key for the token file name (default: the folder name)")
    s.add_argument("--adapter", choices=("gems", "astro", "otto", "ancestral", "anime", "clips", "generic"))
    s.add_argument("--content", choices=("long", "shorts", "mixed"))

    s = common(sub.add_parser("auth"))
    s.add_argument("--client", help="client_secret.json path (default: the clipping publishers' OAuth client)")
    s.add_argument("--manual", action="store_true", help="print the consent URL instead of opening a browser")
    s.add_argument("--monetary", action="store_true", help="also ask for the revenue scope")

    common(sub.add_parser("whoami"))

    s = common(sub.add_parser("pull"))
    s.add_argument("--since", help="channel-wide series start (default: the first upload)")
    s.add_argument("--videos", help="comma-separated video ids to limit the pull")
    s.add_argument("--date", help="snapshot folder name (default: today)")
    s.add_argument("--lag", type=int, default=3, help="days to cut off the end for YouTube's processing lag (default 3)")
    s.add_argument("--refresh", action="store_true", help="re-fetch everything in the snapshot")
    s.add_argument("--dry-run", action="store_true", help="print the planned queries; no network, no token")

    s = common(sub.add_parser("studio"))
    s.add_argument("files", nargs="+", help="Studio export CSV or zip files")
    s.add_argument("--video", help="video id for a retention-curve CSV that does not carry one in its name")
    s.add_argument("--from", dest="date_from")
    s.add_argument("--to", dest="date_to")

    s = common(sub.add_parser("heatmap"))
    s.add_argument("urls", nargs="+")

    s = common(sub.add_parser("cuts"))
    s.add_argument("file")
    s.add_argument("--video", required=True, help="the YouTube video id the file was uploaded as")

    common(sub.add_parser("map"))

    s = common(sub.add_parser("join"))
    s.add_argument("--video", help="one video id")
    s.add_argument("--episode", help="one episode folder, without a catalogue (writes join/<slug>.json)")

    s = common(sub.add_parser("retention"))
    s.add_argument("--video")
    s.add_argument("--curve", help="a curve JSON [{ratio, abs, rel}] to use instead of the pull (tests, Studio)")
    s.add_argument("--charts", action="store_true")

    s = common(sub.add_parser("analyse"))
    s.add_argument("--min-age", type=int, default=7)
    s.add_argument("--noise-floor", type=int, default=300)
    s.add_argument("--hit-ratio", type=float, default=2.0)

    s = common(sub.add_parser("report"))
    s.add_argument("--file", help="output path (default <project>/WHAT WORKS.txt)")

    s = common(sub.add_parser("rules"))
    s.add_argument("action", choices=("list", "propose", "decide", "retest"))
    s.add_argument("--id")
    s.add_argument("--decision", choices=("apply", "changes", "skip", "ask_again"))
    s.add_argument("--wording", help="the rule in the user's words (verbatim)")
    s.add_argument("--edit", help="the gate or template change made for it")
    s.add_argument("--videos", help="the videos the rule came from")
    s.add_argument("--rule", help="add a rule that was not a candidate")
    s.add_argument("--evidence")
    s.add_argument("--tier")
    s.add_argument("--claude-md", help="CLAUDE.md to append to (default <project>/CLAUDE.md)")
    s.add_argument("--house", action="store_true", help="also append to channel-pipeline's house-rules.md")

    s = common(sub.add_parser("run"))
    s.add_argument("--min-age", type=int, default=7)
    s.add_argument("--noise-floor", type=int, default=300)
    s.add_argument("--hit-ratio", type=float, default=2.0)
    return p


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    if args.cmd == "init":
        from .config import cmd_init; cmd_init(args)
    elif args.cmd == "auth":
        from .auth import cmd_auth; cmd_auth(args)
    elif args.cmd == "whoami":
        from .auth import cmd_whoami; cmd_whoami(args)
    elif args.cmd == "pull":
        from .pull import cmd_pull; cmd_pull(args)
    elif args.cmd == "studio":
        from .studio import cmd_studio; cmd_studio(args)
    elif args.cmd == "heatmap":
        from .heatmap import cmd_heatmap; cmd_heatmap(args)
    elif args.cmd == "cuts":
        from .cuts import cmd_cuts; cmd_cuts(args)
    elif args.cmd == "map":
        from .mapping import cmd_map; cmd_map(args)
    elif args.cmd == "join":
        from .mapping import cmd_join; cmd_join(args)
    elif args.cmd == "retention":
        from .retention import cmd_retention; cmd_retention(args)
    elif args.cmd == "analyse":
        from .analyse import cmd_analyse; cmd_analyse(args)
    elif args.cmd == "report":
        from .report import cmd_report; cmd_report(args)
    elif args.cmd == "rules":
        from .rules import cmd_rules; cmd_rules(args)
    elif args.cmd == "run":
        from .mapping import cmd_join, cmd_map
        from .retention import cmd_retention
        from .analyse import cmd_analyse
        cmd_map(args)
        args.video = None; args.episode = None
        cmd_join(args)
        args.curve = None; args.charts = True
        cmd_retention(args)
        cmd_analyse(args)
    else:
        sys.exit(f"unknown command {args.cmd}")
