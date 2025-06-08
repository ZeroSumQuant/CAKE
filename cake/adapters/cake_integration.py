#!/usr/bin/env python3
"""cake_integration.py - Main integration point for CAKE with Claude

This is the main entry point that hooks CAKE into Claude's workflow,
monitoring actions and injecting interventions as needed.

Author: CAKE Team
License: MIT
Python: 3.11+
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from cake.adapters.cake_adapter import create_cake_system

# Import new intervention components
from cake.components.operator import InterventionContext, InterventionType

# Import core components
from cake.core.cake_controller import CakeController

# from cake.core.strategist import Strategist
# from cake.core.stage_router import StageRouter
# from cake.utils.rule_creator import RuleCreator
# from cake.utils.info_fetcher import InfoFetcher

logger = logging.getLogger(__name__)


class CAKEIntegration:
    """Main integration class that connects CAKE components with Claude's workflow."""

    def __init__(self, config_path: Path):
        """Initialize CAKE integration.

        Args:
            config_path: Path to CAKE configuration directory
        """
        self.config_path = config_path
        self.config = self._load_config()

        # Initialize CAKE adapter
        self.adapter = create_cake_system(config_path)

        # Initialize enhanced controller
        self.controller = CakeController(self.config_path, claude_client=self.adapter.claude_client) # Added controller initialization

        # Hook registration
        self._register_hooks()

        logger.info("CAKE Integration initialized")

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
            "strictness": 1.0,
            "recall_ttl_hours": 24,
            "intervention_enabled": True,
            "auto_cleanup": True,
            "min_coverage": 90,
            "enable_telemetry": False,
            "enable_logging_hook": True,
            "escalation_webhook": None,
        }

    def _register_hooks(self):
        """Register system hooks."""  # Hook for telemetry
        if self.config.get("enable_telemetry"):
            self.adapter.add_post_message_hook(self._telemetry_hook)

        # Hook for escalation
        if self.config.get("escalation_webhook"):
            self.adapter.add_post_message_hook(self._escalation_hook)

    async def start_task(
        self, task_description: str, constitution: Dict[str, Any]
    ) -> str:
        """
        Start a new task with CAKE supervision.

        Args:
            task_description: Description of the task
            constitution: User preferences and configuration

        Returns:
            Task ID for tracking
        """
        # Create controller for this task
        # self.controller = CakeController( # Removed this line
        #     constitution=constitution, task_description=task_description
        # )
        await self.controller.start_task(task_description, constitution) # Added this call

        # Update adapter with task context
        self.adapter.update_task_context(
            {
                "description": task_description,
                "type": self._classify_task_type(task_description),
                "scope": self._extract_task_scope(task_description),
                "domain": constitution.get("domain", "software_development"),
            }
        )

        # Get relevant knowledge for this task
        knowledge = self.adapter.get_relevant_knowledge()
        if knowledge:
            logger.info(f"Found {len(knowledge)} relevant knowledge entries")

            # Inject knowledge as context
            knowledge_summary = self._format_knowledge(knowledge)
            await self.adapter.inject_system_message(
                f"Operator (CAKE): Based on previous experience:\n{knowledge_summary}",
                priority=False,
            )

        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Started task {task_id}: {task_description}")

        return task_id

    async def process_stage(
        self, stage: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a TRRDEVS stage with supervision.

        Args:
            stage: Current stage name
            context: Stage execution context

        Returns:
            Processing result with any interventions
        """  # Update adapter state
        self.adapter.update_stage(stage)

        # Check for pre-stage interventions
        pre_check = await self._pre_stage_check(stage, context)
        if pre_check.get("intervention"):
            return pre_check

        # Process stage (would integrate with actual Claude execution)
        result = {"stage": stage, "status": "processing", "interventions": []}

        # Simulate stage processing with intervention checks
        if "error" in context:
            # Check for repeat error
            error_msg = self.adapter.report_error(context["error"])
            if error_msg:
                result["interventions"].append(error_msg)
                result["status"] = "intervention_required"

        if "action" in context:
            # Process action
            intervention = await self.adapter.process_claude_action(context["action"])
            if intervention:
                result["interventions"].append(intervention)
                result["status"] = "intervention_required"

        return result

    async def check_ci_status(self) -> Optional[str]:
        """Check CI status and return intervention if needed."""  # This would integrate with actual CI system
        ci_status = self._get_ci_status()
        return self.adapter.update_ci_status(ci_status)

    async def check_linters(self) -> Optional[str]:
        """Check linter status and return intervention if needed."""  # This would integrate with actual linters
        linter_status = self._get_linter_status()
        return self.adapter.update_linter_status(linter_status)

    async def validate_changes(self, changes: Dict[str, Any]) -> Optional[str]:
        """Validate changes for feature creep and other issues."""
        return self.adapter.check_feature_creep(changes)

    async def finalize_task(
        self, stage_outputs: Dict[str, Any], artifacts: List[str]
    ) -> Dict[str, Any]:
        """
        Finalize task and validate convergence.

        Args:
            stage_outputs: Outputs from each stage
            artifacts: Final artifacts produced

        Returns:
            Final validation report
        """  # Validate task convergence
        validation = await self.adapter.validate_task_convergence(
            stage_outputs, artifacts
        )

        # Get final statistics
        stats = self.adapter.get_system_status()

        # Clean up if needed
        if self.config.get("auto_cleanup"):
            await self.adapter.cleanup()

        return {
            "validation": validation,
            "statistics": stats,
            "intervention_count": stats["intervention_count"],
        }

    async def _pre_stage_check(
        self, stage: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Pre-stage intervention checks."""
        result = {"intervention": None}

        # Check if skipping tests
        if stage == "validate" and not context.get("tests_written"):
            # FIX: Build context and return string message
            intervention_context = InterventionContext(
                intervention_type=InterventionType.TEST_SKIP,
                current_action="stage_transition",
                task_context={
                    "changed_files": context.get("changed_files", []),
                    "min_coverage": self.config.get("min_coverage", 90),
                },
            )
            # FIX: Get string message from operator
            intervention_message = self.adapter.operator.build_message(
                intervention_context
            )
            result["intervention"] = intervention_message

        return result

    def _classify_task_type(self, description: str) -> str:
        """Classify task type from description."""
        desc_lower = description.lower()

        if any(word in desc_lower for word in ["fix", "bug", "error", "issue"]):
            return "bug_fix"
        elif any(
            word in desc_lower for word in ["add", "implement", "create", "feature"]
        ):
            return "feature"
        elif any(word in desc_lower for word in ["refactor", "optimize", "improve"]):
            return "refactor"
        elif any(word in desc_lower for word in ["test", "testing"]):
            return "testing"
        else:
            return "general"

    def _extract_task_scope(self, description: str) -> List[str]:
        """Extract scope indicators from task description."""  # This would use more sophisticated NLP in production
        scope = []

        # Look for file mentions
        import re

        file_pattern = r"\b\w+\.(py|js|tsx?|jsx?|json|yaml|yml)\b"
        files = re.findall(file_pattern, description)
        scope.extend(files)

        # Look for module/component mentions
        if "auth" in description.lower():
            scope.extend(["auth", "login", "authentication"])
        if "api" in description.lower():
            scope.extend(["api", "endpoint", "routes"])

        return scope

    def _format_knowledge(self, knowledge: List[Dict[str, Any]]) -> str:
        """Format knowledge entries for injection."""
        formatted = []

        for i, entry in enumerate(knowledge[:3], 1):  # Top 3
            formatted.append(
                f"{i}. {entry['type']}: {entry['application_guidance']} "
                f"(confidence: {entry['confidence']:.0%})"
            )

        return "\n".join(formatted)

    def _get_ci_status(self) -> Dict[str, Any]:
        """Get current CI status (mock implementation)."""  # This would integrate with actual CI
        return {"passing": True, "failing_tests": [], "test_command": "pytest -xvs"}

    def _get_linter_status(self) -> Dict[str, Any]:
        """Get current linter status (mock implementation)."""  # This would integrate with actual linters
        return {"linter_name": "flake8", "violations": []}

    def _telemetry_hook(self, message: str, context: Any):
        """Send telemetry data."""  # This would send to actual telemetry service
        logger.debug(f"Telemetry: {context.intervention_type.name}")

    def _escalation_hook(self, message: str, context: Any):
        """Handle escalations."""
        if context.intervention_type.name == "ESCALATE":
            # This would send to actual webhook
            logger.warning(f"Escalation triggered: {message}")


# CLI Interface
async def main():
    """Main CLI interface for CAKE."""
    import argparse

    parser = argparse.ArgumentParser(description="CAKE - Claude Autonomy Kit")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".cake",
        help="Configuration directory",
    )
    parser.add_argument("--task", type=str, help="Task description")
    parser.add_argument("--check-ci", action="store_true", help="Check CI status")
    parser.add_argument("--check-linters", action="store_true", help="Check linters")
    parser.add_argument("--status", action="store_true", help="Show system status")

    args = parser.parse_args()

    # Ensure config directory exists
    args.config.mkdir(parents=True, exist_ok=True)

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create integration
    cake = CAKEIntegration(args.config)

    if args.status:
        # Show status
        status = cake.adapter.get_system_status()
        print(json.dumps(status, indent=2))

    elif args.check_ci:
        # Check CI
        intervention = await cake.check_ci_status()
        if intervention:
            print(intervention)
        else:
            print("CI check passed")

    elif args.check_linters:
        # Check linters
        intervention = await cake.check_linters()
        if intervention:
            print(intervention)
        else:
            print("Linter check passed")

    elif args.task:
        # Start task
        constitution = {
            "domain": "software_development",
            "principles": ["quality", "efficiency", "maintainability"],
        }

        task_id = await cake.start_task(args.task, constitution)
        print(f"Started task: {task_id}")

        # Simulate stage processing
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
            print(f"\nProcessing stage: {stage}")

            # Simulate context
            context = {"stage": stage}

            # Add some test scenarios
            if stage == "execute" and "api" in args.task.lower():
                context["error"] = {
                    "type": "ModuleNotFoundError",
                    "message": "ModuleNotFoundError: No module named 'requests'",
                    "file_path": "main.py",
                }

            result = await cake.process_stage(stage, context)

            if result["interventions"]:
                for intervention in result["interventions"]:
                    print(f"  {intervention}")
            else:
                print(f"  ✓ Stage completed")

        # Finalize
        validation = await cake.finalize_task({}, [])
        print(
            f"\nTask completed. Interventions: {validation['statistics']['intervention_count']}"
        )

    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
