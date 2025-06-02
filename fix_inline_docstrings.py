#!/usr/bin/env python3
"""Fix all inline docstrings where code follows """ on the same line."""

import re
from pathlib import Path

def fix_inline_docstrings(filepath: str) -> int:
    """Fix all inline docstrings in a file. Returns count of fixes."""
    file_path = Path(filepath)
    if not file_path.exists():
        print(f"Error: {filepath} not found")
        return 0
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Pattern to match """docstring"""code (with optional spaces)
    # This captures: (indentation)("""docstring""")(code)
    pattern = r'^(\s*)("""[^"]+"""|""".*?""")([a-zA-Z].*)$'
    
    lines = content.split('\n')
    fixed_lines = []
    fix_count = 0
    
    for i, line in enumerate(lines):
        match = re.match(pattern, line)
        if match:
            indent, docstring, code = match.groups()
            # Split into two lines
            fixed_lines.append(indent + docstring)
            fixed_lines.append(indent + code)
            fix_count += 1
            print(f"  Fixed line {i+1}: {line[:60]}...")
        else:
            fixed_lines.append(line)
    
    if fix_count > 0:
        # Write back to file
        with open(file_path, 'w') as f:
            f.write('\n'.join(fixed_lines))
        print(f"Fixed {fix_count} inline docstrings in {filepath}")
    
    return fix_count

def main():
    """Fix all inline docstrings in the project."""
    print("Fixing inline docstring syntax errors...\n")
    
    # Find all Python files with potential issues
    files_to_check = [
        "cake/adapters/cake_adapter.py",
        "cake/adapters/cake_integration.py",
        "cake/adapters/claude_orchestration.py",
        "cake/components/adaptive_confidence_engine.py",
        "cake/components/operator.py",
        "cake/components/recall_db.py",
        "cake/components/semantic_error_classifier.py",
        "cake/components/snapshot_manager.py",
        "cake/components/validator.py",
        "cake/components/voice_similarity_gate.py",
        "cake/core/cake_controller.py",
        "cake/core/escalation_decider.py",
        "cake/core/pty_shim.py",
        "cake/core/stage_router.py",
        "cake/core/trrdevs_engine.py",
        "cake/core/watchdog.py",
        "cake/utils/cross_task_knowledge_ledger.py",
        "cake/utils/info_fetcher.py",
        "cake/utils/rate_limiter.py",
        "cake/utils/rule_creator.py",
    ]
    
    total_fixes = 0
    for filepath in files_to_check:
        fixes = fix_inline_docstrings(filepath)
        total_fixes += fixes
    
    print(f"\nTotal fixes: {total_fixes}")

if __name__ == "__main__":
    main()