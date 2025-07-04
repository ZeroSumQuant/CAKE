#!/usr/bin/env python3
"""adaptive_confidence_system.py - Self-Learning Confidence Engine for CAKE

Tracks decision outcomes and dynamically adjusts confidence scores based on
historical success rates. Implements Bayesian learning for decision patterns,
contextual confidence adjustment, and performance-based strategy optimization.

Author: CAKE Team
License: MIT
Python: 3.11+
"""

import hashlib
import json
import logging
import pickle
import sqlite3
import statistics
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

# Configure module logger
logger = logging.getLogger(__name__)


class OutcomeType(Enum):
    """Types of decision outcomes."""

    SUCCESS = auto()  # Decision led to success
    FAILURE = auto()  # Decision led to failure
    PARTIAL_SUCCESS = auto()  # Mixed results
    TIMEOUT = auto()  # Decision timed out
    ESCALATED = auto()  # Required human intervention
    ABORTED = auto()  # Had to abort due to decision


@dataclass
class DecisionOutcome:
    """
    Records the outcome of a strategic decision.

    Attributes:
        decision_id: Unique identifier for the original decision
        outcome_type: Type of outcome
        success_metrics: Quantified success measurements
        time_to_resolution: How long it took to resolve
        cost_impact: Cost incurred as result of decision
        confidence_accuracy: How accurate the original confidence was
        context_hash: Hash of decision context for pattern matching
        lessons_learned: Structured lessons from this outcome
    """

    decision_id: str
    outcome_type: OutcomeType
    success_metrics: Dict[str, float]
    time_to_resolution: float  # seconds
    cost_impact: float
    confidence_accuracy: float  # |predicted_confidence - actual_success|
    context_hash: str
    lessons_learned: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfidencePattern:
    """
    A learned pattern for confidence adjustment.

    Attributes:
        pattern_id: Unique pattern identifier
        context_features: Features that define this pattern
        base_confidence: Base confidence for this pattern
        adjustment_factor: Learned adjustment (+/- multiplier)
        sample_count: Number of samples this pattern is based on
        success_rate: Historical success rate for this pattern
        variance: Confidence variance for this pattern
        last_updated: When pattern was last updated
    """

    pattern_id: str
    context_features: Dict[str, Any]
    base_confidence: float
    adjustment_factor: float
    sample_count: int
    success_rate: float
    variance: float
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["last_updated"] = self.last_updated.isoformat()
        return data


class ContextFeatureExtractor:
    """
    Extracts relevant features from decision context for pattern matching.
    """

    # Feature extraction patterns
    FEATURE_EXTRACTORS = {
        "stage": lambda ctx: ctx.get("stage", "unknown"),
        "error_type": lambda ctx: extract_error_type(ctx.get("error", "")),
        "failure_count": lambda ctx: min(ctx.get("failure_count", 0), 10),  # Cap at 10
        "cost_ratio": lambda ctx: min(
            ctx.get("cost", 0) / max(ctx.get("budget", 1), 1), 2.0
        ),
        "domain": lambda ctx: ctx.get("domain", "general"),
        "task_complexity": lambda ctx: estimate_task_complexity(ctx),
        "time_of_day": lambda ctx: datetime.now().hour // 6,  # 0-3 (6hr buckets)
        "recent_success_rate": lambda ctx: ctx.get("recent_success_rate", 0.5),
        "oscillation_detected": lambda ctx: ctx.get("oscillation_count", 0) > 0,
        "resource_pressure": lambda ctx: calculate_resource_pressure(ctx),
    }

    def extract_features(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract standardized features from decision context.

        Args:
            context: Raw decision context

        Returns:
            Standardized feature dictionary
        """
        features = {}

        for feature_name, extractor in self.FEATURE_EXTRACTORS.items():
            try:
                features[feature_name] = extractor(context)
            except Exception as e:
                logger.warning(f"Feature extraction failed for {feature_name}: {e}")
                features[feature_name] = None

        # Add derived features
        features["is_critical_stage"] = features["stage"] in ["execute", "validate"]
        features["is_high_failure"] = features["failure_count"] > 2
        features["is_over_budget"] = features["cost_ratio"] > 0.8
        features["is_complex_task"] = features["task_complexity"] > 0.7

        return features

    def generate_pattern_signature(self, features: Dict[str, Any]) -> str:
        """Generate unique signature for feature pattern."""  # Select key features for pattern matching
        key_features = {
            "stage": features.get("stage"),
            "error_type": features.get("error_type"),
            "failure_bucket": self._bucket_value(
                features.get("failure_count", 0), [0, 1, 3, 5]
            ),
            "cost_bucket": self._bucket_value(
                features.get("cost_ratio", 0), [0, 0.3, 0.7, 1.0]
            ),
            "complexity_bucket": self._bucket_value(
                features.get("task_complexity", 0), [0, 0.3, 0.7, 1.0]
            ),
        }

        # Create deterministic hash
        signature_str = json.dumps(key_features, sort_keys=True)
        return hashlib.md5(signature_str.encode(), usedforsecurity=False).hexdigest()[
            :12
        ]

    def _bucket_value(self, value: float, buckets: List[float]) -> str:
        """Bucket continuous values for pattern matching."""
        if value is None:
            return "unknown"

        for i, threshold in enumerate(buckets[1:], 1):
            if value <= threshold:
                return f"bucket_{i-1}"

        return f"bucket_{len(buckets)-1}"


class BayesianConfidenceUpdater:
    """
    Updates confidence using Bayesian learning from historical outcomes.
    """

    def __init__(self, prior_alpha: float = 2.0, prior_beta: float = 2.0):
        """
        Initialize with Beta distribution priors.

        Args:
            prior_alpha: Prior successes (higher = more optimistic)
            prior_beta: Prior failures (higher = more pessimistic)
        """
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta

    def update_confidence(
        self,
        base_confidence: float,
        outcomes: List[DecisionOutcome],
        context_similarity: float = 1.0,
    ) -> Tuple[float, float]:
        """
        Update confidence based on historical outcomes using Bayesian learning.

        Args:
            base_confidence: Original confidence score
            outcomes: Historical outcomes for similar contexts
            context_similarity: How similar current context is to historical ones

        Returns:
            Tuple of (updated_confidence, confidence_variance)
        """
        if not outcomes:
            return base_confidence, 0.1  # Default variance

        # Count successes and failures, weighted by context similarity
        weighted_successes = 0.0
        weighted_failures = 0.0

        for outcome in outcomes:
            weight = context_similarity * self._outcome_weight(outcome)

            if outcome.outcome_type == OutcomeType.SUCCESS:
                weighted_successes += weight
            elif outcome.outcome_type in [OutcomeType.FAILURE, OutcomeType.ABORTED]:
                weighted_failures += weight
            elif outcome.outcome_type == OutcomeType.PARTIAL_SUCCESS:
                weighted_successes += weight * 0.5
                weighted_failures += weight * 0.5
            elif outcome.outcome_type == OutcomeType.ESCALATED:
                weighted_failures += weight * 0.3  # Escalation is partial failure

        # Update Beta distribution parameters
        alpha = self.prior_alpha + weighted_successes
        beta = self.prior_beta + weighted_failures

        # Calculate posterior mean (updated confidence)
        posterior_mean = alpha / (alpha + beta)

        # Calculate confidence interval (variance measure)
        variance = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))

        # Blend with base confidence (reduces extreme adjustments)
        blend_factor = min(len(outcomes) / 10.0, 0.8)  # Max 80% historical influence
        updated_confidence = (
            1 - blend_factor
        ) * base_confidence + blend_factor * posterior_mean

        return max(0.01, min(0.99, updated_confidence)), variance

    def _outcome_weight(self, outcome: DecisionOutcome) -> float:
        """Calculate weight for an outcome based on recency and reliability."""  # Recency weight (exponential decay)
        days_old = (datetime.now() - outcome.timestamp).days
        recency_weight = np.exp(-days_old / 30.0)  # Half-life of 30 days

        # Reliability weight (based on confidence accuracy)
        reliability_weight = 1.0 - min(outcome.confidence_accuracy, 0.5)

        return recency_weight * reliability_weight


class PerformanceTracker:
    """
    Tracks performance of different decision strategies.
    """

    def __init__(self):
        """Initialize performance tracking."""
        self.strategy_performance = defaultdict(
            lambda: {
                "total_decisions": 0,
                "successful_decisions": 0,
                "average_time": 0.0,
                "average_cost": 0.0,
                "confidence_accuracy": deque(maxlen=100),
                "recent_outcomes": deque(maxlen=50),
            }
        )

        self.global_metrics = {
            "total_decisions": 0,
            "baseline_success_rate": 0.7,  # Expected success rate
            "adaptation_rate": 0.1,  # How fast to adapt
            "confidence_calibration": 1.0,  # Global confidence calibration
        }

    def record_outcome(self, strategy: str, outcome: DecisionOutcome):
        """Record an outcome for a specific strategy."""
        stats = self.strategy_performance[strategy]

        # Update counts
        stats["total_decisions"] += 1
        if outcome.outcome_type == OutcomeType.SUCCESS:
            stats["successful_decisions"] += 1
        elif outcome.outcome_type == OutcomeType.PARTIAL_SUCCESS:
            stats["successful_decisions"] += 0.5

        # Update averages
        stats["average_time"] = self._update_average(
            stats["average_time"], outcome.time_to_resolution, stats["total_decisions"]
        )
        stats["average_cost"] = self._update_average(
            stats["average_cost"], outcome.cost_impact, stats["total_decisions"]
        )

        # Track confidence accuracy
        stats["confidence_accuracy"].append(outcome.confidence_accuracy)
        stats["recent_outcomes"].append(outcome.outcome_type)

        # Update global metrics
        self.global_metrics["total_decisions"] += 1
        self._update_global_calibration()

    def get_strategy_performance(self, strategy: str) -> Dict[str, Any]:
        """Get performance metrics for a strategy."""
        stats = self.strategy_performance[strategy]

        if stats["total_decisions"] == 0:
            return {"success_rate": 0.5, "confidence": 0.5, "sample_size": 0}

        success_rate = stats["successful_decisions"] / stats["total_decisions"]
        avg_confidence_accuracy = (
            statistics.mean(stats["confidence_accuracy"])
            if stats["confidence_accuracy"]
            else 0.5
        )

        # Recent trend (last 10 decisions)
        recent_outcomes = list(stats["recent_outcomes"])[-10:]
        recent_success_rate = (
            sum(1 for o in recent_outcomes if o == OutcomeType.SUCCESS)
            / len(recent_outcomes)
            if recent_outcomes
            else 0.5
        )

        return {
            "success_rate": success_rate,
            "recent_success_rate": recent_success_rate,
            "confidence_accuracy": avg_confidence_accuracy,
            "average_time": stats["average_time"],
            "average_cost": stats["average_cost"],
            "sample_size": stats["total_decisions"],
            "trend": "improving" if recent_success_rate > success_rate else "declining",
        }

    def _update_average(
        self, current_avg: float, new_value: float, count: int
    ) -> float:
        """Update running average."""
        return ((current_avg * (count - 1)) + new_value) / count

    def _update_global_calibration(self):
        """Update global confidence calibration factor."""
        if (
            self.global_metrics["total_decisions"] % 10 == 0
        ):  # Update every 10 decisions
            # Calculate overall confidence accuracy
            all_accuracies = []
            for stats in self.strategy_performance.values():
                all_accuracies.extend(stats["confidence_accuracy"])

            if all_accuracies:
                avg_accuracy = statistics.mean(all_accuracies)
                # Adjust calibration (lower accuracy = need to be more conservative)
                self.global_metrics["confidence_calibration"] = 0.5 + (
                    avg_accuracy * 0.5
                )


class AdaptiveConfidenceEngine:
    """
    Main engine that orchestrates adaptive confidence scoring.
    """

    def __init__(self, persistence_path: Path):
        """
        Initialize adaptive confidence engine.

        Args:
            persistence_path: Path for storing learned patterns and outcomes
        """
        self.persistence_path = persistence_path
        self.persistence_path.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.feature_extractor = ContextFeatureExtractor()
        self.bayesian_updater = BayesianConfidenceUpdater()
        self.performance_tracker = PerformanceTracker()

        # Pattern storage
        self.confidence_patterns: Dict[str, ConfidencePattern] = {}
        self.outcome_database = self._init_database()

        # Load existing patterns
        self._load_patterns()

        logger.info(
            f"AdaptiveConfidenceEngine initialized with {len(self.confidence_patterns)} patterns"
        )

    def _init_database(self) -> sqlite3.Connection:
        """Initialize SQLite database for outcome storage."""
        db_path = self.persistence_path / "outcomes.db"
        conn = sqlite3.connect(str(db_path), check_same_thread=False)

        # Create tables
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id TEXT NOT NULL,
                outcome_type TEXT NOT NULL,
                success_metrics TEXT,
                time_to_resolution REAL,
                cost_impact REAL,
                confidence_accuracy REAL,
                context_hash TEXT,
                lessons_learned TEXT,
                timestamp TEXT,
                metadata TEXT
            )
        """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_context_hash ON decision_outcomes(context_hash)
        """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_timestamp ON decision_outcomes(timestamp)
        """
        )

        conn.commit()
        return conn

    def adapt_confidence(
        self, decision_action: str, base_confidence: float, context: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Adapt confidence score based on historical learning.

        Args:
            decision_action: The action being taken (PROCEED, RETRY, etc.)
            base_confidence: Original confidence from strategist
            context: Current decision context

        Returns:
            Tuple of (adapted_confidence, adaptation_metadata)
        """  # Extract features from context
        features = self.feature_extractor.extract_features(context)
        pattern_signature = self.feature_extractor.generate_pattern_signature(features)

        # Get similar historical outcomes
        similar_outcomes = self._get_similar_outcomes(
            pattern_signature, decision_action
        )

        # Calculate context similarity and update confidence
        if similar_outcomes:
            context_similarity = self._calculate_context_similarity(
                features, similar_outcomes
            )
            adapted_confidence, variance = self.bayesian_updater.update_confidence(
                base_confidence, similar_outcomes, context_similarity
            )
        else:
            adapted_confidence = base_confidence
            variance = 0.1

        # Apply global calibration
        calibration = self.performance_tracker.global_metrics["confidence_calibration"]
        adapted_confidence *= calibration

        # Apply strategy-specific adjustments
        strategy_performance = self.performance_tracker.get_strategy_performance(
            decision_action
        )
        strategy_adjustment = self._calculate_strategy_adjustment(strategy_performance)
        adapted_confidence *= strategy_adjustment

        # Ensure confidence stays in valid range
        adapted_confidence = max(0.01, min(0.99, adapted_confidence))

        # Update or create pattern
        self._update_pattern(
            pattern_signature, features, adapted_confidence, similar_outcomes
        )

        # Generate adaptation metadata
        adaptation_metadata = {
            "original_confidence": base_confidence,
            "adapted_confidence": adapted_confidence,
            "adjustment_factor": (
                adapted_confidence / base_confidence if base_confidence > 0 else 1.0
            ),
            "pattern_signature": pattern_signature,
            "similar_outcomes_count": len(similar_outcomes),
            "variance": variance,
            "strategy_performance": strategy_performance,
            "global_calibration": calibration,
            "adaptation_reasoning": self._generate_adaptation_reasoning(
                base_confidence,
                adapted_confidence,
                similar_outcomes,
                strategy_performance,
            ),
        }

        logger.info(
            f"Adapted confidence: {base_confidence:.3f} → {adapted_confidence:.3f} "
            f"(pattern: {pattern_signature[:8]}, samples: {len(similar_outcomes)})"
        )

        return adapted_confidence, adaptation_metadata

    def record_decision_outcome(
        self,
        decision_id: str,
        decision_action: str,
        original_confidence: float,
        adapted_confidence: float,
        context: Dict[str, Any],
        outcome_type: OutcomeType,
        success_metrics: Dict[str, float],
        time_to_resolution: float,
        cost_impact: float,
    ):
        """
        Record the outcome of a decision for future learning.

        Args:
            decision_id: Unique identifier for the decision
            decision_action: Action that was taken
            original_confidence: Original confidence score
            adapted_confidence: Confidence after adaptation
            context: Decision context
            outcome_type: Type of outcome that occurred
            success_metrics: Quantified success measurements
            time_to_resolution: Time taken to resolve
            cost_impact: Cost incurred
        """  # Calculate confidence accuracy
        actual_success = self._outcome_to_success_score(outcome_type, success_metrics)
        confidence_accuracy = abs(adapted_confidence - actual_success)

        # Extract features and generate context hash
        features = self.feature_extractor.extract_features(context)
        context_hash = self.feature_extractor.generate_pattern_signature(features)

        # Create outcome record
        outcome = DecisionOutcome(
            decision_id=decision_id,
            outcome_type=outcome_type,
            success_metrics=success_metrics,
            time_to_resolution=time_to_resolution,
            cost_impact=cost_impact,
            confidence_accuracy=confidence_accuracy,
            context_hash=context_hash,
            lessons_learned=self._extract_lessons(
                outcome_type, context, success_metrics
            ),
            metadata={
                "decision_action": decision_action,
                "original_confidence": original_confidence,
                "adapted_confidence": adapted_confidence,
                "features": features,
            },
        )

        # Store in database
        self._store_outcome(outcome)

        # Update performance tracking
        self.performance_tracker.record_outcome(decision_action, outcome)

        # Update patterns with new learning
        self._update_pattern_with_outcome(context_hash, outcome)

        logger.info(
            f"Recorded outcome for {decision_id}: {outcome_type.name} "
            f"(accuracy: {confidence_accuracy:.3f})"
        )

    def _get_similar_outcomes(
        self, pattern_signature: str, decision_action: str
    ) -> List[DecisionOutcome]:
        """Get outcomes from similar contexts."""  # Query database for similar patterns
        cursor = self.outcome_database.execute(
            """
            SELECT * FROM decision_outcomes 
            WHERE context_hash = ? AND json_extract(metadata, '$.decision_action') = ?
            ORDER BY timestamp DESC
            LIMIT 50
        """,
            (pattern_signature, decision_action),
        )

        outcomes = []
        for row in cursor.fetchall():
            outcome = DecisionOutcome(
                decision_id=row[1],
                outcome_type=OutcomeType[row[2]],
                success_metrics=json.loads(row[3]) if row[3] else {},
                time_to_resolution=row[4],
                cost_impact=row[5],
                confidence_accuracy=row[6],
                context_hash=row[7],
                lessons_learned=json.loads(row[8]) if row[8] else {},
                timestamp=datetime.fromisoformat(row[9]),
                metadata=json.loads(row[10]) if row[10] else {},
            )
            outcomes.append(outcome)

        return outcomes

    def _calculate_context_similarity(
        self, current_features: Dict[str, Any], outcomes: List[DecisionOutcome]
    ) -> float:
        """Calculate how similar current context is to historical outcomes."""
        if not outcomes:
            return 0.0

        similarities = []
        for outcome in outcomes:
            historical_features = outcome.metadata.get("features", {})
            similarity = self._feature_similarity(current_features, historical_features)
            similarities.append(similarity)

        return statistics.mean(similarities)

    def _feature_similarity(
        self, features1: Dict[str, Any], features2: Dict[str, Any]
    ) -> float:
        """Calculate similarity between two feature sets."""
        if not features1 or not features2:
            return 0.0

        # Key features for similarity calculation
        key_features = ["stage", "error_type", "failure_count", "domain"]

        matches = 0
        total = 0

        for feature in key_features:
            if feature in features1 and feature in features2:
                total += 1
                if features1[feature] == features2[feature]:
                    matches += 1

        return matches / total if total > 0 else 0.0

    def _calculate_strategy_adjustment(self, performance: Dict[str, Any]) -> float:
        """Calculate adjustment factor based on strategy performance."""
        success_rate = performance["success_rate"]
        sample_size = performance["sample_size"]

        # No adjustment if insufficient data
        if sample_size < 5:
            return 1.0

        # Calculate adjustment based on success rate vs baseline
        baseline = self.performance_tracker.global_metrics["baseline_success_rate"]
        performance_ratio = success_rate / baseline

        # Conservative adjustment (max 20% change)
        adjustment = 0.8 + (performance_ratio * 0.4)
        return max(0.8, min(1.2, adjustment))

    def _outcome_to_success_score(
        self, outcome_type: OutcomeType, metrics: Dict[str, float]
    ) -> float:
        """Convert outcome to 0-1 success score."""
        base_scores = {
            OutcomeType.SUCCESS: 1.0,
            OutcomeType.PARTIAL_SUCCESS: 0.6,
            OutcomeType.FAILURE: 0.0,
            OutcomeType.TIMEOUT: 0.2,
            OutcomeType.ESCALATED: 0.3,
            OutcomeType.ABORTED: 0.0,
        }

        base_score = base_scores.get(outcome_type, 0.5)

        # Adjust based on metrics if available
        if metrics:
            # Use convergence confidence if available
            convergence_confidence = metrics.get("convergence_confidence", base_score)
            return (base_score + convergence_confidence) / 2

        return base_score

    def _extract_lessons(
        self,
        outcome_type: OutcomeType,
        context: Dict[str, Any],
        metrics: Dict[str, float],
    ) -> Dict[str, Any]:
        """Extract structured lessons from an outcome."""
        lessons = {
            "outcome_type": outcome_type.name,
            "context_stage": context.get("stage"),
            "context_error_type": context.get("error", "")[:100],
        }

        # Specific lessons based on outcome
        if outcome_type == OutcomeType.FAILURE:
            lessons["failure_lesson"] = "Strategy failed in this context"
            if context.get("failure_count", 0) > 3:
                lessons["escalation_lesson"] = (
                    "Should escalate sooner with high failure count"
                )

        elif outcome_type == OutcomeType.SUCCESS:
            lessons["success_lesson"] = "Strategy worked well in this context"
            if metrics.get("time_to_resolution", 0) < 60:
                lessons["efficiency_lesson"] = "Strategy was particularly efficient"

        return lessons

    def _update_pattern(
        self,
        pattern_signature: str,
        features: Dict[str, Any],
        confidence: float,
        outcomes: List[DecisionOutcome],
    ):
        """Update or create confidence pattern."""
        if pattern_signature in self.confidence_patterns:
            pattern = self.confidence_patterns[pattern_signature]
            pattern.sample_count += 1

            # Update with exponential moving average
            alpha = 0.1  # Learning rate
            pattern.base_confidence = (
                1 - alpha
            ) * pattern.base_confidence + alpha * confidence

            if outcomes:
                success_rate = sum(
                    1 for o in outcomes if o.outcome_type == OutcomeType.SUCCESS
                ) / len(outcomes)
                pattern.success_rate = (
                    1 - alpha
                ) * pattern.success_rate + alpha * success_rate

            pattern.last_updated = datetime.now()
        else:
            # Create new pattern
            pattern = ConfidencePattern(
                pattern_id=pattern_signature,
                context_features=features.copy(),
                base_confidence=confidence,
                adjustment_factor=1.0,
                sample_count=1,
                success_rate=0.7,  # Default
                variance=0.1,
            )
            self.confidence_patterns[pattern_signature] = pattern

        # Periodically save patterns
        if len(self.confidence_patterns) % 10 == 0:
            self._save_patterns()

    def _update_pattern_with_outcome(self, context_hash: str, outcome: DecisionOutcome):
        """Update pattern confidence based on actual outcome."""
        if context_hash in self.confidence_patterns:
            pattern = self.confidence_patterns[context_hash]

            # Update success rate
            alpha = 1.0 / pattern.sample_count  # Decreasing learning rate
            actual_success = self._outcome_to_success_score(
                outcome.outcome_type, outcome.success_metrics
            )
            pattern.success_rate = (
                1 - alpha
            ) * pattern.success_rate + alpha * actual_success

            # Update variance
            error = abs(pattern.base_confidence - actual_success)
            pattern.variance = (1 - alpha) * pattern.variance + alpha * (error**2)

    def _store_outcome(self, outcome: DecisionOutcome):
        """Store outcome in database."""
        self.outcome_database.execute(
            """
            INSERT INTO decision_outcomes 
            (decision_id, outcome_type, success_metrics, time_to_resolution, 
             cost_impact, confidence_accuracy, context_hash, lessons_learned, 
             timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                outcome.decision_id,
                outcome.outcome_type.name,
                json.dumps(outcome.success_metrics),
                outcome.time_to_resolution,
                outcome.cost_impact,
                outcome.confidence_accuracy,
                outcome.context_hash,
                json.dumps(outcome.lessons_learned),
                outcome.timestamp.isoformat(),
                json.dumps(outcome.metadata),
            ),
        )
        self.outcome_database.commit()

    def _generate_adaptation_reasoning(
        self,
        original: float,
        adapted: float,
        outcomes: List[DecisionOutcome],
        performance: Dict[str, Any],
    ) -> str:
        """Generate human-readable reasoning for confidence adaptation."""
        if abs(adapted - original) < 0.05:
            return "Minimal adjustment - confidence well-calibrated"

        reasoning_parts = []

        if adapted > original:
            reasoning_parts.append("Increased confidence")
            if outcomes:
                success_rate = sum(
                    1 for o in outcomes if o.outcome_type == OutcomeType.SUCCESS
                ) / len(outcomes)
                if success_rate > 0.8:
                    reasoning_parts.append(
                        f"due to {success_rate:.0%} historical success rate"
                    )
        else:
            reasoning_parts.append("Decreased confidence")
            if outcomes:
                failure_rate = sum(
                    1
                    for o in outcomes
                    if o.outcome_type in [OutcomeType.FAILURE, OutcomeType.ABORTED]
                ) / len(outcomes)
                if failure_rate > 0.3:
                    reasoning_parts.append(
                        f"due to {failure_rate:.0%} historical failure rate"
                    )

        if performance["sample_size"] < 5:
            reasoning_parts.append("(limited historical data)")

        return " ".join(reasoning_parts)

    def _save_patterns(self):
        """Save patterns to disk."""
        patterns_file = self.persistence_path / "confidence_patterns.pkl"
        with open(patterns_file, "wb") as f:
            pickle.dump(self.confidence_patterns, f)

    def _load_patterns(self):
        """Load patterns from disk."""
        patterns_file = self.persistence_path / "confidence_patterns.pkl"
        if patterns_file.exists():
            try:
                with open(patterns_file, "rb") as f:
                    self.confidence_patterns = pickle.load(f)
                logger.info(
                    f"Loaded {len(self.confidence_patterns)} confidence patterns"
                )
            except Exception as e:
                logger.warning(f"Failed to load patterns: {e}")

    def get_adaptation_statistics(self) -> Dict[str, Any]:
        """Get statistics about confidence adaptation."""
        total_patterns = len(self.confidence_patterns)

        if total_patterns == 0:
            return {"total_patterns": 0, "average_samples": 0}

        sample_counts = [p.sample_count for p in self.confidence_patterns.values()]
        success_rates = [p.success_rate for p in self.confidence_patterns.values()]

        return {
            "total_patterns": total_patterns,
            "average_samples_per_pattern": statistics.mean(sample_counts),
            "median_samples_per_pattern": statistics.median(sample_counts),
            "average_success_rate": statistics.mean(success_rates),
            "pattern_variance": (
                statistics.variance(success_rates) if len(success_rates) > 1 else 0
            ),
            "well_established_patterns": sum(
                1 for count in sample_counts if count >= 10
            ),
            "global_calibration": self.performance_tracker.global_metrics[
                "confidence_calibration"
            ],
        }

    def cleanup_old_data(self, days_to_keep: int = 90):
        """Clean up old outcome data."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        cursor = self.outcome_database.execute(
            "DELETE FROM decision_outcomes WHERE timestamp < ?",
            (cutoff_date.isoformat(),),
        )
        deleted_count = cursor.rowcount
        self.outcome_database.commit()

        logger.info(f"Cleaned up {deleted_count} old outcome records")
        return deleted_count


# Helper functions for feature extraction
def extract_error_type(error_text: str) -> str:
    """Extract error type from error message."""
    error_lower = error_text.lower()

    error_types = {
        "module": ["modulenotfounderror", "import"],
        "permission": ["permission denied", "access denied"],
        "syntax": ["syntaxerror", "syntax error"],
        "type": ["typeerror", "type error"],
        "value": ["valueerror", "value error"],
        "connection": ["connection", "timeout", "network"],
        "validation": ["assertion", "validation", "test failed"],
        "resource": ["memory", "disk space", "resource"],
    }

    for error_type, keywords in error_types.items():
        if any(keyword in error_lower for keyword in keywords):
            return error_type

    return "unknown"


def estimate_task_complexity(context: Dict[str, Any]) -> float:
    """Estimate task complexity from context."""
    task = context.get("task", "").lower()

    complexity_indicators = {
        "simple": ["fix typo", "update readme", "add comment"],
        "medium": ["add feature", "refactor", "optimize"],
        "complex": ["implement", "create", "build", "design"],
        "very_complex": ["architecture", "system", "integration", "migration"],
    }

    for level, indicators in complexity_indicators.items():
        if any(indicator in task for indicator in indicators):
            return {"simple": 0.2, "medium": 0.5, "complex": 0.8, "very_complex": 1.0}[
                level
            ]

    return 0.5  # Default medium complexity


def calculate_resource_pressure(context: Dict[str, Any]) -> float:
    """Calculate resource pressure from cost and token usage."""
    cost_ratio = context.get("cost", 0) / max(context.get("budget", 1), 1)
    token_ratio = context.get("tokens", 0) / max(
        context.get("token_limit", 10000), 10000
    )

    return min((cost_ratio + token_ratio) / 2, 1.0)


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    import tempfile

    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        engine = AdaptiveConfidenceEngine(Path(temp_dir))

        # Simulate several decision cycles
        contexts = [
            {
                "stage": "execute",
                "error": "ModuleNotFoundError: requests",
                "failure_count": 1,
                "cost": 0.5,
                "budget": 5.0,
                "task": "implement REST API",
                "domain": "software_development",
            },
            {
                "stage": "execute",
                "error": "ModuleNotFoundError: pandas",
                "failure_count": 2,
                "cost": 1.2,
                "budget": 5.0,
                "task": "data analysis script",
                "domain": "data_science",
            },
            {
                "stage": "validate",
                "error": "AssertionError: test failed",
                "failure_count": 1,
                "cost": 2.0,
                "budget": 5.0,
                "task": "fix unit tests",
                "domain": "software_development",
            },
        ]

        decision_actions = ["RETRY", "FETCH_INFO", "REROUTE"]

        print("=== ADAPTIVE CONFIDENCE TESTING ===\n")

        # Test confidence adaptation
        for i, (context, action) in enumerate(zip(contexts, decision_actions)):
            print(f"Decision {i+1}: {action} in {context['stage']}")

            # Get adapted confidence
            base_confidence = 0.8
            adapted_confidence, metadata = engine.adapt_confidence(
                action, base_confidence, context
            )

            print(f"  Base confidence: {base_confidence:.3f}")
            print(f"  Adapted confidence: {adapted_confidence:.3f}")
            print(f"  Adjustment factor: {metadata['adjustment_factor']:.3f}")
            print(f"  Reasoning: {metadata['adaptation_reasoning']}")

            # Simulate outcome
            outcome_type = (
                OutcomeType.SUCCESS if i % 2 == 0 else OutcomeType.PARTIAL_SUCCESS
            )

            engine.record_decision_outcome(
                decision_id=f"decision_{i+1}",
                decision_action=action,
                original_confidence=base_confidence,
                adapted_confidence=adapted_confidence,
                context=context,
                outcome_type=outcome_type,
                success_metrics={
                    "convergence_confidence": (
                        0.8 if outcome_type == OutcomeType.SUCCESS else 0.6
                    )
                },
                time_to_resolution=30.0 + i * 10,
                cost_impact=0.1 + i * 0.05,
            )

            print(f"  Recorded outcome: {outcome_type.name}\n")

        # Show adaptation statistics
        print("=== ADAPTATION STATISTICS ===")
        stats = engine.get_adaptation_statistics()
        for key, value in stats.items():
            print(f"{key}: {value}")

        print(f"\nPattern signatures: {list(engine.confidence_patterns.keys())}")
