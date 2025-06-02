#!/bin/bash
# cake-lint.sh - Run all code quality tools on CAKE codebase
# Usage: ./cake-lint.sh [options] [path]

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
TARGET_PATH="${1:-$PROJECT_ROOT/cake}"

# Status tracking
FAILED_CHECKS=()
PASSED_CHECKS=()

# Helper functions
print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_status() {
    echo -e "${BLUE}[LINT]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    PASSED_CHECKS+=("$1")
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
    FAILED_CHECKS+=("$1")
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

show_help() {
    cat << EOF
CAKE Code Quality Tool
======================

Usage: ./cake-lint.sh [OPTIONS] [path]

OPTIONS:
    -h, --help          Show this help message
    -c, --check-only    Check only, don't auto-fix (for CI/CD)
    -v, --verbose       Show detailed output
    --no-color          Disable colored output
    --pylint            Include pylint analysis (slower but thorough)
    --deadcode          Check for dead/unused code with vulture
    --all               Run ALL checks including optional ones
    --handoff           Auto-generate handoff doc when all checks pass

ARGUMENTS:
    path                Path to check (default: cake/)

TOOLS RUN:
    1. black          - Code formatting
    2. isort          - Import sorting
    3. flake8         - Style guide enforcement
    4. mypy           - Type checking
    5. bandit         - Security linting
    6. safety         - Dependency vulnerability scanning
    7. pylint         - Advanced code analysis (optional with --pylint)
    8. vulture        - Dead code detection (optional with --deadcode)

EXAMPLES:
    ./cake-lint.sh                    # Lint and auto-fix cake/ directory
    ./cake-lint.sh --check-only       # Check only, don't auto-fix (CI mode)
    ./cake-lint.sh cake/components/   # Lint specific directory
    ./cake-lint.sh --handoff          # Generate handoff when all pass
    ./cake-lint.sh --all --handoff    # Full validation + handoff

EXIT CODES:
    0 - All checks passed
    1 - One or more checks failed
    2 - Tool not found

EOF
    exit 0
}

# Parse arguments
CHECK_ONLY=false
VERBOSE=false
NO_COLOR=false
RUN_PYLINT=false
RUN_DEADCODE=false
RUN_ALL=false
RUN_HANDOFF=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            ;;
        -c|--check-only)
            CHECK_ONLY=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --no-color)
            NO_COLOR=true
            RED=''
            GREEN=''
            YELLOW=''
            BLUE=''
            NC=''
            shift
            ;;
        --pylint)
            RUN_PYLINT=true
            shift
            ;;
        --deadcode)
            RUN_DEADCODE=true
            shift
            ;;
        --all)
            RUN_ALL=true
            RUN_PYLINT=true
            RUN_DEADCODE=true
            shift
            ;;
        --handoff)
            RUN_HANDOFF=true
            shift
            ;;
        *)
            TARGET_PATH="$1"
            shift
            ;;
    esac
done

# Check if path exists
if [ ! -e "$TARGET_PATH" ]; then
    print_error "Path not found: $TARGET_PATH"
    exit 1
fi

# Main execution
print_header "CAKE Code Quality Check"
print_status "Target: $TARGET_PATH"
print_status "Mode: $([ "$CHECK_ONLY" = true ] && echo "Check Only" || echo "Auto-Fix")"
echo

# 1. Black - Code Formatting
print_status "Running Black (code formatting)..."
if command -v black &> /dev/null; then
    if [ "$CHECK_ONLY" = true ]; then
        if black "$TARGET_PATH" --check --line-length 100 &> /dev/null; then
            print_success "Black: Code formatting OK"
        else
            print_error "Black: Code needs formatting"
            [ "$VERBOSE" = true ] && black "$TARGET_PATH" --check --diff --line-length 100
        fi
    else
        if black "$TARGET_PATH" --line-length 100; then
            print_success "Black: Code formatted"
        else
            print_error "Black: Formatting failed"
        fi
    fi
else
    print_error "Black not installed (pip install black)"
fi

# 2. isort - Import Sorting
print_status "Running isort (import sorting)..."
if command -v isort &> /dev/null; then
    if [ "$CHECK_ONLY" = true ]; then
        if isort "$TARGET_PATH" --check-only --profile black --line-length 100 &> /dev/null; then
            print_success "isort: Import order OK"
        else
            print_error "isort: Imports need sorting"
            [ "$VERBOSE" = true ] && isort "$TARGET_PATH" --check-only --diff --profile black
        fi
    else
        if isort "$TARGET_PATH" --profile black --line-length 100; then
            print_success "isort: Imports sorted"
        else
            print_error "isort: Import sorting failed"
        fi
    fi
else
    print_error "isort not installed (pip install isort)"
fi

# 3. Flake8 - Style Guide
print_status "Running flake8 (style guide)..."
if command -v flake8 &> /dev/null; then
    FLAKE8_CONFIG=""
    if [ -f "$PROJECT_ROOT/.flake8" ]; then
        FLAKE8_CONFIG="--config=$PROJECT_ROOT/.flake8"
    else
        FLAKE8_CONFIG="--max-line-length=100 --extend-ignore=E203,W503"
    fi
    
    if flake8 "$TARGET_PATH" $FLAKE8_CONFIG &> /dev/null; then
        print_success "flake8: Style guide passed"
    else
        print_error "flake8: Style violations found"
        if [ "$VERBOSE" = true ]; then
            flake8 "$TARGET_PATH" $FLAKE8_CONFIG
        else
            flake8 "$TARGET_PATH" $FLAKE8_CONFIG --count --statistics
        fi
    fi
else
    print_error "flake8 not installed (pip install flake8)"
fi

# 4. mypy - Type Checking
print_status "Running mypy (type checking)..."
if command -v mypy &> /dev/null; then
    MYPY_CONFIG=""
    if [ -f "$PROJECT_ROOT/pyproject.toml" ]; then
        MYPY_CONFIG="--config-file=$PROJECT_ROOT/pyproject.toml"
    fi
    
    if mypy "$TARGET_PATH" $MYPY_CONFIG &> /dev/null; then
        print_success "mypy: Type checking passed"
    else
        print_error "mypy: Type errors found"
        [ "$VERBOSE" = true ] && mypy "$TARGET_PATH" $MYPY_CONFIG
    fi
else
    print_error "mypy not installed (pip install mypy)"
fi

# 5. Bandit - Security Linting
print_status "Running bandit (security linting)..."
if command -v bandit &> /dev/null; then
    if bandit -r "$TARGET_PATH" -ll &> /dev/null; then
        print_success "bandit: No security issues"
    else
        print_error "bandit: Security issues found"
        [ "$VERBOSE" = true ] && bandit -r "$TARGET_PATH" -ll
    fi
else
    print_error "bandit not installed (pip install bandit)"
fi

# 6. Safety - Dependency Security Check
print_status "Running safety (dependency security check)..."
if command -v safety &> /dev/null; then
    if safety check --json &> /dev/null; then
        print_success "safety: No known vulnerabilities"
    else
        print_error "safety: Vulnerable dependencies found"
        [ "$VERBOSE" = true ] && safety check
    fi
else
    print_error "safety not installed (pip install safety)"
fi

# 7. Pylint - Advanced Code Analysis (optional)
if [ "$RUN_PYLINT" = true ] || [ "$RUN_ALL" = true ]; then
    print_status "Running pylint (advanced code analysis)..."
    if command -v pylint &> /dev/null; then
        PYLINT_CONFIG=""
        if [ -f "$PROJECT_ROOT/.pylintrc" ]; then
            PYLINT_CONFIG="--rcfile=$PROJECT_ROOT/.pylintrc"
        else
            # Reasonable defaults for CAKE project
            PYLINT_CONFIG="--max-line-length=100 --disable=C0111,R0903,W0212"
        fi
        
        if pylint "$TARGET_PATH" $PYLINT_CONFIG --exit-zero &> /dev/null; then
            SCORE=$(pylint "$TARGET_PATH" $PYLINT_CONFIG --exit-zero | grep "Your code has been rated" | awk '{print $7}')
            if [ -n "$SCORE" ]; then
                print_success "pylint: Code rated $SCORE"
            else
                print_success "pylint: Analysis complete"
            fi
        else
            print_error "pylint: Issues found"
            if [ "$VERBOSE" = true ]; then
                pylint "$TARGET_PATH" $PYLINT_CONFIG --exit-zero
            else
                # Show just the score
                pylint "$TARGET_PATH" $PYLINT_CONFIG --exit-zero | grep -E "(Your code has been rated|rated at)"
            fi
        fi
    else
        print_warning "pylint not installed (pip install pylint)"
    fi
fi

# 8. Vulture - Dead Code Detection (optional)
if [ "$RUN_DEADCODE" = true ] || [ "$RUN_ALL" = true ]; then
    print_status "Running vulture (dead code detection)..."
    if command -v vulture &> /dev/null; then
        VULTURE_OUTPUT=$(vulture "$TARGET_PATH" --min-confidence 80 2>&1)
        if [ -z "$VULTURE_OUTPUT" ]; then
            print_success "vulture: No dead code found"
        else
            print_warning "vulture: Potential dead code found"
            if [ "$VERBOSE" = true ]; then
                echo "$VULTURE_OUTPUT"
            else
                # Count issues
                DEAD_COUNT=$(echo "$VULTURE_OUTPUT" | wc -l)
                echo "  Found $DEAD_COUNT potential dead code items (use -v for details)"
            fi
        fi
    else
        print_warning "vulture not installed (pip install vulture)"
    fi
fi

# 9. Additional checks for CAKE-specific requirements
print_status "Running CAKE-specific checks..."

# Check for proper error handling
# Use find to avoid potential grep hanging issues
ERROR_HANDLING=0
while IFS= read -r -d '' file; do
    if grep -q "except:" "$file" 2>/dev/null; then
        ERROR_HANDLING=$((ERROR_HANDLING + 1))
    fi
done < <(find "$TARGET_PATH" -name "*.py" -type f -print0 2>/dev/null)

if [ "$ERROR_HANDLING" -gt 0 ]; then
    print_warning "Found bare 'except:' statements (use specific exceptions)"
    [ "$VERBOSE" = true ] && find "$TARGET_PATH" -name "*.py" -type f -exec grep -Hn "except:" {} \; 2>/dev/null
else
    print_success "No bare except statements"
fi

# Check for proper logging (no print statements in production code)
# Skip this check if we're checking the scripts directory
if [[ "$TARGET_PATH" != *"scripts"* ]]; then
    PRINT_COUNT=0
    while IFS= read -r -d '' file; do
        # Count print statements not in comments
        # First grep might not find anything, so we handle that case
        if grep -q "print(" "$file" 2>/dev/null; then
            count=$(grep "print(" "$file" 2>/dev/null | grep -v "#.*print(" | wc -l | tr -d ' ')
        else
            count=0
        fi
        # Ensure count is a valid number
        if [[ -z "$count" ]] || [[ ! "$count" =~ ^[0-9]+$ ]]; then
            count=0
        fi
        PRINT_COUNT=$((PRINT_COUNT + count))
    done < <(find "$TARGET_PATH" -name "*.py" -type f -print0 2>/dev/null)
    
    if [ "$PRINT_COUNT" -gt 0 ]; then
        print_warning "Found print statements (use logging instead)"
        [ "$VERBOSE" = true ] && find "$TARGET_PATH" -name "*.py" -type f -exec grep -Hn "print(" {} \; 2>/dev/null | grep -v "#.*print("
    else
        print_success "No print statements in production code"
    fi
else
    print_success "Print statements allowed in scripts"
fi

# Summary
print_header "Summary"
echo -e "Passed: ${GREEN}${#PASSED_CHECKS[@]}${NC}"
echo -e "Failed: ${RED}${#FAILED_CHECKS[@]}${NC}"

if [ ${#FAILED_CHECKS[@]} -gt 0 ]; then
    echo
    echo -e "${RED}Failed checks:${NC}"
    for check in "${FAILED_CHECKS[@]}"; do
        echo -e "  - $check"
    done
    
    if [ "$CHECK_ONLY" = true ] && [[ " ${FAILED_CHECKS[@]} " =~ "Black" || " ${FAILED_CHECKS[@]} " =~ "isort" ]]; then
        echo
        print_warning "Run without --check-only to auto-fix formatting issues"
    fi
    
    exit 1
else
    echo
    print_success "All checks passed! 🎉"
    
    # Save lint status for handoff (in hidden directory)
    mkdir -p "$PROJECT_ROOT/.cake"
    echo "✅ All checks passed at $(date +%Y-%m-%d\ %H:%M)" > "$PROJECT_ROOT/.cake/lint-status"
    
    # Generate handoff if requested
    if [ "$RUN_HANDOFF" = true ]; then
        echo
        print_status "Generating handoff documentation..."
        if [ -x "$SCRIPT_DIR/cake-handoff.sh" ]; then
            "$SCRIPT_DIR/cake-handoff.sh"
        else
            print_warning "cake-handoff.sh not found or not executable"
        fi
    fi
    
    exit 0
fi