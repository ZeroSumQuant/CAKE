#!/usr/bin/env python3
"""pty_shim.py - PTY wrapper for command safety and interception

Provides a pseudo-terminal that intercepts commands, checks against
allowlist, and can inject CAKE interventions before dangerous operations.

Author: CAKE Team
License: MIT
Python: 3.11+
"""

import logging
import os
import pty
import re
import select
import subprocess
import sys
import termios
import tty
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CommandPolicy:
    """Policy for command execution."""

    allowed_commands: List[str]
    blocked_patterns: List[str]
    require_confirmation: List[str]
    audit_log: bool = True


class PTYShim:
    """
    PTY wrapper that intercepts and filters commands.

    Provides safe command execution with allowlist and audit logging.
    """

    # Default safe command allowlist
    DEFAULT_ALLOWED = [
        # Python
        "python",
        "python3",
        "pip",
        "pip3",
        "poetry",
        "pipenv",
        # Git (except force push)
        "git add",
        "git commit",
        "git status",
        "git diff",
        "git log",
        "git pull",
        "git fetch",
        "git branch",
        "git checkout",
        "git merge",
        "git rebase",
        "git stash",
        # Testing
        "pytest",
        "python -m pytest",
        "unittest",
        "nose",
        "tox",
        # Linters
        "black",
        "flake8",
        "mypy",
        "pylint",
        "ruff",
        "isort",
        # File operations (safe)
        "ls",
        "cat",
        "less",
        "head",
        "tail",
        "grep",
        "find",
        "echo",
        "touch",
        "mkdir",
        "cp",
        "mv",
        # Development tools
        "make",
        "docker build",
        "docker run",
        "npm",
        "yarn",
        "cargo",
        "go",
        "node",
        # Text editors (read-only by default)
        "vi",
        "vim",
        "nano",
        "emacs",
        "code",
        "subl",
    ]

    # Dangerous patterns to block
    BLOCKED_PATTERNS = [
        r"rm\s+-rf\s+/",  # Recursive root deletion
        r"git\s+push\s+--force(?!-with-lease)",  # Force push without lease
        r":(){ :|:& };:",  # Fork bomb
        r"chmod\s+777",  # Too permissive
        r"curl.*\|\s*sh",  # Curl pipe to shell
        r"wget.*\|\s*bash",  # Wget pipe to bash
        r"sudo\s+rm",  # Sudo deletion
        r">\s*/dev/s[^t]",  # Overwriting devices
        r"dd\s+if=.*of=/dev/",  # Direct disk write
        r"mkfs",  # Filesystem format
    ]

    # Commands requiring confirmation
    CONFIRM_REQUIRED = [
        "git push --force-with-lease",
        "pip install --force-reinstall",
        "rm -rf",
        "docker system prune",
        "kubectl delete",
    ]

    def __init__(
        self,
        policy: Optional[CommandPolicy] = None,
        intervention_callback: Optional[Callable[[str], Optional[str]]] = None,
    ):
        """
        Initialize PTY shim.

        Args:
            policy: Command execution policy
            intervention_callback: Callback for CAKE interventions
        """
        self.policy = policy or CommandPolicy(
            allowed_commands=self.DEFAULT_ALLOWED,
            blocked_patterns=self.BLOCKED_PATTERNS,
            require_confirmation=self.CONFIRM_REQUIRED,
        )
        self.intervention_callback = intervention_callback
        self.command_history: List[Tuple[datetime, str, bool]] = []
        self.original_termios = None

    def start_shell(self, shell: str = "/bin/bash") -> int:
        """
        Start an interactive shell with command filtering.

        Args:
            shell: Shell to execute

        Returns:
            Exit code
        """  # Save terminal settings
        self.original_termios = termios.tcgetattr(sys.stdin)

        try:
            # Create PTY
            master_fd, slave_fd = pty.openpty()

            # Fork process
            pid = os.fork()

            if pid == 0:  # Child process
                # Set up slave PTY
                os.close(master_fd)
                os.setsid()
                os.dup2(slave_fd, 0)
                os.dup2(slave_fd, 1)
                os.dup2(slave_fd, 2)

                # Execute shell
                os.execv(shell, [shell])

            else:  # Parent process
                os.close(slave_fd)

                # Set stdin to raw mode
                tty.setraw(sys.stdin)

                # Handle I/O
                return self._handle_io(master_fd, pid)

        finally:
            # Restore terminal settings
            if self.original_termios:
                termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, self.original_termios)

    def _handle_io(self, master_fd: int, child_pid: int) -> int:
        """Handle I/O between terminal and child process."""
        command_buffer = ""

        while True:
            try:
                # Wait for input
                r, w, e = select.select([sys.stdin, master_fd], [], [])

                if sys.stdin in r:
                    # Read from stdin
                    data = os.read(sys.stdin.fileno(), 1024)
                    if not data:
                        break

                    # Intercept commands
                    filtered_data = self._filter_input(data, command_buffer)
                    if filtered_data is not None:
                        os.write(master_fd, filtered_data)
                        command_buffer = self._update_command_buffer(
                            command_buffer, data
                        )

                if master_fd in r:
                    # Read from child process
                    data = os.read(master_fd, 1024)
                    if not data:
                        break

                    # Write to stdout
                    os.write(sys.stdout.fileno(), data)

            except OSError:
                break

        # Wait for child to exit
        _, status = os.waitpid(child_pid, 0)
        return os.WEXITSTATUS(status)

    def _filter_input(self, data: bytes, command_buffer: str) -> Optional[bytes]:
        """Filter input data for safety."""  # Check if this completes a command (newline)
        if b"\n" in data or b"\r" in data:
            command = (command_buffer + data.decode("utf-8", errors="ignore")).strip()

            # Check command safety
            if not self._is_command_safe(command):
                # Inject intervention message
                if self.intervention_callback:
                    intervention = self.intervention_callback(command)
                    if intervention:
                        # Show intervention instead of executing
                        msg = f"\r\n{intervention}\r\n"
                        os.write(sys.stdout.fileno(), msg.encode())
                        return None

                # Block dangerous command
                msg = f"\r\nOperator (CAKE): Command blocked: '{command}'\r\n"
                os.write(sys.stdout.fileno(), msg.encode())
                self._log_command(command, blocked=True)
                return None

            # Check if confirmation required
            if self._requires_confirmation(command):
                if not self._get_confirmation(command):
                    return None

            # Log allowed command
            self._log_command(command, blocked=False)

        return data

    def _is_command_safe(self, command: str) -> bool:
        """Check if command is safe to execute."""
        command_lower = command.lower().strip()

        # Check blocked patterns
        for pattern in self.policy.blocked_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                logger.warning(f"Blocked command matching pattern: {pattern}")
                return False

        # Check allowlist (prefix matching)
        for allowed in self.policy.allowed_commands:
            if command_lower.startswith(allowed.lower()):
                return True

        # Check if it's just navigation or viewing
        safe_prefixes = ["cd ", "pwd", "ls", "cat ", "less ", "head ", "tail "]
        if any(command_lower.startswith(prefix) for prefix in safe_prefixes):
            return True

        # Default deny
        logger.warning(f"Command not in allowlist: {command}")
        return False

    def _requires_confirmation(self, command: str) -> bool:
        """Check if command requires confirmation."""
        command_lower = command.lower()
        return any(
            pattern in command_lower for pattern in self.policy.require_confirmation
        )

    def _get_confirmation(self, command: str) -> bool:
        """Get user confirmation for dangerous command."""
        msg = f"\r\nOperator (CAKE): Confirm execution of '{command}'? [y/N] "
        os.write(sys.stdout.fileno(), msg.encode())

        # Read single character
        response = os.read(sys.stdin.fileno(), 1).decode("utf-8").lower()
        os.write(sys.stdout.fileno(), b"\r\n")

        return response == "y"

    def _update_command_buffer(self, buffer: str, data: bytes) -> str:
        """Update command buffer with new data."""
        text = data.decode("utf-8", errors="ignore")

        # Handle backspace
        if "\x7f" in text or "\x08" in text:
            return buffer[:-1] if buffer else ""

        # Handle newline (command complete)
        if "\n" in text or "\r" in text:
            return ""

        return buffer + text

    def _log_command(self, command: str, blocked: bool):
        """Log command execution."""
        self.command_history.append((datetime.now(), command, blocked))

        if self.policy.audit_log:
            status = "BLOCKED" if blocked else "ALLOWED"
            logger.info(f"Command {status}: {command}")

    def get_command_history(self) -> List[Dict[str, Any]]:
        """Get command execution history."""
        return [
            {"timestamp": ts.isoformat(), "command": cmd, "blocked": blocked}
            for ts, cmd, blocked in self.command_history
        ]


class PTYShimIntegration:
    """Integration between PTY shim and CAKE."""

    def __init__(self, cake_adapter):
        """Initialize PTY-CAKE integration."""
        self.cake_adapter = cake_adapter
        self.pty_shim = PTYShim(intervention_callback=self._check_command_intervention)

    def _check_command_intervention(self, command: str) -> Optional[str]:
        """Check if CAKE wants to intervene on this command."""  # Update CAKE state
        action = {"type": "command_execution", "command": command}

        # Check for intervention (synchronous wrapper)
        import asyncio

        loop = asyncio.new_event_loop()
        intervention = loop.run_until_complete(
            self.cake_adapter.process_claude_action(action)
        )
        loop.close()

        return intervention

    def start_monitored_shell(self) -> int:
        """Start shell with CAKE monitoring."""
        logger.info("Starting CAKE-monitored shell")
        return self.pty_shim.start_shell()


# Standalone command wrapper
def cake_exec(command: List[str], cake_adapter=None) -> subprocess.CompletedProcess:
    """
    Execute command with CAKE safety checks.

    Args:
        command: Command and arguments
        cake_adapter: Optional CAKE adapter for interventions

    Returns:
        Completed process result
    """
    policy = CommandPolicy(
        allowed_commands=PTYShim.DEFAULT_ALLOWED,
        blocked_patterns=PTYShim.BLOCKED_PATTERNS,
        require_confirmation=[],  # No confirmation in programmatic mode
    )

    # Check command safety
    full_command = " ".join(command)

    # Check blocked patterns
    for pattern in policy.blocked_patterns:
        if re.search(pattern, full_command, re.IGNORECASE):
            raise PermissionError(
                f"Command blocked by CAKE: matches pattern '{pattern}'"
            )

    # Check allowlist
    allowed = False
    for allowed_cmd in policy.allowed_commands:
        if full_command.lower().startswith(allowed_cmd.lower()):
            allowed = True
            break

    if not allowed:
        raise PermissionError(f"Command not in CAKE allowlist: {full_command}")

    # Execute safely
    logger.info(f"CAKE executing: {full_command}")
    return subprocess.run(command, capture_output=True, text=True, check=True)


# Example usage
if __name__ == "__main__":
    import tempfile

    from cake.adapters.cake_adapter import create_cake_system

    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Test standalone execution
    try:
        result = cake_exec(["ls", "-la"])
        print(f"Output: {result.stdout}")
    except PermissionError as e:
        print(f"Blocked: {e}")

    # Test dangerous command
    try:
        result = cake_exec(["rm", "-rf", "/"])
        print("This should not print!")
    except PermissionError as e:
        print(f"Correctly blocked: {e}")

    # Test PTY shim (interactive)
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        with tempfile.TemporaryDirectory() as tmpdir:
            cake_adapter = create_cake_system(Path(tmpdir))
            integration = PTYShimIntegration(cake_adapter)
            exit_code = integration.start_monitored_shell()
            sys.exit(exit_code)
