#!/usr/bin/env python3
"""strategist.py - Deterministic Decision Engine for CAKE

This module provides the strategic brain for CAKE, making deterministic decisions
about workflow control, escalation, and resource management.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, Optional

# Configure module logger
logger = logging.getLogger(__name__)


class Decision(Enum):
    """Possible strategic decisions the system can make."""

    PROCEED = auto()  # Continue to next stage
    RETRY = auto()  # Retry current stage
    REROUTE = auto()  # Jump to different stage
    ESCALATE = auto()  # Escalate to human
    ABORT = auto()  # Abort entire operation
    FETCH_INFO = auto()  # Fetch external information
    CREATE_RULE = auto()  # Create new automation rule
    PAUSE = auto()  # Temporary pause for cooldown
    CHECKPOINT = auto()  # Save state before risky operation


@dataclass
class StrategyDecision:
    """
    Encapsulates a strategic decision with full context.

    Attributes:
        action: The decision type
        target_stage: For REROUTE decisions, where to go
        reason: Human-readable explanation
        confidence: 0.0-1.0 confidence in this decision
        metadata: Additional context-specific data
        estimated_cost: Predicted cost of this action
    """

    action: Decision
    target_stage: Optional[str] = None
    reason: str = ""
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    estimated_cost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/persistence."""
        return {
            "action": self.action.name,
            "target_stage": self.target_stage,
            "reason": self.reason,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "estimated_cost": self.estimated_cost,
            "timestamp": datetime.now().isoformat(),
        }
