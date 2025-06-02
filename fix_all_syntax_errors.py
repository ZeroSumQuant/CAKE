#!/usr/bin/env python3
"""
Comprehensive script to fix all docstring syntax errors in the CAKE project.

This script handles multiple patterns of docstring syntax errors:
- Inline docstrings where code follows triple quotes on the same line
- Docstrings where the closing triple quotes has code after it
- Empty docstring bodies with code on the same line

Author: CAKE Team
Usage: python fix_all_syntax_errors.py [--dry-run]
"""

import argparse
import re
from pathlib import Path
from typing import List, Optional, Tuple


class DocstringFixer:
    """Main class for fixing docstring syntax errors."""

    def __init__(self, dry_run: bool = False):
        """Initialize the fixer with dry run option."""
        self.dry_run = dry_run
        self.fixed_count = 0
        self.already_fixed_count = 0
        self.error_count = 0

    def fix_file(self, filepath: str, line_number: int, hint: Optional[str] = None) -> bool:
        """
        Fix docstring error at specific line in file.

        Args:
            filepath: Path to the file
            line_number: Line number with the error (1-based)
            hint: Optional hint about what comes after the docstring

        Returns:
            True if fixed, False otherwise
        """
        file_path = Path(filepath)
        if not file_path.exists():
            print(f"Error: {filepath} not found")
            self.error_count += 1
            return False

        # Read the file
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            self.error_count += 1
            return False

        # Check if line number is valid
        if line_number > len(lines) or line_number < 1:
            print(f"Error: Line {line_number} out of range for {filepath}")
            self.error_count += 1
            return False

        # Get the problematic line (convert to 0-based index)
        idx = line_number - 1
        line = lines[idx].rstrip("\n")

        # Try different fix patterns
        fixed = False

        # Pattern 1: """docstring"""code
        if '"""' in line and line.count('"""') >= 2:
            fixed = self._fix_inline_docstring(lines, idx, line)

        # Pattern 2: """ followed by code on same line
        elif line.strip() == '"""' and hint:
            fixed = self._fix_empty_docstring_with_code(lines, idx, hint)

        # Pattern 3: """docstring""" at end with hint about next line
        elif line.strip().endswith('"""') and hint:
            fixed = self._fix_docstring_with_next_line_hint(lines, idx, hint)

        if fixed and not self.dry_run:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                print(f"✓ Fixed: {filepath}:{line_number}")
                self.fixed_count += 1
            except Exception as e:
                print(f"Error writing {filepath}: {e}")
                self.error_count += 1
                return False
        elif fixed and self.dry_run:
            print(f"[DRY RUN] Would fix: {filepath}:{line_number}")
            self.fixed_count += 1
        else:
            # Check if already fixed
            if self._is_already_fixed(lines, idx):
                print(f"- Already fixed: {filepath}:{line_number}")
                self.already_fixed_count += 1
            else:
                print(f"? Could not fix: {filepath}:{line_number} - Line: {line[:60]}...")
                self.error_count += 1

        return fixed

    def _fix_inline_docstring(self, lines: List[str], idx: int, line: str) -> bool:
        """Fix inline docstring pattern: '''docstring'''code"""
        # Find all """ positions
        quote_positions = []
        pos = 0
        while True:
            pos = line.find('"""', pos)
            if pos == -1:
                break
            quote_positions.append(pos)
            pos += 3

        # Need at least 2 sets of quotes
        if len(quote_positions) < 2:
            return False

        # Get the last closing quote position
        closing_pos = quote_positions[-1]

        # Check if there's code after the closing quotes
        after_quotes = line[closing_pos + 3 :]
        if after_quotes.strip():
            # Get indentation
            indent = len(line) - len(line.lstrip())
            indent_str = " " * indent

            # Split the line
            docstring_part = line[: closing_pos + 3]
            code_part = after_quotes.strip()

            # Replace with two lines
            lines[idx] = docstring_part + "\n"
            lines.insert(idx + 1, indent_str + code_part + "\n")
            return True

        return False

    def _fix_empty_docstring_with_code(self, lines: List[str], idx: int, hint: str) -> bool:
        """Fix pattern where triple quotes is alone but next line needs indentation fix."""
        if idx + 1 < len(lines):
            next_line = lines[idx + 1]
            # Get expected indentation from the docstring line
            indent = len(lines[idx]) - len(lines[idx].lstrip())
            expected_indent = " " * indent

            # Check if next line needs indentation fix
            if next_line.strip() and not next_line.startswith(expected_indent):
                lines[idx + 1] = expected_indent + next_line.lstrip()
                return True

        return False

    def _fix_docstring_with_next_line_hint(self, lines: List[str], idx: int, hint: str) -> bool:
        """Fix pattern where docstring ends correctly but next line is problematic"""
        line = lines[idx]

        # Check if the line ends with """ and has content before it
        if line.strip().endswith('"""') and len(line.strip()) > 3:
            # Check what comes after the """
            quote_pos = line.rfind('"""')
            after_quotes = line[quote_pos + 3 :].strip()

            # If there's hidden content after quotes
            if after_quotes:
                indent = len(line) - len(line.lstrip())
                indent_str = " " * indent

                docstring_part = line[: quote_pos + 3]
                lines[idx] = docstring_part + "\n"
                lines.insert(idx + 1, indent_str + after_quotes + "\n")
                return True

            # Otherwise check if hint suggests there's code on same line we missed
            if hint and any(
                hint.startswith(start) for start in ["self.", "return", "try:", "if ", "for "]
            ):
                # The error might be hidden characters or the parser seeing something we don't
                # Try adding explicit newline
                if not line.endswith("\n"):
                    lines[idx] = line + "\n"
                    return True

        return False

    def _is_already_fixed(self, lines: List[str], idx: int) -> bool:
        """Check if the docstring appears to be already fixed"""
        line = lines[idx].rstrip("\n")

        # If line ends with """ and nothing after, it's likely fixed
        if line.strip().endswith('"""') and line.strip() != '"""':
            # Check if next line has proper indentation
            if idx + 1 < len(lines):
                next_line = lines[idx + 1]
                if next_line.strip():  # Non-empty next line
                    current_indent = len(line) - len(line.lstrip())
                    next_indent = len(next_line) - len(next_line.lstrip())
                    # Proper indentation means it's likely fixed
                    return next_indent == current_indent

        return False

    def print_summary(self):
        """Print summary of fixes."""
        total = self.fixed_count + self.already_fixed_count + self.error_count
        print(f"\n{'='*60}")
        print(f"SUMMARY:")
        print(f"  Total files processed: {total}")
        print(f"  Files fixed: {self.fixed_count}")
        print(f"  Already fixed: {self.already_fixed_count}")
        print(f"  Errors/Could not fix: {self.error_count}")
        print(f"{'='*60}")


def get_all_errors() -> List[Tuple[str, int, Optional[str]]]:
    """
    Return list of all known docstring errors.
    Format: (filepath, line_number, hint_about_next_code)
    """
    return [
        # First batch - inline docstrings
        ("cake/adapters/cake_adapter.py", 188, "self.current_state"),
        ("cake/adapters/cake_adapter.py", 201, "if self.current_state"),
        ("cake/adapters/cake_adapter.py", 214, "self.current_state"),
        ("cake/adapters/cake_adapter.py", 217, "self.current_state"),
        ("cake/adapters/cake_adapter.py", 220, "return self.knowledge_ledger"),
        ("cake/adapters/cake_adapter.py", 244, "return self.validator"),
        ("cake/adapters/cake_adapter.py", 253, "return {"),
        ("cake/adapters/cake_adapter.py", 264, "self.pre_message_hooks"),
        ("cake/adapters/cake_adapter.py", 267, "self.post_message_hooks"),
        ("cake/adapters/cake_adapter.py", 270, "self.recall_db"),
        ("cake/adapters/cake_adapter.py", 279, "self.current_state"),
        ("cake/adapters/cake_adapter.py", 288, "return {"),
        ("cake/adapters/cake_adapter.py", 311, "self.intervention_count"),
        ("cake/adapters/cake_adapter.py", 328, "for hook in"),
        ("cake/adapters/cake_adapter.py", 338, "for hook in"),
        # cake_integration.py
        ("cake/adapters/cake_integration.py", 185, "return self.adapter"),
        ("cake/adapters/cake_integration.py", 216, "result = {"),
        ("cake/adapters/cake_integration.py", 236, "desc_lower ="),
        ("cake/adapters/cake_integration.py", 269, "formatted = []"),
        ("cake/adapters/cake_integration.py", 292, "if context.intervention_type"),
        # claude_orchestration.py - many entries
        ("cake/adapters/claude_orchestration.py", 650, "self.templates"),
        ("cake/adapters/claude_orchestration.py", 655, "return self.templates"),
        ("cake/adapters/claude_orchestration.py", 658, "template_ids ="),
        ("cake/adapters/claude_orchestration.py", 664, "candidates ="),
        ("cake/adapters/claude_orchestration.py", 685, "score = 0.0"),
        ("cake/adapters/claude_orchestration.py", 712, "if not self.templates_path"),
        ("cake/adapters/claude_orchestration.py", 742, "self.enhancement_strategies"),
        ("cake/adapters/claude_orchestration.py", 768, "enhanced = {"),
        ("cake/adapters/claude_orchestration.py", 781, "if not context.error_context"),
        ("cake/adapters/claude_orchestration.py", 804, "if not context.knowledge_retrieved"),
        ("cake/adapters/claude_orchestration.py", 823, "domain_info ="),
        ("cake/adapters/claude_orchestration.py", 842, "constraints = []"),
        ("cake/adapters/claude_orchestration.py", 867, "enhanced = {}"),
        ("cake/adapters/claude_orchestration.py", 883, "if not classification"),
        ("cake/adapters/claude_orchestration.py", 901, "if not knowledge_list"),
        ("cake/adapters/claude_orchestration.py", 916, "requirements = []"),
        ("cake/adapters/claude_orchestration.py", 929, "standards = []"),
        ("cake/adapters/claude_orchestration.py", 945, "self.quality_metrics"),
        ("cake/adapters/claude_orchestration.py", 1066, "clarity_indicators"),
        ("cake/adapters/claude_orchestration.py", 1078, "actionability_indicators"),
        ("cake/adapters/claude_orchestration.py", 1102, "if not expected_format"),
        ("cake/adapters/claude_orchestration.py", 1122, "extracted = {}"),
        ("cake/adapters/claude_orchestration.py", 1160, "if score >= 0.9"),
        ("cake/adapters/claude_orchestration.py", 1223, "formatting_indicators"),
        ("cake/adapters/claude_orchestration.py", 1232, "issues = []"),
        ("cake/adapters/claude_orchestration.py", 1373, "try:"),
        ("cake/adapters/claude_orchestration.py", 1394, "self.execution_history"),
        ("cake/adapters/claude_orchestration.py", 1439, "recommendations = []"),
        ("cake/adapters/claude_orchestration.py", 1490, "template ="),
        ("cake/adapters/claude_orchestration.py", 1526, "if not self.execution_history"),
        ("cake/adapters/claude_orchestration.py", 1572, "timestamp ="),
        ("cake/adapters/claude_orchestration.py", 1577, 'if "json" in'),
        ("cake/adapters/claude_orchestration.py", 1588, "quality_scores = {"),
        ("cake/adapters/claude_orchestration.py", 1598, "patterns = []"),
        ("cake/adapters/claude_orchestration.py", 1655, "history_file ="),
        ("cake/adapters/claude_orchestration.py", 1673, "history_file ="),
        # Components
        ("cake/components/adaptive_confidence_engine.py", 162, "if value is None"),
        ("cake/components/adaptive_confidence_engine.py", 184, "self.prior_alpha"),
        ("cake/components/adaptive_confidence_engine.py", 254, "self.strategy_performance"),
        ("cake/components/adaptive_confidence_engine.py", 273, "stats ="),
        ("cake/components/adaptive_confidence_engine.py", 299, "stats ="),
        ("cake/components/adaptive_confidence_engine.py", 328, "return ((current_avg"),
        ("cake/components/adaptive_confidence_engine.py", 331, "if self.global_metrics"),
        ("cake/components/adaptive_confidence_engine.py", 373, "db_path ="),
        ("cake/components/adaptive_confidence_engine.py", 579, "if not outcomes"),
        ("cake/components/adaptive_confidence_engine.py", 591, "if not features1"),
        ("cake/components/adaptive_confidence_engine.py", 609, "success_rate ="),
        ("cake/components/adaptive_confidence_engine.py", 627, "base_scores = {"),
        ("cake/components/adaptive_confidence_engine.py", 652, "lessons = {"),
        ("cake/components/adaptive_confidence_engine.py", 678, "if pattern_signature"),
        ("cake/components/adaptive_confidence_engine.py", 711, "if context_hash"),
        ("cake/components/adaptive_confidence_engine.py", 726, "self.outcome_database"),
        ("cake/components/adaptive_confidence_engine.py", 756, "if abs(adapted"),
        ("cake/components/adaptive_confidence_engine.py", 786, "patterns_file ="),
        ("cake/components/adaptive_confidence_engine.py", 791, "patterns_file ="),
        ("cake/components/adaptive_confidence_engine.py", 801, "total_patterns ="),
        ("cake/components/adaptive_confidence_engine.py", 822, "cutoff_date ="),
        ("cake/components/adaptive_confidence_engine.py", 837, "error_lower ="),
        ("cake/components/adaptive_confidence_engine.py", 858, "task ="),
        # More components
        ("cake/components/operator.py", 203, "error_details ="),
        ("cake/components/operator.py", 239, "ci_status ="),
        ("cake/components/operator.py", 255, "error_details ="),
        ("cake/components/operator.py", 276, "task_context ="),
        ("cake/components/operator.py", 292, "task_context ="),
        ("cake/components/operator.py", 308, "coverage ="),
        ("cake/components/operator.py", 326, "ci_status ="),
        ("cake/components/operator.py", 335, "error_details ="),
        ("cake/components/operator.py", 355, "error_details ="),
        ("cake/components/operator.py", 375, "task_context ="),
        ("cake/components/operator.py", 393, "if len(self.intervention_history)"),
        ("cake/components/operator.py", 403, "if not self.intervention_history"),
        ("cake/components/operator.py", 422, "self.pattern_matchers = {"),
        ("cake/components/operator.py", 458, "current_error ="),
        ("cake/components/operator.py", 487, 'if state.get("action")'),
        ("cake/components/operator.py", 503, 'if state.get("action")'),
        ("cake/components/operator.py", 523, "task_type ="),
        ("cake/components/operator.py", 551, 'if state.get("action")'),
        ("cake/components/operator.py", 574, "coverage ="),
        ("cake/components/operator.py", 594, 'if state.get("action")'),
        ("cake/components/operator.py", 614, "command ="),
        ("cake/components/operator.py", 639, "code_analysis ="),
        ("cake/components/operator.py", 670, "task_context ="),
        ("cake/components/operator.py", 712, "for scope_item"),
        # RecallDB
        ("cake/components/recall_db.py", 81, "self.db_path"),
        ("cake/components/recall_db.py", 97, "with self._get_connection()"),
        ("cake/components/recall_db.py", 176, "conn = sqlite3.connect"),
        ("cake/components/recall_db.py", 379, "with self._get_connection()"),
        ("cake/components/recall_db.py", 502, "with self._get_connection()"),
        ("cake/components/recall_db.py", 589, "return hashlib.md5"),
        ("cake/components/recall_db.py", 595, "self.db = recall_db"),
        ("cake/components/recall_db.py", 598, "with self.db._get_connection()"),
        # Semantic Error Classifier
        ("cake/components/semantic_error_classifier.py", 316, "for pattern_name"),
        ("cake/components/semantic_error_classifier.py", 337, "features = {"),
        ("cake/components/semantic_error_classifier.py", 360, "normalized ="),
        ("cake/components/semantic_error_classifier.py", 398, "matches = []"),
        ("cake/components/semantic_error_classifier.py", 437, "entities = {"),
        ("cake/components/semantic_error_classifier.py", 478, "severity_keywords = {"),
        ("cake/components/semantic_error_classifier.py", 514, "clues = {"),
        ("cake/components/semantic_error_classifier.py", 575, "actionable_elements = []"),
        ("cake/components/semantic_error_classifier.py", 630, "hierarchy = {"),
        ("cake/components/semantic_error_classifier.py", 655, "base_confidence = 0.7"),
        ("cake/components/semantic_error_classifier.py", 674, "if not error_messages"),
        ("cake/components/semantic_error_classifier.py", 707, "if not self.is_fitted"),
        ("cake/components/semantic_error_classifier.py", 750, "self.persistence_path"),
        ("cake/components/semantic_error_classifier.py", 811, "if signature.signature_id"),
        ("cake/components/semantic_error_classifier.py", 837, "candidates = []"),
        ("cake/components/semantic_error_classifier.py", 860, "similarity = 0.0"),
        ("cake/components/semantic_error_classifier.py", 900, "signatures_file ="),
        ("cake/components/semantic_error_classifier.py", 916, "signatures_file ="),
        ("cake/components/semantic_error_classifier.py", 935, "if not self.signatures"),
        ("cake/components/semantic_error_classifier.py", 1081, "if self.signature_db"),
        ("cake/components/semantic_error_classifier.py", 1142, "return {"),
        ("cake/components/semantic_error_classifier.py", 1158, "error_type ="),
        ("cake/components/semantic_error_classifier.py", 1184, "suggestions = []"),
        ("cake/components/semantic_error_classifier.py", 1235, "hint_expansions = {"),
        ("cake/components/semantic_error_classifier.py", 1283, "suggestions = []"),
        ("cake/components/semantic_error_classifier.py", 1327, "insights = {"),
        ("cake/components/semantic_error_classifier.py", 1366, "related = []"),
        ("cake/components/semantic_error_classifier.py", 1383, "urgency = 0.0"),
        ("cake/components/semantic_error_classifier.py", 1412, "factors = {}"),
        ("cake/components/semantic_error_classifier.py", 1441, "complexity = 0.0"),
        ("cake/components/semantic_error_classifier.py", 1497, "stats = {"),
        ("cake/components/semantic_error_classifier.py", 1514, "if not self.signature_db"),
        # Snapshot Manager
        ("cake/components/snapshot_manager.py", 135, "snapshot = self.snapshots"),
        ("cake/components/snapshot_manager.py", 230, "sorted_snapshots ="),
        ("cake/components/snapshot_manager.py", 234, "cutoff ="),
        ("cake/components/snapshot_manager.py", 251, "result ="),
        ("cake/components/snapshot_manager.py", 261, "result ="),
        ("cake/components/snapshot_manager.py", 271, "result ="),
        ("cake/components/snapshot_manager.py", 290, "content ="),
        ("cake/components/snapshot_manager.py", 294, "index_data = {"),
        ("cake/components/snapshot_manager.py", 315, "try:"),
        ("cake/components/snapshot_manager.py", 342, "stash_list ="),
        ("cake/components/snapshot_manager.py", 361, "self.cake_adapter"),
        ("cake/components/snapshot_manager.py", 368, "if context.intervention_type"),
        # Validator
        ("cake/components/validator.py", 200, "text_hash ="),
        ("cake/components/validator.py", 204, "sentence_lower ="),
        ("cake/components/validator.py", 219, "implicit = []"),
        ("cake/components/validator.py", 263, "unique_reqs = []"),
        ("cake/components/validator.py", 288, 'return {"critical"'),
        ("cake/components/validator.py", 296, "self.client = claude_client"),
        ("cake/components/validator.py", 320, "analysis = {"),
        ("cake/components/validator.py", 376, "req_keywords ="),
        ("cake/components/validator.py", 447, "result = {"),
        ("cake/components/validator.py", 580, "self.client = claude_client"),
        # Voice Similarity Gate
        ("cake/components/voice_similarity_gate.py", 152, "try:"),
        ("cake/components/voice_similarity_gate.py", 259, "for pattern in"),
        ("cake/components/voice_similarity_gate.py", 271, "try:"),
        ("cake/components/voice_similarity_gate.py", 286, "suggestions = []"),
        ("cake/components/voice_similarity_gate.py", 318, "return self.reference_messages"),
        # Core modules
        ("cake/core/cake_controller.py", 96, "return {"),
        ("cake/core/cake_controller.py", 149, "try:"),
        ("cake/core/cake_controller.py", 243, "return self.validator"),
        ("cake/core/cake_controller.py", 246, "if task_id not in"),
        ("cake/core/cake_controller.py", 260, "if task_id not in"),
        # Escalation Decider
        ("cake/core/escalation_decider.py", 153, "critical_errors ="),
        ("cake/core/escalation_decider.py", 157, "return EscalationDecision("),
        ("cake/core/escalation_decider.py", 172, "key ="),
        ("cake/core/escalation_decider.py", 178, "key ="),
        ("cake/core/escalation_decider.py", 190, "thresholds ="),
        ("cake/core/escalation_decider.py", 222, "if level =="),
        ("cake/core/escalation_decider.py", 238, "if level =="),
        ("cake/core/escalation_decider.py", 266, "actions_map = {"),
        ("cake/core/escalation_decider.py", 302, "cooldowns ="),
        ("cake/core/escalation_decider.py", 306, "self.escalation_history"),
        # PTY Shim
        ("cake/core/pty_shim.py", 268, "command_lower ="),
        ("cake/core/pty_shim.py", 291, "command_lower ="),
        ("cake/core/pty_shim.py", 295, "msg ="),
        ("cake/core/pty_shim.py", 305, "text ="),
        ("cake/core/pty_shim.py", 318, "self.command_history"),
        ("cake/core/pty_shim.py", 325, "return ["),
        ("cake/core/pty_shim.py", 334, "self.cake_adapter ="),
        ("cake/core/pty_shim.py", 351, "logger.info("),
        # Stage Router
        ("cake/core/stage_router.py", 138, "G = nx.DiGraph()"),
        ("cake/core/stage_router.py", 187, "if stage not in"),
        ("cake/core/stage_router.py", 277, "try:"),
        ("cake/core/stage_router.py", 286, "return self.graph"),
        ("cake/core/stage_router.py", 289, "try:"),
        ("cake/core/stage_router.py", 302, "try:"),
        ("cake/core/stage_router.py", 309, "summary = {}"),
        ("cake/core/stage_router.py", 326, "if not self._is_valid_transition"),
        ("cake/core/stage_router.py", 365, "constraints = constraints or {}"),
        ("cake/core/stage_router.py", 385, "if not self.history"),
        ("cake/core/stage_router.py", 405, "sorted_transitions ="),
        ("cake/core/stage_router.py", 411, "completed_paths = []"),
        ("cake/core/stage_router.py", 424, "failure_counts = {}"),
        # TRRDEVS Engine
        ("cake/core/trrdevs_engine.py", 77, "self.stage_handlers[stage]"),
        ("cake/core/trrdevs_engine.py", 169, "return {"),
        ("cake/core/trrdevs_engine.py", 176, 'return {"resources_found"'),
        ("cake/core/trrdevs_engine.py", 179, 'return {"options_considered"'),
        ("cake/core/trrdevs_engine.py", 182, "return {"),
        ("cake/core/trrdevs_engine.py", 189, 'return {"implementation"'),
        ("cake/core/trrdevs_engine.py", 192, 'return {"tests_passed"'),
        ("cake/core/trrdevs_engine.py", 195, "return {"),
        ("cake/core/trrdevs_engine.py", 202, "return ["),
        # Watchdog
        ("cake/core/watchdog.py", 76, "try:"),
        ("cake/core/watchdog.py", 90, "self.callbacks.append(callback)"),
        ("cake/core/watchdog.py", 203, "self._monitoring = False"),
        ("cake/core/watchdog.py", 213, "return {"),
        # Utils
        ("cake/utils/cross_task_knowledge_ledger.py", 199, "knowledge_entries = []"),
        ("cake/utils/cross_task_knowledge_ledger.py", 218, "entries = []"),
        ("cake/utils/cross_task_knowledge_ledger.py", 265, "entries = []"),
        ("cake/utils/cross_task_knowledge_ledger.py", 295, "entries = []"),
        ("cake/utils/cross_task_knowledge_ledger.py", 334, "entries = []"),
        ("cake/utils/cross_task_knowledge_ledger.py", 367, "entries = []"),
        ("cake/utils/cross_task_knowledge_ledger.py", 404, "entries = []"),
        ("cake/utils/cross_task_knowledge_ledger.py", 454, "entries = []"),
        ("cake/utils/cross_task_knowledge_ledger.py", 493, "entries = []"),
        ("cake/utils/cross_task_knowledge_ledger.py", 530, "signature ="),
        ("cake/utils/cross_task_knowledge_ledger.py", 534, "tags = {"),
        ("cake/utils/cross_task_knowledge_ledger.py", 544, "desc_lower ="),
        ("cake/utils/cross_task_knowledge_ledger.py", 564, "indicators = {"),
        ("cake/utils/cross_task_knowledge_ledger.py", 596, "base_confidence = 0.7"),
        ("cake/utils/cross_task_knowledge_ledger.py", 632, "patterns = {"),
        ("cake/utils/cross_task_knowledge_ledger.py", 658, "base_score = 0.5"),
        ("cake/utils/cross_task_knowledge_ledger.py", 679, "requirements = []"),
        ("cake/utils/cross_task_knowledge_ledger.py", 712, "heuristics = []"),
        ("cake/utils/cross_task_knowledge_ledger.py", 735, "heuristics = []"),
        ("cake/utils/cross_task_knowledge_ledger.py", 749, "heuristics = []"),
        ("cake/utils/cross_task_knowledge_ledger.py", 763, "heuristics = []"),
        ("cake/utils/cross_task_knowledge_ledger.py", 777, "categories = defaultdict(set)"),
        ("cake/utils/cross_task_knowledge_ledger.py", 800, "if task.performance_metrics"),
        ("cake/utils/cross_task_knowledge_ledger.py", 808, "techniques = []"),
        ("cake/utils/cross_task_knowledge_ledger.py", 834, "self.db = knowledge_database"),
        ("cake/utils/cross_task_knowledge_ledger.py", 839, "self.knowledge_graph"),
        ("cake/utils/cross_task_knowledge_ledger.py", 907, "relevance = 0.0"),
        ("cake/utils/cross_task_knowledge_ledger.py", 948, "tags = set()"),
        ("cake/utils/cross_task_knowledge_ledger.py", 972, "error_lower ="),
        ("cake/utils/cross_task_knowledge_ledger.py", 991, "desc_lower ="),
        ("cake/utils/cross_task_knowledge_ledger.py", 1073, "db_path ="),
        ("cake/utils/cross_task_knowledge_ledger.py", 1235, "self.database.execute("),
        ("cake/utils/cross_task_knowledge_ledger.py", 1332, "guidance_templates = {"),
        ("cake/utils/cross_task_knowledge_ledger.py", 1351, "if not entry.prerequisites"),
        ("cake/utils/cross_task_knowledge_ledger.py", 1369, "self.database.execute("),
        ("cake/utils/cross_task_knowledge_ledger.py", 1425, "return {"),
        ("cake/utils/cross_task_knowledge_ledger.py", 1436, "cursor ="),
        ("cake/utils/cross_task_knowledge_ledger.py", 1441, "cursor ="),
        ("cake/utils/cross_task_knowledge_ledger.py", 1462, "cutoff ="),
        ("cake/utils/cross_task_knowledge_ledger.py", 1485, "cutoff ="),
        # Info Fetcher
        ("cake/utils/info_fetcher.py", 71, "query_hash ="),
        ("cake/utils/info_fetcher.py", 77, "cache_path ="),
        ("cake/utils/info_fetcher.py", 106, "cache_path ="),
        ("cake/utils/info_fetcher.py", 188, "query_lower ="),
        ("cake/utils/info_fetcher.py", 210, "if source not in"),
        ("cake/utils/info_fetcher.py", 293, "results = []"),
        ("cake/utils/info_fetcher.py", 319, "try:"),
        ("cake/utils/info_fetcher.py", 329, "return ["),
        ("cake/utils/info_fetcher.py", 391, "results = []"),
        ("cake/utils/info_fetcher.py", 418, "path ="),
        ("cake/utils/info_fetcher.py", 444, "self.cache_dir = cache_dir"),
        ("cake/utils/info_fetcher.py", 500, "query_lower ="),
        ("cake/utils/info_fetcher.py", 522, "if not results"),
        ("cake/utils/info_fetcher.py", 587, "try:"),
        ("cake/utils/info_fetcher.py", 617, "cutoff ="),
        # Rate Limiter
        ("cake/utils/rate_limiter.py", 265, "key ="),
        ("cake/utils/rate_limiter.py", 283, "global _tracer, _meter"),
        ("cake/utils/rate_limiter.py", 363, "if not _meter"),
        ("cake/utils/rate_limiter.py", 385, "if not _tracer"),
        # Rule Creator
        ("cake/utils/rule_creator.py", 120, "self.expr_patterns ="),
        ("cake/utils/rule_creator.py", 130, "issues = []"),
        ("cake/utils/rule_creator.py", 154, "issues = []"),
        ("cake/utils/rule_creator.py", 187, "issues = []"),
        ("cake/utils/rule_creator.py", 276, "return {"),
        ("cake/utils/rule_creator.py", 351, "for error_type"),
        ("cake/utils/rule_creator.py", 400, "prompt ="),
        ("cake/utils/rule_creator.py", 413, 'prompt = f"""'),
        ("cake/utils/rule_creator.py", 518, "try:"),
        ("cake/utils/rule_creator.py", 574, "is_valid, issues ="),
        ("cake/utils/rule_creator.py", 626, "if proposal.safety_score"),
        ("cake/utils/rule_creator.py", 673, "data = {"),
        ("cake/utils/rule_creator.py", 686, "return {"),
        ("cake/utils/rule_creator.py", 703, "counts = {}"),
        ("cake/utils/rule_creator.py", 712, "patterns = {}"),
        # Special case - need to check
        ("cake/adapters/cake_adapter.py", 236, "msg = ConversationMessage("),
    ]


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Fix all docstring syntax errors in CAKE project")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be fixed without making changes"
    )
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"CAKE Docstring Syntax Error Fixer")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'FIXING'}")
    print(f"{'='*60}\n")

    # Create fixer
    fixer = DocstringFixer(dry_run=args.dry_run)

    # Get all errors
    errors = get_all_errors()
    print(f"Processing {len(errors)} known syntax errors...\n")

    # Fix each error
    for filepath, line_number, hint in errors:
        fixer.fix_file(filepath, line_number, hint)

    # Print summary
    fixer.print_summary()

    if args.dry_run:
        print("\nRun without --dry-run to apply fixes.")


if __name__ == "__main__":
    main()
