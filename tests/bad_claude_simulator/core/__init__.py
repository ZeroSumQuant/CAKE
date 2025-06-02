"""Core components of the Bad Claude Simulator."""

from . import attack_patterns
from .simulator import BadClaudeSimulator

__all__ = ["BadClaudeSimulator", "attack_patterns"]
