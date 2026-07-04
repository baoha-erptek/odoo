# Workflow Efficiency Metrics

How we measure whether a project's Claude Code workflow is *efficient*, not just
*working*. Run the reporter any time:

```bash
python3 .claude/scripts/session-cost.py            # this project, by session
python3 .claude/scripts/session-cost.py --by slice # cost per master-plan slice
python3 .claude/scripts/session-cost.py --by model # model mix + spend
python3 .claude/scripts/session-cost.py --all --json
```

Data sources it joins:
- `~/.claude/metrics/costs.jsonl` — per-session cost + model (global cost-tracker Stop hook).
- `.claude/metrics/token-ledger.jsonl` — per-session **slice** attribution (this project's
  `record-token-spend.sh` SessionEnd hook).

## The metric set

| Metric | Definition | Why it matters | Good direction |
|---|---|---|---|
| **Cost / session** | est. USD per session | Headline efficiency number | lower |
| **Cost / merged slice** | est. USD summed over the sessions that produced a landed slice | True unit economics of delivery | lower |
| **Model mix** | % of turns on Opus / Sonnet / Haiku | Tier discipline — the #1 cost lever | Opus reserved for planning/architecture |
| **Output tokens / session** | out tokens ÷ sessions | Verbosity / rework proxy | lower for equal output |
| **Cache-read ratio** | cache-read ÷ input tokens | Context reuse efficiency | higher |
| **Slices / session** | landed slices ÷ sessions | Throughput | higher |
| **Sessions / slice** | sessions ÷ landed slices | Focus (thrash indicator) | lower |
| **First-pass review rate** | slices passing `/code-review` with no CRITICAL/HIGH first time | Quality-at-source | higher |
| **Rework rate** | follow-up `fix:`/revert commits per slice | Correctness | lower |

The reporter computes the first four directly from usage data. Slices/session,
first-pass review rate, and rework rate need the master-plan tracker + git history
(count landed slices in `master-plan-tracking.md`, count `fix:` commits per slice).

## Efficiency verdict

`session-cost.py` prints a heuristic verdict per row:
- **OVERSPEND** — ≥80% Opus and ≥$45/session → tier lighter agents down to Sonnet/Haiku.
- **UNDER-RESOURCED** — no Opus at all but ≥80k out-tokens/session → check output quality.
- **OK** — otherwise.

## Baseline scorecard (2026-07, real data)

Measured across three sibling projects (`~/.claude/metrics/costs.jsonl`, 1030 sessions).
This is the worked example that motivated the template's model-tier defaults:

| Project | Sessions | $/session | out-tok/session | Model mix | Read |
|---|---|---|---|---|---|
| hr_project | 179 | **$29** | 65.5k | Opus + Sonnet + Haiku | Most efficient — tiers models AND measures it |
| openeducat_erp19 | 32 | **$69** | 120k | ~99% Opus | Most spec-disciplined, least cost-disciplined (2.4× pricier) |
| odoo19_esty | 37 | **$25** | 50k | Opus + Sonnet | Cheapest; the template's ancestor |

**Takeaway baked into this template:** default agents to Sonnet, reserve Opus for
`planner`/`architect` (see `.claude/rules/common/performance.md`). The
`check-agent-model-tier.sh` hook keeps agents from silently drifting back to Opus.
