#!/bin/bash
# Pre-push verification script - Run this before pushing to main
# This replicates all CI/CD checks locally

set -e  # Exit on any error

echo "🔍 Running CAKE Pre-Push Verification..."
echo "========================================"

# Check we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Not in CAKE project root"
    exit 1
fi

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "❌ Error: Virtual environment not found"
    exit 1
fi

echo "✅ Environment activated"
echo ""

# 1. Code Formatting
echo "📝 Checking code formatting..."
echo "------------------------------"
black . --check || { echo "❌ Black formatting failed. Run 'black .' to fix"; exit 1; }
echo "✅ Black formatting passed"

isort . --check || { echo "❌ Import sorting failed. Run 'isort .' to fix"; exit 1; }
echo "✅ Import sorting passed"
echo ""

# 2. Linting
echo "🔍 Running linters..."
echo "---------------------"
flake8 || { echo "❌ Flake8 found issues"; exit 1; }
echo "✅ Flake8 passed"

# 3. Type Checking
echo "🔍 Running type checks..."
echo "-------------------------"
mypy . || { echo "❌ MyPy type checking failed"; exit 1; }
echo "✅ Type checking passed"
echo ""

# 4. Security Checks
echo "🔐 Running security checks..."
echo "-----------------------------"
bandit -r cake/ -ll || { echo "❌ Bandit found security issues"; exit 1; }
echo "✅ Security scan passed"

safety check || { echo "❌ Vulnerable dependencies found"; exit 1; }
echo "✅ No vulnerable dependencies"
echo ""

# 5. Tests
echo "🧪 Running tests..."
echo "-------------------"
pytest --cov=cake --cov-report=term-missing --cov-fail-under=90 || { echo "❌ Tests failed or coverage < 90%"; exit 1; }
echo "✅ All tests passed with sufficient coverage"
echo ""

# 6. Performance Benchmarks
echo "⚡ Running performance benchmarks..."
echo "-----------------------------------"
if [ -d "tests/perf" ]; then
    pytest tests/perf/ --benchmark-only || { echo "❌ Performance benchmarks failed"; exit 1; }
    echo "✅ Performance benchmarks passed"
else
    echo "⚠️  No performance tests found"
fi
echo ""

# 7. Build Check
echo "📦 Checking build..."
echo "--------------------"
python -m build --sdist --wheel . || { echo "❌ Build failed"; exit 1; }
echo "✅ Build successful"
echo ""

# Summary
echo "======================================"
echo "✅ All checks passed! Safe to push to main."
echo "======================================"
echo ""
echo "To push: git push origin main"