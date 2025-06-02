# CAKE Workflow Automation

This directory contains the Claude workflow automation system - a comprehensive set of tools for managing development sessions with Claude Code, extracting conversation context, and automating documentation and PR creation.

## 🎯 Purpose

The workflow automation system serves a different purpose than the CAKE implementation scripts:

- **CAKE Scripts** (`/scripts/`): Tools for building CAKE itself (linting, testing, component generation)
- **Workflow Scripts** (`/workflow/`): Tools for automating Claude development sessions (context extraction, documentation, PR creation)

## 📁 Directory Structure

```
workflow/
├── core/                    # Core workflow orchestration
│   ├── cake-workflow.sh    # Master orchestrator
│   ├── cake-status.sh      # Development status checker
│   └── cake-fix-ci.sh      # CI failure handler
│
├── extraction/             # Conversation context extraction
│   ├── cake-extract-context.sh    # Main extraction script
│   └── conversation_parser.py     # NLP-based parser
│
├── documentation/          # Documentation generation
│   ├── cake-handoff.sh    # Session handoff generator
│   └── cake-create-pr.sh  # PR creation with context
│
├── config/                 # Configuration files
│   └── workflow.yaml      # Workflow settings (TODO)
│
└── test/                   # Workflow tests (TODO)
```

## 🚀 Quick Start

### Basic Workflow

1. **Start a development session with Claude**
2. **Make changes to the codebase**
3. **Run the workflow orchestrator**:
   ```bash
   ./workflow/core/cake-workflow.sh
   ```

This will automatically:
- Check current development status
- Commit changes if needed
- Run linting
- Generate documentation (handoff + task log)
- Create/update PR with context
- Monitor CI and fix issues

### Workflow Modes

```bash
# Interactive mode (default) - prompts for each step
./workflow/core/cake-workflow.sh

# Automatic mode - runs all steps without prompting
./workflow/core/cake-workflow.sh auto

# Status only - just shows current state
./workflow/core/cake-workflow.sh status
```

## 📊 Core Components

### 1. Workflow Orchestrator (`cake-workflow.sh`)

The master script that coordinates the entire development workflow:

- **Interactive Mode**: Guides through each step with prompts
- **Auto Mode**: Runs everything automatically
- **Smart Recovery**: Handles failures gracefully

**Key Features:**
- Step-by-step execution with status tracking
- Automatic failure recovery
- Integration with all other workflow tools

### 2. Status Checker (`cake-status.sh`)

Comprehensive development environment status:

```
🔍 CAKE Development Status
├── Git Status (branch, commits, changes)
├── Code Quality (last lint run)
├── Documentation (handoff, task log)
├── PR Status (number, state, CI checks)
└── Workflow Health Score (0-100)
```

### 3. CI Failure Handler (`cake-fix-ci.sh`)

Intelligent CI failure recovery:

- Detects specific failure types
- Applies automatic fixes for:
  - Linting issues (black, isort)
  - Simple formatting problems
- Saves detailed logs for manual fixes
- Updates PR with fix information

### 4. Context Extractor (`cake-extract-context.sh`)

Extracts Claude conversation context for documentation:

- Uses `claude-conversation-extractor` package
- Falls back between NLP parser and regex parser
- Outputs structured JSON for other tools

### 5. NLP Conversation Parser (`conversation_parser.py`)

Advanced conversation analysis using spaCy:

- **Deterministic**: Same input → same output
- **Extracts**: Tasks, decisions, problems/solutions, files, commands
- **Performance**: Handles 500+ messages in <5 seconds
- **Accuracy**: Uses semantic analysis, not just regex

### 6. Handoff Generator (`cake-handoff.sh`)

Creates comprehensive handoff documents:

- Current development status
- Tasks completed in session
- Problems solved
- Next steps
- Attached conversation context

### 7. PR Creator (`cake-create-pr.sh`)

Creates pull requests with full context:

- Extracts meaningful commit messages
- Includes conversation context
- Links to handoff documents
- Handles GitHub CLI integration

## 🔧 Configuration

### Environment Requirements

- Python 3.11+ with virtual environment
- Git configured with SSH
- GitHub CLI (`gh`) authenticated
- `claude-conversation-extractor` installed

### Dependencies

```bash
# Activate virtual environment
source .venv/bin/activate

# Install required packages
pip install claude-conversation-extractor spacy mistune

# Download spaCy model
python -m spacy download en_core_web_sm
```

### Workflow Configuration (TODO)

Future configuration via `workflow/config/workflow.yaml`:

```yaml
workflow:
  mode: interactive  # or 'auto'
  
extraction:
  use_nlp_parser: true
  conversation_paths:
    - "/Users/dustinkirby/Desktop/Claude logs"
    
documentation:
  include_full_conversation: true
  
ci:
  auto_fix_enabled: true
  monitor_timeout: 300
```

## 🧪 Testing

### Manual Testing

1. **Test extraction**:
   ```bash
   ./workflow/extraction/cake-extract-context.sh
   ```

2. **Test status**:
   ```bash
   ./workflow/core/cake-status.sh
   ```

3. **Test full workflow**:
   ```bash
   ./workflow/core/cake-workflow.sh
   ```

### Automated Tests (TODO)

Future test suite in `workflow/test/`:
- Unit tests for each component
- Integration tests for full workflow
- Mock tests for external dependencies

## 🐛 Troubleshooting

### Common Issues

1. **"claude-extract: command not found"**
   ```bash
   pip install claude-conversation-extractor
   ```

2. **"spacy model not found"**
   ```bash
   python -m spacy download en_core_web_sm
   ```

3. **"gh: command not found"**
   ```bash
   # Install GitHub CLI: https://cli.github.com/
   ```

4. **Parser falls back to regex**
   - Check spaCy installation
   - Verify conversation format
   - Check logs in `.cake/conversation-context/`

### Debug Mode

Run with debug output:
```bash
bash -x ./workflow/core/cake-workflow.sh
```

## 📈 Workflow Health Metrics

The status checker provides a health score (0-100) based on:

- Number of uncommitted files
- Commits ahead of main
- Age of last lint run  
- PR review status
- CI check status

**Health Indicators:**
- 90-100: Excellent - Everything clean
- 70-89: Good - Minor issues
- <70: Needs Attention - Multiple issues

## 🔄 Integration Points

### With CAKE Development

- Uses `/scripts/cake-lint.sh` for code quality
- Reads from `/docs/` for documentation
- Updates `.cake/` directories for state

### With External Tools

- `claude-conversation-extractor`: For conversation export
- `gh` CLI: For GitHub operations
- `git`: For version control

## 🎯 Future Enhancements

1. **Configuration Management**: YAML-based settings
2. **Plugin System**: Custom workflow steps
3. **Metrics Dashboard**: Workflow analytics
4. **Auto-Learning**: Improve parser over time
5. **Parallel Execution**: Speed improvements

## 📝 Contributing

When adding new workflow components:

1. Place in appropriate subdirectory
2. Update this README
3. Add tests in `workflow/test/`
4. Ensure integration with orchestrator
5. Document configuration options

---

*The workflow automation system is designed to make Claude development sessions more productive by automating repetitive tasks and maintaining context across sessions.*