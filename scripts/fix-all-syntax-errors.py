#!/usr/bin/env python3
"""
Comprehensive syntax error fixer for CAKE codebase.
Consolidates all syntax fixing logic into one script.

Usage:
    python fix-all-syntax-errors.py           # Fix all syntax errors
    python fix-all-syntax-errors.py --check   # Check only, don't fix
    python fix-all-syntax-errors.py --verbose # Show detailed output
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Optional


class SyntaxErrorFixer:
    """Fixes all types of syntax errors in Python code."""

    def __init__(self, verbose: bool = False, dry_run: bool = False):
        """Initialize the fixer."""
        self.verbose = verbose
        self.dry_run = dry_run
        self.fixed_count = 0
        self.error_count = 0
        self.project_root = Path(__file__).parent.parent

    def log(self, message: str, level: str = "INFO"):
        """Log a message."""
        if level == "ERROR":
            print(f"❌ {message}")
        elif level == "SUCCESS":
            print(f"✅ {message}")
        elif level == "WARNING":
            print(f"⚠️  {message}")
        elif self.verbose or level == "INFO":
            print(f"ℹ️  {message}")

    def find_syntax_errors(self) -> List[Tuple[str, int, str]]:
        """Find all E999 syntax errors using flake8."""
        self.log("Scanning for syntax errors...")

        result = subprocess.run(
            ["flake8", ".", "--extend-exclude=.venv,__pycache__", "--select=E999"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )

        errors = []
        for line in result.stdout.strip().split("\n"):
            if "E999" in line and line.strip():
                # Parse: ./path/file.py:123:45: E999 SyntaxError: description
                match = re.match(r"^(.+?):(\d+):\d+: E999 (.+)$", line)
                if match:
                    filepath = match.group(1)
                    line_num = int(match.group(2))
                    error_msg = match.group(3)
                    errors.append((filepath, line_num, error_msg))

        return errors

    def fix_docstring_syntax(self, filepath: str, line_num: int) -> bool:
        """Fix docstring syntax errors where code follows closing quotes."""
        try:
            file_path = Path(filepath)
            if not file_path.exists():
                self.log(f"File not found: {filepath}", "ERROR")
                return False

            with open(file_path, "r") as f:
                lines = f.readlines()

            if line_num > len(lines) or line_num < 1:
                self.log(f"Invalid line number {line_num} for {filepath}", "ERROR")
                return False

            # Get the problematic line (convert to 0-based index)
            idx = line_num - 1
            problem_line = lines[idx]

            # Pattern 1: """docstring"""code on same line
            if '"""' in problem_line:
                # Count quotes to find the closing one
                quote_positions = []
                for i, char in enumerate(problem_line):
                    if problem_line[i : i + 3] == '"""':
                        quote_positions.append(i)

                # If we have an even number of triple quotes and code after the last one
                if len(quote_positions) >= 2 and len(quote_positions) % 2 == 0:
                    last_quote_pos = quote_positions[-1]
                    after_quotes = problem_line[last_quote_pos + 3 :]

                    # Check if there's non-whitespace code after the quotes
                    if after_quotes.strip():
                        # Get indentation
                        indent = len(problem_line) - len(problem_line.lstrip())

                        # Split the line
                        before_and_quotes = problem_line[: last_quote_pos + 3]
                        code_after = after_quotes.lstrip()

                        if not self.dry_run:
                            # Replace the line with two lines
                            lines[idx] = before_and_quotes.rstrip() + "\n"
                            lines.insert(idx + 1, " " * indent + code_after)

                            # Write back
                            with open(file_path, "w") as f:
                                f.writelines(lines)

                        self.log(
                            f"Fixed: {filepath}:{line_num} - moved code to next line",
                            "SUCCESS",
                        )
                        return True

            # Pattern 2: Unterminated string literals
            if "unterminated string literal" in lines[idx]:
                # This is often a comment, we'll skip
                self.log(
                    f"Skipping unterminated string in comment: {filepath}:{line_num}",
                    "WARNING",
                )
                return False

            return False

        except Exception as e:
            self.log(f"Error fixing {filepath}:{line_num} - {str(e)}", "ERROR")
            return False

    def fix_indentation_error(self, filepath: str, line_num: int) -> bool:
        """Fix indentation errors."""
        try:
            file_path = Path(filepath)
            if not file_path.exists():
                return False

            with open(file_path, "r") as f:
                lines = f.readlines()

            if line_num > len(lines) or line_num < 1:
                return False

            idx = line_num - 1
            current_line = lines[idx]

            # Find the expected indentation by looking at surrounding code
            expected_indent = 0

            # Look at previous non-empty lines
            for i in range(idx - 1, -1, -1):
                prev_line = lines[i].rstrip()
                if prev_line and not prev_line.lstrip().startswith("#"):
                    # If previous line ends with :, we need one more indent level
                    if prev_line.endswith(":"):
                        expected_indent = len(lines[i]) - len(lines[i].lstrip()) + 4
                    else:
                        expected_indent = len(lines[i]) - len(lines[i].lstrip())
                    break

            # Apply the fix
            if not self.dry_run:
                lines[idx] = " " * expected_indent + current_line.lstrip()

                with open(file_path, "w") as f:
                    f.writelines(lines)

            self.log(f"Fixed: {filepath}:{line_num} - fixed indentation", "SUCCESS")
            return True

        except Exception as e:
            self.log(
                f"Error fixing indentation in {filepath}:{line_num} - {str(e)}", "ERROR"
            )
            return False

    def fix_all_errors(self) -> bool:
        """Find and fix all syntax errors."""
        errors = self.find_syntax_errors()

        if not errors:
            self.log("No syntax errors found!", "SUCCESS")
            return True

        self.log(f"Found {len(errors)} syntax errors to fix")

        if self.dry_run:
            self.log("Running in dry-run mode - no files will be modified")
            for filepath, line_num, error_msg in errors:
                self.log(f"Would fix: {filepath}:{line_num} - {error_msg}")
            return True

        # Group errors by type
        docstring_errors = []
        indentation_errors = []
        other_errors = []

        for filepath, line_num, error_msg in errors:
            if "closing parenthesis" in error_msg or "unterminated" in error_msg:
                docstring_errors.append((filepath, line_num, error_msg))
            elif (
                "unexpected indent" in error_msg
                or "expected an indented block" in error_msg
            ):
                indentation_errors.append((filepath, line_num, error_msg))
            else:
                other_errors.append((filepath, line_num, error_msg))

        # Fix docstring errors first
        if docstring_errors:
            self.log(f"\nFixing {len(docstring_errors)} docstring syntax errors...")
            for filepath, line_num, error_msg in docstring_errors:
                if self.fix_docstring_syntax(filepath, line_num):
                    self.fixed_count += 1
                else:
                    self.error_count += 1

        # Fix indentation errors
        if indentation_errors:
            self.log(f"\nFixing {len(indentation_errors)} indentation errors...")
            for filepath, line_num, error_msg in indentation_errors:
                if self.fix_indentation_error(filepath, line_num):
                    self.fixed_count += 1
                else:
                    self.error_count += 1

        # Report other errors that need manual fixing
        if other_errors:
            self.log(f"\n{len(other_errors)} errors need manual fixing:", "WARNING")
            for filepath, line_num, error_msg in other_errors:
                self.log(f"  {filepath}:{line_num} - {error_msg}")

        # Summary
        self.log(f"\nSummary: Fixed {self.fixed_count}/{len(errors)} errors")

        # Verify fixes
        remaining_errors = self.find_syntax_errors()
        if remaining_errors:
            self.log(f"{len(remaining_errors)} errors still remain", "WARNING")
            return False
        else:
            self.log("All syntax errors have been fixed!", "SUCCESS")
            return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fix all syntax errors in CAKE codebase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--check", "-c", action="store_true", help="Check only, do not fix (dry run)"
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output"
    )

    args = parser.parse_args()

    fixer = SyntaxErrorFixer(verbose=args.verbose, dry_run=args.check)
    success = fixer.fix_all_errors()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
