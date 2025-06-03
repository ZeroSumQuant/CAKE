#!/usr/bin/env python3
"""cake_adapter.py - Integration adapter for CAKE with Claude

Hooks into Claude's context to prepend operator messages and
maintain conversation flow while enforcing interventions.

Author: CAKE Team
License: MIT
Python: 3.11+
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from cake.components.operator import (
    InterventionAnalyzer,
    InterventionContext,
    InterventionType,
    OperatorBuilder,
)
from cake.components.recall_db import RecallDB
from cake.components.validator import TaskConvergenceValidator
from cake.utils.cross_task_knowledge_ledger import CrossTaskKnowledgeLedger

logger = logging.getLogger(__name__)


class MessageRole(Enum):
    """Message roles in conversation."""

    SYSTEM = auto()  # System-level messages (highest authority)
    OPERATOR = auto()  # Operator interventions
    USER = auto()  # User messages
    ASSISTANT = auto()  # Assistant (Claude) messages


@dataclass
class ConversationMessage:
    """A message in the conversation."""

    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemState:
    """Current state of the CAKE system."""

    task_context: Dict[str, Any]
    current_stage: str
    current_action: str
    error_state: Optional[Dict[str, Any]] = None
    ci_status: Optional[Dict[str, Any]] = None
    linter_status: Optional[Dict[str, Any]] = None
    coverage_metrics: Optional[Dict[str, Any]] = None
    changes: Dict[str, Any] = field(default_factory=dict)
    command_queue: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CAKEAdapter:
    """
    Main adapter that integrates CAKE components with Claude.

    Monitors Claude's actions, detects intervention needs, and
    injects operator messages when necessary.
    """

    def __init__(
        self,
        operator: OperatorBuilder,
        recall_db: RecallDB,
        knowledge_ledger: CrossTaskKnowledgeLedger,
        validator: TaskConvergenceValidator,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize CAKE adapter.

        Args:
            operator: Operator message builder
            recall_db: 24-hour error memory
            knowledge_ledger: Cross-task knowledge system
            validator: Task convergence validator
            config: Optional configuration
        """
        self.operator = operator
        self.recall_db = recall_db
        self.knowledge_ledger = knowledge_ledger
        self.validator = validator
        self.analyzer = InterventionAnalyzer()

        # Configuration
        self.config = config or {}
        self.intervention_enabled = self.config.get("intervention_enabled", True)
        self.auto_cleanup = self.config.get("auto_cleanup", True)
        self.debug_mode = self.config.get("debug_mode", False)

        # State tracking
        self.conversation_history: List[ConversationMessage] = []
        self.current_state = SystemState(
            task_context={}, current_stage="think", current_action="initializing"
        )
        self.intervention_count = 0
        self.last_intervention_time: Optional[datetime] = None

        # Hooks for external systems
        self.pre_message_hooks: List[Callable] = []
        self.post_message_hooks: List[Callable] = []

        logger.info("CAKEAdapter initialized")

    async def process_claude_action(self, action: Dict[str, Any]) -> Optional[str]:
        """
        Process an action from Claude and determine if intervention is needed.

        Args:
            action: Action details from Claude

        Returns:
            Operator message if intervention needed, None otherwise
        """  # Update system state
        self._update_state_from_action(action)

        # Check if intervention is needed
        if not self.intervention_enabled:
            return None

        intervention_context = self.analyzer.analyze_situation(
            self._state_to_dict(), self.recall_db
        )

        if intervention_context:
            # Build operator message
            message = self.operator.build_message(intervention_context)

            # Record intervention
            self._record_intervention(message, intervention_context)

            # Execute hooks
            await self._execute_post_hooks(message, intervention_context)

            return message

        return None

    def report_error(self, error: Dict[str, Any]) -> Optional[str]:
        """
        Report an error and check if it's a repeat.

        Args:
            error: Error details

        Returns:
            Intervention message if repeat error, None otherwise
        """  # Check if repeat error
        if self.recall_db.is_repeat_error(error.get("message", "")):
            context = InterventionContext(
                intervention_type=InterventionType.REPEAT_ERROR,
                current_action="error_handling",
                error_details=error,
                previous_attempts=self.recall_db.get_error_history(error.get("message", "")),
            )
            return self.operator.build_message(context)

        # Record new error
        self.recall_db.record_error(error)
        return None

    def update_ci_status(self, status: Dict[str, Any]) -> Optional[str]:
        """Update CI status and check for intervention."""
        self.current_state.ci_status = status

        if not status.get("passing", True):
            context = InterventionContext(
                intervention_type=InterventionType.CI_FAILURE,
                current_action="ci_check",
                ci_status=status,
            )
            return self.operator.build_message(context)

        return None

    def update_linter_status(self, status: Dict[str, Any]) -> Optional[str]:
        """Update linter status and check for intervention."""
        self.current_state.linter_status = status

        if status.get("violations", []):
            context = InterventionContext(
                intervention_type=InterventionType.LINTER_VIOLATION,
                current_action="linter_check",
                task_context={"violations": status["violations"]},
            )
            return self.operator.build_message(context)

        return None

    def check_feature_creep(self, changes: Dict[str, Any]) -> Optional[str]:
        """Check for feature creep during bug fixes."""
        if self.current_state.task_context.get("type") == "bug_fix":
            # Check if changes go beyond bug fix scope
            if self._detect_feature_creep(changes):
                context = InterventionContext(
                    intervention_type=InterventionType.FEATURE_CREEP,
                    current_action="code_change",
                    task_context={"changes": changes},
                )
                return self.operator.build_message(context)

        return None

    def update_task_context(self, context: Dict[str, Any]):
        """Update task context."""
        self.current_state.task_context.update(context)

    def update_stage(self, stage: str):
        """Update current TRRDEVS stage."""
        self.current_state.current_stage = stage

    def get_relevant_knowledge(self) -> List[Dict[str, Any]]:
        """Get relevant knowledge for current task."""
        return self.knowledge_ledger.search_relevant_knowledge(
            self.current_state.task_context, limit=5
        )

    async def inject_system_message(self, message: str, priority: bool = True):
        """
        Inject a system message into the conversation.

        Args:
            message: Message content
            priority: Whether this is high priority
        """
        msg = ConversationMessage(
            role=MessageRole.SYSTEM if priority else MessageRole.OPERATOR,
            content=message,
            metadata={"injected": True},
        )
        self.conversation_history.append(msg)

        # Execute pre-hooks
        await self._execute_pre_hooks(message)

    async def validate_task_convergence(
        self, stage_outputs: Dict[str, Any], artifacts: List[str]
    ) -> Dict[str, Any]:
        """Validate task completed successfully."""
        return self.validator.validate_convergence(
            {
                "stage_outputs": stage_outputs,
                "artifacts": artifacts,
                "task_description": self.current_state.task_context.get("description", ""),
            }
        )

    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status."""
        return {
            "intervention_count": self.intervention_count,
            "current_stage": self.current_state.current_stage,
            "errors_in_memory": self.recall_db.get_error_count(),
            "knowledge_entries": self.knowledge_ledger.get_entry_count(),
            "last_intervention": (
                self.last_intervention_time.isoformat() if self.last_intervention_time else None
            ),
        }

    def add_pre_message_hook(self, hook: Callable):
        """Add pre-message hook."""
        self.pre_message_hooks.append(hook)

    def add_post_message_hook(self, hook: Callable):
        """Add post-message hook."""
        self.post_message_hooks.append(hook)

    async def cleanup(self):
        """Clean up resources."""
        self.recall_db.cleanup_old_entries()
        if self.auto_cleanup:
            self.conversation_history = [
                msg
                for msg in self.conversation_history
                if (datetime.now() - msg.timestamp).total_seconds() < 3600
            ]

    def _update_state_from_action(self, action: Dict[str, Any]):
        """Update internal state from Claude action."""
        self.current_state.current_action = action.get("type", "unknown")

        if "command" in action:
            self.current_state.command_queue.append(action["command"])

        if "changes" in action:
            self.current_state.changes.update(action["changes"])

    def _state_to_dict(self) -> Dict[str, Any]:
        """Convert current state to dictionary."""
        return {
            "task_context": self.current_state.task_context,
            "current_stage": self.current_state.current_stage,
            "current_action": self.current_state.current_action,
            "error_state": self.current_state.error_state,
            "ci_status": self.current_state.ci_status,
            "linter_status": self.current_state.linter_status,
            "coverage_metrics": self.current_state.coverage_metrics,
            "command_history": self.current_state.command_queue[-10:],  # Last 10 commands
        }

    def _detect_feature_creep(self, changes: Dict[str, Any]) -> bool:
        """Detect if changes go beyond bug fix scope."""  # Simple heuristics for feature creep
        indicators = [
            len(changes.get("new_files", [])) > 2,
            len(changes.get("new_functions", [])) > 5,
            any("feature" in f.lower() for f in changes.get("new_files", [])),
            changes.get("lines_added", 0) > 200,
        ]

        return sum(indicators) >= 2

    def _record_intervention(self, message: str, context: InterventionContext):
        """Record an intervention."""
        self.intervention_count += 1
        self.last_intervention_time = datetime.now()

        # Add to conversation history
        msg = ConversationMessage(
            role=MessageRole.OPERATOR,
            content=message,
            metadata={
                "intervention_type": context.intervention_type.name,
                "context": context.task_context,
            },
        )
        self.conversation_history.append(msg)

        logger.info(f"Intervention #{self.intervention_count}: {context.intervention_type.name}")

    async def _execute_pre_hooks(self, message: str):
        """Execute pre-message hooks."""
        for hook in self.pre_message_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(message)
                else:
                    hook(message)
            except Exception as e:
                logger.error(f"Pre-hook failed: {e}")

    async def _execute_post_hooks(self, message: str, context: Any):
        """Execute post-message hooks."""
        for hook in self.post_message_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(message, context)
                else:
                    hook(message, context)
            except Exception as e:
                logger.error(f"Post-hook failed: {e}")


def create_cake_system(config_path: Path) -> CAKEAdapter:
    """
    Factory function to create a complete CAKE system.

    Args:
        config_path: Path to configuration directory

    Returns:
        Configured CAKEAdapter instance
    """
    # Load configuration
    config_file = config_path / "cake_config.yaml"
    config = {}
    if config_file.exists():
        import yaml

        with open(config_file) as f:
            config = yaml.safe_load(f)

    # Initialize components
    operator = OperatorBuilder()
    recall_db = RecallDB(config_path / "recall.db")
    knowledge_ledger = CrossTaskKnowledgeLedger(config_path / "knowledge.db")
    validator = TaskConvergenceValidator()

    # Create adapter
    adapter = CAKEAdapter(
        operator=operator,
        recall_db=recall_db,
        knowledge_ledger=knowledge_ledger,
        validator=validator,
        config=config,
    )

    logger.info("CAKE system created")
    return adapter
