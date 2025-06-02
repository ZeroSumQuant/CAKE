#!/usr/bin/env python3
"""Fix import issues in CAKE project systematically.
"""

import os
import re
from pathlib import Path

# Define the proper import mappings
IMPORT_MAPPINGS = {
    # Models
    "from cake.models import": "from cake.utils.models import",
    "from cake.persistence import": "from cake.utils.persistence import",
    "from cake.api import": "from cake.api import",  # Need to implement
    # Core components
    "from cake.strategist import": "from cake.core.strategist import",  # Need to implement
    "from cake.stage_router import": "from cake.core.stage_router import",
    "from cake.rule_creator import": "from cake.utils.rule_creator import",
    "from cake.rate_limiter import": "from cake.utils.rate_limiter import",
    # Components
    "from operator import": "from cake.components.operator import",
    "from recall_db import": "from cake.components.recall_db import",
    "from task_convergence_validator import": "from cake.components.validator import",
    "from cross_task_knowledge_ledger import": "from cake.components.knowledge_ledger import",
    "from snapshot_manager import": "from cake.components.snapshot_manager import",
    "from pty_shim import": "from cake.components.pty_shim import",
    "from semantic_error_classifier import": "from cake.components.semantic_error_classifier import",
    # Adapters
    "from claude_prompt_orchestration import": "from cake.adapters.claude_orchestration import",
    "from cake_adapter import": "from cake.adapters.cake_adapter import",
    "from cake_integration import": "from cake.adapters.cake_integration import",
    # Utils
    "from info_fetcher import": "from cake.utils.info_fetcher import",
    "from adaptive_confidence_system import": "from cake.utils.adaptive_confidence import",
}


def fix_imports_in_file(filepath):
    """Fix imports in a single Python file."""if not filepath.endswith(".py"):
        return False

    try:
        with open(filepath, "r") as f:
            content = f.read()

        original = content
        for old_import, new_import in IMPORT_MAPPINGS.items():
            content = content.replace(old_import, new_import)

        if content != original:
            with open(filepath, "w") as f:
                f.write(content)
            print(f"✓ Fixed imports in {filepath}")
            return True
        else:
            print(f"  No changes needed in {filepath}")
            return False

    except Exception as e:
        print(f"✗ Error fixing {filepath}: {e}")
        return False


def main():
    """Fix all imports in the project."""
    project_root = Path("/Users/dustinkirby/Documents/GitHub/CAKE")
    cake_dir = project_root / "cake"

    fixed_count = 0
    error_count = 0

    # Find all Python files
    for py_file in cake_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        if fix_imports_in_file(str(py_file)):
            fixed_count += 1

    print(f"\nFixed {fixed_count} files")

    # Also check test files
    test_file = project_root / "tests/unit/test_cake_core.py"
    if test_file.exists():
        fix_imports_in_file(str(test_file))


if __name__ == "__main__":
    main()
