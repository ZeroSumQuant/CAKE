#!/usr/bin/env python3
"""
Real-time monitoring and intervention system for Claude's actions.
Provides immediate feedback when Claude is about to make common mistakes.
"""

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple


class InterventionType(Enum):
    """Types of interventions."""

    HIDDEN_FILES = auto()
    WRONG_INTERPRETER = auto()
    PATH_CONFUSION = auto()
    INEFFICIENT_TOOLS = auto()
    MISSING_CONTEXT = auto()
    SYNTAX_ERROR_PATTERN = auto()


@dataclass
class Intervention:
    """An intervention message."""

    type: InterventionType
    message: str
    suggestion: str
    severity: str  # "warning", "error", "info"


class ClaudeMonitor:
    """Monitors Claude's actions and provides real-time feedback."""

    def __init__(self):
        self.interventions: List[Intervention] = []
        self.patterns = self._init_patterns()

    def _init_patterns(self) -> Dict[str, Tuple[re.Pattern, Intervention]]:
        """Initialize monitoring patterns."""
        return {
            # Hidden files issue
            "ls_without_la": (
                re.compile(r"^\s*ls\s+(?!.*-[la])"),
                Intervention(
                    type=InterventionType.HIDDEN_FILES,
                    message="⚠️ STOP: You're using 'ls' without -la flag",
                    suggestion="Use 'ls -la' to see hidden directories like .venv",
                    severity="warning",
                ),
            ),
            # Wrong interpreter
            "python_bash_script": (
                re.compile(r"python[3]?\s+.*\.(sh|bash)"),
                Intervention(
                    type=InterventionType.WRONG_INTERPRETER,
                    message="❌ ERROR: Trying to run bash script with Python",
                    suggestion="Use 'bash script.sh' or check shebang with 'head -1 script.sh'",
                    severity="error",
                ),
            ),
            # Path confusion
            "relative_path_danger": (
                re.compile(r"^\s*cd\s+[^/~]"),
                Intervention(
                    type=InterventionType.PATH_CONFUSION,
                    message="⚠️ WARNING: Using relative path with cd",
                    suggestion="First run 'pwd' to verify location, then use absolute paths",
                    severity="warning",
                ),
            ),
            # Virtual env detection
            "venv_search": (
                re.compile(r"find.*venv|ls.*env"),
                Intervention(
                    type=InterventionType.HIDDEN_FILES,
                    message="💡 TIP: Looking for virtual environment?",
                    suggestion="Use: find . -name 'activate' -type f 2>/dev/null | grep -E '(venv|env)'",
                    severity="info",
                ),
            ),
            # Inefficient error fixing
            "individual_fixes": (
                re.compile(r'fix.*docstring.*\.py|sed.*"""'),
                Intervention(
                    type=InterventionType.SYNTAX_ERROR_PATTERN,
                    message="🔄 PATTERN: You're fixing errors one by one",
                    suggestion="First collect ALL errors, analyze patterns, then create ONE comprehensive fix",
                    severity="warning",
                ),
            ),
        }

    def check_command(self, command: str) -> Optional[Intervention]:
        """Check if a command triggers any interventions."""
        for name, (pattern, intervention) in self.patterns.items():
            if pattern.match(command):
                return intervention
        return None

    def check_tool_sequence(self, tools: List[str]) -> Optional[Intervention]:
        """Check for inefficient tool usage patterns."""
        # Check for multiple reads that could be batched
        if len(tools) > 3 and all(t.startswith("Read") for t in tools):
            return Intervention(
                type=InterventionType.INEFFICIENT_TOOLS,
                message="🔄 INEFFICIENT: Multiple separate Read operations",
                suggestion="Batch these reads into a single tool call with multiple files",
                severity="info",
            )
        return None

    def generate_preemptive_checks(self, task: str) -> List[str]:
        """Generate preemptive checks based on the task."""
        checks = []

        if "lint" in task or "syntax" in task:
            checks.append("# First, verify virtual environment:")
            checks.append("find . -name 'activate' -type f 2>/dev/null")
            checks.append("# Then collect ALL errors before fixing:")
            checks.append("flake8 . --select E999 > all_syntax_errors.txt")

        if "script" in task:
            checks.append("# Check script type before running:")
            checks.append("file <script> && head -1 <script>")

        if "hidden" in task or "venv" in task:
            checks.append("# Use -la to see hidden files:")
            checks.append("ls -la")

        return checks


def create_monitoring_hook():
    """Creates a monitoring hook for real-time interventions."""
    monitor = ClaudeMonitor()

    def hook(tool_name: str, params: Dict) -> Optional[str]:
        """Hook that runs before each tool execution."""
        intervention_msg = None

        # Check bash commands
        if tool_name == "Bash" and "command" in params:
            intervention = monitor.check_command(params["command"])
            if intervention:
                intervention_msg = f"\n{intervention.message}\n{intervention.suggestion}\n"

        # Check for hidden file issues
        if tool_name == "LS" and "path" in params:
            if not any(opt in str(params) for opt in ["-la", "-a", "all"]):
                intervention_msg = (
                    "\n⚠️ REMINDER: LS tool doesn't show hidden files by default.\n"
                    "Consider using Bash tool with 'ls -la' instead.\n"
                )

        return intervention_msg

    return hook


# Example monitoring rules that could be added to CLAUDE.md
MONITORING_RULES = """
## Real-Time Monitoring Rules

1. **Before using LS tool**: Remember it doesn't show hidden files
   - Always use `ls -la` with Bash tool for complete directory listing
   
2. **Before running scripts**: Check interpreter
   - Bash scripts: use `bash script.sh`
   - Python scripts: use `python3 script.py`
   - Always check: `file <script>` and `head -1 <script>`
   
3. **Virtual environment detection**:
   ```bash
   find . -name 'activate' -type f 2>/dev/null
   ```
   
4. **Syntax error fixing workflow**:
   - FIRST: Collect all errors
   - SECOND: Analyze patterns  
   - THIRD: Create one comprehensive fix
   - FOURTH: Test with dry-run
   
5. **Path navigation**:
   - Always start with `pwd`
   - Use absolute paths
   - Verify location after `cd`
"""

if __name__ == "__main__":
    # Demo
    monitor = ClaudeMonitor()

    test_commands = [
        "ls",
        "python3 cake-lint.sh",
        "cd scripts",
        "find . -name venv",
        "fix_docstring.py",
    ]

    print("Testing monitoring system:\n")
    for cmd in test_commands:
        intervention = monitor.check_command(cmd)
        if intervention:
            print(f"Command: {cmd}")
            print(f"{intervention.message}")
            print(f"{intervention.suggestion}\n")
