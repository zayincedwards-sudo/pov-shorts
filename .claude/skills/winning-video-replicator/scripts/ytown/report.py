"""WHAT WORKS.txt: the one-page report for the user, plain text at the project root.

The session writes analytics/findings.json first (its judgement in words):
  {"lead": "...", "findings": [{"rule", "numbers", "videos", "action"}], "tests": [...], "limits": [...]}
This command formats it (CRLF, no markdown) and appends the scoreboard from analysis.json. With
no findings.json it writes a draft from the candidate list so the user always has a page.
"""
from __future__ import annotations

from pathlib import Path

from .analyse import SCORE_HEADERS, scoreboard_rows
from .config import load_channel
from .util import TODAY, heading, jload, table, winpath, write_txt


def cmd_report(args) -> None:
    project = winpath(args.project).resolve()
    cfg = load_channel(project, args.out)
    root = Path(cfg["root"])
    analysis = jload(root / "analysis.json", {}) or {}
    findings = jload(root / "findings.json", {}) or {}
    recs = analysis.get("videos", [])
    lines = [heading(f"WHAT WORKS ON {str(cfg.get('name') or 'THIS CHANNEL').upper()}"),
             f"Data to {analysis.get('data_date', '?')}, written {TODAY}. {len(recs)} videos, "
             f"{sum(1 for r in recs if r.get('eligible'))} old enough to count, {sum(1 for r in recs if r.get('hit'))} hits.", ""]
    if findings.get("lead"):
        lines += [findings["lead"], ""]
    fl = findings.get("findings") or []
    if fl:
        lines.append(heading("THE FINDINGS", "-"))
        for i, f in enumerate(fl, 1):
            lines += [f"{i}. {f.get('rule', '')}", f"   Numbers: {f.get('numbers', '')}", f"   Videos: {f.get('videos', '')}", f"   What to do: {f.get('action', '')}", ""]
    else:
        cands = analysis.get("candidates", [])
        lines.append(heading("CANDIDATE FINDINGS (draft, nothing decided)", "-"))
        for c in cands[:10]:
            lines += [f"- [{c['tier']}] {c['plain']}", f"  {c['evidence']}", ""]
    if findings.get("tests"):
        lines.append(heading("WHAT TO TEST NEXT", "-"))
        lines += [f"- {t}" for t in findings["tests"]] + [""]
    if findings.get("limits"):
        lines.append(heading("WHAT THE DATA CANNOT TELL US YET", "-"))
        lines += [f"- {t}" for t in findings["limits"]] + [""]
    if recs:
        lines += [heading("SCOREBOARD", "-"), table(scoreboard_rows(recs), SCORE_HEADERS), "",
                  "views/day d7 = views in the first 7 days divided by 7. x neighbours = that figure against the median of the 3 uploads "
                  "either side. 30 s = share still watching at 30 seconds. avp = average percentage of the video watched."]
    out = winpath(args.file) if args.file else project / "WHAT WORKS.txt"
    write_txt(out, "\n".join(lines))
    print(f"written: {out}")
