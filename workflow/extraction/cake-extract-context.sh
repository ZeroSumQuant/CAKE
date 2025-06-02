#!/bin/bash
# cake-extract-context.sh - Extract and parse conversation context for accurate documentation
# This script extracts conversation context and creates structured data for other scripts

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
WORKFLOW_DIR="$(dirname "$SCRIPT_DIR")"
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
CONVERSATION_MD="$OUTPUT_DIR/conversation-${TODAY}.md"
CONVERSATION_JSON="$OUTPUT_DIR/conversation-${TODAY}.json"

echo "Extracting conversation context..."

# First extract to get the filename
EXTRACT_OUTPUT=$(claude-extract --recent 1 2>&1)
echo "$EXTRACT_OUTPUT" > "$CONVERSATION_RAW"

# Parse the output to find the saved file
SAVED_FILE=$(echo "$EXTRACT_OUTPUT" | grep -oE 'claude-conversation-[0-9-]+\.md' | head -1)

if [ -n "$SAVED_FILE" ]; then
    # Look for the file in common locations
    POSSIBLE_PATHS=(
        "/Users/dustinkirby/Desktop/Claude logs/$SAVED_FILE"
        "/Users/dustinkirby/Desktop/Claude_logs/$SAVED_FILE"
        "/Users/dustinkirby/Desktop/$SAVED_FILE"
        "./$SAVED_FILE"
    )
    
    FOUND_FILE=""
    for path in "${POSSIBLE_PATHS[@]}"; do
        if [ -f "$path" ]; then
            FOUND_FILE="$path"
            break
        fi
    done
    
    if [ -n "$FOUND_FILE" ]; then
        echo "Found conversation at: $FOUND_FILE"
        # Copy the full conversation
        cp "$FOUND_FILE" "$CONVERSATION_MD"
        
        # Also copy to handoff directory for permanent record
        HANDOFF_DIR="$PROJECT_ROOT/docs/handoff"
        if [ -d "$HANDOFF_DIR" ]; then
            CONVERSATION_COPY="$HANDOFF_DIR/conversation-${TODAY}-full.md"
            cp "$FOUND_FILE" "$CONVERSATION_COPY"
            echo "Copied full conversation to: $CONVERSATION_COPY"
        fi
    else
        echo "Warning: Could not find extracted file: $SAVED_FILE"
        echo "Using raw extraction output instead"
        cp "$CONVERSATION_RAW" "$CONVERSATION_MD"
    fi
else
    echo "Warning: Could not parse extraction output"
    echo "Using raw extraction output instead"
    cp "$CONVERSATION_RAW" "$CONVERSATION_MD"
fi

# Check if we should use the new NLP parser or fall back to regex
USE_NLP_PARSER=false

# Check if spacy is installed
if python3 -c "import spacy" 2>/dev/null; then
    # Check if the model is installed
    if python3 -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null; then
        USE_NLP_PARSER=true
        echo "Using NLP-based conversation parser..."
    else
        echo "spaCy model not found. Installing en_core_web_sm..."
        python3 -m spacy download en_core_web_sm || {
            echo "Failed to install spaCy model. Falling back to regex parser."
        }
        # Try again
        if python3 -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null; then
            USE_NLP_PARSER=true
            echo "Using NLP-based conversation parser..."
        fi
    fi
else
    echo "spaCy not found. Falling back to regex-based parser."
    echo "For better results, install: pip install spacy mistune"
fi

if [ "$USE_NLP_PARSER" = true ]; then
    # Use the new NLP parser
    echo "Running NLP parser..."
    if [ -f "$VENV_PATH/bin/python" ]; then
        PYTHON_BIN="$VENV_PATH/bin/python"
    else
        PYTHON_BIN="python3"
    fi
    
    # Run parser (should complete in a few seconds)
    env PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH" "$PYTHON_BIN" -m workflow.extraction.conversation_parser "$CONVERSATION_MD" -o "$CONVERSATION_JSON" || {
        echo "NLP parser failed. Falling back to regex parser..."
        USE_NLP_PARSER=false
    }
fi

# Fall back to regex parser if needed
if [ "$USE_NLP_PARSER" = false ]; then
    echo "Using regex-based parser..."
    python3 - <<EOF > "$CONVERSATION_JSON"
import json
import re
import sys
from pathlib import Path

# Read the conversation file
try:
    raw_file = Path("${CONVERSATION_MD}").read_text()
except:
    print(json.dumps({"error": "Could not read conversation file", "date": "${TODAY}"}))
    sys.exit(0)

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
message_buffer = []
in_code_block = False

def clean_message(msg):
    # Remove markdown formatting and clean up
    msg = re.sub(r'^\s*[-*]\s+', '', msg)  # Remove bullet points
    msg = re.sub(r'`([^`]+)`', r'\1', msg)  # Remove inline code markers
    return msg.strip()

for i, line in enumerate(lines):
    # Track code blocks to avoid parsing code as conversation
    if '```' in line:
        in_code_block = not in_code_block
        continue
        
    # Skip if we're inside a code block
    if in_code_block:
        continue
    
    # Identify speaker (handle markdown format)
    if line.startswith('## 👤 User') or line.startswith('Human:'):
        # Process previous message buffer
        if message_buffer and current_speaker == 'human':
            full_message = ' '.join(message_buffer)
            # Extract tasks from user messages
            if any(phrase in full_message.lower() for phrase in ['we need to', 'let\'s', 'we should', 'can you', 'please create', 'implement']):
                cleaned = clean_message(full_message)
                if len(cleaned) > 20 and len(cleaned) < 300:  # Reasonable length
                    context['tasks_discussed'].append(cleaned)
        
        current_speaker = 'human'
        message_buffer = []
        continue
        
    elif line.startswith('## 🤖 Assistant') or line.startswith('## 🤖 Claude') or line.startswith('Assistant:'):
        # Process previous message buffer
        if message_buffer and current_speaker == 'assistant':
            full_message = ' '.join(message_buffer)
            # Extract what was implemented/decided
            if any(phrase in full_message.lower() for phrase in ['i\'ve created', 'i\'ve implemented', 'let\'s create', 'i\'ll create']):
                cleaned = clean_message(full_message)
                if len(cleaned) > 20 and len(cleaned) < 300:
                    context['decisions_made'].append(cleaned)
        
        current_speaker = 'assistant'
        message_buffer = []
        continue
    
    # Skip empty lines and separators
    if not line.strip() or line.strip() == '---':
        continue
    
    # Accumulate message content
    if current_speaker and not line.startswith('#'):
        message_buffer.append(line)
    
    # Extract specific patterns regardless of speaker
    
    # Files modified/created
    file_patterns = re.findall(r'(?:created?|modified?|updated?|edit(?:ed)?)\s+[`"]?([/\w.-]+\.\w+)[`"]?', line, re.I)
    if file_patterns:
        context['files_modified'].extend(file_patterns)
    
    # Problems solved (look for "fixed", "resolved", "solved")
    if current_speaker == 'assistant' and any(word in line.lower() for word in ['fixed', 'resolved', 'solved', 'issue']):
        if 'CI' in line or 'error' in line.lower() or 'fail' in line.lower():
            cleaned = clean_message(line)
            if len(cleaned) > 20:
                context['problems_solved'].append(cleaned)
    
    # Key insights and important notes
    if any(phrase in line.lower() for phrase in ['the key', 'important:', 'note:', 'this ensures', 'this creates']):
        cleaned = clean_message(line)
        if len(cleaned) > 30 and len(cleaned) < 200:
            context['key_insights'].append(cleaned)
    
    # Commands run (in assistant context)
    if current_speaker == 'assistant' and ('./scripts/' in line or 'cake-' in line):
        cmd_match = re.search(r'(\./scripts/cake-[\w-]+\.sh[^`\s]*)', line)
        if cmd_match:
            context['commands_run'].append(cmd_match.group(1))

# Deduplicate lists
for key in context:
    if isinstance(context[key], list):
        context[key] = list(dict.fromkeys(context[key]))[:10]  # Keep top 10 unique

# Add message count
context['message_count'] = len([line for line in lines if line.strip()])
context['has_content'] = len(context.get('tasks_discussed', [])) > 0 or len(context.get('decisions_made', [])) > 0

print(json.dumps(context, indent=2))
EOF
fi

echo "Context extraction complete: $CONVERSATION_JSON"