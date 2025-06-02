# CAKE Repository Structure (Reorganized)

```
CAKE/
├── .flake8                         # Flake8 configuration
├── .gitignore                      # Git ignore patterns
├── .pylintrc                       # Pylint configuration
├── .venv/                          # Python virtual environment
│
├── cake/                           # CAKE implementation (currently empty)
│   ├── __init__.py
│   ├── components/                 # Core CAKE components (to be implemented)
│   │   └── __init__.py
│   ├── core/                       # Core logic (to be implemented)
│   │   └── __init__.py
│   └── utils/                      # Utilities (to be implemented)
│       └── __init__.py
│
├── workflow/                       # Claude workflow automation ⭐ NEW
│   ├── README.md                   # Comprehensive workflow documentation
│   ├── core/                       # Core workflow orchestration
│   │   ├── cake-workflow.sh        # Master workflow orchestrator
│   │   ├── cake-status.sh          # Development status checker
│   │   └── cake-fix-ci.sh          # CI failure handler
│   ├── extraction/                 # Conversation context extraction
│   │   ├── __init__.py
│   │   ├── cake-extract-context.sh # Context extraction script
│   │   └── conversation_parser.py  # NLP-based conversation parser
│   ├── documentation/              # Documentation generation
│   │   ├── cake-handoff.sh         # Handoff document generator
│   │   └── cake-create-pr.sh       # PR creation with context
│   ├── config/                     # Workflow configuration
│   │   └── workflow.yaml           # Workflow settings
│   └── test/                       # Workflow tests (TODO)
│
├── scripts/                        # CAKE development scripts (reorganized)
│   ├── README.md                   # Scripts documentation
│   ├── components/                 # Component-specific tools
│   │   ├── cake-check-voice.py    # Voice validation tool
│   │   └── cake-stub-component.py  # Component code generator
│   ├── validation/                 # Code validation tools
│   │   ├── cake-lint.sh           # Comprehensive linting
│   │   └── cake-pre-commit.sh     # Pre-commit checks
│   └── setup/                      # Setup and initialization
│       ├── cake-init.sh            # Project initializer
│       ├── cake-setup-dev.sh       # Dev environment setup
│       └── cake-generate-ci.sh     # CI/CD generator
│
├── docs/                           # Documentation
│   ├── guides/                     # Implementation guides
│   │   ├── REPOSITORY-STRUCTURE.md # Old structure (deprecated)
│   │   ├── REPOSITORY-STRUCTURE-NEW.md # This file
│   │   ├── ci-resilient-workflow.md
│   │   └── ...
│   ├── handoff/                    # Session handoff documents
│   ├── specifications/             # CAKE specifications
│   │   ├── cake-architecture-v2.md
│   │   ├── cake-components-v2.md
│   │   └── ...
│   └── task_log.md                 # Task tracking
│
├── tests/                          # Test suite
│   ├── __init__.py
│   └── unit/
│       ├── __init__.py
│       └── test_conversation_parser.py
│
├── CLAUDE.md                       # Project memory and guidelines
├── QUICK-REFERENCE.md              # Quick command reference
├── README.md                       # Project README
└── requirements-dev.txt            # Development dependencies
```

## 🎯 Key Changes in This Reorganization

### 1. **New `workflow/` Directory**
Separated Claude workflow automation from CAKE development scripts:
- **Purpose**: Automate Claude development sessions
- **Location**: Top-level directory for easy access
- **Structure**: Organized by function (core, extraction, documentation)

### 2. **Reorganized `scripts/` Directory**
Categorized CAKE development scripts by purpose:
- **components/**: Tools for building CAKE components
- **validation/**: Code quality and testing tools
- **setup/**: Initial setup and configuration

### 3. **Clear Separation of Concerns**
- **CAKE Implementation** (`/cake/`): The actual CAKE system (to be built)
- **Workflow Automation** (`/workflow/`): Tools for Claude sessions
- **Development Scripts** (`/scripts/`): Tools for building CAKE

## 🚀 Quick Start Commands

### For Claude Development Sessions
```bash
# Run the complete workflow
./workflow/core/cake-workflow.sh

# Check development status
./workflow/core/cake-status.sh

# Extract conversation context
./workflow/extraction/cake-extract-context.sh
```

### For CAKE Development
```bash
# Run linting
./scripts/validation/cake-lint.sh

# Generate a component stub
python scripts/components/cake-stub-component.py --component Operator

# Check voice similarity
python scripts/components/cake-check-voice.py --message "..."
```

## 📝 Benefits of This Structure

1. **Clarity**: Clear separation between workflow automation and CAKE development
2. **Maintainability**: Related scripts grouped together
3. **Discoverability**: Easy to find the right tool for the task
4. **Scalability**: Room to grow each category independently
5. **Documentation**: Each directory has clear purpose and README

## 🔄 Migration Notes

If you have existing scripts or references:
1. Workflow scripts moved from `/scripts/` to `/workflow/`
2. Development scripts reorganized within `/scripts/`
3. Conversation parser moved from `/cake/components/` to `/workflow/extraction/`
4. All script paths have been updated to reflect new locations

## 📋 Next Steps

1. **Test the workflow**: Run `./workflow/core/cake-workflow.sh`
2. **Update any custom scripts**: Check for hardcoded paths
3. **Review the workflow README**: See `/workflow/README.md`
4. **Start implementing CAKE components**: Use scripts in `/scripts/components/`