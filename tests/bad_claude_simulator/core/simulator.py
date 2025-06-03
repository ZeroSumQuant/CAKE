"""
Main simulator engine for Bad Claude adversarial testing.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..attacks import DataExfiltrationAttack, PromptInjectionAttack, ResourceAttack
from .attack_patterns import AttackCategory, AttackPattern


@dataclass
class AttackResult:
    """
    Result of an attack execution."""

    attack_id: str
    attack_type: AttackCategory
    timestamp: datetime
    success: bool
    detection_triggered: bool
    cake_response: Optional[Dict[str, Any]]
    error_details: Optional[str]
    metadata: Dict[str, Any]


class BadClaudeSimulator:
    """
    Simulates adversarial AI behavior for testing CAKE's defenses.

    This simulator provides controlled adversarial testing capabilities
    to ensure CAKE can properly detect and handle malicious behaviors.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Bad Claude Simulator.

        Args:
            config: Configuration dictionary for simulator settings
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self.attack_history: List[AttackResult] = []

        # Initialize attack modules
        self.attacks = {
            AttackCategory.PROMPT_INJECTION: PromptInjectionAttack(),
            AttackCategory.RESOURCE_EXHAUSTION: ResourceAttack(),
            AttackCategory.DATA_EXFILTRATION: DataExfiltrationAttack(),
        }

        # Safety check
        self.safe_mode = self.config.get("safe_mode", True)
        if not self.safe_mode:
            self.logger.warning("Bad Claude running in UNSAFE mode - use with caution!")

    def execute_attack(
        self, attack_pattern: AttackPattern, target_system: Any, **kwargs
    ) -> AttackResult:
        """
        Execute a specific attack pattern against the target system.

        Args:
            attack_pattern: The attack pattern to execute
            target_system: The CAKE instance or component to test
            **kwargs: Additional parameters for the attack

        Returns:
            AttackResult containing execution details
        """
        self.logger.info(f"Executing attack: {attack_pattern.name}")

        # Get the appropriate attack handler
        attack_handler = self.attacks.get(attack_pattern.category)
        if not attack_handler:
            raise ValueError(f"No handler for attack category: {attack_pattern.category}")

        # Execute the attack
        try:
            result = attack_handler.execute(
                pattern=attack_pattern, target=target_system, safe_mode=self.safe_mode, **kwargs
            )

            # Create attack result
            attack_result = AttackResult(
                attack_id=f"bad_claude_{datetime.now().isoformat()}",
                attack_type=attack_pattern.category,
                timestamp=datetime.now(),
                success=result.get("success", False),
                detection_triggered=result.get("detected", False),
                cake_response=result.get("response"),
                error_details=result.get("error"),
                metadata=result.get("metadata", {}),
            )

            # Log the result
            self.attack_history.append(attack_result)
            self._log_attack_result(attack_result)

            return attack_result

        except Exception as e:
            self.logger.error(f"Attack execution failed: {str(e)}")
            raise

    def run_scenario(self, scenario_name: str, target_system: Any, **kwargs) -> List[AttackResult]:
        """
        Run a predefined attack scenario.

        Args:
            scenario_name: Name of the scenario to run
            target_system: The CAKE instance to test
            **kwargs: Additional scenario parameters

        Returns:
            List of AttackResults from the scenario
        """
        self.logger.info(f"Running scenario: {scenario_name}")

        # Import scenarios dynamically
        from ..scenarios import get_scenario

        scenario = get_scenario(scenario_name)
        if not scenario:
            raise ValueError(f"Unknown scenario: {scenario_name}")

        results = []
        for attack_pattern in scenario.attack_sequence:
            try:
                result = self.execute_attack(
                    attack_pattern=attack_pattern, target_system=target_system, **kwargs
                )
                results.append(result)

                # Check if we should continue based on result
                if scenario.stop_on_detection and result.detection_triggered:
                    self.logger.info("Detection triggered - stopping scenario")
                    break

            except Exception as e:
                self.logger.error(f"Error in scenario execution: {str(e)}")
                if scenario.stop_on_error:
                    break

        return results

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate a summary report of all attacks executed.

        Returns:
            Dictionary containing attack statistics and results
        """
        total_attacks = len(self.attack_history)
        successful_attacks = sum(1 for r in self.attack_history if r.success)
        detected_attacks = sum(1 for r in self.attack_history if r.detection_triggered)

        report = {
            "summary": {
                "total_attacks": total_attacks,
                "successful_attacks": successful_attacks,
                "detected_attacks": detected_attacks,
                "detection_rate": detected_attacks / total_attacks if total_attacks > 0 else 0,
            },
            "by_category": self._group_by_category(),
            "timeline": [self._serialize_result(r) for r in self.attack_history],
            "generated_at": datetime.now().isoformat(),
        }

        return report

    def reset(self):
        """Reset the simulator state."""
        self.attack_history.clear()
        self.logger.info("Bad Claude Simulator reset")

    def _log_attack_result(self, result: AttackResult):
        """Log an attack result."""
        log_entry = {
            "attack_id": result.attack_id,
            "type": result.attack_type.value,
            "success": result.success,
            "detected": result.detection_triggered,
            "timestamp": result.timestamp.isoformat(),
        }

        if self.config.get("log_attacks", True):
            self.logger.info(f"Attack result: {json.dumps(log_entry)}")

    def _group_by_category(self) -> Dict[str, Dict[str, int]]:
        """Group attack results by category."""
        categories = {}
        for result in self.attack_history:
            cat_name = result.attack_type.value
            if cat_name not in categories:
                categories[cat_name] = {"total": 0, "successful": 0, "detected": 0}

            categories[cat_name]["total"] += 1
            if result.success:
                categories[cat_name]["successful"] += 1
            if result.detection_triggered:
                categories[cat_name]["detected"] += 1

        return categories

    def _serialize_result(self, result: AttackResult) -> Dict[str, Any]:
        """Serialize an AttackResult for reporting."""
        return {
            "attack_id": result.attack_id,
            "attack_type": result.attack_type.value,
            "timestamp": result.timestamp.isoformat(),
            "success": result.success,
            "detection_triggered": result.detection_triggered,
            "error_details": result.error_details,
            "metadata": result.metadata,
        }
