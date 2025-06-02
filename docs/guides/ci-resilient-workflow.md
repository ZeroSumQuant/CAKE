# CI-Resilient CAKE Development Workflow

## Overview
This workflow ensures graceful handling of CI/CD failures with automatic recovery mechanisms and comprehensive status tracking throughout the development lifecycle.

## Key Components

### 1. cake-workflow.sh - Master Orchestrator
The main entry point that guides you through the entire development workflow.

**Features:**
- Interactive and automatic modes
- Step-by-step guidance
- Automatic failure recovery
- Smart decision making in auto mode

**Usage:**
```bash
./scripts/cake-workflow.sh              # Interactive mode (default)
./scripts/cake-workflow.sh auto         # Fully automatic mode
./scripts/cake-workflow.sh status       # Just show status
```

### 2. cake-status.sh - Comprehensive Status Checker
Shows the complete state of your development environment.

**Tracks:**
- Git repository status (branch, commits, uncommitted files)
- Code quality status (last lint run)
- Documentation status (handoff, task log, conversation context)
- PR status (number, state, reviews)
- CI/CD status (all checks with pass/fail indicators)
- Workflow health score
- Suggested next actions

**Usage:**
```bash
./scripts/cake-status.sh
```

### 3. cake-fix-ci.sh - Automatic CI Failure Handler
Intelligently handles CI failures with automatic fixes where possible.

**Capabilities:**
- Detects specific CI failure types
- Applies automatic fixes for:
  - Linting issues (black, isort)
  - Simple type errors
  - Security warnings (when safe)
- Saves detailed logs for manual fixes
- Updates PR with fix information
- Monitors CI status after fixes

**Usage:**
```bash
./scripts/cake-fix-ci.sh              # Attempt fixes and exit
./scripts/cake-fix-ci.sh --monitor    # Fix and monitor until pass
```

## Complete Development Flow

### Standard Happy Path
```bash
# 1. Make your changes with Claude
# ... coding session ...

# 2. Run the complete workflow
./scripts/cake-workflow.sh

# This will:
# - Check status
# - Commit changes (if needed)
# - Run linting
# - Generate documentation
# - Create/update PR
# - Monitor CI
# - Handle any failures
```

### When CI Fails
```bash
# 1. Automatic recovery
./scripts/cake-fix-ci.sh --monitor

# 2. If automatic fixes aren't enough
# - Check logs in .cake/ci-logs/
# - Make manual fixes
# - Run workflow again
./scripts/cake-workflow.sh
```

## Failure Handling Strategies

### 1. Linting Failures
- **Automatic**: black and isort formatting
- **Manual Required**: Complex flake8 issues, type annotations
- **Logs**: `.cake/ci-logs/flake8-remaining-issues.txt`

### 2. Type Checking Failures
- **Automatic**: None (too risky)
- **Manual Required**: Add type annotations
- **Logs**: `.cake/ci-logs/mypy-issues.txt`

### 3. Test Failures
- **Automatic**: None
- **Manual Required**: Fix failing tests
- **Logs**: `.cake/ci-logs/test-failures.txt`

### 4. Security Issues
- **Automatic**: None (security fixes need review)
- **Manual Required**: Review and fix security issues
- **Logs**: `.cake/ci-logs/bandit-report.json`, `safety-report.json`

## CI Fix Tracking

When `cake-fix-ci.sh` runs, it:

1. **Creates Fix Context**: `.cake/conversation-context/ci-fix-{date}-{pr}.json`
2. **Updates PR Description**: Adds a "CI Fix Applied" section
3. **Commits Changes**: With detailed commit message about fixes
4. **Saves All Logs**: In `.cake/ci-logs/` for debugging

Example PR update:
```markdown
## CI Fix Applied - 2025-06-02 10:30

### Failures Addressed
- lint-and-test (3.9)
- lint-and-test (3.10)

### Automatic Fixes
- Formatted code with black
- Sorted imports with isort

### Status
- 🔄 Fixes pushed - waiting for CI to re-run
- 📋 Fix logs available in `.cake/ci-logs/`
```

## Workflow Health Monitoring

The `cake-status.sh` script provides a health score (0-100) based on:

- Number of uncommitted files
- Commits ahead of main
- Age of last lint run
- PR review status
- CI check status

Health indicators:
- **90-100**: Excellent - Everything is clean and up to date
- **70-89**: Good - Minor issues to address
- **Below 70**: Needs Attention - Multiple issues accumulating

## Best Practices

1. **Use the Workflow Script**: Instead of individual commands, use `cake-workflow.sh` for guided execution

2. **Monitor Health**: Run `cake-status.sh` regularly to catch issues early

3. **Fix CI Immediately**: When CI fails, run `cake-fix-ci.sh` right away while context is fresh

4. **Review Fix Logs**: Even when automatic fixes work, review the logs to understand what changed

5. **Keep PRs Small**: Smaller PRs = fewer CI issues = easier fixes

## Integration with Conversation Context

All CI fixes are tracked alongside conversation context:

```
.cake/
├── conversation-context/
│   ├── conversation-2025-06-02.json      # Original conversation
│   └── ci-fix-2025-06-02-123.json       # CI fix attempts
└── ci-logs/
    ├── ci-failure-2025-06-02-123.json   # CI failure details
    ├── flake8-remaining-issues.txt      # Unfixed lint issues
    └── test-failures.txt                # Test failure details
```

This creates a complete audit trail of:
- What was discussed (conversation)
- What was implemented (commits)
- What failed (CI logs)
- How it was fixed (fix context)

## Emergency Commands

If the workflow gets stuck:

```bash
# Force status check
./scripts/cake-status.sh

# Check PR directly
gh pr view

# Check CI directly  
gh pr checks

# View recent runs
gh run list --limit 5

# Cancel stuck CI
gh run cancel [run-id]

# Close and reopen PR (last resort)
gh pr close
gh pr reopen
```

## Future Enhancements

Potential improvements to make the workflow even more resilient:

1. **Auto-retry flaky tests**: Detect and retry intermittent failures
2. **Dependency updates**: Automatically update dependencies when security issues found
3. **Rollback mechanism**: Automatically revert commits that consistently fail CI
4. **Learning system**: Track which fixes work for which errors over time
5. **Parallel CI fix**: Run multiple fix strategies concurrently