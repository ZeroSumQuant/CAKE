#!/bin/bash
# cake-fix-ci.sh - Automatically fix CI failures and update PR
# This script handles common CI failures and updates the existing PR

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
TIME=$(date +%H:%M)
CONTEXT_DIR="$PROJECT_ROOT/.cake/conversation-context"
CI_LOG_DIR="$PROJECT_ROOT/.cake/ci-logs"
VENV_PATH="$PROJECT_ROOT/.venv"

# Activate virtual environment if it exists (for Python linting tools)
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
    echo -e "${BLUE}[CI-FIX]${NC} $1"
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

print_header "CAKE CI Failure Handler"

# Create directories
mkdir -p "$CI_LOG_DIR"
mkdir -p "$CONTEXT_DIR"

# Step 1: Check if we have an open PR
print_status "Checking for open PR..."
PR_INFO=$(gh pr view --json number,url,state,statusCheckRollup 2>/dev/null || echo "")

if [ -z "$PR_INFO" ]; then
    print_error "No PR found for current branch"
    print_status "Create a PR first with: ./scripts/cake-create-pr.sh"
    exit 1
fi

PR_NUMBER=$(echo "$PR_INFO" | jq -r '.number')
PR_URL=$(echo "$PR_INFO" | jq -r '.url')
PR_STATE=$(echo "$PR_INFO" | jq -r '.state')

if [ "$PR_STATE" != "OPEN" ]; then
    print_error "PR #$PR_NUMBER is not open (state: $PR_STATE)"
    exit 1
fi

print_success "Found open PR #$PR_NUMBER"

# Step 2: Analyze CI failures
print_status "Fetching CI status..."
CI_STATUS=$(echo "$PR_INFO" | jq -r '.statusCheckRollup')

# Save CI logs
CI_LOG_FILE="$CI_LOG_DIR/ci-failure-${TODAY}-${PR_NUMBER}.json"
echo "$CI_STATUS" > "$CI_LOG_FILE"

# Parse failures
FAILED_CHECKS=$(echo "$CI_STATUS" | jq -r '.[] | select(.conclusion == "failure") | .name' 2>/dev/null || echo "")

if [ -z "$FAILED_CHECKS" ]; then
    print_warning "No failed CI checks found. Checking workflow runs..."
    
    # Alternative: check workflow runs
    FAILED_RUNS=$(gh run list --limit 10 --json conclusion,name,headBranch | jq -r '.[] | select(.conclusion == "failure" and .headBranch == "'$(git branch --show-current)'") | .name' | head -5)
    
    if [ -z "$FAILED_RUNS" ]; then
        print_success "No CI failures detected!"
        exit 0
    fi
    
    FAILED_CHECKS="$FAILED_RUNS"
fi

print_warning "Failed checks:"
echo "$FAILED_CHECKS" | sed 's/^/  - /'

# Step 3: Attempt automatic fixes for common issues
print_status "Attempting automatic fixes..."

FIXES_APPLIED=()
FIX_COMMANDS=()

# Check each type of failure and apply fixes
if echo "$FAILED_CHECKS" | grep -q "lint\|black\|isort\|flake8"; then
    print_status "Detected linting failures - running auto-fix..."
    
    # Run black
    if black "$PROJECT_ROOT" --line-length 100; then
        FIXES_APPLIED+=("Formatted code with black")
        FIX_COMMANDS+=("black . --line-length 100")
    fi
    
    # Run isort
    if isort "$PROJECT_ROOT" --profile black --line-length 100; then
        FIXES_APPLIED+=("Sorted imports with isort")
        FIX_COMMANDS+=("isort . --profile black")
    fi
    
    # Run flake8 to check remaining issues
    FLAKE8_OUTPUT=$(flake8 "$PROJECT_ROOT" 2>&1 || true)
    if [ -n "$FLAKE8_OUTPUT" ]; then
        echo "$FLAKE8_OUTPUT" > "$CI_LOG_DIR/flake8-remaining-issues.txt"
        print_warning "Remaining flake8 issues saved to: $CI_LOG_DIR/flake8-remaining-issues.txt"
    fi
fi

if echo "$FAILED_CHECKS" | grep -q "mypy\|type"; then
    print_status "Detected type checking failures..."
    MYPY_OUTPUT=$(mypy "$PROJECT_ROOT" 2>&1 || true)
    echo "$MYPY_OUTPUT" > "$CI_LOG_DIR/mypy-issues.txt"
    print_warning "Type issues saved to: $CI_LOG_DIR/mypy-issues.txt"
    
    # Extract common type fixes
    if echo "$MYPY_OUTPUT" | grep -q "Missing type annotation"; then
        FIXES_APPLIED+=("Type annotations needed - manual fix required")
    fi
fi

if echo "$FAILED_CHECKS" | grep -q "test\|pytest"; then
    print_status "Detected test failures..."
    
    # Run tests and capture output
    TEST_OUTPUT=$(pytest "$PROJECT_ROOT/tests" -v 2>&1 || true)
    echo "$TEST_OUTPUT" > "$CI_LOG_DIR/test-failures.txt"
    
    # Extract failure summary
    FAILED_TESTS=$(echo "$TEST_OUTPUT" | grep "FAILED" | head -10)
    print_warning "Failed tests:"
    echo "$FAILED_TESTS" | sed 's/^/  /'
fi

if echo "$FAILED_CHECKS" | grep -q "security\|bandit\|safety"; then
    print_status "Detected security issues..."
    
    # Run bandit
    BANDIT_OUTPUT=$(bandit -r "$PROJECT_ROOT" -f json 2>&1 || true)
    echo "$BANDIT_OUTPUT" > "$CI_LOG_DIR/bandit-report.json"
    
    # Run safety
    SAFETY_OUTPUT=$(safety check --json 2>&1 || true)
    echo "$SAFETY_OUTPUT" > "$CI_LOG_DIR/safety-report.json"
    
    print_warning "Security reports saved to CI logs directory"
fi

# Step 4: Check if any files were modified
print_status "Checking for changes..."
if [ ${#FIXES_APPLIED[@]} -eq 0 ]; then
    print_warning "No automatic fixes could be applied"
    print_status "Manual intervention required. Check logs in: $CI_LOG_DIR"
else
    # Check if we have actual file changes
    if git diff --quiet; then
        print_warning "Fixes were run but no files were changed"
    else
        print_success "Applied ${#FIXES_APPLIED[@]} automatic fixes"
        
        # Create fix summary
        FIX_SUMMARY=$(printf '%s\n' "${FIXES_APPLIED[@]}" | sed 's/^/- /')
        
        # Step 5: Commit the fixes
        print_status "Committing fixes..."
        
        git add -A
        git commit -m "fix: address CI failures in PR #$PR_NUMBER

Automatic fixes applied:
$FIX_SUMMARY

Commands run:
$(printf '%s\n' "${FIX_COMMANDS[@]}" | sed 's/^/- /')

CI failures detected in:
$(echo "$FAILED_CHECKS" | sed 's/^/- /')

Generated by cake-fix-ci.sh"
        
        print_success "Fixes committed"
        
        # Step 6: Push fixes
        print_status "Pushing fixes to PR..."
        git push
        
        print_success "Fixes pushed to PR #$PR_NUMBER"
    fi
fi

# Step 7: Create CI fix summary for conversation context
print_status "Creating CI fix context..."

CI_FIX_CONTEXT=$(cat <<EOF
{
  "date": "$TODAY",
  "time": "$TIME",
  "pr_number": $PR_NUMBER,
  "failed_checks": $(echo "$FAILED_CHECKS" | jq -R . | jq -s .),
  "fixes_applied": $(printf '%s\n' "${FIXES_APPLIED[@]}" | jq -R . | jq -s .),
  "commands_run": $(printf '%s\n' "${FIX_COMMANDS[@]}" | jq -R . | jq -s .),
  "manual_fixes_needed": $([ ${#FIXES_APPLIED[@]} -eq 0 ] && echo "true" || echo "false"),
  "log_files": $(ls "$CI_LOG_DIR"/*-${PR_NUMBER}.* 2>/dev/null | jq -R . | jq -s .)
}
EOF
)

echo "$CI_FIX_CONTEXT" > "$CONTEXT_DIR/ci-fix-${TODAY}-${PR_NUMBER}.json"

# Step 8: Update PR with CI fix information
if [ ${#FIXES_APPLIED[@]} -gt 0 ]; then
    print_status "Updating PR description..."
    
    CURRENT_BODY=$(gh pr view --json body -q .body)
    
    UPDATE_NOTE="
## CI Fix Applied - $TODAY $TIME

### Failures Addressed
$(echo "$FAILED_CHECKS" | sed 's/^/- /')

### Automatic Fixes
$FIX_SUMMARY

### Status
- 🔄 Fixes pushed - waiting for CI to re-run
- 📋 Fix logs available in \`.cake/ci-logs/\`
"
    
    # Append to PR body
    echo "$CURRENT_BODY

$UPDATE_NOTE" | gh pr edit --body-file -
    
    print_success "PR description updated"
fi

# Step 9: Provide summary and next steps
print_header "CI Fix Summary"

if [ ${#FIXES_APPLIED[@]} -gt 0 ]; then
    echo -e "${GREEN}Automatic fixes applied:${NC}"
    printf '%s\n' "${FIXES_APPLIED[@]}" | sed 's/^/  ✓ /'
    echo
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Wait for CI to re-run (usually automatic)"
    echo "  2. Check PR at: $PR_URL"
    echo "  3. If CI still fails, check logs in: $CI_LOG_DIR"
else
    echo -e "${YELLOW}No automatic fixes available${NC}"
    echo
    echo -e "${BLUE}Manual fixes required:${NC}"
    echo "  1. Review failure logs in: $CI_LOG_DIR"
    echo "  2. Fix issues manually"
    echo "  3. Run: ./scripts/cake-lint.sh to verify"
    echo "  4. Commit and push fixes"
fi

echo
print_status "CI logs saved to: $CI_LOG_DIR"
print_status "Context saved to: $CONTEXT_DIR/ci-fix-${TODAY}-${PR_NUMBER}.json"

# Step 10: If requested, monitor CI status
if [ "${1:-}" == "--monitor" ]; then
    print_status "Monitoring CI status (press Ctrl+C to stop)..."
    
    while true; do
        sleep 30
        STATUS=$(gh pr checks 2>&1 || echo "failed to get status")
        
        if echo "$STATUS" | grep -q "All checks have passed"; then
            print_success "All CI checks have passed! 🎉"
            break
        elif echo "$STATUS" | grep -q "Some checks were not successful"; then
            print_warning "CI still has failures - checking again in 30s..."
        else
            print_status "CI running... checking again in 30s..."
        fi
    done
fi