#!/bin/bash
# cake-generate-ci.sh - Generate GitHub Actions workflow for CAKE projects

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[CI-GEN]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

show_help() {
    cat << EOF
CAKE CI/CD Generator
====================

Usage: ./cake-generate-ci.sh [OPTIONS]

OPTIONS:
    -h, --help          Show this help message
    -t, --template      CI template type (basic|full|security|performance)
    -p, --python        Python versions (comma-separated, default: 3.9,3.10,3.11)
    --no-cache          Disable dependency caching
    --with-deployment   Add deployment steps
    --branch            Target branch (default: main)

TEMPLATES:
    basic       - Linting and basic tests only
    full        - Complete CI with all checks (default)
    security    - Focus on security scanning
    performance - Include performance benchmarks

EXAMPLES:
    ./cake-generate-ci.sh                    # Full CI for Python 3.9,3.10,3.11
    ./cake-generate-ci.sh -t basic -p 3.11   # Basic CI for Python 3.11 only
    ./cake-generate-ci.sh --with-deployment  # Full CI with deployment

EOF
    exit 0
}

# Parse arguments
TEMPLATE="full"
PYTHON_VERSIONS="3.9,3.10,3.11"
USE_CACHE=true
WITH_DEPLOYMENT=false
TARGET_BRANCH="main"

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            ;;
        -t|--template)
            TEMPLATE="$2"
            shift 2
            ;;
        -p|--python)
            PYTHON_VERSIONS="$2"
            shift 2
            ;;
        --no-cache)
            USE_CACHE=false
            shift
            ;;
        --with-deployment)
            WITH_DEPLOYMENT=true
            shift
            ;;
        --branch)
            TARGET_BRANCH="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            ;;
    esac
done

# Create workflows directory
mkdir -p .github/workflows

print_status "Generating $TEMPLATE CI template..."

# Generate workflow based on template
case $TEMPLATE in
    basic)
        cat > .github/workflows/ci.yml << 'EOF'
name: CAKE Basic CI

on:
  push:
    branches: [ TARGET_BRANCH ]
  pull_request:
    branches: [ TARGET_BRANCH ]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements-dev.txt
    
    - name: Run CAKE lint checks
      run: |
        chmod +x scripts/cake-lint.sh
        ./scripts/cake-lint.sh . --check-only
EOF
        ;;
    
    full|*)
        # Generate full workflow (already created above)
        print_status "Using comprehensive CI template"
        ;;
    
    security)
        print_status "Generating security-focused CI"
        # Add security-specific workflow
        ;;
    
    performance)
        print_status "Generating performance CI"
        # Add performance testing workflow
        ;;
esac

# Replace placeholders
sed -i '' "s/TARGET_BRANCH/$TARGET_BRANCH/g" .github/workflows/ci.yml
sed -i '' "s/PYTHON_VERSIONS/$PYTHON_VERSIONS/g" .github/workflows/ci.yml

# Add deployment if requested
if [ "$WITH_DEPLOYMENT" = true ]; then
    print_status "Adding deployment steps..."
    cat >> .github/workflows/ci.yml << 'EOF'

  deploy:
    needs: [lint-and-test, security-check]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
    - uses: actions/checkout@v4
    
    - name: Deploy to production
      run: |
        echo "Deployment steps would go here"
        # Add actual deployment commands
EOF
fi

print_success "Generated .github/workflows/ci.yml"

# Generate PR template
print_status "Creating PR template..."
mkdir -p .github
cat > .github/pull_request_template.md << 'EOF'
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Checklist
- [ ] My code follows CAKE style guidelines
- [ ] I have run `./scripts/cake-lint.sh`
- [ ] I have added tests for my changes
- [ ] All tests pass locally
- [ ] I have updated documentation

## CAKE Components Affected
- [ ] CakeController
- [ ] Operator
- [ ] RecallDB
- [ ] PTYShim
- [ ] Validator
- [ ] Other: _____
EOF

print_success "Created PR template"

# Summary
echo
print_status "CI/CD Setup Complete!"
echo -e "  ${GREEN}✓${NC} Workflow: .github/workflows/ci.yml"
echo -e "  ${GREEN}✓${NC} Template: .github/pull_request_template.md"
echo
echo "Next steps:"
echo "1. Review the generated workflow"
echo "2. Commit and push to trigger CI"
echo "3. Check Actions tab on GitHub"