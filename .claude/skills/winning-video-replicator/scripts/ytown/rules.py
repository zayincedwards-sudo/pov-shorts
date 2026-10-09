"""Rules the user accepted, and their re-tests: analytics/rules.json plus the CLAUDE.md bullets.

The user decides every rule (6 Oct 2026: "put me in charge of committing everything"). The
session walks the candidates through AskUserQuestion; this module only records the decision
and writes the bullet, in the house format:
  - YYYY-MM-DD · <videos> · **rule** · Why: <evidence> · Edit: <gate or template change>
under `## Rules learned from our own channel analytics` in the project's CLAUDE.md (created at
the end of the file when missing), or under `## Reviewed and rejected` for a skip. With --house
the bullet also goes to channel-pipeline's house-rules.md under `## From our own analytics`.
`retest` re-reads the latest analysis.json and marks each applied rule holds / weakened /
contradicted, so a rule the numbers stop supporting is flagged, never silently kept.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from .config import load_channel
from .util import TODAY, jload, jsave, winpath

SECTION = "## Rules learned from our own channel analytics"
SECTION_INTRO = ("Appended by the winning-video-replicator skill after the user's own decision on each rule. One bullet per rule: "
                 "date · the videos · the rule · why (metric and numbers) · the edit or gate. Future videos only.")
REJECTED = "## Reviewed and rejected"
REJECTED_INTRO = "Proposed and refused by the user. Do not propose these again unless the numbers change."
HOUSE = Path("C:/Users/admin/.claude/skills/channel-pipeline/references/house-rules.md")
HOUSE_SECTION = "## From our own analytics"


def _rules_path(root: Path) -> Path:
    return root / "rules.json"


def _rid(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def append_under(md: Path, section: str, intro: str, bullet: str) -> None:
    text = md.read_text(encoding="utf-8") if md.exists() else ""
    nl = "\r\n" if "\r\n" in text else "\n"
    body = text.replace("\r\n", "\n")
    if section not in body:
        if body and not body.endswith("\n"):
            body += "\n"
        body += f"\n{section}\n{intro}\n"
    head, _, tail = body.partition(section)
    # insert the bullet at the end of this section (before the next "## " heading, if any)
    lines = tail.split("\n")
    end = len(lines)
    for i, ln in enumerate(lines[1:], 1):
        if ln.startswith("## "):
            end = i
            break
    while end > 0 and lines[end - 1].strip() == "":
        end -= 1
    lines.insert(end, bullet)
    if end + 1 < len(lines) and lines[end + 1].startswith("## "):
        lines.insert(end + 1, "")
    body = head + section + "\n".join(lines)
    md.write_text(body.replace("\n", nl), encoding="utf-8")


def cmd_rules(args) -> None:
    project = winpath(args.project).resolve()
    cfg = load_channel(project, args.out)
    root = Path(cfg["root"])
    rules = jload(_rules_path(root), []) or []
    if args.action == "list":
        if not rules:
            print("no rules recorded yet")
        for r in rules:
            dec = (r.get("decisions") or [{}])[-1]
            stat = (r.get("status") or [{}])[-1]
            print(f"  {r['id']}  {dec.get('decision', 'proposed'):9} {stat.get('status', '-'):12} {r['rule'][:90]}")
        return
    if args.action == "propose":
        cands = jload(root / "candidates.json", []) or []
        known = {r["candidate_id"] for r in rules if r.get("candidate_id")}
        n = 0
        for c in cands:
            if c["id"] in known:
                continue
            rules.append({"id": _rid(c["id"]), "candidate_id": c["id"], "rule": c["plain"], "evidence": c["evidence"], "tier": c["tier"],
                          "attribute": c["attribute"], "outcome": c["outcome"], "direction": c["direction"], "proposed": TODAY,
                          "decisions": [], "status": []})
            n += 1
        jsave(_rules_path(root), rules)
        print(f"{n} new candidates recorded as proposed ({len(rules)} rules in rules.json); walk them with AskUserQuestion, then `rules decide`")
        return
    if args.action == "decide":
        r = next((x for x in rules if x["id"] == args.id), None)
        if not r and args.rule:
            r = {"id": _rid(args.rule + TODAY), "candidate_id": None, "rule": args.rule, "evidence": args.evidence or "", "tier": args.tier or "USER",
                 "attribute": None, "outcome": None, "direction": None, "proposed": TODAY, "decisions": [], "status": []}
            rules.append(r)
        if not r:
            sys.exit(f"no rule {args.id}; `rules list` shows ids, or pass --rule to add one")
        wording = args.wording or r["rule"]
        r["decisions"].append({"date": TODAY, "decision": args.decision, "wording": wording, "edit": args.edit})
        md = winpath(args.claude_md) if args.claude_md else project / "CLAUDE.md"
        videos = args.videos or ""
        if args.decision in ("apply", "changes"):
            bullet = f"- {TODAY} · {videos or 'own-channel analytics'} · **{wording}** · Why: {r.get('evidence') or args.evidence or 'see analytics/ANALYTICS.md'} · Edit: {args.edit or 'rule only, no gate yet'}"
            append_under(md, SECTION, SECTION_INTRO, bullet)
            print(f"appended to {md}")
            if args.house:
                append_under(HOUSE, HOUSE_SECTION, "Rules the user accepted from their own channel analytics that apply to every channel.",
                             f"- {TODAY} · {cfg.get('name')} · **{wording}** · Why: {r.get('evidence') or ''}")
                print(f"appended to {HOUSE}")
        elif args.decision == "skip":
            append_under(md, REJECTED, REJECTED_INTRO, f"- {TODAY} · own-channel analytics · {wording} · why proposed: {r.get('evidence') or ''} · skipped by the user")
            print(f"recorded under {REJECTED} in {md}")
        else:
            print("recorded: ask again next run")
        jsave(_rules_path(root), rules)
        return
    if args.action == "retest":
        analysis = jload(root / "analysis.json", {}) or {}
        corr = {(c["attribute"], c["outcome"]): c for c in analysis.get("correlations", [])}
        pooled = {}
        for pool in ("beat_kind", "span_type", "section_kind", "boundary"):
            for row in (analysis.get("retention") or {}).get(pool, []):
                pooled[f"{pool}={row['key']}"] = row
        n = 0
        for r in rules:
            dec = (r.get("decisions") or [{}])[-1].get("decision")
            if dec not in ("apply", "changes"):
                continue
            status, numbers = "untestable", ""
            if r.get("outcome") == "retention" and r.get("attribute") in pooled:
                row = pooled[r["attribute"]]
                was_loss = r.get("direction") == "loses"
                now_loss = row["excess_pct_per_min"] > 0
                status = "holds" if (was_loss == now_loss and abs(row["excess_pct_per_min"]) >= 0.5) else \
                         "weakened" if was_loss == now_loss else "contradicted"
                numbers = f"{row['excess_pct_per_min']:+.2f} pts/min over {row['videos']} videos"
            elif (r.get("attribute"), r.get("outcome")) in corr:
                c = corr[(r["attribute"], r["outcome"])]
                sign_was = 1 if r.get("direction") == "higher" else -1
                sign_now = 1 if c["rho"] > 0 else -1
                status = "holds" if (sign_was == sign_now and abs(c["rho"]) >= 0.3) else "weakened" if sign_was == sign_now else "contradicted"
                numbers = f"rho {c['rho']:+.2f} over {c['n']} videos"
            r["status"].append({"date": TODAY, "status": status, "numbers": numbers, "data_date": analysis.get("data_date")})
            n += 1
            flag = "  <-- flag to the user" if status in ("weakened", "contradicted") else ""
            print(f"  {r['id']} {status:12} {numbers:34} {r['rule'][:70]}{flag}")
        jsave(_rules_path(root), rules)
        print(f"retested {n} applied rules against data to {analysis.get('data_date')}")
        return
    sys.exit(f"unknown rules action {args.action}")
