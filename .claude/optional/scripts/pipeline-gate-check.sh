#!/usr/bin/env bash
# pipeline-gate-check.sh - Check pipeline status and enforce gates
#
# Called by hooks:
#   - PreToolUse (Bash): git commit/push -> ACTION=commit|push
#   - Stop: session ending -> ACTION=stop
#   - SessionStart: session starting -> ACTION=session-start
#
# Reads pipeline-status.md for the current branch's JIRA ticket
# and outputs advisory warnings about incomplete pipeline phases.

set -euo pipefail

ACTION="${1:-}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASKS_DIR="$PROJECT_ROOT/.docs/tasks"

# Detect ticket from branch
BRANCH=$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
TICKET=$(echo "$BRANCH" | grep -oE 'NCNB-[0-9]+' || echo "")

if [ -z "$TICKET" ]; then
    exit 0
fi

PIPELINE_STATUS="$TASKS_DIR/$TICKET/pipeline-status.md"
PROGRESS_TRACKER="$TASKS_DIR/$TICKET/progress-tracker.md"

# Helper: extract phase status from pipeline-status.md
# Looks for phase name and extracts COMPLETE|PENDING|IN PROGRESS|N/A
get_phase_status() {
    local phase_name="$1"
    if [ ! -f "$PIPELINE_STATUS" ]; then
        echo "MISSING"
        return
    fi
    local status
    status=$(grep -i "Phase.*$phase_name" "$PIPELINE_STATUS" | grep -oiE '(COMPLETE|PENDING|IN.PROGRESS|N/A)' | head -1 || echo "")
    if [ -z "$status" ]; then
        # Try alternative format: "### Phase N: NAME - STATUS"
        status=$(grep -i "$phase_name" "$PIPELINE_STATUS" | grep -oiE '(COMPLETE|PENDING|IN.PROGRESS|N/A)' | head -1 || echo "UNKNOWN")
    fi
    echo "$status"
}

# Check if pipeline-status.md exists
has_pipeline() {
    [ -f "$PIPELINE_STATUS" ]
}

# Check if task directory exists but no pipeline
has_task_no_pipeline() {
    [ -d "$TASKS_DIR/$TICKET" ] && [ ! -f "$PIPELINE_STATUS" ]
}

case "$ACTION" in
    session-start)
        if has_pipeline; then
            echo "  Pipeline: $TICKET (active)"
            # Find first incomplete phase
            for phase in "SEARCH" "DECIDE" "ACT" "CLEANUP" "UPDATE"; do
                status=$(get_phase_status "$phase")
                case "$status" in
                    PENDING|IN*PROGRESS|UNKNOWN)
                        echo "  Next Phase: $phase ($status)"
                        case "$phase" in
                            SEARCH)
                                echo "  Action: /resolve $TICKET --phase search"
                                ;;
                            DECIDE)
                                echo "  Action: /resolve $TICKET --phase decide"
                                ;;
                            ACT)
                                echo "  Action: Review pipeline-status.md, then proceed to implementation"
                                echo "  GATE: Confirm plan + worktree before coding"
                                ;;
                            CLEANUP)
                                echo "  Action: /resolve $TICKET --phase cleanup"
                                ;;
                            UPDATE)
                                echo "  Action: /resolve $TICKET --phase update"
                                echo "  Includes: /learn, KB update, JIRA sync"
                                ;;
                        esac
                        break
                        ;;
                    COMPLETE|N/A)
                        continue
                        ;;
                esac
            done
        elif has_task_no_pipeline; then
            echo "  Task: $TICKET (no pipeline-status.md)"
            echo "  Tip: Use /resolve $TICKET for full pipeline workflow"
        fi
        ;;

    commit)
        if has_pipeline; then
            update_status=$(get_phase_status "UPDATE")
            act_status=$(get_phase_status "ACT")

            # If ACT is complete but UPDATE is not, remind about Phase 5
            if echo "$act_status" | grep -qiE "COMPLETE"; then
                if echo "$update_status" | grep -qiE "PENDING|IN.PROGRESS|UNKNOWN"; then
                    echo "[Pipeline] Phase 5 UPDATE is incomplete for $TICKET"
                    echo "  After committing, run: /resolve $TICKET --phase update"
                    echo "  Phase 5 captures: /learn, KB update, skill improvements, JIRA sync"
                fi
            fi

            # Warn if task exists but plan file is missing
            PLAN_FILE="$TASKS_DIR/$TICKET/${TICKET}-plan.md"
            if [ -d "$TASKS_DIR/$TICKET" ] && [ ! -f "$PLAN_FILE" ]; then
                echo "[Pipeline] No plan file for $TICKET"
                echo "  Consider: /plan to draft $PLAN_FILE before committing"
            fi
        elif [ -d "$TASKS_DIR/$TICKET" ]; then
            echo "[Pipeline] Task $TICKET exists but no pipeline-status.md"
            echo "  If using /resolve workflow, create pipeline first"
        fi
        ;;

    push)
        if has_pipeline; then
            update_status=$(get_phase_status "UPDATE")
            cleanup_status=$(get_phase_status "CLEANUP")

            if echo "$update_status" | grep -qiE "PENDING|IN.PROGRESS|UNKNOWN"; then
                echo "[Pipeline] Phase 5 UPDATE incomplete for $TICKET - run before or after push"
                echo "  /resolve $TICKET --phase update"
            fi
            if echo "$cleanup_status" | grep -qiE "PENDING|IN.PROGRESS|UNKNOWN"; then
                echo "[Pipeline] Phase 4 CLEANUP pending for $TICKET"
                echo "  /resolve $TICKET --phase cleanup"
            fi
        fi
        ;;

    stop)
        if has_pipeline; then
            incomplete=""
            for phase in "SEARCH" "DECIDE" "ACT" "CLEANUP" "UPDATE"; do
                status=$(get_phase_status "$phase")
                if echo "$status" | grep -qiE "PENDING|IN.PROGRESS|UNKNOWN"; then
                    incomplete="$incomplete $phase"
                fi
            done
            if [ -n "$incomplete" ]; then
                echo "[Pipeline] $TICKET has incomplete phases:$incomplete"
                echo "  Resume next session: /resolve $TICKET --resume"
            fi
        fi
        ;;

    *)
        echo "Usage: pipeline-gate-check.sh {session-start|commit|push|stop}"
        exit 1
        ;;
esac
