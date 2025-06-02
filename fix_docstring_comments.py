#!/usr/bin/env python3
"""
Fix docstring syntax errors where comments follow closing triple quotes.
"""

import re
from pathlib import Path

# Files with docstring + comment on same line
FILES_TO_FIX = [
    ("cake/components/operator.py", 148),
    ("cake/components/operator.py", 203),
    ("cake/components/operator.py", 239),
    ("cake/components/operator.py", 255),
    ("cake/components/operator.py", 276),
    ("cake/components/operator.py", 292),
    ("cake/components/operator.py", 308),
    ("cake/components/operator.py", 326),
    ("cake/components/operator.py", 335),
    ("cake/components/operator.py", 355),
    ("cake/components/operator.py", 375),
    ("cake/components/operator.py", 393),
    ("cake/components/operator.py", 403),
    ("cake/components/operator.py", 422),
    ("cake/components/operator.py", 458),
    ("cake/components/operator.py", 464),
    ("cake/components/operator.py", 487),
    ("cake/components/operator.py", 503),
    ("cake/components/operator.py", 523),
    ("cake/components/operator.py", 551),
    ("cake/components/operator.py", 574),
    ("cake/components/operator.py", 594),
    ("cake/components/operator.py", 614),
    ("cake/components/operator.py", 639),
    ("cake/components/operator.py", 670),
    ("cake/components/operator.py", 712),
    ("cake/components/operator.py", 723),
    ("cake/components/operator.py", 740),
    ("cake/adapters/cake_integration.py", 85),
    ("cake/adapters/cake_integration.py", 103),
    ("cake/adapters/cake_integration.py", 145),
    ("cake/adapters/cake_integration.py", 174),
    ("cake/adapters/cake_integration.py", 179),
    ("cake/adapters/cake_integration.py", 199),
    ("cake/adapters/cake_integration.py", 252),
    ("cake/adapters/cake_integration.py", 283),
    ("cake/adapters/cake_integration.py", 287),
    ("cake/adapters/cake_integration.py", 291),
    ("cake/core/cake_controller.py", 110),
    ("cake/core/cake_controller.py", 135),
    ("cake/core/cake_controller.py", 154),
    ("cake/core/cake_controller.py", 205),
    ("cake/core/cake_controller.py", 218),
    ("cake/core/cake_controller.py", 230),
    ("cake/core/cake_controller.py", 248),
    ("cake/core/escalation_decider.py", 128),
    ("cake/core/escalation_decider.py", 157),
    ("cake/core/escalation_decider.py", 179),
    ("cake/core/escalation_decider.py", 199),
    ("cake/core/escalation_decider.py", 260),
    ("cake/core/escalation_decider.py", 723),
]


def fix_docstring_comment(filepath: str, line_num: int):
    """Fix a specific docstring + comment on same line."""
    file_path = Path(filepath)

    if not file_path.exists():
        print(f"Error: {filepath} not found")
        return False

    # Read file
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Check line (convert to 0-based)
    idx = line_num - 1
    if idx >= len(lines):
        print(f"Error: Line {line_num} out of range for {filepath}")
        return False

    line = lines[idx]

    # Pattern: """<spaces>#<comment>
    pattern = r'^(\s*)(""")\s*(#.*?)$'
    match = re.match(pattern, line)

    if match:
        indent = match.group(1)
        comment = match.group(3)

        # Replace with two lines
        lines[idx] = f'{indent}"""\n'
        lines.insert(idx + 1, f"{indent}{comment}\n")

        # Write back
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(f"✓ Fixed: {filepath}:{line_num}")
        return True
    else:
        print(f"? No match: {filepath}:{line_num} - {line.strip()}")
        return False


def main():
    print("Fixing docstring + comment syntax errors...")
    print("=" * 60)

    fixed = 0
    failed = 0

    for filepath, line_num in FILES_TO_FIX:
        if fix_docstring_comment(filepath, line_num):
            fixed += 1
        else:
            failed += 1

    print("=" * 60)
    print(f"Fixed: {fixed}")
    print(f"Failed: {failed}")
    print(f"Total: {len(FILES_TO_FIX)}")


if __name__ == "__main__":
    main()
