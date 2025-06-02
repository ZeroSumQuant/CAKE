#!/usr/bin/env python3
"""
Fix the remaining 9 syntax errors found after the first round of fixes.
"""

import re
from pathlib import Path


class RemainingErrorFixer:
    """Fix the final batch of syntax errors."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.fixed_count = 0
        self.error_count = 0

        # Remaining errors identified
        self.remaining_errors = [
            ("cake/adapters/claude_orchestration.py", 986),
            ("cake/components/adaptive_confidence_engine.py", 204),
            ("cake/components/semantic_error_classifier.py", 990),
            ("cake/components/validator.py", 620),
            ("cake/core/trrdevs_engine.py", 91),
            ("cake/core/watchdog.py", 103),
            ("cake/utils/cross_task_knowledge_ledger.py", 1035),
            ("cake/utils/info_fetcher.py", 585),
            ("cake/utils/rule_creator.py", 240),
        ]

    def fix_all(self):
        """Fix all remaining errors."""
        print(f"Fixing {len(self.remaining_errors)} remaining syntax errors...")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'FIXING'}\n")

        for filepath, line_number in self.remaining_errors:
            if filepath == "cake/utils/cross_task_knowledge_ledger.py" and line_number == 1035:
                # Special case - different error pattern
                self.fix_assignment_error(filepath, line_number)
            else:
                self.fix_docstring_parenthesis(filepath, line_number)

        print(f"\nSummary: Fixed {self.fixed_count}, Errors {self.error_count}")

    def fix_docstring_parenthesis(self, filepath: str, line_number: int):
        """Fix docstring followed immediately by parenthesis."""
        file_path = Path(filepath)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            idx = line_number - 1
            if idx >= len(lines):
                print(f"✗ Line {line_number} out of range for {filepath}")
                self.error_count += 1
                return

            line = lines[idx]

            # Pattern: """text"""(
            if '"""' in line and line.strip().endswith('"""('):
                # Remove the ( from the end
                lines[idx] = line.rstrip()[:-1] + "\n"
                # Add ( to the next line with proper indentation
                indent = len(line) - len(line.lstrip())
                lines.insert(idx + 1, " " * indent + "(\n")

                if not self.dry_run:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    print(f"✓ Fixed: {filepath}:{line_number}")
                else:
                    print(f"[DRY RUN] Would fix: {filepath}:{line_number}")

                self.fixed_count += 1
            else:
                print(f"? Pattern not found: {filepath}:{line_number}")
                self.error_count += 1

        except Exception as e:
            print(f"✗ Error processing {filepath}: {e}")
            self.error_count += 1

    def fix_assignment_error(self, filepath: str, line_number: int):
        """Fix the assignment error in cross_task_knowledge_ledger.py."""
        file_path = Path(filepath)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            idx = line_number - 1
            if idx >= len(lines):
                print(f"✗ Line {line_number} out of range for {filepath}")
                self.error_count += 1
                return

            line = lines[idx]

            # This appears to be """Convert..."""( pattern
            if '"""' in line and line.strip().endswith('"""('):
                # Remove the ( from the end
                lines[idx] = line.rstrip()[:-1] + "\n"
                # The next line should have the tuple unpacking
                if idx + 1 < len(lines):
                    next_line = lines[idx + 1]
                    # Add proper spacing
                    indent = len(line) - len(line.lstrip())
                    lines[idx + 1] = " " * indent + "(" + next_line.lstrip()

                if not self.dry_run:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    print(f"✓ Fixed: {filepath}:{line_number}")
                else:
                    print(f"[DRY RUN] Would fix: {filepath}:{line_number}")

                self.fixed_count += 1
            else:
                print(f"? Pattern not found: {filepath}:{line_number}")
                self.error_count += 1

        except Exception as e:
            print(f"✗ Error processing {filepath}: {e}")
            self.error_count += 1


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fix remaining syntax errors")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()

    fixer = RemainingErrorFixer(dry_run=args.dry_run)
    fixer.fix_all()


if __name__ == "__main__":
    main()
