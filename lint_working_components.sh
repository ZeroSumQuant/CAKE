#!/bin/bash
# Lint the working components only

echo "🔍 Linting Working CAKE Components"
echo "=================================="

# Working components from health check
WORKING_COMPONENTS=(
    "cake/components/operator.py"
    "cake/components/recall_db.py"
    "cake/components/validator.py"
    "cake/components/snapshot_manager.py"
    "cake/utils/rule_creator.py"
)

# Create temporary directory for results
RESULTS_DIR="lint_results"
mkdir -p "$RESULTS_DIR"

echo "Running black (formatter)..."
black --check "${WORKING_COMPONENTS[@]}" 2>&1 | tee "$RESULTS_DIR/black.log"

echo -e "\nRunning isort (import sorter)..."
isort --check-only "${WORKING_COMPONENTS[@]}" 2>&1 | tee "$RESULTS_DIR/isort.log"

echo -e "\nRunning flake8 (linter)..."
flake8 "${WORKING_COMPONENTS[@]}" 2>&1 | tee "$RESULTS_DIR/flake8.log"

echo -e "\nRunning mypy (type checker)..."
mypy "${WORKING_COMPONENTS[@]}" 2>&1 | tee "$RESULTS_DIR/mypy.log"

echo -e "\n📊 Summary:"
echo "- Black log: $RESULTS_DIR/black.log"
echo "- Isort log: $RESULTS_DIR/isort.log" 
echo "- Flake8 log: $RESULTS_DIR/flake8.log"
echo "- Mypy log: $RESULTS_DIR/mypy.log"