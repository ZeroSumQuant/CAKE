#!/usr/bin/env python3
"""escalation_decider.py - Intelligent Escalation Decision Engine for CAKE

Determines when and how to escalate issues based on failure patterns,
severity, and historical data.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class EscalationLevel(Enum):
    """Levels of escalation severity."""

    NONE = auto()  # No escalation needed
    LOW = auto()  # Minor issue, log only
    MEDIUM = auto()  # Needs attention soon
    HIGH = auto()  # Urgent intervention required
    CRITICAL = auto()  # Immediate human intervention


class InterventionType(Enum):
    """Types of interventions available."""

    AUTO_RETRY = auto()  # Automatic retry
    CONTEXT_ADJUSTMENT = auto()  # Adjust prompts/context
    RESOURCE_INCREASE = auto()  # Increase memory/time limits
    STRATEGY_CHANGE = auto()  # Change approach
    HUMAN_REVIEW = auto()  # Request human review
    EMERGENCY_STOP = auto()  # Stop all operations


@dataclass
class EscalationContext:
    """Context for escalation decision."""

    error_type: str
    error_message: str
    stage: str
    failure_count: int
    time_since_start: float
    previous_interventions: List[str] = field(default_factory=list)
    severity_indicators: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EscalationDecision:
    """Decision made by the escalation system."""

    level: EscalationLevel
    intervention: InterventionType
    reason: str
    confidence: float
    recommended_actions: List[str] = field(default_factory=list)
    cooldown_seconds: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class EscalationDecider:
    """
    Makes intelligent decisions about when and how to escalate issues.

    Uses configurable thresholds, pattern matching, and historical data
    to determine appropriate escalation responses.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize escalation decider.

        Args:
            config: Configuration dictionary
        """
        self.config = config or self._default_config()
        self.escalation_history: List[Tuple[datetime, EscalationDecision]] = []
        self.cooldowns: Dict[str, datetime] = {}

        logger.info("EscalationDecider initialized")

    def _default_config(self) -> Dict[str, Any]:
        """Default escalation configuration."""
        return {
            "max_retries": 3,
            "critical_errors": [
                "OutOfMemoryError",
                "SegmentationFault",
                "SystemExit",
                "KeyboardInterrupt",
            ],
            "high_priority_patterns": [
                "permission denied",
                "authentication failed",
                "rate limit exceeded",
                "quota exceeded",
            ],
            "escalation_thresholds": {
                "failure_count": {"low": 2, "medium": 3, "high": 5, "critical": 10},
                "time_elapsed": {
                    "medium": 300,  # 5 minutes
                    "high": 900,  # 15 minutes
                    "critical": 1800,  # 30 minutes
                },
            },
            "cooldown_periods": {
                "AUTO_RETRY": 5,
                "CONTEXT_ADJUSTMENT": 30,
                "RESOURCE_INCREASE": 60,
                "STRATEGY_CHANGE": 120,
                "HUMAN_REVIEW": 300,
            },
        }

    def decide_escalation(self, context: EscalationContext) -> EscalationDecision:
        """
        Make escalation decision based on context.

        Args:
            context: Current error/failure context

        Returns:
            EscalationDecision with recommended action
        """
        # Check for critical errors first
        if self._is_critical_error(context):
            return self._create_critical_decision(context)

        # Check cooldowns
        if self._in_cooldown(context):
            return self._create_cooldown_decision(context)

        # Determine escalation level
        level = self._determine_level(context)

        # Choose intervention type
        intervention = self._choose_intervention(level, context)

        # Build decision
        decision = EscalationDecision(
            level=level,
            intervention=intervention,
            reason=self._generate_reason(level, context),
            confidence=self._calculate_confidence(context),
            recommended_actions=self._get_recommended_actions(intervention, context),
            cooldown_seconds=self._get_cooldown_period(intervention),
        )

        # Record decision
        self._record_decision(decision, context)

        return decision

    def _is_critical_error(self, context: EscalationContext) -> bool:
        """Check if error is critical."""
        critical_errors = self.config["critical_errors"]
        return any(critical in context.error_type for critical in critical_errors)

    def _create_critical_decision(self, context: EscalationContext) -> EscalationDecision:
        """Create decision for critical errors."""
        return EscalationDecision(
            level=EscalationLevel.CRITICAL,
            intervention=InterventionType.EMERGENCY_STOP,
            reason=f"Critical error detected: {context.error_type}",
            confidence=1.0,
            recommended_actions=[
                "Stop all operations immediately",
                "Preserve current state",
                "Notify human operator",
                "Generate detailed error report",
            ],
            metadata={"critical_error": context.error_type},
        )

    def _in_cooldown(self, context: EscalationContext) -> bool:
        """Check if we're in cooldown period."""
        key = f"{context.stage}:{context.error_type}"
        if key in self.cooldowns:
            return datetime.now() < self.cooldowns[key]
        return False

    def _create_cooldown_decision(self, context: EscalationContext) -> EscalationDecision:
        """Create decision for cooldown period."""
        key = f"{context.stage}:{context.error_type}"
        remaining = (self.cooldowns[key] - datetime.now()).total_seconds()

        return EscalationDecision(
            level=EscalationLevel.NONE,
            intervention=InterventionType.AUTO_RETRY,
            reason=f"In cooldown period, {remaining:.0f}s remaining",
            confidence=0.9,
            cooldown_seconds=int(remaining),
        )

    def _determine_level(self, context: EscalationContext) -> EscalationLevel:
        """Determine escalation level from context."""
        thresholds = self.config["escalation_thresholds"]

        # Check failure count
        failure_thresholds = thresholds["failure_count"]
        if context.failure_count >= failure_thresholds["critical"]:
            return EscalationLevel.CRITICAL
        elif context.failure_count >= failure_thresholds["high"]:
            return EscalationLevel.HIGH
        elif context.failure_count >= failure_thresholds["medium"]:
            return EscalationLevel.MEDIUM
        elif context.failure_count >= failure_thresholds["low"]:
            return EscalationLevel.LOW

        # Check time elapsed
        time_thresholds = thresholds["time_elapsed"]
        if context.time_since_start >= time_thresholds["critical"]:
            return EscalationLevel.CRITICAL
        elif context.time_since_start >= time_thresholds["high"]:
            return EscalationLevel.HIGH
        elif context.time_since_start >= time_thresholds["medium"]:
            return EscalationLevel.MEDIUM

        # Check high priority patterns
        high_priority = self.config["high_priority_patterns"]
        if any(pattern in context.error_message.lower() for pattern in high_priority):
            return EscalationLevel.HIGH

        return EscalationLevel.LOW

    def _choose_intervention(
        self, level: EscalationLevel, context: EscalationContext
    ) -> InterventionType:
        """Choose appropriate intervention type."""
        if level == EscalationLevel.CRITICAL:
            return InterventionType.HUMAN_REVIEW
        elif level == EscalationLevel.HIGH:
            if context.failure_count > 5:
                return InterventionType.STRATEGY_CHANGE
            else:
                return InterventionType.RESOURCE_INCREASE
        elif level == EscalationLevel.MEDIUM:
            if "context" in context.previous_interventions:
                return InterventionType.STRATEGY_CHANGE
            else:
                return InterventionType.CONTEXT_ADJUSTMENT
        else:
            return InterventionType.AUTO_RETRY

    def _generate_reason(self, level: EscalationLevel, context: EscalationContext) -> str:
        """Generate human-readable reason."""
        if level == EscalationLevel.CRITICAL:
            return f"Critical failure after {context.failure_count} attempts"
        elif level == EscalationLevel.HIGH:
            return f"High priority issue: {context.error_type}"
        elif level == EscalationLevel.MEDIUM:
            return f"Repeated failures ({context.failure_count}) in {context.stage}"
        else:
            return f"Minor issue in {context.stage}, attempting recovery"

    def _calculate_confidence(self, context: EscalationContext) -> float:
        """Calculate confidence in the decision."""  # Higher confidence with more data points
        base_confidence = 0.7

        # Increase confidence based on failure count
        if context.failure_count > 5:
            base_confidence += 0.2
        elif context.failure_count > 2:
            base_confidence += 0.1

        # Adjust for previous interventions
        if len(context.previous_interventions) > 2:
            base_confidence += 0.1

        return min(base_confidence, 0.95)

    def _get_recommended_actions(
        self, intervention: InterventionType, context: EscalationContext
    ) -> List[str]:
        """Get recommended actions for intervention."""
        actions_map = {
            InterventionType.AUTO_RETRY: [
                "Wait for cooldown period",
                "Retry with same parameters",
                "Log attempt for pattern analysis",
            ],
            InterventionType.CONTEXT_ADJUSTMENT: [
                "Simplify prompt/context",
                "Add error-specific guidance",
                "Include examples of correct behavior",
            ],
            InterventionType.RESOURCE_INCREASE: [
                "Increase timeout limits",
                "Allocate more memory",
                "Use smaller batch sizes",
            ],
            InterventionType.STRATEGY_CHANGE: [
                "Try alternative approach",
                "Break down into smaller tasks",
                "Use different model/parameters",
            ],
            InterventionType.HUMAN_REVIEW: [
                "Generate detailed error report",
                "Preserve full context",
                "Await human guidance",
            ],
            InterventionType.EMERGENCY_STOP: [
                "Halt all operations",
                "Save current state",
                "Alert administrators",
            ],
        }

        return actions_map.get(intervention, ["No specific actions"])

    def _get_cooldown_period(self, intervention: InterventionType) -> int:
        """Get cooldown period for intervention type."""
        cooldowns = self.config["cooldown_periods"]
        return cooldowns.get(intervention.name, 30)

    def _record_decision(self, decision: EscalationDecision, context: EscalationContext) -> None:
        """Record decision for analysis."""
        self.escalation_history.append((datetime.now(), decision))

        # Set cooldown if needed
        if decision.cooldown_seconds > 0:
            key = f"{context.stage}:{context.error_type}"
            self.cooldowns[key] = datetime.now() + timedelta(seconds=decision.cooldown_seconds)

        logger.info(
            f"Escalation decision: {decision.level.name} - "
            f"{decision.intervention.name} for {context.error_type}"
        )

    def get_escalation_stats(self) -> Dict[str, Any]:
        """Get statistics about escalation decisions."""
        if not self.escalation_history:
            return {"total_escalations": 0}

        # Count by level
        level_counts = {}
        intervention_counts = {}

        for _, decision in self.escalation_history:
            level = decision.level.name
            intervention = decision.intervention.name

            level_counts[level] = level_counts.get(level, 0) + 1
            intervention_counts[intervention] = intervention_counts.get(intervention, 0) + 1

        return {
            "total_escalations": len(self.escalation_history),
            "by_level": level_counts,
            "by_intervention": intervention_counts,
            "recent_escalations": [
                {
                    "time": time.isoformat(),
                    "level": decision.level.name,
                    "intervention": decision.intervention.name,
                    "reason": decision.reason,
                }
                for time, decision in self.escalation_history[-5:]
            ],
        }


# Example usage
if __name__ == "__main__":
    # Create decider
    decider = EscalationDecider()

    # Test scenarios
    test_contexts = [
        EscalationContext(
            error_type="ImportError",
            error_message="No module named 'requests'",
            stage="execute",
            failure_count=1,
            time_since_start=30.0,
        ),
        EscalationContext(
            error_type="PermissionError",
            error_message="Permission denied: /etc/passwd",
            stage="execute",
            failure_count=3,
            time_since_start=120.0,
        ),
        EscalationContext(
            error_type="OutOfMemoryError",
            error_message="Cannot allocate memory",
            stage="validate",
            failure_count=5,
            time_since_start=600.0,
        ),
    ]

    for context in test_contexts:
        decision = decider.decide_escalation(context)
        print(f"\nError: {context.error_type}")
        print(f"Level: {decision.level.name}")
        print(f"Intervention: {decision.intervention.name}")
        print(f"Reason: {decision.reason}")
        print(f"Actions: {decision.recommended_actions}")
