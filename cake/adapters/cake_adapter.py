#!/usr/bin/env python3
"""
cake_adapter.py - Integration adapter for CAKE with Claude

Hooks into Claude's context to prepend operator messages and
maintain conversation flow while enforcing interventions.

Author: CAKE Team
License: MIT
Python: 3.11+
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum, auto

from operator import OperatorBuilder, InterventionAnalyzer, InterventionContext, InterventionType
from recall_db import RecallDB
from task_convergence_validator import TaskConvergenceValidator
from cross_task_knowledge_ledger import CrossTaskKnowledgeLedger

logger = logging.getLogger(__name__)


class MessageRole(Enum):
    """Message roles in conversation."""
    SYSTEM = auto()      # System-level messages (highest authority)
    OPERATOR = auto()    # Operator interventions
    USER = auto()        # User messages
    ASSISTANT = auto()   # Assistant (Claude) messages


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
    
    def __init__(self, 
                 operator: OperatorBuilder,
                 recall_db: RecallDB,
                 knowledge_ledger: CrossTaskKnowledgeLedger,
                 validator: TaskConvergenceValidator,
                 config: Optional[Dict[str, Any]] = None):
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
        self.intervention_enabled = self.config.get('intervention_enabled', True)
        self.auto_cleanup = self.config.get('auto_cleanup', True)
        self.debug_mode = self.config.get('debug_mode', False)
        
        # State tracking
        self.conversation_history: List[ConversationMessage] = []
        self.current_state = SystemState(
            task_context={},
            current_stage='think',
            current_action='initializing'
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
        """
        # Update system state
        self._update_state_from_action(action)
        
        # Check if intervention is needed
        if not self.intervention_enabled:
            return None
        
        intervention_context = self.analyzer.analyze_situation(
            self._state_to_dict(),
            self.recall_db
        )
        
        if intervention