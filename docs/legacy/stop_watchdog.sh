#!/bin/bash
# Stop the Claude Watchdog

if [ -f .watchdog.pid ]; then
    PID=$(cat .watchdog.pid)
    echo "🛑 Stopping watchdog (PID: $PID)..."
    kill $PID 2>/dev/null
    rm .watchdog.pid
    rm -f WATCHDOG_ACTIVE.txt
    echo "✅ Watchdog stopped"
else
    echo "❌ No watchdog running (no .watchdog.pid file found)"
fi