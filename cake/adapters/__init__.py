"""CAKE Adapters - Integration points with Claude and external systems."""

from .cake_adapter import CAKEAdapter, create_cake_system
from .cake_integration import CAKEIntegration
from .claude_orchestration import (
    ContextEnhancer,
    PromptOrchestrator,
    PromptTemplateLibrary,
    ResponseAnalyzer,
)

__all__ = [
    "CAKEAdapter",
    "create_cake_system",
    "CAKEIntegration",
    "PromptOrchestrator",
    "PromptTemplateLibrary",
    "ContextEnhancer",
    "ResponseAnalyzer",
]
