#!/bin/bash
# cake-setup-dev.sh - Set up CAKE development environment
# Usage: source ./scripts/cake-setup-dev.sh

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

print_status() {
    echo -e "${BLUE}[SETUP]${NC} $1"
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

# Check if being sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    print_error "This script must be sourced, not executed!"
    print_warning "Usage: source ./scripts/cake-setup-dev.sh"
    exit 1
fi

print_status "Setting up CAKE development environment..."

# Navigate to project root
cd "$PROJECT_ROOT"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv .venv
    print_success "Virtual environment created"
else
    print_status "Virtual environment already exists"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source .venv/bin/activate
print_success "Virtual environment activated"

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip --quiet
print_success "pip upgraded"

# Install dependencies
if [ -f "requirements.txt" ]; then
    print_status "Installing production dependencies..."
    pip install -r requirements.txt --quiet
    print_success "Production dependencies installed"
fi

if [ -f "requirements-dev.txt" ]; then
    print_status "Installing development dependencies..."
    pip install -r requirements-dev.txt --quiet
    print_success "Development dependencies installed"
else
    print_warning "No requirements-dev.txt found, installing essential dev tools..."
    pip install black isort flake8 mypy bandit safety pylint vulture --quiet
    print_success "Essential dev tools installed"
fi

# Set up git hooks (optional)
if [ -d ".git" ] && command -v pre-commit &> /dev/null; then
    print_status "Setting up git pre-commit hooks..."
    pre-commit install
    print_success "Git hooks installed"
fi

# Verify installation
print_status "Verifying installation..."
echo
echo "Installed tools:"
echo "  Python:  $(python --version)"
echo "  pip:     $(pip --version | awk '{print $2}')"

# Check for key tools
for tool in black isort flake8 mypy bandit safety; do
    if command -v $tool &> /dev/null; then
        version=$($tool --version 2>&1 | head -1 || echo "installed")
        echo "  $tool: $version"
    else
        print_warning "$tool not installed"
    fi
done

echo
print_success "Development environment ready!"
echo
echo "Your prompt should show (.venv) indicating the virtual environment is active."
echo "To deactivate later, run: deactivate"
echo
echo "Next steps:"
echo "  1. Run linting: ./scripts/cake-lint.sh"
echo "  2. Run tests: pytest"
echo "  3. Start coding!"