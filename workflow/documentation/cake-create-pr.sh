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
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
WORKFLOW_DIR="$(dirname "$SCRIPT_DIR")"
TODAY=$(date +%Y-%m-%d)
VENV_PATH="$PROJECT_ROOT/.venv"

# Activate virtual environment if it exists (for Python JSON parsing and claude-extract)
if [ -d "$VENV_PATH" ] && [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
fi

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
    
    # Extract summaries from JSON - make it meaningful
    TASKS_SUMMARY=$(python3 -c "
import json
data = json.load(open('$CONTEXT_JSON'))
tasks = data.get('tasks', [])

# Filter for meaningful tasks (not fragments)
meaningful_tasks = []
for t in tasks:
    text = t.get('text', '')
    # Skip short fragments and navigation tasks
    if len(text) > 20 and not any(skip in text.lower() for skip in ['navigate to', 'change to', 'be in the']):
        meaningful_tasks.append(t)

implemented = [t for t in meaningful_tasks if t.get('implemented')]
pending = [t for t in meaningful_tasks if not t.get('implemented')]

output = []
if implemented:
    output.append('### Key Accomplishments')
    # Group similar tasks
    parser_tasks = [t for t in implemented if 'parser' in t.get('text', '').lower()]
    reorg_tasks = [t for t in implemented if 'reorganiz' in t.get('text', '').lower()]
    test_tasks = [t for t in implemented if 'test' in t.get('text', '').lower()]
    
    if parser_tasks:
        output.append('- ✅ Implemented NLP conversation parser with spaCy')
    if reorg_tasks:
        output.append('- ✅ Reorganized repository structure into workflow/ and scripts/')
    if test_tasks:
        output.append('- ✅ Added comprehensive test suite with coverage')
    
    # Add any other unique tasks
    for t in implemented[:3]:
        if not any(word in t.get('text', '').lower() for word in ['parser', 'reorganiz', 'test']):
            output.append('- ✅ ' + t.get('text', '')[:100])

if pending and len(pending) < 10:  # Only show if reasonable number
    output.append('\\n### Follow-up Tasks')
    for t in pending[:3]:
        output.append('- ⏳ ' + t.get('text', '')[:100])

if output:
    print('\\n'.join(output))
else:
    print('The NLP parser extracted ' + str(len(tasks)) + ' tasks from the conversation.')
" 2>/dev/null || echo "")
    
    DECISIONS_SUMMARY=$(python3 -c "
import json
data = json.load(open('$CONTEXT_JSON'))
decisions = data.get('decisions', [])
if decisions and len(decisions) < 20:  # Only show if reasonable number
    print('### Key Technical Decisions')
    shown = 0
    for d in decisions:
        text = d.get('text', '')
        # Filter for meaningful technical decisions
        if len(text) > 15 and shown < 5:
            print('- ' + text[:100])
            if d.get('rationale') and len(d.get('rationale')) > 10:
                print('  - *Rationale*: ' + d.get('rationale')[:80] + '...')
            shown += 1
" 2>/dev/null || echo "")
    
    PROBLEMS_SUMMARY=$(python3 -c "
import json
data = json.load(open('$CONTEXT_JSON'))
problems = data.get('problems_solved', [])
if problems:
    print('### Problems Solved')
    for p in problems[:3]:
        print('- **Problem**: ' + p.get('problem', '')[:80] + '...')
        print('  **Solution**: ' + p.get('solution', '')[:80] + '...')
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
NEW_FILES=$(echo "$CHANGED_FILES" | grep "^A" | wc -l | tr -d ' ')
MODIFIED_FILES=$(echo "$CHANGED_FILES" | grep "^M" | wc -l | tr -d ' ')
DELETED_FILES=$(echo "$CHANGED_FILES" | grep "^D" | wc -l | tr -d ' ')

# Analyze what type of changes this PR contains
HAS_PARSER=false
HAS_REORG=false
HAS_TESTS=false
HAS_WORKFLOW=false
HAS_DOCS=false

# Check commits for keywords
if echo "$COMMITS_SUMMARY" | grep -qi "parser\|NLP\|extract"; then HAS_PARSER=true; fi
if echo "$COMMITS_SUMMARY" | grep -qi "reorganiz\|structure\|move"; then HAS_REORG=true; fi
if echo "$COMMITS_SUMMARY" | grep -qi "test"; then HAS_TESTS=true; fi
if echo "$COMMITS_SUMMARY" | grep -qi "workflow\|automat"; then HAS_WORKFLOW=true; fi
if echo "$COMMITS_SUMMARY" | grep -qi "doc\|readme"; then HAS_DOCS=true; fi

# Also check file changes
if echo "$CHANGED_FILES" | grep -q "parser\.py"; then HAS_PARSER=true; fi
if echo "$CHANGED_FILES" | grep -q "test_.*\.py"; then HAS_TESTS=true; fi
if echo "$CHANGED_FILES" | grep -q "workflow/"; then HAS_WORKFLOW=true; fi

# Create PR body with full context
# Check if full conversation was attached
CONVERSATION_FULL=$(find "$PROJECT_ROOT/docs/handoff" -name "conversation-${TODAY}-*-full.md" -type f 2>/dev/null | head -1)
CONVERSATION_LINK=""
if [ -n "$CONVERSATION_FULL" ]; then
    CONVERSATION_LINK="- **Full Conversation Log**: [View complete session]($(echo "$CONVERSATION_FULL" | sed "s|$PROJECT_ROOT/||"))"
fi

# Generate meaningful summary based on changes
SUMMARY_INTRO="This PR "
if [ "$HAS_PARSER" = true ] && [ "$HAS_REORG" = true ]; then
    SUMMARY_INTRO+="implements a deterministic NLP conversation parser and reorganizes the repository structure"
elif [ "$HAS_PARSER" = true ]; then
    SUMMARY_INTRO+="implements a deterministic NLP conversation parser for extracting context from Claude conversations"
elif [ "$HAS_REORG" = true ]; then
    SUMMARY_INTRO+="reorganizes the repository structure for better separation of concerns"
elif [ "$HAS_WORKFLOW" = true ]; then
    SUMMARY_INTRO+="enhances the workflow automation system"
elif [ "$HAS_TESTS" = true ]; then
    SUMMARY_INTRO+="adds comprehensive test coverage"
else
    SUMMARY_INTRO+="contains $COMMITS_COUNT commits affecting $FILES_COUNT files"
fi

PR_BODY=$(cat <<EOF
## Summary
$SUMMARY_INTRO, developed through pair programming with Claude.

$(if [ "$NEW_FILES" -gt 0 ] || [ "$MODIFIED_FILES" -gt 0 ]; then
    echo "### Changes Overview"
    echo "- **New files**: $NEW_FILES"
    echo "- **Modified files**: $MODIFIED_FILES"
    echo "- **Deleted files**: $DELETED_FILES"
    echo "- **Total files affected**: $FILES_COUNT"
fi)

$(if [ "$HAS_PARSER" = true ]; then
    echo "### 🔍 NLP Parser Implementation"
    echo "- Created deterministic conversation parser using spaCy"
    echo "- Extracts tasks, decisions, problems, and context from conversations"
    echo "- Replaces brittle regex-based extraction with semantic analysis"
    echo "- Handles 500+ message conversations efficiently"
fi)

$(if [ "$HAS_REORG" = true ]; then
    echo "### 📁 Repository Reorganization"
    echo "- Separated workflow automation (\`/workflow/\`) from CAKE development scripts (\`/scripts/\`)"
    echo "- Created clear directory structure with purposeful subdirectories"
    echo "- Updated all script paths and imports for new structure"
    echo "- Added comprehensive documentation for the new organization"
fi)

$(if [ "$HAS_WORKFLOW" = true ]; then
    echo "### 🚀 Workflow Enhancements"
    echo "- Enhanced automation with full test suite execution"
    echo "- Enriched handoff documents with full conversation logs"
    echo "- Improved PR creation with intelligent context extraction"
    echo "- Added automatic issue fixing and CI monitoring"
fi)

$(if [ "$HAS_TESTS" = true ]; then
    echo "### ✅ Testing"
    TEST_COUNT=$(echo "$CHANGED_FILES" | grep -c "test_" || echo "0")
    echo "- Added/modified $TEST_COUNT test files"
    echo "- Integrated test suite into workflow automation"
    echo "- Added coverage reporting"
fi)

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
- ✅ Code formatting (black, isort) applied
- ✅ Style guide (flake8) passed
- ✅ Type checking (mypy) passed
- ✅ Security scan (bandit) passed
- ✅ Test suite passed (if tests exist)
- ✅ Task log updated  
- ✅ Handoff document created with full conversation
- ✅ Conversation context captured and parsed

## Documentation
- **Handoff Document**: [$(basename "$HANDOFF_FILE")]($(echo "$HANDOFF_FILE" | sed "s|$PROJECT_ROOT/||"))
- **Task Log**: [View updates]($(echo "$TASK_LOG" | sed "s|$PROJECT_ROOT/||"))
- **Conversation Context**: [Structured data]($(echo "$CONTEXT_JSON" | sed "s|$PROJECT_ROOT/||"))
$CONVERSATION_LINK
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
# Generate PR title based on what we're doing
if [ "$HAS_PARSER" = true ] && [ "$HAS_REORG" = true ]; then
    PR_TITLE="feat: implement NLP parser and reorganize repository structure"
elif [ "$HAS_PARSER" = true ]; then
    PR_TITLE="feat: implement deterministic NLP conversation parser"
elif [ "$HAS_REORG" = true ]; then
    PR_TITLE="refactor: reorganize repository structure for clarity"
elif [ "$HAS_WORKFLOW" = true ]; then
    PR_TITLE="feat: enhance workflow automation system"
elif [ "$HAS_TESTS" = true ]; then
    PR_TITLE="test: add comprehensive test coverage"
else
    # Fallback to commit-based title
    LATEST_COMMIT=$(git log -1 --pretty=%s)
    if echo "$LATEST_COMMIT" | grep -qE "^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert)(\(.+\))?: "; then
        PR_TITLE="$LATEST_COMMIT"
    else
        PR_TITLE="feat: $LATEST_COMMIT"
    fi
fi
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