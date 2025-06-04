#!/usr/bin/env python3
"""
Check health of each CAKE component and identify what needs fixing.
"""

import importlib
import sys
from pathlib import Path

# Component list from CLAUDE.md
CORE_COMPONENTS = [
    ("CakeController", "cake.core.cake_controller", "CakeController"),
    ("Operator", "cake.components.operator", "OperatorBuilder"),
    ("RecallDB", "cake.components.recall_db", "RecallDB"),
    ("PTYShim", "cake.components.pty_shim", "PTYShim"),
    ("Validator", "cake.components.validator", "TaskConvergenceValidator"),
    ("Watchdog", "cake.components.watchdog", "Watchdog"),  # Missing
    ("SnapshotManager", "cake.components.snapshot_manager", "SnapshotManager"),
    (
        "VoiceSimilarityGate",
        "cake.components.voice_gate",
        "VoiceSimilarityGate",
    ),  # Missing
    ("KnowledgeLedger", "cake.components.knowledge_ledger", "CrossTaskKnowledgeLedger"),
]

UTILS_COMPONENTS = [
    ("Models", "cake.utils.models", None),
    ("RateLimiter", "cake.utils.rate_limiter", "RateLimiter"),
    ("RuleCreator", "cake.utils.rule_creator", "RuleCreator"),
    ("InfoFetcher", "cake.utils.info_fetcher", "InfoFetcher"),
    (
        "AdaptiveConfidence",
        "cake.utils.adaptive_confidence",
        "AdaptiveConfidenceEngine",
    ),
]

ADAPTER_COMPONENTS = [
    ("CAKEAdapter", "cake.adapters.cake_adapter", "CAKEAdapter"),
    ("CAKEIntegration", "cake.adapters.cake_integration", "CAKEIntegration"),
    ("PromptOrchestrator", "cake.adapters.claude_orchestration", "PromptOrchestrator"),
]


def check_component(name, module_path, class_name=None):
    """Check if a component can be imported."""
    try:
        module = importlib.import_module(module_path)
        if class_name:
            if hasattr(module, class_name):
                print(f"✓ {name:<20} - Module and class found")
                return True, None
            else:
                print(f"✗ {name:<20} - Module found but class '{class_name}' missing")
                return False, f"Class {class_name} not found"
        else:
            print(f"✓ {name:<20} - Module found")
            return True, None
    except ImportError as e:
        print(f"✗ {name:<20} - ImportError: {e}")
        return False, str(e)
    except SyntaxError as e:
        print(f"✗ {name:<20} - SyntaxError: {e}")
        return False, str(e)
    except Exception as e:
        print(f"✗ {name:<20} - {type(e).__name__}: {e}")
        return False, str(e)


def main():
    """Run health check on all components."""
    # Add project root to path
    sys.path.insert(0, str(Path(__file__).parent))

    print("CAKE Component Health Check\n")
    print("=" * 60)

    all_results = []

    print("\n🎯 Core Components (Required):")
    print("-" * 60)
    for component in CORE_COMPONENTS:
        success, error = check_component(*component)
        all_results.append((component[0], success, error))

    print("\n🔧 Utils Components:")
    print("-" * 60)
    for component in UTILS_COMPONENTS:
        success, error = check_component(*component)
        all_results.append((component[0], success, error))

    print("\n🔌 Adapter Components:")
    print("-" * 60)
    for component in ADAPTER_COMPONENTS:
        success, error = check_component(*component)
        all_results.append((component[0], success, error))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("=" * 60)

    successful = sum(1 for _, success, _ in all_results if success)
    failed = len(all_results) - successful

    print(f"✓ Successful: {successful}/{len(all_results)}")
    print(f"✗ Failed: {failed}/{len(all_results)}")

    if failed > 0:
        print("\n❌ Components needing fixes:")
        for name, success, error in all_results:
            if not success:
                print(f"  - {name}: {error}")

    # Missing components
    print("\n⚠️  Missing Components (need implementation):")
    print("  - Watchdog (stream monitor)")
    print("  - VoiceSimilarityGate (style consistency checker)")

    # Truncated files
    print("\n📄 Truncated/Incomplete Files:")
    print("  - cake/adapters/cake_adapter.py (line 136)")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
