#!/usr/bin/env python3
"""Master cleanup tool for CAKE - self-auditing, reversible refactor tool."""

import argparse
import ast
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)


class MasterCleanup:
    """Orchestrates phased cleanup with rollback capability."""

    def __init__(
        self,
        target_path: Path,
        dry_run: bool = True,
        auto_yes: bool = False,
        skip_git: bool = False,
        skip_shell: bool = False,
    ):
        self.target_path = target_path
        self.dry_run = dry_run
        self.auto_yes = auto_yes
        self.skip_git = skip_git or bool(os.getenv("CHATGPT_SANDBOX"))
        self.skip_shell = skip_shell or bool(os.getenv("CHATGPT_SANDBOX"))
        self.error_log = []

        # Handle single file vs directory
        if self.target_path.is_file():
            self.is_single_file = True
            self.target_files = [self.target_path]
        else:
            self.is_single_file = False
            self.target_files = None  # Will use rglob

        self.summary = {
            "start_time": datetime.now().isoformat(),
            "target_path": str(target_path),
            "dry_run": dry_run,
            "phases": [],
            "exit_code": 0,
        }

    def log(self, message: str, level=logging.INFO) -> None:
        """Log message using logging module."""
        logging.log(level, message)

    def safe_run(self, cmd: list, **kwargs) -> subprocess.CompletedProcess:
        """Run shell command unless we're in sandbox mode."""
        if self.skip_shell:
            self.log(f"💡 [dry-shell] {' '.join(str(c) for c in cmd)}")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.run(cmd, **kwargs)

    def iter_python_files(self):
        """Iterate over Python files, handling single file or directory."""
        excluded_dirs = {
            ".venv",
            "venv",
            "__pycache__",
            ".git",
            "node_modules",
            ".tox",
            ".eggs",
        }

        if self.is_single_file:
            yield from self.target_files
        else:
            for py in self.target_path.rglob("*.py"):
                # Skip if any excluded directory is in the path parts
                if not any(part in excluded_dirs for part in py.parts):
                    yield py

    def ast_safe_write(self, path: Path, content: str) -> bool:
        """Write only if AST + compile() both succeed."""
        try:
            ast.parse(content)
            compile(content, str(path), "exec")
        except Exception as exc:
            self.error_log.append(f"{path}: {exc}")
            return False
        if self.dry_run:
            self.log(f"[DRY-RUN] Would write to {path}")
            return True  # pretend success
        try:
            path.write_text(content, encoding="utf-8")
            return True
        except OSError as io_err:
            self.error_log.append(f"{path}: IO error – {io_err}")
            return False

    def validate_codebase(self, checkpoint: str) -> dict:
        """Return metrics dict; halt caller on fatal errors."""
        results = {
            "checkpoint": checkpoint,
            "timestamp": datetime.now().isoformat(),
            "parseable_files": 0,
            "syntax_errors": [],
            "test_result": None,
            "flake8_issues": 0,
        }

        # Collect all Python files
        py_files = list(self.iter_python_files())

        # Skip initial validation if repo is huge
        if checkpoint == "initial-state" and len(py_files) > 2000:
            self.log("Skipping initial validation for large repository")
            return results

        # Process all files including tests to catch all syntax errors
        for py in py_files:
            try:
                src = py.read_text(encoding="utf-8")
                ast.parse(src)
                compile(src, str(py), "exec")
                results["parseable_files"] += 1
            except Exception as e:
                results["syntax_errors"].append({"file": str(py), "error": str(e)})

        if not self.dry_run and not results["syntax_errors"]:
            # Run tests only if no syntax errors and not in dry-run
            # TODO: Consider --lite-ci flag to run AST validation even when skipping shell commands
            test_result = self.safe_run(["pytest", "-q"], capture_output=True)
            results["test_result"] = test_result.returncode

            # Run flake8
            flake8_result = self.safe_run(
                ["flake8", str(self.target_path)], capture_output=True, text=True
            )
            # Count lines or use return code as fallback
            issues = len(flake8_result.stdout.splitlines())
            if not issues and flake8_result.returncode:
                issues = -1  # sentinel for error with no output
            results["flake8_issues"] = issues

        self.summary["phases"].append(results)
        return results

    def run_phase(self, name: str, func) -> None:
        """Execute a phase with validation and optional rollback."""
        self.log(f"▶ {name}")

        # Pre-phase commit (if not dry-run)
        if not self.dry_run and not self.skip_git:
            self.safe_run(["git", "add", "-A"], check=False)
            self.safe_run(["git", "commit", "-am", f"chore: pre-{name}"], check=False)

        # Execute the phase function
        func()

        # Validate the results
        metrics = self.validate_codebase(name)

        # Check for errors (including test failures)
        if (
            metrics["syntax_errors"]
            or metrics.get("test_result") not in (None, 0)
            or metrics.get("flake8_issues", 0) > 0
        ):
            self.log(f"⛔ {name} introduced errors – rolling back")
            if metrics["syntax_errors"]:
                self.log(f"  Syntax errors: {len(metrics['syntax_errors'])}")
            if metrics.get("test_result") not in (None, 0):
                self.log("  Test failures detected")
            if metrics.get("flake8_issues", 0) > 0:
                self.log(f"  Flake8 issues: {metrics['flake8_issues']}")
                self.log("  Run 'black . && isort .' or fix manually before re-running")
            if not self.dry_run and not self.skip_git:
                self.safe_run(["git", "reset", "--hard", "HEAD^"], check=True)
            self.summary["exit_code"] = 1
            raise SystemExit(1)

        # Post-phase commit (if not dry-run and successful)
        if not self.dry_run and not self.skip_git:
            self.safe_run(["git", "add", "-A"], check=False)
            self.safe_run(["git", "commit", "-am", f"chore: apply-{name}"], check=False)

    def sanitize_obvious_corruption(self) -> None:  # noqa: C901
        """Remove duplicated imports, non-UTF8 chars, blatant junk."""
        self.log("Sanitizing obvious corruption...")
        # TODO: String-based duplicate detection may miss multi-line or aliased imports

        for py_file in self.iter_python_files():
            try:
                content = py_file.read_text(encoding="utf-8")
                original_content = content

                # Remove duplicate imports
                lines = content.split("\n")
                seen_imports = set()
                new_lines = []

                for line in lines:
                    # Check for import statements
                    if line.strip().startswith(("import ", "from ")):
                        if line.strip() not in seen_imports:
                            seen_imports.add(line.strip())
                            new_lines.append(line)
                    else:
                        new_lines.append(line)

                content = "\n".join(new_lines)

                # Remove non-UTF8 characters (replace with space)
                cleaned = content.encode("utf-8", errors="replace").decode("utf-8")
                if cleaned != content:
                    self.log(f"  • Non-UTF8 bytes replaced in {py_file}")
                content = cleaned

                # Remove trailing whitespace from each line and normalize line endings
                lines = content.splitlines()
                lines = [line.rstrip() for line in lines]
                content = "\n".join(lines)

                # Only write if changes were made
                if content != original_content:
                    if not self.ast_safe_write(py_file, content):
                        self.log(f"  ⚠️  Failed to sanitize {py_file}")
                    else:
                        self.log(f"  ✓ Sanitized {py_file}")

            except Exception as e:
                self.log(f"  ⚠️  Error processing {py_file}: {e}")
                self.error_log.append(f"{py_file}: {e}")

    def fix_control_block_colons(self) -> None:  # noqa: C901
        """Append missing : on if/for/def... lines."""
        self.log("Fixing control block colons...")

        import re

        # Control flow keywords that require colons
        control_keywords = (
            "if",
            "elif",
            "else",
            "for",
            "while",
            "try",
            "except",
            "finally",
            "with",
            "def",
            "class",
            "async",
            "match",
            "case",
        )

        # Pattern to match control statements missing colons
        # Matches lines that end without a colon (but may have comments)
        control_pattern = re.compile(
            r"^\s*(" + "|".join(control_keywords) + r")\b[^:]*\s*(#.*)?$"
        )

        for py_file in self.iter_python_files():

            try:
                lines = py_file.read_text(encoding="utf-8").splitlines()
                modified = False
                new_lines = []
                in_string = False
                string_delimiter = None

                i = 0
                while i < len(lines):
                    line = lines[i]
                    stripped = line.strip()

                    # Track multi-line strings
                    if not in_string:
                        if stripped.startswith('"""') or stripped.startswith("'''"):
                            string_delimiter = stripped[:3]
                            if stripped.count(string_delimiter) == 1:
                                in_string = True
                    else:
                        if string_delimiter in line:
                            in_string = False

                    # Skip if we're inside a string
                    if in_string:
                        new_lines.append(line)
                        i += 1
                        continue

                    # Check if this is a control line missing a colon
                    if control_pattern.match(line) and not stripped.endswith(":"):
                        new_lines.append(line.rstrip() + ":")
                        modified = True
                    else:
                        new_lines.append(line)

                    i += 1

                if modified:
                    content = "\n".join(new_lines)
                    # Ensure trailing newline
                    if content and not content.endswith("\n"):
                        content += "\n"
                    # Don't validate AST for this phase - we're fixing syntax errors!
                    if self.dry_run:
                        self.log(f"💡 [dry-run] would write fixed colons to {py_file}")
                    else:
                        py_file.write_text(content, encoding="utf-8", errors="replace")
                        self.log(f"  ✓ Fixed control block colons in {py_file}")

            except Exception as e:
                self.log(f"  ⚠️  Error processing {py_file}: {e}")
                self.error_log.append(f"{py_file}: {e}")

    def insert_missing_pass(self) -> None:  # noqa: C901
        """Insert pass into empty blocks."""
        self.log("Inserting missing pass statements...")

        import re

        # Control flow keywords that can have blocks
        block_keywords = {
            "if",
            "elif",
            "else",
            "for",
            "while",
            "try",
            "except",
            "finally",
            "with",
            "def",
            "class",
            "async",
            "match",
            "case",
        }

        # Pattern to match control statements with colons
        block_pattern = re.compile(
            r"^(\s*)"  # indentation
            r"(" + "|".join(block_keywords) + r")\b"  # keyword
            r".*:"  # anything ending with colon
            r"(\s*#.*)?$"  # optional comment
        )

        for py_file in self.iter_python_files():

            try:
                lines = py_file.read_text(encoding="utf-8").splitlines()
                modified = False
                new_lines = []

                i = 0
                while i < len(lines):
                    line = lines[i]
                    stripped = line.strip()

                    # Check if this is a block statement
                    match = block_pattern.match(line)
                    if match and stripped.endswith(":"):
                        indent = match.group(1)
                        block_indent = len(indent)
                        expected_indent = block_indent + 4  # Python standard indent

                        # Look ahead to see if block is empty
                        j = i + 1
                        found_content = False
                        comment_lines = []

                        # Scan the block for content
                        while j < len(lines):
                            next_line = lines[j]
                            next_stripped = next_line.strip()

                            # Empty line - we've reached the end of the block
                            if not next_stripped:
                                break

                            # Check indentation
                            next_indent = len(next_line) - len(next_line.lstrip())

                            # If indent is less or equal to block indent, we're outside the block
                            if next_indent <= block_indent:
                                break

                            # Line is inside the block
                            if next_stripped.startswith("#"):
                                # Comment line - save it
                                comment_lines.append(next_line)
                                j += 1
                                continue

                            # Check if it's actual content at the right indentation
                            if next_indent >= expected_indent:
                                # Check if it's already a pass statement
                                if next_stripped == "pass":
                                    found_content = True
                                elif next_stripped.startswith(('"""', "'''")):
                                    # Docstring counts as content
                                    found_content = True
                                else:
                                    # Any other content
                                    found_content = True
                            break

                        # If no content found, this is an empty block
                        if not found_content:
                            # Append the header line
                            new_lines.append(line)
                            # Append any comment lines we found
                            new_lines.extend(comment_lines)
                            # Add pass statement with proper indentation
                            pass_line = " " * expected_indent + "pass"
                            new_lines.append(pass_line)
                            modified = True
                            # Don't skip ahead - let the natural loop progression handle blank lines
                            i += (
                                len(comment_lines) + 1
                            )  # Skip past the lines we've already added
                        else:
                            # Block has content, just append the header
                            new_lines.append(line)
                            i += 1
                    else:
                        # Not a block statement, just append the line
                        new_lines.append(line)
                        i += 1

                if modified:
                    content = "\n".join(new_lines)
                    # Ensure trailing newline
                    if content and not content.endswith("\n"):
                        content += "\n"
                    if self.ast_safe_write(py_file, content):
                        self.log(f"  ✓ Inserted missing pass in {py_file}")

            except Exception as e:
                self.log(f"  ⚠️  Error processing {py_file}: {e}")
                self.error_log.append(f"{py_file}: {e}")

    def fix_imports(self) -> None:
        """One import per line, dedupe, sort obvious junk away."""
        # Placeholder for Phase 5
        self.log("Fixing imports...")

    def fix_docstrings(self) -> None:
        """Normalise triple quotes, ignore one-liners."""
        # Placeholder for Phase 6
        self.log("Fixing docstrings...")

    def fix_whitespace(self) -> None:  # noqa: C901
        """Strip trailing WS, convert tabs → 4 spaces."""
        self.log("Fixing whitespace...")

        for py_file in self.iter_python_files():
            try:
                with py_file.open(encoding="utf-8") as f:
                    lines = f.readlines()

                # Strip trailing whitespace and convert tabs
                new_lines = []
                changed = False
                for line in lines:
                    new_line = line.rstrip(" \t\r\n")
                    # Convert tabs to spaces
                    new_line = new_line.expandtabs(4)
                    # Preserve original line ending if present
                    if line.endswith("\n"):
                        new_line += "\n"
                    if new_line != line:
                        changed = True
                    new_lines.append(new_line)

                # Ensure file ends with newline
                if new_lines and not new_lines[-1].endswith("\n"):
                    new_lines[-1] += "\n"
                    changed = True

                if changed:
                    content = "".join(new_lines)
                    if self.ast_safe_write(py_file, content):
                        self.log(f"  ✓ Fixed whitespace in {py_file}")

            except Exception as e:
                self.log(f"  ⚠️  Error processing {py_file}: {e}")
                self.error_log.append(f"{py_file}: {e}")

    def run_black(self) -> None:
        """Run black formatter."""
        # Placeholder for Phase 8a
        self.log("Running black...")

    def run_isort(self) -> None:
        """Run isort formatter."""
        # Placeholder for Phase 8b
        self.log("Running isort...")

    def run(self) -> None:
        """Execute all phases in order."""
        # Check branch safety
        if not self.dry_run and not self.skip_git:
            result = self.safe_run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            current = result.stdout.strip() if result.stdout else "unknown"
            if not current.startswith("chore/cleanup"):
                self.log("⚠️  Not on a safety branch – consider aborting!")
                branch_name = "chore/cleanup-auto"
                if not self.auto_yes:
                    response = input(f"Create {branch_name} branch? [y/N]: ")
                    if response.lower() != "y":
                        self.log("Aborting - please switch to a cleanup branch first")
                        sys.exit(1)
                self.safe_run(["git", "checkout", "-b", branch_name], check=True)
                self.log(f"Created and switched to {branch_name}")

        # Create safety tag (even in dry-run)
        if not self.skip_git:
            ts = datetime.now().strftime("%Y%m%d-%H%M")
            tag_name = f"pre-cleanup-{ts}{'-dryrun' if self.dry_run else ''}"
            tag_msg = f"Safety snapshot - dry_run={self.dry_run}"
            self.safe_run(["git", "tag", "-fa", tag_name, "-m", tag_msg], check=False)
            self.log(f"Created safety tag: {tag_name}")

        # Initial validation
        self.log("Starting master cleanup...")
        initial_metrics = self.validate_codebase("initial-state")
        if initial_metrics["parseable_files"] > 0:
            self.log(
                f"Initial state: {initial_metrics['parseable_files']} parseable files, "
                f"{len(initial_metrics['syntax_errors'])} syntax errors"
            )

        # Phase execution list
        phases = [
            ("sanitize_obvious_corruption", self.sanitize_obvious_corruption),
            ("fix_control_block_colons", self.fix_control_block_colons),
            ("insert_missing_pass", self.insert_missing_pass),
            ("fix_whitespace", self.fix_whitespace),
            # Future phases will be added here
            # ("fix_imports", self.fix_imports),
            # ("fix_docstrings", self.fix_docstrings),
            # ("run_black", self.run_black),
            # ("run_isort", self.run_isort),
        ]

        # Execute phases
        for phase_name, phase_func in phases:
            self.run_phase(phase_name, phase_func)

        # Final validation
        final_metrics = self.validate_codebase("final-state")
        self.log(
            f"Final state: {final_metrics['parseable_files']} parseable files, "
            f"{len(final_metrics['syntax_errors'])} syntax errors"
        )

        # Check if we accumulated errors
        if self.error_log:
            self.summary["exit_code"] = 1
            self.log(f"⚠️  {len(self.error_log)} errors encountered during cleanup")

        # Save summary
        self.summary["end_time"] = datetime.now().isoformat()
        self.summary["error_log"] = self.error_log

        # Create reports directory
        reports_dir = Path("cleanup_reports")
        reports_dir.mkdir(exist_ok=True)

        # Save summary JSON
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        if self.summary["phases"]:
            final_checkpoint = self.summary["phases"][-1]["checkpoint"]
        else:
            final_checkpoint = "empty"
        summary_file = f"{timestamp}-{final_checkpoint}-summary.json"
        summary_path = reports_dir / summary_file
        with summary_path.open("w") as f:
            json.dump(self.summary, f, indent=2)
        self.log(f"Summary saved to {summary_path}")

        # Exit with appropriate code
        sys.exit(self.summary["exit_code"])


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Master cleanup tool for CAKE - self-auditing, reversible refactor"
    )
    parser.add_argument(
        "target",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="Target directory to clean (default: current directory)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Simulate changes (default)",
    )
    group.add_argument(
        "--apply", dest="dry_run", action="store_false", help="Write changes to disk"
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Assume yes for all prompts (CI safe)"
    )
    parser.add_argument(
        "--skip-git",
        action="store_true",
        help="Skip git operations (for sandbox/testing)",
    )
    parser.add_argument(
        "--skip-shell",
        action="store_true",
        help="Skip all shell commands (for restricted environments)",
    )

    args = parser.parse_args()

    # Safety check
    if not args.dry_run:
        if not (args.yes or sys.stdin.isatty()):
            logging.error("Apply mode requires --yes when stdin is not a TTY")
            sys.exit(2)
        if not args.yes:
            response = input(
                "⚠️  Running without dry-run will modify files. Continue? [y/N]: "
            )
            if response.lower() != "y":
                print("Aborted.")
                sys.exit(0)

    # Create and run cleanup
    cleanup = MasterCleanup(
        args.target,
        args.dry_run,
        auto_yes=args.yes,
        skip_git=args.skip_git,
        skip_shell=args.skip_shell,
    )
    try:
        cleanup.run()
    except SystemExit as e:
        sys.exit(e.code)


if __name__ == "__main__":
    main()
