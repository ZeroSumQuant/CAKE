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

    def fix_imports(self) -> None:  # noqa: C901
        """One import per line, dedupe, sort obvious junk away."""
        self.log("Fixing imports...")

        # Directories to skip
        skip_dirs = {"migrations", "proto", "static", "__pycache__", ".venv", "venv"}

        for py_file in self.iter_python_files():
            # Skip files in binary/generated directories
            if any(part in skip_dirs for part in py_file.parts):
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                lines = content.splitlines()
                new_lines = []
                modified = False

                # Process file line by line
                i = 0
                while i < len(lines):
                    line = lines[i]
                    stripped = line.strip()

                    # Check if this is the start of an import block
                    if stripped.startswith(
                        ("import ", "from ")
                    ) and not stripped.startswith("from __future__"):
                        # Collect all imports in this contiguous block
                        import_block = []
                        # import_start = i  # Currently unused

                        while i < len(lines) and (
                            lines[i].strip().startswith(("import ", "from "))
                            or not lines[i].strip()
                        ):
                            if lines[i].strip():  # Skip empty lines within import block
                                import_block.append(lines[i])
                            i += 1

                        # Process the import block
                        deduped_imports = self._dedupe_import_block(import_block)

                        # Check if we made changes
                        if deduped_imports != import_block:
                            modified = True

                        # Add the processed imports
                        new_lines.extend(deduped_imports)
                    else:
                        # Not an import line, just add it
                        new_lines.append(line)
                        i += 1

                # Write back if modified
                if modified:
                    new_content = "\n".join(new_lines)
                    if new_content and not new_content.endswith("\n"):
                        new_content += "\n"

                    if self.ast_safe_write(py_file, new_content):
                        self.log(f"  ✓ Fixed imports in {py_file}")

            except Exception as e:
                self.log(f"  ⚠️  Error processing {py_file}: {e}")
                self.error_log.append(f"{py_file}: {e}")

    def _dedupe_import_block(self, block_lines: list[str]) -> list[str]:  # noqa: C901
        """
        Split comma-imports, keep first occurrence of each exact statement,
        then emit in order:
            1) stdlib 'import xxx'
            2) third-party/local 'import xxx'
            3) stdlib 'from xxx import …'
            4) third-party/local 'from xxx import …'
        Original relative order inside each bucket is preserved.
        """
        # Basic stdlib modules
        stdlib = {
            "abc",
            "argparse",
            "ast",
            "asyncio",
            "base64",
            "bisect",
            "collections",
            "contextlib",
            "copy",
            "csv",
            "datetime",
            "decimal",
            "email",
            "enum",
            "functools",
            "hashlib",
            "importlib",
            "io",
            "itertools",
            "json",
            "logging",
            "math",
            "os",
            "pathlib",
            "pickle",
            "re",
            "shutil",
            "sqlite3",
            "string",
            "subprocess",
            "sys",
            "tempfile",
            "threading",
            "time",
            "typing",
            "unittest",
            "urllib",
            "uuid",
            "warnings",
            "weakref",
            "xml",
            "zipfile",
        }

        buckets = {k: [] for k in ("imp_std", "imp_oth", "from_std", "from_oth")}
        seen_stmt: set[str] = set()  # exact statements we've seen
        module_order: list[tuple[str, bool]] = []  # [(base_module, has_alias), ...]
        module_lines: dict[tuple[str, bool], str] = {}  # (base, has_alias) -> line

        for raw in block_lines:
            code, *comment = raw.split("#", 1)
            comment = f"#{comment[0].rstrip()}" if comment else ""
            code = code.rstrip()

            # split comma-import only for plain import
            if code.startswith("import "):
                for part in code[len("import ") :].split(","):
                    part = part.strip()
                    stmt = f"import {part}"

                    if stmt in seen_stmt:
                        continue  # exact duplicate

                    # Split module and alias
                    if " as " in part:
                        base = part.split(" as ")[0].strip()
                        has_alias = True
                    else:
                        base = part
                        has_alias = False

                    # Track order of first occurrence
                    key = (base, has_alias)
                    if key not in module_lines:
                        module_order.append(key)
                        line = stmt + (f"  {comment}" if comment else "")
                        module_lines[key] = line
                        comment = ""  # attach comment only once

                    seen_stmt.add(stmt)

            else:  # from-import line
                if code not in seen_stmt:
                    seen_stmt.add(code)
                    # Extract module name from "from X import ..."
                    parts = code.split()
                    if len(parts) >= 2:
                        mod = parts[1].split(".")[0]
                        bucket = "from_std" if mod in stdlib else "from_oth"
                        buckets[bucket].append(
                            f"{code}{'  ' + comment if comment else ''}"
                        )

        # Now emit imports in the right order: plain imports before aliases
        # First pass: emit plain imports
        for base, has_alias in module_order:
            if not has_alias:
                mod_name = base.split(".")[0]
                bucket = "imp_std" if mod_name in stdlib else "imp_oth"
                buckets[bucket].append(module_lines[(base, has_alias)])

        # Second pass: emit aliased imports
        for base, has_alias in module_order:
            if has_alias:
                mod_name = base.split(".")[0]
                bucket = "imp_std" if mod_name in stdlib else "imp_oth"
                buckets[bucket].append(module_lines[(base, has_alias)])

        result = (
            buckets["imp_std"]
            + buckets["imp_oth"]
            + buckets["from_std"]
            + buckets["from_oth"]
        )
        return result

    def _dedupe_and_sort_import_block(
        self, block_lines: list[str]
    ) -> list[str]:  # noqa: C901
        """Deduplicate and sort imports, grouping by type."""
        # First deduplicate
        deduped = self._dedupe_import_block(block_lines)

        # Then sort into groups
        stdlib = []
        third_party = []
        local = []

        # Known stdlib modules (Python 3.11)
        stdlib_modules = {
            "abc",
            "argparse",
            "ast",
            "asyncio",
            "base64",
            "binascii",
            "bisect",
            "builtins",
            "bz2",
            "calendar",
            "cmath",
            "cmd",
            "code",
            "codecs",
            "collections",
            "colorsys",
            "concurrent",
            "configparser",
            "contextlib",
            "copy",
            "copyreg",
            "csv",
            "ctypes",
            "curses",
            "dataclasses",
            "datetime",
            "dbm",
            "decimal",
            "difflib",
            "dis",
            "doctest",
            "email",
            "encodings",
            "enum",
            "errno",
            "faulthandler",
            "fcntl",
            "filecmp",
            "fileinput",
            "fnmatch",
            "fractions",
            "ftplib",
            "functools",
            "gc",
            "getopt",
            "getpass",
            "gettext",
            "glob",
            "graphlib",
            "grp",
            "gzip",
            "hashlib",
            "heapq",
            "hmac",
            "html",
            "http",
            "imaplib",
            "imghdr",
            "imp",
            "importlib",
            "inspect",
            "io",
            "ipaddress",
            "itertools",
            "json",
            "keyword",
            "linecache",
            "locale",
            "logging",
            "lzma",
            "mailbox",
            "mailcap",
            "marshal",
            "math",
            "mimetypes",
            "mmap",
            "modulefinder",
            "multiprocessing",
            "netrc",
            "nntplib",
            "numbers",
            "operator",
            "optparse",
            "os",
            "pathlib",
            "pdb",
            "pickle",
            "pickletools",
            "pipes",
            "pkgutil",
            "platform",
            "plistlib",
            "poplib",
            "posix",
            "pprint",
            "profile",
            "pstats",
            "pty",
            "pwd",
            "py_compile",
            "pyclbr",
            "pydoc",
            "queue",
            "quopri",
            "random",
            "re",
            "readline",
            "reprlib",
            "resource",
            "rlcompleter",
            "runpy",
            "sched",
            "secrets",
            "select",
            "selectors",
            "shelve",
            "shlex",
            "shutil",
            "signal",
            "site",
            "smtpd",
            "smtplib",
            "sndhdr",
            "socket",
            "socketserver",
            "spwd",
            "sqlite3",
            "ssl",
            "stat",
            "statistics",
            "string",
            "stringprep",
            "struct",
            "subprocess",
            "sunau",
            "symtable",
            "sys",
            "sysconfig",
            "syslog",
            "tabnanny",
            "tarfile",
            "telnetlib",
            "tempfile",
            "termios",
            "test",
            "textwrap",
            "threading",
            "time",
            "timeit",
            "tkinter",
            "token",
            "tokenize",
            "tomllib",
            "trace",
            "traceback",
            "tracemalloc",
            "tty",
            "turtle",
            "types",
            "typing",
            "unicodedata",
            "unittest",
            "urllib",
            "uu",
            "uuid",
            "venv",
            "warnings",
            "wave",
            "weakref",
            "webbrowser",
            "winreg",
            "winsound",
            "wsgiref",
            "xdrlib",
            "xml",
            "xmlrpc",
            "zipapp",
            "zipfile",
            "zipimport",
            "zlib",
            "zoneinfo",
            "__future__",
        }

        for line in deduped:
            # Extract the base module name
            if line.strip().startswith("import "):
                module = line.strip()[7:].split(" as ")[0].split(".")[0]
            elif line.strip().startswith("from "):
                module = line.strip()[5:].split(" import ")[0].split(".")[0]
            else:
                local.append(line)
                continue

            # Categorize
            if module in stdlib_modules:
                stdlib.append(line)
            elif module.startswith("."):
                local.append(line)
            else:
                third_party.append(line)

        # Sort within each group
        # Use stable sort to preserve relative order of imports with same module
        def sort_key(line):
            stripped = line.strip()
            # Put regular imports before from imports
            if stripped.startswith("import "):
                prefix = "0"
                module = stripped[7:].split(" as ")[0]
            else:  # from imports
                prefix = "1"
                module = stripped[5:].split(" import ")[0]
            return (prefix, module.lower())

        stdlib.sort(key=sort_key)
        third_party.sort(key=sort_key)
        local.sort(key=sort_key)

        # Combine with blank lines between groups
        result = []
        if stdlib:
            result.extend(stdlib)
        if third_party:
            if result:
                result.append("")  # Blank line
            result.extend(third_party)
        if local:
            if result:
                result.append("")  # Blank line
            result.extend(local)

        return result

    def fix_docstrings(self) -> None:  # noqa: C901
        """Normalize triple quotes and proper indentation."""
        self.log("Fixing docstrings...")

        import re

        # Directories to skip
        skip_dirs = {"migrations", "proto", "static", "__pycache__", ".venv", "venv"}

        for py_file in self.iter_python_files():
            # Skip files in binary/generated directories
            if any(part in skip_dirs for part in py_file.parts):
                continue

            # Skip .pyi stub files
            if py_file.suffix == ".pyi":
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
                modified = False

                # Replace ''' with """ (but not in raw strings)
                def replace_single_quotes(match):
                    if match.group(0).startswith("r"):
                        return match.group(0)  # Skip raw strings
                    return '"""' + match.group(1) + '"""'

                new_content = re.sub(
                    r"'''(.*?)'''", replace_single_quotes, content, flags=re.DOTALL
                )
                if new_content != content:
                    content = new_content
                    modified = True

                # Process line by line for docstring transformations
                lines = content.splitlines()
                new_lines = []
                i = 0

                while i < len(lines):
                    line = lines[i]
                    stripped = line.strip()

                    # Check for one-line docstring
                    if (
                        '"""' in line
                        and line.count('"""') == 2
                        and not line.strip().startswith('r"""')
                    ):
                        # Extract indent and docstring content
                        indent = line[: len(line) - len(line.lstrip())]

                        # Check if it's > 72 chars
                        if len(line) > 72:
                            # Extract the docstring content
                            start_idx = line.find('"""') + 3
                            end_idx = line.rfind('"""')
                            doc_content = line[start_idx:end_idx]

                            # Convert to multi-line
                            new_lines.append(indent + '"""')
                            new_lines.append(indent + doc_content)
                            new_lines.append(indent + '"""')
                            modified = True
                            i += 1
                            continue

                    # Check for multi-line docstring start
                    elif stripped == '"""' or (
                        stripped.startswith('"""') and not stripped.endswith('"""')
                    ):
                        # This is the start of a multi-line docstring
                        indent = line[: len(line) - len(line.lstrip())]
                        new_lines.append(line)
                        i += 1

                        # Collect the docstring body
                        while i < len(lines):
                            line = lines[i]
                            if '"""' in line:
                                # Found closing quotes
                                if line.strip() == '"""':
                                    # Already on its own line - good
                                    new_lines.append(line)
                                else:
                                    # Closing quotes share line with content
                                    content_before_quotes = line[
                                        : line.rfind('"""')
                                    ].rstrip()
                                    if content_before_quotes:
                                        new_lines.append(content_before_quotes)
                                    new_lines.append(indent + '"""')
                                    modified = True
                                i += 1
                                break
                            else:
                                new_lines.append(line)
                                i += 1
                        continue

                    # Regular line
                    new_lines.append(line)
                    i += 1

                if modified:
                    new_content = "\n".join(new_lines)
                    if new_content and not new_content.endswith("\n"):
                        new_content += "\n"

                    if self.ast_safe_write(py_file, new_content):
                        self.log(f"  ✓ Fixed docstrings in {py_file}")

            except Exception as e:
                self.log(f"  ⚠️  Error processing {py_file}: {e}")
                self.error_log.append(f"{py_file}: {e}")

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
        self.log("Running black...")

        # Skip if in dry-run or skip-shell mode
        if self.dry_run or self.skip_shell:
            self.log("  💡 Skipping black in dry-run/skip-shell mode")
            return

        # Check if black is available
        black_check = self.safe_run(["which", "black"], capture_output=True)
        if black_check.returncode != 0:
            self.log("  ⚠️  black not found - skipping")
            return

        # Run black on the target path
        cmd = ["black", str(self.target_path)]
        result = self.safe_run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            self.log("  ✓ black formatting complete")
            # Parse output for statistics
            if result.stdout:
                for line in result.stdout.splitlines():
                    if "file" in line and "reformatted" in line:
                        self.log(f"    {line}")
        else:
            self.log(f"  ⚠️  black failed: {result.stderr}")
            self.error_log.append(f"black: {result.stderr}")

    def run_isort(self) -> None:
        """Run isort formatter."""
        self.log("Running isort...")

        # Skip if in dry-run or skip-shell mode
        if self.dry_run or self.skip_shell:
            self.log("  💡 Skipping isort in dry-run/skip-shell mode")
            return

        # Check if isort is available
        isort_check = self.safe_run(["which", "isort"], capture_output=True)
        if isort_check.returncode != 0:
            self.log("  ⚠️  isort not found - skipping")
            return

        # Run isort on the target path
        cmd = ["isort", str(self.target_path)]
        result = self.safe_run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            self.log("  ✓ isort formatting complete")
            # Parse output for statistics
            if result.stdout:
                for line in result.stdout.splitlines():
                    if "Fixing" in line or "file" in line:
                        self.log(f"    {line}")
        else:
            self.log(f"  ⚠️  isort failed: {result.stderr}")
            self.error_log.append(f"isort: {result.stderr}")

    def ast_empty_body_sweep(self) -> None:  # noqa: C901
        """Catch any empty bodies that Phase 2 heuristics missed using AST."""
        self.log("Running AST empty body sweep...")

        for py_file in self.iter_python_files():
            try:
                content = py_file.read_text(encoding="utf-8")
                lines = content.splitlines()
                modified = False

                # Parse with AST to find truly empty functions/classes
                try:
                    tree = ast.parse(content)
                except SyntaxError:
                    # Can't parse - might have incomplete functions
                    # Fall back to line-based detection for these edge cases
                    self.log(f"  ⚠️  SyntaxError parsing {py_file}, using fallback")

                    # Simple line-based detection for truly empty functions
                    i = 0
                    while i < len(lines):
                        line = lines[i]
                        stripped = line.strip()

                        # Check for function/class definitions ending with :
                        if stripped.startswith(
                            ("def ", "async def ", "class ")
                        ) and stripped.endswith(":"):

                            indent = len(line) - len(line.lstrip())

                            # Check if there's any content after this line
                            j = i + 1
                            while j < len(lines) and not lines[j].strip():
                                j += 1

                            # If we've reached end or next non-blank has same/less indent
                            if j >= len(lines):
                                # Insert pass after the def line
                                pass_line = " " * (indent + 4) + "pass"
                                lines.insert(i + 1, pass_line)
                                modified = True
                                i += 2  # Skip the inserted line
                                continue
                            else:
                                next_line = lines[j]
                                next_indent = len(next_line) - len(next_line.lstrip())
                                if next_indent <= indent:
                                    # Empty body
                                    pass_line = " " * (indent + 4) + "pass"
                                    lines.insert(i + 1, pass_line)
                                    modified = True
                                    i += 2  # Skip the inserted line
                                    continue

                        i += 1

                    # Write back if modified
                    if modified:
                        new_content = "\n".join(lines)
                        if new_content and not new_content.endswith("\n"):
                            new_content += "\n"

                        if self.ast_safe_write(py_file, new_content):
                            self.log(f"  ✓ Fixed empty bodies in {py_file}")

                    continue  # Skip AST processing for this file

                # Define what constitutes an empty body
                TARGETS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

                def _body_is_runtime_empty(body: list[ast.stmt]) -> bool:
                    """True if body has no executable statements."""
                    if not body:
                        return True  # completely empty
                    for stmt in body:
                        # Ignore nested defs/classes, docstrings, ellipsis
                        if isinstance(stmt, TARGETS):
                            continue
                        if isinstance(stmt, ast.Expr):
                            # Check for docstring
                            if isinstance(stmt.value, (ast.Str, ast.Constant)):
                                if isinstance(stmt.value, ast.Constant) and isinstance(
                                    stmt.value.value, str
                                ):
                                    continue  # docstring
                                elif isinstance(stmt.value, ast.Str):
                                    continue  # docstring (older AST)
                            # Check for ellipsis
                            elif isinstance(stmt.value, ast.Ellipsis):
                                return False  # has ellipsis, don't add pass
                            elif (
                                isinstance(stmt.value, ast.Constant)
                                and stmt.value.value is ...
                            ):
                                return False  # has ellipsis (newer AST)
                        if isinstance(stmt, ast.Pass):
                            return False  # already has pass
                        # Found real code
                        return False
                    return True

                # Collect AST nodes that need pass statements
                empty_nodes = []

                class EmptyNodeCollector(ast.NodeVisitor):
                    def visit_FunctionDef(self, node):
                        if _body_is_runtime_empty(node.body):
                            empty_nodes.append(node)
                        self.generic_visit(node)

                    def visit_AsyncFunctionDef(self, node):
                        if _body_is_runtime_empty(node.body):
                            empty_nodes.append(node)
                        self.generic_visit(node)

                    def visit_ClassDef(self, node):
                        # Check if only has docstring
                        has_only_docstring = (
                            len(node.body) == 1
                            and isinstance(node.body[0], ast.Expr)
                            and isinstance(node.body[0].value, (ast.Str, ast.Constant))
                        )
                        if not node.body or has_only_docstring:
                            empty_nodes.append(node)
                        self.generic_visit(node)

                collector = EmptyNodeCollector()
                collector.visit(tree)

                # Calculate where to insert pass for each empty node
                insertions = []
                for node in empty_nodes:
                    # Determine insertion line
                    if hasattr(node, "body") and node.body:
                        # Insert after the last item in the body
                        last = node.body[-1]
                        if hasattr(last, "end_lineno"):
                            insert_line = last.end_lineno + 1
                        else:
                            insert_line = node.lineno + 1
                    else:
                        # Body is completely empty, insert right after the def/class line
                        insert_line = node.lineno + 1

                    # Determine indentation
                    if hasattr(node, "col_offset"):
                        indent = node.col_offset + 4
                    else:
                        # Fallback: find the line and calculate indent
                        if node.lineno <= len(lines):
                            header_line = lines[node.lineno - 1]
                            indent = len(header_line) - len(header_line.lstrip()) + 4
                        else:
                            indent = 4

                    insertions.append((insert_line, indent))

                # Sort insertions by line number (descending) to avoid offset issues
                insertions.sort(reverse=True)

                # Insert pass statements
                for insert_line, indent in insertions:
                    # Convert to 0-based index
                    idx = insert_line - 1

                    # Make sure we're not out of bounds
                    if idx > len(lines):
                        idx = len(lines)

                    # Check if there's already a pass or ellipsis at or near this location
                    has_pass = False
                    if 0 <= idx < len(lines):
                        line_to_check = lines[idx].strip()
                        if line_to_check in ("pass", "..."):
                            has_pass = True

                    if not has_pass:
                        pass_line = " " * indent + "pass"
                        lines.insert(idx, pass_line)
                        modified = True

                if modified:
                    new_content = "\n".join(lines)
                    if new_content and not new_content.endswith("\n"):
                        new_content += "\n"

                    if self.ast_safe_write(py_file, new_content):
                        self.log(f"  ✓ Fixed empty bodies in {py_file}")

            except Exception as e:
                self.log(f"  ⚠️  Error processing {py_file}: {e}")
                self.error_log.append(f"{py_file}: {e}")

    def classify_file(self, path: Path) -> str:  # noqa: C901
        """Classify a file based on its content and purpose."""
        # Handle notebooks
        if path.suffix == ".ipynb":
            return "notebook"

        # Handle binary files
        if path.suffix in {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".ico",
            ".svg",
            ".pdf",
            ".zip",
            ".tar",
            ".gz",
            ".bz2",
            ".7z",
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".a",
            ".o",
            ".pyc",
            ".pyo",
            ".pyd",
            ".whl",
        }:
            return "binary"

        # Handle template files
        if path.suffix in {
            ".html",
            ".htm",
            ".xml",
            ".jinja",
            ".jinja2",
            ".j2",
            ".tmpl",
            ".tpl",
            ".mustache",
            ".handlebars",
        }:
            return "template"

        # Handle Python files
        if path.suffix == ".py":
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                # Check for shebang script
                if content.startswith("#!/usr/bin/env python") or content.startswith(
                    "#!/usr/bin/python"
                ):
                    return "script"
                # Check for test files
                if (
                    "pytest" in content
                    or "import pytest" in content
                    or "import unittest" in content
                ):
                    return "test"
                # Check for scripts (executable files)
                if "__name__" in content and "main" in content:
                    return "script"
                # Default to module
                return "module"
            except Exception:
                return "module"  # Default for unreadable Python files

        # Handle data files
        if path.suffix in {".csv", ".json", ".parquet", ".xlsx", ".h5", ".hdf5"}:
            return "data"

        # Handle documentation
        if path.suffix in {".md", ".rst", ".txt"} or path.name in {
            "README",
            "LICENSE",
            "CHANGELOG",
        }:
            return "documentation"

        # Handle configuration
        if path.name in {
            ".gitignore",
            ".flake8",
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "requirements.txt",
            "Pipfile",
            "poetry.lock",
            "Makefile",
            "Dockerfile",
            ".dockerignore",
            ".editorconfig",
            ".gitattributes",
        }:
            return "configuration"

        # Everything else
        return "other"

    def build_manifest(self) -> dict:
        """Build a manifest of all files in the project."""
        self.log("Building file manifest...")

        manifest = {
            "timestamp": datetime.now().isoformat(),
            "target_path": str(self.target_path),
            "files": {},
            "summary": {
                "notebook": 0,
                "test": 0,
                "script": 0,
                "module": 0,
                "data": 0,
                "documentation": 0,
                "configuration": 0,
                "binary": 0,
                "template": 0,
                "other": 0,
                "oversize_files": 0,
            },
        }

        # Skip directories
        skip_dirs = {
            ".git",
            "__pycache__",
            ".venv",
            "venv",
            "node_modules",
            ".tox",
            ".eggs",
            ".pytest_cache",
            ".mypy_cache",
            "htmlcov",
            ".coverage",
            "build",
            "dist",
            ".cache",
        }

        # Walk through all files
        for file_path in self.target_path.rglob("*"):
            # Skip if in excluded directory
            if any(part in skip_dirs for part in file_path.parts):
                continue

            # Skip egg-info directories
            if any(part.endswith(".egg-info") for part in file_path.parts):
                continue

            # Skip directories themselves
            if file_path.is_dir():
                continue

            # Skip hidden files except important ones
            if file_path.name.startswith(".") and file_path.name not in {
                ".gitignore",
                ".flake8",
            }:
                continue

            # Classify the file
            classification = self.classify_file(file_path)
            relative_path = file_path.relative_to(self.target_path)

            # Get file stats
            file_size = file_path.stat().st_size
            file_info = {
                "classification": classification,
                "size": file_size,
                "suffix": file_path.suffix,
                "executable": os.access(file_path, os.X_OK),
            }

            # Check for oversize data files (> 20MB)
            if classification == "data" and file_size > 20 * 1024 * 1024:
                file_info["oversize"] = True
                manifest["summary"]["oversize_files"] += 1

            manifest["files"][str(relative_path)] = file_info
            manifest["summary"][classification] += 1

        self.log(f"  ✓ Classified {len(manifest['files'])} files")
        for category, count in manifest["summary"].items():
            if category != "oversize_files" and count > 0:
                self.log(f"    - {category}: {count}")

        if manifest["summary"]["oversize_files"] > 0:
            self.log(
                f"  ⚠️  Found {manifest['summary']['oversize_files']} oversize data files (>20MB)"
            )

        # Save manifest to .cake directory
        cake_dir = self.target_path / ".cake"
        cake_dir.mkdir(exist_ok=True)

        manifest_path = cake_dir / "manifest.json"
        with manifest_path.open("w") as f:
            json.dump(manifest, f, indent=2)

        self.log(f"  ✓ Manifest saved → {manifest_path} (open to view details)")
        return manifest

    def _load_manifest(self) -> dict:
        """Load the manifest from .cake/manifest.json."""
        manifest_path = self.target_path / ".cake" / "manifest.json"
        if not manifest_path.exists():
            self.log("  ⚠️  No manifest found. Run build_manifest phase first.")
            return {"files": {}, "summary": {}}

        with manifest_path.open() as f:
            return json.load(f)

    def _get_project_name(self) -> str:
        """Get the project name for src/<project>/ directory."""
        # Use the target directory name, lowercased
        return self.target_path.name.lower()

    def _target_path_for_file(self, file_path: str, file_info: dict):  # noqa: C901
        """Determine the target path for a file based on its classification."""
        classification = file_info["classification"]
        source = Path(file_path)

        # Skip if already in the right place
        if classification == "notebook" and source.parts[0] == "notebooks":
            return None
        if classification == "test" and source.parts[0] == "tests":
            return None
        if classification == "script" and source.parts[0] == "scripts":
            return None
        if classification == "binary" and source.parts[0] == "assets":
            return None
        if classification == "template" and source.parts[0] == "templates":
            return None
        if (
            classification == "data"
            and len(source.parts) >= 2
            and source.parts[0] == "data"
        ):
            return None

        # Map classifications to target directories
        if classification == "notebook":
            # Preserve subdirectory structure
            if len(source.parts) > 1:
                return Path("notebooks") / Path(*source.parts[1:])
            return Path("notebooks") / source.name

        elif classification == "test":
            return Path("tests") / source.name

        elif classification == "script":
            return Path("scripts") / source.name

        elif classification == "module":
            project_name = self._get_project_name()
            return Path("src") / project_name / source.name

        elif classification == "data":
            return Path("data") / "raw" / source.name

        elif classification == "binary":
            return Path("assets") / source.name

        elif classification == "template":
            return Path("templates") / source.name

        # Leave other files in place
        return None

    def organise_project(self) -> None:  # noqa: C901
        """Organize project files based on the manifest."""
        self.log("Organizing project structure...")

        # Load manifest
        manifest = self._load_manifest()
        if not manifest["files"]:
            self.log("  ⚠️  No files in manifest to organize")
            return

        # Plan moves
        moves = []
        skipped = 0

        for file_path, file_info in manifest["files"].items():
            source = self.target_path / file_path

            # Skip if source doesn't exist (might have been moved already)
            if not source.exists():
                continue

            # Get target path
            target_relative = self._target_path_for_file(file_path, file_info)
            if not target_relative:
                continue  # File is already in the right place

            target = self.target_path / target_relative

            # Skip if target already exists
            if target.exists():
                self.log(f"  ⚠️  Target {target_relative} exists; skipping {file_path}")
                skipped += 1
                continue

            moves.append((source, target, file_path, target_relative))

        # Report plan in dry-run mode
        if self.dry_run:
            self.log(f"  📋 Planning to move {len(moves)} files:")
            for source, target, src_rel, tgt_rel in moves[:10]:  # Show first 10
                self.log(f"     {src_rel} → {tgt_rel}")
            if len(moves) > 10:
                self.log(f"     ... and {len(moves) - 10} more")

            if moves:
                self.log(
                    f"\n  Plan: {len(moves)} files will be moved. Re-run with --apply to execute."
                )
            self.summary["organise_moves_planned"] = len(moves)
            self.summary["organise_moves_skipped"] = skipped
            return

        # Execute moves
        moved = 0
        import shutil

        for source, target, src_rel, tgt_rel in moves:
            try:
                # Create target directory
                target.parent.mkdir(parents=True, exist_ok=True)

                # Move the file
                if self.skip_git or not (self.target_path / ".git").exists():
                    # Use regular move if skip_git is True or not in a git repo
                    shutil.move(str(source), str(target))
                else:
                    # Use git mv when in a git repository
                    result = self.safe_run(
                        ["git", "mv", str(source), str(target)],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode != 0:
                        # Fall back to regular move if git mv fails
                        self.log("  ⚠️  git mv failed, using shutil.move")
                        shutil.move(str(source), str(target))

                self.log(f"  ✓ Moved {src_rel} → {tgt_rel}")
                moved += 1

            except Exception as e:
                self.log(f"  ⚠️  Failed to move {src_rel}: {e}")
                self.error_log.append(f"Move failed: {src_rel} → {tgt_rel}: {e}")

        # Create missing __init__.py files
        if moved > 0:
            for init_dir in ["tests", "src"]:
                init_path = self.target_path / init_dir / "__init__.py"
                if init_path.parent.exists() and not init_path.exists():
                    init_path.touch()
                    self.log(f"  ✓ Created {init_dir}/__init__.py")

            # Create data/README.md if we moved data files
            data_readme = self.target_path / "data" / "README.md"
            if data_readme.parent.exists() and not data_readme.exists():
                data_readme.write_text(
                    "# Data Directory\n\nThis directory contains project data files.\n"
                )
                self.log("  ✓ Created data/README.md")

        self.summary["organise"] = {"moved": moved, "skipped": skipped}

        self.log(f"  ✓ Organization complete: {moved} moved, {skipped} skipped")

    # ─────────────────── Phase 4 ─ Scaffold ────────────────────
    def write_pyproject(self) -> None:
        """Create a minimal pyproject.toml if one does not exist."""
        pyproj = self.target_path / "pyproject.toml"
        if pyproj.exists():
            return

        name = self.target_path.name.lower().replace(" ", "-")
        tmpl = (
            "[project]\n"
            f'name = "{name}"\n'
            'version = "0.0.0"\n'
            'authors = ["Unknown <user@example.com>"]\n'
            'description = ""\n'
            'requires-python = ">=3.8"\n'
        )
        pyproj.write_text(tmpl)
        self.log(f"  ✓ Created pyproject.toml for project '{name}'")
        self.summary["scaffold_pyproject"] = str(pyproj)

    def ensure_stub_files(self) -> None:
        """Create __init__.py and README files in key directories if they don't exist."""
        self.log("Checking for stub files...")
        created_files = []

        # Create tests/__init__.py if tests directory exists
        tests_dir = self.target_path / "tests"
        if tests_dir.exists() and tests_dir.is_dir():
            init_file = tests_dir / "__init__.py"
            if not init_file.exists():
                init_file.write_text("# Test package\n")
                self.log("  ✓ Created tests/__init__.py")
                created_files.append(str(init_file))

        # Create notebooks/README.md if notebooks directory exists
        notebooks_dir = self.target_path / "notebooks"
        if notebooks_dir.exists() and notebooks_dir.is_dir():
            readme_file = notebooks_dir / "README.md"
            if not readme_file.exists():
                content = """# Notebooks

This directory contains Jupyter notebooks for analysis and experimentation.

## Organization

- Place exploratory notebooks directly in this directory
- Create subdirectories for specific analysis topics if needed
- Use descriptive names for notebooks (e.g., `data_exploration.ipynb`, `model_training.ipynb`)

## Best Practices

- Clear output before committing (unless output is essential)
- Include a markdown cell at the top explaining the notebook's purpose
- Use meaningful variable names and add comments for complex operations
"""
                readme_file.write_text(content)
                self.log("  ✓ Created notebooks/README.md")
                created_files.append(str(readme_file))

        # Create src/<project>/__init__.py if src directory exists
        src_dir = self.target_path / "src"
        if src_dir.exists() and src_dir.is_dir():
            project_name = self._get_project_name()
            project_dir = src_dir / project_name
            if project_dir.exists() and project_dir.is_dir():
                init_file = project_dir / "__init__.py"
                if not init_file.exists():
                    init_file.write_text(f'"""Package: {project_name}"""\n')
                    self.log(f"  ✓ Created src/{project_name}/__init__.py")
                    created_files.append(str(init_file))

        if created_files:
            self.summary["scaffold_stubs"] = created_files
        else:
            self.log("  ✓ All stub files already exist")

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
            ("fix_imports", self.fix_imports),
            ("fix_docstrings", self.fix_docstrings),
            ("ast_empty_body_sweep", self.ast_empty_body_sweep),
            ("run_black", self.run_black),
            ("run_isort", self.run_isort),
            ("build_manifest", self.build_manifest),
            ("organise_project", self.organise_project),
            ("write_pyproject", self.write_pyproject),
            ("ensure_stub_files", self.ensure_stub_files),
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
