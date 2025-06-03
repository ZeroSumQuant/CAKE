#!/usr/bin/env python3
"""cake_controller.py - Main orchestrator for CAKE system

Central controller that manages TRRDEVS workflow execution,
coordinates components, and ensures autonomous operation.

Author: CAKE Team
License: MIT
Python: 3.11+
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional

from cake.components.operator import OperatorBuilder
from cake.components.recall_db import RecallDB
from cake.components.snapshot_manager import SnapshotManager
from cake.components.validator import TaskConvergenceValidator

# Core imports
from cake.core.pty_shim import PTYShim
from cake.core.stage_router import StageRouter
from cake.core.watchdog import Watchdog
from cake.utils.cross_task_knowledge_ledger import CrossTaskKnowledgeLedger
from cake.utils.models import Constitution
from cake.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status."""

    INITIALIZING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    ABORTED = auto()


@dataclass
class TaskContext:
    """Context for task execution."""

    task_id: str
    description: str
    constitution: Constitution
    start_time: datetime = field(default_factory=datetime.now)
    current_stage: str = "think"
    status: TaskStatus = TaskStatus.INITIALIZING
    stage_outputs: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    interventions: List[str] = field(default_factory=list)
    task_metadata: Dict[str, Any] = field(default_factory=dict)


class CakeController:
    """
    Main CAKE orchestrator that manages autonomous task execution.

    Coordinates all components to provide intervention-free operation
    following TRRDEVS methodology.
    """

    def __init__(self, config_path: Path):
        """
        Initialize CAKE controller.

        Args:
            config_path: Path to configuration directory
        """
        self.config_path = config_path
        self.config = self._load_config()

        # Initialize components
        self._init_components()

        # Task tracking
        self.active_tasks: Dict[str, TaskContext] = {}

        logger.info("CakeController initialized")

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        config_file = self.config_path / "cake_config.yaml"
        if config_file.exists():
            import yaml

            with open(config_file) as f:
                return yaml.safe_load(f)
        return self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        """Default configuration."""
        return {
            "max_stage_iterations": 3,
            "timeout_minutes": 120,
            "auto_retry": True,
            "strict_mode": True,
            "min_coverage": 90,
            "enable_snapshots": True,
        }

    def _init_components(self):
        """Initialize all CAKE components."""  # Core components
        self.stage_router = StageRouter()
        self.operator = OperatorBuilder()
        self.recall_db = RecallDB(self.config_path / "recall.db")
        self.validator = TaskConvergenceValidator()
        self.knowledge_ledger = CrossTaskKnowledgeLedger(
            self.config_path / "knowledge.db"
        )

        # Rate limiter for Claude API
        self.rate_limiter = RateLimiter()

        # Initialize core components
        self.watchdog = Watchdog()
        self.pty_shim = PTYShim()
        self.snapshot_manager = SnapshotManager()

    async def start_task(
        self, task_description: str, constitution: Constitution
    ) -> str:
        """
        Start a new autonomous task.

        Args:
            task_description: What to accomplish
            constitution: User preferences and constraints

        Returns:
            Task ID for tracking
        """
        # Generate task ID
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Create task context
        context = TaskContext(
            task_id=task_id, description=task_description, constitution=constitution
        )

        # Store active task
        self.active_tasks[task_id] = context

        # Start execution
        asyncio.create_task(self._execute_task(context))

        logger.info(f"Started task {task_id}: {task_description}")
        return task_id

    async def _execute_task(self, context: TaskContext):
        """Execute task through TRRDEVS stages."""
        try:
            context.status = TaskStatus.IN_PROGRESS

            # Execute stages
            stages = [
                "think",
                "research",
                "reflect",
                "decide",
                "execute",
                "validate",
                "solidify",
            ]

            for stage in stages:
                context.current_stage = stage

                # Check for intervention needs
                intervention = await self._check_intervention_needed(context, stage)
                if intervention:
                    context.interventions.append(intervention)
                    logger.warning(f"Intervention: {intervention}")

                # Execute stage
                result = await self._execute_stage(context, stage)

                # Store output
                context.stage_outputs[stage] = result

                # Check if we should continue
                if not await self._should_continue(context, stage, result):
                    break

            # Validate final result
            if await self._validate_completion(context):
                context.status = TaskStatus.COMPLETED
            else:
                context.status = TaskStatus.FAILED

        except Exception as e:
            logger.error(f"Task {context.task_id} failed: {e}")
            context.status = TaskStatus.FAILED
            context.errors.append(
                {
                    "stage": context.current_stage,
                    "error": str(e),
                    "timestamp": datetime.now(),
                }
            )

    async def _check_intervention_needed(
        self, context: TaskContext, stage: str
    ) -> Optional[str]:
        """Check if operator intervention is needed."""  # Check recall DB for repeat errors
        if context.errors:
            last_error = context.errors[-1]
            if self.recall_db.is_repeat_error(last_error["error"]):
                return self.operator.build_repeat_error_message(last_error["error"])

        # Check stage-specific issues
        if stage == "validate" and not context.stage_outputs.get("execute"):
            return self.operator.build_message(
                {"type": "TEST_SKIP", "context": "No tests written"}
            )

        return None

    async def _execute_stage(self, context: TaskContext, stage: str) -> Dict[str, Any]:
        """Execute a single TRRDEVS stage."""  # This would integrate with Claude
        # For now, return mock result
        return {
            "stage": stage,
            "status": "completed",
            "output": f"Mock output for {stage}",
            "timestamp": datetime.now(),
        }

    async def _should_continue(
        self, context: TaskContext, stage: str, result: Dict[str, Any]
    ) -> bool:
        """Determine if we should continue to next stage."""  # Check for failures
        if result.get("status") == "failed":
            return False

        # Check for abort conditions
        if len(context.errors) > self.config["max_stage_iterations"]:
            logger.error(f"Too many errors in task {context.task_id}")
            return False

        # Check timeout
        elapsed = (datetime.now() - context.start_time).total_seconds()
        if elapsed > self.config["timeout_minutes"] * 60:
            logger.error(f"Task {context.task_id} timed out")
            return False

        return True

    async def _validate_completion(self, context: TaskContext) -> bool:
        """Validate task completed successfully."""
        return self.validator.validate_task_convergence(
            context.stage_outputs, context.description
        )

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a task."""
        if task_id not in self.active_tasks:
            return None

        context = self.active_tasks[task_id]
        return {
            "task_id": task_id,
            "status": context.status.name,
            "current_stage": context.current_stage,
            "interventions": len(context.interventions),
            "errors": len(context.errors),
            "elapsed_minutes": (datetime.now() - context.start_time).total_seconds()
            / 60,
        }

    async def abort_task(self, task_id: str) -> bool:
        """Abort a running task."""
        if task_id not in self.active_tasks:
            return False

        context = self.active_tasks[task_id]
        context.status = TaskStatus.ABORTED

        logger.info(f"Aborted task {task_id}")
        return True

    async def cleanup(self):
        """Clean up resources."""
        # Clean old tasks
        cutoff = datetime.now() - timedelta(hours=24)
        old_tasks = [
            tid for tid, ctx in self.active_tasks.items() if ctx.start_time < cutoff
        ]

        for task_id in old_tasks:
            del self.active_tasks[task_id]

        # Clean recall DB
        self.recall_db.cleanup_old_entries()

        logger.info(f"Cleaned up {len(old_tasks)} old tasks")
