#!/bin/bash
# cake-status.sh - Comprehensive status checker for CAKE workflow
# Shows current state of branch, PR, CI, and provides next actions

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TODAY=$(date +%Y-%m-%d)

# Helper functions
print_header() {
    echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_section() {
    echo -e "\n${BLUE}▶ $1${NC}"
}

status_icon() {
    case "$1" in
        "success"|"passed") echo -e "${GREEN}✓${NC}" ;;
        "failure"|"failed") echo -e "${RED}✗${NC}" ;;
        "pending"|"running") echo -e "${YELLOW}⟳${NC}" ;;
        *) echo -e "${BLUE}•${NC}" ;;
    esac
}

print_header "CAKE Workflow Status"
echo -e "Generated: $(date '+%Y-%m-%d %H:%M:%S')"

# 1. Git Status
print_section "Git Repository"
BRANCH=$(git branch --show-current)
COMMITS_AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "0")
UNCOMMITTED=$(git status --porcelain | wc -l | tr -d ' ')

echo "  Branch: ${CYAN}$BRANCH${NC}"
echo "  Commits ahead of main: $COMMITS_AHEAD"
echo "  Uncommitted changes: $UNCOMMITTED"

# 2. Lint Status
print_section "Code Quality"
if [ -f "$PROJECT_ROOT/.cake/lint-status" ]; then
    LINT_STATUS=$(cat "$PROJECT_ROOT/.cake/lint-status")
    LINT_TIME=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$PROJECT_ROOT/.cake/lint-status" 2>/dev/null || echo "unknown")
    echo "  $(status_icon "passed") Lint: $LINT_STATUS"
    echo "    Last run: $LINT_TIME"
else
    echo "  $(status_icon "pending") Lint: Not run yet"
fi

# 3. Documentation Status
print_section "Documentation"
HANDOFF_TODAY=$(find "$PROJECT_ROOT/docs/handoff" -name "${TODAY}-*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
TASK_LOG_UPDATED="No"
if [ -f "$PROJECT_ROOT/docs/task_log.md" ]; then
    if grep -q "$TODAY" "$PROJECT_ROOT/docs/task_log.md"; then
        TASK_LOG_UPDATED="Yes"
    fi
fi

echo "  Handoff documents today: $HANDOFF_TODAY"
echo "  Task log updated today: $TASK_LOG_UPDATED"

CONTEXT_EXISTS="No"
if [ -f "$PROJECT_ROOT/.cake/conversation-context/conversation-${TODAY}.json" ]; then
    CONTEXT_EXISTS="Yes"
fi
echo "  Conversation context extracted: $CONTEXT_EXISTS"

# 4. PR Status
print_section "Pull Request"
PR_INFO=$(gh pr view --json number,url,state,isDraft,statusCheckRollup,reviews 2>/dev/null || echo "")

if [ -z "$PR_INFO" ]; then
    echo "  $(status_icon "") No PR for current branch"
else
    PR_NUMBER=$(echo "$PR_INFO" | jq -r '.number')
    PR_URL=$(echo "$PR_INFO" | jq -r '.url')
    PR_STATE=$(echo "$PR_INFO" | jq -r '.state')
    PR_DRAFT=$(echo "$PR_INFO" | jq -r '.isDraft')
    
    echo "  PR #$PR_NUMBER: ${CYAN}$PR_STATE${NC}"
    echo "  URL: $PR_URL"
    echo "  Draft: $PR_DRAFT"
    
    # Review status
    REVIEWS=$(echo "$PR_INFO" | jq -r '.reviews | length' 2>/dev/null || echo "0")
    echo "  Reviews: $REVIEWS"
fi

# 5. CI Status
print_section "CI/CD Status"
if [ -n "$PR_INFO" ]; then
    # Get CI checks from PR
    CI_CHECKS=$(echo "$PR_INFO" | jq -r '.statusCheckRollup[]' 2>/dev/null || echo "")
    
    if [ -n "$CI_CHECKS" ]; then
        echo "$CI_CHECKS" | jq -r '. | "  \(.name): \(.conclusion // .status)"' | while read -r line; do
            CHECK_NAME=$(echo "$line" | cut -d: -f1 | xargs)
            CHECK_STATUS=$(echo "$line" | cut -d: -f2 | xargs)
            echo "  $(status_icon "$CHECK_STATUS") $CHECK_NAME: $CHECK_STATUS"
        done
    else
        echo "  $(status_icon "pending") No CI checks found"
    fi
else
    # Check recent workflow runs
    RECENT_RUN=$(gh run list --limit 1 --json conclusion,status,name,headBranch | jq -r '.[] | select(.headBranch == "'$BRANCH'")')
    
    if [ -n "$RECENT_RUN" ]; then
        RUN_NAME=$(echo "$RECENT_RUN" | jq -r '.name')
        RUN_STATUS=$(echo "$RECENT_RUN" | jq -r '.status')
        RUN_CONCLUSION=$(echo "$RECENT_RUN" | jq -r '.conclusion // "pending"')
        
        echo "  $(status_icon "$RUN_CONCLUSION") Last run: $RUN_NAME"
        echo "    Status: $RUN_STATUS / $RUN_CONCLUSION"
    else
        echo "  No CI runs for this branch"
    fi
fi

# 6. Suggested Actions
print_section "Suggested Next Actions"

SUGGESTIONS=()

# Check uncommitted changes
if [ "$UNCOMMITTED" -gt 0 ]; then
    SUGGESTIONS+=("You have uncommitted changes. Run: ${CYAN}git add -A && git commit${NC}")
fi

# Check lint status
if [ ! -f "$PROJECT_ROOT/.cake/lint-status" ] || [ "$UNCOMMITTED" -gt 0 ]; then
    SUGGESTIONS+=("Run linting: ${CYAN}./scripts/cake-lint.sh${NC}")
fi

# Check documentation
if [ "$HANDOFF_TODAY" -eq 0 ] || [ "$TASK_LOG_UPDATED" = "No" ]; then
    SUGGESTIONS+=("Generate documentation: ${CYAN}./scripts/cake-lint.sh --handoff${NC}")
fi

# Check PR status
if [ -z "$PR_INFO" ] && [ "$COMMITS_AHEAD" -gt 0 ]; then
    SUGGESTIONS+=("Create PR: ${CYAN}./scripts/cake-lint.sh --create-pr${NC}")
elif [ -n "$PR_INFO" ]; then
    # Check CI status
    if echo "$CI_CHECKS" | grep -q "failure\|failed"; then
        SUGGESTIONS+=("CI has failures. Run: ${CYAN}./scripts/cake-fix-ci.sh${NC}")
    elif [ "$PR_STATE" = "OPEN" ] && [ "$REVIEWS" -eq 0 ]; then
        SUGGESTIONS+=("PR is ready for review. Request reviews on GitHub.")
    fi
fi

# Display suggestions
if [ ${#SUGGESTIONS[@]} -eq 0 ]; then
    echo -e "  ${GREEN}✓${NC} Everything looks good! No immediate actions needed."
else
    for i in "${!SUGGESTIONS[@]}"; do
        echo -e "  $((i+1)). ${SUGGESTIONS[$i]}"
    done
fi

# 7. Quick Commands
print_section "Quick Commands"
echo "  Full workflow:     ${CYAN}./scripts/cake-lint.sh --create-pr${NC}"
echo "  Fix CI:           ${CYAN}./scripts/cake-fix-ci.sh --monitor${NC}"
echo "  Check status:     ${CYAN}./scripts/cake-status.sh${NC}"
echo "  View PR:          ${CYAN}gh pr view --web${NC}"

# 8. Workflow Health
print_section "Workflow Health"
HEALTH_SCORE=100
HEALTH_ISSUES=()

# Check for various health indicators
if [ "$UNCOMMITTED" -gt 10 ]; then
    HEALTH_SCORE=$((HEALTH_SCORE - 10))
    HEALTH_ISSUES+=("Too many uncommitted files ($UNCOMMITTED)")
fi

if [ "$COMMITS_AHEAD" -gt 20 ]; then
    HEALTH_SCORE=$((HEALTH_SCORE - 10))
    HEALTH_ISSUES+=("Too many commits ahead ($COMMITS_AHEAD) - consider creating PR")
fi

if [ -f "$PROJECT_ROOT/.cake/lint-status" ]; then
    LINT_AGE_HOURS=$(( ($(date +%s) - $(stat -f %m "$PROJECT_ROOT/.cake/lint-status")) / 3600 ))
    if [ "$LINT_AGE_HOURS" -gt 24 ]; then
        HEALTH_SCORE=$((HEALTH_SCORE - 15))
        HEALTH_ISSUES+=("Lint status is ${LINT_AGE_HOURS}h old")
    fi
fi

# Display health
if [ "$HEALTH_SCORE" -ge 90 ]; then
    echo -e "  Overall: ${GREEN}Excellent${NC} ($HEALTH_SCORE/100)"
elif [ "$HEALTH_SCORE" -ge 70 ]; then
    echo -e "  Overall: ${YELLOW}Good${NC} ($HEALTH_SCORE/100)"
else
    echo -e "  Overall: ${RED}Needs Attention${NC} ($HEALTH_SCORE/100)"
fi

if [ ${#HEALTH_ISSUES[@]} -gt 0 ]; then
    echo "  Issues:"
    for issue in "${HEALTH_ISSUES[@]}"; do
        echo "    - $issue"
    done
fi

echo # Empty line at end