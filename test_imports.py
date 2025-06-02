#!/usr/bin/env python3
"""Test basic imports to identify what's broken."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def test_import(module_path, component_name=""):
    """Test importing a module and report results."""
    try:
        __import__(module_path)
        print(f"✓ {module_path} {component_name}")
        return True
    except ImportError as e:
        print(f"✗ {module_path} - ImportError: {e}")
        return False
    except Exception as e:
        print(f"✗ {module_path} - {type(e).__name__}: {e}")
        return False


# Test imports based on test_cake_core.py expectations
print("Testing Core Module Imports:\n")

# Models
test_import("cake.models", "(expected from test)")
test_import("cake.utils.models", "(actual location)")

# Persistence
test_import("cake.persistence")

# API
test_import("cake.api")

# Core components
test_import("cake.rate_limiter")
test_import("cake.utils.rate_limiter", "(actual location)")
test_import("cake.strategist")
test_import("cake.stage_router")
test_import("cake.core.stage_router", "(actual location)")
test_import("cake.rule_creator")
test_import("cake.utils.rule_creator", "(actual location)")

# Adapters
test_import("cake.adapters")
test_import("cake.adapters.cake_adapter")
test_import("cake.adapters.cake_integration")

# Components
test_import("cake.components.operator")
test_import("cake.components.recall_db")
test_import("cake.components.validator")

print("\nTesting Actual Module Structure:\n")

# Utils
test_import("cake.utils")
test_import("cake.utils.info_fetcher")

# Core
test_import("cake.core")
test_import("cake.core.cake_controller")

# Components
test_import("cake.components")
test_import("cake.components.knowledge_ledger")
