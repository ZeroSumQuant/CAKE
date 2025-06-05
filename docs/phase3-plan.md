# Phase 3: Import & Docstring Cleanup Plan

## Overview
Phase 3 builds on the syntax fixes from Phase 2 to handle more complex code organization tasks:
- Import deduplication and sorting
- Docstring normalization
- Global formatting pass
- AST-based empty body sweep
- **Skip binary/generated directories**: migrations/, proto/, static/, __pycache__, etc.

## Implementation Tasks

### 1. `fix_imports()` - Import Cleanup
**Goal**: One import per line, deduplicated, sorted, with unused imports removed.

**Approach**:
- Use AST to parse and understand imports
- Split multi-imports (`import a, b, c` → separate lines)
- **Duplicate strategy**: Keep first occurrence, drop subsequent duplicates
- Preserve comments (including `# noqa`) with their imports
- Group imports by type (stdlib, third-party, local)
- Use `isort.api.sort_code()` for in-memory sorting
- Optional: Remove unused imports with autoflake

**Edge Cases**:
- Star imports (`from x import *`)
- Aliased imports (`import foo as bar`)
- Relative imports (`from . import x`)
- Side-effect imports (must preserve even if "unused")
- `# noqa` comments must travel with their import line

### 2. `fix_docstrings()` - Docstring Normalization
**Goal**: Consistent triple-quote style and proper indentation.

**Approach**:
- Use tokenize stream to find STRING tokens that are docstrings
- Normalize quote style (prefer `"""` over `'''`)
- Fix indentation for multi-line docstrings
- Convert one-line docstrings >72 chars to multi-line format
- Ensure closing quotes on their own line for multi-line
- **Skip .pyi stub files and raw strings (r""")**

**Edge Cases**:
- Raw docstrings (r""") - preserve as-is
- Docstrings with embedded quotes
- Module-level vs function-level vs class-level docstrings
- Type stub files (.pyi) - skip entirely

### 3. `run_black()` and `run_isort()` - Global Formatting
**Goal**: Apply black and isort to entire codebase.

**Approach**:
- **Skip entirely if `--dry-run` or `--skip-shell`** (avoids sandbox prompts)
- Shell out to black with project config
- Shell out to isort with project config
- Only run with `--apply` flag
- Capture and report any files that fail

**Implementation**:
```python
if not (self.dry_run or self.skip_shell):
    self.safe_run(["black", str(self.target_path)])
    self.safe_run(["isort", str(self.target_path)])
```

**Edge Cases**:
- Files with syntax errors (skip them)
- Very large files (may need timeout)
- Files excluded by .gitignore

### 4. `ast_empty_body_sweep()` - Final Safety Net
**Goal**: Catch any empty bodies that Phase 2 heuristics missed.

**Approach**:
- Full AST parse of each file
- Find any node with empty body
- Insert pass statement if missing
- More robust than regex-based approach

**Implementation**:
```python
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        if not node.body:
            inject_pass(node)
```

**Edge Cases**:
- Abstract methods (may need special handling)
- Protocol methods
- Ellipsis (`...`) as body
- Dynamically generated code blocks (fail gracefully)

## Test Strategy

### Unit Tests
- Test each transformation in isolation
- Cover edge cases listed above
- Ensure transformations are idempotent

### Integration Tests
- Run all phases in sequence
- Verify no syntax errors introduced
- Check that files remain functionally equivalent

### Performance Tests
- Ensure reasonable performance on large codebases
- Set timeouts for each phase

## Success Criteria
- All imports properly organized
- All docstrings consistently formatted
- Zero syntax errors after all transformations
- Existing tests still pass
- Performance within acceptable bounds (<5 min for 1000 files)

## Rollback Plan
- Git safety tag before running
- Each phase in separate commit
- Ability to skip phases with flags