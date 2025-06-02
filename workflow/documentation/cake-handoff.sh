#!/bin/bash
# cake-handoff.sh - Auto-generate handoff document and update task log
# Usage: ./cake-handoff.sh [--auto]

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
WORKFLOW_DIR="$(dirname "$SCRIPT_DIR")"
DOCS_DIR="$PROJECT_ROOT/docs"
HANDOFF_DIR="$DOCS_DIR/handoff"
TASK_LOG="$DOCS_DIR/task_log.md"
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M)
HANDOFF_COUNT=1
VENV_PATH="$PROJECT_ROOT/.venv"

# Activate virtual environment if it exists (for Python JSON parsing)
if [ -d "$VENV_PATH" ] && [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
fi

# Find next handoff number for today
if [ -d "$HANDOFF_DIR" ]; then
    while [ -f "$HANDOFF_DIR/$DATE-$HANDOFF_COUNT.md" ]; do
        ((HANDOFF_COUNT++))
    done
fi

HANDOFF_FILE="$HANDOFF_DIR/$DATE-$HANDOFF_COUNT.md"

print_status() {
    echo -e "${BLUE}[HANDOFF]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Create directories if they don't exist
mkdir -p "$HANDOFF_DIR"
[ ! -f "$TASK_LOG" ] && echo "# CAKE Task Log" > "$TASK_LOG"

# Extract conversation context if available
CONTEXT_JSON="$PROJECT_ROOT/.cake/conversation-context/conversation-${DATE}.json"
CONVERSATION_CONTEXT=""
WORKFLOW_DIR="$PROJECT_ROOT/workflow"
if [ -x "$WORKFLOW_DIR/extraction/cake-extract-context.sh" ]; then
    print_status "Extracting conversation context..."
    "$WORKFLOW_DIR/extraction/cake-extract-context.sh" >/dev/null 2>&1 || true
    
    if [ -f "$CONTEXT_JSON" ]; then
        CONVERSATION_CONTEXT="Available"
        # Parse JSON to get key data - updated for new format
        TASKS_DISCUSSED=$(python3 -c "import json; data=json.load(open('$CONTEXT_JSON')); tasks=data.get('tasks',[]); print('\n'.join(['- ' + t.get('text','') + (' ✓' if t.get('implemented') else '') for t in tasks[:10]]))" 2>/dev/null || echo "")
        DECISIONS_MADE=$(python3 -c "import json; data=json.load(open('$CONTEXT_JSON')); decisions=data.get('decisions',[]); print('\n'.join(['- ' + d.get('text','') for d in decisions[:10]]))" 2>/dev/null || echo "")
        PROBLEMS_SOLVED=$(python3 -c "import json; data=json.load(open('$CONTEXT_JSON')); probs=data.get('problems_solved',[]); print('\n'.join(['- ' + p.get('problem','') + ' → ' + p.get('solution','')[:50] + '...' for p in probs[:5]]))" 2>/dev/null || echo "")
        KEY_INSIGHTS=$(python3 -c "import json; data=json.load(open('$CONTEXT_JSON')); print('\n'.join(['- ' + i for i in data.get('key_insights', [])[:5]]))" 2>/dev/null || echo "")
    else
        CONVERSATION_CONTEXT="Not available"
    fi
else
    CONVERSATION_CONTEXT="Extractor not found"
fi

# Gather information
print_status "Gathering project status..."

# Git information
CURRENT_BRANCH=$(git -C "$PROJECT_ROOT" branch --show-current 2>/dev/null || echo "main")
LAST_COMMIT=$(git -C "$PROJECT_ROOT" log -1 --pretty=format:"%h - %s" 2>/dev/null || echo "No commits yet")
UNCOMMITTED=$(git -C "$PROJECT_ROOT" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
FILES_CHANGED=$(git -C "$PROJECT_ROOT" diff --name-only 2>/dev/null | wc -l | tr -d ' ')

# Recent activity (last 10 commands from history if available)
RECENT_COMMANDS=""
if [ -f ~/.zsh_history ]; then
    RECENT_COMMANDS=$(tail -50 ~/.zsh_history | grep -E "(cake|CAKE|pytest|lint)" | tail -10 || echo "No recent CAKE commands")
elif [ -f ~/.bash_history ]; then
    RECENT_COMMANDS=$(tail -50 ~/.bash_history | grep -E "(cake|CAKE|pytest|lint)" | tail -10 || echo "No recent CAKE commands")
fi

# Test status
TEST_STATUS="Not run"
if command -v pytest &> /dev/null && [ -d "$PROJECT_ROOT/tests" ]; then
    if pytest "$PROJECT_ROOT/tests" -q 2>/dev/null; then
        TEST_STATUS="✅ All tests passing"
    else
        TEST_STATUS="❌ Some tests failing"
    fi
fi

# Lint status from last run
LINT_STATUS="Not checked"
if [ -f "$PROJECT_ROOT/.cake/lint-status" ]; then
    LINT_STATUS=$(cat "$PROJECT_ROOT/.cake/lint-status")
fi

# TODO count (excluding .venv and other build directories)
TODO_COUNT=$(grep -r "TODO" "$PROJECT_ROOT" --include="*.py" --include="*.sh" --exclude-dir=".venv" --exclude-dir="venv" --exclude-dir="__pycache__" --exclude-dir=".git" 2>/dev/null | wc -l | tr -d ' ')
FIXME_COUNT=$(grep -r "FIXME" "$PROJECT_ROOT" --include="*.py" --include="*.sh" --exclude-dir=".venv" --exclude-dir="venv" --exclude-dir="__pycache__" --exclude-dir=".git" 2>/dev/null | wc -l | tr -d ' ')

# Generate handoff document
print_status "Generating handoff document..."

cat > "$HANDOFF_FILE" << EOF
# CAKE Development Handoff - $DATE (#$HANDOFF_COUNT)

Generated: $DATE at $TIME

## 🎯 Current Status

- **Branch**: \`$CURRENT_BRANCH\`
- **Last Commit**: $LAST_COMMIT
- **Uncommitted Changes**: $UNCOMMITTED files
- **Files Modified**: $FILES_CHANGED files
- **Test Status**: $TEST_STATUS
- **Lint Status**: $LINT_STATUS
- **TODOs**: $TODO_COUNT | **FIXMEs**: $FIXME_COUNT

## 📋 Today's Progress

### Tasks Discussed in Conversation
${TASKS_DISCUSSED:-"- No conversation context available"}

### Decisions Made
${DECISIONS_MADE:-"- No decisions captured"}

### Problems Solved
${PROBLEMS_SOLVED:-"- No problems recorded"}

### Key Insights
${KEY_INSIGHTS:-"- No insights captured"}

### Completed Tasks (from git)
$(git -C "$PROJECT_ROOT" log --since="$DATE 00:00" --pretty=format:"- %s" 2>/dev/null || echo "- No commits today yet")

### Files Modified Today
\`\`\`
$(git -C "$PROJECT_ROOT" diff --name-only --since="$DATE 00:00" 2>/dev/null || echo "No files modified today")
\`\`\`

### Current Working Directory State
\`\`\`
$(cd "$PROJECT_ROOT" && find . -name "*.py" -o -name "*.sh" -o -name "*.md" | grep -v ".venv" | grep -v "__pycache__" | sort | head -20)
... (showing first 20 files)
\`\`\`

## 🔄 Recent Activity

### Recent CAKE Commands
\`\`\`bash
$RECENT_COMMANDS
\`\`\`

## 🚧 Work in Progress

### Uncommitted Changes
\`\`\`
$(cd "$PROJECT_ROOT" && git status --short 2>/dev/null || echo "No uncommitted changes")
\`\`\`

### Current TODOs
\`\`\`
$(grep -r "TODO" "$PROJECT_ROOT" --include="*.py" --include="*.sh" --exclude-dir=".venv" --exclude-dir="venv" --exclude-dir="__pycache__" --exclude-dir=".git" -n | head -10 || echo "No TODOs found")
\`\`\`

## 📝 Notes for Next Session

- [ ] Review uncommitted changes
- [ ] Run \`./scripts/cake-lint.sh\` to ensure code quality
- [ ] Update tests if new functionality added
- [ ] Check GitHub issues for priorities

## 🎯 Next Steps

1. **If continuing current work**: Check uncommitted changes above
2. **If starting new work**: Review cake-roadmap-v2.md for priorities

## 📎 Attachments

### Conversation Context
- **Status**: $CONVERSATION_CONTEXT
- **Structured data**: ${CONTEXT_JSON#$PROJECT_ROOT/}
EOF

# Copy full conversation if available
CONVERSATION_MD="$PROJECT_ROOT/.cake/conversation-context/conversation-${DATE}.md"
if [ -f "$CONVERSATION_MD" ]; then
    CONVERSATION_COPY="$HANDOFF_DIR/conversation-${DATE}-${HANDOFF_COUNT}-full.md"
    cp "$CONVERSATION_MD" "$CONVERSATION_COPY"
    echo "- **Full conversation**: [conversation-${DATE}-${HANDOFF_COUNT}-full.md](conversation-${DATE}-${HANDOFF_COUNT}-full.md)" >> "$HANDOFF_FILE"
    print_success "Attached full conversation log"
else
    # Try to find the conversation in Desktop location
    DESKTOP_CONV=$(find "/Users/dustinkirby/Desktop/Claude logs" -name "claude-conversation-*.md" -mtime 0 2>/dev/null | head -1)
    if [ -n "$DESKTOP_CONV" ] && [ -f "$DESKTOP_CONV" ]; then
        CONVERSATION_COPY="$HANDOFF_DIR/conversation-${DATE}-${HANDOFF_COUNT}-full.md"
        cp "$DESKTOP_CONV" "$CONVERSATION_COPY"
        echo "- **Full conversation**: [conversation-${DATE}-${HANDOFF_COUNT}-full.md](conversation-${DATE}-${HANDOFF_COUNT}-full.md)" >> "$HANDOFF_FILE"
        print_success "Attached full conversation log from Desktop"
    fi
fi

cat >> "$HANDOFF_FILE" << EOF
3. **Before committing**: Run \`./scripts/cake-pre-commit.sh\`

---
*Auto-generated by cake-handoff.sh*
EOF

print_success "Handoff document created: $HANDOFF_FILE"

# Update task log
print_status "Updating task log..."

# Create task log entry with conversation context
TASK_SUMMARY="${TASKS_DISCUSSED:-"No specific tasks discussed"}"
TASK_SUMMARY_BRIEF=$(echo "$TASK_SUMMARY" | head -3)  # First 3 tasks for brevity

TASK_LOG_ENTRY="
## $DATE - Session $HANDOFF_COUNT

**Time**: $TIME  
**Branch**: $CURRENT_BRANCH  
**Status**: $LINT_STATUS  
**Context**: $CONVERSATION_CONTEXT

### Session Summary
${TASK_SUMMARY_BRIEF}

### Work Completed
$(git -C "$PROJECT_ROOT" log --since="$DATE 00:00" --pretty=format:"- %s" 2>/dev/null || echo "- Session in progress")

### Key Decisions
${DECISIONS_MADE:-"- No major decisions recorded"}

### Files Modified
$(git -C "$PROJECT_ROOT" diff --name-only --since="$DATE 00:00" 2>/dev/null | sed 's/^/- /' || echo "- No files modified yet")

### Documentation
- **Handoff**: [View handoff]($HANDOFF_FILE)
- **Conversation Log**: ${CONTEXT_JSON#$PROJECT_ROOT/}

---"

# Append to task log
echo "$TASK_LOG_ENTRY" >> "$TASK_LOG"
print_success "Task log updated: $TASK_LOG"

# Summary
echo
print_status "Handoff Summary:"
echo -e "  ${GREEN}✓${NC} Handoff document: ${BLUE}$HANDOFF_FILE${NC}"
echo -e "  ${GREEN}✓${NC} Task log updated: ${BLUE}$TASK_LOG${NC}"
echo -e "  ${GREEN}✓${NC} Current status captured"
echo

# If running in auto mode, add and commit
if [ "${1:-}" == "--auto" ]; then
    print_status "Auto-committing handoff documents..."
    cd "$PROJECT_ROOT"
    git add "$HANDOFF_FILE" "$TASK_LOG"
    git commit -m "docs: Auto-generate handoff $DATE-$HANDOFF_COUNT

- Updated task log
- Created handoff document
- Captured current project state

Generated by: cake-handoff.sh"
    print_success "Handoff documents committed!"
fi