#!/usr/bin/env python3
"""Validates intervention messages against Dustin's voice style.

This script ensures that CAKE's Operator component generates messages that match
Dustin's intervention style with ≥90% similarity.

Usage:
    python cake-check-voice.py --message "Operator (CAKE): Stop. Run tests. See output."
    python cake-check-voice.py --file messages.txt
    python cake-check-voice.py --interactive
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class VoiceCheckResult:
    """Result of voice similarity check."""

    message: str
    score: float
    passed: bool
    issues: List[str]
    suggestions: List[str]


class DustinVoiceValidator:
    """Validates messages against Dustin's intervention style."""

    # Dustin's approved action verbs
    APPROVED_VERBS = {"Run", "Check", "Fix", "Try", "See"}

    # Expected message format
    MESSAGE_PATTERN = r"^Operator \(CAKE\): (Stop\.|Hold on\.|Wait\.) (.+)\. (.+)\.$"

    # Dustin's style characteristics
    MAX_SENTENCES = 3
    MAX_MESSAGE_LENGTH = 150

    def __init__(self) -> None:
        """Initialize validator with Dustin's voice patterns."""
        # Common patterns in Dustin's interventions
        self.dustin_patterns = {
            "directness": [
                "Run {command}",
                "Check {file}",
                "Fix {error}",
                "Try {solution}",
                "See {output}",
            ],
            "references": [
                "See line {num}",
                "Check output above",
                "Review error message",
                "See test results",
                "Check logs",
            ],
            "avoid_words": [
                "please",
                "could",
                "would",
                "should",
                "maybe",
                "perhaps",
                "might",
                "sorry",
                "excuse",
            ],
        }

    def check_message(self, message: str) -> VoiceCheckResult:
        """Check if message matches Dustin's voice."""
        issues: List[str] = []
        suggestions: List[str] = []
        score: float = 100.0

        # Check various aspects and collect issues
        score = self._check_format_and_update_score(message, issues, score)
        score = self._check_length_and_update_score(message, issues, score)
        score = self._check_sentences_and_update_score(message, issues, score)
        score = self._check_verbs_and_update_score(message, issues, score)
        score = self._check_directness_and_update_score(message, score)
        score = self._check_avoided_words_and_update_score(message, issues, score)

        # Generate suggestions if needed
        if score < 90:
            suggestions = self._generate_suggestions(message, issues)

        # Ensure score is between 0 and 100
        score = max(0, min(100, score))

        return VoiceCheckResult(
            message=message, score=score, passed=score >= 90, issues=issues, suggestions=suggestions
        )

    def _check_format_and_update_score(
        self, message: str, issues: List[str], score: float
    ) -> float:
        """Check format and update score accordingly."""
        if not self._check_format(message):
            issues.append(
                "Invalid format. Must be: 'Operator (CAKE): Stop. {action}. {reference}.'"
            )
            score -= 30
        return score

    def _check_length_and_update_score(
        self, message: str, issues: List[str], score: float
    ) -> float:
        """Check message length and update score."""
        if len(message) > self.MAX_MESSAGE_LENGTH:
            issues.append(
                f"Message too long ({len(message)} chars). Max: {self.MAX_MESSAGE_LENGTH}"
            )
            score -= 10
        return score

    def _check_sentences_and_update_score(
        self, message: str, issues: List[str], score: float
    ) -> float:
        """Check sentence count and update score."""
        sentences = message.count(".")
        if sentences > self.MAX_SENTENCES:
            issues.append(f"Too many sentences ({sentences}). Max: {self.MAX_SENTENCES}")
            score -= 15
        return score

    def _check_verbs_and_update_score(self, message: str, issues: List[str], score: float) -> float:
        """Check approved verbs and update score."""
        verb_score = self._check_verbs(message)
        if verb_score < 100:
            issues.append("Use only approved verbs: Run, Check, Fix, Try, See")
            score -= (100 - verb_score) * 0.2
        return score

    def _check_directness_and_update_score(self, message: str, score: float) -> float:
        """Check directness and update score."""
        directness_score = self._check_directness(message)
        score -= (100 - directness_score) * 0.15
        return score

    def _check_avoided_words_and_update_score(
        self, message: str, issues: List[str], score: float
    ) -> float:
        """Check for avoided words and update score."""
        avoided = self._check_avoided_words(message)
        if avoided:
            issues.append(f"Remove polite/uncertain words: {', '.join(avoided)}")
            score -= len(avoided) * 5
        return score

    def _check_format(self, message: str) -> bool:
        """Check if message matches expected format."""
        return bool(re.match(self.MESSAGE_PATTERN, message))

    def _check_verbs(self, message: str) -> float:
        """Check if message uses approved verbs."""
        # Extract the action part
        match = re.match(self.MESSAGE_PATTERN, message)
        if not match:
            return 0

        action = match.group(2)
        words = action.split()

        # First word should be an approved verb
        if not words:
            return 0

        return 100 if words[0] in self.APPROVED_VERBS else 50

    def _check_directness(self, message: str) -> float:
        """Check how direct and imperative the message is."""
        score = 100

        # Penalize questions
        if "?" in message:
            score -= 20

        # Penalize explanations (words like "because", "since", etc.)
        explanation_words = ["because", "since", "as", "due to", "owing to"]
        for word in explanation_words:
            if word.lower() in message.lower():
                score -= 10

        return max(0, score)

    def _check_avoided_words(self, message: str) -> List[str]:
        """Find polite/uncertain words that should be avoided."""
        found = []
        message_lower = message.lower()

        for word in self.dustin_patterns["avoid_words"]:
            if word in message_lower:
                found.append(word)

        return found

    def _generate_suggestions(self, message: str, issues: List[str]) -> List[str]:
        """Generate suggestions to improve the message."""
        suggestions = []

        # Try to extract intent and rebuild
        match = re.match(r".*?: (.+)", message)
        if match:
            content = match.group(1)

            # Identify likely action
            if "test" in content.lower():
                suggestions.append("Operator (CAKE): Stop. Run pytest. See test results.")
            elif "error" in content.lower():
                suggestions.append("Operator (CAKE): Stop. Check error output. Fix import.")
            elif "install" in content.lower():
                suggestions.append("Operator (CAKE): Stop. Run pip install. Check requirements.")
            else:
                suggestions.append("Operator (CAKE): Stop. Check issue. Try solution.")

        return suggestions


def _create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description="Validate CAKE intervention messages against Dustin's voice",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --message "Operator (CAKE): Stop. Run tests. See output."
  %(prog)s --file messages.txt
  %(prog)s --interactive

Voice Requirements:
  - Format: "Operator (CAKE): Stop. {action}. {reference}."
  - Approved verbs: Run, Check, Fix, Try, See
  - Max 3 sentences, 150 characters
  - Direct, imperative style (no explanations)
  - ≥90%% similarity score to pass
        """,
    )

    parser.add_argument("--message", "-m", help="Single message to validate")
    parser.add_argument("--file", "-f", type=Path, help="File containing messages (one per line)")
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Interactive mode - enter messages to check",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed analysis")

    return parser


def _process_single_message(
    validator: DustinVoiceValidator, message: str
) -> List[VoiceCheckResult]:
    """Process a single message and return results."""
    result = validator.check_message(message)
    return [result]


def _process_file(validator: DustinVoiceValidator, file_path: Path) -> List[VoiceCheckResult]:
    """Process messages from a file."""
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return []

    results = []
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                result = validator.check_message(line)
                results.append(result)

    return results


def _run_interactive_mode(validator: DustinVoiceValidator, verbose: bool) -> None:
    """Run interactive validation mode."""
    print("CAKE Voice Validator - Interactive Mode")
    print("Enter messages to check (Ctrl+C to exit)")
    print("-" * 40)

    try:
        while True:
            message = input("\nMessage: ").strip()
            if message:
                result = validator.check_message(message)
                _print_result(result, verbose=verbose)
    except KeyboardInterrupt:
        print("\n\nExiting...")


def _output_results(results: List[VoiceCheckResult], as_json: bool, verbose: bool) -> None:
    """Output results in the requested format."""
    if not results:
        return

    if as_json:
        output = []
        for result in results:
            output.append(
                {
                    "message": result.message,
                    "score": result.score,
                    "passed": result.passed,
                    "issues": result.issues,
                    "suggestions": result.suggestions,
                }
            )
        print(json.dumps(output, indent=2))
    else:
        for result in results:
            _print_result(result, verbose=verbose)


def main() -> int:
    """Main entry point."""
    parser = _create_parser()
    args = parser.parse_args()

    # Validate arguments
    if not any([args.message, args.file, args.interactive]):
        parser.print_help()
        return 1

    validator = DustinVoiceValidator()

    # Handle interactive mode separately (doesn't collect results)
    if args.interactive:
        _run_interactive_mode(validator, args.verbose)
        return 0

    # Process non-interactive modes
    results = []
    if args.message:
        results = _process_single_message(validator, args.message)
    elif args.file:
        results = _process_file(validator, args.file)

    # Output results
    _output_results(results, args.json, args.verbose)

    # Return appropriate exit code
    return 0 if results and all(r.passed for r in results) else 1


def _print_result(result: VoiceCheckResult, verbose: bool = False) -> None:
    """Print a single result."""
    # Color codes
    green = "\033[92m"
    red = "\033[91m"
    yellow = "\033[93m"
    blue = "\033[94m"
    reset = "\033[0m"

    # Status
    if result.passed:
        status = f"{green}PASSED{reset}"
    else:
        status = f"{red}FAILED{reset}"

    print(f"\n{status} - Score: {result.score:.1f}%")
    print(f"Message: {result.message}")

    if result.issues:
        print(f"\n{yellow}Issues:{reset}")
        for issue in result.issues:
            print(f"  - {issue}")

    if result.suggestions:
        print(f"\n{blue}Suggestions:{reset}")
        for suggestion in result.suggestions:
            print(f"  → {suggestion}")

    if verbose and result.passed:
        print(f"\n{green}✓ Voice similarity meets requirements{reset}")


if __name__ == "__main__":
    sys.exit(main())
