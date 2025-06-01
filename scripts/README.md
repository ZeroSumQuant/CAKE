# CAKE Scripts - Essential Tools Only

This directory contains CAKE-specific scripts that help implement the system based on the specification documents.

## 🎯 Essential Scripts for CAKE Development

### 1. Code Generation from Specifications
- **cake-stub-component.py** - Generates component code from cake-components-v2.md
- **cake-generate-tests.py** - Creates test files from cake-testing-v2.md
- **cake-implement-interface.py** - Implements adapters from specifications

### 2. Voice & Operator Validation (CRITICAL)
- **cake-check-voice.py** - Validates intervention messages match Dustin's style
- **cake-generate-message.py** - Creates properly formatted interventions
- **cake-train-voice.py** - Updates voice similarity model

### 3. CAKE-Specific Testing
- **cake-simulate-8hour.py** - Runs mini 8-hour autonomous test
- **cake-trace-intervention.sh** - Traces intervention flow with timing
- **cake-simulate-error.py** - Injects errors to test interventions

### 4. Spec Compliance & Validation
- **cake-validate-interface.py** - Ensures code matches specifications
- **cake-check-spec-compliance.py** - Verifies all MUST requirements

### 5. Development Workflow
- **cake-generate-issues.py** - Creates GitHub issues from specs
- **cake-check-docs-sync.py** - Verifies docs match implementation
- **cake-db-seed.py** - Seeds RecallDB with test patterns
- **cake-ready-to-ship.py** - Validates against done checklist

### 6. Development Tools (Essential Dev Helpers)
- **cake-lint.sh** - Runs all linters (black, isort, flake8, mypy, bandit)
- **cake-test.sh** - Runs tests with coverage for specific components
- **cake-pre-commit.sh** - Quick validation before commits
- **cake-benchmark.sh** - Runs performance benchmarks
- **cake-watch-tests.sh** - Auto-runs tests on file changes (TDD helper)

## 🚀 Quick Start

```bash
# Generate a component from specification
python scripts/cake-stub-component.py --component Operator

# Validate an intervention message
python scripts/cake-check-voice.py --message "Operator (CAKE): Stop. Run tests. See output."

# Check if ready to ship
python scripts/cake-ready-to-ship.py
```

## ❌ What We DON'T Need

We already have comprehensive guides, so we don't need:
- Generic project setup scripts (use the guides)
- Standard development tools (use Make, pytest, etc.)
- Generic git workflows (use standard git)
- Build/deployment scripts (defined in cake-deployment-v2.md)

## 📝 Implementation Priority

1. **First**: Voice validation scripts (critical for Operator component)
2. **Second**: Component generation from specs
3. **Third**: Testing and validation tools
4. **Last**: Workflow helpers

Each script should:
- Read from the specification documents
- Generate/validate based on CAKE requirements
- Focus on CAKE-specific needs only