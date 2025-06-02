#!/bin/bash
# cake-create-pr.sh - Create PR with full conversation context after successful linting
# This script integrates with claude-conversation-extractor to capture discussion context

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TODAY=$(date +%Y-%m-%d)
VENV_PATH="$PROJECT_ROOT/.venv"

# Helper functions
print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_status() {
    echo -e "${BLUE}[PR-GEN]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    print_error "Not in a git repository"
    exit 1
fi

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
    print_error "Cannot create PR from main/master branch"
    print_status "Please create a feature branch first"
    exit 1
fi

print_header "CAKE PR Generator with Conversation Context"
print_status "Current branch: $CURRENT_BRANCH"

# Step 1: Verify lint status
print_status "Checking lint status..."
if [ ! -f "$PROJECT_ROOT/.cake/lint-status" ]; then
    print_error "No lint status found. Run cake-lint.sh first"
    exit 1
fi

LINT_STATUS=$(cat "$PROJECT_ROOT/.cake/lint-status")
if [[ ! "$LINT_STATUS" =~ "✅ All checks passed" ]]; then
    print_error "Lint checks have not passed"
    print_status "Run: ./scripts/cake-lint.sh"
    exit 1
fi
print_success "Lint checks passed"

# Step 2: Verify handoff document exists
print_status "Checking for today's handoff document..."
HANDOFF_COUNT=$(find "$PROJECT_ROOT/docs/handoff" -name "${TODAY}-*.md" -type f 2>/dev/null | wc -l)
if [ "$HANDOFF_COUNT" -eq 0 ]; then
    print_error "No handoff document found for today ($TODAY)"
    print_status "Run: ./scripts/cake-handoff.sh"
    exit 1
fi
HANDOFF_FILE=$(find "$PROJECT_ROOT/docs/handoff" -name "${TODAY}-*.md" -type f 2>/dev/null | sort | tail -1)
print_success "Found handoff: $(basename "$HANDOFF_FILE")"

# Step 3: Verify task log updated
print_status "Checking task log updates..."
TASK_LOG="$PROJECT_ROOT/docs/task_log.md"
if [ ! -f "$TASK_LOG" ]; then
    print_error "Task log not found at $TASK_LOG"
    exit 1
fi

# Check if task log was modified today
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    TASK_LOG_MODIFIED=$(stat -f "%Sm" -t "%Y-%m-%d" "$TASK_LOG")
else
    # Linux
    TASK_LOG_MODIFIED=$(date -r "$TASK_LOG" "+%Y-%m-%d")
fi

if [ "$TASK_LOG_MODIFIED" != "$TODAY" ]; then
    print_warning "Task log was last modified on $TASK_LOG_MODIFIED (not today)"
    print_status "Please update the task log before creating PR"
    exit 1
fi
print_success "Task log updated today"

# Step 4: Use existing conversation context from handoff
print_status "Loading conversation context..."

CONTEXT_JSON="$PROJECT_ROOT/.cake/conversation-context/conversation-${TODAY}.json"
CONVERSATION_SUMMARY="No conversation context available"
DECISIONS_SUMMARY=""
PROBLEMS_SUMMARY=""

if [ -f "$CONTEXT_JSON" ]; then
    print_success "Found conversation context from handoff generation"
    
    # Extract summaries from JSON
    TASKS_SUMMARY=$(python3 -c "
import json
data = json.load(open('$CONTEXT_JSON'))
tasks = data.get('tasks_discussed', [])[:5]
if tasks:
    print('### Tasks Discussed\\n' + '\\n'.join(['- ' + t for t in tasks]))
" 2>/dev/null || echo "")
    
    DECISIONS_SUMMARY=$(python3 -c "
import json
data = json.load(open('$CONTEXT_JSON'))
decisions = data.get('decisions_made', [])[:5]
if decisions:
    print('### Key Decisions\\n' + '\\n'.join(['- ' + d for d in decisions]))
" 2>/dev/null || echo "")
    
    PROBLEMS_SUMMARY=$(python3 -c "
import json
data = json.load(open('$CONTEXT_JSON'))
problems = data.get('problems_solved', [])[:5]
if problems:
    print('### Problems Solved\\n' + '\\n'.join(['- ' + p for p in problems]))
" 2>/dev/null || echo "")
    
    # Combine summaries
    CONVERSATION_SUMMARY="${TASKS_SUMMARY}

${DECISIONS_SUMMARY}

${PROBLEMS_SUMMARY}"
else
    print_warning "No conversation context found. Run cake-handoff.sh first to extract context."
fi

# Step 5: Generate PR description
print_status "Generating PR description..."

# Get commit summary
COMMITS_SUMMARY=$(git log origin/main..HEAD --oneline 2>/dev/null || echo "No commits yet")
COMMITS_COUNT=$(echo "$COMMITS_SUMMARY" | wc -l | tr -d ' ')

# Get changed files summary
CHANGED_FILES=$(git diff origin/main...HEAD --name-status 2>/dev/null || git diff --cached --name-status)
FILES_COUNT=$(echo "$CHANGED_FILES" | wc -l | tr -d ' ')

# Create PR body with full context
PR_BODY=$(cat <<EOF
## Summary
This PR contains $COMMITS_COUNT commits affecting $FILES_COUNT files, developed through pair programming with Claude.

## Conversation Context

$CONVERSATION_SUMMARY

## Changes Made

### Commits
\`\`\`
$COMMITS_SUMMARY
\`\`\`

### Files Changed
\`\`\`
$CHANGED_FILES
\`\`\`

## Validation
- ✅ All lint checks passed
- ✅ Task log updated  
- ✅ Handoff document created
- ✅ Conversation context captured

## Documentation
- **Handoff Document**: [$(basename "$HANDOFF_FILE")]($(echo "$HANDOFF_FILE" | sed "s|$PROJECT_ROOT/||"))
- **Task Log**: [View updates]($(echo "$TASK_LOG" | sed "s|$PROJECT_ROOT/||"))
- **Conversation Context**: [Full context]($(echo "$CONTEXT_JSON" | sed "s|$PROJECT_ROOT/||"))
- **Lint Status**: All checks passed at $(date -r "$PROJECT_ROOT/.cake/lint-status" "+%Y-%m-%d %H:%M" 2>/dev/null || echo "unknown time")

## Review Notes
The handoff document contains:
- Complete conversation context with tasks discussed and decisions made
- Full project status at time of PR creation
- Detailed file changes and git history
- Links to conversation logs for full traceability

## CI Failure Handling
If CI fails on this PR, run:
\`\`\`bash
./scripts/cake-fix-ci.sh        # Attempt automatic fixes
./scripts/cake-fix-ci.sh --monitor  # Fix and monitor status
\`\`\`

This will:
- Analyze CI failures
- Apply automatic fixes where possible
- Update this PR with fix details
- Save detailed logs for manual fixes

---
*Generated by cake-create-pr.sh on $(date)*
*Context extracted using claude-conversation-extractor*
EOF
)

# Step 6: Create the PR
print_status "Creating pull request..."

# Ensure we have the latest from origin
git fetch origin main --quiet

# Check if there are any commits to push
if ! git log origin/main..HEAD --oneline >/dev/null 2>&1; then
    print_error "No commits to create PR from"
    print_status "Make sure you have committed your changes"
    exit 1
fi

# Push the current branch if needed
if ! git push -u origin "$CURRENT_BRANCH" 2>/dev/null; then
    print_warning "Branch already pushed or push failed"
fi

# Create PR using gh CLI
PR_TITLE="feat: $(git log -1 --pretty=%s)"
print_status "Creating PR with title: $PR_TITLE"

# Save PR body to temp file (gh has issues with heredocs sometimes)
PR_BODY_FILE=$(mktemp)
echo "$PR_BODY" > "$PR_BODY_FILE"

if gh pr create \
    --title "$PR_TITLE" \
    --body-file "$PR_BODY_FILE" \
    --base main \
    --head "$CURRENT_BRANCH"; then
    print_success "Pull request created successfully!"
    
    # Clean up temp file
    rm -f "$PR_BODY_FILE"
    
    # Show PR URL
    PR_URL=$(gh pr view --json url -q .url)
    print_status "PR URL: $PR_URL"
else
    print_error "Failed to create pull request"
    rm -f "$PR_BODY_FILE"
    exit 1
fi

print_header "PR Creation Complete"
print_success "Successfully created PR with conversation context"
print_status "Next steps:"
echo "  1. Review the PR at: $PR_URL"
echo "  2. Request reviews as needed"
echo "  3. Merge when CI passes"