#!/usr/bin/env python3
"""
Claude Watchdog - Real-time monitoring of Claude's actions.
Runs in background and creates intervention files when errors detected.
"""

import os
import queue
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class ClaudeWatchdog:
    """Monitors file system and command history for Claude's mistakes."""

    def __init__(self):
        self.watch_dir = Path("/Users/dustinkirby/Documents/GitHub/CAKE")
        self.intervention_file = self.watch_dir / "CLAUDE_STOP.txt"
        self.log_file = self.watch_dir / "claude_watchdog.log"
        self.patterns = self._init_patterns()
        self.last_check = datetime.now()
        self.intervention_queue = queue.Queue()

    def _init_patterns(self) -> Dict[str, Dict]:
        """Initialize error patterns to watch for."""
        return {
            "multiple_fix_scripts": {
                "pattern": r"fix_.*\.py",
                "threshold": 3,
                "message": "🛑 STOP! You're creating multiple fix scripts!\nCollect ALL errors first, then create ONE comprehensive fix!",
                "check": "file_creation",
            },
            "wrong_interpreter": {
                "pattern": r"python[3]?\s+.*\.(sh|bash)",
                "message": "❌ STOP! You're running a bash script with Python!\nUse: bash script.sh",
                "check": "command",
            },
            "hidden_file_miss": {
                "pattern": r"(No such file.*venv|cannot find.*env)",
                "message": "💡 STOP! .venv is a hidden directory!\nUse: find . -name 'activate' -type f",
                "check": "error",
            },
            "bare_ls": {
                "pattern": r"^ls\s*$",
                "message": "⚠️ STOP! Use 'ls -la' to see hidden files!",
                "check": "command",
            },
        }

    def create_intervention(self, pattern_name: str, details: str = ""):
        """Create an intervention file that Claude will see."""
        intervention = self.patterns[pattern_name]["message"]

        content = f"""
╔══════════════════════════════════════════════════════════════╗
║                    🛑 CLAUDE INTERVENTION 🛑                 ║
╚══════════════════════════════════════════════════════════════╝

{intervention}

Detected at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Pattern: {pattern_name}
Details: {details}

This file will auto-delete after you read it.
╚══════════════════════════════════════════════════════════════╝
"""

        # Write intervention file
        with open(self.intervention_file, "w") as f:
            f.write(content)

        # Log it
        self._log(f"Intervention created: {pattern_name}")

        # Auto-cleanup after 30 seconds
        threading.Timer(30.0, self._cleanup_intervention).start()

    def _cleanup_intervention(self):
        """Remove intervention file after delay."""
        if self.intervention_file.exists():
            self.intervention_file.unlink()
            self._log("Intervention file cleaned up")

    def monitor_file_creation(self):
        """Monitor for problematic file creation patterns."""
        # Check for multiple fix scripts created recently
        fix_scripts = list(self.watch_dir.glob("fix_*.py"))
        recent_scripts = [f for f in fix_scripts if f.stat().st_mtime > self.last_check.timestamp()]

        if len(recent_scripts) >= 3:
            self.create_intervention(
                "multiple_fix_scripts", f"Found {len(recent_scripts)} fix scripts created"
            )

    def monitor_commands(self):
        """Monitor recent bash history for problematic commands."""
        try:
            # Get recent bash history (last 10 commands)
            result = subprocess.run(
                ["tail", "-10", os.path.expanduser("~/.bash_history")],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                recent_commands = result.stdout.strip().split("\n")

                for cmd in recent_commands:
                    # Check each pattern
                    for pattern_name, pattern_info in self.patterns.items():
                        if pattern_info["check"] == "command":
                            if re.search(pattern_info["pattern"], cmd):
                                self.create_intervention(pattern_name, f"Command: {cmd}")
                                return
        except Exception as e:
            self._log(f"Error monitoring commands: {e}")

    def monitor_errors(self):
        """Monitor for error patterns in recent output files."""
        # Check recent log files for error patterns
        log_files = list(self.watch_dir.glob("**/*.log"))
        recent_logs = [f for f in log_files if f.stat().st_mtime > self.last_check.timestamp()]

        for log_file in recent_logs:
            try:
                with open(log_file, "r") as f:
                    content = f.read()

                for pattern_name, pattern_info in self.patterns.items():
                    if pattern_info["check"] == "error":
                        if re.search(pattern_info["pattern"], content):
                            self.create_intervention(pattern_name, f"Found in {log_file.name}")
                            return
            except:
                pass

    def _log(self, message: str):
        """Log watchdog activity."""
        with open(self.log_file, "a") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")

    def run(self, check_interval: int = 5):
        """Run the watchdog monitoring loop."""
        print(f"🐕 Claude Watchdog started!")
        print(f"Monitoring: {self.watch_dir}")
        print(f"Intervention file: {self.intervention_file}")
        print(f"Check interval: {check_interval}s")
        print("\nPress Ctrl+C to stop")

        self._log("Watchdog started")

        try:
            while True:
                # Run all monitors
                self.monitor_file_creation()
                self.monitor_commands()
                self.monitor_errors()

                # Update last check time
                self.last_check = datetime.now()

                # Wait before next check
                time.sleep(check_interval)

        except KeyboardInterrupt:
            print("\n🛑 Watchdog stopped")
            self._log("Watchdog stopped")


def main():
    """Run the watchdog."""
    watchdog = ClaudeWatchdog()
    watchdog.run()


if __name__ == "__main__":
    main()
