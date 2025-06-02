#!/usr/bin/env python3
"""Fix docstring indentation issues where code after docstring is not properly indented."""

from pathlib import Path

# Files with indentation issues after docstrings
FILES_TO_FIX = [
    ("cake/adapters/cake_integration.py", 73, 74),
    ("cake/adapters/cake_adapter.py", 174, 175),
    ("cake/components/adaptive_confidence_engine.py", 127, 128),
    ("cake/components/snapshot_manager.py", 57, 58),
    ("cake/components/recall_db.py", 50, 51),
    ("cake/components/validator.py", 151, 152),
    ("cake/core/cake_controller.py", 86, 87),
    ("cake/core/trrdevs_engine.py", 59, 60),
    ("cake/components/voice_similarity_gate.py", 119, 120),
    ("cake/core/escalation_decider.py", 82, 83),
    ("cake/components/operator.py", 176, 177),
    ("cake/core/watchdog.py", 76, 77),
    ("cake/utils/info_fetcher.py", 67, 68),
]


def fix_indentation(filepath: str, docstring_line: int, code_line: int) -> bool:
    """Fix indentation of code line after docstring."""
    file_path = Path(filepath)
    if not file_path.exists():
        print(f"Error: {filepath} not found")
        return False

    # Read the file
    with open(file_path, "r") as f:
        lines = f.readlines()

    # Check if line numbers are valid
    if code_line > len(lines) or docstring_line > len(lines):
        print(f"Error: Line numbers out of range for {filepath}")
        return False

    # Get the docstring line to determine indentation
    doc_idx = docstring_line - 1
    doc_line = lines[doc_idx]

    # Calculate expected indentation (same as the function definition)
    # Look backwards for the function definition
    func_indent = 0
    for i in range(doc_idx - 1, max(0, doc_idx - 10), -1):
        if lines[i].strip().startswith("def "):
            func_indent = len(lines[i]) - len(lines[i].lstrip())
            break

    # Expected indentation for code inside function
    expected_indent = func_indent + 4

    # Check the code line
    code_idx = code_line - 1
    if code_idx < len(lines):
        code = lines[code_idx]
        current_indent = len(code) - len(code.lstrip())

        # If indentation is wrong, fix it
        if current_indent != expected_indent and code.strip():
            lines[code_idx] = " " * expected_indent + code.lstrip()

            # Write back to file
            with open(file_path, "w") as f:
                f.writelines(lines)

            print(f"Fixed: {filepath}:{code_line} (indent: {current_indent} -> {expected_indent})")
            return True

    print(f"No fix needed: {filepath}:{code_line}")
    return False


def main():
    """Fix all indentation issues."""
    print("Fixing docstring indentation issues...\n")

    fixed_count = 0
    for filepath, doc_line, code_line in FILES_TO_FIX:
        if fix_indentation(filepath, doc_line, code_line):
            fixed_count += 1

    print(f"\nSummary: Fixed {fixed_count}/{len(FILES_TO_FIX)} files")


if __name__ == "__main__":
    main()
