# Claude Watchdog System

## Overview
The Claude Watchdog is a **MANDATORY** background monitoring system that prevents Claude from making common mistakes during CAKE development.

## 🔴 MANDATORY STARTUP PROCEDURE
Every CAKE session MUST begin with:
```bash
cd /Users/dustinkirby/Documents/GitHub/CAKE
./start_watchdog.sh
```

## How It Works

### 1. **Background Monitoring**
- Runs silently checking every 5 seconds
- Monitors file creation patterns
- Watches command history
- Scans error logs

### 2. **Intervention System**
When a mistake is detected, the watchdog:
1. Creates a `CLAUDE_STOP.txt` file
2. This file appears in Claude's directory listing
3. Contains specific instructions on what went wrong
4. Auto-deletes after 30 seconds

### 3. **Patterns It Catches**

#### Multiple Fix Scripts
- **Trigger**: Creating 3+ `fix_*.py` scripts
- **Why**: Claude tends to fix errors one-by-one instead of comprehensively
- **Intervention**: "Collect ALL errors first, then create ONE fix!"

#### Wrong Interpreter
- **Trigger**: `python3 something.sh`
- **Why**: Running bash scripts with Python
- **Intervention**: "Use bash script.sh"

#### Hidden File Miss
- **Trigger**: "No such file" errors with venv/env
- **Why**: Forgetting that .venv is hidden
- **Intervention**: "Use find . -name 'activate' -type f"

#### Bare LS Command
- **Trigger**: Using `ls` without flags
- **Why**: Missing hidden directories
- **Intervention**: "Use ls -la to see hidden files"

## File Structure

```
claude_watchdog.py      # Main watchdog script
start_watchdog.sh       # Startup script (MANDATORY)
stop_watchdog.sh        # Cleanup script
WATCHDOG_ACTIVE.txt     # Indicator that watchdog is running
claude_watchdog.log     # Watchdog activity log
CLAUDE_STOP.txt         # Intervention file (appears on errors)
.watchdog.pid           # Process ID for cleanup
```

## Example Intervention

When Claude makes a mistake, this appears:

```
╔══════════════════════════════════════════════════════════════╗
║                    🛑 CLAUDE INTERVENTION 🛑                 ║
╚══════════════════════════════════════════════════════════════╝

❌ STOP! You're running a bash script with Python!
Use: bash script.sh

Detected at: 2025-06-02 15:30:00
Pattern: wrong_interpreter
Details: Command: python3 cake-lint.sh

This file will auto-delete after you read it.
╚══════════════════════════════════════════════════════════════╝
```

## Stopping the Watchdog

To stop (only when session ends):
```bash
./stop_watchdog.sh
```

## Why This Is Mandatory

1. **Prevents Repeated Mistakes**: Claude has consistent patterns of errors
2. **Real-Time Feedback**: Interventions appear immediately
3. **Learning Reinforcement**: Seeing the same interventions helps Claude remember
4. **Efficiency**: Prevents wasted time on wrong approaches

## Troubleshooting

### Watchdog won't start
- Check if already running: `ps aux | grep claude_watchdog`
- Check log: `tail claude_watchdog.log`

### Interventions not appearing
- Verify watchdog is active: `ls WATCHDOG_ACTIVE.txt`
- Check PID: `cat .watchdog.pid`

### Too many interventions
- Adjust patterns in `claude_watchdog.py`
- Increase check interval (default 5s)

## Integration with CAKE

This watchdog demonstrates CAKE's philosophy:
- **Autonomous monitoring** (no human needed)
- **Deterministic interventions** (same mistake = same response)
- **Pattern learning** (recognizes repeated errors)
- **Zero escalation** (handles issues without paging humans)