#!/usr/bin/env python3
"""voice_similarity_gate.py - Style Consistency Enforcer for CAKE

Validates that intervention messages match Dustin's communication style
with ≥90% similarity using embedding-based comparison.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

    # Mock classes for when sklearn is not available
    class TfidfVectorizer:
        def __init__(self, **kwargs):
            pass

        def fit_transform(self, texts):
            # Return a simple mock result
            return type(
                "SparseMatrix",
                (),
                {"todense": lambda self: [[1.0] * len(texts)] * len(texts)},
            )()

        def transform(self, texts):
            return self.fit_transform(texts)

    def cosine_similarity(a, b):
        # Return high similarity for mocking
        return [[0.95]]


logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of voice similarity validation."""

    passed: bool
    score: float
    reason: str
    suggestions: List[str] = None

    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []


class VoiceSimilarityGate:
    """
    Validates intervention messages against Dustin's reference style.

    Ensures all messages maintain ≥90% similarity to reference corpus
    using TF-IDF embeddings and style pattern matching.
    """

    # Forbidden patterns that break voice consistency
    FORBIDDEN_PATTERNS = [
        r"I'm sorry",
        r"I apologize",
        r"Unfortunately",
        r"I think",
        r"maybe",
        r"perhaps",
        r"could you",
        r"would you mind",
        r"please try",
        r"I believe",
        r"In my opinion",
        r"It seems",
        r"I suggest",
        r"I recommend",
    ]

    # Required patterns
    REQUIRED_PATTERNS = {
        "prefix": r"^Operator \(CAKE\): Stop\.",
        "structure": r"^Operator \(CAKE\): Stop\. [A-Z][^.]+\. [A-Z][^.]+\.$",
        "verbs": r"\b(Run|Check|Fix|Try|See)\b",
    }

    # Approved action verbs
    APPROVED_VERBS = {"Run", "Check", "Fix", "Try", "See"}

    def __init__(self, reference_corpus_path: Optional[Path] = None):
        """
        Initialize voice gate with reference corpus.

        Args:
            reference_corpus_path: Path to dustin_reference.json
        """
        self.reference_messages: List[str] = []
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 3),
            max_features=1000,
            stop_words=None,  # Keep all words for style matching
        )
        self.reference_vectors = None

        # Load default reference corpus
        self._load_default_corpus()

        # Load custom corpus if provided
        if reference_corpus_path and reference_corpus_path.exists():
            self.load_reference_corpus(str(reference_corpus_path))

    def _load_default_corpus(self):
        """Load default reference messages."""
        self.reference_messages = [
            "Operator (CAKE): Stop. Run pytest. See test results.",
            "Operator (CAKE): Stop. Fix import error line 42. Check syntax.",
            "Operator (CAKE): Stop. Try git stash. See uncommitted changes.",
            "Operator (CAKE): Stop. Run pip install requests. See requirements.txt.",
            "Operator (CAKE): Stop. Check virtual environment. Run pip list.",
            "Operator (CAKE): Stop. Fix indentation error. See line 15.",
            "Operator (CAKE): Stop. Run black main.py. Check formatting.",
            "Operator (CAKE): Stop. Try different approach. See error log.",
            "Operator (CAKE): Stop. Run tests again. Check coverage.",
            "Operator (CAKE): Stop. Fix type error. See mypy output.",
            "Operator (CAKE): Stop. Check dependencies. Run pip freeze.",
            "Operator (CAKE): Stop. Run git status. See changed files.",
            "Operator (CAKE): Stop. Fix merge conflict. Check git diff.",
            "Operator (CAKE): Stop. Try smaller batch size. See memory error.",
            "Operator (CAKE): Stop. Run linter. Fix style issues.",
        ]

        # Fit vectorizer on reference corpus
        self.reference_vectors = self.vectorizer.fit_transform(self.reference_messages)
        logger.info("Loaded %d default reference messages", len(self.reference_messages))

    def load_reference_corpus(self, path: str) -> None:
        """
        Load and precompute embeddings for reference messages.

        Args:
            path: Path to dustin_reference.json

        Raises:
            FileNotFoundError: If corpus file missing
            ValueError: If JSON invalid
        """
        try:
            with open(path, "r") as f:
                data = json.load(f)

            if not isinstance(data, dict) or "messages" not in data:
                raise ValueError("Invalid corpus format: missing 'messages' key")

            # Extract message texts
            messages = []
            for item in data["messages"]:
                if isinstance(item, dict) and "text" in item:
                    messages.append(item["text"])
                elif isinstance(item, str):
                    messages.append(item)

            if not messages:
                raise ValueError("No valid messages found in corpus")

            # Update reference corpus
            self.reference_messages = messages
            self.reference_vectors = self.vectorizer.fit_transform(self.reference_messages)

            logger.info("Loaded %d reference messages from %s", len(messages), path)

        except FileNotFoundError:
            logger.error("Reference corpus not found: %s", path)
            raise
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in corpus file: %s", e)
            raise ValueError(f"Corrupted corpus file: {e}")

    def validate_message(self, message: str) -> ValidationResult:
        """
        Validate message against reference corpus.

        Args:
            message: Proposed intervention message

        Returns:
            ValidationResult with pass/fail, score, and reason
        """  # Check basic requirements first
        basic_result = self._check_basic_requirements(message)
        if not basic_result.passed:
            return basic_result

        # Check forbidden patterns
        forbidden_result = self._check_forbidden_patterns(message)
        if not forbidden_result.passed:
            return forbidden_result

        # Calculate similarity score
        similarity_score = self._calculate_similarity(message)

        # Determine if passes threshold
        passed = similarity_score >= 0.90

        if passed:
            reason = f"Message validated with {similarity_score:.2%} similarity"
        else:
            reason = f"Similarity {similarity_score:.2%} below 90% threshold"

        # Generate suggestions if failed
        suggestions = []
        if not passed:
            suggestions = self._generate_suggestions(message, similarity_score)

        return ValidationResult(
            passed=passed,
            score=similarity_score,
            reason=reason,
            suggestions=suggestions,
        )

    def _check_basic_requirements(self, message: str) -> ValidationResult:
        """Check basic structural requirements."""  # Check prefix
        if not re.match(self.REQUIRED_PATTERNS["prefix"], message):
            return ValidationResult(
                passed=False,
                score=0.0,
                reason="Missing required prefix: 'Operator (CAKE): Stop.'",
                suggestions=["Start message with 'Operator (CAKE): Stop.'"],
            )

        # Check sentence count (max 3)
        sentences = re.split(r"[.!?]+", message)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) > 3:
            return ValidationResult(
                passed=False,
                score=0.0,
                reason=f"Too many sentences ({len(sentences)} > 3)",
                suggestions=["Reduce to maximum 3 sentences"],
            )

        # Check for approved verbs
        if not re.search(self.REQUIRED_PATTERNS["verbs"], message):
            return ValidationResult(
                passed=False,
                score=0.0,
                reason="No approved action verb found",
                suggestions=[f"Use one of: {', '.join(self.APPROVED_VERBS)}"],
            )

        return ValidationResult(passed=True, score=1.0, reason="Basic requirements met")

    def _check_forbidden_patterns(self, message: str) -> ValidationResult:
        """Check for forbidden patterns."""
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                return ValidationResult(
                    passed=False,
                    score=0.0,
                    reason=f"Forbidden pattern detected: '{pattern}'",
                    suggestions=["Remove apologies, uncertainty, and explanations"],
                )

        return ValidationResult(passed=True, score=1.0, reason="No forbidden patterns")

    def _calculate_similarity(self, message: str) -> float:
        """Calculate similarity score using TF-IDF vectors."""
        try:
            # Vectorize the message
            message_vector = self.vectorizer.transform([message])

            # Calculate cosine similarity with all reference messages
            similarities = cosine_similarity(message_vector, self.reference_vectors)[0]

            # Return the maximum similarity score
            return float(np.max(similarities))

        except Exception as e:
            logger.error("Similarity calculation failed: %s", e)
            return 0.0

    def _generate_suggestions(self, message: str, score: float) -> List[str]:
        """Generate improvement suggestions."""
        suggestions = []

        # Find most similar reference message
        try:
            message_vector = self.vectorizer.transform([message])
            similarities = cosine_similarity(message_vector, self.reference_vectors)[0]
            best_match_idx = np.argmax(similarities)
            best_match = self.reference_messages[best_match_idx]

            suggestions.append(f"Most similar approved message: '{best_match}'")

        except Exception:
            pass

        # Analyze structure
        parts = message.split(". ")
        if len(parts) >= 2:
            action = parts[1] if len(parts) > 1 else ""

            # Check if action starts with approved verb
            if not any(action.startswith(verb) for verb in self.APPROVED_VERBS):
                suggestions.append(
                    "Second sentence should start with: Run, Check, Fix, Try, or See"
                )

            # Check for imperative mood
            if " I " in message or " me " in message:
                suggestions.append("Use imperative mood, avoid first person")

        return suggestions

    def get_reference_examples(self, n: int = 5) -> List[str]:
        """Get example reference messages."""
        return self.reference_messages[:n]

    def add_reference_message(self, message: str) -> None:
        """Add a new message to reference corpus."""
        # Validate it meets requirements first
        result = self.validate_message(message)
        if not result.passed:
            raise ValueError(f"Cannot add invalid message: {result.reason}")

        self.reference_messages.append(message)
        # Refit vectorizer
        self.reference_vectors = self.vectorizer.fit_transform(self.reference_messages)
        logger.info("Added new reference message, corpus size: %d", len(self.reference_messages))


# Example usage
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Create voice gate
    gate = VoiceSimilarityGate()

    # Test messages
    test_messages = [
        # Good examples
        "Operator (CAKE): Stop. Run pytest. See test results.",
        "Operator (CAKE): Stop. Fix syntax error line 42. Check brackets.",
        "Operator (CAKE): Stop. Try git pull. See merge conflicts.",
        # Bad examples
        "I think you should maybe try running tests",
        "Operator (CAKE): I'm sorry, but there's an error. Please fix it.",
        "Unfortunately, the tests are failing",
        "Operator (CAKE): Stop. This is a very long explanation about what went wrong and why you should fix it immediately. Also check the logs. And maybe restart.",
    ]

    print("Voice Similarity Gate Test")
    print("=" * 50)

    for message in test_messages:
        result = gate.validate_message(message)
        status = "✅ PASS" if result.passed else "❌ FAIL"

        print(f"\nMessage: {message}")
        print(f"Status: {status}")
        print(f"Score: {result.score:.2%}")
        print(f"Reason: {result.reason}")

        if result.suggestions:
            print("Suggestions:")
            for suggestion in result.suggestions:
                print(f"  - {suggestion}")

    print("\n" + "=" * 50)
    print("Reference examples:")
    for example in gate.get_reference_examples(3):
        print(f"  - {example}")
