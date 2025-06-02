#!/bin/bash
# A script that could be run periodically to check Claude's recent actions

echo "🔍 Checking Claude's recent commands for common mistakes..."

# Check bash history for problematic patterns
if history | tail -20 | grep -E "^ls\s*$"; then
    echo "⚠️ WARNING: Found 'ls' without -la flag in recent commands!"
    echo "Hidden files won't show! Use: ls -la"
fi

if history | tail -20 | grep -E "python[3]?\s+.*\.sh"; then
    echo "❌ ERROR: Found Python trying to run bash scripts!"
    echo "Use bash for .sh files!"
fi

# Check for repeated failed commands
if history | tail -20 | grep -c "No such file" > 3; then
    echo "🔄 PATTERN: Multiple 'No such file' errors detected"
    echo "Are you looking for hidden files? Try: ls -la"
fi

echo "✅ Check complete"