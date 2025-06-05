# Contributing to CAKE

Thank you for your interest in contributing to CAKE! This document provides guidelines and instructions for contributing.

## Development Process

We use an adversarial pair programming approach with LLMs for rapid development and hardening. See [PROCESS.md](PROCESS.md) for details.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone git@github.com:YOUR_USERNAME/CAKE.git`
3. Create a feature branch: `git checkout -b feature/your-feature-name`
4. Start the watchdog: `./start_watchdog.sh` (if available)
5. Make your changes
6. Run quality checks (see below)
7. Submit a pull request

## Quality Standards

All code must pass these checks before submission:

```bash
# Format code
black . && isort .

# Lint
flake8 && mypy .

# Security scan
bandit -r cake/ -ll && safety check

# Run tests
pytest --cov=cake --cov-report=term-missing
```

### Performance Requirements

- Detection latency: <100ms
- Command validation: <50ms
- RecallDB queries: <10ms for 10k records
- Message generation: 100 messages in ≤0.3s

### Voice Consistency

Operator messages must maintain ≥90% similarity to Dustin's intervention style:
- Format: `"Operator (CAKE): Stop. {action}. {reference}."`
- Use approved verbs: Run, Check, Fix, Try, See
- Maximum 3 sentences per intervention

## Code Style

- Follow PEP 8 with Black formatting
- Use type hints for all functions
- Write comprehensive docstrings
- Maintain >90% test coverage

## Testing

- Write unit tests for all new functionality
- Include integration tests for component interactions
- Test dangerous command blocking
- Verify performance benchmarks

## Documentation

- Update relevant documentation
- Add docstrings to all public functions
- Include examples in docstrings
- Update CHANGELOG.md (if present)

## Pull Request Process

1. Ensure all quality checks pass
2. Update documentation as needed
3. Add tests for new functionality
4. Create a PR with a clear description
5. Reference any related issues

## Commit Messages

Follow Conventional Commits format:
- `feat(component): add new feature`
- `fix(validator): resolve edge case`
- `docs(readme): update installation steps`
- `test(recall): add integration tests`
- `perf(controller): optimize state transitions`

## Questions?

Feel free to open an issue for any questions about contributing.