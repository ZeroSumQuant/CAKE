# CAKE Scripts Guide

This directory contains the essential scripts for CAKE development workflow.

## Primary Scripts (The ones you need)

### 1. Full Workflow Automation
```bash
./workflow/core/cake-workflow.sh
```
- Runs the complete development workflow
- Includes: lint, auto-fix, commit, handoff generation, PR creation
- Modes: `interactive` (default), `auto`, `status`
- This is the main script that orchestrates everything

### 2. Standalone Linting
```bash
./scripts/validation/cake-lint.sh
```
- Run code quality checks without the full workflow
- Options: `--check-only` (no auto-fix), `--verbose`, `--all`
- Use when you just want to check code quality

### 3. Syntax Error Fixer
```bash
python ./scripts/fix-all-syntax-errors.py
```
- Fixes all E999 syntax errors automatically
- Consolidates all syntax fixing logic
- Options: `--check` (dry run), `--verbose`

## Quick Start

For daily development, you typically only need:

```bash
# Fix any syntax errors first
python scripts/fix-all-syntax-errors.py

# Run the full workflow (includes everything)
./workflow/core/cake-workflow.sh auto

# Or just check code quality
./scripts/validation/cake-lint.sh
```

## Script Locations

- **Workflow Scripts**: `workflow/core/`
  - cake-workflow.sh (main orchestrator)
  - cake-status.sh (check status)
  - cake-fix-ci.sh (fix CI issues)

- **Validation Scripts**: `scripts/validation/`
  - cake-lint.sh (code quality)
  - cake-pre-commit.sh (git hooks)

- **Fix Scripts**: `scripts/`
  - fix-all-syntax-errors.py (consolidated syntax fixer)

## Legacy Scripts to Remove

The following individual fix scripts have been consolidated:
- fix_all_docstrings.py
- fix_comprehensive_syntax_errors.py
- fix_docstring_comments.py
- fix_docstring_indentation.py
- fix_imports.py
- fix_inline_docstrings.py
- fix_remaining_syntax_errors.py
- fix_final_syntax_errors.py
- etc.
EOF < /dev/null