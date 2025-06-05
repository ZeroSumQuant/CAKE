# CAKE - Claude Autonomy Kit Engine

[![CI Status](https://github.com/ZeroSumQuant/CAKE/actions/workflows/ci.yml/badge.svg)](https://github.com/ZeroSumQuant/CAKE/actions/workflows/ci.yml)
[![Development Status](https://img.shields.io/badge/status-alpha-orange.svg)](https://github.com/ZeroSumQuant/CAKE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/ZeroSumQuant/CAKE/blob/main/LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://makeapullrequest.com)

**CAKE** is a deterministic intervention system that monitors LLM operations, prevents known failure patterns, and enforces safety guardrails without human escalation.

**Icing** is an optional refactoring tool that helps keep Python repositories CI-green by fixing syntax errors, organizing imports, and standardizing project structure. See [icing/README.md](icing/README.md) for details.

> **Note**: CAKE is under active development. We're using an innovative adversarial LLM pair programming approach for rapid prototyping. See [PROCESS.md](docs/PROCESS.md) for our development methodology.

## 🎯 Overview

CAKE acts as an autonomous "operator" that watches, intervenes, and recovers from errors in real-time. It's designed to achieve **zero-escalation autonomy** - resolving all failures without paging humans.

## 📁 Repository Layout

```
├── cake/         # Main CAKE application code
├── icing/        # Repository cleanup helper (pip install -e icing/)
├── tests/        # Test suite for CAKE
├── docs/         # Documentation and specifications
├── scripts/      # Utility scripts and tools
├── .github/      # CI/CD workflows
└── README.md     # This file
```

## 🏗️ Architecture

CAKE uses a single-process, component-based architecture:

- **CakeController**: Central state machine orchestrator
- **Operator**: Intervention message generator (matches Dustin's voice style)
- **RecallDB**: Error pattern memory store
- **PTYShim**: Command interceptor for safety
- **Validator**: Error classifier
- **Watchdog**: Stream monitor for error detection

See [cake-architecture-v2.md](cake-architecture-v2.md) for detailed architecture documentation.

## 🧪 Testing with Bad Claude

CAKE includes a comprehensive testing framework called "Bad Claude Simulator" that intentionally makes mistakes to validate our safety systems. Bad Claude helps test:

- Dangerous command blocking
- Repeat error detection
- CI/CD safety violations
- Anti-pattern recognition
- And much more!

See [tests/bad_claude_simulator/](tests/bad_claude_simulator/) for the mischievous testing framework.

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Git

### Setup

1. Clone the repository:
```bash
git clone https://github.com/ZeroSumQuant/CAKE.git
cd CAKE
```

2. Create virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements-dev.txt
```

4. Run quality checks:
```bash
./scripts/cake-lint.sh scripts/
```

## 🛠️ Development

### Essential Scripts

- **cake-lint.sh**: Comprehensive linting (black, isort, flake8, mypy, bandit, safety)
- **cake-check-voice.py**: Validates Operator messages match intervention style
- **cake-handoff.sh**: Auto-generates handoff documentation
- **cake-stub-component.py**: Generates component code from specifications

### Code Quality

All code must pass strict quality checks:
```bash
./scripts/cake-lint.sh .              # Run all checks
./scripts/cake-lint.sh . --check-only  # CI mode (no auto-fix)
```

### Testing

```bash
pytest tests/ -v --cov=cake
```

## 📚 Documentation

- [CLAUDE.md](CLAUDE.md) - Project memory and guidelines
- [cake-architecture-v2.md](cake-architecture-v2.md) - System architecture
- [cake-components-v2.md](cake-components-v2.md) - Component specifications
- [cake-testing-v2.md](cake-testing-v2.md) - Testing requirements
- [cake-roadmap-v2.md](cake-roadmap-v2.md) - Development roadmap

## 🤝 Contributing

1. Create a feature branch
2. Run `./scripts/cake-lint.sh` before committing
3. Ensure all tests pass
4. Submit a pull request

## 📄 License

[License information to be added]

## 🙏 Acknowledgments

Built with Claude Code assistance.