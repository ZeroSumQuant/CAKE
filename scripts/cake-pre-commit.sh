#!/bin/bash
# cake-pre-commit.sh - Quick validation before commits (<30 seconds)
# Usage: ./cake-pre-commit.sh

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

# Timer
START_TIME=$(date +%s)

print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  CAKE Pre-Commit Checks${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_status() {
    echo -e "${BLUE}[PRE-COMMIT]${NC} $1"
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

# Track results
FAILED=false

print_header
print_status "Running quick validation checks..."

# 1. Check for syntax errors
print_status "Checking Python syntax..."
if find "$PROJECT_ROOT/cake" -name "*.py" -exec python3 -m py_compile {} + 2>/dev/null; then
    print_success "Python syntax OK"
else
    print_error "Python syntax errors found"
    FAILED=true
fi

# 2. Quick format check (black)
if command -v black &> /dev/null; then
    print_status "Checking code formatting..."
    if black "$PROJECT_ROOT/cake" --check --quiet --line-length 100 2>/dev/null; then
        print_success "Code formatting OK"
    else
        print_warning "Code needs formatting (run: ./scripts/cake-lint.sh)"
        FAILED=true
    fi
fi

# 3. Import order check (isort)
if command -v isort &> /dev/null; then
    print_status "Checking import order..."
    if isort "$PROJECT_ROOT/cake" --check-only --quiet --profile black 2>/dev/null; then
        print_success "Import order OK"
    else
        print_warning "Imports need sorting (run: ./scripts/cake-lint.sh)"
        FAILED=true
    fi
fi

# 4. Basic flake8 check (errors only)
if command -v flake8 &> /dev/null; then
    print_status "Checking for critical issues..."
    if flake8 "$PROJECT_ROOT/cake" --select=E9,F63,F7,F82 --quiet 2>/dev/null; then
        print_success "No critical issues"
    else
        print_error "Critical flake8 errors found"
        FAILED=true
    fi
fi

# 5. Check for debugging artifacts
print_status "Checking for debug artifacts..."
DEBUG_FOUND=false
if grep -r "import pdb\|pdb.set_trace\|breakpoint()" "$PROJECT_ROOT/cake" 2>/dev/null; then
    print_error "Found pdb/breakpoint statements"
    DEBUG_FOUND=true
    FAILED=true
fi
if grep -r "print(" "$PROJECT_ROOT/cake" --include="*.py" | grep -v "#.*print(" 2>/dev/null; then
    print_warning "Found print statements (use logging instead)"
fi
if [ "$DEBUG_FOUND" = false ]; then
    print_success "No debug artifacts"
fi

# 6. Check for merge conflicts
print_status "Checking for merge conflicts..."
if grep -r "<<<<<<< \|======= \|>>>>>>> " "$PROJECT_ROOT/cake" 2>/dev/null; then
    print_error "Merge conflicts found"
    FAILED=true
else
    print_success "No merge conflicts"
fi

# 7. Quick test of changed files (if pytest available)
if command -v pytest &> /dev/null && command -v git &> /dev/null; then
    # Get changed Python files
    CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep "\.py$" || true)
    if [ -n "$CHANGED_FILES" ]; then
        print_status "Running tests for changed files..."
        # Convert file paths to test paths
        TEST_FILES=""
        for file in $CHANGED_FILES; do
            if [[ $file == cake/* ]]; then
                test_file="tests/unit/test_${file#cake/}"
                test_file="${test_file%.py}.py"
                if [ -f "$PROJECT_ROOT/$test_file" ]; then
                    TEST_FILES="$TEST_FILES $test_file"
                fi
            fi
        done
        
        if [ -n "$TEST_FILES" ]; then
            if pytest $TEST_FILES -q --tb=short 2>/dev/null; then
                print_success "Tests passed"
            else
                print_error "Tests failed"
                FAILED=true
            fi
        else
            print_warning "No tests found for changed files"
        fi
    fi
fi

# Calculate elapsed time
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

# Summary
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ "$FAILED" = true ]; then
    echo -e "${RED}Pre-commit checks FAILED${NC} (${ELAPSED}s)"
    echo -e "\nPlease fix the issues above before committing."
    echo -e "Run ${BLUE}./scripts/cake-lint.sh${NC} to auto-fix formatting issues"
    exit 1
else
    echo -e "${GREEN}All pre-commit checks PASSED${NC} (${ELAPSED}s)"
    echo -e "\n${GREEN}Ready to commit! 🎉${NC}"
    exit 0
fi