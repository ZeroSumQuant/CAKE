# Changelog

All notable changes to CAKE will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- PROCESS.md documenting the development methodology
- CONTRIBUTING.md with contribution guidelines
- Additional README badges for professionalism
- MIT License

## [0.9.0-beta] - 2025-06-05

### Added
- Icing tool extraction as standalone package
- Comprehensive CI/CD pipeline with quality gates
- Bad Claude Simulator for adversarial testing
- Voice similarity validation (≥90% match required)
- Performance benchmarks and requirements
- Handoff documentation system

### Changed
- Migrated legacy scripts to docs/legacy/
- Applied Black/isort formatting across codebase
- Reorganized test structure
- Enhanced error classification system

### Fixed
- All syntax errors across the codebase
- Import organization and circular dependencies
- CI pipeline reliability issues

## [0.8.0-alpha] - 2025-05-15

### Added
- Core CAKE components (Controller, Operator, RecallDB, etc.)
- PTYShim for command interception
- Watchdog for real-time monitoring
- Workflow automation scripts
- Initial test suite

### Security
- Command blocking for dangerous operations
- Snapshot system for state preservation
- Audit logging for all interventions

## [0.7.0-dev] - 2025-04-30

### Added
- Initial project structure
- Basic component scaffolding
- Architecture documentation
- Development guides

[Unreleased]: https://github.com/ZeroSumQuant/CAKE/compare/v0.9.0-beta...HEAD
[0.9.0-beta]: https://github.com/ZeroSumQuant/CAKE/compare/v0.8.0-alpha...v0.9.0-beta
[0.8.0-alpha]: https://github.com/ZeroSumQuant/CAKE/compare/v0.7.0-dev...v0.8.0-alpha
[0.7.0-dev]: https://github.com/ZeroSumQuant/CAKE/releases/tag/v0.7.0-dev