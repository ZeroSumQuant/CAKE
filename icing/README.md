# Icing - Repository Cleanup Tool for CAKE

Icing is a companion tool to CAKE that helps clean up Python codebases by fixing common issues like syntax errors, import problems, and formatting inconsistencies. It's designed to get your repository CI-green quickly.

## Quick Start

```bash
# Install Icing
pip install -e icing/

# Run in dry-run mode (default)
icing /path/to/your/project

# Apply changes
icing --apply /path/to/your/project
```

## Features

- **Phase 1: Syntax Fixes**
  - Remove duplicate imports and non-UTF8 characters
  - Fix control block colons (missing `:` after `if`, `for`, etc.)
  - Insert missing `pass` statements in empty blocks

- **Phase 2: Import & Formatting**
  - Deduplicate and organize imports
  - Normalize docstring style
  - Apply black and isort formatting

- **Phase 3: AST-based Fixes**
  - Detect and fix truly empty function/class bodies
  - Safe transformations that preserve code functionality

- **Phase 4: Project Organization**
  - Build manifest of all project files
  - Organize files into standard directory structure
  - Create minimal pyproject.toml if missing
  - Add stub files (__init__.py, README.md) where needed

## Scope

Icing is specifically designed for:
- Cleaning up legacy Python codebases
- Preparing projects for modern CI/CD pipelines
- Standardizing project structure
- Making codebases more maintainable

## Safety Features

- Git safety tags before any changes
- Dry-run mode by default
- AST validation after each transformation
- Automatic rollback on errors
- Preserves git history with `git mv`

## Development

See the main CAKE repository for development guidelines and contribution instructions.

## Roadmap

Future enhancements:
- Additional file type support
- Custom organization templates
- Integration with more linting tools
- Performance optimizations for large codebases

---

Icing is part of the CAKE (Claude Autonomy Kit Engine) project.