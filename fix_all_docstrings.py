#!/usr/bin/env python3
"""Fix all docstring syntax errors where closing quotes are on the same line as code."""

import re
from pathlib import Path

# Define all files and their specific line numbers with syntax errors
FILES_TO_FIX = [
    ("cake/adapters/cake_integration.py", 73),
    ("cake/adapters/cake_adapter.py", 174),
    ("cake/components/adaptive_confidence_engine.py", 127),
    ("cake/components/snapshot_manager.py", 57),
    ("cake/components/recall_db.py", 50),
    ("cake/components/validator.py", 151),
    ("cake/core/cake_controller.py", 86),
    ("cake/core/trrdevs_engine.py", 59),
    ("cake/components/voice_similarity_gate.py", 119),
    ("cake/core/escalation_decider.py", 82),
    ("cake/components/operator.py", 176),
    ("cake/core/watchdog.py", 76),
    ("cake/utils/info_fetcher.py", 67),
    ("cake/adapters/claude_orchestration.py", 650),
    ("cake/core/stage_router.py", 138),
    ("cake/utils/rule_creator.py", 56),
    ("cake/core/pty_shim.py", 199),
    ("cake/components/semantic_error_classifier.py", 292),
    ("cake/utils/rate_limiter.py", 221),
    ("cake/utils/cross_task_knowledge_ledger.py", 180),
]


def fix_docstring_in_file(filepath: str, line_number: int) -> bool:
    """Fix a specific docstring error at the given line number."""
    file_path = Path(filepath)
    if not file_path.exists():
        print(f"Error: {filepath} not found")
        return False

    # Read the file
    with open(file_path, "r") as f:
        lines = f.readlines()

    # Check if line number is valid
    if line_number > len(lines) or line_number < 1:
        print(f"Error: Line {line_number} out of range for {filepath}")
        return False

    # Get the problematic line (convert to 0-based index)
    idx = line_number - 1
    line = lines[idx].rstrip("\n")

    # Get indentation from the line
    indent = len(line) - len(line.lstrip())
    indent_str = " " * indent

    # Check various patterns
    fixed = False

    # Pattern 1: Line has """ followed by code on same line
    # e.g., """docstring"""code or """docstring""" code
    if '"""' in line:
        # Find the last occurrence of """
        last_quote_pos = line.rfind('"""')

        # Check if there's content after the last """
        if last_quote_pos != -1 and last_quote_pos + 3 < len(line):
            after_quotes = line[last_quote_pos + 3 :]
            # If there's non-whitespace content after """, split it
            if after_quotes.strip():
                docstring_part = line[: last_quote_pos + 3]
                code_part = after_quotes
                lines[idx] = docstring_part + "\n"
                lines.insert(idx + 1, indent_str + code_part.strip() + "\n")
                fixed = True

    # Pattern 2: Line contains only """ but next line has unindented code
    if not fixed and line.strip() == '"""':
        if idx + 1 < len(lines):
            next_line = lines[idx + 1]
            # If next line has content and wrong indentation
            if next_line.strip() and not next_line.startswith(indent_str):
                lines[idx + 1] = indent_str + next_line.lstrip()
                fixed = True

    if fixed:
        # Write back to file
        with open(file_path, "w") as f:
            f.writelines(lines)

        print(f"Fixed: {filepath}:{line_number}")
        return True
    else:
        print(f"No fix needed: {filepath}:{line_number}")
        print(f"  Line content: {line.strip()}")
        return False


def main():
    """Fix all docstring errors."""
    print("Fixing docstring syntax errors...\n")

    fixed_count = 0
    for filepath, line_number in FILES_TO_FIX:
        if fix_docstring_in_file(filepath, line_number):
            fixed_count += 1

    print(f"\nSummary: Fixed {fixed_count}/{len(FILES_TO_FIX)} files")


if __name__ == "__main__":
    main()
