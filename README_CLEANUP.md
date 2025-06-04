# CAKE Master Cleanup Tool

A self-auditing, reversible refactoring tool that systematically fixes Python code issues through phased transformations.

## Features

- **Dry-run by default**: Preview all changes before applying them
- **Git integration**: Automatic safety tags and per-phase commits
- **AST validation**: Every change is validated before writing
- **Rollback capability**: Automatic rollback on validation failures
- **Audit trail**: JSON summary with metrics and error logs
- **CI/Sandbox friendly**: Supports `--skip-git` and `CHATGPT_SANDBOX` environment variable

## Getting Started

```bash
# Dry run
python scripts/master_cleanup.py --dry-run .

# Apply
python scripts/master_cleanup.py --apply .
```

## Usage

```bash
# Preview changes (default)
python scripts/master_cleanup.py

# Apply changes to current directory
python scripts/master_cleanup.py --apply

# Target specific directory
python scripts/master_cleanup.py /path/to/code --dry-run
python scripts/master_cleanup.py /path/to/code --apply

# CI-safe mode (no prompts)
python scripts/master_cleanup.py --apply --yes

# Sandbox mode (skip git operations)
python scripts/master_cleanup.py --apply --yes --skip-git
# or
CHATGPT_SANDBOX=1 python scripts/master_cleanup.py --apply --yes
```

## Safety Features

1. **Branch protection**: Warns if not on a `chore/cleanup-*` branch
2. **Safety tags**: Creates `pre-cleanup-YYYYMMDD-HHMM` tags before changes
3. **Validation**: Runs AST parse, compile, pytest, and flake8 after each phase
4. **Atomic commits**: Each phase creates pre/post commits for bisectability
5. **Audit logs**: Detailed JSON reports in `cleanup_reports/`

## Phases

| Phase | Function | Description | Status |
|-------|----------|-------------|--------|
| 1 | `sanitize_obvious_corruption()` | Remove duplicate imports, non-UTF8 chars, trailing whitespace | ✅ Implemented |
| 2 | `validate_codebase()` | AST validation checkpoint | ✅ Implemented |
| 3 | `fix_control_block_colons()` | Add missing `:` on if/for/def/etc | 🔜 Phase 2 |
| 4 | `insert_missing_pass()` | Add `pass` to empty blocks | 🔜 Phase 2 |
| 5 | `fix_imports()` | One import per line, dedupe, sort | 🔜 Phase 3 |
| 6 | `fix_docstrings()` | Normalize triple quotes | 🔜 Phase 3 |
| 7 | `fix_whitespace()` | Convert tabs to spaces, strip trailing | ✅ Implemented |
| 8 | `run_black()` | Apply black formatter | 🔜 Phase 4 |
| 9 | `run_isort()` | Sort imports with isort | 🔜 Phase 4 |

## Example Output

```bash
$ python scripts/master_cleanup.py --dry-run
[10:23:45] INFO: Starting master cleanup...
[10:23:45] INFO: Created safety tag: pre-cleanup-20250603-1023-dryrun
[10:23:45] INFO: Initial state: 157 parseable files, 3 syntax errors
[10:23:45] INFO: ▶ sanitize_obvious_corruption
[10:23:45] INFO: Sanitizing obvious corruption...
[10:23:45] INFO:   • Non-UTF8 bytes replaced in cake/legacy/parser.py
[10:23:45] INFO:   ✓ Sanitized cake/utils/helpers.py
[10:23:45] INFO: [DRY-RUN] Would write to cake/utils/helpers.py
[10:23:46] INFO: Final state: 157 parseable files, 3 syntax errors
[10:23:46] INFO: Summary saved to cleanup_reports/20250603-1023-final-state-summary.json
```

## JSON Summary Format

```json
{
  "start_time": "2025-06-03T10:23:45.123456",
  "target_path": "/Users/dustinkirby/Documents/GitHub/CAKE",
  "dry_run": true,
  "phases": [
    {
      "checkpoint": "initial-state",
      "timestamp": "2025-06-03T10:23:45.234567",
      "parseable_files": 157,
      "syntax_errors": [
        {"file": "cake/broken.py", "error": "invalid syntax"}
      ],
      "test_result": null,
      "flake8_issues": 0
    }
  ],
  "exit_code": 0,
  "end_time": "2025-06-03T10:23:46.345678",
  "error_log": []
}
```

## Requirements

- Python 3.11+
- Git
- pytest (for test validation)
- flake8 (for linting checks)
- black (for phase 8)
- isort (for phase 9)

## Development

To add a new phase:

1. Implement the phase method in `MasterCleanup` class
2. Add it to the `phases` list in `run()`
3. Update this README's phase table
4. Test with `--dry-run` first
5. Verify rollback works by intentionally breaking something

## Troubleshooting

**"Not on a safety branch"**: Switch to a branch starting with `chore/cleanup-` or let the tool create one.

**Rollback occurred**: Check the error log in the JSON summary and fix the underlying issue.

**Large repository**: Initial validation is skipped for repos with >2000 Python files to improve performance.

**Sandbox/CI mode**: Use `--skip-git` or set `CHATGPT_SANDBOX=1` to disable git operations.

## Future Enhancements

- Parallel file processing for large codebases
- Custom phase configuration via YAML
- Integration with pre-commit hooks
- Support for other languages