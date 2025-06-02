# 🍰 CAKE Quick Reference - Dustin's Cheat Sheet

## Most Common Commands (90% of the time)

### When you're done coding for the day:
```bash
./scripts/cake-lint.sh --create-pr
```
This one command:
- ✅ Runs all linting and fixes what it can
- ✅ Generates handoff documentation
- ✅ Updates task log
- ✅ Creates PR with full context

### To check what's going on:
```bash
./scripts/cake-status.sh
```
Shows everything: branch, commits, PR status, CI status, what to do next

### If CI fails on your PR:
```bash
./scripts/cake-fix-ci.sh --monitor
```
Attempts to fix common CI issues and watches until it passes

## Other Useful Commands

### Just want to lint?
```bash
./scripts/cake-lint.sh scripts/    # Lint and auto-fix scripts
./scripts/cake-lint.sh             # Lint cake/ directory (default)
```

### Need a handoff doc?
```bash
./scripts/cake-handoff.sh          # Creates handoff + updates task log
```

### Check if a message sounds like you:
```bash
./scripts/cake-check-voice.py --message "Operator (CAKE): Stop. Run tests. See output."
```

### Generate component stub:
```bash
./scripts/cake-stub-component.py --component Operator --output cake/components/operator.py
```

### Full guided workflow:
```bash
./scripts/cake-workflow.sh         # Interactive mode
./scripts/cake-workflow.sh auto    # Just do everything
```

## Quick Status Checks

**Am I ready to push?**
```bash
./scripts/cake-status.sh | grep "Uncommitted"
```

**Is my PR passing CI?**
```bash
gh pr checks
```

**What's left to implement?**
```bash
gh issue list --label "priority:critical"
```

## The "Oh Shit" Commands

**CI is broken and I don't know why:**
```bash
gh run view            # See the actual error
./scripts/cake-fix-ci.sh
```

**I need to see what I discussed with Claude:**
```bash
ls -la docs/handoff/conversation-*-full.md
# Pick the one you want and read it
```

**I forgot what I was doing:**
```bash
cat docs/task_log.md | tail -30
```

## Remember:
- Scripts auto-activate the venv (you don't need to)
- Everything important is in `./scripts/`
- When in doubt: `./scripts/cake-status.sh`
- The answer is usually: `./scripts/cake-lint.sh --create-pr`

---
*For when Dustin forgets how his own tools work* 🤷‍♂️