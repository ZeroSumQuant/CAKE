#!/bin/bash
# cake-workflow.sh - Master workflow orchestrator for CAKE development
# Provides guided workflow with automatic failure recovery

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Helper functions
print_banner() {
    echo -e "${MAGENTA}"
    echo "╔═══════════════════════════════════════════╗"
    echo "║        CAKE Workflow Orchestrator         ║"
    echo "╚═══════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo -e "\n${CYAN}[$1]${NC} $2"
}

print_success() {
    echo -e "${GREEN}  ✓${NC} $1"
}

print_error() {
    echo -e "${RED}  ✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}  ℹ${NC} $1"
}

wait_for_user() {
    echo -e "\n${YELLOW}Press Enter to continue or Ctrl+C to abort...${NC}"
    read -r
}

# Command execution with status
run_command() {
    local cmd="$1"
    local description="$2"
    
    echo -e "${BLUE}  ▶${NC} Running: ${CYAN}$cmd${NC}"
    if eval "$cmd"; then
        print_success "$description successful"
        return 0
    else
        print_error "$description failed"
        return 1
    fi
}

# Main workflow
print_banner

# Parse arguments
MODE="${1:-interactive}"

case "$MODE" in
    "interactive"|"-i")
        print_info "Running in interactive mode"
        ;;
    "auto"|"-a")
        print_info "Running in automatic mode"
        ;;
    "status"|"-s")
        exec "$SCRIPT_DIR/cake-status.sh"
        ;;
    "help"|"-h"|"--help")
        cat << EOF
Usage: ./cake-workflow.sh [mode]

Modes:
  interactive  (default) Step-by-step guided workflow
  auto         Automatic workflow with smart decisions
  status       Show current status and exit
  help         Show this help message

The workflow will:
1. Check current status
2. Run linting and tests
3. Generate documentation
4. Create/update PR
5. Monitor CI status
6. Fix CI failures automatically
7. Guide you to successful merge

Examples:
  ./cake-workflow.sh              # Interactive mode
  ./cake-workflow.sh auto         # Fully automatic
  ./cake-workflow.sh status       # Just show status
EOF
        exit 0
        ;;
    *)
        print_error "Unknown mode: $MODE"
        exit 1
        ;;
esac

# Step 1: Status Check
print_step "1/7" "Checking current status"
"$SCRIPT_DIR/cake-status.sh"

if [ "$MODE" = "interactive" ]; then
    wait_for_user
fi

# Step 2: Check for uncommitted changes
print_step "2/7" "Checking for uncommitted changes"
UNCOMMITTED=$(git status --porcelain | wc -l | tr -d ' ')

if [ "$UNCOMMITTED" -gt 0 ]; then
    print_info "Found $UNCOMMITTED uncommitted files"
    
    if [ "$MODE" = "interactive" ]; then
        echo -e "${YELLOW}Would you like to:${NC}"
        echo "  1) Stage and commit all changes"
        echo "  2) Review changes first"
        echo "  3) Skip commit for now"
        read -p "Choice [1-3]: " choice
        
        case "$choice" in
            1)
                read -p "Commit message: " commit_msg
                run_command "git add -A && git commit -m \"$commit_msg\"" "Commit"
                ;;
            2)
                git status
                git diff
                wait_for_user
                ;;
            3)
                print_info "Skipping commit"
                ;;
        esac
    else
        # Auto mode: commit with generated message
        run_command "git add -A && git commit -m 'chore: auto-commit changes from cake-workflow'" "Auto-commit"
    fi
else
    print_success "No uncommitted changes"
fi

# Step 3: Run linting
print_step "3/7" "Running code quality checks"

LINT_NEEDED=true
if [ -f "$PROJECT_ROOT/.cake/lint-status" ]; then
    LINT_AGE_HOURS=$(( ($(date +%s) - $(stat -f %m "$PROJECT_ROOT/.cake/lint-status")) / 3600 ))
    if [ "$LINT_AGE_HOURS" -lt 1 ] && [ "$UNCOMMITTED" -eq 0 ]; then
        print_info "Lint was run recently and no new changes"
        LINT_NEEDED=false
    fi
fi

if [ "$LINT_NEEDED" = true ]; then
    if ! run_command "$SCRIPT_DIR/cake-lint.sh" "Linting"; then
        print_error "Linting failed"
        
        if [ "$MODE" = "interactive" ]; then
            echo -e "${YELLOW}Would you like to:${NC}"
            echo "  1) View detailed lint errors"
            echo "  2) Try auto-fix"
            echo "  3) Skip and continue"
            read -p "Choice [1-3]: " choice
            
            case "$choice" in
                1)
                    "$SCRIPT_DIR/cake-lint.sh" --verbose
                    ;;
                2)
                    "$SCRIPT_DIR/cake-lint.sh"
                    ;;
                3)
                    print_info "Skipping lint fixes"
                    ;;
            esac
        else
            # Auto mode: try to fix
            print_info "Attempting auto-fix in auto mode"
            "$SCRIPT_DIR/cake-lint.sh" || true
        fi
    fi
fi

# Step 4: Generate documentation
print_step "4/7" "Generating documentation"

if ! run_command "$SCRIPT_DIR/cake-handoff.sh" "Documentation generation"; then
    print_error "Documentation generation failed"
    print_info "This is usually not critical, continuing..."
fi

# Step 5: Check PR status
print_step "5/7" "Managing pull request"

PR_EXISTS=$(gh pr view --json number 2>/dev/null || echo "")
BRANCH=$(git branch --show-current)

if [ -z "$PR_EXISTS" ]; then
    if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
        print_error "Cannot create PR from main branch"
        print_info "Create a feature branch first: git checkout -b feature/your-feature"
        exit 1
    fi
    
    print_info "No PR exists for branch: $BRANCH"
    
    if [ "$MODE" = "interactive" ]; then
        read -p "Create PR now? [Y/n]: " create_pr
        if [[ "$create_pr" =~ ^[Yy]?$ ]]; then
            run_command "$SCRIPT_DIR/cake-create-pr.sh" "PR creation"
        fi
    else
        # Auto mode: create PR
        run_command "$SCRIPT_DIR/cake-create-pr.sh" "PR creation"
    fi
else
    PR_NUMBER=$(echo "$PR_EXISTS" | jq -r '.number')
    print_success "PR #$PR_NUMBER already exists"
    
    # Check if we need to push
    COMMITS_TO_PUSH=$(git log origin/"$BRANCH".."$BRANCH" --oneline 2>/dev/null | wc -l | tr -d ' ')
    if [ "$COMMITS_TO_PUSH" -gt 0 ]; then
        print_info "Found $COMMITS_TO_PUSH commits to push"
        run_command "git push" "Push commits"
    fi
fi

# Step 6: Monitor CI
print_step "6/7" "Monitoring CI status"

if [ -n "$PR_EXISTS" ]; then
    print_info "Checking CI status..."
    
    # Quick CI check
    CI_STATUS=$(gh pr checks 2>&1 || echo "unknown")
    
    if echo "$CI_STATUS" | grep -q "All checks have passed"; then
        print_success "All CI checks passed!"
    elif echo "$CI_STATUS" | grep -q "Some checks were not successful"; then
        print_error "CI has failures"
        
        if [ "$MODE" = "interactive" ]; then
            read -p "Attempt automatic CI fixes? [Y/n]: " fix_ci
            if [[ "$fix_ci" =~ ^[Yy]?$ ]]; then
                run_command "$SCRIPT_DIR/cake-fix-ci.sh" "CI fixes"
            fi
        else
            # Auto mode: always try to fix
            run_command "$SCRIPT_DIR/cake-fix-ci.sh" "CI fixes"
        fi
        
        # Monitor after fixes
        print_info "Monitoring CI (press Ctrl+C to stop)..."
        "$SCRIPT_DIR/cake-fix-ci.sh" --monitor || true
    else
        print_info "CI is running or status unknown"
        
        if [ "$MODE" = "interactive" ]; then
            read -p "Monitor CI status? [Y/n]: " monitor
            if [[ "$monitor" =~ ^[Yy]?$ ]]; then
                "$SCRIPT_DIR/cake-fix-ci.sh" --monitor || true
            fi
        fi
    fi
fi

# Step 7: Final summary
print_step "7/7" "Workflow complete"

echo -e "\n${GREEN}═══════════════════════════════════${NC}"
echo -e "${GREEN}    Workflow Summary${NC}"
echo -e "${GREEN}═══════════════════════════════════${NC}"

# Show final status
"$SCRIPT_DIR/cake-status.sh" | grep -E "(Branch:|PR #|Lint:|CI/CD)" || true

echo -e "\n${CYAN}Quick actions:${NC}"
echo "  • View PR:        gh pr view --web"
echo "  • Check status:   ./scripts/cake-status.sh"
echo "  • Monitor CI:     ./scripts/cake-fix-ci.sh --monitor"

if [ -n "$PR_EXISTS" ]; then
    PR_URL=$(gh pr view --json url -q .url)
    echo -e "\n${CYAN}Your PR:${NC} $PR_URL"
fi

echo -e "\n${GREEN}✨ Workflow complete!${NC}"