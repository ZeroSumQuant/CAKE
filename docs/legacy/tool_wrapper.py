#!/usr/bin/env python3
"""
Tool wrapper that intercepts and modifies tool responses to include interventions.
This would need to be integrated into the actual tool execution pipeline.
"""

import re
from typing import Any, Dict, Optional


class ToolInterceptor:
    """Intercepts tool calls and adds intervention messages to responses."""

    def __init__(self):
        self.intervention_patterns = {
            "ls_command": {
                "pattern": r"^ls\s*$",
                "message": "\n⚠️ INTERVENTION: You used 'ls' without -la flag!\nHidden directories like .venv won't show!\nTry: ls -la\n",
            },
            "python_bash": {
                "pattern": r"python[3]?\s+.*\.sh",
                "message": "\n❌ STOP: You're trying to run a bash script with Python!\nUse: bash script.sh\n",
            },
            "venv_not_found": {
                "error_pattern": r"No such file.*venv",
                "message": "\n💡 HINT: .venv is hidden! Use: find . -name 'activate' -type f\n",
            },
        }

    def wrap_bash_response(self, command: str, response: str) -> str:
        """Wrap bash command responses with interventions."""
        # Check command patterns
        for name, pattern_info in self.intervention_patterns.items():
            if "pattern" in pattern_info:
                if re.match(pattern_info["pattern"], command):
                    return pattern_info["message"] + response

        # Check error patterns in response
        for name, pattern_info in self.intervention_patterns.items():
            if "error_pattern" in pattern_info:
                if re.search(pattern_info["error_pattern"], response):
                    return response + pattern_info["message"]

        return response

    def wrap_ls_response(self, path: str, response: str) -> str:
        """Wrap LS tool responses with warnings."""
        warning = (
            "\n⚠️ NOTE: LS tool doesn't show hidden files (starting with .)\n"
            "To see ALL files including .venv, use Bash tool with: ls -la\n\n"
        )
        return warning + response


# Example of how this would modify responses:
if __name__ == "__main__":
    interceptor = ToolInterceptor()

    # Simulate tool responses
    print("Example 1 - Bad ls command:")
    print(interceptor.wrap_bash_response("ls", "file1.txt\nfile2.txt"))

    print("\nExample 2 - Python running bash:")
    print(
        interceptor.wrap_bash_response("python3 test.sh", "SyntaxError: invalid syntax")
    )

    print("\nExample 3 - Missing venv:")
    print(
        interceptor.wrap_bash_response("cd .venv", "No such file or directory: .venv")
    )
