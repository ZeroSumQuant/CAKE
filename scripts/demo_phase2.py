#!/usr/bin/env python3
"""Demo Phase 2 transformations without shell prompts."""

import itertools
import os
import re
import subprocess
from pathlib import Path

# Set environment to skip git/shell
os.environ["CHATGPT_SANDBOX"] = "1"

# Find project root
root = Path(__file__).resolve().parent.parent

# Run cleanup script
cmd = ["python3", "scripts/master_cleanup.py", "--dry-run", "--skip-shell", str(root)]
print(f"Running: {' '.join(cmd)}\n")

result = subprocess.run(cmd, capture_output=True, text=True)

# Filter output for relevant lines
pattern = re.compile(r"(phase2|✓|exit_code|control_block|missing_pass)", re.IGNORECASE)

# Get all matching lines
all_matches = [line for line in result.stdout.splitlines() if pattern.search(line)]

# Show last 20 matches
print("=== Last 20 relevant lines ===")
for line in all_matches[-20:]:
    print(line)

# Show any errors
if result.stderr:
    print("\n=== Errors ===")
    print(result.stderr)

print(f"\nExit status: {result.returncode}")

# Check summary file
summary_files = sorted(Path("cleanup_reports").glob("*-summary.json"))
if summary_files:
    latest = summary_files[-1]
    print(f"\nLatest summary: {latest}")

    import json

    with open(latest) as f:
        summary = json.load(f)
        print(f"Exit code in summary: {summary.get('exit_code', 'N/A')}")
        print(f"Phases run: {len(summary.get('phases', []))}")

        # Check for syntax errors in final state
        final_phase = summary["phases"][-1] if summary["phases"] else {}
        syntax_errors = final_phase.get("syntax_errors", [])
        if syntax_errors:
            print(f"Syntax errors: {len(syntax_errors)}")
            for err in syntax_errors[:3]:  # Show first 3
                print(f"  - {err['file']}: {err['error']}")
