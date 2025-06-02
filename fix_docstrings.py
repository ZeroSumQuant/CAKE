#!/usr/bin/env python3
"""Fix D212 docstring violations - multi-line docstrings should start on first line."""
import re
import sys
from pathlib import Path


def fix_docstrings(content: str) -> str:
    """Fix multi-line docstrings to start on the first line."""  # Pattern to match docstrings that violate D212
    # Matches:
    # '''
    # Text here
    # or
    # """
    # Text here
    pattern = r'([ \t]*)("""|\'\'\')(\n)([ \t]*)(.*?)(\n[ \t]*\2)'

    def replacer(match):
        indent = match.group(1)
        quotes = match.group(2)
        # Skip the newline after opening quotes
        inner_indent = match.group(4)
        content = match.group(5)
        closing = match.group(6)

        # If content is empty or just whitespace, leave as is
        if not content.strip():
            return match.group(0)

        # Return fixed version - content on same line as opening quotes
        return f"{indent}{quotes}{content}{closing}"

    # Fix the pattern
    fixed = re.sub(pattern, replacer, content, flags=re.MULTILINE | re.DOTALL)

    # Also fix module-level docstrings at the start of files
    # Pattern for module docstrings
    module_pattern = r'^(#!/usr/bin/env python3\n)?("""|\'\'\')(\n)(.*?)(\n\2)'

    def module_replacer(match):
        shebang = match.group(1) or ""
        quotes = match.group(2)
        content = match.group(4)
        closing = match.group(5)

        if not content.strip():
            return match.group(0)

        return f"{shebang}{quotes}{content}{closing}"

    fixed = re.sub(module_pattern, module_replacer, fixed, count=1, flags=re.MULTILINE | re.DOTALL)

    return fixed


def main():
    """Process all Python files to fix docstrings."""
    # Get all Python files
    root = Path("/Users/dustinkirby/Documents/GitHub/CAKE")
    python_files = list(root.glob("**/*.py"))

    # Exclude virtual environment and cache
    python_files = [
        f for f in python_files if ".venv" not in str(f) and "__pycache__" not in str(f)
    ]

    fixed_count = 0

    for file_path in python_files:
        try:
            content = file_path.read_text()
            fixed_content = fix_docstrings(content)

            if content != fixed_content:
                file_path.write_text(fixed_content)
                print(f"Fixed: {file_path}")
                fixed_count += 1

        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
