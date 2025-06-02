#!/bin/bash
# cake-extract-context.sh - Extract and parse conversation context for accurate documentation
# This script extracts conversation context and creates structured data for other scripts

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PATH="$PROJECT_ROOT/.venv"
OUTPUT_DIR="$PROJECT_ROOT/.cake/conversation-context"
TODAY=$(date +%Y-%m-%d)

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

# Activate virtual environment if it exists
if [ -d "$VENV_PATH" ] && [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
else
    echo "Warning: Virtual environment not found at $VENV_PATH"
    echo "Make sure claude-conversation-extractor is installed"
    exit 1
fi

# Extract recent conversation
CONVERSATION_RAW="$OUTPUT_DIR/conversation-${TODAY}.raw"
CONVERSATION_JSON="$OUTPUT_DIR/conversation-${TODAY}.json"

echo "Extracting conversation context..."
claude-extract --recent 1 > "$CONVERSATION_RAW" 2>&1

# Parse conversation and extract structured data
python3 - <<EOF > "$CONVERSATION_JSON"
import json
import re
import sys
from pathlib import Path

# Read the raw conversation
raw_file = Path("${CONVERSATION_RAW}").read_text()

# Structure to extract
context = {
    "date": "${TODAY}",
    "tasks_discussed": [],
    "decisions_made": [],
    "problems_solved": [],
    "files_modified": [],
    "testing_notes": [],
    "future_work": [],
    "key_insights": [],
    "commands_run": [],
    "errors_encountered": []
}

# Parse patterns from conversation
lines = raw_file.split('\n')
current_speaker = None

for line in lines:
    # Identify speaker
    if line.startswith('Human:'):
        current_speaker = 'human'
        continue
    elif line.startswith('Assistant:'):
        current_speaker = 'assistant'
        continue
    
    if not line.strip():
        continue
    
    # Extract files mentioned
    file_patterns = re.findall(r'(?:created?|modified?|updated?|edit(?:ed)?)\s+[`"]?([/\w.-]+\.\w+)[`"]?', line, re.I)
    context['files_modified'].extend(file_patterns)
    
    # Extract commands
    if '```bash' in line or 'cd ' in line or './' in line:
        cmd_match = re.search(r'(?:```bash\s*\n)?([^`]+)(?:```)?', line)
        if cmd_match and current_speaker == 'assistant':
            context['commands_run'].append(cmd_match.group(1).strip())
    
    # Extract task-related phrases
    if current_speaker == 'human':
        if any(word in line.lower() for word in ['need to', 'let\'s', 'we should', 'create', 'implement']):
            context['tasks_discussed'].append(line.strip())
    
    # Extract decisions
    if 'decided to' in line.lower() or 'will use' in line.lower() or 'let\'s go with' in line.lower():
        context['decisions_made'].append(line.strip())
    
    # Extract problems/errors
    if 'error' in line.lower() or 'failed' in line.lower() or 'issue' in line.lower():
        context['errors_encountered'].append(line.strip())
    
    # Extract insights
    if any(phrase in line.lower() for phrase in ['the key', 'important', 'note that', 'remember']):
        context['key_insights'].append(line.strip())

# Deduplicate lists
for key in context:
    if isinstance(context[key], list):
        context[key] = list(dict.fromkeys(context[key]))[:10]  # Keep top 10 unique

print(json.dumps(context, indent=2))
EOF

echo "Context extraction complete: $CONVERSATION_JSON"