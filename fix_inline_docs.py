#!/usr/bin/env python3
"""Fix inline docstrings where code follows triple quotes on same line."""

from pathlib import Path


def fix_inline_docstrings(filepath: str) -> int:
    """Fix all inline docstrings in a file. Returns count of fixes."""
    file_path = Path(filepath)
    if not file_path.exists():
        print(f"Error: {filepath} not found")
        return 0

    # Read the file
    with open(file_path, "r") as f:
        lines = f.readlines()

    fixed_lines = []
    fix_count = 0

    for i, line in enumerate(lines):
        # Check if line contains """ followed by more content
        stripped = line.strip()
        if '"""' in line:
            # Find positions of triple quotes
            first_quote = line.find('"""')
            second_quote = line.find('"""', first_quote + 3)

            # If we found two sets of triple quotes
            if second_quote != -1:
                # Check if there's code after the closing quotes
                after_quotes = line[second_quote + 3 :].strip()
                if after_quotes and after_quotes[0].isalpha():
                    # Get indentation
                    indent = line[:first_quote]
                    # Get docstring part
                    docstring_part = line[first_quote : second_quote + 3]
                    # Split into two lines
                    fixed_lines.append(indent + docstring_part + "\n")
                    fixed_lines.append(indent + after_quotes + "\n")
                    fix_count += 1
                    print(f"  Fixed line {i+1}: {stripped[:60]}...")
                else:
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)

    if fix_count > 0:
        # Write back to file
        with open(file_path, "w") as f:
            f.writelines(fixed_lines)
        print(f"Fixed {fix_count} inline docstrings in {filepath}")

    return fix_count


def main():
    """Fix all inline docstrings in the project."""
    print("Fixing inline docstring syntax errors...\n")

    # Find all Python files with potential issues
    files_to_check = [
        "cake/adapters/cake_adapter.py",
        "cake/adapters/cake_integration.py",
        "cake/adapters/claude_orchestration.py",
        "cake/components/adaptive_confidence_engine.py",
        "cake/components/operator.py",
        "cake/components/recall_db.py",
        "cake/components/semantic_error_classifier.py",
        "cake/components/snapshot_manager.py",
        "cake/components/validator.py",
        "cake/components/voice_similarity_gate.py",
        "cake/core/cake_controller.py",
        "cake/core/escalation_decider.py",
        "cake/core/pty_shim.py",
        "cake/core/stage_router.py",
        "cake/core/trrdevs_engine.py",
        "cake/core/watchdog.py",
        "cake/utils/cross_task_knowledge_ledger.py",
        "cake/utils/info_fetcher.py",
        "cake/utils/rate_limiter.py",
        "cake/utils/rule_creator.py",
    ]

    total_fixes = 0
    for filepath in files_to_check:
        fixes = fix_inline_docstrings(filepath)
        total_fixes += fixes

    print(f"\nTotal fixes: {total_fixes}")


if __name__ == "__main__":
    main()
