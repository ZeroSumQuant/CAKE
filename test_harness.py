#!/usr/bin/env python3
"""CAKE Testing Harness - Progressive Component Testing
"""

import importlib
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))


@dataclass
class ComponentTest:
    name: str
    module_path: str
    status: str = "untested"
    error: str = ""
    dependencies: List[str] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


# Define test order (dependencies first)
COMPONENT_TESTS = [
    # Core components (no dependencies on other CAKE components)
    ComponentTest("Operator", "cake.components.operator"),
    ComponentTest("RecallDB", "cake.components.recall_db"),
    ComponentTest("Validator", "cake.components.validator"),
    ComponentTest("SnapshotManager", "cake.components.snapshot_manager"),
    ComponentTest("RuleCreator", "cake.utils.rule_creator"),
    # Components with dependencies
    ComponentTest("PTYShim", "cake.core.pty_shim"),
    ComponentTest("Watchdog", "cake.core.watchdog"),
    ComponentTest("VoiceSimilarityGate", "cake.components.voice_similarity_gate"),
    ComponentTest("EscalationDecider", "cake.core.escalation_decider"),
    ComponentTest("KnowledgeLedger", "cake.utils.cross_task_knowledge_ledger"),
    ComponentTest("AdaptiveEngine", "cake.components.adaptive_confidence_engine"),
    ComponentTest("TRRDEVSEngine", "cake.core.trrdevs_engine"),
    ComponentTest("CakeController", "cake.core.cake_controller"),
    ComponentTest("CAKEAdapter", "cake.adapters.cake_adapter"),
]


class TestHarness:
    def __init__(self):
        self.results: Dict[str, ComponentTest] = {}
        self.working_components: List[str] = []
        self.failed_components: List[str] = []

    def test_component(self, component: ComponentTest) -> bool:
        """Test a single component import"""print(f"\n{'='*60}")
        print(f"Testing: {component.name}")
        print(f"Module: {component.module_path}")

        try:
            module = importlib.import_module(component.module_path)
            component.status = "working"
            self.working_components.append(component.name)
            print(f"✅ SUCCESS: Module imported successfully")
            return True

        except ImportError as e:
            component.status = "import_error"
            component.error = str(e)
            self.failed_components.append(component.name)
            print(f"❌ IMPORT ERROR: {e}")

        except SyntaxError as e:
            component.status = "syntax_error"
            component.error = f"Line {e.lineno}: {e.msg}"
            self.failed_components.append(component.name)
            print(f"❌ SYNTAX ERROR: {component.error}")
            print(f"   → File: {e.filename}")

        except Exception as e:
            component.status = "runtime_error"
            component.error = str(e)
            self.failed_components.append(component.name)
            print(f"❌ RUNTIME ERROR: {e}")

        return False

    def run_progressive_tests(self):
        """Run tests in dependency order"""print("\nCAKE COMPONENT TESTING")
        print("=" * 60)

        for component in COMPONENT_TESTS:
            self.results[component.name] = component
            self.test_component(component)

        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)

        print(f"\n✅ Working: {len(self.working_components)}")
        for comp in self.working_components:
            print(f"   - {comp}")

        print(f"\n❌ Failed: {len(self.failed_components)}")
        for comp in self.failed_components:
            component = self.results[comp]
            print(f"   - {comp}: {component.error}")

        print(f"\n📊 Score: {len(self.working_components)}/{len(COMPONENT_TESTS)}")


def main():
    harness = TestHarness()
    harness.run_progressive_tests()


if __name__ == "__main__":
    main()
