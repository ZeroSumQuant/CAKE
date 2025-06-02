#!/bin/bash
# Start the Claude Watchdog in background

echo "🐕 Starting Claude Watchdog..."

# Create a visible marker file
cat > WATCHDOG_ACTIVE.txt << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║               🐕 CLAUDE WATCHDOG IS ACTIVE 🐕                ║
╚══════════════════════════════════════════════════════════════╝

The watchdog is monitoring for these patterns:
- Multiple fix scripts (collect errors first!)
- Running bash scripts with Python
- Missing hidden directories (.venv)
- Using 'ls' without -la flag

If you make these mistakes, a CLAUDE_STOP.txt file will appear!

To stop watchdog: ./stop_watchdog.sh
╚══════════════════════════════════════════════════════════════╝
EOF

# Start the watchdog in background
python3 claude_watchdog.py >> claude_watchdog.log 2>&1 &
WATCHDOG_PID=$!

# Save PID for stopping later
echo $WATCHDOG_PID > .watchdog.pid

echo "✅ Watchdog started with PID: $WATCHDOG_PID"
echo "📋 Log file: claude_watchdog.log"
echo "🛑 To stop: ./stop_watchdog.sh"