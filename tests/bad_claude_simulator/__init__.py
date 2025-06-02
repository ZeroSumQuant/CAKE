#!/usr/bin/env python3
"""Bad Claude Simulator - A Mischievous AI for Testing CAKE

This module simulates Claude making various mistakes and poor decisions
to test CAKE's intervention capabilities. It's designed to trigger every
type of intervention CAKE can perform.

Remember: Bad Claude is for testing only. Real Claude would never do these things! 😇
"""

from .bad_claude import BadClaude, BadClaudeScenario
from .scenarios import SCENARIO_LIBRARY

__all__ = ["BadClaude", "BadClaudeScenario", "SCENARIO_LIBRARY"]
