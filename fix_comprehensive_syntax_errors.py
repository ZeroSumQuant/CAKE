#!/usr/bin/env python3
"""
Comprehensive fix for ALL docstring syntax errors in CAKE.
This single script handles all 15 remaining syntax errors.
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple


class ComprehensiveSyntaxFixer:
    """Fixes all docstring syntax errors in one pass."""

    def __init__(self, dry_run: bool = False):
        """Initialize the fixer."""
        self.dry_run = dry_run
        self.fixed_count = 0
        self.error_count = 0

        # All known syntax errors from our analysis
        # Updated with the new errors found after first run
        self.syntax_errors = [
            # Original errors (already fixed)
            ("cake/adapters/cake_adapter.py", 236),
            ("cake/adapters/claude_orchestration.py", 768),
            ("cake/components/adaptive_confidence_engine.py", 184),
            ("cake/components/recall_db.py", 81),
            ("cake/components/semantic_error_classifier.py", 337),
            ("cake/components/snapshot_manager.py", 135),
            ("cake/components/validator.py", 320),
            ("cake/components/voice_similarity_gate.py", 152),
            ("cake/core/stage_router.py", 365),
            ("cake/core/trrdevs_engine.py", 77),
            ("cake/core/watchdog.py", 90),
            ("cake/utils/cross_task_knowledge_ledger.py", 199),
            ("cake/utils/info_fetcher.py", 444),
            ("cake/utils/rate_limiter.py", 283),
            ("cake/utils/rule_creator.py", 130),
            # New errors found after first run
            ("cake/adapters/claude_orchestration.py", 986),
            ("cake/components/adaptive_confidence_engine.py", 204),
            ("cake/components/semantic_error_classifier.py", 990),
            ("cake/components/validator.py", 620),
            ("cake/core/trrdevs_engine.py", 91),
            ("cake/core/watchdog.py", 103),
            ("cake/utils/cross_task_knowledge_ledger.py", 1035),
            ("cake/utils/info_fetcher.py", 585),
            ("cake/utils/rule_creator.py", 240),
            # Final errors found after second run
            ("cake/adapters/claude_orchestration.py", 1294),
            ("cake/components/adaptive_confidence_engine.py", 361),
            ("cake/core/trrdevs_engine.py", 137),
            ("cake/core/watchdog.py", 189),
            ("cake/utils/cross_task_knowledge_ledger.py", 1080),
            ("cake/utils/rule_creator.py", 273),
            # Last 3 errors
            ("cake/adapters/claude_orchestration.py", 1339),
            ("cake/utils/cross_task_knowledge_ledger.py", 1171),
            ("cake/utils/rule_creator.py", 652),
        ]

    def fix_all_errors(self):
        """Fix all syntax errors."""
        print(f"{'='*60}")
        print(f"Fixing {len(self.syntax_errors)} syntax errors...")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'FIXING'}")
        print(f"{'='*60}\n")

        for filepath, line_number in self.syntax_errors:
            self.fix_docstring_syntax(filepath, line_number)

        print(f"\n{'='*60}")
        print(f"SUMMARY:")
        print(f"  Fixed: {self.fixed_count}")
        print(f"  Errors: {self.error_count}")
        print(f"{'='*60}")

    def fix_docstring_syntax(self, filepath: str, line_number: int):
        """Fix a specific docstring syntax error."""
        file_path = Path(filepath)

        if not file_path.exists():
            print(f"✗ Error: {filepath} not found")
            self.error_count += 1
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"✗ Error reading {filepath}: {e}")
            self.error_count += 1
            return

        # Check line (convert to 0-based)
        idx = line_number - 1
        if idx >= len(lines):
            print(f"✗ Error: Line {line_number} out of range for {filepath}")
            self.error_count += 1
            return

        line = lines[idx]

        # Special case for assignment error
        if filepath == "cake/utils/cross_task_knowledge_ledger.py" and line_number == 1035:
            self.fix_assignment_pattern(file_path, lines, idx)
            return

        # Pattern 1: """<text>"""<code>
        # Pattern 2: """<text>"""(  <- new pattern found
        if '"""' in line:
            # Find the last occurrence of """
            last_quote_pos = line.rfind('"""')

            # Check if there's code after the closing """
            after_quotes = line[last_quote_pos + 3 :]

            # If there's non-whitespace after the quotes, we need to fix it
            if after_quotes.strip():
                # Get the indentation of the current line
                indent = len(line) - len(line.lstrip())
                indent_str = " " * indent

                # Split into docstring part and code part
                docstring_part = line[: last_quote_pos + 3]
                code_part = after_quotes.strip()

                # Check if it ends with """(
                if line.strip().endswith('"""('):
                    # Remove the ( from the docstring line
                    lines[idx] = line.rstrip()[:-1] + "\n"
                    # Add ( to next line
                    lines.insert(idx + 1, indent_str + "(\n")
                else:
                    # Normal case - code after """
                    lines[idx] = docstring_part + "\n"
                    lines.insert(idx + 1, indent_str + code_part + "\n")

                if not self.dry_run:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    print(f"✓ Fixed: {filepath}:{line_number}")
                else:
                    print(f"[DRY RUN] Would fix: {filepath}:{line_number}")

                self.fixed_count += 1
            else:
                print(f"? No fix needed: {filepath}:{line_number}")
        else:
            print(f"✗ No docstring found: {filepath}:{line_number}")
            self.error_count += 1

    def fix_assignment_pattern(self, file_path: Path, lines: List[str], idx: int):
        """Fix the special assignment pattern error."""
        line = lines[idx]

        # This is """text"""( with assignment on next line
        if line.strip().endswith('"""('):
            indent = len(line) - len(line.lstrip())
            indent_str = " " * indent

            # Remove ( from end of docstring
            lines[idx] = line.rstrip()[:-1] + "\n"

            # The next line has the tuple unpacking - add ( to it
            if idx + 1 < len(lines):
                next_line = lines[idx + 1]
                lines[idx + 1] = indent_str + "(" + next_line.lstrip()

            if not self.dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                print(f"✓ Fixed: {file_path}:{idx + 1}")
            else:
                print(f"[DRY RUN] Would fix: {file_path}:{idx + 1}")

            self.fixed_count += 1
        else:
            print(f"? Special pattern not found at line {idx + 1}")
            self.error_count += 1


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Fix all docstring syntax errors comprehensively")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be fixed without making changes"
    )
    args = parser.parse_args()

    fixer = ComprehensiveSyntaxFixer(dry_run=args.dry_run)
    fixer.fix_all_errors()


if __name__ == "__main__":
    main()
