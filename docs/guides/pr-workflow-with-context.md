# CAKE PR Workflow with Conversation Context

## Overview
This workflow ensures that all documentation (handoff, task log, and PR) accurately reflects the actual conversation and decisions made during development sessions with Claude.

## Workflow Components

### 1. cake-extract-context.sh
- Extracts conversation using `claude-conversation-extractor`
- Parses conversation to identify:
  - Tasks discussed
  - Decisions made
  - Problems solved
  - Files modified
  - Key insights
  - Commands run
  - Errors encountered
- Outputs structured JSON to `.cake/conversation-context/`

### 2. cake-handoff.sh (Enhanced)
- Calls `cake-extract-context.sh` first
- Uses conversation context to populate:
  - Tasks discussed section
  - Decisions made section
  - Problems solved section
  - Key insights section
- Creates traditional handoff content (git status, TODOs, etc.)
- Links to full conversation logs
- Updates task log with conversation-aware summary

### 3. cake-create-pr.sh (Enhanced)
- Loads existing conversation context from handoff
- Creates PR description with:
  - Conversation context sections
  - Traditional git changes
  - Links to all documentation
- No need to re-extract conversation (uses cached data)

## Complete Workflow

```bash
# 1. Do your work with Claude
# ... coding session ...

# 2. Run linting with handoff and PR creation
./scripts/cake-lint.sh --create-pr

# This automatically:
# - Runs all lint checks
# - If passed, generates handoff with conversation context
# - Updates task log with context
# - Creates PR with full conversation context
```

## Workflow Diagram

```
┌─────────────────────┐
│ Claude Conversation │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     ┌──────────────────┐
│  cake-lint.sh       │────▶│ Lint checks pass │
└─────────────────────┘     └────────┬─────────┘
                                     │
                                     ▼
                            ┌────────────────────┐
                            │ cake-handoff.sh    │
                            └────────┬───────────┘
                                     │
                          ┌──────────┴──────────┐
                          ▼                     ▼
                ┌─────────────────────┐ ┌──────────────────┐
                │cake-extract-context │ │ Generate Handoff │
                └────────┬────────────┘ └────────┬─────────┘
                         │                       │
                         ▼                       ▼
                ┌─────────────────┐     ┌──────────────┐
                │ conversation.json│     │ Update Task  │
                └────────┬─────────┘     │     Log      │
                         │               └──────────────┘
                         │
                         ▼
                ┌─────────────────────┐
                │ cake-create-pr.sh   │
                └────────┬────────────┘
                         │
                         ▼
                ┌─────────────────────┐
                │   GitHub PR with    │
                │  Full Context       │
                └─────────────────────┘
```

## Benefits

1. **Accuracy**: Documentation reflects actual conversation, not just code changes
2. **Context Preservation**: Decisions and rationale are captured automatically
3. **Review Quality**: PR reviewers understand the "why" not just the "what"
4. **Traceability**: Full conversation logs attached for deep review if needed
5. **Automation**: One command triggers the entire workflow

## Data Flow

1. **Conversation Extraction**
   ```
   Claude conversation → claude-extract → conversation.raw → parse → conversation.json
   ```

2. **Handoff Generation**
   ```
   conversation.json + git status + project state → handoff.md + task_log.md
   ```

3. **PR Creation**
   ```
   conversation.json + handoff.md + git diff → PR description
   ```

## Example Output

### Conversation Context in Handoff
```markdown
### Tasks Discussed in Conversation
- Create PR automation script with conversation context
- Integrate claude-conversation-extractor
- Update handoff to use conversation logs

### Decisions Made
- Use JSON format for structured conversation data
- Cache conversation context to avoid re-extraction
- Link all documents together for traceability
```

### Task Log Entry
```markdown
## 2025-06-02 - Session 1

**Time**: 10:30  
**Branch**: feat/pr-automation  
**Status**: ✅ All checks passed  
**Context**: Available

### Session Summary
- Create PR automation script with conversation context
- Integrate claude-conversation-extractor
- Update handoff to use conversation logs

### Key Decisions
- Use JSON format for structured conversation data
- Cache conversation context to avoid re-extraction
```

### PR Description
```markdown
## Conversation Context

### Tasks Discussed
- Create PR automation script with conversation context
- Integrate claude-conversation-extractor

### Key Decisions
- Use JSON format for structured conversation data
- Cache conversation context to avoid re-extraction

### Problems Solved
- Workflow was losing conversation context
- Manual PR creation was time-consuming
```

## Configuration

The workflow requires:
- `claude-conversation-extractor` installed (`pip install claude-conversation-extractor`)
- All scripts in `scripts/` directory
- `.cake/` directory for storing context
- Virtual environment activated