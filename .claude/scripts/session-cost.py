#!/usr/bin/env python3
"""session-cost.py — efficiency report for this project's Claude sessions.

Reads two sources and joins them:
  * global   ~/.claude/metrics/costs.jsonl   (per-session cost + model, written by
             the cost-tracker Stop hook: {session_id, cwd, model, input_tokens,
             output_tokens, estimated_cost_usd})
  * local    .claude/metrics/token-ledger.jsonl (per-session SLICE attribution,
             written by record-token-spend.sh: {session, slice, in, out, ...})

Reports cost/session, output-tokens/session, model mix, and an efficiency verdict,
rolled up by session (default), slice, or model. See .claude/METRICS.md for the
metric definitions.

Usage:
  python3 .claude/scripts/session-cost.py [--by session|slice|model]
                                          [--all] [--since YYYY-MM-DD] [--json]

--all reports across every project in the global file; default filters to sessions
whose cwd is inside this project tree.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# List price per 1M tokens (USD) — fallback only, used when a row has no
# estimated_cost_usd. Keep in sync with record-token-spend.sh.
RATES = {
    "opus":   {"in": 15.00, "out": 75.00},
    "sonnet": {"in": 3.00,  "out": 15.00},
    "haiku":  {"in": 1.00,  "out": 5.00},
}


def tier(model: str) -> str:
    m = (model or "").lower()
    for t in ("opus", "sonnet", "haiku"):
        if t in m:
            return t
    return "unknown"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def est_cost(row: dict) -> float:
    c = row.get("estimated_cost_usd")
    if c:
        return float(c)
    r = RATES.get(tier(row.get("model", "")))
    if not r:
        return 0.0
    return (row.get("input_tokens", 0) * r["in"]
            + row.get("output_tokens", 0) * r["out"]) / 1_000_000


def verdict(share_opus: float, cost_per_session: float, out_per_session: int) -> str:
    """Cheap heuristic — flags the two failure modes we actually see."""
    if share_opus >= 0.80 and cost_per_session >= 45:
        return "OVERSPEND (mostly Opus — tier lighter agents to Sonnet/Haiku)"
    if share_opus == 0.0 and out_per_session >= 80_000:
        return "UNDER-RESOURCED (heavy output with no Opus — check quality)"
    return "OK"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--by", choices=("session", "slice", "model"), default="session")
    ap.add_argument("--all", action="store_true", help="all projects, not just this one")
    ap.add_argument("--since", help="ISO date lower bound, e.g. 2026-06-01")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--costs", default=os.path.expanduser("~/.claude/metrics/costs.jsonl"))
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    proj_name = project_root.name

    global_rows = read_jsonl(Path(args.costs))
    ledger = read_jsonl(project_root / ".claude" / "metrics" / "token-ledger.jsonl")
    slice_of = {r.get("session"): r.get("slice", "no-slice") for r in ledger}

    def keep(r: dict) -> bool:
        if args.since and str(r.get("timestamp", "")) < args.since:
            return False
        if args.all:
            return True
        return proj_name in (r.get("cwd") or "")

    rows = [r for r in global_rows if keep(r)]
    if not rows:
        msg = f"No session data for '{proj_name}' in {args.costs}."
        print(json.dumps({"error": msg}) if args.json else msg)
        return 0

    # group key
    def key(r: dict) -> str:
        if args.by == "slice":
            return slice_of.get(r.get("session_id"), "no-slice")
        if args.by == "model":
            return tier(r.get("model", ""))
        return r.get("session_id", "?")

    agg = defaultdict(lambda: {"cost": 0.0, "in": 0, "out": 0,
                               "sessions": set(), "tier": defaultdict(int)})
    for r in rows:
        a = agg[key(r)]
        a["cost"] += est_cost(r)
        a["in"] += r.get("input_tokens", 0)
        a["out"] += r.get("output_tokens", 0)
        a["sessions"].add(r.get("session_id"))
        a["tier"][tier(r.get("model", ""))] += 1

    report = []
    for k, a in sorted(agg.items(), key=lambda kv: -kv[1]["cost"]):
        n = max(len(a["sessions"]), 1)
        total_tier = sum(a["tier"].values()) or 1
        share_opus = a["tier"].get("opus", 0) / total_tier
        rec = {
            "key": k,
            "sessions": len(a["sessions"]),
            "cost_usd": round(a["cost"], 2),
            "cost_per_session": round(a["cost"] / n, 2),
            "out_tokens": a["out"],
            "out_per_session": a["out"] // n,
            "model_mix": {t: round(c / total_tier, 2) for t, c in a["tier"].items()},
            "verdict": verdict(share_opus, a["cost"] / n, a["out"] // n),
        }
        report.append(rec)

    if args.json:
        print(json.dumps({"project": proj_name, "by": args.by, "rows": report}, indent=2))
        return 0

    print(f"Efficiency report — {proj_name} (by {args.by})")
    print(f"{'key':<28} {'sess':>4} {'$total':>8} {'$/sess':>7} {'out/sess':>9}  mix / verdict")
    for r in report:
        mix = " ".join(f"{t}:{p:.0%}" for t, p in r["model_mix"].items())
        print(f"{r['key'][:28]:<28} {r['sessions']:>4} {r['cost_usd']:>8.2f} "
              f"{r['cost_per_session']:>7.2f} {r['out_per_session']:>9}  {mix}")
        if r["verdict"] != "OK":
            print(f"{'':<28} -> {r['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
