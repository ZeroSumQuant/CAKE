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
    level=logging.INFO
)


class MasterCleanup:
    """Orchestrates phased cleanup with rollback capability."""

    def __init__(self, target_path: Path, dry_run: bool = True,
                 auto_yes: bool = False, skip_git: bool = False):
        self.target_path = target_path
        self.dry_run = dry_run
        self.auto_yes = auto_yes
        self.skip_git = skip_git or bool(os.getenv("CHATGPT_SANDBOX"))
        self.error_log = []
        self.summary = {
            "start_time": datetime.now().isoformat(),
            "target_path": str(target_path),
            "dry_run": dry_run,
            "phases": [],
            "exit_code": 0
        }

    def log(self, message: str, level=logging.INFO) -> None:
        """Log message using logging module."""
        logging.log(level, message)

    def ast_safe_write(self, path: Path, content: str) -> bool:
        """Write only if AST + compile() both succeed."""
        try:
            ast.parse(content)
            compile(content, str(path), 'exec')
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

        # Collect all Python files, excluding certain directories
        excluded_dirs = {'.venv', 'venv', '__pycache__', '.git', 'node_modules', '.tox', '.eggs'}
        py_files = []
        for py in self.target_path.rglob("*.py"):
            # Skip if any excluded directory is in the path
            if any(excluded in py.parts for excluded in excluded_dirs):
                continue
            py_files.append(py)

        # Skip initial validation if repo is huge
        if checkpoint == "initial-state" and len(py_files) > 2000:
            self.log("Skipping initial validation for large repository")
            return results

        # Process all files including tests to catch all syntax errors
        for py in py_files:
            try:
                src = py.read_text(encoding="utf-8")
                ast.parse(src)
                compile(src, str(py), 'exec')
                results["parseable_files"] += 1
            except Exception as e:
                results["syntax_errors"].append({"file": str(py), "error": str(e)})

        if not self.dry_run and not results["syntax_errors"]:
            # Run tests only if no syntax errors and not in dry-run
            test_result = subprocess.run(["pytest", "-q"], capture_output=True)
            results["test_result"] = test_result.returncode

            # Run flake8
            flake8_result = subprocess.run(
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
            subprocess.run(["git", "add", "-A"], check=False)
            subprocess.run(["git", "commit", "-am", f"chore: pre-{name}"], check=False)

        # Execute the phase function
        func()

        # Validate the results
        metrics = self.validate_codebase(name)

        # Check for errors (including test failures)
        if (metrics["syntax_errors"]
                or metrics.get("test_result") not in (None, 0)
                or metrics.get("flake8_issues", 0) > 0):
            self.log(f"⛔ {name} introduced errors – rolling back")
            if metrics["syntax_errors"]:
                self.log(f"  Syntax errors: {len(metrics['syntax_errors'])}")
            if metrics.get("test_result") not in (None, 0):
                self.log("  Test failures detected")
            if metrics.get("flake8_issues", 0) > 0:
                self.log(f"  Flake8 issues: {metrics['flake8_issues']}")
                self.log("  Run 'black . && isort .' or fix manually before re-running")
            if not self.dry_run and not self.skip_git:
                subprocess.run(["git", "reset", "--hard", "HEAD^"], check=True)
            self.summary["exit_code"] = 1
            raise SystemExit(1)

        # Post-phase commit (if not dry-run and successful)
        if not self.dry_run and not self.skip_git:
            subprocess.run(["git", "add", "-A"], check=False)
            subprocess.run(["git", "commit", "-am", f"chore: apply-{name}"], check=False)

    def sanitize_obvious_corruption(self) -> None:  # noqa: C901
        """Remove duplicated imports, non-UTF8 chars, blatant junk."""
        self.log("Sanitizing obvious corruption...")
        # TODO: String-based duplicate detection may miss multi-line or aliased imports

        # Use same exclusion logic as validate_codebase
        excluded_dirs = {'.venv', 'venv', '__pycache__', '.git', 'node_modules', '.tox', '.eggs'}

        for py_file in self.target_path.rglob("*.py"):
            # Skip if any excluded directory is in the path
            if any(excluded in py_file.parts for excluded in excluded_dirs):
                continue
            try:
                content = py_file.read_text(encoding="utf-8")
                original_content = content

                # Remove duplicate imports
                lines = content.split('\n')
                seen_imports = set()
                new_lines = []

                for line in lines:
                    # Check for import statements
                    if line.strip().startswith(('import ', 'from ')):
                        if line.strip() not in seen_imports:
                            seen_imports.add(line.strip())
                            new_lines.append(line)
                    else:
                        new_lines.append(line)

                content = '\n'.join(new_lines)

                # Remove non-UTF8 characters (replace with space)
                cleaned = content.encode('utf-8', errors='replace').decode('utf-8')
                if cleaned != content:
                    self.log(f"  • Non-UTF8 bytes replaced in {py_file}")
                content = cleaned

                # Remove trailing whitespace from each line and normalize line endings
                lines = content.splitlines()
                lines = [line.rstrip() for line in lines]
                content = '\n'.join(lines)

                # Only write if changes were made
                if content != original_content:
                    if not self.ast_safe_write(py_file, content):
                        self.log(f"  ⚠️  Failed to sanitize {py_file}")
                    else:
                        self.log(f"  ✓ Sanitized {py_file}")

            except Exception as e:
                self.log(f"  ⚠️  Error processing {py_file}: {e}")
                self.error_log.append(f"{py_file}: {e}")

    def fix_control_block_colons(self) -> None:
        """Append missing : on if/for/def... lines."""
        # Placeholder for Phase 3
        self.log("Fixing control block colons...")

    def insert_missing_pass(self) -> None:
        """Insert pass into empty blocks."""
        # Placeholder for Phase 4
        self.log("Inserting missing pass statements...")

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

        # Use same exclusion logic
        excluded_dirs = {'.venv', 'venv', '__pycache__', '.git', 'node_modules', '.tox', '.eggs'}

        for py_file in self.target_path.rglob("*.py"):
            # Skip if any excluded directory is in the path
            if any(excluded in py_file.parts for excluded in excluded_dirs):
                continue
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
                    if line.endswith('\n'):
                        new_line += '\n'
                    if new_line != line:
                        changed = True
                    new_lines.append(new_line)

                # Ensure file ends with newline
                if new_lines and not new_lines[-1].endswith('\n'):
                    new_lines[-1] += '\n'
                    changed = True

                if changed:
                    content = ''.join(new_lines)
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
            current = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                text=True
            ).strip()
            if not current.startswith("chore/cleanup"):
                self.log("⚠️  Not on a safety branch – consider aborting!")
                branch_name = "chore/cleanup-auto"
                if not self.auto_yes:
                    response = input(f"Create {branch_name} branch? [y/N]: ")
                    if response.lower() != 'y':
                        self.log("Aborting - please switch to a cleanup branch first")
                        sys.exit(1)
                subprocess.run(["git", "checkout", "-b", branch_name], check=True)
                self.log(f"Created and switched to {branch_name}")

        # Create safety tag (even in dry-run)
        if not self.skip_git:
            ts = datetime.now().strftime("%Y%m%d-%H%M")
            tag_name = f"pre-cleanup-{ts}{'-dryrun' if self.dry_run else ''}"
            tag_msg = f"Safety snapshot - dry_run={self.dry_run}"
            subprocess.run(["git", "tag", "-fa", tag_name, "-m", tag_msg], check=False)
            self.log(f"Created safety tag: {tag_name}")

        # Initial validation
        self.log("Starting master cleanup...")
        initial_metrics = self.validate_codebase("initial-state")
        if initial_metrics["parseable_files"] > 0:
            self.log(f"Initial state: {initial_metrics['parseable_files']} parseable files, "
                     f"{len(initial_metrics['syntax_errors'])} syntax errors")

        # Phase execution list
        phases = [
            ("sanitize_obvious_corruption", self.sanitize_obvious_corruption),
            ("fix_whitespace", self.fix_whitespace),
            # Future phases will be added here
            # ("fix_control_block_colons", self.fix_control_block_colons),
            # ("insert_missing_pass", self.insert_missing_pass),
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
        self.log(f"Final state: {final_metrics['parseable_files']} parseable files, "
                 f"{len(final_metrics['syntax_errors'])} syntax errors")

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
        with summary_path.open('w') as f:
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
        help="Target directory to clean (default: current directory)"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Simulate changes (default)"
    )
    group.add_argument(
        "--apply",
        dest="dry_run",
        action="store_false",
        help="Write changes to disk"
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Assume yes for all prompts (CI safe)"
    )
    parser.add_argument(
        "--skip-git",
        action="store_true",
        help="Skip git operations (for sandbox/testing)"
    )

    args = parser.parse_args()

    # Safety check
    if not args.dry_run:
        if not (args.yes or sys.stdin.isatty()):
            logging.error("Apply mode requires --yes when stdin is not a TTY")
            sys.exit(2)
        if not args.yes:
            response = input("⚠️  Running without dry-run will modify files. Continue? [y/N]: ")
            if response.lower() != 'y':
                print("Aborted.")
                sys.exit(0)

    # Create and run cleanup
    cleanup = MasterCleanup(args.target, args.dry_run, auto_yes=args.yes, skip_git=args.skip_git)
    try:
        cleanup.run()
    except SystemExit as e:
        sys.exit(e.code)


if __name__ == "__main__":
    main()
