#!/bin/bash
# cake-extract-context-simple.sh - Simplified version for testing

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
OUTPUT_DIR="$PROJECT_ROOT/.cake/conversation-context"
TODAY=$(date +%Y-%m-%d)

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

# Output files
CONVERSATION_JSON="$OUTPUT_DIR/conversation-${TODAY}.json"

# Use the existing conversation file
CONVERSATION_FILE="/Users/dustinkirby/Desktop/Claude logs/claude-conversation-2025-06-02-1ea90363.md"

if [ ! -f "$CONVERSATION_FILE" ]; then
    echo "Error: Conversation file not found: $CONVERSATION_FILE"
    exit 1
fi

echo "Parsing conversation from: $CONVERSATION_FILE"

# Run the parser directly
if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
else
    PYTHON_BIN="python3"
fi

export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"
"$PYTHON_BIN" -m workflow.extraction.conversation_parser "$CONVERSATION_FILE" -o "$CONVERSATION_JSON"

echo "Context extracted to: $CONVERSATION_JSON"

# Show summary
echo ""
echo "Summary of extracted context:"
"$PYTHON_BIN" -c "
import json
with open('$CONVERSATION_JSON') as f:
    data = json.load(f)
    print(f'Tasks: {len(data.get(\"tasks\", []))}')
    print(f'Decisions: {len(data.get(\"decisions\", []))}')
    print(f'Files: {len(data.get(\"files_modified\", []))}')
    print(f'Commands: {len(data.get(\"commands_run\", []))}')
"