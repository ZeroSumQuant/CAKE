#!/usr/bin/env python3
"""models.py - SQLModel database models for CAKE

Replaces unsafe pickle/SQLite with proper ORM models.
Includes Alembic migration support.

Author: CAKE Team
License: MIT
Python: 3.11+
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

try:
    from sqlalchemy import Index, UniqueConstraint
    from sqlmodel import JSON, Column, Field, Relationship, SQLModel

    SQLMODEL_AVAILABLE = True
except ImportError:
    SQLMODEL_AVAILABLE = False
    # Create minimal mocks for when sqlmodel is not available
    from typing import Any

    class SQLModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def __init_subclass__(cls, table=False, **kwargs):
            # Handle table parameter for SQLModel subclasses
            pass

    def Field(*args, **kwargs):
        if "default_factory" in kwargs:
            return kwargs["default_factory"]()
        elif "default" in kwargs:
            return kwargs["default"]
        return None

    def Relationship(*args, **kwargs):
        return []

    class Column:
        def __init__(self, *args, **kwargs):
            pass

    class JSON:
        pass

    class Index:
        def __init__(self, *args, **kwargs):
            pass

    class UniqueConstraint:
        def __init__(self, *args, **kwargs):
            pass


try:
    from pydantic import BaseModel, validator
except ImportError:
    # Basic mock for pydantic
    def validator(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)


class StageStatus(str, Enum):
    """TRRDEVS stage statuses."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DecisionType(str, Enum):
    """Strategic decision types."""

    PROCEED = "proceed"
    RETRY = "retry"
    REROUTE = "reroute"
    ESCALATE = "escalate"
    ABORT = "abort"
    FETCH_INFO = "fetch_info"
    CREATE_RULE = "create_rule"
    PAUSE = "pause"
    CHECKPOINT = "checkpoint"


class TaskRun(SQLModel, table=True):
    """Main task execution record."""

    __tablename__ = "task_runs"

    record_id: UUID = Field(default_factory=uuid4, primary_key=True)
    task_description: str = Field(index=True)
    constitution_id: UUID = Field(foreign_key="constitutions.constitution_id")

    # Status tracking
    status: StageStatus = Field(default=StageStatus.NOT_STARTED)
    current_stage: Optional[str] = Field(default=None, index=True)

    # Metrics
    total_cost_usd: float = Field(default=0.0)
    total_tokens: int = Field(default=0)
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = Field(default=None)

    # Relationships
    constitution: "Constitution" = Relationship(back_populates="task_runs")
    stage_executions: List["StageExecution"] = Relationship(back_populates="task_run")
    decisions: List["StrategicDecision"] = Relationship(back_populates="task_run")
    rules_created: List["AutomationRule"] = Relationship(
        back_populates="created_by_task"
    )

    class Config:
        arbitrary_types_allowed = True


class Constitution(SQLModel, table=True):
    """User preferences and domain configuration."""

    __tablename__ = "constitutions"

    constitution_id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True, index=True)

    # JSON fields for flexibility
    base_identity: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    domain_overrides: Dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )
    quality_gates: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    task_runs: List[TaskRun] = Relationship(back_populates="constitution")


class StageExecution(SQLModel, table=True):
    """Individual stage execution record."""

    __tablename__ = "stage_executions"
    __table_args__ = (Index("ix_stage_task", "task_run_id", "stage_name"),)

    execution_id: UUID = Field(default_factory=uuid4, primary_key=True)
    task_run_id: UUID = Field(foreign_key="task_runs.record_id", index=True)
    stage_name: str = Field(index=True)
    attempt_number: int = Field(default=1)

    # Execution details
    status: StageStatus
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = Field(default=None)

    # Claude interaction
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    cost_usd: float = Field(default=0.0)

    # Results
    output: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    error: Optional[str] = Field(default=None)

    # Relationships
    task_run: TaskRun = Relationship(back_populates="stage_executions")


class StrategicDecision(SQLModel, table=True):
    """Strategic decisions made by the Strategist."""

    __tablename__ = "strategic_decisions"
    __table_args__ = (Index("ix_decision_task_time", "task_run_id", "timestamp"),)

    decision_id: UUID = Field(default_factory=uuid4, primary_key=True)
    task_run_id: UUID = Field(foreign_key="task_runs.record_id", index=True)

    # Decision details
    decision_type: DecisionType
    from_stage: str
    to_stage: Optional[str] = Field(default=None)
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)

    # Context
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    state_snapshot: Dict[str, Any] = Field(sa_column=Column(JSON))
    extra_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Relationships
    task_run: TaskRun = Relationship(back_populates="decisions")


class AutomationRule(SQLModel, table=True):
    """Learned automation rules."""

    __tablename__ = "automation_rules"
    __table_args__ = (
        UniqueConstraint("signature", name="uq_rule_signature"),
        Index("ix_rule_stage_active", "stage", "is_active"),
    )

    rule_id: UUID = Field(default_factory=uuid4, primary_key=True)
    signature: str = Field(unique=True, index=True)

    # Rule definition
    stage: str = Field(index=True)
    check_expression: str
    fix_command: str

    # Metadata
    confidence: float = Field(ge=0.0, le=1.0)
    safety_score: float = Field(ge=0.0, le=1.0)
    explanation: str

    # Usage tracking
    times_applied: int = Field(default=0)
    times_succeeded: int = Field(default=0)
    is_active: bool = Field(default=True, index=True)

    # Audit trail
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_task_id: Optional[UUID] = Field(foreign_key="task_runs.record_id")
    last_applied_at: Optional[datetime] = Field(default=None)

    # Relationships
    created_by_task: Optional[TaskRun] = Relationship(back_populates="rules_created")
    applications: List["RuleApplication"] = Relationship(back_populates="rule")


class RuleApplication(SQLModel, table=True):
    """Track rule applications for learning."""

    __tablename__ = "rule_applications"

    application_id: UUID = Field(default_factory=uuid4, primary_key=True)
    rule_id: UUID = Field(foreign_key="automation_rules.rule_id", index=True)
    stage_execution_id: UUID = Field(foreign_key="stage_executions.execution_id")

    # Application details
    applied_at: datetime = Field(default_factory=datetime.utcnow)
    success: bool
    execution_time_ms: int
    error_message: Optional[str] = Field(default=None)

    # Relationships
    rule: AutomationRule = Relationship(back_populates="applications")


class ErrorPattern(SQLModel, table=True):
    """Classified error patterns for learning."""

    __tablename__ = "error_patterns"
    __table_args__ = (Index("ix_pattern_hash_stage", "pattern_hash", "stage"),)

    pattern_id: UUID = Field(default_factory=uuid4, primary_key=True)
    pattern_hash: str = Field(index=True)  # Hash of normalized error

    # Pattern details
    stage: str = Field(index=True)
    error_type: str  # E.g., "ModuleNotFoundError"
    error_category: str  # E.g., "dependency", "syntax", "logic"

    # Frequency tracking
    occurrence_count: int = Field(default=1)
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)

    # Pattern data
    example_errors: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    extracted_features: Dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )


class KnowledgeEntry(SQLModel, table=True):
    """Cross-task knowledge base."""

    __tablename__ = "knowledge_entries"
    __table_args__ = (Index("ix_knowledge_type_tags", "entry_type", "tags"),)

    entry_id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Entry classification
    entry_type: str  # "pattern", "solution", "constraint", etc.
    domain: str = Field(default="general", index=True)
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Content
    title: str
    content: Dict[str, Any] = Field(sa_column=Column(JSON))

    # Metadata
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    usage_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships via association table
    related_entries: List["KnowledgeEntry"] = Relationship(
        back_populates="related_entries", link_model="KnowledgeRelation"
    )


class KnowledgeRelation(SQLModel, table=True):
    """Many-to-many relationships between knowledge entries."""

    __tablename__ = "knowledge_relations"

    source_id: UUID = Field(foreign_key="knowledge_entries.entry_id", primary_key=True)
    target_id: UUID = Field(foreign_key="knowledge_entries.entry_id", primary_key=True)
    relation_type: str = Field(default="related")  # "prerequisite", "alternative", etc.
    strength: float = Field(ge=0.0, le=1.0, default=0.5)


class PerformanceMetric(SQLModel, table=True):
    """System performance tracking."""

    __tablename__ = "performance_metrics"
    __table_args__ = (Index("ix_metric_time", "metric_name", "timestamp"),)

    metric_id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Metric identification
    metric_name: str = Field(index=True)  # E.g., "stage_completion_time"
    stage: Optional[str] = Field(default=None, index=True)

    # Value and metadata
    value: float
    unit: str  # "seconds", "tokens", "dollars", etc.
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)

    # Context
    task_run_id: Optional[UUID] = Field(foreign_key="task_runs.record_id", index=True)
    extra_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


# Pydantic models for API requests/responses
class TaskRunCreate(BaseModel):
    """Create a new task run."""

    task_description: str
    constitution_name: str
    cost_budget: float = 10.0
    token_budget: int = 100000


class RuleProposalRequest(BaseModel):
    """Request to create a new rule."""

    stage: str
    error_pattern: str
    check_expression: str
    fix_command: str
    confidence: float = 0.8
    test_cases: List[Dict[str, Any]] = []


class DecisionRequest(BaseModel):
    """Request for strategic decision."""

    current_stage: str
    failure_count: int
    error: Optional[str] = None
    cost_so_far: float
    context: Dict[str, Any] = {}


class MetricReport(BaseModel):
    """Performance metric report."""

    metric_name: str
    value: float
    unit: str
    stage: Optional[str] = None
    metadata: Dict[str, Any] = {}


# Create tables function for Alembic
def create_db_tables(engine):
    """Create all tables - used by Alembic."""
    SQLModel.metadata.create_all(engine)
